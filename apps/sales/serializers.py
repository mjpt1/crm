from decimal import Decimal

from rest_framework import serializers

from apps.sales.models import Invoice, InvoiceItem, InvoiceStatus, ManualPayment


class InvoiceItemSerializer(serializers.ModelSerializer):
    total_price = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = InvoiceItem
        fields = ['id', 'description', 'quantity', 'unit_price', 'total_price']


class ManualPaymentSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source='recorded_by.get_full_name', read_only=True)
    confirmed_by_name = serializers.CharField(source='confirmed_by.get_full_name', read_only=True, default=None)

    class Meta:
        model = ManualPayment
        fields = [
            'id', 'invoice', 'amount', 'method', 'reference', 'description',
            'recorded_by', 'recorded_by_name', 'confirmed_by', 'confirmed_by_name',
            'is_confirmed', 'confirmed_at', 'payment_date', 'created_at',
        ]
        read_only_fields = ['recorded_by', 'confirmed_by', 'is_confirmed', 'confirmed_at', 'created_at']


class InvoiceListSerializer(serializers.ModelSerializer):
    total_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    paid_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = Invoice
        fields = [
            'id', 'number', 'customer_name', 'customer_phone',
            'status', 'total_amount', 'paid_amount', 'due_date',
            'created_by', 'created_by_name', 'created_at',
        ]


class InvoiceDetailSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, read_only=True)
    manual_payments = ManualPaymentSerializer(many=True, read_only=True)
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    tax_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    paid_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    remaining_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True, default=None)

    class Meta:
        model = Invoice
        fields = [
            'id', 'number', 'lead', 'customer_name', 'customer_phone', 'customer_email',
            'status', 'discount', 'tax_rate', 'notes', 'due_date',
            'subtotal', 'tax_amount', 'total_amount', 'paid_amount', 'remaining_amount',
            'created_by', 'created_by_name', 'approved_by', 'approved_by_name', 'approved_at',
            'created_at', 'updated_at', 'items', 'manual_payments',
        ]
        read_only_fields = [
            'number', 'created_by', 'approved_by', 'approved_at', 'created_at', 'updated_at',
        ]


class InvoiceCreateSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True)

    class Meta:
        model = Invoice
        fields = [
            'lead', 'customer_name', 'customer_phone', 'customer_email',
            'discount', 'tax_rate', 'notes', 'due_date', 'items',
        ]

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError('Invoice must contain at least one item.')
        return value

    def validate_discount(self, value):
        if value < Decimal('0'):
            raise serializers.ValidationError('Discount cannot be negative.')
        return value

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        invoice = Invoice.objects.create(**validated_data)
        InvoiceItem.objects.bulk_create([
            InvoiceItem(invoice=invoice, **item) for item in items_data
        ])
        return invoice


class InvoiceUpdateSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, required=False)

    class Meta:
        model = Invoice
        fields = ['customer_name', 'customer_phone', 'customer_email',
                  'discount', 'tax_rate', 'notes', 'due_date', 'items']

    def validate(self, attrs):
        if self.instance and self.instance.status not in (
            InvoiceStatus.DRAFT, InvoiceStatus.PENDING_APPROVAL
        ):
            raise serializers.ValidationError('Only Draft or Pending invoices can be edited.')
        return attrs

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            instance.items.all().delete()
            InvoiceItem.objects.bulk_create([
                InvoiceItem(invoice=instance, **item) for item in items_data
            ])
        return instance


class ManualPaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ManualPayment
        fields = ['invoice', 'amount', 'method', 'reference', 'description', 'payment_date']

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Amount must be positive.')
        return value
