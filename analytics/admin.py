from django.contrib import admin
from django.utils.html import format_html
from .models import (
    DailyMetrics,
    VolumeForecast,
    PerformanceAlert,
    DriverPerformance
)


@admin.register(DailyMetrics)
class DailyMetricsAdmin(admin.ModelAdmin):
    list_display = [
        'date', 'partner', 'total_orders', 'delivered_orders',
        'success_rate_display', 'net_revenue_display'
    ]
    list_filter = ['partner', 'date']
    search_fields = ['partner__name']
    date_hierarchy = 'date'
    
    def success_rate_display(self, obj):
        color = 'green' if obj.success_rate >= 90 else 'orange' if obj.success_rate >= 75 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, obj.success_rate
        )
    success_rate_display.short_description = 'Taxa Sucesso'
    
    def net_revenue_display(self, obj):
        return f"€{obj.net_revenue:,.2f}"
    net_revenue_display.short_description = 'Receita Líquida'


@admin.register(VolumeForecast)
class VolumeForecastAdmin(admin.ModelAdmin):
    list_display = [
        'forecast_date', 'partner', 'predicted_volume',
        'method', 'confidence_level', 'accuracy'
    ]
    list_filter = ['partner', 'method', 'forecast_date']
    date_hierarchy = 'forecast_date'


@admin.register(PerformanceAlert)
class PerformanceAlertAdmin(admin.ModelAdmin):
    list_display = [
        'created_at', 'severity', 'partner',
        'alert_type', 'is_acknowledged'
    ]
    list_filter = ['severity', 'alert_type', 'partner', 'is_acknowledged']
    date_hierarchy = 'created_at'
    actions = ['mark_acknowledged']
    
    def mark_acknowledged(self, request, queryset):
        for alert in queryset:
            alert.acknowledge(user=request.user)
        self.message_user(request, f'{queryset.count()} alertas reconhecidos.')
    mark_acknowledged.short_description = 'Marcar como reconhecido'


@admin.register(DriverPerformance)
class DriverPerformanceAdmin(admin.ModelAdmin):
    list_display = [
        'month', 'driver', 'total_deliveries',
        'success_rate', 'days_worked', 'rank_in_team'
    ]
    list_filter = ['month']
    date_hierarchy = 'month'
