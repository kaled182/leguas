from django.urls import path

from . import (
    views, views_payables, views_suppliers, views_taxes,
    views_treasury, views_ocr, views_cost_centers, views_categories,
    views_hub, views_reconciliation, views_dre_export, views_audit,
    views_exec, views_period_lock,
)

app_name = "accounting"

urlpatterns = [
    # Dashboard
    path("", views.dashboard, name="dashboard"),

    # Hub financeiro unificado (AR + AP + Tesouraria + DRE + Motoristas)
    path("hub/", views_hub.hub_financeiro, name="hub_financeiro"),

    # Auditoria centralizada — timeline cross-modelo
    path("auditoria/", views_audit.audit_timeline, name="audit_timeline"),

    # Dashboard executivo mensal (imprimível em A4)
    path("exec/", views_exec.executive_dashboard, name="executive_dashboard"),

    # Fechos de período contabilístico (lock/unlock)
    path(
        "periodos/",
        views_period_lock.period_lock_list, name="period_lock_list",
    ),
    path(
        "periodos/toggle/",
        views_period_lock.period_lock_toggle, name="period_lock_toggle",
    ),

    # Reconciliação bancária (match BankTransaction ↔ Bills/PartnerInvoice/PF)
    path(
        "reconciliacao-bancaria/",
        views_reconciliation.bank_reconciliation,
        name="bank_reconciliation",
    ),
    path(
        "reconciliacao-bancaria/<int:tx_id>/confirm/",
        views_reconciliation.bank_match_confirm,
        name="bank_match_confirm",
    ),
    path(
        "reconciliacao-bancaria/<int:tx_id>/clear/",
        views_reconciliation.bank_match_clear,
        name="bank_match_clear",
    ),

    # ── Inbox unificado de Pagamentos a Fazer ──
    path("a-pagar/", views_payables.payables_inbox, name="payables_inbox"),
    path(
        "pendentes-regularizacao/",
        views_payables.pending_reconciliation,
        name="pending_reconciliation",
    ),
    path(
        "a-pagar/marcar-pago/", views_payables.payables_mark_paid,
        name="payables_mark_paid",
    ),
    path(
        "a-pagar/sem-pf/",
        views_payables.payables_drivers_without_pf,
        name="payables_no_pf",
    ),
    path(
        "a-pagar/sem-ff/",
        views_payables.payables_fleets_without_invoice,
        name="payables_no_ff",
    ),
    path(
        "a-pagar/pf/<int:pf_id>/health/",
        views_payables.payables_pf_health,
        name="payables_pf_health",
    ),
    path(
        "a-pagar/pf/<int:pf_id>/compare/",
        views_payables.payables_pf_compare,
        name="payables_pf_compare",
    ),
    path(
        "a-pagar/pf/<int:pf_id>/notes/",
        views_payables.payables_pf_notes,
        name="payables_pf_notes",
    ),
    path(
        "a-pagar/calendario/",
        views_payables.payables_calendar,
        name="payables_calendar",
    ),
    path(
        "a-pagar/forecast/",
        views_payables.payables_forecast,
        name="payables_forecast",
    ),
    # URLs para Receitas
    path("receitas/", views.revenue_list, name="revenue_list"),
    path("receitas/nova/", views.revenue_create, name="revenue_create"),
    path("receitas/<int:pk>/", views.revenue_detail, name="revenue_detail"),
    path("receitas/<int:pk>/editar/", views.revenue_edit, name="revenue_edit"),
    path(
        "receitas/<int:pk>/deletar/",
        views.revenue_delete,
        name="revenue_delete",
    ),
    # URLs para Despesas
    path("despesas/", views.expense_list, name="expense_list"),
    path("despesas/nova/", views.expense_create, name="expense_create"),
    path("despesas/<int:pk>/", views.expense_detail, name="expense_detail"),
    path("despesas/<int:pk>/editar/", views.expense_edit, name="expense_edit"),
    path(
        "despesas/<int:pk>/deletar/",
        views.expense_delete,
        name="expense_delete",
    ),
    path(
        "despesas/<int:pk>/toggle-pagamento/",
        views.expense_toggle_payment,
        name="expense_toggle_payment",
    ),
    # Relatórios
    path("relatorios/", views.reports, name="reports"),

    # ── Fase 1: Contas a Pagar (Bills) + DRE ──
    path("contas-a-pagar/", views.bill_list, name="bill_list"),
    path("contas-a-pagar/nova/", views.bill_create, name="bill_create"),
    path(
        "contas-a-pagar/lixeira/",
        views.bill_trash, name="bill_trash",
    ),
    path(
        "contas-a-pagar/<int:pk>/restaurar/",
        views.bill_restore, name="bill_restore",
    ),
    path(
        "contas-a-pagar/<int:pk>/eliminar-definitivo/",
        views.bill_hard_delete, name="bill_hard_delete",
    ),
    path(
        "contas-a-pagar/<int:pk>/",
        views.bill_detail, name="bill_detail",
    ),
    path(
        "contas-a-pagar/<int:pk>/editar/",
        views.bill_edit, name="bill_edit",
    ),
    path(
        "contas-a-pagar/<int:pk>/apagar/",
        views.bill_delete, name="bill_delete",
    ),
    path(
        "contas-a-pagar/<int:pk>/marcar-paga/",
        views.bill_mark_paid, name="bill_mark_paid",
    ),
    path(
        "contas-a-pagar/anexo/<int:pk>/apagar/",
        views.bill_attachment_delete,
        name="bill_attachment_delete",
    ),
    path(
        "contas-a-pagar/<int:pk>/gerar-proxima/",
        views.bill_generate_next,
        name="bill_generate_next",
    ),
    path(
        "contas-a-pagar/<int:pk>/aprovar/",
        views.bill_approve, name="bill_approve",
    ),
    path(
        "contas-a-pagar/<int:pk>/rejeitar/",
        views.bill_reject, name="bill_reject",
    ),
    path("dre/", views.dre, name="dre"),
    path("dre/export/", views_dre_export.dre_export, name="dre_export"),
    path("fluxo-caixa/", views.cash_flow_projection, name="cash_flow"),
    path(
        "break-even/", views.break_even_monitor,
        name="break_even",
    ),
    path(
        "break-even/data/", views.break_even_data,
        name="break_even_data",
    ),

    # Conciliação bancária
    path(
        "extractos/", views.bank_statement_list,
        name="bank_statement_list",
    ),
    path(
        "extractos/upload/", views.bank_statement_upload,
        name="bank_statement_upload",
    ),
    path(
        "extractos/<int:pk>/", views.bank_statement_detail,
        name="bank_statement_detail",
    ),
    path(
        "extractos/transacao/<int:pk>/conciliar/",
        views.bank_transaction_match,
        name="bank_transaction_match",
    ),
    path(
        "extractos/transacao/<int:pk>/desconciliar/",
        views.bank_transaction_unmatch,
        name="bank_transaction_unmatch",
    ),

    # ── Fornecedores (cadastro) ───────────────────────────────────────
    path(
        "fornecedores/",
        views_suppliers.fornecedor_list, name="fornecedor_list",
    ),
    path(
        "fornecedores/novo/",
        views_suppliers.fornecedor_create, name="fornecedor_create",
    ),
    path(
        "fornecedores/<int:pk>/editar/",
        views_suppliers.fornecedor_edit, name="fornecedor_edit",
    ),
    path(
        "fornecedores/<int:pk>/toggle-ativo/",
        views_suppliers.fornecedor_toggle_active,
        name="fornecedor_toggle_active",
    ),
    path(
        "fornecedores/tags/",
        views_suppliers.fornecedor_tag_list,
        name="fornecedor_tag_list",
    ),
    path(
        "fornecedores/tags/<int:pk>/apagar/",
        views_suppliers.fornecedor_tag_delete,
        name="fornecedor_tag_delete",
    ),
    path(
        "fornecedores/api/search/",
        views_suppliers.fornecedor_search_api,
        name="fornecedor_search_api",
    ),
    path(
        "fornecedores/api/quick-create/",
        views_suppliers.fornecedor_quick_create_api,
        name="fornecedor_quick_create_api",
    ),
    path(
        "fornecedores/api/<int:pk>/",
        views_suppliers.fornecedor_detail_api,
        name="fornecedor_detail_api",
    ),

    # ── Impostos ──────────────────────────────────────────────────────
    path("impostos/", views_taxes.imposto_list, name="imposto_list"),
    path(
        "impostos/novo/",
        views_taxes.imposto_create, name="imposto_create",
    ),
    path(
        "impostos/ocr-extract/",
        views_taxes.imposto_ocr_extract, name="imposto_ocr_extract",
    ),
    path(
        "impostos/<int:pk>/editar/",
        views_taxes.imposto_edit, name="imposto_edit",
    ),
    path(
        "impostos/<int:pk>/marcar-pago/",
        views_taxes.imposto_mark_paid, name="imposto_mark_paid",
    ),
    path(
        "impostos/<int:pk>/anular/",
        views_taxes.imposto_anular, name="imposto_anular",
    ),

    # Planos prestacionais (subconjunto: pais PARCELADO)
    path(
        "impostos/planos/",
        views_taxes.plano_list, name="plano_list",
    ),
    path(
        "impostos/planos/<int:pk>/",
        views_taxes.plano_detail, name="plano_detail",
    ),

    # ── Tesouraria ────────────────────────────────────────────────────
    path(
        "tesouraria/",
        views_treasury.treasury_dashboard, name="treasury_dashboard",
    ),

    # ── OCR de faturas ────────────────────────────────────────────────
    path(
        "ocr/extract/",
        views_ocr.ocr_extract_api, name="ocr_extract",
    ),

    # ── Centros de Custo ──────────────────────────────────────────────
    path(
        "centros-custo/",
        views_cost_centers.cost_center_list, name="cost_center_list",
    ),
    path(
        "centros-custo/novo/",
        views_cost_centers.cost_center_create, name="cost_center_create",
    ),
    path(
        "centros-custo/<int:pk>/editar/",
        views_cost_centers.cost_center_edit, name="cost_center_edit",
    ),
    path(
        "centros-custo/<int:pk>/toggle-ativo/",
        views_cost_centers.cost_center_toggle_active,
        name="cost_center_toggle_active",
    ),
    path(
        "centros-custo/sync-hubs/",
        views_cost_centers.cost_center_sync_hubs,
        name="cost_center_sync_hubs",
    ),

    # ── Categorias de Despesa ─────────────────────────────────────────
    path(
        "categorias/",
        views_categories.category_list, name="category_list",
    ),
    path(
        "categorias/nova/",
        views_categories.category_create, name="category_create",
    ),
    path(
        "categorias/<int:pk>/editar/",
        views_categories.category_edit, name="category_edit",
    ),
]
