from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import ExpenseForm, RevenueForm
from .models import Expenses, Revenues

# Create your views here.


@login_required
def dashboard(request):
    """Dashboard principal com resumo de receitas e despesas"""
    # Resumo de receitas
    total_revenues = (
        Revenues.objects.aggregate(Sum("valor_com_iva"))["valor_com_iva__sum"] or 0
    )
    recent_revenues = Revenues.objects.order_by("-data_entrada")[:5]

    # Resumo de despesas
    total_expenses = (
        Expenses.objects.aggregate(Sum("valor_com_iva"))["valor_com_iva__sum"] or 0
    )
    recent_expenses = Expenses.objects.order_by("-data_entrada")[:5]

    # Despesas pendentes
    pending_expenses = Expenses.objects.filter(pago=False).count()

    context = {
        "total_revenues": total_revenues,
        "total_expenses": total_expenses,
        "balance": total_revenues - total_expenses,
        "recent_revenues": recent_revenues,
        "recent_expenses": recent_expenses,
        "pending_expenses": pending_expenses,
    }
    return render(request, "accounting/dashboard.html", context)


# ===== VIEWS PARA RECEITAS =====


@login_required
def revenue_list(request):
    """Lista todas as receitas com filtros e paginação"""
    revenues = Revenues.objects.all().order_by("-data_entrada")

    # Filtros
    search = request.GET.get("search")
    natureza = request.GET.get("natureza")
    fonte = request.GET.get("fonte")
    data_inicio = request.GET.get("data_inicio")
    data_fim = request.GET.get("data_fim")

    if search:
        revenues = revenues.filter(
            Q(descricao__icontains=search) | Q(referencia__icontains=search)
        )

    if natureza:
        revenues = revenues.filter(natureza=natureza)

    if fonte:
        revenues = revenues.filter(fonte=fonte)

    if data_inicio:
        revenues = revenues.filter(data_entrada__gte=data_inicio)

    if data_fim:
        revenues = revenues.filter(data_entrada__lte=data_fim)

    # Paginação
    paginator = Paginator(revenues, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Total filtrado
    total_filtered = revenues.aggregate(Sum("valor_com_iva"))["valor_com_iva__sum"] or 0

    context = {
        "page_obj": page_obj,
        "revenues": page_obj,
        "total_filtered": total_filtered,
        "natureza_choices": Revenues.NATUREZA_CHOICES,
        "fonte_choices": Revenues.FONTE_CHOICES,
        "filters": {
            "search": search,
            "natureza": natureza,
            "fonte": fonte,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
        },
    }
    return render(request, "accounting/revenue_list.html", context)


@login_required
def revenue_create(request):
    """Criar nova receita"""
    if request.method == "POST":
        form = RevenueForm(request.POST, request.FILES)
        if form.is_valid():
            revenue = form.save(commit=False)
            revenue.user = request.user
            revenue.save()
            messages.success(request, "Receita criada com sucesso!")
            return redirect("accounting:revenue_detail", pk=revenue.pk)
    else:
        form = RevenueForm()

    return render(
        request,
        "accounting/revenue_form.html",
        {"form": form, "title": "Nova Receita"},
    )


@login_required
def revenue_detail(request, pk):
    """Visualizar detalhes de uma receita"""
    revenue = get_object_or_404(Revenues, pk=pk)

    context = {
        "revenue": revenue,
    }
    return render(request, "accounting/revenue_detail.html", context)


@login_required
def revenue_edit(request, pk):
    """Editar receita existente"""
    revenue = get_object_or_404(Revenues, pk=pk)

    if request.method == "POST":
        form = RevenueForm(request.POST, request.FILES, instance=revenue)
        if form.is_valid():
            form.save()
            messages.success(request, "Receita atualizada com sucesso!")
            return redirect("accounting:revenue_detail", pk=revenue.pk)
    else:
        form = RevenueForm(instance=revenue)

    return render(
        request,
        "accounting/revenue_form.html",
        {"form": form, "revenue": revenue, "title": "Editar Receita"},
    )


@login_required
@require_http_methods(["DELETE"])
def revenue_delete(request, pk):
    """Deletar receita (via AJAX)"""
    revenue = get_object_or_404(Revenues, pk=pk)
    revenue.delete()
    return JsonResponse({"success": True})


# ===== VIEWS PARA DESPESAS =====


@login_required
def expense_list(request):
    """Lista todas as despesas com filtros e paginação"""
    expenses = Expenses.objects.all().order_by("-data_entrada")

    # Filtros
    search = request.GET.get("search")
    natureza = request.GET.get("natureza")
    fonte = request.GET.get("fonte")
    pago = request.GET.get("pago")
    data_inicio = request.GET.get("data_inicio")
    data_fim = request.GET.get("data_fim")

    if search:
        expenses = expenses.filter(
            Q(descricao__icontains=search) | Q(referencia__icontains=search)
        )

    if natureza:
        expenses = expenses.filter(natureza=natureza)

    if fonte:
        expenses = expenses.filter(fonte=fonte)

    if pago == "true":
        expenses = expenses.filter(pago=True)
    elif pago == "false":
        expenses = expenses.filter(pago=False)

    if data_inicio:
        expenses = expenses.filter(data_entrada__gte=data_inicio)

    if data_fim:
        expenses = expenses.filter(data_entrada__lte=data_fim)

    # Paginação
    paginator = Paginator(expenses, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Total filtrado
    total_filtered = expenses.aggregate(Sum("valor_com_iva"))["valor_com_iva__sum"] or 0
    total_pending = (
        expenses.filter(pago=False).aggregate(Sum("valor_com_iva"))[
            "valor_com_iva__sum"
        ]
        or 0
    )

    context = {
        "page_obj": page_obj,
        "expenses": page_obj,
        "total_filtered": total_filtered,
        "total_pending": total_pending,
        "natureza_choices": Expenses.NATUREZA_CHOICES,
        "fonte_choices": Expenses.FONTE_CHOICES,
        "filters": {
            "search": search,
            "natureza": natureza,
            "fonte": fonte,
            "pago": pago,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
        },
    }
    return render(request, "accounting/expense_list.html", context)


@login_required
def expense_create(request):
    """Criar nova despesa"""
    if request.method == "POST":
        form = ExpenseForm(request.POST, request.FILES)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.user = request.user
            expense.save()
            messages.success(request, "Despesa criada com sucesso!")
            return redirect("accounting:expense_detail", pk=expense.pk)
    else:
        form = ExpenseForm()

    return render(
        request,
        "accounting/expense_form.html",
        {"form": form, "title": "Nova Despesa"},
    )


@login_required
def expense_detail(request, pk):
    """Visualizar detalhes de uma despesa"""
    expense = get_object_or_404(Expenses, pk=pk)

    context = {
        "expense": expense,
    }
    return render(request, "accounting/expense_detail.html", context)


@login_required
def expense_edit(request, pk):
    """Editar despesa existente"""
    expense = get_object_or_404(Expenses, pk=pk)

    if request.method == "POST":
        form = ExpenseForm(request.POST, request.FILES, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, "Despesa atualizada com sucesso!")
            return redirect("accounting:expense_detail", pk=expense.pk)
    else:
        form = ExpenseForm(instance=expense)

    return render(
        request,
        "accounting/expense_form.html",
        {"form": form, "expense": expense, "title": "Editar Despesa"},
    )


@login_required
@require_http_methods(["DELETE"])
def expense_delete(request, pk):
    """Deletar despesa (via AJAX)"""
    expense = get_object_or_404(Expenses, pk=pk)
    expense.delete()
    return JsonResponse({"success": True})


@login_required
@require_http_methods(["POST"])
def expense_toggle_payment(request, pk):
    """Alternar status de pagamento da despesa (via AJAX)"""
    expense = get_object_or_404(Expenses, pk=pk)

    if expense.pago:
        expense.pago = False
        expense.data_pagamento = None
    else:
        expense.pago = True
        expense.data_pagamento = date.today()

    expense.save()

    return JsonResponse(
        {
            "success": True,
            "pago": expense.pago,
            "data_pagamento": (
                expense.data_pagamento.strftime("%d/%m/%Y")
                if expense.data_pagamento
                else None
            ),
            "status_text": expense.status_pagamento,
        }
    )


# ===== VIEWS DE RELATÓRIOS =====


@login_required
def reports(request):
    """Página de relatórios com gráficos e estatísticas"""
    # Dados para gráficos (últimos 12 meses)
    from datetime import datetime, timedelta

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=365)

    revenues_by_month = []
    expenses_by_month = []

    # Você pode implementar lógica mais complexa aqui para gerar dados mensais

    context = {
        "revenues_by_month": revenues_by_month,
        "expenses_by_month": expenses_by_month,
    }
    return render(request, "accounting/reports.html", context)


# ============================================================================
# Fase 1 — Contas a Pagar (Bills) + DRE
# ============================================================================


from decimal import Decimal
from .forms import BillForm, BillAttachmentForm
from .models import (
    ApprovalRule, BankStatement, BankTransaction,
    Bill, BillApproval, BillAttachment,
    CostCenter, ExpenseCategory,
)


@login_required
def bill_list(request):
    """Lista de contas a pagar com filtros."""
    qs = Bill.objects.select_related(
        "category", "cost_center", "created_by",
    )

    # Filtros
    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)
    cc_id = request.GET.get("cost_center", "").strip()
    if cc_id:
        qs = qs.filter(cost_center_id=cc_id)
    cat_id = request.GET.get("category", "").strip()
    if cat_id:
        qs = qs.filter(category_id=cat_id)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(description__icontains=q)
            | Q(supplier__icontains=q)
            | Q(invoice_number__icontains=q),
        )
    df = request.GET.get("date_from", "").strip()
    if df:
        from django.utils.dateparse import parse_date
        d = parse_date(df)
        if d:
            qs = qs.filter(due_date__gte=d)
    dt = request.GET.get("date_to", "").strip()
    if dt:
        from django.utils.dateparse import parse_date
        d = parse_date(dt)
        if d:
            qs = qs.filter(due_date__lte=d)

    # KPIs
    total_pending = qs.filter(status=Bill.STATUS_PENDING).aggregate(
        s=Sum("amount_total"),
    )["s"] or Decimal("0")
    total_overdue = qs.filter(status=Bill.STATUS_OVERDUE).aggregate(
        s=Sum("amount_total"),
    )["s"] or Decimal("0")
    total_paid = qs.filter(status=Bill.STATUS_PAID).aggregate(
        s=Sum("amount_total"),
    )["s"] or Decimal("0")
    total_awaiting = qs.filter(status=Bill.STATUS_AWAITING).aggregate(
        s=Sum("amount_total"),
    )["s"] or Decimal("0")
    n_overdue = qs.filter(status=Bill.STATUS_OVERDUE).count()
    n_awaiting = qs.filter(status=Bill.STATUS_AWAITING).count()

    page = Paginator(qs, 50).get_page(request.GET.get("page") or 1)

    context = {
        "page_obj": page,
        "total_pending": total_pending,
        "total_overdue": total_overdue,
        "total_paid": total_paid,
        "total_awaiting": total_awaiting,
        "n_overdue": n_overdue,
        "n_awaiting": n_awaiting,
        "filters": {
            "status": status,
            "cost_center": cc_id,
            "category": cat_id,
            "q": q,
            "date_from": df,
            "date_to": dt,
        },
        "cost_centers": CostCenter.objects.filter(is_active=True),
        "categories": ExpenseCategory.objects.filter(is_active=True),
        "STATUS_CHOICES": Bill.STATUS_CHOICES,
    }
    return render(request, "accounting/bill_list.html", context)


