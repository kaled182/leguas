import json
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from system_config.utils import env_manager


class Command(BaseCommand):
    help = "Cria um backup completo da base de dados MySQL e ficheiros de media"

    def handle(self, *args, **options):
        backup_dir = Path(settings.BASE_DIR) / "database" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"manual_backup_{timestamp}.zip"
        filepath = backup_dir / filename

        db_conf = settings.DATABASES["default"]
        db_name = db_conf.get("NAME", "")
        db_user = db_conf.get("USER", "")
        db_host = db_conf.get("HOST", "")
        db_port = str(db_conf.get("PORT", "3306"))
        db_pass = db_conf.get("PASSWORD", "")

        if not all([db_name, db_user, db_host]):
            raise RuntimeError("Database configuration is incomplete.")

        self.stdout.write(f"Iniciando backup de {db_name} em {db_host}...")

        # Pass password via env var to avoid it appearing in process list
        env = os.environ.copy()
        if db_pass:
            env["MYSQL_PWD"] = str(db_pass)

        with tempfile.TemporaryDirectory(dir=backup_dir) as temp_dir:
            temp_dir_path = Path(temp_dir)
            dump_path = temp_dir_path / f"mysql_backup_{timestamp}.sql"
            metadata_path = temp_dir_path / f"mysql_backup_{timestamp}.config.json"

            cmd = [
                "mysqldump",
                f"--host={db_host}",
                f"--port={db_port}",
                f"--user={db_user}",
                "--single-transaction",
                "--routines",
                "--triggers",
                "--add-drop-table",
                "--default-character-set=utf8mb4",
                db_name,
            ]

            try:
                with dump_path.open("w", encoding="utf-8") as f:
                    result = subprocess.run(
                        cmd,
                        env=env,
                        check=True,
                        stdout=f,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
            except FileNotFoundError as exc:
                raise RuntimeError(
                    "O comando 'mysqldump' não foi encontrado. "
                    "Instale 'default-mysql-client' no container do backend."
                ) from exc
            except subprocess.CalledProcessError as exc:
                stderr = exc.stderr.strip() if exc.stderr else ""
                raise RuntimeError(f"Erro no mysqldump: {stderr}") from exc

            # Metadata snapshot
            config_keys = [
                "SECRET_KEY", "DEBUG", "DB_HOST", "DB_PORT", "DB_NAME",
                "DB_USER", "REDIS_URL", "BACKUP_RETENTION_DAYS", "BACKUP_RETENTION_COUNT",
            ]
            config_snapshot = env_manager.read_values(config_keys)
            env_payload = ""
            if env_manager.ENV_PATH.exists():
                env_payload = env_manager.ENV_PATH.read_text(encoding="utf-8")

            metadata = {
                "backup_file": filename,
                "created_at": datetime.now().isoformat(),
                "db_engine": "mysql",
                "app_version": os.getenv("APP_VERSION", "dev"),
                "env_file": env_payload,
                "configuration": config_snapshot,
            }
            metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

            # Encrypt with AES zip
            values = env_manager.read_values(["BACKUP_ZIP_PASSWORD"])
            password = values.get("BACKUP_ZIP_PASSWORD", "").strip()
            if len(password) < 8:
                raise RuntimeError(
                    "BACKUP_ZIP_PASSWORD deve ter pelo menos 8 caracteres."
                )

            try:
                import pyzipper
            except ImportError as exc:
                raise RuntimeError(
                    "pyzipper é necessário para backups cifrados. "
                    "Execute: pip install pyzipper"
                ) from exc

            with pyzipper.AESZipFile(
                filepath,
                "w",
                compression=pyzipper.ZIP_DEFLATED,
                encryption=pyzipper.WZ_AES,
            ) as zipf:
                zipf.setpassword(password.encode("utf-8"))

                # Database dump + metadata
                zipf.write(dump_path, dump_path.name)
                zipf.write(metadata_path, metadata_path.name)

                # Media files (fotos, PDFs, anexos, etc.)
                media_root = Path(settings.MEDIA_ROOT)
                if media_root.exists():
                    media_files = [
                        p for p in media_root.rglob("*") if p.is_file()
                    ]
                    self.stdout.write(
                        f"A incluir {len(media_files)} ficheiro(s) de media..."
                    )
                    for media_file in media_files:
                        archive_name = "media/" + str(
                            media_file.relative_to(media_root)
                        ).replace("\\", "/")
                        zipf.write(media_file, archive_name)

        size_mb = filepath.stat().st_size / (1024 * 1024)
        self.stdout.write(
            self.style.SUCCESS(f"Backup criado com sucesso: {filename}")
        )
        self.stdout.write(f"Tamanho: {size_mb:.2f} MB")
        return filename
