from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customauth", "0007_driverloginotp"),
    ]

    operations = [
        migrations.AlterField(
            model_name="driverloginotp",
            name="id",
            field=models.BigAutoField(
                auto_created=True,
                primary_key=True,
                serialize=False,
                verbose_name="ID",
            ),
        ),
    ]
