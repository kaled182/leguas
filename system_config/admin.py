from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import SystemConfiguration, ConfigurationAudit, CronJobExecution


@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'configured', 'cron_jobs_status_display', 'configured_at', 'updated_at')
    readonly_fields = (
        'configured_at', 'updated_at',
        'cron_metrics_last_run', 'cron_metrics_last_status',
        'cron_forecasts_last_run', 'cron_forecasts_last_status',
        'cron_alerts_last_run', 'cron_alerts_last_status',
        'cron_jobs_summary'
    )
    
    fieldsets = (
        ('Informações da Empresa', {
            'fields': ('company_name', 'logo')
        }),
        ('Configurações de Mapas', {
            'fields': (
                'map_provider', 'maps_api_key', 'mapbox_token',
                'map_default_lat', 'map_default_lng', 'map_default_zoom',
                'map_type', 'map_language', 'map_theme',
                'enable_street_view', 'enable_traffic', 
                'enable_map_clustering', 'enable_drawing_tools', 'enable_fullscreen'
            ),
            'classes': ('collapse',)
        }),
        ('Google Drive', {
            'fields': (
                'gdrive_enabled', 'gdrive_auth_mode', 'gdrive_credentials_json',
                'gdrive_folder_id', 'gdrive_shared_drive_id',
                'gdrive_oauth_client_id', 'gdrive_oauth_client_secret',
                'gdrive_oauth_refresh_token', 'gdrive_oauth_user_email'
            ),
            'classes': ('collapse',)
        }),
        ('FTP', {
            'fields': (
                'ftp_enabled', 'ftp_host', 'ftp_port', 
                'ftp_user', 'ftp_password', 'ftp_path'
            ),
            'classes': ('collapse',)
        }),
        ('SMTP / Email', {
            'fields': (
                'smtp_enabled', 'smtp_host', 'smtp_port', 'smtp_security',
                'smtp_user', 'smtp_password', 'smtp_auth_mode',
                'smtp_oauth_client_id', 'smtp_oauth_client_secret',
                'smtp_oauth_refresh_token', 'smtp_from_name',
                'smtp_from_email', 'smtp_test_recipient'
            ),
            'classes': ('collapse',)
        }),
        ('SMS', {
            'fields': (
                'sms_enabled', 'sms_provider', 'sms_username', 'sms_password',
                'sms_api_token', 'sms_api_url', 'sms_sender_id',
                'sms_test_recipient', 'sms_test_message',
                'sms_aws_region', 'sms_aws_access_key_id', 'sms_aws_secret_access_key',
                'sms_infobip_base_url'
            ),
            'classes': ('collapse',)
        }),
        ('WhatsApp', {
            'fields': (
                'whatsapp_enabled', 'evolution_api_url', 'evolution_api_key'
            ),
            'classes': ('collapse',)
        }),
        ('⏰ Cron Jobs - Analytics', {
            'fields': (
                'cron_jobs_summary',
                ('cron_metrics_enabled', 'cron_metrics_schedule', 'cron_metrics_backfill_days'),
                ('cron_metrics_last_run', 'cron_metrics_last_status'),
                ('cron_forecasts_enabled', 'cron_forecasts_schedule'),
                ('cron_forecasts_days_ahead', 'cron_forecasts_method', 'cron_forecasts_best_only'),
                ('cron_forecasts_last_run', 'cron_forecasts_last_status'),
                ('cron_alerts_enabled', 'cron_alerts_schedule'),
                ('cron_alerts_check_days', 'cron_alerts_send_notifications'),
                ('cron_alerts_last_run', 'cron_alerts_last_status'),
            ),
            'description': 'Configure jobs automáticos para cálculo de métricas, forecasts e alertas. '
                          'Estes jobs são executados automaticamente nos horários configurados.'
        }),
        ('Sistema', {
            'fields': ('configured', 'configured_at', 'updated_at')
        }),
    )
    
    def cron_jobs_status_display(self, obj):
        """Exibe status resumido dos cron jobs"""
        if not obj:
            return '-'
        
        jobs_enabled = []
        if obj.cron_metrics_enabled:
            jobs_enabled.append('📊')
        if obj.cron_forecasts_enabled:
            jobs_enabled.append('📈')
        if obj.cron_alerts_enabled:
            jobs_enabled.append('🔔')
        
        if not jobs_enabled:
            return format_html('<span style="color: #999;">Nenhum ativo</span>')
        
        return format_html(' '.join(jobs_enabled))
    
    cron_jobs_status_display.short_description = 'Jobs Ativos'
    
    def cron_jobs_summary(self, obj):
        """Exibe resumo visual dos cron jobs"""
        if not obj:
            return '-'
        
        from django.utils import timezone
        
        html = '<div style="background: #f0f0f0; padding: 15px; border-radius: 5px;">'
        html += '<h3 style="margin-top: 0;">📊 Status dos Cron Jobs</h3>'
        
        jobs = [
            {
                'name': '📊 Métricas Diárias',
                'enabled': obj.cron_metrics_enabled,
                'schedule': obj.cron_metrics_schedule,
                'last_run': obj.cron_metrics_last_run,
                'status': obj.cron_metrics_last_status,
            },
            {
                'name': '📈 Forecasts de Volume',
                'enabled': obj.cron_forecasts_enabled,
                'schedule': obj.cron_forecasts_schedule,
                'last_run': obj.cron_forecasts_last_run,
                'status': obj.cron_forecasts_last_status,
            },
            {
                'name': '🔔 Alertas de Performance',
                'enabled': obj.cron_alerts_enabled,
                'schedule': obj.cron_alerts_schedule,
                'last_run': obj.cron_alerts_last_run,
                'status': obj.cron_alerts_last_status,
            },
        ]
        
        for job in jobs:
            status_color = '#28a745' if job['enabled'] else '#6c757d'
            status_text = 'ATIVO' if job['enabled'] else 'INATIVO'
            
            html += f'<div style="margin: 10px 0; padding: 10px; background: white; border-left: 4px solid {status_color};">'
            html += f'<strong>{job["name"]}</strong> '
            html += f'<span style="background: {status_color}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{status_text}</span><br>'
            
            if job['enabled']:
                html += f'<small>⏰ Horário: {job["schedule"]}</small><br>'
                
                if job['last_run']:
                    time_diff = timezone.now() - job['last_run']
                    if time_diff.days > 0:
                        time_ago = f"há {time_diff.days} dia(s)"
                    elif time_diff.seconds > 3600:
                        time_ago = f"há {time_diff.seconds // 3600} hora(s)"
                    else:
                        time_ago = f"há {time_diff.seconds // 60} minuto(s)"
                    
                    status_icon = {
                        'success': '✅',
                        'failed': '❌',
                        'running': '⏳'
                    }.get(job['status'], '❓')
                    
                    html += f'<small>Última execução: {job["last_run"].strftime("%d/%m/%Y %H:%M")} ({time_ago}) {status_icon}</small>'
                else:
                    html += '<small style="color: #999;">Ainda não executado</small>'
            
            html += '</div>'
        
        html += '<p style="margin-top: 15px;"><a href="/admin/system_config/cronjobexecution/" class="button">Ver Histórico de Execuções</a></p>'
        html += '</div>'
        
        return mark_safe(html)
    
    cron_jobs_summary.short_description = 'Resumo dos Jobs'
    
    def has_add_permission(self, request):
        # Apenas uma instância de configuração permitida
        return not SystemConfiguration.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Não permitir deletar a configuração
        return False


