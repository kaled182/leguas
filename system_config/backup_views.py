"""
Backup management views — standalone module that does NOT import api_views
to avoid the 'integrations' dependency error.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.management import call_command
from django.http import FileResponse, JsonResponse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .models import ConfigurationAudit
from .utils import env_manager

BACKUP_DIR = Path(settings.BASE_DIR) / "database" / "backups"
_ALLOWED_BACKUP_EXTENSIONS = {".zip"}


def _staff_check(user):
    return user.is_active and user.is_staff


def _safe_backup_path(filename: str) -> Path:
    if not filename:
        raise ValueError("Filename required")
    safe_name = Path(filename).name
    if safe_name != filename:
        raise ValueError("Invalid filename")
    return BACKUP_DIR / safe_name


def _ensure_backup_dir() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def _get_backup_password() -> bytes:
    values = env_manager.read_values(["BACKUP_ZIP_PASSWORD"])
    password = values.get("BACKUP_ZIP_PASSWORD", "").strip()
    if not password or len(password) < 8:
        raise ValueError("BACKUP_ZIP_PASSWORD must be at least 8 characters.")
    return password.encode()


def _detect_backup_type(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".config.json"):
        return "config"
    if lower.startswith("manual_backup_") or "manual" in lower:
        return "manual"
    if "auto" in lower or "scheduled" in lower or "snapshot" in lower:
        return "auto"
    if "import" in lower or "upload" in lower:
        return "upload"
    return "unknown"


# ── List / Create / Import ────────────────────────────────────────────────────

@require_http_methods(["GET", "POST"])
@login_required
@user_passes_test(_staff_check)
def backups_manager(request):
    """List backups (GET) or create/import a backup (POST)."""
    if request.method == "GET":
        _ensure_backup_dir()
        backups = []
        for fp in BACKUP_DIR.iterdir():
            if not fp.is_file():
                continue
            if fp.suffix.lower() not in _ALLOWED_BACKUP_EXTENSIONS:
                continue
            try:
                stat = fp.stat()
            except FileNotFoundError:
                continue
            cloud_uploaded = (BACKUP_DIR / f".{fp.name}.uploaded").exists()
            backups.append({
                "id": fp.name,
                "name": fp.name,
                "filename": fp.name,
                "size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "type": _detect_backup_type(fp.name),
                "cloud_uploaded": cloud_uploaded,
            })
        backups.sort(key=lambda x: x["created_at"], reverse=True)
        return JsonResponse({"success": True, "backups": backups})

    # POST — import an uploaded file
    _ensure_backup_dir()
    if request.FILES.get("file"):
        upload = request.FILES["file"]
        safe_name = Path(upload.name).name
        if not safe_name:
            return JsonResponse({"success": False, "message": "Invalid file name."}, status=400)
        if Path(safe_name).suffix.lower() not in _ALLOWED_BACKUP_EXTENSIONS:
            return JsonResponse({"success": False, "message": "Formato não suportado. Use .zip."}, status=400)
        target = BACKUP_DIR / safe_name
        if target.exists():
            stamped = datetime.now().strftime("%Y%m%d_%H%M%S")
            target = BACKUP_DIR / f"upload_{stamped}_{safe_name}"
        with target.open("wb") as handler:
            for chunk in upload.chunks():
                handler.write(chunk)
        ConfigurationAudit.log_change(
            user=request.user, action="import", section="Backups",
            new_value=target.name, request=request, success=True,
        )
        return JsonResponse({"success": True, "message": "Backup importado.", "filename": target.name}, status=201)

    # POST — generate new backup
    if shutil.which("mysqldump") is None:
        return JsonResponse({"success": False, "message": "mysqldump não disponível no servidor."}, status=500)
    try:
        _get_backup_password()
    except ValueError as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)

    try:
        filename = call_command("make_backup") or ""
        if not filename:
            zips = [p for p in BACKUP_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".zip"]
            if zips:
                filename = max(zips, key=lambda p: p.stat().st_mtime).name
        ConfigurationAudit.log_change(
            user=request.user, action="create", section="Backups",
            new_value=filename or "", request=request, success=True,
        )
        return JsonResponse({"success": True, "message": "Backup criado.", "filename": filename or ""})
    except Exception as exc:
        return JsonResponse({"success": False, "message": f"Erro ao criar backup: {exc}"}, status=500)


# ── Download ──────────────────────────────────────────────────────────────────

@require_GET
@login_required
@user_passes_test(_staff_check)
def download_backup(request, filename):
    """Download a backup file."""
    try:
        backup_path = _safe_backup_path(filename)
    except ValueError as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)
    if not backup_path.exists():
        return JsonResponse({"success": False, "message": "Ficheiro não encontrado."}, status=404)
    return FileResponse(backup_path.open("rb"), as_attachment=True, filename=backup_path.name)


# ── Restore ───────────────────────────────────────────────────────────────────

@require_POST
@login_required
@user_passes_test(_staff_check)
def restore_backup(request):
    """Restore a backup file."""
    try:
        body = request.POST.dict() or json.loads(request.body or "{}")
        filename = body.get("filename", "")
        backup_path = _safe_backup_path(filename)
        if not backup_path.exists():
            return JsonResponse({"success": False, "message": "Ficheiro não encontrado."}, status=404)

        if shutil.which("mysql") is None:
            return JsonResponse({"success": False, "message": "Ferramentas de restauro não disponíveis."}, status=500)

        if backup_path.suffix.lower() == ".zip":
            try:
                import pyzipper
            except ImportError:
                return JsonResponse({"success": False, "message": "pyzipper necessário para restaurar backups cifrados."}, status=500)
            # Permite o user fornecer a password via UI (útil quando o backup
            # foi feito com uma instalação anterior que tinha outra password).
            user_password = (body.get("password") or "").strip()
            if user_password:
                password = user_password.encode("utf-8")
            else:
                try:
                    password = _get_backup_password()
                except ValueError as exc:
                    return JsonResponse({"success": False, "message": str(exc)}, status=400)

            with tempfile.TemporaryDirectory(dir=BACKUP_DIR) as tmp_dir:
                tmp_path = Path(tmp_dir)
                try:
                    with pyzipper.AESZipFile(backup_path) as zf:
                        zf.pwd = password
                        zf.extractall(tmp_path)
                except (RuntimeError, Exception) as zip_exc:
                    msg = str(zip_exc)
                    if "Bad password" in msg or "Bad CRC" in msg:
                        return JsonResponse({
                            "success": False,
                            "message": (
                                "Password incorrecta para este backup. "
                                "Se o backup foi feito por uma instalação anterior, "
                                "preenche o campo 'Password do ZIP' no diálogo."
                            ),
                            "needs_password": True,
                        }, status=400)
                    raise

                # Restore database
                candidates = list(tmp_path.glob("*.sql"))
                if not candidates:
                    return JsonResponse({"success": False, "message": "Backup não contém ficheiro .sql."}, status=400)
                restore_name = f"restore_tmp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
                restore_path = BACKUP_DIR / restore_name
                shutil.copy2(candidates[0], restore_path)
                try:
                    call_command("restore_db", restore_path.name)
                finally:
                    restore_path.unlink(missing_ok=True)

                # Restore media files if present in the backup
                media_src = tmp_path / "media"
                if media_src.exists() and media_src.is_dir():
                    from django.conf import settings as dj_settings
                    media_root = Path(dj_settings.MEDIA_ROOT)
                    media_root.mkdir(parents=True, exist_ok=True)
                    restored_count = 0
                    for src_file in media_src.rglob("*"):
                        if not src_file.is_file():
                            continue
                        dest_file = media_root / src_file.relative_to(media_src)
                        dest_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src_file, dest_file)
                        restored_count += 1
        else:
            call_command("restore_db", backup_path.name)

        ConfigurationAudit.log_change(
            user=request.user, action="restore", section="Backups",
            new_value=filename, request=request, success=True,
        )
        return JsonResponse({"success": True, "message": "Restauro concluído. Base de dados e ficheiros de media restaurados com sucesso."})
    except Exception as exc:
        return JsonResponse({"success": False, "message": f"Erro no restauro: {exc}"}, status=500)


# ── Delete ────────────────────────────────────────────────────────────────────

@require_POST
@login_required
@user_passes_test(_staff_check)
def delete_backup(request):
    """Delete a backup file."""
    try:
        body = request.POST.dict() or json.loads(request.body or "{}")
        filename = body.get("filename", "")
        backup_path = _safe_backup_path(filename)
        if not backup_path.exists():
            return JsonResponse({"success": False, "message": "Ficheiro não encontrado."}, status=404)
        backup_path.unlink(missing_ok=True)
        # Remove cloud marker if present
        marker = BACKUP_DIR / f".{filename}.uploaded"
        marker.unlink(missing_ok=True)
        ConfigurationAudit.log_change(
            user=request.user, action="delete", section="Backups",
            new_value=filename, request=request, success=True,
        )
        return JsonResponse({"success": True, "message": "Backup removido."})
    except Exception as exc:
        return JsonResponse({"success": False, "message": f"Erro ao apagar: {exc}"}, status=500)


# ── Upload to Cloud ───────────────────────────────────────────────────────────

@require_POST
@login_required
@user_passes_test(_staff_check)
def upload_backup_to_cloud(request):
    """Upload an existing backup to cloud (Google Drive / FTP)."""
    try:
        body = request.POST.dict() or json.loads(request.body or "{}")
        filename = body.get("filename", "")
        backup_path = _safe_backup_path(filename)
        if not backup_path.exists():
            return JsonResponse({"success": False, "message": "Ficheiro não encontrado."}, status=404)
        # Lazy import to avoid circular dependency
        from .services.cloud_backups import upload_backup_to_gdrive
        from .models import SystemConfiguration
        cfg = SystemConfiguration.get_config()
        result = {"gdrive": {}, "ftp": {}}
        if getattr(cfg, "gdrive_enabled", False):
            result["gdrive"] = upload_backup_to_gdrive(
                backup_path,
                auth_mode=getattr(cfg, "gdrive_auth_mode", "service_account"),
                credentials_json=getattr(cfg, "gdrive_credentials_json", "") or "",
                folder_id=getattr(cfg, "gdrive_folder_id", "") or None,
            )
        ConfigurationAudit.log_change(
            user=request.user, action="upload_cloud", section="Backups",
            new_value=filename, request=request, success=True,
        )
        return JsonResponse({"success": True, "result": result})
    except Exception as exc:
        return JsonResponse({"success": False, "message": f"Erro no upload: {exc}"}, status=500)
