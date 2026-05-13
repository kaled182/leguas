from django.urls import path

from . import views

app_name = "drivers_app"

urlpatterns = [
    # Pagina publica de cadastro
    path("cadastro/", views.public_driver_register, name="public_register"),
    path(
        "cadastro-completo/",
        views.public_driver_register_full,
        name="public_register_full",
    ),
    # Dashboard de motoristas
    path("dashboard/", views.driver_dashboard_view, name="driver_dashboard"),
    path("export/xlsx/", views.driver_export_xlsx, name="driver_export_xlsx"),
    path("logout/", views.driver_logout_view, name="driver_logout"),

    # ─── Portal do Driver (Fase 1: KPIs + relatórios + faturas) ───
    path("portal/<int:driver_id>/", views.driver_portal, name="driver_portal"),
    path(
        "portal/<int:driver_id>/relatorios/",
        views.driver_portal_reports,
        name="driver_portal_reports",
    ),
    path(
        "portal/<int:driver_id>/faturas/",
        views.driver_portal_invoices,
        name="driver_portal_invoices",
    ),
    path(
        "portal/<int:driver_id>/perfil/",
        views.driver_portal_profile,
        name="driver_portal_profile",
    ),
    path(
        "portal/<int:driver_id>/indicacoes/",
        views.driver_portal_referrals,
        name="driver_portal_referrals",
    ),
    # ─── Portal Admin (substitui modais antigos) ───
    path("portal/<int:driver_id>/editar/", views.driver_admin_edit, name="driver_admin_edit"),
    path(
        "portal/<int:driver_id>/unify/search/",
        views.driver_unify_search, name="driver_unify_search",
    ),
    path(
        "portal/<int:driver_id>/unify/preview/<int:target_id>/",
        views.driver_unify_preview, name="driver_unify_preview",
    ),
    path(
        "portal/<int:driver_id>/unify/execute/",
        views.driver_unify_execute, name="driver_unify_execute",
    ),
    path("portal/<int:driver_id>/documentos/", views.driver_documents, name="driver_documents"),
    path("portal/<int:driver_id>/veiculos/", views.driver_vehicles, name="driver_vehicles"),
    path("portal/<int:driver_id>/helpers/", views.driver_helpers, name="driver_helpers"),
    path("portal/<int:driver_id>/reclamacoes/", views.driver_complaints, name="driver_complaints"),
    path(
        "portal/<int:driver_id>/descontos/",
        views.driver_claims, name="driver_claims",
    ),
    path(
        "portal/<int:driver_id>/descontos/<int:claim_id>/recorrer/",
        views.driver_claim_appeal, name="driver_claim_appeal",
    ),
    path(
        "portal/<int:driver_id>/reclamacoes/<int:complaint_id>/aplicar-desconto/",
        views.driver_complaint_apply_claim,
        name="driver_complaint_apply_claim",
    ),
    path("portal/<int:driver_id>/logins/", views.driver_logins, name="driver_logins"),
    path("portal/<int:driver_id>/financeiro/", views.driver_financeiro, name="driver_financeiro"),
    path(
        "portal/<int:driver_id>/pf/<int:pre_invoice_id>/",
        views.driver_pre_invoice_detail,
        name="driver_pre_invoice_detail",
    ),
    path(
        "portal/<int:driver_id>/pf/<int:pre_invoice_id>/upload-recibo/",
        views.driver_pre_invoice_upload_recibo,
        name="driver_pre_invoice_upload_recibo",
    ),
    path(
        "portal/<int:driver_id>/pf/<int:pre_invoice_id>/pdf/",
        views.driver_pre_invoice_pdf,
        name="driver_pre_invoice_pdf",
    ),
    path(
        "portal/<int:driver_id>/caderneta/<int:year>/pdf/",
        views.driver_caderneta_pdf,
        name="driver_caderneta_pdf",
    ),

    # ─── Admin: aprovar pedidos de alteração ───
    path(
        "admin/pedidos-alteracao/",
        views.change_requests_list,
        name="change_requests_list",
    ),
    path(
        "admin/pedidos-alteracao/<int:pk>/acao/",
        views.change_request_action,
        name="change_request_action",
    ),
    # ─── Central de Motoristas (admin moderna) ───
    path("admin/", views.drivers_central, name="drivers_central"),
    path("admin/central/", views.drivers_central, name="drivers_central_alias"),

    # Admin - Gestao de Motoristas
    path("admin/criar/", views.admin_create_driver, name="admin_create_driver"),
    path(
        "admin/aprovar/",
        views.admin_approve_drivers,
        name="admin_approve_drivers",
    ),
    path(
        "admin/aprovar/<int:driver_id>/",
        views.admin_approve_driver_action,
        name="admin_approve_driver_action",
    ),
    path(
        "admin/ativos/",
        views.admin_active_drivers,
        name="admin_active_drivers",
    ),
    # Bulk actions na página Motoristas Ativos
    path(
        "admin/bulk/block/",
        views.bulk_block_drivers,
        name="bulk_block_drivers",
    ),
    path(
        "admin/bulk/unblock/",
        views.bulk_unblock_drivers,
        name="bulk_unblock_drivers",
    ),
    path(
        "admin/bulk/whatsapp/",
        views.bulk_whatsapp_drivers,
        name="bulk_whatsapp_drivers",
    ),
    path(
        "admin/bulk/export-csv/",
        views.bulk_export_drivers_csv,
        name="bulk_export_drivers_csv",
    ),
    # Drawer / quick-view API
    path(
        "admin/quickview/<int:driver_id>/",
        views.driver_quickview,
        name="driver_quickview",
    ),
    # Admin - Gestão Completa (Edição, Documentos, Veículos)
    path(
        "admin/editar/<int:driver_id>/pessoal/",
        views.admin_edit_driver_personal,
        name="admin_edit_driver_personal",
    ),
    path(
        "admin/editar/<int:driver_id>/profissional/",
        views.admin_edit_driver_professional,
        name="admin_edit_driver_professional",
    ),
    path(
        "admin/anexar-documento/<int:driver_id>/",
        views.admin_attach_document,
        name="admin_attach_document",
    ),
    path(
        "admin/deletar-documento/<int:document_id>/",
        views.admin_delete_document,
        name="admin_delete_document",
    ),
    path(
        "admin/adicionar-veiculo/<int:driver_id>/",
        views.admin_add_vehicle,
        name="admin_add_vehicle",
    ),
    path(
        "admin/deletar-veiculo/<int:vehicle_id>/",
        views.admin_delete_vehicle,
        name="admin_delete_vehicle",
    ),
    path(
        "admin/deletar-documento-veiculo/<int:document_id>/",
        views.admin_delete_vehicle_document,
        name="admin_delete_vehicle_document",
    ),
    path(
        "admin/desativar/<int:driver_id>/",
        views.admin_deactivate_driver,
        name="admin_deactivate_driver",
    ),
    path(
        "admin/ativar/<int:driver_id>/",
        views.admin_activate_driver,
        name="admin_activate_driver",
    ),
    path(
        "admin/excluir/<int:driver_id>/",
        views.admin_delete_driver,
        name="admin_delete_driver",
    ),
    path(
        "admin/get-driver-data/<int:driver_id>/",
        views.admin_get_driver_data,
        name="admin_get_driver_data",
    ),
    # API endpoints
    path(
        "api/register-typebot/",
        views.register_driver_typebot,
        name="register_driver_typebot",
    ),
    # Indicações / Referrals
    path("api/referrals/search/", views.referral_search_drivers, name="referral-search"),
    path("api/referrals/<int:driver_id>/", views.referral_list, name="referral-list"),
    path("api/referrals/<int:driver_id>/add/", views.referral_add, name="referral-add"),
    path("api/referrals/item/<int:referral_id>/update/", views.referral_update, name="referral-update"),
    path("api/referrals/item/<int:referral_id>/delete/", views.referral_delete, name="referral-delete"),
    # Empresas Parceiras
    path("empresas-parceiras/", views.empresas_parceiras_list, name="empresas-parceiras"),
    path("api/empresas-parceiras/create/", views.empresa_parceira_create, name="empresa-parceira-create"),
    path("api/empresas-parceiras/<int:empresa_id>/update/", views.empresa_parceira_update, name="empresa-parceira-update"),
    path("api/empresas-parceiras/<int:empresa_id>/delete/", views.empresa_parceira_delete, name="empresa-parceira-delete"),
    path("api/empresas-parceiras/<int:empresa_id>/motoristas/", views.empresa_parceira_motoristas, name="empresa-parceira-motoristas"),
    path("api/empresas-parceiras/<int:empresa_id>/motoristas/search/", views.empresa_parceira_search_drivers, name="empresa-parceira-search-drivers"),
    path("api/empresas-parceiras/<int:empresa_id>/motoristas/<int:driver_id>/assign/", views.empresa_parceira_assign_driver, name="empresa-parceira-assign-driver"),
    path("api/empresas-parceiras/<int:empresa_id>/motoristas/<int:driver_id>/remove/", views.empresa_parceira_remove_driver, name="empresa-parceira-remove-driver"),
    path("api/empresas-parceiras/<int:empresa_id>/prefaturas/", views.empresa_parceira_prefaturas, name="empresa-parceira-prefaturas"),
    # Auto-emit config (Fase 6.7)
    path("api/empresas-parceiras/<int:empresa_id>/auto-emit/", views.empresa_auto_emit_config, name="empresa-auto-emit-config"),
    path("api/empresas-parceiras/<int:empresa_id>/auto-emit/run-now/", views.empresa_auto_emit_run_now, name="empresa-auto-emit-run-now"),
    # Lançamentos manuais
    path("api/empresas-parceiras/<int:empresa_id>/lancamentos/create/", views.empresa_lancamento_create, name="empresa-lancamento-create"),
    path("api/empresas-parceiras/lancamentos/<int:lancamento_id>/update/", views.empresa_lancamento_update, name="empresa-lancamento-update"),
    path("api/empresas-parceiras/lancamentos/<int:lancamento_id>/delete/", views.empresa_lancamento_delete, name="empresa-lancamento-delete"),
    # PDF Pré-fatura Empresa Parceira
    path(
        "empresas-parceiras/<int:empresa_id>/prefatura/pdf/",
        views.empresa_parceira_prefatura_pdf,
        name="empresa-parceira-prefatura-pdf",
    ),
    # Painel Global de Reclamações
    path(
        "admin/reclamacoes/",
        views.admin_complaints_dashboard,
        name="admin_complaints_dashboard",
    ),
    path(
        "api/admin/reclamacoes/list/",
        views.admin_complaints_list_api,
        name="admin_complaints_list_api",
    ),
    path(
        "api/admin/reclamacoes/driver-search/",
        views.admin_complaints_driver_search,
        name="admin_complaints_driver_search",
    ),
    # Reclamações de Clientes
    path(
        "api/complaints/<int:driver_id>/",
        views.driver_complaints_api,
        name="driver-complaints-api",
    ),
    path(
        "api/complaints/<int:driver_id>/create/",
        views.driver_complaint_create,
        name="driver-complaint-create",
    ),
    path(
        "api/waybill-lookup/",
        views.waybill_lookup_for_complaint,
        name="waybill-lookup-for-complaint",
    ),
    path(
        "api/complaints/ocr-extract/",
        views.complaint_ocr_extract,
        name="complaint-ocr-extract",
    ),
    path(
        "api/complaints/item/<int:complaint_id>/update/",
        views.driver_complaint_update,
        name="driver-complaint-update",
    ),
    path(
        "api/complaints/item/<int:complaint_id>/delete/",
        views.driver_complaint_delete,
        name="driver-complaint-delete",
    ),
    path(
        "api/complaints/item/<int:complaint_id>/attachment/add/",
        views.driver_complaint_add_attachment,
        name="driver-complaint-attachment-add",
    ),
    path(
        "api/complaints/attachment/<int:attachment_id>/delete/",
        views.driver_complaint_delete_attachment,
        name="driver-complaint-attachment-delete",
    ),
    path(
        "complaints/<int:complaint_id>/pdf/",
        views.driver_complaint_pdf,
        name="driver-complaint-pdf",
    ),
]
