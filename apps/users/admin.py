from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.users.models import AuditLog, CustomUser, Team


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['email', 'first_name', 'last_name', 'role', 'team', 'is_active', 'created_at']
    list_filter = ['role', 'team', 'is_active']
    search_fields = ['email', 'first_name', 'last_name', 'phone']
    ordering = ['email']
    readonly_fields = ['created_at', 'updated_at', 'date_joined', 'last_login']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('اطلاعات شخصی', {'fields': ('first_name', 'last_name', 'phone', 'avatar')}),
        ('نقش و تیم', {'fields': ('role', 'team')}),
        ('دسترسی‌ها', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('تاریخ‌ها', {'fields': ('date_joined', 'last_login', 'created_at', 'updated_at')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'role', 'team', 'password1', 'password2'),
        }),
    )


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ['name', 'supervisor', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']
    raw_id_fields = ['supervisor']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'model_name', 'object_id', 'ip_address', 'timestamp']
    list_filter = ['action', 'model_name']
    search_fields = ['user__email', 'model_name', 'object_id']
    readonly_fields = list_display
    ordering = ['-timestamp']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
