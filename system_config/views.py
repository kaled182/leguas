import json
import logging
import secrets

import requests
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.views.decorators.csrf import ensure_csrf_cookie

from .models import SystemConfiguration, ConfigurationAudit
from .whatsapp_helper import WhatsAppWPPConnectAPI, format_phone_number
from .token_utils import propagate_whatsapp_token


logger = logging.getLogger(__name__)


@login_required
def system_config_view(request):
    """View para exibir e editar configurações do sistema"""
    config = SystemConfiguration.get_config()
    
    context = {
        'config': config,
    }
    
    return render(request, 'system_config/config.html', context)


@login_required
@require_http_methods(["POST"])
def save_config(request):
    """View para salvar configurações do sistema"""
    config = SystemConfiguration.get_config()
    
    # Todos os campos de texto/número do formulário
    field_mappings = {
        # Empresa
        'company_name': 'company_name',
        
        # Mapas - Básicos
        'map_provider': 'map_provider',
        'map_default_lat': 'map_default_lat',
        'map_default_lng': 'map_default_lng',
        'map_default_zoom': 'map_default_zoom',
        'map_type': 'map_type',
        'map_language': 'map_language',
        'map_theme': 'map_theme',
        'map_styles': 'map_styles',
        
        # Mapas - APIs
        'google_maps_api_key': 'google_maps_api_key',
        'mapbox_access_token': 'mapbox_access_token',
        'mapbox_style': 'mapbox_style',
        'mapbox_custom_style': 'mapbox_custom_style',
        'esri_api_key': 'esri_api_key',
        'esri_basemap': 'esri_basemap',
        'osm_tile_server': 'osm_tile_server',
        
        # Google Drive
        'gdrive_auth_mode': 'gdrive_auth_mode',
        'gdrive_credentials_json': 'gdrive_credentials_json',
        'gdrive_folder_id': 'gdrive_folder_id',
        'gdrive_shared_drive_id': 'gdrive_shared_drive_id',
        'gdrive_oauth_client_id': 'gdrive_oauth_client_id',
        'gdrive_oauth_client_secret': 'gdrive_oauth_client_secret',
        'gdrive_oauth_refresh_token': 'gdrive_oauth_refresh_token',
        'gdrive_oauth_user_email': 'gdrive_oauth_user_email',
        
        # FTP
        'ftp_host': 'ftp_host',
        'ftp_port': 'ftp_port',
        'ftp_user': 'ftp_user',
        'ftp_password': 'ftp_password',
        'ftp_directory': 'ftp_directory',
        
        # SMTP
        'smtp_host': 'smtp_host',
        'smtp_port': 'smtp_port',
        'smtp_security': 'smtp_security',
        'smtp_user': 'smtp_user',
        'smtp_password': 'smtp_password',
        'smtp_auth_mode': 'smtp_auth_mode',
        'smtp_oauth_client_id': 'smtp_oauth_client_id',
        'smtp_oauth_client_secret': 'smtp_oauth_client_secret',
        'smtp_oauth_refresh_token': 'smtp_oauth_refresh_token',
        'smtp_from_name': 'smtp_from_name',
        'smtp_from_email': 'smtp_from_email',
        'smtp_test_recipient': 'smtp_test_recipient',
        
        # WhatsApp
        'whatsapp_evolution_api_url': 'whatsapp_evolution_api_url',
        'whatsapp_evolution_api_key': 'whatsapp_evolution_api_key',
        'whatsapp_instance_name': 'whatsapp_instance_name',
        
        # Typebot
        'typebot_builder_url': 'typebot_builder_url',
        'typebot_viewer_url': 'typebot_viewer_url',
        'typebot_api_key': 'typebot_api_key',
        'typebot_admin_email': 'typebot_admin_email',
        'typebot_admin_password': 'typebot_admin_password',
        'typebot_encryption_secret': 'typebot_encryption_secret',
        'typebot_database_url': 'typebot_database_url',
        'typebot_s3_endpoint': 'typebot_s3_endpoint',
        'typebot_s3_bucket': 'typebot_s3_bucket',
        'typebot_s3_access_key': 'typebot_s3_access_key',
        'typebot_s3_secret_key': 'typebot_s3_secret_key',
        'typebot_smtp_host': 'typebot_smtp_host',
        'typebot_smtp_port': 'typebot_smtp_port',
        'typebot_smtp_username': 'typebot_smtp_username',
        'typebot_smtp_password': 'typebot_smtp_password',
        'typebot_smtp_from': 'typebot_smtp_from',
        'typebot_google_client_id': 'typebot_google_client_id',
        'typebot_google_client_secret': 'typebot_google_client_secret',
        'typebot_default_workspace_plan': 'typebot_default_workspace_plan',
        
        # SMS
        'sms_provider': 'sms_provider',
        'sms_provider_rank': 'sms_provider_rank',
        'sms_account_sid': 'sms_account_sid',
        'sms_auth_token': 'sms_auth_token',
        'sms_api_key': 'sms_api_key',
        'sms_api_url': 'sms_api_url',
        'sms_from_number': 'sms_from_number',
        'sms_test_recipient': 'sms_test_recipient',
        'sms_test_message': 'sms_test_message',
        'sms_priority': 'sms_priority',
        'sms_aws_region': 'sms_aws_region',
        'sms_aws_access_key_id': 'sms_aws_access_key_id',
        'sms_aws_secret_access_key': 'sms_aws_secret_access_key',
        'sms_infobip_base_url': 'sms_infobip_base_url',
        
        # Database
        'db_host': 'db_host',
        'db_port': 'db_port',
        'db_name': 'db_name',
        'db_user': 'db_user',
        'db_password': 'db_password',
        
        # Redis
        'redis_url': 'redis_url',
        
        # Cron Jobs - Analytics
        'cron_metrics_schedule': 'cron_metrics_schedule',
        'cron_metrics_backfill_days': 'cron_metrics_backfill_days',
        'cron_metrics_last_status': 'cron_metrics_last_status',
        'cron_forecasts_schedule': 'cron_forecasts_schedule',
        'cron_forecasts_days_ahead': 'cron_forecasts_days_ahead',
        'cron_forecasts_method': 'cron_forecasts_method',
        'cron_forecasts_last_status': 'cron_forecasts_last_status',
        'cron_alerts_schedule': 'cron_alerts_schedule',
        'cron_alerts_check_days': 'cron_alerts_check_days',
        'cron_alerts_last_status': 'cron_alerts_last_status',
    }
    
    # Atualizar todos os campos de texto
    for form_field, model_field in field_mappings.items():
        if form_field in request.POST:
            value = request.POST[form_field].strip()
            if hasattr(config, model_field):
                # Se o valor está vazio, só setar None se o campo aceitar NULL
                if value:
                    setattr(config, model_field, value)
                else:
                    # Verifica se o campo aceita NULL no modelo
                    field = config._meta.get_field(model_field)
                    if field.null or field.blank:
                        setattr(config, model_field, None)
                    # Se não aceita NULL, não alterar (manter valor padrão)
    
    # Atualizar checkboxes (campos booleanos)
    boolean_fields = {
        'gdrive_enabled': 'gdrive_enabled',
        'ftp_enabled': 'ftp_enabled',
        'smtp_enabled': 'smtp_enabled',
        'smtp_use_tls': 'smtp_use_tls',
        'sms_enabled': 'sms_enabled',
        'typebot_enabled': 'typebot_enabled',
        'typebot_disable_signup': 'typebot_disable_signup',
        'enable_street_view': 'enable_street_view',
        'enable_traffic': 'enable_traffic',
        'enable_map_clustering': 'enable_map_clustering',
        'enable_drawing_tools': 'enable_drawing_tools',
        'enable_fullscreen': 'enable_fullscreen',
        'mapbox_enable_3d': 'mapbox_enable_3d',
        # Cron Jobs
        'cron_metrics_enabled': 'cron_metrics_enabled',
        'cron_forecasts_enabled': 'cron_forecasts_enabled',
        'cron_forecasts_best_only': 'cron_forecasts_best_only',
        'cron_alerts_enabled': 'cron_alerts_enabled',
        'cron_alerts_send_notifications': 'cron_alerts_send_notifications',
    }
    
    for form_field, model_field in boolean_fields.items():
        if hasattr(config, model_field):
            setattr(config, model_field, form_field in request.POST)
    
    # Atualizar logo se fornecido
    if 'logo' in request.FILES:
        config.logo = request.FILES['logo']
    
    # Marcar como configurado
    config.configured = True
    config.save()
    
    # Registrar auditoria
    ConfigurationAudit.objects.create(
        user=request.user,
        action='BULK_UPDATE',
        field_name='all_fields',
        old_value='',
        new_value=f'{len(field_mappings) + len(boolean_fields)} campos atualizados',
        ip_address=request.META.get('REMOTE_ADDR', '')
    )
    
    messages.success(request, 'Configurações guardadas com sucesso!')
    return redirect('system_config:index')


