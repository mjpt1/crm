"""
Online payment model — tracks Zibal gateway transactions.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.sales.models import Invoice


class PaymentGateway(models.TextChoices):
    ZIBAL = 'zibal', _('زیبال')


class PaymentStatus(models.TextChoices):
    PENDING = 'pending', _('در انتظار')
    SUCCESS = 'success', _('موفق')
    FAILED = 'failed', _('ناموفق')
    CANCELLED = 'cancelled', _('لغو شده')
    VERIFIED = 'verified', _('تأیید شده')


class OnlinePayment(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name='online_payments',
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    gateway = models.CharField(
        max_length=20,
        choices=PaymentGateway.choices,
        default=PaymentGateway.ZIBAL,
    )

    # ─── Zibal-specific fields ─────────────────────────────────────────────
    track_id = models.CharField(max_length=50, blank=True, db_index=True)
    payment_url = models.URLField(blank=True)
    ref_number = models.CharField(max_length=100, blank=True)  # Bank reference
    card_number = models.CharField(max_length=20, blank=True)  # Masked card number

    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
    )
    callback_data = models.JSONField(default=dict)  # Raw gateway callback payload

    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='initiated_payments',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = 'online_payments'
        ordering = ['-created_at']

    def __str__(self):
        return f'Payment {self.track_id} | {self.status} | {self.amount}'

    @property
    def amount_in_rials(self):
        """Zibal expects Rials. Stored value assumed to be Tomans."""
        return int(self.amount * 10)
