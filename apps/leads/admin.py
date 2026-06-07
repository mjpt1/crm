from django.contrib import admin

from apps.leads.models import Lead, LeadAssignment, LeadNote, LeadStatusHistory


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'phone', 'email', 'status', 'source', 'assigned_to', 'created_at']
    list_filter = ['status', 'source', 'priority']
    search_fields = ['first_name', 'last_name', 'phone', 'email', 'company']
    raw_id_fields = ['assigned_to', 'created_by']
    readonly_fields = ['created_at', 'updated_at', 'assigned_at']
    date_hierarchy = 'created_at'


@admin.register(LeadAssignment)
class LeadAssignmentAdmin(admin.ModelAdmin):
    list_display = ['lead', 'assigned_to', 'assigned_by', 'assigned_at', 'is_active']
    list_filter = ['is_active']
    raw_id_fields = ['lead', 'assigned_to', 'assigned_by']
    readonly_fields = ['assigned_at']


@admin.register(LeadStatusHistory)
class LeadStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ['lead', 'old_status', 'new_status', 'changed_by', 'changed_at']
    readonly_fields = list_display + ['notes']
    raw_id_fields = ['lead', 'changed_by']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(LeadNote)
class LeadNoteAdmin(admin.ModelAdmin):
    list_display = ['lead', 'author', 'is_pinned', 'created_at']
    raw_id_fields = ['lead', 'author']
    search_fields = ['content']
