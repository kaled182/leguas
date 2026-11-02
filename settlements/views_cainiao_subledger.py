"""Pré-faturas Cainiao a partir do sub-ledger do portal CES."""
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .models import CainiaoBill, CainiaoClientPreInvoice, CainiaoSubledgerImport
from .services_cainiao_subledger import (
    SubledgerError, charges_for, checks, create_pre_invoice, documents,
    dynamic, export_xlsx, import_subledger, unassigned_bills,
)


def _quinzena(day):
    """Quinzena anterior à data: 1–15 ou 16–fim do mês."""
    if day.day > 15:
        return day.replace(day=1), day.replace(day=15)
    prev_end = day.replace(day=1).toordinal() - 1
    prev = date.fromordinal(prev_end)
    return prev.replace(day=16), prev


@login_required
def subledger_list(request):
    pre_invoices = CainiaoClientPreInvoice.objects.prefetch_related("bills")
    period_from, period_to = _quinzena(date.today())
    return render(request, "settlements/cainiao_subledger/list.html", {
        "pre_invoices": pre_invoices,
        "bills": unassigned_bills(),
        "imports": CainiaoSubledgerImport.objects.all()[:5],
        "period_from": period_from,
        "period_to": period_to,
    })


@login_required
@require_http_methods(["POST"])
def subledger_upload(request):
    files = request.FILES.getlist("file")
    if not files:
        messages.error(request, "Escolha o CSV do sub-ledger.")
        return redirect("cainiao-subledger-list")
    for f in files:
        try:
            _, n_new, n_dup, bills = import_subledger(f, request.user)
        except SubledgerError as e:
            messages.error(request, f"{f.name}: {e}")
            continue
        msg = f"{f.name}: {n_new} linhas novas em {len(bills)} faturas Cainiao."
        if n_dup:
            msg += f" {n_dup} linhas já existiam e foram ignoradas."
        messages.success(request, msg)
    return redirect("cainiao-subledger-list")


@login_required
@require_http_methods(["POST"])
def pre_invoice_create(request):
    try:
        period_from = date.fromisoformat(request.POST.get("period_from", ""))
        period_to = date.fromisoformat(request.POST.get("period_to", ""))
    except ValueError:
        messages.error(request, "Indique as datas do período.")
        return redirect("cainiao-subledger-list")
    try:
        pre = create_pre_invoice(request.POST.getlist("bill"), period_from, period_to, request.user)
    except SubledgerError as e:
        messages.error(request, str(e))
        return redirect("cainiao-subledger-list")
    return redirect("cainiao-preinvoice-detail", pk=pre.pk)


@login_required
def pre_invoice_detail(request, pk):
    pre = get_object_or_404(CainiaoClientPreInvoice, pk=pk)
    charges = charges_for(pre)
    return render(request, "settlements/cainiao_subledger/detail.html", {
        "pre": pre,
        "docs": documents(charges),
        "dyn": dynamic(charges, pre.period_from, pre.period_to),
        "bills": pre.bills.order_by("bill_id"),
        "free_bills": unassigned_bills(),
    })


@login_required
def pre_invoice_checks(request, pk):
    pre = get_object_or_404(CainiaoClientPreInvoice, pk=pk)
    return render(request, "settlements/cainiao_subledger/checks.html", {
        "pre": pre, "c": checks(pre),
    })


@login_required
def pre_invoice_export(request, pk):
    pre = get_object_or_404(CainiaoClientPreInvoice, pk=pk)
    response = HttpResponse(
        export_xlsx(pre),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    name = f"cainiao-{pre.period_from:%Y%m%d}-{pre.period_to:%Y%m%d}.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{name}"'
    return response


@login_required
@require_http_methods(["POST"])
def pre_invoice_update(request, pk):
    pre = get_object_or_404(CainiaoClientPreInvoice, pk=pk)
    action = request.POST.get("action")
    if action == "bills" and pre.status == pre.STATUS_DRAFT:
        add = request.POST.getlist("add")
        remove = request.POST.getlist("remove")
        CainiaoBill.objects.filter(bill_id__in=add, pre_invoice__isnull=True).update(pre_invoice=pre)
        pre.bills.filter(bill_id__in=remove).update(pre_invoice=None)
        messages.success(request, "Faturas Cainiao atualizadas.")
    elif action == "issue":
        invoice = request.POST.get("toconline_invoice", "").strip()
        if not invoice:
            messages.error(request, "Indique o número da fatura do TOConline.")
            return redirect("cainiao-preinvoice-detail", pk=pre.pk)
        pre.toconline_invoice = invoice[:40]
        pre.toconline_credit_note = request.POST.get("toconline_credit_note", "").strip()[:40]
        try:
            pre.issued_at = date.fromisoformat(request.POST.get("issued_at", ""))
        except ValueError:
            pre.issued_at = date.today()
        pre.status = pre.STATUS_ISSUED
        pre.save()
        messages.success(request, "Pré-fatura marcada como emitida no TOConline.")
    elif action == "reopen":
        pre.status = pre.STATUS_DRAFT
        pre.save(update_fields=["status"])
        messages.success(request, "Pré-fatura reaberta.")
    elif action == "notes":
        pre.notes = request.POST.get("notes", "")
        pre.save(update_fields=["notes"])
        messages.success(request, "Notas guardadas.")
    return redirect("cainiao-preinvoice-detail", pk=pre.pk)


@login_required
@require_http_methods(["POST"])
def pre_invoice_delete(request, pk):
    pre = get_object_or_404(CainiaoClientPreInvoice, pk=pk)
    if pre.status != pre.STATUS_DRAFT:
        messages.error(request, "Só uma pré-fatura em rascunho pode ser eliminada.")
        return redirect("cainiao-preinvoice-detail", pk=pre.pk)
    pre.bills.update(pre_invoice=None)
    pre.delete()
    messages.success(request, "Pré-fatura eliminada. As faturas Cainiao voltaram à lista.")
    return redirect("cainiao-subledger-list")
