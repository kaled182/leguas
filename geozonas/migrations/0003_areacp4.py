from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("geozonas", "0002_ingestjob"),
    ]

    operations = [
        migrations.CreateModel(
            name="AreaCP4",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cp4", models.CharField(db_index=True, max_length=4, unique=True, verbose_name="CP4")),
                ("concelho_nome", models.CharField(blank=True, max_length=160, verbose_name="Concelho")),
                ("distrito", models.CharField(blank=True, max_length=120, verbose_name="Distrito")),
                ("poligono", models.JSONField(blank=True, null=True, verbose_name="Contorno (GeoJSON)")),
                ("centro_lat", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("centro_lng", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Área CP4",
                "verbose_name_plural": "Áreas CP4",
                "ordering": ["cp4"],
            },
        ),
    ]
