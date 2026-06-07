"""
Middleware for team-based data isolation and request enrichment.
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db.utils import OperationalError, ProgrammingError

from apps.users.models import Role

logger = logging.getLogger(__name__)
_schema_checked = False


class TeamIsolationMiddleware:
    """
    Attaches team-isolation metadata to the request.
    Views use request.accessible_user_ids to scope querysets.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _ensure_demo_admin_exists():
        global _schema_checked
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
            # On serverless cold starts with ephemeral SQLite, schema may not exist yet.
            if not _schema_checked:
                try:
                    call_command('migrate', interactive=False, verbosity=0)
                except Exception:
                    logger.exception('Auto-migrate failed while provisioning demo admin')
                    _schema_checked = True
                    return
                _schema_checked = True
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
                return

    def __call__(self, request):
        self._ensure_demo_admin_exists()
        if hasattr(request, 'user') and request.user.is_authenticated:
            request.accessible_user_ids = list(
                request.user.get_accessible_user_ids()
            )
        else:
            request.accessible_user_ids = []
        response = self.get_response(request)
        return response
