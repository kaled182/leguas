import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pudo_network", "0001_initial"),
        ("sorting", "0002_customer_data_targets"),
    ]

    operations = [
        migrations.AddField(
            model_name="sortingbigbag",
            name="pudo_store",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sorting_bigbags",
                to="pudo_network.pudostore",
                verbose_name="PUDO destino",
            ),
        ),
        migrations.AddField(
            model_name="sortingbigbag",
            name="consumida",
            field=models.BooleanField(
                default=False,
                help_text="Bigbag já entregue/assinada ao PUDO; bloqueia reutilização.",
                verbose_name="Consumida",
            ),
        ),
    ]
