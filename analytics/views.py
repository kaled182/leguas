"""
Views de relatórios: sincronização com o ReliableMaps.
"""

from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from settlements.models import ReliableClaimVerdict, ReliableEpodSync
from system_config.models import SystemConfiguration

# A task corre das 7h às 23h, aos minutos 5 e 35 (my_project/celery.py).
OVERDUE_AFTER = timedelta(hours=2)
OVERDUE_FIRST_HOUR = 9
PERIOD_DAYS = (1, 7, 30, 90)
DEFAULT_DAYS = 7


def _epod_health(cfg, hubs, last_import, now):
    """Estado da importação EPOD: (estado, mensagem)."""
    if not cfg.reliable_epod_sync_enabled:
        return "unknown", "Sincronização desligada"
    if not (cfg.reliable_api_url or "").strip() or not (cfg.reliable_api_key or "").strip():
        return "unknown", "URL ou chave em falta"
    failed = [h.hub or "Sem hub" for h in hubs if h.status == ReliableEpodSync.STATUS_FAILED]
    if failed:
        return "critical", f"Último ficheiro falhou: {', '.join(failed)}"
    in_window = timezone.localtime(now).hour >= OVERDUE_FIRST_HOUR
    if in_window and (not last_import or now - last_import > OVERDUE_AFTER):
        return "warning", "Sem importação há mais de 2 horas"
    return "healthy", ""


def _hub_rows(now):
    """Último ficheiro tratado de cada hub, nos últimos 7 dias."""
    files = (
        ReliableEpodSync.objects.filter(created_at__gte=now - timedelta(days=7))
        .exclude(status__in=[ReliableEpodSync.STATUS_SUPERSEDED, ReliableEpodSync.STATUS_SKIPPED])
        .order_by("-created_at")
    )
    latest = {}
    for item in files:
        latest.setdefault(item.hub, item)
    return sorted(latest.values(), key=lambda item: item.hub)


@login_required
def api_status_dashboard(request):
    """Estado da sincronização com o ReliableMaps. Só lê."""
    now = timezone.now()
    day_ago = now - timedelta(hours=24)
    cfg = SystemConfiguration.get_config()

    treated = ReliableEpodSync.objects.exclude(
        status__in=[ReliableEpodSync.STATUS_SUPERSEDED, ReliableEpodSync.STATUS_SKIPPED]
    ).order_by("-created_at")
    last_import = (
        treated.filter(status=ReliableEpodSync.STATUS_IMPORTED)
        .values_list("created_at", flat=True)
        .first()
    )
    hubs = _hub_rows(now)
    health_status, health_message = _epod_health(cfg, hubs, last_import, now)
    last_verdict = (
        ReliableClaimVerdict.objects.exclude(verdict_at=None)
        .order_by("-verdict_at")
        .values_list("verdict_at", flat=True)
        .first()
    )

    context = {
        "health_status": health_status,
        "health_message": health_message,
        "last_import": last_import,
        "imported_24h": treated.filter(
            status=ReliableEpodSync.STATUS_IMPORTED, created_at__gte=day_ago
        ).count(),
        "failed_24h": treated.filter(
            status=ReliableEpodSync.STATUS_FAILED, created_at__gte=day_ago
        ).count(),
        "hubs": hubs,
        "recent_files": treated[:10],
        "claims_enabled": cfg.reliable_claims_sync_enabled,
        "last_verdict": last_verdict,
    }

    return render(request, "analytics/api_status_dashboard.html", context)


def _period_days(value):
    """Período pedido no URL. Um valor inválido usa o período por omissão."""
    try:
        days = int(value)
    except (TypeError, ValueError):
        return DEFAULT_DAYS
    return days if days in PERIOD_DAYS else DEFAULT_DAYS


@login_required
def sync_logs_list(request):
    """Histórico dos ficheiros do ReliableMaps, com filtros."""
    status_filter = request.GET.get("status")
    hub_filter = request.GET.get("hub")
    days = _period_days(request.GET.get("days"))

    end_date = timezone.localdate()
    start_date = end_date - timedelta(days=days)

    logs = ReliableEpodSync.objects.filter(
        created_at__date__gte=start_date, created_at__date__lte=end_date
    )
    if status_filter:
        logs = logs.filter(status=status_filter)
    if hub_filter:
        logs = logs.filter(hub=hub_filter)
    logs = logs.order_by("-created_at")

    context = {
        "logs": logs[:100],  # Limitar a 100 registos por performance
        "total_logs": logs.count(),
        "imported_logs": logs.filter(status=ReliableEpodSync.STATUS_IMPORTED).count(),
        "failed_logs": logs.filter(status=ReliableEpodSync.STATUS_FAILED).count(),
        "other_logs": logs.filter(
            status__in=[ReliableEpodSync.STATUS_SUPERSEDED, ReliableEpodSync.STATUS_SKIPPED]
        ).count(),
        "status_choices": ReliableEpodSync.STATUS_CHOICES,
        "hubs": ReliableEpodSync.objects.exclude(hub="").order_by("hub").values_list("hub", flat=True).distinct(),
        "filters": {"status": status_filter, "hub": hub_filter, "days": days},
        "start_date": start_date,
        "end_date": end_date,
    }

    return render(request, "analytics/sync_logs_list.html", context)
