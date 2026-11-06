from django.apps import AppConfig


class SettlementsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "settlements"
    verbose_name = "Fechos Financeiros"

    def ready(self):
        # Importa signals (audit de deleções de ManualForecast)
        from . import signals  # noqa: F401
        # Fonte embutida nos PDF (ver reports/fonts.py)
        from .reports.fonts import embed_helvetica
        embed_helvetica()