@login_required
def bill_create(request):
    if request.method == "POST":
        form = BillForm(request.POST)
        if form.is_valid():
            bill = form.save(commit=False)
            bill.created_by = request.user
            bill.save()
            # Anexos
            for f in request.FILES.getlist("attachments_invoice"):
                BillAttachment.objects.create(
                    bill=bill, kind=BillAttachment.KIND_INVOICE,
                    file=f, uploaded_by=request.user,
                )
            for f in request.FILES.getlist("attachments_proof"):
                BillAttachment.objects.create(
                    bill=bill, kind=BillAttachment.KIND_PROOF,
                    file=f, uploaded_by=request.user,
                )
            messages.success(request, f"Conta '{bill.description}' criada.")
            return redirect("accounting:bill_detail", pk=bill.pk)
    else:
        form = BillForm()
    return render(request, "accounting/bill_form.html", {
        "form": form, "is_create": True,
    })


@login_required
def bill_edit(request, pk):
    bill = get_object_or_404(Bill, pk=pk)
    if request.method == "POST":
        form = BillForm(request.POST, instance=bill)
        if form.is_valid():
            form.save()
            for f in request.FILES.getlist("attachments_invoice"):
                BillAttachment.objects.create(
                    bill=bill, kind=BillAttachment.KIND_INVOICE,
                    file=f, uploaded_by=request.user,
                )
            for f in request.FILES.getlist("attachments_proof"):
                BillAttachment.objects.create(
                    bill=bill, kind=BillAttachment.KIND_PROOF,
                    file=f, uploaded_by=request.user,
                )
            messages.success(request, "Conta actualizada.")
            return redirect("accounting:bill_detail", pk=bill.pk)
    else:
        form = BillForm(instance=bill)
    return render(request, "accounting/bill_form.html", {
        "form": form, "bill": bill, "is_create": False,
    })


