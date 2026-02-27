from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import datetime, timedelta
from ordersmanager_paack.models import Driver  # ajuste se necessário (legacy)

class SettlementRun(models.Model):
    driver          = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name="settlement_runs")
    run_date        = models.DateField(db_index=True)
    client          = models.CharField(max_length=80, db_index=True)      # "Paack", "Delnext"
    area_code       = models.CharField(max_length=20, blank=True, null=True, db_index=True)  # "A","B","A-B"

    qtd_saida       = models.PositiveIntegerField()
    qtd_pact        = models.PositiveIntegerField()
    qtd_entregue    = models.PositiveIntegerField()

    vl_pct          = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    total_pct       = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gasoleo         = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    desconto_tickets= models.DecimalField(max_digits=12, decimal_places=2, default=0)
    rec_liq_tickets = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    outros          = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vl_final        = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    notes           = models.TextField(blank=True, null=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("driver", "run_date", "client", "area_code")
        indexes = [
            models.Index(fields=["run_date", "client"]),
            models.Index(fields=["driver", "run_date"]),
        ]
        ordering = ["-run_date", "driver__name"]

    def clean(self):
        if not (self.qtd_entregue <= self.qtd_pact <= self.qtd_saida):
            from django.core.exceptions import ValidationError
            raise ValidationError(_("Regra inválida: entregue ≤ qtd_pact ≤ qtd_saida"))

    def compute_totals(self):
        self.total_pct = Decimal(self.vl_pct) * Decimal(self.qtd_entregue or 0)
        descontos = Decimal(self.gasoleo or 0) + Decimal(self.desconto_tickets or 0) + Decimal(self.rec_liq_tickets or 0) + Decimal(self.outros or 0)
        self.vl_final  = self.total_pct - descontos

    def save(self, *args, **kwargs):
        self.compute_totals()
        super().save(*args, **kwargs)


class CompensationPlan(models.Model):
    driver      = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name="comp_plans")
    client      = models.CharField(max_length=80, blank=True, null=True, db_index=True)
    area_code   = models.CharField(max_length=20, blank=True, null=True, db_index=True)
    starts_on   = models.DateField()
    ends_on     = models.DateField(blank=True, null=True)
    base_fixed  = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # €/mês
    is_active   = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=["driver","client","area_code","starts_on","ends_on"])]

    def __str__(self):
        scope = f"{self.client or '*'} / {self.area_code or '*'}"
        return f"{self.driver.name} [{scope}] {self.starts_on}→{self.ends_on or '…'}"


class PerPackageRate(models.Model):
    plan          = models.ForeignKey(CompensationPlan, on_delete=models.CASCADE, related_name="pkg_rates")
    min_delivered = models.PositiveIntegerField(default=0)
    max_delivered = models.PositiveIntegerField(blank=True, null=True)
    rate_eur      = models.DecimalField(max_digits=10, decimal_places=2)  # ex.: 0.40
    priority      = models.PositiveSmallIntegerField(default=1)
    progressive   = models.BooleanField(default=False, help_text="Se marcado, calcula progressivo por faixas")

    class Meta:
        ordering = ["priority","min_delivered"]

    def __str__(self):
        upto = f"–{self.max_delivered}" if self.max_delivered is not None else "+"
        mode = "progressivo" if self.progressive else "faixa"
        return f"{self.min_delivered}{upto} @ €{self.rate_eur} ({mode})"


class ThresholdBonus(models.Model):
    class Kind(models.TextChoices):
        ONCE = "ONCE", "Uma vez"
        EACH_STEP = "EACH_STEP", "A cada passo"

    plan          = models.ForeignKey(CompensationPlan, on_delete=models.CASCADE, related_name="thresholds")
    kind          = models.CharField(max_length=16, choices=Kind.choices, default=Kind.EACH_STEP)
    start_at      = models.PositiveIntegerField()
    step          = models.PositiveIntegerField(default=0, help_text="Usado em EACH_STEP (ex.: 100)")
    amount_eur    = models.DecimalField(max_digits=10, decimal_places=2)  # ex.: 18.00

    def __str__(self):
        return f"{self.kind} from {self.start_at} step {self.step} = €{self.amount_eur}"


