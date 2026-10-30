from my_project.settings import *
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "/rbdata/seed.sqlite3", "OPTIONS": {"timeout": 30}}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
MEDIA_ROOT = "/rbdata/media"
SECRET_KEY = "rebrand-baseline"
DEBUG = False
ALLOWED_HOSTS = ["*"]
CELERY_TASK_ALWAYS_EAGER = False
CELERY_BROKER_URL = "memory://"
LOGGING = {"version": 1, "disable_existing_loggers": False, "handlers": {"c": {"class": "logging.StreamHandler"}}, "root": {"handlers": ["c"], "level": "WARNING"}}