@login_required
def bill_detail(request, pk):
    bill = get_object_or_404(
        Bill.objects.select_related(
            "category", "cost_center", "created_by",
        ).prefetch_related("attachments", "approvals__approver"),
        pk=pk,
    )
    can_approve = False
    if bill.status == Bill.STATUS_AWAITING:
        rule = ApprovalRule.rule_for_amount(bill.amount_total)
        can_approve = bool(
            rule and rule.approvers.filter(pk=request.user.pk).exists(),
        )
    return render(request, "accounting/bill_detail.html", {
        "bill": bill,
        "can_approve": can_approve,
    })


@login_required
@require_http_methods(["POST"])
def bill_delete(request, pk):
    """Soft-delete: marca a conta como apagada (auditável e reversível).

    A conta some das listagens / DRE / cash flow, mas fica registada
    com quem apagou, quando e o motivo. Pode ser restaurada na lixeira
    (/contas-a-pagar/lixeira/).
    """
    bill = get_object_or_404(Bill, pk=pk)
    reason = (request.POST.get("reason") or "").strip()
    bill.soft_delete(user=request.user, reason=reason)
    messages.success(
        request,
        f"Conta «{bill.description}» movida para a lixeira. "
        "Pode restaurá-la em Contas a Pagar → Lixeira.",
    )
    return redirect("accounting:bill_list")


@login_required
def bill_trash(request):
    """Lixeira / auditoria — contas a pagar soft-deleted."""
    qs = (
        Bill.all_objects.filter(is_deleted=True)
        .select_related("category", "cost_center", "deleted_by",
                        "created_by")
        .order_by("-deleted_at")
    )
    return render(request, "accounting/bill_trash.html", {
        "bills": qs,
        "total": qs.count(),
    })


@login_required
@require_http_methods(["POST"])
def bill_restore(request, pk):
    """Restaura uma conta a pagar soft-deleted."""
    bill = get_object_or_404(Bill.all_objects, pk=pk, is_deleted=True)
    bill.restore()
    messages.success(request, f"Conta «{bill.description}» restaurada.")
    return redirect("accounting:bill_trash")


@login_required
@require_http_methods(["POST"])
def bill_hard_delete(request, pk):
    """Remoção definitiva — só de contas já na lixeira. Irreversível."""
    bill = get_object_or_404(Bill.all_objects, pk=pk, is_deleted=True)
    desc = bill.description
    bill.delete()
    messages.success(
        request, f"Conta «{desc}» eliminada definitivamente.",
    )
    return redirect("accounting:bill_trash")


@login_required
@require_http_methods(["POST"])
def bill_mark_paid(request, pk):
    bill = get_object_or_404(Bill, pk=pk)
    if bill.status != Bill.STATUS_PAID:
        bill.status = Bill.STATUS_PAID
        bill.paid_date = date.today()
        bill.save()
    return JsonResponse({
        "success": True, "status": bill.status,
        "paid_date": bill.paid_date.isoformat() if bill.paid_date else None,
    })


@login_required
@require_http_methods(["POST"])
def bill_attachment_delete(request, pk):
    att = get_object_or_404(BillAttachment, pk=pk)
    bill_pk = att.bill_id
    att.delete()
    return JsonResponse({"success": True, "bill_id": bill_pk})


@login_required
@require_http_methods(["POST"])
def bill_approve(request, pk):
    """Aprova uma Bill em estado AWAITING. Só users autorizados pela
    ApprovalRule aplicável podem aprovar."""
    bill = get_object_or_404(Bill, pk=pk)
    if bill.status != Bill.STATUS_AWAITING:
        return JsonResponse({
            "success": False,
            "error": f"Bill não está a aguardar aprovação ({bill.get_status_display()}).",
        }, status=400)
    rule = ApprovalRule.rule_for_amount(bill.amount_total)
    if rule and not rule.approvers.filter(pk=request.user.pk).exists():
        return JsonResponse({
            "success": False,
            "error": "Não tens permissão para aprovar bills neste valor.",
        }, status=403)
    BillApproval.objects.create(
        bill=bill, approver=request.user,
        decision=BillApproval.DECISION_APPROVED,
        comments=request.POST.get("comments", ""),
    )
    bill.status = Bill.STATUS_PENDING
    bill.save()
    return JsonResponse({"success": True, "status": bill.status})


@login_required
@require_http_methods(["POST"])
def bill_reject(request, pk):
    """Rejeita uma Bill em estado AWAITING."""
    bill = get_object_or_404(Bill, pk=pk)
    if bill.status != Bill.STATUS_AWAITING:
        return JsonResponse({
            "success": False,
            "error": f"Bill não está a aguardar aprovação ({bill.get_status_display()}).",
        }, status=400)
    rule = ApprovalRule.rule_for_amount(bill.amount_total)
    if rule and not rule.approvers.filter(pk=request.user.pk).exists():
        return JsonResponse({
            "success": False,
            "error": "Não tens permissão para rejeitar bills neste valor.",
        }, status=403)
    BillApproval.objects.create(
        bill=bill, approver=request.user,
        decision=BillApproval.DECISION_REJECTED,
        comments=request.POST.get("comments", ""),
    )
    bill.status = Bill.STATUS_REJECTED
    bill.save()
    return JsonResponse({"success": True, "status": bill.status})


@login_required
@require_http_methods(["POST"])
def bill_generate_next(request, pk):
    """Gera a próxima instância de uma conta recorrente."""
    bill = get_object_or_404(Bill, pk=pk)
    if bill.recurrence == Bill.RECURRENCE_NONE:
        return JsonResponse(
            {"success": False, "error": "Esta conta não é recorrente."},
            status=400,
        )
    new_bill = bill.generate_next_instance(by_user=request.user)
    if not new_bill:
        return JsonResponse(
            {"success": False,
             "error": "Próxima instância já existe ou não foi gerada."},
            status=400,
        )
    return JsonResponse({
        "success": True,
        "id": new_bill.pk,
        "description": new_bill.description,
        "due_date": new_bill.due_date.isoformat(),
        "redirect_url": f"/accounting/contas-a-pagar/{new_bill.pk}/",
    })


# ── DRE (Demonstração de Resultados) ────────────────────────────────────────


def _resolve_dre_period(request):
    """Lê date_from/date_to dos GET com fallback ao mês actual."""
    from django.utils.dateparse import parse_date
    today = date.today()
    df = parse_date(request.GET.get("date_from") or "")
    dt = parse_date(request.GET.get("date_to") or "")
    if not df:
        df = today.replace(day=1)
    if not dt:
        dt = today
    if df > dt:
        df, dt = dt, df
    return df, dt


