from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import VehicleForm, VehicleMaintenanceForm
from .models import (
    Vehicle,
    VehicleAssignment,
    VehicleIncident,
    VehicleMaintenance,
)


@login_required
def vehicle_list(request):
    """Lista de veículos com filtros e paginação"""
    vehicles = Vehicle.objects.all()

    # Filtros
    search = request.GET.get("search", "")
    status_filter = request.GET.get("status", "")
    vehicle_type_filter = request.GET.get("vehicle_type", "")

    if search:
        vehicles = vehicles.filter(
            Q(license_plate__icontains=search)
            | Q(brand__icontains=search)
            | Q(model__icontains=search)
            | Q(owner__icontains=search)
        )

    if status_filter:
        vehicles = vehicles.filter(status=status_filter)

    if vehicle_type_filter:
        vehicles = vehicles.filter(vehicle_type=vehicle_type_filter)

    # Estatísticas
    total_count = Vehicle.objects.count()
    active_count = Vehicle.objects.filter(status="ACTIVE").count()
    maintenance_count = Vehicle.objects.filter(status="MAINTENANCE").count()

    # Alertas - veículos com inspeção ou seguro expirando
    today = date.today()
    alert_period = today + timedelta(days=30)

    inspection_alerts = Vehicle.objects.filter(
        status="ACTIVE",
        inspection_expiry__lte=alert_period,
        inspection_expiry__gte=today,
    ).count()

    insurance_alerts = Vehicle.objects.filter(
        status="ACTIVE",
        insurance_expiry__lte=alert_period,
        insurance_expiry__gte=today,
    ).count()

    # Paginação
    paginator = Paginator(vehicles, 25)
    page_number = request.GET.get("page")
    vehicles = paginator.get_page(page_number)

    context = {
        "vehicles": vehicles,
        "search": search,
        "status_filter": status_filter,
        "vehicle_type_filter": vehicle_type_filter,
        "total_count": total_count,
        "active_count": active_count,
        "maintenance_count": maintenance_count,
        "inspection_alerts": inspection_alerts,
        "insurance_alerts": insurance_alerts,
        "status_choices": Vehicle.STATUS_CHOICES,
        "vehicle_types": Vehicle.VEHICLE_TYPES,
    }
    return render(request, "fleet_management/vehicle_list.html", context)


@login_required
def vehicle_detail(request, pk):
    """Detalhes de um veículo"""
    vehicle = get_object_or_404(Vehicle, pk=pk)

    # Buscar atribuições recentes
    assignments = (
        VehicleAssignment.objects.filter(vehicle=vehicle)
        .select_related("driver")
        .order_by("-start_date")[:10]
    )

    # Buscar manutenções recentes
    maintenances = VehicleMaintenance.objects.filter(vehicle=vehicle).order_by(
        "-scheduled_date"
    )[:10]

    # Buscar incidentes
    incidents = VehicleIncident.objects.filter(vehicle=vehicle).order_by(
        "-incident_date"
    )[:10]

    # Verificar alertas
    today = date.today()
    inspection_alert = None
    insurance_alert = None

    if vehicle.inspection_expiry:
        days_to_inspection = (vehicle.inspection_expiry - today).days
        if days_to_inspection < 0:
            inspection_alert = {
                "status": "expired",
                "days": abs(days_to_inspection),
            }
        elif days_to_inspection <= 30:
            inspection_alert = {
                "status": "warning",
                "days": days_to_inspection,
            }

    if vehicle.insurance_expiry:
        days_to_insurance = (vehicle.insurance_expiry - today).days
        if days_to_insurance < 0:
            insurance_alert = {
                "status": "expired",
                "days": abs(days_to_insurance),
            }
        elif days_to_insurance <= 30:
            insurance_alert = {"status": "warning", "days": days_to_insurance}

    context = {
        "vehicle": vehicle,
        "assignments": assignments,
        "maintenances": maintenances,
        "incidents": incidents,
        "inspection_alert": inspection_alert,
        "insurance_alert": insurance_alert,
    }
    return render(request, "fleet_management/vehicle_detail.html", context)


@login_required
def vehicle_create(request):
    """Criar novo veículo"""
    if request.method == "POST":
        form = VehicleForm(request.POST)
        if form.is_valid():
            vehicle = form.save()
            messages.success(
                request, f"Veículo {vehicle.license_plate} criado com sucesso!"
            )
            return redirect("fleet:vehicle-detail", pk=vehicle.pk)
    else:
        form = VehicleForm()

    context = {"form": form, "vehicle": None}
    return render(request, "fleet_management/vehicle_form.html", context)


@login_required
def vehicle_edit(request, pk):
    """Editar veículo existente"""
    vehicle = get_object_or_404(Vehicle, pk=pk)

    if request.method == "POST":
        form = VehicleForm(request.POST, instance=vehicle)
        if form.is_valid():
            vehicle = form.save()
            messages.success(
                request,
                f"Veículo {vehicle.license_plate} atualizado com sucesso!",
            )
            return redirect("fleet:vehicle-detail", pk=vehicle.pk)
    else:
        form = VehicleForm(instance=vehicle)

    context = {"form": form, "vehicle": vehicle}
    return render(request, "fleet_management/vehicle_form.html", context)


