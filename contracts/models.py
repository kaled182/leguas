"""Sistema de contratos: templates + assinaturas dos motoristas."""
import hashlib
from django.db import models
from django.utils import timezone


class ContractTemplate(models.Model):
    """Modelo (template) de contrato — versionado.

    Quando um template é alterado, cria-se uma nova versão (não se edita a
    anterior, para preservar a integridade dos contratos já assinados).
    """

    SCOPE_CHOICES = [
        ("all", "Todos os motoristas"),
        ("independent", "Apenas independentes"),
        ("fleet", "Apenas frotas (subcontratados)"),
    ]

    name = models.CharField(
        "Nome", max_length=200,
        help_text="Ex: Termo de Adesão, NDA, Contrato de Prestação de Serviços",
    )
    version = models.CharField(
        "Versão", max_length=20, default="1.0",
        help_text="Ex: 1.0, 2024-Q1, etc.",
    )
    scope = models.CharField(
        "Aplicabilidade", max_length=15,
        choices=SCOPE_CHOICES, default="all",
    )
    content = models.TextField(
        "Conteúdo (HTML/Markdown)",
        help_text="Aceita HTML básico ou Markdown. Será mostrado ao motorista antes da assinatura.",
    )

    is_active = models.BooleanField(
        "Activo", default=True,
        help_text="Quando inactivo, novos motoristas não recebem este contrato. Os já assinados continuam válidos.",
    )
    effective_from = models.DateField(
        "Vigente desde", default=timezone.now,
    )
    expires_at = models.DateField(
        "Vigente até", null=True, blank=True,
        help_text="Opcional. Após esta data, motoristas devem re-assinar versão nova.",
    )

    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="created_contract_templates",
    )

    class Meta:
        verbose_name = "Modelo de Contrato"
        verbose_name_plural = "Modelos de Contratos"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_active", "scope"]),
        ]

    def __str__(self):
        return f"{self.name} v{self.version}"

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        return timezone.now().date() > self.expires_at


class DriverContract(models.Model):
    """Contrato assinado por um motorista (snapshot do template no momento)."""

    driver = models.ForeignKey(
        "drivers_app.DriverProfile",
        on_delete=models.CASCADE,
        related_name="contracts",
    )
    template = models.ForeignKey(
        ContractTemplate,
        on_delete=models.PROTECT,
        related_name="signed_contracts",
    )

    # Snapshot — imutável após assinatura
    content_snapshot = models.TextField(
        "Conteúdo no momento da assinatura",
        help_text="Cópia do template para preservar conteúdo mesmo se o template mudar.",
    )

    # Assinatura
    signed_at = models.DateTimeField(default=timezone.now, db_index=True)
    ip_address = models.GenericIPAddressField(
        "IP da assinatura", null=True, blank=True,
    )
    user_agent = models.TextField("User-Agent", blank=True)
    signature_text = models.CharField(
        "Frase de aceitação", max_length=200,
        default="Li e aceito os termos.",
    )

    # Hash de integridade
    content_hash = models.CharField(
        "Hash SHA-256 do conteúdo", max_length=64, blank=True,
        help_text="Garante que o conteúdo não foi modificado depois da assinatura.",
    )

    # PDF gerado (opcional, para download offline)
    pdf_file = models.FileField(
        "PDF assinado", upload_to="contracts/signed/",
        null=True, blank=True,
    )

    # Revogação (admin pode invalidar um contrato — ex: motorista reportou abuso)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="revoked_contracts",
    )
    revoked_reason = models.TextField(blank=True)

    class Meta:
        verbose_name = "Contrato Assinado"
        verbose_name_plural = "Contratos Assinados"
        ordering = ["-signed_at"]
        indexes = [
            models.Index(fields=["driver", "-signed_at"]),
            models.Index(fields=["template", "-signed_at"]),
        ]
        constraints = [
            # Um driver só pode assinar a mesma versão uma vez (excepto se revogado)
            models.UniqueConstraint(
                fields=["driver", "template"],
                condition=models.Q(revoked_at__isnull=True),
                name="unique_active_contract_per_driver_template",
            ),
        ]

    def __str__(self):
        return f"{self.driver_id} · {self.template} · {self.signed_at:%Y-%m-%d}"

    @property
    def is_active(self):
        return self.revoked_at is None

    def compute_hash(self):
        """SHA-256 de driver+template+content+signed_at (integridade)."""
        h = hashlib.sha256()
        h.update(f"{self.driver_id}|{self.template_id}".encode())
        h.update(self.content_snapshot.encode("utf-8"))
        h.update(self.signed_at.isoformat().encode())
        return h.hexdigest()

    def save(self, *args, **kwargs):
        if not self.content_hash and self.content_snapshot:
            self.content_hash = self.compute_hash()
        super().save(*args, **kwargs)