def _compute_dre_metrics(date_from, date_to):
    """Calcula receita, custos e margens para um período."""
    from django.db.models import Count
    from settlements.models import (
        CainiaoOperationTask, CainiaoHub, DriverPreInvoice,
        WaybillReturn,
    )
    from core.models import Partner
    from core.finance import resolve_partner_price

    cainiao_partner = Partner.objects.filter(
        name__iexact="CAINIAO",
    ).first()
    partner_price = resolve_partner_price(cainiao_partner) \
        if cainiao_partner else Decimal("0")

    # Receita por HUB
    revenues_by_hub = []
    total_revenue = Decimal("0")
    for hub in CainiaoHub.objects.prefetch_related("cp4_codes"):
        cp4s = list(hub.cp4_codes.values_list("cp4", flat=True))
        if not cp4s:
            continue
        hub_q = Q()
        for c in cp4s:
            hub_q |= Q(zip_code__startswith=c)
        delivered = (
            CainiaoOperationTask.objects.filter(
                task_date__range=(date_from, date_to),
                task_status="Delivered",
            ).filter(hub_q).count()
        )
        rev = partner_price * delivered
        total_revenue += rev
        cc = CostCenter.objects.filter(cainiao_hub=hub).first()
        revenues_by_hub.append({
            "hub_id": hub.id,
            "hub_name": hub.name,
            "deliveries": delivered,
            "revenue": rev,
            "cost_center_id": cc.id if cc else None,
            "cost_center_name": cc.name if cc else "—",
        })

    total_driver_cost = DriverPreInvoice.objects.filter(
        periodo_inicio__lte=date_to,
        periodo_fim__gte=date_from,
    ).aggregate(s=Sum("total_a_receber"))["s"] or Decimal("0")

    total_returns_cost = WaybillReturn.objects.filter(
        return_date__range=(date_from, date_to),
    ).aggregate(s=Sum("return_cost_eur"))["s"] or Decimal("0")

    # Excluir Bills passthrough (com driver) — são adiantamentos a
    # motoristas que serão descontados na PF, não despesa real da empresa.
    # O IVA dedutível dessas Bills mantém-se como benefício separado
    # (não entra no DRE como receita; reduz o IVA a entregar no apuramento).
    bills_qs = Bill.objects.company_only().filter(
        issue_date__range=(date_from, date_to),
    ).exclude(status=Bill.STATUS_CANCELLED).select_related(
        "category", "cost_center",
    )

    by_nature = {
        ExpenseCategory.NATURE_DIRETO: [],
        ExpenseCategory.NATURE_VARIAVEL: [],
        ExpenseCategory.NATURE_FIXO: [],
        ExpenseCategory.NATURE_FINANCEIRO: [],
    }
    sums = {
        ExpenseCategory.NATURE_DIRETO: Decimal("0"),
        ExpenseCategory.NATURE_VARIAVEL: Decimal("0"),
        ExpenseCategory.NATURE_FIXO: Decimal("0"),
        ExpenseCategory.NATURE_FINANCEIRO: Decimal("0"),
    }

    cat_agg = bills_qs.values(
        "category_id", "category__name", "category__nature",
        "category__icon",
    ).annotate(
        total=Sum("amount_total"), n=Count("id"),
    ).order_by("category__nature", "category__name")
    for r in cat_agg:
        nature = r["category__nature"]
        item = {
            "category_id": r["category_id"],
            "name": r["category__name"],
            "icon": r["category__icon"] or "",
            "total": r["total"] or Decimal("0"),
            "n": r["n"],
        }
        by_nature.setdefault(nature, []).append(item)
        sums[nature] = sums.get(nature, Decimal("0")) + (
            r["total"] or Decimal("0")
        )

    by_cost_center = {}
    cc_agg = bills_qs.values(
        "cost_center_id", "cost_center__name", "cost_center__type",
    ).annotate(total=Sum("amount_total")).order_by("-total")
    for r in cc_agg:
        by_cost_center[r["cost_center__name"]] = {
            "id": r["cost_center_id"],
            "type": r["cost_center__type"],
            "total": r["total"] or Decimal("0"),
        }

    total_direct_extra = sums[ExpenseCategory.NATURE_DIRETO]
    total_direct_op = (
        total_driver_cost + total_returns_cost + total_direct_extra
    )
    margem_bruta = total_revenue - total_direct_op
    total_variavel = sums[ExpenseCategory.NATURE_VARIAVEL]
    margem_contribuicao = margem_bruta - total_variavel
    total_fixo = sums[ExpenseCategory.NATURE_FIXO]
    ebitda = margem_contribuicao - total_fixo
    total_financeiro = sums[ExpenseCategory.NATURE_FINANCEIRO]
    resultado_liquido = ebitda - total_financeiro

    return {
        "partner_price": partner_price,
        "total_revenue": total_revenue,
        "revenues_by_hub": revenues_by_hub,
        "total_driver_cost": total_driver_cost,
        "total_returns_cost": total_returns_cost,
        "total_direct_extra": total_direct_extra,
        "direct_extra_lines": by_nature[ExpenseCategory.NATURE_DIRETO],
        "total_direct_op": total_direct_op,
        "margem_bruta": margem_bruta,
        "total_variavel": total_variavel,
        "variavel_lines": by_nature[ExpenseCategory.NATURE_VARIAVEL],
        "margem_contribuicao": margem_contribuicao,
        "total_fixo": total_fixo,
        "fixo_lines": by_nature[ExpenseCategory.NATURE_FIXO],
        "ebitda": ebitda,
        "total_financeiro": total_financeiro,
        "financeiro_lines": by_nature[ExpenseCategory.NATURE_FINANCEIRO],
        "resultado_liquido": resultado_liquido,
        "by_cost_center": by_cost_center,
    }


@login_required
def bank_statement_list(request):
    """Lista de extractos bancários importados."""
    qs = BankStatement.objects.all().order_by("-uploaded_at")
    return render(request, "accounting/bank_statement_list.html", {
        "statements": qs,
    })


