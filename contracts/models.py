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
