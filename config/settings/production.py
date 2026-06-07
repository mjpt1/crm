"""Production settings with hardened security."""
import os
from pathlib import Path

from .base import *  # noqa

DEBUG = False

# ─── Security Hardening ───────────────────────────────────────────────────────
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# ─── Trusted Proxies (Nginx) ──────────────────────────────────────────────────
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ─── Host / CSRF (Production + Vercel) ───────────────────────────────────────
ALLOWED_HOSTS = list(dict.fromkeys(ALLOWED_HOSTS + ['.vercel.app']))
_csrf_origins = [
	origin.strip() for origin in config('CSRF_TRUSTED_ORIGINS', cast=Csv(), default='')
	if origin and origin.strip()
]
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(_csrf_origins + ['https://*.vercel.app']))

# ─── Vercel Serverless Compatibility ─────────────────────────────────────────
IS_VERCEL = bool(os.getenv('VERCEL'))

# ─── Demo Admin Auto Provisioning ───────────────────────────────────────────
AUTO_CREATE_DEMO_ADMIN = config('AUTO_CREATE_DEMO_ADMIN', cast=bool, default=IS_VERCEL)
DEMO_ADMIN_EMAIL = config('DEMO_ADMIN_EMAIL', default='admin@crm.com')
DEMO_ADMIN_PASSWORD = config('DEMO_ADMIN_PASSWORD', default='Admin@12345678')

if IS_VERCEL:
	# Vercel serverless has read-only code filesystem, so file handlers fail.
	LOGGING['handlers'].pop('file', None)
	LOGGING['root']['handlers'] = ['console']
	for logger_name in ('django', 'apps'):
		LOGGING['loggers'][logger_name]['handlers'] = ['console']

	# Avoid hard dependency on Redis in serverless runtime.
	CACHES = {
		'default': {
			'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
		}
	}
	SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'

	# If no external DB config is present, use ephemeral SQLite to prevent boot crashes.
	has_external_db_config = any([
		os.getenv('DATABASE_URL'),
		os.getenv('DB_HOST'),
		os.getenv('POSTGRES_HOST'),
	])
	if not has_external_db_config:
		DATABASES = {
			'default': {
				'ENGINE': 'django.db.backends.sqlite3',
				'NAME': Path('/tmp/db.sqlite3'),
			}
		}

	# On Vercel, collectstatic may not generate a manifest in every workflow.
	STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

	# Fallback for preview deployments when SECRET_KEY was not set yet.
	if not os.getenv('SECRET_KEY'):
		SECRET_KEY = 'unsafe-vercel-preview-secret-key-change-me'

# ─── Logging ──────────────────────────────────────────────────────────────────
if not IS_VERCEL:
	LOG_DIR = BASE_DIR / 'logs'  # noqa
	os.makedirs(LOG_DIR, exist_ok=True)

LOGGING['root']['level'] = 'WARNING'  # noqa
