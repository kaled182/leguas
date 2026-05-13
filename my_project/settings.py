import os
from pathlib import Path

import environ
from django.contrib.messages import constants as messages

# Base do projeto
BASE_DIR = Path(__file__).resolve().parent.parent

# Carrega variáveis do .env
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

# Segurança
SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

if DEBUG:
    for host in ("localhost", "127.0.0.1", "testserver"):
        if host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(host)

FORCE_HTTPS = env.bool("FORCE_HTTPS", default=not DEBUG)

# Nunca força HTTPS se DEBUG estiver True
if DEBUG:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
else:
    if FORCE_HTTPS:
        SECURE_SSL_REDIRECT = True
        SESSION_COOKIE_SECURE = True
        CSRF_COOKIE_SECURE = True
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    else:
        SECURE_SSL_REDIRECT = False
        SESSION_COOKIE_SECURE = False
        CSRF_COOKIE_SECURE = False

# Encryption Keys (for EncryptedCharField)
FERNET_KEYS = [
    env(
        "FERNET_KEY",
        default="leguas-default-encryption-key-change-in-production",
    )
]

# Constantes customizadas
COOKIE_KEY = env("COOKIE_KEY")
SYNC_TOKEN = env("SYNC_TOKEN")
API_URL = env("API_URL")
GEOAPI_TOKEN = os.getenv("GEOAPI_TOKEN")

# WhatsApp Reports
AUTHENTICATION_API_KEY = env("AUTHENTICATION_API_KEY", default="")
WHATSAPP_API_URL = env("WHATSAPP_API_URL", default="")
WHATSAPP_REPORT_GROUP = env("WHATSAPP_REPORT_GROUP", default="")

# ── OCR de faturas (Bill form) ────────────────────────────────────────
# Provider activo: 'anthropic' (Claude Vision — pago) ou 'gemini' (free tier)
OCR_PROVIDER = env("OCR_PROVIDER", default="gemini")
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
GEMINI_API_KEY = env("GEMINI_API_KEY", default="")
ANTHROPIC_OCR_MODEL = env(
    "ANTHROPIC_OCR_MODEL", default="claude-sonnet-4-6",
)
GEMINI_OCR_MODEL = env(
    "GEMINI_OCR_MODEL", default="gemini-2.5-flash",
)

# WPPConnect Server (Leguas)
WPPCONNECT_URL = env("WPPCONNECT_URL", default="")
WPPCONNECT_SESSION = env("WPPCONNECT_SESSION", default="leguas_wppconnect")
WPPCONNECT_TOKEN = env("WPPCONNECT_TOKEN", default="")
WPPCONNECT_SECRET = env("WPPCONNECT_SECRET", default="THISISMYSECURETOKEN")

# Tailwind
TAILWIND_APP_NAME = "theme"

# IPs internos
INTERNAL_IPS = [
    "127.0.0.1",
]

# Apps
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",  # Django REST Framework
    "import_export",  # Django Import Export
    "django_celery_beat",  # Celery Beat com DatabaseScheduler
    "tailwind",
    "theme",
    "customauth",
    # Legacy Apps (Paack-only - serão descontinuados)
    "ordersmanager_paack",
    "send_paack_reports",
    "paack_dashboard",
    "manualorders_paack",
    # Core Apps
    "management",
    "drivers_app",
    "converter",
    "settlements",
    "accounting",
    "payroll",
    "system_config",
    # New Multi-Partner Architecture (Fase 1)
    "core",  # Gestão de Parceiros
    "orders_manager",  # Gestão de Pedidos (genérico)
    "fleet_management",  # Gestão de Frota
    "pricing",  # Tarifação e Zonas Postais
    "route_allocation",  # Atribuição de Rotas e Turnos
    # Analytics (Fase 2)
    "analytics",  # Métricas, Forecasting e Dashboards
    # Contratos
    "contracts",
]

# Middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Security: Allow iframes from same origin (for PDF preview)
X_FRAME_OPTIONS = "SAMEORIGIN"

# URL config
ROOT_URLCONF = "my_project.urls"

# Templates
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "drivers_app.context_processors.drivers_counts",
                "drivers_app.context_processors.portal_layout",
                "system_config.context_processors.map_config",
            ],
        },
    },
]

WSGI_APPLICATION = "my_project.wsgi.application"

