import system_config.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("system_config", "0009_update_gemini_default"),
    ]

    operations = [
        migrations.AddField(
            model_name="systemconfiguration",
            name="geoapi_token",
            field=system_config.fields.EncryptedCharField(
                blank=True,
                help_text="Chave da GeoAPI.pt usada pelo Mapa de Códigos Postais.",
                max_length=512,
                null=True,
                verbose_name="GeoAPI.pt Token",
            ),
        ),
    ]
