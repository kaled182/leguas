"""Inbox unificado de Pagamentos a Fazer.

Agrega 4 fontes de payables:
  - DriverPreInvoice         (motoristas independentes)
  - EmpresaParceiraLancamento (empresas parceiras / frotas)
  - ThirdPartyReimbursement   (sócios)
  - Bill                      (contas gerais a fornecedores)

Regra de liberação:
  - Pré-Fatura motorista: precisa fatura_ficheiro anexada
  - Lançamento empresa: precisa estado APROVADO ou PENDENTE
  - Reembolso sócio: status PENDENTE
  - Bill: status PENDING/OVERDUE/AWAITING (AWAITING precisa aprovação primeiro)
"""
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Optional

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods


def _notify_driver_payment_async(pf):
    """Envia WhatsApp ao motorista a confirmar pagamento da PF.

    Best-effort: erros loggados mas não propagados (não impede o save).
    Usa o helper system_config.whatsapp_helper.WhatsAppAPI.
    """
    import logging
    log = logging.getLogger(__name__)
    try:
        from system_config.whatsapp_helper import WhatsAppWPPConnectAPI
        from system_config.models import SystemConfiguration
    except ImportError:
        return
    phone = (pf.driver.telefone or "").strip()
    if not phone or phone == "000000000":
        return
    try:
        api = WhatsAppWPPConnectAPI.from_config()
    except Exception as e:
        log.warning("WhatsApp API not configured: %s", e)
        return
    try:
        cfg = SystemConfiguration.get_config()
        empresa = cfg.company_name or "Léguas Franzinas"
    except Exception:
        empresa = "Léguas Franzinas"
    msg = (
        f"Olá {pf.driver.nome_completo.split()[0]} 👋\n\n"
        f"A tua pré-fatura *{pf.numero}* "
        f"({pf.periodo_inicio.strftime('%d/%m')} → "
        f"{pf.periodo_fim.strftime('%d/%m/%Y')}) "
        f"foi paga.\n\n"
        f"💰 Valor: *€{pf.total_a_receber:.2f}*\n"
        f"📅 Data: {pf.data_pagamento.strftime('%d/%m/%Y') if pf.data_pagamento else '—'}\n"
    )
    if pf.referencia_pagamento:
        msg += f"📋 Referência: {pf.referencia_pagamento}\n"
    msg += f"\n_{empresa}_"
    try:
        api.send_text(phone, msg)
        log.info("WhatsApp PF-paid notification sent to %s", phone)
    except Exception as e:
        log.warning("Failed to send WhatsApp notification: %s", e)


@dataclass
class PayableRow:
    entity_type: str          # "pre_invoice" | "fleet" | "shareholder" | "bill"
    entity_id: int
    type_label: str
    type_color: str           # tailwind family: blue/violet/amber/rose
    icon: str                 # lucide
    numero: str
    descricao: str
    detail_url: str
    due_date: Optional[object] = None
    period_label: str = ""
    amount: Decimal = Decimal("0.00")
    status: str = ""
    status_display: str = ""
    payable: bool = False
    block_reason: str = ""
    has_recibo: Optional[bool] = None  # só para PFs
    alerts: list = field(default_factory=list)  # anomalias detectadas
    # Decomposição fiscal (quando aplicável): amount = amount_base + vat_amount
    amount_base: Decimal = Decimal("0.00")
    vat_amount: Decimal = Decimal("0.00")
    vat_label: str = ""  # ex: "IVA 23%" — vazio se isento/sem IVA

    @property
    def days_to_due(self) -> Optional[int]:
        if not self.due_date:
            return None
        today = timezone.now().date()
        return (self.due_date - today).days

    @property
    def is_overdue(self) -> bool:
        d = self.days_to_due
        return d is not None and d < 0

    @property
    def due_soon(self) -> bool:
        d = self.days_to_due
        return d is not None and 0 <= d <= 7


