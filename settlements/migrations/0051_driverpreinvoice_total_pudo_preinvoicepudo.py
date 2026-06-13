from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("settlements", "0050_driverclaim_appeal_reason_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="driverpreinvoice",
            name="total_pudo",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                help_text="Soma das entregas PUDO (fórmula 1ª + adicionais).",
                max_digits=12,
                verbose_name="Total Entregas PUDO (€)",
            ),
        ),
        migrations.CreateModel(
            name="PreInvoicePudo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("data", models.DateField(verbose_name="Data")),
                ("n_pacotes", models.PositiveIntegerField(default=0, verbose_name="Nº Pacotes")),
                ("valor", models.DecimalField(decimal_places=2, default=Decimal("0.00"), help_text="1ª + (N-1) × adicional para este PUDO neste dia.", max_digits=10, validators=[django.core.validators.MinValueValidator(0)], verbose_name="Valor (€)")),
                ("morada", models.CharField(blank=True, max_length=300, verbose_name="Morada / PUDO")),
                ("zip_code", models.CharField(blank=True, max_length=12, verbose_name="Código Postal")),
                ("api_source", models.CharField(blank=True, max_length=50)),
                ("observacoes", models.CharField(blank=True, max_length=300, verbose_name="Observações")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("pre_invoice", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="pudos", to="settlements.driverpreinvoice", verbose_name="Pré-Fatura")),
            ],
            options={
                "verbose_name": "Entrega PUDO",
                "verbose_name_plural": "Entregas PUDO",
                "ordering": ["data"],
            },
        ),
    ]
