"""Reconciliação bancária — match BankTransaction ↔ Bills/PartnerInvoice/PF.

Página `/accounting/reconciliacao-bancaria/` lista transacções
não conciliadas e propõe matches automáticos por valor e data.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import Bill, BankPayee, BankStatement, BankTransaction


_TOL_AMT = Decimal("0.02")
_TOL_DAYS = 3
# Com IBAN já conhecido, a data pode estar mais longe.
_TOL_DAYS_PAYEE = 10


def _payee_for(tx: BankTransaction):
    """IBAN de destino já confirmado antes, se existir."""
    if not tx.counterparty_iban:
        return None
    return BankPayee.objects.filter(iban=tx.counterparty_iban).first()


def _advance_candidates(tx, desc, payee):
    """Adiantamentos pagos pela empresa com o mesmo valor e data próxima."""
    from settlements.models import PreInvoiceAdvance
    days = _TOL_DAYS_PAYEE if payee and payee.driver_id else _TOL_DAYS
    qs = PreInvoiceAdvance.objects.filter(
        valor__gte=tx.amount - _TOL_AMT,
        valor__lte=tx.amount + _TOL_AMT,
        paid_by_source="EMPRESA",
        bank_transactions__isnull=True,
        data__range=(tx.date - timedelta(days=days), tx.date + timedelta(days=days)),
    ).exclude(status="CANCELADO").select_related("driver")
    out = []
    for a in qs[:10]:
        score = 0
        if a.valor == tx.amount:
            score += 5
        if a.data == tx.date:
            score += 3
        if payee and payee.driver_id == a.driver_id:
            score += 20
        elif payee and payee.driver_id:
            continue
        first = (a.driver.nome_completo or "").split()[:1]
        if first and first[0].lower() in desc:
            score += 10
        out.append({
            "type": "advance",
            "obj": a,
            "score": score,
            "label": (
                f"{a.get_tipo_display()} · {a.driver.nome_completo}"
                f"{' · ' + a.descricao if a.descricao else ''}"
            ),
            "amount": a.valor,
            "date": a.data,
            "url": f"/settlements/pre-invoices/{a.pre_invoice_id}/" if a.pre_invoice_id else "",
            "id": a.id,
        })
    return out


def _candidates_for(tx: BankTransaction):
    """Devolve lista de sugestões para uma transacção (com tipo + objecto + score)."""
    suggestions = []
    if tx.is_matched or tx.is_internal:
        return suggestions
    payee = _payee_for(tx)

    if tx.direction == BankTransaction.DIRECTION_DEBIT:
        # Bills (PAID ou PENDING)
        bills = Bill.objects.filter(
            amount_total__gte=tx.amount - _TOL_AMT,
            amount_total__lte=tx.amount + _TOL_AMT,
            bank_transactions__isnull=True,
        ).filter(
            Q(paid_date__range=(
                tx.date - timedelta(days=_TOL_DAYS),
                tx.date + timedelta(days=_TOL_DAYS),
            ))
            | Q(due_date__range=(
                tx.date - timedelta(days=_TOL_DAYS),
                tx.date + timedelta(days=_TOL_DAYS),
            )),
        ).select_related("fornecedor")[:5]
        desc = (tx.description or "").lower()
        for b in bills:
            score = 0
            if b.amount_total == tx.amount:
                score += 5
            if b.fornecedor and b.fornecedor.name.lower() in desc:
                score += 10
            if b.paid_date == tx.date:
                score += 3
            if payee and payee.fornecedor_id and payee.fornecedor_id == b.fornecedor_id:
                score += 20
            suggestions.append({
                "type": "bill",
                "obj": b,
                "score": score,
                "label": (
                    f"{b.fornecedor.name if b.fornecedor_id else b.supplier or 'Fornecedor'} · "
                    f"{b.description}"
                ),
                "amount": b.amount_total,
                "date": b.paid_date or b.due_date,
                "url": f"/accounting/contas-a-pagar/{b.id}/",
                "id": b.id,
            })

        # PFs PAGAS
        try:
            from settlements.models import DriverPreInvoice
            pfs = list(
                DriverPreInvoice.objects.filter(
                    total_a_receber__gte=tx.amount - _TOL_AMT,
                    total_a_receber__lte=tx.amount + _TOL_AMT,
                    bank_transactions__isnull=True,
                ).filter(
                    Q(status="PAGO", data_pagamento__range=(
                        tx.date - timedelta(days=_TOL_DAYS),
                        tx.date + timedelta(days=_TOL_DAYS),
                    ))
                    | Q(periodo_fim__range=(
                        tx.date - timedelta(days=45), tx.date,
                    )),
                ).exclude(status="CANCELADO").select_related("driver")[:5]
            )
            for pf in pfs:
                score = 0
                if payee and payee.driver_id:
                    if payee.driver_id != pf.driver_id:
                        continue
                    score += 20
                if pf.total_a_receber == tx.amount:
                    score += 5
                if pf.driver and pf.driver.nome_completo:
                    first = pf.driver.nome_completo.split()[0].lower()
                    if first and first in desc:
                        score += 10
                suggestions.append({
                    "type": "pf",
                    "obj": pf,
                    "score": score,
                    "label": (
                        f"PF {pf.numero} · "
                        f"{pf.driver.nome_completo if pf.driver_id else '?'}"
                        f"{'' if pf.status == 'PAGO' else ' · ainda não marcada paga'}"
                    ),
                    "amount": pf.total_a_receber,
                    "date": pf.data_pagamento,
                    "url": f"/settlements/pre-invoices/{pf.id}/",
                    "id": pf.id,
                })
        except Exception:
            pass

        suggestions += _advance_candidates(tx, desc, payee)

    elif tx.direction == BankTransaction.DIRECTION_CREDIT:
        try:
            from settlements.models import PartnerInvoice
            invs = PartnerInvoice.objects.filter(
                gross_amount__gte=tx.amount - _TOL_AMT,
                gross_amount__lte=tx.amount + _TOL_AMT,
                bank_transactions__isnull=True,
            ).filter(
                Q(paid_date__range=(
                    tx.date - timedelta(days=_TOL_DAYS),
                    tx.date + timedelta(days=_TOL_DAYS),
                ))
                | Q(due_date__range=(
                    tx.date - timedelta(days=_TOL_DAYS),
                    tx.date + timedelta(days=_TOL_DAYS),
                )),
            ).select_related("partner")[:5]
            desc = (tx.description or "").lower()
            for inv in invs:
                score = 0
                if inv.gross_amount == tx.amount:
                    score += 5
                if inv.partner and inv.partner.name.lower() in desc:
                    score += 10
                suggestions.append({
                    "type": "partner",
                    "obj": inv,
                    "score": score,
                    "label": (
                        f"{inv.partner.name if inv.partner_id else 'Parceiro'} · "
                        f"{inv.invoice_number}"
                    ),
                    "amount": inv.gross_amount,
                    "date": inv.paid_date or inv.due_date,
                    "url": f"/settlements/invoices/{inv.id}/",
                    "id": inv.id,
                })
        except Exception:
            pass

    suggestions.sort(key=lambda s: -s["score"])
    return suggestions


_UNMATCHED = Q(
    matched_bill__isnull=True,
    matched_partner_invoice__isnull=True,
    matched_pf__isnull=True,
    matched_advance__isnull=True,
    is_internal=False,
)
_MATCH_FIELDS = [
    "matched_bill", "matched_partner_invoice", "matched_pf",
    "matched_advance", "matched_at", "matched_by",
]


@login_required
def bank_reconciliation(request):
    """Lista transacções não conciliadas + sugestões."""
    direction = (request.GET.get("direction") or "").strip().upper()
    account = (request.GET.get("account") or "").strip()
    show_matched = request.GET.get("matched") == "1"

    base = BankTransaction.objects.all()
    if account:
        base = base.filter(statement__account_number=account)
    qs = base.select_related("statement", "matched_by").order_by("-date", "-id")
    if not show_matched:
        qs = qs.filter(_UNMATCHED)
    if direction in ("DEBIT", "CREDIT"):
        qs = qs.filter(direction=direction)

    qs = qs[:200]

    rows = []
    for tx in qs:
        sugs = _candidates_for(tx) if not tx.is_matched else []
        rows.append({"tx": tx, "suggestions": sugs})

    total_unmatched = base.filter(_UNMATCHED).count()
    total_internal = base.filter(is_internal=True).count()
    total_matched = base.exclude(_UNMATCHED).filter(is_internal=False).count()
    with_suggestions = sum(1 for r in rows if r["suggestions"])
    accounts = list(
        BankStatement.objects.exclude(account_number="")
        .values_list("account_number", flat=True).distinct()
        .order_by("account_number")
    )

    return render(request, "accounting/bank_reconciliation.html", {
        "rows": rows,
        "total_unmatched": total_unmatched,
        "total_matched": total_matched,
        "total_internal": total_internal,
        "with_suggestions": with_suggestions,
        "accounts": accounts,
        "filters": {
            "direction": direction,
            "account": account,
            "show_matched": show_matched,
        },
    })


def _learn_payee(tx):
    """Guarda o IBAN de destino para sugerir melhor da próxima vez."""
    if not tx.counterparty_iban or tx.direction != BankTransaction.DIRECTION_DEBIT:
        return
    driver_id = fornecedor_id = None
    if tx.matched_pf_id:
        driver_id = tx.matched_pf.driver_id
    elif tx.matched_advance_id:
        driver_id = tx.matched_advance.driver_id
    elif tx.matched_bill_id:
        fornecedor_id = tx.matched_bill.fornecedor_id
    if driver_id or fornecedor_id:
        BankPayee.objects.update_or_create(
            iban=tx.counterparty_iban,
            defaults={"driver_id": driver_id, "fornecedor_id": fornecedor_id},
        )


def _back(request):
    nxt = request.POST.get("next") or ""
    if nxt.startswith("/accounting/"):
        return redirect(nxt)
    return redirect("accounting:bank_reconciliation")


@login_required
@require_http_methods(["POST"])
def bank_match_confirm(request, tx_id):
    """Confirma um match entre transacção bancária e
    Bill/PartnerInvoice/PF/adiantamento."""
    tx = get_object_or_404(BankTransaction, pk=tx_id)
    target_type = (request.POST.get("type") or "").strip()
    target_id = (request.POST.get("id") or "").strip()
    if not target_id.isdigit():
        messages.error(request, "ID inválido.")
        return _back(request)

    field = {
        "bill": "matched_bill_id",
        "partner": "matched_partner_invoice_id",
        "pf": "matched_pf_id",
        "advance": "matched_advance_id",
    }.get(target_type)
    if not field:
        messages.error(request, f"Tipo desconhecido: {target_type}")
        return _back(request)

    setattr(tx, field, int(target_id))
    tx.matched_at = timezone.now()
    tx.matched_by = request.user
    tx.save(update_fields=_MATCH_FIELDS)
    _learn_payee(tx)
    messages.success(request, f"Movimento de {tx.date:%d/%m} conciliado.")
    return _back(request)


@login_required
@require_http_methods(["POST"])
def bank_match_clear(request, tx_id):
    """Remove o match de uma transacção."""
    tx = get_object_or_404(BankTransaction, pk=tx_id)
    tx.matched_bill = None
    tx.matched_partner_invoice = None
    tx.matched_pf = None
    tx.matched_advance = None
    tx.matched_at = None
    tx.matched_by = None
    tx.save(update_fields=_MATCH_FIELDS)
    messages.success(request, "Ligação removida.")
    return _back(request)
