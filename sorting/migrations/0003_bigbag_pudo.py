from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sorting", "0002_customer_data_targets"),
    ]

    operations = [
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
