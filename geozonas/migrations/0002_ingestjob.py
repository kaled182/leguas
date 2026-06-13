from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("geozonas", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="IngestJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cp4", models.CharField(db_index=True, max_length=4, verbose_name="CP4")),
                ("com_coordenadas", models.BooleanField(default=False)),
                ("status", models.CharField(choices=[("PENDENTE", "Pendente"), ("A_CORRER", "A correr"), ("CONCLUIDO", "Concluído"), ("ERRO", "Erro")], db_index=True, default="PENDENTE", max_length=10)),
                ("concelho", models.CharField(blank=True, max_length=120)),
                ("total", models.IntegerField(default=0, verbose_name="Total de CP3")),
                ("processados", models.IntegerField(default=0, verbose_name="CP3 catalogados")),
                ("coords_total", models.IntegerField(default=0)),
                ("coords_feitas", models.IntegerField(default=0)),
                ("coords_falhadas", models.IntegerField(default=0)),
                ("erro", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Importação (Job)",
                "verbose_name_plural": "Importações (Jobs)",
                "ordering": ["-created_at"],
            },
        ),
    ]
