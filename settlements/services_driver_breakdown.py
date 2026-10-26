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
    from .services_same_door import is_same_door_active, sorted_same_door_groups

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

    counts["pudo"] = len(pudo_tasks)
    counts["door"] = len(door_delivered)
    counts["same_door"] = len(extra_ids)
    counts["door_normal"] = counts["door"] - counts["same_door"]
    return counts, extra_ids, pudo_tasks, door_delivered, groups


def driver_breakdown(driver, date_from, date_to, partner=None):
    """Total do motorista no período, dividido por tipo e por dia."""
    from core.finance import resolve_driver_price
    from core.models import Partner
    from drivers_app.portal_views import _driver_base_queryset

    from .models import PackagePriceOverride
    from .services_pudo import compute_pudo_payment, pudo_key

    if partner is None:
        partner = Partner.objects.filter(name__iexact="CAINIAO").first()

    tasks = list(
        _driver_base_queryset(driver, date_from, date_to).only(
            "id", "waybill_number", "task_date", "task_status",
            "delivery_type", "delivery_time", "detailed_address", "zip_code",
            "receiver_latitude", "receiver_longitude", "courier_name",
            "task_group_order",
        )
    )
    counts, extra_ids, pudo_tasks, door_delivered, sd_groups = split_counts(tasks, partner)

    # ─── Valor estimado (mesmas regras da pré-fatura) ───
    base_price, _src = resolve_driver_price(driver, partner)
    base_price = base_price or Decimal("0")
    # Preço por CP (valor negociado → tarifa do CP → base), como na PF.
    from drivers_app.services_cp_pricing import CpPricer
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
    for t in door_delivered:
        if t.waybill_number in overrides:
            amount_door_normal += overrides[t.waybill_number]
        elif t.id in extra_ids:
            amount_same_door += sd_price
            n_same_door_paid += 1
        else:
            unit, _src, _cp = pricer.price(t.zip_code)
            amount_door_normal += unit

    pudo_groups = defaultdict(list)
    for t in pudo_tasks:
        pudo_groups[(t.task_date, pudo_key(t) or ("solo", t.id))].append(t)
    amount_pudo = Decimal("0")
    pudo_amount_by_day = defaultdict(Decimal)
    for (day, _k), g in pudo_groups.items():
        a = compute_pudo_payment(len(g), partner)
        amount_pudo += a
        pudo_amount_by_day[day] += a

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

    amount_total = amount_door_normal + amount_same_door + amount_pudo
    return {
        "totals": counts,
        "days": days,
        "n_days": sum(1 for d in days if d["delivered"]),
        "base_price": base_price,
        "same_door_price": sd_price,
        "same_door_active": bool(partner and partner.same_door_enabled),
        "same_door_groups": same_door_groups,
        "amounts": {
            "door_normal": amount_door_normal,
            "same_door": amount_same_door,
            "pudo": amount_pudo,
            "total": amount_total,
            # Diferença paga a menos pela regra mesma porta
            "same_door_saving": (base_price - sd_price) * n_same_door_paid,
        },
    }