def _load_whatsapp_api():
    """Instancia o cliente WPPConnect ou retorna erro detalhado."""
    try:
        api = WhatsAppWPPConnectAPI.from_config()
        return api, None
    except Exception as exc:  # pragma: no cover - apenas para feedback em runtime
        logger.warning("Falha ao carregar cliente WPPConnect: %s", exc)
        return None, str(exc)


@ensure_csrf_cookie
@login_required
def whatsapp_dashboard(request):
    """Painel de controle do WhatsApp via WPPConnect."""
    config = SystemConfiguration.get_config()
    api, error = _load_whatsapp_api()
    session_info = {}

    if api is not None:
        try:
            session_info = api.get_session_info()
        except Exception as exc:  # pragma: no cover - depende do servidor externo
            logger.warning("Não foi possível obter informações da sessão do WhatsApp: %s", exc)
            error = error or str(exc)
            session_info = {"connected": False, "status": "error", "error": str(exc)}

    if request.method == "POST" and request.headers.get("x-requested-with") == "XMLHttpRequest":
        action = (request.POST.get("action") or "").strip()
        if action == "toggle":
            enable = request.POST.get("enable") == "true"
            config.whatsapp_enabled = enable
            config.save(update_fields=["whatsapp_enabled", "updated_at"])
            return JsonResponse({"success": True, "enabled": config.whatsapp_enabled})

    session_name = getattr(config, "whatsapp_instance_name", "") or ""
    stored_token = config.whatsapp_evolution_api_key or ""
    
    context = {
        "config": config,
        "whatsapp_error": error,
        "session_info": session_info,
        "session_name": session_name.strip(),
        "is_enabled": bool(config.whatsapp_enabled),
        "is_connected": session_info.get("connected", False),
        "connection_status": session_info.get("status", "unknown"),
        "phone_number": session_info.get("phone", ""),
        "device_info": session_info.get("device", {}),
        "battery_info": session_info.get("battery", {}),
        "token_value": stored_token,
        "has_api_key": bool(stored_token),
    }
    return render(request, "system_config/whatsapp_dashboard.html", context)


