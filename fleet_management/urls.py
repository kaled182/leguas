from django.urls import path

from . import views

app_name = "fleet"

urlpatterns = [
    # Dashboard
    path("dashboard/", views.fleet_dashboard, name="dashboard"),
    # Vehicles
    path("vehicles/", views.vehicle_list, name="vehicle_list"),
    path("vehicles/create/", views.vehicle_create, name="vehicle_create"),
    path("vehicles/<int:pk>/", views.vehicle_detail, name="vehicle_detail"),
    path("vehicles/<int:pk>/edit/", views.vehicle_edit, name="vehicle_edit"),
    path(
        "vehicles/<int:pk>/toggle-status/",
        views.vehicle_toggle_status,
        name="vehicle_toggle_status",
    ),
    # Maintenance
    path("maintenance/", views.maintenance_list, name="maintenance_list"),
    path(
        "maintenance/calendar/",
        views.maintenance_calendar,
        name="maintenance_calendar",
    ),
    path(
        "maintenance/create/",
        views.maintenance_create,
        name="maintenance_create",
    ),
    path(
        "maintenance/<int:pk>/",
        views.maintenance_detail,
        name="maintenance_detail",
    ),
    path(
        "maintenance/<int:pk>/edit/",
        views.maintenance_edit,
        name="maintenance_edit",
    ),
    # Incidents
    path("incidents/", views.incident_list, name="incident_list"),
]
