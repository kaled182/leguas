from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import Order, OrderStatusHistory, OrderIncident


class OrderStatusHistoryInline(admin.TabularInline):
    """Inline para histórico de status"""
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ['status', 'notes', 'changed_by', 'changed_at', 'location']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


class OrderIncidentInline(admin.TabularInline):
    """Inline para incidentes do pedido"""
    model = OrderIncident
    extra = 0
    readonly_fields = ['created_at', 'created_by']
    fields = [
        'incident_type',
        'description',
        'driver_responsible',
        'claim_amount',
        'resolved',
        'created_at',
    ]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'external_reference',
        'partner',
        'recipient_name',
        'postal_code',
        'formatted_status',
        'scheduled_delivery',
        'formatted_driver',
        'is_overdue_display',
        'created_at',
    ]
    
    list_filter = [
        'current_status',
        'partner',
        ('scheduled_delivery', admin.DateFieldListFilter),
        ('created_at', admin.DateFieldListFilter),
        'assigned_driver',
    ]
    
    search_fields = [
        'external_reference',
        'recipient_name',
        'recipient_phone',
        'postal_code',
        'recipient_address',
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'assigned_at',
        'delivered_at',
        'is_overdue',
        'days_since_creation',
    ]
    
    inlines = [OrderStatusHistoryInline, OrderIncidentInline]
    
    fieldsets = (
        ('Parceiro', {
            'fields': ('partner', 'external_reference')
        }),
        ('Destinatário', {
            'fields': (
                'recipient_name',
                'recipient_address',
                'postal_code',
                'recipient_phone',
                'recipient_email',
            )
        }),
        ('Detalhes do Pedido', {
            'fields': (
                'declared_value',
                'weight_kg',
                'dimensions',
            )
        }),
        ('Agendamento', {
            'fields': (
                'scheduled_delivery',
                'delivery_window_start',
                'delivery_window_end',
            )
        }),
        ('Atribuição', {
            'fields': (
                'assigned_driver',
                'assigned_at',
            )
        }),
        ('Status e Entrega', {
            'fields': (
                'current_status',
                'delivered_at',
                'delivery_proof',
            )
        }),
        ('Observações', {
            'fields': (
                'notes',
                'special_instructions',
            )
        }),
        ('Metadados', {
            'fields': (
                'created_at',
                'updated_at',
                'is_overdue',
                'days_since_creation',
            ),
            'classes': ('collapse',),
        }),
    )
    
    def formatted_status(self, obj):
        colors = {
            'PENDING': 'gray',
            'ASSIGNED': 'blue',
            'IN_TRANSIT': 'orange',
            'DELIVERED': 'green',
            'RETURNED': 'purple',
            'INCIDENT': 'red',
            'CANCELLED': 'black',
        }
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            colors.get(obj.current_status, 'gray'),
            obj.get_current_status_display()
        )
    formatted_status.short_description = 'Status'
    formatted_status.admin_order_field = 'current_status'
    
    def formatted_driver(self, obj):
        if obj.assigned_driver:
            return format_html(
                '<span style="color: green;">✓</span> {}',
                obj.assigned_driver.user.get_full_name()
            )
        return format_html('<span style="color: orange;">⚠</span> Não atribuído')
    formatted_driver.short_description = 'Motorista'
    
    def is_overdue_display(self, obj):
        if obj.is_overdue:
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠ ATRASADO</span>'
            )
        return format_html('<span style="color: green;">✓ OK</span>')
    is_overdue_display.short_description = 'Prazo'
    
    actions = ['mark_as_delivered', 'mark_as_incident']
    
    def mark_as_delivered(self, request, queryset):
        """Ação para marcar pedidos como entregues"""
        count = 0
        for order in queryset:
            if order.current_status not in ['DELIVERED', 'CANCELLED']:
                order.mark_as_delivered()
                count += 1
        
        self.message_user(
            request,
            f"{count} pedido(s) marcado(s) como entregue."
        )
    mark_as_delivered.short_description = "Marcar como Entregue"
    
    def mark_as_incident(self, request, queryset):
        """Ação para marcar pedidos com incidente"""
        updated = queryset.update(current_status='INCIDENT')
        self.message_user(
            request,
            f"{updated} pedido(s) marcado(s) com incidente."
        )
    mark_as_incident.short_description = "Marcar como Incidente"


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'order',
        'formatted_status',
        'changed_by',
        'changed_at',
        'location',
    ]
    
    list_filter = [
        'status',
        ('changed_at', admin.DateFieldListFilter),
    ]
    
    search_fields = [
        'order__external_reference',
        'notes',
        'location',
    ]
    
    readonly_fields = ['changed_at']
    
    def formatted_status(self, obj):
        colors = {
            'PENDING': 'gray',
            'ASSIGNED': 'blue',
            'IN_TRANSIT': 'orange',
            'DELIVERED': 'green',
            'RETURNED': 'purple',
            'INCIDENT': 'red',
            'CANCELLED': 'black',
        }
        
        return format_html(
            '<span style="color: {};">●</span> {}',
            colors.get(obj.status, 'gray'),
            obj.get_status_display()
        )
    formatted_status.short_description = 'Status'


@admin.register(OrderIncident)
class OrderIncidentAdmin(admin.ModelAdmin):
    list_display = [
        'order',
        'incident_type',
        'driver_responsible',
        'claim_amount',
        'formatted_resolved',
        'created_at',
    ]
    
    list_filter = [
        'incident_type',
        'resolved',
        'driver_responsible',
        ('created_at', admin.DateFieldListFilter),
    ]
    
    search_fields = [
        'order__external_reference',
        'description',
        'resolution_notes',
    ]
    
    readonly_fields = [
        'created_at',
        'created_by',
        'resolved_at',
    ]
    
    fieldsets = (
        ('Pedido', {
            'fields': ('order',)
        }),
        ('Detalhes do Incidente', {
            'fields': (
                'incident_type',
                'description',
                'driver_responsible',
                'claim_amount',
                'photos',
            )
        }),
        ('Resolução', {
            'fields': (
                'resolved',
                'resolution_notes',
                'resolved_at',
            )
        }),
        ('Metadados', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',),
        }),
    )
    
    def formatted_resolved(self, obj):
        if obj.resolved:
            return format_html(
                '<span style="color: green;">✓</span> Resolvido'
            )
        return format_html(
            '<span style="color: red;">⚠</span> Pendente'
        )
    formatted_resolved.short_description = 'Status'
    
    actions = ['mark_as_resolved']
    
    def mark_as_resolved(self, request, queryset):
        """Ação para marcar incidentes como resolvidos"""
        updated = queryset.filter(resolved=False).update(
            resolved=True,
            resolved_at=timezone.now()
        )
        
        self.message_user(
            request,
            f"{updated} incidente(s) marcado(s) como resolvido."
        )
    mark_as_resolved.short_description = "Marcar como Resolvido"
