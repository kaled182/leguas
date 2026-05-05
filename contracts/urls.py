from django.urls import path
from . import views

app_name = "contracts"

urlpatterns = [
    # ─── Driver Portal ───
    path("portal/<int:driver_id>/", views.driver_contracts, name="driver_contracts"),
    path(
        "portal/<int:driver_id>/sign/<int:template_id>/",
        views.driver_contract_sign, name="driver_contract_sign",
    ),
    path(
        "portal/<int:driver_id>/view/<int:contract_id>/",
        views.driver_contract_view, name="driver_contract_view",
    ),

    # ─── Admin ───
    path("admin/templates/", views.admin_templates_list, name="admin_templates_list"),
    path("admin/templates/create/", views.admin_template_create, name="admin_template_create"),
    path("admin/templates/<int:pk>/edit/", views.admin_template_edit, name="admin_template_edit"),
    path("admin/signed/", views.admin_signed_contracts, name="admin_signed_contracts"),
    path("admin/missing/", views.admin_missing_contracts, name="admin_missing_contracts"),
    path("admin/contract/<int:pk>/revoke/", views.admin_revoke_contract, name="admin_revoke_contract"),
]
