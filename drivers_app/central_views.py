"""Central de Motoristas — vista admin moderna que substitui modais por
páginas dedicadas e reúne KPIs, filtros e acções rápidas."""
from datetime import date, timedelta

from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from .models import DriverProfile, EmpresaParceira, DriverProfileChangeRequest


def _is_admin(u):
    return u.is_authenticated and (u.is_staff or u.is_superuser)


admin_required = user_passes_test(_is_admin, login_url="/auth/login/")


@admin_required
def drivers_central(request):
    """Página central de gestão de motoristas — moderna, sem modais."""
    from contracts.models import ContractTemplate, DriverContract
    from customauth.models import DriverAccess

    # ─── Filtros ───
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    vinculo = request.GET.get("vinculo", "")
    fleet_id = request.GET.get("fleet", "")
    sort = request.GET.get("sort", "name")
    flag = request.GET.get("flag", "")  # 'pending_changes' / 'no_contract' / 'no_access'

    qs = DriverProfile.objects.select_related("empresa_parceira")

    if q:
        qs = qs.filter(
            Q(nome_completo__icontains=q)
            | Q(apelido__icontains=q)
            | Q(nif__icontains=q)
            | Q(courier_id_cainiao__icontains=q)
            | Q(telefone__icontains=q)
            | Q(email__icontains=q)
        )

    if status:
        qs = qs.filter(status=status)

    if vinculo:
        qs = qs.filter(tipo_vinculo=vinculo)

    if fleet_id:
        if fleet_id == "none":
            qs = qs.filter(empresa_parceira__isnull=True)
        else:
            qs = qs.filter(empresa_parceira_id=fleet_id)

    # ─── Anotações ───
    today = timezone.now().date()
    month_start = today.replace(day=1)

    # Pacotes do mês via signatures (todos os couriers que tocaram)
    # Para performance, calculamos depois por driver na renderização (top N)

    # Driver_ids com pedidos de alteração pending
    pending_change_driver_ids = set(
        DriverProfileChangeRequest.objects.filter(status="pending")
        .values_list("driver_id", flat=True)
        .distinct()
    )

    # Driver_ids sem contrato activo (any active template)
    active_templates = ContractTemplate.objects.filter(
        is_active=True, effective_from__lte=today,
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gte=today)
    )
    has_active_templates = active_templates.exists()
    drivers_with_contracts = set(
        DriverContract.objects.filter(revoked_at__isnull=True)
        .values_list("driver_id", flat=True).distinct()
    )

    # Driver_ids com DriverAccess activo
    drivers_with_access = set(
        DriverAccess.objects.filter(is_active=True, driver_profile__isnull=False)
        .values_list("driver_profile_id", flat=True)
    )

    # Aplicar flags filter (depois das outras queries)
    if flag == "pending_changes":
        qs = qs.filter(id__in=pending_change_driver_ids)
    elif flag == "no_contract" and has_active_templates:
        qs = qs.exclude(id__in=drivers_with_contracts)
    elif flag == "no_access":
        qs = qs.exclude(id__in=drivers_with_access)

    # Ordenação
    if sort == "name":
        qs = qs.order_by("nome_completo")
    elif sort == "recent":
        qs = qs.order_by("-created_at")
    elif sort == "status":
        qs = qs.order_by("status", "nome_completo")
    else:
        qs = qs.order_by("nome_completo")

    drivers_list = list(qs[:300])

    # Anotar info para cada driver mostrado
    for d in drivers_list:
        d.has_pending_changes = d.id in pending_change_driver_ids
        d.has_contract = d.id in drivers_with_contracts
        d.has_access = d.id in drivers_with_access

    # ─── KPIs (sobre TODOS, não só filtrados) ───
    all_drivers = DriverProfile.objects.all()
    total_drivers = all_drivers.count()
    counts = {
        "total": total_drivers,
        "ativo": all_drivers.filter(status="ATIVO").count(),
        "pendente": all_drivers.filter(status__in=["PENDENTE", "EM_ANALISE"]).count(),
        "bloqueado": all_drivers.filter(status="BLOQUEADO").count(),
        "pending_changes": len(pending_change_driver_ids),
        "no_contract": (
            all_drivers.exclude(id__in=drivers_with_contracts).count()
            if has_active_templates else 0
        ),
        "no_access": all_drivers.exclude(id__in=drivers_with_access).count(),
    }

    fleets = EmpresaParceira.objects.filter(ativo=True).order_by("nome")

    return render(request, "drivers_app/admin/drivers_central.html", {
        "drivers": drivers_list,
        "counts": counts,
        "q": q,
        "status_filter": status,
        "vinculo_filter": vinculo,
        "fleet_filter": fleet_id,
        "sort_filter": sort,
        "flag_filter": flag,
        "fleets": fleets,
        "shown_count": len(drivers_list),
        "filtered_count": qs.count() if q or status or vinculo or fleet_id or flag else total_drivers,
    })
