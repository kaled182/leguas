from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import DriverShift


@admin.register(DriverShift)
class DriverShiftAdmin(admin.ModelAdmin):
    list_display = [
        'driver',
        'date',
        'formatted_time',
        'formatted_stats',
        'formatted_status',
        'whatsapp_sent',
    ]
    
    list_filter = [
        'status',
        ('date', admin.DateFieldListFilter),
        'whatsapp_notification_sent',
    ]
    
    search_fields = [
        'driver__user__first_name',
        'driver__user__last_name',
        'notes',
    ]
    
    readonly_fields = [
        'whatsapp_notification_sent_at',
        'created_at',
        'updated_at',
        'success_rate',
        'duration_hours',
        'is_active',
    ]
    
    filter_horizontal = ['assigned_postal_zones']
    
    fieldsets = (
        ('Motorista e Data', {
            'fields': ('driver', 'date', 'created_by')
        }),
        ('Zonas Atribuídas', {
            'fields': ('assigned_postal_zones',)
        }),
        ('Horário Previsto', {
            'fields': ('start_time', 'end_time')
        }),
        ('Horário Real', {
            'fields': (
                'actual_start_time',
                'actual_end_time',
                'duration_hours',
            )
        }),
        ('Estatísticas', {
            'fields': (
                'total_deliveries',
                'successful_deliveries',
                'failed_deliveries',
                'success_rate',
            )
        }),
        ('Status', {
            'fields': ('status', 'is_active')
        }),
        ('Notificação WhatsApp', {
            'fields': (
                'whatsapp_notification_sent',
                'whatsapp_notification_sent_at',
            )
        }),
        ('Observações', {
            'fields': ('notes',)
        }),
        ('Metadados', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def formatted_time(self, obj):
        return format_html(
            '{} - {}',
            obj.start_time.strftime('%H:%M'),
            obj.end_time.strftime('%H:%M')
        )
    formatted_time.short_description = 'Horário'
    
    def formatted_stats(self, obj):
        if obj.total_deliveries == 0:
            return format_html('<span style="color: gray;">Sem entregas</span>')
        
        color = 'green' if obj.success_rate >= 90 else 'orange' if obj.success_rate >= 70 else 'red'
        
        return format_html(
            '<span style="color: {};">{}/{} ({:.1f}%)</span>',
            color,
            obj.successful_deliveries,
            obj.total_deliveries,
            obj.success_rate
        )
    formatted_stats.short_description = 'Entregas (Sucesso)'
    
    def formatted_status(self, obj):
        colors = {
            'SCHEDULED': 'blue',
            'IN_PROGRESS': 'orange',
            'COMPLETED': 'green',
            'CANCELLED': 'red',
        }
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            colors.get(obj.status, 'gray'),
            obj.get_status_display()
        )
    formatted_status.short_description = 'Status'
    
    def whatsapp_sent(self, obj):
        if obj.whatsapp_notification_sent:
            return format_html(
                '<span style="color: green;">✓ Enviada</span>'
            )
        return format_html(
            '<span style="color: orange;">⚠ Não enviada</span>'
        )
    whatsapp_sent.short_description = 'WhatsApp'
    
    actions = [
        'send_whatsapp_notifications',
        'update_statistics',
        'mark_as_completed',
        'assign_orders_to_shifts',
    ]
    
    def send_whatsapp_notifications(self, request, queryset):
        """Envia notificações WhatsApp para turnos selecionados"""
        sent_count = 0
        
        for shift in queryset:
            if shift.send_whatsapp_notification():
                sent_count += 1
        
        self.message_user(
            request,
            f"{sent_count} notificação(ões) WhatsApp enviada(s)."
        )
    send_whatsapp_notifications.short_description = "Enviar notificações WhatsApp"
    
    def update_statistics(self, request, queryset):
        """Atualiza estatísticas dos turnos"""
        for shift in queryset:
            shift.update_statistics()
        
        self.message_user(
            request,
            f"Estatísticas atualizadas para {queryset.count()} turno(s)."
        )
    update_statistics.short_description = "Atualizar estatísticas"
    
    def mark_as_completed(self, request, queryset):
        """Marca turnos como concluídos"""
        updated = queryset.update(status='COMPLETED')
        
        self.message_user(
            request,
            f"{updated} turno(s) marcado(s) como concluído."
        )
    mark_as_completed.short_description = "Marcar como Concluído"
    
    def assign_orders_to_shifts(self, request, queryset):
        """Atribui pedidos aos turnos selecionados"""
        from route_allocation.models import RouteOptimizer
        
        total_assigned = 0
        
        for shift in queryset:
            result = RouteOptimizer.assign_orders_to_shift(shift)
            if result['success']:
                total_assigned += result['assigned_count']
        
        self.message_user(
            request,
            f"{total_assigned} pedido(s) atribuído(s) a {queryset.count()} turno(s)."
        )
    assign_orders_to_shifts.short_description = "Atribuir pedidos automaticamente"