def _row_pre_invoice(pf):
    from .services_payable_alerts import alerts_for_pre_invoice
    has_recibo = bool(pf.fatura_ficheiro)
    payable = pf.status in ("APROVADO", "PENDENTE") and has_recibo
    block = ""
    if not has_recibo:
        block = "Aguardando fatura-recibo do motorista"
    elif pf.status == "CALCULADO":
        block = "Falta aprovar a pré-fatura"
    elif pf.status not in ("APROVADO", "PENDENTE"):
        block = f"Estado {pf.get_status_display()} não permite pagamento"

    alerts = alerts_for_pre_invoice(pf)

    # Valor a pagar inclui IVA quando driver é Regime Normal — Léguas
    # paga ao motorista o total c/IVA (sai da Tesouraria com IVA).
    vat_amt = pf.vat_amount or Decimal("0.00")
    base_amt = pf.total_a_receber or Decimal("0.00")
    if vat_amt > 0:
        amount_total = pf.total_com_iva
        vat_label = "Inclui IVA 23%"
    else:
        amount_total = base_amt
        vat_label = ""

    return PayableRow(
        entity_type="pre_invoice",
        entity_id=pf.id,
        type_label="Pré-Fatura Motorista",
        type_color="blue",
        icon="user",
        numero=pf.numero,
        descricao=pf.driver.nome_completo,
        detail_url=reverse(
            "drivers_app:driver_pre_invoice_detail",
            kwargs={"driver_id": pf.driver_id, "pre_invoice_id": pf.id},
        ),
        due_date=pf.periodo_fim,
        period_label=(
            f"{pf.periodo_inicio.strftime('%d/%m')} → "
            f"{pf.periodo_fim.strftime('%d/%m')}"
        ),
        amount=amount_total,
        amount_base=base_amt,
        vat_amount=vat_amt,
        vat_label=vat_label,
        status=pf.status,
        status_display=pf.get_status_display(),
        payable=payable,
        block_reason=block,
        has_recibo=has_recibo,
        alerts=alerts,
    )


def _row_fleet(lanc):
    payable = lanc.status in ("APROVADO", "PENDENTE")
    block = ""
    if lanc.status == "RASCUNHO":
        block = "Falta aprovar o lançamento"
    elif not payable:
        block = f"Estado {lanc.get_status_display()} não permite pagamento"
    return PayableRow(
        entity_type="fleet",
        entity_id=lanc.id,
        type_label="Lançamento Frota",
        type_color="violet",
        icon="building-2",
        numero=f"FRT-{lanc.id:04d}",
        descricao=f"{lanc.empresa.nome} — {lanc.descricao[:60]}",
        detail_url=reverse(
            "drivers_app:empresas-parceiras",
        ) + f"?empresa={lanc.empresa_id}",
        due_date=lanc.periodo_fim,
        period_label=(
            f"{lanc.periodo_inicio.strftime('%d/%m')} → "
            f"{lanc.periodo_fim.strftime('%d/%m')}"
        ),
        amount=lanc.total_a_receber,
        status=lanc.status,
        status_display=lanc.get_status_display(),
        payable=payable,
        block_reason=block,
    )


def _row_fleet_invoice(fi):
    """PayableRow para FleetInvoice (FF-NNNN — pré-fatura global da frota).

    Estados pagáveis: CALCULADO ou APROVADO (a frota já tem fatura
    formal no PDF gerado). Mostra valor c/IVA — é o que o parceiro paga.
    """
    payable = fi.status in ("CALCULADO", "APROVADO")
    block = ""
    if fi.status == "RASCUNHO":
        block = "Falta calcular a pré-fatura"
    elif not payable:
        block = f"Estado {fi.get_status_display()} não permite pagamento"
    fi_vat = fi.vat_amount or Decimal("0.00")
    fi_base = fi.total_a_receber or Decimal("0.00")
    fi_vat_label = ""
    if fi_vat > 0:
        rate = getattr(fi, "vat_rate", None) or Decimal("23.00")
        try:
            fi_vat_label = f"Inclui IVA {float(rate):.0f}%"
        except (TypeError, ValueError):
            fi_vat_label = "Inclui IVA"

    return PayableRow(
        entity_type="fleet_invoice",
        entity_id=fi.id,
        type_label="Pré-Fatura Frota",
        type_color="violet",
        icon="building-2",
        numero=fi.numero,
        descricao=fi.empresa.nome,
        detail_url=reverse(
            "drivers_app:empresas-parceiras",
        ) + f"?empresa={fi.empresa_id}",
        due_date=fi.periodo_fim,
        period_label=(
            f"{fi.periodo_inicio.strftime('%d/%m')} → "
            f"{fi.periodo_fim.strftime('%d/%m')}"
        ),
        amount=fi.total_com_iva,
        amount_base=fi_base,
        vat_amount=fi_vat,
        vat_label=fi_vat_label,
        status=fi.status,
        status_display=fi.get_status_display(),
        payable=payable,
        block_reason=block,
    )


def _row_shareholder(reemb):
    payable = reemb.status == "PENDENTE"
    block = "" if payable else (
        f"Estado {reemb.get_status_display()} não permite pagamento"
    )
    return PayableRow(
        entity_type="shareholder",
        entity_id=reemb.id,
        type_label="Reembolso Sócio",
        type_color="amber",
        icon="hand-coins",
        numero=f"REE-{reemb.id:04d}",
        descricao=f"{reemb.lender.nome} — {reemb.descricao[:60]}",
        detail_url=reverse(
            "shareholder-dashboard",
        ) + f"?reemb={reemb.id}",
        due_date=reemb.data_emprestimo + timedelta(days=30),
        amount=reemb.valor,
        status=reemb.status,
        status_display=reemb.get_status_display(),
        payable=payable,
        block_reason=block,
    )


