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

from .models import Bill, BankTransaction


_TOL_AMT = Decimal("0.02")
_TOL_DAYS = 3


def _candidates_for(tx: BankTransaction):
    """Devolve lista de sugestões para uma transacção (com tipo + objecto + score)."""
    suggestions = []
    if tx.is_matched:
        return suggestions

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
                    status="PAGO",
                    data_pagamento__range=(
                        tx.date - timedelta(days=_TOL_DAYS),
                        tx.date + timedelta(days=_TOL_DAYS),
                    ),
                ).select_related("driver")[:5]
            )
            for pf in pfs:
                score = 0
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
                    ),
                    "amount": pf.total_a_receber,
                    "date": pf.data_pagamento,
                    "url": f"/settlements/pre-invoices/{pf.id}/",
                    "id": pf.id,
                })
        except Exception:
            pass

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


@login_required
def bank_reconciliation(request):
    """Lista transacções não conciliadas + sugestões."""
    direction = (request.GET.get("direction") or "").strip().upper()
    show_matched = request.GET.get("matched") == "1"

    qs = BankTransaction.objects.select_related("statement").order_by("-date")
    if not show_matched:
        qs = qs.filter(
            matched_bill__isnull=True,
            matched_partner_invoice__isnull=True,
            matched_pf__isnull=True,
        )
    if direction in ("DEBIT", "CREDIT"):
        qs = qs.filter(direction=direction)

    qs = qs[:200]

    rows = []
    for tx in qs:
        sugs = _candidates_for(tx) if not tx.is_matched else []
        rows.append({"tx": tx, "suggestions": sugs})

    # KPIs
    total_unmatched = BankTransaction.objects.filter(
        matched_bill__isnull=True,
        matched_partner_invoice__isnull=True,
        matched_pf__isnull=True,
    ).count()
    total_matched = BankTransaction.objects.filter(
        Q(matched_bill__isnull=False)
        | Q(matched_partner_invoice__isnull=False)
        | Q(matched_pf__isnull=False),
    ).count()
    with_suggestions = sum(1 for r in rows if r["suggestions"])

    return render(request, "accounting/bank_reconciliation.html", {
        "rows": rows,
        "total_unmatched": total_unmatched,
        "total_matched": total_matched,
        "with_suggestions": with_suggestions,
        "filters": {
            "direction": direction,
            "show_matched": show_matched,
        },
    })


@login_required
@require_http_methods(["POST"])
def bank_match_confirm(request, tx_id):
    """Confirma um match entre transacção bancária e
    Bill/PartnerInvoice/PF."""
    tx = get_object_or_404(BankTransaction, pk=tx_id)
    target_type = (request.POST.get("type") or "").strip()
    target_id = (request.POST.get("id") or "").strip()
    if not target_id.isdigit():
        messages.error(request, "ID inválido.")
        return redirect("accounting:bank_reconciliation")

    target_id = int(target_id)
    if target_type == "bill":
        tx.matched_bill_id = target_id
    elif target_type == "partner":
        tx.matched_partner_invoice_id = target_id
    elif target_type == "pf":
        tx.matched_pf_id = target_id
    else:
        messages.error(request, f"Tipo desconhecido: {target_type}")
        return redirect("accounting:bank_reconciliation")

    tx.matched_at = timezone.now()
    tx.matched_by = request.user
    tx.save(update_fields=[
        "matched_bill", "matched_partner_invoice", "matched_pf",
        "matched_at", "matched_by",
    ])
    messages.success(request, f"Match confirmado para transacção #{tx.id}.")
    return redirect("accounting:bank_reconciliation")


@login_required
@require_http_methods(["POST"])
def bank_match_clear(request, tx_id):
    """Remove o match de uma transacção."""
    tx = get_object_or_404(BankTransaction, pk=tx_id)
    tx.matched_bill = None
    tx.matched_partner_invoice = None
    tx.matched_pf = None
    tx.matched_at = None
    tx.matched_by = None
    tx.save(update_fields=[
        "matched_bill", "matched_partner_invoice", "matched_pf",
        "matched_at", "matched_by",
    ])
    messages.success(request, "Match removido.")
    return redirect("accounting:bank_reconciliation")
