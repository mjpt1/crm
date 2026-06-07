from django.contrib import admin

from apps.sales.models import Invoice, InvoiceItem, ManualPayment


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1
    fields = ['description', 'quantity', 'unit_price']


class ManualPaymentInline(admin.TabularInline):
    model = ManualPayment
    extra = 0
    readonly_fields = ['recorded_by', 'confirmed_by', 'confirmed_at']
    fields = ['amount', 'method', 'reference', 'payment_date', 'is_confirmed',
              'recorded_by', 'confirmed_by', 'confirmed_at']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['number', 'customer_name', 'status', 'created_by', 'created_at']
    list_filter = ['status']
    search_fields = ['number', 'customer_name', 'customer_phone']
    readonly_fields = ['number', 'created_at', 'updated_at', 'approved_at']
    inlines = [InvoiceItemInline, ManualPaymentInline]
    raw_id_fields = ['lead', 'created_by', 'approved_by']
    date_hierarchy = 'created_at'


@admin.register(ManualPayment)
class ManualPaymentAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'amount', 'method', 'is_confirmed', 'payment_date', 'recorded_by']
    list_filter = ['is_confirmed', 'method']
    raw_id_fields = ['invoice', 'recorded_by', 'confirmed_by']
    readonly_fields = ['confirmed_at']