# ════════════════════════════════════════════════════════════════════
# Contrato único por hub/CP (gerado no sistema, assinado em papel)
# ════════════════════════════════════════════════════════════════════

class ContractSettings(models.Model):
    """Parâmetros gerais do contrato (uma só linha, id=1).

    Caução por regime (decisão A1): semanal → retenção rotativa de N
    semanas; mensal → caução fixa em €.
    """

    company_rep = models.CharField(
        "Representante da empresa", max_length=120, default="Rivelly Rodrigues",
    )
    duration_months = models.PositiveSmallIntegerField("Duração (meses)", default=12)
    route_confirm_until = models.CharField("Confirmação de rota até (véspera)", max_length=5, default="22:00")
    hub_pickup_until = models.CharField("Recolha no hub até", max_length=5, default="10:00")
    loss_min = models.PositiveIntegerField("Perda / entrega falsa — mínimo (€/vol.)", default=50)
    loss_cap = models.PositiveIntegerField("Perda — teto do valor declarado (€; 0 = sem teto)", default=250)
    damage = models.PositiveIntegerField("Dano (€/vol.)", default=15)
    wrong_place = models.PositiveIntegerField("Entrega em local diferente, recebida (€/vol.)", default=5)
    no_show = models.PositiveIntegerField("Rota confirmada não executada (€)", default=50)
    no_return = models.PositiveIntegerField("Não devolução de volumes (€/ocorr.)", default=30)
    response_hours = models.PositiveSmallIntegerField("Resposta a reclamações (horas)", default=24)
    notice_days = models.PositiveSmallIntegerField("Pré-aviso de saída (dias)", default=15)
    settle_with_notice_days = models.PositiveSmallIntegerField("Liquidação com aviso (dias)", default=45)
    settle_without_notice_days = models.PositiveSmallIntegerField("Liquidação sem aviso — máx. (dias)", default=60)
    weekly_retention_weeks = models.PositiveSmallIntegerField("Semanal: retenção rotativa (semanas)", default=3)
    weekly_maturation_days = models.PositiveSmallIntegerField("Semanal: maturação do 1.º pagamento (dias)", default=28)
    monthly_deposit = models.PositiveIntegerField("Mensal: caução fixa (€)", default=300)
    weekly_discount = models.DecimalField(
        "Semanal: desconto por volume (€)", max_digits=6, decimal_places=4, default=0.05,
        help_text="Usado quando o CP não tem preço semanal próprio.",
    )
    cp_pricing_from = models.DateField(
        "Preço por CP nas PF a partir de", null=True, blank=True,
        help_text=(
            "PF com início nesta data ou depois usam: valor negociado do CP → "
            "tarifa padrão do CP → preço do motorista/frota/parceiro. "
            "Vazio = desligado (só preço do motorista/frota/parceiro)."
        ),
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Parâmetros do Contrato"
        verbose_name_plural = "Parâmetros do Contrato"

    def __str__(self):
        return "Parâmetros do contrato"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class HubContractTerms(models.Model):
    """Condições do contrato que dependem do hub."""

    MONTHLY_MODE_CHOICES = [
        ("DAYS_AFTER_CLOSE", "N dias após o fecho do mês (fatura)"),
        ("DAY_OF_NEXT_MONTH", "Dia N do mês seguinte"),
    ]
    WEEKDAY_CHOICES = [
        (0, "segunda-feira"), (1, "terça-feira"), (2, "quarta-feira"),
        (3, "quinta-feira"), (4, "sexta-feira"),
    ]

    hub = models.OneToOneField(
        "settlements.CainiaoHub", on_delete=models.CASCADE,
        related_name="contract_terms",
    )
    signing_place = models.CharField("Local de assinatura", max_length=80, blank=True)
    allows_monthly = models.BooleanField("Aceita regime mensal", default=True)
    allows_weekly = models.BooleanField("Aceita regime semanal", default=False)
    monthly_payment_mode = models.CharField(
        "Pagamento mensal", max_length=20,
        choices=MONTHLY_MODE_CHOICES, default="DAYS_AFTER_CLOSE",
    )
    monthly_payment_value = models.PositiveSmallIntegerField(
        "Valor (dias ou dia do mês)", default=30,
    )
    weekly_payday = models.PositiveSmallIntegerField(
        "Dia de pagamento semanal", choices=WEEKDAY_CHOICES, default=1,
    )
    weekly_lag_weeks = models.PositiveSmallIntegerField(
        "Semanal: paga a semana trabalhada N semanas antes", default=4,
    )
    min_fare_enabled = models.BooleanField("Tarifa mínima por rota (escalão C)", default=False)
    min_fare_value = models.PositiveIntegerField("Tarifa mínima (€/dia/rota)", default=60)
    min_fare_under_volumes = models.PositiveIntegerField("Rotas com menos de (volumes)", default=50)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Condições do Hub"
        verbose_name_plural = "Condições dos Hubs"

    def __str__(self):
        return f"Condições · {self.hub.name}"

    @property
    def allowed_regimes(self):
        out = []
        if self.allows_monthly:
            out.append("MENSAL")
        if self.allows_weekly:
            out.append("SEMANAL")
        return out

    def monthly_payment_text(self):
        if self.monthly_payment_mode == "DAY_OF_NEXT_MONTH":
            return f"dia {self.monthly_payment_value} do mês seguinte"
        return f"{self.monthly_payment_value} dias após o fecho do mês"


class HubZoneTariff(models.Model):
    """Preço por volume ao motorista, por CP4 de um hub (Anexo I)."""

    TIER_CHOICES = [("A", "A"), ("B", "B"), ("C", "C")]

    hub = models.ForeignKey(
        "settlements.CainiaoHub", on_delete=models.CASCADE,
        related_name="zone_tariffs",
    )
    cp4 = models.CharField("CP4", max_length=4, db_index=True)
    zone_name = models.CharField("Zona", max_length=120)
    tier = models.CharField("Escalão", max_length=1, choices=TIER_CHOICES, blank=True)
    price_monthly = models.DecimalField("€/vol. mensal", max_digits=6, decimal_places=4)
    price_weekly = models.DecimalField(
        "€/vol. semanal", max_digits=6, decimal_places=4, null=True, blank=True,
        help_text="Vazio = mensal menos o desconto semanal dos parâmetros.",
    )
    valid_from = models.DateField("Válido desde", default=timezone.now)
    is_active = models.BooleanField("Activo", default=True)

    class Meta:
        verbose_name = "Tarifa por CP"
        verbose_name_plural = "Tarifas por CP"
        ordering = ["hub__name", "cp4", "-valid_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["hub", "cp4", "valid_from"], name="unique_hub_cp4_from",
            ),
        ]

    def __str__(self):
        return f"{self.hub.name} · {self.cp4} {self.zone_name}"

    def price_for(self, regime, settings=None):
        if regime == "SEMANAL":
            if self.price_weekly is not None:
                return self.price_weekly
            settings = settings or ContractSettings.get()
            return self.price_monthly - settings.weekly_discount
        return self.price_monthly


