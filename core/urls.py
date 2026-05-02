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
    path("partners/<int:pk>/delete/", views.partner_delete, name="partner-delete"),
    path(
        "partners/<int:pk>/financial/",
        views.partner_financial_dashboard,
        name="partner-financial",
    ),
    path(
        "partners/<int:pk>/financial/generate-preview/",
        views.partner_financial_preview,
        name="partner-financial-preview",
    ),
    path(
        "partners/<int:pk>/financial/generate/",
        views.partner_financial_generate,
        name="partner-financial-generate",
    ),
    # Fase 5 — Override de preço numa pré-fatura
    path(
        "pre-invoices/<int:pre_invoice_id>/price-override/",
        views.pre_invoice_price_override_create,
        name="pre-invoice-price-override",
    ),
    # Vincular courier_name ↔ DriverProfile
    path(
        "partners/<int:pk>/link-courier/",
        views.partner_link_courier,
        name="partner-link-courier",
    ),
    path(
        "partners/<int:pk>/drivers-search/",
        views.partner_drivers_search,
        name="partner-drivers-search",
    ),
    # Fase 6 — Auto-detecção de perdas
    path(
        "cainiao/detect-lost-packages/",
        views.cainiao_detect_lost_packages,
        name="cainiao-detect-lost-packages",
    ),
    # Fase 7 — Regras de bónus/penalty
    path(
        "partners/<int:pk>/bonus-rules/",
        views.partner_bonus_rules,
        name="partner-bonus-rules",
    ),
    path(
        "partners/<int:pk>/bonus-rules/save/",
        views.partner_bonus_rule_save,
        name="partner-bonus-rule-save",
    ),
    path(
        "partners/<int:pk>/bonus-rules/<int:rule_id>/delete/",
        views.partner_bonus_rule_delete,
        name="partner-bonus-rule-delete",
    ),
    # Fase 8 — Extras
    path(
        "drivers/<int:driver_id>/account/",
        views.driver_account_statement,
        name="driver-account",
    ),
    # Logins do motorista (DriverCourierMapping CRUD)
    path(
        "drivers/<int:driver_id>/couriers/",
        views.driver_courier_logins_list,
        name="driver-couriers-list",
    ),
    path(
        "drivers/<int:driver_id>/couriers/save/",
        views.driver_courier_login_save,
        name="driver-courier-save",
    ),
    path(
        "drivers/<int:driver_id>/couriers/<int:mapping_id>/delete/",
        views.driver_courier_login_delete,
        name="driver-courier-delete",
    ),
    path(
        "pre-invoice/sign/<str:token>/",
        views.pre_invoice_remote_sign,
        name="pre-invoice-remote-sign",
    ),
    path(
        "pre-invoices/<int:pre_invoice_id>/send-whatsapp/",
        views.pre_invoice_send_whatsapp,
        name="pre-invoice-send-whatsapp",
    ),
    path(
        "partners/<int:partner_id>/saft-export/",
        views.pre_invoice_saft_export,
        name="partner-saft-export",
    ),
    path(
        "financial-alerts/",
        views.financial_alerts_list,
        name="financial-alerts",
    ),
    path(
        "financial-alerts/<int:alert_id>/resolve/",
        views.financial_alert_resolve,
        name="financial-alert-resolve",
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
        "integrations/<int:integration_id>/sync/",
        views.partner_sync_manual,
        name="partner-sync-manual",
    ),
    path(
        "integrations/dashboard/",
        views.integrations_dashboard,
        name="integrations-dashboard",
    ),
    # Dashboards específicos
    path(
        "delnext/dashboard/",
        views.delnext_dashboard,
        name="delnext-dashboard",
    ),
]
