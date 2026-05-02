#!/usr/bin/env python
"""
Script para sincronização manual da integração Delnext.
Usa o comando management sync_delnext via Docker.

Uso:
    python sync_delnext_manual.py                           # Sincronizar último dia útil
    python sync_delnext_manual.py --date 2026-02-27        # Data específica
    python sync_delnext_manual.py --zone VianaCastelo      # Zona específica
    python sync_delnext_manual.py --dry-run                # Teste sem salvar
"""

import argparse
import subprocess
import sys
from datetime import datetime, timedelta


def get_last_weekday():
    """Retorna o último dia útil (segunda a sexta)"""
    today = datetime.now()
    # Se hoje é segunda (0), voltar para sexta (3 dias atrás)
    # Se outro dia da semana, voltar 1 dia
    if today.weekday() == 0:  # Segunda
        last_weekday = today - timedelta(days=3)
    elif today.weekday() == 6:  # Domingo
        last_weekday = today - timedelta(days=2)
    else:
        last_weekday = today - timedelta(days=1)
    
    return last_weekday.strftime("%Y-%m-%d")


def run_sync(date=None, zone=None, dry_run=False):
    """Executa sincronização Delnext via Docker"""
    
    # Construir comando
    cmd = ["docker", "exec", "leguas_web", "python", "manage.py", "sync_delnext"]
    
    if date:
        cmd.extend(["--date", date])
    
    if zone:
        cmd.extend(["--zone", zone])
    
    if dry_run:
        cmd.append("--dry-run")
    
    # Mostrar comando
    print(f"\n🚀 Executando: {' '.join(cmd)}\n")
    print("=" * 80)
    
    # Executar
    try:
        result = subprocess.run(cmd, check=True, text=True)
        print("=" * 80)
        print("\n✅ Sincronização concluída com sucesso!")
        return result.returncode
    except subprocess.CalledProcessError as e:
        print("=" * 80)
        print(f"\n❌ Erro na sincronização: {e}")
        return e.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Sincronizar pedidos da Delnext",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  
  # Sincronizar último dia útil (padrão)
  python sync_delnext_manual.py
  
  # Sincronizar data específica
  python sync_delnext_manual.py --date 2026-02-27
  
  # Sincronizar zona específica
  python sync_delnext_manual.py --zone "VianaCastelo"
  
  # Teste sem salvar no banco
  python sync_delnext_manual.py --dry-run
  
  # Combinação
  python sync_delnext_manual.py --date 2026-02-27 --zone "2.0 Lisboa" --dry-run
        """
    )
    
    parser.add_argument(
        "--date",
        help="Data dos pedidos (formato: YYYY-MM-DD). Padrão: último dia útil"
    )
    
    parser.add_argument(
        "--zone",
        help="Filtrar por zona específica (ex: 'VianaCastelo', '2.0 Lisboa')"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Modo teste - não salva no banco de dados"
    )
    
    args = parser.parse_args()
    
    # Se não passou data, usar último dia útil
    date = args.date or get_last_weekday()
    
    # Mostrar informações
    print("\n" + "=" * 80)
    print("🔄 SINCRONIZAÇÃO DELNEXT - MANUAL")
    print("=" * 80)
    print(f"📅 Data: {date}")
    
    if args.zone:
        print(f"📍 Zona: {args.zone}")
    else:
        print(f"📍 Zona: Todas")
    
    if args.dry_run:
        print("⚠️  Modo: DRY-RUN (teste, não salva dados)")
    else:
        print("✅ Modo: PRODUÇÃO (salva no banco de dados)")
    
    # Executar
    return run_sync(date=date, zone=args.zone, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
