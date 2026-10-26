"""Pagamentos a Motoristas — agenda por regime (semanal / mensal).

Mostra o que há a pagar em cada data, o que está atrasado e o que falta
aprovar. Pagar continua na caixa "A pagar" (accounting.payables_inbox),
que exige comprovativo e confere o valor.
"""
import csv
from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import DriverProfile
from .services_payments import expected_for_pf, is_weekly_period, next_weekday, pf_amount


def _is_admin(u):
    return u.is_authenticated and (u.is_staff or u.is_superuser)


admin_required = user_passes_test(_is_admin, login_url="/auth/login/")

OPEN_STATUSES = ("CALCULADO", "APROVADO", "PENDENTE", "CONTESTADO")
TABS = [
    ("proximo", "Próximo pagamento"),
    ("atraso", "Em atraso"),
    ("aprovar", "Por aprovar"),
    ("aberto", "Todos em aberto"),
    ("negativas", "Saldo devedor"),
    ("pagos", "Pagos (30 dias)"),
]
WEEKS_AHEAD = 8


def _primary_hubs():
    """{driver_id: nome do hub principal}."""
    from .models import DriverHubAssignment

    out = {}
    for did, name in DriverHubAssignment.objects.order_by("-is_primary").values_list(
        "driver_id", "hub__name",
    ):
        out.setdefault(did, name)
    return out


def _estimated_unbilled(today, days=60):
    """Produção ainda sem PF: entregas desde o fim da última PF × preço.

    Estimativa: usa o preço por pacote do motorista (motorista → frota →
    parceiro), não a tarifa por CP. Devolve (valor, n.º motoristas).
    """
    from core.finance import resolve_driver_price
    from core.models import Partner
    from settlements.models import DriverPreInvoice

    from .services_activity import daily_activity

    start = today - timedelta(days=days)
    activity = daily_activity(start, today)
    if not activity:
        return Decimal("0"), 0
    last_end = {}
    for did, fim in DriverPreInvoice.objects.exclude(status="REPROVADO").values_list(
        "driver_id", "periodo_fim",
    ):
        if fim and (did not in last_end or fim > last_end[did]):
            last_end[did] = fim
    cainiao = Partner.objects.filter(name__iexact="CAINIAO").first()
    drivers = DriverProfile.objects.select_related("empresa_parceira").in_bulk(list(activity))
    total, n = Decimal("0"), 0
    for did, days_map in activity.items():
        d = drivers.get(did)
        if not d:
            continue
        since = last_end.get(did)
        delivered = sum(v for day, v in days_map.items() if not since or day > since)
        if delivered:
            price, _src = resolve_driver_price(d, cainiao)
            total += Decimal(delivered) * price
            n += 1
    return total.quantize(Decimal("0.01")), n


