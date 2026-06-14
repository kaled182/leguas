"""
Cliente síncrono da GeoAPI.pt para o módulo GeoZonas.

A grande melhoria face ao script original: usar o endpoint /cp/{CP4}, que devolve
TODOS os CP3 de um prefixo numa só chamada (em vez de varrer 1000 códigos um a um).

Autenticação: header `X-API-Key` (chave em settings.GEOAPI_TOKEN, lida do .env).
Docs: https://geoapi.pt/docs/ — limite premium: 10.000 pedidos/dia.
"""

import time

import requests
from django.conf import settings

BASE_URL = "https://json.geoapi.pt"


class GeoAPIError(Exception):
    """Erro ao comunicar com a GeoAPI."""


class GeoAPIRateLimitError(GeoAPIError):
    """Limite de pedidos da GeoAPI atingido (HTTP 429)."""


def resolver_api_key():
    """Resolve a chave da GeoAPI: 1) SystemConfiguration (editável na UI,
    encriptada) → 2) settings.GEOAPI_TOKEN (.env)."""
    try:
        from system_config.models import SystemConfiguration
        tok = (SystemConfiguration.get_config().geoapi_token or "").strip()
        if tok:
            return tok
    except Exception:
        pass
    return getattr(settings, "GEOAPI_TOKEN", None)


class GeoAPIClient:
    def __init__(self, api_key=None, timeout=20):
        self.api_key = api_key or resolver_api_key()
        self.timeout = timeout
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"X-API-Key": self.api_key})

    def _get(self, path, params=None, max_retries=5):
        """GET com backoff exponencial em HTTP 429."""
        url = f"{BASE_URL}/{path.lstrip('/')}"
        params = dict(params or {})
        params.setdefault("json", "1")

        for tentativa in range(max_retries):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                raise GeoAPIError(f"Falha de rede em {path}: {exc}") from exc

            # A GeoAPI devolve a quota em cabeçalhos RateLimit-* em (quase)
            # todas as respostas — guardamos sempre que vierem (custo zero).
            _capturar_quota(resp.headers)

            if resp.status_code == 200:
                try:
                    return resp.json()
                except ValueError as exc:
                    raise GeoAPIError(f"Resposta não-JSON em {path}") from exc
            if resp.status_code == 404:
                return None
            if resp.status_code == 429:
                # Uma tentativa curta para um pico transitório; se persistir,
                # falha rápido com mensagem clara (provável limite da chave).
                if tentativa < 1:
                    time.sleep(3)
                    continue
                raise GeoAPIRateLimitError(
                    "Limite da GeoAPI atingido (HTTP 429). O uso da chave pode "
                    "ter excedido o limite diário/horário — tenta novamente "
                    "mais tarde."
                )
            raise GeoAPIError(f"HTTP {resp.status_code} em {path}")

        return None

    def consultar_cp4(self, cp4):
        """Devolve todos os dados de um prefixo CP4 (ex.: '4990') numa só chamada."""
        cp4 = str(cp4).strip()
        return self._get(f"cp/{cp4}")

    def consultar_cp(self, cp):
        """Detalhe de um CP completo 'CP4-CP3' (ex.: '4990-530'): centroide, polígono."""
        cp = str(cp).strip()
        return self._get(f"cp/{cp}")

    def gps_reverso(self, lat, lon):
        """Geocodificação reversa: a partir de lat/lon devolve distrito/concelho/freguesia."""
        return self._get(f"gps/{lat},{lon}/base")

    def atualizar_quota(self):
        """Faz 1 chamada leve para refrescar a quota guardada. Devolve o dict."""
        try:
            # Detalhe pequeno (vs. bulk de 2MB) — 1 pedido, devolve RateLimit-*.
            self.consultar_cp("4990-008")
        except GeoAPIError:
            pass
        return get_quota()


_QUOTA_CACHE_KEY = "geozonas:geoapi_quota"


def _capturar_quota(headers):
    """Guarda os cabeçalhos RateLimit-* da GeoAPI na cache (Redis partilhado)."""
    try:
        remaining = headers.get("RateLimit-Remaining")
        if remaining is None:
            return
        from datetime import timedelta

        from django.core.cache import cache
        from django.utils import timezone

        def _int(v):
            v = str(v).strip()
            return int(v) if v.lstrip("-").isdigit() else None

        now = timezone.now()
        reset_secs = _int(headers.get("RateLimit-Reset"))
        data = {
            "limit": _int(headers.get("RateLimit-Limit")),
            "remaining": _int(remaining),
            "reset_at": (
                (now + timedelta(seconds=reset_secs)).isoformat()
                if reset_secs is not None else None
            ),
            "captured_at": now.isoformat(),
        }
        cache.set(_QUOTA_CACHE_KEY, data, timeout=60 * 60 * 26)
    except Exception:
        # Nunca deixar a captura de quota afetar a chamada principal.
        pass


def get_quota():
    """Devolve o último estado de quota guardado (ou None)."""
    try:
        from django.core.cache import cache
        return cache.get(_QUOTA_CACHE_KEY)
    except Exception:
        return None
