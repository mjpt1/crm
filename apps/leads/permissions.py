from rest_framework.permissions import BasePermission

from apps.users.models import Role


class CanAccessLead(BasePermission):
    """
    - Super Admin, Sales Manager: full access.
    - Supervisor: leads belonging to their team.
    - Sales Expert: only their own assigned leads.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.can_manage_all:
            return True
        if user.is_supervisor and user.team_id:
            if obj.assigned_to:
                return obj.assigned_to.team_id == user.team_id
            return True  # Supervisor can see unassigned leads
        # Sales expert — only their assigned leads
        return obj.assigned_to_id == user.id


class CanManageLeads(BasePermission):
    """Create / import leads — Supervisor and above."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in (Role.SUPER_ADMIN, Role.SALES_MANAGER, Role.SUPERVISOR)
        )
