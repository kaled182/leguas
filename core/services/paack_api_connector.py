"""
Conector para API Paack (AppSheet).
Adaptado de ordersmanager_paack/APIConnect.py para usar PartnerIntegration.
"""

import json
import logging
from datetime import datetime

import requests

logger = logging.getLogger(__name__)


class PaackAPIConnector:
    """
    Classe responsável pela conexão com a API Paack (AppSheet).
    Usa configurações de PartnerIntegration ao invés de variáveis de ambiente.
    """

    def __init__(self, partner_integration):
        """
        Inicializa o conector com uma PartnerIntegration.
        
        Args:
            partner_integration: Instância de core.models.PartnerIntegration
        """
        self.integration = partner_integration
        auth_config = partner_integration.auth_config or {}
        
        self.api_url = auth_config.get("api_url")
        self.cookie_key = auth_config.get("cookie_key")
        self.sync_token = auth_config.get("sync_token")

        if not all([self.api_url, self.cookie_key, self.sync_token]):
            raise ValueError(
                f"Configurações incompletas para {partner_integration.partner.name}. "
                "Verifique auth_config (api_url, cookie_key, sync_token)."
            )

    def _build_headers(self):
        """Constrói os headers necessários para a requisição"""
        return {
            "Accept": "*/*",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
            "Cookie": self.cookie_key,
            "Authorization": f"Bearer {self.sync_token}",
        }

    def _build_payload(self):
        """Constrói o payload da requisição baseado no formato AppSheet"""
        current_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        return {
            "settings": json.dumps({"_THISUSER": "onlyvalue"}),
            "getAllTables": True,
            "syncsOnConsent": True,
            "syncUI": "Subtle",
            "initiatedBy": "User",
            "isPreview": False,
            "apiLevel": 2,
            "supportsJsonDataSets": True,
            "tzOffset": -60,
            "locale": "pt-BR",
            "perTableParams": {
                "DATA_EXTRACT_AVG": {
                    "time": current_time,
                    "etag": "D7EF8D1712858901F8FA91A7CAB64ACC",
                },
                "DATA_PIVOT": {
                    "time": current_time,
                    "etag": "63FF4BC1FFEA18FDD5C40D35C59C4EA7",
                },
            },
            "lastSyncTime": current_time,
            "appStartTime": current_time,
            "dataStamp": current_time,
            "clientId": "09939592-a94c-41d0-8d7a-0642fc73aacc",
            "build": "aaaaaaaaaaaaaaaaaaaa-1747452017222-60291a87",
            "hasValidPlan": True,
            "userConsentedScopes": "data_input,device_identity,device_io,profile,usage",
            "localVersion": "1.000140",
            "isBackgroundSync": True,
            "syncToken": self.sync_token,
        }

    def fetch_data(self):
        """
        Busca dados da API Paack (AppSheet).
        
        Returns:
            dict: Dados JSON da API ou None em caso de erro
        """
        try:
            logger.info(f"🌐 Conectando com API {self.integration.partner.name}...")
            logger.info(f"   • URL: {self.api_url}")
            logger.info(f"   • Token configurado: {'✅' if self.sync_token else '❌'}")
            logger.info(f"   • Cookie configurado: {'✅' if self.cookie_key else '❌'}")

            headers = self._build_headers()
            payload = self._build_payload()

            logger.info("📡 Enviando requisição POST...")

            response = requests.post(
                self.api_url, 
                headers=headers, 
                json=payload, 
                timeout=30
            )

            logger.info(f"📨 Resposta recebida - Status: {response.status_code}")

            response.raise_for_status()

            data = response.json()
            logger.info("✅ JSON decodificado com sucesso")
            logger.info(
                f"🔍 Chaves principais: {list(data.keys()) if data else 'Nenhuma'}"
            )

            return data

        except requests.exceptions.Timeout:
            logger.error("⏱️ Timeout - API não respondeu em 30 segundos")
            return None
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP Error: {e}")
            logger.error(f"   Status: {response.status_code}")
            logger.error(f"   Response: {response.text[:200]}")
            return None
            
        except Exception as e:
            logger.error(f"💥 Erro ao buscar dados da API: {e}")
            import traceback
            logger.error(f"📋 Stack trace: {traceback.format_exc()}")
            return None
