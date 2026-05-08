"""Endpoint API para OCR de facturas no Bill form."""
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import Bill, ExpenseCategory, Fornecedor
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

    # Sugerir ExpenseCategory existente por nome (icontains do hint)
    suggested_category = None
    hint = (data.get("category_hint") or "").strip()
    if hint:
        # 1ª tentativa: match exacto (case-insensitive) por name
        cat = ExpenseCategory.objects.filter(
            is_active=True, name__iexact=hint,
        ).first()
        # 2ª: match parcial — qualquer palavra do hint contida no name
        if not cat:
            for token in hint.split():
                if len(token) < 3:
                    continue
                cat = ExpenseCategory.objects.filter(
                    is_active=True, name__icontains=token,
                ).first()
                if cat:
                    break
        if cat:
            suggested_category = {
                "id": cat.id, "name": cat.name, "code": cat.code,
                "matched_via": hint,
            }

    # Detectar Bill duplicada por (fornecedor existente, invoice_number).
    # Se já existe uma Bill para o mesmo fornecedor com o mesmo nº de
    # factura, retornar info para a UI avisar antes do operador gravar.
    duplicate = None
    inv_num = (data.get("invoice_number") or "").strip()
    if suggested and inv_num:
        existing = Bill.objects.filter(
            fornecedor_id=suggested["id"],
            invoice_number=inv_num,
        ).order_by("-id").first()
        if existing:
            duplicate = {
                "id": existing.id,
                "description": existing.description,
                "amount_total": str(existing.amount_total),
                "issue_date": (
                    existing.issue_date.isoformat()
                    if existing.issue_date else None
                ),
                "status": existing.status,
                "status_display": existing.get_status_display(),
                "edit_url": f"/accounting/contas-a-pagar/{existing.id}/editar/",
            }

    return JsonResponse({
        "success": True,
        "data": data,
        "suggested_fornecedor": suggested,
        "suggested_category": suggested_category,
        "duplicate": duplicate,
    })
