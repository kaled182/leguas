from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("drivers_app", "0001_initial"),
        ("settlements", "0039_cainiao_billing_import"),
    ]

    operations = [
        migrations.AddField(
            model_name="driverclaim",
            name="customer_complaint",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Reclamação de cliente associada a este desconto — "
                    "preserva todo o protocolo (cliente, morada, "
                    "deadline, anexos) para permitir defesa estruturada."
                ),
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="driver_claims",
                to="drivers_app.customercomplaint",
            ),
        ),
    ]
