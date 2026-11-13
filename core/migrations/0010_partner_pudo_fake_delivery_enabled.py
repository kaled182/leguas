from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_partner_same_door'),
    ]

    operations = [
        migrations.AddField(
            model_name='partner',
            name='pudo_fake_delivery_enabled',
            field=models.BooleanField(default=True, help_text='Se desligada, as suspeitas continuam listadas, mas não se cria desconto ao motorista. O contrato segue esta opção.', verbose_name='PUDO — penalização Fake Delivery activa'),
        ),
    ]