def _row_bill(bill):
    payable = bill.status in ("PENDING", "OVERDUE")
    block = ""
    if bill.status == "AWAITING":
        block = "Aguardando aprovação"
    elif not payable:
        block = f"Estado {bill.get_status_display()} não permite pagamento"

    # Valor a sair da Tesouraria = total c/IVA - retenção (esta fica
    # como dívida ao Estado, entregue depois pela Léguas)
    irs_amt = bill.irs_retention_amount or Decimal("0.00")
    payable_amount = bill.amount_payable
    vat_label = ""
    if irs_amt > 0:
        try:
            rate = bill.irs_retention_rate or Decimal("0")
            vat_label = f"Retém IRS {float(rate):.2f}% (-€{float(irs_amt):.2f})"
        except (TypeError, ValueError):
            vat_label = f"Retém IRS (-€{float(irs_amt):.2f})"

    return PayableRow(
        entity_type="bill",
        entity_id=bill.id,
        type_label="Conta a Pagar",
        type_color="rose",
        icon="receipt",
        numero=f"CNT-{bill.id:04d}",
        descricao=f"{bill.supplier} — {bill.description[:60]}",
        detail_url=reverse("accounting:bill_detail", kwargs={"pk": bill.id}),
        due_date=bill.due_date,
        amount=payable_amount,
        amount_base=bill.amount_total,
        vat_amount=irs_amt,
        vat_label=vat_label,
        status=bill.status,
        status_display=bill.get_status_display(),
        payable=payable,
        block_reason=block,
    )


@login_required
def payables_forecast(request):
    """Previsão de necessidade de caixa nos próximos N dias.

    Inclui:
    - PFs já emitidas com vencimento no horizonte
    - Bills pendentes com vencimento no horizonte
    - PFs estimadas baseadas em entregas em curso desde a última PF
      do motorista (heuristic: extrapola valor proporcional ao período)
    - Adiantamentos PENDENTE (devem ser cobrados na próxima PF)
    """
    from datetime import date as _date
    from drivers_app.models import EmpresaParceiraLancamento
    from settlements.models import (
        DriverPreInvoice, ThirdPartyReimbursement, PreInvoiceAdvance,
    )
    from .models import Bill

    today = timezone.now().date()
    try:
        days = int(request.GET.get("days", 30))
    except (ValueError, TypeError):
        days = 30
    horizon = today + timedelta(days=days)

    rows = []

    def _row(due, type_label, type_color, desc, amount, certainty, source_url=""):
        rows.append({
            "due_date": due, "type_label": type_label,
            "type_color": type_color, "desc": desc,
            "amount": float(amount or 0), "certainty": certainty,
            "days_to_due": (due - today).days,
            "source_url": source_url,
        })

    # 1. PFs emitidas pendentes (alta certeza)
    for pf in DriverPreInvoice.objects.filter(
        periodo_fim__range=(today, horizon),
        status__in=["CALCULADO", "APROVADO", "PENDENTE"],
    ).select_related("driver"):
        _row(pf.periodo_fim, "PF Motorista", "blue",
             f"{pf.numero} · {pf.driver.nome_completo}",
             pf.total_a_receber, "high",
             f"/driversapp/portal/{pf.driver_id}/pf/{pf.id}/")

    # 2. Frotas
    for lanc in EmpresaParceiraLancamento.objects.filter(
        periodo_fim__range=(today, horizon),
        status__in=["RASCUNHO", "APROVADO", "PENDENTE"],
    ).select_related("empresa"):
        _row(lanc.periodo_fim, "PF Frota", "violet",
             f"FRT-{lanc.id:04d} · {lanc.empresa.nome}",
             lanc.total_a_receber, "high")

    # 3. Reembolsos a sócios (data + 30 dias)
    for r in ThirdPartyReimbursement.objects.filter(status="PENDENTE"):
        due = r.data_emprestimo + timedelta(days=30)
        if today <= due <= horizon:
            _row(due, "Sócio", "amber",
                 f"REE-{r.id:04d} · {r.lender.nome}",
                 r.valor, "high")

    # 4. Bills pendentes
    for b in Bill.objects.filter(
        due_date__range=(today, horizon),
        status__in=["PENDING", "OVERDUE", "AWAITING"],
    ):
        _row(b.due_date, "Conta", "rose",
             f"CNT-{b.id:04d} · {b.supplier}",
             b.amount_total, "high",
             f"/accounting/contas-a-pagar/{b.id}/")

    # 5. PFs estimadas (baixa certeza) — drivers sem PF actual mas com
    #    histórico de pagamento mensal
    last_pf_per_driver = {}
    for pf in (
        DriverPreInvoice.objects
        .filter(status__in=["PAGO", "APROVADO", "PENDENTE"])
        .order_by("driver_id", "-periodo_fim")
        .select_related("driver")
    ):
        if pf.driver_id not in last_pf_per_driver:
            last_pf_per_driver[pf.driver_id] = pf

    for driver_id, last_pf in last_pf_per_driver.items():
        gap_days = (today - last_pf.periodo_fim).days
        if gap_days < 7:
            continue  # PF recente, esperar
        if gap_days > 90:
            continue  # motorista inactivo, não estimar
        # Estima nova PF baseada no valor médio diário
        prev_period_days = (last_pf.periodo_fim - last_pf.periodo_inicio).days + 1
        if prev_period_days <= 0:
            continue
        avg_daily = float(last_pf.total_a_receber or 0) / prev_period_days
        next_period_days = min(gap_days, 30)
        estimated = avg_daily * next_period_days
        if estimated < 50:
            continue  # ignore tiny estimates
        # Vencimento estimado: hoje + 7 dias
        due = today + timedelta(days=7)
        if due > horizon:
            continue
        _row(due, "PF Estimada", "gray",
             f"~ {last_pf.driver.nome_completo} ({next_period_days}d)",
             estimated, "low",
             f"/driversapp/portal/{driver_id}/faturas/")

    # 6. Total de adiantamentos pendentes (por motorista)
    advance_by_driver = {}
    for adv in PreInvoiceAdvance.objects.filter(status="PENDENTE"):
        advance_by_driver.setdefault(adv.driver_id, Decimal("0"))
        advance_by_driver[adv.driver_id] += adv.valor or Decimal("0")
    advances_total = sum(advance_by_driver.values())

    # Ordenar por data
    rows.sort(key=lambda r: r["due_date"])

    # KPIs
    total_high = sum(r["amount"] for r in rows if r["certainty"] == "high")
    total_low = sum(r["amount"] for r in rows if r["certainty"] == "low")

    return render(request, "accounting/payables_forecast.html", {
        "rows": rows, "today": today, "horizon": horizon, "days": days,
        "total_high": total_high, "total_low": total_low,
        "total_all": total_high + total_low,
        "advances_pending_count": sum(1 for _ in advance_by_driver),
        "advances_pending_total": float(advances_total),
    })


