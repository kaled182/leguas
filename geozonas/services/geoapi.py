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


class GeoAPIClient:
    def __init__(self, api_key=None, timeout=20):
        self.api_key = api_key or getattr(settings, "GEOAPI_TOKEN", None)
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

            if resp.status_code == 200:
                try:
                    return resp.json()
                except ValueError as exc:
                    raise GeoAPIError(f"Resposta não-JSON em {path}") from exc
            if resp.status_code == 404:
                return None
            if resp.status_code == 429:
                espera = 10 * (2 ** tentativa)
                if tentativa < max_retries - 1:
                    time.sleep(espera)
                    continue
                raise GeoAPIError(f"429 persistente em {path}")
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