class GeneratedContract(models.Model):
    """Contrato ou aditivo gerado no sistema a partir da ficha do motorista."""

    KIND_CHOICES = [
        ("CONTRATO", "Contrato de Prestação de Serviços"),
        ("ADITIVO", "Aditivo (entregas e responsabilidade)"),
    ]
    STATUS_CHOICES = [
        ("GERADO", "Gerado"),
        ("ENVIADO", "Enviado ao motorista"),
        ("ASSINADO", "Assinado"),
        ("ANULADO", "Anulado"),
    ]

    driver = models.ForeignKey(
        "drivers_app.DriverProfile", on_delete=models.CASCADE,
        related_name="generated_contracts",
    )
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default="CONTRATO")
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default="GERADO", db_index=True,
    )
    regime = models.CharField(max_length=10, blank=True)
    hubs = models.JSONField(
        default=list, blank=True,
        help_text="[{hub_id, name, cp4s:[...]}] no momento da geração",
    )
    params = models.JSONField(default=dict, blank=True)
    content_snapshot = models.TextField(blank=True)
    content_hash = models.CharField(max_length=64, blank=True)
    original_contract_date = models.DateField(
        "Data do contrato original (aditivo)", null=True, blank=True,
    )
    generated_at = models.DateTimeField(default=timezone.now)
    generated_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    signed_file = models.FileField(
        "Contrato assinado (PDF/imagem)", upload_to="contracts/generated/%Y/%m/",
        null=True, blank=True,
    )
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Contrato Gerado"
        verbose_name_plural = "Contratos Gerados"
        ordering = ["-generated_at"]

    def __str__(self):
        return f"{self.get_kind_display()} · {self.driver_id} · {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if self.content_snapshot and not self.content_hash:
            self.content_hash = hashlib.sha256(
                self.content_snapshot.encode("utf-8"),
            ).hexdigest()
        super().save(*args, **kwargs)