@login_required
def payables_calendar(request):
    """Calendário mensal de pagamentos a fazer."""
    from calendar import monthrange
    from datetime import date as _date
    from drivers_app.models import EmpresaParceiraLancamento
    from settlements.models import DriverPreInvoice, ThirdPartyReimbursement
    from .models import Bill

    today = timezone.now().date()
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
    except (ValueError, TypeError):
        year, month = today.year, today.month

    first_day = _date(year, month, 1)
    last_day = _date(year, month, monthrange(year, month)[1])

    # Recolhe items com vencimento neste mês
    items_by_day = {}
    totals_by_day = {}

    def _add(day, label, amount, color):
        items_by_day.setdefault(day, []).append({
            "label": label, "amount": float(amount or 0), "color": color,
        })
        totals_by_day[day] = totals_by_day.get(day, 0) + float(amount or 0)

    # PFs (vencem no periodo_fim)
    for pf in DriverPreInvoice.objects.filter(
        periodo_fim__range=(first_day, last_day),
        status__in=["CALCULADO", "APROVADO", "PENDENTE"],
    ).select_related("driver"):
        _add(pf.periodo_fim.day,
             f"{pf.numero} · {pf.driver.nome_completo}",
             pf.total_a_receber, "blue")

    # Frotas
    for lanc in EmpresaParceiraLancamento.objects.filter(
        periodo_fim__range=(first_day, last_day),
        status__in=["RASCUNHO", "APROVADO", "PENDENTE"],
    ).select_related("empresa"):
        _add(lanc.periodo_fim.day,
             f"FRT-{lanc.id:04d} · {lanc.empresa.nome}",
             lanc.total_a_receber, "violet")

    # Sócios (data_emprestimo + 30d)
    for r in ThirdPartyReimbursement.objects.filter(status="PENDENTE"):
        due = r.data_emprestimo + timedelta(days=30)
        if first_day <= due <= last_day:
            _add(due.day,
                 f"REE-{r.id:04d} · {r.lender.nome}",
                 r.valor, "amber")

    # Bills
    for b in Bill.objects.filter(
        due_date__range=(first_day, last_day),
        status__in=["PENDING", "OVERDUE", "AWAITING"],
    ):
        _add(b.due_date.day,
             f"CNT-{b.id:04d} · {b.supplier}",
             b.amount_total, "rose")

    # Construir grid de calendário (semanas)
    first_weekday = first_day.weekday()  # 0=Mon
    days_in_month = (last_day - first_day).days + 1
    cells = []
    # padding inicial
    for _ in range(first_weekday):
        cells.append(None)
    for d in range(1, days_in_month + 1):
        cells.append({
            "day": d,
            "items": items_by_day.get(d, []),
            "total": totals_by_day.get(d, 0),
            "is_today": (year == today.year and month == today.month and d == today.day),
        })
    # padding final até completar 7×N
    while len(cells) % 7 != 0:
        cells.append(None)
    weeks = [cells[i:i+7] for i in range(0, len(cells), 7)]

    # Navegação prev/next
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    month_total = sum(totals_by_day.values())
    month_count = sum(len(v) for v in items_by_day.values())

    PT_MONTHS = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                 "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    return render(request, "accounting/payables_calendar.html", {
        "year": year, "month": month,
        "month_label": f"{PT_MONTHS[month - 1]} {year}",
        "weeks": weeks,
        "month_total": month_total, "month_count": month_count,
        "prev_year": prev_year, "prev_month": prev_month,
        "next_year": next_year, "next_month": next_month,
    })


