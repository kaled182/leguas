"""
Models para analytics, forecasting e métricas de performance.

Armazena dados agregados e previsões para dashboards e relatórios.
"""

from django.db import models
from django.utils import timezone
from decimal import Decimal
from datetime import datetime, timedelta
from core.models import Partner


class DailyMetrics(models.Model):
    """
    Métricas diárias agregadas por partner.
    Cacheia dados para dashboards rápidos.
    """
    
    # Identificação
    partner = models.ForeignKey(
        Partner,
        on_delete=models.CASCADE,
        related_name='daily_metrics',
        verbose_name='Parceiro'
    )
    
    date = models.DateField(
        'Data',
        db_index=True
    )
    
    # Métricas de Pedidos
    total_orders = models.IntegerField(
        'Total de Pedidos',
        default=0
    )
    
    delivered_orders = models.IntegerField(
        'Pedidos Entregues',
        default=0
    )
    
    failed_orders = models.IntegerField(
        'Pedidos Falhados',
        default=0
    )
    
    pending_orders = models.IntegerField(
        'Pedidos Pendentes',
        default=0
    )
    
    # Métricas de Performance
    success_rate = models.DecimalField(
        'Taxa de Sucesso (%)',
        max_digits=5,
        decimal_places=2,
        default=0
    )
    
    average_delivery_time_hours = models.DecimalField(
        'Tempo Médio de Entrega (horas)',
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Métricas Financeiras
    total_revenue = models.DecimalField(
        'Receita Total',
        max_digits=10,
        decimal_places=2,
        default=0
    )
    
    total_bonuses = models.DecimalField(
        'Total de Bónus',
        max_digits=10,
        decimal_places=2,
        default=0
    )
    
    total_penalties = models.DecimalField(
        'Total de Penalidades',
        max_digits=10,
        decimal_places=2,
        default=0
    )
    
    # Métricas de Motoristas
    active_drivers_count = models.IntegerField(
        'Motoristas Ativos',
        default=0
    )
    
    # Métricas de Veículos
    active_vehicles_count = models.IntegerField(
        'Veículos Ativos',
        default=0
    )
    
    # Metadata
    calculated_at = models.DateTimeField(
        'Calculado em',
        auto_now=True
    )
    
    class Meta:
        db_table = 'analytics_daily_metrics'
        unique_together = [['partner', 'date']]
        ordering = ['-date', 'partner']
        indexes = [
            models.Index(fields=['partner', '-date']),
            models.Index(fields=['-date', 'success_rate']),
        ]
        verbose_name = 'Métrica Diária'
        verbose_name_plural = 'Métricas Diárias'
    
    def __str__(self):
        return f"{self.partner.name} - {self.date.strftime('%Y-%m-%d')}"
    
    @property
    def failure_rate(self):
        """Taxa de falha"""
        if self.total_orders == 0:
            return Decimal('0.00')
        return Decimal('100.00') - self.success_rate
    
    @property
    def net_revenue(self):
        """Receita líquida (receita - penalidades + bónus)"""
        return self.total_revenue - self.total_penalties + self.total_bonuses


class VolumeForecast(models.Model):
    """
    Previsões de volume de pedidos.
    Usa médias móveis e tendências históricas.
    """
    
    # Identificação
    partner = models.ForeignKey(
        Partner,
        on_delete=models.CASCADE,
        related_name='volume_forecasts',
        verbose_name='Parceiro'
    )
    
    forecast_date = models.DateField(
        'Data da Previsão',
        db_index=True,
        help_text='Data para a qual se prevê o volume'
    )
    
    # Previsões
    predicted_volume = models.IntegerField(
        'Volume Previsto',
        help_text='Número de pedidos previstos'
    )
    
    confidence_level = models.DecimalField(
        'Nível de Confiança (%)',
        max_digits=5,
        decimal_places=2,
        help_text='Confiança estatística da previsão'
    )
    
    lower_bound = models.IntegerField(
        'Limite Inferior',
        help_text='Menor volume esperado (intervalo de confiança)'
    )
    
    upper_bound = models.IntegerField(
        'Limite Superior',
        help_text='Maior volume esperado (intervalo de confiança)'
    )
    
    # Método de Cálculo
    FORECAST_METHODS = [
        ('MA7', 'Média Móvel 7 dias'),
        ('MA30', 'Média Móvel 30 dias'),
        ('EMA', 'Média Móvel Exponencial'),
        ('TREND', 'Análise de Tendência'),
        ('SEASONAL', 'Sazonalidade'),
    ]
    
    method = models.CharField(
        'Método',
        max_length=20,
        choices=FORECAST_METHODS,
        default='MA7'
    )
    
    # Dados Históricos Usados
    historical_days = models.IntegerField(
        'Dias Históricos',
        default=30,
        help_text='Número de dias usados no cálculo'
    )
    
    # Metadata
    created_at = models.DateTimeField(
        'Criado em',
        auto_now_add=True
    )
    
    # Validação (após o dia passar)
    actual_volume = models.IntegerField(
        'Volume Real',
        null=True,
        blank=True,
        help_text='Volume real após o dia passar'
    )
    
    accuracy = models.DecimalField(
        'Acurácia (%)',
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Quão próxima foi a previsão do real'
    )
    
    class Meta:
        db_table = 'analytics_volume_forecast'
        unique_together = [['partner', 'forecast_date', 'method']]
        ordering = ['-forecast_date', 'partner']
        indexes = [
            models.Index(fields=['partner', '-forecast_date']),
            models.Index(fields=['-forecast_date', 'method']),
        ]
        verbose_name = 'Previsão de Volume'
        verbose_name_plural = 'Previsões de Volume'
    
    def __str__(self):
        return (
            f"{self.partner.name} - "
            f"{self.forecast_date.strftime('%Y-%m-%d')} - "
            f"{self.predicted_volume} pedidos"
        )
    
    def calculate_accuracy(self):
        """Calcula acurácia após conhecer o volume real"""
        if self.actual_volume is not None:
            error = abs(self.predicted_volume - self.actual_volume)
            if self.actual_volume > 0:
                accuracy = (1 - (error / self.actual_volume)) * 100
                self.accuracy = max(Decimal('0.00'), Decimal(str(accuracy)))
            else:
                self.accuracy = (
                    Decimal('0.00') if error > 0 else Decimal('100.00')
                )
            self.save()


class PerformanceAlert(models.Model):
    """
    Alertas automáticos de performance.
    Dispara quando métricas ultrapassam thresholds.
    """
    
    # Identificação
    partner = models.ForeignKey(
        Partner,
        on_delete=models.CASCADE,
        related_name='performance_alerts',
        verbose_name='Parceiro'
    )
    
    ALERT_TYPES = [
        ('LOW_SUCCESS', 'Taxa de Sucesso Baixa'),
        ('HIGH_FAILURES', 'Muitas Falhas'),
        ('DELAYED_DELIVERIES', 'Entregas Atrasadas'),
        ('LOW_DRIVER_COUNT', 'Poucos Motoristas Ativos'),
        ('VOLUME_SPIKE', 'Pico de Volume Inesperado'),
        ('REVENUE_DROP', 'Queda de Receita'),
    ]
    
    alert_type = models.CharField(
        'Tipo de Alerta',
        max_length=30,
        choices=ALERT_TYPES,
        db_index=True
    )
    
    SEVERITY_LEVELS = [
        ('INFO', 'Informativo'),
        ('WARNING', 'Aviso'),
        ('CRITICAL', 'Crítico'),
    ]
    
    severity = models.CharField(
        'Severidade',
        max_length=10,
        choices=SEVERITY_LEVELS,
        default='WARNING'
    )
    
    # Detalhes
    date = models.DateField(
        'Data',
        db_index=True
    )
    
    description = models.TextField(
        'Descrição',
        help_text='Descrição detalhada do alerta'
    )
    
    metric_value = models.DecimalField(
        'Valor da Métrica',
        max_digits=10,
        decimal_places=2,
        help_text='Valor que disparou o alerta'
    )
    
    threshold_value = models.DecimalField(
        'Threshold',
        max_digits=10,
        decimal_places=2,
        help_text='Valor do threshold configurado'
    )
    
    # Status
    is_acknowledged = models.BooleanField(
        'Reconhecido',
        default=False,
        help_text='Se o alerta foi visto por um gestor'
    )
    
    acknowledged_at = models.DateTimeField(
        'Reconhecido em',
        null=True,
        blank=True
    )
    
    acknowledged_by = models.CharField(
        'Reconhecido por',
        max_length=100,
        blank=True
    )
    
    # Metadata
    created_at = models.DateTimeField(
        'Criado em',
        auto_now_add=True
    )
    
    class Meta:
        db_table = 'analytics_performance_alert'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['partner', '-created_at']),
            models.Index(fields=['-created_at', 'severity']),
            models.Index(fields=['is_acknowledged', '-created_at']),
        ]
        verbose_name = 'Alerta de Performance'
        verbose_name_plural = 'Alertas de Performance'
    
    def __str__(self):
        return (
            f"{self.get_severity_display()} - "
            f"{self.partner.name} - "
            f"{self.get_alert_type_display()}"
        )
    
    def acknowledge(self, user=None):
        """Marca alerta como reconhecido"""
        self.is_acknowledged = True
        self.acknowledged_at = timezone.now()
        if user:
            self.acknowledged_by = str(user)
        self.save()


