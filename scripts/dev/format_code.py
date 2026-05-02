#!/usr/bin/env python3
"""
Script de formatação automática de código Python.
Remove imports não utilizados e formata código conforme PEP8.
"""

import subprocess


def run_command(cmd, description):
    """Executa um comando e reporta o resultado."""
    print(f"\n{'=' * 60}")
    print(f"🔧 {description}")
    print(f"{'=' * 60}")

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"✅ Sucesso!")
        if result.stdout:
            print(result.stdout)
    else:
        print(f"⚠️  Aviso:")
        if result.stderr:
            print(result.stderr)
        if result.stdout:
            print(result.stdout)

    return result.returncode


def main():
    print("\n" + "=" * 60)
    print("🧹 FORMATAÇÃO AUTOMÁTICA DE CÓDIGO")
    print("=" * 60)

    # Diretórios a excluir
    exclude_dirs = "migrations,staticfiles,media,.venv,venv,__pycache__"

    # 1. Remover imports não utilizados
    autoflake_cmd = (
        f"autoflake --in-place --remove-all-unused-imports "
        f"--remove-unused-variables --recursive "
        f"--exclude={exclude_dirs} ."
    )
    run_command(autoflake_cmd, "Removendo imports não utilizados")

    # 2. Organizar imports
    isort_cmd = (
        f"isort . --skip migrations --skip .venv --skip staticfiles "
        f"--skip media --profile black --line-length 79"
    )
    run_command(isort_cmd, "Organizando imports")

    # 3. Formatar código com Black
    black_cmd = (
        f"black --line-length 79 "
        f"--exclude '(migrations|\\.venv|staticfiles|media|__pycache__)' ."
    )
    run_command(black_cmd, "Formatando código com Black")

    print("\n" + "=" * 60)
    print("✅ FORMATAÇÃO CONCLUÍDA!")
    print("=" * 60)
    print("\nPróximos passos:")
    print("1. Verifique as mudanças: git diff")
    print("2. Teste a aplicação: docker-compose restart web")
    print("3. Commit: git add . && git commit -m 'Format code with Black'")
    print()


if __name__ == "__main__":
    main()
