"""
Service layer for users app.
"""
from apps.users.models import AuditLog


class AuditService:
    """Centralized audit logging service."""

    @staticmethod
    def log(user, action, model_name, object_id='', data=None, request=None):
        ip_address = None
        user_agent = ''
        if request:
            ip_address = AuditService._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        AuditLog.objects.create(
            user=user,
            action=action,
            model_name=model_name,
            object_id=str(object_id),
            data=data or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @staticmethod
    def _get_client_ip(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
