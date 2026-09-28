import system_config.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("system_config", "0010_systemconfiguration_geoapi_token"),
    ]

    operations = [
        migrations.AddField(
            model_name="systemconfiguration",
            name="reliable_api_url",
            field=models.CharField(
                blank=True,
                help_text="Ex.: https://reliable.exemplo.pt (sem /api/...).",
                max_length=255,
                null=True,
                verbose_name="ReliableMaps URL",
            ),
        ),
        migrations.AddField(
            model_name="systemconfiguration",
            name="reliable_api_key",
            field=system_config.fields.EncryptedCharField(
                blank=True,
                help_text="Chave criada no ReliableMaps com manage.py criar_chave_de_integracao.",
                max_length=512,
                null=True,
                verbose_name="ReliableMaps Chave de Integração",
            ),
        ),
        migrations.AddField(
            model_name="systemconfiguration",
            name="reliable_epod_sync_enabled",
            field=models.BooleanField(
                default=False, verbose_name="Sincronizar EPOD do ReliableMaps"
            ),
        ),
    ]
