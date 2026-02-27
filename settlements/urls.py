from django.urls import path
from . import views
from . import plan_api

urlpatterns = [
    # relatórios/fechos (legacy)
    path("summary", views.summary, name="settlements-summary"),
    path("drivers-rank", views.drivers_rank, name="settlements-drivers-rank"),
    path("runs", views.runs_list, name="settlements-runs"),
    path("payouts", views.payouts, name="settlements-payouts"),
    path("payouts.csv", views.payouts_csv, name="settlements-payouts-csv"),

    # planos
    path("plans", plan_api.plans_list, name="plans-list"),
    path("plans/conflicts", plan_api.plans_conflicts, name="plans-conflicts"),
    path("plans/create", plan_api.plan_create, name="plans-create"),
    path("plans/<int:plan_id>", plan_api.plan_detail, name="plans-detail"),
    path("plans/<int:plan_id>/update", plan_api.plan_update, name="plans-update"),
    path("plans/<int:plan_id>/clone", plan_api.plan_clone, name="plans-clone"),
    path("plans/<int:plan_id>/delete", plan_api.plan_delete, name="plans-delete"),
    path("plans/preview", plan_api.plan_preview, name="plans-preview"),
    
    # Financial System (Fase 6)
    path("financial/", views.financial_dashboard, name="financial-dashboard"),
    
    # Invoices
    path("invoices/", views.invoice_list, name="invoice-list"),
    path("invoices/<int:invoice_id>/", views.invoice_detail, name="invoice-detail"),
    path("invoices/<int:invoice_id>/pdf/", views.invoice_download_pdf, name="invoice-pdf"),
    
    # Settlements
    path("settlements/", views.settlement_list, name="settlement-list"),
    path("settlements/<int:settlement_id>/", views.settlement_detail, name="settlement-detail"),
    path("settlements/<int:settlement_id>/pdf/", views.settlement_download_pdf, name="settlement-pdf"),
    
    # Claims
    path("claims/", views.claim_list, name="claim-list"),
    path("claims/<int:claim_id>/", views.claim_detail, name="claim-detail"),
]
