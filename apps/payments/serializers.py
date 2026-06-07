from rest_framework import serializers

from apps.payments.models import OnlinePayment


class OnlinePaymentSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source='invoice.number', read_only=True)
    initiated_by_name = serializers.CharField(source='initiated_by.get_full_name', read_only=True)

    class Meta:
        model = OnlinePayment
        fields = [
            'id', 'invoice', 'invoice_number', 'amount', 'gateway',
            'track_id', 'payment_url', 'ref_number', 'card_number',
            'status', 'initiated_by', 'initiated_by_name',
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
        if invoice.remaining_amount <= 0:
            raise serializers.ValidationError('Invoice is already fully paid.')
        return value
