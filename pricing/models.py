from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from datetime import date
from core.models import Partner


class PostalZone(models.Model):
    """
    Zonas postais para segmentação de tarifas.
    Permite diferentes preços por região geográfica.
    """
    
    # Identificação
    name = models.CharField(
        'Nome da Zona',
        max_length=100,
        help_text='Nome descritivo (e.g., "Lisboa Centro")'
    )
    
    code = models.CharField(
        'Código',
        max_length=20,
        unique=True,
        help_text='Código único da zona (e.g., "LIS-CENTRO", "PORTO-NORTE")'
    )
    
    # Padrão de Códigos Postais
    postal_code_pattern = models.CharField(
        'Padrão de Códigos Postais',
        max_length=200,
        help_text='Padrão regex (e.g., "^11\\d{2}" para Lisboa)'
    )
    
    # Região
    region = models.CharField(
        'Região',
        max_length=100,
        blank=True,
        choices=[
            ('NORTE', 'Norte'),
            ('CENTRO', 'Centro'),
            ('LISBOA', 'Lisboa e Vale do Tejo'),
            ('ALENTEJO', 'Alentejo'),
            ('ALGARVE', 'Algarve'),
            ('MADEIRA', 'Madeira'),
            ('ACORES', 'Açores'),
        ]
    )
    
    # Coordenadas (para cálculo de distâncias)
    center_latitude = models.DecimalField(
        'Latitude Central',
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='Latitude do centro da zona'
    )
    
    center_longitude = models.DecimalField(
        'Longitude Central',
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='Longitude do centro da zona'
    )
    
    # Características Operacionais
    is_urban = models.BooleanField(
        'Zona Urbana',
        default=True,
        help_text='Se zona é urbana (vs. rural)'
    )
    
    average_delivery_time_hours = models.IntegerField(
        'Tempo Médio de Entrega (horas)',
        default=24,
        help_text='Tempo médio estimado para entrega nesta zona'
    )
    
    # Status
    is_active = models.BooleanField(
        'Ativa',
        default=True
    )
    
    # Observações
    notes = models.TextField(
        'Observações',
        blank=True
    )
    
    # Metadados
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Zona Postal'
        verbose_name_plural = 'Zonas Postais'
        ordering = ['region', 'name']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['region', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    def clean(self):
        """Validações customizadas"""
        super().clean()
        
        # Normalizar código (uppercase, sem espaços)
        if self.code:
            self.code = self.code.upper().strip().replace(' ', '-')
    
    def matches_postal_code(self, postal_code):
        """
        Verifica se um código postal pertence a esta zona.
        
        Args:
            postal_code: Código postal no formato XXXX-XXX
        
        Returns:
            Boolean indicando se código postal pertence à zona
        """
        import re
        
        # Remover traço para comparação
        clean_code = postal_code.replace('-', '')
        
        try:
            pattern = self.postal_code_pattern
            return bool(re.match(pattern, clean_code))
        except re.error:
            return False
    
    @classmethod
    def find_zone_for_postal_code(cls, postal_code):
        """
        Encontra a zona postal para um código postal.
        
        Args:
            postal_code: Código postal no formato XXXX-XXX
        
        Returns:
            PostalZone instance ou None
        """
        zones = cls.objects.filter(is_active=True)
        
        for zone in zones:
            if zone.matches_postal_code(postal_code):
                return zone
        
        return None


class PartnerTariff(models.Model):
    """
    Tarifa de entrega por parceiro e zona postal.
    Define quanto será pago por entrega bem-sucedida, e penalizações.
    """
    
    # Parceiro e Zona
    partner = models.ForeignKey(
        Partner,
        on_delete=models.CASCADE,
        related_name='tariffs',
        verbose_name='Parceiro'
    )
    
    postal_zone = models.ForeignKey(
        PostalZone,
        on_delete=models.CASCADE,
        related_name='tariffs',
        verbose_name='Zona Postal'
    )
    
    # Preços Base
    base_price = models.DecimalField(
        'Preço Base',
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text='Preço base por entrega (€)'
    )
    
    # Bónus por Sucesso
    success_bonus = models.DecimalField(
        'Bónus por Entrega',
        max_digits=6,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Bónus adicional por entrega bem-sucedida (€)'
    )
    
    # Penalizações
    failure_penalty = models.DecimalField(
        'Penalização por Falha',
        max_digits=6,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Dedução por falha na entrega (€)'
    )
    
    late_delivery_penalty = models.DecimalField(
        'Penalização por Atraso',
        max_digits=6,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Dedução por entrega atrasada (€)'
    )
    
    # Modificadores
    weekend_multiplier = models.DecimalField(
        'Multiplicador Fim de Semana',
        max_digits=4,
        decimal_places=2,
        default=1.0,
        validators=[MinValueValidator(0)],
        help_text='Multiplicador fim de semana (1.0 = sem alteração)'
    )
    
    express_multiplier = models.DecimalField(
        'Multiplicador Expresso',
        max_digits=4,
        decimal_places=2,
        default=1.5,
        validators=[MinValueValidator(0)],
        help_text='Multiplicador para entregas expressas'
    )
    
    # Validade
    valid_from = models.DateField(
        'Válido Desde',
        default=date.today,
        db_index=True,
        help_text='Data a partir da qual esta tarifa é aplicável'
    )
    
    valid_until = models.DateField(
        'Válido Até',
        null=True,
        blank=True,
        db_index=True,
        help_text='Data limite (vazio = sem limite)'
    )
    
    # Status
    is_active = models.BooleanField(
        'Ativa',
        default=True
    )
    
    # Observações
    notes = models.TextField(
        'Observações',
        blank=True
    )
    
    # Metadados
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Tarifa de Parceiro'
        verbose_name_plural = 'Tarifas de Parceiros'
        ordering = ['partner', 'postal_zone', '-valid_from']
        # Uma tarifa por parceiro/zona/período
        unique_together = [['partner', 'postal_zone', 'valid_from']]
        indexes = [
            models.Index(fields=['partner', 'postal_zone', 'is_active']),
            models.Index(fields=['valid_from', 'valid_until']),
        ]
    
    def __str__(self):
        return (
            f"{self.partner.name} - {self.postal_zone.name} "
            f"(€{self.base_price})"
        )
    
    def clean(self):
        """Validações customizadas"""
        super().clean()
        
        # Validar período de validade
        if self.valid_until and self.valid_from:
            if self.valid_until < self.valid_from:
                raise ValidationError({
                    'valid_until': (
                        'Data final deve ser posterior à data inicial'
                    )
                })
    
    def is_valid_on_date(self, check_date=None):
        """
        Verifica se tarifa está válida numa determinada data.
        
        Args:
            check_date: Data a verificar (default: hoje)
        
        Returns:
            Boolean indicando se tarifa está válida
        """
        if not self.is_active:
            return False
        
        if check_date is None:
            check_date = date.today()
        
        # Verificar se está dentro do período
        if check_date < self.valid_from:
            return False
        
        if self.valid_until and check_date > self.valid_until:
            return False
        
        return True
    
    def calculate_price(self, delivery_date=None, is_express=False, is_weekend=False):
        """
        Calcula o preço final considerando modificadores.
        
        Args:
            delivery_date: Data da entrega (default: hoje)
            is_express: Se é entrega expressa
            is_weekend: Se é entrega em fim de semana
        
        Returns:
            Decimal com preço calculado
        """
        price = self.base_price + self.success_bonus
        
        # Aplicar multiplicador de fim de semana
        if is_weekend:
            price *= self.weekend_multiplier
        
        # Aplicar multiplicador expresso
        if is_express:
            price *= self.express_multiplier
        
        return price.quantize(models.Decimal('0.01'))
    
    @classmethod
    def get_tariff_for_order(cls, partner, postal_code, delivery_date=None):
        """
        Encontra a tarifa aplicável para um pedido.
        
        Args:
            partner: Instância de Partner
            postal_code: Código postal da entrega
            delivery_date: Data da entrega (default: hoje)
        
        Returns:
            PartnerTariff instance ou None
        """
        if delivery_date is None:
            delivery_date = date.today()
        
        # Encontrar zona postal
        zone = PostalZone.find_zone_for_postal_code(postal_code)
        
        if not zone:
            return None
        
        # Encontrar tarifa válida
        tariffs = cls.objects.filter(
            partner=partner,
            postal_zone=zone,
            is_active=True,
            valid_from__lte=delivery_date,
        ).filter(
            models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=delivery_date)
        ).order_by('-valid_from')
        
        return tariffs.first()


