import re
import json
import aiohttp
import asyncio
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from unidecode import unidecode

@dataclass
class GeoValidationResult:
    is_valid: bool
    confidence_score: float
    validated_address: Optional[str] = None
    coordinates: Optional[Tuple[float, float]] = None
    error_message: Optional[str] = None
    matching_street: Optional[str] = None

class GeoAPIValidator:
    """
    Validador de endereços usando a API de Códigos Postais de Portugal
    e serviços de geocodificação.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://json.geoapi.pt"
        self.cache = {}  # Cache para resultados de validação
        
    def _get_request_params(self, extra_params: Dict = None) -> Tuple[Dict, Dict]:
        """
        Prepara os parâmetros e headers para as requisições.
        """
        headers = {}
        params = {}
        
        if self.api_key:
            # Adiciona a API key no header
            headers['X-API-Key'] = self.api_key
            
        if extra_params:
            params.update(extra_params)
            
        return params, headers
        
    def _extract_postal_code(self, address: str) -> Optional[str]:
        """Extrai o código postal de um endereço."""
        # Procura por padrão XXXX-XXX
        match = re.search(r'\b(\d{4}-\d{3})\b', address)
        if match:
            return match.group(1)
        
        # Procura por padrão XXXX (CP4)
        match = re.search(r'\b(\d{4})\b', address)
        if match:
            return match.group(1)
        
        return None
    
    def _normalize_street_name(self, street: str) -> str:
        """
        Normaliza o nome da rua para comparação:
        - Remove acentos
        - Converte para minúsculas
        - Remove espaços extras
        - Padroniza abreviações comuns
        """
        street = unidecode(street.lower().strip())
        
        # Padroniza abreviações comuns
        replacements = {
            'r.': 'rua',
            'av.': 'avenida',
            'pc.': 'praca',
            'pç.': 'praca',
            'lg.': 'largo',
            'tv.': 'travessa'
        }
        
        for old, new in replacements.items():
            street = street.replace(old, new)
        
        # Remove palavras muito comuns para melhorar a comparação
        words_to_remove = ['de', 'da', 'do', 'das', 'dos']
        words = street.split()
        words = [w for w in words if w not in words_to_remove]
        
        return ' '.join(words)
    
    def _extract_street_name(self, address: str) -> Optional[str]:
        """Extrai o nome da rua do endereço completo."""
        # Remove o código postal e qualquer texto após ele
        postal_code_match = re.search(r'\d{4}-\d{3}', address)
        if postal_code_match:
            address = address[:postal_code_match.start()].strip()
        
        # Procura por padrões comuns de início de rua
        patterns = [
            (r'^(rua|r\.|avenida|av\.|travessa|tv\.|largo|lg\.|praça|pc\.|pç\.|alameda)\s+(.+?)(?:\s+\d+)?$', 2),
            (r'^(.+?)(?:\s+\d+)?$', 1)  # Fallback: pega todo o texto até um número
        ]
        
        for pattern, group in patterns:
            match = re.search(pattern, address, re.IGNORECASE)
            if match:
                return match.group(group).strip()
        
        return None
    
    def _compare_street_names(self, street1: str, street2: str) -> float:
        """
        Compara dois nomes de rua e retorna um score de similaridade (0-1).
        Usa técnicas de fuzzy matching para lidar com variações.
        """
        from difflib import SequenceMatcher
        
        # Normaliza ambas as ruas
        street1_norm = self._normalize_street_name(street1)
        street2_norm = self._normalize_street_name(street2)
        
        # Calcula similaridade
        ratio = SequenceMatcher(None, street1_norm, street2_norm).ratio()
        
        # Ajusta o score baseado em características específicas
        if street1_norm in street2_norm or street2_norm in street1_norm:
            ratio = max(ratio, 0.8)  # Aumenta o score se uma é substring da outra
            
        return ratio
    
    async def validate_address(self, address: str) -> GeoValidationResult:
        """
        Valida um endereço usando a API de Códigos Postais e geocodificação.
        Retorna um objeto GeoValidationResult com o resultado da validação.
        """
        # Verifica cache primeiro
        if address in self.cache:
            return self.cache[address]
            
        try:
            # Extrai código postal e nome da rua
            postal_code = self._extract_postal_code(address)
            street_name = self._extract_street_name(address)
            
            if not postal_code:
                return GeoValidationResult(
                    is_valid=False,
                    confidence_score=0.0,
                    error_message="Código postal não encontrado no endereço"
                )
            
            # Consulta a API de Códigos Postais
            try:
                # Prepara os parâmetros da requisição
                params, headers = self._get_request_params()
                
                async with aiohttp.ClientSession() as session:
                    # Primeiro tenta o CP7 completo
                    async with session.get(
                        f"{self.base_url}/cp/{postal_code}",
                        params=params,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        
                        if response.status == 404 and '-' in postal_code:
                            # Se não encontrar com CP7, tenta com CP4
                            cp4 = postal_code.split('-')[0]
                            async with session.get(
                                f"{self.base_url}/cp/{cp4}",
                                params=params,
                                headers=headers,
                                timeout=aiohttp.ClientTimeout(total=10)
                            ) as response:
                                if response.status == 404:
                                    return GeoValidationResult(
                                        is_valid=False,
                                        confidence_score=0.0,
                                        error_message=f"Código postal {postal_code} não encontrado na base de dados"
                                    )
                                
                                if response.status != 200:
                                    return GeoValidationResult(
                                        is_valid=False,
                                        confidence_score=0.0,
                                        error_message=f"Erro na API: {response.status}"
                                    )
                                data = await response.json()
                        else:
                            if response.status == 404:
                                return GeoValidationResult(
                                    is_valid=False,
                                    confidence_score=0.0,
                                    error_message=f"Código postal {postal_code} não encontrado na base de dados"
                                )
                            
                            if response.status != 200:
                                return GeoValidationResult(
                                    is_valid=False,
                                    confidence_score=0.0,
                                    error_message=f"Erro na API: {response.status}"
                                )
                            data = await response.json()
                    
            except aiohttp.ClientConnectionError:
                return GeoValidationResult(
                    is_valid=False,
                    confidence_score=0.0,
                    error_message=f"Erro de conexão com a API: verifique sua conexão com a internet"
                )
            except asyncio.TimeoutError:
                return GeoValidationResult(
                    is_valid=False,
                    confidence_score=0.0,
                    error_message="Tempo limite excedido ao contactar a API"
                )
            except Exception as e:
                return GeoValidationResult(
                    is_valid=False,
                    confidence_score=0.0,
                    error_message=f"Erro ao contactar a API: {str(e)}"
                )
            
            # Verifica se há ruas disponíveis
            if "ruas" not in data or not data["ruas"]:
                # Se não há ruas, valida apenas o código postal
                return GeoValidationResult(
                    is_valid=True,
                    confidence_score=0.5,  # Score médio pois só validamos o CP
                    validated_address=address,
                    coordinates=tuple(data.get("centro", [0, 0])),
                    matching_street=None
                )
            
            # Procura a melhor correspondência entre as ruas
            best_match = None
            best_score = 0
            
            for rua in data["ruas"]:
                score = self._compare_street_names(street_name, rua)
                if score > best_score:
                    best_score = score
                    best_match = rua
            
            # Define thresholds para validação
            if best_score >= 0.8:  # Match muito bom
                confidence = best_score
                is_valid = True
            elif best_score >= 0.6:  # Match razoável
                confidence = best_score * 0.8
                is_valid = True
            else:
                confidence = best_score * 0.5
                is_valid = False
            
            # Tenta geocodificar o endereço
            geo_info = await self.geocode_address(address)
            
            result = GeoValidationResult(
                is_valid=is_valid,
                confidence_score=confidence,
                validated_address=geo_info.get("formatted_address", address) if geo_info else address,
                coordinates=tuple(geo_info.get("coordinates", data.get("centro", [0, 0]))) if geo_info else tuple(data.get("centro", [0, 0])),
                matching_street=best_match if is_valid else None
            )
            
            # Salva no cache
            self.cache[address] = result
            
            return result
            
        except Exception as e:
            return GeoValidationResult(
                is_valid=False,
                confidence_score=0.0,
                error_message=f"Erro na validação: {str(e)}"
            )
    
    async def bulk_validate_addresses(self, addresses: List[str]) -> Dict[str, GeoValidationResult]:
        """
        Valida múltiplos endereços em lote.
        Retorna um dicionário com os resultados para cada endereço.
        """
        results = {}
        for address in addresses:
            results[address] = await self.validate_address(address)
        return results
    
    async def geocode_address(self, address: str) -> Optional[Dict]:
        """
        Geocodifica um endereço usando o serviço de geocoding do GeoAPI.pt.
        """
        try:
            # Prepara os parâmetros da requisição
            params, headers = self._get_request_params({"q": address})
            
            async with aiohttp.ClientSession() as session:
                # Primeiro tenta uma pesquisa direta
                async with session.get(
                    f"{self.base_url}/geocode",
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and "features" in data and len(data["features"]) > 0:
                            feature = data["features"][0]
                            return {
                                "coordinates": feature["geometry"]["coordinates"],
                                "confidence": feature.get("properties", {}).get("confidence", 0.5),
                                "formatted_address": feature.get("properties", {}).get("formatted", address),
                                "details": feature.get("properties", {})
                            }
                
                # Se não encontrar, tenta com o código postal
                postal_code = self._extract_postal_code(address)
                if postal_code:
                    async with session.get(
                        f"{self.base_url}/cp/{postal_code}",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            if "centro" in data:
                                return {
                                    "coordinates": data["centro"],
                                    "confidence": 0.5,  # Confiança média pois é baseado apenas no CP
                                    "formatted_address": address,
                                    "details": {
                                        "postal_code": postal_code,
                                        "locality": data.get("Localidade"),
                                        "district": data.get("Distrito"),
                                        "county": data.get("Concelho")
                                    }
                                }
            
            return None
            
        except Exception as e:
            print(f"Erro na geocodificação: {str(e)}")
            return None
            
    def get_geocoding_info(self, validated_result: GeoValidationResult) -> Dict:
        """
        Retorna informações de geocodificação para um endereço validado.
        """
        if not validated_result.is_valid:
            return {}
            
        return {
            "coordinates": validated_result.coordinates,
            "validated_address": validated_result.validated_address,
            "confidence": validated_result.confidence_score,
            "matching_street": validated_result.matching_street
        }
