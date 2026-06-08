"""
Payment views — Zibal payment initiation, callback, and verification.
"""
import logging

from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from apps.payments.models import OnlinePayment, PaymentGatewayConfig
from apps.payments.serializers import (
    InitiatePaymentSerializer,
    OnlinePaymentSerializer,
    PaymentSettingsSerializer,
)
from apps.payments.services import ZibalException, ZibalService
from apps.payments.models import PaymentStatus
from apps.sales.models import Invoice

logger = logging.getLogger(__name__)


class OnlinePaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only list/detail of online payment records."""
    serializer_class = OnlinePaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = OnlinePayment.objects.select_related('invoice', 'initiated_by')
        if user.can_manage_all or user.is_finance:
            return qs
        return qs.filter(initiated_by=user)

    @action(detail=False, methods=['post'], url_path='initiate')
    def initiate(self, request):
        """
        POST /payments/online/initiate/
        Initiates a Zibal payment for an approved invoice.
        Returns the payment URL to redirect the customer to.
        """
        try:
            serializer = InitiatePaymentSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            invoice = get_object_or_404(Invoice, id=serializer.validated_data['invoice_id'])
            payment = ZibalService.initiate_payment(invoice=invoice, initiated_by=request.user)
        except ZibalException as e:
            return Response({'detail': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception:
            invoice_id = request.data.get('invoice_id')
            logger.exception('Unexpected error while initiating online payment for invoice_id=%s', invoice_id)
            return Response(
                {'detail': 'Payment initiation failed. Please try again.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({
            'track_id': payment.track_id,
            'payment_url': payment.payment_url,
            'amount': payment.amount,
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='verify')
    def verify(self, request):
        """
        POST /payments/online/verify/
        Manually trigger verification for a trackId (admin/finance use).
        """
        track_id = request.data.get('track_id')
        if not track_id:
            return Response({'detail': 'track_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            payment = ZibalService.verify_payment(str(track_id))
        except ZibalException as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception('Unexpected error while verifying payment track_id=%s', track_id)
            return Response(
                {'detail': 'Payment verification failed. Please try again.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if payment.status not in (PaymentStatus.VERIFIED, PaymentStatus.SUCCESS):
            return Response(
                {
                    'detail': payment.error_message or 'Payment is not successful.',
                    'payment_status': payment.status,
                    'track_id': payment.track_id,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(OnlinePaymentSerializer(payment).data)


@api_view(['GET', 'POST'])
@permission_classes([permissions.AllowAny])
def zibal_callback(request):
    """
    GET/POST /payments/zibal/callback/
    Zibal redirects the customer here after payment completion.
    This is NOT an authenticated endpoint (called by the user's browser).
    """
    data = request.GET if request.method == 'GET' else request.data
    try:
        payment = ZibalService.handle_callback(data)
        # Redirect to a success page
        return redirect(f'/payment-success/?invoice={payment.invoice_id}')
    except ZibalException as e:
        logger.warning('Zibal callback failed: %s | data: %s', e, data)
        track_id = data.get('trackId', '')
        return redirect(f'/payment-failed/?reason={str(e)}&trackId={track_id}')


@api_view(['GET', 'PUT'])
@permission_classes([permissions.IsAuthenticated])
def payment_settings(request):
    """Expose non-sensitive payment gateway settings for system settings UI."""
    user = request.user
    if not (user.can_manage_all or user.is_supervisor or user.is_finance):
        return Response({'detail': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        cfg, _ = PaymentGatewayConfig.objects.get_or_create(
            gateway='zibal',
            defaults={
                'merchant': getattr(settings, 'ZIBAL_MERCHANT', ''),
                'callback_url': getattr(settings, 'ZIBAL_CALLBACK_URL', ''),
                'is_active': True,
                'updated_by': user,
            },
        )
    except (OperationalError, ProgrammingError):
        # Fallback before migrations: allow read-only config view from settings.
        if request.method == 'PUT':
            return Response(
                {'detail': 'Payment settings table is not ready yet. Run migrations and try again.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({
            'gateway': 'zibal',
            'merchant': getattr(settings, 'ZIBAL_MERCHANT', ''),
            'merchant_masked': '****' if getattr(settings, 'ZIBAL_MERCHANT', '') else '',
            'merchant_configured': bool(getattr(settings, 'ZIBAL_MERCHANT', '')),
            'callback_url': getattr(settings, 'ZIBAL_CALLBACK_URL', ''),
            'request_url': settings.ZIBAL_REQUEST_URL,
            'verify_url': settings.ZIBAL_VERIFY_URL,
            'payment_url_pattern': settings.ZIBAL_PAYMENT_URL,
            'is_active': True,
            'updated_at': None,
        })

    if request.method == 'GET':
        return Response(PaymentSettingsSerializer(cfg).data)

    serializer = PaymentSettingsSerializer(cfg, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    obj = serializer.save(updated_by=user)
    return Response(PaymentSettingsSerializer(obj).data)
