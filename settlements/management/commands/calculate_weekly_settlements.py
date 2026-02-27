"""
Management command para calcular settlements semanais.
Execução: python manage.py calculate_weekly_settlements --week 10 --year 2026
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime
from settlements.calculators import SettlementCalculator


class Command(BaseCommand):
    help = 'Calcula settlements semanais para todos os motoristas ativos'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--week',
            type=int,
            help='Número da semana (1-52). Se não informado, usa semana atual'
        )
        parser.add_argument(
            '--year',
            type=int,
            help='Ano. Se não informado, usa ano atual'
        )
        parser.add_argument(
            '--driver-id',
            type=int,
            help='ID do motorista específico. Se não informado, calcula para todos'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Executa sem salvar no banco (teste)'
        )
    
    def handle(self, *args, **options):
        # Determinar semana e ano
        now = timezone.now()
        year = options['year'] or now.year
        week = options['week'] or now.isocalendar()[1]
        driver_id = options['driver_id']
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 Modo DRY RUN - Nenhuma alteração será salva\n'))
        
        self.stdout.write(
            self.style.SUCCESS(f'📊 Calculando settlements - Semana {week}/{year}\n')
        )
        
        # Criar calculator
        calculator = SettlementCalculator()
        
        if driver_id:
            # Calcular para motorista específico
            from drivers_app.models import DriverProfile
            
            try:
                driver = DriverProfile.objects.get(id=driver_id)
                self.stdout.write(f'Processando motorista: {driver.nome_completo}')
                
                settlement = calculator.calculate_weekly_settlement(driver, year, week)
                
                if not dry_run:
                    settlement.save()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ Settlement criado: {settlement.driver.nome_completo} - '
                            f'€{settlement.net_amount} ({settlement.total_orders} pedidos)'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'[DRY RUN] Settlement: {settlement.driver.nome_completo} - '
                            f'€{settlement.net_amount} ({settlement.total_orders} pedidos)'
                        )
                    )
                
                # Mostrar debug
                self.stdout.write('\n📋 Detalhes do cálculo:')
                self.stdout.write(calculator.get_debug_log())
                
            except DriverProfile.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'❌ Motorista com ID {driver_id} não encontrado')
                )
                return
        
        else:
            # Calcular para todos os motoristas
            if not dry_run:
                settlements = calculator.calculate_all_weekly_settlements(year, week)
                
                self.stdout.write('\n' + '='*60)
                self.stdout.write(self.style.SUCCESS(f'✅ {len(settlements)} settlements criados'))
                
                # Estatísticas
                total_amount = sum(s.net_amount for s in settlements)
                total_orders = sum(s.total_orders for s in settlements)
                
                self.stdout.write(f'Total a pagar: €{total_amount}')
                self.stdout.write(f'Total de pedidos: {total_orders}')
                
                # Listar settlements criados
                self.stdout.write('\n📋 Settlements criados:')
                for settlement in settlements:
                    self.stdout.write(
                        f'  • {settlement.driver.nome_completo}: €{settlement.net_amount} '
                        f'({settlement.total_orders} pedidos, {settlement.success_rate}% sucesso)'
                    )
            
            else:
                # Dry run: apenas contar
                from drivers_app.models import DriverProfile
                active_drivers = DriverProfile.objects.filter(is_active=True).count()
                self.stdout.write(
                    self.style.WARNING(
                        f'[DRY RUN] Seria calculado para {active_drivers} motoristas ativos'
                    )
                )
        
        # Mostrar log de debug
        if calculator.debug:
            self.stdout.write('\n📋 Log completo:')
            self.stdout.write(calculator.get_debug_log())
