"""Dashboard executivo — resumo mensal imprimível em A4.

Acessível em `/accounting/exec/?month=YYYY-MM` (default: mês passado).
"""
import json
from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import render
from django.utils import timezone

from .models import Bill, Imposto
from .views import _compute_cc_evolution, _compute_dre_metrics
from .services_treasury import treasury_snapshot


def _zero():
    return Decimal("0.00")


def _resolve_month(request):
    """Resolve param ?month=YYYY-MM → (date_from, date_to). Default = mês passado."""
    raw = (request.GET.get("month") or "").strip()
    today = timezone.localdate()
    if raw and len(raw) == 7 and raw[4] == "-":
        try:
            y, m = int(raw[:4]), int(raw[5:7])
            d1 = date(y, m, 1)
        except (ValueError, IndexError):
            d1 = date(today.year, today.month, 1)
    else:
        # Mês passado por defeito (relatório executivo mensal típico)
        y, m = today.year, today.month - 1
        if m < 1:
            m = 12
            y -= 1
        d1 = date(y, m, 1)
    last = monthrange(d1.year, d1.month)[1]
    d2 = date(d1.year, d1.month, last)
    return d1, d2


@login_required
def executive_dashboard(request):
    date_from, date_to = _resolve_month(request)
    cur = _compute_dre_metrics(date_from, date_to)
    snap = treasury_snapshot(timezone.localdate())

    # Top fornecedores por gasto (Bills não-passthrough, no mês)
    top_suppliers = list(
        Bill.objects.company_only()
        .filter(
            issue_date__range=(date_from, date_to),
        ).exclude(status=Bill.STATUS_CANCELLED)
        .values("fornecedor__name", "supplier")
        .annotate(total=Sum("amount_total"), n=Count("id"))
        .order_by("-total")[:5]
    )
    for r in top_suppliers:
        r["name"] = r["fornecedor__name"] or r["supplier"] or "—"

    # Top categorias por gasto
    top_categories = list(
        Bill.objects.company_only()
        .filter(
            issue_date__range=(date_from, date_to),
        ).exclude(status=Bill.STATUS_CANCELLED)
        .values("category__name", "category__nature")
        .annotate(total=Sum("amount_total"), n=Count("id"))
        .order_by("-total")[:5]
    )

    # Vencidos acumulados
    today = timezone.localdate()
    overdue_bills = (
        Bill.objects.filter(
            status__in=[Bill.STATUS_PENDING, Bill.STATUS_OVERDUE],
            due_date__lt=today,
        ).aggregate(t=Sum("amount_total"))["t"] or _zero()
    )
    overdue_taxes = (
        Imposto.objects.filter(
            status__in=[
                Imposto.STATUS_PENDENTE, Imposto.STATUS_EM_ATRASO,
            ],
            data_vencimento__lt=today,
        )
        .filter(parent__isnull=False)
        .aggregate(t=Sum("valor"))["t"] or _zero()
    )

    # Evolução 6 meses (acaba no fim do mês reportado)
    evol = _compute_cc_evolution(date_to, n_months=6)

    # KPIs principais
    margem_bruta_pct = (
        float(cur["margem_bruta"] / cur["total_revenue"] * 100)
        if cur["total_revenue"] else 0
    )
    ebitda_pct = (
        float(cur["ebitda"] / cur["total_revenue"] * 100)
        if cur["total_revenue"] else 0
    )
    res_liq_pct = (
        float(cur["resultado_liquido"] / cur["total_revenue"] * 100)
        if cur["total_revenue"] else 0
    )

    # Dados para chart de receita por hub
    hub_labels = [h["hub_name"] for h in cur["revenues_by_hub"]]
    hub_data = [float(h["revenue"]) for h in cur["revenues_by_hub"]]

    # Linha de evolução resultado líquido nos últimos 6 meses
    # Reutilizamos cc_evolution para ter os meses, mas calculamos métricas
    # do DRE por mês.
    six_month_lines = []
    for mi in evol["months"]:
        m_metrics = _compute_dre_metrics(mi["from"], mi["to"])
        six_month_lines.append({
            "label": mi["label"],
            "revenue": float(m_metrics["total_revenue"]),
            "ebitda": float(m_metrics["ebitda"]),
            "resultado_liquido": float(m_metrics["resultado_liquido"]),
        })

    context = {
        "date_from": date_from,
        "date_to": date_to,
        "month_label": f"{date_from:%B de %Y}".title(),
        "generated_at": timezone.now(),
        # KPIs
        "total_revenue": cur["total_revenue"],
        "margem_bruta": cur["margem_bruta"],
        "margem_bruta_pct": margem_bruta_pct,
        "ebitda": cur["ebitda"],
        "ebitda_pct": ebitda_pct,
        "resultado_liquido": cur["resultado_liquido"],
        "resultado_pct": res_liq_pct,
        "total_direct_op": cur["total_direct_op"],
        "total_driver_cost": cur["total_driver_cost"],
        "total_fixo": cur["total_fixo"],
        "total_variavel": cur["total_variavel"],
        # Tesouraria
        "saldo_bancario": snap["saldo_bancario"],
        "saldo_projectado_30d": snap["saldo_projectado_30d"],
        "overdue_total": overdue_bills + overdue_taxes,
        # Top listas
        "top_suppliers": top_suppliers,
        "top_categories": top_categories,
        "revenues_by_hub": cur["revenues_by_hub"],
        # Chart data
        "hub_labels_json": json.dumps(hub_labels),
        "hub_data_json": json.dumps(hub_data),
        "six_month_lines": six_month_lines,
        "six_month_labels_json": json.dumps(
            [m["label"] for m in six_month_lines]
        ),
        "six_month_revenue_json": json.dumps(
            [m["revenue"] for m in six_month_lines]
        ),
        "six_month_ebitda_json": json.dumps(
            [m["ebitda"] for m in six_month_lines]
        ),
        "six_month_resliq_json": json.dumps(
            [m["resultado_liquido"] for m in six_month_lines]
        ),
        # Por centro de custo (linha resumida)
        "by_cost_center": cur["by_cost_center"],
    }
    return render(request, "accounting/executive_dashboard.html", context)
