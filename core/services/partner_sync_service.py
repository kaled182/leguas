"""
Serviço principal de sincronização com parceiros.
Adaptado de ordersmanager_paack/sync_service.py para sistema genérico.
"""

import logging

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from core.models import SyncLog
from .paack_api_connector import PaackAPIConnector
from .partner_data_processor import PartnerDataProcessor

logger = logging.getLogger(__name__)


class PartnerSyncService:
    """
    Serviço principal de sincronização com parceiros logísticos.
    Coordena a conexão com a API e o processamento dos dados.
    """

    # Cache timeout: 5 minutos (300 segundos)
    CACHE_TIMEOUT = 300

    def __init__(self, partner_integration):
        """
        Inicializa o serviço de sincronização.
        
        Args:
            partner_integration: Instância de core.models.PartnerIntegration
        """
        self.integration = partner_integration
        self.partner = partner_integration.partner
        self.cache_key = f"partner_sync_data_{self.partner.id}"

        # Inicializar conectores baseados no tipo de integração
        # Por enquanto apenas Paack (AppSheet), mas extensível para outros
        auth_type = partner_integration.auth_config.get("type", "")
        
        if auth_type == "custom_paack":
            self.api_connector = PaackAPIConnector(partner_integration)
        else:
            # TODO: Adicionar outros conectores (Amazon, DPD, etc.)
            raise ValueError(
                f"Tipo de integração não suportado: {auth_type}. "
                f"Tipos disponíveis: custom_paack"
            )

        self.data_processor = PartnerDataProcessor(partner_integration)

    def sync_data(self, force_refresh=False):
        """
        Executa a sincronização completa dos dados.
        
        Args:
            force_refresh (bool): Se True, ignora o cache
            
        Returns:
            dict: Resultado da sincronização com estatísticas
        """
        sync_log = None
        
        try:
            logger.info(f"🚀 Iniciando sincronização com {self.partner.name}...")
            logger.info(f"   • Integração ID: {self.integration.id}")
            logger.info(f"   • Force refresh: {force_refresh}")
            logger.info(f"   • Última sync: {self.integration.last_sync_at or 'Nunca'}")

            # Criar log de sincronização
            sync_log = SyncLog.objects.create(
                integration=self.integration,
                status="STARTED"
            )

            # Verificar cache primeiro
            if not force_refresh:
                cached_data = cache.get(self.cache_key)
                if cached_data:
                    logger.info("📦 Dados encontrados no cache, processando...")
                    result = self._process_cached_data(cached_data, sync_log)
                    return result

            logger.info("🌐 Cache ignorado ou vazio, buscando dados da API...")

            # Buscar dados da API
            api_data = self.api_connector.fetch_data()
            
            if not api_data:
                error_msg = "Falha ao obter dados da API - resposta vazia"
                logger.error(f"❌ {error_msg}")
                
                # Atualizar log de erro
                sync_log.completed_at = timezone.now()
                sync_log.status = "ERROR"
                sync_log.error_details = error_msg
                sync_log.save()
                
                # Atualizar integração
                self.integration.last_sync_at = timezone.now()
                self.integration.last_sync_status = "ERROR"
                self.integration.save()
                
                return {
                    "success": False,
                    "error": error_msg,
                    "stats": {},
                }

            logger.info("✅ Dados da API obtidos com sucesso!")
            logger.info("📋 Iniciando processamento em transação atômica...")

            # Processar dados em transação
            with transaction.atomic():
                stats = self.data_processor.process_data(api_data)

            # Armazenar em cache
            cache.set(self.cache_key, api_data, self.CACHE_TIMEOUT)
            logger.info(f"💾 Dados armazenados no cache por {self.CACHE_TIMEOUT}s")

            # Atualizar log de sucesso
            sync_log.completed_at = timezone.now()
            sync_log.status = "SUCCESS"
            sync_log.records_processed = stats.get("total_processed", 0)
            sync_log.records_created = stats.get("orders_created", 0)
            sync_log.records_updated = stats.get("orders_updated", 0)
            sync_log.save()

            # Atualizar integração
            self.integration.last_sync_at = timezone.now()
            self.integration.last_sync_status = "SUCCESS"
            self.integration.save()

            logger.info("🎉 Sincronização concluída com sucesso!")

            return {
                "success": True,
                "message": "Sincronização concluída",
                "stats": stats,
                "sync_log_id": sync_log.id,
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"💥 ERRO CRÍTICO na sincronização: {error_msg}")
            
            import traceback
            logger.error(f"📋 Stack trace: {traceback.format_exc()}")

            # Atualizar log de erro
            if sync_log:
                sync_log.completed_at = timezone.now()
                sync_log.status = "ERROR"
                sync_log.error_details = error_msg[:500]  # Limitar tamanho
                sync_log.save()

            # Atualizar integração
            self.integration.last_sync_at = timezone.now()
            self.integration.last_sync_status = "ERROR"
            self.integration.save()

            return {
                "success": False,
                "error": error_msg,
                "stats": {},
            }

    def _process_cached_data(self, cached_data, sync_log):
        """Processa dados do cache"""
        try:
            logger.info("📦 Processando dados do cache...")
            
            with transaction.atomic():
                stats = self.data_processor.process_data(cached_data)

            # Atualizar log
            sync_log.completed_at = timezone.now()
            sync_log.status = "SUCCESS"
            sync_log.records_processed = stats.get("total_processed", 0)
            sync_log.records_created = stats.get("orders_created", 0)
            sync_log.records_updated = stats.get("orders_updated", 0)
            sync_log.is_from_cache = True  # Marcar como do cache
            sync_log.save()

            # Atualizar integração
            self.integration.last_sync_at = timezone.now()
            self.integration.last_sync_status = "SUCCESS"
            self.integration.save()

            return {
                "success": True,
                "message": "Dados processados do cache",
                "stats": stats,
                "sync_log_id": sync_log.id,
                "from_cache": True,
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Erro ao processar cache: {error_msg}")
            
            # Atualizar log de erro
            sync_log.completed_at = timezone.now()
            sync_log.status = "ERROR"
            sync_log.error_details = error_msg[:500]
            sync_log.save()
            
            raise
