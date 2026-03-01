#!/usr/bin/env python3
"""
Script para corrigir TODOS os problemas de linting automaticamente.
Corrige: linhas longas, trailing whitespace, espaçamento entre funções, etc.
"""

import re
import subprocess
from pathlib import Path


def run_command(cmd):
    """Executa comando e retorna resultado."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout, result.stderr


def fix_trailing_whitespace(file_path):
    """Remove trailing whitespace de todas as linhas."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Remove trailing whitespace
    lines = content.split("\n")
    fixed_lines = [line.rstrip() for line in lines]

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(fixed_lines))


def fix_function_spacing(file_path):
    """Garante 2 linhas em branco entre funções de nível superior."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Regex para encontrar funções/classes de nível superior
    # Adiciona 2 linhas antes de def/class que não estão indentadas
    pattern = r"\n(def |class |@\w+\n*def |@\w+\n*class )"

    # Primeiro, normaliza: remove linhas em branco extras
    lines = content.split("\n")
    normalized = []
    prev_blank = False

    for i, line in enumerate(lines):
        is_blank = line.strip() == ""

        # Detecta início de função/classe
        is_function = (
            line.startswith("def ") or line.startswith("class ") or line.startswith("@")
        )

        # Se é função/classe de nível superior, garante 2 linhas antes
        if is_function and i > 0 and not lines[i - 1].startswith(" "):
            # Conta quantas linhas em branco existem antes
            blank_count = 0
            j = len(normalized) - 1
            while j >= 0 and normalized[j].strip() == "":
                blank_count += 1
                j -= 1

            # Remove linhas em branco extras
            while blank_count > 0:
                if normalized and normalized[-1].strip() == "":
                    normalized.pop()
                    blank_count -= 1
                else:
                    break

            # Adiciona exatamente 2 linhas em branco
            if normalized:  # Não adiciona no início do arquivo
                normalized.append("")
                normalized.append("")

        normalized.append(line)
        prev_blank = is_blank

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(normalized))


def fix_long_lines_in_file(file_path):
    """
    Quebra linhas muito longas de forma inteligente.
    Usa Black para fazer isso automaticamente.
    """
    # Black já foi executado, mas vamos garantir
    subprocess.run(f'black "{file_path}"', shell=True, capture_output=True)


def fix_all_issues_in_file(file_path):
    """Aplica todas as correções em um arquivo."""
    print(f"Corrigindo: {file_path}")

    # 1. Black (formata e quebra linhas longas)
    subprocess.run(f'black "{file_path}"', shell=True, capture_output=True)

    # 2. Remove trailing whitespace
    fix_trailing_whitespace(file_path)

    # 3. Corrige espaçamento entre funções
    fix_function_spacing(file_path)

    # 4. Autopep8 para correções PEP8
    subprocess.run(
        f'autopep8 --in-place --aggressive --aggressive "{file_path}"',
        shell=True,
        capture_output=True,
    )


def main():
    print("=" * 70)
    print("🔧 CORREÇÃO COMPLETA DE TODOS OS PROBLEMAS DE LINTING")
    print("=" * 70)

    # Encontra todos os arquivos Python
    root = Path(".")
    python_files = []

    exclude_dirs = {
        "migrations",
        ".venv",
        "venv",
        "env",
        "staticfiles",
        "media",
        "__pycache__",
        "node_modules",
        ".git",
    }

    for py_file in root.rglob("*.py"):
        # Verifica se está em diretório excluído
        if any(exc in py_file.parts for exc in exclude_dirs):
            continue
        python_files.append(py_file)

    print(f"\n📄 Encontrados {len(python_files)} arquivos Python")
    print("\n🔧 Aplicando correções...\n")

    for i, file_path in enumerate(python_files, 1):
        print(f"[{i}/{len(python_files)}] {file_path}")
        try:
            fix_all_issues_in_file(str(file_path))
        except Exception as e:
            print(f"   ⚠️  Erro: {e}")

    print("\n" + "=" * 70)
    print("✅ TODAS AS CORREÇÕES APLICADAS!")
    print("=" * 70)

    # Executar Black final para garantir consistência
    print("\n🎨 Executando Black final...")
    subprocess.run(
        'black . --exclude "(migrations|\\.venv|staticfiles|media)"',
        shell=True,
        capture_output=True,
    )

    # Executar isort final
    print("📑 Organizando imports final...")
    subprocess.run(
        "isort . --skip migrations --skip .venv --profile black",
        shell=True,
        capture_output=True,
    )

    print("\n✅ CONCLUÍDO!")
    print("\nPróximos passos:")
    print("1. Recarregue o VS Code (Ctrl+Shift+P → Reload Window)")
    print("2. Verifique o painel Problems")
    print("3. Execute: docker-compose restart web")
    print()


if __name__ == "__main__":
    main()
