from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone


class Partner(models.Model):
    """
    Representa um parceiro logístico (e.g., Paack, Amazon, DPD, CTT).
    Este é o modelo central da arquitetura multi-partner.
    """
    
    # Identificação
    name = models.CharField(
        'Nome do Parceiro',
        max_length=200,
        unique=True,
        help_text='Nome oficial do parceiro (e.g., "Paack", "Amazon Logistics")'
    )
    
    nif_validator = RegexValidator(
        regex=r'^(PT)?\d{9}$',
        message='NIF deve ter 9 dígitos, opcionalmente precedidos por "PT"'
    )
    nif = models.CharField(
        'NIF',
        max_length=20,
        unique=True,
        validators=[nif_validator],
        help_text='Número de Identificação Fiscal português'
    )
    
    # Contactos
    contact_email = models.EmailField(
        'Email de Contacto',
        help_text='Email principal para comunicações operacionais'
    )
    
    contact_phone = models.CharField(
        'Telefone de Contacto',
        max_length=20,
        blank=True,
        help_text='Telefone de suporte operacional'
    )
    
    # Configurações de Integração
    api_credentials = models.JSONField(
        'Credenciais API',
        default=dict,
        blank=True,
        help_text='Credenciais de API (api_key, api_secret, etc.). Será encriptado em produção.'
    )
    
    # Status
    is_active = models.BooleanField(
        'Ativo',
        default=True,
        help_text='Se desativado, não serão feitas novas importações de pedidos'
    )
    
    # Configurações Operacionais
    default_delivery_time_days = models.IntegerField(
        'Prazo de Entrega Padrão (dias)',
        default=2,
        help_text='Prazo padrão para entregas sem data específica'
    )
    
    auto_assign_orders = models.BooleanField(
        'Auto-Atribuir Pedidos',
        default=True,
        help_text='Se ativo, pedidos serão automaticamente atribuídos a motoristas disponíveis'
    )
    
    # Metadados
    created_at = models.DateTimeField(
        'Criado em',
        auto_now_add=True
    )
    
    updated_at = models.DateTimeField(
        'Atualizado em',
        auto_now=True
    )
    
    notes = models.TextField(
        'Observações',
        blank=True,
        help_text='Notas internas sobre o parceiro'
    )
    
    class Meta:
        verbose_name = 'Parceiro'
        verbose_name_plural = 'Parceiros'
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active', 'name']),
            models.Index(fields=['nif']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.nif})"
    
    def clean(self):
        """Validações customizadas"""
        super().clean()
        
        # Normalizar NIF (remover espaços, uppercase PT)
        if self.nif:
            self.nif = self.nif.strip().upper()
            if not self.nif.startswith('PT') and len(self.nif) == 9:
                self.nif = f"PT{self.nif}"
        
        # Validar email
        if self.contact_email and not '@' in self.contact_email:
            raise ValidationError({'contact_email': 'Email inválido'})
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def active_orders_count(self):
        """Conta pedidos ativos deste parceiro"""
        return self.orders.exclude(current_status='DELIVERED').count()
    
    @property
    def has_active_integration(self):
        """Verifica se tem integração API ativa"""
        return self.integrations.filter(is_active=True).exists()


class PartnerIntegration(models.Model):
    """
    Configurações de integração API com cada parceiro.
    Um parceiro pode ter múltiplas integrações (API, SFTP, Email, etc.)
    """
    
    INTEGRATION_TYPES = [
        ('API', 'API REST/JSON'),
        ('SFTP', 'SFTP (CSV/XML)'),
        ('EMAIL', 'Email (anexos)'),
        ('WEBHOOK', 'Webhook'),
        ('MANUAL', 'Manual'),
    ]
    
    partner = models.ForeignKey(
        Partner,
        on_delete=models.CASCADE,
        related_name='integrations',
        verbose_name='Parceiro'
    )
    
    integration_type = models.CharField(
        'Tipo de Integração',
        max_length=20,
        choices=INTEGRATION_TYPES,
        default='API'
    )
    
    endpoint_url = models.URLField(
        'URL do Endpoint',
        max_length=500,
        blank=True,
        help_text='URL base da API do parceiro'
    )
    
    auth_config = models.JSONField(
        'Configuração de Autenticação',
        default=dict,
        blank=True,
        help_text='Configuração de autenticação (type: bearer/basic/oauth, tokens, etc.)'
    )
    
    # Configurações de Sincronização
    sync_frequency_minutes = models.IntegerField(
        'Frequência de Sincronização (minutos)',
        default=15,
        help_text='Intervalo entre importações automáticas de pedidos'
    )
    
    last_sync_at = models.DateTimeField(
        'Última Sincronização',
        null=True,
        blank=True
    )
    
    last_sync_status = models.CharField(
        'Status da Última Sincronização',
        max_length=20,
        blank=True,
        choices=[
            ('SUCCESS', 'Sucesso'),
            ('ERROR', 'Erro'),
            ('PARTIAL', 'Parcial'),
        ]
    )
    
    last_sync_message = models.TextField(
        'Mensagem da Última Sincronização',
        blank=True
    )
    
    # Status
    is_active = models.BooleanField(
        'Ativo',
        default=True,
        help_text='Se desativado, não fará sincronizações automáticas'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Integração de Parceiro'
        verbose_name_plural = 'Integrações de Parceiros'
        ordering = ['partner__name', '-is_active']
        indexes = [
            models.Index(fields=['partner', 'is_active']),
            models.Index(fields=['last_sync_at']),
        ]
    
    def __str__(self):
        return f"{self.partner.name} - {self.get_integration_type_display()}"
    
    def mark_sync_success(self, message=''):
        """Marca sincronização como bem-sucedida"""
        self.last_sync_at = timezone.now()
        self.last_sync_status = 'SUCCESS'
        self.last_sync_message = message
        self.save()
    
    def mark_sync_error(self, error_message):
        """Marca sincronização como erro"""
        self.last_sync_at = timezone.now()
        self.last_sync_status = 'ERROR'
        self.last_sync_message = error_message
        self.save()
    
    @property
    def is_sync_overdue(self):
        """Verifica se sincronização está atrasada"""
        if not self.last_sync_at:
            return True
        
        from datetime import timedelta
        threshold = timezone.now() - timedelta(minutes=self.sync_frequency_minutes * 2)
        return self.last_sync_at < threshold