@login_required
def bank_statement_upload(request):
    """Upload de CSV/OFX e parse para BankTransaction."""
    if request.method != "POST":
        return render(
            request, "accounting/bank_statement_upload.html",
        )
    f = request.FILES.get("file")
    if not f:
        messages.error(request, "Anexa um ficheiro CSV ou OFX.")
        return redirect("accounting:bank_statement_upload")

    from .bank_parser import parse_statement
    try:
        rows = parse_statement(f.name, f.read())
    except Exception as e:
        messages.error(request, f"Erro a parsear ficheiro: {e}")
        return redirect("accounting:bank_statement_upload")
    if not rows:
        messages.error(
            request,
            "Não foi possível extrair transacções do ficheiro.",
        )
        return redirect("accounting:bank_statement_upload")

    name = request.POST.get("name") or f.name
    period_from = min(r["date"] for r in rows)
    period_to = max(r["date"] for r in rows)
    f.seek(0)  # reset para guardar de novo
    statement = BankStatement.objects.create(
        name=name,
        period_from=period_from, period_to=period_to,
        file=f,
        n_transactions=len(rows),
        uploaded_by=request.user,
    )
    BankTransaction.objects.bulk_create([
        BankTransaction(
            statement=statement,
            date=r["date"],
            description=r["description"],
            direction=r["direction"],
            amount=r["amount"],
            external_id=r.get("external_id", ""),
        )
        for r in rows
    ])
    messages.success(
        request,
        f"{len(rows)} transacções importadas de '{name}'.",
    )
    return redirect(
        "accounting:bank_statement_detail", pk=statement.pk,
    )


@login_required
def bank_statement_detail(request, pk):
    """Detalhe de extracto + sugestões de matching para cada transacção."""
    statement = get_object_or_404(BankStatement, pk=pk)
    txs = list(
        statement.transactions
        .select_related("matched_bill")
        .order_by("date", "id"),
    )
    # Pré-computar sugestões para débitos não conciliados
    rows = []
    for tx in txs:
        suggestions = []
        pf_suggestions = []
        if tx.direction == BankTransaction.DIRECTION_DEBIT and not tx.matched_bill_id:
            suggestions = list(tx.suggest_bill_matches())
            pf_suggestions = tx.suggest_pf_matches()
        rows.append({
            "tx": tx,
            "suggestions": suggestions,
            "pf_suggestions": pf_suggestions,
        })
    n_matched = sum(1 for tx in txs if tx.matched_bill_id)
    n_pending = sum(
        1 for tx in txs
        if tx.direction == BankTransaction.DIRECTION_DEBIT
        and not tx.matched_bill_id
    )
    return render(request, "accounting/bank_statement_detail.html", {
        "statement": statement,
        "rows": rows,
        "n_matched": n_matched,
        "n_pending": n_pending,
        "n_total": len(txs),
    })


@login_required
@require_http_methods(["POST"])
def bank_transaction_match(request, pk):
    """Concilia uma transacção a uma Bill (e marca a Bill como PAID)."""
    from django.utils import timezone as _tz
    tx = get_object_or_404(BankTransaction, pk=pk)
    bill_id = request.POST.get("bill_id")
    bill = get_object_or_404(Bill, pk=bill_id)
    tx.matched_bill = bill
    tx.matched_at = _tz.now()
    tx.matched_by = request.user
    tx.save()
    # Se a Bill ainda não está paga, marca como paga na data da transacção
    if bill.status != Bill.STATUS_PAID:
        bill.status = Bill.STATUS_PAID
        bill.paid_date = tx.date
        bill.save()
    # Atualizar contagem na statement
    s = tx.statement
    s.n_matched = s.transactions.exclude(
        matched_bill__isnull=True,
    ).count()
    s.save(update_fields=["n_matched"])
    return JsonResponse({
        "success": True,
        "tx_id": tx.pk,
        "bill_id": bill.pk,
        "bill_status": bill.status,
    })


@login_required
@require_http_methods(["POST"])
def bank_transaction_unmatch(request, pk):
    """Remove a conciliação (mantém a Bill como está)."""
    tx = get_object_or_404(BankTransaction, pk=pk)
    tx.matched_bill = None
    tx.matched_at = None
    tx.matched_by = None
    tx.save()
    s = tx.statement
    s.n_matched = s.transactions.exclude(
        matched_bill__isnull=True,
    ).count()
    s.save(update_fields=["n_matched"])
    return JsonResponse({"success": True, "tx_id": tx.pk})


