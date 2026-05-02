"""
Migration 0008: Adiciona campo iva_percentual a PreInvoiceLostPackage.
Registos existentes ficam com 0% (sem impacto nos valores já calculados).
"""
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("settlements", "0007_preinvoice_new_status_choices"),
    ]

    operations = [
        migrations.AddField(
            model_name="preinvoicelostpackage",
            name="iva_percentual",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                help_text="Percentagem de IVA a aplicar sobre o valor base (ex: 23)",
                max_digits=5,
                verbose_name="IVA (%)",
            ),
        ),
    ]