@login_required
def payables_pf_compare(request, pf_id):
    """JSON com comparação entre uma PF e a PF anterior do mesmo motorista.

    Mostra as principais métricas lado a lado com delta percentual.
    """
    from settlements.models import DriverPreInvoice
    pf = get_object_or_404(DriverPreInvoice, pk=pf_id)
    prev = (
        DriverPreInvoice.objects
        .filter(driver=pf.driver, periodo_fim__lt=pf.periodo_inicio)
        .order_by("-periodo_fim").first()
    )

    def _delta_pct(curr, prev_v):
        try:
            curr_f = float(curr or 0)
            prev_f = float(prev_v or 0)
            if prev_f == 0:
                return None
            return round(((curr_f - prev_f) / prev_f) * 100, 1)
        except (TypeError, ValueError):
            return None

    def _serialize(p):
        if not p:
            return None
        return {
            "id": p.id,
            "numero": p.numero,
            "periodo": (
                f"{p.periodo_inicio.strftime('%d/%m')}–"
                f"{p.periodo_fim.strftime('%d/%m/%Y')}"
            ),
            "base_entregas": float(p.base_entregas or 0),
            "total_bonus": float(p.total_bonus or 0),
            "total_pacotes_perdidos": float(p.total_pacotes_perdidos or 0),
            "total_adiantamentos": float(p.total_adiantamentos or 0),
            "total_a_receber": float(p.total_a_receber or 0),
            "status": p.get_status_display(),
        }

    metrics = ["base_entregas", "total_bonus", "total_pacotes_perdidos",
               "total_adiantamentos", "total_a_receber"]
    deltas = {}
    if prev:
        for m in metrics:
            deltas[m] = _delta_pct(
                getattr(pf, m), getattr(prev, m),
            )

    return JsonResponse({
        "success": True,
        "current": _serialize(pf),
        "previous": _serialize(prev),
        "deltas_pct": deltas,
    })


@login_required
@require_http_methods(["GET", "POST", "DELETE"])
def payables_pf_notes(request, pf_id):
    """CRUD de notas internas duma PF.

    GET: lista notas
    POST: cria nota com body
    DELETE: ?note_id=N apaga nota (só autor ou superuser)
    """
    from settlements.models import DriverPreInvoice, PreInvoiceNote
    pf = get_object_or_404(DriverPreInvoice, pk=pf_id)

    if request.method == "GET":
        notes = list(
            pf.notes.select_related("author").values(
                "id", "body", "created_at",
                "author__username", "author__id",
            )
        )
        return JsonResponse({"success": True, "notes": [
            {
                "id": n["id"],
                "body": n["body"],
                "author": n["author__username"] or "—",
                "author_id": n["author__id"],
                "created_at": n["created_at"].isoformat(),
            } for n in notes
        ]})

    if request.method == "POST":
        body = (request.POST.get("body") or "").strip()
        if not body:
            return JsonResponse(
                {"success": False, "error": "Conteúdo obrigatório."},
                status=400,
            )
        n = PreInvoiceNote.objects.create(
            pre_invoice=pf, author=request.user, body=body[:2000],
        )
        return JsonResponse({
            "success": True,
            "note": {
                "id": n.id, "body": n.body,
                "author": request.user.username,
                "author_id": request.user.id,
                "created_at": n.created_at.isoformat(),
            },
        })

    # DELETE
    note_id = request.GET.get("note_id")
    if not note_id:
        return JsonResponse({"success": False, "error": "note_id obrigatório."}, status=400)
    n = PreInvoiceNote.objects.filter(pk=note_id, pre_invoice=pf).first()
    if not n:
        return JsonResponse({"success": False, "error": "Nota não encontrada."}, status=404)
    if n.author_id != request.user.id and not request.user.is_superuser:
        return JsonResponse(
            {"success": False, "error": "Sem permissão."}, status=403,
        )
    n.delete()
    return JsonResponse({"success": True})


