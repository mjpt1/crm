"""
VoIP Call Log model.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.leads.models import Lead


class CallDirection(models.TextChoices):
    INBOUND = 'inbound', _('ورودی')
    OUTBOUND = 'outbound', _('خروجی')


class CallStatus(models.TextChoices):
    INITIATED = 'initiated', _('شروع شده')
    RINGING = 'ringing', _('در حال زنگ')
    ANSWERED = 'answered', _('پاسخ داده شد')
    MISSED = 'missed', _('از دست رفته')
    BUSY = 'busy', _('اشغال')
    FAILED = 'failed', _('ناموفق')
    VOICEMAIL = 'voicemail', _('پیغام صوتی')


class CallLog(models.Model):
    # ─── Parties ──────────────────────────────────────────────────────────────
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='call_logs',
    )
    lead = models.ForeignKey(
        Lead,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='call_logs',
    )
    phone_number = models.CharField(max_length=20)  # caller/callee number

    # ─── Call Details ─────────────────────────────────────────────────────────
    direction = models.CharField(max_length=10, choices=CallDirection.choices, db_index=True)
    status = models.CharField(max_length=20, choices=CallStatus.choices, default=CallStatus.INITIATED)
    duration_seconds = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    # ─── Recording ────────────────────────────────────────────────────────────
    recording_url = models.URLField(blank=True)

    # ─── Gateway Metadata ─────────────────────────────────────────────────────
    external_call_id = models.CharField(max_length=100, blank=True, db_index=True)
    raw_payload = models.JSONField(default=dict)

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'call_logs'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['agent', 'started_at']),
            models.Index(fields=['lead', 'started_at']),
        ]

    def __str__(self):
        return f'{self.direction} call | {self.phone_number} | {self.status} | {self.started_at}'

    @property
    def duration_formatted(self):
        m, s = divmod(self.duration_seconds, 60)
        h, m = divmod(m, 60)
        return f'{h:02d}:{m:02d}:{s:02d}'
