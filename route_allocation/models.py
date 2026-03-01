from datetime import date, time

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class DriverShift(models.Model):
    """
    Turno de trabalho de um motorista para um determinado dia.
    Define qual motorista trabalha em quais zonas postais.
    """

    STATUS_CHOICES = [
        ("SCHEDULED", "Agendado"),
        ("IN_PROGRESS", "Em Progresso"),
        ("COMPLETED", "Concluído"),
        ("CANCELLED", "Cancelado"),
    ]

    # Motorista
    driver = models.ForeignKey(
        "drivers_app.DriverProfile",
        on_delete=models.CASCADE,
        related_name="shifts",
        verbose_name="Motorista",
    )

    # Data do Turno
    date = models.DateField("Data do Turno", db_index=True)

    # Zonas Postais Atribuídas
    assigned_postal_zones = models.ManyToManyField(
        "pricing.PostalZone",
        related_name="driver_shifts",
        verbose_name="Zonas Postais Atribuídas",
        help_text="Zonas onde o motorista deve fazer entregas neste turno",
    )

    # Horário
    start_time = models.TimeField(
        "Hora de Início",
        default=time(9, 0),
        help_text="Hora de início do turno",
    )

    end_time = models.TimeField(
        "Hora de Fim",
        default=time(18, 0),
        help_text="Hora prevista de fim do turno",
    )

    actual_start_time = models.DateTimeField(
        "Início Real",
        null=True,
        blank=True,
        help_text="Hora em que motorista iniciou turno (check-in)",
    )

    actual_end_time = models.DateTimeField(
        "Fim Real",
        null=True,
        blank=True,
        help_text="Hora em que motorista finalizou turno (check-out)",
    )

    # Estatísticas
    total_deliveries = models.IntegerField(
        "Total de Entregas",
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Número total de entregas atribuídas",
    )

    successful_deliveries = models.IntegerField(
        "Entregas Bem-Sucedidas", default=0, validators=[MinValueValidator(0)]
    )

    failed_deliveries = models.IntegerField(
        "Entregas Falhadas", default=0, validators=[MinValueValidator(0)]
    )

    # Status
    status = models.CharField(
        "Status",
        max_length=20,
        choices=STATUS_CHOICES,
        default="SCHEDULED",
        db_index=True,
    )

    # Observações
    notes = models.TextField("Observações", blank=True)

    # WhatsApp Notification
    whatsapp_notification_sent = models.BooleanField(
        "Notificação WhatsApp Enviada", default=False
    )

    whatsapp_notification_sent_at = models.DateTimeField(
        "Notificação Enviada em", null=True, blank=True
    )

    # Metadados
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_shifts",
        verbose_name="Criado por",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Turno de Motorista"
        verbose_name_plural = "Turnos de Motoristas"
        ordering = ["-date", "start_time"]
        # Um motorista só pode ter um turno por dia
        unique_together = [["driver", "date"]]
        indexes = [
            models.Index(fields=["driver", "-date"]),
            models.Index(fields=["date", "status"]),
            models.Index(fields=["-date"]),
        ]

    def __str__(self):
        return f"{self.driver.user.get_full_name()} - {self.date} ({self.get_status_display()})"

    def clean(self):
        """Validações customizadas"""
        super().clean()

        # Validar horários
        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                raise ValidationError(
                    {"end_time": "Hora de fim deve ser após hora de início"}
                )

        # Validar horários reais
        if self.actual_start_time and self.actual_end_time:
            if self.actual_start_time >= self.actual_end_time:
                raise ValidationError(
                    {
                        "actual_end_time": "Hora de fim real deve ser após hora de início real"
                    }
                )

        # Validar estatísticas
        if self.successful_deliveries + self.failed_deliveries > self.total_deliveries:
            raise ValidationError(
                {"total_deliveries": "Total deve ser >= sucesso + falhas"}
            )

    def start_shift(self):
        """Marca início do turno (check-in)"""
        self.actual_start_time = timezone.now()
        self.status = "IN_PROGRESS"
        self.save()

    def end_shift(self):
        """Marca fim do turno (check-out)"""
        self.actual_end_time = timezone.now()
        self.status = "COMPLETED"
        self.save()

    def update_statistics(self):
        """Atualiza estatísticas baseado nos pedidos do dia"""
        from orders_manager.models import Order

        # Buscar pedidos atribuídos ao motorista para este dia
        orders = Order.objects.filter(
            assigned_driver=self.driver,
            scheduled_delivery=self.date,
        )

        self.total_deliveries = orders.count()
        self.successful_deliveries = orders.filter(current_status="DELIVERED").count()
        self.failed_deliveries = orders.filter(
            current_status__in=["RETURNED", "INCIDENT"]
        ).count()

        self.save()

    @property
    def success_rate(self):
        """Calcula taxa de sucesso"""
        if self.total_deliveries == 0:
            return 0
        return (self.successful_deliveries / self.total_deliveries) * 100

    @property
    def duration_hours(self):
        """Calcula duração real do turno em horas"""
        if self.actual_start_time and self.actual_end_time:
            duration = self.actual_end_time - self.actual_start_time
            return duration.total_seconds() / 3600
        return 0

    @property
    def is_active(self):
        """Verifica se turno está ativo"""
        return self.status == "IN_PROGRESS"

    @property
    def is_upcoming(self):
        """Verifica se turno é futuro"""
        return self.date > date.today() and self.status == "SCHEDULED"

    def send_whatsapp_notification(self):
        """
        Envia notificação WhatsApp ao motorista.
        TODO: Integrar com wppconnect-chatwoot-bridge
        """
        if self.whatsapp_notification_sent:
            return False

        # TODO: Implementar envio real via WhatsApp
        # Por enquanto, apenas marca como enviado

        message = f"""
🚗 *Turno Agendado*

📅 Data: {self.date.strftime('%d/%m/%Y')}
🕐 Horário: {self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}
📦 Entregas: {self.total_deliveries}

Zonas atribuídas:
{', '.join([zone.name for zone in self.assigned_postal_zones.all()])}

Bom trabalho! 💪
        """.strip()

        # Aqui entraria a lógica de envio
        # from wppconnect_bridge.services import send_message
        # send_message(self.driver.phone, message)

        self.whatsapp_notification_sent = True
        self.whatsapp_notification_sent_at = timezone.now()
        self.save()

        return True


