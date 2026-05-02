from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from core.models import Partner


class Order(models.Model):
    """
    Representa um pedido de entrega de qualquer parceiro.
    Este é o modelo central que substitui PaackOrder.
    """

    # Status possíveis do pedido
    STATUS_CHOICES = [
        ("PENDING", "Pendente"),
        ("ASSIGNED", "Atribuído a Motorista"),
        ("IN_TRANSIT", "Em Trânsito"),
        ("DELIVERED", "Entregue"),
        ("RETURNED", "Devolvido"),
        ("INCIDENT", "Incidente"),
        ("CANCELLED", "Cancelado"),
    ]

    # Relação com Parceiro (chave principal da arquitetura multi-partner)
    partner = models.ForeignKey(
        Partner,
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name="Parceiro",
        help_text="Parceiro logístico de origem do pedido",
    )

    # Identificação
    external_reference = models.CharField(
        "Referência Externa",
        max_length=200,
        db_index=True,
        help_text="Tracking code ou ID externo do parceiro",
    )

    # Destinatário
    recipient_name = models.CharField("Nome do Destinatário", max_length=200)

    recipient_address = models.TextField("Morada de Entrega")

    postal_code_validator = RegexValidator(
        regex=r"^\d{4}-\d{3}$",
        message="Código postal deve estar no formato XXXX-XXX",
    )
    postal_code = models.CharField(
        "Código Postal",
        max_length=8,
        validators=[postal_code_validator],
        db_index=True,
        help_text="Formato: XXXX-XXX",
    )

    recipient_phone = models.CharField(
        "Telefone do Destinatário", max_length=20, blank=True
    )

    recipient_email = models.EmailField("Email do Destinatário", blank=True)

    # Detalhes do Pedido
    declared_value = models.DecimalField(
        "Valor Declarado",
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Valor declarado do conteúdo em €",
    )

    weight_kg = models.DecimalField(
        "Peso (kg)", max_digits=6, decimal_places=2, null=True, blank=True
    )

    dimensions = models.JSONField(
        "Dimensões",
        default=dict,
        blank=True,
        help_text="Dimensões da encomenda (length, width, height em cm)",
    )

    # Agendamento
    scheduled_delivery = models.DateField(
        "Data de Entrega Agendada", null=True, blank=True, db_index=True
    )

    delivery_window_start = models.TimeField(
        "Início da Janela de Entrega", null=True, blank=True
    )

    delivery_window_end = models.TimeField(
        "Fim da Janela de Entrega", null=True, blank=True
    )

    # Atribuição
    assigned_driver = models.ForeignKey(
        "drivers_app.DriverProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_orders",
        verbose_name="Motorista Atribuído",
    )

    assigned_at = models.DateTimeField("Atribuído em", null=True, blank=True)

    # Status Atual
    current_status = models.CharField(
        "Status Atual",
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
        db_index=True,
    )

    # Entrega
    delivered_at = models.DateTimeField("Entregue em", null=True, blank=True)

    delivery_proof = models.JSONField(
        "Prova de Entrega",
        default=dict,
        blank=True,
        help_text="Assinatura, foto, código de confirmação, etc.",
    )

    # Observações
    notes = models.TextField("Observações", blank=True)

    special_instructions = models.TextField(
        "Instruções Especiais",
        blank=True,
        help_text="Instruções específicas do destinatário (código porta, andar, etc.)",
    )

    # Metadados
    created_at = models.DateTimeField("Criado em", auto_now_add=True, db_index=True)

    updated_at = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["partner", "current_status"]),
            models.Index(fields=["assigned_driver", "current_status"]),
            models.Index(fields=["scheduled_delivery", "current_status"]),
            models.Index(fields=["postal_code", "current_status"]),
            models.Index(fields=["external_reference", "partner"]),
        ]
        # Garantir unicidade de tracking code por parceiro
        unique_together = [["partner", "external_reference"]]

    def __str__(self):
        return f"{self.partner.name} - {self.external_reference}"

    def clean(self):
        """Validações customizadas"""
        super().clean()

        # Validar janela de entrega
        if self.delivery_window_start and self.delivery_window_end:
            if self.delivery_window_start >= self.delivery_window_end:
                raise ValidationError(
                    {"delivery_window_end": "Fim da janela deve ser após o início"}
                )

        # Validar data de entrega
        if self.scheduled_delivery:
            if self.scheduled_delivery < timezone.now().date():
                raise ValidationError(
                    {"scheduled_delivery": "Data de entrega não pode ser no passado"}
                )

    def save(self, *args, **kwargs):
        # Normalizar código postal
        if self.postal_code:
            self.postal_code = self.postal_code.strip()

        # Auto-atribuir data de atribuição
        if self.assigned_driver and not self.assigned_at:
            self.assigned_at = timezone.now()
            if self.current_status == "PENDING":
                self.current_status = "ASSIGNED"

        # Auto-atribuir data de entrega
        if self.current_status == "DELIVERED" and not self.delivered_at:
            self.delivered_at = timezone.now()

        super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        """Verifica se entrega está atrasada"""
        if not self.scheduled_delivery:
            return False

        if self.current_status in ["DELIVERED", "RETURNED", "CANCELLED"]:
            return False

        return self.scheduled_delivery < timezone.now().date()

    @property
    def days_since_creation(self):
        """Dias desde criação do pedido"""
        delta = timezone.now() - self.created_at
        return delta.days

    def assign_to_driver(self, driver):
        """Atribui pedido a um motorista"""
        self.assigned_driver = driver
        self.assigned_at = timezone.now()
        self.current_status = "ASSIGNED"
        self.save()

        # Criar registro de mudança de status
        OrderStatusHistory.objects.create(
            order=self,
            status="ASSIGNED",
            notes=f"Atribuído a {driver.user.get_full_name()}",
        )

    def mark_as_delivered(self, proof=None):
        """Marca pedido como entregue"""
        self.current_status = "DELIVERED"
        self.delivered_at = timezone.now()
        if proof:
            self.delivery_proof = proof
        self.save()

        # Criar registro de mudança de status
        OrderStatusHistory.objects.create(
            order=self, status="DELIVERED", notes="Pedido entregue com sucesso"
        )


