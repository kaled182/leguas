"""CRUD de CostCenter (Centro de Custo) e sincronização com HUBs."""
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import CostCenterForm
from .models import Bill, CostCenter


@login_required
def cost_center_list(request):
    """Lista com KPIs e despesas YTD por centro."""
    today = date.today()
    year_start = date(today.year, 1, 1)

    # total_ytd só conta Bills "company_only" (sem driver). Bills com
    # motorista são passthrough — descontados na PF, não despesa do CC.
    qs = CostCenter.objects.select_related("cainiao_hub").annotate(
        n_bills=Count("bills", filter=Q(bills__driver__isnull=True)),
        total_ytd=Sum(
            "bills__amount_total",
            filter=Q(
                bills__driver__isnull=True,
                bills__issue_date__gte=year_start,
                bills__status__in=[Bill.STATUS_PAID, Bill.STATUS_PENDING],
            ),
        ),
    )

    type_f = (request.GET.get("type") or "").strip()
    if type_f:
        qs = qs.filter(type=type_f)

    show = (request.GET.get("show") or "active").strip()
    if show == "active":
        qs = qs.filter(is_active=True)
    elif show == "inactive":
        qs = qs.filter(is_active=False)

    qs = qs.order_by("type", "name")

    # KPIs por tipo
    kpis = {
        "total": CostCenter.objects.filter(is_active=True).count(),
        "hubs": CostCenter.objects.filter(
            is_active=True, type=CostCenter.TYPE_HUB,
        ).count(),
        "frota": CostCenter.objects.filter(
            is_active=True, type=CostCenter.TYPE_FLEET,
        ).count(),
        "admin": CostCenter.objects.filter(
            is_active=True, type=CostCenter.TYPE_ADMIN,
        ).count(),
    }

    # HUBs sem CostCenter (por sincronizar)
    from settlements.models import CainiaoHub
    hubs_sem_cc = CainiaoHub.objects.exclude(
        id__in=CostCenter.objects.exclude(
            cainiao_hub__isnull=True,
        ).values_list("cainiao_hub_id", flat=True),
    )

    return render(request, "accounting/cost_center_list.html", {
        "centros": qs,
        "kpis": kpis,
        "hubs_sem_cc": hubs_sem_cc,
        "filters": {"type": type_f, "show": show},
        "type_choices": CostCenter.TYPE_CHOICES,
        "year": today.year,
    })


@login_required
def cost_center_create(request):
    if request.method == "POST":
        form = CostCenterForm(request.POST)
        if form.is_valid():
            cc = form.save()
            messages.success(
                request, f"Centro de custo '{cc.code}' criado.",
            )
            return redirect("accounting:cost_center_list")
    else:
        form = CostCenterForm()
    return render(request, "accounting/cost_center_form.html", {
        "form": form, "is_create": True,
    })


@login_required
def cost_center_edit(request, pk):
    cc = get_object_or_404(CostCenter, pk=pk)
    if request.method == "POST":
        form = CostCenterForm(request.POST, instance=cc)
        if form.is_valid():
            form.save()
            messages.success(request, "Centro de custo actualizado.")
            return redirect("accounting:cost_center_list")
    else:
        form = CostCenterForm(instance=cc)
    return render(request, "accounting/cost_center_form.html", {
        "form": form, "centro": cc, "is_create": False,
    })


@login_required
@require_http_methods(["POST"])
def cost_center_toggle_active(request, pk):
    cc = get_object_or_404(CostCenter, pk=pk)
    cc.is_active = not cc.is_active
    cc.save(update_fields=["is_active"])
    state = "activado" if cc.is_active else "desactivado"
    messages.success(request, f"Centro '{cc.code}' {state}.")
    return redirect("accounting:cost_center_list")


@login_required
@require_http_methods(["POST"])
def cost_center_sync_hubs(request):
    """Cria CostCenter para HUBs que ainda não têm. Idempotente."""
    from settlements.models import CainiaoHub
    from .signals import _hub_to_cost_center_code

    created = 0
    for hub in CainiaoHub.objects.all():
        if CostCenter.objects.filter(cainiao_hub=hub).exists():
            continue
        code = _hub_to_cost_center_code(hub.name)
        base = code
        i = 2
        while CostCenter.objects.filter(code=code).exists():
            code = f"{base}-{i}"[:20]
            i += 1
        CostCenter.objects.create(
            code=code,
            name=hub.name,
            type=CostCenter.TYPE_HUB,
            cainiao_hub=hub,
            is_active=True,
            notes=f"Criado por sincronização manual (HUB #{hub.id}).",
        )
        created += 1

    if created:
        messages.success(
            request, f"{created} Centro(s) de Custo criado(s) a partir de HUBs."
        )
    else:
        messages.info(request, "Todos os HUBs já têm Centro de Custo.")
    return redirect("accounting:cost_center_list")
