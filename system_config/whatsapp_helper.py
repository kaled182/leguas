"""Helper para integração com WhatsApp através do WPPConnect Server."""
import base64
import io
import logging
import os
import re
from typing import Optional, Dict, List, Sequence, Tuple

import requests
from PIL import Image


DEFAULT_TIMEOUT = 60  # Timeout aumentado para operações de conexão do WhatsApp
logger = logging.getLogger(__name__)


class WhatsAppWPPConnectAPI:
    """Cliente HTTP para WPPConnect Server."""

    def __init__(self, base_url: str, session_name: str, auth_token: str, secret_key: str):
        self.base_url = base_url.rstrip('/')
        self.session_name = session_name
        self.auth_token = auth_token
        self.secret_key = secret_key
        self._token_hash: Optional[str] = None
        self.headers = {
            "Authorization": f"Bearer {auth_token}",
            "x-secret-key": secret_key,
            "Content-Type": "application/json"
        }
    
    def _is_bcrypt_hash(self, token: str) -> bool:
        """Verifica se o token é um hash bcrypt válido."""
        # Hash bcrypt tem formato: $2a$, $2b$ ou $2y$ seguido de exatamente 53 caracteres
        bcrypt_pattern = r'^\$2[ayb]\$\d{2}\$[A-Za-z0-9./]{53}$'
        return bool(re.match(bcrypt_pattern, token))
    
    def _ensure_token_hash(self) -> str:
        """Garante que temos um token hash bcrypt válido."""
        if self._token_hash:
            return self._token_hash
        
        if self._is_bcrypt_hash(self.auth_token):
            self._token_hash = self.auth_token
            return self._token_hash
        
        # Token não é hash bcrypt, precisa gerar via servidor
        try:
            # WPPConnect usa SECRET_KEY padrão: THISISMYSECURETOKEN
            secret_for_generation = "THISISMYSECURETOKEN"
            url = f"{self.base_url}/api/{self.session_name}/{secret_for_generation}/generate-token"
            logger.info(f"[WhatsApp] Gerando token hash via: {url}")
            response = requests.post(url, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            logger.info(f"[WhatsApp] Resposta generate-token: {data}")
            self._token_hash = data.get("token", "")
            
            # Atualizar header para requisições futuras
            if self._token_hash:
                self.headers["Authorization"] = f"Bearer {self._token_hash}"
                logger.info(f"[WhatsApp] Token hash gerado com sucesso: {self._token_hash[:20]}...")
            
            return self._token_hash
        except Exception as e:
            logger.error(f"[WhatsApp] Erro ao gerar token hash: {e}")
            # Se falhar, usa o token original e deixa o servidor recusar
            return self.auth_token

    @classmethod
    def from_config(cls):
        """Cria instância usando SystemConfiguration e variáveis de ambiente."""
        from system_config.models import SystemConfiguration

        config = SystemConfiguration.get_config()

        if not config.whatsapp_enabled:
            raise ValueError("WhatsApp não está habilitado nas configurações")

        base_url = (config.whatsapp_evolution_api_url or "").strip()
        session_name = (config.whatsapp_instance_name or "").strip()

        token = cls._first_env_value([
            "WPP_CONNECT_AUTH_TOKEN",
            "WPP_AUTH_TOKEN",
            "WPPCONNECT_TOKEN"
        ]) or (config.whatsapp_evolution_api_key or "").strip()

        secret_key = cls._first_env_value([
            "WPP_CONNECT_SECRET_KEY",
            "WPP_SECRET_KEY",
            "WPPCONNECT_SECRET_KEY"
        ]) or token

        if not base_url:
            raise ValueError("URL do WPPConnect não configurada")
        if not session_name:
            raise ValueError("Nome da sessão do WhatsApp não configurado")
        if not token:
            raise ValueError("Token de autenticação do WPPConnect não configurado")
        if not secret_key:
            raise ValueError("Secret key do WPPConnect não configurada")

        return cls(base_url=base_url, session_name=session_name, auth_token=token, secret_key=secret_key)

    @staticmethod
    def _first_env_value(keys: Sequence[str]) -> Optional[str]:
        for key in keys:
            value = os.getenv(key)
            if value:
                return value.strip()
        return None

    # ========================================
    # REQUISIÇÕES
    # ========================================

    def _build_url(self, endpoint: str) -> str:
        endpoint = endpoint or ""
        if endpoint and not endpoint.startswith('/'):
            endpoint = f"/{endpoint}"
        return f"{self.base_url}/api/{self.session_name}{endpoint}"

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        # Garante que temos um token hash válido antes de fazer a requisição
        self._ensure_token_hash()
        
        headers = kwargs.pop("headers", {})
        merged_headers = {**self.headers, **headers}
        
        # Timeout maior para operações de start/close de sessão
        timeout = kwargs.pop("timeout", DEFAULT_TIMEOUT)
        if "start" in endpoint or "close" in endpoint or "logout" in endpoint:
            timeout = max(timeout, 90)  # 90 segundos para operações de sessão
        
        response = requests.request(method, self._build_url(endpoint), headers=merged_headers, timeout=timeout, **kwargs)
        response.raise_for_status()
        if response.content:
            return response.json()
        return {}

    # ========================================
    # SESSÃO
    # ========================================

    def create_instance(self, wait_qrcode: bool = True, wait_connection: bool = False, webhook: str = "") -> Dict:
        payload = {
            "waitQrCode": wait_qrcode,
            "waitConnection": wait_connection,
            "webhook": webhook
        }
        try:
            return self._request("post", "/start-session", json=payload)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                return self._request("post", "/start", json=payload)
            raise

    def start_session(self, **kwargs) -> Dict:
        """Alias para create_instance mantendo compatibilidade."""
        return self.create_instance(**kwargs)

    def logout(self) -> Dict:
        try:
            return self._request("post", "/logout-session", json={})
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                return self._request("post", "/logout", json={})
            raise

    def close_session(self) -> Dict:
        return self._request("post", "/close-session", json={})

    def get_qrcode(self) -> Dict:
        try:
            return self._request("get", "/qrcode-session")
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                return self._request("get", "/qrcode/base64")
            raise

    def get_qrcode_image(self) -> Optional[Image.Image]:
        try:
            qr_data = self.get_qrcode()
            base64_str = qr_data.get("qrcode") or qr_data.get("base64") or ""
            if not base64_str:
                return None
            if ',' in base64_str:
                base64_str = base64_str.split(',')[1]
            image_data = base64.b64decode(base64_str)
            return Image.open(io.BytesIO(image_data))
        except Exception as exc:  # pragma: no cover - saída de depuração
            print(f"Erro ao obter QR Code: {exc}")
            return None

    def get_connection_state(self) -> Dict:
        endpoints = [
            "/check-connection-session",
            "/status-session",
            "/status",
        ]
        last_exc: Optional[Exception] = None
        for endpoint in endpoints:
            try:
                return self._request("get", endpoint)
            except requests.HTTPError as exc:
                last_exc = exc
                if exc.response is not None and exc.response.status_code == 404:
                    continue
                raise
        if last_exc:
            raise last_exc
        return {}

    def is_connected(self) -> bool:
        try:
            state = self.get_connection_state()
        except Exception:
            return False

        status_flags = {
            str(state.get("status", "")).upper(),
            str(state.get("state", "")).upper(),
            str(state.get("session", "")).upper()
        }
        if state.get("connected") is True:
            return True
        return any(flag in {"CONNECTED", "OPEN", "LOGGED", "ISLOGGED"} for flag in status_flags)

    def get_session_info(self) -> Dict:
        """Obtém informações detalhadas da sessão incluindo status e dados do perfil."""
        try:
            info = {
                "connected": False,
                "status": "disconnected",
                "session_name": self.session_name,
            }
            
            # 1. Status da conexão
            try:
                state = self.get_connection_state()
                is_connected = (
                    state.get("status") == True or 
                    str(state.get("message", "")).lower() == "connected"
                )
                info.update({
                    "connected": is_connected,
                    "status": "connected" if is_connected else "disconnected",
                    "raw_status": state,
                })
                
                # Extrair número da sessão se disponível
                session_id = state.get("session", "")
                if session_id and is_connected:
                    info["phone"] = f"Sessão: {session_id}"
                    
            except Exception as e:
                logger.warning(f"[WhatsApp] Erro ao obter status da conexão: {e}")
            
            # 2. Informações adicionais se conectado
            if info.get("connected"):
                # Tentar obter detalhes via diferentes endpoints
                additional_endpoints = [
                    ('/status-session', 'Status detalhado'),
                    ('/host-device', 'Dispositivo host'),
                    ('/get-battery-level', 'Bateria'),
                ]
                
                for endpoint, desc in additional_endpoints:
                    try:
                        result = self._request("get", endpoint)
                        logger.info(f"[WhatsApp] {desc} obtido: {result}")
                        
                        # Processar resposta baseado no endpoint
                        if 'host-device' in endpoint and result:
                            phone_data = result.get("id") or result.get("wid") or {}
                            if phone_data.get("user"):
                                info["phone"] = phone_data["user"]
                            info["device"] = {
                                "pushname": result.get("pushname"),
                                "platform": result.get("platform"),
                                "phone": phone_data.get("user"),
                            }
                        elif 'battery' in endpoint and result:
                            info["battery"] = {
                                "level": result.get("battery") or result.get("level"),
                                "plugged": result.get("plugged"),
                            }
                        elif 'status-session' in endpoint and result:
                            # Extrair informações do status da sessão
                            if result.get("number"):
                                info["phone"] = result["number"]
                            if result.get("state") == "CONNECTED":
                                info["status"] = "connected"
                                info["connected"] = True
                                
                    except Exception as e:
                        logger.debug(f"[WhatsApp] Endpoint {endpoint} não disponível: {e}")
                        continue
            
            return info
            
        except Exception as e:
            logger.error(f"[WhatsApp] Erro ao obter informações da sessão: {e}")
            return {
                "connected": False,
                "status": "error",
                "error": str(e),
                "session_name": self.session_name,
            }

    # ========================================
    # MENSAGENS
    # ========================================

    @staticmethod
    def _ensure_recipients(number: Sequence[str] | str) -> List[str]:
        if isinstance(number, str):
            return [number]
        return [str(item) for item in number]

    def send_text(self, number: Sequence[str] | str, text: str) -> Dict:
        payload = {
            "phone": self._ensure_recipients(number),
            "message": text
        }
        return self._request("post", "/send-message", json=payload)

    def send_image(self, number: Sequence[str] | str, image_url: str, caption: str = "") -> Dict:
        b64_file, filename = self._download_as_base64(image_url, default_name="image.png")
        payload = {
            "phone": self._ensure_recipients(number),
            "base64": b64_file,
            "filename": filename,
            "caption": caption
        }
        return self._request("post", "/send-file-base64", json=payload)

    def send_document(self, number: Sequence[str] | str, document_url: str, filename: str = "") -> Dict:
        b64_file, guessed_name = self._download_as_base64(document_url, default_name=filename or "document")
        payload = {
            "phone": self._ensure_recipients(number),
            "base64": b64_file,
            "filename": guessed_name,
            "caption": filename or guessed_name
        }
        return self._request("post", "/send-file-base64", json=payload)

    def send_audio(self, number: Sequence[str] | str, audio_url: str, quoted_message_id: Optional[str] = None) -> Dict:
        b64_file, filename = self._download_as_base64(audio_url, default_name="audio")
        payload = {
            "phone": self._ensure_recipients(number),
            "base64Ptt": b64_file,
            "filename": filename
        }
        if quoted_message_id:
            payload["quotedMessageId"] = quoted_message_id
        return self._request("post", "/send-voice-base64", json=payload)

    def send_location(self, number: Sequence[str] | str, latitude: float, longitude: float, name: str = "", address: str = "") -> Dict:
        payload = {
            "phone": self._ensure_recipients(number),
            "lat": str(latitude),
            "lng": str(longitude),
            "title": name,
            "address": address
        }
        return self._request("post", "/send-location", json=payload)

    def send_contact(self, number: Sequence[str] | str, contact_number: str, contact_name: str) -> Dict:
        payload = {
            "phone": self._ensure_recipients(number),
            "contactsId": [contact_number],
            "name": contact_name
        }
        return self._request("post", "/contact-vcard", json=payload)

    # ========================================
    # GRUPOS
    # ========================================

    def create_group(self, group_name: str, participants: Sequence[str]) -> Dict:
        payload = {
            "name": group_name,
            "participants": self._ensure_recipients(list(participants))
        }
        return self._request("post", "/create-group", json=payload)

    def add_participant(self, group_id: str, participants: Sequence[str]) -> Dict:
        payload = {
            "groupId": group_id,
            "phone": self._ensure_recipients(list(participants))
        }
        return self._request("post", "/add-participant-group", json=payload)

    def remove_participant(self, group_id: str, participants: Sequence[str]) -> Dict:
        payload = {
            "groupId": group_id,
            "phone": self._ensure_recipients(list(participants))
        }
        return self._request("post", "/remove-participant-group", json=payload)

    def promote_to_admin(self, group_id: str, participants: Sequence[str]) -> Dict:
        payload = {
            "groupId": group_id,
            "phone": self._ensure_recipients(list(participants))
        }
        return self._request("post", "/promote-participant-group", json=payload)

    # ========================================
    # WEBHOOK
    # ========================================

    def set_webhook(self, webhook_url: str, events: Optional[List[str]] = None) -> Dict:
        payload: Dict[str, object] = {
            "url": webhook_url,
            "enabled": True
        }
        if events:
            payload["events"] = events
        return self._request("post", "/set-webhook", json=payload)

    def get_webhook(self) -> Dict:
        return self._request("get", "/webhook")

    # ========================================
    # UTILITÁRIOS
    # ========================================

    @staticmethod
    def _infer_filename(source: str, default_name: str) -> str:
        parsed = source.split('/')[-1].split('?')[0].strip()
        if parsed:
            return parsed
        return default_name

    def _download_as_base64(self, url: str, default_name: str) -> Tuple[str, str]:
        response = requests.get(url, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        content = response.content or b""
        if not content:
            raise ValueError("Arquivo remoto vazio")
        filename = self._infer_filename(url, default_name)
        encoded = base64.b64encode(content).decode("utf-8")
        return encoded, filename


# ========================================
# FUNÇÕES HELPER
# ========================================

def format_phone_number(phone: str) -> str:
    """
    Formata número de telefone para padrão WhatsApp
    
    Args:
        phone: Número em qualquer formato
        
    Returns:
        Número formatado: DDI+DDD+Número (ex: 5511999999999)
    """
    # Remove tudo que não é número
    clean = ''.join(filter(str.isdigit, phone))
    
    # Se não começa com 55 (Brasil), adiciona
    if not clean.startswith('55'):
        clean = '55' + clean
    
    return clean


def save_qrcode_image(image: Image.Image, filepath: str):
    """
    Salva QR Code como imagem
    
    Args:
        image: Imagem PIL do QR Code
        filepath: Caminho para salvar (ex: qrcode.png)
    """
    image.save(filepath, 'PNG')
    print(f"QR Code salvo em: {filepath}")


# ========================================
# EXEMPLO DE USO
# ========================================

if __name__ == "__main__":
    # Usar configuração do sistema
    try:
        whatsapp = WhatsAppWPPConnectAPI.from_config()
        
        # Verificar conexão
        if whatsapp.is_connected():
            print("✅ WhatsApp conectado!")
            
            # Enviar mensagem teste
            response = whatsapp.send_text(
                number="5511999999999",
                text="Olá! Esta é uma mensagem de teste! 🚚"
            )
            print(f"Mensagem enviada: {response}")
        else:
            print("❌ WhatsApp não está conectado")
            print("Obtendo QR Code...")
            
            # Obter e salvar QR Code
            qr_image = whatsapp.get_qrcode_image()
            if qr_image:
                save_qrcode_image(qr_image, "whatsapp_qrcode.png")
                print("Escaneie o QR Code com o WhatsApp!")
    
    except Exception as e:
        print(f"Erro: {e}")
