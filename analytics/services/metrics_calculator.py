"""
Calculador de métricas diárias agregadas.

Processa pedidos e gera estatísticas para dashboards.
"""

from django.db.models import Count, Avg, Sum, Q, F
from django.utils import timezone
from datetime import datetime, timedelta, date
from decimal import Decimal

from analytics.models import DailyMetrics
from core.models import Partner


class MetricsCalculator:
    """
    Calcula métricas diárias agregadas por partner.
    """
    
    def __init__(self, partner=None):
        self.partner = partner
    
    def calculate_daily_metrics(self, target_date=None):
        """
        Calcula métricas para uma data específica.
        
        Args:
            target_date: Data para calcular (default: ontem)
        
        Returns:
            DailyMetrics object ou lista de DailyMetrics
        """
        if target_date is None:
            target_date = (timezone.now() - timedelta(days=1)).date()
        
        if self.partner:
            return self._calculate_for_partner(self.partner, target_date)
        else:
            # Calcular para todos os partners
            metrics = []
            for partner in Partner.objects.filter(is_active=True):
                metric = self._calculate_for_partner(partner, target_date)
                metrics.append(metric)
            return metrics
    
    def _calculate_for_partner(self, partner, target_date):
        """Calcula métricas para um partner específico"""
        from orders_manager.models import Order
        from drivers_app.models import DriverProfile
        from fleet_management.models import Vehicle
        
        # Buscar ou criar métrica
        metric, created = DailyMetrics.objects.get_or_create(
            partner=partner,
            date=target_date
        )
        
        # Filtrar pedidos do dia
        orders = Order.objects.filter(
            partner=partner,
            created_at__date=target_date
        )
        
        # Métricas de Pedidos
        metric.total_orders = orders.count()
        metric.delivered_orders = orders.filter(
            current_status='DELIVERED'
        ).count()
        metric.failed_orders = orders.filter(
            current_status__in=['INCIDENT', 'RETURNED', 'CANCELLED']
        ).count()
        metric.pending_orders = orders.filter(
            current_status__in=['PENDING', 'ASSIGNED', 'IN_TRANSIT']
        ).count()
        
        # Taxa de Sucesso
        if metric.total_orders > 0:
            metric.success_rate = Decimal(
                (metric.delivered_orders / metric.total_orders) * 100
            )
        else:
            metric.success_rate = Decimal('0.00')
        
        # Tempo Médio de Entrega
        delivered = orders.filter(
            current_status='DELIVERED',
            created_at__isnull=False,
            updated_at__isnull=False
        )
        
        if delivered.exists():
            avg_seconds = delivered.annotate(
                delivery_time=F('updated_at') - F('created_at')
            ).aggregate(
                avg=Avg('delivery_time')
            )['avg']
            
            if avg_seconds:
                metric.average_delivery_time_hours = Decimal(
                    str(avg_seconds.total_seconds() / 3600)
                )
        
        # Métricas Financeiras (se pricing ativo)
        from django.conf import settings
        use_pricing = getattr(settings, 'USE_POSTAL_ZONE_PRICING', False)
        
        if use_pricing:
            from pricing.models import PriceCalculator
            
            calculator = PriceCalculator()
            total_revenue = Decimal('0.00')
            total_bonuses = Decimal('0.00')
            total_penalties = Decimal('0.00')
            
            for order in orders:
                price_breakdown = calculator.calculate_delivery_price(order)
                total_revenue += price_breakdown.get('total', Decimal('0.00'))
                total_bonuses += price_breakdown.get('bonuses', Decimal('0.00'))
                total_penalties += price_breakdown.get(
                    'penalties', Decimal('0.00')
                )
            
            metric.total_revenue = total_revenue
            metric.total_bonuses = total_bonuses
            metric.total_penalties = total_penalties
        
        # Motoristas Ativos
        metric.active_drivers_count = DriverProfile.objects.filter(
            is_active=True
        ).count()
        
        # Veículos Ativos
        metric.active_vehicles_count = Vehicle.objects.filter(
            status='ACTIVE'
        ).count()
        
        metric.save()
        
        return metric
    
    def backfill_metrics(self, start_date, end_date=None):
        """
        Preenche métricas para um período histórico.
        
        Args:
            start_date: Data inicial
            end_date: Data final (default: ontem)
            
        Returns:
            dict with created, updated, skipped, errors counts and details list
        """
        if end_date is None:
            end_date = (timezone.now() - timedelta(days=1)).date()
        
        current_date = start_date
        results = {
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
            'details': []
        }
        
        while current_date <= end_date:
            try:
                # Get all partners
                for partner in Partner.objects.filter(is_active=True):
                    try:
                        from analytics.models import DailyMetrics
                        
                        # Check if exists
                        existing = DailyMetrics.objects.filter(
                            partner=partner,
                            date=current_date
                        ).first()
                        
                        if existing:
                            results['skipped'] += 1
                            results['details'].append({
                                'date': str(current_date),
                                'partner_id': partner.id,
                                'status': 'skipped'
                            })
                        else:
                            # Calculate metrics
                            metric = self._calculate_for_partner(partner, current_date)
                            results['created'] += 1
                            results['details'].append({
                                'date': str(current_date),
                                'partner_id': partner.id,
                                'status': 'created'
                            })
                    except Exception as e:
                        results['errors'] += 1
                        results['details'].append({
                            'date': str(current_date),
                            'partner_id': partner.id,
                            'status': 'error',
                            'error': str(e)
                        })
            
            except Exception as e:
                results['errors'] += 1
                results['details'].append({
                    'date': str(current_date),
                    'partner_id': None,
                    'status': 'error',
                    'error': str(e)
                })
            
            current_date += timedelta(days=1)
        
        return results


def calculate_metrics_for_date(target_date):
    """Helper function para calcular métricas de uma data"""
    calculator = MetricsCalculator()
    return calculator.calculate_daily_metrics(target_date)


def calculate_metrics_for_yesterday():
    """Helper function para calcular métricas de ontem"""
    yesterday = (timezone.now() - timedelta(days=1)).date()
    return calculate_metrics_for_date(yesterday)
