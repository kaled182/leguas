"""Precisa de atenção: o que espera por uma ação da equipa."""
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Count
from django.db.models.functions import Substr
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from drivers_app.context_processors import drivers_counts
from settlements.models import CainiaoOperationTask

CACHE_KEY = "dashboard:attention_packages"
CACHE_SECONDS = 300


def _package_counts():
    today = timezone.localdate()
    tasks = CainiaoOperationTask.objects
    return {
        "stale": tasks.filter(task_status="Stale_Armazem").count(),
        "backlog": tasks.filter(task_status="Driver_received", task_date__lt=today).count(),
        "failures": tasks.filter(task_status="Attempt Failure", task_date=today).count(),
    }


def attention_count(request):
    """Total do contador do menu. Os pacotes ficam 5 minutos em cache."""
    packages = cache.get_or_set(CACHE_KEY, _package_counts, CACHE_SECONDS)
    drivers = drivers_counts(request)
    return (
        sum(packages.values())
        + drivers.get("pending_drivers_count", 0)
        + drivers.get("pending_change_requests_count", 0)
    )


def _backlog_by_cp4():
    today = timezone.localdate()
    return (
        CainiaoOperationTask.objects.filter(task_status="Driver_received", task_date__lt=today)
        .exclude(zip_code="")
        .annotate(cp4=Substr("zip_code", 1, 4))
        .values("cp4")
        .annotate(total=Count("id"))
        .order_by("-total")[:10]
    )


@login_required
def attention(request):
    packages = _package_counts()
    drivers = drivers_counts(request)
    list_url = reverse("cainiao-packages-page")
    candidates = (
        ("pacotes parados há mais de 7 dias", packages["stale"], "danger", f"{list_url}?status=Stale_Armazem"),
        ("pacotes em distribuição há mais de 1 dia", packages["backlog"], "warning", f"{list_url}?status=Driver_received"),
        ("falhas de entrega hoje", packages["failures"], "danger", f"{list_url}?status=Attempt+Failure"),
        ("cadastros por aprovar", drivers.get("pending_drivers_count", 0), "warning", reverse("drivers_app:admin_approve_drivers")),
        ("pedidos de alteração", drivers.get("pending_change_requests_count", 0), "warning", reverse("drivers_app:change_requests_list")),
    )
    return render(request, "dashboard_leguas/attention.html", {
        "items": [
            {"label": label, "count": count, "tone": tone, "url": url}
            for label, count, tone, url in candidates if count
        ],
        "backlog_by_cp4": _backlog_by_cp4(),
    })
