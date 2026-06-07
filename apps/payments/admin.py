from django.contrib import admin

from apps.payments.models import OnlinePayment


@admin.register(OnlinePayment)
class OnlinePaymentAdmin(admin.ModelAdmin):
    list_display = ['track_id', 'invoice', 'amount', 'gateway', 'status', 'created_at', 'verified_at']
    list_filter = ['status', 'gateway']
    search_fields = ['track_id', 'ref_number', 'invoice__number']
    readonly_fields = ['track_id', 'payment_url', 'ref_number', 'card_number',
                       'callback_data', 'created_at', 'verified_at']
    raw_id_fields = ['invoice', 'initiated_by']
    ordering = ['-created_at']
