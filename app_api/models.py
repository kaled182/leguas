"""Modelos da API da app do motorista (autenticação por token)."""
import secrets

from django.db import models
from django.utils import timezone


class DriverAppToken(models.Model):
    """Token Bearer de acesso da app, emitido após validar o OTP.

    Liga a um DriverProfile. A app envia-o em
    ``Authorization: Bearer <key>`` (sem cookies de sessão).
    """

    driver_profile = models.ForeignKey(
        "drivers_app.DriverProfile",
        on_delete=models.CASCADE,
        related_name="app_tokens",
        verbose_name="Perfil do Motorista",
    )
    key = models.CharField("Token", max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    last_used_at = models.DateTimeField("Último uso", null=True, blank=True)
    expires_at = models.DateTimeField("Expira em", null=True, blank=True)
    revoked = models.BooleanField("Revogado", default=False)
    user_agent = models.CharField("User-Agent", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "Token da App"
        verbose_name_plural = "Tokens da App"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Token {self.driver_profile_id} ({self.key[:8]}…)"

    @staticmethod
    def generate_key():
        """64 caracteres hex (32 bytes) — opaco e único."""
        return secrets.token_hex(32)

    @property
    def is_expired(self):
        return self.expires_at is not None and timezone.now() >= self.expires_at

    @property
    def is_valid(self):
        return not self.revoked and not self.is_expired
