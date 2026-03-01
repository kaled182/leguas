# URLs do app core
from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    # Partners
    path("partners/", views.partner_list, name="partner-list"),
    path("partners/create/", views.partner_create, name="partner-create"),
    path("partners/<int:pk>/", views.partner_detail, name="partner-detail"),
    path("partners/<int:pk>/edit/", views.partner_edit, name="partner-edit"),
    path(
        "partners/<int:pk>/toggle-status/",
        views.partner_toggle_status,
        name="partner-toggle-status",
    ),
    # Integrations
    path(
        "partners/<int:partner_pk>/integrations/create/",
        views.integration_create,
        name="integration-create",
    ),
    path(
        "integrations/<int:pk>/edit/",
        views.integration_edit,
        name="integration-edit",
    ),
    path(
        "integrations/<int:pk>/toggle-status/",
        views.integration_toggle_status,
        name="integration-toggle-status",
    ),
    path(
        "integrations/dashboard/",
        views.integrations_dashboard,
        name="integrations-dashboard",
    ),
]