@login_required
def payables_pf_health(request, pf_id):
    """JSON com snapshot completo de Saúde do Motorista para uma PF."""
    from settlements.models import DriverPreInvoice
    from .services_driver_health import driver_health_snapshot
    pf = get_object_or_404(DriverPreInvoice, pk=pf_id)
    return JsonResponse({"success": True, **driver_health_snapshot(pf)})


@login_required
def payables_drivers_without_pf(request):
    """Página dedicada: motoristas com entregas no período e sem PF."""
    from datetime import datetime, timedelta as td
    from .services_pf_gaps import find_drivers_without_pf, MIN_GAP_DAYS

    today = timezone.now().date()
    custom_from = request.GET.get("date_from", "")
    custom_to = request.GET.get("date_to", "")
    period = request.GET.get("period", "30d")

    if custom_from and custom_to:
        try:
            date_from = datetime.strptime(custom_from, "%Y-%m-%d").date()
            date_to = datetime.strptime(custom_to, "%Y-%m-%d").date()
            period = "custom"
        except ValueError:
            date_from, date_to = today - td(days=29), today
    elif period == "7d":
        date_from, date_to = today - td(days=6), today
    elif period == "90d":
        date_from, date_to = today - td(days=89), today
    else:
        date_from, date_to = today - td(days=29), today

    include_all = request.GET.get("all") == "1"
    min_gap = int(request.GET.get("min_gap", MIN_GAP_DAYS) or MIN_GAP_DAYS)

    drivers = find_drivers_without_pf(
        date_from, date_to,
        min_gap_days=min_gap,
        include_all=include_all,
    )

    # KPIs agregados
    total_delivered = sum(d["delivered_count"] for d in drivers)
    total_estimated = sum(d["estimated_amount"] for d in drivers)
    total_estimated_com_iva = sum(
        d.get("estimated_total_com_iva", d["estimated_amount"]) for d in drivers
    )
    total_vat = sum(d.get("estimated_vat", 0) for d in drivers)
    total_gap_days = sum(d["gap_days"] for d in drivers)

    return render(request, "accounting/payables_no_pf.html", {
        "drivers": drivers,
        "date_from": date_from,
        "date_to": date_to,
        "period": period,
        "include_all": include_all,
        "min_gap": min_gap,
        "kpi_total_drivers": len(drivers),
        "kpi_total_delivered": total_delivered,
        "kpi_total_estimated": total_estimated,
        "kpi_total_estimated_com_iva": total_estimated_com_iva,
        "kpi_total_vat": total_vat,
        "kpi_total_gap_days": total_gap_days,
    })


@login_required
def payables_fleets_without_invoice(request):
    """Página dedicada: frotas com entregas no período e sem FleetInvoice."""
    from datetime import datetime, timedelta as td
    from .services_pf_gaps import (
        find_fleets_without_invoice, MIN_GAP_DAYS,
    )

    today = timezone.now().date()
    custom_from = request.GET.get("date_from", "")
    custom_to = request.GET.get("date_to", "")
    period = request.GET.get("period", "30d")

    if custom_from and custom_to:
        try:
            date_from = datetime.strptime(custom_from, "%Y-%m-%d").date()
            date_to = datetime.strptime(custom_to, "%Y-%m-%d").date()
            period = "custom"
        except ValueError:
            date_from, date_to = today - td(days=29), today
    elif period == "7d":
        date_from, date_to = today - td(days=6), today
    elif period == "90d":
        date_from, date_to = today - td(days=89), today
    else:
        date_from, date_to = today - td(days=29), today

    include_all = request.GET.get("all") == "1"
    min_gap = int(request.GET.get("min_gap", MIN_GAP_DAYS) or MIN_GAP_DAYS)

    fleets = find_fleets_without_invoice(
        date_from, date_to,
        min_gap_days=min_gap,
        include_all=include_all,
    )

    total_delivered = sum(f["delivered_count"] for f in fleets)
    total_estimated = sum(f["estimated_amount"] for f in fleets)
    total_estimated_com_iva = sum(
        f.get("estimated_total_com_iva", f["estimated_amount"])
        for f in fleets
    )
    total_vat = sum(f.get("estimated_vat", 0) for f in fleets)
    total_gap_days = sum(f["gap_days"] for f in fleets)

    return render(request, "accounting/payables_no_ff.html", {
        "fleets": fleets,
        "date_from": date_from,
        "date_to": date_to,
        "period": period,
        "include_all": include_all,
        "min_gap": min_gap,
        "kpi_total_fleets": len(fleets),
        "kpi_total_delivered": total_delivered,
        "kpi_total_estimated": total_estimated,
        "kpi_total_estimated_com_iva": total_estimated_com_iva,
        "kpi_total_vat": total_vat,
        "kpi_total_gap_days": total_gap_days,
    })


