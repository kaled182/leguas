#!/bin/bash
# ════════════════════════════════════════════════════════════════════
# Léguas Franzinas — Backup script (DB + media)
# ════════════════════════════════════════════════════════════════════
# Faz dump de MySQL + tar do volume media, com timestamp e compressão.
# Retém últimos N backups (default 30) — apaga mais antigos.
#
# Uso:
#   ./backup.sh                      # backup on-demand
#   ./backup.sh --upload             # + upload Google Drive (se config)
#
# Cron (diário às 03h):
#   0 3 * * * cd /path/to/production && ./backup.sh >> backup.log 2>&1
# ════════════════════════════════════════════════════════════════════
set -e

# ── Config ───────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Carregar .env
if [ -f .env ]; then
    set -a; source .env; set +a
else
    echo "[backup] ERRO: .env não encontrado em $SCRIPT_DIR"
    exit 1
fi

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# ── Cores para logs ──────────────────────────────────────────────────
G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'; N='\033[0m'
log()  { echo -e "${G}[backup ${TIMESTAMP}]${N} $1"; }
warn() { echo -e "${Y}[backup ${TIMESTAMP}]${N} $1"; }
err()  { echo -e "${R}[backup ${TIMESTAMP}]${N} $1"; }

# ── 1. Dump MySQL ────────────────────────────────────────────────────
DB_FILE="$BACKUP_DIR/db_${TIMESTAMP}.sql.gz"
log "A fazer dump da BD '${DB_NAME}'…"
docker compose exec -T db sh -c "
    mysqldump --single-transaction --routines --triggers --events \
              -u${DB_USER} -p${DB_PASSWORD} ${DB_NAME}
" 2>/dev/null | gzip > "$DB_FILE"

if [ ! -s "$DB_FILE" ]; then
    err "Dump BD falhou (ficheiro vazio)"; exit 1
fi
DB_SIZE=$(du -h "$DB_FILE" | cut -f1)
log "BD dump: $DB_FILE ($DB_SIZE)"

# ── 2. Backup volume media ───────────────────────────────────────────
MEDIA_FILE="$BACKUP_DIR/media_${TIMESTAMP}.tar.gz"
log "A fazer backup do volume media…"
docker run --rm \
    -v "$(docker compose ps -q web | head -1 | xargs -I {} docker inspect {} --format '{{ range .Mounts }}{{ if eq .Destination "/app/media" }}{{ .Name }}{{ end }}{{ end }}'):/source:ro" \
    -v "$(pwd)/$BACKUP_DIR:/dest" \
    alpine sh -c "cd /source && tar czf /dest/media_${TIMESTAMP}.tar.gz ." 2>/dev/null

if [ ! -s "$MEDIA_FILE" ]; then
    warn "Media backup vazio (volume vazio?)"
else
    MEDIA_SIZE=$(du -h "$MEDIA_FILE" | cut -f1)
    log "Media backup: $MEDIA_FILE ($MEDIA_SIZE)"
fi

# ── 3. Checksums ─────────────────────────────────────────────────────
SUM_FILE="$BACKUP_DIR/checksums_${TIMESTAMP}.sha256"
( cd "$BACKUP_DIR" && sha256sum "db_${TIMESTAMP}.sql.gz" "media_${TIMESTAMP}.tar.gz" 2>/dev/null > "checksums_${TIMESTAMP}.sha256" )
log "Checksums: $SUM_FILE"

# ── 4. Retenção: apagar backups > RETENTION_DAYS ─────────────────────
log "A limpar backups com mais de ${RETENTION_DAYS} dias…"
DELETED=$(find "$BACKUP_DIR" -name "db_*.sql.gz" -mtime +${RETENTION_DAYS} -delete -print 2>/dev/null | wc -l)
find "$BACKUP_DIR" -name "media_*.tar.gz" -mtime +${RETENTION_DAYS} -delete 2>/dev/null
find "$BACKUP_DIR" -name "checksums_*.sha256" -mtime +${RETENTION_DAYS} -delete 2>/dev/null
if [ "$DELETED" -gt 0 ]; then
    log "Apagados $DELETED backups antigos"
fi

# ── 5. Upload Google Drive (opcional) ────────────────────────────────
if [ "$1" = "--upload" ]; then
    log "Upload Google Drive…"
    docker compose exec -T web python manage.py shell -c "
from system_config.api_views import _upload_to_gdrive
try:
    r1 = _upload_to_gdrive('$DB_FILE')
    r2 = _upload_to_gdrive('$MEDIA_FILE')
    print(f'GDrive: db={r1}, media={r2}')
except Exception as e:
    print(f'Falha upload: {e}')
" 2>&1 | tail -5
fi

# ── Resumo ───────────────────────────────────────────────────────────
TOTAL_BACKUPS=$(ls "$BACKUP_DIR"/db_*.sql.gz 2>/dev/null | wc -l)
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
log "✅ Backup concluído. Total: ${TOTAL_BACKUPS} backups (${TOTAL_SIZE})"