# Banco de dados (suporta configuração via .env para Docker)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("DB_NAME", default="leguas_db"),
        "USER": env("DB_USER", default="leguas_external_user"),
        "PASSWORD": env("DB_PASSWORD", default="Lrpr2003."),
        "HOST": env("DB_HOST", default="45.160.176.10"),
        "PORT": env("DB_PORT", default="3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            "sql_mode": "STRICT_TRANS_TABLES",
            # Força o MySQL a usar UTC como timezone padrão
            # 'default_storage_engine': 'InnoDB',  # Removido - não suportado no mysqlclient 2.2.x
        },
    }
}

# DATABASES = {
#    'default': {
#        'ENGINE': 'django.db.backends.sqlite3',
#        'NAME': BASE_DIR / 'db.sqlite3',
#    }
# }

# Validação de senha
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Idioma e timezone
LANGUAGE_CODE = "pt-pt"
TIME_ZONE = "Europe/Lisbon"
USE_I18N = True
USE_TZ = True

# Arquivos estáticos
STATIC_URL = "/static/"

# Diretório onde os arquivos coletados vão (usado em produção)
STATIC_ROOT = BASE_DIR / "staticfiles"

# Configuração para usar arquivos estáticos de cada app
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# Diretório adicional de arquivos estáticos globais
STATICFILES_DIRS = [
    BASE_DIR / "static",  # Arquivos globais do projeto
]

# Campo padrão de chave primária
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Redirecionamento de login
LOGIN_URL = "/auth/login/"

# URL interna da API para requests do dashboard
INTERNAL_API_URL = env("INTERNAL_API_URL", default="http://127.0.0.1:8000")

# Redis Configuration
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

# Cache com Redis
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "leguas",
        "TIMEOUT": 300,  # 5 minutos
    }
}

# Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 100,
}

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
        "sync_format": {
            "format": "[{asctime}] {levelname} - {name} - {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "sync_console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "sync_format",
        },
    },
    "loggers": {
        "dashboard_paack": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
        "ordersmanager_paack": {
            "handlers": ["sync_console"],
            "level": "INFO",
            "propagate": False,
        },
        "ordersmanager_paack.sync_service": {
            "handlers": ["sync_console"],
            "level": "INFO",
            "propagate": False,
        },
        "ordersmanager_paack.data_processor": {
            "handlers": ["sync_console"],
            "level": "INFO",
            "propagate": False,
        },
        "ordersmanager_paack.APIConnect": {
            "handlers": ["sync_console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

MESSAGE_TAGS = {
    messages.DEBUG: "bg-gray-500",
    messages.INFO: "bg-blue-500",
    messages.SUCCESS: "bg-green-500",
    messages.WARNING: "bg-yellow-500",
    messages.ERROR: "bg-red-500",
}

# ============================================================================
# FEATURE FLAGS - Multi-Partner Architecture
# ============================================================================
# Importa feature flags para controlar rollout gradual da nova arquitetura
# Referência: system_config/feature_flags.py e docs/MIGRATION_GUIDE.md


# ============================================================================
# CELERY CONFIGURATION
# ============================================================================
# Configurações para processamento assíncrono de tasks e sincronizações automáticas

# Broker (usando Redis - recomendado para produção)
# Se não tiver Redis instalado, pode usar RabbitMQ ou mesmo Django DB como broker
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default=REDIS_URL)

# Backend para armazenar resultados das tasks
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default=REDIS_URL)

# Aceitar conteúdo JSON apenas (segurança)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

# Timezone
CELERY_TIMEZONE = 'Europe/Lisbon'
CELERY_ENABLE_UTC = True

# Expiração de resultados (7 dias)
CELERY_RESULT_EXPIRES = 60 * 60 * 24 * 7

# Configurações de retry
CELERY_TASK_ACKS_LATE = True  # Task só é marcada como concluída após terminar
CELERY_TASK_REJECT_ON_WORKER_LOST = True  # Re-executar se worker morrer

# Limite de memória (prevenir memory leaks)
CELERY_WORKER_MAX_MEMORY_PER_CHILD = 200000  # 200MB

# Logging
CELERY_WORKER_HIJACK_ROOT_LOGGER = False  # Deixar Django lidar com logging

# Email para notificações de erros em tasks
CELERY_SEND_TASK_ERROR_EMAILS = True
