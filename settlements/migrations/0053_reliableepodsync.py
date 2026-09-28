from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("settlements", "0052_driverpreinvoice_total_extras_preinvoiceextra"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReliableEpodSync",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("remote_id", models.PositiveIntegerField(db_index=True, verbose_name="ID no ReliableMaps")),
                ("sha256", models.CharField(max_length=64, unique=True, verbose_name="SHA-256")),
                ("filename", models.CharField(max_length=255, verbose_name="Ficheiro")),
                ("hub", models.CharField(blank=True, max_length=40, verbose_name="Hub")),
                ("remote_loaded_at", models.DateTimeField(db_index=True, verbose_name="Carregado no ReliableMaps")),
                ("status", models.CharField(
                    choices=[
                        ("imported", "Importado"),
                        ("failed", "Falhou"),
                        ("superseded", "Substituído por export mais recente"),
                        ("skipped", "Ignorado"),
                    ],
                    max_length=12,
                    verbose_name="Estado",
                )),
                ("message", models.TextField(blank=True, verbose_name="Mensagem")),
                ("summary", models.JSONField(blank=True, default=dict, verbose_name="Resumo")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                "verbose_name": "Sync EPOD ReliableMaps",
                "verbose_name_plural": "Syncs EPOD ReliableMaps",
                "ordering": ["-remote_loaded_at"],
            },
        ),
    ]
