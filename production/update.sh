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
# web faz o build da imagem leguas-web:production; celery_worker e
# celery_beat partilham essa mesma imagem (instala novas deps como shapely).
log "A reconstruir imagem…"
docker compose build web

# ── 4. Aplicar migrations (já com a imagem nova) ─────────────────────
log "A aplicar migrations…"
docker compose run --rm web python manage.py migrate --noinput

# ── 5. Recriar serviços de app com a imagem nova ─────────────────────
# Sobe tudo e força a recriação de web + celery (worker/beat) para
# garantirem o código/deps novos, SEM reiniciar db/redis.
log "A reiniciar serviços…"
docker compose up -d
docker compose up -d --force-recreate --no-deps web celery_worker celery_beat

log "A aguardar app ficar pronta…"
for i in {1..30}; do
    if docker compose exec -T web curl -fsS http://localhost:8000/health/ &>/dev/null; then
        log "App OK ✓"; exit 0
    fi
    sleep 3
done
err "App não respondeu em 90s. Verificar 'docker compose logs web'"
exit 1
