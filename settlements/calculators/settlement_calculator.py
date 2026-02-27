"""
SettlementCalculator: Motor de cálculo de acertos com motoristas.
Integra com orders_manager, pricing e fleet_management.
"""
from decimal import Decimal
from datetime import datetime, timedelta
from django.db.models import Count, Sum, Q, Avg
from django.utils import timezone


class SettlementCalculator:
    """
    Calcula settlements de motoristas baseado em:
    - Orders entregues no período
    - Tarifas do partner
    - Performance (taxa de sucesso)
    - Claims pendentes
    """
    
    def __init__(self):
        self.debug = []
    
    def calculate_weekly_settlement(self, driver, year, week_number, partner=None):
        """
        Calcula settlement semanal para um motorista.
        
        Args:
            driver: DriverProfile instance
            year: int (2026)
            week_number: int (1-52)
            partner: Partner instance ou None (multi-partner)
        
        Returns:
            DriverSettlement instance (não salvo)
        """
        from settlements.models import DriverSettlement
        from orders_manager.models import Order
        from pricing.models import PartnerTariff
        
        # Calcular datas do período
        period_start, period_end = self._get_week_dates(year, week_number)
        
        self.debug.append(f"Calculando settlement: {driver.nome_completo} - Semana {week_number}/{year}")
        self.debug.append(f"Período: {period_start} → {period_end}")
        
        # Criar settlement
        settlement = DriverSettlement(
            driver=driver,
            partner=partner,
            period_type='WEEKLY',
            week_number=week_number,
            year=year,
            period_start=period_start,
            period_end=period_end
        )
        
        # Buscar pedidos do motorista no período
        orders_query = Order.objects.filter(
            assigned_driver=driver,
            created_at__date__gte=period_start,
            created_at__date__lte=period_end
        )
        
        if partner:
            orders_query = orders_query.filter(partner=partner)
        
        orders = orders_query.select_related('partner')
        
        # Estatísticas
        settlement.total_orders = orders.count()
        settlement.delivered_orders = orders.filter(current_status='DELIVERED').count()
        settlement.failed_orders = settlement.total_orders - settlement.delivered_orders
        
        if settlement.total_orders > 0:
            settlement.success_rate = (
                Decimal(settlement.delivered_orders) / Decimal(settlement.total_orders)
            ) * Decimal('100.00')
        else:
            settlement.success_rate = Decimal('0.00')
        
        self.debug.append(f"Pedidos: {settlement.total_orders} (Entregues: {settlement.delivered_orders}, Taxa: {settlement.success_rate}%)")
        
        # Calcular valor bruto
        gross = Decimal('0.00')
        orders_breakdown = []
        
        for order in orders:
            order_value = self._calculate_order_value(order)
            gross += order_value
            orders_breakdown.append({
                'order_id': order.id,
                'tracking': order.tracking_code,
                'status': order.current_status,
                'value': order_value
            })
        
        settlement.gross_amount = gross
        self.debug.append(f"Valor bruto: €{gross}")
        
        # Calcular bônus por performance
        settlement.bonus_amount = self._calculate_bonus(settlement.gross_amount, settlement.success_rate)
        self.debug.append(f"Bônus: €{settlement.bonus_amount}")
        
        # Buscar claims pendentes
        from settlements.models import DriverClaim
        pending_claims = DriverClaim.objects.filter(
            driver=driver,
            status='APPROVED',
            settlement__isnull=True,  # Ainda não aplicado
            occurred_at__date__gte=period_start,
            occurred_at__date__lte=period_end
        )
        
        claims_total = sum(claim.amount for claim in pending_claims)
        settlement.claims_deducted = claims_total
        self.debug.append(f"Claims: €{claims_total} ({pending_claims.count()} itens)")
        
        # Calcular valor líquido
        total_deductions = (
            settlement.fuel_deduction +
            settlement.claims_deducted +
            settlement.other_deductions
        )
        
        settlement.net_amount = settlement.gross_amount + settlement.bonus_amount - total_deductions
        self.debug.append(f"Valor líquido: €{settlement.net_amount}")
        
        # Atualizar status
        settlement.status = 'CALCULATED'
        settlement.calculated_at = timezone.now()
        
        return settlement
    
    def calculate_monthly_settlement(self, driver, year, month_number, partner=None):
        """Calcula settlement mensal"""
        from settlements.models import DriverSettlement
        from orders_manager.models import Order
        
        # Calcular datas do período
        period_start, period_end = self._get_month_dates(year, month_number)
        
        # Criar settlement
        settlement = DriverSettlement(
            driver=driver,
            partner=partner,
            period_type='MONTHLY',
            month_number=month_number,
            year=year,
            period_start=period_start,
            period_end=period_end
        )
        
        # Lógica similar ao semanal...
        settlement.calculate_settlement()
        
        return settlement
    
    def _get_week_dates(self, year, week_number):
        """Retorna (start_date, end_date) para uma semana ISO"""
        # Primeira segunda-feira do ano
        jan_4 = datetime(year, 1, 4)
        week_start = jan_4 - timedelta(days=jan_4.weekday())  # Segunda-feira
        week_start += timedelta(weeks=week_number - 1)
        week_end = week_start + timedelta(days=6)  # Domingo
        
        return week_start.date(), week_end.date()
    
    def _get_month_dates(self, year, month_number):
        """Retorna (start_date, end_date) para um mês"""
        from calendar import monthrange
        
        start_date = datetime(year, month_number, 1).date()
        last_day = monthrange(year, month_number)[1]
        end_date = datetime(year, month_number, last_day).date()
        
        return start_date, end_date
    
    def _calculate_order_value(self, order):
        """Calcula valor de um pedido baseado em tarifa"""
        from pricing.models import PartnerTariff
        
        try:
            # Buscar tarifa aplicável
            postal_code_prefix = order.postal_code[:4] if order.postal_code else '0000'
            
            tariff = PartnerTariff.objects.filter(
                partner=order.partner,
                postal_zone__code=postal_code_prefix,
                valid_from__lte=order.created_at.date(),
                valid_until__gte=order.created_at.date()
            ).first()
            
            if tariff:
                if order.current_status == 'DELIVERED':
                    return tariff.base_price + tariff.success_bonus
                else:
                    return tariff.base_price - tariff.failure_penalty
            
        except Exception as e:
            self.debug.append(f"Erro calculando order {order.id}: {e}")
        
        # Fallback: valores padrão
        return Decimal('5.00') if order.current_status == 'DELIVERED' else Decimal('2.00')
    
    def _calculate_bonus(self, gross_amount, success_rate):
        """Calcula bônus baseado em taxa de sucesso"""
        if success_rate >= Decimal('95.00'):
            return gross_amount * Decimal('0.10')  # 10% de bônus
        elif success_rate >= Decimal('90.00'):
            return gross_amount * Decimal('0.05')  # 5% de bônus
        elif success_rate >= Decimal('85.00'):
            return gross_amount * Decimal('0.02')  # 2% de bônus
        
        return Decimal('0.00')
    
    def get_debug_log(self):
        """Retorna log de debug do cálculo"""
        return '\n'.join(self.debug)
    
    def calculate_all_weekly_settlements(self, year, week_number):
        """Calcula settlements semanais para todos os motoristas ativos"""
        from drivers_app.models import DriverProfile
        from settlements.models import DriverSettlement
        
        active_drivers = DriverProfile.objects.filter(is_active=True)
        settlements_created = []
        
        for driver in active_drivers:
            try:
                # Verificar se já existe
                existing = DriverSettlement.objects.filter(
                    driver=driver,
                    year=year,
                    week_number=week_number,
                    partner__isnull=True  # Multi-partner
                ).first()
                
                if existing:
                    self.debug.append(f"Settlement já existe para {driver.nome_completo}")
                    continue
                
                # Calcular novo settlement
                settlement = self.calculate_weekly_settlement(driver, year, week_number)
                
                # Salvar apenas se houver pedidos
                if settlement.total_orders > 0:
                    settlement.save()
                    settlements_created.append(settlement)
                    self.debug.append(f"✅ Settlement criado para {driver.nome_completo}")
                
            except Exception as e:
                self.debug.append(f"❌ Erro calculando {driver.nome_completo}: {e}")
        
        return settlements_created
