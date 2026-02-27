import logging
from django.core.cache import cache
from django.db import transaction
from django.conf import settings
from .APIConnect import APIConnector
from .data_processor import DataProcessor

logger = logging.getLogger(__name__)

class SyncService:
    """
    Serviço principal de sincronização.
    Coordena a conexão com a API e o processamento dos dados.
    """
    
    CACHE_KEY = 'paack_api_data'
    CACHE_TIMEOUT = 300  # 5 minutos
    
    def __init__(self):
        self.api_connector = APIConnector()
        self.data_processor = DataProcessor()
    
    def sync_data(self, force_refresh=False):
        """
        Executa a sincronização completa dos dados.
        Garante que todas as operações ORM utilizem o banco padrão (MySQL).
        
        Args:
            force_refresh (bool): Se True, ignora o cache
            
        Returns:
            dict: Resultado da sincronização com estatísticas
        """
        try:
            logger.info("� Configurações do sistema:")
            logger.info(f"   • Banco: {settings.DATABASES['default']['ENGINE']}")
            logger.info(f"   • Host: {settings.DATABASES['default']['HOST']}")
            logger.info(f"   • Database: {settings.DATABASES['default']['NAME']}")
            logger.info(f"   • Force refresh: {force_refresh}")
            
            # Verificar cache primeiro
            if not force_refresh:
                cached_data = cache.get(self.CACHE_KEY)
                if cached_data:
                    logger.info("📦 Dados encontrados no cache, processando...")
                    return self._process_cached_data(cached_data)
            
            logger.info("🌐 Cache ignorado ou vazio, buscando dados da API...")
            
            # Buscar dados da API
            api_data = self.api_connector.fetch_data()
            if not api_data:
                logger.error("❌ Falha ao obter dados da API - resposta vazia")
                return {
                    'success': False,
                    'error': 'Falha ao obter dados da API',
                    'stats': {}
                }
            
            logger.info(f"✅ Dados da API obtidos com sucesso!")
            logger.info(f"📋 Iniciando processamento em transação atômica...")
            
            # Processar dados em transação (usa o banco padrão automaticamente)
            with transaction.atomic():
                stats = self.data_processor.process_data(api_data)
            
            # Armazenar em cache
            cache.set(self.CACHE_KEY, api_data, self.CACHE_TIMEOUT)
            logger.info(f"💾 Dados armazenados no cache por {self.CACHE_TIMEOUT} segundos")
            
            logger.info("🎉 Sincronização concluída com sucesso!")
            
            return {
                'success': True,
                'message': 'Sincronização concluída',
                'stats': stats
            }
            
        except Exception as e:
            logger.error(f"💥 ERRO CRÍTICO na sincronização: {e}")
            import traceback
            logger.error(f"📋 Stack trace: {traceback.format_exc()}")
            return {
                'success': False,
                'error': str(e),
                'stats': {}
            }
    
    def _process_cached_data(self, cached_data):
        """Processa dados do cache (usa banco padrão automaticamente)"""
        with transaction.atomic():
            stats = self.data_processor.process_data(cached_data)
        
        return {
            'success': True,
            'message': 'Dados processados do cache',
            'stats': stats
        }
    
    def clear_cache(self):
        """Limpa o cache de dados"""
        cache.delete(self.CACHE_KEY)
        logger.info("🗑️ Cache limpo")