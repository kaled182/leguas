"""
Migration 0007: Adiciona novos status a DriverPreInvoice
(PENDENTE, CONTESTADO, REPROVADO) — só altera choices, sem schema change.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("settlements", "0006_preinvoiceline_remove_preinvoice_delivery_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="driverpreinvoice",
            name="status",
            field=models.CharField(
                choices=[
                    ("RASCUNHO", "Rascunho"),
                    ("CALCULADO", "Calculado"),
                    ("APROVADO", "Aprovado"),
                    ("PENDENTE", "Pendente Pagamento"),
                    ("CONTESTADO", "Contestado"),
                    ("REPROVADO", "Reprovado"),
                    ("PAGO", "Pago"),
                ],
                db_index=True,
                default="RASCUNHO",
                max_length=20,
                verbose_name="Status",
            ),
        ),
    ]
