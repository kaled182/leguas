from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("settlements", "0051_driverpreinvoice_total_pudo_preinvoicepudo"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="driverpreinvoice",
            name="total_extras",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                help_text="Soma de lançamentos a crédito (arrasto, serviços extra).",
                max_digits=12,
                verbose_name="Total Serviços Extra (€)",
            ),
        ),
        migrations.CreateModel(
            name="PreInvoiceExtra",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("data", models.DateField(verbose_name="Data")),
                ("tipo", models.CharField(choices=[("ARRASTO", "Arrasto"), ("SERVICO_EXTRA", "Serviço Extra"), ("AJUDA", "Ajuda / Apoio"), ("AJUSTE", "Ajuste / Crédito"), ("OUTRO", "Outro")], default="SERVICO_EXTRA", max_length=20, verbose_name="Tipo")),
                ("descricao", models.CharField(blank=True, max_length=300, verbose_name="Descrição")),
                ("valor", models.DecimalField(decimal_places=2, default=Decimal("0.00"), help_text="Valor a creditar ao motorista (positivo).", max_digits=10, validators=[django.core.validators.MinValueValidator(0)], verbose_name="Valor (€)")),
                ("api_source", models.CharField(blank=True, max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_pre_invoice_extras", to=settings.AUTH_USER_MODEL)),
                ("pre_invoice", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="extras", to="settlements.driverpreinvoice", verbose_name="Pré-Fatura")),
            ],
            options={
                "verbose_name": "Serviço Extra",
                "verbose_name_plural": "Serviços Extra",
                "ordering": ["data"],
            },
        ),
    ]
