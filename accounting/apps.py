from django.apps import AppConfig


class AccountingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounting"

    def ready(self):
        # Regista signals (auto-criação de CostCenter ao criar HUB)
        from . import signals  # noqa: F401