# ============================================================================
# 🆕 MULTI-PARTNER FINANCIAL MODELS (Fase 6 - Roadmap)
# ============================================================================

class PartnerInvoice(models.Model):
    """
    Faturas a receber dos Partners (Paack, Amazon, DPD, etc.)
    Base para reconciliação financeira.
    """
    
    STATUS_CHOICES = [
        ('DRAFT', 'Rascunho'),
        ('PENDING', 'Pendente'),
        ('PAID', 'Pago'),
        ('OVERDUE', 'Atrasado'),
        ('CANCELLED', 'Cancelado'),
    ]
    
    # Relacionamentos
    partner = models.ForeignKey(
        'core.Partner',
        on_delete=models.PROTECT,
        related_name='invoices',
        verbose_name='Parceiro'
    )
    
    # Identificação
    invoice_number = models.CharField(
        'Número da Fatura',
        max_length=100,
        unique=True,
        help_text='Número único da fatura (ex: PAACK-2026-001)'
    )
    
    external_reference = models.CharField(
        'Referência Externa',
        max_length=200,
        blank=True,
        help_text='Referência do sistema do partner'
    )
    
    # Período
    period_start = models.DateField(
        'Início do Período',
        db_index=True
    )
    
    period_end = models.DateField(
        'Fim do Período',
        db_index=True
    )
    
    # Valores
    gross_amount = models.DecimalField(
        'Valor Bruto',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)]
    )
    
    tax_amount = models.DecimalField(
        'IVA',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)]
    )
    
    net_amount = models.DecimalField(
        'Valor Líquido',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)]
    )
    
    # Status e Pagamento
    status = models.CharField(
        'Status',
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        db_index=True
    )
    
    issue_date = models.DateField(
        'Data de Emissão',
        default=timezone.now
    )
    
    due_date = models.DateField(
        'Data de Vencimento',
        db_index=True
    )
    
    paid_date = models.DateField(
        'Data de Pagamento',
        null=True,
        blank=True
    )
    
    paid_amount = models.DecimalField(
        'Valor Pago',
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    
    # Metadata
    total_orders = models.PositiveIntegerField(
        'Total de Pedidos',
        default=0,
        help_text='Quantidade de pedidos incluídos'
    )
    
    total_delivered = models.PositiveIntegerField(
        'Pedidos Entregues',
        default=0
    )
    
    notes = models.TextField(
        'Notas',
        blank=True
    )
    
    # Auditoria
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_invoices'
    )
    
    class Meta:
        verbose_name = 'Fatura de Parceiro'
        verbose_name_plural = 'Faturas de Parceiros'
        ordering = ['-period_end', '-created_at']
        indexes = [
            models.Index(fields=['partner', 'period_start', 'period_end']),
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.invoice_number} - {self.partner.name} ({self.period_start} → {self.period_end})"
    
    def calculate_totals(self):
        """Calcula valores baseado em pedidos do período"""
        from orders_manager.models import Order
        
        orders = Order.objects.filter(
            partner=self.partner,
            current_status='DELIVERED',
            created_at__date__gte=self.period_start,
            created_at__date__lte=self.period_end
        )
        
        self.total_orders = orders.count()
        self.total_delivered = orders.filter(current_status='DELIVERED').count()
        
        # Calcular valor bruto baseado em tarifas
        from pricing.models import PartnerTariff
        gross = Decimal('0.00')
        
        for order in orders:
            # Buscar tarifa aplicável
            try:
                tariff = PartnerTariff.objects.get(
                    partner=self.partner,
                    postal_zone__code=order.postal_code[:4],  # Primeiros 4 dígitos
                    valid_from__lte=order.created_at.date(),
                    valid_until__gte=order.created_at.date()
                )
                
                if order.current_status == 'DELIVERED':
                    gross += tariff.base_price + tariff.success_bonus
                else:
                    gross += tariff.base_price - tariff.failure_penalty
                    
            except PartnerTariff.DoesNotExist:
                # Fallback para preço base
                gross += Decimal('5.00')
        
        self.gross_amount = gross
        self.tax_amount = gross * Decimal('0.23')  # IVA 23%
        self.net_amount = gross + self.tax_amount
    
    def mark_as_paid(self, paid_amount=None, paid_date=None):
        """Marca fatura como paga"""
        self.status = 'PAID'
        self.paid_date = paid_date or timezone.now().date()
        self.paid_amount = paid_amount or self.net_amount
        self.save()
    
    def check_overdue(self):
        """Verifica se fatura está atrasada"""
        if self.status in ['PENDING'] and self.due_date < timezone.now().date():
            self.status = 'OVERDUE'
            self.save()


