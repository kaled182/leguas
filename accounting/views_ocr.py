"""Endpoint API para OCR de facturas no Bill form."""
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import Fornecedor
from .services_ocr import extract_invoice_data

logger = logging.getLogger(__name__)

MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
ALLOWED_EXT = (".pdf", ".jpg", ".jpeg", ".png", ".webp")


@login_required
@require_http_methods(["POST"])
def ocr_extract_api(request):
    """Recebe um ficheiro (PDF/imagem) e devolve dados estruturados."""
    f = request.FILES.get("file")
    if not f:
        return JsonResponse(
            {"success": False, "error": "Ficheiro 'file' obrigatório."},
            status=400,
        )
    name = (f.name or "").lower()
    if not name.endswith(ALLOWED_EXT):
        return JsonResponse({
            "success": False,
            "error": f"Tipo não suportado. Permitidos: {', '.join(ALLOWED_EXT)}.",
        }, status=400)
    if f.size > MAX_SIZE_BYTES:
        return JsonResponse({
            "success": False,
            "error": f"Ficheiro acima de 10MB ({f.size} bytes).",
        }, status=400)

    provider = (request.POST.get("provider") or "").strip().lower() or None
    try:
        data = extract_invoice_data(f, provider=provider)
    except Exception as e:
        logger.exception("[ocr] extracção falhou")
        return JsonResponse({"success": False, "error": str(e)}, status=500)

    # Sugerir Fornecedor existente por NIF
    suggested = None
    if data.get("supplier_nif"):
        s = Fornecedor.objects.filter(
            nif=data["supplier_nif"], is_active=True,
        ).first()
        if s:
            suggested = {
                "id": s.id, "name": s.name, "nif": s.nif,
                "default_categoria_id": s.default_categoria_id,
                "default_centro_custo_id": s.default_centro_custo_id,
                "default_iva_rate": str(s.default_iva_rate),
                "iva_dedutivel": s.iva_dedutivel,
            }

    return JsonResponse({
        "success": True,
        "data": data,
        "suggested_fornecedor": suggested,
    })
