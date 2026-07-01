from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sorting', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='sortingsession',
            name='target_cps',
            field=models.CharField(blank=True, help_text='CP4 esperados nesta sessão (vírgulas). Vazio = aceita todos.', max_length=255, verbose_name='CP4 alvo'),
        ),
        migrations.AddField(
            model_name='sortingparcel',
            name='nome_cliente',
            field=models.CharField(blank=True, max_length=200, verbose_name='Cliente'),
        ),
        migrations.AddField(
            model_name='sortingparcel',
            name='telefone_cliente',
            field=models.CharField(blank=True, max_length=40, verbose_name='Telefone'),
        ),
        migrations.AddField(
            model_name='sortingparcel',
            name='morada',
            field=models.CharField(blank=True, max_length=255, verbose_name='Morada'),
        ),
        migrations.AddField(
            model_name='sortingparcel',
            name='divergent',
            field=models.BooleanField(db_index=True, default=False, verbose_name='Divergente'),
        ),
    ]
