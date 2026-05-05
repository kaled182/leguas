"""View de recovery keys — só superuser.

Mostra as chaves críticas (BACKUP_ZIP_PASSWORD, UPDATER_SECRET, etc.)
para o operador poder copiá-las para um password manager. Sem este
acesso, se o .env e o .recovery_keys.txt forem perdidos, qualquer
backup antigo torna-se irrecuperável.
"""
import os

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render


def _is_superuser(user):
    return user.is_authenticated and user.is_superuser


KEYS = [
    # (env_var, label, description, is_critical)
    ("DJANGO_SUPERUSER_USERNAME", "Admin user", "Login do superuser",
     False),
    ("DJANGO_SUPERUSER_EMAIL", "Admin email",
     "Email do superuser", False),
    ("DB_USER", "DB user", "Utilizador MySQL", False),
    ("DB_PASSWORD", "DB password",
     "Password do utilizador MySQL", True),
    ("DB_ROOT_PASSWORD", "DB root password",
     "Password root do MySQL", True),
    ("SECRET_KEY", "Django SECRET_KEY",
     "Usado para sessões e CSRF — perda força logout de todos", True),
    ("FERNET_KEY", "Fernet key",
     "Encripta tokens guardados na DB (Cainiao, Delnext)", True),
    ("BACKUP_ZIP_PASSWORD", "BACKUP ZIP password",
     "Cifra os ZIPs de backup. SEM ESTA CHAVE, backups antigos ficam "
     "irrecuperáveis.", True),
    ("UPDATER_SECRET", "Updater secret",
     "Token usado pelo botão 'Atualizar agora'", True),
    ("WPPCONNECT_SECRET", "WPPConnect secret",
     "Token de autenticação do servidor WhatsApp", True),
    ("DOMAIN", "Domínio", "Hostname público do sistema", False),
    ("LETSENCRYPT_EMAIL", "Let's Encrypt email",
     "Email para certificados SSL", False),
]


@login_required
@user_passes_test(_is_superuser)
def recovery_keys_index(request):
    """Mostra as recovery keys actuais (só superuser)."""
    keys = []
    for env_var, label, desc, critical in KEYS:
        value = os.environ.get(env_var, "")
        keys.append({
            "env_var": env_var, "label": label, "description": desc,
            "critical": critical, "value": value,
            "has_value": bool(value),
        })
    return render(request, "system_config/recovery_keys.html", {
        "keys": keys,
    })


@login_required
@user_passes_test(_is_superuser)
def recovery_keys_download_env(request):
    """Devolve as variáveis críticas como .env file para download."""
    lines = [
        "# ════════════════════════════════════════════════════════════",
        "# Léguas Franzinas — Recovery Keys",
        "# Exportado de /system/recovery-keys/ — guardar em local seguro",
        "# ════════════════════════════════════════════════════════════",
        "",
    ]
    for env_var, label, _desc, _critical in KEYS:
        value = os.environ.get(env_var, "")
        if not value:
            continue
        lines.append(f"# {label}")
        lines.append(f"{env_var}={value}")
        lines.append("")
    body = "\n".join(lines)
    response = HttpResponse(body, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = (
        'attachment; filename="recovery_keys.txt"'
    )
    return response
