#!/usr/bin/env python3
"""
Script otimizado para corrigir problemas de linting nos arquivos principais.
"""

import subprocess
import sys
from pathlib import Path


def run_formatters():
    """Executa os formatadores de código."""

    print("=" * 70)
    print("🔧 CORREÇÃO AUTOMÁTICA DE CÓDIGO")
    print("=" * 70)

    commands = [
        {
            "name": "1. Removendo imports não utilizados",
            "cmd": (
                "autoflake --in-place --remove-all-unused-imports "
                "--remove-unused-variables --recursive "
                "--exclude=migrations,staticfiles,media,.venv,__pycache__,files,debug_files "
                "--ignore-init-module-imports "
                "core/ customauth/ drivers_app/ fleet_management/ "
                "pricing/ route_allocation/ orders_manager/ analytics/ "
                "settlements/ accounting/ converter/ system_config/ "
                "paack_dashboard/ ordersmanager_paack/ manualorders_paack/ "
                "send_paack_reports/ management/"
            ),
        },
        {
            "name": "2. Organizando imports (isort)",
            "cmd": (
                "isort . "
                "--skip migrations --skip .venv --skip staticfiles "
                "--skip media --skip files --skip debug_files "
                "--skip __pycache__ --skip wppconnect-chatwoot-bridge "
                "--profile black --line-length 88"
            ),
        },
        {
            "name": "3. Formatando código (Black)",
            "cmd": (
                "black . "
                '--exclude "(migrations|\\.venv|staticfiles|media|'
                '__pycache__|files|debug_files|wppconnect-chatwoot-bridge)" '
                "--line-length 88"
            ),
        },
        {
            "name": "4. Correções PEP8 (autopep8)",
            "cmd": (
                "autopep8 --in-place --aggressive --aggressive "
                "--recursive --exclude=migrations,staticfiles,media,"
                ".venv,__pycache__,files,debug_files "
                "core/ customauth/ drivers_app/ fleet_management/ "
                "pricing/ route_allocation/ orders_manager/ analytics/ "
                "settlements/ accounting/ converter/ system_config/"
            ),
        },
    ]

    for cmd_info in commands:
        print(f"\n{cmd_info['name']}...")
        result = subprocess.run(
            cmd_info["cmd"], shell=True, capture_output=True, text=True
        )

        if result.returncode == 0:
            print("✅ Concluído")
            if result.stdout and len(result.stdout) < 500:
                print(result.stdout)
        else:
            print(f"⚠️  Aviso: {result.stderr[:200] if result.stderr else 'OK'}")

    print("\n" + "=" * 70)
    print("✅ FORMATAÇÃO CONCLUÍDA!")
    print("=" * 70)
    print("\nPróximos passos:")
    print("1. Recarregue o VS Code (Ctrl+Shift+P → Reload Window)")
    print("2. Verifique o painel Problems")
    print()


if __name__ == "__main__":
    run_formatters()
