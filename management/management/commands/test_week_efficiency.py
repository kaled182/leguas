from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, datetime
from django.db.models import Q
from ordersmanager_paack.models import Order

class Command(BaseCommand):
    help = 'Testa o cálculo da eficiência semanal'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Data para calcular (formato: YYYY-MM-DD). Se não fornecida, usa hoje.'
        )

    def handle(self, *args, **options):
        # Determinar data alvo
        if options['date']:
            try:
                target_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(self.style.ERROR('Formato de data inválido. Use YYYY-MM-DD'))
                return
        else:
            target_date = timezone.now().date()

        self.stdout.write(f"\n=== TESTE EFICIÊNCIA SEMANAL ===")
        self.stdout.write(f"Data alvo: {target_date} ({target_date.strftime('%A')})")
        
        # Configurar início da semana (segunda-feira = 0, domingo = 6)
        days_since_monday = target_date.weekday()
        week_start = target_date - timedelta(days=days_since_monday)
        
        # Se hoje for domingo, incluir até domingo. Senão, só até hoje
        if target_date.weekday() == 6:  # domingo
            week_end = target_date
        else:
            week_end = target_date
        
        self.stdout.write(f"Início da semana: {week_start} ({week_start.strftime('%A')})")
        self.stdout.write(f"Fim da semana: {week_end} ({week_end.strftime('%A')})")
        self.stdout.write("-" * 50)
        
        week_efficiency_rates = []
        current_day = week_start
        
        while current_day <= week_end:
            # Entregas do dia
            day_deliveries = Order.objects.filter(
                actual_delivery_date=current_day,
                is_delivered=True,
                status='delivered'
            ).count()
            
            # Falhas do dia  
            day_fails = Order.objects.filter(
                actual_delivery_date=current_day
            ).filter(
                Q(status__in=['failed', 'returned', 'cancelled']) |
                Q(simplified_order_status__in=['failed', 'undelivered'])
            ).count()
            
            # Total de tentativas do dia
            day_total_attempts = day_deliveries + day_fails
            
            # Taxa de sucesso do dia
            if day_total_attempts > 0:
                day_success_rate = (day_deliveries / day_total_attempts) * 100
                week_efficiency_rates.append(day_success_rate)
                self.stdout.write(
                    f"{current_day} ({current_day.strftime('%A')}): "
                    f"{day_deliveries} entregas, {day_fails} falhas, "
                    f"{day_total_attempts} tentativas = {day_success_rate:.1f}%"
                )
            else:
                self.stdout.write(
                    f"{current_day} ({current_day.strftime('%A')}): "
                    f"0 tentativas - dia ignorado"
                )
            
            current_day += timedelta(days=1)
        
        # Calcular média das taxas de sucesso diárias
        if week_efficiency_rates:
            week_avg = sum(week_efficiency_rates) / len(week_efficiency_rates)
            week_efficiency = f"{week_avg:.1f}%"
            
            self.stdout.write("-" * 50)
            self.stdout.write(f"Taxas diárias: {[f'{rate:.1f}%' for rate in week_efficiency_rates]}")
            self.stdout.write(f"Soma: {sum(week_efficiency_rates):.1f}")
            self.stdout.write(f"Quantidade de dias: {len(week_efficiency_rates)}")
            self.stdout.write(f"Média: {sum(week_efficiency_rates):.1f} / {len(week_efficiency_rates)} = {week_avg:.1f}%")
        else:
            week_efficiency = "0.0%"
            self.stdout.write("Nenhum dia com tentativas - eficiência = 0.0%")
        
        self.stdout.write("-" * 50)
        self.stdout.write(self.style.SUCCESS(f"RESULTADO FINAL: {week_efficiency}"))
        self.stdout.write("=== FIM TESTE ===\n")