def _compute_break_even(date_from, date_to, include_awaiting=True):
    """Cálculo do ponto de equilíbrio para um período."""
    from datetime import date as _d
    from django.db.models import Count
    from settlements.models import (
        CainiaoOperationTask, CainiaoHub, DriverPreInvoice,
        CainiaoPlanningPackage, WaybillReturn,
    )
    from core.models import Partner
    from core.finance import resolve_partner_price

    today = _d.today()

    # ── Receita realizada ───────────────────────────────────────────────
    cainiao_partner = Partner.objects.filter(
        name__iexact="CAINIAO",
    ).first()
    partner_price = resolve_partner_price(cainiao_partner) \
        if cainiao_partner else Decimal("0")
    delivered_qs = CainiaoOperationTask.objects.filter(
        task_date__range=(date_from, date_to),
        task_status="Delivered",
    )
    n_delivered = delivered_qs.count()
    revenue = partner_price * n_delivered

    # Receita por HUB
    by_hub = []
    for hub in CainiaoHub.objects.prefetch_related("cp4_codes"):
        cp4s = list(hub.cp4_codes.values_list("cp4", flat=True))
        if not cp4s:
            continue
        hub_q = Q()
        for c in cp4s:
            hub_q |= Q(zip_code__startswith=c)
        n = delivered_qs.filter(hub_q).count()
        by_hub.append({
            "hub_id": hub.id, "hub_name": hub.name,
            "delivered": n, "revenue": partner_price * n,
        })

    # ── Custos directos ────────────────────────────────────────────────
    cd_drivers = DriverPreInvoice.objects.filter(
        periodo_inicio__lte=date_to,
        periodo_fim__gte=date_from,
    ).aggregate(s=Sum("total_a_receber"))["s"] or Decimal("0")
    cd_returns = WaybillReturn.objects.filter(
        return_date__range=(date_from, date_to),
    ).aggregate(s=Sum("return_cost_eur"))["s"] or Decimal("0")
    cd_extra = Bill.objects.company_only().filter(
        issue_date__range=(date_from, date_to),
        category__nature=ExpenseCategory.NATURE_DIRETO,
    ).exclude(status=Bill.STATUS_CANCELLED).aggregate(
        s=Sum("amount_total"),
    )["s"] or Decimal("0")
    cost_direct = cd_drivers + cd_returns + cd_extra

    # ── Custos fixos (Bills FIXO + FINANCEIRO + VARIAVEL) ──────────────
    # company_only(): exclui Bills passthrough (com driver), que são
    # adiantamentos compensados na PF do motorista.
    cf_statuses = [Bill.STATUS_PENDING, Bill.STATUS_OVERDUE, Bill.STATUS_PAID]
    if include_awaiting:
        cf_statuses.append(Bill.STATUS_AWAITING)
    cf_qs = Bill.objects.company_only().filter(
        due_date__range=(date_from, date_to),
        status__in=cf_statuses,
        category__nature__in=[
            ExpenseCategory.NATURE_VARIAVEL,
            ExpenseCategory.NATURE_FIXO,
            ExpenseCategory.NATURE_FINANCEIRO,
        ],
    )
    cost_fixed = cf_qs.aggregate(s=Sum("amount_total"))["s"] or Decimal("0")
    n_awaiting_in_cf = cf_qs.filter(
        status=Bill.STATUS_AWAITING,
    ).count() if include_awaiting else 0
    cost_awaiting_in_cf = (
        cf_qs.filter(status=Bill.STATUS_AWAITING).aggregate(
            s=Sum("amount_total"),
        )["s"] or Decimal("0")
    ) if include_awaiting else Decimal("0")

    # ── Métricas core ──────────────────────────────────────────────────
    margem_contrib = revenue - cost_direct
    margem_unit = (
        margem_contrib / n_delivered if n_delivered else Decimal("0")
    )
    if margem_unit > 0:
        pkgs_be = int((cost_fixed / margem_unit).to_integral_value(
            rounding="ROUND_UP",
        ))
    else:
        pkgs_be = None  # impossível com a margem actual
    pkgs_falta = max(0, pkgs_be - n_delivered) if pkgs_be else None
    pct_atingido = (
        float(margem_contrib / cost_fixed * 100)
        if cost_fixed > 0 else 100.0
    )
    be_atingido = margem_contrib >= cost_fixed

    # ── Ritmo ──────────────────────────────────────────────────────────
    days_total = (date_to - date_from).days + 1
    days_elapsed = max(1, min(
        days_total, (today - date_from).days + 1,
    )) if today >= date_from else 0
    days_remaining = max(0, (date_to - today).days)
    rate_actual = (
        n_delivered / days_elapsed if days_elapsed > 0 else 0
    )
    rate_needed = (
        pkgs_falta / days_remaining
        if (pkgs_falta and days_remaining) else 0
    )

    # ── Forecast ───────────────────────────────────────────────────────
    forecast_pkgs = CainiaoPlanningPackage.objects.filter(
        operation_date__gt=today,
        operation_date__lte=date_to,
    ).count()
    forecast_revenue = partner_price * forecast_pkgs
    projected_total_pkgs = n_delivered + forecast_pkgs
    projected_total_rev = revenue + forecast_revenue
    # Custo directo escalonado linearmente pela qty
    cost_per_pkg = (
        cost_direct / n_delivered if n_delivered else partner_price * Decimal("0.7")
    )
    projected_cd = cost_per_pkg * projected_total_pkgs
    projected_margem = projected_total_rev - projected_cd
    projected_be_atingivel = projected_margem >= cost_fixed
    # Estimar dia do BE (linha cumulativa cruzando CF)
    be_day = None
    if margem_unit > 0 and pkgs_falta:
        # Precisamos pkgs_falta entregas a rate_actual/dia
        days_until_be = pkgs_falta / rate_actual if rate_actual else None
        if days_until_be:
            from datetime import timedelta
            be_day = today + timedelta(days=int(days_until_be))

    # ── Sensibilidade (variações de ±5% em alavancas) ──────────────────
    def _be_with(price_factor, cost_factor):
        new_price = partner_price * Decimal(str(price_factor))
        new_revenue_unit = new_price
        new_cost_unit = cost_per_pkg * Decimal(str(cost_factor))
        m = new_revenue_unit - new_cost_unit
        if m <= 0:
            return None
        return int(
            (cost_fixed / m).to_integral_value(rounding="ROUND_UP"),
        )

    sensitivity = [
        {"label": "Partner price +5%", "be": _be_with(1.05, 1.0)},
        {"label": "Partner price −5%", "be": _be_with(0.95, 1.0)},
        {"label": "Custo motorista −5%", "be": _be_with(1.0, 0.95)},
        {"label": "Custo motorista +5%", "be": _be_with(1.0, 1.05)},
    ]

    return {
        "date_from": date_from,
        "date_to": date_to,
        "today": today,
        "include_awaiting": include_awaiting,
        # Receita
        "partner_price": partner_price,
        "n_delivered": n_delivered,
        "revenue": revenue,
        "by_hub": by_hub,
        # Custos
        "cost_direct": cost_direct,
        "cd_drivers": cd_drivers,
        "cd_returns": cd_returns,
        "cd_extra": cd_extra,
        "cost_fixed": cost_fixed,
        "n_awaiting_in_cf": n_awaiting_in_cf,
        "cost_awaiting_in_cf": cost_awaiting_in_cf,
        # Núcleo break-even
        "margem_contrib": margem_contrib,
        "margem_unit": margem_unit,
        "pkgs_be": pkgs_be,
        "pkgs_falta": pkgs_falta,
        "pct_atingido": pct_atingido,
        "be_atingido": be_atingido,
        # Ritmo
        "days_total": days_total,
        "days_elapsed": days_elapsed,
        "days_remaining": days_remaining,
        "rate_actual": rate_actual,
        "rate_needed": rate_needed,
        # Forecast
        "forecast_pkgs": forecast_pkgs,
        "forecast_revenue": forecast_revenue,
        "projected_total_pkgs": projected_total_pkgs,
        "projected_total_rev": projected_total_rev,
        "projected_margem": projected_margem,
        "projected_be_atingivel": projected_be_atingivel,
        "be_day": be_day,
        # Sensibilidade
        "sensitivity": sensitivity,
        "cost_per_pkg": cost_per_pkg,
    }


def _compute_be_history(months=12):
    """Histórico de break-even — atingiu/não para últimos N meses."""
    from calendar import monthrange
    from datetime import date as _d
    today = _d.today()
    out = []
    y, m = today.year, today.month
    for _ in range(months):
        first = _d(y, m, 1)
        last = _d(y, m, monthrange(y, m)[1])
        # Não calcular para meses futuros
        if first > today:
            atingido = None
            mc = cf = None
        else:
            data = _compute_break_even(first, min(last, today))
            mc = data["margem_contrib"]
            cf = data["cost_fixed"]
            atingido = data["be_atingido"]
        out.append({
            "year": y, "month": m,
            "label": f"{m:02d}/{y}",
            "atingido": atingido,
            "margem_contrib": mc,
            "cost_fixed": cf,
        })
        m -= 1
        if m <= 0:
            m = 12
            y -= 1
    out.reverse()
    return out


