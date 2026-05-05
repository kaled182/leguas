#!/bin/bash
# ════════════════════════════════════════════════════════════════════
# Léguas Franzinas — Bootstrap (instala pré-requisitos)
# ────────────────────────────────────────────────────────────────────
# Instala Docker, Docker Compose, git e curl numa máquina Linux limpa.
# Adiciona o user actual ao grupo `docker` (precisa logout/login depois).
#
# Uso:
#   curl -fsSL https://raw.githubusercontent.com/kaled182/leguas/main/production/bootstrap.sh | bash
#
# OU (recomendado — inspecciona antes):
#   wget https://raw.githubusercontent.com/kaled182/leguas/main/production/bootstrap.sh
#   chmod +x bootstrap.sh
#   ./bootstrap.sh
#
# Suporta: Ubuntu, Debian, CentOS, RHEL, Rocky, AlmaLinux
# ════════════════════════════════════════════════════════════════════

set -e

# ── Cores ──
G='\033[0;32m'
Y='\033[1;33m'
R='\033[0;31m'
B='\033[0;34m'
N='\033[0m'

log()  { echo -e "${G}[bootstrap]${N} $*"; }
warn() { echo -e "${Y}[!]${N} $*"; }
err()  { echo -e "${R}[X]${N} $*" >&2; }
ask()  { echo -en "${B}[?]${N} $*"; }

# ── Banner ──
echo
echo -e "${B}┌─────────────────────────────────────────────────────────┐${N}"
echo -e "${B}│  Léguas Franzinas — Bootstrap                            │${N}"
echo -e "${B}│  Instala Docker, Compose v2, git num host limpo          │${N}"
echo -e "${B}└─────────────────────────────────────────────────────────┘${N}"
echo

# ── 1. Detectar OS ──
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    log "Sistema detectado: ${PRETTY_NAME:-$OS}"
else
    err "Não consigo detectar o OS (/etc/os-release ausente)."
    exit 1
fi

# ── 2. Privilégios sudo ──
if [ "$EUID" -eq 0 ]; then
    SUDO=""
elif command -v sudo &>/dev/null; then
    SUDO="sudo"
    log "A usar sudo para operações privilegiadas…"
else
    err "Não és root e sudo não está disponível. Instala sudo ou corre como root."
    exit 1
fi

# ── 3. Update package index + instala utilitários básicos ──
log "A actualizar package index…"
case "$OS" in
    ubuntu|debian)
        export DEBIAN_FRONTEND=noninteractive
        $SUDO apt-get update -qq
        $SUDO apt-get install -qq -y \
            git curl ca-certificates gnupg lsb-release
        ;;
    centos|rhel|rocky|almalinux|fedora)
        $SUDO yum install -y -q git curl ca-certificates
        ;;
    *)
        warn "Distro '$OS' não testada. A tentar apt-get…"
        $SUDO apt-get update -qq && \
        $SUDO apt-get install -qq -y git curl ca-certificates || {
            err "Não consegui instalar utilitários básicos."
            exit 1
        }
        ;;
esac
log "git $(git --version | awk '{print $3}') ✓"

# ── 4. Instala Docker (se em falta) ──
if ! command -v docker &>/dev/null; then
    log "Docker não encontrado. A instalar via script oficial get.docker.com…"
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    $SUDO sh /tmp/get-docker.sh
    rm -f /tmp/get-docker.sh
    log "Docker instalado ✓ ($(docker --version | awk '{print $3}' | tr -d ','))"
else
    log "Docker já instalado ✓ ($(docker --version | awk '{print $3}' | tr -d ','))"
fi

# ── 5. Verifica + instala Docker Compose v2 ──
if ! docker compose version &>/dev/null; then
    log "Docker Compose v2 não encontrado. A tentar instalar plugin…"
    case "$OS" in
        ubuntu|debian)
            $SUDO apt-get install -qq -y docker-compose-plugin || {
                warn "Falhou via apt. Verifica https://docs.docker.com/compose/install/"
            }
            ;;
        centos|rhel|rocky|almalinux|fedora)
            $SUDO yum install -y -q docker-compose-plugin || {
                warn "Falhou via yum. Verifica https://docs.docker.com/compose/install/"
            }
            ;;
    esac
fi

if docker compose version &>/dev/null; then
    log "Docker Compose ✓ ($(docker compose version --short 2>/dev/null))"
else
    err "Docker Compose v2 não disponível. Instala manualmente:"
    err "  https://docs.docker.com/compose/install/"
    exit 1
fi

# ── 6. Liga e activa o serviço Docker ──
if command -v systemctl &>/dev/null; then
    if ! systemctl is-active --quiet docker; then
        log "A iniciar serviço Docker…"
        $SUDO systemctl enable --now docker
    fi
fi

# ── 7. Adiciona user ao grupo docker ──
USER_TO_ADD="${SUDO_USER:-$USER}"
if [ "$USER_TO_ADD" != "root" ]; then
    if ! groups "$USER_TO_ADD" 2>/dev/null | grep -q '\bdocker\b'; then
        log "A adicionar $USER_TO_ADD ao grupo docker…"
        $SUDO usermod -aG docker "$USER_TO_ADD"
        NEEDS_LOGOUT=1
    else
        log "$USER_TO_ADD já está no grupo docker ✓"
    fi
fi

# ── 8. Teste rápido ──
log "A testar Docker…"
if docker info &>/dev/null 2>&1; then
    log "Docker operacional ✓"
elif $SUDO docker info &>/dev/null 2>&1; then
    log "Docker operacional via sudo ✓"
    NEEDS_LOGOUT=1
else
    err "Docker instalado mas não responde. Verifica: $SUDO systemctl status docker"
    exit 1
fi

# ── 9. Conclusão ──
echo
echo -e "${G}╔══════════════════════════════════════════════════════════╗${N}"
echo -e "${G}║       ✓ Pré-requisitos instalados                         ║${N}"
echo -e "${G}╚══════════════════════════════════════════════════════════╝${N}"
echo
echo -e "  ${B}Próximos passos:${N}"
echo
echo -e "  1. ${B}Clonar o repositório:${N}"
echo "       git clone https://github.com/kaled182/leguas.git"
echo "       cd leguas/production"
echo
echo -e "  2. ${B}Correr o instalador:${N}"
echo "       ./install.sh"
echo

if [ "${NEEDS_LOGOUT:-0}" = "1" ]; then
    echo -e "  ${Y}IMPORTANTE:${N}"
    echo -e "    Faz ${R}logout + login${N} (ou ${R}newgrp docker${N}) antes de continuar,"
    echo "    para o teu user usar Docker sem sudo."
    echo
fi
