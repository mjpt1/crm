"""
Online payment model — tracks Zibal gateway transactions.
"""
from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError
from django.db import connection, models
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


class PaymentGatewayConfig(models.Model):
    """Stores editable payment gateway settings from the admin UI."""
    gateway = models.CharField(
        max_length=20,
        choices=PaymentGateway.choices,
        default=PaymentGateway.ZIBAL,
        unique=True,
    )
    merchant = models.CharField(max_length=200, blank=True)
    callback_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_gateway_configs',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payment_gateway_configs'
        ordering = ['gateway']

    def __str__(self):
        return f'{self.gateway} config'

    @classmethod
    def get_zibal_config(cls):
        table_name = cls._meta.db_table
        try:
            if table_name not in connection.introspection.table_names():
                return None
            return cls.objects.filter(gateway=PaymentGateway.ZIBAL).first()
        except (OperationalError, ProgrammingError):
            # Table may not exist yet on fresh deployments before migrations run.
            return None
