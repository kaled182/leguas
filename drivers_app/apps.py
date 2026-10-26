from django.apps import AppConfig


class DriversAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "drivers_app"

    def ready(self):
        from . import signals_payments  # noqa: F401