class RouteOptimizer:
    """
    Serviço para otimização de rotas.
    Atribui pedidos a motoristas de forma eficiente.
    """

    @staticmethod
    def assign_orders_to_shift(shift):
        """
        Atribui pedidos pendentes ao turno de um motorista.

        Args:
            shift: Instância de DriverShift

        Returns:
            Dict com estatísticas da atribuição
        """
        from orders_manager.models import Order

        assigned_count = 0

        # Buscar zonas do turno
        zones = shift.assigned_postal_zones.all()

        if not zones:
            return {
                "success": False,
                "error": "No zones assigned to shift",
                "assigned_count": 0,
            }

        # Buscar pedidos pendentes nas zonas
        for zone in zones:
            # Pedidos sem motorista atribuído na zona
            pending_orders = Order.objects.filter(
                current_status="PENDING",
                scheduled_delivery=shift.date,
                assigned_driver__isnull=True,
            )

            # Filtrar por código postal da zona
            for order in pending_orders:
                if zone.matches_postal_code(order.postal_code):
                    order.assign_to_driver(shift.driver)
                    assigned_count += 1

        # Atualizar estatísticas do turno
        shift.update_statistics()

        return {
            "success": True,
            "assigned_count": assigned_count,
            "total_deliveries": shift.total_deliveries,
        }

    @staticmethod
    def auto_assign_shifts_for_date(target_date):
        """
        Auto-atribui turnos para uma data específica.
        Distribui pedidos entre motoristas disponíveis.

        Args:
            target_date: Data para atribuição

        Returns:
            Dict com estatísticas
        """
        shifts = DriverShift.objects.filter(date=target_date, status="SCHEDULED")

        total_assigned = 0

        for shift in shifts:
            result = RouteOptimizer.assign_orders_to_shift(shift)
            if result["success"]:
                total_assigned += result["assigned_count"]

        return {
            "success": True,
            "shifts_processed": shifts.count(),
            "total_orders_assigned": total_assigned,
        }
