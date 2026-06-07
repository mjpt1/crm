"""Development settings."""
from .base import *  # noqa

DEBUG = True
SECRET_KEY = 'dev-secret-key-not-for-production-use-only'  # noqa

ALLOWED_HOSTS = ['*']

# ─── SQLite برای محیط توسعه (نیازی به PostgreSQL نیست) ──────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',  # noqa
    }
}

# ─── حافظه داخلی به جای Redis ─────────────────────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# ─── Celery همزمان (بدون Redis Broker) ────────────────────────────────────
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# ─── Development Email ────────────────────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ─── Debug Toolbar (optional) ─────────────────────────────────────────────────
INTERNAL_IPS = ['127.0.0.1', 'localhost']

# ─── Relaxed CORS for local dev ───────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = True

# ─── Django REST Framework browsable API ─────────────────────────────────────
REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] += [  # noqa
    'rest_framework.renderers.BrowsableAPIRenderer',
]

# ─── Logging ──────────────────────────────────────────────────────────────────
LOGGING['root']['level'] = 'DEBUG'  # noqa
