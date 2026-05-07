from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("settlements", "0040_driverclaim_customer_complaint"),
    ]

    operations = [
        migrations.AlterField(
            model_name="driverclaim",
            name="claim_type",
            field=models.CharField(
                choices=[
                    ("ORDER_LOSS", "Perda de Pedido"),
                    ("ORDER_DAMAGE", "Dano em Pedido"),
                    ("VEHICLE_FINE", "Multa de Veículo"),
                    ("VEHICLE_DAMAGE", "Dano em Veículo"),
                    ("FUEL_EXCESS", "Excesso de Combustível"),
                    ("MISSING_POD", "Falta de Comprovante"),
                    ("LATE_DELIVERY", "Entrega Atrasada"),
                    ("CUSTOMER_COMPLAINT", "Reclamação de Cliente"),
                    ("FAKE_DELIVERY", "Fake Delivery (PUDO)"),
                    ("OTHER", "Outro"),
                ],
                db_index=True,
                max_length=30,
                verbose_name="Tipo de Desconto",
            ),
        ),
    ]
