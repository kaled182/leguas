"""Sincronização da task list (EPOD) da Cainiao a partir do ReliableMaps.

O robô do ReliableMaps exporta o EPOD_TASK_LIST_V2 do CES de cada hub a cada
30 min e guarda o xlsx original. Aqui lemos esses ficheiros pela API de
integrações (/api/integracoes/v1/epod/) e importamo-los com a mesma lógica do
upload manual da Operation Update (import_operation_file).

Cada export cobre ontem + hoje por completo, por isso só importamos o mais
recente de cada (hub, dia do export); os anteriores ficam "superseded".
"""
import hashlib
import logging
from collections import defaultdict
from datetime import timedelta

import requests
from django.core.cache import cache
from django.utils import timezone
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)

LOCK_KEY = "settlements:reliable_epod_sync"
LOCK_TIMEOUT = 25 * 60
FIRST_RUN_WINDOW = timedelta(days=1)
OVERLAP = timedelta(hours=6)
MAX_PAGES = 10
LIST_TIMEOUT = 20
DOWNLOAD_TIMEOUT = 120


class ReliableSyncError(Exception):
    pass


class ReliableFileGone(ReliableSyncError):
    """O ReliableMaps já não tem o ficheiro (404): não adianta tentar de novo."""


def _config():
    from system_config.models import SystemConfiguration

    cfg = SystemConfiguration.get_config()
    base = (cfg.reliable_api_url or "").strip().rstrip("/")
    key = (cfg.reliable_api_key or "").strip()
    return cfg.reliable_epod_sync_enabled, base, key


def _get(base, key, path, params=None, timeout=LIST_TIMEOUT):
    try:
        resp = requests.get(
            f"{base}/api/integracoes/v1/{path}",
            params=params,
            headers={"Authorization": f"Bearer {key}"},
            timeout=timeout,
        )
    except requests.RequestException as e:
        raise ReliableSyncError(f"Sem ligação ao ReliableMaps: {e}") from e
    if resp.status_code == 401:
        raise ReliableSyncError("Chave de integração inválida ou desativada (401).")
    if resp.status_code == 404:
        raise ReliableFileGone(f"Ficheiro já não disponível no ReliableMaps ({path}).")
    if resp.status_code != 200:
        raise ReliableSyncError(f"ReliableMaps respondeu {resp.status_code} em {path}.")
    return resp


def _list_remote_files(base, key, since):
    files = []
    desde = since
    for _ in range(MAX_PAGES):
        data = _get(base, key, "epod/", params={"desde": desde.isoformat()}).json()
        page = data.get("ficheiros", [])
        files.extend(page)
        if len(page) < data.get("limite", len(page) + 1):
            break
        desde = parse_datetime(page[-1]["carregado_em"])
    # A paginação por `desde` repete o último da página anterior.
    unique = {f["sha256"]: f for f in files}
    return sorted(unique.values(), key=lambda f: (f["carregado_em"], f["id"]))


def _group_key(f):
    moment = parse_datetime(f.get("exportado_em") or f["carregado_em"])
    return (f.get("hub") or "", timezone.localtime(moment).date())


def sync_epod_from_reliable(triggered_by="cron"):
    """Importa os EPOD novos do ReliableMaps. Devolve um resumo (dict)."""
    enabled, base, key = _config()
    if not enabled:
        return {"ok": True, "skipped": "Sincronização desligada."}
    if not base or not key:
        return {"ok": False, "error": "URL ou chave do ReliableMaps em falta."}

    if not cache.add(LOCK_KEY, triggered_by, LOCK_TIMEOUT):
        return {"ok": True, "skipped": "Já há uma sincronização a correr."}
    try:
        return _sync(base, key)
    except ReliableSyncError as e:
        logger.warning("sync EPOD ReliableMaps: %s", e)
        return {"ok": False, "error": str(e)}
    finally:
        cache.delete(LOCK_KEY)


def _sync(base, key):
    from .cainiao_views import import_operation_file
    from .models import ReliableEpodSync

    last = ReliableEpodSync.objects.order_by("-remote_loaded_at").first()
    since = (last.remote_loaded_at - OVERLAP) if last else (timezone.now() - FIRST_RUN_WINDOW)

    remote = _list_remote_files(base, key, since)
    known = set(
        ReliableEpodSync.objects.filter(sha256__in=[f["sha256"] for f in remote])
        .values_list("sha256", flat=True)
    )
    new = [f for f in remote if f["sha256"] not in known]

    def record(f, status, message="", summary=None):
        ReliableEpodSync.objects.create(
            remote_id=f["id"],
            sha256=f["sha256"],
            filename=f["ficheiro"][:255],
            hub=(f.get("hub") or "")[:40],
            remote_loaded_at=parse_datetime(f["carregado_em"]),
            status=status,
            message=message,
            summary=summary or {},
        )

    result = {"ok": True, "found": len(new), "imported": 0, "failed": 0,
              "superseded": 0, "skipped": 0, "files": []}

    groups = defaultdict(list)
    for f in new:
        if f.get("atribuidas"):
            # Tarefas só atribuídas, geradas pelo robô a partir do JSON do CES:
            # não são um export do EPOD e trazem poucas colunas.
            record(f, ReliableEpodSync.STATUS_SKIPPED, "Ficheiro de atribuídas.")
            result["skipped"] += 1
            continue
        groups[_group_key(f)].append(f)

    for _, files in sorted(groups.items(), key=lambda kv: kv[1][-1]["carregado_em"]):
        latest = files[-1]
        try:
            resp = _get(base, key, f"epod/{latest['id']}/ficheiro/", timeout=DOWNLOAD_TIMEOUT)
        except ReliableFileGone as e:
            # Na próxima volta o anterior do mesmo grupo passa a ser o mais recente.
            record(latest, ReliableEpodSync.STATUS_FAILED, str(e))
            result["failed"] += 1
            continue
        except ReliableSyncError as e:
            # Erro de rede: não se regista, tenta-se na próxima volta.
            result["ok"] = False
            result["error"] = str(e)
            continue
        content = resp.content
        if hashlib.sha256(content).hexdigest() != latest["sha256"]:
            record(latest, ReliableEpodSync.STATUS_FAILED, "SHA-256 não confere com o anunciado.")
            result["failed"] += 1
            continue

        try:
            payload, status = import_operation_file(content, latest["ficheiro"], user=None)
        except Exception as e:  # noqa: BLE001 — um ficheiro mau não pára os outros
            logger.exception("sync EPOD ReliableMaps: erro ao importar %s", latest["ficheiro"])
            payload, status = {"success": False, "error": f"{type(e).__name__}: {e}"}, 500

        if payload.get("success"):
            summary = {k: payload.get(k) for k in ("total_novos", "total_atualizados", "date_range", "batch_ids")}
            record(latest, ReliableEpodSync.STATUS_IMPORTED, summary=summary)
            result["imported"] += 1
            result["files"].append({"ficheiro": latest["ficheiro"], **summary})
        else:
            record(latest, ReliableEpodSync.STATUS_FAILED, payload.get("error", f"HTTP {status}"))
            result["failed"] += 1
            continue

        for older in files[:-1]:
            record(older, ReliableEpodSync.STATUS_SUPERSEDED, f"Substituído por {latest['ficheiro']}.")
            result["superseded"] += 1

    return result
