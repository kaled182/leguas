from decimal import Decimal
from typing import Optional
from datetime import date
from django.db import models
from django.db.models import Sum
from .models import SettlementRun, CompensationPlan, PerPackageRate, ThresholdBonus

def _pick_plan(driver, client: Optional[str], area: Optional[str], day: date) -> Optional[CompensationPlan]:
    q = (CompensationPlan.objects
         .filter(driver=driver, is_active=True, starts_on__lte=day)
         .filter(models.Q(ends_on__isnull=True) | models.Q(ends_on__gte=day)))
    return (q.filter(client=client, area_code=area).first()
        or q.filter(client=client, area_code__isnull=True).first()
        or q.filter(client__isnull=True, area_code=area).first()
        or q.filter(client__isnull=True, area_code__isnull=True).first())

def _apply_pkg_rates(plan: Optional[CompensationPlan], delivered: int) -> Decimal:
    if not plan or delivered <= 0:
        return Decimal("0")
    rates = list(plan.pkg_rates.all())
    if not rates:
        return Decimal("0")

    # modo progressivo (faixas) se qualquer linha estiver marcada
    if any(r.progressive for r in rates):
        total = Decimal("0")
        for r in rates:
            lower = r.min_delivered
            upper = r.max_delivered if r.max_delivered is not None else delivered
            if delivered <= lower:
                continue
            span = min(delivered, upper) - lower
            if span > 0:
                total += Decimal(r.rate_eur) * Decimal(span)
        return total

    # modo simples (taxa única da faixa que cobre o total)
    for r in rates:
        if (delivered >= r.min_delivered) and (r.max_delivered is None or delivered <= r.max_delivered):
            return Decimal(r.rate_eur) * Decimal(delivered)

    tail = [r for r in rates if r.max_delivered is None]
    if tail:
        return Decimal(tail[-1].rate_eur) * Decimal(delivered)
    return Decimal("0")

def _apply_thresholds(plan: Optional[CompensationPlan], delivered: int) -> Decimal:
    if not plan:
        return Decimal("0")
    bonus = Decimal("0")
    for th in plan.thresholds.all():
        if delivered < th.start_at:
            continue
        if th.kind == ThresholdBonus.Kind.ONCE:
            bonus += Decimal(th.amount_eur)
        else:  # EACH_STEP
            if th.step and delivered >= th.start_at:
                steps = (delivered - th.start_at) // th.step + 1
                bonus += Decimal(th.amount_eur) * steps
    return bonus

def compute_payouts(period_from: date, period_to: date, client: Optional[str] = None, area: Optional[str] = None):
    qs = SettlementRun.objects.filter(run_date__gte=period_from, run_date__lte=period_to)
    if client: qs = qs.filter(client=client)
    if area:   qs = qs.filter(area_code=area)

    agg = (qs.values("driver_id","driver__name")
             .annotate(
                 delivered=Sum("qtd_entregue"),
                 op_gasoleo=Sum("gasoleo"),
                 op_desc_tickets=Sum("desconto_tickets"),
                 op_recl_tickets=Sum("rec_liq_tickets"),
                 op_outros=Sum("outros"),
             ))

    results = []
    for row in agg:
        delivered = int(row["delivered"] or 0)
        sample_run = (SettlementRun.objects
                      .filter(driver_id=row["driver_id"])
                      .order_by("-run_date").first())
        driver = sample_run.driver

        plan = _pick_plan(driver, client, area, period_to)
        base_fixed = Decimal(plan.base_fixed) if plan else Decimal("0")
        gross_by_pkg = _apply_pkg_rates(plan, delivered)
        bonus = _apply_thresholds(plan, delivered)
        gross = base_fixed + gross_by_pkg + bonus

        descontos = sum([Decimal(row[k] or 0) for k in ["op_gasoleo","op_desc_tickets","op_recl_tickets","op_outros"]])
        liquido = gross - descontos

        results.append({
            "driver_id": row["driver_id"],
            "driver": row["driver__name"],
            "period_from": period_from.isoformat(),
            "period_to": period_to.isoformat(),
            "entregues": delivered,
            "bruto_pkg": float(gross_by_pkg),
            "bonus": float(bonus),
            "fixo": float(base_fixed),
            "bruto_total": float(gross),
            "descontos": float(descontos),
            "liquido": float(liquido),
            "media_liq_por_pacote": float(liquido / delivered) if delivered else 0.0,
        })
    return sorted(results, key=lambda x: (-x["liquido"], x["driver"]))
