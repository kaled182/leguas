#!/bin/bash
# ════════════════════════════════════════════════════════════════════
# Léguas Franzinas — Production Install Wizard
# ════════════════════════════════════════════════════════════════════
# Para Linux (Ubuntu/Debian recomendado).
#
# Uso:
#   chmod +x install.sh
#   ./install.sh
#
# Faz:
#   1. Verifica Docker + Docker Compose instalados (instala se não)
#   2. Pede inputs interactivamente (domínio, DB pass, admin user/pass…)
#   3. Gera .env baseado em .env.example
#   4. Build da imagem
#   5. Sobe stack
#   6. Cria superuser
#   7. Mostra URL final + próximos passos
# ════════════════════════════════════════════════════════════════════
set -e

# Cores
G='\033[0;32m'; B='\033[0;34m'; Y='\033[1;33m'; R='\033[0;31m'; N='\033[0m'
log()    { echo -e "${G}[install]${N} $1"; }
ask()    { echo -en "${B}[?]${N} $1"; }
warn()   { echo -e "${Y}[!]${N} $1"; }
err()    { echo -e "${R}[ERR]${N} $1"; }

cd "$(dirname "${BASH_SOURCE[0]}")"

# ── Banner ───────────────────────────────────────────────────────────
cat << 'EOF'

  _                 _
 | |   ___  __ _ _ _| |__ _ ___
 | |__/ -_)/ _` | || / _` (_-<
 |____\___|\__, |\_,_\__,_/__/
           |___/  Franzinas — Production Installer

EOF

# ── 1. Pré-requisitos ────────────────────────────────────────────────
log "A verificar pré-requisitos…"

if ! command -v docker &> /dev/null; then
    warn "Docker não encontrado."
    ask "Instalar Docker agora? (s/N): "; read -r INSTALL_DOCKER
    if [[ "$INSTALL_DOCKER" =~ ^[sS]$ ]]; then
        curl -fsSL https://get.docker.com | sh
        sudo usermod -aG docker "$USER"
        warn "Docker instalado. Faz logout/login e re-executa ./install.sh"
        exit 0
    else
        err "Docker é obrigatório. Aborta."; exit 1
    fi
fi

if ! docker compose version &> /dev/null; then
    err "Docker Compose v2 não encontrado. Atualiza Docker Desktop ou instala 'docker-compose-plugin'."
    exit 1
fi
log "Docker $(docker --version | awk '{print $3}' | tr -d ',') ✓"
log "Docker Compose $(docker compose version --short) ✓"

# ── 2. Inputs interactivos ───────────────────────────────────────────
log "Vou pedir alguns dados de configuração. Premir Enter aceita o default."
echo

ask "Domínio (vazio=HTTP-only no IP do servidor): "; read -r DOMAIN_INPUT
DOMAIN="${DOMAIN_INPUT:-:80}"

if [ "$DOMAIN" != ":80" ]; then
    ask "Email para Let's Encrypt [admin@$DOMAIN]: "; read -r LE_EMAIL
    LE_EMAIL="${LE_EMAIL:-admin@$DOMAIN}"
else
    LE_EMAIL="internal"
fi

ask "Username admin [admin]: "; read -r ADMIN_USER
ADMIN_USER="${ADMIN_USER:-admin}"

while true; do
    ask "Password admin (mín. 8 chars): "
    read -rs ADMIN_PASS; echo
    if [ ${#ADMIN_PASS} -ge 8 ]; then break; fi
    warn "Password muito curta."
done

ask "Email admin [admin@leguasfranzinas.pt]: "; read -r ADMIN_EMAIL
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@leguasfranzinas.pt}"

# Auto-gera secrets
SECRET_KEY=$(docker run --rm python:3.11-alpine python -c "import secrets; print(secrets.token_urlsafe(50))")
DB_PASSWORD=$(openssl rand -hex 24 2>/dev/null || head -c 32 /dev/urandom | base64 | tr -d "=+/" | head -c 32)
DB_ROOT_PASSWORD=$(openssl rand -hex 24 2>/dev/null || head -c 32 /dev/urandom | base64 | tr -d "=+/" | head -c 32)
WPP_SECRET=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | base64 | tr -d "=+/" | head -c 64)
BACKUP_PASS=$(openssl rand -hex 16 2>/dev/null || head -c 24 /dev/urandom | base64 | tr -d "=+/" | head -c 24)
UPDATER_SECRET=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | base64 | tr -d "=+/" | head -c 64)

