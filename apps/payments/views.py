"""
Payment views — Zibal payment initiation, callback, and verification.
"""
import logging

from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from apps.payments.models import OnlinePayment
from apps.payments.serializers import InitiatePaymentSerializer, OnlinePaymentSerializer
from apps.payments.services import ZibalException, ZibalService
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
        serializer = InitiatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice = get_object_or_404(Invoice, id=serializer.validated_data['invoice_id'])
        try:
            payment = ZibalService.initiate_payment(invoice=invoice, initiated_by=request.user)
        except ZibalException as e:
            return Response({'detail': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
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


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def payment_settings(request):
    """Expose non-sensitive payment gateway settings for system settings UI."""
    user = request.user
    if not (user.can_manage_all or user.is_supervisor or user.is_finance):
        return Response({'detail': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)

    merchant = (settings.ZIBAL_MERCHANT or '').strip()
    masked_merchant = merchant[:4] + '***' if merchant and merchant.lower() != 'zibal' else merchant

    data = {
        'gateway': 'zibal',
        'merchant_configured': bool(merchant),
        'merchant': masked_merchant,
        'request_url': settings.ZIBAL_REQUEST_URL,
        'verify_url': settings.ZIBAL_VERIFY_URL,
        'payment_url_pattern': settings.ZIBAL_PAYMENT_URL,
        'callback_url': settings.ZIBAL_CALLBACK_URL,
    }
    return Response(data)
