"""
Lead, LeadAssignment, LeadStatusHistory, and LeadNote models.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class LeadStatus(models.TextChoices):
    NEW = 'new', _('جدید')
    CONTACTED = 'contacted', _('تماس‌گرفته‌شده')
    QUALIFIED = 'qualified', _('واجد شرایط')
    NEGOTIATION = 'negotiation', _('در مذاکره')
    WON = 'won', _('برنده')
    LOST = 'lost', _('از دست‌رفته')
    INVALID = 'invalid', _('نامعتبر')


class LeadSource(models.TextChoices):
    WEBSITE = 'website', _('وب‌سایت')
    REFERRAL = 'referral', _('معرفی')
    COLD_CALL = 'cold_call', _('تماس سرد')
    SOCIAL_MEDIA = 'social_media', _('شبکه اجتماعی')
    EMAIL = 'email', _('کمپین ایمیل')
    EXHIBITION = 'exhibition', _('نمایشگاه')
    OTHER = 'other', _('سایر')


class Lead(models.Model):
    # ─── Customer Identity ─────────────────────────────────────────────────
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, db_index=True)
    email = models.EmailField(blank=True)
    company = models.CharField(max_length=200, blank=True)
    address = models.TextField(blank=True)

    # ─── Lead Metadata ─────────────────────────────────────────────────────
    source = models.CharField(max_length=20, choices=LeadSource.choices, default=LeadSource.OTHER)
    status = models.CharField(
        max_length=20,
        choices=LeadStatus.choices,
        default=LeadStatus.NEW,
        db_index=True,
    )
    priority = models.PositiveSmallIntegerField(default=2)  # 1=High, 2=Medium, 3=Low

    # ─── Assignment ────────────────────────────────────────────────────────
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_leads',
        db_index=True,
    )
    assigned_at = models.DateTimeField(null=True, blank=True)

    # ─── Tracking ──────────────────────────────────────────────────────────
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_leads',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'leads'
        ordering = ['-created_at']
        verbose_name = 'سرنخ'
        verbose_name_plural = 'سرنخ‌ها'
        indexes = [
            models.Index(fields=['status', 'assigned_to']),
            models.Index(fields=['phone']),
        ]

    def __str__(self):
        return f'{self.first_name} {self.last_name} ({self.phone})'

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'


class LeadAssignment(models.Model):
    """Tracks every assignment event for a lead."""
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='assignments')
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lead_assignments',
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='lead_assignments_made',
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)  # False when reassigned

    class Meta:
        db_table = 'lead_assignments'
        ordering = ['-assigned_at']
        verbose_name = 'تخصیص سرنخ'
        verbose_name_plural = 'تخصیص‌های سرنخ'

    def __str__(self):
        return f'{self.lead} → {self.assigned_to} at {self.assigned_at}'


class LeadStatusHistory(models.Model):
    """Immutable audit trail of all status changes on a lead."""
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='status_history')
    old_status = models.CharField(max_length=20, choices=LeadStatus.choices, blank=True)
    new_status = models.CharField(max_length=20, choices=LeadStatus.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='lead_status_changes',
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'lead_status_history'
        ordering = ['-changed_at']

    def __str__(self):
        return f'{self.lead} | {self.old_status} → {self.new_status}'


class LeadNote(models.Model):
    """Free-text notes attached to a lead."""
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='notes')
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='lead_notes',
    )
    content = models.TextField()
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lead_notes'
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return f'Note on {self.lead} by {self.author}'
