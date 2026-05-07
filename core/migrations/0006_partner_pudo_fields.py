from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_partner_driver_default_price_per_package"),
    ]

    operations = [
        migrations.AddField(
            model_name="partner",
            name="pudo_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Se ativo, entregas com Delivery Type=PUDO no EPOD "
                    "são remuneradas pelas regras PUDO em vez do preço "
                    "padrão."
                ),
                verbose_name="PUDO activo neste parceiro",
            ),
        ),
        migrations.AddField(
            model_name="partner",
            name="pudo_first_delivery_price",
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal("1.0000"),
                help_text=(
                    "Pago pela primeira encomenda entregue num PUDO. "
                    "Cada encomenda adicional no MESMO PUDO usa "
                    "pudo_additional_delivery_price."
                ),
                max_digits=6,
                verbose_name="PUDO — 1ª entrega no mesmo PUDO (€)",
            ),
        ),
        migrations.AddField(
            model_name="partner",
            name="pudo_additional_delivery_price",
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal("0.2000"),
                help_text=(
                    "Pago por cada encomenda extra no MESMO PUDO além "
                    "da primeira. Fórmula total: 1ª + (N-1) × adicional."
                ),
                max_digits=6,
                verbose_name=(
                    "PUDO — entregas adicionais no mesmo PUDO (€)"
                ),
            ),
        ),
        migrations.AddField(
            model_name="partner",
            name="pudo_fake_delivery_penalty",
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal("1.3000"),
                help_text=(
                    "Descontado ao motorista quando uma entrega marcada "
                    "como PUDO é entregue em mãos do cliente em vez do "
                    "PUDO."
                ),
                max_digits=6,
                verbose_name="PUDO — penalização Fake Delivery (€)",
            ),
        ),
        migrations.AddField(
            model_name="partner",
            name="pudo_geo_tolerance_meters",
            field=models.PositiveIntegerField(
                default=200,
                help_text=(
                    "Distância máxima em metros entre a localização do "
                    "PUDO (receiver_lat/lng) e o local onde o motorista "
                    "marcou Delivered (actual_lat/lng). Acima desta "
                    "tolerância a entrega é sinalizada como SUSPEITA "
                    "de Fake Delivery — operador confirma manualmente "
                    "antes de gerar penalização."
                ),
                verbose_name="PUDO — tolerância geo (metros)",
            ),
        ),
    ]
