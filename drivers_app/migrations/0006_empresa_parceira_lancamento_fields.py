from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("drivers_app", "0005_empresa_parceira_lancamento"),
    ]

    operations = [
        migrations.AddField(
            model_name="empresaparceiralancamento",
            name="qtd_entregas",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Número de caixas/pacotes entregues",
                verbose_name="Qtd. Entregas",
            ),
        ),
        migrations.AddField(
            model_name="empresaparceiralancamento",
            name="valor_por_entrega",
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal("0.0000"),
                max_digits=8,
                verbose_name="Valor por Entrega (€)",
            ),
        ),
        migrations.AddField(
            model_name="empresaparceiralancamento",
            name="pacotes_perdidos",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                help_text="Desconto por pacotes perdidos",
                max_digits=12,
                verbose_name="Pacotes Perdidos (€)",
            ),
        ),
        migrations.AddField(
            model_name="empresaparceiralancamento",
            name="adiantamentos",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=12,
                verbose_name="Adiantamentos / Combustível (€)",
            ),
        ),
        migrations.AlterField(
            model_name="empresaparceiralancamento",
            name="valor_base",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                help_text="Preenchido automaticamente (qtd × valor) ou manualmente",
                max_digits=12,
                verbose_name="Base Entregas (€)",
            ),
        ),
    ]
