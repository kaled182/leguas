"""Hub Financeiro — visão unificada AR/AP/Tesouraria/DRE/Motoristas.

Junta os indicadores-chave de cada módulo numa única página e
constrói uma tabela e um heatmap das movimentações esperadas
nos próximos 30 dias.
"""
import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, Count
from django.shortcuts import render
from django.utils import timezone

from .models import Bill, Imposto
from .services_treasury import treasury_snapshot


def _zero():
    return Decimal("0.00")


def _decimal_default(o):
    if isinstance(o, Decimal):
        return float(o)
    raise TypeError(f"Tipo não serializável: {type(o)}")


def _coletar_movimentos_30d(today: date, horizon: date):
    """Recolhe movimentos esperados entre `today` e `horizon`.

    Devolve lista ordenada por data com:
      { date, type: 'IN'|'OUT', source, label, amount, url, status }
    """
    movs = []

    # ── ENTRADAS ──────────────────────────────────────────────────
    try:
        from settlements.models import PartnerInvoice
        for inv in PartnerInvoice.objects.filter(
            status__in=["PENDING", "OVERDUE", "APPROVED"],
            due_date__lte=horizon,
        ).select_related("partner")[:200]:
            movs.append({
                "date": inv.due_date,
                "type": "IN",
                "source": "AR",
                "label": (
                    f"{inv.partner.name if inv.partner_id else 'Parceiro'} · "
                    f"{inv.invoice_number}"
                ),
                "amount": inv.gross_amount,
                "url": f"/settlements/invoices/{inv.id}/",
                "status": inv.status,
            })
    except Exception:
        pass

    # FleetInvoice — vencimento estimado em periodo_fim + 30d
    try:
        from settlements.models import FleetInvoice
        for fi in FleetInvoice.objects.filter(
            status__in=["CALCULADO", "APROVADO"],
        ).select_related("empresa")[:200]:
            venc = fi.periodo_fim + timedelta(days=30)
            if venc > horizon or venc < today - timedelta(days=60):
                continue
            movs.append({
                "date": venc,
                "type": "IN",
                "source": "FLEET",
                "label": (
                    f"{fi.empresa.nome if fi.empresa_id else 'Frota'} · "
                    f"{fi.numero}"
                ),
                "amount": fi.total_a_receber,
                "url": f"/settlements/fleet-invoices/{fi.id}/",
                "status": fi.status,
            })
    except Exception:
        pass

    # ── SAÍDAS: BILLS ─────────────────────────────────────────────
    bills = Bill.objects.filter(
        status__in=[Bill.STATUS_PENDING, Bill.STATUS_AWAITING, Bill.STATUS_OVERDUE],
        due_date__lte=horizon,
        due_date__gte=today - timedelta(days=60),  # inclui vencidas recentes
    ).select_related("fornecedor")[:300]
    for b in bills:
        movs.append({
            "date": b.due_date,
            "type": "OUT",
            "source": "AP",
            "label": (
                f"{b.fornecedor.name if b.fornecedor_id else b.supplier or 'Fornecedor'} · "
                f"{b.description}"
            ),
            "amount": b.amount_total,
            "url": f"/accounting/contas-a-pagar/{b.id}/",
            "status": b.status,
        })

    # ── SAÍDAS: IMPOSTOS (parcelas + outros) ──────────────────────
    impostos = Imposto.objects.filter(
        Q(status=Imposto.STATUS_PENDENTE) | Q(status=Imposto.STATUS_EM_ATRASO),
        data_vencimento__lte=horizon,
        data_vencimento__gte=today - timedelta(days=60),
    ).filter(
        Q(parent__isnull=False)
        | ~Q(modalidade=Imposto.MODALIDADE_PARCELADO),
    ).select_related("fornecedor", "parent")[:200]
    for i in impostos:
        if i.parent_id:
            label = f"{i.get_tipo_display()} · {i.parent.nome} #{i.parcela_numero}"
            url = f"/accounting/impostos/planos/{i.parent_id}/"
        else:
            label = f"{i.get_tipo_display()} · {i.nome}"
            url = f"/accounting/impostos/{i.id}/editar/"
        movs.append({
            "date": i.data_vencimento,
            "type": "OUT",
            "source": "TAX",
            "label": label,
            "amount": i.valor,
            "url": url,
            "status": i.status,
        })

    # ── SAÍDAS: PRE-FATURAS MOTORISTAS ────────────────────────────
    try:
        from settlements.models import DriverPreInvoice
        # PFs aprovadas/pendentes/calculadas — usar end_date+5d como
        # estimativa de pagamento se não houver data oficial.
        for pf in DriverPreInvoice.objects.filter(
            status__in=["APROVADO", "PENDENTE", "CALCULADO"],
        ).select_related("driver")[:200]:
            est = (pf.end_date or today) + timedelta(days=5)
            if est > horizon or est < today - timedelta(days=60):
                continue
            movs.append({
                "date": est,
                "type": "OUT",
                "source": "DRIVER",
                "label": (
                    f"PF {pf.driver.full_name if pf.driver_id else 'Motorista'} · "
                    f"{pf.start_date}→{pf.end_date}"
                ),
                "amount": pf.total_a_receber,
                "url": f"/settlements/pre-invoices/{pf.id}/",
                "status": pf.status,
            })
    except Exception:
        pass

    movs.sort(key=lambda m: (m["date"], -float(m["amount"] or 0)))
    return movs