class OrderStatusHistory(models.Model):
    """
    Histórico de mudanças de status de um pedido.
    Mantém auditoria completa de todas as transições.
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="status_history",
        verbose_name="Pedido",
    )

    status = models.CharField("Status", max_length=20, choices=Order.STATUS_CHOICES)

    notes = models.TextField("Observações", blank=True)

    location = models.CharField(
        "Localização",
        max_length=200,
        blank=True,
        help_text="GPS ou descrição da localização quando mudança ocorreu",
    )

    changed_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_status_changes",
        verbose_name="Alterado por",
    )

    changed_at = models.DateTimeField(
        "Data/Hora da Mudança", auto_now_add=True, db_index=True
    )

    class Meta:
        verbose_name = "Histórico de Status"
        verbose_name_plural = "Históricos de Status"
        ordering = ["-changed_at"]
        indexes = [
            models.Index(fields=["order", "-changed_at"]),
        ]

    def __str__(self):
        return f"{self.order} - {self.get_status_display()} em {self.changed_at}"


class OrderIncident(models.Model):
    """
    Incidentes relacionados a pedidos (avarias, extravios, devoluções, etc.)
    """

    INCIDENT_TYPES = [
        ("DAMAGED", "Encomenda Danificada"),
        ("LOST", "Encomenda Extraviada"),
        ("WRONG_ADDRESS", "Morada Errada"),
        ("RECIPIENT_ABSENT", "Destinatário Ausente"),
        ("REFUSED", "Recusado pelo Destinatário"),
        ("DELAYED", "Atraso na Entrega"),
        ("OTHER", "Outro"),
    ]

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="incidents",
        verbose_name="Pedido",
    )

    incident_type = models.CharField(
        "Tipo de Incidente", max_length=20, choices=INCIDENT_TYPES
    )

    description = models.TextField("Descrição do Incidente")

    driver_responsible = models.BooleanField(
        "Motorista Responsável",
        default=False,
        help_text="Se marcado, incidente foi causado por erro do motorista",
    )

    claim_amount = models.DecimalField(
        "Valor da Reclamação",
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Valor a ser deduzido do settlement do motorista (se responsável)",
    )

    photos = models.JSONField(
        "Fotos",
        default=list,
        blank=True,
        help_text="URLs de fotos do incidente",
    )

    resolved = models.BooleanField("Resolvido", default=False)

    resolution_notes = models.TextField("Notas de Resolução", blank=True)

    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_incidents",
        verbose_name="Criado por",
    )

    created_at = models.DateTimeField("Criado em", auto_now_add=True)

    resolved_at = models.DateTimeField("Resolvido em", null=True, blank=True)

    class Meta:
        verbose_name = "Incidente de Pedido"
        verbose_name_plural = "Incidentes de Pedidos"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["order", "-created_at"]),
            models.Index(fields=["resolved", "-created_at"]),
        ]

    def __str__(self):
        status = "✓ Resolvido" if self.resolved else "⚠ Pendente"
        return f"{self.order} - {self.get_incident_type_display()} ({status})"

    def mark_as_resolved(self, resolution_notes):
        """Marca incidente como resolvido"""
        self.resolved = True
        self.resolved_at = timezone.now()
        self.resolution_notes = resolution_notes
        self.save()


class GeocodedAddress(models.Model):
    """
    Cache de endereços geocodificados para evitar requests repetidos
    """
    
    # Endereço original
    address = models.TextField("Endereço Original")
    postal_code = models.CharField("Código Postal", max_length=10)
    locality = models.CharField("Localidade", max_length=200)
    
    # Endereço normalizado (usado para busca)
    normalized_address = models.TextField("Endereço Normalizado", db_index=True)
    
    # Coordenadas geocodificadas
    latitude = models.DecimalField(
        "Latitude", 
        max_digits=9, 
        decimal_places=6,
        null=True,
        blank=True
    )
    longitude = models.DecimalField(
        "Longitude", 
        max_digits=9, 
        decimal_places=6,
        null=True,
        blank=True
    )
    
    # Qualidade da geocodificação
    geocode_quality = models.CharField(
        "Qualidade",
        max_length=20,
        choices=[
            ('EXACT', 'Endereço Exato'),
            ('STREET', 'Rua'),
            ('POSTAL_CODE', 'Código Postal'),
            ('LOCALITY', 'Localidade'),
            ('MANUAL', 'Manual'),
            ('FAILED', 'Falhou'),
        ],
        default='FAILED'
    )
    
    # Metadata
    geocoded_at = models.DateTimeField("Geocodificado em", auto_now_add=True)
    geocode_source = models.CharField("Fonte", max_length=50, default="Nominatim")
    
    class Meta:
        verbose_name = "Endereço Geocodificado"
        verbose_name_plural = "Endereços Geocodificados"
        indexes = [
            models.Index(fields=['normalized_address']),
            models.Index(fields=['postal_code', 'locality']),
        ]
        unique_together = ['normalized_address']
    
    def __str__(self):
        return f"{self.normalized_address} → ({self.latitude}, {self.longitude})"


class GeocodingFailure(models.Model):
    """Registra endereços que falharam na geocodificação para revisão manual"""
    
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='geocoding_failures',
        verbose_name="Pedido"
    )
    
    # Dados do endereço original
    original_address = models.TextField("Endereço Original")
    normalized_address = models.TextField("Endereço Normalizado")
    postal_code = models.CharField("Código Postal", max_length=20)
    locality = models.CharField("Localidade", max_length=100, blank=True)
    
    # Informações da falha
    failure_reason = models.TextField("Motivo da Falha", blank=True)
    attempted_at = models.DateTimeField("Tentativa em", auto_now_add=True)
    retry_count = models.IntegerField("Tentativas", default=1)
    last_retry_at = models.DateTimeField("Última Tentativa", auto_now=True)
    
    # Status
    resolved = models.BooleanField("Resolvido", default=False)
    resolved_at = models.DateTimeField("Resolvido em", null=True, blank=True)
    resolved_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Resolvido por"
    )
    
    # Coordenadas manuais (se resolvido manualmente)
    manual_latitude = models.DecimalField(
        "Latitude Manual",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    manual_longitude = models.DecimalField(
        "Longitude Manual",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = "Falha de Geocodificação"
        verbose_name_plural = "Falhas de Geocodificação"
        ordering = ['-attempted_at']
        indexes = [
            models.Index(fields=['resolved', 'attempted_at']),
            models.Index(fields=['postal_code']),
        ]
    
    def __str__(self):
        status = "✓ Resolvido" if self.resolved else f"✗ Falhou ({self.retry_count}x)"
        return f"{status} - {self.order.external_reference}"
    
    def mark_resolved(self, lat, lng, user=None):
        """Marca a falha como resolvida com coordenadas manuais"""
        from django.utils import timezone
        self.resolved = True
        self.resolved_at = timezone.now()
        self.resolved_by = user
        self.manual_latitude = lat
        self.manual_longitude = lng
        self.save()
        
        # Criar entrada de geocodificação
        GeocodedAddress.objects.update_or_create(
            normalized_address=self.normalized_address,
            defaults={
                'address': self.original_address,
                'postal_code': self.postal_code,
                'locality': self.locality,
                'latitude': lat,
                'longitude': lng,
                'geocode_quality': 'MANUAL',
                'geocode_source': 'Manual'
            }
        )
