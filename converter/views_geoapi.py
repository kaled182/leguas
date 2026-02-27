from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.conf import settings
import json
import asyncio
import logging
import traceback
from asgiref.sync import async_to_sync
from .geoapicheck import GeoAPIValidator
from . import api_settings

logger = logging.getLogger(__name__)
from asgiref.sync import sync_to_async, async_to_sync
from channels.db import database_sync_to_async

@login_required
@csrf_exempt
async def validate_addresses(request):
    """
    View para validar endereços usando a GeoAPI.pt
    """
    logger.info(f"Recebida requisição para validar endereços. Método: {request.method}")
    logger.info(f"Headers da requisição: {dict(request.headers)}")
    
    if request.method != 'POST':
        logger.error(f"Método não permitido: {request.method}")
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    try:
        # Verifica o Content-Type
        logger.info(f"Content-Type da requisição: {request.content_type}")
        if not request.content_type.startswith('application/json'):
            logger.error(f"Content-Type inválido: {request.content_type}")
            return JsonResponse({
                'error': 'Content-Type deve ser application/json'
            }, status=400)
            
        # Tenta fazer o parse do JSON
        try:
            request_body = request.body.decode('utf-8')
            logger.info(f"Body da requisição: {request_body}")
            data = json.loads(request_body)
            logger.info(f"Dados JSON parseados: {data}")
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao decodificar JSON: {str(e)}")
            logger.error(f"Body que causou o erro: {request_body}")
            return JsonResponse({
                'error': f'JSON inválido: {str(e)}',
                'details': {
                    'body': request_body[:200] + '...' if len(request_body) > 200 else request_body,
                    'error_position': e.pos,
                    'error_message': e.msg
                }
            }, status=400)
            
        addresses = data.get('addresses', [])
        logger.info(f"Endereços recebidos: {addresses}")
        
        if not addresses:
            logger.error("Nenhum endereço fornecido no payload")
            return JsonResponse({'error': 'Nenhum endereço fornecido'}, status=400)
        
        # Pega o token da API das configurações
        api_token = getattr(settings, 'GEOAPI_TOKEN', None)
        logger.info(f"Token da API está {'presente' if api_token else 'ausente'}")
        
        # Inicializa o validador
        try:
            validator = GeoAPIValidator(api_key=api_token)
            logger.info("Validador inicializado com sucesso")
        except Exception as e:
            logger.error(f"Erro ao inicializar validador: {str(e)}")
            return JsonResponse({
                'error': 'Erro ao inicializar serviço de validação',
                'details': str(e)
            }, status=500)
        
        try:
            logger.info("Iniciando validação de endereços")
            results = await validator.bulk_validate_addresses(addresses)
            logger.info(f"Validação concluída com sucesso para {len(results)} endereços")
        except Exception as e:
            logger.error(f"Erro na validação: {str(e)}", exc_info=True)
            return JsonResponse({
                'error': 'Erro na validação de endereços',
                'details': {
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'traceback': traceback.format_exc()
                }
            }, status=500)
        
        # Formata os resultados
        formatted_results = {}
        for address, result in results.items():
            formatted_results[address] = {
                'is_valid': result.is_valid,
                'confidence': result.confidence_score,
                'validated_address': result.validated_address,
                'coordinates': result.coordinates,
                'error': result.error_message,
                'matching_street': result.matching_street
            }
        
        return JsonResponse({
            'success': True,
            'results': formatted_results,
            'summary': {
                'total': len(addresses),
                'valid': sum(1 for r in results.values() if r.is_valid),
                'invalid': sum(1 for r in results.values() if not r.is_valid)
            }
        })
        
    except Exception as e:
        logger.error(f"Erro inesperado: {str(e)}")
        return JsonResponse({
            'error': f'Erro ao processar validação: {str(e)}'
        }, status=500)