class DriverPerformance(models.Model):
    """
    Performance histórica de motoristas.
    Agregado mensal para análise de tendências.
    """
    
    # Identificação
    driver = models.ForeignKey(
        'drivers_app.DriverProfile',
        on_delete=models.CASCADE,
        related_name='performance_history'
    )
    
    month = models.DateField(
        'Mês',
        db_index=True,
        help_text='Primeiro dia do mês (YYYY-MM-01)'
    )
    
    # Métricas do Mês
    total_deliveries = models.IntegerField(
        'Total de Entregas',
        default=0
    )
    
    successful_deliveries = models.IntegerField(
        'Entregas Bem-Sucedidas',
        default=0
    )
    
    failed_deliveries = models.IntegerField(
        'Entregas Falhadas',
        default=0
    )
    
    success_rate = models.DecimalField(
        'Taxa de Sucesso (%)',
        max_digits=5,
        decimal_places=2,
        default=0
    )
    
    # Métricas Financeiras
    total_earnings = models.DecimalField(
        'Ganhos Totais',
        max_digits=10,
        decimal_places=2,
        default=0
    )
    
    total_bonuses = models.DecimalField(
        'Bónus Totais',
        max_digits=10,
        decimal_places=2,
        default=0
    )
    
    total_penalties = models.DecimalField(
        'Penalidades Totais',
        max_digits=10,
        decimal_places=2,
        default=0
    )
    
    # Métricas Temporais
    days_worked = models.IntegerField(
        'Dias Trabalhados',
        default=0
    )
    
    total_hours = models.DecimalField(
        'Horas Totais',
        max_digits=6,
        decimal_places=2,
        default=0
    )
    
    average_deliveries_per_day = models.DecimalField(
        'Média Entregas/Dia',
        max_digits=5,
        decimal_places=2,
        default=0
    )
    
    # Ranking
    rank_in_team = models.IntegerField(
        'Posição no Ranking',
        null=True,
        blank=True,
        help_text='Posição entre todos os motoristas'
    )
    
    # Metadata
    calculated_at = models.DateTimeField(
        'Calculado em',
        auto_now=True
    )
    
    class Meta:
        db_table = 'analytics_driver_performance'
        unique_together = [['driver', 'month']]
        ordering = ['-month', 'driver']
        indexes = [
            models.Index(fields=['driver', '-month']),
            models.Index(fields=['-month', '-success_rate']),
        ]
        verbose_name = 'Performance de Motorista'
        verbose_name_plural = 'Performance de Motoristas'
    
    def __str__(self):
        return (
            f"{self.driver.user.get_full_name()} - "
            f"{self.month.strftime('%Y-%m')}"
        )
    
    @property
    def net_earnings(self):
        """Ganhos líquidos"""
        return (
            self.total_earnings + self.total_bonuses - self.total_penalties
        )

