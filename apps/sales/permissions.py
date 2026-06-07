from rest_framework.permissions import BasePermission

from apps.users.models import Role


class CanCreateInvoice(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role in (
            Role.SUPER_ADMIN, Role.SALES_MANAGER, Role.SUPERVISOR, Role.SALES_EXPERT
        )


class CanApproveInvoice(BasePermission):
    """Only Finance or Super Admin can approve/reject invoices."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role in (
            Role.SUPER_ADMIN, Role.FINANCE
        )


class CanAccessInvoice(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.can_manage_all or user.role == Role.FINANCE:
            return True
        if user.is_supervisor and user.team_id:
            return obj.created_by and obj.created_by.team_id == user.team_id
        return obj.created_by_id == user.id
