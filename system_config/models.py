from django.db import models
from django.contrib.auth import get_user_model
from typing import Dict, List, Optional

from .fields import EncryptedCharField

User = get_user_model()


class SystemConfiguration(models.Model):
    """Configuração global do sistema - Singleton pattern"""
    
    # Company Information
    company_name = models.CharField("Nome da Empresa", max_length=255, blank=True, null=True)
    logo = models.ImageField("Logotipo", upload_to="system_config/logos/", null=True, blank=True)
    
    # Maps Configuration - Provider Selection
    map_provider = models.CharField(
        "Provedor de Mapas",
        max_length=20,
        choices=[
            ("google", "Google Maps"),
            ("mapbox", "Mapbox"),
            ("osm", "OpenStreetMap"),
        ],
        default="google",
    )
    
    # Maps - Google Maps
    google_maps_api_key = EncryptedCharField("Google Maps API Key", max_length=512, blank=True, null=True)
    map_default_zoom = models.IntegerField("Zoom Padrão", default=12)
    map_default_lat = models.DecimalField("Latitude Padrão", max_digits=10, decimal_places=7, default=41.69314)
    map_default_lng = models.DecimalField("Longitude Padrão", max_digits=10, decimal_places=7, default=-8.83565)
    map_type = models.CharField("Tipo de Mapa", max_length=20, default='terrain')
    map_styles = models.TextField("Estilos Customizados (JSON)", blank=True, null=True)
    enable_street_view = models.BooleanField("Ativar Street View", default=True)
    enable_traffic = models.BooleanField("Ativar Trânsito", default=False)
    
    # Maps - Mapbox
    mapbox_access_token = EncryptedCharField("Mapbox Access Token", max_length=512, blank=True, null=True)
    mapbox_style = models.CharField("Estilo Mapbox", max_length=255, default='mapbox://styles/mapbox/streets-v12')
    mapbox_custom_style = models.CharField("Estilo Customizado Mapbox", max_length=255, blank=True, null=True)
    mapbox_enable_3d = models.BooleanField("Ativar 3D Mapbox", default=False)
    
    # Maps - Esri
    esri_api_key = EncryptedCharField("Esri API Key", max_length=512, blank=True, null=True)
    esri_basemap = models.CharField("Basemap Esri", max_length=50, default='streets')
    
    # Maps - Common Settings
    map_language = models.CharField("Idioma do Mapa", max_length=10, default='pt-PT')
    map_theme = models.CharField(
        "Tema do Mapa",
        max_length=10,
        default='light',
        choices=[
            ('light', 'Claro'),
            ('dark', 'Escuro'),
            ('auto', 'Automático')
        ]
    )
    enable_map_clustering = models.BooleanField("Ativar Clustering", default=True)
    enable_drawing_tools = models.BooleanField("Ativar Ferramentas de Desenho", default=True)
    enable_fullscreen = models.BooleanField("Ativar Fullscreen", default=True)
    
    # Maps - OSM
    osm_tile_server = models.CharField("Servidor de Tiles OSM", max_length=255, blank=True, null=True)
    
    # Google Drive Configuration
    gdrive_enabled = models.BooleanField("Google Drive Ativado", default=False)
    gdrive_auth_mode = models.CharField(
        "Modo de Autenticação Google Drive",
        max_length=32,
        default="service_account",
        choices=[
            ("service_account", "Service Account"),
            ("oauth", "OAuth (Conta pessoal)"),
        ],
    )
    gdrive_credentials_json = EncryptedCharField("Google Drive Credentials JSON", max_length=4096, max_plain_length=4096, blank=True, null=True)
    gdrive_folder_id = EncryptedCharField("Google Drive Folder ID", max_length=255, blank=True, null=True)
    gdrive_shared_drive_id = EncryptedCharField("Google Drive Shared Drive ID", max_length=255, blank=True, null=True)
    gdrive_oauth_client_id = EncryptedCharField("OAuth Client ID", max_length=255, blank=True, null=True)
    gdrive_oauth_client_secret = EncryptedCharField("OAuth Client Secret", max_length=255, blank=True, null=True)
    gdrive_oauth_refresh_token = EncryptedCharField("OAuth Refresh Token", max_length=512, blank=True, null=True)
    gdrive_oauth_user_email = EncryptedCharField("OAuth User Email", max_length=255, blank=True, null=True)
    
    # FTP Configuration
    ftp_enabled = models.BooleanField("FTP Ativado", default=False)
    ftp_host = EncryptedCharField("Host FTP", max_length=255, blank=True, null=True)
    ftp_port = models.IntegerField("Porta FTP", default=21)
    ftp_user = EncryptedCharField("Utilizador FTP", max_length=255, blank=True, null=True)
    ftp_password = EncryptedCharField("Senha FTP", max_length=255, blank=True, null=True)
    ftp_directory = EncryptedCharField("Diretório FTP", max_length=255, blank=True, null=True)
    
    # SMTP Configuration
    smtp_enabled = models.BooleanField("SMTP Ativado", default=False)
    smtp_host = EncryptedCharField("Host SMTP", max_length=255, blank=True, null=True)
    smtp_port = EncryptedCharField("Porta SMTP", max_length=32, blank=True, null=True, default="587")
    smtp_security = EncryptedCharField("Segurança SMTP", max_length=16, blank=True, null=True, default="TLS")
    smtp_user = EncryptedCharField("Utilizador SMTP", max_length=255, blank=True, null=True)
    smtp_password = EncryptedCharField("Senha SMTP", max_length=255, blank=True, null=True)
    smtp_auth_mode = EncryptedCharField("Modo de Autenticação SMTP", max_length=32, blank=True, null=True, default="password")
    smtp_oauth_client_id = EncryptedCharField("OAuth Client ID SMTP", max_length=255, blank=True, null=True)
    smtp_oauth_client_secret = EncryptedCharField("OAuth Client Secret SMTP", max_length=255, blank=True, null=True)
    smtp_oauth_refresh_token = EncryptedCharField("OAuth Refresh Token SMTP", max_length=512, blank=True, null=True)
    smtp_from_name = EncryptedCharField("Nome do Remetente", max_length=255, blank=True, null=True)
    smtp_from_email = EncryptedCharField("E-mail do Remetente", max_length=255, blank=True, null=True)
    smtp_test_recipient = EncryptedCharField("Destinatário de Teste", max_length=255, blank=True, null=True)
    smtp_use_tls = models.BooleanField("Usar TLS", default=True)
    
    # SMS Configuration
    sms_enabled = models.BooleanField("SMS Ativado", default=False)
    sms_provider = models.CharField(
        "Provedor SMS",
        max_length=32,
        default="twilio",
        choices=[
            ("twilio", "Twilio"),
            ("nexmo", "Nexmo"),
            ("aws_sns", "AWS SNS"),
            ("infobip", "Infobip"),
            ("zenvia", "Zenvia"),
            ("totalvoice", "TotalVoice"),
        ],
    )
    sms_provider_rank = models.IntegerField("Rank do Provedor SMS", default=1)
    sms_account_sid = EncryptedCharField("Account SID/Username SMS", max_length=255, blank=True, null=True)
    sms_auth_token = EncryptedCharField("Auth Token/Password SMS", max_length=512, blank=True, null=True)
    sms_api_key = EncryptedCharField("API Key SMS", max_length=512, blank=True, null=True)
    sms_api_url = EncryptedCharField("API URL SMS", max_length=512, blank=True, null=True)
    sms_from_number = EncryptedCharField("Número de Envio SMS", max_length=64, blank=True, null=True)
    sms_test_recipient = EncryptedCharField("Destinatário de Teste SMS", max_length=64, blank=True, null=True)
    sms_test_message = EncryptedCharField("Mensagem de Teste SMS", max_length=255, blank=True, null=True)
    sms_priority = EncryptedCharField("Prioridade SMS", max_length=16, blank=True, null=True)
    
    # SMS - AWS SNS specific
    sms_aws_region = EncryptedCharField("AWS Region", max_length=64, blank=True, null=True)
    sms_aws_access_key_id = EncryptedCharField("AWS Access Key ID", max_length=255, blank=True, null=True)
    sms_aws_secret_access_key = EncryptedCharField("AWS Secret Access Key", max_length=255, blank=True, null=True)
    
    # SMS - Infobip specific
    sms_infobip_base_url = EncryptedCharField("Infobip Base URL", max_length=255, blank=True, null=True)
    
    # WhatsApp Configuration (Evolution API)
    whatsapp_enabled = models.BooleanField("WhatsApp Ativado", default=False)
    whatsapp_evolution_api_url = EncryptedCharField("Evolution API URL", max_length=512, blank=True, null=True)
    whatsapp_evolution_api_key = EncryptedCharField("Evolution API Key", max_length=512, blank=True, null=True)
    whatsapp_instance_name = models.CharField("Nome da Instância WhatsApp", max_length=255, blank=True, null=True)
    
    # Typebot Configuration
    typebot_enabled = models.BooleanField("Typebot Ativado", default=False)
    typebot_builder_url = EncryptedCharField("Typebot Builder URL", max_length=512, blank=True, null=True, default="http://localhost:8081")
    typebot_viewer_url = EncryptedCharField("Typebot Viewer URL", max_length=512, blank=True, null=True, default="http://localhost:8082")
    typebot_api_key = EncryptedCharField("Typebot API Key", max_length=512, blank=True, null=True)
    typebot_admin_email = EncryptedCharField("Typebot Admin Email", max_length=255, blank=True, null=True)
    typebot_admin_password = EncryptedCharField("Typebot Admin Password", max_length=255, blank=True, null=True)
    typebot_encryption_secret = EncryptedCharField("Typebot Encryption Secret", max_length=512, blank=True, null=True)
    typebot_database_url = EncryptedCharField("Typebot Database URL", max_length=512, blank=True, null=True)
    typebot_s3_endpoint = EncryptedCharField("Typebot S3 Endpoint", max_length=512, blank=True, null=True)
    typebot_s3_bucket = EncryptedCharField("Typebot S3 Bucket", max_length=255, blank=True, null=True)
    typebot_s3_access_key = EncryptedCharField("Typebot S3 Access Key", max_length=255, blank=True, null=True)
    typebot_s3_secret_key = EncryptedCharField("Typebot S3 Secret Key", max_length=512, blank=True, null=True)
    typebot_smtp_host = EncryptedCharField("Typebot SMTP Host", max_length=255, blank=True, null=True)
    typebot_smtp_port = models.IntegerField("Typebot SMTP Port", default=587, blank=True, null=True)
    typebot_smtp_username = EncryptedCharField("Typebot SMTP Username", max_length=255, blank=True, null=True)
    typebot_smtp_password = EncryptedCharField("Typebot SMTP Password", max_length=512, blank=True, null=True)
    typebot_smtp_from = EncryptedCharField("Typebot SMTP From", max_length=255, blank=True, null=True)
    typebot_google_client_id = EncryptedCharField("Typebot Google Client ID", max_length=512, blank=True, null=True)
    typebot_google_client_secret = EncryptedCharField("Typebot Google Client Secret", max_length=512, blank=True, null=True)
    typebot_default_workspace_plan = models.CharField(
        "Typebot Default Workspace Plan",
        max_length=32,
        default="free",
        choices=[
            ("free", "Free"),
            ("starter", "Starter"),
            ("pro", "Pro"),
            ("unlimited", "Unlimited"),
        ],
    )
    typebot_disable_signup = models.BooleanField("Typebot Disable Signup", default=True)
    
    # Database Configuration (para backups, etc)
    db_host = EncryptedCharField("Host da Base de Dados", max_length=512, blank=True, null=True)
    db_port = EncryptedCharField("Porta da Base de Dados", max_length=64, blank=True, null=True)
    db_name = EncryptedCharField("Nome da Base de Dados", max_length=512, blank=True, null=True)
    db_user = EncryptedCharField("Utilizador da Base de Dados", max_length=512, blank=True, null=True)
    db_password = EncryptedCharField("Senha da Base de Dados", max_length=512, blank=True, null=True)
    
    # Redis Configuration
    redis_url = EncryptedCharField("URL do Redis", max_length=512, blank=True, null=True)
    
    # System Status
    configured = models.BooleanField("Sistema Configurado", default=False)
    configured_at = models.DateTimeField("Configurado em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizado em", auto_now=True)
    
    class Meta:
        verbose_name = "Configuração do Sistema"
        verbose_name_plural = "Configurações do Sistema"
    
    def __str__(self) -> str:
        return self.company_name or "Configuração do Sistema"
    
    @classmethod
    def get_config(cls):
        """Retorna a única instância de configuração (singleton pattern)"""
        config, created = cls.objects.get_or_create(pk=1)
        return config
    
    def save(self, *args, **kwargs):
        """Garante que só existe uma instância"""
        self.pk = 1
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Previne deleção da configuração"""
        pass


class ConfigurationAudit(models.Model):
    """Audit trail for configuration changes"""
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Utilizador")
    timestamp = models.DateTimeField("Data/Hora", auto_now_add=True)
    action = models.CharField("Ação", max_length=50)
    field_name = models.CharField("Campo", max_length=100, blank=True, null=True)
    old_value = models.TextField("Valor Anterior", blank=True, null=True)
    new_value = models.TextField("Novo Valor", blank=True, null=True)
    ip_address = models.GenericIPAddressField("Endereço IP", blank=True, null=True)
    
    class Meta:
        verbose_name = "Auditoria de Configuração"
        verbose_name_plural = "Auditorias de Configuração"
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.user} - {self.action} - {self.timestamp}"


class MessagingGateway(models.Model):
    """Configuração de gateways de mensagens (SMS, WhatsApp, E-mail, etc)"""
    
    GATEWAY_TYPES = [
        ("sms", "SMS"),
        ("whatsapp", "WhatsApp"),
        ("telegram", "Telegram"),
        ("smtp", "SMTP"),
    ]

    name = models.CharField("Nome", max_length=120)
    gateway_type = models.CharField("Tipo de Gateway", max_length=16, choices=GATEWAY_TYPES)
    provider = models.CharField("Provedor", max_length=64, blank=True, null=True)
    priority = models.IntegerField("Prioridade", default=1)
    enabled = models.BooleanField("Ativado", default=True)
    config = models.JSONField("Configuração", default=dict, blank=True)
    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Gateway de Mensagens"
        verbose_name_plural = "Gateways de Mensagens"
        ordering = ['priority', 'name']

    def __str__(self) -> str:
        return f"{self.name} ({self.gateway_type})"


class CompanyProfile(models.Model):
    """Profile da empresa com assets e informações adicionais"""
    
    company_name = models.CharField("Nome da Empresa", max_length=255)
    assets_logo = models.ImageField("Logotipo (Assets)", upload_to="company/logos/", null=True, blank=True)
    assets_favicon = models.ImageField("Favicon", upload_to="company/favicon/", null=True, blank=True)
    primary_color = models.CharField("Cor Primária", max_length=7, default="#0ea5e9", help_text="Código hexadecimal (ex: #0ea5e9)")
    secondary_color = models.CharField("Cor Secundária", max_length=7, default="#0369a1", help_text="Código hexadecimal (ex: #0369a1)")
    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizado em", auto_now=True)
    
    class Meta:
        verbose_name = "Perfil da Empresa"
        verbose_name_plural = "Perfis da Empresa"
    
    def __str__(self) -> str:
        return self.company_name