def _construir_heatmap(movs, today: date, horizon: date):
    """Agrupa movimentos por dia e devolve uma lista para o heatmap."""
    daily = {}
    d = today
    while d <= horizon:
        daily[d] = {"date": d, "in": _zero(), "out": _zero(), "net": _zero()}
        d += timedelta(days=1)
    for m in movs:
        if m["date"] not in daily:
            continue
        if m["type"] == "IN":
            daily[m["date"]]["in"] += m["amount"] or _zero()
        else:
            daily[m["date"]]["out"] += m["amount"] or _zero()
    for cell in daily.values():
        cell["net"] = cell["in"] - cell["out"]
    return list(daily.values())


@login_required
def hub_financeiro(request):
    today = timezone.localdate()
    horizon = today + timedelta(days=30)
    snap = treasury_snapshot(today)

    movs = _coletar_movimentos_30d(today, horizon)
    heatmap = _construir_heatmap(movs, today, horizon)

    # KPIs extra: vencidos (anteriores a hoje)
    vencidos_in = sum(
        (m["amount"] for m in movs if m["type"] == "IN" and m["date"] < today),
        _zero(),
    )
    vencidos_out = sum(
        (m["amount"] for m in movs if m["type"] == "OUT" and m["date"] < today),
        _zero(),
    )

    # Planos prestacionais — KPI: nº planos com prestações em aberto
    # + Σ das prestações com vencimento no mês corrente.
    from calendar import monthrange as _mr
    first_day_m = today.replace(day=1)
    last_day_m = today.replace(day=_mr(today.year, today.month)[1])
    n_planos_activos = Imposto.objects.filter(
        modalidade=Imposto.MODALIDADE_PARCELADO,
        parent__isnull=True,
        parcelas__status__in=[
            Imposto.STATUS_PENDENTE, Imposto.STATUS_EM_ATRASO,
        ],
    ).distinct().count()
    planos_total_mes = (
        Imposto.objects.filter(
            parent__isnull=False,
            data_vencimento__gte=first_day_m,
            data_vencimento__lte=last_day_m,
            status__in=[
                Imposto.STATUS_PENDENTE, Imposto.STATUS_EM_ATRASO,
            ],
        ).aggregate(s=Sum("valor"))["s"] or _zero()
    )
    planos_n_parcelas_mes = Imposto.objects.filter(
        parent__isnull=False,
        data_vencimento__gte=first_day_m,
        data_vencimento__lte=last_day_m,
        status__in=[Imposto.STATUS_PENDENTE, Imposto.STATUS_EM_ATRASO],
    ).count()

    # Receita do mês corrente (Cainiao) — soft import, falha silenciosa
    receita_mes = _zero()
    custos_mes = _zero()
    try:
        from cainiao.models import CainiaoOperationTask
        from cainiao.models import CainiaoHub
        from django.db.models import F
        primeiro = today.replace(day=1)
        tasks_mes = CainiaoOperationTask.objects.filter(
            status="Delivered",
            operation_time__date__gte=primeiro,
            operation_time__date__lte=today,
        ).select_related("hub")
        receita_mes = sum(
            (
                Decimal(str(t.hub.partner_price or 0))
                for t in tasks_mes if t.hub_id
            ),
            _zero(),
        )
    except Exception:
        pass
    try:
        primeiro = today.replace(day=1)
        custos_mes = (
            Bill.objects.filter(
                issue_date__gte=primeiro,
                issue_date__lte=today,
                status__in=[Bill.STATUS_PAID, Bill.STATUS_PENDING, Bill.STATUS_OVERDUE],
                driver__isnull=True,  # só despesa própria, não passthrough
            ).aggregate(t=Sum("amount_total"))["t"] or _zero()
        )
    except Exception:
        pass

    margem_mes = receita_mes - custos_mes
    margem_pct = (
        (margem_mes / receita_mes * 100) if receita_mes else _zero()
    )

    # Dados para JS (heatmap)
    heatmap_json = json.dumps(
        [
            {
                "date": c["date"].isoformat(),
                "in": c["in"],
                "out": c["out"],
                "net": c["net"],
            }
            for c in heatmap
        ],
        default=_decimal_default,
    )

    context = {
        "today": today,
        "horizon": horizon,
        "snap": snap,
        "movs": movs,
        "heatmap": heatmap,
        "heatmap_json": heatmap_json,
        "vencidos_in": vencidos_in,
        "vencidos_out": vencidos_out,
        "receita_mes": receita_mes,
        "custos_mes": custos_mes,
        "margem_mes": margem_mes,
        "margem_pct": margem_pct,
        "n_movs": len(movs),
        "n_planos_activos": n_planos_activos,
        "planos_total_mes": planos_total_mes,
        "planos_n_parcelas_mes": planos_n_parcelas_mes,
    }
    return render(request, "accounting/hub.html", context)
