from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("drivers_app", "0009_add_deadline_to_complaint"),
    ]

    operations = [
        migrations.AddField(
            model_name="customercomplaint",
            name="data_entrega",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Data/Hora da Entrega",
                help_text="Data e hora em que a entrega foi realizada (ou tentada).",
            ),
        ),
    ]
