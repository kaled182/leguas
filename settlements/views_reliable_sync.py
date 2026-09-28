"""Estado e configuração da sincronização EPOD com o ReliableMaps."""
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import ReliableEpodSync


def _mascarar(tok):
    tok = (tok or "").strip()
    if not tok:
        return ""
    return "…" + tok[-4:] if len(tok) > 4 else "••••"


@login_required
@require_http_methods(["GET", "POST"])
def api_reliable_sync(request):
    """GET: estado + últimos ficheiros. POST {action}:
      • "sync" — agenda uma sincronização agora (qualquer utilizador autenticado);
      • "save" {url, key, enabled} — guarda a configuração (só admin; key vazia mantém a atual).
    """
    from system_config.models import SystemConfiguration

    cfg = SystemConfiguration.get_config()
    is_admin = request.user.is_staff or request.user.is_superuser

    if request.method == "POST":
        try:
            data = json.loads(request.body or "{}")
        except ValueError:
            return JsonResponse({"ok": False, "erro": "JSON inválido"}, status=400)
        action = data.get("action")
        if action == "save":
            if not is_admin:
                return JsonResponse({"ok": False, "erro": "Sem permissão"}, status=403)
            cfg.reliable_api_url = (data.get("url") or "").strip().rstrip("/") or None
            if data.get("clear_key"):
                cfg.reliable_api_key = None
            elif (data.get("key") or "").strip():
                cfg.reliable_api_key = data["key"].strip()
            cfg.reliable_epod_sync_enabled = bool(data.get("enabled"))
            cfg.reliable_claims_sync_enabled = bool(data.get("claims_enabled"))
            # update_fields: um save completo re-encripta todos os campos e
            # falha se algum antigo já não se consegue desencriptar.
            cfg.save(update_fields=[
                "reliable_api_url", "reliable_api_key",
                "reliable_epod_sync_enabled", "reliable_claims_sync_enabled",
            ])
        elif action == "sync":
            from .tasks import sync_claim_verdicts_from_reliable, sync_epod_from_reliable
            sync_epod_from_reliable.delay(triggered_by=f"manual:{request.user.username}")
            if cfg.reliable_claims_sync_enabled:
                sync_claim_verdicts_from_reliable.delay(triggered_by=f"manual:{request.user.username}")
        else:
            return JsonResponse({"ok": False, "erro": "Ação desconhecida"}, status=400)

    recent = [
        {
            "ficheiro": s.filename,
            "hub": s.hub,
            "estado": s.status,
            "estado_display": s.get_status_display(),
            "carregado_em": s.remote_loaded_at.isoformat(),
            "sincronizado_em": s.created_at.isoformat(),
            "mensagem": s.message,
            "resumo": s.summary,
        }
        for s in ReliableEpodSync.objects.exclude(status=ReliableEpodSync.STATUS_SUPERSEDED)
        .order_by("-created_at")[:10]
    ]
    last_ok = (
        ReliableEpodSync.objects.filter(status=ReliableEpodSync.STATUS_IMPORTED)
        .order_by("-created_at").values_list("created_at", flat=True).first()
    )
    from django.db.models import Count

    from .models import ReliableClaimVerdict

    verdicts = dict(
        ReliableClaimVerdict.objects.values_list("outcome").annotate(n=Count("id")).values_list("outcome", "n")
    )
    return JsonResponse({
        "ok": True,
        "enabled": cfg.reliable_epod_sync_enabled,
        "claims_enabled": cfg.reliable_claims_sync_enabled,
        "verdicts": verdicts,
        "configured": bool((cfg.reliable_api_url or "").strip() and (cfg.reliable_api_key or "").strip()),
        "is_admin": is_admin,
        "url": (cfg.reliable_api_url or "") if is_admin else "",
        "key_masked": _mascarar(cfg.reliable_api_key) if is_admin else "",
        "last_import_at": last_ok.isoformat() if last_ok else None,
        "recent": recent,
    })