def _whatsapp_response(callback):
    api, error = _load_whatsapp_api()
    if api is None:
        logger.warning("[WhatsApp] API não configurada: %s", error)
        return JsonResponse({"success": False, "message": error or "Configuração do WhatsApp incompleta."}, status=400)

    try:
        return callback(api)
    except requests.HTTPError as exc:  # pragma: no cover - integrações externas
        status_code = exc.response.status_code if exc.response is not None else 500
        error_msg = f"Erro HTTP {status_code} na API WPPConnect"
        try:
            error_detail = exc.response.json() if exc.response is not None else {}
            error_msg += f": {error_detail}"
        except Exception:
            error_msg += f": {exc.response.text if exc.response is not None else str(exc)}"
        
        logger.warning("[WhatsApp] %s", error_msg)
        return JsonResponse({"success": False, "message": error_msg, "status_code": status_code}, status=status_code)
    except Exception as exc:  # pragma: no cover - outros erros
        logger.exception("[WhatsApp] Erro inesperado na operação WPPConnect")
        return JsonResponse({"success": False, "message": str(exc)}, status=500)


@login_required
@require_POST
def whatsapp_start_session(request):
    """Inicia a sessão e retorna QR code quando disponível."""

    def _start(api: WhatsAppWPPConnectAPI):
        # wait_connection=False para evitar timeout, mas com webhook para receber notificação
        # O polling do frontend detectará quando conectar
        payload = api.create_instance(wait_qrcode=True, wait_connection=False, webhook="")
        qrcode = payload.get("qrcode") or payload.get("base64") or payload.get("qrCode")
        pairing = payload.get("pairingCode") or payload.get("code")
        state = {}
        try:
            state = api.get_connection_state()
        except Exception:  # pragma: no cover - consulta opcional
            state = {}
        return JsonResponse({
            "success": True,
            "qrcode": qrcode,
            "pairingCode": pairing,
            "raw": payload,
            "status": state,
        })

    return _whatsapp_response(_start)


@login_required
@require_POST
def whatsapp_logout(request):

    def _logout(api: WhatsAppWPPConnectAPI):
        response = api.logout()
        return JsonResponse({"success": True, "response": response})

    return _whatsapp_response(_logout)


@login_required
@require_GET
def whatsapp_status(request):

    def _status(api: WhatsAppWPPConnectAPI):
        session_info = api.get_session_info()
        return JsonResponse({"success": True, "session": session_info})

    return _whatsapp_response(_status)


