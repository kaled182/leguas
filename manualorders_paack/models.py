from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from ordersmanager_paack.models import Order, Dispatch, Driver

class ManualCorrection(models.Model):
    CORRECTION_TYPES = [
        ('ADD', 'Adição'),
        ('SUB', 'Subtração'),
        ('EDIT', 'Edição'),
    ]

    STATUS_CHOICES = [
        ('delivered', 'Entregue'),
        ('on_course', 'Em Rota'),
        ('picked_up', 'Coletado'),
        ('reached_picked_up', 'Chegou ao Ponto de Coleta'),
        ('return_in_progress', 'Retorno em Andamento'),
        ('undelivered', 'Não Entregue'),
        ('failed', 'Falhou'),
        ('cancelled', 'Cancelado'),
    ]

    correction_type = models.CharField('Tipo de Correção', max_length=4, choices=CORRECTION_TYPES)
    status = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default='delivered')
    reason = models.TextField('Motivo')
    driver = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name='manual_corrections')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='manual_corrections')
    dispatch = models.ForeignKey(Dispatch, on_delete=models.CASCADE, related_name='manual_corrections')
    
    # Campos para rastreabilidade e controle
    original_status = models.CharField('Status Original', max_length=20, blank=True, null=True)
    original_driver = models.ForeignKey(Driver, on_delete=models.PROTECT, blank=True, null=True, related_name='original_manual_corrections')
    correction_date = models.DateField('Data da Correção', help_text='Data para qual a correção se aplica')
    quantity = models.PositiveIntegerField('Quantidade', default=1, help_text='Quantidade de entregas adicionadas/removidas')
    
    # Metadados
    created_by = models.ForeignKey(get_user_model(), on_delete=models.PROTECT, related_name='manual_corrections')
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)
    
    # Controle de atividade
    is_active = models.BooleanField('Ativo', default=True, help_text='Se False, a correção foi desfeita')

    class Meta:
        verbose_name = 'Correção Manual'
        verbose_name_plural = 'Correções Manuais'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['correction_date', 'driver']),
            models.Index(fields=['created_at', 'correction_type']),
            models.Index(fields=['is_active', 'correction_date']),
        ]

    def __str__(self):
        return f"{self.get_correction_type_display()} por {self.created_by} em {self.created_at.strftime('%d/%m/%Y %H:%M')}"
    
    @property
    def clean_driver_name(self):
        """Extract clean driver name removing codes and prefixes"""
        if not self.driver or not self.driver.name:
            return "N/A"
            
        full_name = self.driver.name
        prefixes = ['SC', 'OPO', 'LF', 'M', 'D', 'LX', 'Porto', 'Lisboa', 'FCO', 'PRT']
        suffixes = ['LMO', 'XYZ', 'ABC', 'IJK']
        
        parts = full_name.split()
        name_candidate = []
        
        for part in parts:
            if part in prefixes:
                continue
            if len(part) > 2 and part[0].isupper() and not part.isupper():
                name_candidate.append(part)
        
        if name_candidate:
            # Remove common suffixes
            if name_candidate and name_candidate[-1] in suffixes:
                name_candidate.pop()
            clean_name = ' '.join(name_candidate)
        else:
            # Fallback: use last 2 parts
            clean_name = ' '.join(parts[-2:]) if len(parts) >= 2 else full_name
        
        return clean_name.strip()
    
    def save(self, *args, **kwargs):
        # Garantir que correction_date está definida
        if not self.correction_date:
            self.correction_date = self.created_at.date() if self.created_at else timezone.now().date()
        super().save(*args, **kwargs)