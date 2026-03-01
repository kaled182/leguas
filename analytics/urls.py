"""
URLs da aplicação analytics.
"""

from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    # Dashboard principal
    path("", views.dashboard_overview, name="dashboard"),
    # Dashboards específicos
    path("metrics/", views.metrics_dashboard, name="metrics_dashboard"),
    path("forecasts/", views.forecasts_dashboard, name="forecasts_dashboard"),
    path("alerts/", views.alerts_dashboard, name="alerts_dashboard"),
    path(
        "drivers/",
        views.drivers_performance_dashboard,
        name="drivers_dashboard",
    ),
    path("incidents/", views.incidents_report, name="incidents_report"),
    path("vehicles/", views.vehicles_performance_report, name="vehicles_report"),
    # API endpoints para dados JSON (para gráficos dinâmicos)
    path("api/metrics-data/", views.api_metrics_data, name="api_metrics_data"),
    path(
        "api/forecasts-data/",
        views.api_forecasts_data,
        name="api_forecasts_data",
    ),
    path("api/alerts-data/", views.api_alerts_data, name="api_alerts_data"),
    path("api/drivers-data/", views.api_drivers_data, name="api_drivers_data"),
    # Exportações
    path(
        "export/metrics/",
        views.export_metrics_excel,
        name="export_metrics_excel",
    ),
    path(
        "export/drivers/",
        views.export_drivers_excel,
        name="export_drivers_excel",
    ),
    path("export/report-pdf/", views.export_report_pdf, name="export_report_pdf"),
    # Automações
    path(
        "automations/",
        views.automations_dashboard,
        name="automations_dashboard",
    ),
    path(
        "automations/run-assignment/",
        views.run_auto_assignment,
        name="run_auto_assignment",
    ),
    path(
        "automations/route-optimizer/",
        views.route_optimizer,
        name="route_optimizer",
    ),
    path(
        "automations/shift-suggestions/",
        views.shift_suggestions,
        name="shift_suggestions",
    ),
    # Relatórios Avançados
    path(
        "reports/vehicle-utilization/",
        views.vehicle_utilization_report,
        name="vehicle_utilization_report",
    ),
    path(
        "reports/fleet-costs/",
        views.fleet_cost_report,
        name="fleet_cost_report",
    ),
    path(
        "reports/shift-performance/",
        views.shift_performance_report,
        name="shift_performance_report",
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