@login_required
def payables_inbox(request):
    """Inbox unificado de pagamentos a fazer."""
    from drivers_app.models import EmpresaParceiraLancamento
    from settlements.models import (
        DriverPreInvoice, ThirdPartyReimbursement, FleetInvoice,
    )
    from .models import Bill

    # Filtros
    type_filter = request.GET.get("tipo", "all")
    status_filter = request.GET.get("status", "open")  # open | all | overdue
    search = (request.GET.get("q") or "").strip()

    rows: list[PayableRow] = []

    # Pré-Faturas motorista
    if type_filter in ("all", "pre_invoice"):
        pfs = (
            DriverPreInvoice.objects
            .select_related("driver")
            .filter(status__in=["CALCULADO", "APROVADO", "PENDENTE"])
        )
        if search:
            pfs = pfs.filter(
                Q(numero__icontains=search) |
                Q(driver__nome_completo__icontains=search)
            )
        for pf in pfs:
            rows.append(_row_pre_invoice(pf))

    # Pré-Faturas Frota (FleetInvoice — FF-NNNN, factura global por período)
    if type_filter in ("all", "fleet", "fleet_invoice"):
        ffs = (
            FleetInvoice.objects
            .select_related("empresa")
            .filter(status__in=["CALCULADO", "APROVADO"])
        )
        if search:
            ffs = ffs.filter(
                Q(numero__icontains=search) |
                Q(empresa__nome__icontains=search)
            )
        for fi in ffs:
            rows.append(_row_fleet_invoice(fi))

    # Lançamentos manuais de Empresas Parceiras (despesas/serviços avulso)
    if type_filter in ("all", "fleet"):
        lancs = (
            EmpresaParceiraLancamento.objects
            .select_related("empresa")
            .filter(status__in=["RASCUNHO", "APROVADO", "PENDENTE"])
        )
        if search:
            lancs = lancs.filter(
                Q(descricao__icontains=search) |
                Q(empresa__nome__icontains=search)
            )
        for lanc in lancs:
            rows.append(_row_fleet(lanc))

    # Reembolsos a sócios
    if type_filter in ("all", "shareholder"):
        reembs = (
            ThirdPartyReimbursement.objects
            .select_related("lender")
            .filter(status="PENDENTE")
        )
        if search:
            reembs = reembs.filter(
                Q(descricao__icontains=search) |
                Q(lender__nome__icontains=search)
            )
        for r in reembs:
            rows.append(_row_shareholder(r))

    # Bills
    if type_filter in ("all", "bill"):
        bills = Bill.objects.filter(
            status__in=["AWAITING", "PENDING", "OVERDUE"],
        )
        if search:
            bills = bills.filter(
                Q(supplier__icontains=search) |
                Q(description__icontains=search)
            )
        for b in bills:
            rows.append(_row_bill(b))

    # Filtro de status
    if status_filter == "open":
        rows = [r for r in rows if r.payable or r.block_reason]
    elif status_filter == "overdue":
        rows = [r for r in rows if r.is_overdue]

    # Ordenar por data de vencimento (overdue primeiro, depois mais próximas)
    rows.sort(key=lambda r: (r.due_date or timezone.now().date(), -float(r.amount)))

    # KPIs
    total_amount = sum((r.amount for r in rows), Decimal("0"))
    overdue_amount = sum(
        (r.amount for r in rows if r.is_overdue), Decimal("0"),
    )
    due_soon_amount = sum(
        (r.amount for r in rows if r.due_soon), Decimal("0"),
    )
    blocked_amount = sum(
        (r.amount for r in rows if not r.payable), Decimal("0"),
    )

    kpis = {
        "total_count": len(rows),
        "total_amount": total_amount,
        "overdue_count": sum(1 for r in rows if r.is_overdue),
        "overdue_amount": overdue_amount,
        "due_soon_count": sum(1 for r in rows if r.due_soon),
        "due_soon_amount": due_soon_amount,
        "blocked_count": sum(1 for r in rows if not r.payable),
        "blocked_amount": blocked_amount,
        "ready_count": sum(1 for r in rows if r.payable),
    }

    by_type = {}
    for r in rows:
        by_type.setdefault(r.entity_type, {"count": 0, "amount": Decimal("0")})
        by_type[r.entity_type]["count"] += 1
        by_type[r.entity_type]["amount"] += r.amount

    return render(request, "accounting/payables_inbox.html", {
        "rows": rows,
        "kpis": kpis,
        "by_type": by_type,
        "type_filter": type_filter,
        "status_filter": status_filter,
        "search": search,
    })