@login_required
@require_GET
def whatsapp_qrcode(request):

    def _qrcode(api: WhatsAppWPPConnectAPI):
        payload = api.get_qrcode()
        qrcode = payload.get("qrcode") or payload.get("base64") or payload.get("qrCode")
        pairing = payload.get("pairingCode") or payload.get("code")
        return JsonResponse({
            "success": True,
            "qrcode": qrcode,
            "pairingCode": pairing,
            "raw": payload,
        })

    return _whatsapp_response(_qrcode)


@login_required
@require_POST
def whatsapp_send_test(request):

    def _send(api: WhatsAppWPPConnectAPI):
        data = {}
        if request.body:
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                data = {}

        phone = (data.get("phone") or data.get("recipient") or "").strip()
        message = (data.get("message") or "Teste WhatsApp WPPConnect").strip()
        if not phone:
            return JsonResponse({"success": False, "message": "Informe o número do destinatário."}, status=400)

        formatted = format_phone_number(phone)
        response = api.send_text(formatted, message)
        return JsonResponse({
            "success": True,
            "recipient": formatted,
            "message": message,
            "response": response,
        })

    return _whatsapp_response(_send)


@login_required
@require_POST
def whatsapp_update_config(request):
    config = SystemConfiguration.get_config()

    data = {}
    if request.body:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = {}

    api_url = (data.get("api_url") or "").strip()
    instance = (data.get("instance_name") or "").strip()
    api_key = (data.get("api_key") or "").strip()
    clear_key_raw = data.get("clear_api_key")
    clear_key = False
    if isinstance(clear_key_raw, bool):
        clear_key = clear_key_raw
    elif isinstance(clear_key_raw, str):
        clear_key = clear_key_raw.lower() in {"1", "true", "yes", "on"}

    update_fields = {"updated_at"}
    config.whatsapp_evolution_api_url = api_url or None
    update_fields.add("whatsapp_evolution_api_url")
    config.whatsapp_instance_name = instance or None
    update_fields.add("whatsapp_instance_name")

    if clear_key:
        config.whatsapp_evolution_api_key = None
        update_fields.add("whatsapp_evolution_api_key")
    elif api_key:
        config.whatsapp_evolution_api_key = api_key
        update_fields.add("whatsapp_evolution_api_key")

    config.save(update_fields=list(update_fields))

    propagation = {}
    if not clear_key and api_key:
        try:
            propagation = propagate_whatsapp_token(config.whatsapp_evolution_api_key or "")
        except Exception as exc:  # pragma: no cover - propagation is best effort
            logger.warning("Falha ao propagar token do WhatsApp: %s", exc)
            propagation = {"error": str(exc)}

    stored_token = config.whatsapp_evolution_api_key or ""

    return JsonResponse({
        "success": True,
        "api_url": config.whatsapp_evolution_api_url or "",
        "instance_name": config.whatsapp_instance_name or "",
        "has_api_key": bool(config.whatsapp_evolution_api_key),
        "token_value": stored_token,
        "propagation": propagation,
    })


@login_required
@require_POST
def whatsapp_generate_token(request):
    config = SystemConfiguration.get_config()

    new_token = secrets.token_urlsafe(32)
    config.whatsapp_evolution_api_key = new_token
    config.save(update_fields=["whatsapp_evolution_api_key", "updated_at"])

    propagation = {}
    try:
        propagation = propagate_whatsapp_token(new_token)
    except Exception as exc:  # pragma: no cover - propagation is best effort
        logger.warning("Falha ao propagar token do WhatsApp: %s", exc)
        propagation = {"error": str(exc)}

    return JsonResponse({
        "success": True,
        "token": new_token,
        "token_value": new_token,
        "api_url": config.whatsapp_evolution_api_url or "",
        "instance_name": config.whatsapp_instance_name or "",
        "has_api_key": True,
        "propagation": propagation,
    })


# ============================================================================
# TYPEBOT VIEWS
# ============================================================================

