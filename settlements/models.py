from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from ordersmanager_paack.models import Driver  # ajuste se necessário (legacy)


class SettlementRun(models.Model):
    driver = models.ForeignKey(
        Driver, on_delete=models.PROTECT, related_name="settlement_runs"
    )
    run_date = models.DateField(db_index=True)
    client = models.CharField(max_length=80, db_index=True)  # "Paack", "Delnext"
    area_code = models.CharField(
        max_length=20, blank=True, null=True, db_index=True
    )  # "A","B","A-B"

    qtd_saida = models.PositiveIntegerField()
    qtd_pact = models.PositiveIntegerField()
    qtd_entregue = models.PositiveIntegerField()

    vl_pct = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    total_pct = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gasoleo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    desconto_tickets = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    rec_liq_tickets = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    outros = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vl_final = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
        descontos = (
            Decimal(self.gasoleo or 0)
            + Decimal(self.desconto_tickets or 0)
            + Decimal(self.rec_liq_tickets or 0)
            + Decimal(self.outros or 0)
        )
        self.vl_final = self.total_pct - descontos

    def save(self, *args, **kwargs):
        self.compute_totals()
        super().save(*args, **kwargs)


class CompensationPlan(models.Model):
    driver = models.ForeignKey(
        Driver, on_delete=models.PROTECT, related_name="comp_plans"
    )
    client = models.CharField(max_length=80, blank=True, null=True, db_index=True)
    area_code = models.CharField(max_length=20, blank=True, null=True, db_index=True)
    starts_on = models.DateField()
    ends_on = models.DateField(blank=True, null=True)
    base_fixed = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )  # €/mês
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(
                fields=[
                    "driver",
                    "client",
                    "area_code",
                    "starts_on",
                    "ends_on",
                ]
            )
        ]

    def __str__(self):
        scope = f"{self.client or '*'} / {self.area_code or '*'}"
        return f"{self.driver.name} [{scope}] {self.starts_on}→{self.ends_on or '…'}"


class PerPackageRate(models.Model):
    plan = models.ForeignKey(
        CompensationPlan, on_delete=models.CASCADE, related_name="pkg_rates"
    )
    min_delivered = models.PositiveIntegerField(default=0)
    max_delivered = models.PositiveIntegerField(blank=True, null=True)
    rate_eur = models.DecimalField(max_digits=10, decimal_places=2)  # ex.: 0.40
    priority = models.PositiveSmallIntegerField(default=1)
    progressive = models.BooleanField(
        default=False, help_text="Se marcado, calcula progressivo por faixas"
    )

    class Meta:
        ordering = ["priority", "min_delivered"]

    def __str__(self):
        upto = f"–{self.max_delivered}" if self.max_delivered is not None else "+"
        mode = "progressivo" if self.progressive else "faixa"
        return f"{self.min_delivered}{upto} @ €{self.rate_eur} ({mode})"


