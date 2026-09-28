from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_partner_pudo_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="partner",
            name="verdict_claim_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("30.00"),
                help_text=(
                    "Valor por omissão do desconto criado quando a Cainiao julga uma "
                    "reclamação como responsabilidade nossa (via ReliableMaps). "
                    "Cada desconto pode ser editado depois em Claims."
                ),
                max_digits=8,
                verbose_name="Desconto por reclamação julgada contra o DSP (€)",
            ),
        ),
    ]
