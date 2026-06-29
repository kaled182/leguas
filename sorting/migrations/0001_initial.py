from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('geozonas', '0001_initial'),
        ('drivers_app', '0021_ticketimportrow_classification'),
    ]

    operations = [
        migrations.CreateModel(
            name='SortingSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(blank=True, max_length=160, verbose_name='Nome da Sessão')),
                ('hub', models.CharField(blank=True, db_index=True, max_length=120, verbose_name='HUB')),
                ('mode', models.CharField(choices=[('CP4', 'Por CP4 (total)'), ('ZONA', 'Por Geozona')], default='CP4', max_length=10, verbose_name='Modo')),
                ('status', models.CharField(choices=[('EM_ANDAMENTO', 'Em Andamento'), ('FINALIZADO', 'Finalizado')], db_index=True, default='EM_ANDAMENTO', max_length=20, verbose_name='Estado')),
                ('observacao', models.TextField(blank=True, verbose_name='Observação')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True, verbose_name='Finalizada em')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sorting_sessions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Sessão de Sorting',
                'verbose_name_plural': 'Sessões de Sorting',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='SortingBigbag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cp4', models.CharField(blank=True, db_index=True, max_length=4, verbose_name='CP4')),
                ('zona_nome', models.CharField(blank=True, max_length=120, verbose_name='Zona')),
                ('codigo', models.CharField(blank=True, max_length=80, verbose_name='Código Bigbag')),
                ('observacao', models.CharField(blank=True, max_length=255, verbose_name='Observação')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('driver', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sorting_bigbags', to='drivers_app.driverprofile', verbose_name='Motorista')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bigbags', to='sorting.sortingsession')),
                ('zona', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sorting_bigbags', to='geozonas.zonageo')),
            ],
            options={
                'verbose_name': 'Bigbag (Sorting)',
                'verbose_name_plural': 'Bigbags (Sorting)',
                'ordering': ['cp4', 'zona_nome', 'id'],
                'unique_together': {('session', 'cp4', 'zona')},
            },
        ),
        migrations.CreateModel(
            name='SortingParcel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('waybill_number', models.CharField(db_index=True, max_length=100, verbose_name='Waybill')),
                ('cp', models.CharField(blank=True, max_length=12, verbose_name='Código Postal')),
                ('cp4', models.CharField(blank=True, db_index=True, max_length=4, verbose_name='CP4')),
                ('zona_nome', models.CharField(blank=True, max_length=120, verbose_name='Zona')),
                ('localidade', models.CharField(blank=True, max_length=160, verbose_name='Localidade')),
                ('status', models.CharField(choices=[('OK', 'Classificado'), ('UNRESOLVED', 'Não Classificado')], db_index=True, default='OK', max_length=20, verbose_name='Estado')),
                ('note', models.CharField(blank=True, max_length=200, verbose_name='Nota')),
                ('scanned_at', models.DateTimeField(auto_now_add=True)),
                ('bigbag', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='parcels', to='sorting.sortingbigbag')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='parcels', to='sorting.sortingsession')),
                ('scanned_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sorting_scans', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Pacote (Sorting)',
                'verbose_name_plural': 'Pacotes (Sorting)',
                'ordering': ['-scanned_at'],
                'indexes': [models.Index(fields=['session', 'waybill_number'], name='sorting_sor_session_wb_idx')],
            },
        ),
    ]
