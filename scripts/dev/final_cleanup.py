#!/usr/bin/env python3
"""
Script final para eliminar todos os problemas de linting.
Foca em problemas específicos que ainda persistem.
"""

import os
import re
import subprocess
from pathlib import Path

# Diretórios do projeto (excluindo dependências)
PROJECT_DIRS = [
    "accounting",
    "analytics",
    "converter",
    "core",
    "customauth",
    "drivers_app",
    "fleet_management",
    "management",
    "manualorders_paack",
    "my_project",
    "orders_manager",
    "ordersmanager_paack",
    "paack_dashboard",
    "pricing",
    "route_allocation",
    "send_paack_reports",
    "settlements",
    "system_config",
]

# Arquivos Python na raiz
ROOT_FILES = [
    "manage.py",
    "configure_typebot.py",
    "fix_config_fields.py",
    "format_code.py",
    "test_csv_import.py",
    "test_dashboard.py",
    "test_maintenance_module.py",
    "test_maps.py",
    "test_orders_module.py",
    "test_pagination.py",
    "test_typebot_views.py",
    "test_typebot.py",
    "tmp_check_whatsapp.py",
    "validate_backend.py",
]


def fix_whitespace_issues(file_path):
    """
    Remove trailing whitespace e whitespace em linhas vazias.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        fixed_lines = []
        for line in lines:
            # Remove trailing whitespace (incluindo de linhas vazias)
            fixed_line = line.rstrip() + "\n" if line.strip() else "\n"
            fixed_lines.append(fixed_line)

        # Remove newlines extras no final do arquivo
        while (
            len(fixed_lines) > 1 and fixed_lines[-1] == "\n" and fixed_lines[-2] == "\n"
        ):
            fixed_lines.pop()

        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(fixed_lines)

        return True
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False


def apply_autopep8_aggressive(file_path):
    """
    Aplica autopep8 de forma ultra-agressiva.
    """
    try:
        cmd = [
            "autopep8",
            "--in-place",
            "--aggressive",
            "--aggressive",
            "--aggressive",
            "--max-line-length=88",
            str(file_path),
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=False)
        return True
    except Exception as e:
        print(f"   ❌ Erro autopep8: {e}")
        return False


def apply_black(file_path):
    """
    Aplica Black formatter.
    """
    try:
        cmd = ["black", "--line-length=88", "--quiet", str(file_path)]
        subprocess.run(cmd, capture_output=True, text=True, check=False)
        return True
    except Exception as e:
        print(f"   ❌ Erro black: {e}")
        return False


def process_file(file_path):
    """
    Processa um arquivo aplicando todas as correções.
    """
    print(f"   📄 {file_path}")

    # 1. Autopep8 ultra-agressivo primeiro
    apply_autopep8_aggressive(file_path)

    # 2. Remove todo trailing whitespace
    fix_whitespace_issues(file_path)

    # 3. Black para formatar linhas longas
    apply_black(file_path)

    # 4. Remove trailing whitespace novamente (Black pode adicionar)
    fix_whitespace_issues(file_path)


def main():
    print("=" * 70)
    print("🔧 LIMPEZA FINAL - ELIMINANDO TODOS OS PROBLEMAS")
    print("=" * 70)
    print()

    base_path = Path("/app")
    processed = 0

    # 1. Processar arquivos da raiz
    print("1️⃣  Processando arquivos da raiz...")
    for filename in ROOT_FILES:
        file_path = base_path / filename
        if file_path.exists():
            process_file(file_path)
            processed += 1

    # 2. Processar diretórios do projeto
    print("\n2️⃣  Processando diretórios do projeto...")
    for directory in PROJECT_DIRS:
        dir_path = base_path / directory
        if not dir_path.exists():
            continue

        print(f"\n📁 {directory}/")
        for file_path in dir_path.rglob("*.py"):
            # Pular migrations
            if "migrations" in file_path.parts:
                continue

            process_file(file_path)
            processed += 1

    print("\n" + "=" * 70)
    print(f"✅ CONCLUÍDO! {processed} arquivos processados")
    print("=" * 70)
    print()
    print("📋 Próximos passos:")
    print("   1. Recarregue o VS Code: Ctrl+Shift+P → 'Reload Window'")
    print("   2. Verifique o painel Problems (deve estar quase vazio)")
    print("   3. Teste a aplicação: docker-compose restart web")
    print()


if __name__ == "__main__":
    main()