@admin_required
def payments_dashboard(request):
    from settlements.models import DriverPreInvoice

    today = timezone.localdate()
    tab = request.GET.get("tab", "proximo")
    if tab not in dict(TABS):
        tab = "proximo"
    regime_f = request.GET.get("regime", "")
    hub_f = request.GET.get("hub", "")

    # PF sem data prevista (anteriores a esta funcionalidade): calcular e gravar.
    for pf in DriverPreInvoice.objects.filter(
        data_prevista_pagamento__isnull=True, status__in=OPEN_STATUSES,
    ).select_related("driver"):
        d = expected_for_pf(pf)
        if d:
            DriverPreInvoice.objects.filter(pk=pf.pk).update(data_prevista_pagamento=d)

    hubs = _primary_hubs()
    next_payday = next_weekday(today, 1)
    open_pfs = list(
        DriverPreInvoice.objects.filter(status__in=OPEN_STATUSES)
        .select_related("driver")
        .order_by("data_prevista_pagamento", "driver__nome_completo")
    )
    for pf in open_pfs:
        pf.amount = pf_amount(pf)
        pf.kind = "SEMANAL" if is_weekly_period(pf.periodo_inicio, pf.periodo_fim) else "MENSAL"
        pf.hub = hubs.get(pf.driver_id, "")
        pf.due = pf.data_prevista_pagamento
        pf.late_days = (today - pf.due).days if pf.due and pf.due < today else 0

    def total(rows):
        return sum((r.amount for r in rows), Decimal("0"))

    # Só sai dinheiro quando o valor é positivo. PF negativas = o motorista
    # deve à empresa (adiantamentos/perdas maiores do que a produção).
    payable = [p for p in open_pfs if p.status != "CONTESTADO" and p.amount > 0]
    debtors = [p for p in open_pfs if p.amount < 0]
    upcoming_week = [p for p in payable if p.due and today <= p.due <= next_payday]
    overdue = [p for p in payable if p.due and p.due < today]
    to_approve = [p for p in open_pfs if p.status == "CALCULADO"]
    monthly_future = sorted(
        {p.due for p in payable if p.kind == "MENSAL" and p.due and p.due >= today},
    )
    next_monthly = monthly_future[0] if monthly_future else None
    next_monthly_rows = [p for p in payable if p.kind == "MENSAL" and p.due == next_monthly]

    month_start = today.replace(day=1)
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
    paid_qs = DriverPreInvoice.objects.filter(status="PAGO")
    paid_month = paid_qs.filter(data_pagamento__gte=month_start).aggregate(
        s=Sum("total_a_receber"), v=Sum("vat_amount"))
    paid_prev = paid_qs.filter(
        data_pagamento__gte=prev_month_start, data_pagamento__lt=month_start,
    ).aggregate(s=Sum("total_a_receber"), v=Sum("vat_amount"))

    def _paid(a):
        return (a["s"] or Decimal("0")) + (a["v"] or Decimal("0"))

    unbilled, unbilled_n = _estimated_unbilled(today)

    active = DriverProfile.objects.filter(status="ATIVO", inactive_since__isnull=True)
    regime_counts = Counter(active.values_list("payment_regime", flat=True))
    from .central_views import _contract_driver_ids

    contract_ids = _contract_driver_ids()
    alerts = {
        "sem_regime": active.filter(payment_regime="").count(),
        "sem_iban": active.filter(iban="").count(),
        "sem_contrato": active.exclude(id__in=contract_ids).count(),
        "sem_hub": active.filter(hub_assignments__isnull=True).count(),
        "contestadas": sum(1 for p in open_pfs if p.status == "CONTESTADO"),
        "negativas": len(debtors),
        "negativas_total": total(debtors),
    }

    kpis = {
        "next_payday": next_payday,
        "week_total": total(upcoming_week), "week_n": len({p.driver_id for p in upcoming_week}),
        "next_monthly": next_monthly,
        "monthly_total": total(next_monthly_rows), "monthly_n": len(next_monthly_rows),
        "overdue_total": total(overdue), "overdue_n": len(overdue),
        "approve_total": total([p for p in to_approve if p.amount > 0]), "approve_n": len(to_approve),
        "unbilled": unbilled, "unbilled_n": unbilled_n,
        "paid_month": _paid(paid_month), "paid_prev": _paid(paid_prev),
        "open_total": total(payable),
    }

    # ─── Gráficos ───
    week0 = today - timedelta(days=today.weekday())
    week_labels = ["Em atraso"] + [
        (week0 + timedelta(weeks=i)).strftime("%d/%m") for i in range(WEEKS_AHEAD)
    ] + ["Depois"]
    by_week = {"SEMANAL": [0.0] * len(week_labels), "MENSAL": [0.0] * len(week_labels)}
    for p in payable:
        if not p.due:
            continue
        if p.due < today:
            i = 0
        else:
            w = (p.due - week0).days // 7
            i = 1 + w if w < WEEKS_AHEAD else len(week_labels) - 1
        by_week[p.kind][i] += float(p.amount)

    paid_months = []
    for k in range(11, -1, -1):
        y, mth = month_start.year, month_start.month - k
        while mth <= 0:
            y, mth = y - 1, mth + 12
        m_start = month_start.replace(year=y, month=mth)
        m_end = (m_start + timedelta(days=32)).replace(day=1)
        a = paid_qs.filter(data_pagamento__gte=m_start, data_pagamento__lt=m_end).aggregate(
            s=Sum("total_a_receber"), v=Sum("vat_amount"))
        paid_months.append({"label": m_start.strftime("%m/%y"), "v": float(_paid(a))})

    by_hub = defaultdict(float)
    for p in payable:
        by_hub[p.hub or "Sem hub"] += float(p.amount)

    charts = {
        "weeks": week_labels,
        "weekly": [round(x, 2) for x in by_week["SEMANAL"]],
        "monthly": [round(x, 2) for x in by_week["MENSAL"]],
        "paid": paid_months,
        "regimes": [
            {"label": "Mensal", "n": regime_counts.get("MENSAL", 0)},
            {"label": "Semanal", "n": regime_counts.get("SEMANAL", 0)},
            {"label": "Por definir", "n": regime_counts.get("", 0)},
        ],
        "hubs": sorted(
            ({"label": k, "v": round(v, 2)} for k, v in by_hub.items()),
            key=lambda r: -r["v"],
        ),
    }

    # ─── Tabela ───
    if tab == "proximo":
        rows = upcoming_week + [p for p in next_monthly_rows if p not in upcoming_week]
    elif tab == "atraso":
        rows = overdue
    elif tab == "aprovar":
        rows = to_approve
    elif tab == "aberto":
        rows = open_pfs
    elif tab == "negativas":
        rows = debtors
    else:
        rows = list(
            paid_qs.filter(data_pagamento__gte=today - timedelta(days=30))
            .select_related("driver").order_by("-data_pagamento")
        )
        for pf in rows:
            pf.amount = pf_amount(pf)
            pf.kind = "SEMANAL" if is_weekly_period(pf.periodo_inicio, pf.periodo_fim) else "MENSAL"
            pf.hub = hubs.get(pf.driver_id, "")
            pf.due = pf.data_prevista_pagamento
            pf.late_days = 0
    if regime_f:
        rows = [r for r in rows if r.kind == regime_f]
    if hub_f:
        rows = [r for r in rows if (r.hub or "Sem hub") == hub_f]

    tab_counts = {
        "proximo": len(upcoming_week) + len([p for p in next_monthly_rows if p not in upcoming_week]),
        "atraso": len(overdue), "aprovar": len(to_approve), "aberto": len(open_pfs),
        "negativas": len(debtors),
    }

    return render(request, "drivers_app/admin/payments.html", {
        "kpis": kpis,
        "alerts": alerts,
        "charts": charts,
        "rows": rows,
        "rows_total": total(rows),
        "tabs": [(k, label, tab_counts.get(k)) for k, label in TABS],
        "tab": tab,
        "regime_filter": regime_f,
        "hub_filter": hub_f,
        "hub_names": sorted({p.hub or "Sem hub" for p in open_pfs}),
        "today": today,
    })


