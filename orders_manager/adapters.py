"""
Adapters para escrita/leitura paralela durante migração.

Implementa o padrão Adapter para permitir dual write/read entre
sistema antigo (ordersmanager_paack) e novo (orders_manager).

Referência: docs/MIGRATION_GUIDE.md - Fase 2: Read/Write em Paralelo
"""

from django.conf import settings
from django.db import transaction
import logging
import re
from decimal import Decimal

logger = logging.getLogger(__name__)


class OrderAdapter:
    """
    Adapter para operações de pedidos com dual write/read.
    
    Baseado nas feature flags:
    - DUAL_WRITE_ORDERS: Escreve em ambos os sistemas
    - USE_GENERIC_ORDERS_WRITE: Escreve apenas no novo sistema
    - USE_GENERIC_ORDERS_READ: Lê do novo sistema
    """
    
    def __init__(self):
        self.dual_write = getattr(settings, 'DUAL_WRITE_ORDERS', False)
        self.write_generic = getattr(settings, 'USE_GENERIC_ORDERS_WRITE', False)
        self.read_generic = getattr(settings, 'USE_GENERIC_ORDERS_READ', False)
        self.validate = getattr(settings, 'ENABLE_MIGRATION_VALIDATION', True)
        self.log_operations = getattr(settings, 'LOG_MIGRATION_OPERATIONS', True)
    
    def create_order(self, order_data, partner_name='Paack'):
        """
        Cria pedido com dual write se ativado.
        
        Args:
            order_data: Dicionário com dados do pedido
            partner_name: Nome do parceiro (default: 'Paack')
        
        Returns:
            tuple: (order_generic, order_paack) ou apenas um deles dependendo das flags
        """
        from core.models import Partner
        from orders_manager.models import Order as GenericOrder
        from ordersmanager_paack.models import Order as PaackOrder
        
        order_generic = None
        order_paack = None
        
        with transaction.atomic():
            # Dual write: escrever em ambos
            if self.dual_write:
                if self.log_operations:
                    logger.info(f"[DUAL WRITE] Criando pedido em ambos os sistemas")
                
                # 1. Criar no sistema antigo (Paack) PRIMEIRO
                order_paack = self._create_paack_order(order_data)
                
                # 2. Criar no sistema novo (Generic) usando UUID do Paack
                partner = Partner.objects.get(name=partner_name)
                # Usar UUID do Paack como external_reference
                order_data_with_uuid = order_data.copy()
                order_data_with_uuid['external_reference'] = str(order_paack.uuid)
                order_generic = self._create_generic_order(order_data_with_uuid, partner)
                
                # 3. Validar se ativado
                if self.validate:
                    self._validate_dual_write(order_paack, order_generic)
                
                if self.log_operations:
                    logger.info(
                        f"[DUAL WRITE] Pedido criado - "
                        f"Paack UUID: {order_paack.uuid}, "
                        f"Generic ID: {order_generic.id}"
                    )
            
            # Write apenas no novo sistema
            elif self.write_generic:
                if self.log_operations:
                    logger.info(f"[GENERIC WRITE] Criando pedido no sistema novo")
                
                partner = Partner.objects.get(name=partner_name)
                order_generic = self._create_generic_order(order_data, partner)
                
                if self.log_operations:
                    logger.info(f"[GENERIC WRITE] Pedido criado - ID: {order_generic.id}")
            
            # Write apenas no sistema antigo (padrão atual)
            else:
                if self.log_operations:
                    logger.info(f"[PAACK WRITE] Criando pedido no sistema antigo")
                
                order_paack = self._create_paack_order(order_data)
                
                if self.log_operations:
                    logger.info(f"[PAACK WRITE] Pedido criado - UUID: {order_paack.uuid}")
        
        return order_generic, order_paack
    
    def update_order_status(self, identifier, new_status, notes=''):
        """
        Atualiza status de pedido com dual write.
        
        Args:
            identifier: UUID (Paack) ou ID (Generic)
            new_status: Novo status
            notes: Observações da mudança
        """
        from orders_manager.models import Order as GenericOrder, OrderStatusHistory
        from ordersmanager_paack.models import Order as PaackOrder
        
        with transaction.atomic():
            if self.dual_write:
                # Atualizar em ambos os sistemas
                try:
                    # Tentar como UUID (Paack)
                    paack_order = PaackOrder.objects.get(uuid=identifier)
                    paack_order.status = new_status
                    paack_order.save()
                    
                    # Atualizar correspondente no Generic
                    generic_order = GenericOrder.objects.get(
                        external_reference=str(identifier)
                    )
                    generic_order.current_status = self._map_status_to_generic(new_status)
                    generic_order.save()
                    
                    # Registrar histórico
                    OrderStatusHistory.objects.create(
                        order=generic_order,
                        old_status=generic_order.current_status,
                        new_status=self._map_status_to_generic(new_status),
                        notes=notes
                    )
                    
                    if self.log_operations:
                        logger.info(
                            f"[DUAL WRITE] Status atualizado - "
                            f"UUID: {identifier}, Status: {new_status}"
                        )
                
                except (PaackOrder.DoesNotExist, GenericOrder.DoesNotExist) as e:
                    logger.error(f"[DUAL WRITE] Erro ao atualizar status: {e}")
                    raise
            
            elif self.write_generic:
                # Atualizar apenas no Generic
                generic_order = GenericOrder.objects.get(id=identifier)
                old_status = generic_order.current_status
                generic_order.current_status = new_status
                generic_order.save()
                
                OrderStatusHistory.objects.create(
                    order=generic_order,
                    old_status=old_status,
                    new_status=new_status,
                    notes=notes
                )
            
            else:
                # Atualizar apenas no Paack
                paack_order = PaackOrder.objects.get(uuid=identifier)
                paack_order.status = new_status
                paack_order.save()
    
    def get_order(self, identifier):
        """
        Busca pedido do sistema apropriado baseado nas flags.
        
        Args:
            identifier: UUID (Paack) ou ID (Generic)
        
        Returns:
            Order object (Generic ou Paack)
        """
        from orders_manager.models import Order as GenericOrder
        from ordersmanager_paack.models import Order as PaackOrder
        
        if self.read_generic:
            # Ler do sistema novo
            try:
                if isinstance(identifier, int):
                    return GenericOrder.objects.get(id=identifier)
                else:
                    return GenericOrder.objects.get(external_reference=str(identifier))
            except GenericOrder.DoesNotExist:
                logger.warning(f"[GENERIC READ] Pedido não encontrado: {identifier}")
                raise
        else:
            # Ler do sistema antigo
            try:
                return PaackOrder.objects.get(uuid=identifier)
            except PaackOrder.DoesNotExist:
                logger.warning(f"[PAACK READ] Pedido não encontrado: {identifier}")
                raise
    
    def list_orders(self, filters=None, limit=100):
        """
        Lista pedidos do sistema apropriado.
        
        Args:
            filters: Dicionário com filtros (driver, date_range, status, etc.)
            limit: Limite de resultados
        
        Returns:
            QuerySet de pedidos
        """
        from orders_manager.models import Order as GenericOrder
        from ordersmanager_paack.models import Order as PaackOrder
        
        filters = filters or {}
        
        if self.read_generic:
            # Ler do sistema novo
            queryset = GenericOrder.objects.all()
            
            if 'status' in filters:
                queryset = queryset.filter(current_status=filters['status'])
            
            if 'driver' in filters:
                queryset = queryset.filter(assigned_driver=filters['driver'])
            
            if 'date_range' in filters:
                start, end = filters['date_range']
                queryset = queryset.filter(
                    scheduled_delivery__range=[start, end]
                )
            
            return queryset[:limit]
        else:
            # Ler do sistema antigo
            queryset = PaackOrder.objects.all()
            
            if 'status' in filters:
                queryset = queryset.filter(status=filters['status'])
            
            if 'date_range' in filters:
                start, end = filters['date_range']
                queryset = queryset.filter(
                    intended_delivery_date__range=[start, end]
                )
            
            return queryset[:limit]
    
    # ========================================================================
    # MÉTODOS PRIVADOS
    # ========================================================================
    
    def _create_paack_order(self, order_data):
        """Cria pedido no sistema antigo (Paack)"""
        from ordersmanager_paack.models import Order as PaackOrder
        import uuid
        
        # Mapear dados para modelo Paack
        paack_data = {
            'uuid': uuid.uuid4(),
            'order_id': order_data.get('external_reference', ''),
            'order_type': order_data.get('order_type', 'standard'),
            'service_type': order_data.get('service_type', 'standard'),
            'status': order_data.get('status', 'pending'),
            'packages_count': order_data.get('packages_count', 1),
            'packages_barcode': order_data.get('packages_barcode', ''),
            'retailer': order_data.get('retailer', 'Paack'),
            'retailer_order_number': order_data.get('external_reference', ''),
            'retailer_sales_number': order_data.get('external_reference', ''),
            'client_address': order_data.get('recipient_address', ''),
            'client_address_text': order_data.get('recipient_address', ''),
            'client_phone': order_data.get('recipient_phone', ''),
            'client_email': order_data.get('recipient_email', ''),
            'intended_delivery_date': order_data.get('scheduled_delivery'),
            'delivery_timeslot': order_data.get('delivery_timeslot', ''),
            'simplified_order_status': order_data.get('status', 'pending'),
            'is_delivered': order_data.get('status', '').lower() == 'delivered',
            'is_failed': order_data.get('status', '').lower() in ['failed', 'incident'],
        }
        
        return PaackOrder.objects.create(**paack_data)
    
    def _create_generic_order(self, order_data, partner):
        """Cria pedido no sistema novo (Generic)"""
        from orders_manager.models import Order as GenericOrder
        
        # Extrair código postal se não fornecido
        postal_code = order_data.get('postal_code', '0000-000')
        if postal_code == '0000-000' and 'recipient_address' in order_data:
            postal_code = self._extract_postal_code(order_data['recipient_address'])
        
        generic_data = {
            'partner': partner,
            'external_reference': order_data.get('external_reference', ''),
            'recipient_name': order_data.get('recipient_name', ''),
            'recipient_address': order_data.get('recipient_address', ''),
            'postal_code': postal_code,
            'recipient_phone': order_data.get('recipient_phone', ''),
            'recipient_email': order_data.get('recipient_email', ''),
            'declared_value': Decimal(str(order_data.get('declared_value', 0))),
            'weight_kg': order_data.get('weight_kg'),
            'scheduled_delivery': order_data.get('scheduled_delivery'),
            'assigned_driver': order_data.get('assigned_driver'),
            'current_status': self._map_status_to_generic(
                order_data.get('status', 'PENDING')
            ),
            'notes': order_data.get('notes', ''),
        }
        
        return GenericOrder.objects.create(**generic_data)
    
    def _extract_postal_code(self, address):
        """Extrai código postal português do endereço"""
        match = re.search(r'\d{4}-\d{3}', str(address))
        return match.group() if match else '0000-000'
    
    def _map_status_to_generic(self, paack_status):
        """Mapeia status Paack para status genérico"""
        mapping = {
            'pending': 'PENDING',
            'assigned': 'ASSIGNED',
            'in_transit': 'IN_TRANSIT',
            'out_for_delivery': 'IN_TRANSIT',
            'delivered': 'DELIVERED',
            'returned': 'RETURNED',
            'incident': 'INCIDENT',
            'failed': 'INCIDENT',
            'undelivered': 'INCIDENT',
            'cancelled': 'CANCELLED',
        }
        return mapping.get(paack_status.lower(), 'PENDING')
    
    def _validate_dual_write(self, order_paack, order_generic):
        """Valida consistência entre os dois sistemas"""
        issues = []
        
        # Validar referência externa
        if str(order_paack.uuid) != order_generic.external_reference:
            issues.append(
                f"Referência externa não match: "
                f"Paack={order_paack.uuid}, Generic={order_generic.external_reference}"
            )
        
        # Validar status
        mapped_status = self._map_status_to_generic(order_paack.status)
        if mapped_status != order_generic.current_status:
            issues.append(
                f"Status não match: "
                f"Paack={order_paack.status}→{mapped_status}, "
                f"Generic={order_generic.current_status}"
            )
        
        # Validar data de entrega
        if order_paack.intended_delivery_date != order_generic.scheduled_delivery:
            issues.append(
                f"Data de entrega não match: "
                f"Paack={order_paack.intended_delivery_date}, "
                f"Generic={order_generic.scheduled_delivery}"
            )
        
        if issues:
            logger.warning(
                f"[DUAL WRITE VALIDATION] Inconsistências detectadas:\n" +
                "\n".join(f"  - {issue}" for issue in issues)
            )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_order_adapter():
    """Factory function para obter adapter de pedidos"""
    return OrderAdapter()
