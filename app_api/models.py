"""Modelos da API da app do motorista."""
import secrets

from django.db import models
from django.utils import timezone


class DriverAppToken(models.Model):
    """Token Bearer da app, emitido apos validacao OTP."""

    driver_profile = models.ForeignKey(
        "drivers_app.DriverProfile",
        on_delete=models.CASCADE,
        related_name="app_tokens",
        verbose_name="Perfil do Motorista",
    )
    key = models.CharField("Token", max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    last_used_at = models.DateTimeField("Ultimo uso", null=True, blank=True)
    expires_at = models.DateTimeField("Expira em", null=True, blank=True)
    revoked = models.BooleanField("Revogado", default=False)
    user_agent = models.CharField("User-Agent", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "Token da App"
        verbose_name_plural = "Tokens da App"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Token {self.driver_profile_id} ({self.key[:8]}...)"

    @staticmethod
    def generate_key():
        return secrets.token_hex(32)

    @property
    def is_expired(self):
        return self.expires_at is not None and timezone.now() >= self.expires_at

    @property
    def is_valid(self):
        return not self.revoked and not self.is_expired


class IncidencePacket(models.Model):
    """Registro de incidencias lidas no scanner da app."""

    driver_profile = models.ForeignKey(
        "drivers_app.DriverProfile",
        on_delete=models.CASCADE,
        related_name="incidence_packets",
    )
    barcode = models.CharField(max_length=80, unique=True, db_index=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    client_name = models.CharField(max_length=255)
    address = models.TextField()
    latitude = models.DecimalField(max_digits=10, decimal_places=8, default=0)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, default=0)
    package_image = models.ImageField(upload_to="incidences/%Y/%m/%d/", null=True, blank=True)
    scanned_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ocr_data = models.JSONField(null=True, blank=True)
    zone = models.CharField(max_length=80, blank=True, default="")

    class Meta:
        ordering = ["-scanned_at"]
        indexes = [
            models.Index(fields=["driver_profile", "scanned_at"]),
            models.Index(fields=["zone", "scanned_at"]),
        ]

    def __str__(self):
        return f"{self.barcode} - {self.client_name}"


class OcrCorrectionLearning(models.Model):
    FIELD_CHOICES = [
        ("recipient_name", "Nome do Destinatario"),
        ("address", "Endereco"),
        ("package_code", "Codigo do Pacote"),
        ("operation_code", "Codigo de Operacao"),
        ("city", "Cidade"),
        ("state", "Estado"),
        ("country", "Pais"),
        ("postal_code", "Codigo Postal"),
    ]

    field_name = models.CharField(max_length=50, choices=FIELD_CHOICES)
    original_value = models.TextField()
    corrected_value = models.TextField()
    normalized_original = models.CharField(max_length=500, db_index=True)
    normalized_corrected = models.CharField(max_length=500, db_index=True)
    occurrence_count = models.IntegerField(default=1)
    success_count = models.IntegerField(default=0)
    correction_count = models.IntegerField(default=0)
    score = models.FloatField(default=0.5)
    last_used_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    incidence = models.ForeignKey(
        IncidencePacket,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ocr_corrections",
    )

    class Meta:
        indexes = [
            models.Index(fields=["field_name", "normalized_original"]),
            models.Index(fields=["field_name", "score"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.field_name}: {self.original_value} -> {self.corrected_value}"

    def update_score(self, was_confirmed=True):
        if was_confirmed:
            self.success_count += 1
            self.score = min(1.0, self.score + 0.05)
        else:
            self.correction_count += 1
            self.score = max(0.0, self.score - 0.1)
        self.occurrence_count = self.success_count + self.correction_count


class OcrScanAttempt(models.Model):
    driver_profile = models.ForeignKey(
        "drivers_app.DriverProfile",
        on_delete=models.CASCADE,
        related_name="ocr_scan_attempts",
    )
    qr_code = models.CharField(max_length=120, db_index=True)
    image = models.ImageField(upload_to="ocr_attempts/%Y/%m/%d/", null=True, blank=True)
    local_raw_text = models.TextField(blank=True, default="")
    server_raw_text = models.TextField(blank=True, default="")
    detected_data = models.JSONField(null=True, blank=True)
    confirmed_data = models.JSONField(null=True, blank=True)
    confidence = models.JSONField(null=True, blank=True)
    was_edited = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.qr_code} ({self.created_at:%d/%m/%Y %H:%M})"