@login_required
def break_even_monitor(request):
    """Monitor da operação — termómetro break-even + cards + gráfico."""
    from datetime import date as _d
    from django.utils.dateparse import parse_date
    today = _d.today()
    df = parse_date(request.GET.get("date_from") or "")
    dt = parse_date(request.GET.get("date_to") or "")
    if not df:
        df = today.replace(day=1)
    if not dt:
        from calendar import monthrange
        dt = df.replace(
            day=monthrange(df.year, df.month)[1],
        )
    if df > dt:
        df, dt = dt, df
    include_awaiting = (
        request.GET.get("include_awaiting", "1") != "0"
    )

    data = _compute_break_even(df, dt, include_awaiting)
    history = _compute_be_history(12)

    return render(request, "accounting/break_even.html", {
        "d": data,
        "history": history,
        "include_awaiting": include_awaiting,
    })


@login_required
def break_even_data(request):
    """Endpoint JSON usado pelo auto-refresh do monitor."""
    from datetime import date as _d
    from django.utils.dateparse import parse_date
    today = _d.today()
    df = parse_date(request.GET.get("date_from") or "") or today.replace(day=1)
    dt = parse_date(request.GET.get("date_to") or "")
    if not dt:
        from calendar import monthrange
        dt = df.replace(day=monthrange(df.year, df.month)[1])
    include_awaiting = (
        request.GET.get("include_awaiting", "1") != "0"
    )
    data = _compute_break_even(df, dt, include_awaiting)
    # Cumulativo dia-a-dia
    from datetime import timedelta
    from django.db.models import Count
    from settlements.models import CainiaoOperationTask
    cumulative = []
    cum_pkgs = 0
    cum_rev = Decimal("0")
    by_day = dict(
        CainiaoOperationTask.objects.filter(
            task_date__range=(df, dt),
            task_status="Delivered",
        ).values("task_date").annotate(
            n=Count("id"),
        ).values_list("task_date", "n")
    )
    d = df
    while d <= dt:
        n = by_day.get(d, 0)
        cum_pkgs += n
        cum_rev += data["partner_price"] * n
        cumulative.append({
            "date": d.isoformat(),
            "delivered": n,
            "cum_pkgs": cum_pkgs,
            "cum_revenue": float(cum_rev),
            "is_future": d > today,
        })
        d += timedelta(days=1)

    return JsonResponse({
        "success": True,
        "today": today.isoformat(),
        "n_delivered": data["n_delivered"],
        "revenue": float(data["revenue"]),
        "cost_direct": float(data["cost_direct"]),
        "cost_fixed": float(data["cost_fixed"]),
        "margem_contrib": float(data["margem_contrib"]),
        "margem_unit": float(data["margem_unit"]),
        "pkgs_be": data["pkgs_be"],
        "pkgs_falta": data["pkgs_falta"],
        "pct_atingido": data["pct_atingido"],
        "be_atingido": data["be_atingido"],
        "rate_actual": float(data["rate_actual"]),
        "rate_needed": float(data["rate_needed"]),
        "days_remaining": data["days_remaining"],
        "forecast_pkgs": data["forecast_pkgs"],
        "projected_be_atingivel": data["projected_be_atingivel"],
        "be_day": data["be_day"].isoformat() if data["be_day"] else None,
        "cumulative": cumulative,
        "by_hub": [
            {**h, "revenue": float(h["revenue"])}
            for h in data["by_hub"]
        ],
    })


@login_required
def cash_flow_projection(request):
    """Projecção de fluxo de caixa — N dias a partir de `start`.

    Híbrido realizado + previsto, sincronizado com o DRE Realizado:

      Datas passadas (< hoje) — REALIZADO
        Saídas: Bills da empresa com paid_date no dia (status=PAID).
        Entradas: pacotes Cainiao com task_status=Delivered nesse dia
                  × preço-parceiro (mesmo cálculo do DRE).

      Datas futuras (>= hoje) — PREVISTO
        Saídas: Bills com due_date no dia em status pendente
                (AWAITING/PENDING/OVERDUE), mais Bills já pagas hoje.
        Entradas: forecast via CainiaoPlanningPackage.operation_date.
    """
    from datetime import timedelta
    from django.db.models import Count
    from django.utils.dateparse import parse_date
    from settlements.models import (
        CainiaoHub, CainiaoOperationTask, CainiaoPlanningPackage,
    )
    from core.models import Partner
    from core.finance import resolve_partner_price

    today = date.today()
    horizon_days = int(request.GET.get("days") or 30)
    horizon_days = max(7, min(horizon_days, 180))
    start = parse_date(request.GET.get("start") or "") or today
    # `end` agora é relativo a `start` (não a hoje) — janela = horizon_days
    end = start + timedelta(days=horizon_days - 1)

    # Limites realizado / previsto
    realized_end = min(end, today - timedelta(days=1))  # < hoje
    forecast_start = max(start, today)                  # >= hoje
    has_realized = start <= realized_end
    has_forecast = forecast_start <= end

    # Saldo inicial (opcional, default 0)
    try:
        opening_balance = Decimal(
            str(request.GET.get("opening") or "0"),
        )
    except Exception:
        opening_balance = Decimal("0")

    # ── SAÍDAS ──────────────────────────────────────────────────────────
    by_day_out = {}      # date -> Decimal
    bills_detail = []    # para tabela inferior (mistura realizado + previsto)

    # Passado — bills pagas (cash basis): paid_date no intervalo passado
    if has_realized:
        paid_past = (
            Bill.objects.company_only()
            .filter(
                paid_date__gte=start, paid_date__lte=realized_end,
                status=Bill.STATUS_PAID,
            )
            .select_related("category", "cost_center")
            .order_by("paid_date")
        )
        for b in paid_past:
            val = b.paid_amount or b.amount_total
            by_day_out.setdefault(b.paid_date, Decimal("0"))
            by_day_out[b.paid_date] += val
            bills_detail.append(b)

    # Hoje em diante — bills pendentes pelo due_date
    if has_forecast:
        pending_future = (
            Bill.objects.company_only()
            .filter(
                due_date__gte=forecast_start, due_date__lte=end,
                status__in=[
                    Bill.STATUS_AWAITING, Bill.STATUS_PENDING,
                    Bill.STATUS_OVERDUE,
                ],
            )
            .select_related("category", "cost_center")
            .order_by("due_date")
        )
        for b in pending_future:
            by_day_out.setdefault(b.due_date, Decimal("0"))
            by_day_out[b.due_date] += b.amount_total
            bills_detail.append(b)

        # Bills já pagas HOJE (saída real do caixa de hoje)
        if start <= today <= end:
            paid_today = (
                Bill.objects.company_only()
                .filter(paid_date=today, status=Bill.STATUS_PAID)
                .select_related("category", "cost_center")
            )
            for b in paid_today:
                val = b.paid_amount or b.amount_total
                by_day_out.setdefault(today, Decimal("0"))
                by_day_out[today] += val
                bills_detail.append(b)

    # ── ENTRADAS ────────────────────────────────────────────────────────
    cainiao_partner = Partner.objects.filter(
        name__iexact="CAINIAO",
    ).first()
    partner_price = resolve_partner_price(cainiao_partner) \
        if cainiao_partner else Decimal("0")

    # Constrói filtro hub (mesmo do DRE)
    hub_q = Q()
    has_hubs = False
    for hub in CainiaoHub.objects.prefetch_related("cp4_codes"):
        for c in hub.cp4_codes.values_list("cp4", flat=True):
            hub_q |= Q(zip_code__startswith=c)
            has_hubs = True

    by_day_in = {}

    # Passado — entregas realizadas (idêntico ao DRE)
    if has_realized and has_hubs:
        delivered_agg = (
            CainiaoOperationTask.objects
            .filter(
                task_date__gte=start, task_date__lte=realized_end,
                task_status="Delivered",
            )
            .filter(hub_q)
            .values("task_date")
            .annotate(n=Count("id"))
        )
        for r in delivered_agg:
            by_day_in[r["task_date"]] = partner_price * r["n"]

    # Hoje + futuro — forecast pelo Planning
    if has_forecast:
        plan_qs = (
            CainiaoPlanningPackage.objects
            .filter(
                operation_date__gte=forecast_start,
                operation_date__lte=end,
            )
            .values("operation_date")
            .annotate(n=Count("id"))
            .order_by("operation_date")
        )
        for r in plan_qs:
            by_day_in[r["operation_date"]] = partner_price * r["n"]

    # ── Linha do tempo dia-a-dia ────────────────────────────────────────
    timeline = []
    balance = opening_balance
    n_days = (end - start).days + 1
    total_in = Decimal("0")
    total_out = Decimal("0")
    for i in range(n_days):
        d = start + timedelta(days=i)
        inn = by_day_in.get(d, Decimal("0"))
        out = by_day_out.get(d, Decimal("0"))
        balance += (inn - out)
        total_in += inn
        total_out += out
        timeline.append({
            "date": d,
            "weekday": ["Seg","Ter","Qua","Qui","Sex","Sáb","Dom"][d.weekday()],
            "inflow": inn,
            "outflow": out,
            "net": inn - out,
            "balance": balance,
            "negative": balance < 0,
            "is_past": d < today,
            "is_today": d == today,
        })

    # Ordena bills_detail por data relevante (paid_date para passado,
    # due_date para futuro) e limita a 200
    bills_detail.sort(
        key=lambda b: b.paid_date if b.status == Bill.STATUS_PAID
        else b.due_date,
    )
    bills_detail = bills_detail[:200]

    # Dias críticos (saldo negativo)
    critical_days = [t for t in timeline if t["negative"]]

    context = {
        "start": start,
        "end": end,
        "horizon_days": horizon_days,
        "opening_balance": opening_balance,
        "total_in": total_in,
        "total_out": total_out,
        "net_change": total_in - total_out,
        "final_balance": opening_balance + total_in - total_out,
        "timeline": timeline,
        "bills_detail": bills_detail,
        "critical_days": critical_days,
        "n_critical": len(critical_days),
        "partner_price": partner_price,
    }
    return render(
        request, "accounting/cash_flow.html", context,
    )


