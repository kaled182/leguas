import json
import logging
import os
from datetime import datetime

import requests

logger = logging.getLogger(__name__)


class APIConnector:
    """
    Classe responsável pela conexão e comunicação com a API externa.
    Baseada no serviço funcional do ordersmanager.
    """

    def __init__(self):
        self.api_url = os.getenv("API_URL")
        self.cookie_key = os.getenv("COOKIE_KEY")
        self.sync_token = os.getenv("SYNC_TOKEN")

        if not all([self.api_url, self.cookie_key, self.sync_token]):
            raise ValueError("Configurações da API não encontradas no .env")

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
        """Constrói o payload da requisição baseado no ordersmanager funcional"""
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
        Busca dados da API externa - IMPLEMENTAÇÃO REAL
        """
        try:
            logger.info("🌐 Configurando conexão com a API...")
            logger.info(f"   • URL: {self.api_url}")
            logger.info(f"   • Token configurado: {'✅' if self.sync_token else '❌'}")
            logger.info(f"   • Cookie configurado: {'✅' if self.cookie_key else '❌'}")

            headers = self._build_headers()
            payload = self._build_payload()

            logger.info("📡 Enviando requisição para a API...")

            response = requests.post(
                self.api_url, headers=headers, json=payload, timeout=30
            )

            logger.info(f"📨 Resposta recebida - Status: {response.status_code}")

            response.raise_for_status()

            data = response.json()
            logger.info("✅ JSON decodificado com sucesso")
            logger.info(
                f"🔍 Chaves principais: {list(data.keys()) if data else 'Nenhuma'}"
            )

            processed_data = self._process_nested_datasets(data)
            logger.info(
                f"📋 Datasets processados: {list(processed_data.keys()) if processed_data else 'Nenhum'}"
            )

            return processed_data

        except requests.RequestException as e:
            logger.error(f"❌ Erro na requisição HTTP: {e}")
            logger.error(
                f"📋 Status code: {getattr(e.response, 'status_code', 'N/A') if hasattr(e, 'response') else 'N/A'}"
            )
            return None
        except json.JSONDecodeError as e:
            logger.error(f"❌ Erro ao decodificar JSON da resposta: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Erro inesperado na conexão: {e}")
            import traceback

            logger.error(f"📋 Stack trace: {traceback.format_exc()}")
            return None

    def _process_nested_datasets(self, data):
        """
        Processa os datasets aninhados da resposta da API.
        Baseado no ordersmanager funcional.
        """
        logger.info("🔄 Processando datasets da resposta...")

        processed = {}
        nested_datasets = data.get("NestedDataSets", [])

        logger.info(f"📦 Encontrados {len(nested_datasets)} datasets aninhados")

        for dataset in nested_datasets:
            name = dataset.get("Name")
            content = dataset.get("DataSet")

            if name and content:
                try:
                    parsed_content = (
                        json.loads(content) if isinstance(content, str) else content
                    )
                    processed[name] = parsed_content

                    # Log detalhes do dataset
                    if isinstance(parsed_content, dict) and "data" in parsed_content:
                        rows_count = (
                            len(parsed_content["data"]) if parsed_content["data"] else 0
                        )
                        cols_count = (
                            len(parsed_content.get("columns", []))
                            if parsed_content.get("columns")
                            else 0
                        )
                        logger.info(
                            f"   📊 {name}: {rows_count} linhas x {cols_count} colunas"
                        )
                    else:
                        logger.info(f"   📋 {name}: processado")

                except json.JSONDecodeError:
                    logger.warning(f"   ⚠️ Falha ao decodificar dataset {name}")
            else:
                logger.warning(f"   ⚠️ Dataset inválido ou vazio: {name}")

        logger.info(f"✅ Processamento concluído. Datasets válidos: {len(processed)}")
        return processed
