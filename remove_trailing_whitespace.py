#!/usr/bin/env python3
"""
Script ULTRA-SIMPLES para remover trailing whitespace.
Não usa ferramentas externas, apenas Python puro.
"""

from pathlib import Path


def clean_file(file_path):
    """Remove trailing whitespace de um arquivo."""
    try:
        # Ler arquivo
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            original = f.read()

        # Processar linha por linha
        lines = original.split("\n")
        cleaned_lines = [line.rstrip() for line in lines]

        # Reconstruir arquivo
        cleaned = "\n".join(cleaned_lines)

        # Garantir final do arquivo com uma linha vazia
        if cleaned and not cleaned.endswith("\n"):
            cleaned += "\n"

        # Salvar apenas se houve mudança
        if cleaned != original:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(cleaned)
            return True

        return False
    except Exception as e:
        print(f"   ❌ Erro em {file_path}: {e}")
        return False


def main():
    print("=" * 70)
    print("🧹 LIMPEZA DE TRAILING WHITESPACE")
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
        "my_project",
        "orders_manager",
        "ordersmanager_paack",
        "paack_dashboard",
        "pricing",
        "route_allocation",
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
            if clean_file(file_path):
                total_cleaned += 1
                print(f"   ✅ {file_path.relative_to(base_path)}")

    print()
    print("=" * 70)
    print(f"✅ Concluído!")
    print(f"   Arquivos processados: {total_files}")
    print(f"   Arquivos limpos: {total_cleaned}")
    print("=" * 70)
    print()
    print("🔄 Agora RECARREGUE o VS Code:")
    print("   Ctrl + Shift + P → 'Reload Window'")
    print()


if __name__ == "__main__":
    main()
