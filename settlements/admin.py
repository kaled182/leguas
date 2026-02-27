from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    SettlementRun, CompensationPlan, PerPackageRate, ThresholdBonus,
    PartnerInvoice, DriverSettlement, DriverClaim
)


# ============================================================================
# LEGACY MODELS (manter para backwards compatibility)
# ============================================================================

@admin.register(SettlementRun)
class SettlementRunAdmin(admin.ModelAdmin):
    list_display  = ("run_date","client","driver","area_code","qtd_entregue","vl_pct","total_pct","vl_final")
    list_filter   = ("client","area_code","run_date","driver")
    search_fields = ("driver__name","client","area_code")
    date_hierarchy = "run_date"
    autocomplete_fields = ("driver",)

class PerPackageRateInline(admin.TabularInline):
    model = PerPackageRate
    extra = 0

class ThresholdBonusInline(admin.TabularInline):
    model = ThresholdBonus
    extra = 0

@admin.register(CompensationPlan)
class CompensationPlanAdmin(admin.ModelAdmin):
    list_display = ("driver","client","area_code","starts_on","ends_on","base_fixed","is_active")
    list_filter  = ("client","area_code","is_active")
    search_fields = ("driver__name","client","area_code")
    date_hierarchy = "starts_on"
    autocomplete_fields = ("driver",)
    inlines = [PerPackageRateInline, ThresholdBonusInline]


# ============================================================================
# 🆕 MULTI-PARTNER FINANCIAL ADMIN (Fase 6)
# ============================================================================

