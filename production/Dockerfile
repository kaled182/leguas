# ════════════════════════════════════════════════════════════════════
# Léguas Franzinas — Production Dockerfile (Multi-Stage)
# ════════════════════════════════════════════════════════════════════
# Stage 1: builder    — instala deps Python + Playwright (image grande)
# Stage 2: runtime    — copia só o que interessa (image enxuta)
# ════════════════════════════════════════════════════════════════════

# ─────────────────────────── STAGE 1: BUILDER ──────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build deps (gcc, pkg-config, headers MySQL) — só usadas para compilar
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    pkg-config \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Criar venv isolado em /opt/venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Instalar deps Python no venv
COPY requirements.txt /tmp/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt


# ─────────────────────────── STAGE 2: RUNTIME ──────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app

# Runtime deps: MySQL client + Playwright system libs (sem build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-mysql-client \
    libmariadb3 \
    curl \
    ca-certificates \
    # Playwright runtime libs (browser Chromium)
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copiar venv pronto da stage builder
COPY --from=builder /opt/venv /opt/venv

# Instalar browser Chromium (Playwright) em pasta acessível ao user django
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
RUN mkdir -p /opt/playwright && playwright install chromium

# Criar user django (não-root) para correr a app
RUN groupadd -r django && useradd -r -g django -d /app -s /bin/bash django

WORKDIR /app

# Copiar app code
COPY --chown=django:django . /app/

# Criar dirs necessários e dar permissão ao user django
RUN mkdir -p /app/staticfiles /app/media /app/logs && \
    chown -R django:django /app/staticfiles /app/media /app/logs /opt/playwright

# Entrypoint production
COPY --chown=django:django production/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Mudar para user não-root
USER django

EXPOSE 8000

# Healthcheck — Django responde em /health/
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -fsS http://localhost:8000/health/ || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "--config", "/app/production/gunicorn_config.py", "my_project.wsgi:application"]
