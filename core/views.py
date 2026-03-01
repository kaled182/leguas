from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import PartnerForm, PartnerIntegrationForm
from .models import Partner, PartnerIntegration


@login_required
def partner_list(request):
    """Lista de parceiros com filtros e paginação"""
    partners_qs = Partner.objects.all()

    # Filtros
    search = request.GET.get("search", "")
    status_filter = request.GET.get("status", "")

    if search:
        partners_qs = partners_qs.filter(
            Q(name__icontains=search)
            | Q(nif__icontains=search)
            | Q(contact_email__icontains=search)
        )

    if status_filter == "active":
        partners_qs = partners_qs.filter(is_active=True)
    elif status_filter == "inactive":
        partners_qs = partners_qs.filter(is_active=False)

    # Anotar com contagens
    partners_qs = partners_qs.annotate(
        integrations_count=Count("integrations"),
        active_integrations_count=Count(
            "integrations", filter=Q(integrations__is_active=True)
        ),
    )

    # Ordenação
    partners_qs = partners_qs.order_by("-is_active", "name")

    # Paginação
    paginator = Paginator(partners_qs, 25)
    page = request.GET.get("page", 1)

    try:
        partners = paginator.page(page)
    except PageNotAnInteger:
        partners = paginator.page(1)
    except EmptyPage:
        partners = paginator.page(paginator.num_pages)

    context = {
        "partners": partners,
        "search": search,
        "status_filter": status_filter,
        "total_count": partners_qs.count(),
    }

    return render(request, "core/partner_list.html", context)


@login_required
def partner_detail(request, pk):
    """Detalhes de um parceiro"""
    partner = get_object_or_404(Partner, pk=pk)

    # Integrações do parceiro
    integrations = partner.integrations.all().order_by("-is_active", "-last_sync_at")

    # Estatísticas (se o model Order existir e tiver FK para Partner)
    try:
        orders_stats = {
            "total": partner.orders.count(),
            "pending": partner.orders.filter(current_status="PENDING").count(),
            "in_progress": partner.orders.filter(
                current_status__in=["PICKED_UP", "IN_TRANSIT"]
            ).count(),
            "delivered": partner.orders.filter(current_status="DELIVERED").count(),
            "failed": partner.orders.filter(current_status="FAILED").count(),
        }
    except BaseException:
        orders_stats = None

    context = {
        "partner": partner,
        "integrations": integrations,
        "orders_stats": orders_stats,
    }

    return render(request, "core/partner_detail.html", context)


@login_required
def partner_create(request):
    """Criar novo parceiro"""
    if request.method == "POST":
        form = PartnerForm(request.POST)
        if form.is_valid():
            partner = form.save()
            messages.success(request, f'Parceiro "{partner.name}" criado com sucesso!')
            return redirect("core:partner-detail", pk=partner.pk)
    else:
        form = PartnerForm()

    context = {
        "form": form,
        "title": "Novo Parceiro",
        "button_text": "Criar Parceiro",
    }

    return render(request, "core/partner_form.html", context)


@login_required
def partner_edit(request, pk):
    """Editar parceiro existente"""
    partner = get_object_or_404(Partner, pk=pk)

    if request.method == "POST":
        form = PartnerForm(request.POST, instance=partner)
        if form.is_valid():
            partner = form.save()
            messages.success(
                request, f'Parceiro "{partner.name}" atualizado com sucesso!'
            )
            return redirect("core:partner-detail", pk=partner.pk)
    else:
        form = PartnerForm(instance=partner)

    context = {
        "form": form,
        "partner": partner,
        "title": f"Editar {partner.name}",
        "button_text": "Salvar Alterações",
    }

    return render(request, "core/partner_form.html", context)


@login_required
def partner_toggle_status(request, pk):
    """Ativar/desativar parceiro"""
    partner = get_object_or_404(Partner, pk=pk)
    partner.is_active = not partner.is_active
    partner.save()

    status = "ativado" if partner.is_active else "desativado"
    messages.success(request, f'Parceiro "{partner.name}" {status}!')

    return redirect("core:partner-detail", pk=partner.pk)


@login_required
def integration_create(request, partner_pk):
    """Criar nova integração para um parceiro"""
    partner = get_object_or_404(Partner, pk=partner_pk)

    if request.method == "POST":
        form = PartnerIntegrationForm(request.POST)
        if form.is_valid():
            integration = form.save(commit=False)
            integration.partner = partner
            integration.save()
            messages.success(request, f"Integração criada com sucesso!")
            return redirect("core:partner-detail", pk=partner.pk)
    else:
        form = PartnerIntegrationForm()

    context = {
        "form": form,
        "partner": partner,
        "title": f"Nova Integração - {partner.name}",
        "button_text": "Criar Integração",
    }

    return render(request, "core/integration_form.html", context)


@login_required
def integration_edit(request, pk):
    """Editar integração existente"""
    integration = get_object_or_404(PartnerIntegration, pk=pk)

    if request.method == "POST":
        form = PartnerIntegrationForm(request.POST, instance=integration)
        if form.is_valid():
            integration = form.save()
            messages.success(request, f"Integração atualizada com sucesso!")
            return redirect("core:partner-detail", pk=integration.partner.pk)
    else:
        form = PartnerIntegrationForm(instance=integration)

    context = {
        "form": form,
        "integration": integration,
        "partner": integration.partner,
        "title": f"Editar Integração - {integration.partner.name}",
        "button_text": "Salvar Alterações",
    }

    return render(request, "core/integration_form.html", context)


@login_required
def integration_toggle_status(request, pk):
    """Ativar/desativar integração"""
    integration = get_object_or_404(PartnerIntegration, pk=pk)
    integration.is_active = not integration.is_active
    integration.save()

    status = "ativada" if integration.is_active else "desativada"
    messages.success(request, f"Integração {status}!")

    return redirect("core:partner-detail", pk=integration.partner.pk)


@login_required
def integrations_dashboard(request):
    """Dashboard de integrações - status geral"""
    integrations = (
        PartnerIntegration.objects.select_related("partner")
        .filter(is_active=True)
        .order_by("-last_sync_at")
    )

    # Estatísticas
    total_integrations = integrations.count()

    # Integrações com sincronização atrasada (2x a frequência esperada)
    overdue_integrations = [i for i in integrations if i.is_sync_overdue]

    # Últimas 10 sincronizações com erro
    error_integrations = PartnerIntegration.objects.filter(
        last_sync_status="ERROR"
    ).order_by("-last_sync_at")[:10]

    context = {
        "integrations": integrations,
        "total_integrations": total_integrations,
        "overdue_integrations": overdue_integrations,
        "error_integrations": error_integrations,
        "overdue_count": len(overdue_integrations),
    }

    return render(request, "core/integrations_dashboard.html", context)