# Gera Fernet key (precisa Python cryptography)
FERNET_KEY=$(docker run --rm python:3.11-alpine sh -c "pip install -q cryptography && python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'")

# ALLOWED_HOSTS
if [ "$DOMAIN" = ":80" ]; then
    ALLOWED_HOSTS="localhost,127.0.0.1,$(hostname -I 2>/dev/null | awk '{print $1}')"
else
    ALLOWED_HOSTS="localhost,127.0.0.1,$DOMAIN,www.$DOMAIN"
fi

# ── 3. Gerar .env ────────────────────────────────────────────────────
log "A gerar .env…"
if [ -f .env ]; then
    warn ".env já existe. Backup em .env.bak"
    cp .env .env.bak
fi

cat > .env <<EOF
# Gerado por install.sh em $(date)
# ─────────────────────── DJANGO ─────────────────────────
SECRET_KEY=$SECRET_KEY
DEBUG=False
ALLOWED_HOSTS=$ALLOWED_HOSTS
CSRF_TRUSTED_ORIGINS=http://localhost,http://$DOMAIN,https://$DOMAIN
FORCE_HTTPS=$([ "$DOMAIN" != ":80" ] && echo "True" || echo "False")
FERNET_KEY=$FERNET_KEY

# ─────────────────────── BD ─────────────────────────────
DB_NAME=leguas_db
DB_USER=leguas_user
DB_PASSWORD=$DB_PASSWORD
DB_ROOT_PASSWORD=$DB_ROOT_PASSWORD
DB_HOST=db
DB_PORT=3306

# ─────────────────────── REDIS ──────────────────────────
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# ─────────────────────── ADMIN ──────────────────────────
DJANGO_SUPERUSER_USERNAME=$ADMIN_USER
DJANGO_SUPERUSER_PASSWORD=$ADMIN_PASS
DJANGO_SUPERUSER_EMAIL=$ADMIN_EMAIL

# ─────────────────────── DOMÍNIO + SSL ──────────────────
DOMAIN=$DOMAIN
LETSENCRYPT_EMAIL=$LE_EMAIL

# ─────────────────────── WPPCONNECT ─────────────────────
WPPCONNECT_URL=http://wppconnect:21465
WPPCONNECT_SECRET=$WPP_SECRET
WPPCONNECT_TOKEN=$WPP_SECRET
WPPCONNECT_INSTANCE=leguas_wppconnect
WHATSAPP_REPORT_GROUP=
WHATSAPP_API_URL=

# ─────────────────────── INTEGRAÇÕES (preencher depois pela UI) ─────
API_URL=
COOKIE_KEY=
SYNC_TOKEN=
INTERNAL_API_URL=
DELNEXT_ORIGIN_URL=
DELNEXT_LOGIN_URL=
DELNEXT_STATS_URL=
DELNEXT_ADMIN_NAME=
DELNEXT_ADMIN_PASS=
GEOAPI_TOKEN=

# ─────────────────────── BACKUP ─────────────────────────
BACKUP_ZIP_PASSWORD=$BACKUP_PASS

# ─────────────────────── AUTO-UPDATER SIDECAR ───────────
UPDATER_SECRET=$UPDATER_SECRET
UPDATER_BRANCH=main
COMPOSE_PROJECT_NAME=appleguasfranzinaspt

# ─────────────────────── EVOLUTION (opcional, legacy) ───
AUTHENTICATION_API_KEY=
EOF

chmod 600 .env
log ".env gerado e protegido (chmod 600) ✓"

# ── 4. Build + start ─────────────────────────────────────────────────
log "A construir imagem (pode levar 3-5 min na primeira vez)…"
docker compose build

log "A iniciar serviços…"
docker compose up -d

log "A aguardar app ficar pronta (até 90s)…"
for i in {1..30}; do
    if docker compose exec -T web curl -fsS http://localhost:8000/health/ &>/dev/null; then
        log "App OK ✓"; break
    fi
    sleep 3
done

