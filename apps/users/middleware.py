"""
Middleware for team-based data isolation and request enrichment.
"""
import logging
import shutil
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.utils import OperationalError, ProgrammingError

from apps.users.models import Role

logger = logging.getLogger(__name__)
_sqlite_bootstrapped = False


class TeamIsolationMiddleware:
    """
    Attaches team-isolation metadata to the request.
    Views use request.accessible_user_ids to scope querysets.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _bootstrap_sqlite_if_needed():
        global _sqlite_bootstrapped
        if _sqlite_bootstrapped:
            return
        try:
            db = settings.DATABASES.get('default', {})
            if db.get('ENGINE') != 'django.db.backends.sqlite3':
                _sqlite_bootstrapped = True
                return

            db_name = str(db.get('NAME', ''))
            if '/tmp/' not in db_name.replace('\\', '/'):
                _sqlite_bootstrapped = True
                return

            target = Path(db_name)
            if target.exists():
                _sqlite_bootstrapped = True
                return

            seed_db = Path(settings.BASE_DIR) / 'db.sqlite3'
            if not seed_db.exists():
                _sqlite_bootstrapped = True
                return

            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(seed_db, target)
            _sqlite_bootstrapped = True
        except Exception:
            logger.exception('SQLite bootstrap failed')
            _sqlite_bootstrapped = True
            return

    @staticmethod
    def _ensure_demo_admin_exists():
        if not getattr(settings, 'AUTO_CREATE_DEMO_ADMIN', False):
            return
        email = getattr(settings, 'DEMO_ADMIN_EMAIL', '').strip().lower()
        password = getattr(settings, 'DEMO_ADMIN_PASSWORD', '')
        if not email or not password:
            return

        User = get_user_model()
        try:
            if not User.objects.filter(email=email).exists():
                User.objects.create_user(
                    email=email,
                    password=password,
                    first_name='System',
                    last_name='Admin',
                    role=Role.SUPER_ADMIN,
                    is_staff=True,
                    is_superuser=True,
                    is_active=True,
                )
        except (OperationalError, ProgrammingError):
            logger.exception('Demo admin provisioning skipped due to DB readiness issue')
            return

    def __call__(self, request):
        try:
            self._bootstrap_sqlite_if_needed()
            self._ensure_demo_admin_exists()
        except Exception:
            logger.exception('Middleware initialization failed')
        try:
            if hasattr(request, 'user') and request.user.is_authenticated:
                request.accessible_user_ids = list(
                    request.user.get_accessible_user_ids()
                )
            else:
                request.accessible_user_ids = []
        except (OperationalError, ProgrammingError):
            request.accessible_user_ids = []
        response = self.get_response(request)
        return response
