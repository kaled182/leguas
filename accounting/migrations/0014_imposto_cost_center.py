from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0013_bill_delete_reason_bill_deleted_at_bill_deleted_by_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="imposto",
            name="cost_center",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Segrega a carga fiscal por centro. Se vazio, o Bill "
                    "espelho usa o ADMIN por defeito."
                ),
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="impostos",
                to="accounting.costcenter",
                verbose_name="Centro de Custo",
            ),
        ),
    ]
