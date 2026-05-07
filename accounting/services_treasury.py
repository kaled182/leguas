"""Posição de Tesouraria — agrega dados de Bills, Impostos, PartnerInvoices,
DriverPreInvoices e BankTransactions para construir o dashboard.

Funções principais:
  - treasury_snapshot(today) → dict com todos os KPIs principais
  - cash_projection_30d(today) → list[{date, in_amount, out_amount, balance}]
  - iva_dedutivel_pendente(period_start, period_end) → Decimal
  - upcoming_tax_installments(today, n=5) → queryset

Convenção: tudo em Decimal/€. Datas são date (não datetime).
"""
from datetime import timedelta, date
from decimal import Decimal

from django.db.models import Q, Sum

from .models import (
    Bill, BankTransaction, Fornecedor, Imposto,
)


# ── Helpers internos ─────────────────────────────────────────────────────

def _zero():
    return Decimal("0.00")


def _saldo_bancario_atual():
    """Saldo computacional = soma de CREDIT − soma de DEBIT em todas as
    transacções importadas. Devolve (saldo, data_ultima_tx)."""
    agg = BankTransaction.objects.aggregate(
        creditos=Sum("amount", filter=Q(direction=BankTransaction.DIRECTION_CREDIT)),
        debitos=Sum("amount", filter=Q(direction=BankTransaction.DIRECTION_DEBIT)),
    )
    creditos = agg["creditos"] or _zero()
    debitos = agg["debitos"] or _zero()
    saldo = creditos - debitos
    last_tx = (
        BankTransaction.objects.order_by("-date").values_list("date", flat=True).first()
    )
    return saldo, last_tx


# ── Snapshots agregados ──────────────────────────────────────────────────

def treasury_snapshot(today: date | None = None) -> dict:
    """Devolve um dict com todos os números-chave do dashboard."""
    if today is None:
        from django.utils import timezone
        today = timezone.localdate()
    horizon = today + timedelta(days=30)

    # ── A PAGAR (próximos 30 dias) ──────────────────────────────────────
    bills_a_pagar = Bill.objects.filter(
        status__in=[Bill.STATUS_PENDING, Bill.STATUS_AWAITING, Bill.STATUS_OVERDUE],
        due_date__lte=horizon,
    )
    bills_a_pagar_total = bills_a_pagar.aggregate(t=Sum("amount_total"))["t"] or _zero()

    impostos_a_pagar = Imposto.objects.filter(
        Q(status=Imposto.STATUS_PENDENTE) | Q(status=Imposto.STATUS_EM_ATRASO),
        data_vencimento__lte=horizon,
        # Excluir os pais PARCELADO (já contamos as filhas)
        parent__isnull=False,
    )
    impostos_a_pagar_outros = Imposto.objects.filter(
        Q(status=Imposto.STATUS_PENDENTE) | Q(status=Imposto.STATUS_EM_ATRASO),
        data_vencimento__lte=horizon,
        parent__isnull=True,
    ).exclude(modalidade=Imposto.MODALIDADE_PARCELADO)
    impostos_total = (
        (impostos_a_pagar.aggregate(t=Sum("valor"))["t"] or _zero())
        + (impostos_a_pagar_outros.aggregate(t=Sum("valor"))["t"] or _zero())
    )

    # Pré-faturas de motoristas (pendentes/aprovadas)
    try:
        from settlements.models import DriverPreInvoice
        driver_a_pagar = DriverPreInvoice.objects.filter(
            status__in=["APROVADO", "PENDENTE", "CALCULADO"],
        )
        driver_total = (
            driver_a_pagar.aggregate(t=Sum("total_a_receber"))["t"] or _zero()
        )
        driver_n = driver_a_pagar.count()
    except Exception:
        driver_total = _zero()
        driver_n = 0

    a_pagar_total = bills_a_pagar_total + impostos_total + driver_total

    # ── A RECEBER ──────────────────────────────────────────────────────
    try:
        from settlements.models import PartnerInvoice
        partner_a_receber = PartnerInvoice.objects.filter(
            status__in=["PENDING", "OVERDUE"],
        )
        partner_total = (
            partner_a_receber.aggregate(t=Sum("gross_amount"))["t"] or _zero()
        )
        partner_n = partner_a_receber.count()
    except Exception:
        partner_total = _zero()
        partner_n = 0

    # IVA dedutível pendente (sobre Bills pagas no trimestre atual)
    iva_dedutivel = iva_dedutivel_pendente(today)

    a_receber_total = partner_total + iva_dedutivel

    # ── SALDO BANCÁRIO ─────────────────────────────────────────────────
    saldo, saldo_data = _saldo_bancario_atual()

    # ── KPIs combustível / peças (IVA dedutível por categoria) ─────────
    fuel_iva = iva_dedutivel_por_tag(today, slugs=["combustivel", "combustível"])
    parts_iva = iva_dedutivel_por_tag(
        today, slugs=["peças", "pecas", "manutencao", "manutenção", "mecanica", "mecânica"],
    )

    # ── Próximas prestações de impostos parcelados ─────────────────────
    proximas_parcelas = list(
        Imposto.objects
        .filter(
            parent__isnull=False,
            status__in=[Imposto.STATUS_PENDENTE, Imposto.STATUS_EM_ATRASO],
            data_vencimento__lte=horizon,
        )
        .select_related("parent", "fornecedor")
        .order_by("data_vencimento")[:5]
    )

    return {
        "today": today,
        "horizon": horizon,
        "a_pagar_total": a_pagar_total,
        "a_pagar_breakdown": {
            "bills": bills_a_pagar_total,
            "bills_count": bills_a_pagar.count(),
            "impostos": impostos_total,
            "impostos_count": impostos_a_pagar.count() + impostos_a_pagar_outros.count(),
            "drivers": driver_total,
            "drivers_count": driver_n,
        },
        "a_receber_total": a_receber_total,
        "a_receber_breakdown": {
            "partner_invoices": partner_total,
            "partner_count": partner_n,
            "iva_dedutivel": iva_dedutivel,
        },
        "saldo_bancario": saldo,
        "saldo_data": saldo_data,
        "iva_dedutivel": iva_dedutivel,
        "fuel_iva_dedutivel": fuel_iva,
        "parts_iva_dedutivel": parts_iva,
        "proximas_parcelas": proximas_parcelas,
        # Cálculo: saldo projectado em +30d (saldo + receber − pagar)
        "saldo_projectado_30d": saldo + a_receber_total - a_pagar_total,
    }


