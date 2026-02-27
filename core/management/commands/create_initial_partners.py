"""
Management command para criar Partners iniciais no sistema.
Usado na fase de migração para criar registro de Partner para Paack.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Partner, PartnerIntegration


class Command(BaseCommand):
    help = 'Cria Partners iniciais no sistema (Paack e outros)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-paack',
            action='store_true',
            help='Pula criação do parceiro Paack',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(self.style.SUCCESS(' CRIAÇÃO DE PARTNERS INICIAIS'))
        self.stdout.write(self.style.SUCCESS('='*60 + '\n'))
        
        created_count = 0
        
        with transaction.atomic():
            # Partner 1: Paack
            if not options['skip_paack']:
                paack, created = self._create_paack_partner()
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Partner "Paack" criado com sucesso!')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'⚠ Partner "Paack" já existe')
                    )
            
            # Aqui podem ser adicionados outros parceiros futuros
            # Partner 2: Amazon
            # amazon, created = self._create_amazon_partner()
            # ...
        
        # Resumo
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(
            f'✅ Criação concluída! {created_count} parceiro(s) criado(s).'
        ))
        self.stdout.write('='*60)
    
    def _create_paack_partner(self):
        """Cria o partner Paack com configuração padrão"""
        
        # Nota: Ajustar estes valores com dados reais da empresa
        partner, created = Partner.objects.get_or_create(
            name='Paack',
            defaults={
                'nif': 'PT000000000',  # TODO: Atualizar com NIF real da Paack
                'contact_email': 'operations@paack.co',
                'contact_phone': '+351000000000',
                'api_credentials': {
                    # TODO: Atualizar com credenciais reais (ou deixar vazio e configurar depois no admin)
                    'api_key': '',
                    'api_secret': '',
                },
                'is_active': True,
                'default_delivery_time_days': 2,
                'auto_assign_orders': True,
            }
        )
        
        if created:
            # Criar integração API para Paack
            PartnerIntegration.objects.create(
                partner=partner,
                integration_type='API',
                endpoint_url='https://api.paack.co/v1',  # TODO: Verificar URL correcta
                auth_config={
                    'type': 'bearer',
                },
                sync_frequency_minutes=15,
                is_active=False,  # Inativo até configurar credenciais corretas
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'  → Integração API criada para Paack (inativa - configurar credenciais)'
                )
            )
        
        return partner, created
    
    def _create_amazon_partner(self):
        """Cria o partner Amazon (placeholder para futuro)"""
        
        partner, created = Partner.objects.get_or_create(
            name='Amazon',
            defaults={
                'nif': 'PT000000000',  # TODO: Atualizar com NIF real
                'contact_email': 'logistics@amazon.com',
                'contact_phone': '+351000000000',
                'api_credentials': {},
                'is_active': False,  # Inativo até configurar
                'default_delivery_time_days': 1,
                'auto_assign_orders': True,
            }
        )
        
        return partner, created
