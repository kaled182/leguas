"""
Management command para criar zonas postais de Portugal e tarifas de exemplo.

Uso:
    python manage.py seed_postal_zones
    python manage.py seed_postal_zones --with-tariffs  # Criar tarifas também
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from pricing.models import PostalZone, PartnerTariff
from core.models import Partner
from decimal import Decimal


class Command(BaseCommand):
    help = 'Cria zonas postais de Portugal e tarifas de exemplo'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--with-tariffs',
            action='store_true',
            help='Criar tarifas de exemplo para parceiros',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(self.style.SUCCESS(' CRIAÇÃO DE ZONAS POSTAIS'))
        self.stdout.write(self.style.SUCCESS('='*60 + '\n'))
        
        created_zones = 0
        created_tariffs = 0
        
        with transaction.atomic():
            # Criar zonas postais principais de Portugal
            zones_data = self._get_portugal_zones()
            
            for zone_data in zones_data:
                zone, created = PostalZone.objects.get_or_create(
                    code=zone_data['code'],
                    defaults=zone_data
                )
                
                if created:
                    created_zones += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Zona "{zone.name}" ({zone.code}) criada'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠ Zona "{zone.name}" ({zone.code}) já existe'
                        )
                    )
            
            # Criar tarifas se solicitado
            if options['with_tariffs']:
                self.stdout.write('\n🏷️ Criando tarifas de exemplo...\n')
                
                try:
                    paack = Partner.objects.get(name='Paack')
                    
                    for zone in PostalZone.objects.all():
                        # Criar tarifa base para Paack
                        tariff, created = PartnerTariff.objects.get_or_create(
                            partner=paack,
                            postal_zone=zone,
                            defaults={
                                'base_price': self._calculate_base_price(zone),
                                'success_bonus': Decimal('0.50'),
                                'failure_penalty': Decimal('1.00'),
                                'late_delivery_penalty': Decimal('0.50'),
                                'weekend_multiplier': Decimal('1.5'),
                                'express_multiplier': Decimal('1.8'),
                                'is_active': True,
                            }
                        )
                        
                        if created:
                            created_tariffs += 1
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'  ✓ Tarifa para {zone.name}: €{tariff.base_price}'
                                )
                            )
                
                except Partner.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(
                            '\n⚠ Partner "Paack" não encontrado. Execute primeiro:\n'
                            '   python manage.py create_initial_partners'
                        )
                    )
        
        # Resumo
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(
            f'✅ Criação concluída!\n'
            f'   • Zonas criadas: {created_zones}\n'
            f'   • Tarifas criadas: {created_tariffs}'
        ))
        self.stdout.write('='*60)
    
    def _get_portugal_zones(self):
        """Retorna lista de zonas postais principais de Portugal"""
        
        return [
            # Lisboa
            {
                'name': 'Lisboa Centro',
                'code': 'LIS-CENTRO',
                'postal_code_pattern': r'^(10\d{2}|11\d{2}|12\d{2})',
                'region': 'LISBOA',
                'center_latitude': Decimal('38.7223'),
                'center_longitude': Decimal('-9.1393'),
                'is_urban': True,
                'average_delivery_time_hours': 4,
            },
            {
                'name': 'Grande Lisboa',
                'code': 'LIS-GRANDE',
                'postal_code_pattern': r'^(13\d{2}|14\d{2}|15\d{2}|16\d{2}|17\d{2}|18\d{2}|19\d{2})',
                'region': 'LISBOA',
                'center_latitude': Decimal('38.7436'),
                'center_longitude': Decimal('-9.2302'),
                'is_urban': True,
                'average_delivery_time_hours': 6,
            },
            
            # Porto
            {
                'name': 'Porto Centro',
                'code': 'PORTO-CENTRO',
                'postal_code_pattern': r'^(40\d{2}|41\d{2}|42\d{2})',
                'region': 'NORTE',
                'center_latitude': Decimal('41.1579'),
                'center_longitude': Decimal('-8.6291'),
                'is_urban': True,
                'average_delivery_time_hours': 4,
            },
           {
                'name': 'Grande Porto',
                'code': 'PORTO-GRANDE',
                'postal_code_pattern': r'^(43\d{2}|44\d{2}|45\d{2})',
                'region': 'NORTE',
                'center_latitude': Decimal('41.1496'),
                'center_longitude': Decimal('-8.6109'),
                'is_urban': True,
                'average_delivery_time_hours': 6,
            },
            
            # Braga
            {
                'name': 'Braga',
                'code': 'BRAGA',
                'postal_code_pattern': r'^47\d{2}',
                'region': 'NORTE',
                'center_latitude': Decimal('41.5454'),
                'center_longitude': Decimal('-8.4265'),
                'is_urban': True,
                'average_delivery_time_hours': 24,
            },
            
            # Coimbra
            {
                'name': 'Coimbra',
                'code': 'COIMBRA',
                'postal_code_pattern': r'^30\d{2}',
                'region': 'CENTRO',
                'center_latitude': Decimal('40.2033'),
                'center_longitude': Decimal('-8.4103'),
                'is_urban': True,
                'average_delivery_time_hours': 24,
            },
            
            # Setúbal
            {
                'name': 'Setúbal',
                'code': 'SETUBAL',
                'postal_code_pattern': r'^29\d{2}',
                'region': 'LISBOA',
                'center_latitude': Decimal('38.5244'),
                'center_longitude': Decimal('-8.8926'),
                'is_urban': True,
                'average_delivery_time_hours': 12,
            },
            
            # Algarve
            {
                'name': 'Faro',
                'code': 'FARO',
                'postal_code_pattern': r'^80\d{2}',
                'region': 'ALGARVE',
                 'center_latitude': Decimal('37.0194'),
                'center_longitude': Decimal('-7.9322'),
                'is_urban': True,
                'average_delivery_time_hours': 48,
            },
            {
                'name': 'Portimão',
                'code': 'PORTIMAO',
                'postal_code_pattern': r'^82\d{2}',
                'region': 'ALGARVE',
                'center_latitude': Decimal('37.1364'),
                'center_longitude': Decimal('-8.5376'),
               'is_urban': True,
                'average_delivery_time_hours': 48,
            },
            
            # Alentejo
            {
                'name': 'Évora',
                'code': 'EVORA',
                'postal_code_pattern': r'^70\d{2}',
                'region': 'ALENTEJO',
                'center_latitude': Decimal('38.5667'),
                'center_longitude': Decimal('-7.9000'),
                'is_urban': False,
                'average_delivery_time_hours': 48,
            },
            
            # Outras regiões Norte
            {
                'name': 'Viana do Castelo',
                'code': 'VIANA',
                'postal_code_pattern': r'^49\d{2}',
                'region': 'NORTE',
                'center_latitude': Decimal('41.6917'),
                'center_longitude': Decimal('-8.8344'),
                'is_urban': False,
                'average_delivery_time_hours': 24,
            },
        ]
    
    def _calculate_base_price(self, zone):
        """Calcula preço base baseado em características da zona"""
        
        # Preço base
        base = Decimal('2.00')
        
        # Ajustes por região
        if zone.region == 'LISBOA':
            base = Decimal('2.50')
        elif zone.region == 'NORTE':
            base = Decimal('2.30')
        elif zone.region in ['ALGARVE', 'ALENTEJO']:
            base = Decimal('3.00')  # Mais longe
        
        # Ajuste urbano/rural
        if not zone.is_urban:
            base += Decimal('0.50')
        
        return base