@admin.register(ConfigurationAudit)
class ConfigurationAuditAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'field_name', 'ip_address')
    list_filter = ('action', 'timestamp')
    search_fields = ('user__username', 'field_name', 'ip_address')
    readonly_fields = ('user', 'timestamp', 'action', 'field_name', 'old_value', 'new_value', 'ip_address')
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CronJobExecution)
class CronJobExecutionAdmin(admin.ModelAdmin):
    list_display = (
        'job_type_display',
        'started_at',
        'duration_display',
        'status_display',
        'results_summary',
        'triggered_by'
    )
    list_filter = ('job_type', 'status', 'triggered_by', 'started_at')
    search_fields = ('output_log', 'error_log', 'hostname')
    readonly_fields = (
        'started_at', 'finished_at', 'duration_seconds',
        'records_created', 'records_updated', 'records_skipped', 'errors_count',
        'output_log', 'error_log', 'parameters', 'hostname',
        'duration_display_detailed', 'success_rate_display'
    )
    date_hierarchy = 'started_at'
    
    fieldsets = (
        ('Informações da Execução', {
            'fields': (
                'job_type', 'status', 'triggered_by',
                ('started_at', 'finished_at'),
                'duration_display_detailed', 'hostname'
            )
        }),
        ('Resultados', {
            'fields': (
                ('records_created', 'records_updated'),
                ('records_skipped', 'errors_count'),
                'success_rate_display'
            )
        }),
        ('Parâmetros', {
            'fields': ('parameters',),
            'classes': ('collapse',)
        }),
        ('Logs', {
            'fields': ('output_log', 'error_log'),
            'classes': ('collapse',)
        }),
    )
    
    def job_type_display(self, obj):
        """Exibe tipo do job com emoji"""
        icons = {
            'metrics': '📊',
            'forecasts': '📈',
            'alerts': '🔔'
        }
        icon = icons.get(obj.job_type, '📋')
        return format_html('{} {}', icon, obj.get_job_type_display())
    
    job_type_display.short_description = 'Tipo de Job'
    job_type_display.admin_order_field = 'job_type'
    
    def duration_display(self, obj):
        """Exibe duração formatada"""
        return obj.get_duration_display()
    
    duration_display.short_description = 'Duração'
    
    def duration_display_detailed(self, obj):
        """Exibe duração detalhada"""
        if obj.duration_seconds is None:
            return format_html('<span style="color: #ff9800;">⏳ Em execução...</span>')
        
        duration = obj.get_duration_display()
        
        # Cor baseada na duração
        if obj.duration_seconds < 60:
            color = '#28a745'  # Verde - rápido
        elif obj.duration_seconds < 300:
            color = '#ffc107'  # Amarelo - normal
        else:
            color = '#dc3545'  # Vermelho - lento
        
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, duration)
    
    duration_display_detailed.short_description = 'Duração'
    
    def status_display(self, obj):
        """Exibe status com cor"""
        colors = {
            'success': '#28a745',
            'failed': '#dc3545',
            'running': '#ff9800'
        }
        icons = {
            'success': '✅',
            'failed': '❌',
            'running': '⏳'
        }
        color = colors.get(obj.status, '#6c757d')
        icon = icons.get(obj.status, '❓')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icon, obj.get_status_display()
        )
    
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status'
    
    def results_summary(self, obj):
        """Exibe resumo dos resultados"""
        total = obj.records_created + obj.records_updated + obj.records_skipped + obj.errors_count
        
        if total == 0:
            return format_html('<span style="color: #999;">Sem dados</span>')
        
        parts = []
        if obj.records_created > 0:
            parts.append(f'<span style="color: #28a745;">✨ {obj.records_created}</span>')
        if obj.records_updated > 0:
            parts.append(f'<span style="color: #17a2b8;">🔄 {obj.records_updated}</span>')
        if obj.records_skipped > 0:
            parts.append(f'<span style="color: #6c757d;">⏭️ {obj.records_skipped}</span>')
        if obj.errors_count > 0:
            parts.append(f'<span style="color: #dc3545;">❌ {obj.errors_count}</span>')
        
        return format_html(' | '.join(parts))
    
    results_summary.short_description = 'Resultados'
    
    def success_rate_display(self, obj):
        """Exibe taxa de sucesso"""
        rate = obj.get_success_rate()
        
        if rate >= 95:
            color = '#28a745'
            icon = '✅'
        elif rate >= 80:
            color = '#ffc107'
            icon = '⚠️'
        else:
            color = '#dc3545'
            icon = '❌'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {:.1f}%</span>',
            color, icon, rate
        )
    
    success_rate_display.short_description = 'Taxa de Sucesso'
    
    def has_add_permission(self, request):
        # Execuções são criadas automaticamente
        return False
    
    def has_change_permission(self, request, obj=None):
        # Não permitir edição
        return False

