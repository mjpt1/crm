"""
Invoice, InvoiceItem, and ManualPayment models.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.leads.models import Lead


class InvoiceStatus(models.TextChoices):
    DRAFT = 'draft', _('پیش‌نویس')
    PENDING_APPROVAL = 'pending_approval', _('در انتظار تایید مالی')
    APPROVED = 'approved', _('تایید شده')
    PAID = 'paid', _('پرداخت‌شده')
    PARTIALLY_PAID = 'partially_paid', _('پرداخت جزئی')
    CANCELLED = 'cancelled', _('لغو شده')
    REFUNDED = 'refunded', _('بازگشت شده')


class PaymentMethod(models.TextChoices):
    CASH = 'cash', _('نقد')
    BANK_TRANSFER = 'bank_transfer', _('انتقال بانکی')
    ONLINE = 'online', _('پرداخت آنلاین')
    CHEQUE = 'cheque', _('چک')


class Invoice(models.Model):
    number = models.CharField(max_length=30, unique=True, editable=False)
    lead = models.ForeignKey(
        Lead,
        on_delete=models.PROTECT,
        related_name='invoices',
        null=True,
        blank=True,
    )

    # ─── Customer snapshot (stored so invoice survives lead changes) ────────
    customer_name = models.CharField(max_length=300)
    customer_phone = models.CharField(max_length=20)
    customer_email = models.EmailField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.DRAFT,
        db_index=True,
    )
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # percentage
    notes = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)

    # ─── Staff tracking ─────────────────────────────────────────────────────
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_invoices',
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_invoices',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'invoices'
        ordering = ['-created_at']
        verbose_name = 'فاکتور'
        verbose_name_plural = 'فاکتورها'
        indexes = [models.Index(fields=['status', 'created_by'])]

    def __str__(self):
        return f'Invoice #{self.number} — {self.customer_name}'

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = self._generate_number()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_number():
        import uuid
        from django.utils import timezone
        prefix = timezone.now().strftime('%Y%m')
        suffix = uuid.uuid4().hex[:6].upper()
        return f'INV-{prefix}-{suffix}'

    @property
    def subtotal(self):
        return sum(item.total_price for item in self.items.all())

    @property
    def tax_amount(self):
        return round(self.subtotal * self.tax_rate / 100, 2)

    @property
    def total_amount(self):
        return round(self.subtotal + self.tax_amount - self.discount, 2)

    @property
    def paid_amount(self):
        return sum(p.amount for p in self.manual_payments.filter(is_confirmed=True))

    @property
    def remaining_amount(self):
        return round(self.total_amount - self.paid_amount, 2)


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        db_table = 'invoice_items'

    def __str__(self):
        return f'{self.description} x{self.quantity}'

    @property
    def total_price(self):
        return round(self.quantity * self.unit_price, 2)


class ManualPayment(models.Model):
    """Records an offline/manual payment against an invoice."""
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='manual_payments')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    reference = models.CharField(max_length=200, blank=True, help_text='Cheque no., transfer ID, etc.')
    description = models.TextField(blank=True)

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='manual_payments_recorded',
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='manual_payments_confirmed',
    )
    is_confirmed = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    payment_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'manual_payments'
        ordering = ['-created_at']

    def __str__(self):
        return f'Payment {self.amount} on {self.invoice}'