class PriceCalculator:
    """
    Serviço para cálculo de preços de entregas.
    Encapsula lógica de pricing complexa.
    """
    
    @staticmethod
    def calculate_delivery_price(order):
        """
        Calcula preço para um pedido.
        
        Args:
            order: Instância de Order
        
        Returns:
            Dict com breakdown do preço
        """
        tariff = PartnerTariff.get_tariff_for_order(
            partner=order.partner,
            postal_code=order.postal_code,
            delivery_date=order.scheduled_delivery or date.today()
        )
        
        if not tariff:
            return {
                'success': False,
                'error': 'No tariff found for this order',
                'base_price': 0,
                'total': 0,
            }
        
        # Verificar se é fim de semana
        delivery_date = order.scheduled_delivery or date.today()
        is_weekend = delivery_date.weekday() >= 5  # 5=Sábado, 6=Domingo
        
        # Calcular preço base
        base_price = tariff.calculate_price(
            delivery_date=delivery_date,
            is_express=False,  # TODO: Adicionar flag is_express no Order
            is_weekend=is_weekend
        )
        
        # Aplicar penalizações se aplicável
        penalties = models.Decimal('0.00')
        
        if order.current_status == 'RETURNED':
            penalties += tariff.failure_penalty
        
        if order.is_overdue and order.current_status != 'DELIVERED':
            penalties += tariff.late_delivery_penalty
        
        total = base_price - penalties
        
        return {
            'success': True,
            'tariff_id': tariff.id,
            'base_price': float(base_price),
            'penalties': float(penalties),
            'total': float(max(total, 0)),  # Não pode ser negativo
            'zone': tariff.postal_zone.name,
            'is_weekend': is_weekend,
        }
