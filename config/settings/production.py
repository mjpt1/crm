"""Production settings with hardened security."""
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

# ─── Logging ──────────────────────────────────────────────────────────────────
import os  # noqa

LOG_DIR = BASE_DIR / 'logs'  # noqa
os.makedirs(LOG_DIR, exist_ok=True)
LOGGING['root']['level'] = 'WARNING'  # noqa
