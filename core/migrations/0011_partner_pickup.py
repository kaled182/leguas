from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_partner_pudo_fake_delivery_enabled'),
    ]

    operations = [
        migrations.AddField(
            model_name='partner',
            name='pickup_enabled',
            field=models.BooleanField(default=True, help_text='Volumes recolhidos no mesmo local, no mesmo dia: 1.º ao valor da 1.ª recolha e cada adicional ao valor adicional. Entra no contrato e na proposta.', verbose_name='Recolhas — regra activa'),
        ),
        migrations.AddField(
            model_name='partner',
            name='pickup_first_price',
            field=models.DecimalField(decimal_places=4, default=Decimal('1.0000'), max_digits=6, verbose_name='Recolhas — 1.º volume no mesmo local e dia (€)'),
        ),
        migrations.AddField(
            model_name='partner',
            name='pickup_additional_price',
            field=models.DecimalField(decimal_places=4, default=Decimal('0.2000'), help_text='Fórmula: 1.º + (N-1) × adicional, por local e por dia.', max_digits=6, verbose_name='Recolhas — cada volume adicional no mesmo local e dia (€)'),
        ),
    ]
