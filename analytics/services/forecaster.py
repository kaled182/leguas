"""
Forecaster de volume de pedidos.

Usa médias móveis e análise de tendências para prever volume futuro.
"""

from django.db.models import Count
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import statistics

from analytics.models import VolumeForecast, DailyMetrics
from core.models import Partner


class VolumeForecaster:
    """
    Prevê volume de pedidos usando diferentes métodos estatísticos.
    """
    
    def __init__(self, partner=None):
        self.partner = partner
    
    def forecast_next_days(self, days=7, method='MA7', partner=None):
        """
        Gera previsões para os próximos N dias.
        
        Args:
            days: Número de dias para prever
            method: Método de forecasting (MA7, MA30, EMA, TREND, SEASONAL)
            partner: Partner para prever (usa self.partner se não informado)
        
        Returns:
            Lista de VolumeForecast objects
        """
        target_partner = partner or self.partner
        if not target_partner:
            raise ValueError("Partner must be provided either in __init__ or as argument")
        
        forecasts = []
        
        for i in range(1, days + 1):
            forecast_date = (timezone.now() + timedelta(days=i)).date()
            forecast = self.create_forecast(forecast_date, method, target_partner)
            if forecast:
                forecasts.append(forecast)
        
        return forecasts
    
    def create_forecast(self, forecast_date, method='MA7', partner=None):
        """
        Cria previsão para uma data específica.
        
        Args:
            forecast_date: Data da previsão
            method: Método de cálculo
            partner: Partner para prever (usa self.partner se não informado)
        
        Returns:
            VolumeForecast object
        """
        target_partner = partner or self.partner
        if not target_partner:
            raise ValueError("Partner must be provided either in __init__ or as argument")
        
        # Temporarily set partner for internal methods
        original_partner = self.partner
        self.partner = target_partner
        
        try:
            # Selecionar calculador baseado no método
            if method == 'MA7':
                predicted, confidence, lower, upper = self._moving_average_7()
                historical_days = 7
            elif method == 'MA30':
                predicted, confidence, lower, upper = self._moving_average_30()
                historical_days = 30
            elif method == 'EMA':
                predicted, confidence, lower, upper = self._exponential_moving_average()
                historical_days = 14
            elif method == 'TREND':
                predicted, confidence, lower, upper = self._trend_analysis()
                historical_days = 30
            elif method == 'SEASONAL':
                predicted, confidence, lower, upper = self._seasonal_analysis()
                historical_days = 90
            else:
                raise ValueError(f"Método desconhecido: {method}")
            
            # Criar ou atualizar forecast
            forecast, created = VolumeForecast.objects.update_or_create(
                partner=self.partner,
                forecast_date=forecast_date,
                method=method,
                defaults={
                    'predicted_volume': predicted,
                    'confidence_level': confidence,
                    'lower_bound': lower,
                    'upper_bound': upper,
                    'historical_days': historical_days,
                }
            )
            
            return forecast
        finally:
            # Restore original partner
            self.partner = original_partner
    
    def _moving_average_7(self):
        """Média móvel de 7 dias"""
        volumes = self._get_historical_volumes(days=7)
        
        if len(volumes) < 3:
            return 0, Decimal('0.00'), 0, 0
        
        avg = statistics.mean(volumes)
        stdev = statistics.stdev(volumes) if len(volumes) > 1 else 0
        
        predicted = int(avg)
        confidence = self._calculate_confidence(volumes)
        lower = max(0, int(avg - stdev))
        upper = int(avg + stdev)
        
        return predicted, confidence, lower, upper
    
    def _moving_average_30(self):
        """Média móvel de 30 dias"""
        volumes = self._get_historical_volumes(days=30)
        
        if len(volumes) < 7:
            return 0, Decimal('0.00'), 0, 0
        
        avg = statistics.mean(volumes)
        stdev = statistics.stdev(volumes) if len(volumes) > 1 else 0
        
        predicted = int(avg)
        confidence = self._calculate_confidence(volumes)
        lower = max(0, int(avg - 1.5 * stdev))
        upper = int(avg + 1.5 * stdev)
        
        return predicted, confidence, lower, upper
    
    def _exponential_moving_average(self):
        """Média móvel exponencial (mais peso nos dados recentes)"""
        volumes = self._get_historical_volumes(days=14)
        
        if len(volumes) < 3:
            return 0, Decimal('0.00'), 0, 0
        
        # EMA com alpha = 0.3 (30% peso nos dados recentes)
        alpha = 0.3
        ema = volumes[0]
        
        for vol in volumes[1:]:
            ema = alpha * vol + (1 - alpha) * ema
        
        predicted = int(ema)
        
        # Variância baseada nos últimos dias
        recent_volumes = volumes[-7:]
        stdev = statistics.stdev(recent_volumes) if len(recent_volumes) > 1 else 0
        
        confidence = self._calculate_confidence(recent_volumes)
        lower = max(0, int(ema - stdev))
        upper = int(ema + stdev)
        
        return predicted, confidence, lower, upper
    
    def _trend_analysis(self):
        """Análise de tendência (crescimento/decrescimento)"""
        volumes = self._get_historical_volumes(days=30)
        
        if len(volumes) < 7:
            return 0, Decimal('0.00'), 0, 0
        
        # Calcular tendência (regressão linear simplificada)
        n = len(volumes)
        x = list(range(n))
        y = volumes
        
        # Slope (m) e intercept (b) da linha y = mx + b
        x_mean = statistics.mean(x)
        y_mean = statistics.mean(y)
        
        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return int(y_mean), Decimal('50.00'), int(y_mean), int(y_mean)
        
        slope = numerator / denominator
        intercept = y_mean - slope * x_mean
        
        # Prever próximo valor
        next_x = n
        predicted = int(slope * next_x + intercept)
        predicted = max(0, predicted)
        
        # Confiança baseada em R²
        stdev = statistics.stdev(volumes)
        confidence = self._calculate_confidence(volumes)
        
        lower = max(0, int(predicted - stdev))
        upper = int(predicted + stdev)
        
        return predicted, confidence, lower, upper
    
    def _seasonal_analysis(self):
        """Análise sazonal (dia da semana)"""
        from orders_manager.models import Order
        
        # Buscar dados dos últimos 90 dias
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=90)
        
        # Agrupar por dia da semana
        weekday_volumes = {i: [] for i in range(7)}
        
        current_date = start_date
        while current_date <= end_date:
            weekday = current_date.weekday()
            
            volume = Order.objects.filter(
                partner=self.partner,
                created_at__date=current_date
            ).count()
            
            weekday_volumes[weekday].append(volume)
            current_date += timedelta(days=1)
        
        # Calcular média por dia da semana
        tomorrow = (timezone.now() + timedelta(days=1)).date()
        tomorrow_weekday = tomorrow.weekday()
        
        volumes = weekday_volumes[tomorrow_weekday]
        
        if len(volumes) < 2:
            return 0, Decimal('0.00'), 0, 0
        
        avg = statistics.mean(volumes)
        stdev = statistics.stdev(volumes) if len(volumes) > 1 else 0
        
        predicted = int(avg)
        confidence = self._calculate_confidence(volumes)
        lower = max(0, int(avg - stdev))
        upper = int(avg + stdev)
        
        return predicted, confidence, lower, upper
    
    def _get_historical_volumes(self, days=30):
        """Busca volumes históricos"""
        from orders_manager.models import Order
        
        volumes = []
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Tentar usar DailyMetrics cache
        metrics = DailyMetrics.objects.filter(
            partner=self.partner,
            date__range=[start_date, end_date]
        ).order_by('date')
        
        if metrics.count() >= days * 0.7:  # Pelo menos 70% dos dados
            volumes = [m.total_orders for m in metrics]
        else:
            # Calcular manualmente
            current_date = start_date
            while current_date <= end_date:
                volume = Order.objects.filter(
                    partner=self.partner,
                    created_at__date=current_date
                ).count()
                volumes.append(volume)
                current_date += timedelta(days=1)
        
        return volumes
    
    def _calculate_confidence(self, volumes):
        """
        Calcula nível de confiança baseado na consistência dos dados.
        
        Menor variação = maior confiança
        """
        if len(volumes) < 2:
            return Decimal('0.00')
        
        mean = statistics.mean(volumes)
        if mean == 0:
            return Decimal('50.00')
        
        stdev = statistics.stdev(volumes)
        
        # Coeficiente de variação (CV)
        cv = (stdev / mean) * 100
        
        # Converter CV em confiança (invertido)
        # CV baixo = confiança alta
        if cv < 10:
            confidence = 95
        elif cv < 20:
            confidence = 85
        elif cv < 30:
            confidence = 75
        elif cv < 40:
            confidence = 65
        else:
            confidence = 50
        
        return Decimal(str(confidence))


def forecast_volume_for_partner(partner, days=7, method='MA7'):
    """Helper function para prever volume"""
    forecaster = VolumeForecaster(partner)
    return forecaster.forecast_next_days(days, method)


def forecast_all_partners(days=7):
    """Prevê volume para todos os partners ativos"""
    forecasts = []
    
    for partner in Partner.objects.filter(is_active=True):
        partner_forecasts = forecast_volume_for_partner(partner, days)
        forecasts.extend(partner_forecasts)
    
    return forecasts
