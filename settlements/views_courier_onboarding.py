"""Painel 'names sem mapping': cadastrar motorista novo a partir do login Cainiao."""
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .services_courier_onboarding import (
    OnboardingError, create_driver_for_courier_name, lookup_courier_id, suggested_full_name,
)


@login_required
@require_GET
def cainiao_unmapped_lookup(request):
    """GET ?courier_name=… → Courier ID encontrado (ou null) + nome sugerido."""
    name = (request.GET.get("courier_name") or "").strip()
    if not name:
        return JsonResponse({"success": False, "error": "courier_name obrigatório"}, status=400)
    return JsonResponse({
        "success": True,
        "courier_name": name,
        "suggested_name": suggested_full_name(name),
        "found": lookup_courier_id(name),
    })


@login_required
@require_POST
def cainiao_unmapped_create_driver(request):
    """POST {old_courier_name, courier_id, nome?, nif?, telefone?, email?}."""
    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"success": False, "error": "JSON inválido"}, status=400)
    try:
        result = create_driver_for_courier_name(
            body.get("old_courier_name"), body.get("courier_id"),
            nome=body.get("nome") or "", nif=body.get("nif") or "",
            telefone=body.get("telefone") or "", email=body.get("email") or "",
            user=request.user,
        )
    except OnboardingError as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)
    return JsonResponse({"success": True, **result})
