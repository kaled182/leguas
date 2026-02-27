from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import Partner, PartnerIntegration


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'nif',
        'formatted_status',
        'active_orders_count',
        'has_integrations',
        'contact_email',
        'created_at',
    ]
    
    list_filter = [
        'is_active',
        'auto_assign_orders',
        'created_at',
    ]
    
    search_fields = [
        'name',
        'nif',
        'contact_email',
        'contact_phone',
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'active_orders_count',
        'has_active_integration',
    ]
    
    fieldsets = (
        ('Identificação', {
            'fields': ('name', 'nif')
        }),
        ('Contactos', {
            'fields': ('contact_email', 'contact_phone')
        }),
        ('Configurações de Integração', {
            'fields': ('api_credentials',),
            'classes': ('collapse',),
        }),
        ('Configurações Operacionais', {
            'fields': (
                'is_active',
                'auto_assign_orders',
                'default_delivery_time_days',
            )
        }),
        ('Informações Adicionais', {
            'fields': ('notes',)
        }),
        ('Metadados', {
            'fields': (
                'created_at',
                'updated_at',
                'active_orders_count',
                'has_active_integration',
            ),
            'classes': ('collapse',),
        }),
    )
    
    def formatted_status(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="color: green;">●</span> Ativo'
            )
        return format_html(
            '<span style="color: red;">●</span> Inativo'
        )
    formatted_status.short_description = 'Status'
    
    def has_integrations(self, obj):
        count = obj.integrations.filter(is_active=True).count()
        if count > 0:
            return format_html(
                '<span style="color: green;">✓</span> {} integraç{}</span>',
                count,
                'ão' if count == 1 else 'ões'
            )
        return format_html(
            '<span style="color: orange;">⚠</span> Sem integrações'
        )
    has_integrations.short_description = 'Integrações'


@admin.register(PartnerIntegration)
class PartnerIntegrationAdmin(admin.ModelAdmin):
    list_display = [
        'partner',
        'integration_type',
        'formatted_status',
        'sync_status',
        'last_sync_at',
        'is_overdue',
    ]
    
    list_filter = [
        'integration_type',
        'is_active',
        'last_sync_status',
        'partner',
    ]
    
    search_fields = [
        'partner__name',
        'endpoint_url',
    ]
    
    readonly_fields = [
        'last_sync_at',
        'last_sync_status',
        'last_sync_message',
        'is_sync_overdue',
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        ('Parceiro', {
            'fields': ('partner',)
        }),
        ('Configuração de Integração', {
            'fields': (
                'integration_type',
                'endpoint_url',
                'auth_config',
            )
        }),
        ('Sincronização', {
            'fields': (
                'is_active',
                'sync_frequency_minutes',
                'last_sync_at',
                'last_sync_status',
                'last_sync_message',
                'is_sync_overdue',
            )
        }),
        ('Metadados', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def formatted_status(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="color: green;">●</span> Ativo'
            )
        return format_html(
            '<span style="color: red;">●</span> Inativo'
        )
    formatted_status.short_description = 'Status'
    
    def sync_status(self, obj):
        if not obj.last_sync_status:
            return format_html(
                '<span style="color: gray;">Nunca sincronizado</span>'
            )
        
        colors = {
            'SUCCESS': 'green',
            'ERROR': 'red',
            'PARTIAL': 'orange',
        }
        
        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(obj.last_sync_status, 'gray'),
            obj.get_last_sync_status_display()
        )
    sync_status.short_description = 'Última Sinc.'
    
    def is_overdue(self, obj):
        if obj.is_sync_overdue:
            return format_html(
                '<span style="color: red;">⚠ Atrasada</span>'
            )
        return format_html(
            '<span style="color: green;">✓ OK</span>'
        )
    is_overdue.short_description = 'Status Sinc.'
    
    actions = ['trigger_sync']
    
    def trigger_sync(self, request, queryset):
        """Ação para disparar sincronização manual"""
        # TODO: Implementar lógica de sincronização
        self.message_user(
            request,
            f"Sincronização manual disparada para {queryset.count()} integrações."
        )
    trigger_sync.short_description = "Disparar sincronização manual"
