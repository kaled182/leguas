"""Imprime as recovery keys actuais (BACKUP_ZIP_PASSWORD, etc.).

Uso:
    docker exec leguas_web python manage.py show_recovery_keys

Útil quando o operador perde o .recovery_keys.txt e precisa de obter
a BACKUP_ZIP_PASSWORD para restaurar um backup antigo.
"""
import os

from django.core.management.base import BaseCommand


KEYS_TO_SHOW = [
    ("DJANGO_SUPERUSER_USERNAME", "Admin user"),
    ("DJANGO_SUPERUSER_EMAIL", "Admin email"),
    ("DB_USER", "DB user"),
    ("DB_PASSWORD", "DB password"),
    ("DB_ROOT_PASSWORD", "DB root password"),
    ("SECRET_KEY", "Django SECRET_KEY (truncated)"),
    ("FERNET_KEY", "Fernet key (encriptação de tokens)"),
    ("BACKUP_ZIP_PASSWORD", "BACKUP ZIP password ★"),
    ("UPDATER_SECRET", "Updater secret"),
    ("WPPCONNECT_SECRET", "WPPConnect secret"),
    ("DOMAIN", "Domínio"),
    ("LETSENCRYPT_EMAIL", "Let's Encrypt email"),
]


class Command(BaseCommand):
    help = "Imprime as recovery keys (secrets) lidas do environment."

    def add_arguments(self, parser):
        parser.add_argument(
            "--mask", action="store_true",
            help="Mascara passwords (mostra só primeiros/últimos chars)",
        )

    def handle(self, *args, **opts):
        mask = opts["mask"]
        self.stdout.write(self.style.WARNING(
            "\n🔑 Recovery Keys — Léguas Franzinas\n"
            + "=" * 60 + "\n"
        ))
        for env_key, label in KEYS_TO_SHOW:
            value = os.environ.get(env_key, "")
            if not value:
                self.stdout.write(f"  {label:.<35} (não definido)")
                continue
            display = value
            if mask and len(value) > 12 and env_key not in (
                "DJANGO_SUPERUSER_USERNAME", "DB_USER",
                "DJANGO_SUPERUSER_EMAIL", "DOMAIN", "LETSENCRYPT_EMAIL",
            ):
                display = f"{value[:4]}…{value[-4:]} ({len(value)} chars)"
            star = "★ " if "BACKUP" in env_key else "  "
            self.stdout.write(f"{star}{label:.<35} {display}")
        self.stdout.write(self.style.WARNING(
            "\n" + "=" * 60 + "\n"
            "★ BACKUP_ZIP_PASSWORD: sem esta chave, backups antigos\n"
            "  ficam irrecuperáveis. Guarda num password manager.\n"
        ))
