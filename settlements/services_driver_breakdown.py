"""Resumo das entregas de um motorista: total primeiro, depois a divisão.

Fonte única para a pré-fatura, o portal do motorista e o dashboard do
parceiro, para que todos mostrem os mesmos números:

    total entregue = porta normal + mesma porta (adicionais) + PUDO

`driver_breakdown(driver, date_from, date_to)` devolve os totais, o valor
estimado (mesmas regras de preço da pré-fatura) e uma linha por dia.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal


def _empty_counts():
    return {
        "delivered": 0, "door": 0, "door_normal": 0, "same_door": 0,
        "pudo": 0, "failures": 0, "total": 0,
    }


def split_counts(tasks, partner):
    """Conta as tasks por tipo. `tasks` são objectos com task_status,
    delivery_type, task_date, etc. Devolve (counts, extra_ids, pudo_tasks,
    door_delivered, same_door_groups)."""
    from .services_same_door import (
        is_same_door_active, same_door_review_groups, sorted_same_door_groups,
    )

    pudo_active = bool(partner and getattr(partner, "pudo_enabled", False))
    counts = _empty_counts()
    door_delivered, pudo_tasks = [], []
    for t in tasks:
        counts["total"] += 1
        if t.task_status == "Attempt Failure":
            counts["failures"] += 1
        if t.task_status != "Delivered":
            continue
        counts["delivered"] += 1
        if pudo_active and (t.delivery_type or "").upper().strip() == "PUDO":
            pudo_tasks.append(t)
        else:
            door_delivered.append(t)

    extra_ids, groups = set(), []
    if is_same_door_active(partner):
        start = getattr(partner, "same_door_start_date", None)
        eligible = [t for t in door_delivered if not start or t.task_date >= start]
        groups = sorted_same_door_groups(eligible)
        extra_ids = {t.id for g in groups for t in g[1:]}
        counts["same_door_review"] = same_door_review_groups(eligible)

    counts["pudo"] = len(pudo_tasks)
    counts["door"] = len(door_delivered)
    counts["same_door"] = len(extra_ids)
    counts["door_normal"] = counts["door"] - counts["same_door"]
    return counts, extra_ids, pudo_tasks, door_delivered, groups


TASK_FIELDS = (
    "id", "waybill_number", "task_date", "task_status",
    "delivery_type", "delivery_time", "detailed_address", "zip_code",
    "receiver_latitude", "receiver_longitude", "courier_name",
    "task_group_order",
)


def price_tasks(driver, tasks, date_from, date_to, partner):
    """Valor das tasks do motorista com as regras da pré-fatura.

    Ordem por pacote à porta: override de preço → mesma porta (valor do
    parceiro) → preço por CP (CpPricer). PUDO: fórmula por ponto e dia.
    Fonte única para o resumo do motorista e para o lote da frota (FF).
    """
    from core.finance import resolve_driver_price
    from drivers_app.services_cp_pricing import CpPricer

    from .models import PackagePriceOverride
    from .services_pudo import compute_pudo_payment, pudo_key

    counts, extra_ids, pudo_tasks, door_delivered, sd_groups = split_counts(tasks, partner)
    base_price, base_src = resolve_driver_price(driver, partner)
    base_price = base_price or Decimal("0")
    pricer = CpPricer(driver, partner, date_from, date_to)
    sd_price = getattr(partner, "same_door_additional_price", None) or Decimal("0")
    overrides = dict(
        PackagePriceOverride.objects.filter(
            task_date__range=(date_from, date_to),
            waybill_number__in=[t.waybill_number for t in door_delivered],
        ).values_list("waybill_number", "price")
    )
    amount_door_normal = Decimal("0")
    amount_same_door = Decimal("0")
    n_same_door_paid = 0
    n_cp_negotiated = 0
    for t in door_delivered:
        # Mesma porta primeiro: o preço fixo por guia só substitui o preço da porta.
        if t.id in extra_ids:
            amount_same_door += sd_price
            n_same_door_paid += 1
        elif t.waybill_number in overrides:
            amount_door_normal += overrides[t.waybill_number]
        else:
            unit, src, _cp = pricer.price(t.zip_code)
            amount_door_normal += unit
            if src == "negociado":
                n_cp_negotiated += 1

    pudo_groups = defaultdict(list)
    for t in pudo_tasks:
        pudo_groups[(t.task_date, pudo_key(t) or ("solo", t.id))].append(t)
    amount_pudo = Decimal("0")
    pudo_amount_by_day = defaultdict(Decimal)
    for (day, _k), g in pudo_groups.items():
        a = compute_pudo_payment(len(g), partner)
        amount_pudo += a
        pudo_amount_by_day[day] += a

    n_door_paid = len(door_delivered) - n_same_door_paid
    return {
        "counts": counts,
        "extra_ids": extra_ids,
        "pudo_tasks": pudo_tasks,
        "door_delivered": door_delivered,
        "sd_groups": sd_groups,
        "base_price": base_price,
        "base_src": base_src,
        "cp_active": pricer.active,
        "n_cp_negotiated": n_cp_negotiated,
        "sd_price": sd_price,
        "n_same_door_paid": n_same_door_paid,
        "door_avg_price": (
            (amount_door_normal / n_door_paid).quantize(Decimal("0.001"))
            if n_door_paid else base_price
        ),
        "amount_door_normal": amount_door_normal,
        "amount_same_door": amount_same_door,
        "amount_pudo": amount_pudo,
        "pudo_amount_by_day": pudo_amount_by_day,
        "amount_total": amount_door_normal + amount_same_door + amount_pudo,
    }


def driver_breakdown(driver, date_from, date_to, partner=None):
    """Total do motorista no período, dividido por tipo e por dia."""
    from core.models import Partner
    from drivers_app.portal_views import _driver_base_queryset

    from .services_same_door import max_spread_m

    if partner is None:
        partner = Partner.objects.filter(name__iexact="CAINIAO").first()

    tasks = list(_driver_base_queryset(driver, date_from, date_to).only(*TASK_FIELDS))
    p = price_tasks(driver, tasks, date_from, date_to, partner)
    counts, extra_ids = p["counts"], p["extra_ids"]
    pudo_tasks, door_delivered, sd_groups = p["pudo_tasks"], p["door_delivered"], p["sd_groups"]
    base_price, sd_price = p["base_price"], p["sd_price"]
    n_same_door_paid = p["n_same_door_paid"]
    amount_door_normal = p["amount_door_normal"]
    amount_same_door = p["amount_same_door"]
    amount_pudo = p["amount_pudo"]
    pudo_amount_by_day = p["pudo_amount_by_day"]

    # ─── Por dia ───
    from django.utils import timezone

    by_day = defaultdict(_empty_counts)
    first_last = {}  # dia → (1ª entrega, última entrega), hora local
    for t in tasks:
        d = by_day[t.task_date]
        d["total"] += 1
        if t.task_status == "Attempt Failure":
            d["failures"] += 1
        if t.task_status != "Delivered":
            continue
        d["delivered"] += 1
        if t.delivery_time:
            ts = timezone.localtime(t.delivery_time)
            lo, hi = first_last.get(t.task_date, (ts, ts))
            first_last[t.task_date] = (min(lo, ts), max(hi, ts))
    for t in pudo_tasks:
        by_day[t.task_date]["pudo"] += 1
    for t in door_delivered:
        d = by_day[t.task_date]
        d["door"] += 1
        if t.id in extra_ids:
            d["same_door"] += 1
        else:
            d["door_normal"] += 1
    days = [
        {"date": day, **c, "pudo_amount": pudo_amount_by_day.get(day, Decimal("0")),
         "first": first_last.get(day, (None, None))[0],
         "last": first_last.get(day, (None, None))[1]}
        for day, c in sorted(by_day.items())
    ]
    same_door_groups = [
        {
            "date": g[0].task_date,
            "address": (g[0].detailed_address or "").strip(),
            "zip_code": g[0].zip_code or "",
            "n": len(g),
            "waybills": [t.waybill_number for t in g],
        }
        for g in sd_groups
    ]

    # Mesma morada mas pacotes a mais de 300 m: não juntam, para revisão.
    same_door_review = [
        {
            "date": g[0].task_date,
            "address": (g[0].detailed_address or "").strip(),
            "zip_code": g[0].zip_code or "",
            "n": len(g),
            "spread_m": round(max_spread_m(g)),
            "waybills": [t.waybill_number for t in g],
        }
        for g in counts.pop("same_door_review", [])
    ]

    amount_total = amount_door_normal + amount_same_door + amount_pudo
    return {
        "totals": counts,
        "days": days,
        "n_days": sum(1 for d in days if d["delivered"]),
        "base_price": base_price,
        # Preço médio à porta (com preço por CP, varia por pacote).
        "door_avg_price": p["door_avg_price"],
        "cp_pricing": p["cp_active"],
        "same_door_price": sd_price,
        "same_door_active": bool(partner and partner.same_door_enabled),
        "same_door_groups": same_door_groups,
        "same_door_review": same_door_review,
        "amounts": {
            "door_normal": amount_door_normal,
            "same_door": amount_same_door,
            "pudo": amount_pudo,
            "total": amount_total,
            # Diferença paga a menos pela regra mesma porta
            "same_door_saving": (base_price - sd_price) * n_same_door_paid,
        },
    }
