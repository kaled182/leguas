"""Gunicorn config — Léguas Franzinas production.

Tuning:
  - Workers: 2 × CPU + 1 (formula clássica)
  - Worker class: sync (WSGI standard, não usamos channels/ASGI)
  - Threads: 4 por worker
  - Timeout: 120s (uploads grandes, geração de PDFs grandes)
  - Restart workers a cada 1000 reqs (previne memory leaks)

Override via env vars:
  GUNICORN_WORKERS=N         (override workers)
  GUNICORN_TIMEOUT=N         (override timeout em segundos)
  GUNICORN_LOG_LEVEL=info    (debug|info|warning|error|critical)
"""
import multiprocessing
import os


# ── Bind ──────────────────────────────────────────────────────────────
# 0.0.0.0 dentro do container (Caddy/nginx faz proxy até cá)
bind = "0.0.0.0:8000"

# ── Workers ───────────────────────────────────────────────────────────
_default_workers = multiprocessing.cpu_count() * 2 + 1
workers = int(os.environ.get("GUNICORN_WORKERS", _default_workers))
worker_class = "sync"
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
worker_connections = 1000

# ── Timeouts ──────────────────────────────────────────────────────────
# Aumentado para 120s — geração de PDFs grandes, uploads de XLSX,
# Playwright scrape do Delnext.
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
graceful_timeout = 30
keepalive = 5

# ── Restart workers para mitigar memory leaks ─────────────────────────
max_requests = 1000
max_requests_jitter = 100  # evita thundering herd

# ── Logging ───────────────────────────────────────────────────────────
accesslog = "-"  # stdout (capturado pelo Docker logs)
errorlog = "-"   # stderr
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
access_log_format = (
    '%(h)s "%(r)s" %(s)s %(b)s %(L)ss "%(f)s" "%(a)s"'
)

# ── Process naming ────────────────────────────────────────────────────
proc_name = "leguas_web"

# ── WSGI app ──────────────────────────────────────────────────────────
wsgi_app = "my_project.wsgi:application"

# ── Misc ──────────────────────────────────────────────────────────────
preload_app = True  # carrega app uma vez no master, partilha c/ workers
