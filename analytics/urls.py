"""
URLs da aplicação analytics.
"""

from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    # Relatórios de frota
    path("incidents/", views.incidents_report, name="incidents_report"),
    path("vehicles/", views.vehicles_performance_report, name="vehicles_report"),
    path(
        "reports/fleet-costs/",
        views.fleet_cost_report,
        name="fleet_cost_report",
    ),
    # Integrações & API Status
    path(
        "integrations/status/",
        views.api_status_dashboard,
        name="api_status_dashboard",
    ),
    path("integrations/logs/", views.sync_logs_list, name="sync_logs_list"),
    path(
        "integrations/logs/<int:log_id>/retry/",
        views.retry_failed_sync,
        name="retry_failed_sync",
    ),
]
