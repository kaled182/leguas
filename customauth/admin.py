"""
Configuração do Django Admin para customauth.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import DriverAccess


@admin.register(DriverAccess)
class DriverAccessAdmin(admin.ModelAdmin):
    """
    Configuração do admin para DriverAccess.
    """
    
    list_display = [
        'full_name', 'email', 'nif', 'phone', 
        'driver_display', 'user', 'created_at'
    ]
    
    list_filter = [
        'created_at', 'updated_at', 'user'
    ]
    
    search_fields = [
        'profile_picture' 'first_name', 'last_name', 'email', 'nif', 'phone'
    ]
    
    readonly_fields = ['created_at', 'updated_at', 'password']
    
    fieldsets = (
        ('Informações Pessoais', {
            'fields': ('profile_picture', 'first_name', 'last_name', 'email', 'phone', 'nif')
        }),
        ('Relacionamentos', {
            'fields': ('user', 'driver')
        }),
        ('Autenticação', {
            'fields': ('password',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def driver_display(self, obj):
        """Exibe informações do motorista associado."""
        if obj.driver:
            return format_html(
                '<span style="color: green;">✓ {}</span>', 
                obj.driver.name
            )
        return format_html(
            '<span style="color: orange;">⚠ Não vinculado</span>'
        )
    driver_display.short_description = 'Motorista'
    
    def get_queryset(self, request):
        """Otimiza consultas do admin."""
        return super().get_queryset(request).select_related('user', 'driver')