@login_required
def vehicle_toggle_status(request, pk):
    """Alternar status do veículo (ativo/manutenção/inativo)"""
    vehicle = get_object_or_404(Vehicle, pk=pk)

    if request.method == "POST":
        new_status = request.POST.get("new_status")
        if new_status in dict(Vehicle.STATUS_CHOICES):
            vehicle.status = new_status
            vehicle.save()
            messages.success(
                request,
                f"Status do veículo {vehicle.license_plate} alterado para {vehicle.get_status_display()}",
            )
        else:
            messages.error(request, "Status inválido")

    return redirect("fleet:vehicle-detail", pk=pk)


@login_required
def fleet_dashboard(request):
    """Dashboard geral da frota"""

    # Estatísticas gerais
    total_vehicles = Vehicle.objects.count()
    active_vehicles = Vehicle.objects.filter(status="ACTIVE").count()
    maintenance_vehicles = Vehicle.objects.filter(status="MAINTENANCE").count()
    inactive_vehicles = Vehicle.objects.filter(status="INACTIVE").count()

    # Distribuição por tipo
    vehicles_by_type = (
        Vehicle.objects.values("vehicle_type")
        .annotate(count=Count("id"))
        .order_by("vehicle_type")
    )

    # Alertas
    today = date.today()
    alert_period = today + timedelta(days=30)

    inspection_expiring = Vehicle.objects.filter(
        status="ACTIVE",
        inspection_expiry__lte=alert_period,
        inspection_expiry__gte=today,
    ).order_by("inspection_expiry")

    insurance_expiring = Vehicle.objects.filter(
        status="ACTIVE",
        insurance_expiry__lte=alert_period,
        insurance_expiry__gte=today,
    ).order_by("insurance_expiry")

    # Veículos recentemente em manutenção
    recent_maintenances = (
        VehicleMaintenance.objects.filter(is_completed=True)
        .select_related("vehicle")
        .order_by("-completed_date")[:5]
    )

    # Incidentes recentes
    recent_incidents = VehicleIncident.objects.select_related(
        "vehicle", "driver"
    ).order_by("-incident_date")[:5]

    # Veículos atualmente atribuídos (hoje)
    current_assignments = VehicleAssignment.objects.filter(date=today).select_related(
        "vehicle", "driver"
    )

    context = {
        "stats": {
            "total": total_vehicles,
            "active": active_vehicles,
            "maintenance": maintenance_vehicles,
            "inactive": inactive_vehicles,
        },
        "total_vehicles": total_vehicles,
        "active_vehicles": active_vehicles,
        "maintenance_vehicles": maintenance_vehicles,
        "inactive_vehicles": inactive_vehicles,
        "vehicles_by_type": vehicles_by_type,
        "expiring_inspections": inspection_expiring,
        "expiring_insurance": insurance_expiring,
        "recent_maintenances": recent_maintenances,
        "recent_incidents": recent_incidents,
        "current_assignments": current_assignments,
    }
    return render(request, "fleet_management/fleet_dashboard.html", context)


@login_required
def maintenance_list(request):
    """Lista de manutenções"""
    maintenances = VehicleMaintenance.objects.select_related("vehicle").all()

    # Filtros
    completed_filter = request.GET.get("completed", "")
    vehicle_filter = request.GET.get("vehicle", "")
    maintenance_type_filter = request.GET.get("maintenance_type", "")

    if completed_filter:
        if completed_filter == "true":
            maintenances = maintenances.filter(is_completed=True)
        elif completed_filter == "false":
            maintenances = maintenances.filter(is_completed=False)

    if vehicle_filter:
        maintenances = maintenances.filter(vehicle_id=vehicle_filter)

    if maintenance_type_filter:
        maintenances = maintenances.filter(maintenance_type=maintenance_type_filter)

    # Paginação
    paginator = Paginator(maintenances, 25)
    page_number = request.GET.get("page")
    maintenances = paginator.get_page(page_number)

    # Veículos para filtro
    vehicles = Vehicle.objects.filter(status="ACTIVE").order_by("license_plate")

    context = {
        "maintenances": maintenances,
        "completed_filter": completed_filter,
        "vehicle_filter": vehicle_filter,
        "maintenance_type_filter": maintenance_type_filter,
        "vehicles": vehicles,
        "maintenance_types": VehicleMaintenance.MAINTENANCE_TYPES,
    }
    return render(request, "fleet_management/maintenance_list.html", context)


