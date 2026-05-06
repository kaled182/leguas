"""Saúde do motorista — vista consolidada para decisão de pagamento.

Computa:
  - Tendência últimos N meses (entregas + valor pago)
  - Reclamações abertas (DriverClaim)
  - Adiantamentos pendentes
  - Estatísticas históricas (média, desvio, total pago)
  - Alertas (reuso de services_payable_alerts)
"""
from collections import OrderedDict
from datetime import date, timedelta
from decimal import Decimal


def driver_health_snapshot(pf, months_back=6):
    """Devolve dict completo para o modal Saúde do Motorista.

    Args:
        pf: instance DriverPreInvoice (a PF que o operador está a rever)
        months_back: profundidade do histórico

    Returns:
        {
            "driver": {id, nome, apelido, courier_id_cainiao},
            "current_pf": {numero, periodo, total, status},
            "history": [
                {month_label, year, month, paid_count, paid_total,
                 pending_count, pending_total, delivered}
                ...
            ],
            "stats": {avg, stdev, total_paid_lifetime, count_lifetime},
            "open_claims": [...],
            "pending_advances": {included: [...], not_included: [...]},
            "alerts": [...] (de services_payable_alerts),
        }
    """
    from .services_payable_alerts import alerts_for_pre_invoice
    from settlements.models import (
        DriverPreInvoice, DriverClaim, PreInvoiceAdvance,
        CainiaoOperationTask,
    )
    import statistics

    driver = pf.driver
    today = date.today()

    # --- Histórico mensal de PFs ---
    start = today.replace(day=1) - timedelta(days=30 * months_back)
    pfs = DriverPreInvoice.objects.filter(
        driver=driver, periodo_inicio__gte=start,
    ).order_by("periodo_inicio")
    history = OrderedDict()
    for i in range(months_back):
        # Mês alvo: months_back-i meses atrás
        target = today.replace(day=1) - timedelta(days=30 * (months_back - 1 - i))
        key = (target.year, target.month)
        history[key] = {
            "year": target.year,
            "month": target.month,
            "month_label": target.strftime("%b/%y"),
            "paid_count": 0, "paid_total": Decimal("0"),
            "pending_count": 0, "pending_total": Decimal("0"),
            "delivered": 0,
        }
    for p in pfs:
        key = (p.periodo_inicio.year, p.periodo_inicio.month)
        if key not in history:
            continue
        if p.status == "PAGO":
            history[key]["paid_count"] += 1
            history[key]["paid_total"] += p.total_a_receber or Decimal("0")
        elif p.status in ("APROVADO", "PENDENTE", "CALCULADO"):
            history[key]["pending_count"] += 1
            history[key]["pending_total"] += p.total_a_receber or Decimal("0")

    # --- Entregas Cainiao por mês (delivered count) ---
    if driver.courier_id_cainiao or driver.apelido:
        from django.db.models import Q, Count
        from django.db.models.functions import TruncMonth
        q = Q()
        if driver.courier_id_cainiao:
            q |= Q(courier_id_cainiao=driver.courier_id_cainiao)
        if driver.apelido:
            q |= Q(courier_name=driver.apelido)
        deliv_by_month = (
            CainiaoOperationTask.objects
            .filter(q, task_status="Delivered", task_date__gte=start)
            .annotate(m=TruncMonth("task_date"))
            .values("m").annotate(c=Count("id"))
        )
        for row in deliv_by_month:
            d = row["m"]
            key = (d.year, d.month)
            if key in history:
                history[key]["delivered"] = row["c"]

    # --- Estatísticas globais (todas as PFs pagas) ---
    paid_pfs = DriverPreInvoice.objects.filter(
        driver=driver, status="PAGO",
    )
    total_paid_lifetime = sum(
        (p.total_a_receber or Decimal("0")) for p in paid_pfs
    )
    count_lifetime = paid_pfs.count()
    amounts = [float(p.total_a_receber or 0) for p in paid_pfs]
    try:
        avg = statistics.mean(amounts) if amounts else 0
        stdev = statistics.stdev(amounts) if len(amounts) >= 2 else 0
    except statistics.StatisticsError:
        avg, stdev = 0, 0

    # --- Reclamações abertas ---
    open_claims = []
    for c in DriverClaim.objects.filter(
        driver=driver, status__in=["PENDING", "APPEALED"],
    ).order_by("-occurred_at")[:10]:
        open_claims.append({
            "id": c.id,
            "claim_type": c.get_claim_type_display() if hasattr(c, "get_claim_type_display") else c.claim_type,
            "amount": float(c.amount or 0),
            "status": c.status,
            "occurred_at": c.occurred_at.isoformat() if c.occurred_at else "",
            "description": (c.description or "")[:100],
            "waybill": c.waybill_number or "",
        })

    # --- Adiantamentos pendentes ---
    advances_included = list(
        PreInvoiceAdvance.objects.filter(
            driver=driver, pre_invoice=pf, status="INCLUIDO_PF",
        ).values("id", "tipo", "valor", "data", "descricao")
    )
    advances_not_included = list(
        PreInvoiceAdvance.objects.filter(
            driver=driver, status="PENDENTE",
            data__gte=pf.periodo_inicio, data__lte=pf.periodo_fim,
        ).values("id", "tipo", "valor", "data", "descricao")
    )

    # Convert Decimal/date to JSON-safe
    def _safe(items):
        out = []
        for it in items:
            out.append({
                "id": it["id"], "tipo": it["tipo"],
                "valor": float(it["valor"] or 0),
                "data": it["data"].isoformat() if it["data"] else "",
                "descricao": (it["descricao"] or "")[:80],
            })
        return out

    return {
        "driver": {
            "id": driver.id,
            "nome": driver.nome_completo,
            "apelido": driver.apelido or "",
            "courier_id_cainiao": driver.courier_id_cainiao or "",
        },
        "current_pf": {
            "id": pf.id,
            "numero": pf.numero,
            "periodo_inicio": pf.periodo_inicio.isoformat(),
            "periodo_fim": pf.periodo_fim.isoformat(),
            "total": float(pf.total_a_receber or 0),
            "status": pf.status,
            "status_display": pf.get_status_display(),
        },
        "history": [
            {**v, "paid_total": float(v["paid_total"]),
             "pending_total": float(v["pending_total"])}
            for v in history.values()
        ],
        "stats": {
            "avg": round(avg, 2),
            "stdev": round(stdev, 2),
            "total_paid_lifetime": float(total_paid_lifetime),
            "count_lifetime": count_lifetime,
        },
        "open_claims": open_claims,
        "advances": {
            "included": _safe(advances_included),
            "not_included": _safe(advances_not_included),
        },
        "alerts": alerts_for_pre_invoice(pf),
    }
