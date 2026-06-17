import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("drivers_app", "0019_driverautoemitconfig"),
    ]

    operations = [
        migrations.CreateModel(
            name="DriverAppToken",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "key",
                    models.CharField(
                        db_index=True,
                        max_length=64,
                        unique=True,
                        verbose_name="Token",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Criado em"
                    ),
                ),
                (
                    "last_used_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Último uso"
                    ),
                ),
                (
                    "expires_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Expira em"
                    ),
                ),
                (
                    "revoked",
                    models.BooleanField(default=False, verbose_name="Revogado"),
                ),
                (
                    "user_agent",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="User-Agent",
                    ),
                ),
                (
                    "driver_profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="app_tokens",
                        to="drivers_app.driverprofile",
                        verbose_name="Perfil do Motorista",
                    ),
                ),
            ],
            options={
                "verbose_name": "Token da App",
                "verbose_name_plural": "Tokens da App",
                "ordering": ["-created_at"],
            },
        ),
    ]
