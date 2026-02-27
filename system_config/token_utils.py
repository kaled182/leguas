from __future__ import annotations

import logging
import os
import re
import subprocess
import threading
from pathlib import Path
from typing import Iterable

from django.conf import settings

logger = logging.getLogger(__name__)

BASE_DIR = settings.BASE_DIR
DOCKER_COMPOSE_PATH = BASE_DIR / "docker-compose.yml"
ENV_FILES: tuple[Path, ...] = (
    BASE_DIR / ".env",
    BASE_DIR / ".env.docker",
)
OPTIONAL_ENV_FILES: tuple[Path, ...] = (
    BASE_DIR / ".env.docker.example",
)
ENV_KEYS = ("AUTHENTICATION_API_KEY", "EVOLUTION_API_KEY")
COMPOSE_KEYS = ("AUTHENTICATION_API_KEY", "TOKEN")


def _replace_env_line(content: str, key: str, value: str) -> tuple[str, int]:
    pattern = re.compile(rf"(^\s*{re.escape(key)}\s*=\s*)(\".*?\"|[^\r\n]*)", re.MULTILINE)

    def repl(match) -> str:
        prefix = match.group(1)
        original = match.group(2)
        quoted = original.startswith('"') and original.endswith('"')
        replacement = f'"{value}"' if quoted else value
        return prefix + replacement

    return pattern.subn(repl, content, count=1)


def _replace_compose_line(content: str, key: str, value: str) -> tuple[str, int]:
    pattern = re.compile(rf"(^\s*-\s*{re.escape(key)}=)[^\r\n]*", re.MULTILINE)
    def repl(match):
        prefix = match.group(1)
        return f"{prefix}{value}"

    return pattern.subn(repl, content, count=1)


def _update_file(path: Path, key_value_pairs: Iterable[tuple[str, str]], *, compose: bool = False) -> bool:
    if not path.exists():
        logger.debug("Skip missing file when propagating token: %s", path)
        return False

    original = path.read_text(encoding="utf-8")
    content = original
    total_replacements = 0

    for key, value in key_value_pairs:
        if compose:
            content, count = _replace_compose_line(content, key, value)
        else:
            content, count = _replace_env_line(content, key, value)
        total_replacements += count

    if total_replacements and content != original:
        path.write_text(content, encoding="utf-8")
        logger.info("Updated %s with new WhatsApp token", path.name)
        return True

    if total_replacements == 0:
        logger.debug("No token placeholders found in %s", path)
    return False


def _collect_restart_commands() -> list[str]:
    raw = os.getenv("WHATSAPP_RESTART_COMMANDS", "")
    commands = [snippet.strip() for snippet in raw.split(";") if snippet.strip()]
    return commands


def _run_restart_commands(commands: Iterable[str]) -> None:
    for command in commands:
        try:
            logger.info("Restarting service via command: %s", command)
            subprocess.run(command, shell=True, check=True)
        except subprocess.CalledProcessError as exc:
            logger.error("Restart command failed (%s): %s", exc.returncode, command, exc_info=True)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Unexpected error executing restart command: %s", command)


def propagate_whatsapp_token(token: str | None) -> dict[str, object]:
    result = {
        "updated_files": [],
        "restart_triggered": False,
    }
    if not token:
        logger.info("Propagation skipped because token is empty")
        return result

    updates: list[tuple[Path, bool]] = []

    compose_pairs = [(key, token) for key in COMPOSE_KEYS]
    updates.append((DOCKER_COMPOSE_PATH, _update_file(DOCKER_COMPOSE_PATH, compose_pairs, compose=True)))

    env_pairs = [(key, token) for key in ENV_KEYS]
    for env_path in ENV_FILES:
        updates.append((env_path, _update_file(env_path, env_pairs)))

    for env_path in OPTIONAL_ENV_FILES:
        updates.append((env_path, _update_file(env_path, env_pairs)))

    for path, changed in updates:
        if changed:
            display = path.relative_to(BASE_DIR)
            result["updated_files"].append(str(display))

    commands = _collect_restart_commands()
    if commands:
        thread = threading.Thread(target=_run_restart_commands, args=(commands,), daemon=True)
        thread.start()
        result["restart_triggered"] = True

    return result
