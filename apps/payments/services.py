"""
Zibal Payment Gateway integration service.

API Docs: https://help.zibal.ir/IPG/API/
"""
import logging

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.payments.models import OnlinePayment, PaymentStatus
from apps.sales.models import InvoiceStatus
from apps.sales.services import InvoiceService

logger = logging.getLogger(__name__)

# ─── Zibal Result Codes ───────────────────────────────────────────────────────
ZIBAL_SUCCESS_CODE = 100
ZIBAL_ALREADY_VERIFIED_CODE = 201

ZIBAL_STATUS_MESSAGES = {
    -1: 'اطلاعات ارسال شده ناقص است.',
    -2: 'IP یا merchant معتبر نیست.',
    -3: 'با توجه به محدودیت‌های شاپرک امکان پرداخت با رقم درخواست شده میسر نمی‌باشد.',
    -4: 'سطح تأیید پذیرنده پایین‌تر از سطح نقره‌ای است.',
    100: 'عملیات موفق',
    102: 'merchant یافت نشد.',
    103: 'merchant غیرفعال',
    104: 'merchant نامعتبر',
    105: 'amount بایستی بزرگتر از 1,000 ریال باشد.',
    106: 'callbackUrl نامعتبر می‌باشد.',
    113: 'amount مبلغ تراکنش از سقف مجاز بیشتر است.',
    201: 'قبلاً تأیید شده.',
    202: 'سفارش پرداخت نشده یا ناموفق بوده است.',
    203: 'trackId نامعتبر است.',
}


class ZibalService:
    """
    Encapsulates all interactions with the Zibal payment gateway.
    """

    REQUEST_TIMEOUT = 15  # seconds

    @classmethod
    def _post(cls, url, payload):
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=cls.REQUEST_TIMEOUT,
                headers={'Content-Type': 'application/json'},
            )
            response.raise_for_status()
            return response.json()
        except requests.Timeout:
            logger.error('Zibal API timeout: %s', url)
            raise ZibalException('Payment gateway timeout. Please try again.')
        except requests.RequestException as exc:
            logger.error('Zibal API request error: %s — %s', url, exc)
            raise ZibalException('Could not connect to payment gateway.')

    @classmethod
    @transaction.atomic
    def initiate_payment(cls, invoice, initiated_by):
        """
        Step 1: Request a trackId from Zibal, create an OnlinePayment record,
        and return the payment URL to redirect the customer to.
        """
        amount_rials = int(invoice.total_amount * 10)  # Tomans → Rials
        if amount_rials < 1000:
            raise ZibalException('Minimum payment amount is 100 Tomans.')

        payload = {
            'merchant': settings.ZIBAL_MERCHANT,
            'amount': amount_rials,
            'callbackUrl': settings.ZIBAL_CALLBACK_URL,
            'description': f'Payment for invoice {invoice.number}',
            'orderId': str(invoice.id),
        }

        data = cls._post(settings.ZIBAL_REQUEST_URL, payload)
        result_code = data.get('result')

        if result_code != ZIBAL_SUCCESS_CODE:
            msg = ZIBAL_STATUS_MESSAGES.get(result_code, f'Gateway error code: {result_code}')
            logger.error('Zibal initiate failed for invoice %s: %s', invoice.number, msg)
            raise ZibalException(msg)

        track_id = str(data['trackId'])
        payment_url = settings.ZIBAL_PAYMENT_URL.format(track_id=track_id)

        payment = OnlinePayment.objects.create(
            invoice=invoice,
            amount=invoice.total_amount,
            track_id=track_id,
            payment_url=payment_url,
            status=PaymentStatus.PENDING,
            initiated_by=initiated_by,
        )

        logger.info(
            'Zibal payment initiated: trackId=%s invoice=%s',
            track_id, invoice.number,
        )
        return payment

    @classmethod
    @transaction.atomic
    def verify_payment(cls, track_id):
        """
        Step 2: Called after the customer completes (or fails) payment.
        Verifies the transaction and updates invoice status.
        Returns the OnlinePayment instance.
        """
        try:
            payment = OnlinePayment.objects.select_for_update().get(track_id=track_id)
        except OnlinePayment.DoesNotExist:
            raise ZibalException(f'No payment record found for trackId: {track_id}')

        if payment.status == PaymentStatus.VERIFIED:
            logger.warning('Payment %s already verified', track_id)
            return payment

        payload = {
            'merchant': settings.ZIBAL_MERCHANT,
            'trackId': int(track_id),
        }

        data = cls._post(settings.ZIBAL_VERIFY_URL, payload)
        result_code = data.get('result')

        payment.callback_data = data

        if result_code in (ZIBAL_SUCCESS_CODE, ZIBAL_ALREADY_VERIFIED_CODE):
            payment.status = PaymentStatus.VERIFIED
            payment.ref_number = str(data.get('refNumber', ''))
            payment.card_number = str(data.get('cardNumber', ''))
            payment.verified_at = timezone.now()
            payment.save()

            # Update invoice payment status
            InvoiceService.recalculate_payment_status(payment.invoice)

            logger.info(
                'Zibal payment verified: trackId=%s refNumber=%s',
                track_id, payment.ref_number,
            )
        else:
            msg = ZIBAL_STATUS_MESSAGES.get(result_code, f'Verification failed: {result_code}')
            payment.status = PaymentStatus.FAILED
            payment.error_message = msg
            payment.save()
            logger.warning('Zibal payment failed: trackId=%s code=%s', track_id, result_code)

        return payment

    @classmethod
    def handle_callback(cls, request_data):
        """
        Process the callback/redirect from Zibal after the user's browser is redirected back.
        Zibal sends: trackId, success, status, orderId
        """
        track_id = str(request_data.get('trackId', ''))
        success = int(request_data.get('success', 0))

        if not track_id:
            raise ZibalException('Missing trackId in callback.')

        if success != 1:
            # Payment was cancelled or failed at gateway
            try:
                payment = OnlinePayment.objects.get(track_id=track_id)
                payment.status = PaymentStatus.CANCELLED
                payment.callback_data = dict(request_data)
                payment.error_message = 'Payment cancelled by user or gateway.'
                payment.save()
            except OnlinePayment.DoesNotExist:
                pass
            raise ZibalException('Payment was not completed.')

        return cls.verify_payment(track_id)


class ZibalException(Exception):
    """Raised when a Zibal API call fails."""
    pass
