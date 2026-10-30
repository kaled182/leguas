from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def api_zonas_export(request):
    """Export das zonas em GeoJSON para o ReliableMaps (só leitura).
    Autenticação: `Authorization: Bearer <ZONAS_EXPORT_KEY>`.
    ?desde=<ISO 8601> devolve só as zonas mudadas desde essa hora."""
    import hmac

    from django.conf import settings as dj_settings
    from django.utils.dateparse import parse_datetime

    from .services.export import exportar_zonas

    chave = (getattr(dj_settings, "ZONAS_EXPORT_KEY", "") or "").strip()
    auth = request.headers.get("Authorization", "")
    dada = auth[7:].strip() if auth.startswith("Bearer ") else ""
    if not chave or not dada or not hmac.compare_digest(dada, chave):
        return JsonResponse({"ok": False, "erro": "Chave ausente ou inválida"}, status=401)

    desde = None
    if request.GET.get("desde"):
        desde = parse_datetime(request.GET["desde"].replace(" ", "+"))
        if desde is None or desde.tzinfo is None:
            return JsonResponse(
                {"ok": False, "erro": "desde: ISO 8601 com fuso"}, status=400
            )
    fc, _ = exportar_zonas(desde=desde)
    return JsonResponse(fc, json_dumps_params={"ensure_ascii": False})
