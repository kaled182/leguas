# ordersmanager/models.py
from django.db import models
from django.db.models import Count, Case, When, Q
from datetime import datetime, timedelta

# Custom QuerySets para consultas otimizadas
class OrderQuerySet(models.QuerySet):
    def delivered(self):
        return self.filter(status='delivered')
    
    def failed(self):
        return self.filter(simplified_order_status__in=['failed', 'undelivered'])
    
    def pending(self):
        return self.filter(simplified_order_status='to_attempt')
    
    def by_driver(self, driver):
        return self.filter(dispatch__driver=driver)
    
    def by_driver_id(self, driver_id):
        return self.filter(dispatch__driver__driver_id=driver_id)
    
    def by_date_range(self, start_date, end_date):
        return self.filter(intended_delivery_date__range=[start_date, end_date])
    
    def delivered_on_date(self, date):
        return self.filter(actual_delivery_date=date, status='delivered')
    
    def with_multiple_attempts(self):
        return self.annotate(
            attempt_count=Count('deliveryattempt')
        ).filter(attempt_count__gt=1)
    
    def by_retailer(self, retailer):
        return self.filter(retailer=retailer)

class OrderManager(models.Manager):
    def get_queryset(self):
        return OrderQuerySet(self.model, using=self._db)
    
    def delivered(self):
        return self.get_queryset().delivered()
    
    def failed(self):
        return self.get_queryset().failed()
    
    def pending(self):
        return self.get_queryset().pending()
    
    def by_driver(self, driver):
        return self.get_queryset().by_driver(driver)

class DriverQuerySet(models.QuerySet):
    def with_delivery_stats(self, start_date=None, end_date=None):
        queryset = self.annotate(
            total_orders=Count('dispatch__order'),
            delivered_orders=Count(
                'dispatch__order',
                filter=Q(dispatch__order__status='delivered')
            ),
            failed_orders=Count(
                'dispatch__order',
                filter=Q(dispatch__order__simplified_order_status='failed')
            )
        )
        
        if start_date and end_date:
            queryset = queryset.filter(
                dispatch__order__intended_delivery_date__range=[start_date, end_date]
            )
        
        return queryset

class DriverManager(models.Manager):
    def get_queryset(self):
        return DriverQuerySet(self.model, using=self._db)
    
    def with_stats(self, start_date=None, end_date=None):
        return self.get_queryset().with_delivery_stats(start_date, end_date)

