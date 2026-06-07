from django.contrib import admin

from apps.voip.models import CallLog


@admin.register(CallLog)
class CallLogAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'direction', 'status', 'agent', 'lead', 'duration_seconds', 'started_at']
    list_filter = ['direction', 'status']
    search_fields = ['phone_number', 'agent__email', 'external_call_id']
    raw_id_fields = ['agent', 'lead']
    readonly_fields = ['created_at', 'external_call_id', 'raw_payload']
    date_hierarchy = 'started_at'
