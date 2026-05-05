#!/bin/bash
# ════════════════════════════════════════════════════════════════════
# Léguas Franzinas — Production entrypoint
# ════════════════════════════════════════════════════════════════════
# Executa em ordem:
#   1. Espera DB ficar pronto
#   2. Migrations
#   3. collectstatic (a primeira vez ou quando STATIC_VERSION muda)
#   4. Cria superuser admin se DJANGO_SUPERUSER_* env vars definidas
#   5. Arranca processo passado (gunicorn, celery worker, celery beat)
# ════════════════════════════════════════════════════════════════════
set -e

cd /app

# ── Cores para logs ──────────────────────────────────────────────────
G='\033[0;32m'  # green
Y='\033[1;33m'  # yellow
R='\033[0;31m'  # red
N='\033[0m'     # no color

log_info()  { echo -e "${G}[entrypoint]${N} $1"; }
log_warn()  { echo -e "${Y}[entrypoint]${N} $1"; }
log_error() { echo -e "${R}[entrypoint]${N} $1"; }

# ── Detectar role do container (web | celery_worker | celery_beat) ───
ROLE="${ROLE:-web}"
log_info "Iniciando container com role=${ROLE}"

# ── Aguardar DB ──────────────────────────────────────────────────────
DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-3306}"
log_info "A aguardar BD em ${DB_HOST}:${DB_PORT}…"
RETRIES=60
until python -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
try:
    s.connect(('${DB_HOST}', ${DB_PORT}))
    s.close()
    exit(0)
except Exception:
    exit(1)
" 2>/dev/null; do
    RETRIES=$((RETRIES - 1))
    if [ $RETRIES -le 0 ]; then
        log_error "BD não respondeu em 60s"; exit 1
    fi
    sleep 1
done
log_info "BD acessível ✓"

# ── Aguardar Redis ───────────────────────────────────────────────────
REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"
log_info "A aguardar Redis em ${REDIS_HOST}:${REDIS_PORT}…"
RETRIES=30
until python -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
try:
    s.connect(('${REDIS_HOST}', ${REDIS_PORT}))
    s.close()
    exit(0)
except Exception:
    exit(1)
" 2>/dev/null; do
    RETRIES=$((RETRIES - 1))
    if [ $RETRIES -le 0 ]; then
        log_error "Redis não respondeu em 30s"; exit 1
    fi
    sleep 1
done
log_info "Redis acessível ✓"

# ── Tarefas só no container web (uma vez por deploy) ─────────────────
if [ "${ROLE}" = "web" ]; then
    log_info "Aplicar migrations…"
    python manage.py migrate --noinput

    log_info "Collectstatic…"
    # --noinput sem --clear (preserva ficheiros pré-existentes caso o
    # volume venha de instalação anterior — evita PermissionError).
    python manage.py collectstatic --noinput || \
        log_warn "Collectstatic falhou (não fatal — alguns ficheiros podem precisar de actualização manual)"

    # ── Auto-criar superuser se variáveis definidas ──────────────────
    # Útil em primeira instalação; ignora se user já existe.
    if [ -n "${DJANGO_SUPERUSER_USERNAME}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD}" ]; then
        log_info "A garantir superuser '${DJANGO_SUPERUSER_USERNAME}'…"
        python manage.py shell -c "
from django.contrib.auth import get_user_model
U = get_user_model()
u = '${DJANGO_SUPERUSER_USERNAME}'
e = '${DJANGO_SUPERUSER_EMAIL:-admin@example.com}'
p = '${DJANGO_SUPERUSER_PASSWORD}'
if not U.objects.filter(username=u).exists():
    U.objects.create_superuser(u, e, p)
    print(f'[superuser] {u} criado')
else:
    print(f'[superuser] {u} já existe (ignorado)')
" || log_warn "Falha a criar superuser (não fatal)"
    fi

    # ── Garantir partner CAINIAO existe (idempotente) ────────────────
    log_info "A garantir partners iniciais…"
    python manage.py create_initial_partners 2>/dev/null \
        || log_warn "create_initial_partners não rodou (não fatal)"
fi

log_info "Tudo pronto. Arranca: $@"
exec "$@"