class DriverSettlement(models.Model):
    """
    Acerto financeiro semanal/mensal com motoristas.
    Evolução do SettlementRun para multi-partner.
    """
    
    STATUS_CHOICES = [
        ('DRAFT', 'Rascunho'),
        ('CALCULATED', 'Calculado'),
        ('APPROVED', 'Aprovado'),
        ('PAID', 'Pago'),
        ('DISPUTED', 'Em Disputa'),
    ]
    
    # Relacionamentos
    driver = models.ForeignKey(
        'drivers_app.DriverProfile',
        on_delete=models.PROTECT,
        related_name='settlements',
        verbose_name='Motorista'
    )
    
    partner = models.ForeignKey(
        'core.Partner',
        on_delete=models.PROTECT,
        related_name='driver_settlements',
        verbose_name='Parceiro',
        null=True,
        blank=True,
        help_text='Se null, é um settlement consolidado multi-partner'
    )
    
    # Período
    period_type = models.CharField(
        'Tipo de Período',
        max_length=20,
        choices=[
            ('WEEKLY', 'Semanal'),
            ('MONTHLY', 'Mensal'),
        ],
        default='WEEKLY'
    )
    
    week_number = models.PositiveIntegerField(
        'Número da Semana',
        null=True,
        blank=True,
        help_text='Semana do ano (1-52)'
    )
    
    month_number = models.PositiveIntegerField(
        'Mês',
        null=True,
        blank=True,
        help_text='Mês do ano (1-12)'
    )
    
    year = models.PositiveIntegerField(
        'Ano',
        db_index=True
    )
    
    period_start = models.DateField(
        'Início do Período',
        db_index=True
    )
    
    period_end = models.DateField(
        'Fim do Período',
        db_index=True
    )
    
    # Estatísticas de Entregas
    total_orders = models.PositiveIntegerField(
        'Total de Pedidos',
        default=0
    )
    
    delivered_orders = models.PositiveIntegerField(
        'Pedidos Entregues',
        default=0
    )
    
    failed_orders = models.PositiveIntegerField(
        'Pedidos Falhados',
        default=0
    )
    
    success_rate = models.DecimalField(
        'Taxa de Sucesso',
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)],
        help_text='Percentual de entregas com sucesso'
    )
    
    # Valores Financeiros
    gross_amount = models.DecimalField(
        'Valor Bruto',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)],
        help_text='Total antes de descontos'
    )
    
    bonus_amount = models.DecimalField(
        'Bônus',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)],
        help_text='Bônus por performance'
    )
    
    fuel_deduction = models.DecimalField(
        'Desconto Combustível',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)]
    )
    
    claims_deducted = models.DecimalField(
        'Descontos (Claims)',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)],
        help_text='Multas, perdas, danos'
    )
    
    other_deductions = models.DecimalField(
        'Outros Descontos',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)]
    )
    
    net_amount = models.DecimalField(
        'Valor Líquido',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Valor final a pagar'
    )
    
    # Status e Pagamento
    status = models.CharField(
        'Status',
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        db_index=True
    )
    
    calculated_at = models.DateTimeField(
        'Calculado em',
        null=True,
        blank=True
    )
    
    approved_at = models.DateTimeField(
        'Aprovado em',
        null=True,
        blank=True
    )
    
    approved_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_settlements'
    )
    
    paid_at = models.DateTimeField(
        'Pago em',
        null=True,
        blank=True
    )
    
    payment_reference = models.CharField(
        'Referência de Pagamento',
        max_length=200,
        blank=True,
        help_text='MB WAY, Transferência, etc.'
    )
    
    # Metadata
    notes = models.TextField(
        'Notas',
        blank=True
    )
    
    pdf_file = models.FileField(
        'PDF do Extrato',
        upload_to='settlements/pdfs/%Y/%m/',
        null=True,
        blank=True
    )
    
    whatsapp_sent = models.BooleanField(
        'WhatsApp Enviado',
        default=False
    )
    
    whatsapp_sent_at = models.DateTimeField(
        'WhatsApp Enviado em',
        null=True,
        blank=True
    )
    
    # Auditoria
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_settlements'
    )
    
    class Meta:
        verbose_name = 'Acerto de Motorista'
        verbose_name_plural = 'Acertos de Motoristas'
        ordering = ['-year', '-week_number', '-month_number', 'driver__nome_completo']
        unique_together = [
            ('driver', 'partner', 'year', 'week_number'),  # Para settlements semanais
            ('driver', 'partner', 'year', 'month_number'),  # Para settlements mensais
        ]
        indexes = [
            models.Index(fields=['driver', 'period_start', 'period_end']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['year', 'week_number']),
        ]
    
    def __str__(self):
        partner_name = self.partner.name if self.partner else 'Multi-Partner'
        if self.period_type == 'WEEKLY':
            return f"{self.driver.nome_completo} - {partner_name} - Semana {self.week_number}/{self.year}"
        return f"{self.driver.nome_completo} - {partner_name} - {self.month_number}/{self.year}"
    
    def calculate_settlement(self):
        """Calcula valores do settlement baseado em pedidos e tarifas"""
        from orders_manager.models import Order
        from pricing.models import PartnerTariff
        
        # Buscar pedidos do motorista no período
        orders_query = Order.objects.filter(
            assigned_driver=self.driver,
            created_at__date__gte=self.period_start,
            created_at__date__lte=self.period_end
        )
        
        if self.partner:
            orders_query = orders_query.filter(partner=self.partner)
        
        orders = orders_query.select_related('partner')
        
        # Estatísticas
        self.total_orders = orders.count()
        self.delivered_orders = orders.filter(current_status='DELIVERED').count()
        self.failed_orders = self.total_orders - self.delivered_orders
        
        if self.total_orders > 0:
            self.success_rate = (Decimal(self.delivered_orders) / Decimal(self.total_orders)) * Decimal('100.00')
        
        # Calcular valor bruto
        gross = Decimal('0.00')
        
        for order in orders:
            try:
                # Buscar tarifa aplicável
                tariff = PartnerTariff.objects.get(
                    partner=order.partner,
                    postal_zone__code=order.postal_code[:4],
                    valid_from__lte=order.created_at.date(),
                    valid_until__gte=order.created_at.date()
                )
                
                if order.current_status == 'DELIVERED':
                    gross += tariff.base_price + tariff.success_bonus
                else:
                    gross += tariff.base_price - tariff.failure_penalty
                    
            except PartnerTariff.DoesNotExist:
                # Fallback
                gross += Decimal('5.00') if order.current_status == 'DELIVERED' else Decimal('2.00')
        
        self.gross_amount = gross
        
        # Calcular bônus por performance
        if self.success_rate >= Decimal('95.00'):
            self.bonus_amount = gross * Decimal('0.10')  # 10% de bônus
        elif self.success_rate >= Decimal('90.00'):
            self.bonus_amount = gross * Decimal('0.05')  # 5% de bônus
        
        # Buscar claims pendentes
        pending_claims = self.claims.filter(status='APPROVED')
        self.claims_deducted = sum(claim.amount for claim in pending_claims)
        
        # Calcular valor líquido
        total_deductions = (
            self.fuel_deduction +
            self.claims_deducted +
            self.other_deductions
        )
        
        self.net_amount = self.gross_amount + self.bonus_amount - total_deductions
        
        # Atualizar status e timestamp
        self.status = 'CALCULATED'
        self.calculated_at = timezone.now()
        self.save()
    
    def approve(self, user):
        """Aprova o settlement"""
        if self.status != 'CALCULATED':
            raise ValueError("Settlement deve estar no status CALCULATED")
        
        self.status = 'APPROVED'
        self.approved_at = timezone.now()
        self.approved_by = user
        self.save()
    
    def mark_as_paid(self, payment_reference=''):
        """Marca como pago"""
        if self.status != 'APPROVED':
            raise ValueError("Settlement deve estar APPROVED")
        
        self.status = 'PAID'
        self.paid_at = timezone.now()
        self.payment_reference = payment_reference
        self.save()


