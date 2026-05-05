"""Views do módulo de Atualização: changelog, sugestões e check do GitHub."""
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import requests
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import Suggestion, SystemVersionState


def _is_admin(request):
    return request.user.is_authenticated and (
        request.user.is_staff or request.user.is_superuser
    )


def _parse_github_repo(url):
    """Extrai (owner, repo) de uma URL GitHub. Devolve (None, None) se inválido."""
    if not url:
        return None, None
    try:
        parts = urlparse(url).path.strip("/").split("/")
        if len(parts) >= 2:
            owner, repo = parts[0], parts[1].replace(".git", "")
            return owner, repo
    except Exception:
        pass
    return None, None


def _fetch_recent_commits(state, max_commits=80):
    """Busca commits recentes do GitHub e agrupa por dia.

    Devolve uma lista de dias (mais recente primeiro), cada um com:
        { date, version, commit_count, commits: [...] }

    Versão de cada dia: `beta-DD-MM.N` onde N = nº de commits do dia.
    A entrada do dia mostra todos os commits (cada um com sha + msg + autor).

    Em caso de erro, devolve (lista_vazia, error_string).
    """
    owner, repo = _parse_github_repo(state.github_repo_url)
    if not owner or not repo:
        return [], "URL do repositório GitHub não configurada."
    branch = state.github_branch or "main"
    headers = {"Accept": "application/vnd.github+json"}
    if state.github_token:
        headers["Authorization"] = f"Bearer {state.github_token}"
    try:
        r = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/commits",
            params={"sha": branch, "per_page": min(max_commits, 100)},
            headers=headers, timeout=15,
        )
    except requests.exceptions.RequestException as e:
        return [], f"Erro de rede: {e}"
    if r.status_code != 200:
        try:
            msg = r.json().get("message", r.text[:200])
        except (ValueError, json.JSONDecodeError):
            msg = r.text[:200]
        return [], f"GitHub respondeu {r.status_code}: {msg}"

    raw = r.json() or []
    by_date = {}
    for c in raw:
        author_date = c["commit"]["author"]["date"]  # ISO 8601 UTC
        try:
            d = datetime.fromisoformat(author_date.replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            continue
        full_msg = c["commit"]["message"]
        first_line = (full_msg.split("\n")[0] or "").strip()[:140]
        body_lines = [
            ln.strip() for ln in full_msg.split("\n")[1:]
            if ln.strip() and not ln.startswith("Co-Authored-By")
        ]
        by_date.setdefault(d, []).append({
            "sha": c["sha"],
            "sha_short": c["sha"][:7],
            "message": first_line,
            "body": "\n".join(body_lines)[:600],
            "author": c["commit"]["author"]["name"],
            "url": c["html_url"],
            "date": author_date,
        })

    days = []
    for d in sorted(by_date.keys(), reverse=True):
        commits = by_date[d]
        # Ordenar do mais recente para o mais antigo dentro do dia
        commits.sort(key=lambda x: x["date"], reverse=True)
        version = f"beta-{d.day:02d}-{d.month:02d}.{len(commits)}"
        days.append({
            "date": d,
            "version": version,
            "commit_count": len(commits),
            "commits": commits,
        })
    return days, None


@login_required
def updates_index(request):
    """Página principal de Atualização: versão actual, changelog (GitHub), sugestões."""
    state = SystemVersionState.get()

    commit_days, changelog_error = _fetch_recent_commits(state)
    suggestions_recent = Suggestion.objects.all()[:30]
    suggestions_open = Suggestion.objects.filter(status="NEW").count()

    return render(request, "system_config/updates.html", {
        "state": state,
        "commit_days": commit_days,
        "changelog_error": changelog_error,
        "suggestions_recent": suggestions_recent,
        "suggestions_open": suggestions_open,
        "is_admin_view": _is_admin(request),
    })


@login_required
@require_http_methods(["POST"])
def suggestion_create(request):
    """Submete uma sugestão de melhoria."""
    title = (request.POST.get("title") or "").strip()
    description = (request.POST.get("description") or "").strip()
    category = (request.POST.get("category") or "OTHER").strip()

    if not title or not description:
        return JsonResponse(
            {"success": False, "error": "Título e descrição são obrigatórios."},
            status=400,
        )

    s = Suggestion.objects.create(
        title=title[:200], description=description, category=category,
        submitter=request.user if request.user.is_authenticated else None,
        submitter_name=(
            request.user.get_full_name() or request.user.username
            if request.user.is_authenticated else
            (request.POST.get("submitter_name") or "Anónimo")
        ),
    )
    return JsonResponse({"success": True, "id": s.id})


@login_required
@require_http_methods(["POST"])
def suggestion_update_status(request, suggestion_id):
    if not _is_admin(request):
        return HttpResponseForbidden()
    s = get_object_or_404(Suggestion, id=suggestion_id)
    new_status = (request.POST.get("status") or "").strip()
    response = (request.POST.get("admin_response") or "").strip()
    if new_status in dict(Suggestion.STATUS_CHOICES):
        s.status = new_status
    if response:
        s.admin_response = response
        s.responded_at = timezone.now()
    s.save()
    return JsonResponse({"success": True, "status": s.status})


@login_required
@require_http_methods(["POST"])
def github_save_config(request):
    """Configura URL/branch/token do repositório GitHub para verificações."""
    if not _is_admin(request):
        return HttpResponseForbidden()
    state = SystemVersionState.get()
    state.github_repo_url = (request.POST.get("github_repo_url") or "").strip()
    state.github_branch = (request.POST.get("github_branch") or "main").strip()
    token = (request.POST.get("github_token") or "").strip()
    if token and token != "***":
        state.github_token = token
    state.save()
    messages.success(request, "Configuração do GitHub guardada.")
    return redirect("system_config:updates_index")


@login_required
def updates_check(request):
    """Verifica o GitHub para novos commits.

    Devolve JSON com:
      - up_to_date: bool
      - local_hash, remote_hash
      - commits: lista dos commits novos (até 20)
      - error: caso falhe
    """
    state = SystemVersionState.get()
    owner, repo = _parse_github_repo(state.github_repo_url)
    if not owner or not repo:
        return JsonResponse({
            "success": False,
            "error": "URL do repositório GitHub não configurada.",
        }, status=400)

    branch = state.github_branch or "main"
    headers = {"Accept": "application/vnd.github+json"}
    if state.github_token:
        headers["Authorization"] = f"Bearer {state.github_token}"

    try:
        # Get HEAD commit of branch
        r = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}",
            headers=headers, timeout=15,
        )
        if r.status_code != 200:
            return JsonResponse({
                "success": False,
                "error": f"GitHub respondeu {r.status_code}: "
                         f"{r.json().get('message', r.text[:200])}",
            }, status=502)
        head = r.json()
        remote_hash = head["sha"]
        local_hash = state.deployed_commit_hash or ""
        up_to_date = remote_hash == local_hash

        commits = []
        if not up_to_date and local_hash:
            # Compare local..remote para listar commits pendentes
            cmp = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/compare/"
                f"{local_hash}...{remote_hash}",
                headers=headers, timeout=15,
            )
            if cmp.status_code == 200:
                data = cmp.json()
                for c in (data.get("commits") or [])[:20]:
                    commits.append({
                        "sha": c["sha"][:7],
                        "message": c["commit"]["message"].split("\n")[0][:120],
                        "author": c["commit"]["author"]["name"],
                        "date": c["commit"]["author"]["date"],
                    })
            ahead_by = (data.get("ahead_by") if cmp.status_code == 200 else None)
        else:
            ahead_by = 0 if up_to_date else None
            if not up_to_date and not local_hash:
                # Sem hash local — só mostra o último commit
                commits.append({
                    "sha": remote_hash[:7],
                    "message": head["commit"]["message"].split("\n")[0][:120],
                    "author": head["commit"]["author"]["name"],
                    "date": head["commit"]["author"]["date"],
                })

        result = {
            "success": True,
            "up_to_date": up_to_date,
            "local_hash": local_hash[:7] if local_hash else "",
            "remote_hash": remote_hash[:7],
            "ahead_by": ahead_by,
            "commits": commits,
            "checked_at": timezone.now().isoformat(),
        }
        state.last_check_at = timezone.now()
        state.last_check_result = result
        state.save(update_fields=["last_check_at", "last_check_result"])
        return JsonResponse(result)
    except requests.exceptions.RequestException as e:
        return JsonResponse(
            {"success": False, "error": f"Erro de rede: {e}"}, status=502,
        )


