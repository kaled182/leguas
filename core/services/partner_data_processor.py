"""
Processador de dados genérico para parceiros.
Adaptado de ordersmanager_paack/data_processor.py para usar orders_manager.Order.
"""

import logging
from datetime import datetime
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from orders_manager.models import Order

logger = logging.getLogger(__name__)


def parse_api_date(date_str):
    """Converte string de data da API para date object"""
    if not date_str or date_str == "null":
        return None
    try:
        return parse_date(date_str)
    except (ValueError, TypeError):
        return None


def parse_api_datetime(datetime_str):
    """Converte string de datetime da API para datetime object"""
    if not datetime_str or datetime_str == "null":
        return None
    try:
        return parse_datetime(datetime_str)
    except (ValueError, TypeError):
        return None


class PartnerDataProcessor:
    """
    Classe responsável pelo processamento e transformação dos dados da API
    para o modelo Order genérico. Baseada no ordersmanager_paack.
    """

    # Mapeamento de status Paack → Status genérico
    STATUS_MAPPING = {
        "delivered": "DELIVERED",
        "picked_up": "DELIVERED",
        "in_transit": "IN_TRANSIT",
        "to_attempt": "PENDING",
        "failed": "INCIDENT",
        "returned": "RETURNED",
        "cancelled": "CANCELLED",
        "assigned": "ASSIGNED",
    }

    def __init__(self, partner_integration):
        """
        Inicializa o processador.
        
        Args:
            partner_integration: Instância de core.models.PartnerIntegration
        """
        self.integration = partner_integration
        self.partner = partner_integration.partner
        self.stats = {
            "total_processed": 0,
            "orders_created": 0,
            "orders_updated": 0,
            "errors": [],
        }

    def process_data(self, api_data):
        """
        Processa os dados da API e retorna estatísticas.
        
        Args:
            api_data: Dados JSON da API (formato AppSheet para Paack)
            
        Returns:
            dict: Estatísticas do processamento
        """
        try:
            logger.info(f"🔍 Processando dados de {self.partner.name}...")

            # Obter dataset principal (formato AppSheet)
            dataset = api_data.get("DATA_EXTRACT_AVG") or api_data.get("DATA_PIVOT")
            if not dataset:
                logger.error("❌ Dataset não encontrado na resposta da API")
                logger.error(
                    f"🔍 Chaves disponíveis: {list(api_data.keys()) if api_data else 'Nenhuma'}"
                )
                return self.stats

            columns = dataset.get("columns", [])
            rows = dataset.get("data", [])

            logger.info(f"📋 Dataset encontrado com {len(columns)} colunas")
            logger.info(f"📦 Total de linhas brutas: {len(rows)}")

            # Filtrar linhas válidas
            valid_rows = [row for row in rows if len(row) == len(columns)]
            invalid_rows = len(rows) - len(valid_rows)

            if invalid_rows > 0:
                logger.warning(
                    f"⚠️ {invalid_rows} linhas descartadas (estrutura incorreta)"
                )

            if not columns or not valid_rows:
                logger.warning("⚠️ Nenhum dado válido para processar")
                return self.stats

            logger.info(f"✅ Processando {len(valid_rows)} registros válidos...")

            # Processar em transação
            processed_count = 0
            with transaction.atomic():
                for row_index, row in enumerate(valid_rows):
                    try:
                        self._process_single_row(row, columns)
                        self.stats["total_processed"] += 1
                        processed_count += 1

                        # Log de progresso a cada 50 registros
                        if processed_count % 50 == 0:
                            logger.info(
                                f"📈 Progresso: {processed_count}/{len(valid_rows)} processados"
                            )

                    except Exception as e:
                        error_msg = f"Erro na linha {row_index}: {str(e)}"
                        logger.error(f"❌ {error_msg}")
                        self.stats["errors"].append(error_msg)
                        continue

            self._log_stats()
            return self.stats

        except Exception as e:
            logger.error(f"❌ Erro geral no processamento: {e}")
            import traceback
            logger.error(f"📋 Stack trace: {traceback.format_exc()}")
            self.stats["errors"].append(str(e))
            return self.stats

    def _process_single_row(self, row, columns):
        """Processa uma linha individual - adaptado para Order genérico"""

        def get_value(column_name, default=None):
            try:
                index = columns.index(column_name)
                value = row[index] if index < len(row) else default
                return value if value not in ["", None, "null"] else default
            except ValueError:
                return default

        # Validar UUID/ID da ordem (usar como external_reference)
        order_uuid = get_value("ORDER_UUID")
        order_id = get_value("ORDER_ID", "")
        
        if not order_uuid and not order_id:
            raise ValueError("ORDER_UUID ou ORDER_ID é obrigatório")

        # Use UUID se disponível, senão ORDER_ID
        external_ref = order_uuid if order_uuid else order_id

        # Extrair código postal (formato XXXX-XXX)
        postal_code = self._extract_postal_code(
            get_value("CLIENT_ADDRESS", "")
        )

        # Mapear status
        raw_status = get_value("ORDER_STATUS", "to_attempt")
        mapped_status = self.STATUS_MAPPING.get(raw_status, "PENDING")

        # Criar/atualizar ordem
        order_data = {
            "partner": self.partner,
            "external_reference": external_ref,
            "recipient_name": get_value("CLIENT_ADDRESS_TEXT", "Destinatário Desconhecido")[:200],
            "recipient_address": get_value("CLIENT_ADDRESS", "")[:500],
            "postal_code": postal_code or "0000-000",  # Fallback
            "recipient_phone": get_value("CLIENT_PHONE", "")[:20],
            "recipient_email": get_value("CLIENT_EMAIL", "")[:254],
            "scheduled_delivery": parse_api_date(
                get_value("ORDER_INTENDED_DELIVERY_DATE")
            ),
            "current_status": mapped_status,
            "notes": self._build_notes(get_value, row, columns),
        }

        # Atualizar delivered_at se status é DELIVERED
        if mapped_status == "DELIVERED":
            order_data["delivered_at"] = parse_api_datetime(
                get_value("ORDER_ACTUAL_DELIVERY_DATE")
            ) or timezone.now()

        # Criar/atualizar ordem
        order, created = Order.objects.update_or_create(
            external_reference=external_ref,
            partner=self.partner,
            defaults=order_data
        )

        if created:
            self.stats["orders_created"] += 1
            logger.info(f"📦 Nova ordem: {external_ref}")
        else:
            self.stats["orders_updated"] += 1

        return order

    def _extract_postal_code(self, address):
        """Extrai código postal do endereço (formato XXXX-XXX)"""
        import re
        if not address:
            return None
        match = re.search(r'\b(\d{4}-\d{3})\b', address)
        return match.group(1) if match else None

    def _build_notes(self, get_value, row, columns):
        """Constrói campo notes com informações adicionais"""
        notes_parts = []
        
        # Adicionar informações do pedido
        order_type = get_value("ORDER_TYPE")
        if order_type:
            notes_parts.append(f"Tipo: {order_type}")
            
        service_type = get_value("SERVICE_TYPE")
        if service_type:
            notes_parts.append(f"Serviço: {service_type}")
            
        packages = get_value("PACKAGES_COUNT")
        if packages:
            notes_parts.append(f"Pacotes: {packages}")
            
        barcode = get_value("PACKAGES_BARCODE")
        if barcode:
            notes_parts.append(f"Código de Barras: {barcode}")
            
        retailer = get_value("RETAILER")
        if retailer:
            notes_parts.append(f"Retalhista: {retailer}")
            
        # Informações do motorista (se disponível)
        driver_name = get_value("DISPATCH_DRIVER_NAME")
        if driver_name:
            notes_parts.append(f"Motorista: {driver_name}")
            
        vehicle = get_value("DISPATCH_DRIVER_VEHICLE")
        if vehicle:
            notes_parts.append(f"Veículo: {vehicle}")

        return " | ".join(notes_parts) if notes_parts else ""

    def _log_stats(self):
        """Registra estatísticas do processamento"""
        logger.info("=" * 50)
        logger.info(f"📈 ESTATÍSTICAS - {self.partner.name}")
        logger.info("=" * 50)
        logger.info(f"   📦 Total processado: {self.stats['total_processed']}")
        logger.info(f"   🆕 Ordens criadas: {self.stats['orders_created']}")
        logger.info(f"   🔄 Ordens atualizadas: {self.stats['orders_updated']}")

        if self.stats["errors"]:
            logger.warning(f"   ⚠️ Erros: {len(self.stats['errors'])}")
            logger.warning("   📋 Primeiros 3 erros:")
            for i, error in enumerate(self.stats["errors"][:3]):
                logger.warning(f"      {i+1}. {error}")
        else:
            logger.info("   ✅ Nenhum erro!")

        logger.info("=" * 50)
