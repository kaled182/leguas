from django.contrib import admin
from .models import SystemConfiguration, ConfigurationAudit


@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'configured', 'configured_at', 'updated_at')
    readonly_fields = ('configured_at', 'updated_at')
    
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
        ('Sistema', {
            'fields': ('configured', 'configured_at', 'updated_at')
        }),
    )
    
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
