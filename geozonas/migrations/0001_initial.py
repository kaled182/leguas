import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("pricing", "0001_initial"),
        ("drivers_app", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Concelho",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=120, unique=True, verbose_name="Concelho")),
                ("distrito", models.CharField(blank=True, max_length=120, verbose_name="Distrito")),
                ("codigo_ine", models.CharField(blank=True, db_index=True, max_length=12, verbose_name="Código INE")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Concelho",
                "verbose_name_plural": "Concelhos",
                "ordering": ["nome"],
            },
        ),
        migrations.CreateModel(
            name="Freguesia",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=180, verbose_name="Freguesia")),
                ("codigo_ine", models.CharField(blank=True, db_index=True, max_length=12, verbose_name="Código INE")),
                ("geojson", models.JSONField(blank=True, null=True, verbose_name="Polígono (GeoJSON)")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("concelho", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="freguesias", to="geozonas.concelho")),
            ],
            options={
                "verbose_name": "Freguesia",
                "verbose_name_plural": "Freguesias",
                "ordering": ["concelho__nome", "nome"],
                "unique_together": {("concelho", "nome")},
            },
        ),
        migrations.CreateModel(
            name="Localidade",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(db_index=True, max_length=180, verbose_name="Localidade")),
                ("freguesia", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="localidades", to="geozonas.freguesia")),
            ],
            options={
                "verbose_name": "Localidade",
                "verbose_name_plural": "Localidades",
                "ordering": ["nome"],
            },
        ),
        migrations.CreateModel(
            name="CodigoPostal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cp4", models.CharField(db_index=True, max_length=4, verbose_name="CP4")),
                ("cp3", models.CharField(max_length=3, verbose_name="CP3")),
                ("designacao_postal", models.CharField(blank=True, max_length=180, verbose_name="Designação Postal")),
                ("latitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name="Latitude")),
                ("longitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name="Longitude")),
                ("arterias", models.JSONField(blank=True, null=True, verbose_name="Artérias/Ruas")),
                ("fonte", models.CharField(choices=[("geoapi", "GeoAPI"), ("ctt", "CTT"), ("seed", "Importação inicial"), ("manual", "Manual")], default="geoapi", max_length=10)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("concelho", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cps", to="geozonas.concelho")),
                ("freguesia", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cps", to="geozonas.freguesia")),
                ("localidade", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cps", to="geozonas.localidade")),
            ],
            options={
                "verbose_name": "Código Postal",
                "verbose_name_plural": "Códigos Postais",
                "ordering": ["cp4", "cp3"],
            },
        ),
        migrations.CreateModel(
            name="ZonaGeo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(help_text='Ex.: "Zona A"', max_length=100, verbose_name="Nome da Zona")),
                ("codigo", models.SlugField(max_length=40, unique=True, verbose_name="Código")),
                ("cor", models.CharField(default="#2563eb", help_text="Hex, ex.: #2563eb", max_length=7, verbose_name="Cor")),
                ("poligono", models.JSONField(blank=True, null=True, verbose_name="Polígono (GeoJSON)")),
                ("is_active", models.BooleanField(default=True, verbose_name="Ativa")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("motorista_default", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="geozonas_default", to="drivers_app.driverprofile")),
                ("postal_zone", models.ForeignKey(blank=True, help_text="Zona de tarifário espelhada (opcional)", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="geozonas", to="pricing.postalzone")),
            ],
            options={
                "verbose_name": "Zona Geográfica",
                "verbose_name_plural": "Zonas Geográficas",
                "ordering": ["nome"],
            },
        ),
        migrations.AddIndex(
            model_name="codigopostal",
            index=models.Index(fields=["cp4", "cp3"], name="geozonas_co_cp4_cp3_idx"),
        ),
        migrations.AddIndex(
            model_name="codigopostal",
            index=models.Index(fields=["concelho"], name="geozonas_co_concelh_idx"),
        ),
        migrations.AlterUniqueTogether(
            name="codigopostal",
            unique_together={("cp4", "cp3")},
        ),
    ]
