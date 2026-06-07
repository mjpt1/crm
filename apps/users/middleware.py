"""
Middleware for team-based data isolation and request enrichment.
"""
import logging

logger = logging.getLogger(__name__)


class TeamIsolationMiddleware:
    """
    Attaches team-isolation metadata to the request.
    Views use request.accessible_user_ids to scope querysets.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if hasattr(request, 'user') and request.user.is_authenticated:
            request.accessible_user_ids = list(
                request.user.get_accessible_user_ids()
            )
        else:
            request.accessible_user_ids = []
        response = self.get_response(request)
        return response
