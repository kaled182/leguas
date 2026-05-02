from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("settlements", "0012_add_comprovante_to_preinvoice"),
    ]

    operations = [
        migrations.AddField(
            model_name="driverpreinvoice",
            name="fatura_ficheiro",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="pre_invoices/faturas/%Y/%m/",
                verbose_name="Fatura",
                help_text="PDF da fatura emitida pelo motorista",
            ),
        ),
    ]