def _delta_pct(current, previous):
    """Variação percentual entre dois Decimal/numbers. None se sem base."""
    if previous in (None, 0, Decimal("0")):
        return None
    return float((current - previous) / abs(previous) * 100)


@login_required
def dre(request):
    """Demonstração de Resultados — agregação por período + comparativo."""
    from datetime import timedelta

    date_from, date_to = _resolve_dre_period(request)
    span = (date_to - date_from).days + 1

    # Período actual
    cur = _compute_dre_metrics(date_from, date_to)

    # Comparativos: período anterior (mesma duração) e ano anterior
    prev_to = date_from - timedelta(days=1)
    prev_from = prev_to - timedelta(days=span - 1)
    prev = _compute_dre_metrics(prev_from, prev_to)

    yoy_from = date_from.replace(year=date_from.year - 1)
    yoy_to = date_to.replace(year=date_to.year - 1)
    yoy = _compute_dre_metrics(yoy_from, yoy_to)

    def pct_of_revenue(x):
        rev = cur["total_revenue"]
        return float(x / rev * 100) if rev else 0

    # Deltas para cada KPI principal vs período anterior e ano anterior
    metric_keys = [
        "total_revenue", "total_direct_op", "margem_bruta",
        "total_variavel", "margem_contribuicao",
        "total_fixo", "ebitda",
        "total_financeiro", "resultado_liquido",
    ]
    deltas = {}
    for k in metric_keys:
        deltas[k] = {
            "vs_prev_pct": _delta_pct(cur[k], prev[k]),
            "vs_yoy_pct": _delta_pct(cur[k], yoy[k]),
            "prev": prev[k],
            "yoy": yoy[k],
        }

    context = {
        "date_from": date_from,
        "date_to": date_to,
        "prev_from": prev_from, "prev_to": prev_to,
        "yoy_from": yoy_from, "yoy_to": yoy_to,
        # Receitas
        "total_revenue": cur["total_revenue"],
        "revenues_by_hub": cur["revenues_by_hub"],
        "partner_price": cur["partner_price"],
        # Custos directos
        "total_driver_cost": cur["total_driver_cost"],
        "total_returns_cost": cur["total_returns_cost"],
        "total_direct_extra": cur["total_direct_extra"],
        "direct_extra_lines": cur["direct_extra_lines"],
        "total_direct_op": cur["total_direct_op"],
        "margem_bruta": cur["margem_bruta"],
        "margem_bruta_pct": pct_of_revenue(cur["margem_bruta"]),
        # Variáveis
        "total_variavel": cur["total_variavel"],
        "variavel_lines": cur["variavel_lines"],
        "margem_contribuicao": cur["margem_contribuicao"],
        "margem_contribuicao_pct":
            pct_of_revenue(cur["margem_contribuicao"]),
        # Fixos
        "total_fixo": cur["total_fixo"],
        "fixo_lines": cur["fixo_lines"],
        "ebitda": cur["ebitda"],
        "ebitda_pct": pct_of_revenue(cur["ebitda"]),
        # Financeiro
        "total_financeiro": cur["total_financeiro"],
        "financeiro_lines": cur["financeiro_lines"],
        "resultado_liquido": cur["resultado_liquido"],
        "resultado_pct": pct_of_revenue(cur["resultado_liquido"]),
        # Centro de custo
        "by_cost_center": cur["by_cost_center"],
        # Comparativos
        "deltas": deltas,
    }
    return render(request, "accounting/dre.html", context)
