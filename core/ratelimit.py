"""Limite de pedidos por IP, com o cache do Django."""
from django.core.cache import cache

HOUR = 3600
OTP_SEND_LIMIT = 10
OTP_VERIFY_LIMIT = 30
REGISTER_LIMIT = 10


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def over_limit(request, scope, limit, window=HOUR):
    key = f"ratelimit:{scope}:{client_ip(request)}"
    cache.add(key, 0, window)
    try:
        return cache.incr(key) > limit
    except ValueError:
        return False