@login_required
@require_POST
def typebot_test_connection(request):
    """Testa conexão com Typebot Builder e verifica autenticação"""
    config = SystemConfiguration.get_config()
    
    if not config.typebot_enabled:
        return JsonResponse({
            "success": False,
            "error": "Typebot não está habilitado nas configurações"
        }, status=400)
    
    if not config.typebot_builder_url:
        return JsonResponse({
            "success": False,
            "error": "URL do Typebot Builder não configurada"
        }, status=400)
    
    try:
        # Convert localhost URLs to internal Docker network URLs
        builder_url = config.typebot_builder_url.rstrip('/')
        internal_builder_url = builder_url.replace('http://localhost:8081', 'http://typebot_builder:3000')
        
        # Prepare headers with API Key if available
        headers = {}
        if config.typebot_api_key:
            headers['Authorization'] = f'Bearer {config.typebot_api_key}'
        
        # Testa health endpoint
        health_response = requests.get(
            f"{internal_builder_url}/api/health",
            headers=headers,
            timeout=10
        )
        
        if health_response.status_code != 200:
            return JsonResponse({
                "success": False,
                "error": f"Typebot Builder retornou status {health_response.status_code}",
                "details": health_response.text[:200]
            }, status=502)
        
        # Se temos API Key, consider authenticated
        auth_status = "not_configured"
        if config.typebot_api_key:
            auth_status = "api_key_configured"
        elif config.typebot_admin_email and config.typebot_admin_password:
            # Tenta autenticar com email/senha
            try:
                auth_response = requests.post(
                    f"{internal_builder_url}/api/auth/signin",
                    json={
                        "email": config.typebot_admin_email,
                        "password": config.typebot_admin_password
                    },
                    timeout=10
                )
                
                if auth_response.status_code == 200:
                    auth_data = auth_response.json()
                    if auth_data.get('user'):
                        auth_status = "authenticated"
                    else:
                        auth_status = "auth_failed"
                else:
                    auth_status = "auth_failed"
                    
            except Exception as auth_error:
                logger.warning(f"Erro ao testar autenticação Typebot: {auth_error}")
                auth_status = "auth_error"
        
        return JsonResponse({
            "success": True,
            "builder_url": builder_url,
            "viewer_url": config.typebot_viewer_url,
            "status": "online",
            "auth_status": auth_status,
            "message": "Typebot está acessível e funcionando corretamente"
        })
        
    except requests.exceptions.Timeout:
        return JsonResponse({
            "success": False,
            "error": "Timeout ao conectar com Typebot Builder",
            "details": "Verifique se o container está rodando e acessível"
        }, status=504)
        
    except requests.exceptions.ConnectionError:
        return JsonResponse({
            "success": False,
            "error": "Não foi possível conectar ao Typebot Builder",
            "details": f"Verifique se URL '{config.typebot_builder_url}' está correta e o serviço está rodando"
        }, status=503)
        
    except Exception as e:
        logger.exception("Erro ao testar conexão Typebot")
        return JsonResponse({
            "success": False,
            "error": f"Erro inesperado: {str(e)}"
        }, status=500)


@login_required
@require_GET
def typebot_auto_login(request):
    """Redireciona para Typebot Builder com login automático se configurado"""
    config = SystemConfiguration.get_config()
    
    if not config.typebot_enabled or not config.typebot_builder_url:
        messages.error(request, 'Typebot não está configurado')
        return redirect('system_config:index')
    
    builder_url = config.typebot_builder_url.rstrip('/')
    
    # Se temos credenciais, tenta fazer login automático
    if config.typebot_admin_email and config.typebot_admin_password:
        try:
            # Convert to internal URL for API calls
            internal_builder_url = builder_url.replace('http://localhost:8081', 'http://typebot_builder:3000')
            
            # Tenta autenticar
            auth_response = requests.post(
                f"{internal_builder_url}/api/auth/signin",
                json={
                    "email": config.typebot_admin_email,
                    "password": config.typebot_admin_password
                },
                timeout=10,
                allow_redirects=False
            )
            
            if auth_response.status_code == 200:
                auth_data = auth_response.json()
                
                # Se retornou token ou sessão, redireciona com sucesso
                if auth_data.get('user'):
                    messages.success(request, 'Login automático realizado com sucesso!')
                    return redirect(builder_url)
                    
        except Exception as e:
            logger.warning(f"Erro ao fazer login automático no Typebot: {e}")
            messages.warning(request, 'Não foi possível fazer login automático. Redirecionando para tela de login.')
    
    # Se não tem credenciais ou falhou, apenas redireciona
    messages.info(request, 'Redirecionando para Typebot Builder')
    return redirect(builder_url)


@login_required
@require_POST
def typebot_generate_encryption_secret(request):
    """Gera um novo encryption secret para Typebot"""
    config = SystemConfiguration.get_config()
    
    # Gera secret de 32 bytes em formato hex (64 caracteres)
    new_secret = secrets.token_hex(32)
    
    config.typebot_encryption_secret = new_secret
    config.save(update_fields=["typebot_encryption_secret", "updated_at"])
    
    return JsonResponse({
        "success": True,
        "secret": new_secret,
        "message": "Novo encryption secret gerado com sucesso"
    })