# Models principais
class Order(models.Model):
    # Identificação da ordem
    uuid = models.UUIDField(unique=True, db_index=True)
    order_id = models.CharField(max_length=50, db_index=True)
    order_type = models.CharField(max_length=50)
    service_type = models.CharField(max_length=50)
    status = models.CharField(max_length=50, db_index=True)
    cod = models.CharField(max_length=50, blank=True, null=True)
    
    # Informações do pacote
    packages_count = models.IntegerField()
    packages_barcode = models.CharField(max_length=255)
    
    # Informações do varejista
    retailer = models.CharField(max_length=100, db_index=True)
    retailer_order_number = models.CharField(max_length=100)
    retailer_sales_number = models.CharField(max_length=100)

    # Informações do cliente
    client_address = models.TextField()
    client_address_text = models.TextField()
    client_phone = models.CharField(max_length=50)
    client_email = models.EmailField()

    # Datas de entrega
    intended_delivery_date = models.DateField(db_index=True)
    actual_delivery_date = models.DateField(blank=True, null=True, db_index=True)
    delivery_timeslot = models.CharField(max_length=50)

    # Status simplificado para facilitar consultas
    simplified_order_status = models.CharField(max_length=50, db_index=True)
    
    # Campos calculados para facilitar consultas
    is_delivered = models.BooleanField(default=False)
    is_failed = models.BooleanField(default=False)
    delivery_date_only = models.DateField(blank=True, null=True, db_index=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OrderManager()

    class Meta:
        indexes = [
            models.Index(fields=['status', 'intended_delivery_date']),
            models.Index(fields=['retailer', 'intended_delivery_date']),
            models.Index(fields=['simplified_order_status', 'actual_delivery_date']),
            models.Index(fields=['is_delivered', 'actual_delivery_date']),
        ]
        ordering = ['-intended_delivery_date', 'order_id']

    def __str__(self):
        return f"{self.order_id} - {self.status}"
    
    def get_delivery_attempts_count(self):
        return self.deliveryattempt_set.count()
    
    def get_failed_attempts_count(self):
        return self.deliveryattempt_set.filter(success=False).count()
    
    def is_multiple_attempts(self):
        return self.get_delivery_attempts_count() > 1
    
    def get_total_delivery_time(self):
        """Calcula o tempo total desde a primeira tentativa até a entrega"""
        if not self.actual_delivery_date:
            return None
        
        first_attempt = self.deliveryattempt_set.order_by('time').first()
        if not first_attempt or not first_attempt.time:
            return None
        
        # Converter date para datetime para o cálculo
        from datetime import datetime, time as dt_time
        delivery_datetime = datetime.combine(self.actual_delivery_date, dt_time.min)
        
        return delivery_datetime - first_attempt.time
    
    def save(self, *args, **kwargs):
        # Atualizar campos calculados
        self.is_delivered = self.status == 'delivered'
        self.is_failed = self.simplified_order_status in ['failed', 'undelivered']
        
        if self.actual_delivery_date:
            self.delivery_date_only = self.actual_delivery_date
        
        super().save(*args, **kwargs)

class Driver(models.Model):
    driver_id = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=100, db_index=True)
    vehicle = models.CharField(max_length=50)
    vehicle_norm = models.CharField(max_length=50)
    
    # Campos adicionais que podem ser úteis
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = DriverManager()

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.driver_id})"
    
    def get_deliveries_by_date(self, date):
        """Retorna todas as entregas realizadas pelo motorista em uma data específica"""
        return Order.objects.filter(
            dispatch__driver=self,
            actual_delivery_date=date,
            is_delivered=True
        )
    
    def get_orders_by_date(self, date):
        """Retorna todas as ordens designadas ao motorista em uma data específica"""
        return Order.objects.filter(
            dispatch__driver=self,
            intended_delivery_date=date
        )
    
    def get_success_rate(self, start_date=None, end_date=None):
        """Calcula a taxa de sucesso do motorista"""
        queryset = Order.objects.filter(dispatch__driver=self)
        
        if start_date:
            queryset = queryset.filter(intended_delivery_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(intended_delivery_date__lte=end_date)
        
        total_orders = queryset.count()
        if total_orders == 0:
            return 0
        
        delivered_orders = queryset.filter(is_delivered=True).count()
        return (delivered_orders / total_orders) * 100
    
    def get_daily_stats(self, date):
        """Retorna estatísticas do motorista para um dia específico"""
        orders = self.get_orders_by_date(date)
        deliveries = self.get_deliveries_by_date(date)
        
        return {
            'total_orders': orders.count(),
            'delivered_orders': deliveries.count(),
            'failed_orders': orders.filter(is_failed=True).count(),
            'pending_orders': orders.filter(simplified_order_status='to_attempt').count(),
            'success_rate': (deliveries.count() / orders.count() * 100) if orders.count() > 0 else 0
        }

class Dispatch(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='dispatch')
    driver = models.ForeignKey(Driver, on_delete=models.SET_NULL, null=True, blank=True)
    fleet = models.CharField(max_length=100)
    dc = models.CharField(max_length=100)  # Distribution Center
    driver_route_stop = models.IntegerField()
    dispatch_time = models.DateTimeField(blank=True, null=True, db_index=True)
    recovered = models.BooleanField(default=False)
    
    # Campo para rastreamento de mudanças
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['driver', 'dispatch_time']),
            models.Index(fields=['fleet', 'dispatch_time']),
            models.Index(fields=['dc', 'dispatch_time']),
        ]

    def __str__(self):
        driver_name = self.driver.name if self.driver else "No Driver"
        return f"Dispatch for {self.order.order_id} - {driver_name}"

class DeliveryAttempt(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    attempt_number = models.IntegerField()
    success = models.BooleanField()
    failure_reason = models.TextField(blank=True, null=True)
    time = models.DateTimeField(blank=True, null=True, db_index=True)

    # Geolocalização
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    location_description = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('order', 'attempt_number')
        indexes = [
            models.Index(fields=['order', 'attempt_number']),
            models.Index(fields=['success', 'time']),
        ]
        ordering = ['order', 'attempt_number']

    def __str__(self):
        status = "Success" if self.success else "Failed"
        return f"Attempt {self.attempt_number} for {self.order.order_id} - {status}"

class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    status = models.CharField(max_length=50)
    previous_status = models.CharField(max_length=50, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Informações adicionais sobre a mudança
    changed_by = models.CharField(max_length=100, blank=True, null=True)  # API, System, User, etc.
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['order', 'timestamp']),
            models.Index(fields=['status', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.order.order_id} - {self.status} at {self.timestamp}"