class DriverClaim(models.Model):
    """
    Descontos aplicados a motoristas (multas, perdas, danos, etc.)
    Reduz o valor do settlement.
    """
    
    CLAIM_TYPES = [
        ('ORDER_LOSS', 'Perda de Pedido'),
        ('ORDER_DAMAGE', 'Dano em Pedido'),
        ('VEHICLE_FINE', 'Multa de Veículo'),
        ('VEHICLE_DAMAGE', 'Dano em Veículo'),
        ('FUEL_EXCESS', 'Excesso de Combustível'),
        ('MISSING_POD', 'Falta de Comprovante'),
        ('LATE_DELIVERY', 'Entrega Atrasada'),
        ('CUSTOMER_COMPLAINT', 'Reclamação de Cliente'),
        ('OTHER', 'Outro'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pendente'),
        ('APPROVED', 'Aprovado'),
        ('REJECTED', 'Rejeitado'),
        ('APPEALED', 'Em Recurso'),
    ]
    
    # Relacionamentos
    driver = models.ForeignKey(
        'drivers_app.DriverProfile',
        on_delete=models.PROTECT,
        related_name='claims',
        verbose_name='Motorista'
    )
    
    settlement = models.ForeignKey(
        DriverSettlement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='claims',
        verbose_name='Acerto',
        help_text='Settlement onde o desconto foi aplicado'
    )
    
    # Referências
    order = models.ForeignKey(
        'orders_manager.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='claims',
        verbose_name='Pedido Relacionado'
    )
    
    vehicle_incident = models.ForeignKey(
        'fleet_management.VehicleIncident',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='claims',
        verbose_name='Incidente de Veículo'
    )
    
    # Detalhes do Claim
    claim_type = models.CharField(
        'Tipo de Desconto',
        max_length=30,
        choices=CLAIM_TYPES,
        db_index=True
    )
    
    amount = models.DecimalField(
        'Valor',
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    
    description = models.TextField(
        'Descrição',
        help_text='Detalhes do motivo do desconto'
    )
    
    evidence_file = models.FileField(
        'Evidência',
        upload_to='claims/evidence/%Y/%m/',
        null=True,
        blank=True,
        help_text='Foto, documento, etc.'
    )
    
    justification = models.TextField(
        'Justificativa',
        blank=True,
        help_text='Justificativa ou recurso do motorista'
    )
    
    # Status e Aprovação
    status = models.CharField(
        'Status',
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True
    )
    
    occurred_at = models.DateTimeField(
        'Ocorrido em',
        default=timezone.now,
        db_index=True
    )
    
    reviewed_at = models.DateTimeField(
        'Revisado em',
        null=True,
        blank=True
    )
    
    reviewed_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_claims',
        verbose_name='Revisado por'
    )
    
    review_notes = models.TextField(
        'Notas da Revisão',
        blank=True
    )
    
    # Auditoria
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_claims'
    )
    
    class Meta:
        verbose_name = 'Desconto de Motorista'
        verbose_name_plural = 'Descontos de Motoristas'
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['driver', 'status', '-occurred_at']),
            models.Index(fields=['claim_type', 'status']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_claim_type_display()} - {self.driver.nome_completo} - €{self.amount}"
    
    def approve(self, user, notes=''):
        """Aprova o claim"""
        self.status = 'APPROVED'
        self.reviewed_at = timezone.now()
        self.reviewed_by = user
        self.review_notes = notes
        self.save()
    
    def reject(self, user, notes=''):
        """Rejeita o claim"""
        self.status = 'REJECTED'
        self.reviewed_at = timezone.now()
        self.reviewed_by = user
        self.review_notes = notes
        self.save()
    
    def appeal(self, justification):
        """Motorista recorre do claim"""
        self.status = 'APPEALED'
        self.justification = justification
        self.save()
