"""
ClaimProcessor: Processador de descontos/claims de motoristas.
Valida, aprova e aplica claims em settlements.
"""
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum


class ClaimProcessor:
    """
    Processa claims (descontos) de motoristas:
    - Valida valores e evidências
    - Aprova/rejeita claims
    - Vincula claims a settlements
    - Notifica motoristas
    """
    
    def __init__(self):
        self.notifications = []
    
    def create_claim_from_order(self, order, claim_type, amount, description, created_by=None):
        """
        Cria claim automaticamente a partir de um pedido falhado.
        
        Args:
            order: Order instance
            claim_type: 'ORDER_LOSS', 'ORDER_DAMAGE', etc.
            amount: Decimal
            description: str
            created_by: User instance
        
        Returns:
            DriverClaim instance
        """
        from settlements.models import DriverClaim
        
        if not order.assigned_driver:
            raise ValueError("Pedido não tem motorista atribuído")
        
        claim = DriverClaim.objects.create(
            driver=order.assigned_driver,
            order=order,
            claim_type=claim_type,
            amount=amount,
            description=description,
            occurred_at=order.updated_at,
            created_by=created_by,
            status='PENDING'
        )
        
        self.notifications.append(f"Claim criado: {claim}")
        
        return claim
    
    def create_claim_from_vehicle_incident(self, incident, created_by=None):
        """
        Cria claim a partir de incidente de veículo.
        
        Args:
            incident: VehicleIncident instance
            created_by: User instance
        
        Returns:
            DriverClaim instance
        """
        from settlements.models import DriverClaim
        
        if not incident.driver:
            raise ValueError("Incidente não tem motorista atribuído")
        
        # Mapear tipo de incidente para claim type
        claim_type_mapping = {
            'FINE': 'VEHICLE_FINE',
            'ACCIDENT': 'VEHICLE_DAMAGE',
            'DAMAGE': 'VEHICLE_DAMAGE',
        }
        
        claim_type = claim_type_mapping.get(incident.incident_type, 'OTHER')
        
        claim = DriverClaim.objects.create(
            driver=incident.driver,
            vehicle_incident=incident,
            claim_type=claim_type,
            amount=incident.fine_amount or Decimal('0.00'),
            description=incident.description,
            occurred_at=incident.incident_date,
            created_by=created_by,
            status='PENDING'
        )
        
        self.notifications.append(f"Claim criado a partir de incidente: {claim}")
        
        return claim
    
    def approve_claim(self, claim, user, notes=''):
        """
        Aprova um claim pendente.
        
        Args:
            claim: DriverClaim instance
            user: User instance (quem aprovou)
            notes: str (notas da revisão)
        """
        if claim.status != 'PENDING':
            raise ValueError(f"Claim deve estar PENDING. Status atual: {claim.status}")
        
        claim.approve(user, notes)
        
        self.notifications.append(
            f"Claim aprovado: {claim.driver.nome_completo} - €{claim.amount}"
        )
        
        # Notificar motorista via WhatsApp?
        # TODO: Integração futura
        
        return claim
    
    def reject_claim(self, claim, user, notes=''):
        """Rejeita um claim"""
        if claim.status != 'PENDING':
            raise ValueError(f"Claim deve estar PENDING. Status atual: {claim.status}")
        
        claim.reject(user, notes)
        
        self.notifications.append(
            f"Claim rejeitado: {claim.driver.nome_completo} - €{claim.amount}"
        )
        
        return claim
    
    def apply_claims_to_settlement(self, settlement):
        """
        Vincula claims aprovados ao settlement e atualiza o valor.
        
        Args:
            settlement: DriverSettlement instance
        
        Returns:
            list of DriverClaim instances vinculados
        """
        from settlements.models import DriverClaim
        
        # Buscar claims aprovados ainda não aplicados
        pending_claims = DriverClaim.objects.filter(
            driver=settlement.driver,
            status='APPROVED',
            settlement__isnull=True,
            occurred_at__date__gte=settlement.period_start,
            occurred_at__date__lte=settlement.period_end
        )
        
        total_claims = Decimal('0.00')
        claims_applied = []
        
        for claim in pending_claims:
            claim.settlement = settlement
            claim.save()
            
            total_claims += claim.amount
            claims_applied.append(claim)
            
            self.notifications.append(
                f"Claim aplicado ao settlement: {claim.get_claim_type_display()} - €{claim.amount}"
            )
        
        # Atualizar settlement
        settlement.claims_deducted = total_claims
        
        # Recalcular valor líquido
        total_deductions = (
            settlement.fuel_deduction +
            settlement.claims_deducted +
            settlement.other_deductions
        )
        
        settlement.net_amount = (
            settlement.gross_amount +
            settlement.bonus_amount -
            total_deductions
        )
        
        settlement.save()
        
        self.notifications.append(
            f"Settlement atualizado: {len(claims_applied)} claims aplicados, "
            f"total de descontos: €{total_claims}"
        )
        
        return claims_applied
    
    def get_driver_claims_summary(self, driver, start_date=None, end_date=None):
        """
        Retorna resumo de claims de um motorista.
        
        Returns:
            dict com estatísticas
        """
        from settlements.models import DriverClaim
        
        claims_query = DriverClaim.objects.filter(driver=driver)
        
        if start_date:
            claims_query = claims_query.filter(occurred_at__date__gte=start_date)
        if end_date:
            claims_query = claims_query.filter(occurred_at__date__lte=end_date)
        
        summary = {
            'total_count': claims_query.count(),
            'pending_count': claims_query.filter(status='PENDING').count(),
            'approved_count': claims_query.filter(status='APPROVED').count(),
            'rejected_count': claims_query.filter(status='REJECTED').count(),
            'total_amount': claims_query.filter(status='APPROVED').aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00'),
            'by_type': {}
        }
        
        # Agrupar por tipo
        for claim_type, claim_label in DriverClaim.CLAIM_TYPES:
            type_claims = claims_query.filter(claim_type=claim_type, status='APPROVED')
            summary['by_type'][claim_type] = {
                'label': claim_label,
                'count': type_claims.count(),
                'total': type_claims.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            }
        
        return summary
    
    def auto_create_claims_from_failed_orders(self, start_date, end_date):
        """
        Cria claims automaticamente para pedidos falhados no período.
        
        Args:
            start_date: date
            end_date: date
        
        Returns:
            list of created DriverClaim instances
        """
        from orders_manager.models import Order, OrderIncident
        from settlements.models import DriverClaim
        
        failed_orders = Order.objects.filter(
            current_status__in=['FAILED', 'INCIDENT'],
            assigned_driver__isnull=False,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        claims_created = []
        
        for order in failed_orders:
            # Verificar se já existe claim
            existing = DriverClaim.objects.filter(order=order).exists()
            if existing:
                continue
            
            # Buscar incidente associado
            incident = OrderIncident.objects.filter(order=order).first()
            
            if incident and incident.driver_responsible:
                # Criar claim
                claim_type = 'ORDER_LOSS'  # Padrão
                amount = order.declared_value * Decimal('0.50')  # 50% do valor declarado
                
                claim = DriverClaim.objects.create(
                    driver=order.assigned_driver,
                    order=order,
                    claim_type=claim_type,
                    amount=amount,
                    description=f"Pedido falhado: {incident.reason}. {incident.description}",
                    occurred_at=incident.occurred_at,
                    status='PENDING'
                )
                
                claims_created.append(claim)
                self.notifications.append(f"Claim auto-criado: {claim}")
        
        return claims_created
    
    def get_notifications(self):
        """Retorna notificações geradas"""
        return self.notifications
