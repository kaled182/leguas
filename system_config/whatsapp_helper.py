"""Helper para integração com WhatsApp através do WPPConnect Server."""

import base64
import io
import logging
import os
import re
from typing import Dict, List, Optional, Sequence, Tuple

import requests
from PIL import Image

DEFAULT_TIMEOUT = 60  # Timeout aumentado para operações de conexão do WhatsApp
logger = logging.getLogger(__name__)


class WhatsAppWPPConnectAPI:
    """Cliente HTTP para WPPConnect Server."""

    def __init__(
        self,
        base_url: str,
        session_name: str,
        auth_token: str,
        secret_key: str,
    ):
        self.base_url = base_url.rstrip("/")
        self.session_name = session_name
        self.auth_token = auth_token
        self.secret_key = secret_key
        self._token_hash: Optional[str] = None
        self.headers = {
            "Authorization": f"Bearer {auth_token}",
            "x-secret-key": secret_key,
            "Content-Type": "application/json",
        }

    def _is_bcrypt_hash(self, token: str) -> bool:
        """Verifica se o token é um hash bcrypt válido."""
        # Hash bcrypt tem formato: $2a$, $2b$ ou $2y$ seguido de exatamente 53
        # caracteres
        bcrypt_pattern = r"^\$2[ayb]\$\d{2}\$[A-Za-z0-9./]{53}$"
        return bool(re.match(bcrypt_pattern, token))

    def _generate_token_with_secret(self, secret: str) -> Optional[str]:
        """Tenta gerar um token bcrypt usando um SECRET_KEY específico.

        Devolve o token gerado, ou None se o secret for recusado.
        """
        if not secret:
            return None
        url = (
            f"{self.base_url}/api/{self.session_name}/{secret}/generate-token"
        )
        try:
            response = requests.post(url, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            # WPPConnect devolve {"status":"success","token":"..."} em êxito
            # ou {"response":false,"message":"The SECRET_KEY is incorrect"}
            if data.get("response") is False or data.get("status") == "error":
                logger.warning(
                    "[WhatsApp] generate-token recusou o secret "
                    f"({data.get('message')})"
                )
                return None
            return data.get("token") or None
        except Exception as e:
            logger.warning(f"[WhatsApp] generate-token falhou: {e}")
            return None

    def _ensure_token_hash(self) -> str:
        """Garante que temos um token hash bcrypt válido.

        Tenta gerar com o SECRET_KEY configurado; se for recusado, faz
        fallback ao default do WPPConnect (THISISMYSECURETOKEN) — cobre
        ambientes onde o container ainda corre com o secret antigo.
        """
        if self._token_hash:
            return self._token_hash

        if self._is_bcrypt_hash(self.auth_token):
            self._token_hash = self.auth_token
            return self._token_hash

        # Token não é hash bcrypt — gerar via servidor.
        # Ordem de tentativa: secret configurado → secret default.
        candidates = []
        if self.secret_key:
            candidates.append(self.secret_key)
        if "THISISMYSECURETOKEN" not in candidates:
            candidates.append("THISISMYSECURETOKEN")

        for secret in candidates:
            token = self._generate_token_with_secret(secret)
            if token:
                self._token_hash = token
                self.headers["Authorization"] = f"Bearer {token}"
                logger.info(
                    "[WhatsApp] Token hash gerado com sucesso "
                    f"({token[:20]}...)"
                )
                return self._token_hash

        logger.error(
            "[WhatsApp] Não foi possível gerar token hash — nenhum "
            "SECRET_KEY aceite. Usando token original."
        )
        return self.auth_token

    @classmethod
    def from_config(cls, require_enabled: bool = True):
        """Cria instância a partir de SystemConfiguration + variáveis de ambiente.

        SystemConfiguration tem prioridade; quando um campo está vazio,
        recorre às env vars (WPPCONNECT_URL / WPPCONNECT_INSTANCE / …).
        Isto evita divergências entre o painel de configurações e os
        serviços que enviam mensagens (ex.: pré-faturas).
        """
        from system_config.models import SystemConfiguration

        config = SystemConfiguration.get_config()

        if require_enabled and not config.whatsapp_enabled:
            raise ValueError("WhatsApp não está habilitado nas configurações")

        base_url = (
            (config.whatsapp_evolution_api_url or "").strip()
            or cls._first_env_value(["WPPCONNECT_URL"])
            or ""
        )
        session_name = (
            (config.whatsapp_instance_name or "").strip()
            or cls._first_env_value(
                ["WPPCONNECT_INSTANCE", "WPPCONNECT_SESSION"]
            )
            or ""
        )

        token = (
            cls._first_env_value(
                [
                    "WPP_CONNECT_AUTH_TOKEN",
                    "WPP_AUTH_TOKEN",
                    "WPPCONNECT_TOKEN",
                ]
            )
            or (config.whatsapp_evolution_api_key or "").strip()
        )

        secret_key = (
            cls._first_env_value(
                [
                    "WPP_CONNECT_SECRET_KEY",
                    "WPP_SECRET_KEY",
                    "WPPCONNECT_SECRET_KEY",
                    "WPPCONNECT_SECRET",
                ]
            )
            or token
        )

        if not base_url:
            raise ValueError("URL do WPPConnect não configurada")
        if not session_name:
            raise ValueError("Nome da sessão do WhatsApp não configurado")
        if not token:
            raise ValueError("Token de autenticação do WPPConnect não configurado")
        if not secret_key:
            raise ValueError("Secret key do WPPConnect não configurada")

        return cls(
            base_url=base_url,
            session_name=session_name,
            auth_token=token,
            secret_key=secret_key,
        )

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
        if endpoint and not endpoint.startswith("/"):
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

        response = requests.request(
            method,
            self._build_url(endpoint),
            headers=merged_headers,
            timeout=timeout,
            **kwargs,
        )
        response.raise_for_status()
        if response.content:
            return response.json()
        return {}

    # ========================================
    # SESSÃO
    # ========================================

    def create_instance(
        self,
        wait_qrcode: bool = True,
        wait_connection: bool = False,
        webhook: str = "",
    ) -> Dict:
        payload = {
            "waitQrCode": wait_qrcode,
            "waitConnection": wait_connection,
            "webhook": webhook,
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
        """Encerra a sessão. Idempotente — se já estiver fechada, devolve ok.

        Diferentes versões do WPPConnect expõem endpoints distintos e
        respondem 500 "Error closing session" quando não há nada a fechar.
        """
        last_exc = None
        for endpoint in ("/logout-session", "/close-session", "/logout"):
            try:
                return self._request("post", endpoint, json={})
            except requests.HTTPError as exc:
                last_exc = exc
                code = (
                    exc.response.status_code
                    if exc.response is not None else 0
                )
                if code == 404:
                    continue  # endpoint não existe nesta versão
                if code in (409, 500):
                    # sessão já estava fechada/sem sessão activa
                    return {
                        "status": True,
                        "message": "Session already closed",
                    }
                raise
            except Exception as exc:
                last_exc = exc
                continue
        return {
            "status": True,
            "message": "Nenhum endpoint de logout disponível",
            "warning": str(last_exc) if last_exc else None,
        }

    def close_session(self) -> Dict:
        return self._request("post", "/close-session", json={})

    def get_qrcode(self) -> Dict:
        """Obtém o QR Code da sessão de forma defensiva.

        O WPPConnect pode responder JSON ({status, qrcode}) ou — quando
        o QR está pronto — a imagem PNG crua. Normalizamos sempre para
        {"qrcode": <data-uri|None>, "status": <str>, ...} e NUNCA
        levantamos JSONDecodeError (era a causa do 500 em /qrcode/).
        """
        self._ensure_token_hash()
        last_err = None
        for endpoint in ("/qrcode-session", "/qrcode/base64"):
            try:
                resp = requests.get(
                    self._build_url(endpoint),
                    headers=self.headers,
                    timeout=DEFAULT_TIMEOUT,
                )
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                ctype = resp.headers.get("Content-Type", "")
                if ctype.startswith("image/"):
                    b64 = base64.b64encode(resp.content).decode("utf-8")
                    return {
                        "qrcode": f"data:{ctype};base64,{b64}",
                        "status": "QRCODE",
                    }
                try:
                    data = resp.json()
                except ValueError:
                    last_err = "resposta não-JSON do /qrcode"
                    continue
                qr = (
                    data.get("qrcode") or data.get("base64")
                    or data.get("qrCode")
                )
                return {
                    "qrcode": qr,
                    "pairingCode": (
                        data.get("pairingCode") or data.get("urlcode")
                        or data.get("code")
                    ),
                    "status": data.get("status", ""),
                    "message": data.get("message", ""),
                    "raw": data,
                }
            except requests.HTTPError as exc:
                last_err = str(exc)
                continue
            except Exception as exc:
                last_err = str(exc)
                continue
        return {"qrcode": None, "status": "UNKNOWN", "error": last_err}

    def get_qrcode_image(self) -> Optional[Image.Image]:
        try:
            qr_data = self.get_qrcode()
            base64_str = qr_data.get("qrcode") or qr_data.get("base64") or ""
            if not base64_str:
                return None
            if "," in base64_str:
                base64_str = base64_str.split(",")[1]
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

    # Mapeamento dos status textuais do WPPConnect → estado normalizado
    _CONNECTED_STATES = {
        "CONNECTED", "INCHAT", "ISLOGGED", "QRREADSUCCESS", "MAINLOADED",
    }
    _QR_STATES = {"QRCODE", "PAIRING", "UNPAIRED", "UNPAIRED_IDLE", "NOTLOGGED"}
    _INIT_STATES = {"INITIALIZING", "STARTING", "WAITING", "BROWSER"}
    _CLOSED_STATES = {"CLOSED", "DISCONNECTED", "DESTROYED", "CONFLICT"}

    def get_health(self) -> Dict:
        """Diagnóstico unificado do serviço + sessão — fonte única de verdade.

        Devolve:
          service_up : o servidor WPPConnect respondeu
          connected  : WhatsApp autenticado e operacional
          state      : CONNECTED | QRCODE | INITIALIZING | CLOSED | UNKNOWN
          phone, session, raw, error
        """
        health = {
            "service_up": False,
            "session": self.session_name,
            "connected": False,
            "state": "UNKNOWN",
            "phone": "",
            "raw": {},
            "error": None,
        }

        # status-session — status textual rico (CLOSED/CONNECTED/QRCODE/…)
        raw = {}
        try:
            raw = self._request("get", "/status-session")
            health["service_up"] = True
        except requests.HTTPError as exc:
            # o servidor respondeu (mesmo que com erro) → está de pé
            health["service_up"] = True
            code = getattr(exc.response, "status_code", "?")
            health["error"] = f"status-session HTTP {code}"
        except Exception as exc:
            health["error"] = f"Serviço WPPConnect inacessível: {exc}"
            return health  # service_up permanece False

        health["raw"] = raw
        state_str = str(raw.get("status", "")).upper()

        if state_str in self._CONNECTED_STATES:
            health["state"] = "CONNECTED"
            health["connected"] = True
        elif state_str in self._QR_STATES:
            health["state"] = "QRCODE"
        elif state_str in self._INIT_STATES:
            health["state"] = "INITIALIZING"
        elif state_str in self._CLOSED_STATES:
            health["state"] = "CLOSED"

        # Confirmação cruzada — check-connection-session usa status booleano
        try:
            chk = self._request("get", "/check-connection-session")
            if chk.get("status") is True:
                health["connected"] = True
                if health["state"] in ("UNKNOWN", "CLOSED"):
                    health["state"] = "CONNECTED"
            elif chk.get("status") is False and health["connected"]:
                # status-session disse conectado mas o check diz que não —
                # confia no check (mais fiável p/ sessão realmente activa)
                health["connected"] = False
                if health["state"] == "CONNECTED":
                    health["state"] = "CLOSED"
        except Exception:
            pass  # check-connection é apenas confirmação

        # Número de telefone quando conectado
        if health["connected"]:
            try:
                host = self._request("get", "/host-device")
                wid = host.get("id") or host.get("wid") or {}
                if isinstance(wid, dict) and wid.get("user"):
                    health["phone"] = wid["user"]
                elif raw.get("number"):
                    health["phone"] = raw["number"]
            except Exception:
                if raw.get("number"):
                    health["phone"] = raw["number"]

        return health

    def is_connected(self) -> bool:
        """True só se o WhatsApp estiver realmente autenticado e operacional."""
        try:
            return bool(self.get_health().get("connected"))
        except Exception:
            return False

    def get_session_info(self) -> Dict:
        """Compat: shape antigo, agora derivado de `get_health()`."""
        h = self.get_health()
        return {
            "connected": h["connected"],
            "service_up": h["service_up"],
            "state": h["state"],
            "status": "connected" if h["connected"] else h["state"].lower(),
            "session_name": h["session"],
            "phone": h["phone"],
            "raw_status": h["raw"],
            "error": h["error"],
        }

    def ensure_session(self) -> Dict:
        """Garante uma sessão utilizável e devolve o que o frontend precisa.

        - Serviço em baixo → devolve health (service_up=False).
        - Já conectado → devolve health.
        - Sessão CLOSED → arranca-a; o WPPConnect bloqueia o
          /start-session (waitQrCode) e devolve o QR directamente.
        - Sessão INITIALIZING/QRCODE → já está a arrancar; faz um
          curto polling à espera que o QR materialize. Se não
          aparecer, devolve `needs_restart=True` para o frontend
          aconselhar reinício do serviço WPPConnect.

        Nota: o WPPConnect só entrega o QR de forma fiável quando a
        sessão arranca a partir de CLOSED. Sessões presas em
        INITIALIZING não recuperam pela API (o close-session deixa
        órfãos de puppeteer) — a recuperação fiável é reiniciar o
        container do WPPConnect.
        """
        import time as _time

        health = self.get_health()
        result = dict(health)
        result["qrcode"] = None
        result["pairingCode"] = None
        result["needs_restart"] = False

        if not health["service_up"] or health["connected"]:
            return result

        # Caminho feliz: sessão fechada → arranca e recebe o QR na resposta
        if health["state"] in ("CLOSED", "UNKNOWN"):
            try:
                payload = self.create_instance(
                    wait_qrcode=True, wait_connection=False, webhook="",
                )
                result["qrcode"] = (
                    payload.get("qrcode") or payload.get("base64")
                    or payload.get("qrCode")
                )
                result["pairingCode"] = (
                    payload.get("pairingCode") or payload.get("urlcode")
                    or payload.get("code")
                )
                pstate = str(payload.get("status", "")).upper()
                if result["qrcode"] or pstate in ("QRCODE", "QRCODE"):
                    result["state"] = "QRCODE"
                elif pstate in self._CONNECTED_STATES:
                    result["state"] = "CONNECTED"
                    result["connected"] = True
            except Exception as exc:
                result["error"] = f"Falha ao arrancar sessão: {exc}"
                return result

        # Sessão já a arrancar (ou acabou de arrancar sem QR na resposta):
        # faz um curto polling — o QR costuma materializar em segundos.
        if not result["qrcode"] and not result["connected"]:
            for _ in range(8):  # ~24s no total
                _time.sleep(3)
                qr = self.get_qrcode()
                if qr.get("qrcode"):
                    result["qrcode"] = qr["qrcode"]
                    result["pairingCode"] = qr.get("pairingCode")
                    result["state"] = "QRCODE"
                    break
                hh = self.get_health()
                if hh["connected"]:
                    result["connected"] = True
                    result["state"] = "CONNECTED"
                    break
                result["state"] = hh["state"]
            else:
                # esgotou o polling sem QR — sessão presa
                result["needs_restart"] = True
                result["error"] = (
                    "A sessão não gerou o QR Code. Reinicie o serviço "
                    "WPPConnect (botão 'Desativar/Ativar' ou reinício "
                    "do container) e tente novamente."
                )

        return result

    # ========================================
    # MENSAGENS
    # ========================================

    @staticmethod
    def _ensure_recipients(number: Sequence[str] | str) -> List[str]:
        if isinstance(number, str):
            return [number]
        return [str(item) for item in number]

    def send_text(self, number: Sequence[str] | str, text: str) -> Dict:
        payload = {"phone": self._ensure_recipients(number), "message": text}
        return self._request("post", "/send-message", json=payload)

    def send_image(
        self, number: Sequence[str] | str, image_url: str, caption: str = ""
    ) -> Dict:
        b64_file, filename = self._download_as_base64(
            image_url, default_name="image.png"
        )
        payload = {
            "phone": self._ensure_recipients(number),
            "base64": b64_file,
            "filename": filename,
            "caption": caption,
        }
        return self._request("post", "/send-file-base64", json=payload)

    def send_document(
        self,
        number: Sequence[str] | str,
        document_url: str,
        filename: str = "",
    ) -> Dict:
        b64_file, guessed_name = self._download_as_base64(
            document_url, default_name=filename or "document"
        )
        payload = {
            "phone": self._ensure_recipients(number),
            "base64": b64_file,
            "filename": guessed_name,
            "caption": filename or guessed_name,
        }
        return self._request("post", "/send-file-base64", json=payload)

    def send_document_base64(
        self,
        number: Sequence[str] | str,
        b64_content: str,
        filename: str,
        caption: str = "",
    ) -> Dict:
        """Envia um documento já em base64 (sem download via URL).

        Útil para PDFs gerados em memória que estão atrás de login.
        """
        payload = {
            "phone": self._ensure_recipients(number),
            "base64": b64_content,
            "filename": filename,
            "caption": caption or filename,
        }
        return self._request("post", "/send-file-base64", json=payload)

    def send_audio(
        self,
        number: Sequence[str] | str,
        audio_url: str,
        quoted_message_id: Optional[str] = None,
    ) -> Dict:
        b64_file, filename = self._download_as_base64(audio_url, default_name="audio")
        payload = {
            "phone": self._ensure_recipients(number),
            "base64Ptt": b64_file,
            "filename": filename,
        }
        if quoted_message_id:
            payload["quotedMessageId"] = quoted_message_id
        return self._request("post", "/send-voice-base64", json=payload)

    def send_location(
        self,
        number: Sequence[str] | str,
        latitude: float,
        longitude: float,
        name: str = "",
        address: str = "",
    ) -> Dict:
        payload = {
            "phone": self._ensure_recipients(number),
            "lat": str(latitude),
            "lng": str(longitude),
            "title": name,
            "address": address,
        }
        return self._request("post", "/send-location", json=payload)

    def send_contact(
        self,
        number: Sequence[str] | str,
        contact_number: str,
        contact_name: str,
    ) -> Dict:
        payload = {
            "phone": self._ensure_recipients(number),
            "contactsId": [contact_number],
            "name": contact_name,
        }
        return self._request("post", "/contact-vcard", json=payload)

    # ========================================
    # GRUPOS
    # ========================================

    def create_group(self, group_name: str, participants: Sequence[str]) -> Dict:
        payload = {
            "name": group_name,
            "participants": self._ensure_recipients(list(participants)),
        }
        return self._request("post", "/create-group", json=payload)

    def add_participant(self, group_id: str, participants: Sequence[str]) -> Dict:
        payload = {
            "groupId": group_id,
            "phone": self._ensure_recipients(list(participants)),
        }
        return self._request("post", "/add-participant-group", json=payload)

    def remove_participant(self, group_id: str, participants: Sequence[str]) -> Dict:
        payload = {
            "groupId": group_id,
            "phone": self._ensure_recipients(list(participants)),
        }
        return self._request("post", "/remove-participant-group", json=payload)

    def promote_to_admin(self, group_id: str, participants: Sequence[str]) -> Dict:
        payload = {
            "groupId": group_id,
            "phone": self._ensure_recipients(list(participants)),
        }
        return self._request("post", "/promote-participant-group", json=payload)

    # ========================================
    # WEBHOOK
    # ========================================

    def set_webhook(self, webhook_url: str, events: Optional[List[str]] = None) -> Dict:
        payload: Dict[str, object] = {"url": webhook_url, "enabled": True}
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
        parsed = source.split("/")[-1].split("?")[0].strip()
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
    clean = "".join(filter(str.isdigit, phone))

    # Se não começa com 55 (Brasil), adiciona
    if not clean.startswith("55"):
        clean = "55" + clean

    return clean


def save_qrcode_image(image: Image.Image, filepath: str):
    """
    Salva QR Code como imagem

    Args:
        image: Imagem PIL do QR Code
        filepath: Caminho para salvar (ex: qrcode.png)
    """
    image.save(filepath, "PNG")
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
                text="Olá! Esta é uma mensagem de teste! 🚚",
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
