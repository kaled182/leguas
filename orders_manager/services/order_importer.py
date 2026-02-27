"""
Order Importer - Factory Pattern

Sistema de importação de pedidos de diferentes parceiros.
Cada parceiro tem seu próprio importer que sabe como interagir com sua API.
"""

from abc import ABC, abstractmethod
import requests
from django.utils import timezone
from core.models import Partner, PartnerIntegration
from orders_manager.models import Order, OrderStatusHistory
import logging

logger = logging.getLogger(__name__)


class BaseOrderImporter(ABC):
    """
    Classe base para importadores de pedidos.
    Cada parceiro implementa sua própria subclasse.
    """
    
    def __init__(self, partner):
        self.partner = partner
        self.integration = partner.integrations.filter(
            is_active=True,
            integration_type='API'
        ).first()
        
        if not self.integration:
            raise ValueError(f"Partner {partner.name} não tem integração API ativa")
    
    @abstractmethod
    def fetch_orders(self, start_date=None, end_date=None):
        """
        Busca pedidos da API do parceiro.
        Retorna lista de pedidos em formato normalizado.
        """
        pass
    
    @abstractmethod
    def normalize_order_data(self, raw_order):
        """
        Normaliza dados do pedido para formato interno.
        Retorna dicionário com campos do modelo Order.
        """
        pass
    
    def import_orders(self, start_date=None, end_date=None):
        """
        Importa pedidos do parceiro.
        Retorna (success_count, error_count, errors_list)
        """
        success_count = 0
        error_count = 0
        errors = []
        
        try:
            # Buscar pedidos da API
            raw_orders = self.fetch_orders(start_date, end_date)
            
            logger.info(
                f"[{self.partner.name}] Fetched {len(raw_orders)} orders from API"
            )
            
            # Processar cada pedido
            for raw_order in raw_orders:
                try:
                    # Normalizar dados
                    order_data = self.normalize_order_data(raw_order)
                    
                    # Criar ou atualizar pedido
                    order, created = Order.objects.update_or_create(
                        partner=self.partner,
                        external_reference=order_data['external_reference'],
                        defaults=order_data
                    )
                    
                    if created:
                        logger.info(
                            f"[{self.partner.name}] Created order {order_data['external_reference']}"
                        )
                    
                    success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    error_msg = f"Error importing order: {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"[{self.partner.name}] {error_msg}")
            
            # Marcar integração como bem-sucedida
            self.integration.mark_sync_success(
                f"Imported {success_count} orders, {error_count} errors"
            )
            
        except Exception as e:
            error_msg = f"Fatal error: {str(e)}"
            errors.append(error_msg)
            logger.error(f"[{self.partner.name}] {error_msg}")
            
            # Marcar integração como erro
            self.integration.mark_sync_error(error_msg)
        
        return (success_count, error_count, errors)


class PaackOrderImporter(BaseOrderImporter):
    """
    Importador específico para Paack.
    """
    
    def fetch_orders(self, start_date=None, end_date=None):
        """Busca pedidos da API da Paack"""
        
        endpoint = f"{self.integration.endpoint_url}/orders"
        
        # Headers de autenticação
        headers = {
            'Authorization': f"Bearer {self.partner.api_credentials.get('api_key')}",
            'Content-Type': 'application/json',
        }
        
        # Parâmetros de query
        params = {}
        if start_date:
            params['start_date'] = start_date.isoformat()
        if end_date:
            params['end_date'] = end_date.isoformat()
        
        # Fazer request
        response = requests.get(
            endpoint,
            headers=headers,
            params=params,
            timeout=30
        )
        
        response.raise_for_status()
        
        data = response.json()
        return data.get('orders', [])
    
    def normalize_order_data(self, raw_order):
        """Normaliza dados da Paack para formato interno"""
        
        return {
            'external_reference': raw_order['tracking_code'],
            'recipient_name': raw_order['recipient']['name'],
            'recipient_address': raw_order['recipient']['address'],
            'postal_code': raw_order['recipient']['postal_code'],
            'recipient_phone': raw_order['recipient'].get('phone', ''),
            'recipient_email': raw_order['recipient'].get('email', ''),
            'declared_value': raw_order.get('declared_value', 0),
            'weight_kg': raw_order.get('weight', None),
            'scheduled_delivery': raw_order.get('delivery_date'),
            'current_status': self._map_paack_status(raw_order['status']),
            'special_instructions': raw_order.get('notes', ''),
        }
    
    def _map_paack_status(self, paack_status):
        """Mapeia status da Paack para status interno"""
        mapping = {
            'pending': 'PENDING',
            'assigned': 'ASSIGNED',
            'in_transit': 'IN_TRANSIT',
            'delivered': 'DELIVERED',
            'returned': 'RETURNED',
            'incident': 'INCIDENT',
        }
        return mapping.get(paack_status.lower(), 'PENDING')


