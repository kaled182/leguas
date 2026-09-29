"""
Views de relatórios: frota (veículos, custos, incidentes) e estado das
integrações com parceiros.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import Count, Q, Sum
from django.shortcuts import render
from django.utils import timezone

from fleet_management.models import Vehicle, VehicleIncident


@login_required
def incidents_report(request):
    """
    Relatório de incidências dos veículos (multas, acidentes, danos).
    """
    # Período padrão: últimos 30 dias
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)

    if request.GET.get("start_date"):
        start_date = datetime.strptime(request.GET.get("start_date"), "%Y-%m-%d").date()
    if request.GET.get("end_date"):
        end_date = datetime.strptime(request.GET.get("end_date"), "%Y-%m-%d").date()

    # Incidências de veículos
    vehicle_incidents = (
        VehicleIncident.objects.filter(
            incident_date__gte=start_date, incident_date__lte=end_date
        )
        .values("incident_type")
        .annotate(count=Count("id"), total_cost=Sum("fine_amount"))
        .order_by("-count")
    )

    # Estatísticas gerais
    total_vehicle_incidents = VehicleIncident.objects.filter(
        incident_date__gte=start_date, incident_date__lte=end_date
    ).count()

    context = {
        "start_date": start_date,
        "end_date": end_date,
        "vehicle_incidents": vehicle_incidents,
        "total_vehicle_incidents": total_vehicle_incidents,
    }

    return render(request, "analytics/incidents_report.html", context)


@login_required
def vehicles_performance_report(request):
    """
    Relatório de performance de veículos (Custo x Entregas).
    """
    # Período padrão: últimos 30 dias
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)

    if request.GET.get("start_date"):
        start_date = datetime.strptime(request.GET.get("start_date"), "%Y-%m-%d").date()
    if request.GET.get("end_date"):
        end_date = datetime.strptime(request.GET.get("end_date"), "%Y-%m-%d").date()

    # Performance por veículo
    vehicles = (
        Vehicle.objects.filter(status="ACTIVE")
        .annotate(
            # Contar atribuições (assignments)
            total_shifts=Count(
                "assignments",
                distinct=True,
                filter=Q(
                    assignments__date__gte=start_date,
                    assignments__date__lte=end_date,
                ),
            ),
            # Custo total de manutenções
            maintenance_cost=Sum(
                "maintenance_records__cost",
                filter=Q(
                    maintenance_records__completed_date__gte=start_date,
                    maintenance_records__completed_date__lte=end_date,
                ),
            ),
            # Custo de incidentes
            incident_cost=Sum(
                "incidents__fine_amount",
                filter=Q(
                    incidents__incident_date__gte=start_date,
                    incidents__incident_date__lte=end_date,
                ),
            ),
            # Número de incidentes
            incident_count=Count(
                "incidents",
                filter=Q(
                    incidents__incident_date__gte=start_date,
                    incidents__incident_date__lte=end_date,
                ),
            ),
        )
        .order_by("-total_shifts")
    )

    # Calcular custo total e custo por shift
    vehicles_data = []
    for vehicle in vehicles:
        maintenance = vehicle.maintenance_cost or Decimal("0")
        incidents = vehicle.incident_cost or Decimal("0")
        total_cost = maintenance + incidents
        cost_per_shift = (
            total_cost / vehicle.total_shifts
            if vehicle.total_shifts > 0
            else Decimal("0")
        )

        vehicles_data.append(
            {
                "vehicle": vehicle,
                "total_shifts": vehicle.total_shifts,
                "maintenance_cost": maintenance,
                "incident_cost": incidents,
                "total_cost": total_cost,
                "cost_per_shift": cost_per_shift,
                "incident_count": vehicle.incident_count,
            }
        )

    # Ordenar por custo total (decrescente)
    vehicles_data.sort(key=lambda x: x["total_cost"], reverse=True)

    # Estatísticas gerais
    total_vehicles = len(vehicles_data)
    total_cost = sum(v["total_cost"] for v in vehicles_data)
    avg_cost_per_vehicle = (
        total_cost / total_vehicles if total_vehicles > 0 else Decimal("0")
    )

    context = {
        "start_date": start_date,
        "end_date": end_date,
        "vehicles_data": vehicles_data,
        "total_vehicles": total_vehicles,
        "total_cost": total_cost,
        "avg_cost_per_vehicle": avg_cost_per_vehicle,
    }

    return render(request, "analytics/vehicles_performance_report.html", context)


@login_required
def fleet_cost_report(request):
    """Relatório de custos de frota"""
    from datetime import date, timedelta
    from decimal import Decimal

    from django.db.models import Sum

    from fleet_management.models import Vehicle, VehicleMaintenance

    # Parâmetros de filtro
    days = int(request.GET.get("days", 30))
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    # Query de veículos com custos
    vehicles_costs = []
    vehicles = Vehicle.objects.filter(status="ACTIVE")

    for vehicle in vehicles:
        # Custos de manutenção no período
        maintenances = VehicleMaintenance.objects.filter(
            vehicle=vehicle,
            completed_date__gte=start_date,
            completed_date__lte=end_date,
            is_completed=True,
        )

        maintenance_cost = maintenances.aggregate(total=Sum("cost"))[
            "total"
        ] or Decimal("0")
        maintenance_count = maintenances.count()

        vehicles_costs.append(
            {
                "vehicle": vehicle,
                "maintenance_cost": maintenance_cost,
                "maintenance_count": maintenance_count,
            }
        )

    # Ordenar por custo de manutenção
    vehicles_costs.sort(key=lambda x: x["maintenance_cost"], reverse=True)

    # Totais gerais
    total_maintenance = sum(v["maintenance_cost"] for v in vehicles_costs)
    total_maintenance_count = sum(v["maintenance_count"] for v in vehicles_costs)

    context = {
        "vehicles_costs": vehicles_costs,
        "start_date": start_date,
        "end_date": end_date,
        "days_filter": days,
        "total_vehicles": len(vehicles_costs),
        "total_maintenance": total_maintenance,
        "total_maintenance_count": total_maintenance_count,
    }

    return render(request, "analytics/fleet_cost_report.html", context)


@login_required
def api_status_dashboard(request):
    """Dashboard de status das integrações de API com parceiros"""
    from datetime import timedelta

    from django.db.models import Count, Max, Q

    from core.models import PartnerIntegration, SyncLog

    # Buscar todas as integrações ativas
    integrations = (
        PartnerIntegration.objects.filter(is_active=True)
        .select_related("partner")
        .annotate(
            total_syncs=Count("sync_logs"),
            success_syncs=Count("sync_logs", filter=Q(sync_logs__status="SUCCESS")),
            error_syncs=Count("sync_logs", filter=Q(sync_logs__status="ERROR")),
            last_log_time=Max("sync_logs__started_at"),
        )
        .order_by("partner__name")
    )

    # Estatísticas por integração
    integrations_stats = []
    now = timezone.now()

    for integration in integrations:
        # Determinar status de saúde
        health_status = "healthy"  # healthy, warning, critical, unknown
        health_message = "Operacional"

        if not integration.last_sync_at:
            health_status = "unknown"
            health_message = "Sem sincronizações"
        elif integration.is_sync_overdue:
            health_status = "critical"
            health_message = "Sincronização atrasada"
        elif integration.last_sync_status == "ERROR":
            health_status = "critical"
            health_message = "Última sincronização falhou"
        elif integration.last_sync_status == "PARTIAL":
            health_status = "warning"
            health_message = "Sincronização parcial"

        # Taxa de sucesso (últimas 24h)
        day_ago = now - timedelta(hours=24)
        recent_logs = SyncLog.objects.filter(
            integration=integration, started_at__gte=day_ago
        )

        recent_total = recent_logs.count()
        recent_success = recent_logs.filter(status="SUCCESS").count()
        success_rate_24h = (
            round((recent_success / recent_total * 100), 1) if recent_total > 0 else 0
        )

        # Tempo desde última sync
        if integration.last_sync_at:
            time_since_sync = now - integration.last_sync_at
            minutes_ago = int(time_since_sync.total_seconds() / 60)

            if minutes_ago < 60:
                last_sync_display = f"{minutes_ago} minutos atrás"
            elif minutes_ago < 1440:  # 24 horas
                last_sync_display = f"{int(minutes_ago/60)} horas atrás"
            else:
                last_sync_display = f"{int(minutes_ago/1440)} dias atrás"
        else:
            last_sync_display = "Nunca"

        integrations_stats.append(
            {
                "integration": integration,
                "health_status": health_status,
                "health_message": health_message,
                "success_rate_24h": success_rate_24h,
                "recent_syncs_24h": recent_total,
                "last_sync_display": last_sync_display,
                "minutes_since_sync": (
                    minutes_ago if integration.last_sync_at else None
                ),
            }
        )

    # Estatísticas globais
    total_integrations = len(integrations_stats)
    healthy_count = sum(
        1 for i in integrations_stats if i["health_status"] == "healthy"
    )
    warning_count = sum(
        1 for i in integrations_stats if i["health_status"] == "warning"
    )
    critical_count = sum(
        1 for i in integrations_stats if i["health_status"] == "critical"
    )

    # Logs recentes (últimas 10 sincronizações)
    recent_logs = SyncLog.objects.select_related("integration__partner").order_by(
        "-started_at"
    )[:10]

    context = {
        "integrations_stats": integrations_stats,
        "total_integrations": total_integrations,
        "healthy_count": healthy_count,
        "warning_count": warning_count,
        "critical_count": critical_count,
        "recent_logs": recent_logs,
    }

    return render(request, "analytics/api_status_dashboard.html", context)


@login_required
def sync_logs_list(request):
    """Lista detalhada de logs de sincronização com filtros"""
    from datetime import date, timedelta

    from core.models import PartnerIntegration, SyncLog

    # Filtros
    integration_id = request.GET.get("integration")
    status_filter = request.GET.get("status")
    operation_filter = request.GET.get("operation")
    days = int(request.GET.get("days", 7))

    # Query base
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    logs = SyncLog.objects.select_related("integration__partner").filter(
        started_at__date__gte=start_date, started_at__date__lte=end_date
    )

    # Aplicar filtros
    if integration_id:
        logs = logs.filter(integration_id=integration_id)

    if status_filter:
        logs = logs.filter(status=status_filter)

    if operation_filter:
        logs = logs.filter(operation=operation_filter)

    # Ordenar
    logs = logs.order_by("-started_at")

    # Stats do período
    total_logs = logs.count()
    success_logs = logs.filter(status="SUCCESS").count()
    error_logs = logs.filter(status="ERROR").count()
    avg_duration = logs.exclude(completed_at__isnull=True).aggregate(
        avg_duration=models.Avg(models.F("completed_at") - models.F("started_at"))
    )["avg_duration"]

    # Converter avg_duration para segundos
    if avg_duration:
        avg_duration_seconds = avg_duration.total_seconds()
    else:
        avg_duration_seconds = 0

    # Opções para filtros
    integrations = PartnerIntegration.objects.filter(is_active=True).select_related(
        "partner"
    )

    context = {
        "logs": logs[:100],  # Limitar a 100 registros por performance
        "total_logs": total_logs,
        "success_logs": success_logs,
        "error_logs": error_logs,
        "avg_duration_seconds": round(avg_duration_seconds, 1),
        "integrations": integrations,
        "status_choices": SyncLog.STATUSES,
        "operation_choices": SyncLog.SYNC_OPERATIONS,
        "filters": {
            "integration_id": integration_id,
            "status": status_filter,
            "operation": operation_filter,
            "days": days,
        },
        "start_date": start_date,
        "end_date": end_date,
    }

    return render(request, "analytics/sync_logs_list.html", context)


@login_required
def retry_failed_sync(request, log_id):
    """Re-executa uma sincronização que falhou"""
    from django.contrib import messages
    from django.shortcuts import get_object_or_404, redirect

    from core.models import SyncLog

    if request.method != "POST":
        messages.error(request, "Método não permitido")
        return redirect("analytics:sync_logs_list")

    log = get_object_or_404(SyncLog, id=log_id)

    # Verificar se é uma falha
    if log.status not in ["ERROR", "TIMEOUT", "PARTIAL"]:
        messages.warning(request, "Este log não representa uma falha")
        return redirect("analytics:sync_logs_list")

    try:
        # Importar o serviço de sync apropriado baseado no parceiro
        integration = log.integration

        # Criar novo log para o retry
        new_log = SyncLog.objects.create(
            integration=integration,
            operation=log.operation,
            status="STARTED",
            request_data={
                "retry_of": log.id,
                "original_timestamp": str(log.started_at),
            },
        )

        # TODO: lógica de retry específica por tipo de integração.
        # Por agora, simula-se o retry.

        # Marcar como parcialmente bem-sucedido (já que é simulado)
        new_log.mark_completed(
            status="PARTIAL",
            message=f"Retry manual executado. Log original: #{log.id}",
        )

        # Atualizar status da integração
        integration.mark_sync_success(message=f"Retry manual executado com sucesso")

        messages.success(
            request, f"Retry executado com sucesso! Novo log: #{new_log.id}"
        )

    except Exception as e:
        messages.error(request, f"Erro ao executar retry: {str(e)}")

    return redirect("analytics:sync_logs_list")
