"""
Serviço de geocodificação de endereços
"""
import re
import time
import logging
from typing import Optional, Tuple
import requests
from django.core.cache import cache

logger = logging.getLogger(__name__)


class AddressNormalizer:
    """Normaliza e limpa endereços para geocodificação"""
    
    # Padrões para remover
    REMOVE_PATTERNS = [
        r'\b[Rr]/[Cc]\b',  # R/C (rés-do-chão)
        r'\b[Dd]/[TtEe]\b',  # D/T, D/E (direito/trás, direito/esquerdo)
        r'\b[Tt]/[TtEe]\b',  # T/T, T/E
        r'\bfra[cç][aã]o\s+[A-Z0-9]+\b',  # fração A, fracão B
        r'\blote\s+\d+[/\-]?\d*\b',  # lote 317/318
        r'\bhab\.?\s*\d+\b',  # hab 106, hab. 106
        r'\bbloco\s+[A-Z0-9]+\b',  # bloco A4A
        r'\bapartamento\s+\d+\b',  # apartamento 3
        r'\bapto\.?\s*\d+\b',  # apto 3, apto. 3
        r'\bandar\s+\d+\b',  # andar 2
        r'\bº\s*andar\b',  # 2º andar
        r'\b\d+º\b',  # 1º, 2º
        r'\bporta\s+\d+\b',  # porta 3
        r'\besq\.?\b',  # esq, esq.
        r'\bdir\.?\b',  # dir, dir.
        r'\bfrente\b',
        r'\bfundo\b',
        r'\btraseiras\b',
    ]
    
    # Padrão para encontrar números de porta duplicados
    DUPLICATE_NUMBER_PATTERN = r'\b([Nn]\.?\s*[-]?\s*)?(\d+)\s*([Nn]\.?\s*[-]?\s*\d+\s*)*'
    
    @classmethod
    def normalize(cls, address: str, postal_code: str, locality: str) -> str:
        """
        Normaliza um endereço removendo informações irrelevantes
        
        Args:
            address: Endereço original
            postal_code: Código postal (XXXX-XXX)
            locality: Localidade
            
        Returns:
            Endereço normalizado
        """
        if not address:
            return f"{postal_code} {locality}"
        
        # Converter para minúsculas para processamento
        normalized = address.strip()
        
        # Remover padrões irrelevantes
        for pattern in cls.REMOVE_PATTERNS:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        # Limpar números duplicados (N 821 N-821 N-821 → 821)
        def clean_number(match):
            # Pegar apenas o primeiro número válido
            numbers = re.findall(r'\d+', match.group(0))
            if numbers:
                return numbers[0]
            return match.group(0)
        
        normalized = re.sub(
            r'[Nn]\.?\s*[-]?\s*\d+(?:\s+[Nn]\.?\s*[-]?\s*\d+)+',
            clean_number,
            normalized
        )
        
        # Limpar "N" antes de números (N 10 → 10)
        normalized = re.sub(r'\b[Nn]\.?\s+(\d+)\b', r'\1', normalized)
        
        # Limpar vírgulas e pontos duplicados
        normalized = re.sub(r'[,\s]+,', ',', normalized)
        normalized = re.sub(r'\.+', '.', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)  # Múltiplos espaços
        
        # Remover ponto final se houver
        normalized = normalized.rstrip('.')
        
        # Limpar espaços extras
        normalized = normalized.strip()
        
        # Formato final: "Rua Nome número, XXXX-XXX Localidade"
        # Adicionar vírgula antes do código postal se não houver
        if postal_code and postal_code not in normalized:
            normalized = f"{normalized}, {postal_code} {locality}"
        elif locality and locality.lower() not in normalized.lower():
            normalized = f"{normalized} {locality}"
            
        return normalized
    
    @classmethod
    def extract_street_number(cls, address: str) -> Optional[str]:
        """Extrai o número da porta/rua do endereço"""
        # Procurar padrões como "n 123", "nº 123", "123"
        match = re.search(r'\b[Nn]\.?º?\s*(\d+)\b|\b(\d+)\b', address)
        if match:
            return match.group(1) or match.group(2)
        return None


