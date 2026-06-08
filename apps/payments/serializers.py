from rest_framework import serializers

from django.conf import settings

from apps.payments.models import OnlinePayment, PaymentGatewayConfig


class OnlinePaymentSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source='invoice.number', read_only=True)
    initiated_by_name = serializers.CharField(source='initiated_by.get_full_name', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = OnlinePayment
        fields = [
            'id', 'invoice', 'invoice_number', 'amount', 'gateway',
            'track_id', 'payment_url', 'ref_number', 'card_number',
            'status', 'status_label', 'initiated_by', 'initiated_by_name',
            'created_at', 'verified_at', 'error_message',
        ]
        read_only_fields = [
            'track_id', 'payment_url', 'ref_number', 'card_number',
            'status', 'initiated_by', 'created_at', 'verified_at', 'error_message',
        ]


class InitiatePaymentSerializer(serializers.Serializer):
    invoice_id = serializers.IntegerField()

    def validate_invoice_id(self, value):
        from apps.sales.models import Invoice, InvoiceStatus
        try:
            invoice = Invoice.objects.get(id=value)
        except Invoice.DoesNotExist:
            raise serializers.ValidationError('Invoice not found.')
        if invoice.status not in (InvoiceStatus.APPROVED, InvoiceStatus.PARTIALLY_PAID):
            raise serializers.ValidationError(
                'Only approved or partially paid invoices can be paid online.'
            )
        try:
            remaining = invoice.remaining_amount
        except Exception:
            raise serializers.ValidationError('Could not evaluate invoice payment balance.')
        if remaining <= 0:
            raise serializers.ValidationError('Invoice is already fully paid.')
        return value


class PaymentSettingsSerializer(serializers.ModelSerializer):
    gateway = serializers.CharField(default='zibal')
    merchant_masked = serializers.SerializerMethodField(read_only=True)
    merchant_configured = serializers.SerializerMethodField(read_only=True)
    request_url = serializers.SerializerMethodField(read_only=True)
    verify_url = serializers.SerializerMethodField(read_only=True)
    payment_url_pattern = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PaymentGatewayConfig
        fields = [
            'gateway',
            'merchant',
            'merchant_masked',
            'merchant_configured',
            'callback_url',
            'request_url',
            'verify_url',
            'payment_url_pattern',
            'is_active',
            'updated_at',
        ]
        read_only_fields = [
            'merchant_masked',
            'merchant_configured',
            'request_url',
            'verify_url',
            'payment_url_pattern',
            'updated_at',
        ]

    def get_merchant_masked(self, obj):
        merchant = (obj.merchant or '').strip()
        if not merchant:
            return ''
        if len(merchant) <= 4:
            return '****'
        return f'{merchant[:4]}***'

    def get_merchant_configured(self, obj):
        return bool((obj.merchant or '').strip())

    def get_request_url(self, obj):
        return settings.ZIBAL_REQUEST_URL

    def get_verify_url(self, obj):
        return settings.ZIBAL_VERIFY_URL

    def get_payment_url_pattern(self, obj):
        return settings.ZIBAL_PAYMENT_URL

    def validate_gateway(self, value):
        if value != 'zibal':
            raise serializers.ValidationError('Only zibal gateway is supported right now.')
        return value
