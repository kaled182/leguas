from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("drivers_app", "0008_add_customer_complaint_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="customercomplaint",
            name="deadline",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Deadline",
                help_text="Prazo limite para resposta/resolução (ex: prazo da plataforma).",
            ),
        ),
    ]
