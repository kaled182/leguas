from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("drivers_app", "0010_add_data_entrega_to_complaint"),
    ]

    operations = [
        migrations.AddField(
            model_name="empresaparceiraLancamento",
            name="taxa_iva",
            field=models.DecimalField(
                verbose_name="Taxa IVA (%)",
                max_digits=5,
                decimal_places=2,
                default=Decimal("23.00"),
                help_text="Taxa de IVA aplicada a este lançamento",
            ),
        ),
    ]
