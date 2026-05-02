from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('settlements', '0017_cainiao_new_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='CainiaoHub',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='Nome do HUB')),
                ('address', models.CharField(blank=True, max_length=255, verbose_name='Endereço')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'HUB Cainiao',
                'verbose_name_plural': 'HUBs Cainiao',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='CainiaoHubCP4',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cp4', models.CharField(db_index=True, max_length=4, verbose_name='Código CP4')),
                ('hub', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='cp4_codes',
                    to='settlements.cainiaohub',
                )),
            ],
            options={
                'verbose_name': 'CP4 do HUB',
                'verbose_name_plural': 'CP4s do HUB',
                'ordering': ['cp4'],
                'unique_together': {('hub', 'cp4')},
            },
        ),
    ]
