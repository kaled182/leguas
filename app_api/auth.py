"""Autenticação por token Bearer para a API da app do motorista."""
from datetime import timedelta
from functools import wraps

from django.http import JsonResponse
from django.utils import timezone

from .models import DriverAppToken

# Validade do token (dias). Reemissão a cada login por OTP.
TOKEN_TTL_DAYS = 90


def issue_token(profile, user_agent=""):
    """Emite um novo token para o motorista."""
    return DriverAppToken.objects.create(
        driver_profile=profile,
        key=DriverAppToken.generate_key(),
        expires_at=timezone.now() + timedelta(days=TOKEN_TTL_DAYS),
        user_agent=(user_agent or "")[:255],
    )


def _bearer_key(request):
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return ""


def authenticate(request):
    """Devolve o DriverAppToken válido do pedido, ou None."""
    key = _bearer_key(request)
    if not key:
        return None
    tok = (
        DriverAppToken.objects
        .select_related("driver_profile")
        .filter(key=key, revoked=False)
        .first()
    )
    if not tok or not tok.is_valid:
        return None
    # marca uso (throttle: no máx. 1 escrita/hora)
    now = timezone.now()
    if tok.last_used_at is None or (now - tok.last_used_at) > timedelta(hours=1):
        tok.last_used_at = now
        tok.save(update_fields=["last_used_at"])
    return tok


def app_token_required(view):
    """Decorator: exige token Bearer válido. Coloca request.driver_profile
    e request.app_token. Devolve 401 JSON caso contrário."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        tok = authenticate(request)
        if tok is None:
            return JsonResponse(
                {"success": False, "error": "Token ausente ou inválido."},
                status=401,
            )
        request.app_token = tok
        request.driver_profile = tok.driver_profile
        return view(request, *args, **kwargs)
    return wrapper
