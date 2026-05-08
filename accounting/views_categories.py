"""CRUD mínimo de ExpenseCategory (categorias de despesa para DRE)."""
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ExpenseCategoryForm
from .models import Bill, ExpenseCategory


@login_required
def category_list(request):
    today = date.today()
    year_start = date(today.year, 1, 1)

    # total_ytd só conta Bills "company_only" (sem driver) — passthrough
    # com motorista é adiantamento, descontado na PF, não despesa real.
    qs = ExpenseCategory.objects.annotate(
        n_bills=Count("bills", filter=Q(bills__driver__isnull=True)),
        total_ytd=Sum(
            "bills__amount_total",
            filter=Q(
                bills__driver__isnull=True,
                bills__issue_date__gte=year_start,
                bills__status__in=[Bill.STATUS_PAID, Bill.STATUS_PENDING],
            ),
        ),
    ).order_by("nature", "sort_order", "name")

    show = (request.GET.get("show") or "active").strip()
    if show == "active":
        qs = qs.filter(is_active=True)
    elif show == "inactive":
        qs = qs.filter(is_active=False)

    return render(request, "accounting/category_list.html", {
        "categorias": qs,
        "filters": {"show": show},
        "year": today.year,
    })


@login_required
def category_create(request):
    if request.method == "POST":
        form = ExpenseCategoryForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f"Categoria '{obj.code}' criada.")
            if request.GET.get("from") == "ocr":
                return redirect("accounting:bill_create")
            return redirect("accounting:category_list")
    else:
        # Pré-preenche a partir de query params (ex: vindo do OCR)
        initial = {}
        for key in ("name", "code", "icon", "nature"):
            v = (request.GET.get(key) or "").strip()
            if v:
                initial[key] = v
        form = ExpenseCategoryForm(initial=initial)
    return render(request, "accounting/category_form.html", {
        "form": form, "is_create": True,
        "from_ocr": request.GET.get("from") == "ocr",
    })


@login_required
def category_edit(request, pk):
    obj = get_object_or_404(ExpenseCategory, pk=pk)
    if request.method == "POST":
        form = ExpenseCategoryForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Categoria actualizada.")
            return redirect("accounting:category_list")
    else:
        form = ExpenseCategoryForm(instance=obj)
    return render(request, "accounting/category_form.html", {
        "form": form, "categoria": obj, "is_create": False,
    })