class GeocodingService:
    """Serviço de geocodificação usando Nominatim (OpenStreetMap)"""
    
    NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
    CACHE_TIMEOUT = 86400 * 30  # 30 dias
    RATE_LIMIT_DELAY = 1.0  # 1 segundo entre requests (política do Nominatim)
    
    _last_request_time = 0
    
    @classmethod
    def _rate_limit(cls):
        """Implementa rate limiting"""
        current_time = time.time()
        elapsed = current_time - cls._last_request_time
        if elapsed < cls.RATE_LIMIT_DELAY:
            time.sleep(cls.RATE_LIMIT_DELAY - elapsed)
        cls._last_request_time = time.time()
    
    @classmethod
    def geocode(
        cls,
        address: str,
        postal_code: str,
        locality: str,
        country: str = "Portugal"
    ) -> Optional[Tuple[float, float]]:
        """
        Geocodifica um endereço
        
        Args:
            address: Endereço da rua
            postal_code: Código postal
            locality: Localidade/Cidade
            country: País (padrão: Portugal)
            
        Returns:
            Tupla (latitude, longitude) ou None
        """
        # Normalizar endereço
        normalized_address = AddressNormalizer.normalize(address, postal_code, locality)
        
        # Verificar cache
        cache_key = f"geocode:{normalized_address}"
        cached = cache.get(cache_key)
        if cached:
            logger.info(f"Cache hit para: {normalized_address}")
            return cached
        
        # Tentar geocodificação com endereço completo
        coords = cls._geocode_nominatim(normalized_address, country)
        
        if not coords:
            # Fallback 1: Rua + código postal + localidade (sem número)
            street_only = re.sub(r'\b\d+\b', '', address).strip()
            fallback_address = f"{street_only}, {postal_code} {locality}, {country}"
            coords = cls._geocode_nominatim(fallback_address, country)
        
        if not coords:
            # Fallback 2: Apenas código postal + localidade
            fallback_address = f"{postal_code} {locality}, {country}"
            coords = cls._geocode_nominatim(fallback_address, country)
        
        # Cachear resultado (mesmo que seja None para evitar requests repetidos)
        if coords:
            cache.set(cache_key, coords, cls.CACHE_TIMEOUT)
            logger.info(f"Geocodificado com sucesso: {normalized_address} → {coords}")
        else:
            # Cachear por menos tempo se falhar
            cache.set(cache_key, None, 3600)  # 1 hora
            logger.warning(f"Falha na geocodificação: {normalized_address}")
        
        return coords
    
    @classmethod
    def _geocode_nominatim(cls, query: str, country: str = "Portugal") -> Optional[Tuple[float, float]]:
        """
        Faz request ao Nominatim
        
        Args:
            query: String de busca
            country: País para filtrar resultados
            
        Returns:
            Tupla (latitude, longitude) ou None
        """
        try:
            # Rate limiting
            cls._rate_limit()
            
            params = {
                'q': query,
                'format': 'json',
                'limit': 1,
                'countrycodes': 'pt',  # Apenas Portugal
                'addressdetails': 1
            }
            
            headers = {
                'User-Agent': 'Leguas Delivery Management System/1.0'
            }
            
            response = requests.get(
                cls.NOMINATIM_URL,
                params=params,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                results = response.json()
                if results and len(results) > 0:
                    result = results[0]
                    lat = float(result['lat'])
                    lon = float(result['lon'])
                    return (lat, lon)
            else:
                logger.error(f"Nominatim error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Erro ao geocodificar '{query}': {e}")
        
        return None
    
    @classmethod
    def batch_geocode(cls, addresses: list) -> dict:
        """
        Geocodifica múltiplos endereços
        
        Args:
            addresses: Lista de dicts com 'address', 'postal_code', 'locality'
            
        Returns:
            Dict com resultados {index: (lat, lon)}
        """
        results = {}
        
        for idx, addr_data in enumerate(addresses):
            coords = cls.geocode(
                addr_data.get('address', ''),
                addr_data.get('postal_code', ''),
                addr_data.get('locality', '')
            )
            if coords:
                results[idx] = coords
            
            # Delay entre requests
            if idx < len(addresses) - 1:
                time.sleep(cls.RATE_LIMIT_DELAY)
        
        return results