@login_required
def maintenance_calendar(request):
    """Calendário de manutenções"""
    import json

    # Buscar todas as manutenções
    maintenances = VehicleMaintenance.objects.select_related("vehicle").all()

    # Preparar eventos para o calendário (formato FullCalendar)
    events = []
    for maintenance in maintenances:
        # Evento para agendamento
        if maintenance.scheduled_date:
            events.append(
                {
                    "id": f"scheduled_{maintenance.id}",
                    "title": f"{maintenance.vehicle.license_plate} - {maintenance.get_maintenance_type_display()}",
                    "start": maintenance.scheduled_date.isoformat(),
                    "allDay": True,
                    "backgroundColor": (
                        "#f59e0b" if not maintenance.is_completed else "#10b981"
                    ),
                    "borderColor": (
                        "#f59e0b" if not maintenance.is_completed else "#10b981"
                    ),
                    "extendedProps": {
                        "maintenance_id": maintenance.id,
                        "vehicle": str(maintenance.vehicle),
                        "type": maintenance.get_maintenance_type_display(),
                        "cost": (float(maintenance.cost) if maintenance.cost else 0),
                        "workshop": maintenance.workshop or "N/A",
                        "completed": maintenance.is_completed,
                    },
                }
            )

        # Evento para conclusão (se diferente do agendamento)
        if (
            maintenance.completed_date
            and maintenance.completed_date != maintenance.scheduled_date
        ):
            events.append(
                {
                    "id": f"completed_{maintenance.id}",
                    "title": f"✓ {maintenance.vehicle.license_plate} - Concluído",
                    "start": maintenance.completed_date.isoformat(),
                    "allDay": True,
                    "backgroundColor": "#10b981",
                    "borderColor": "#10b981",
                    "extendedProps": {
                        "maintenance_id": maintenance.id,
                        "vehicle": str(maintenance.vehicle),
                        "type": maintenance.get_maintenance_type_display(),
                        "completed": True,
                    },
                }
            )

    context = {
        "events_json": json.dumps(events),
        "maintenance_types": VehicleMaintenance.MAINTENANCE_TYPES,
    }
    return render(request, "fleet_management/maintenance_calendar.html", context)


@login_required
def maintenance_detail(request, pk):
    """Detalhes de uma manutenção"""
    maintenance = get_object_or_404(
        VehicleMaintenance.objects.select_related("vehicle"), pk=pk
    )

    context = {
        "maintenance": maintenance,
    }
    return render(request, "fleet_management/maintenance_detail.html", context)


@login_required
def maintenance_create(request):
    """Criar nova manutenção (agendar)"""
    if request.method == "POST":
        form = VehicleMaintenanceForm(request.POST)
        if form.is_valid():
            maintenance = form.save()
            messages.success(
                request,
                f"Manutenção agendada com sucesso para {maintenance.vehicle}.",
            )
            return redirect("fleet:maintenance_detail", pk=maintenance.pk)
    else:
        form = VehicleMaintenanceForm()

        # Pré-preencher veículo se fornecido na query string
        vehicle_id = request.GET.get("vehicle")
        if vehicle_id:
            form.initial["vehicle"] = vehicle_id

    context = {
        "form": form,
        "title": "Agendar Manutenção",
    }
    return render(request, "fleet_management/maintenance_form.html", context)


@login_required
def maintenance_edit(request, pk):
    """Editar manutenção existente (incluindo registrar conclusão)"""
    maintenance = get_object_or_404(VehicleMaintenance, pk=pk)

    if request.method == "POST":
        form = VehicleMaintenanceForm(request.POST, instance=maintenance)
        if form.is_valid():
            maintenance = form.save()

            # Mensagem específica se foi marcada como concluída
            if maintenance.is_completed and maintenance.completed_date:
                messages.success(
                    request,
                    f"Manutenção de {maintenance.vehicle} registrada como concluída.",
                )
            else:
                messages.success(
                    request, f"Manutenção de {maintenance.vehicle} atualizada."
                )

            return redirect("fleet:maintenance_detail", pk=maintenance.pk)
    else:
        form = VehicleMaintenanceForm(instance=maintenance)

    context = {
        "form": form,
        "maintenance": maintenance,
        "title": "Editar Manutenção",
    }
    return render(request, "fleet_management/maintenance_form.html", context)


@login_required
def incident_list(request):
    """Lista de incidentes"""
    incidents = VehicleIncident.objects.select_related("vehicle", "driver").all()

    # Filtros
    incident_type_filter = request.GET.get("incident_type", "")
    vehicle_filter = request.GET.get("vehicle", "")

    if incident_type_filter:
        incidents = incidents.filter(incident_type=incident_type_filter)

    if vehicle_filter:
        incidents = incidents.filter(vehicle_id=vehicle_filter)

    # Paginação
    paginator = Paginator(incidents, 25)
    page_number = request.GET.get("page")
    incidents = paginator.get_page(page_number)

    # Veículos para filtro
    vehicles = Vehicle.objects.all().order_by("license_plate")

    context = {
        "incidents": incidents,
        "incident_type_filter": incident_type_filter,
        "vehicle_filter": vehicle_filter,
        "vehicles": vehicles,
        "incident_types": VehicleIncident.INCIDENT_TYPES,
    }
    return render(request, "fleet_management/incident_list.html", context)