@login_required
@require_http_methods(["POST"])
def payables_mark_paid(request):
    """Marca um payable como pago. Inputs (multipart):
       entity_type, entity_id, paid_date (YYYY-MM-DD),
       payment_reference, comprovante (file, opcional).
    """
    from datetime import datetime
    from drivers_app.models import EmpresaParceiraLancamento
    from settlements.models import (
        DriverPreInvoice, ThirdPartyReimbursement, FleetInvoice,
    )
    from .models import Bill

    entity_type = request.POST.get("entity_type", "")
    entity_id = request.POST.get("entity_id", "")
    paid_date_str = request.POST.get("paid_date", "")
    payment_reference = (request.POST.get("payment_reference") or "").strip()
    comprovante = request.FILES.get("comprovante")

    try:
        paid_date = datetime.strptime(paid_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        paid_date = timezone.now().date()

    # Dispatch
    if entity_type == "pre_invoice":
        pf = get_object_or_404(DriverPreInvoice, id=entity_id)
        if not pf.fatura_ficheiro:
            return JsonResponse({
                "success": False,
                "error": "PF sem fatura-recibo. Não pode ser paga.",
            }, status=400)
        if pf.status not in ("APROVADO", "PENDENTE"):
            return JsonResponse({
                "success": False,
                "error": f"Estado {pf.get_status_display()} não permite pagamento.",
            }, status=400)
        pf.status = "PAGO"
        pf.data_pagamento = paid_date
        if payment_reference:
            pf.referencia_pagamento = payment_reference
        if comprovante:
            pf.comprovante_pagamento = comprovante
        pf.save()
        # Notifica motorista via WhatsApp (best-effort, não bloqueia)
        _notify_driver_payment_async(pf)
        return JsonResponse({"success": True, "numero": pf.numero})

    if entity_type == "fleet":
        lanc = get_object_or_404(EmpresaParceiraLancamento, id=entity_id)
        if lanc.status not in ("APROVADO", "PENDENTE"):
            return JsonResponse({
                "success": False,
                "error": f"Estado {lanc.get_status_display()} não permite pagamento.",
            }, status=400)
        lanc.status = "PAGO"
        lanc.data_pagamento = paid_date
        if payment_reference:
            lanc.referencia_pagamento = payment_reference
        if comprovante:
            lanc.comprovante_pagamento = comprovante
        lanc.save()
        return JsonResponse({"success": True, "numero": f"FRT-{lanc.id:04d}"})

    if entity_type == "fleet_invoice":
        fi = get_object_or_404(FleetInvoice, id=entity_id)
        if fi.status not in ("CALCULADO", "APROVADO"):
            return JsonResponse({
                "success": False,
                "error": (
                    f"Estado {fi.get_status_display()} "
                    "não permite pagamento."
                ),
            }, status=400)
        fi.status = "PAGO"
        fi.data_pagamento = paid_date
        if payment_reference:
            fi.referencia_pagamento = payment_reference
        fi.save(update_fields=[
            "status", "data_pagamento", "referencia_pagamento", "updated_at",
        ])
        return JsonResponse({"success": True, "numero": fi.numero})

    if entity_type == "shareholder":
        reemb = get_object_or_404(ThirdPartyReimbursement, id=entity_id)
        if reemb.status != "PENDENTE":
            return JsonResponse({
                "success": False,
                "error": f"Estado {reemb.get_status_display()} não permite pagamento.",
            }, status=400)
        reemb.status = "PAGO"
        reemb.data_pagamento = paid_date
        if payment_reference:
            reemb.referencia_pagamento = payment_reference
        if comprovante:
            reemb.comprovante_pagamento = comprovante
        if request.user.is_authenticated:
            reemb.pago_por = request.user
        reemb.save()
        return JsonResponse({"success": True, "numero": f"REE-{reemb.id:04d}"})

    if entity_type == "bill":
        bill = get_object_or_404(Bill, id=entity_id)
        if bill.status not in ("PENDING", "OVERDUE"):
            return JsonResponse({
                "success": False,
                "error": f"Estado {bill.get_status_display()} não permite pagamento.",
            }, status=400)
        bill.status = Bill.STATUS_PAID
        bill.paid_date = paid_date
        bill.paid_amount = bill.amount_total
        if payment_reference:
            bill.payment_reference = payment_reference
        if comprovante:
            bill.payment_proof = comprovante
        bill.save()
        return JsonResponse({"success": True, "numero": f"CNT-{bill.id:04d}"})

    return JsonResponse(
        {"success": False, "error": "entity_type inválido."}, status=400,
    )