class AmazonOrderImporter(BaseOrderImporter):
    """
    Importador específico para Amazon Logistics.
    """
    
    def fetch_orders(self, start_date=None, end_date=None):
        """Busca pedidos da API da Amazon"""
        
        # TODO: Implementar integração com Amazon SP-API
        # Esta é uma implementação placeholder
        
        logger.warning("Amazon importer not fully implemented yet")
        return []
    
    def normalize_order_data(self, raw_order):
        """Normaliza dados da Amazon para formato interno"""
        
        # TODO: Implementar normalização Amazon
        return {}


class OrderImporterFactory:
    """
    Factory para criar importadores específicos por parceiro.
    """
    
    _importers = {
        'Paack': PaackOrderImporter,
        'Amazon': AmazonOrderImporter,
        # Adicionar outros parceiros conforme necessário
    }
    
    @classmethod
    def create_importer(cls, partner):
        """
        Cria importer apropriado para o parceiro.
        
        Args:
            partner: Instância de Partner
        
        Returns:
            Instância de BaseOrderImporter específica do parceiro
        
        Raises:
            ValueError: Se parceiro não tem importer configurado
        """
        importer_class = cls._importers.get(partner.name)
        
        if not importer_class:
            raise ValueError(
                f"No importer configured for partner: {partner.name}"
            )
        
        return importer_class(partner)
    
    @classmethod
    def register_importer(cls, partner_name, importer_class):
        """
        Registra um novo importer para um parceiro.
        
        Args:
            partner_name: Nome do parceiro
            importer_class: Classe do importer (subclasse de BaseOrderImporter)
        """
        cls._importers[partner_name] = importer_class
    
    @classmethod
    def get_available_importers(cls):
        """Retorna lista de parceiros com importers disponíveis"""
        return list(cls._importers.keys())


def import_orders_for_partner(partner_name, start_date=None, end_date=None):
    """
    Função helper para importar pedidos de um parceiro.
    
    Args:
        partner_name: Nome do parceiro
        start_date: Data inicial (opcional)
        end_date: Data final (opcional)
    
    Returns:
        Dict com estatísticas da importação
    """
    try:
        partner = Partner.objects.get(name=partner_name, is_active=True)
    except Partner.DoesNotExist:
        return {
            'success': False,
            'error': f"Partner {partner_name} not found or inactive"
        }
    
    try:
        importer = OrderImporterFactory.create_importer(partner)
        success_count, error_count, errors = importer.import_orders(
            start_date, end_date
        )
        
        return {
            'success': True,
            'partner': partner_name,
            'success_count': success_count,
            'error_count': error_count,
            'errors': errors,
        }
        
    except Exception as e:
        return {
            'success': False,
            'partner': partner_name,
            'error': str(e)
        }


def import_orders_for_all_partners(start_date=None, end_date=None):
    """
    Importa pedidos de todos os parceiros ativos.
    
    Returns:
        Lista de dicts com estatísticas por parceiro
    """
    results = []
    
    partners = Partner.objects.filter(is_active=True)
    
    for partner in partners:
        result = import_orders_for_partner(
            partner.name,
            start_date,
            end_date
        )
        results.append(result)
    
    return results
