"""
Serviços de integração com parceiros logísticos.
"""

import logging
from datetime import datetime, timedelta
from django.utils import timezone

from orders_manager.adapters import DelnextAdapter
from .partner_sync_service import PartnerSyncService
from .paack_api_connector import PaackAPIConnector
from .partner_data_processor import PartnerDataProcessor

logger = logging.getLogger(__name__)


class DelnextSyncService(PartnerSyncService):
    """
    Serviço de sincronização específico para Delnext.
    Usa web scraping ao invés de API REST.
    """

    def __init__(self, partner_integration):
        """
        Inicializa o serviço Delnext (sem API connector).
        
        Args:
            partner_integration: Instância de core.models.PartnerIntegration
        """
        self.integration = partner_integration
        self.partner = partner_integration.partner
        self.cache_key = f"partner_sync_data_{self.partner.id}"
        
        # Delnext não usa API connector, usa web scraping
        # Então não inicializamos self.api_connector nem self.data_processor

    def sync(self, date=None, zone=None):
        """
        Sincroniza pedidos do Delnext.
        
        Args:
            date (str): Data no formato YYYY-MM-DD (default: última sexta)
            zone (str): Zona para filtrar (default: do auth_config)
        
        Returns:
            dict: Estatísticas da sincronização
        """
        from orders_manager.adapters import get_delnext_adapter
        from orders_manager.models import Order
        import re

        try:
            logger.info(f"[DELNEXT SYNC] Iniciando sincronização - Partner: {self.partner.name}")

            # Obter configurações da integração
            config = self.integration.auth_config or {}
            username = config.get("username", "VianaCastelo")
            password = config.get("password")
            default_zone = config.get("zone", "VianaCastelo")

            # Usar zona fornecida ou default
            zone = zone or default_zone

            # Criar adapter
            adapter = get_delnext_adapter(username, password)

            # Buscar dados
            logger.info(f"[DELNEXT SYNC] Buscando dados - Data: {date or 'auto'}, Zona: {zone}")
            delnext_data = adapter.fetch_outbound_data(date=date, zone=zone)

            if not delnext_data:
                logger.warning(f"[DELNEXT SYNC] Nenhum dado encontrado")
                stats = {
                    "total": 0,
                    "created": 0,
                    "updated": 0,
                    "errors": 0,
                }
                self.integration.last_sync_at = timezone.now()
                self.integration.last_sync_status = "SUCCESS"
                self.integration.last_sync_message = "Nenhum pedido encontrado"
                self.integration.save()
                return stats

            logger.info(f"[DELNEXT SYNC] {len(delnext_data)} pedidos encontrados")

            # Preparar pedidos para bulk_create
            orders_to_create = []
            orders_to_update = []
            existing_refs = set(
                Order.objects.filter(
                    partner=self.partner
                ).values_list('external_reference', flat=True)
            )

            for item in delnext_data:
                # Normalizar código postal
                postal_code = item.get("postal_code", "")
                postal_code = re.sub(r'[^\d-]', '', postal_code)
                
                if '-' not in postal_code and len(postal_code) >= 7:
                    postal_code = f"{postal_code[:4]}-{postal_code[4:7]}"
                
                if not re.match(r'^\d{4}-\d{3}$', postal_code):
                    postal_code = "0000-000"

                # Parse data
                scheduled_delivery = None
                date_str = item.get("date", "")
                if date_str:
                    try:
                        scheduled_delivery = datetime.strptime(date_str, "%Y-%m-%d").date()
                    except:
                        pass

                # Mapear status (usa STATUS_MAP canônico do DelnextAdapter)
                current_status = DelnextAdapter.STATUS_MAP.get(
                    item.get("status", "Pendente"), "PENDING"
                )

                # Endereço
                address_parts = [item.get("address", ""), item.get("city", "")]
                recipient_address = ", ".join(filter(None, address_parts)) or "Endereço não informado"

                # Dados do pedido
                order_data = {
                    "partner": self.partner,
                    "external_reference": item["product_id"],
                    "recipient_name": item.get("customer_name", "Cliente")[:200],
                    "recipient_address": recipient_address[:500],
                    "postal_code": postal_code,
                    "scheduled_delivery": scheduled_delivery,
                    "current_status": current_status,
                    "notes": f"Zona: {item.get('destination_zone', '')}",
                }

                # Verificar se já existe
                if item["product_id"] in existing_refs:
                    orders_to_update.append(order_data)
                else:
                    order = Order(**order_data)
                    orders_to_create.append(order)

            # Bulk create
            created_orders = []
            if orders_to_create:
                created_orders = Order.objects.bulk_create(
                    orders_to_create,
                    ignore_conflicts=True
                )

            # Update
            updated_count = 0
            for order_data in orders_to_update:
                try:
                    Order.objects.filter(
                        partner=self.partner,
                        external_reference=order_data["external_reference"]
                    ).update(**{
                        k: v for k, v in order_data.items() 
                        if k not in ['partner', 'external_reference']
                    })
                    updated_count += 1
                except Exception as e_update:
                    logger.error(f"[DELNEXT SYNC] Erro ao atualizar {order_data['external_reference']}: {e_update}")

            stats = {
                "total": len(delnext_data),
                "created": len(created_orders),
                "updated": updated_count,
                "errors": 0,
                "zone": zone,
                "date": date or "auto",
            }

            logger.info(
                f"[DELNEXT SYNC] Sincronização concluída - "
                f"Criados: {stats['created']}, Atualizados: {stats['updated']}"
            )

            self.integration.last_sync_at = timezone.now()
            self.integration.last_sync_status = "SUCCESS"
            self.integration.last_sync_message = f"{stats['created']} criados, {stats['updated']} atualizados"
            self.integration.save()
            
            # FASE 2: Geocodificar pedidos recentes (em background)
            if stats['created'] > 0 or stats['updated'] > 0:
                logger.info("[DELNEXT SYNC] Iniciando geocodificação em background...")
                try:
                    from core.tasks import geocode_recent_orders
                    # Geocodificar pedidos das últimas 2 horas (abrange os recém-importados)
                    geocode_recent_orders.delay(partner_name='Delnext', hours=2)
                    logger.info("[DELNEXT SYNC] Task de geocodificação agendada com sucesso")
                except Exception as geo_error:
                    logger.warning(f"[DELNEXT SYNC] Erro ao agendar geocodificação: {geo_error}")
                    # Não falhar a sincronização por causa disso
            
            return stats

        except Exception as e:
            logger.error(f"[DELNEXT SYNC] Erro na sincronização: {e}", exc_info=True)
            self.integration.last_sync_at = timezone.now()
            self.integration.last_sync_status = "ERROR"
            self.integration.last_sync_message = str(e)
            self.integration.save()
            raise


def get_sync_service(integration):
    """
    Factory para obter serviço de sincronização correto.
    
    Args:
        integration (PartnerIntegration): Integração
    
    Returns:
        PartnerSyncService: Instância do serviço apropriado
    """
    # Mapa de parceiros para serviços
    SERVICE_MAP = {
        "Delnext": DelnextSyncService,
    }

    partner_name = integration.partner.name
    service_class = SERVICE_MAP.get(partner_name, PartnerSyncService)
    
    return service_class(integration)


__all__ = [
    "PartnerSyncService", 
    "PaackAPIConnector", 
    "PartnerDataProcessor",
    "DelnextSyncService",
    "get_sync_service",
]
