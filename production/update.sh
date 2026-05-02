#!/bin/bash
# ════════════════════════════════════════════════════════════════════
# Léguas Franzinas — Update script
# ════════════════════════════════════════════════════════════════════
# Atualiza para a versão mais recente sem perder dados.
#
# Uso:
#   ./update.sh                  # update normal
#   ./update.sh --no-backup      # skip backup pré-update (mais rápido)
# ════════════════════════════════════════════════════════════════════
set -e

cd "$(dirname "${BASH_SOURCE[0]}")"
G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'; N='\033[0m'
log()  { echo -e "${G}[update]${N} $1"; }
warn() { echo -e "${Y}[update]${N} $1"; }
err()  { echo -e "${R}[update]${N} $1"; }

# ── 1. Backup pré-update (recomendado) ───────────────────────────────
if [ "$1" != "--no-backup" ]; then
    log "Backup pré-update…"
    ./backup.sh || { err "Backup falhou. Aborta. Use --no-backup para forçar."; exit 1; }
fi

# ── 2. Pull código (se for git repo) ─────────────────────────────────
if [ -d ../.git ]; then
    log "git pull origin main…"
    cd .. && git pull origin main && cd production
fi

# ── 3. Rebuild imagem ────────────────────────────────────────────────
log "A reconstruir imagem…"
docker compose build web

# ── 4. Aplicar migrations e restart ──────────────────────────────────
log "A aplicar migrations…"
docker compose run --rm web python manage.py migrate --noinput

log "A reiniciar serviços…"
docker compose up -d

log "A aguardar app ficar pronta…"
for i in {1..30}; do
    if docker compose exec -T web curl -fsS http://localhost:8000/health/ &>/dev/null; then
        log "App OK ✓"; exit 0
    fi
    sleep 3
done
err "App não respondeu em 90s. Verificar 'docker compose logs web'"
exit 1
