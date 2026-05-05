from django.urls import path

from . import views, views_payables

app_name = "accounting"

urlpatterns = [
    # Dashboard
    path("", views.dashboard, name="dashboard"),

    # ── Inbox unificado de Pagamentos a Fazer ──
    path("a-pagar/", views_payables.payables_inbox, name="payables_inbox"),
    path(
        "a-pagar/marcar-pago/", views_payables.payables_mark_paid,
        name="payables_mark_paid",
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
]
