"""
VoIP service — click-to-dial and placeholder integration.
"""
import hashlib
import hmac
import logging

import requests
from django.conf import settings
from django.utils import timezone

from apps.voip.models import CallDirection, CallLog, CallStatus

logger = logging.getLogger(__name__)


class VoipService:
    """
    Adapter for a generic REST-based VoIP provider.
    Replace the API calls with your specific VoIP vendor's SDK/endpoints.
    """

    @classmethod
    def _headers(cls):
        return {
            'Authorization': f'Bearer {settings.VOIP_API_KEY}',
            'Content-Type': 'application/json',
        }

    @classmethod
    def click_to_dial(cls, agent, phone_number, lead=None):
        """
        Initiates an outbound call from the agent's extension to phone_number.
        Returns a CallLog instance.
        """
        payload = {
            'agent_extension': agent.phone,
            'destination': phone_number,
        }
        call_log = CallLog.objects.create(
            agent=agent,
            lead=lead,
            phone_number=phone_number,
            direction=CallDirection.OUTBOUND,
            status=CallStatus.INITIATED,
            started_at=timezone.now(),
        )

        if not settings.VOIP_API_BASE_URL:
            logger.warning('VOIP_API_BASE_URL not configured. Dial skipped.')
            return call_log

        try:
            response = requests.post(
                f'{settings.VOIP_API_BASE_URL}/dial',
                json=payload,
                headers=cls._headers(),
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            call_log.external_call_id = str(data.get('call_id', ''))
            call_log.raw_payload = data
            call_log.save(update_fields=['external_call_id', 'raw_payload'])
        except requests.RequestException as exc:
            logger.error('VoIP dial failed for agent %s → %s: %s', agent.email, phone_number, exc)

        return call_log

    @classmethod
    def process_incoming_webhook(cls, payload, signature=None):
        """
        Processes an incoming call webhook from the VoIP provider.
        Returns a CallLog instance.
        """
        # Verify webhook signature if secret is set
        if settings.VOIP_WEBHOOK_SECRET and signature:
            cls._verify_signature(payload, signature)

        event_type = payload.get('event', '')
        external_call_id = str(payload.get('call_id', ''))
        phone_number = payload.get('caller_number', '') or payload.get('callee_number', '')

        # Try to find existing call log (for updates to ongoing call)
        call_log = CallLog.objects.filter(external_call_id=external_call_id).first()

        if not call_log:
            # Try to match lead by phone number
            from apps.leads.models import Lead
            lead = Lead.objects.filter(phone=phone_number).first()

            status_map = {
                'incoming': CallStatus.RINGING,
                'answered': CallStatus.ANSWERED,
                'missed': CallStatus.MISSED,
                'ended': CallStatus.ANSWERED,
            }
            call_log = CallLog(
                phone_number=phone_number,
                direction=CallDirection.INBOUND,
                status=status_map.get(event_type, CallStatus.INITIATED),
                started_at=timezone.now(),
                external_call_id=external_call_id,
                lead=lead,
                raw_payload=payload,
            )
        else:
            call_log.raw_payload = payload

        # Update status from event
        if event_type == 'answered':
            call_log.status = CallStatus.ANSWERED
        elif event_type == 'missed':
            call_log.status = CallStatus.MISSED
        elif event_type == 'ended':
            call_log.ended_at = timezone.now()
            if call_log.started_at:
                call_log.duration_seconds = int(
                    (call_log.ended_at - call_log.started_at).total_seconds()
                )
            recording_url = payload.get('recording_url', '')
            if recording_url:
                call_log.recording_url = recording_url

        call_log.save()
        logger.info('VoIP webhook processed: event=%s call_id=%s', event_type, external_call_id)
        return call_log

    @staticmethod
    def _verify_signature(payload, received_signature):
        """HMAC-SHA256 signature verification."""
        import json
        body = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode()
        expected = hmac.new(
            settings.VOIP_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, received_signature):
            raise ValueError('Invalid webhook signature.')