class ThresholdBonus(models.Model):
    class Kind(models.TextChoices):
        ONCE = "ONCE", "Uma vez"
        EACH_STEP = "EACH_STEP", "A cada passo"

    plan = models.ForeignKey(
        CompensationPlan, on_delete=models.CASCADE, related_name="thresholds"
    )
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.EACH_STEP)
    start_at = models.PositiveIntegerField()
    step = models.PositiveIntegerField(
        default=0, help_text="Usado em EACH_STEP (ex.: 100)"
    )
    amount_eur = models.DecimalField(max_digits=10, decimal_places=2)  # ex.: 18.00

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
        ("DRAFT", "Rascunho"),
        ("PENDING", "Pendente"),
        ("PAID", "Pago"),
        ("OVERDUE", "Atrasado"),
        ("CANCELLED", "Cancelado"),
    ]

    # Relacionamentos
    partner = models.ForeignKey(
        "core.Partner",
        on_delete=models.PROTECT,
        related_name="invoices",
        verbose_name="Parceiro",
    )

    # Identificação
    invoice_number = models.CharField(
        "Número da Fatura",
        max_length=100,
        unique=True,
        help_text="Número único da fatura (ex: PAACK-2026-001)",
    )

    external_reference = models.CharField(
        "Referência Externa",
        max_length=200,
        blank=True,
        help_text="Referência do sistema do partner",
    )

    # Período
    period_start = models.DateField("Início do Período", db_index=True)

    period_end = models.DateField("Fim do Período", db_index=True)

    # Valores
    gross_amount = models.DecimalField(
        "Valor Bruto",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )

    tax_amount = models.DecimalField(
        "IVA",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )

    net_amount = models.DecimalField(
        "Valor Líquido",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )

    # Status e Pagamento
    status = models.CharField(
        "Status",
        max_length=20,
        choices=STATUS_CHOICES,
        default="DRAFT",
        db_index=True,
    )

    issue_date = models.DateField("Data de Emissão", default=timezone.now)

    due_date = models.DateField("Data de Vencimento", db_index=True)

    paid_date = models.DateField("Data de Pagamento", null=True, blank=True)

    paid_amount = models.DecimalField(
        "Valor Pago",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )

    payment_reference = models.CharField(
        "Referência de Pagamento", max_length=200, blank=True,
        help_text="MB WAY, IBAN, transferência, etc.",
    )

    payment_proof = models.FileField(
        "Comprovativo de Pagamento",
        upload_to="partner_invoices/comprovativos/%Y/%m/",
        null=True, blank=True,
    )

    # Metadata
    total_orders = models.PositiveIntegerField(
        "Total de Pedidos",
        default=0,
        help_text="Quantidade de pedidos incluídos",
    )

    total_delivered = models.PositiveIntegerField("Pedidos Entregues", default=0)

    notes = models.TextField("Notas", blank=True)

    # Auditoria
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_invoices",
    )

    class Meta:
        verbose_name = "Fatura de Parceiro"
        verbose_name_plural = "Faturas de Parceiros"
        ordering = ["-period_end", "-created_at"]
        indexes = [
            models.Index(fields=["partner", "period_start", "period_end"]),
            models.Index(fields=["status", "due_date"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"{self.invoice_number} - {self.partner.name} ({self.period_start} → {self.period_end})"

    def calculate_totals(self):
        """Calcula valores baseado em pedidos do período"""
        from orders_manager.models import Order

        orders = Order.objects.filter(
            partner=self.partner,
            current_status="DELIVERED",
            created_at__date__gte=self.period_start,
            created_at__date__lte=self.period_end,
        )

        self.total_orders = orders.count()
        self.total_delivered = orders.filter(current_status="DELIVERED").count()

        # Calcular valor bruto baseado em tarifas
        from pricing.models import PartnerTariff

        gross = Decimal("0.00")

        for order in orders:
            # Buscar tarifa aplicável
            try:
                tariff = PartnerTariff.objects.get(
                    partner=self.partner,
                    postal_zone__code=order.postal_code[:4],  # Primeiros 4 dígitos
                    valid_from__lte=order.created_at.date(),
                    valid_until__gte=order.created_at.date(),
                )

                if order.current_status == "DELIVERED":
                    gross += tariff.base_price + tariff.success_bonus
                else:
                    gross += tariff.base_price - tariff.failure_penalty

            except PartnerTariff.DoesNotExist:
                # Fallback para preço base
                gross += Decimal("5.00")

        self.gross_amount = gross
        self.tax_amount = gross * Decimal("0.23")  # IVA 23%
        self.net_amount = gross + self.tax_amount

    def mark_as_paid(self, paid_amount=None, paid_date=None):
        """Marca fatura como paga"""
        self.status = "PAID"
        self.paid_date = paid_date or timezone.now().date()
        self.paid_amount = paid_amount or self.net_amount
        self.save()

    def check_overdue(self):
        """Verifica se fatura está atrasada"""
        if self.status in ["PENDING"] and self.due_date < timezone.now().date():
            self.status = "OVERDUE"
            self.save()


class DriverSettlement(models.Model):
    """
    Acerto financeiro semanal/mensal com motoristas.
    Evolução do SettlementRun para multi-partner.
    """

    STATUS_CHOICES = [
        ("DRAFT", "Rascunho"),
        ("CALCULATED", "Calculado"),
        ("APPROVED", "Aprovado"),
        ("PAID", "Pago"),
        ("DISPUTED", "Em Disputa"),
    ]

    # Relacionamentos
    driver = models.ForeignKey(
        "drivers_app.DriverProfile",
        on_delete=models.PROTECT,
        related_name="settlements",
        verbose_name="Motorista",
    )

    partner = models.ForeignKey(
        "core.Partner",
        on_delete=models.PROTECT,
        related_name="driver_settlements",
        verbose_name="Parceiro",
        null=True,
        blank=True,
        help_text="Se null, é um settlement consolidado multi-partner",
    )

    # Período
    period_type = models.CharField(
        "Tipo de Período",
        max_length=20,
        choices=[
            ("WEEKLY", "Semanal"),
            ("MONTHLY", "Mensal"),
        ],
        default="WEEKLY",
    )

    week_number = models.PositiveIntegerField(
        "Número da Semana",
        null=True,
        blank=True,
        help_text="Semana do ano (1-52)",
    )

    month_number = models.PositiveIntegerField(
        "Mês", null=True, blank=True, help_text="Mês do ano (1-12)"
    )

    year = models.PositiveIntegerField("Ano", db_index=True)

    period_start = models.DateField("Início do Período", db_index=True)

    period_end = models.DateField("Fim do Período", db_index=True)

    # Estatísticas de Entregas
    total_orders = models.PositiveIntegerField("Total de Pedidos", default=0)

    delivered_orders = models.PositiveIntegerField("Pedidos Entregues", default=0)

    failed_orders = models.PositiveIntegerField("Pedidos Falhados", default=0)

    success_rate = models.DecimalField(
        "Taxa de Sucesso",
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Percentual de entregas com sucesso",
    )

    # Valores Financeiros
    gross_amount = models.DecimalField(
        "Valor Bruto",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Total antes de descontos",
    )

    bonus_amount = models.DecimalField(
        "Bônus",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Bônus por performance",
    )

    fuel_deduction = models.DecimalField(
        "Desconto Combustível",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )

    claims_deducted = models.DecimalField(
        "Descontos (Claims)",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Multas, perdas, danos",
    )

    other_deductions = models.DecimalField(
        "Outros Descontos",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )

    net_amount = models.DecimalField(
        "Valor Líquido",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Valor final a pagar",
    )

    # Status e Pagamento
    status = models.CharField(
        "Status",
        max_length=20,
        choices=STATUS_CHOICES,
        default="DRAFT",
        db_index=True,
    )

    calculated_at = models.DateTimeField("Calculado em", null=True, blank=True)

    approved_at = models.DateTimeField("Aprovado em", null=True, blank=True)

    approved_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_settlements",
    )

    paid_at = models.DateTimeField("Pago em", null=True, blank=True)

    payment_reference = models.CharField(
        "Referência de Pagamento",
        max_length=200,
        blank=True,
        help_text="MB WAY, Transferência, etc.",
    )

    # Metadata
    notes = models.TextField("Notas", blank=True)

    pdf_file = models.FileField(
        "PDF do Extrato",
        upload_to="settlements/pdfs/%Y/%m/",
        null=True,
        blank=True,
    )

    whatsapp_sent = models.BooleanField("WhatsApp Enviado", default=False)

    whatsapp_sent_at = models.DateTimeField(
        "WhatsApp Enviado em", null=True, blank=True
    )

    # Auditoria
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_settlements",
    )

    class Meta:
        verbose_name = "Acerto de Motorista"
        verbose_name_plural = "Acertos de Motoristas"
        ordering = [
            "-year",
            "-week_number",
            "-month_number",
            "driver__nome_completo",
        ]
        unique_together = [
            (
                "driver",
                "partner",
                "year",
                "week_number",
            ),  # Para settlements semanais
            (
                "driver",
                "partner",
                "year",
                "month_number",
            ),  # Para settlements mensais
        ]
        indexes = [
            models.Index(fields=["driver", "period_start", "period_end"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["year", "week_number"]),
        ]

    def __str__(self):
        partner_name = self.partner.name if self.partner else "Multi-Partner"
        if self.period_type == "WEEKLY":
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
            created_at__date__lte=self.period_end,
        )

        if self.partner:
            orders_query = orders_query.filter(partner=self.partner)

        orders = orders_query.select_related("partner")

        # Estatísticas
        self.total_orders = orders.count()
        self.delivered_orders = orders.filter(current_status="DELIVERED").count()
        self.failed_orders = self.total_orders - self.delivered_orders

        if self.total_orders > 0:
            self.success_rate = (
                Decimal(self.delivered_orders) / Decimal(self.total_orders)
            ) * Decimal("100.00")

        # Calcular valor bruto
        gross = Decimal("0.00")

        for order in orders:
            try:
                # Buscar tarifa aplicável
                tariff = PartnerTariff.objects.get(
                    partner=order.partner,
                    postal_zone__code=order.postal_code[:4],
                    valid_from__lte=order.created_at.date(),
                    valid_until__gte=order.created_at.date(),
                )

                if order.current_status == "DELIVERED":
                    gross += tariff.base_price + tariff.success_bonus
                else:
                    gross += tariff.base_price - tariff.failure_penalty

            except PartnerTariff.DoesNotExist:
                # Fallback
                gross += (
                    Decimal("5.00")
                    if order.current_status == "DELIVERED"
                    else Decimal("2.00")
                )

        self.gross_amount = gross

        # Calcular bônus por performance
        if self.success_rate >= Decimal("95.00"):
            self.bonus_amount = gross * Decimal("0.10")  # 10% de bônus
        elif self.success_rate >= Decimal("90.00"):
            self.bonus_amount = gross * Decimal("0.05")  # 5% de bônus

        # Buscar claims pendentes
        pending_claims = self.claims.filter(status="APPROVED")
        self.claims_deducted = sum(claim.amount for claim in pending_claims)

        # Calcular valor líquido
        total_deductions = (
            self.fuel_deduction + self.claims_deducted + self.other_deductions
        )

        self.net_amount = self.gross_amount + self.bonus_amount - total_deductions

        # Atualizar status e timestamp
        self.status = "CALCULATED"
        self.calculated_at = timezone.now()
        self.save()

    def approve(self, user):
        """Aprova o settlement"""
        if self.status != "CALCULATED":
            raise ValueError("Settlement deve estar no status CALCULATED")

        self.status = "APPROVED"
        self.approved_at = timezone.now()
        self.approved_by = user
        self.save()

    def mark_as_paid(self, payment_reference=""):
        """Marca como pago"""
        if self.status != "APPROVED":
            raise ValueError("Settlement deve estar APPROVED")

        self.status = "PAID"
        self.paid_at = timezone.now()
        self.payment_reference = payment_reference
        self.save()


class DriverClaim(models.Model):
    """
    Descontos aplicados a motoristas (multas, perdas, danos, etc.)
    Reduz o valor do settlement.
    """

    CLAIM_TYPES = [
        ("ORDER_LOSS", "Perda de Pedido"),
        ("ORDER_DAMAGE", "Dano em Pedido"),
        ("VEHICLE_FINE", "Multa de Veículo"),
        ("VEHICLE_DAMAGE", "Dano em Veículo"),
        ("FUEL_EXCESS", "Excesso de Combustível"),
        ("MISSING_POD", "Falta de Comprovante"),
        ("LATE_DELIVERY", "Entrega Atrasada"),
        ("CUSTOMER_COMPLAINT", "Reclamação de Cliente"),
        ("FAKE_DELIVERY", "Fake Delivery (PUDO)"),
        ("OTHER", "Outro"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "Pendente"),
        ("APPROVED", "Aprovado"),
        ("REJECTED", "Rejeitado"),
        ("APPEALED", "Em Recurso"),
    ]

    # Relacionamentos
    driver = models.ForeignKey(
        "drivers_app.DriverProfile",
        on_delete=models.PROTECT,
        related_name="claims",
        verbose_name="Motorista",
    )

    settlement = models.ForeignKey(
        DriverSettlement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="claims",
        verbose_name="Acerto",
        help_text="Settlement onde o desconto foi aplicado",
    )

    # Referências
    order = models.ForeignKey(
        "orders_manager.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="claims",
        verbose_name="Pedido Relacionado",
    )

    vehicle_incident = models.ForeignKey(
        "fleet_management.VehicleIncident",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="claims",
        verbose_name="Incidente de Veículo",
    )

    # Detalhes do Claim
    claim_type = models.CharField(
        "Tipo de Desconto", max_length=30, choices=CLAIM_TYPES, db_index=True
    )

    amount = models.DecimalField(
        "Valor",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    description = models.TextField(
        "Descrição", help_text="Detalhes do motivo do desconto"
    )

    evidence_file = models.FileField(
        "Evidência",
        upload_to="claims/evidence/%Y/%m/",
        null=True,
        blank=True,
        help_text="Foto, documento, etc.",
    )

    justification = models.TextField(
        "Justificativa",
        blank=True,
        help_text="Justificativa ou recurso do motorista",
    )

    # Status e Aprovação
    status = models.CharField(
        "Status",
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
        db_index=True,
    )

    occurred_at = models.DateTimeField(
        "Ocorrido em", default=timezone.now, db_index=True
    )

    reviewed_at = models.DateTimeField("Revisado em", null=True, blank=True)

    reviewed_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_claims",
        verbose_name="Revisado por",
    )

    review_notes = models.TextField("Notas da Revisão", blank=True)

    # === LINK À RECLAMAÇÃO DE CLIENTE (protocolo completo) ============
    customer_complaint = models.ForeignKey(
        "drivers_app.CustomerComplaint",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="driver_claims",
        help_text=(
            "Reclamação de cliente associada a este desconto — preserva "
            "todo o protocolo (cliente, morada, deadline, anexos) para "
            "permitir defesa estruturada."
        ),
    )

    # === LINK AO PACOTE CAINIAO (Fase 6 — auto-detecção) ================
    waybill_number = models.CharField(
        "Waybill do Pacote",
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Waybill do CainiaoOperationTask associado (para auto-detecção de perdas).",
    )
    operation_task_date = models.DateField(
        "Data da Tarefa",
        null=True, blank=True, db_index=True,
        help_text="Data do CainiaoOperationTask (em conjunto com waybill dá a chave única).",
    )
    auto_detected = models.BooleanField(
        "Detetado Automaticamente",
        default=False,
        db_index=True,
        help_text="Criado pelo processo de auto-detecção (task Celery).",
    )

    # Auditoria
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_claims",
    )

    class Meta:
        verbose_name = "Desconto de Motorista"
        verbose_name_plural = "Descontos de Motoristas"
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["driver", "status", "-occurred_at"]),
            models.Index(fields=["claim_type", "status"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"{self.get_claim_type_display()} - {self.driver.nome_completo} - €{self.amount}"

    def approve(self, user, notes=""):
        """Aprova o claim e auto-inclui em PFs em CALCULADO/APROVADO
        do mesmo driver no período.

        Se já existe DriverPreInvoice em estado editável (CALCULADO,
        APROVADO ou PENDENTE) cujo período cobre a data do claim,
        adiciona-o automaticamente como PreInvoiceLostPackage.
        """
        self.status = "APPROVED"
        self.reviewed_at = timezone.now()
        self.reviewed_by = user
        self.review_notes = notes
        self.save()

        # Auto-inclui em PF aberta do período se houver
        try:
            from .services_claims_in_pf import auto_include_approved_claims
            ref_date = (
                self.operation_task_date
                or (self.occurred_at.date() if self.occurred_at else None)
            )
            if ref_date is None or self.driver_id is None:
                return
            open_pfs = DriverPreInvoice.objects.filter(
                driver_id=self.driver_id,
                periodo_inicio__lte=ref_date,
                periodo_fim__gte=ref_date,
                status__in=["CALCULADO", "APROVADO", "PENDENTE"],
            )
            for pf in open_pfs:
                result = auto_include_approved_claims(pf)
                if result["included"]:
                    pf.recalcular()
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "auto_include_approved_claims falhou na approve()"
            )

    def reject(self, user, notes=""):
        """Rejeita o claim"""
        self.status = "REJECTED"
        self.reviewed_at = timezone.now()
        self.reviewed_by = user
        self.review_notes = notes
        self.save()

    def appeal(self, justification):
        """Motorista recorre do claim"""
        self.status = "APPEALED"
        self.justification = justification
        self.save()


# ============================================================================
# PRÉ-FATURA DE MOTORISTA (entrada manual, compatível com futura integração API)
# ============================================================================


class DriverPreInvoice(models.Model):
    """
    Pré-fatura mensal do motorista (equivalente às folhas PF_01..PF_15 do Excel).
    Entrada manual por padrão; preparado para receber dados via API futuramente.
    """

    STATUS_CHOICES = [
        ("RASCUNHO", "Rascunho"),
        ("CALCULADO", "Calculado"),
        ("APROVADO", "Aprovado"),
        ("PENDENTE", "Pendente Pagamento"),
        ("CONTESTADO", "Contestado"),
        ("REPROVADO", "Reprovado"),
        ("PAGO", "Pago"),
    ]

    # Transições de estado permitidas
    TRANSICOES = {
        "RASCUNHO":   ["CALCULADO"],
        "CALCULADO":  ["APROVADO", "CONTESTADO", "REPROVADO"],
        "APROVADO":   ["PENDENTE", "CONTESTADO"],
        "PENDENTE":   ["PAGO", "APROVADO"],
        "CONTESTADO": ["CALCULADO", "REPROVADO"],
        "REPROVADO":  ["CALCULADO"],
        "PAGO":       [],
    }

    # Identificação
    numero = models.CharField(
        "Nº Pré-Fatura",
        max_length=20,
        unique=True,
        help_text="Ex: PF-0001",
    )

    driver = models.ForeignKey(
        "drivers_app.DriverProfile",
        on_delete=models.PROTECT,
        related_name="pre_invoices",
        verbose_name="Motorista",
    )

    # Período
    periodo_inicio = models.DateField("Período Início", db_index=True)
    periodo_fim = models.DateField("Período Fim", db_index=True)

    # Valores calculados (actualizados por recalcular())
    base_entregas = models.DecimalField(
        "Base Entregas (€)",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Soma das linhas: pacotes × taxa (+ DSR)",
    )
    total_bonus = models.DecimalField(
        "Total Bônus Domingo/Feriado (€)",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    ajuste_manual = models.DecimalField(
        "Ajuste Manual (€)",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Correções positivas extraordinárias",
    )
    penalizacoes_gerais = models.DecimalField(
        "Penalizações Gerais (€)",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Descontos gerais (excluindo pacotes perdidos)",
    )
    total_pacotes_perdidos = models.DecimalField(
        "Total Pacotes Perdidos (€)",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total_adiantamentos = models.DecimalField(
        "Total Adiantamentos/Combustível (€)",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total_comissoes_indicacao = models.DecimalField(
        "Comissões de Indicação (€)",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Calculado automaticamente com base nas indicações activas.",
    )
    subtotal_bruto = models.DecimalField(
        "Subtotal Bruto (€)",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total_a_receber = models.DecimalField(
        "Total a Receber (€)",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    # === ASSINATURA REMOTA (Fase 8.3) ==================================
    signed_at = models.DateTimeField(
        "Aceite pelo motorista em", null=True, blank=True,
        help_text="Timestamp quando o motorista aceitou remotamente.",
    )
    signed_token = models.CharField(
        "Token de Assinatura",
        max_length=64, blank=True, db_index=True,
        help_text="Token único para link de aceitação remota.",
    )
    signed_ip = models.GenericIPAddressField(
        "IP da Aceitação", null=True, blank=True,
    )
    whatsapp_sent_at = models.DateTimeField(
        "Enviado via WhatsApp em", null=True, blank=True,
    )

    # === IVA / IRS (Fase 8.4) ==========================================
    vat_amount = models.DecimalField(
        "IVA (€)", max_digits=12, decimal_places=2, default=Decimal("0.00"),
    )
    irs_retention_amount = models.DecimalField(
        "Retenção IRS (€)",
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
    )
    caucao_retida = models.DecimalField(
        "Caução Retida (€)",
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
    )

    # Status e pagamento
    status = models.CharField(
        "Status",
        max_length=20,
        choices=STATUS_CHOICES,
        default="RASCUNHO",
        db_index=True,
    )
    data_pagamento = models.DateField("Data de Pagamento", null=True, blank=True)
    referencia_pagamento = models.CharField(
        "Referência de Pagamento",
        max_length=200,
        blank=True,
        help_text="MB WAY, Transferência, etc.",
    )
    comprovante_pagamento = models.FileField(
        "Comprovante de Pagamento",
        upload_to="pre_invoices/comprovativos/%Y/%m/",
        null=True,
        blank=True,
        help_text="Foto ou ficheiro do comprovativo de pagamento",
    )
    fatura_ficheiro = models.FileField(
        "Fatura",
        upload_to="pre_invoices/faturas/%Y/%m/",
        null=True,
        blank=True,
        help_text="PDF da fatura emitida pelo motorista",
    )

    # DSP / Empresa
    dsp_empresa = models.CharField(
        "DSP / Empresa",
        max_length=200,
        blank=True,
        default="LÉGUAS FRANZINAS - UNIPESSOAL LDA",
    )

    # Controlo API (para futura integração)
    api_source = models.CharField(
        "Fonte API",
        max_length=50,
        blank=True,
        help_text="Ex: paack, amazon, delnext — vazio se entrada manual",
    )
    api_reference = models.CharField(
        "Referência API",
        max_length=200,
        blank=True,
        help_text="ID ou referência do sistema externo",
    )

    # Notas e auditoria
    observacoes = models.TextField("Observações", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_pre_invoices",
    )

    class Meta:
        verbose_name = "Pré-Fatura de Motorista"
        verbose_name_plural = "Pré-Faturas de Motoristas"
        ordering = ["-periodo_fim", "driver__nome_completo"]
        indexes = [
            models.Index(fields=["driver", "periodo_inicio", "periodo_fim"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.numero} - {self.driver.nome_completo} ({self.periodo_inicio} → {self.periodo_fim})"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Snapshot do status original para detectar transições no save()
        self._original_status = (
            self.status if not self._state.adding else None
        )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Quando a PF é reprovada (cancelada), libertar lançamentos
        # incluídos para que voltem a PENDENTE — não perdemos nenhum
        # lançamento por causa de uma PF cancelada.
        if (
            self._original_status != "REPROVADO"
            and self.status == "REPROVADO"
        ):
            from .cash_entry_services import detach_entries_from_pf
            detach_entries_from_pf(self)
        self._original_status = self.status

    def recalcular(self):
        """Recalcula todos os totais com base nas linhas de trabalho e sub-linhas."""
        self.base_entregas = sum(
            l.base_entregas for l in self.linhas.all()
        )
        self.total_bonus = sum(
            b.bonus_calculado for b in self.bonificacoes.all()
        )
        self.total_pacotes_perdidos = sum(
            p.valor_com_iva for p in self.pacotes_perdidos.all()
        )
        self.total_adiantamentos = sum(
            a.valor for a in self.adiantamentos.filter(
                status="INCLUIDO_PF",
            )
        )

        # Comissões de indicação — soma automática por cada motorista indicado
        from drivers_app.models import DriverReferral
        comissoes = Decimal("0.00")
        for ref in self.driver.referrals_given.filter(ativo=True):
            referred_pfs = DriverPreInvoice.objects.filter(
                driver=ref.referred,
                periodo_inicio=self.periodo_inicio,
                periodo_fim=self.periodo_fim,
            )
            for rpf in referred_pfs:
                total_pcts = sum(l.total_pacotes for l in rpf.linhas.all())
                comissoes += Decimal(total_pcts) * ref.comissao_por_pacote
        self.total_comissoes_indicacao = comissoes

        self.subtotal_bruto = (
            self.base_entregas
            + self.total_bonus
            + self.ajuste_manual
        )
        self.total_a_receber = (
            self.subtotal_bruto
            - self.penalizacoes_gerais
            - self.total_pacotes_perdidos
            - self.total_adiantamentos
            + self.total_comissoes_indicacao
        )

        # IVA: motoristas em regime Normal cobram 23% na factura.
        # Isento (art. 53º) e Simplificado: sem IVA.
        # IVA é adicional ao total_a_receber (não substitui).
        regime = getattr(self.driver, "vat_regime", "isento") or "isento"
        if regime == "normal":
            self.vat_amount = (
                self.total_a_receber * Decimal("0.23")
            ).quantize(Decimal("0.01"))
        else:
            self.vat_amount = Decimal("0.00")

        # Retenção IRS sobre total_a_receber (sem IVA)
        irs_pct = getattr(self.driver, "irs_retention_pct", None) or Decimal("0")
        if irs_pct > 0:
            self.irs_retention_amount = (
                self.total_a_receber * irs_pct / Decimal("100")
            ).quantize(Decimal("0.01"))
        else:
            self.irs_retention_amount = Decimal("0.00")

        self.status = "CALCULADO"
        self.save()

    @property
    def total_com_iva(self):
        """Total a receber + IVA. Para drivers em regime Normal, é o
        valor que a factura do motorista efectivamente apresenta."""
        return self.total_a_receber + self.vat_amount

    @property
    def total_liquido(self):
        """Valor líquido após retenção IRS (mas mantendo IVA cobrado).
        total_com_iva - irs_retention_amount.
        """
        return self.total_com_iva - self.irs_retention_amount


class PreInvoiceLine(models.Model):
    """
    Linha de trabalho dentro de uma pré-fatura.
    Cada linha representa entregas para um parceiro específico num período.
    Permite múltiplos parceiros (Paack, Delnext, Cainiao…) na mesma pré-fatura.
    """

    pre_invoice = models.ForeignKey(
        DriverPreInvoice,
        on_delete=models.CASCADE,
        related_name="linhas",
        verbose_name="Pré-Fatura",
    )
    parceiro = models.ForeignKey(
        "core.Partner",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Parceiro / Operação",
        help_text="Ex: Paack, Delnext, Cainiao",
    )
    courier_id = models.CharField(
        "Courier ID",
        max_length=100,
        blank=True,
        help_text="ID no sistema do parceiro (futura integração API)",
    )
    total_pacotes = models.PositiveIntegerField("Total Pacotes", default=0)
    taxa_por_entrega = models.DecimalField(
        "Taxa por Entrega (€)",
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )
    dsr_percentual = models.DecimalField(
        "DSR (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Descanso Semanal Remunerado aplicado à base",
    )
    base_entregas = models.DecimalField(
        "Base Entregas (€)",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        editable=False,
        help_text="Calculado: pacotes × taxa × (1 + DSR/100)",
    )
    observacoes = models.CharField("Observações", max_length=300, blank=True)
    api_source = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Linha de Trabalho"
        verbose_name_plural = "Linhas de Trabalho"
        ordering = ["created_at"]

    def __str__(self):
        parceiro_nome = self.parceiro.name if self.parceiro else "—"
        return f"{parceiro_nome}: {self.total_pacotes} pcts × €{self.taxa_por_entrega} = €{self.base_entregas}"

    def calcular_e_salvar(self):
        """Calcula base_entregas e grava, depois dispara recalcular() na pré-fatura."""
        self.base_entregas = Decimal(self.total_pacotes) * self.taxa_por_entrega
        self.save()
        self.pre_invoice.recalcular()


class PreInvoiceBonus(models.Model):
    """
    Bonificação por domingo ou feriado trabalhado.
    Cada linha = 1 evento. O bônus é calculado automaticamente.
    """

    TIPO_CHOICES = [
        ("DOMINGO", "Domingo"),
        ("FERIADO", "Feriado Nacional"),
        ("FERIADO_LOCAL", "Feriado Local"),
    ]

    # Faixas de bônus (€30 até 30 entregas, €50 com 60+)
    BONUS_30 = Decimal("30.00")
    BONUS_50 = Decimal("50.00")
    LIMIAR_30 = 30
    LIMIAR_60 = 60

    pre_invoice = models.ForeignKey(
        DriverPreInvoice,
        on_delete=models.CASCADE,
        related_name="bonificacoes",
        verbose_name="Pré-Fatura",
    )

    data = models.DateField("Data")
    tipo = models.CharField("Tipo", max_length=20, choices=TIPO_CHOICES, default="DOMINGO")
    qtd_entregas_elegiveis = models.PositiveIntegerField(
        "Qtd. Entregas Elegíveis",
        default=0,
        help_text="Entregas contabilizadas para o bônus neste dia",
    )
    bonus_calculado = models.DecimalField(
        "Bônus (€)",
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        editable=False,
    )

    # Campo preparado para API
    api_source = models.CharField(max_length=50, blank=True)

    observacoes = models.CharField("Observações", max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Bonificação Domingo/Feriado"
        verbose_name_plural = "Bonificações Domingo/Feriado"
        ordering = ["data"]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.data} — {self.qtd_entregas_elegiveis} entregas — €{self.bonus_calculado}"

    def save(self, *args, **kwargs):
        # Calcular bônus automaticamente pelas faixas
        if self.qtd_entregas_elegiveis >= self.LIMIAR_60:
            self.bonus_calculado = self.BONUS_50
        elif self.qtd_entregas_elegiveis >= self.LIMIAR_30:
            self.bonus_calculado = self.BONUS_30
        else:
            self.bonus_calculado = Decimal("0.00")
        super().save(*args, **kwargs)


class PreInvoiceLostPackage(models.Model):
    """
    Pacote perdido associado a uma pré-fatura.
    O valor padrão é €50, mas pode ser ajustado.
    """

    VALOR_PADRAO = Decimal("50.00")

    pre_invoice = models.ForeignKey(
        DriverPreInvoice,
        on_delete=models.CASCADE,
        related_name="pacotes_perdidos",
        verbose_name="Pré-Fatura",
    )

    data = models.DateField("Data", null=True, blank=True)
    numero_pacote = models.CharField("Nº Pacote", max_length=100, blank=True)
    descricao = models.CharField("Descrição", max_length=300, blank=True)
    valor = models.DecimalField(
        "Valor Base (€)",
        max_digits=8,
        decimal_places=2,
        default=VALOR_PADRAO,
        validators=[MinValueValidator(0)],
    )
    iva_percentual = models.DecimalField(
        "IVA (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Percentagem de IVA a aplicar sobre o valor base (ex: 23)",
    )

    # Campo preparado para API
    api_source = models.CharField(max_length=50, blank=True)

    observacoes = models.CharField("Observações", max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pacote Perdido"
        verbose_name_plural = "Pacotes Perdidos"
        ordering = ["data"]

    @property
    def valor_iva(self):
        """Valor do IVA calculado."""
        return (self.valor * (self.iva_percentual / Decimal("100"))).quantize(Decimal("0.01"))

    @property
    def valor_com_iva(self):
        """Valor base + IVA."""
        return self.valor + self.valor_iva

    def __str__(self):
        return f"Perdido {self.numero_pacote or '—'} — €{self.valor_com_iva}"


class Shareholder(models.Model):
    """Sócio da empresa — pode adiantar dinheiro do bolso para despesas de
    motoristas (combustível, adiantamento) quando a empresa não tem caixa
    no momento. A empresa fica devendo o valor ao sócio até reembolsar."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="shareholder_profile",
        verbose_name="Utilizador (login)",
    )
    nome = models.CharField("Nome", max_length=200)
    iban = models.CharField("IBAN", max_length=34, blank=True)
    telefone = models.CharField("Telefone", max_length=30, blank=True)
    ativo = models.BooleanField("Ativo", default=True, db_index=True)
    observacoes = models.TextField("Observações", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sócio"
        verbose_name_plural = "Sócios"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class PreInvoiceAdvance(models.Model):
    """
    Lançamento financeiro do motorista — adiantamento, combustível,
    abastecimento ou outro débito que será cobrado numa pré-fatura.

    Conta-corrente do motorista: nasce sempre com PENDENTE e ligado ao
    motorista; só é anexado a uma PF quando o operador decide incluir
    (manualmente ou via prompt na criação/recálculo da PF). Cada lançamento
    pode estar em apenas uma PF a qualquer momento.
    """

    TIPO_CHOICES = [
        ("ADIANTAMENTO", "Adiantamento"),
        ("COMBUSTIVEL", "Combustível"),
        ("ABASTECIMENTO", "Abastecimento"),
        ("OUTRO", "Outro"),
    ]

    PAID_BY_SOURCE_CHOICES = [
        ("EMPRESA", "Empresa"),
        ("TERCEIRO", "Sócio (terceiro)"),
    ]

    STATUS_CHOICES = [
        ("PENDENTE", "Pendente"),
        ("INCLUIDO_PF", "Incluído em PF"),
        ("CANCELADO", "Cancelado"),
    ]

    driver = models.ForeignKey(
        "drivers_app.DriverProfile",
        on_delete=models.PROTECT,
        related_name="cash_entries",
        verbose_name="Motorista",
    )

    pre_invoice = models.ForeignKey(
        DriverPreInvoice,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="adiantamentos",
        verbose_name="Pré-Fatura (quando incluído)",
    )

    status = models.CharField(
        "Status",
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDENTE",
        db_index=True,
    )

    data = models.DateField("Data", null=True, blank=True)
    tipo = models.CharField("Tipo", max_length=20, choices=TIPO_CHOICES, default="ADIANTAMENTO")
    descricao = models.CharField("Descrição", max_length=300, blank=True)
    valor = models.DecimalField(
        "Valor (€)",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    documento_referencia = models.CharField(
        "Documento / Observações",
        max_length=300,
        blank=True,
    )

    # Quem pagou: empresa (caixa) ou um sócio (terceiro). Quando TERCEIRO,
    # paid_by_lender é obrigatório e gera um ThirdPartyReimbursement
    # automático (conta a pagar para o sócio).
    paid_by_source = models.CharField(
        "Pago por",
        max_length=20,
        choices=PAID_BY_SOURCE_CHOICES,
        default="EMPRESA",
        db_index=True,
    )
    paid_by_lender = models.ForeignKey(
        Shareholder,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name="advances_pagas",
        verbose_name="Sócio que adiantou",
    )

    # Bill que originou este lançamento (combustível pago em nome da
    # empresa para um motorista específico). Quando preenchido, a Bill
    # é a fonte de verdade — alterar a Bill propaga aqui via
    # Bill._sync_driver_advance_for_bill.
    origem_bill = models.ForeignKey(
        "accounting.Bill",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="driver_advances",
        verbose_name="Bill de origem",
    )

    # Campo preparado para API
    api_source = models.CharField(max_length=50, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Adiantamento / Combustível"
        verbose_name_plural = "Adiantamentos / Combustível"
        ordering = ["data"]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.data} — €{self.valor}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._sync_reimbursement()

    def _sync_reimbursement(self):
        """Mantém um ThirdPartyReimbursement em sincronia com este advance.

        - paid_by_source == TERCEIRO + paid_by_lender → cria/atualiza
          reembolso PENDENTE ligado a este advance.
        - Caso contrário → cancela qualquer reembolso PENDENTE deste advance
          (mantém PAGO/CANCELADO intactos para preservar histórico).
        """
        existing = self.reembolsos_terceiros.filter(
            status="PENDENTE",
        ).first()
        if self.paid_by_source == "TERCEIRO" and self.paid_by_lender_id:
            data_emp = self.data or timezone.now().date()
            desc = (
                f"{self.get_tipo_display()} · "
                f"{self.driver.nome_completo}"
            )
            if self.descricao:
                desc = f"{desc} · {self.descricao}"
            desc = desc[:300]
            if existing:
                existing.lender = self.paid_by_lender
                existing.valor = self.valor
                existing.data_emprestimo = data_emp
                existing.descricao = desc
                existing.save()
            else:
                ThirdPartyReimbursement.objects.create(
                    lender=self.paid_by_lender,
                    valor=self.valor,
                    data_emprestimo=data_emp,
                    descricao=desc,
                    origem_advance=self,
                    status="PENDENTE",
                )
        else:
            if existing:
                existing.status = "CANCELADO"
                existing.save()

    def delete(self, *args, **kwargs):
        # Cancela reembolsos pendentes antes de apagar o advance
        self.reembolsos_terceiros.filter(status="PENDENTE").update(
            status="CANCELADO",
        )
        return super().delete(*args, **kwargs)


class ThirdPartyReimbursement(models.Model):
    """Conta a pagar a um sócio que adiantou dinheiro do bolso.

    Dívida paralela à do motorista (que continua devendo o adiantamento à
    empresa via PreInvoiceAdvance). Não interfere com a PF do motorista.
    """

    STATUS_CHOICES = [
        ("PENDENTE", "Pendente"),
        ("PAGO", "Pago"),
        ("CANCELADO", "Cancelado"),
    ]

    lender = models.ForeignKey(
        Shareholder,
        on_delete=models.PROTECT,
        related_name="reembolsos",
        verbose_name="Sócio",
    )
    valor = models.DecimalField(
        "Valor (€)", max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    data_emprestimo = models.DateField("Data do empréstimo")
    descricao = models.CharField("Descrição", max_length=300, blank=True)

    origem_advance = models.ForeignKey(
        PreInvoiceAdvance,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reembolsos_terceiros",
        verbose_name="Lançamento de origem",
    )
    origem_bill = models.ForeignKey(
        "accounting.Bill",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reembolsos_terceiros",
        verbose_name="Bill de origem",
        help_text=(
            "Conta a Pagar paga por um sócio. Cria reembolso quando "
            "a Bill fica PAID com paid_by_source=TERCEIRO."
        ),
    )

    status = models.CharField(
        "Status", max_length=20, choices=STATUS_CHOICES,
        default="PENDENTE", db_index=True,
    )
    data_pagamento = models.DateField(
        "Data do pagamento", null=True, blank=True,
    )
    referencia_pagamento = models.CharField(
        "Referência do pagamento", max_length=200, blank=True,
    )
    comprovante_pagamento = models.FileField(
        "Comprovativo de pagamento",
        upload_to="reembolsos_terceiros/comprovativos/%Y/%m/",
        null=True, blank=True,
    )
    pago_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reembolsos_terceiros_pagos",
        verbose_name="Pago por (utilizador)",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reembolsos_terceiros_criados",
    )

    class Meta:
        verbose_name = "Reembolso a Sócio"
        verbose_name_plural = "Reembolsos a Sócios"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "lender"]),
        ]

    def __str__(self):
        return (
            f"{self.lender.nome} — €{self.valor} "
            f"({self.get_status_display()})"
        )


class DriverCourierMapping(models.Model):
    """
    Liga um DriverProfile ao identificador de courier de um parceiro específico.
    Cada parceiro tem o seu próprio sistema de IDs (Cainiao, Paack, Delnext...).
    """
    from drivers_app.models import DriverProfile as _DP

    driver = models.ForeignKey(
        "drivers_app.DriverProfile",
        on_delete=models.CASCADE,
        related_name="courier_mappings",
        verbose_name="Motorista",
    )
    partner = models.ForeignKey(
        "core.Partner",
        on_delete=models.CASCADE,
        related_name="courier_mappings",
        verbose_name="Parceiro",
    )
    courier_id = models.CharField("Courier ID", max_length=100)
    courier_name = models.CharField("Nome no Sistema Parceiro", max_length=200, blank=True)

    class Meta:
        verbose_name = "Mapeamento Courier"
        verbose_name_plural = "Mapeamentos Courier"
        unique_together = [("partner", "courier_id")]

    def __str__(self):
        return f"{self.partner.name} / {self.courier_id} → {self.driver.nome_completo}"


# ─── Cainiao Import ────────────────────────────────────────────────────────────

class CainiaoImportBatch(models.Model):
    """Registo de um import de planilha Cainiao."""
    filename      = models.CharField("Ficheiro", max_length=255)
    periodo_inicio = models.DateField("Período Início")
    periodo_fim    = models.DateField("Período Fim")
    total_delivered = models.PositiveIntegerField("Total Entregas (Delivered)", default=0)
    created_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cainiao_imports",
        verbose_name="Importado por",
    )
    created_at    = models.DateTimeField("Importado em", auto_now_add=True)

    class Meta:
        verbose_name = "Import Cainiao"
        verbose_name_plural = "Imports Cainiao"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Cainiao {self.periodo_inicio} → {self.periodo_fim} ({self.total_delivered} entregues)"


class CainiaoDelivery(models.Model):
    """Linha individual de entrega (Delivered) importada do Cainiao."""
    batch          = models.ForeignKey(
        CainiaoImportBatch, on_delete=models.CASCADE,
        related_name="deliveries", verbose_name="Batch",
    )
    driver         = models.ForeignKey(
        "drivers_app.DriverProfile", on_delete=models.CASCADE,
        related_name="cainiao_deliveries", verbose_name="Motorista",
    )
    courier_id     = models.CharField("Courier ID", max_length=100)
    helper_name    = models.CharField("Courier Helper", max_length=200, blank=True)
    lp_number      = models.CharField("LP No.", max_length=200, blank=True, db_index=True)
    waybill_number = models.CharField("Waybill Number", max_length=200, blank=True, db_index=True)
    delivery_time  = models.DateTimeField("Data de Entrega", null=True, blank=True)

    class Meta:
        verbose_name = "Entrega Cainiao"
        verbose_name_plural = "Entregas Cainiao"
        indexes = [
            models.Index(fields=["driver", "batch"]),
            models.Index(fields=["courier_id"]),
        ]

    def __str__(self):
        helper = f" [{self.helper_name}]" if self.helper_name else ""
        return f"{self.waybill_number}{helper}"


class DriverHelper(models.Model):
    """Helper (ajudante) associado a um motorista, descoberto via imports Cainiao."""
    driver      = models.ForeignKey(
        "drivers_app.DriverProfile", on_delete=models.CASCADE,
        related_name="helpers", verbose_name="Motorista",
    )
    helper_name = models.CharField("Nome do Helper", max_length=200)
    is_active   = models.BooleanField("Ativo", default=True)
    first_seen  = models.DateField("Visto pela primeira vez", null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Helper do Motorista"
        verbose_name_plural = "Helpers dos Motoristas"
        unique_together = [("driver", "helper_name")]
        ordering = ["helper_name"]

    def __str__(self):
        return f"{self.helper_name} (helper de {self.driver.nome_completo})"

    def total_deliveries(self):
        return CainiaoDelivery.objects.filter(
            driver=self.driver, helper_name=self.helper_name
        ).count()


# ============================================================================
# CAINIAO — PLANILHA DE PREVISÃO DE VOLUME
# ============================================================================

class CainiaoForecastBatch(models.Model):
    """Registo de um import de planilha Cainiao (qualquer tipo)."""

    TYPE_FORECAST = "FORECAST"
    TYPE_INBOUND = "INBOUND"
    TYPE_EOD = "EOD"
    IMPORT_TYPES = [
        (TYPE_FORECAST, "Previsão de Volume"),
        (TYPE_INBOUND, "Inbound"),
        (TYPE_EOD, "Final do Dia"),
    ]

    filename = models.CharField("Ficheiro", max_length=255)
    import_type = models.CharField(
        "Tipo de Import", max_length=20,
        choices=IMPORT_TYPES, default=TYPE_FORECAST,
    )
    operation_date = models.DateField("Data da Operação")
    total_packages = models.PositiveIntegerField("Total Pacotes", default=0)
    updated_packages = models.PositiveIntegerField(
        "Pacotes Atualizados", default=0,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cainiao_forecast_imports",
        verbose_name="Importado por",
    )
    created_at = models.DateTimeField("Importado em", auto_now_add=True)

    class Meta:
        verbose_name = "Import Cainiao (Planilha)"
        verbose_name_plural = "Imports Cainiao (Planilhas)"
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.get_import_type_display()} {self.operation_date} "
            f"({self.total_packages} pacotes)"
        )


class CainiaoForecastPackage(models.Model):
    """Pacote Cainiao importado via planilha (previsão, inbound ou EOD)."""

    STATUS_CREATE = "Create"
    STATUS_LMS_INB = "LMS_inb"
    STATUS_SORT_START = "Sort_start"
    STATUS_SORT_FINISH = "Sort_finish"
    STATUS_DRIVER_RECEIVED = "Driver_received"
    STATUS_DELIVERED = "Delivered"
    STATUS_ATTEMPT_FAILURE = "Attempt_Failure"

    operation_date = models.DateField("Data da Operação", db_index=True)
    tracking_number = models.CharField(
        "Tracking No.", max_length=100, db_index=True,
    )
    status = models.CharField(
        "Status", max_length=30, default=STATUS_CREATE, db_index=True,
    )
    last_import_batch = models.ForeignKey(
        CainiaoForecastBatch, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="packages", verbose_name="Último Batch",
    )
    lp_number = models.CharField("LP No.", max_length=100, blank=True)
    site_code = models.CharField("Site Code", max_length=100, blank=True)
    inbound_bigbag_id = models.CharField(
        "Inbound Bigbag ID", max_length=100, blank=True, db_index=True,
    )
    bigbag_number = models.CharField("Bigbag No.", max_length=100, blank=True)
    sort_code = models.CharField("Sort Code", max_length=50, blank=True)
    order_type = models.CharField("Order Type", max_length=20, blank=True)
    sop_type = models.CharField("SOP Type", max_length=20, blank=True)
    receiver_name = models.CharField(
        "Nome Cliente", max_length=200, blank=True,
    )
    receiver_phone = models.CharField("Telefone", max_length=50, blank=True)
    receiver_region = models.CharField("Região", max_length=100, blank=True)
    receiver_city = models.CharField("Cidade", max_length=100, blank=True)
    receiver_zip = models.CharField(
        "Código Postal", max_length=20, blank=True,
    )
    receiver_address = models.TextField("Endereço", blank=True)
    latitude = models.DecimalField(
        "Latitude", max_digits=11, decimal_places=7,
        null=True, blank=True,
    )
    longitude = models.DecimalField(
        "Longitude", max_digits=11, decimal_places=7,
        null=True, blank=True,
    )
    # Campos extra do PARCEL_LIST (formato mais rico, 105 colunas)
    receiver_contact_number = models.CharField(
        "Contacto adicional", max_length=50, blank=True,
    )
    receiver_email = models.CharField(
        "Email", max_length=200, blank=True,
    )
    address_abnormal = models.CharField(
        "Address Abnormal", max_length=50, blank=True,
    )
    modified_zip_code = models.CharField(
        "CP modificado", max_length=20, blank=True,
    )
    modified_address = models.TextField(
        "Endereço modificado", blank=True,
    )
    modified_phone = models.CharField(
        "Telefone modificado", max_length=50, blank=True,
    )
    exception_type = models.CharField(
        "Tipo de Exceção", max_length=100, blank=True,
    )
    exception_detail = models.TextField(
        "Detalhe Exceção", blank=True,
    )
    last_exception_time = models.DateTimeField(
        "Última Exceção", null=True, blank=True,
    )
    create_time = models.DateTimeField(
        "Create Time", null=True, blank=True,
    )
    actual_inbound_time = models.DateTimeField(
        "Inbound Real", null=True, blank=True,
    )
    actual_outbound_time = models.DateTimeField(
        "Outbound Real", null=True, blank=True,
    )
    actual_delivery_time = models.DateTimeField(
        "Entrega Real", null=True, blank=True,
    )
    weight_g = models.FloatField(
        "Peso (g)", null=True, blank=True,
    )
    dimensions_lwh = models.CharField(
        "Dimensões L×W×H", max_length=50, blank=True,
    )
    dsp_name = models.CharField(
        "DSP Name", max_length=200, blank=True,
    )
    seller_name = models.CharField(
        "Seller Name", max_length=200, blank=True,
    )
    last_task_plan_date = models.DateField(
        "Última data planeada", null=True, blank=True,
        db_index=True,
    )
    arriving_at_wrong_hub = models.BooleanField(
        "Wrong HUB", default=False,
    )
    wrong_hub_name = models.CharField(
        "Wrong HUB Name", max_length=100, blank=True,
    )
    has_commercial_area_tag = models.BooleanField(
        "Tem tag Commercial Area", default=False,
    )
    zone = models.CharField("Zone", max_length=100, blank=True)
    task_id = models.CharField(
        "Task ID", max_length=100, blank=True,
    )
    is_consolidation = models.BooleanField(
        "Is Consolidation", default=False,
    )
    pin_code = models.CharField(
        "PIN Code", max_length=20, blank=True,
    )
    has_pin_code = models.BooleanField(
        "Has PIN Code", default=False,
    )
    locker_id = models.CharField(
        "Locker ID", max_length=100, blank=True,
    )
    delivery_mode = models.CharField(
        "Delivery Mode", max_length=50, blank=True,
    )
    pod_url = models.CharField(
        "POD", max_length=500, blank=True,
    )
    updated_at = models.DateTimeField("Última Atualização", auto_now=True)
    created_at = models.DateTimeField(
        "Criado em", default=timezone.now, editable=False,
    )

    class Meta:
        verbose_name = "Pacote Cainiao (Planilha)"
        verbose_name_plural = "Pacotes Cainiao (Planilha)"
        unique_together = [("operation_date", "tracking_number")]
        indexes = [
            models.Index(fields=["operation_date", "status"]),
            models.Index(fields=["inbound_bigbag_id"]),
        ]

    def __str__(self):
        return f"{self.tracking_number} [{self.status}] → {self.receiver_name}"

    @property
    def is_delivered(self):
        return self.status == self.STATUS_DELIVERED

    @property
    def is_incident(self):
        return self.status == self.STATUS_ATTEMPT_FAILURE


# ============================================================================
# CAINIAO — PLANILHA FORECAST (previsão de volume por dia)
# ============================================================================

class CainiaoPlanningBatch(models.Model):
    """Registo de um import da planilha Forecast (previsão de volume)."""
    filename = models.CharField("Ficheiro", max_length=255)
    operation_date = models.DateField("Data da Operação", db_index=True)
    total_packages = models.PositiveIntegerField("Total Pacotes", default=0)
    new_packages = models.PositiveIntegerField("Pacotes Novos", default=0)
    updated_packages = models.PositiveIntegerField("Pacotes Atualizados", default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cainiao_planning_imports",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Import Forecast Cainiao"
        verbose_name_plural = "Imports Forecast Cainiao"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Forecast {self.operation_date} ({self.total_packages} pacotes)"


class CainiaoPlanningPackage(models.Model):
    """Pacote de previsão Cainiao — planilha Forecast (27 colunas)."""

    operation_date = models.DateField("Data da Operação", db_index=True)
    parcel_id = models.CharField("Parcel ID", max_length=100, db_index=True)
    lp_code = models.CharField("LP Code", max_length=100, blank=True)
    receiver_province = models.CharField("Provincia", max_length=100, blank=True)
    receiver_city = models.CharField("Cidade", max_length=100, blank=True)
    receiver_zip = models.CharField("Código Postal", max_length=20, blank=True, db_index=True)
    receiver_address = models.TextField("Endereço", blank=True)
    receiver_name = models.CharField("Nome Cliente", max_length=200, blank=True)
    receiver_phone = models.CharField("Telefone", max_length=50, blank=True)
    receiver_email = models.CharField("Email", max_length=200, blank=True)
    order_creation_time = models.DateTimeField("Criação do Pedido", null=True, blank=True)
    sc_consolidation_time = models.DateTimeField("SC Consolidation", null=True, blank=True)
    sc_outbound_time = models.DateTimeField("SC Outbound", null=True, blank=True)
    actual_inbound_time = models.DateTimeField("Inbound Real", null=True, blank=True)
    task_acceptance_time = models.DateTimeField("Task Acceptance", null=True, blank=True)
    sign_time = models.DateTimeField("Sign Time", null=True, blank=True)
    exception_type = models.CharField("Tipo Exceção", max_length=100, blank=True)
    exception_reason = models.CharField("Razão Exceção", max_length=300, blank=True)
    last_exception_time = models.DateTimeField("Última Exceção", null=True, blank=True)
    hub = models.CharField("HUB", max_length=100, blank=True)
    dsp = models.CharField("DSP", max_length=200, blank=True)
    creation_time = models.DateTimeField("Creation Time", null=True, blank=True)
    seller_name = models.CharField("Seller Name", max_length=200, blank=True)
    inbound_time = models.DateTimeField("Inbound Time", null=True, blank=True)
    assign_time = models.DateTimeField("Assign Time", null=True, blank=True)
    delivery_success_time = models.DateTimeField("Delivery Success", null=True, blank=True)
    delivery_fail_time = models.DateTimeField("Delivery Fail", null=True, blank=True)
    pickup_time = models.DateTimeField("Pick-up Time", null=True, blank=True)
    last_import_batch = models.ForeignKey(
        CainiaoPlanningBatch, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="packages",
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        verbose_name = "Pacote Forecast Cainiao"
        verbose_name_plural = "Pacotes Forecast Cainiao"
        unique_together = [("operation_date", "parcel_id")]
        indexes = [
            models.Index(fields=["operation_date", "receiver_zip"]),
            models.Index(fields=["lp_code"]),
        ]

    def __str__(self):
        return f"{self.parcel_id} [{self.operation_date}] → {self.receiver_city}"


# ============================================================================
# CAINIAO — PLANILHA OPERATION UPDATE (status das entregas por dia)
# ============================================================================

class CainiaoOperationBatch(models.Model):
    """Registo de um import da planilha Operation Update."""
    filename = models.CharField("Ficheiro", max_length=255)
    task_date = models.DateField("Data da Tarefa", db_index=True)
    total_tasks = models.PositiveIntegerField("Total Tarefas", default=0)
    new_tasks = models.PositiveIntegerField("Tarefas Novas", default=0)
    updated_tasks = models.PositiveIntegerField("Tarefas Atualizadas", default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cainiao_operation_imports",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Import Operation Update Cainiao"
        verbose_name_plural = "Imports Operation Update Cainiao"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Operation {self.task_date} ({self.total_tasks} tarefas)"


class CainiaoOperationTask(models.Model):
    """Linha da planilha Operation Update — estado de entrega de um pacote."""

    waybill_number = models.CharField("Waybill Number", max_length=100, db_index=True)
    lp_number = models.CharField("LP No.", max_length=100, blank=True, db_index=True)
    task_date = models.DateField("Task Date", db_index=True)
    task_status = models.CharField("Task Status", max_length=50, blank=True, db_index=True)
    courier_name = models.CharField("Courier Name", max_length=200, blank=True, db_index=True)
    courier_id_cainiao = models.CharField(
        "Courier ID (Cainiao)",
        max_length=50, blank=True, db_index=True,
        help_text=(
            "Identificador único Cainiao do motorista (não muda mesmo se o "
            "courier_name for editado). Resolvido via DriverCourierMapping "
            "no import. Permite manter ligação a entregas antigas após "
            "renomear o courier_name."
        ),
    )
    dsp_name = models.CharField("DSP Name", max_length=200, blank=True)
    delivery_type = models.CharField("Delivery Type", max_length=50, blank=True)
    order_type = models.CharField("Order Type", max_length=50, blank=True)
    task_group_order = models.CharField("Task Group Order", max_length=50, blank=True)
    sitecode = models.CharField("Sitecode", max_length=50, blank=True)
    # Destino
    destination_country = models.CharField("País", max_length=10, blank=True)
    destination_area = models.CharField("Área", max_length=100, blank=True)
    destination_city = models.CharField("Cidade", max_length=100, blank=True)
    zip_code = models.CharField("CP", max_length=20, blank=True, db_index=True)
    detailed_address = models.TextField("Endereço", blank=True)
    # Geo
    receiver_latitude = models.CharField("Lat. Destinatário", max_length=30, blank=True)
    receiver_longitude = models.CharField("Long. Destinatário", max_length=30, blank=True)
    actual_latitude = models.CharField("Lat. Real", max_length=30, blank=True)
    actual_longitude = models.CharField("Long. Real", max_length=30, blank=True)
    delivery_gap_distance = models.CharField("Gap Distância", max_length=30, blank=True)
    # Tempos
    creation_time = models.DateTimeField("Criação", null=True, blank=True)
    receipt_time = models.DateTimeField("Receção", null=True, blank=True)
    outbound_time = models.DateTimeField("Saída", null=True, blank=True)
    start_delivery_time = models.DateTimeField("Início Entrega", null=True, blank=True)
    delivery_time = models.DateTimeField("Delivery Time", null=True, blank=True, db_index=True)
    delivery_failure_time = models.DateTimeField("Falha Entrega", null=True, blank=True)
    # Exceções
    exception_type = models.CharField("Tipo Exceção", max_length=100, blank=True)
    exception_detail = models.TextField("Detalhe Exceção", blank=True)
    # Física
    weight_g = models.FloatField("Peso (g)", null=True, blank=True)
    length = models.FloatField("Comprimento", null=True, blank=True)
    width = models.FloatField("Largura", null=True, blank=True)
    height = models.FloatField("Altura", null=True, blank=True)
    # Outros
    seller_name = models.CharField("Seller Name", max_length=200, blank=True)
    zone = models.CharField("Zone", max_length=100, blank=True)
    original_plan_task_date = models.CharField("Original Plan Date", max_length=30, blank=True)
    sign_pod = models.CharField("Sign POD", max_length=200, blank=True)
    pudo_address = models.CharField("PUDO Address", max_length=300, blank=True)
    task_id = models.CharField("Task ID", max_length=100, blank=True)
    # Campos extra do Cainiao Tracking/Planning (nem sempre presentes)
    is_priority_external = models.BooleanField(
        "Priority (Cainiao)", default=False, db_index=True,
        help_text="Flag PRIORITYS=Yes vinda do Cainiao",
    )
    pre_assigned_driver = models.CharField(
        "Pre-assigned driver", max_length=200, blank=True,
    )
    pre_allocated_dsp = models.CharField(
        "Pre-allocated DSP", max_length=200, blank=True,
    )
    wrong_hub_parcel = models.BooleanField(
        "Wrong HUB Parcel", default=False,
    )
    arrive_wrong_hub = models.BooleanField(
        "Arrive Wrong Hub", default=False,
    )
    commercial_area = models.CharField(
        "Commercial Area", max_length=100, blank=True,
    )
    hub_exception_reason = models.CharField(
        "HUB Exception Reason", max_length=255, blank=True,
    )
    bigbag_number = models.CharField(
        "Bigbag No.", max_length=100, blank=True,
    )
    task_plan_date = models.DateField(
        "Task Plan Date", null=True, blank=True, db_index=True,
    )
    last_import_batch = models.ForeignKey(
        CainiaoOperationBatch, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="tasks",
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        verbose_name = "Tarefa Operation Cainiao"
        verbose_name_plural = "Tarefas Operation Cainiao"
        unique_together = [("waybill_number", "task_date")]
        indexes = [
            models.Index(fields=["task_date", "task_status"]),
            models.Index(fields=["courier_name", "task_date"]),
            models.Index(fields=["zip_code"]),
            models.Index(
                fields=["is_priority_external", "task_status"],
            ),
        ]

    def __str__(self):
        return f"{self.waybill_number} [{self.task_status}] {self.task_date}"


class CainiaoOperationTaskHistory(models.Model):
    """Histórico de mudanças por waybill — preserva a timeline operacional.

    Cada entry representa um snapshot de mudança detectada num import:
        - status mudou (ex: Driver_received → Delivered)
        - courier mudou (ex: ARMAZEM XPT → Driver A → Driver B)
        - task_date mudou (smart_date moveu para outra data)
        - Stale cleanup (tarefa marcou como Stale_Armazem)

    Use case principal: backlog operacional. Quando um pacote é entregue ao
    Driver A, devolvido, e re-atribuído ao Driver B, o history regista cada
    transição para auditoria e recuperação de operação.
    """

    waybill_number = models.CharField(max_length=100, db_index=True)

    # Snapshot do estado APÓS a mudança
    task_date = models.DateField()
    task_status = models.CharField(max_length=50, blank=True)
    courier_name = models.CharField(max_length=200, blank=True)
    courier_id_cainiao = models.CharField(max_length=50, blank=True)

    # Snapshot do estado ANTES da mudança (NULL se for criação)
    previous_task_date = models.DateField(null=True, blank=True)
    previous_task_status = models.CharField(max_length=50, blank=True)
    previous_courier_name = models.CharField(max_length=200, blank=True)

    # Tipo de mudança
    CHANGE_TYPES = [
        ("created",         "Criação"),
        ("status_change",   "Mudança de Status"),
        ("courier_change",  "Mudança de Courier"),
        ("date_move",       "Movido para nova data"),
        ("stale_cleanup",   "Marcado como Stale"),
        ("manual_edit",     "Edição manual"),
        ("signature",       "Assinatura (linha da planilha)"),
        ("rolled_forward",  "Roll-forward (pacote ainda activo)"),
    ]
    change_type = models.CharField(
        max_length=30, choices=CHANGE_TYPES, db_index=True,
    )

    # Quando o evento ocorreu na realidade (do Cainiao) — last_event_ts da row
    event_timestamp = models.DateTimeField(null=True, blank=True, db_index=True)
    # Quando foi importado/registado
    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)

    # Origem (qual import trouxe esta mudança)
    batch = models.ForeignKey(
        CainiaoOperationBatch,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="history_entries",
    )

    class Meta:
        verbose_name = "Histórico de Tarefa Cainiao"
        verbose_name_plural = "Histórico de Tarefas Cainiao"
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["waybill_number", "-recorded_at"]),
            models.Index(fields=["change_type", "-recorded_at"]),
        ]

    def __str__(self):
        return (
            f"{self.waybill_number} [{self.change_type}] "
            f"{self.previous_task_status or '∅'}→{self.task_status} "
            f"@ {self.recorded_at:%Y-%m-%d %H:%M}"
        )


# ============================================================================
# CAINIAO — PLANILHA DRIVER STATISTIC (resumo por motorista)
# ============================================================================

class CainiaoDriverStatBatch(models.Model):
    """Registo de um import da planilha Driver Statistic."""
    filename = models.CharField("Ficheiro", max_length=255)
    dispatch_date_range = models.CharField("Período", max_length=50, blank=True)
    total_couriers = models.PositiveIntegerField("Total Couriers", default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cainiao_driverstat_imports",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Import Driver Stat Cainiao"
        verbose_name_plural = "Imports Driver Stat Cainiao"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Driver Stat {self.dispatch_date_range} ({self.total_couriers} couriers)"


class CainiaoDriverStat(models.Model):
    """Estatística de um courier — planilha Driver Statistic (8 colunas)."""

    batch = models.ForeignKey(
        CainiaoDriverStatBatch, on_delete=models.CASCADE,
        related_name="stats",
    )
    courier_id = models.CharField("Courier ID", max_length=100, db_index=True)
    courier_name = models.CharField("Courier Name", max_length=200, db_index=True)
    dsp_name = models.CharField("DSP Name", max_length=200, blank=True)
    total_parcels = models.PositiveIntegerField("Total Parcels", default=0)
    delivery_success_rate = models.CharField("Success Rate", max_length=20, blank=True)
    signed_parcels = models.PositiveIntegerField("Signed Parcels", default=0)
    courier_status = models.CharField("Courier Status", max_length=20, blank=True)
    dispatch_date = models.CharField("Dispatch Date", max_length=50, blank=True)

    class Meta:
        verbose_name = "Stat Courier Cainiao"
        verbose_name_plural = "Stats Couriers Cainiao"
        unique_together = [("batch", "courier_id")]
        indexes = [
            models.Index(fields=["courier_id"]),
            models.Index(fields=["courier_name"]),
        ]

    def __str__(self):
        return f"{self.courier_name} — {self.total_parcels} pacotes ({self.delivery_success_rate})"


# ============================================================================
# CAINIAO — PLANILHA DRIVER DETAIL (detalhe de entrega por pacote/motorista)
# ============================================================================

class CainiaoDriverDetailBatch(models.Model):
    """Registo de um import da planilha Driver Detail Info."""
    filename = models.CharField("Ficheiro", max_length=255)
    report_date = models.DateField("Data do Relatório", db_index=True)
    total_records = models.PositiveIntegerField("Total Registos", default=0)
    new_records = models.PositiveIntegerField("Registos Novos", default=0)
    updated_records = models.PositiveIntegerField("Registos Atualizados", default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cainiao_driverdetail_imports",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Import Driver Detail Cainiao"
        verbose_name_plural = "Imports Driver Detail Cainiao"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Driver Detail {self.report_date} ({self.total_records} registos)"


class CainiaoDriverDetailRecord(models.Model):
    """Detalhe de entrega por pacote — planilha Driver Detail Info (16 colunas)."""

    batch = models.ForeignKey(
        CainiaoDriverDetailBatch, on_delete=models.CASCADE,
        related_name="records",
    )
    courier_id = models.CharField("Courier ID", max_length=100, db_index=True)
    courier_name = models.CharField("Courier Name", max_length=200, db_index=True)
    courier_helper = models.CharField("Courier Helper", max_length=200, blank=True)
    courier_telephone = models.CharField("Telefone", max_length=50, blank=True)
    courier_status = models.CharField("Courier Status", max_length=20, blank=True)
    dsp_name = models.CharField("DSP Name", max_length=200, blank=True)
    lp_number = models.CharField("LP No.", max_length=100, blank=True, db_index=True)
    waybill_number = models.CharField("Waybill Number", max_length=100, db_index=True)
    task_status = models.CharField("Task Status", max_length=50, blank=True, db_index=True)
    delivery_time = models.DateTimeField("Delivery Time", null=True, blank=True)
    delivery_failure_time = models.DateTimeField("Delivery Failure Time", null=True, blank=True)
    exception_type = models.CharField("Exception Type", max_length=100, blank=True)
    exception_detail = models.TextField("Exception Detail", blank=True)
    weight_g = models.FloatField("Weight (g)", null=True, blank=True)
    delivery_type = models.CharField("Delivery Type", max_length=50, blank=True)
    pudo_locker_id = models.CharField("PUDO/Locker ID", max_length=100, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        verbose_name = "Detalhe Driver Cainiao"
        verbose_name_plural = "Detalhes Driver Cainiao"
        unique_together = [("batch", "waybill_number")]
        indexes = [
            models.Index(fields=["courier_id", "task_status"]),
            models.Index(fields=["waybill_number"]),
            models.Index(fields=["courier_name"]),
        ]

    def __str__(self):
        return f"{self.courier_name} / {self.waybill_number} [{self.task_status}]"


# ---------------------------------------------------------------------------
# HUBs Cainiao
# ---------------------------------------------------------------------------

class CainiaoHub(models.Model):
    """HUB operacional Cainiao (ex: Viana do Castelo, Aveiro)."""

    name = models.CharField("Nome do HUB", max_length=100, unique=True)
    address = models.CharField("Endereço", max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "HUB Cainiao"
        verbose_name_plural = "HUBs Cainiao"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def cp4_list(self):
        return list(self.cp4_codes.values_list("cp4", flat=True).order_by("cp4"))


class CainiaoHubCP4(models.Model):
    """CP4 pertencente a um HUB Cainiao."""

    hub = models.ForeignKey(
        CainiaoHub, on_delete=models.CASCADE, related_name="cp4_codes"
    )
    cp4 = models.CharField("Código CP4", max_length=4, db_index=True)

    class Meta:
        verbose_name = "CP4 do HUB"
        verbose_name_plural = "CP4s do HUB"
        unique_together = [("hub", "cp4")]
        ordering = ["cp4"]

    def __str__(self):
        return f"{self.hub.name} / {self.cp4}"


# ============================================================================
# FASE 1b — NOVOS MODELOS DO SISTEMA FINANCEIRO COMPLETO
# ============================================================================


class PreInvoiceAuditLog(models.Model):
    """Timeline / auditoria de alterações numa pré-fatura (Fase 8.10)."""

    ACTION_CHOICES = [
        ("CREATED",   "Criada"),
        ("EDITED",    "Editada"),
        ("LINE_ADD",  "Linha adicionada"),
        ("LINE_EDIT", "Linha editada"),
        ("LINE_DEL",  "Linha removida"),
        ("PRICE_OVR", "Preço alterado"),
        ("APPROVED",  "Aprovada"),
        ("REJECTED",  "Rejeitada"),
        ("SIGNED",    "Aceite por motorista"),
        ("PAID",      "Paga"),
        ("RECEIPT",   "Comprovativo anexado"),
        ("WHATSAPP",  "Enviada via WhatsApp"),
    ]

    pre_invoice = models.ForeignKey(
        DriverPreInvoice, on_delete=models.CASCADE, related_name="audit_logs",
    )
    action = models.CharField("Acção", max_length=15, choices=ACTION_CHOICES, db_index=True)
    summary = models.CharField("Resumo", max_length=250, blank=True)
    diff = models.JSONField("Detalhes", default=dict, blank=True)
    user = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="pre_invoice_audit_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Log de Auditoria da Pré-Fatura"
        verbose_name_plural = "Logs de Auditoria das Pré-Faturas"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.pre_invoice.numero} · {self.get_action_display()} @ {self.created_at:%d/%m %H:%M}"


class PreInvoicePriceOverride(models.Model):
    """Override granular de preço numa pré-fatura (Fase 5).

    Scope: LINE | WAYBILL | DAY_RANGE | ZONE (CP4).
    Fica registado quem e porquê (auditoria).
    """

    SCOPE_CHOICES = [
        ("LINE",      "Linha de trabalho"),
        ("WAYBILL",   "Waybill específico"),
        ("DAY_RANGE", "Período (dias)"),
        ("ZONE",      "Zona (CP4)"),
    ]

    pre_invoice = models.ForeignKey(
        DriverPreInvoice, on_delete=models.CASCADE, related_name="price_overrides",
    )
    scope = models.CharField("Escopo", max_length=15, choices=SCOPE_CHOICES, db_index=True)
    # Identificadores do scope
    line = models.ForeignKey(
        "PreInvoiceLine", on_delete=models.CASCADE, null=True, blank=True,
        related_name="overrides",
    )
    waybill_number = models.CharField(max_length=100, blank=True, db_index=True)
    date_from = models.DateField(null=True, blank=True)
    date_to = models.DateField(null=True, blank=True)
    cp4 = models.CharField(max_length=4, blank=True, db_index=True)

    # Override
    new_price = models.DecimalField(
        "Novo Preço por Pacote (€)", max_digits=10, decimal_places=4,
    )
    reason = models.TextField("Justificação", blank=True)

    # Auditoria
    created_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_price_overrides",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Override de Preço"
        verbose_name_plural = "Overrides de Preço"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["pre_invoice", "scope"]),
        ]

    def __str__(self):
        return f"{self.get_scope_display()} · €{self.new_price}"


class PerformanceBonusRule(models.Model):
    """Regra configurável de bónus/penalty por performance (Fase 7).

    Ligada a um Partner (cascata a todos os drivers) e opcionalmente
    restringível a Frotas específicas.
    """

    CONDITION_CHOICES = [
        ("SUCCESS_RATE_GTE", "Taxa sucesso ≥ X%"),
        ("VOLUME_GTE",       "Volume ≥ X pacotes"),
        ("FAIL_RATE_LTE",    "Taxa falha ≤ X%"),
        ("SPECIAL_DAY",      "Dia especial (domingo/feriado)"),
    ]
    EFFECT_CHOICES = [
        ("PCT_BONUS",   "% bónus sobre base"),
        ("FIXED_BONUS", "Valor fixo em €"),
        ("PCT_PENALTY", "% penalização sobre base"),
        ("FIXED_PENALTY", "Penalização fixa em €"),
    ]
    SCOPE_CHOICES = [
        ("WEEKLY",  "Semanal"),
        ("MONTHLY", "Mensal"),
        ("DAILY",   "Diário"),
    ]

    partner = models.ForeignKey(
        "core.Partner", on_delete=models.CASCADE, related_name="bonus_rules",
    )
    name = models.CharField("Nome", max_length=120)
    enabled = models.BooleanField("Activo", default=True)
    condition = models.CharField("Condição", max_length=20, choices=CONDITION_CHOICES)
    condition_value = models.DecimalField(
        "Valor da condição", max_digits=8, decimal_places=2, default=0,
        help_text="Ex: 95 (taxa sucesso ≥ 95%) ou 200 (volume ≥ 200 pacotes).",
    )
    effect = models.CharField("Efeito", max_length=20, choices=EFFECT_CHOICES)
    effect_value = models.DecimalField(
        "Valor do efeito", max_digits=10, decimal_places=2, default=0,
        help_text="Ex: 10 (10% bónus) ou 30.00 (30€ fixo).",
    )
    scope_period = models.CharField(
        "Período", max_length=10, choices=SCOPE_CHOICES, default="WEEKLY",
    )
    applies_to_fleets_only = models.BooleanField(
        "Só frotas", default=False,
        help_text="Se activo, a regra só se aplica a motoristas com frota (Empresa Parceira).",
    )
    applies_to_independent_only = models.BooleanField(
        "Só independentes", default=False,
        help_text="Se activo, a regra só se aplica a motoristas directos (sem frota).",
    )
    notes = models.TextField("Notas", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Regra de Bónus/Penalty"
        verbose_name_plural = "Regras de Bónus/Penalty"
        ordering = ["partner", "name"]

    def __str__(self):
        return f"[{self.partner.name}] {self.name}"


class OperationalCost(models.Model):
    """Custos operacionais recorrentes descontados automaticamente (Fase 8.6).

    Aplica-se a um Driver ou a uma Frota (Empresa Parceira).
    Pode ser fixo por período ou % do bruto.
    """

    KIND_CHOICES = [
        ("CARRINHA",    "Renda de Carrinha"),
        ("COMBUSTIVEL", "Combustível"),
        ("SEGURO",      "Seguro"),
        ("MANUTENCAO",  "Manutenção"),
        ("OUTRO",       "Outro"),
    ]
    MODE_CHOICES = [
        ("FIXED",   "Fixo (€)"),
        ("PCT",     "% do bruto"),
        ("PER_KM",  "Por km percorrido"),
    ]
    PERIOD_CHOICES = [
        ("WEEKLY",  "Semanal"),
        ("MONTHLY", "Mensal"),
        ("DAILY",   "Diário"),
        ("ONESHOT", "Avulso (uma vez)"),
    ]

    driver = models.ForeignKey(
        "drivers_app.DriverProfile", on_delete=models.CASCADE,
        null=True, blank=True, related_name="operational_costs",
    )
    fleet = models.ForeignKey(
        "drivers_app.EmpresaParceira", on_delete=models.CASCADE,
        null=True, blank=True, related_name="operational_costs",
    )
    kind = models.CharField("Tipo", max_length=20, choices=KIND_CHOICES, db_index=True)
    description = models.CharField("Descrição", max_length=200, blank=True)
    mode = models.CharField("Modo", max_length=10, choices=MODE_CHOICES, default="FIXED")
    amount = models.DecimalField("Valor", max_digits=10, decimal_places=2)
    period = models.CharField("Período", max_length=10, choices=PERIOD_CHOICES, default="MONTHLY")
    active_from = models.DateField("Activo desde", default=timezone.now)
    active_until = models.DateField("Activo até", null=True, blank=True)
    enabled = models.BooleanField("Activo", default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Custo Operacional"
        verbose_name_plural = "Custos Operacionais"
        ordering = ["driver", "fleet", "-active_from"]

    def __str__(self):
        target = self.driver.nome_completo if self.driver else (
            self.fleet.nome if self.fleet else "—")
        return f"{self.get_kind_display()} · {target} · €{self.amount}"


class FinancialAlert(models.Model):
    """Alertas financeiros automáticos (Fase 8.8).

    Gerados por tasks Celery e mostrados no dashboard.
    """

    LEVEL_CHOICES = [
        ("INFO",    "Informação"),
        ("WARN",    "Aviso"),
        ("DANGER",  "Crítico"),
    ]
    KIND_CHOICES = [
        ("PAYMENT_OVERDUE",   "Pagamento em atraso"),
        ("ADVANCE_OVER_LIMIT", "Limite de adiantamentos excedido"),
        ("CLAIM_PENDING",     "Claim pendente há muitos dias"),
        ("NO_PREINVOICE",     "Motorista sem pré-fatura"),
        ("LOW_SUCCESS_RATE",  "Taxa de sucesso baixa"),
        ("OTHER",             "Outro"),
    ]

    level = models.CharField("Nível", max_length=10, choices=LEVEL_CHOICES, default="WARN")
    kind = models.CharField("Tipo", max_length=30, choices=KIND_CHOICES, db_index=True)
    title = models.CharField("Título", max_length=200)
    description = models.TextField("Descrição", blank=True)

    # Scope (opcional) — pode referir-se a um motorista, frota, parceiro, pré-fatura
    driver = models.ForeignKey(
        "drivers_app.DriverProfile", on_delete=models.CASCADE,
        null=True, blank=True, related_name="financial_alerts",
    )
    fleet = models.ForeignKey(
        "drivers_app.EmpresaParceira", on_delete=models.CASCADE,
        null=True, blank=True, related_name="financial_alerts",
    )
    partner = models.ForeignKey(
        "core.Partner", on_delete=models.CASCADE,
        null=True, blank=True, related_name="financial_alerts",
    )
    pre_invoice = models.ForeignKey(
        DriverPreInvoice, on_delete=models.CASCADE,
        null=True, blank=True, related_name="financial_alerts",
    )

    resolved = models.BooleanField("Resolvido", default=False, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="resolved_financial_alerts",
    )
    resolution_notes = models.TextField("Notas de Resolução", blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Alerta Financeiro"
        verbose_name_plural = "Alertas Financeiros"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["resolved", "-created_at"]),
            models.Index(fields=["level", "resolved"]),
        ]

    def __str__(self):
        return f"[{self.get_level_display()}] {self.title}"


class CourierNameAlias(models.Model):
    """Mapeamento persistente courier_name → courier_id por parceiro.

    Garante que entregas com nomes históricos (renomeados no painel do
    parceiro) mantenham a ligação ao Login ID correcto através de
    re-imports. Cada manual mapping cria/actualiza um alias; cada
    Driver Statistic import preserva o nome antigo antes de mudar
    DriverCourierMapping.courier_name.
    """
    SOURCE_CHOICES = [
        ("manual", "Manual"),
        ("import", "Import"),
        ("auto", "Auto"),
    ]

    partner = models.ForeignKey(
        "core.Partner", on_delete=models.CASCADE,
        related_name="courier_name_aliases",
    )
    courier_name = models.CharField(max_length=255, db_index=True)
    courier_id = models.CharField(max_length=64, db_index=True)
    source = models.CharField(
        max_length=20, choices=SOURCE_CHOICES, default="auto",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Alias de Courier Name"
        verbose_name_plural = "Aliases de Courier Name"
        unique_together = [("partner", "courier_name")]
        indexes = [
            models.Index(fields=["partner", "courier_name"]),
            models.Index(fields=["partner", "courier_id"]),
        ]

    def __str__(self):
        return f"{self.partner.name} / {self.courier_name!r} → {self.courier_id}"


class Holiday(models.Model):
    """Feriado (nacional, regional ou customizado).

    Usado pelo motor de bonificação de pré-faturas para identificar dias
    com bónus (domingo já é detectado pelo dia da semana). Suporta
    feriados recorrentes anuais (data fixa, ex: 25/12) e datas únicas
    (ex: feriados móveis com data específica num ano).
    """
    SCOPE_CHOICES = [
        ("national", "Nacional"),
        ("regional", "Regional"),
        ("custom",   "Customizado"),
    ]

    name = models.CharField("Nome", max_length=120)
    date = models.DateField("Data", db_index=True)
    is_recurring_yearly = models.BooleanField(
        "Repete anualmente",
        default=False,
        help_text=(
            "Se ativo, aplica em todos os anos no mesmo dia/mês "
            "(ex: 25/12). Para datas móveis (ex: Páscoa) deixar inativo "
            "e adicionar uma entrada por ano."
        ),
    )
    scope = models.CharField(
        "Tipo", max_length=20, choices=SCOPE_CHOICES, default="national",
    )
    region = models.CharField(
        "Região",
        max_length=80, blank=True,
        help_text=(
            "Aplica apenas a uma região (ex: 'Aveiro'). Vazio = aplica a "
            "todos os drivers/parceiros."
        ),
    )
    notes = models.CharField("Notas", max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Feriado"
        verbose_name_plural = "Feriados / Calendário"
        ordering = ["date"]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["is_recurring_yearly"]),
        ]

    def __str__(self):
        suffix = " (anual)" if self.is_recurring_yearly else ""
        return f"{self.date.strftime('%d/%m/%Y')} — {self.name}{suffix}"

    @classmethod
    def is_holiday(cls, target_date, region=None):
        """Verifica se uma data é feriado.

        Match prioritário:
          1. Entrada exata (date == target_date)
          2. Entrada recorrente anual (mesmo dia/mês)

        Se region for fornecida, inclui feriados regionais que casam.
        """
        from django.db.models import Q
        q = (
            Q(date=target_date) |
            Q(is_recurring_yearly=True,
              date__day=target_date.day,
              date__month=target_date.month)
        )
        qs = cls.objects.filter(q)
        if region:
            qs = qs.filter(Q(region="") | Q(region__iexact=region))
        else:
            qs = qs.filter(region="")
        return qs.exists()

    @classmethod
    def get_holiday(cls, target_date, region=None):
        """Retorna a entrada Holiday se a data for feriado, ou None."""
        from django.db.models import Q
        q = (
            Q(date=target_date) |
            Q(is_recurring_yearly=True,
              date__day=target_date.day,
              date__month=target_date.month)
        )
        qs = cls.objects.filter(q)
        if region:
            qs = qs.filter(Q(region="") | Q(region__iexact=region))
        else:
            qs = qs.filter(region="")
        return qs.first()


class BonusBlackoutDate(models.Model):
    """Datas em que NÃO há bonificação, mesmo sendo domingo/feriado.

    Cada entrada bloqueia uma data específica (ano-mês-dia). Se a data
    cair num feriado anual recorrente (ex: 25/12) o bloqueio aplica-se
    apenas àquele ano. Para bloquear permanentemente, criar uma entrada
    por ano.
    """
    date = models.DateField("Data", unique=True, db_index=True)
    reason = models.CharField(
        "Motivo", max_length=255, blank=True,
        help_text="Razão do bloqueio (ex: 'feriado mas operação reduzida').",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="bonus_blackouts_created",
    )

    class Meta:
        verbose_name = "Bloqueio de Bonificação"
        verbose_name_plural = "Bloqueios de Bonificação"
        ordering = ["-date"]

    def __str__(self):
        return f"{self.date.strftime('%d/%m/%Y')} — {self.reason or 'sem bonus'}"

    @classmethod
    def is_blocked(cls, target_date):
        """True se a data está marcada como sem bonificação."""
        return cls.objects.filter(date=target_date).exists()

    @classmethod
    def dates_in_range(cls, start_date, end_date):
        """Set de datas bloqueadas no intervalo (inclusive). Usar para evitar N queries."""
        return set(cls.objects.filter(
            date__gte=start_date, date__lte=end_date,
        ).values_list("date", flat=True))


# ════════════════════════════════════════════════════════════════════════
# FASE 6.2 (REFACTOR) — Pré-fatura GLOBAL da frota
# ════════════════════════════════════════════════════════════════════════
# Um único documento FleetInvoice por emissão de uma frota num período.
# Internamente tem N linhas (uma por motorista), e cada linha pode ter
# detalhe de bónus dias e claims. PDF master gera 1 documento legível
# para o parceiro pagar a frota inteira.

class FleetInvoice(models.Model):
    """Pré-fatura GLOBAL emitida a uma EmpresaParceira (frota).

    Uma fatura única que agrega todos os motoristas activos da frota
    no período, com detalhe por driver. É o que o parceiro paga à frota
    (e a frota distribui pelos motoristas).
    """
    STATUS_CHOICES = [
        ("RASCUNHO",  "Rascunho"),
        ("CALCULADO", "Calculado"),
        ("APROVADO",  "Aprovado"),
        ("PAGO",      "Pago"),
        ("CANCELADO", "Cancelado"),
    ]
    TRANSICOES = {
        "RASCUNHO":  ["CALCULADO", "CANCELADO"],
        "CALCULADO": ["APROVADO", "RASCUNHO", "CANCELADO"],
        "APROVADO":  ["PAGO", "CALCULADO", "CANCELADO"],
        "PAGO":      ["CANCELADO"],
        "CANCELADO": [],
    }

    numero = models.CharField(
        "Número", max_length=20, unique=True,
        help_text="Ex: FF-0001 (Frota)",
    )
    empresa = models.ForeignKey(
        "drivers_app.EmpresaParceira", on_delete=models.PROTECT,
        related_name="fleet_invoices",
    )
    periodo_inicio = models.DateField("Período Início", db_index=True)
    periodo_fim = models.DateField("Período Fim", db_index=True)

    # Snapshot do preço cobrado (Léguas → Parceiro paga este valor)
    partner_price_per_package = models.DecimalField(
        "Preço cobrado ao Parceiro (€/pacote)",
        max_digits=8, decimal_places=4, default=Decimal("0"),
    )

    # Totais (calculados)
    total_deliveries = models.PositiveIntegerField(default=0)
    total_base = models.DecimalField(
        "Total Base (entregas)",
        max_digits=10, decimal_places=2, default=Decimal("0"),
    )
    total_bonus = models.DecimalField(
        "Total Bónus", max_digits=10, decimal_places=2,
        default=Decimal("0"),
    )
    total_claims = models.DecimalField(
        "Total Claims (descontos)",
        max_digits=10, decimal_places=2, default=Decimal("0"),
    )
    total_a_receber = models.DecimalField(
        "Total a Receber pela frota",
        max_digits=10, decimal_places=2, default=Decimal("0"),
    )

    status = models.CharField(
        "Estado", max_length=20, choices=STATUS_CHOICES,
        default="CALCULADO", db_index=True,
    )
    data_pagamento = models.DateField(null=True, blank=True)
    referencia_pagamento = models.CharField(max_length=100, blank=True)

    observacoes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="fleet_invoices_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pré-fatura Frota"
        verbose_name_plural = "Pré-faturas Frota"
        ordering = ["-periodo_fim", "-id"]
        indexes = [
            models.Index(fields=["empresa", "-periodo_fim"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.numero} — {self.empresa.nome}"

    def recalcular(self):
        """Recalcula os totais a partir das linhas."""
        from django.db.models import Sum
        agg = self.lines.aggregate(
            d=Sum("deliveries"),
            b=Sum("base_amount"),
            bn=Sum("bonus_amount"),
            cl=Sum("claims_amount"),
        )
        self.total_deliveries = agg["d"] or 0
        self.total_base = agg["b"] or Decimal("0")
        self.total_bonus = agg["bn"] or Decimal("0")
        self.total_claims = agg["cl"] or Decimal("0")
        self.total_a_receber = (
            self.total_base + self.total_bonus - self.total_claims
        )
        self.save(update_fields=[
            "total_deliveries", "total_base", "total_bonus",
            "total_claims", "total_a_receber", "updated_at",
        ])

    # ── IVA (calculado dinamicamente a partir de empresa.taxa_iva) ──
    # As frotas (Empresas Parceiras) cobram sempre IVA — é obrigatório
    # por serem pessoas colectivas. A taxa é guardada no modelo da
    # empresa (default 23%). Não persistimos vat_amount aqui para
    # evitar uma migration; é trivial calcular on-demand.
    @property
    def vat_rate(self):
        return getattr(self.empresa, "taxa_iva", Decimal("23.00")) or Decimal("0")

    @property
    def vat_amount(self):
        rate = self.vat_rate
        if not rate:
            return Decimal("0.00")
        return (
            self.total_a_receber * rate / Decimal("100")
        ).quantize(Decimal("0.01"))

    @property
    def total_com_iva(self):
        return self.total_a_receber + self.vat_amount


class FleetInvoiceDriverLine(models.Model):
    """Linha por motorista dentro de uma FleetInvoice."""
    fleet_invoice = models.ForeignKey(
        FleetInvoice, on_delete=models.CASCADE, related_name="lines",
    )
    driver = models.ForeignKey(
        "drivers_app.DriverProfile", on_delete=models.PROTECT,
        related_name="+",
    )

    # Snapshots (mesmo que driver/courier mudem depois, fica registado)
    driver_name_snapshot = models.CharField(max_length=200, blank=True)
    courier_id_snapshot = models.CharField(max_length=64, blank=True)
    courier_name_snapshot = models.CharField(max_length=200, blank=True)

    # Quantidades
    deliveries = models.PositiveIntegerField(default=0)

    # Preço efectivo aplicado (snapshot da cascata)
    price_per_package = models.DecimalField(
        max_digits=8, decimal_places=4, default=Decimal("0"),
    )
    price_source = models.CharField(
        max_length=20, blank=True,
        help_text="driver_override / fleet_default / partner_default / none",
    )

    # Componentes do total
    base_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0"),
    )
    bonus_days_count = models.PositiveSmallIntegerField(default=0)
    bonus_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0"),
    )
    claims_count = models.PositiveSmallIntegerField(default=0)
    claims_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0"),
    )
    subtotal = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0"),
    )

    observacoes = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name = "Linha por Driver (FleetInvoice)"
        verbose_name_plural = "Linhas por Driver (FleetInvoice)"
        ordering = ["-deliveries"]

    def __str__(self):
        return f"{self.driver_name_snapshot}: {self.deliveries} entregas"

    def recalc_subtotal(self):
        self.subtotal = (
            self.base_amount + self.bonus_amount - self.claims_amount
        )


class FleetInvoiceBonusDay(models.Model):
    """Detalhe de cada dia bonificado dentro de uma linha por driver."""
    line = models.ForeignKey(
        FleetInvoiceDriverLine, on_delete=models.CASCADE,
        related_name="bonus_days_detail",
    )
    data = models.DateField()
    tipo = models.CharField(
        max_length=20,
        choices=[("DOMINGO", "Domingo"), ("FERIADO", "Feriado")],
    )
    deliveries = models.PositiveIntegerField()
    bonus = models.DecimalField(max_digits=8, decimal_places=2)
    feriado_nome = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["data"]


class ForecastPlan(models.Model):
    """Plano de distribuição de drivers por CP4 para um dia/HUB.

    Representa a "escala" prevista — o operador atribui drivers a CP4s
    antes do dia começar para visualização/preparação. Pode ser DRAFT
    (rascunho) ou PUBLISHED (publicado e enviado aos drivers).
    """
    STATUS_DRAFT = "DRAFT"
    STATUS_PUBLISHED = "PUBLISHED"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Rascunho"),
        (STATUS_PUBLISHED, "Publicado"),
    ]

    operation_date = models.DateField(
        "Data da Operação", db_index=True,
    )
    hub = models.ForeignKey(
        "CainiaoHub", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="forecast_plans",
    )
    status = models.CharField(
        "Estado", max_length=20,
        choices=STATUS_CHOICES, default=STATUS_DRAFT,
        db_index=True,
    )
    notes = models.TextField("Notas", blank=True)
    notify_on_publish = models.BooleanField(
        "Notificar drivers ao publicar", default=False,
    )
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )
    created_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="forecast_plans_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plano de Distribuição"
        verbose_name_plural = "Planos de Distribuição"
        ordering = ["-operation_date", "-id"]
        # Uma frota plano por (data, hub) — facilita o "open or create"
        unique_together = [("operation_date", "hub")]

    def __str__(self):
        hub = f" · {self.hub.name}" if self.hub else ""
        return (
            f"Plano {self.operation_date}{hub} "
            f"[{self.get_status_display()}]"
        )


class ForecastPlanAssignment(models.Model):
    """Linha individual: parte de um CP4 alocada a um driver, frota ou
    nome manual. Permite que vários assignees partilhem o mesmo CP4.
    """
    plan = models.ForeignKey(
        ForecastPlan, on_delete=models.CASCADE,
        related_name="assignments",
    )
    cp4 = models.CharField(max_length=4, db_index=True)
    driver = models.ForeignKey(
        "drivers_app.DriverProfile", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="forecast_assignments",
    )
    fleet = models.ForeignKey(
        "drivers_app.EmpresaParceira", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="forecast_assignments",
        help_text="Frota inteira que recebe este CP4 (ex: subcontratada).",
    )
    manual_name = models.CharField(
        "Nome manual", max_length=120, blank=True,
        help_text=(
            "Usado quando o driver não está cadastrado (ex: 'João Temp')."
        ),
    )
    qty = models.PositiveIntegerField("Qtd. atribuída", default=0)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Atribuição (Plano)"
        verbose_name_plural = "Atribuições (Plano)"
        ordering = ["cp4", "-qty"]
        indexes = [
            models.Index(fields=["plan", "cp4"]),
            models.Index(fields=["driver"]),
            models.Index(fields=["fleet"]),
        ]

    def __str__(self):
        who = (
            self.manual_name or
            (self.driver.nome_completo if self.driver else None) or
            (self.fleet.nome if self.fleet else "?")
        )
        return f"CP4 {self.cp4} → {who} ({self.qty})"

    @property
    def display_name(self):
        if self.manual_name:
            return self.manual_name
        if self.driver:
            return self.driver.apelido or self.driver.nome_completo
        if self.fleet:
            return self.fleet.nome
        return "—"

    @property
    def assignee_kind(self):
        """driver | fleet | manual"""
        if self.driver_id:
            return "driver"
        if self.fleet_id:
            return "fleet"
        return "manual"


class ForecastPlanCP4Skip(models.Model):
    """CP4 marcado como ignorado num plano (não dimensionar)."""
    plan = models.ForeignKey(
        ForecastPlan, on_delete=models.CASCADE,
        related_name="skipped_cp4s",
    )
    cp4 = models.CharField(max_length=4)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "CP4 ignorado (Plano)"
        verbose_name_plural = "CP4s ignorados (Plano)"
        unique_together = [("plan", "cp4")]

    def __str__(self):
        return f"Skip CP4 {self.cp4}"


class CainiaoManualForecast(models.Model):
    """Previsão manual de volume por CP4 e data.

    Usado quando o parceiro não envia ficheiro de forecast — apenas
    comunica volumes verbais por código (ex: "amanhã 4500 = 30 pacotes").
    Estes valores são SOMADOS aos do CainiaoPlanningPackage no modal
    "Previsão de Volume".
    """
    operation_date = models.DateField("Data da Operação", db_index=True)
    cp4 = models.CharField("CP4", max_length=4, db_index=True)
    qty = models.PositiveIntegerField("Quantidade")
    notes = models.CharField("Notas", max_length=255, blank=True)
    created_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Previsão Manual (Cainiao)"
        verbose_name_plural = "Previsões Manuais (Cainiao)"
        ordering = ["-operation_date", "cp4"]
        unique_together = [("operation_date", "cp4")]
        indexes = [
            models.Index(fields=["operation_date", "cp4"]),
        ]

    def __str__(self):
        return f"{self.operation_date} CP4 {self.cp4}: {self.qty}"


class FleetInvoiceClaim(models.Model):
    """Claim (pacote perdido) dentro de uma linha por driver."""
    line = models.ForeignKey(
        FleetInvoiceDriverLine, on_delete=models.CASCADE,
        related_name="claims_detail",
    )
    waybill_number = models.CharField(max_length=100, blank=True)
    valor = models.DecimalField(max_digits=8, decimal_places=2)
    descricao = models.CharField(max_length=300, blank=True)
    driver_claim = models.ForeignKey(
        "DriverClaim", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )


class FleetInvoiceAttachment(models.Model):
    """Anexos genéricos a uma FleetInvoice (fatura emitida pela frota,
    recibo de pagamento, notas, etc.)."""

    KIND_CHOICES = [
        ("FATURA", "Fatura emitida pela frota"),
        ("RECIBO", "Recibo de pagamento"),
        ("NOTA_CREDITO", "Nota de crédito"),
        ("OUTRO", "Outro"),
    ]

    fleet_invoice = models.ForeignKey(
        FleetInvoice,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    kind = models.CharField(
        "Tipo", max_length=20, choices=KIND_CHOICES, default="OUTRO",
        db_index=True,
    )
    file = models.FileField(
        "Ficheiro", upload_to="fleet_invoices/%Y/%m/",
    )
    description = models.CharField("Descrição", max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "Anexo de FleetInvoice"
        verbose_name_plural = "Anexos de FleetInvoice"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.get_kind_display()} — {self.fleet_invoice.numero}"

    @property
    def filename(self):
        import os
        return os.path.basename(self.file.name) if self.file else ""


# ============================================================================
# Resolução manual de pacotes Not Arrived
# ============================================================================
class WaybillResolution(models.Model):
    """Resolução manual de um pacote 'Not Arrived'.

    Permite registar que um pacote foi entregue por outro HUB, devolvido
    ao remetente, perdido, etc., sem precisar de importar a planilha
    do outro HUB. Quando existe uma resolução activa para um waybill,
    ele deixa de aparecer na lista de Not Arrived.
    """

    TYPE_DELIVERED_OTHER_HUB = "DELIVERED_OTHER_HUB"
    TYPE_RETURNED = "RETURNED"
    TYPE_LOST = "LOST"
    TYPE_DELIVERED_LATE = "DELIVERED_LATE"
    TYPE_AUTO_REIMPORT = "AUTO_REIMPORT"
    TYPE_OTHER = "OTHER"

    TYPE_CHOICES = [
        (TYPE_DELIVERED_OTHER_HUB, "Entregue por outro HUB"),
        (TYPE_DELIVERED_LATE, "Entregue tarde (sem reimport)"),
        (TYPE_RETURNED, "Devolvido ao remetente"),
        (TYPE_LOST, "Pacote perdido"),
        (TYPE_AUTO_REIMPORT, "Auto-resolvido (reimport)"),
        (TYPE_OTHER, "Outro"),
    ]

    waybill_number = models.CharField(
        "Waybill", max_length=100, db_index=True, unique=True,
    )
    resolution_type = models.CharField(
        "Tipo", max_length=30,
        choices=TYPE_CHOICES, default=TYPE_DELIVERED_OTHER_HUB,
    )
    resolved_at = models.DateTimeField(
        "Resolvido em", default=timezone.now,
    )
    other_hub = models.CharField(
        "HUB que entregou", max_length=100, blank=True,
    )
    other_courier = models.CharField(
        "Courier (outro HUB)", max_length=200, blank=True,
    )
    other_delivery_time = models.DateTimeField(
        "Data/hora de entrega real", null=True, blank=True,
    )
    notes = models.TextField("Notas", blank=True)
    resolved_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="waybill_resolutions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Resolução de Waybill"
        verbose_name_plural = "Resoluções de Waybills"
        ordering = ["-resolved_at"]
        indexes = [
            models.Index(fields=["resolution_type", "resolved_at"]),
        ]

    def __str__(self):
        return f"{self.waybill_number} → {self.get_resolution_type_display()}"


class WaybillComment(models.Model):
    """Thread de comentários por waybill (memória institucional).

    Útil para registar tentativas de contacto, respostas do Cainiao,
    ações tomadas etc. ao longo do tempo.
    """
    waybill_number = models.CharField(
        "Waybill", max_length=100, db_index=True,
    )
    body = models.TextField("Comentário")
    author = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="waybill_comments",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Comentário de Waybill"
        verbose_name_plural = "Comentários de Waybills"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.waybill_number} · {self.created_at:%Y-%m-%d}"


# ============================================================================
# Sinalização persistente de waybills
# ============================================================================
class WaybillFlag(models.Model):
    """Flag activo de um waybill (independente do cálculo dinâmico).

    Quando o gestor identifica que um pacote está em risco/perdido e
    quer rastreá-lo activamente, cria uma flag. A flag persiste até:
      - Ser limpa manualmente pelo gestor
      - Ser auto-limpa pelo signal quando o pacote reaparece picked
    """
    TYPE_NOT_ARRIVED = "NOT_ARRIVED"
    TYPE_SUSPECTED_LOST = "SUSPECTED_LOST"
    TYPE_NEEDS_INVESTIGATION = "NEEDS_INVESTIGATION"

    TYPE_CHOICES = [
        (TYPE_NOT_ARRIVED, "Not Arrived"),
        (TYPE_SUSPECTED_LOST, "Suspeita de perdido"),
        (TYPE_NEEDS_INVESTIGATION, "Necessita investigação"),
    ]

    REASON_CHOICES = [
        ("customer_reported", "Cliente reportou que não recebeu"),
        ("driver_lost", "Driver disse que perdeu"),
        ("suspected_return", "Suspeita de devolução não registada"),
        ("transferred_other_hub", "Transferido para outro HUB"),
        ("under_investigation", "Investigação em curso"),
        ("other", "Outro"),
    ]

    waybill_number = models.CharField(
        "Waybill", max_length=100, db_index=True,
    )
    flag_type = models.CharField(
        "Tipo", max_length=30,
        choices=TYPE_CHOICES, default=TYPE_NOT_ARRIVED,
    )
    reason = models.CharField(
        "Razão", max_length=40,
        choices=REASON_CHOICES, default="other",
    )
    notes = models.TextField("Notas", blank=True)
    flagged_at = models.DateTimeField(
        "Sinalizado em", default=timezone.now, db_index=True,
    )
    flagged_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="waybill_flags",
    )
    cleared_at = models.DateTimeField(
        "Limpo em", null=True, blank=True, db_index=True,
    )
    cleared_reason = models.CharField(
        "Razão de limpeza", max_length=255, blank=True,
    )
    auto_cleared = models.BooleanField(
        "Auto-limpo", default=False,
        help_text="True se foi limpo automaticamente pelo signal",
    )
    cleared_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="waybill_flags_cleared",
    )

    class Meta:
        verbose_name = "Flag de Waybill"
        verbose_name_plural = "Flags de Waybills"
        ordering = ["-flagged_at"]
        indexes = [
            models.Index(
                fields=["waybill_number", "cleared_at"],
            ),
            models.Index(fields=["flag_type", "cleared_at"]),
        ]

    def __str__(self):
        state = "ACTIVO" if self.cleared_at is None else "limpo"
        return (
            f"{self.waybill_number} · "
            f"{self.get_flag_type_display()} · {state}"
        )

    @property
    def is_active(self):
        return self.cleared_at is None


# ============================================================================
# Snapshots diários da lista Not Arrived (auditoria)
# ============================================================================
class NotArrivedSnapshot(models.Model):
    """Snapshot diário da lista Not Arrived. Usado para auditoria
    histórica — quando o armazém principal questiona, podemos provar
    o que estava sinalizado em qualquer dia passado.
    """
    snapshot_date = models.DateField(
        "Data do snapshot", db_index=True,
    )
    hub = models.ForeignKey(
        CainiaoHub, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="not_arrived_snapshots",
    )
    created_at = models.DateTimeField(
        "Gerado em", default=timezone.now,
    )
    created_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    is_automatic = models.BooleanField(
        "Automático", default=True,
        help_text=(
            "True = gerado por Celery task; False = manual"
        ),
    )
    total_packages = models.IntegerField(
        "Total pacotes", default=0,
    )
    total_cost_eur = models.DecimalField(
        "Custo estimado (€)", max_digits=10, decimal_places=2,
        default=0,
    )
    n_to_escalate = models.IntegerField(
        "Total a escalar (>10d)", default=0,
    )
    n_drivers_affected = models.IntegerField(
        "Drivers afectados", default=0,
    )
    n_cp4s_affected = models.IntegerField(
        "CP4s afectados", default=0,
    )

    class Meta:
        verbose_name = "Snapshot Not Arrived"
        verbose_name_plural = "Snapshots Not Arrived"
        ordering = ["-snapshot_date", "-created_at"]
        unique_together = [("snapshot_date", "hub")]

    def __str__(self):
        return (
            f"Snapshot {self.snapshot_date} · "
            f"{self.total_packages} pacotes"
        )


class PrioritySettings(models.Model):
    """Singleton: regras configuráveis de prioridade automática.

    Um pacote é considerado prioritário se:
      - is_priority_external == True (PRIORITYS=Yes do Cainiao), OU
      - days_in_hub >= min_days_in_hub, OU
      - n_attempts >= min_attempts.
    """
    min_days_in_hub = models.PositiveIntegerField(
        "Mín. dias no HUB para ser prioritário", default=3,
        help_text="Pacotes parados há ≥ N dias úteis no HUB tornam-se prioritários.",
    )
    min_attempts = models.PositiveIntegerField(
        "Mín. tentativas falhadas para ser prioritário", default=2,
        help_text="Pacotes com ≥ N tentativas de entrega tornam-se prioritários.",
    )
    auto_apply = models.BooleanField(
        "Aplicar regras automáticas", default=True,
        help_text="Desligar para usar só a flag PRIORITYS do Cainiao.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração de Prioridade"
        verbose_name_plural = "Configurações de Prioridade"

    def __str__(self):
        return (
            f"PrioritySettings(days≥{self.min_days_in_hub}, "
            f"attempts≥{self.min_attempts}, "
            f"auto={self.auto_apply})"
        )

    @classmethod
    def load(cls):
        """Singleton — sempre retorna a única instância (cria se preciso)."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class WaybillTag(models.Model):
    """Etiquetas livres por waybill. Múltiplas tags por waybill."""
    waybill_number = models.CharField(
        "Waybill", max_length=100, db_index=True,
    )
    tag = models.CharField("Etiqueta", max_length=50, db_index=True)
    notes = models.CharField(
        "Notas", max_length=255, blank=True,
    )
    created_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="waybill_tags",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tag de Waybill"
        ordering = ["-created_at"]
        unique_together = [("waybill_number", "tag")]

    def __str__(self):
        return f"{self.waybill_number} · {self.tag}"


class WaybillWatch(models.Model):
    """Watchlist: utilizador segue um waybill, recebe alertas em mudanças."""
    waybill_number = models.CharField(
        "Waybill", max_length=100, db_index=True,
    )
    user = models.ForeignKey(
        "auth.User", on_delete=models.CASCADE,
        related_name="waybill_watches",
    )
    notes = models.CharField(
        "Notas", max_length=255, blank=True,
    )
    notify_on_change = models.BooleanField(
        "Notificar mudanças", default=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Watch de Waybill"
        unique_together = [("waybill_number", "user")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} ⊙ {self.waybill_number}"


class ReturnBatch(models.Model):
    """Lote de devoluções — agrupa N waybills devolvidos numa
    única expedição de retorno (uma viagem ao hub, etc.).
    """
    name = models.CharField(
        "Nome do lote", max_length=100,
        help_text="ex: 'Devoluções Aveiro 27/04'",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="return_batches",
    )
    closed_at = models.DateTimeField(
        "Fechado em", null=True, blank=True,
    )
    notes = models.TextField("Notas", blank=True)
    total_cost_eur = models.DecimalField(
        "Custo total (€)", max_digits=10, decimal_places=2,
        default=0,
    )

    class Meta:
        verbose_name = "Lote de Devolução"
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.id} · {self.name}"


class WaybillReturn(models.Model):
    """Devolução de um pacote ao remetente."""
    STATUS_PREPARING = "PREPARING"
    STATUS_IN_TRANSIT = "IN_TRANSIT"
    STATUS_RETURNED = "RETURNED_TO_SENDER"
    STATUS_CLOSED = "CLOSED"

    STATUS_CHOICES = [
        (STATUS_PREPARING, "A preparar"),
        (STATUS_IN_TRANSIT, "Em trânsito de retorno"),
        (STATUS_RETURNED, "Chegou ao remetente"),
        (STATUS_CLOSED, "Fechado"),
    ]

    REASON_CHOICES = [
        ("address_wrong", "Endereço errado"),
        ("customer_refused", "Cliente recusou"),
        ("customer_not_found", "Cliente não encontrado"),
        ("damaged", "Pacote danificado"),
        ("no_response", "Cliente não respondeu"),
        ("expired", "Prazo expirou"),
        ("other", "Outro"),
    ]

    waybill_number = models.CharField(
        "Waybill", max_length=100, db_index=True, unique=True,
    )
    return_status = models.CharField(
        "Status", max_length=30,
        choices=STATUS_CHOICES, default=STATUS_PREPARING,
        db_index=True,
    )
    return_reason = models.CharField(
        "Razão", max_length=40,
        choices=REASON_CHOICES, default="address_wrong",
    )
    return_date = models.DateField(
        "Data de devolução", default=timezone.now,
    )
    return_tracking_number = models.CharField(
        "Tracking de retorno", max_length=100, blank=True,
    )
    return_carrier = models.CharField(
        "Transportadora retorno", max_length=100, blank=True,
        help_text="ex: Cainiao, CTT, DHL...",
    )
    return_cost_eur = models.DecimalField(
        "Custo da devolução (€)",
        max_digits=8, decimal_places=2, default=0,
    )
    batch = models.ForeignKey(
        ReturnBatch, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="returns",
    )
    customer_notified = models.BooleanField(
        "Cliente notificado", default=False,
    )
    notification_method = models.CharField(
        "Método de notificação", max_length=30, blank=True,
        help_text="WhatsApp, SMS, Email…",
    )
    notes = models.TextField("Notas", blank=True)
    marked_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="waybill_returns_marked",
    )
    closed_at = models.DateTimeField(
        "Fechado em", null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Devolução de Waybill"
        verbose_name_plural = "Devoluções de Waybills"
        ordering = ["-return_date", "-created_at"]
        indexes = [
            models.Index(fields=["return_status", "return_date"]),
            models.Index(fields=["return_reason"]),
        ]

    def __str__(self):
        return (
            f"{self.waybill_number} · "
            f"{self.get_return_status_display()}"
        )

    @property
    def is_open(self):
        return self.return_status not in (
            self.STATUS_RETURNED, self.STATUS_CLOSED,
        )


class SavedSearchFilter(models.Model):
    """Filtros guardados pelo utilizador para a página de pacotes."""
    user = models.ForeignKey(
        "auth.User", on_delete=models.CASCADE,
        related_name="saved_search_filters",
    )
    name = models.CharField("Nome", max_length=100)
    filter_data = models.JSONField(
        "Dados do filtro", default=dict,
    )
    is_shared = models.BooleanField(
        "Partilhado com a equipa", default=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Filtro Guardado"
        ordering = ["-updated_at"]
        unique_together = [("user", "name")]

    def __str__(self):
        return f"{self.user.username}: {self.name}"


class NotArrivedSnapshotRow(models.Model):
    """Linha individual dentro de um snapshot diário.

    Congela todos os dados relevantes do waybill no momento do
    snapshot — não muda mais, mesmo que o waybill seja resolvido
    depois.
    """
    snapshot = models.ForeignKey(
        NotArrivedSnapshot, on_delete=models.CASCADE,
        related_name="rows",
    )
    waybill_number = models.CharField(
        max_length=100, db_index=True,
    )
    courier_name = models.CharField(max_length=200, blank=True)
    courier_id_cainiao = models.CharField(max_length=50, blank=True)
    cp4 = models.CharField(max_length=4, blank=True, db_index=True)
    city = models.CharField(max_length=100, blank=True)
    customer_name = models.CharField(max_length=200, blank=True)
    seller = models.CharField(max_length=200, blank=True)
    weight_g = models.FloatField(null=True, blank=True)
    business_days_stuck = models.IntegerField(default=0)
    sla_level = models.CharField(max_length=10, blank=True)
    first_seen = models.DateField(null=True, blank=True)
    estimated_cost_eur = models.DecimalField(
        max_digits=8, decimal_places=4, default=0,
    )

    class Meta:
        verbose_name = "Linha Snapshot Not Arrived"
        ordering = ["-business_days_stuck", "courier_name"]
        indexes = [
            models.Index(
                fields=["snapshot", "waybill_number"],
            ),
            models.Index(fields=["waybill_number", "snapshot"]),
        ]

    def __str__(self):
        return (
            f"{self.snapshot.snapshot_date} · {self.waybill_number}"
        )



# ============================================================================
# Transferências de atribuição entre motoristas
#
# Use case: motorista A teve avaria; motorista B socorreu e fez entregas
# usando o login do A. As rows Cainiao continuam a mostrar courier=A,
# mas os créditos financeiros vão para B. Este modelo regista o override.
# ============================================================================


class WaybillAttributionOverride(models.Model):
    waybill_number = models.CharField(
        "Waybill", max_length=100, unique=True, db_index=True,
    )
    task_date = models.DateField(
        "Data da operação", db_index=True,
        help_text="Dia em que a entrega foi efectivamente feita.",
    )
    original_courier_id = models.CharField(
        "Courier ID original (Cainiao)", max_length=64, blank=True,
    )
    original_courier_name = models.CharField(
        "Courier name original", max_length=120, blank=True,
    )
    attributed_to_driver = models.ForeignKey(
        "drivers_app.DriverProfile", on_delete=models.CASCADE,
        related_name="waybill_attributions",
        verbose_name="Atribuir a (driver destino)",
    )
    reason = models.CharField(
        "Razão", max_length=200, blank=True,
        help_text="ex: Socorro — carro avariado",
    )
    transferred_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="waybill_transfers",
    )
    transferred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Transferência de Atribuição"
        verbose_name_plural = "Transferências de Atribuição"
        ordering = ["-transferred_at"]
        indexes = [
            models.Index(fields=["task_date", "attributed_to_driver"]),
        ]

    def __str__(self):
        return (
            f"{self.waybill_number} · {self.task_date} → "
            f"{self.attributed_to_driver.nome_completo}"
        )


# ============================================================================
# Override de preço por waybill — preço diferente em pacotes específicos
# (ex: apoios em CP4s longe, sábados/feriados especiais, etc.)
# ============================================================================


class PackagePriceOverride(models.Model):
    waybill_number = models.CharField(
        "Waybill", max_length=100, unique=True, db_index=True,
    )
    task_date = models.DateField("Data da operação", db_index=True)
    cp4 = models.CharField(
        "CP4 (snapshot)", max_length=10, blank=True, db_index=True,
    )
    original_courier_name = models.CharField(
        "Courier original", max_length=120, blank=True,
    )
    price = models.DecimalField(
        "Preço por pacote (€)", max_digits=8, decimal_places=4,
        help_text="Substitui o preço base para este pacote.",
    )
    reason = models.CharField(
        "Razão", max_length=200, blank=True,
        help_text="ex: Apoio CP4 4970 — distância maior",
    )
    created_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="price_overrides_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Override de Preço"
        verbose_name_plural = "Overrides de Preço"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["task_date", "cp4"]),
        ]

    def __str__(self):
        return (
            f"{self.waybill_number} · {self.task_date} · "
            f"€{self.price}/pacote"
        )


class PreInvoiceNote(models.Model):
    """Comentário interno de operadores numa Pré-Fatura.

    Uso: thread de notas para discussão entre operadores antes de
    pagar (ex: 'verificar com motorista se concorda com €50 desconto').
    Não visível ao motorista.
    """
    pre_invoice = models.ForeignKey(
        "DriverPreInvoice", on_delete=models.CASCADE,
        related_name="notes",
    )
    author = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="pf_notes_authored",
    )
    body = models.TextField("Conteúdo")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Nota de Pré-Fatura"
        verbose_name_plural = "Notas de Pré-Fatura"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.pre_invoice.numero}: {self.body[:50]}"


# ════════════════════════════════════════════════════════════════════
#  CAINIAO BILLING IMPORT
#  Importação da pré-fatura mensal/quinzenal que a Cainiao envia em
#  XLSX. 1 import = 1 ficheiro. Reimport idempotente via file_hash +
#  unique constraint nas linhas. Cria automaticamente uma
#  PartnerInvoice agregando os totais.
# ════════════════════════════════════════════════════════════════════

class CainiaoBillingImport(models.Model):
    """Sessão de importação de uma pré-fatura Cainiao (XLSX)."""

    STATUS_CHOICES = [
        ("PROCESSING", "Em processamento"),
        ("COMPLETED", "Concluído"),
        ("FAILED", "Falhou"),
    ]

    partner_invoice = models.OneToOneField(
        PartnerInvoice,
        on_delete=models.CASCADE,
        related_name="cainiao_import",
        null=True, blank=True,
        help_text=(
            "PartnerInvoice criada automaticamente com os totais agregados."
        ),
    )

    file_name = models.CharField("Nome do Ficheiro", max_length=255)
    file_hash = models.CharField(
        "SHA256 do Ficheiro", max_length=64, unique=True, db_index=True,
        help_text="Bloqueia reimport do mesmo ficheiro (idempotência).",
    )

    period_from = models.DateField("Período Início", db_index=True)
    period_to = models.DateField("Período Fim", db_index=True)

    # Contadores cached (reduz queries na listagem)
    total_lines = models.PositiveIntegerField("Total de Linhas", default=0)
    total_envio = models.DecimalField(
        "Total Envios (€)", max_digits=12, decimal_places=2,
        default=Decimal("0.00"),
    )
    total_compensacion = models.DecimalField(
        "Total Compensações (€)", max_digits=12, decimal_places=2,
        default=Decimal("0.00"),
    )
    n_billing_ids = models.PositiveIntegerField(
        "Lotes (billing_id)", default=0,
    )
    n_staff_ids = models.PositiveIntegerField(
        "Motoristas distintos", default=0,
    )

    status = models.CharField(
        "Estado", max_length=20, choices=STATUS_CHOICES,
        default="PROCESSING",
    )
    error_message = models.TextField("Erro", blank=True)

    imported_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cainiao_billing_imports",
    )
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Importação Cainiao"
        verbose_name_plural = "Importações Cainiao"
        ordering = ["-imported_at"]
        indexes = [
            models.Index(fields=["period_from", "period_to"]),
            models.Index(fields=["status", "-imported_at"]),
        ]

    def __str__(self):
        return (
            f"Cainiao {self.period_from}→{self.period_to} "
            f"({self.total_lines} linhas)"
        )

    @property
    def total_amount(self):
        return self.total_envio + self.total_compensacion


class CainiaoBillingLine(models.Model):
    """Uma linha do XLSX Cainiao — 1 envio fee ou 1 compensación.

    Chave de dedupe (waybill, fee_type, cainiao_billing_id) garante que
    reimports do mesmo ficheiro ou ficheiros sobrepostos (quinzenas)
    não criam duplicados.
    """

    FEE_TYPE_CHOICES = [
        ("envio fee", "Envio fee"),
        ("compensacion", "Compensación"),
    ]

    import_session = models.ForeignKey(
        CainiaoBillingImport,
        on_delete=models.CASCADE,
        related_name="lines",
    )

    # Campos directos do XLSX
    fee_type = models.CharField(
        "Fee Type", max_length=30, choices=FEE_TYPE_CHOICES, db_index=True,
    )
    biz_time = models.DateTimeField("Biz Time", db_index=True)
    amount = models.DecimalField(
        "Valor (€)", max_digits=10, decimal_places=4,
    )
    moneda = models.CharField("Moneda", max_length=10, default="EUR")
    waybill_number = models.CharField(
        "Waybill (REFs)", max_length=100, db_index=True,
    )
    cp_name = models.CharField("CP Name", max_length=120, blank=True)
    ciudad = models.CharField("Cidade", max_length=120, blank=True)
    staff_id = models.CharField(
        "Staff ID (Cainiao)", max_length=50, blank=True, db_index=True,
        help_text="courier_id_cainiao do motorista que entregou.",
    )
    cainiao_billing_id = models.CharField(
        "Billing ID Cainiao", max_length=50, blank=True, db_index=True,
        help_text="ID do lote/corte de facturação Cainiao.",
    )
    fb1 = models.TextField("FB1", blank=True)
    fb2 = models.TextField(
        "FB2 (motivo)", blank=True,
        help_text="Razão da compensação (apenas em compensaciones).",
    )

    # Campos resolvidos no save (matching com modelos locais)
    task = models.ForeignKey(
        CainiaoOperationTask,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="billing_lines",
        help_text="Task local resolvida pelo waybill_number.",
    )
    driver = models.ForeignKey(
        "drivers_app.DriverProfile",
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cainiao_billing_lines",
        help_text=(
            "Driver resolvido por staff_id (DriverProfile.courier_id_cainiao "
            "ou DriverCourierMapping). Para compensaciones com staff_id "
            "vazio, é resolvido via task.courier_id_cainiao."
        ),
    )
    claim = models.ForeignKey(
        DriverClaim,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cainiao_billing_lines",
        help_text="DriverClaim criado a partir desta linha (se compensación).",
    )
    price_override = models.ForeignKey(
        PackagePriceOverride,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cainiao_billing_lines",
        help_text="PackagePriceOverride criado para preço especial (≠ €1.60).",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Linha Pré-Fatura Cainiao"
        verbose_name_plural = "Linhas Pré-Fatura Cainiao"
        # Idempotência: o mesmo waybill+fee+lote nunca aparece 2× na BD,
        # mesmo que o operador reimporte o ficheiro ou importe a quinzena
        # seguinte que sobreponha alguns dias.
        unique_together = [
            ("waybill_number", "fee_type", "cainiao_billing_id"),
        ]
        ordering = ["-biz_time"]
        indexes = [
            models.Index(fields=["fee_type", "-biz_time"]),
            models.Index(fields=["staff_id", "-biz_time"]),
            models.Index(fields=["cainiao_billing_id"]),
            models.Index(fields=["import_session", "fee_type"]),
        ]

    def __str__(self):
        return f"{self.fee_type} {self.waybill_number} €{self.amount}"

    @property
    def is_special_price(self):
        """Envio fee com preço ≠ €1.60 (preço base padrão Cainiao)."""
        return (
            self.fee_type == "envio fee"
            and self.amount != Decimal("1.60")
        )

    @property
    def is_claim(self):
        return self.fee_type == "compensacion"
