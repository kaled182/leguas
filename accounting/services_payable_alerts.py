"""Detector de anomalias por linha do A Pagar.

Para cada PF, computa flags úteis ao operador antes de pagar:
  - overlap: outra PF do mesmo motorista cobre dias do período
  - high_value: valor 2× o desvio padrão acima da média histórica
  - open_claims: motorista tem reclamações abertas (DriverClaim status
    != REJECTED) que afectam pagamento e não foram descontadas
  - unincluded_advances: tem PreInvoiceAdvance PENDENTE que devia ter
    sido incluído na PF
"""
from decimal import Decimal
import statistics


def alerts_for_pre_invoice(pf, history_lookback=6):
    """Devolve lista de alertas para uma DriverPreInvoice.

    Args:
        pf: instance de settlements.DriverPreInvoice
        history_lookback: nº de PFs anteriores a considerar para baseline

    Devolve list[dict]:
        { "level": "warn"|"error", "code": str, "label": str, "detail": str }
    """
    from settlements.models import (
        DriverPreInvoice, DriverClaim, PreInvoiceAdvance,
    )
    alerts = []

    # 1. Sobreposição com outra PF do mesmo motorista (não conta a própria)
    overlapping = (
        DriverPreInvoice.objects.filter(
            driver=pf.driver,
            periodo_inicio__lte=pf.periodo_fim,
            periodo_fim__gte=pf.periodo_inicio,
        )
        .exclude(pk=pf.pk)
        .exclude(status="REPROVADO")
        .order_by("-periodo_fim")
    )
    if overlapping.exists():
        first = overlapping.first()
        alerts.append({
            "level": "error",
            "code": "overlap",
            "label": "Sobrepõe outra PF",
            "detail": (
                f"PF {first.numero} ({first.periodo_inicio}→"
                f"{first.periodo_fim}, {first.get_status_display()}) "
                f"cobre dias do mesmo período."
            ),
        })

    # 2. Valor anómalo vs histórico do motorista
    history = list(
        DriverPreInvoice.objects
        .filter(driver=pf.driver, status__in=["PAGO", "APROVADO", "PENDENTE"])
        .exclude(pk=pf.pk)
        .order_by("-periodo_fim")[:history_lookback]
    )
    if len(history) >= 3:
        amounts = [float(p.total_a_receber or 0) for p in history]
        try:
            mean = statistics.mean(amounts)
            stdev = statistics.stdev(amounts) if len(amounts) >= 2 else 0
        except statistics.StatisticsError:
            mean, stdev = 0, 0
        if stdev > 0:
            current = float(pf.total_a_receber or 0)
            deviation = current - mean
            if abs(deviation) >= 2 * stdev:
                direction = "acima" if deviation > 0 else "abaixo"
                alerts.append({
                    "level": "warn",
                    "code": "high_value" if deviation > 0 else "low_value",
                    "label": (
                        f"Valor {direction} do habitual"
                    ),
                    "detail": (
                        f"€{current:.2f} vs média €{mean:.2f} "
                        f"(±2σ = €{2*stdev:.2f}) dos últimos "
                        f"{len(history)} PFs."
                    ),
                })

    # 3. Reclamações abertas (DriverClaim) sobre o motorista
    open_claims = DriverClaim.objects.filter(
        driver=pf.driver,
        status__in=["PENDING", "APPEALED"],
    )
    if open_claims.exists():
        n = open_claims.count()
        total_claim = sum(
            (c.amount or Decimal("0")) for c in open_claims
        )
        alerts.append({
            "level": "warn",
            "code": "open_claims",
            "label": f"{n} reclamação(ões) aberta(s)",
            "detail": (
                f"€{total_claim:.2f} a descontar quando aprovadas — "
                "verifica se devem entrar nesta PF."
            ),
        })

    # 4. Adiantamentos pendentes não incluídos
    unincluded = PreInvoiceAdvance.objects.filter(
        driver=pf.driver,
        status="PENDENTE",
        data__gte=pf.periodo_inicio,
        data__lte=pf.periodo_fim,
    )
    if unincluded.exists():
        n = unincluded.count()
        total_adv = sum(
            (a.valor or Decimal("0")) for a in unincluded
        )
        alerts.append({
            "level": "warn",
            "code": "unincluded_advances",
            "label": f"{n} adiantamento(s) PENDENTE no período",
            "detail": (
                f"€{total_adv:.2f} ainda não incluídos nesta PF. "
                "Considera adicionar antes de pagar."
            ),
        })

    return alerts
