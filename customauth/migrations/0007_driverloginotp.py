import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("drivers_app", "0019_driverautoemitconfig"),
        ("customauth", "0006_empresa_access"),
    ]

    operations = [
        migrations.CreateModel(
            name="DriverLoginOTP",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("phone", models.CharField(max_length=20, verbose_name="Telefone")),
                ("code", models.CharField(max_length=6, verbose_name="Código")),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Criado em"
                    ),
                ),
                ("expires_at", models.DateTimeField(verbose_name="Expira em")),
                (
                    "used_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Usado em"
                    ),
                ),
                (
                    "attempts",
                    models.PositiveSmallIntegerField(
                        default=0, verbose_name="Tentativas"
                    ),
                ),
                (
                    "driver_profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="login_otps",
                        to="drivers_app.driverprofile",
                        verbose_name="Perfil do Motorista",
                    ),
                ),
            ],
            options={
                "verbose_name": "Código de login (OTP)",
                "verbose_name_plural": "Códigos de login (OTP)",
                "ordering": ["-created_at"],
            },
        ),
    ]
