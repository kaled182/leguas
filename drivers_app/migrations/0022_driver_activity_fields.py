from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('drivers_app', '0021_ticketimportrow_classification'),
    ]

    operations = [
        migrations.AddField(
            model_name='driverprofile',
            name='last_activity_date',
            field=models.DateField(blank=True, db_index=True, help_text='Último dia com entrega ou tentativa (Cainiao).', null=True, verbose_name='Última Atividade'),
        ),
        migrations.AddField(
            model_name='driverprofile',
            name='inactive_since',
            field=models.DateField(blank=True, db_index=True, help_text='Preenchido quando passa mais de 7 dias sem atividade. Vazio = activo.', null=True, verbose_name='Inactivo desde'),
        ),
        migrations.AddField(
            model_name='driverprofile',
            name='activity_checked_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Atividade verificada em'),
        ),
        migrations.AlterField(
            model_name='driverdocument',
            name='tipo_documento',
            field=models.CharField(choices=[('CC', 'Cartao de Cidadao'), ('TR', 'Titulo de Residencia'), ('PP', 'Passaporte'), ('MI', 'Manifestacao de Interesse'), ('CNH_FRENTE', 'Carta de Conducao - Frente'), ('CNH_VERSO', 'Carta de Conducao - Verso'), ('ADR', 'Certificado ADR'), ('RC', 'Registo Criminal'), ('DECLARACAO_ATIVIDADE', 'Declaracao de Inicio de Atividade'), ('CONTRATO', 'Contrato Assinado (anexo)'), ('OUTRO', 'Outro Documento')], max_length=30, verbose_name='Tipo de Documento'),
        ),
    ]
