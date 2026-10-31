"""
URLs da aplicação analytics.
"""

from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "analytics"

urlpatterns = [
    # Sincronização com o ReliableMaps
    path(
        "integrations/status/",
        views.api_status_dashboard,
        name="api_status_dashboard",
    ),
    path("integrations/logs/", views.sync_logs_list, name="sync_logs_list"),
    # A repetição simulada saiu. A rota mantém-se e volta à lista.
    path(
        "integrations/logs/<int:log_id>/retry/",
        RedirectView.as_view(url="/analytics/integrations/logs/"),
        name="retry_failed_sync",
    ),
]
