#!/usr/bin/env python3
"""
Script DEFINITIVO para remover trailing whitespace e limpar linhas vazias.
"""

from pathlib import Path
import sys


def clean_file_aggressive(file_path):
    """
    Remove TODOS os espaços em branco no final de linhas,
    incluindo linhas completamente vazias.
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        original_content = content

        # Processar linha por linha
        lines = content.splitlines()
        cleaned_lines = []

        for line in lines:
            # Remove TODOS os espaços/tabs do final da linha
            cleaned_line = line.rstrip(" \t\r")
            cleaned_lines.append(cleaned_line)

        # Reconstruir arquivo com \n no final de cada linha
        new_content = "\n".join(cleaned_lines)

        # Garantir que arquivo termina com \n
        if new_content and not new_content.endswith("\n"):
            new_content += "\n"

        # Salvar se houve mudança
        if new_content != original_content:
            with open(file_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(new_content)
            return True

        return False

    except Exception as e:
        print(f"   ❌ Erro em {file_path}: {e}")
        return False


def main():
    print("=" * 70)
    print("🧹 LIMPEZA AGRESSIVA DE LINHAS EM BRANCO")
    print("=" * 70)
    print()

    base_path = Path("/app")

    # Diretórios para processar
    dirs_to_process = [
        "accounting",
        "analytics",
        "converter",
        "core",
        "customauth",
        "drivers_app",
        "fleet_management",
        "management",
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

    total_files = 0
    total_cleaned = 0

    for directory in dirs_to_process:
        dir_path = base_path / directory
        if not dir_path.exists():
            continue

        print(f"📁 {directory}/")

        for file_path in dir_path.rglob("*.py"):
            # Pular migrations
            if "migrations" in file_path.parts:
                continue

            total_files += 1
            if clean_file_aggressive(file_path):
                total_cleaned += 1
                print(f"   ✅ {file_path.relative_to(base_path)}")

    print()
    print("=" * 70)
    print(f"✅ CONCLUÍDO!")
    print(f"   📊 Arquivos processados: {total_files}")
    print(f"   🧹 Arquivos limpos: {total_cleaned}")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
