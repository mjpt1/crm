"""
RBAC Permission classes for the CRM system.
"""
from rest_framework.permissions import BasePermission

from apps.users.models import Role


class IsSuperAdmin(BasePermission):
    """Only Super Admins."""
    message = 'Only Super Admins can perform this action.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == Role.SUPER_ADMIN
        )


class IsSalesManager(BasePermission):
    """Only Sales Managers or Super Admins."""
    message = 'Only Sales Managers can perform this action.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in (Role.SUPER_ADMIN, Role.SALES_MANAGER)
        )


class IsSupervisorOrAbove(BasePermission):
    """Supervisor, Sales Manager, or Super Admin."""
    message = 'Insufficient permissions.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in (
                Role.SUPER_ADMIN,
                Role.SALES_MANAGER,
                Role.SUPERVISOR,
            )
        )


class IsFinance(BasePermission):
    """Finance team or Super Admin."""
    message = 'Only Finance team members can perform this action.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in (Role.SUPER_ADMIN, Role.FINANCE)
        )


class IsTeamMember(BasePermission):
    """
    Object-level: user can access object only if it belongs to their team.
    Super Admin and Sales Manager bypass this restriction.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.can_manage_all:
            return True
        # Check if obj has an 'assigned_to' or 'user' or 'created_by' field
        for attr in ('assigned_to', 'user', 'created_by', 'agent'):
            owner = getattr(obj, attr, None)
            if owner is not None:
                if user.is_supervisor:
                    return owner.team_id == user.team_id
                return owner.id == user.id
        return False


class CanManageUsers(BasePermission):
    """Super Admin can manage all users; Sales Manager can manage non-admins."""
    message = 'You do not have permission to manage users.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in (Role.SUPER_ADMIN, Role.SALES_MANAGER)
        )

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role == Role.SUPER_ADMIN:
            return True
        # Sales Manager cannot modify Super Admins
        return obj.role != Role.SUPER_ADMIN
