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

from .models import (
    ChangelogEntry, Suggestion, SystemVersionState, suggest_next_version,
)


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


@login_required
def updates_index(request):
    """Página principal de Atualização: versão actual, changelog, sugestões."""
    state = SystemVersionState.get()

    entries = ChangelogEntry.objects.all()[:50]
    suggestions_recent = Suggestion.objects.all()[:30]
    suggestions_open = Suggestion.objects.filter(status="NEW").count()

    suggested_version = suggest_next_version()

    return render(request, "system_config/updates.html", {
        "state": state,
        "entries": entries,
        "suggestions_recent": suggestions_recent,
        "suggestions_open": suggestions_open,
        "suggested_version": suggested_version,
        "is_admin_view": _is_admin(request),
    })


@login_required
@require_http_methods(["POST"])
def changelog_save(request):
    """Cria ou actualiza a entrada de changelog do dia."""
    if not _is_admin(request):
        return HttpResponseForbidden("Apenas admin.")

    today = timezone.now().date()
    version = (request.POST.get("version") or "").strip()
    content = (request.POST.get("content") or "").strip()

    if not content:
        messages.error(request, "Conteúdo é obrigatório.")
        return redirect("system_config:updates_index")

    if not version:
        version = suggest_next_version()

    entry, created = ChangelogEntry.objects.get_or_create(
        date=today,
        defaults={
            "version": version,
            "content": content,
            "created_by": request.user,
        },
    )
    if not created:
        # Actualiza conteúdo + faz bump de versão se a fornecida é nova
        entry.content = content
        if version and version != entry.version:
            history = list(entry.version_history or [])
            if entry.version and entry.version not in history:
                history.append(entry.version)
            entry.version = version
            entry.version_history = history
        entry.publish_status = "PENDING"  # nova versão precisa de re-publish
        entry.save()

    # Publicação automática (best-effort — não falha o save se push falhar)
    success, err = _publish_changelog_to_github(entry)
    if success:
        messages.success(
            request,
            f"Entrada {entry.version} guardada e publicada no GitHub.",
        )
    else:
        messages.warning(
            request,
            f"Entrada {entry.version} guardada, mas publicação no GitHub "
            f"falhou: {err}",
        )
    return redirect("system_config:updates_index")


@login_required
@require_http_methods(["POST"])
def changelog_publish(request, entry_id):
    """Re-tenta publicar uma entrada específica no GitHub."""
    if not _is_admin(request):
        return HttpResponseForbidden()
    entry = get_object_or_404(ChangelogEntry, id=entry_id)
    success, err = _publish_changelog_to_github(entry)
    if success:
        return JsonResponse({
            "success": True,
            "commit_sha": entry.published_commit_sha,
            "published_at": entry.published_at.isoformat() if entry.published_at else None,
        })
    return JsonResponse({"success": False, "error": err}, status=502)


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


def _build_changelog_markdown():
    """Gera o conteúdo do CHANGELOG.md a partir das entradas em DB.

    Formato:
        # Changelog
        ## beta-DD-MM.N — YYYY-MM-DD
        <content>
    """
    lines = [
        "# Changelog",
        "",
        "All notable changes to this project are documented in this file.",
        "Auto-gerado pelo módulo de Atualização do sistema.",
        "",
    ]
    for e in ChangelogEntry.objects.all().order_by("-date"):
        lines.append(f"## {e.version} — {e.date.strftime('%Y-%m-%d')}")
        if e.version_history and len(e.version_history) > 1:
            others = ", ".join(v for v in e.version_history if v != e.version)
            lines.append(f"_Versões anteriores deste dia: {others}_")
        lines.append("")
        lines.append((e.content or "").rstrip())
        lines.append("")
    return "\n".join(lines)


def _publish_changelog_to_github(entry):
    """Tenta publicar o CHANGELOG.md no GitHub. Atualiza o status da entrada.

    Devolve (success: bool, error: str).
    """
    state = SystemVersionState.get()
    if not state.github_token:
        entry.publish_status = "FAILED"
        entry.publish_error = "Token do GitHub não configurado."
        entry.save(update_fields=["publish_status", "publish_error"])
        return False, entry.publish_error
    if not state.github_repo_url:
        entry.publish_status = "FAILED"
        entry.publish_error = "URL do repositório não configurada."
        entry.save(update_fields=["publish_status", "publish_error"])
        return False, entry.publish_error

    secret = _updater_secret()
    if not secret:
        entry.publish_status = "FAILED"
        entry.publish_error = "UPDATER_SECRET não configurado."
        entry.save(update_fields=["publish_status", "publish_error"])
        return False, entry.publish_error

    content = _build_changelog_markdown()
    payload = {
        "content": content,
        "token": state.github_token,
        "repo_url": state.github_repo_url,
        "branch": state.github_branch or "main",
        "commit_message": (
            f"chore(changelog): {entry.version} — {entry.date.isoformat()}"
        ),
    }
    try:
        r = requests.post(
            _updater_url("/changelog-push"),
            headers={"X-Updater-Secret": secret},
            json=payload, timeout=60,
        )
    except requests.exceptions.RequestException as e:
        entry.publish_status = "FAILED"
        entry.publish_error = f"Updater inacessível: {e}"
        entry.save(update_fields=["publish_status", "publish_error"])
        return False, entry.publish_error
    if r.status_code != 200:
        entry.publish_status = "FAILED"
        try:
            entry.publish_error = (
                f"Updater respondeu {r.status_code}: "
                f"{r.json().get('error', r.text[:200])}"
            )
        except (ValueError, json.JSONDecodeError):
            entry.publish_error = f"Updater respondeu {r.status_code}"
        entry.save(update_fields=["publish_status", "publish_error"])
        return False, entry.publish_error
    data = r.json()
    entry.publish_status = "PUBLISHED"
    entry.publish_error = ""
    entry.published_at = timezone.now()
    entry.published_commit_sha = data.get("commit_sha", "")[:40]
    entry.save(update_fields=[
        "publish_status", "publish_error",
        "published_at", "published_commit_sha",
    ])
    return True, ""


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