@admin_required
@require_POST
def payments_bulk(request):
    """Ações em lote: aprovar (CALCULADO → APROVADO) e exportar CSV."""
    from settlements.models import DriverPreInvoice

    ids = [int(x) for x in request.POST.getlist("ids") if x.isdigit()]
    action = request.POST.get("action", "")
    back = request.POST.get("next") or "drivers_app:payments_dashboard"
    if not back.startswith("/"):
        back = "drivers_app:payments_dashboard"
    if not ids:
        messages.error(request, "Selecione pelo menos uma pré-fatura.")
        return redirect(back)

    qs = DriverPreInvoice.objects.filter(id__in=ids).select_related("driver")
    if action == "approve":
        n = 0
        stamp = timezone.now().strftime("%d/%m/%Y %H:%M")
        for pf in qs.filter(status="CALCULADO"):
            pf.status = "APROVADO"
            pf.observacoes = (
                (pf.observacoes or "") + f"\n[APROVADO] em lote por {request.user.username} em {stamp}"
            ).strip()
            pf.save()
            n += 1
        skipped = len(ids) - n
        messages.success(
            request,
            f"{n} pré-fatura(s) aprovada(s)." + (f" {skipped} ignorada(s): não estavam em CALCULADO." if skipped else ""),
        )
        return redirect(back)

    if action == "csv":
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="pagamentos_{timezone.localdate():%Y%m%d}.csv"'
        resp.write("﻿")
        w = csv.writer(resp, delimiter=";")
        w.writerow(["PF", "Motorista", "NIF", "IBAN", "Período", "Regime", "Previsto", "Estado", "Valor (€)"])
        for pf in qs.order_by("data_prevista_pagamento", "driver__nome_completo"):
            w.writerow([
                pf.numero, pf.driver.nome_completo, pf.driver.nif, pf.driver.iban,
                f"{pf.periodo_inicio:%d/%m/%Y}–{pf.periodo_fim:%d/%m/%Y}",
                "Semanal" if is_weekly_period(pf.periodo_inicio, pf.periodo_fim) else "Mensal",
                f"{pf.data_prevista_pagamento:%d/%m/%Y}" if pf.data_prevista_pagamento else "",
                pf.get_status_display(),
                f"{pf_amount(pf):.2f}".replace(".", ","),
            ])
        return resp

    messages.error(request, "Acção desconhecida.")
    return redirect(back)
