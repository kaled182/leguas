from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, timedelta


class Vehicle(models.Model):
    """
    Representa um veículo da frota.
    """
    
    VEHICLE_TYPES = [
        ('CAR', 'Carro'),
        ('VAN', 'Carrinha'),
        ('MOTORCYCLE', 'Mota'),
        ('BICYCLE', 'Bicicleta'),
        ('TRUCK', 'Camião'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Ativo'),
        ('MAINTENANCE', 'Em Manutenção'),
        ('INACTIVE', 'Inativo'),
        ('SOLD', 'Vendido'),
    ]
    
    # Identificação do Veículo
    license_plate = models.CharField(
        'Matrícula',
        max_length=20,
        unique=True,
        help_text='Matrícula do veículo (e.g., AA-00-BB)'
    )
    
    brand = models.CharField(
        'Marca',
        max_length=50,
        help_text='Marca do veículo (e.g., Renault, Peugeot)'
    )
    
    model = models.CharField(
        'Modelo',
        max_length=100,
        help_text='Modelo do veículo (e.g., Kangoo, Partner)'
    )
    
    year = models.IntegerField(
        'Ano',
        help_text='Ano de fabrico'
    )
    
    vehicle_type = models.CharField(
        'Tipo de Veículo',
        max_length=20,
        choices=VEHICLE_TYPES,
        default='VAN'
    )
    
    # Propriedade
    owner = models.CharField(
        'Proprietário',
        max_length=200,
        blank=True,
        help_text='Nome do proprietário (empresa ou pessoa física)'
    )
    
    is_company_owned = models.BooleanField(
        'Pertence à Empresa',
        default=True,
        help_text='Se não, é veículo de motorista'
    )
    
    # Especificações Técnicas
    max_load_kg = models.DecimalField(
        'Carga Máxima (kg)',
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    fuel_type = models.CharField(
        'Tipo de Combustível',
        max_length=20,
        blank=True,
        choices=[
            ('GASOLINE', 'Gasolina'),
            ('DIESEL', 'Gasóleo'),
            ('ELECTRIC', 'Elétrico'),
            ('HYBRID', 'Híbrido'),
        ]
    )
    
    # Documentação
    inspection_expiry = models.DateField(
        'Validade da Inspeção',
        null=True,
        blank=True,
        db_index=True,
        help_text='Data de validade da inspeção periódica obrigatória'
    )
    
    insurance_expiry = models.DateField(
        'Validade do Seguro',
        null=True,
        blank=True,
        db_index=True,
        help_text='Data de validade do seguro'
    )
    
    insurance_policy_number = models.CharField(
        'Número da Apólice',
        max_length=100,
        blank=True
    )
    
    # Status
    status = models.CharField(
        'Status',
        max_length=20,
        choices=STATUS_CHOICES,
        default='ACTIVE'
    )
    
    # Odómetro
    current_odometer_km = models.IntegerField(
        'Quilómetros Atuais',
        default=0,
        help_text='Quilometragem atual do veículo'
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
        verbose_name = 'Veículo'
        verbose_name_plural = 'Veículos'
        ordering = ['license_plate']
        indexes = [
            models.Index(fields=['status', 'vehicle_type']),
            models.Index(fields=['inspection_expiry']),
            models.Index(fields=['insurance_expiry']),
        ]
    
    def __str__(self):
        return f"{self.license_plate} - {self.brand} {self.model}"
    
    def clean(self):
        """Validações customizadas"""
        super().clean()
        
        # Normalizar matrícula (uppercase, remover espaços)
        if self.license_plate:
            self.license_plate = self.license_plate.upper().strip()
        
        # Validar ano
        current_year = date.today().year
        if self.year and (self.year < 1900 or self.year > current_year + 1):
            raise ValidationError({
                'year': f'Ano deve estar entre 1900 e {current_year + 1}'
            })
    
    @property
    def is_inspection_valid(self):
        """Verifica se inspeção está válida"""
        if not self.inspection_expiry:
            return False
        return self.inspection_expiry >= date.today()
    
    @property
    def is_insurance_valid(self):
        """Verifica se seguro está válido"""
        if not self.insurance_expiry:
            return False
        return self.insurance_expiry >= date.today()
    
    @property
    def inspection_expires_soon(self):
        """Verifica se inspeção expira em 30 dias"""
        if not self.inspection_expiry:
            return False
        return self.inspection_expiry <= date.today() + timedelta(days=30)
    
    @property
    def insurance_expires_soon(self):
        """Verifica se seguro expira em 30 dias"""
        if not self.insurance_expiry:
            return False
        return self.insurance_expiry <= date.today() + timedelta(days=30)
    
    @property
    def is_available(self):
        """Verifica se veículo está disponível para atribuição"""
        return (
            self.status == 'ACTIVE' and
            self.is_inspection_valid and
            self.is_insurance_valid
        )


class VehicleAssignment(models.Model):
    """
    Atribuição de veículo a motorista para um determinado dia.
    """
    
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='assignments',
        verbose_name='Veículo'
    )
    
    driver = models.ForeignKey(
        'drivers_app.DriverProfile',
        on_delete=models.CASCADE,
        related_name='vehicle_assignments',
        verbose_name='Motorista'
    )
    
    # Data e Horário
    date = models.DateField(
        'Data',
        db_index=True
    )
    
    start_time = models.TimeField(
        'Hora de Início',
        null=True,
        blank=True
    )
    
    end_time = models.TimeField(
        'Hora de Fim',
        null=True,
        blank=True
    )
    
    # Odómetro
    odometer_start = models.IntegerField(
        'Quilómetros Iniciais',
        null=True,
        blank=True,
        help_text='Quilometragem no início do turno'
    )
    
    odometer_end = models.IntegerField(
        'Quilómetros Finais',
        null=True,
        blank=True,
        help_text='Quilometragem no fim do turno'
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
        verbose_name = 'Atribuição de Veículo'
        verbose_name_plural = 'Atribuições de Veículos'
        ordering = ['-date', 'vehicle']
        # Um veículo só pode ser atribuído a um motorista por dia
        unique_together = [['vehicle', 'date']]
        indexes = [
            models.Index(fields=['driver', '-date']),
            models.Index(fields=['vehicle', '-date']),
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        return f"{self.vehicle.license_plate} → {self.driver.user.get_full_name()} ({self.date})"
    
    def clean(self):
        """Validações customizadas"""
        super().clean()
        
        # Validar horários
        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                raise ValidationError({
                    'end_time': 'Hora de fim deve ser após hora de início'
                })
        
        # Validar odómetro
        if self.odometer_start and self.odometer_end:
            if self.odometer_end < self.odometer_start:
                raise ValidationError({
                    'odometer_end': 'Quilometragem final deve ser >= quilometragem inicial'
                })
    
    @property
    def kilometers_driven(self):
        """Calcula quilómetros percorridos"""
        if self.odometer_start and self.odometer_end:
            return self.odometer_end - self.odometer_start
        return 0
    
    @property
    def duration_hours(self):
        """Calcula duração em horas"""
        if self.start_time and self.end_time:
            from datetime import datetime, timedelta
            
            start = datetime.combine(date.today(), self.start_time)
            end = datetime.combine(date.today(), self.end_time)
            
            if end < start:
                end += timedelta(days=1)
            
            duration = end - start
            return duration.total_seconds() / 3600
        return 0


class VehicleMaintenance(models.Model):
    """
    Registos de manutenção de veículos.
    """
    
    MAINTENANCE_TYPES = [
        ('PREVENTIVE', 'Preventiva'),
        ('CORRECTIVE', 'Corretiva'),
        ('INSPECTION', 'Inspeção'),
        ('TIRE_CHANGE', 'Mudança de Pneus'),
        ('OIL_CHANGE', 'Mudança de Óleo'),
        ('BRAKE_SERVICE', 'Travões'),
        ('OTHER', 'Outro'),
    ]
    
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='maintenance_records',
        verbose_name='Veículo'
    )
    
    maintenance_type = models.CharField(
        'Tipo de Manutenção',
        max_length=20,
        choices=MAINTENANCE_TYPES
    )
    
    description = models.TextField(
        'Descrição',
        help_text='Descrição detalhada do serviço realizado'
    )
    
    # Quando
    scheduled_date = models.DateField(
        'Data Agendada',
        null=True,
        blank=True
    )
    
    completed_date = models.DateField(
        'Data de Conclusão',
        null=True,
        blank=True
    )
    
    # Onde
    workshop = models.CharField(
        'Oficina',
        max_length=200,
        blank=True,
        help_text='Nome da oficina/prestador de serviço'
    )
    
    # Custos
    cost = models.DecimalField(
        'Custo',
        max_digits=10,
        decimal_places=2,
        default=0
    )
    
    invoice_number = models.CharField(
        'Número da Fatura',
        max_length=100,
        blank=True
    )
    
    # Odómetro quando feito
    odometer_at_service = models.IntegerField(
        'Quilómetros no Serviço',
        null=True,
        blank=True
    )
    
    # Status
    is_completed = models.BooleanField(
        'Concluído',
        default=False
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
        verbose_name = 'Manutenção de Veículo'
        verbose_name_plural = 'Manutenções de Veículos'
        ordering = ['-scheduled_date']
        indexes = [
            models.Index(fields=['vehicle', '-scheduled_date']),
            models.Index(fields=['is_completed', '-scheduled_date']),
        ]
    
    def __str__(self):
        status = "✓" if self.is_completed else "⚠"
        return f"{status} {self.vehicle.license_plate} - {self.get_maintenance_type_display()}"


class VehicleIncident(models.Model):
    """
    Incidentes com veículos (multas, acidentes, danos).
    """
    
    INCIDENT_TYPES = [
        ('FINE', 'Multa'),
        ('ACCIDENT', 'Acidente'),
        ('DAMAGE', 'Dano'),
        ('THEFT', 'Roubo'),
        ('OTHER', 'Outro'),
    ]
    
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='incidents',
        verbose_name='Veículo'
    )
    
    driver = models.ForeignKey(
        'drivers_app.DriverProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vehicle_incidents',
        verbose_name='Motorista',
        help_text='Motorista responsável (se aplicável)'
    )
    
    incident_type = models.CharField(
        'Tipo de Incidente',
        max_length=20,
        choices=INCIDENT_TYPES
    )
    
    description = models.TextField(
        'Descrição do Incidente'
    )
    
    incident_date = models.DateField(
        'Data do Incidente',
        db_index=True
    )
    
    location = models.CharField(
        'Local',
        max_length=200,
        blank=True
    )
    
    # Financeiro
    fine_amount = models.DecimalField(
        'Valor',
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Valor da multa ou custo do dano'
    )
    
    driver_responsible = models.BooleanField(
        'Motorista Responsável',
        default=False,
        help_text='Se sim, valor será deduzido do settlement'
    )
    
    claim_amount = models.DecimalField(
        'Valor a Reclamar',
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Valor a ser deduzido do motorista'
    )
    
    # Documentação
    photos = models.JSONField(
        'Fotos',
        default=list,
        blank=True,
        help_text='URLs de fotos do incidente'
    )
    
    police_report_number = models.CharField(
        'Número de Participação',
        max_length=100,
        blank=True,
        help_text='Número de participação policial (se aplicável)'
    )
    
    # Status
    resolved = models.BooleanField(
        'Resolvido',
        default=False
    )
    
    resolution_notes = models.TextField(
        'Notas de Resolução',
        blank=True
    )
    
    # Metadados
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Incidente de Veículo'
        verbose_name_plural = 'Incidentes de Veículos'
        ordering = ['-incident_date']
        indexes = [
            models.Index(fields=['vehicle', '-incident_date']),
            models.Index(fields=['driver', '-incident_date']),
            models.Index(fields=['resolved', '-incident_date']),
        ]
    
    def __str__(self):
        status = "✓ Resolvido" if self.resolved else "⚠ Pendente"
        return f"{self.vehicle.license_plate} - {self.get_incident_type_display()} ({status})"
