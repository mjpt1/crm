"""
Sales Target and Reward models.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class TargetType(models.TextChoices):
    REVENUE = 'revenue', _('هدف درآمد (تومان)')
    INVOICE_COUNT = 'invoice_count', _('تعداد فاکتور')
    LEAD_CONVERSION = 'lead_conversion', _('نرخ تبدیل سرنخ (%)')


class SalesTarget(models.Model):
    """Defines a performance target for a user or team in a period."""
    title = models.CharField(max_length=200)
    target_type = models.CharField(max_length=20, choices=TargetType.choices)

    # Target can be for individual user OR team (one of these should be set)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sales_targets',
    )
    team = models.ForeignKey(
        'users.Team',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sales_targets',
    )

    target_value = models.DecimalField(max_digits=16, decimal_places=2)
    period_start = models.DateField(db_index=True)
    period_end = models.DateField(db_index=True)
    description = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_targets',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sales_targets'
        ordering = ['-period_start']
        verbose_name = 'هدف فروش'
        verbose_name_plural = 'اهداف فروش'

    def __str__(self):
        assignee = self.user or self.team
        return f'{self.title} | {assignee} | {self.period_start} → {self.period_end}'

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.user and not self.team:
            raise ValidationError('Target must be assigned to either a user or a team.')
        if self.user and self.team:
            raise ValidationError('Target cannot be assigned to both a user and a team.')
        if self.period_start >= self.period_end:
            raise ValidationError('period_end must be after period_start.')


class Reward(models.Model):
    """A reward granted to a user — may be linked to a target."""
    target = models.ForeignKey(
        SalesTarget,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rewards',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='rewards',
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_auto = models.BooleanField(default=False, help_text='Automatically granted on target completion')
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='rewards_granted',
    )
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'rewards'
        ordering = ['-granted_at']

    def __str__(self):
        return f'Reward {self.amount} → {self.user} ({self.title})'
