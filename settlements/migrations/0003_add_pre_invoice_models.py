# Generated manually - DriverPreInvoice, PreInvoiceBonus, PreInvoiceLostPackage, PreInvoiceAdvance

from decimal import Decimal
import django.core.validators
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('drivers_app', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('settlements', '0002_driversettlement_driverclaim_partnerinvoice_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='DriverPreInvoice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero', models.CharField(help_text='Ex: PF-0001', max_length=20, unique=True, verbose_name='Nº Pré-Fatura')),
                ('periodo_inicio', models.DateField(db_index=True, verbose_name='Período Início')),
                ('periodo_fim', models.DateField(db_index=True, verbose_name='Período Fim')),
                ('courier_id', models.CharField(blank=True, help_text='ID do motorista no sistema do parceiro (futura integração API)', max_length=100, verbose_name='Courier ID')),
                ('taxa_por_entrega', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=8, validators=[django.core.validators.MinValueValidator(0)], verbose_name='Taxa por Entrega (€)')),
                ('total_pacotes', models.PositiveIntegerField(default=0, help_text='Quantidade total de entregas no período', verbose_name='Total Pacotes')),
                ('dsr_percentual', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Percentual de Descanso Semanal Remunerado', max_digits=5, validators=[django.core.validators.MinValueValidator(0)], verbose_name='DSR (%)')),
                ('base_entregas', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Pacotes × Taxa por entrega', max_digits=12, verbose_name='Base Entregas (€)')),
                ('total_bonus', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12, verbose_name='Total Bônus Domingo/Feriado (€)')),
                ('ajuste_manual', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Correções positivas extraordinárias', max_digits=12, verbose_name='Ajuste Manual (€)')),
                ('penalizacoes_gerais', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Descontos gerais (excluindo pacotes perdidos)', max_digits=12, verbose_name='Penalizações Gerais (€)')),
                ('total_pacotes_perdidos', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12, verbose_name='Total Pacotes Perdidos (€)')),
                ('total_adiantamentos', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12, verbose_name='Total Adiantamentos/Combustível (€)')),
                ('subtotal_bruto', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12, verbose_name='Subtotal Bruto (€)')),
                ('total_a_receber', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12, verbose_name='Total a Receber (€)')),
                ('status', models.CharField(choices=[('RASCUNHO', 'Rascunho'), ('CALCULADO', 'Calculado'), ('APROVADO', 'Aprovado'), ('PAGO', 'Pago')], db_index=True, default='RASCUNHO', max_length=20, verbose_name='Status')),
                ('data_pagamento', models.DateField(blank=True, null=True, verbose_name='Data de Pagamento')),
                ('referencia_pagamento', models.CharField(blank=True, help_text='MB WAY, Transferência, etc.', max_length=200, verbose_name='Referência de Pagamento')),
                ('dsp_empresa', models.CharField(blank=True, default='LÉGUAS FRANZINAS - UNIPESSOAL LDA', max_length=200, verbose_name='DSP / Empresa')),
                ('api_source', models.CharField(blank=True, help_text='Ex: paack, amazon, delnext — vazio se entrada manual', max_length=50, verbose_name='Fonte API')),
                ('api_reference', models.CharField(blank=True, help_text='ID ou referência do sistema externo', max_length=200, verbose_name='Referência API')),
                ('observacoes', models.TextField(blank=True, verbose_name='Observações')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('driver', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='pre_invoices', to='drivers_app.driverprofile', verbose_name='Motorista')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_pre_invoices', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Pré-Fatura de Motorista',
                'verbose_name_plural': 'Pré-Faturas de Motoristas',
                'ordering': ['-periodo_fim', 'driver__nome_completo'],
            },
        ),
        migrations.AddIndex(
            model_name='driverpreinvoice',
            index=models.Index(fields=['driver', 'periodo_inicio', 'periodo_fim'], name='settle_preinv_driver_period_idx'),
        ),
        migrations.AddIndex(
            model_name='driverpreinvoice',
            index=models.Index(fields=['status', '-created_at'], name='settle_preinv_status_idx'),
        ),
        migrations.CreateModel(
            name='PreInvoiceBonus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data', models.DateField(verbose_name='Data')),
                ('tipo', models.CharField(choices=[('DOMINGO', 'Domingo'), ('FERIADO', 'Feriado Nacional'), ('FERIADO_LOCAL', 'Feriado Local')], default='DOMINGO', max_length=20, verbose_name='Tipo')),
                ('qtd_entregas_elegiveis', models.PositiveIntegerField(default=0, help_text='Entregas contabilizadas para o bônus neste dia', verbose_name='Qtd. Entregas Elegíveis')),
                ('bonus_calculado', models.DecimalField(decimal_places=2, default=Decimal('0.00'), editable=False, max_digits=8, verbose_name='Bônus (€)')),
                ('api_source', models.CharField(blank=True, max_length=50)),
                ('observacoes', models.CharField(blank=True, max_length=300, verbose_name='Observações')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('pre_invoice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bonificacoes', to='settlements.driverpreinvoice', verbose_name='Pré-Fatura')),
            ],
            options={
                'verbose_name': 'Bonificação Domingo/Feriado',
                'verbose_name_plural': 'Bonificações Domingo/Feriado',
                'ordering': ['data'],
            },
        ),
        migrations.CreateModel(
            name='PreInvoiceLostPackage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data', models.DateField(blank=True, null=True, verbose_name='Data')),
                ('numero_pacote', models.CharField(blank=True, max_length=100, verbose_name='Nº Pacote')),
                ('descricao', models.CharField(blank=True, max_length=300, verbose_name='Descrição')),
                ('valor', models.DecimalField(decimal_places=2, default=Decimal('50.00'), max_digits=8, validators=[django.core.validators.MinValueValidator(0)], verbose_name='Valor (€)')),
                ('api_source', models.CharField(blank=True, max_length=50)),
                ('observacoes', models.CharField(blank=True, max_length=300, verbose_name='Observações')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('pre_invoice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pacotes_perdidos', to='settlements.driverpreinvoice', verbose_name='Pré-Fatura')),
            ],
            options={
                'verbose_name': 'Pacote Perdido',
                'verbose_name_plural': 'Pacotes Perdidos',
                'ordering': ['data'],
            },
        ),
        migrations.CreateModel(
            name='PreInvoiceAdvance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data', models.DateField(blank=True, null=True, verbose_name='Data')),
                ('tipo', models.CharField(choices=[('ADIANTAMENTO', 'Adiantamento'), ('COMBUSTIVEL', 'Combustível'), ('ABASTECIMENTO', 'Abastecimento'), ('OUTRO', 'Outro')], default='ADIANTAMENTO', max_length=20, verbose_name='Tipo')),
                ('descricao', models.CharField(blank=True, max_length=300, verbose_name='Descrição')),
                ('valor', models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(0)], verbose_name='Valor (€)')),
                ('documento_referencia', models.CharField(blank=True, max_length=300, verbose_name='Documento / Observações')),
                ('api_source', models.CharField(blank=True, max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('pre_invoice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='adiantamentos', to='settlements.driverpreinvoice', verbose_name='Pré-Fatura')),
            ],
            options={
                'verbose_name': 'Adiantamento / Combustível',
                'verbose_name_plural': 'Adiantamentos / Combustível',
                'ordering': ['data'],
            },
        ),
    ]
