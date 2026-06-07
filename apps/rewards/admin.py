from django.contrib import admin

from apps.rewards.models import Reward, SalesTarget


@admin.register(SalesTarget)
class SalesTargetAdmin(admin.ModelAdmin):
    list_display = ['title', 'target_type', 'user', 'team', 'target_value', 'period_start', 'period_end']
    list_filter = ['target_type']
    raw_id_fields = ['user', 'team', 'created_by']


@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'title', 'is_auto', 'granted_by', 'granted_at']
    list_filter = ['is_auto']
    raw_id_fields = ['user', 'target', 'granted_by']
    readonly_fields = ['granted_at']
