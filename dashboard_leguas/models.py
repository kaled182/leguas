from django.db import models


class SlaZoneRule(models.Model):
    """Prazo de entrega por CP4 (dias úteis após a chegada ao hub).

    CP4 sem regra usam services_sla.SLA_DAYS (T+1).
    """

    SLA_CHOICES = [(1, "T+1"), (2, "T+2"), (3, "T+3")]

    cp4 = models.CharField("CP4", max_length=4, unique=True)
    sla_days = models.PositiveSmallIntegerField("Prazo", choices=SLA_CHOICES, default=1)
    label = models.CharField(
        "Etiqueta", max_length=30, blank=True,
        help_text='Ex.: "T+2 R" (zona remota).',
    )
    notes = models.CharField("Notas", max_length=200, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )

    class Meta:
        verbose_name = "Prazo SLA por CP4"
        verbose_name_plural = "Prazos SLA por CP4"
        ordering = ["cp4"]

    def __str__(self):
        return f"{self.cp4} · {self.label or self.get_sla_days_display()}"
