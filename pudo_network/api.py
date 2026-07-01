"""API do handshake PUDO para a app do estafeta.

Estilo `app_api` (views Django + JSON, token Bearer via `@app_token_required`),
montada em /api/app/v1/pudo/. NÃO usa DRF. O endpoint é **idempotente pela uuid**:
reenvios devolvem sempre o mesmo estado (200), nunca duplicam.

Este ficheiro é a fonte-de-verdade do contrato que a app Android futura consome;
manter em sincronia com docs/api/PUDO_HANDSHAKE.md.
"""
import json

from django.http import JsonResponse
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app_api.auth import app_token_required

from .models import PudoStore, PudoTransaction
from .services import process_handshake


def _json_body(request):
    try:
        return json.loads(request.body or b"{}")
    except (ValueError, TypeError):
        return {}


def _resolve_store(ref):
    """Aceita número (PUDO-0001) ou id inteiro."""
    ref = (str(ref) if ref is not None else "").strip()
    if not ref:
        return None
    store = PudoStore.objects.filter(numero__iexact=ref).first()
    if store:
        return store
    if ref.isdigit():
        return PudoStore.objects.filter(id=int(ref)).first()
    return None


def _package_dict(pkg):
    if pkg is None:
        return None
    return {
        "id": pkg.id,
        "tracking_ref": pkg.tracking_ref,
        "status": pkg.status,
        "store": pkg.store.numero,
        "received_at": pkg.received_at.isoformat() if pkg.received_at else None,
        "aging_deadline": (
            pkg.aging_deadline.isoformat() if pkg.aging_deadline else None
        ),
    }


@csrf_exempt
@require_http_methods(["POST"])
@app_token_required
def handshake(request):
    """Regista um handshake de custódia (entrega ou devolução ao PUDO).

    Body JSON:
        uuid          (str, obrigatório) — chave de idempotência do dispositivo
        pudo          (str, obrigatório) — número PUDO-0001 ou id da loja
        tracking_ref  (str, obrigatório) — código/waybill do pacote
        tipo          (str, opcional)    — ENTREGA (default) | DEVOLUCAO
        device_ts     (str ISO, opcional)
        payload       (obj, opcional)    — dados livres (ex.: client_phone)

    Resposta 200 (sempre que válido, mesmo em reenvio idempotente):
        {success, idempotent, transaction_uuid, package: {...}}
    """
    data = _json_body(request)
    uuid = (data.get("uuid") or "").strip()
    tracking_ref = (data.get("tracking_ref") or "").strip()
    tipo = (data.get("tipo") or PudoTransaction.Tipo.ENTREGA).strip().upper()

    em_falta = [k for k, v in (
        ("uuid", uuid), ("pudo", data.get("pudo")), ("tracking_ref", tracking_ref),
    ) if not v]
    if em_falta:
        return JsonResponse(
            {"success": False, "error": "Campos obrigatórios em falta: "
             + ", ".join(em_falta)},
            status=400,
        )

    if tipo not in PudoTransaction.Tipo.values:
        return JsonResponse(
            {"success": False, "error": f"tipo inválido: {tipo}"}, status=400,
        )

    store = _resolve_store(data.get("pudo"))
    if store is None:
        return JsonResponse(
            {"success": False, "error": "PUDO não encontrado."}, status=404,
        )

    device_ts = parse_datetime(data.get("device_ts") or "") or None
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}

    result = process_handshake(
        uuid=uuid, tipo=tipo, store=store, tracking_ref=tracking_ref,
        origin=PudoTransaction.Origin.DRIVER_APP,
        actor=str(request.driver_profile.id), actor_type="DRIVER",
        driver=request.driver_profile, device_ts=device_ts, payload=payload,
    )

    return JsonResponse({
        "success": True,
        "idempotent": result.idempotent,
        "transaction_uuid": str(result.transaction.uuid),
        "package": _package_dict(result.package),
    }, status=200)