def iva_dedutivel_pendente(today: date) -> Decimal:
    """IVA dedutível acumulado no trimestre actual sobre Bills pagas com
    Fornecedor.iva_dedutivel=True. Calcula `amount_total - amount_net`.

    Este valor representa o crédito que a empresa pode descontar do IVA
    a pagar no próximo apuramento (regime trimestral assumido por defeito).
    """
    quarter = (today.month - 1) // 3
    period_start = date(today.year, quarter * 3 + 1, 1)
    qs = Bill.objects.filter(
        fornecedor__iva_dedutivel=True,
        issue_date__gte=period_start,
        issue_date__lte=today,
        status__in=[Bill.STATUS_PAID, Bill.STATUS_PENDING, Bill.STATUS_OVERDUE],
    )
    agg = qs.aggregate(
        net=Sum("amount_net"),
        total=Sum("amount_total"),
    )
    iva = (agg["total"] or _zero()) - (agg["net"] or _zero())
    return iva


def iva_dedutivel_por_tag(today: date, slugs: list[str]) -> Decimal:
    """IVA dedutível acumulado no trimestre actual filtrado por tag(s)
    do Fornecedor (ex: combustível, peças).
    """
    quarter = (today.month - 1) // 3
    period_start = date(today.year, quarter * 3 + 1, 1)
    qs = Bill.objects.filter(
        fornecedor__iva_dedutivel=True,
        fornecedor__tags__slug__in=slugs,
        issue_date__gte=period_start,
        issue_date__lte=today,
        status__in=[Bill.STATUS_PAID, Bill.STATUS_PENDING, Bill.STATUS_OVERDUE],
    ).distinct()
    agg = qs.aggregate(net=Sum("amount_net"), total=Sum("amount_total"))
    return (agg["total"] or _zero()) - (agg["net"] or _zero())


# ── Projeção 30 dias ─────────────────────────────────────────────────────

