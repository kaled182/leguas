from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from ordersmanager_paack.models import Driver  # ajuste se necessário

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
