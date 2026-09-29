from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("settlements", "0054_reliableclaimverdict"),
    ]

    operations = [
        migrations.AddField(
            model_name="driverclaim",
            name="billing_after",
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name="Descontar só depois de",
                help_text=(
                    "Passado para a próxima fatura: só entra em pré-faturas que "
                    "começam depois desta data (o fim da pré-fatura de onde saiu)."
                ),
            ),
        ),
    ]
