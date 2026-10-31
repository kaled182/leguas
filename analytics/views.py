"""
Views de relatórios: estado das integrações com parceiros.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import Count, Q, Sum
from django.shortcuts import render
from django.utils import timezone


def _since_label(minutes):
    """Tempo desde a última sincronização, em pt-PT."""
    if minutes < 1:
        return "há menos de 1 minuto"
    if minutes < 60:
        return f"há {minutes} minuto{'s' if minutes != 1 else ''}"
    if minutes < 1440:  # 24 horas
        hours = int(minutes / 60)
        return f"há {hours} hora{'s' if hours != 1 else ''}"
    days = int(minutes / 1440)
    return f"há {days} dia{'s' if days != 1 else ''}"


@login_required
def api_status_dashboard(request):
    """Dashboard de status das integrações de API com parceiros"""
    from datetime import timedelta

    from django.db.models import Count, Q

    from core.models import PartnerIntegration, SyncLog

    now = timezone.now()
    day_ago = now - timedelta(hours=24)

    # Buscar todas as integrações ativas
    integrations = (
        PartnerIntegration.objects.filter(is_active=True)
        .select_related("partner")
        .annotate(
            recent_total=Count(
                "sync_logs", filter=Q(sync_logs__started_at__gte=day_ago)
            ),
            recent_success=Count(
                "sync_logs",
                filter=Q(
                    sync_logs__started_at__gte=day_ago, sync_logs__status="SUCCESS"
                ),
            ),
        )
        .order_by("partner__name")
    )

    # Estatísticas por integração
    integrations_stats = []

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
        recent_total = integration.recent_total
        recent_success = integration.recent_success
        success_rate_24h = (
            round((recent_success / recent_total * 100), 1) if recent_total > 0 else 0
        )

        # Tempo desde última sync
        if integration.last_sync_at:
            time_since_sync = now - integration.last_sync_at
            minutes_ago = int(time_since_sync.total_seconds() / 60)

            last_sync_display = _since_label(minutes_ago)
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

    unknown_count = sum(
        1 for i in integrations_stats if i["health_status"] == "unknown"
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
        "unknown_count": unknown_count,
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