# ── 5. Recovery keys: gravar ficheiro + imprimir no terminal ─────────
RECOVERY_FILE=".recovery_keys.txt"
cat > "$RECOVERY_FILE" <<EOF
# ════════════════════════════════════════════════════════════════════
# Léguas Franzinas — Recovery Keys
# Gerado pelo install.sh em $(date)
#
# *** CRITICAL ***
# Guarda este ficheiro num cofre/password manager.
# Sem o BACKUP_ZIP_PASSWORD, qualquer backup criado por esta instalação
# torna-se irrecuperável se o .env for perdido.
#
# Acesso a estas chaves também disponível em:
#   - http://<host>/system/recovery-keys/  (superuser)
#   - docker exec leguas_web python manage.py show_recovery_keys
# ════════════════════════════════════════════════════════════════════

ADMIN_USER=$ADMIN_USER
ADMIN_PASSWORD=$ADMIN_PASS
ADMIN_EMAIL=$ADMIN_EMAIL

DJANGO_SECRET_KEY=$SECRET_KEY
FERNET_KEY=$FERNET_KEY

DB_USER=leguas_user
DB_PASSWORD=$DB_PASSWORD
DB_ROOT_PASSWORD=$DB_ROOT_PASSWORD

BACKUP_ZIP_PASSWORD=$BACKUP_PASS
UPDATER_SECRET=$UPDATER_SECRET
WPPCONNECT_SECRET=$WPP_SECRET

DOMAIN=$DOMAIN
LETSENCRYPT_EMAIL=$LE_EMAIL
EOF
chmod 600 "$RECOVERY_FILE"

# ── 6. Resumo ────────────────────────────────────────────────────────
echo
echo -e "${G}╔══════════════════════════════════════════════════════════╗"
echo -e "║       ✓ Instalação concluída                              ║"
echo -e "╚══════════════════════════════════════════════════════════╝${N}"
echo
if [ "$DOMAIN" = ":80" ]; then
    SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
    echo -e "  ${B}URL:${N}      http://${SERVER_IP:-localhost}/"
else
    echo -e "  ${B}URL:${N}      https://$DOMAIN/"
    echo -e "  ${Y}NOTA:${N}     Caddy vai obter cert SSL Let's Encrypt em ~30s. Aguardar."
fi
echo -e "  ${B}Admin:${N}    $ADMIN_USER (password definida)"
echo -e "  ${B}Logs:${N}     docker compose logs -f web"
echo -e "  ${B}Status:${N}   docker compose ps"
echo

echo -e "${Y}╔══════════════════════════════════════════════════════════╗${N}"
echo -e "${Y}║   🔑 RECOVERY KEYS — guarda estas chaves AGORA!           ║${N}"
echo -e "${Y}╚══════════════════════════════════════════════════════════╝${N}"
echo
echo -e "  ${B}Admin user:${N}              $ADMIN_USER"
echo -e "  ${B}Admin password:${N}          $ADMIN_PASS"
echo -e "  ${B}Admin email:${N}             $ADMIN_EMAIL"
echo
echo -e "  ${B}DB password:${N}             $DB_PASSWORD"
echo -e "  ${B}DB root password:${N}        $DB_ROOT_PASSWORD"
echo
echo -e "  ${R}BACKUP_ZIP_PASSWORD:${N}     $BACKUP_PASS"
echo -e "    ${Y}↳ sem esta chave, backups antigos ficam irrecuperáveis!${N}"
echo
echo -e "  ${B}UPDATER_SECRET:${N}          $UPDATER_SECRET"
echo -e "  ${B}WPPCONNECT_SECRET:${N}       $WPP_SECRET"
echo
echo -e "  ${G}✓ Gravado em $(pwd)/$RECOVERY_FILE (chmod 600)${N}"
echo -e "  ${G}✓ Disponível também em /system/recovery-keys/ (superuser)${N}"
echo
echo -e "  ${Y}Próximos passos:${N}"
echo -e "    1. ${R}MOVE${N} ${RECOVERY_FILE} para password manager (1Password / Bitwarden / etc.)"
echo -e "    2. Login em / com user '$ADMIN_USER'"
echo -e "    3. Configurar integrações em /system/ (Cainiao, Delnext, GeoAPI…)"
echo -e "    4. Autenticar WhatsApp em /system/whatsapp/ (escanear QR)"
echo
warn "GUARDA o ${RECOVERY_FILE} (e o .env) em local seguro."
