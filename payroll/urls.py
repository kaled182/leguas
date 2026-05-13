from django.urls import path

from . import views

app_name = "payroll"

urlpatterns = [
    # Funcionários
    path("funcionarios/", views.employee_list, name="employee_list"),
    path("funcionarios/novo/", views.employee_create, name="employee_create"),
    path("funcionarios/<int:pk>/", views.employee_edit, name="employee_edit"),
    path("funcionarios/<int:pk>/delete/", views.employee_delete, name="employee_delete"),

    # Folhas
    path("folhas/", views.payroll_list, name="payroll_list"),
    path("folhas/gerar/", views.payroll_generate, name="payroll_generate"),
    path("folhas/<int:pk>/", views.payroll_detail, name="payroll_detail"),
    path("folhas/<int:pk>/recalc/", views.payroll_recalc, name="payroll_recalc"),
    path("folhas/<int:pk>/aprovar/", views.payroll_approve, name="payroll_approve"),
    path("folhas/<int:pk>/pagar/", views.payroll_pay, name="payroll_pay"),
    path("folhas/<int:pk>/cancelar/", views.payroll_cancel, name="payroll_cancel"),
    path("folhas/<int:pk>/component/add/", views.payroll_component_add, name="component_add"),
    path(
        "folhas/<int:pk>/component/<int:cid>/delete/",
        views.payroll_component_delete, name="component_delete",
    ),
    path("folhas/<int:pk>/recibo.pdf", views.payroll_recibo_pdf, name="payroll_pdf"),
]
