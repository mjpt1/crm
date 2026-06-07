"""
Middleware for team-based data isolation and request enrichment.
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.utils import OperationalError, ProgrammingError

from apps.users.models import Role

logger = logging.getLogger(__name__)


class TeamIsolationMiddleware:
    """
    Attaches team-isolation metadata to the request.
    Views use request.accessible_user_ids to scope querysets.
    """

    def __init__(self, get_response):
        self.get_response = get_response

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
            # DB might be unavailable during cold starts or before migrations.
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
