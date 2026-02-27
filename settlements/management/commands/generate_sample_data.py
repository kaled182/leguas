"""
Management command para gerar dados de exemplo para o app settlements
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
import random
from datetime import date, timedelta
from ordersmanager_paack.models import Driver
from settlements.models import SettlementRun, CompensationPlan, PerPackageRate, ThresholdBonus

class Command(BaseCommand):
    help = 'Gera dados de exemplo para o app settlements'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Número de dias de dados para gerar (padrão: 30)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Limpa dados existentes antes de criar novos',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Limpando dados existentes...')
            SettlementRun.objects.all().delete()
            CompensationPlan.objects.all().delete()
            
        days = options['days']
        self.stdout.write(f'Gerando dados para {days} dias...')
        
        # Obter ou criar motoristas
        drivers = list(Driver.objects.all())
        if not drivers:
            self.stdout.write('Criando motoristas de exemplo...')
            drivers_data = [
                {'driver_id': 'D001', 'name': 'João Silva', 'vehicle': 'Van01', 'vehicle_norm': 'VAN'},
                {'driver_id': 'D002', 'name': 'Maria Santos', 'vehicle': 'Van02', 'vehicle_norm': 'VAN'},
                {'driver_id': 'D003', 'name': 'Pedro Costa', 'vehicle': 'Moto01', 'vehicle_norm': 'MOTO'},
                {'driver_id': 'D004', 'name': 'Ana Ferreira', 'vehicle': 'Van03', 'vehicle_norm': 'VAN'},
                {'driver_id': 'D005', 'name': 'Carlos Oliveira', 'vehicle': 'Moto02', 'vehicle_norm': 'MOTO'},
            ]
            for driver_data in drivers_data:
                driver, created = Driver.objects.get_or_create(
                    driver_id=driver_data['driver_id'],
                    defaults=driver_data
                )
                drivers.append(driver)
        
        # Criar planos de compensação
        self.stdout.write('Criando planos de compensação...')
        for driver in drivers[:3]:  # Apenas para alguns motoristas
            plan, created = CompensationPlan.objects.get_or_create(
                driver=driver,
                client='Paack',
                area_code=None,
                starts_on=date.today() - timedelta(days=60),
                defaults={
                    'base_fixed': Decimal('200.00'),
                    'is_active': True,
                }
            )
            
            if created:
                # Criar taxas por pacote
                PerPackageRate.objects.create(
                    plan=plan,
                    min_delivered=0,
                    max_delivered=50,
                    rate_eur=Decimal('0.30'),
                    priority=1
                )
                PerPackageRate.objects.create(
                    plan=plan,
                    min_delivered=51,
                    max_delivered=100,
                    rate_eur=Decimal('0.40'),
                    priority=2
                )
                PerPackageRate.objects.create(
                    plan=plan,
                    min_delivered=101,
                    max_delivered=None,
                    rate_eur=Decimal('0.50'),
                    priority=3
                )
                
                # Criar bônus por threshold
                ThresholdBonus.objects.create(
                    plan=plan,
                    kind=ThresholdBonus.Kind.ONCE,
                    start_at=80,
                    amount_eur=Decimal('25.00')
                )
        
        # Criar settlement runs
        self.stdout.write('Criando settlement runs...')
        clients = ['Paack', 'Delnext']
        areas = ['A', 'B', 'A-B', None]
        
        start_date = date.today() - timedelta(days=days)
        
        created_count = 0
        for day in range(days):
            current_date = start_date + timedelta(days=day)
            
            # Apenas dias úteis
            if current_date.weekday() < 5:
                for driver in drivers:
                    # 70% de chance de ter uma corrida por dia por motorista
                    if random.random() < 0.7:
                        client = random.choice(clients)
                        area = random.choice(areas)
                        
                        # Gerar números realistas
                        qtd_saida = random.randint(50, 150)
                        qtd_pact = random.randint(int(qtd_saida * 0.8), qtd_saida)
                        qtd_entregue = random.randint(int(qtd_pact * 0.6), qtd_pact)
                        
                        vl_pct = Decimal(str(round(random.uniform(0.25, 0.60), 2)))
                        
                        # Calcular descontos
                        gasoleo = Decimal(str(round(random.uniform(15.0, 45.0), 2)))
                        desconto_tickets = Decimal(str(round(random.uniform(0.0, 20.0), 2)))
                        rec_liq_tickets = Decimal(str(round(random.uniform(0.0, 15.0), 2)))
                        outros = Decimal(str(round(random.uniform(0.0, 10.0), 2)))
                        
                        settlement_run, created = SettlementRun.objects.get_or_create(
                            driver=driver,
                            run_date=current_date,
                            client=client,
                            area_code=area,
                            defaults={
                                'qtd_saida': qtd_saida,
                                'qtd_pact': qtd_pact,
                                'qtd_entregue': qtd_entregue,
                                'vl_pct': vl_pct,
                                'gasoleo': gasoleo,
                                'desconto_tickets': desconto_tickets,
                                'rec_liq_tickets': rec_liq_tickets,
                                'outros': outros,
                            }
                        )
                        
                        if created:
                            created_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Sucesso! Criados {created_count} settlement runs, '
                f'{CompensationPlan.objects.count()} planos de compensação, '
                f'{len(drivers)} motoristas.'
            )
        )