@admin.register(PartnerInvoice)
class PartnerInvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'invoice_number',
        'partner_badge',
        'period_display',
        'net_amount_display',
        'status_badge',
        'due_date',
        'paid_date'
    )
    
    list_filter = (
        'status',
        'partner',
        'issue_date',
        'due_date',
        ('paid_date', admin.EmptyFieldListFilter)
    )
    
    search_fields = (
        'invoice_number',
        'external_reference',
        'partner__name'
    )
    
    date_hierarchy = 'period_end'
    
    readonly_fields = (
        'invoice_number',
        'created_at',
        'updated_at',
        'created_by'
    )
    
    fieldsets = (
        ('Identificação', {
            'fields': ('partner', 'invoice_number', 'external_reference')
        }),
        ('Período', {
            'fields': ('period_start', 'period_end')
        }),
        ('Valores', {
            'fields': (
                ('gross_amount', 'tax_amount', 'net_amount'),
                ('total_orders', 'total_delivered')
            )
        }),
        ('Status e Pagamento', {
            'fields': (
                'status',
                ('issue_date', 'due_date'),
                ('paid_date', 'paid_amount')
            )
        }),
        ('Notas', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Auditoria', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_paid', 'check_overdue', 'recalculate_totals']
    
    def partner_badge(self, obj):
        if obj.partner:
            color = 'green' if obj.partner.is_active else 'gray'
            return format_html(
                '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
                color, obj.partner.name
            )
        return '-'
    partner_badge.short_description = 'Parceiro'
    
    def period_display(self, obj):
        return f"{obj.period_start.strftime('%d/%m')} → {obj.period_end.strftime('%d/%m/%Y')}"
    period_display.short_description = 'Período'
    
    def net_amount_display(self, obj):
        return format_html(
            '<strong style="color: #2196F3;">€{:,.2f}</strong>',
            obj.net_amount
        )
    net_amount_display.short_description = 'Valor Líquido'
    
    def status_badge(self, obj):
        colors = {
            'DRAFT': 'gray',
            'PENDING': 'orange',
            'PAID': 'green',
            'OVERDUE': 'red',
            'CANCELLED': 'darkgray'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def mark_as_paid(self, request, queryset):
        count = 0
        for invoice in queryset:
            if invoice.status != 'PAID':
                invoice.mark_as_paid()
                count += 1
        
        self.message_user(
            request,
            f'{count} invoice(s) marcado(s) como pago(s).'
        )
    mark_as_paid.short_description = "Marcar como pago"
    
    def check_overdue(self, request, queryset):
        count = 0
        for invoice in queryset:
            if invoice.status == 'PENDING' and invoice.due_date < timezone.now().date():
                invoice.check_overdue()
                count += 1
        
        self.message_user(
            request,
            f'{count} invoice(s) marcado(s) como atrasado(s).'
        )
    check_overdue.short_description = "Verificar atrasos"
    
    def recalculate_totals(self, request, queryset):
        count = 0
        for invoice in queryset:
            invoice.calculate_totals()
            invoice.save()
            count += 1
        
        self.message_user(
            request,
            f'{count} invoice(s) recalculado(s).'
        )
    recalculate_totals.short_description = "Recalcular valores"


class DriverClaimInline(admin.TabularInline):
    model = DriverClaim
    extra = 0
    fields = ('claim_type', 'amount', 'status', 'description')
    readonly_fields = ('claim_type', 'amount', 'description')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(DriverSettlement)
class DriverSettlementAdmin(admin.ModelAdmin):
    list_display = (
        'settlement_display',
        'driver_name',
        'partner_badge',
        'period_display',
        'orders_stats',
        'net_amount_display',
        'status_badge'
    )
    
    list_filter = (
        'status',
        'period_type',
        'partner',
        'year',
        ('approved_at', admin.EmptyFieldListFilter),
        ('paid_at', admin.EmptyFieldListFilter)
    )
    
    search_fields = (
        'driver__nome_completo',
        'driver__email',
        'partner__name'
    )
    
    date_hierarchy = 'period_end'
    
    readonly_fields = (
        'calculated_at',
        'approved_at',
        'approved_by',
        'paid_at',
        'created_at',
        'updated_at',
        'created_by'
    )
    
    fieldsets = (
        ('Motorista e Parceiro', {
            'fields': ('driver', 'partner')
        }),
        ('Período', {
            'fields': (
                'period_type',
                ('year', 'week_number', 'month_number'),
                ('period_start', 'period_end')
            )
        }),
        ('Estatísticas de Entregas', {
            'fields': (
                ('total_orders', 'delivered_orders', 'failed_orders'),
                'success_rate'
            )
        }),
        ('Valores Financeiros', {
            'fields': (
                'gross_amount',
                'bonus_amount',
                ('fuel_deduction', 'claims_deducted', 'other_deductions'),
                'net_amount'
            )
        }),
        ('Status e Aprovação', {
            'fields': (
                'status',
                ('calculated_at', 'approved_at', 'approved_by'),
                ('paid_at', 'payment_reference')
            )
        }),
        ('Documentação', {
            'fields': (
                'pdf_file',
                ('whatsapp_sent', 'whatsapp_sent_at')
            ),
            'classes': ('collapse',)
        }),
        ('Notas', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Auditoria', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [DriverClaimInline]
    
    actions = ['recalculate_settlement', 'approve_settlement', 'mark_as_paid']
    
    def settlement_display(self, obj):
        if obj.period_type == 'WEEKLY':
            return f"Semana {obj.week_number}/{obj.year}"
        return f"{obj.month_number:02d}/{obj.year}"
    settlement_display.short_description = 'Período'
    
    def driver_name(self, obj):
        return obj.driver.nome_completo
    driver_name.short_description = 'Motorista'
    
    def partner_badge(self, obj):
        if obj.partner:
            return format_html(
                '<span style="background-color: #2196F3; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
                obj.partner.name
            )
        return format_html(
            '<span style="background-color: gray; color: white; padding: 3px 8px; border-radius: 3px;">Multi-Partner</span>'
        )
    partner_badge.short_description = 'Parceiro'
    
    def period_display(self, obj):
        return f"{obj.period_start.strftime('%d/%m')} → {obj.period_end.strftime('%d/%m/%Y')}"
    period_display.short_description = 'Datas'
    
    def orders_stats(self, obj):
        return format_html(
            '{} pedidos<br><small>{} entregues ({:.1f}%)</small>',
            obj.total_orders,
            obj.delivered_orders,
            obj.success_rate
        )
    orders_stats.short_description = 'Pedidos'
    
    def net_amount_display(self, obj):
        return format_html(
            '<strong style="color: #4CAF50;">€{:,.2f}</strong>',
            obj.net_amount
        )
    net_amount_display.short_description = 'Valor Líquido'
    
    def status_badge(self, obj):
        colors = {
            'DRAFT': 'gray',
            'CALCULATED': 'blue',
            'APPROVED': 'green',
            'PAID': 'darkgreen',
            'DISPUTED': 'red'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def recalculate_settlement(self, request, queryset):
        count = 0
        for settlement in queryset:
            settlement.calculate_settlement()
            count += 1
        
        self.message_user(
            request,
            f'{count} settlement(s) recalculado(s).'
        )
    recalculate_settlement.short_description = "Recalcular valores"
    
    def approve_settlement(self, request, queryset):
        count = 0
        for settlement in queryset:
            if settlement.status == 'CALCULATED':
                settlement.approve(request.user)
                count += 1
        
        self.message_user(
            request,
            f'{count} settlement(s) aprovado(s).'
        )
    approve_settlement.short_description = "Aprovar settlements"
    
    def mark_as_paid(self, request, queryset):
        count = 0
        for settlement in queryset:
            if settlement.status == 'APPROVED':
                settlement.mark_as_paid()
                count += 1
        
        self.message_user(
            request,
            f'{count} settlement(s) marcado(s) como pago(s).'
        )
    mark_as_paid.short_description = "Marcar como pago"


@admin.register(DriverClaim)
class DriverClaimAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'driver_name',
        'claim_type_badge',
        'amount_display',
        'order_link',
        'status_badge',
        'occurred_at'
    )
    
    list_filter = (
        'status',
        'claim_type',
        'occurred_at',
        ('settlement', admin.EmptyFieldListFilter)
    )
    
    search_fields = (
        'driver__nome_completo',
        'description',
        'order__tracking_code'
    )
    
    date_hierarchy = 'occurred_at'
    
    readonly_fields = (
        'reviewed_at',
        'reviewed_by',
        'created_at',
        'updated_at',
        'created_by'
    )
    
    fieldsets = (
        ('Motorista e Settlement', {
            'fields': ('driver', 'settlement')
        }),
        ('Referências', {
            'fields': ('order', 'vehicle_incident')
        }),
        ('Detalhes do Claim', {
            'fields': (
                'claim_type',
                'amount',
                'description',
                'evidence_file'
            )
        }),
        ('Justificativa do Motorista', {
            'fields': ('justification',),
            'classes': ('collapse',)
        }),
        ('Status e Revisão', {
            'fields': (
                'status',
                'occurred_at',
                ('reviewed_at', 'reviewed_by'),
                'review_notes'
            )
        }),
        ('Auditoria', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_claims', 'reject_claims']
    
    def driver_name(self, obj):
        return obj.driver.nome_completo
    driver_name.short_description = 'Motorista'
    
    def claim_type_badge(self, obj):
        return format_html(
            '<span style="background-color: #FF9800; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            obj.get_claim_type_display()
        )
    claim_type_badge.short_description = 'Tipo'
    
    def amount_display(self, obj):
        return format_html(
            '<strong style="color: #F44336;">-€{:,.2f}</strong>',
            obj.amount
        )
    amount_display.short_description = 'Valor'
    
    def order_link(self, obj):
        if obj.order:
            url = reverse('admin:orders_manager_order_change', args=[obj.order.id])
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.order.tracking_code
            )
        return '-'
    order_link.short_description = 'Pedido'
    
    def status_badge(self, obj):
        colors = {
            'PENDING': 'orange',
            'APPROVED': 'green',
            'REJECTED': 'red',
            'APPEALED': 'purple'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def approve_claims(self, request, queryset):
        count = 0
        for claim in queryset:
            if claim.status == 'PENDING':
                claim.approve(request.user, notes='Aprovado via admin')
                count += 1
        
        self.message_user(
            request,
            f'{count} claim(s) aprovado(s).'
        )
    approve_claims.short_description = "Aprovar claims"
    
    def reject_claims(self, request, queryset):
        count = 0
        for claim in queryset:
            if claim.status == 'PENDING':
                claim.reject(request.user, notes='Rejeitado via admin')
                count += 1
        
        self.message_user(
            request,
            f'{count} claim(s) rejeitado(s).'
        )
    reject_claims.short_description = "Rejeitar claims"

