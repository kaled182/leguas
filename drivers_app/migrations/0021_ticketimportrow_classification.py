from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('drivers_app', '0020_ticket_import_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticketimportrow',
            name='category',
            field=models.CharField(choices=[('EXPEDITED', 'Expedited Delivery'), ('FAKE_DELIVERY', 'Fake Delivery'), ('PARCEL_LOST', 'Parcel Lost'), ('OTHER', 'Outro')], db_index=True, default='OTHER', max_length=20, verbose_name='Categoria'),
        ),
        migrations.AddField(
            model_name='ticketimportrow',
            name='is_delivered',
            field=models.BooleanField(blank=True, help_text='Resultado do cruzamento com CainiaoOperationTask.', null=True, verbose_name='Entregue?'),
        ),
        migrations.AddField(
            model_name='ticketimportrow',
            name='delivered_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Data de Entrega'),
        ),
        migrations.AddField(
            model_name='ticketimportrow',
            name='row_action',
            field=models.CharField(choices=[('', 'Pendente'), ('IGNORED', 'Ignorado'), ('CLOSED', 'Fechado')], db_index=True, default='', max_length=10, verbose_name='Disposição'),
        ),
    ]
