import os
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Restaura um backup MySQL. CUIDADO: Apaga os dados atuais."

    def add_arguments(self, parser):
        parser.add_argument(
            "filename",
            type=str,
            help="Nome do arquivo .sql na pasta de backups",
        )

    def handle(self, *args, **options):
        filename = options["filename"]
        backup_dir = Path(settings.BASE_DIR) / "database" / "backups"
        backup_path = backup_dir / filename

        if not backup_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {backup_path}")

        if backup_path.suffix.lower() != ".sql":
            raise RuntimeError(
                f"Formato '{backup_path.suffix}' não suportado. "
                "Use .sql gerado pelo mysqldump."
            )

        db_conf = settings.DATABASES["default"]
        db_name = db_conf.get("NAME", "")
        db_user = db_conf.get("USER", "")
        db_host = db_conf.get("HOST", "")
        db_port = str(db_conf.get("PORT", "3306"))
        db_pass = db_conf.get("PASSWORD", "")

        if not all([db_name, db_user, db_host]):
            raise RuntimeError("Database configuration is incomplete.")

        env = os.environ.copy()
        if db_pass:
            env["MYSQL_PWD"] = str(db_pass)

        cmd = [
            "mysql",
            f"--host={db_host}",
            f"--port={db_port}",
            f"--user={db_user}",
            "--default-character-set=utf8mb4",
            db_name,
        ]

        try:
            self.stdout.write(f"Restaurando {filename} em {db_name}...")
            with backup_path.open("r", encoding="utf-8") as f:
                subprocess.run(cmd, env=env, check=True, stdin=f, text=True)
            self.stdout.write(self.style.SUCCESS("Restauração concluída!"))
        except FileNotFoundError as exc:
            raise RuntimeError(
                "O comando 'mysql' não foi encontrado. "
                "Instale 'default-mysql-client' no container do backend."
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"Erro no restore: {exc}") from exc
