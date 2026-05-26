from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("settlements", "0047_partnerinvoice_approved_at_and_more"),
        ("accounting", "0014_imposto_cost_center"),
    ]

    operations = [
        migrations.AddField(
            model_name="driverpreinvoice",
            name="cost_center",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Centro de custo onde esta PF é imputada. Vazio = "
                    "inferir do hub principal do motorista."
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="pre_invoices",
                to="accounting.costcenter",
                verbose_name="Centro de Custo",
            ),
        ),
    ]
