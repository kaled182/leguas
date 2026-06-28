from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('drivers_app', '0019_driverautoemitconfig'),
    ]

    operations = [
        migrations.CreateModel(
            name='TicketImportBatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(blank=True, max_length=200, verbose_name='Nome do Lote')),
                ('ficheiro_nome', models.CharField(blank=True, max_length=255, verbose_name='Ficheiro Original')),
                ('total_rows', models.IntegerField(default=0, verbose_name='Total de Linhas')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ticket_import_batches', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Lote de Importação de Tickets',
                'verbose_name_plural': 'Lotes de Importação de Tickets',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='TicketImportRow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('exception_id', models.CharField(blank=True, db_index=True, max_length=60, verbose_name='Exception ID')),
                ('lp_number', models.CharField(blank=True, max_length=60, verbose_name='LP Number')),
                ('waybill_number', models.CharField(blank=True, db_index=True, max_length=100, verbose_name='Tracking Number')),
                ('ticket_no', models.CharField(blank=True, db_index=True, max_length=60, verbose_name='Ticket No.')),
                ('exception_creation_time', models.DateTimeField(blank=True, null=True, verbose_name='Criação da Exception')),
                ('exception_name', models.CharField(blank=True, max_length=120, verbose_name='Exception Name')),
                ('ticket_type', models.CharField(blank=True, max_length=40, verbose_name='Ticket Type')),
                ('description', models.TextField(blank=True, verbose_name='Descrição')),
                ('hub', models.CharField(blank=True, db_index=True, max_length=120, verbose_name='HUB')),
                ('driver_name_raw', models.CharField(blank=True, max_length=200, verbose_name='Driver (planilha)')),
                ('raw', models.JSONField(blank=True, default=dict, verbose_name='Linha Original')),
                ('internal_status', models.CharField(choices=[('SEM_RECLAMACAO', 'Sem Reclamação'), ('ABERTA', 'Reclamação Aberta'), ('FECHADA', 'Reclamação Fechada'), ('EM_RECURSO', 'Em Recurso'), ('DESCONTADA', 'Descontada')], db_index=True, default='SEM_RECLAMACAO', max_length=20, verbose_name='Estado Interno')),
                ('claim_id_ref', models.IntegerField(blank=True, help_text='PK do settlements.DriverClaim activo (recurso/desconto).', null=True, verbose_name='DriverClaim relacionado')),
                ('selected', models.BooleanField(default=False, verbose_name='Selecionada')),
                ('suggested_tipo', models.CharField(blank=True, max_length=30, verbose_name='Tipo Sugerido')),
                ('operator_notes', models.TextField(blank=True, verbose_name='Notas do Operador')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('batch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rows', to='drivers_app.ticketimportbatch')),
                ('complaint', models.ForeignKey(blank=True, help_text='Reclamação existente ou criada a partir desta linha.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='import_rows', to='drivers_app.customercomplaint')),
                ('driver', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ticket_import_rows', to='drivers_app.driverprofile', verbose_name='Motorista Resolvido')),
            ],
            options={
                'verbose_name': 'Linha de Importação de Ticket',
                'verbose_name_plural': 'Linhas de Importação de Tickets',
                'ordering': ['-exception_creation_time', 'id'],
            },
        ),
        migrations.CreateModel(
            name='TicketImportAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ficheiro', models.FileField(upload_to='ticket_imports/%Y/%m/', verbose_name='Ficheiro')),
                ('descricao', models.CharField(blank=True, max_length=200, verbose_name='Descrição')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('row', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='drivers_app.ticketimportrow')),
            ],
            options={
                'ordering': ['id'],
            },
        ),
        migrations.AddIndex(
            model_name='ticketimportrow',
            index=models.Index(fields=['batch', 'internal_status'], name='drivers_app_batch_i_idx'),
        ),
    ]
