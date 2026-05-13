from django.contrib import admin

from .models import (
    Employee, Payroll, PayrollComponent, IRSTable, IRSEscalao,
)


class IRSEscalaoInline(admin.TabularInline):
    model = IRSEscalao
    extra = 1
    fields = ("limite_superior", "taxa", "parcela_abater")


@admin.register(IRSTable)
class IRSTableAdmin(admin.ModelAdmin):
    list_display = ("ano", "tabela_id", "nome", "is_active")
    list_filter = ("ano", "is_active")
    search_fields = ("nome",)
    inlines = [IRSEscalaoInline]


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "nome", "contrato_tipo", "vencimento_base",
        "subsidios_mode", "ativo",
    )
    list_filter = ("contrato_tipo", "subsidios_mode", "ativo")
    search_fields = ("nome", "nif", "niss", "email")


class PayrollComponentInline(admin.TabularInline):
    model = PayrollComponent
    extra = 0
    fields = ("tipo", "descricao", "valor", "quantidade")
    readonly_fields = ()


@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
    list_display = (
        "employee", "periodo_ano", "periodo_mes", "status",
        "total_bruto", "total_descontos", "total_liquido",
    )
    list_filter = ("status", "periodo_ano", "periodo_mes")
    search_fields = ("employee__nome",)
    inlines = [PayrollComponentInline]
    readonly_fields = (
        "total_bruto", "total_descontos", "total_liquido", "tsu_empregador",
    )