def cash_projection_30d(today: date | None = None) -> dict:
    """Constroi a projeção dia-a-dia do saldo nos próximos 30 dias.

    Devolve dict com:
      - days: list[{date_iso, weekday, in_amount, out_amount,
                     daily_delta, balance, events_in, events_out}]
      - start_balance: saldo bancário actual
      - end_balance: saldo projectado em today+30
      - first_negative: data em que o saldo fica negativo (ou None)
    """
    if today is None:
        from django.utils import timezone
        today = timezone.localdate()
    horizon = today + timedelta(days=30)

    saldo_atual, _saldo_data = _saldo_bancario_atual()

    # Eventos OUT (pagamentos previstos)
    out_events_by_date: dict[date, list] = {}
    for b in Bill.objects.filter(
        status__in=[Bill.STATUS_PENDING, Bill.STATUS_AWAITING, Bill.STATUS_OVERDUE],
        due_date__gte=today, due_date__lte=horizon,
    ):
        out_events_by_date.setdefault(b.due_date, []).append({
            "type": "bill",
            "label": b.description[:50],
            "amount": b.amount_total,
            "url": f"/accounting/contas-a-pagar/{b.pk}/",
        })

    # Impostos: contar prestações filhas + impostos sem parent que não sejam pais
    imp_qs = Imposto.objects.filter(
        Q(status=Imposto.STATUS_PENDENTE) | Q(status=Imposto.STATUS_EM_ATRASO),
        data_vencimento__gte=today, data_vencimento__lte=horizon,
    ).exclude(
        # Excluir pais PARCELADO (são informativos, não pagas o pai)
        modalidade=Imposto.MODALIDADE_PARCELADO, parent__isnull=True,
    )
    for i in imp_qs:
        out_events_by_date.setdefault(i.data_vencimento, []).append({
            "type": "imposto",
            "label": f"{i.get_tipo_display()} — {i.nome[:50]}",
            "amount": i.valor,
            "url": f"/accounting/impostos/{i.pk}/editar/",
        })

    # Pré-faturas de motoristas — assumimos vencem no fim do período
    try:
        from settlements.models import DriverPreInvoice
        for pf in DriverPreInvoice.objects.filter(
            status__in=["APROVADO", "PENDENTE"],
            periodo_fim__gte=today - timedelta(days=30),
            periodo_fim__lte=horizon,
        ):
            # Vencimento previsto = periodo_fim + 5 dias úteis (heurística)
            venc = pf.periodo_fim + timedelta(days=7)
            if today <= venc <= horizon:
                out_events_by_date.setdefault(venc, []).append({
                    "type": "driver_pf",
                    "label": (
                        f"PF {pf.numero} — "
                        f"{pf.driver.nome_completo[:30] if pf.driver_id else '?'}"
                    ),
                    "amount": pf.total_a_receber,
                    "url": f"/settlements/pre-invoices/{pf.pk}/",
                })
    except Exception:
        pass

    # Eventos IN (recebimentos previstos)
    in_events_by_date: dict[date, list] = {}
    try:
        from settlements.models import PartnerInvoice
        for pi in PartnerInvoice.objects.filter(
            status__in=["PENDING", "OVERDUE"],
            due_date__gte=today, due_date__lte=horizon,
        ):
            in_events_by_date.setdefault(pi.due_date, []).append({
                "type": "partner_invoice",
                "label": f"{pi.partner.name} — {pi.invoice_number}",
                "amount": pi.gross_amount,
                "url": f"/settlements/invoices/{pi.pk}/",
            })
    except Exception:
        pass

    # Construir os 30 dias
    days = []
    balance = saldo_atual
    first_negative = None
    weekday_pt = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    for offset in range(31):  # incluir today+30 (31 pontos)
        d = today + timedelta(days=offset)
        evs_in = in_events_by_date.get(d, [])
        evs_out = out_events_by_date.get(d, [])
        in_amount = sum((e["amount"] for e in evs_in), _zero())
        out_amount = sum((e["amount"] for e in evs_out), _zero())
        daily_delta = in_amount - out_amount
        balance = balance + daily_delta
        if first_negative is None and balance < 0:
            first_negative = d
        days.append({
            "date": d,
            "date_iso": d.isoformat(),
            "weekday": weekday_pt[d.weekday()],
            "in_amount": in_amount,
            "out_amount": out_amount,
            "daily_delta": daily_delta,
            "balance": balance,
            "events_in": evs_in,
            "events_out": evs_out,
        })

    return {
        "days": days,
        "start_balance": saldo_atual,
        "end_balance": balance,
        "first_negative": first_negative,
    }