def _updater_url(path):
    base = os.environ.get("UPDATER_URL", "http://updater:9999")
    return f"{base.rstrip('/')}{path}"


def _updater_secret():
    return os.environ.get("UPDATER_SECRET", "")




@login_required
@require_http_methods(["POST"])
def updates_apply(request):
    """Aciona o sidecar updater para fazer git pull + rebuild + recreate."""
    if not _is_admin(request):
        return HttpResponseForbidden()

    secret = _updater_secret()
    if not secret:
        return JsonResponse({
            "success": False,
            "error": (
                "UPDATER_SECRET não configurado no ambiente do web. "
                "Definir no .env e reiniciar."
            ),
        }, status=500)
    try:
        r = requests.post(
            _updater_url("/update"),
            headers={"X-Updater-Secret": secret},
            timeout=10,
        )
    except requests.exceptions.RequestException as e:
        return JsonResponse({
            "success": False,
            "error": f"Não foi possível contactar o updater: {e}",
        }, status=502)
    if r.status_code == 202:
        data = r.json()
        return JsonResponse({
            "success": True,
            "job_id": data.get("job_id"),
            "message": (
                "Atualização iniciada em segundo plano. "
                "O sistema poderá ficar inacessível durante poucos segundos."
            ),
        })
    if r.status_code == 409:
        return JsonResponse({
            "success": False,
            "error": "Já existe uma atualização em curso.",
            "job_id": r.json().get("job_id"),
        }, status=409)
    return JsonResponse({
        "success": False,
        "error": f"Updater respondeu {r.status_code}: {r.text[:200]}",
    }, status=502)


@login_required
def updates_status(request):
    """Devolve o estado actual do job de update (proxy ao sidecar)."""
    if not _is_admin(request):
        return HttpResponseForbidden()
    secret = _updater_secret()
    if not secret:
        return JsonResponse(
            {"phase": "idle", "error": "UPDATER_SECRET não configurado."},
        )
    try:
        r = requests.get(
            _updater_url("/status"),
            headers={"X-Updater-Secret": secret},
            timeout=5,
        )
    except requests.exceptions.RequestException as e:
        return JsonResponse(
            {"phase": "unknown", "error": f"Updater inacessível: {e}"},
            status=502,
        )
    return JsonResponse(r.json(), status=r.status_code)
