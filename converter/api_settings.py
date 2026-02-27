"""
Configurações da API GeoAPI.pt
"""

# URL base da API
GEOAPI_BASE_URL = "https://json.geoapi.pt"

# Token da API - deve ser configurado no .env ou settings.py
GEOAPI_TOKEN = "797c45c0-2846-4add-9b33-7299fc7f6c91"  # Será sobrescrito pelo settings.py

# Configurações de timeout
GEOAPI_TIMEOUT = 10  # segundos

# Configurações de cache
GEOAPI_CACHE_TIMEOUT = 60 * 60 * 24  # 24 horas em segundos
