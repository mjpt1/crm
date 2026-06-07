"""
VoIP views — call log history, click-to-dial, and incoming webhook.
"""
import logging

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from apps.voip.models import CallLog
from apps.voip.serializers import CallLogSerializer, ClickToDialSerializer
from apps.voip.services import VoipService

logger = logging.getLogger(__name__)


class CallLogViewSet(viewsets.ModelViewSet):
    """
    List, retrieve, and create call log entries.
    Webhook and dial endpoints are separate views.
    """
    serializer_class = CallLogSerializer
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    ordering = ['-started_at']

    def get_queryset(self):
        user = self.request.user
        qs = CallLog.objects.select_related('agent', 'lead')
        if user.can_manage_all:
            return qs
        if user.is_supervisor and user.team_id:
            return qs.filter(agent__team=user.team)
        return qs.filter(agent=user)

    def get_permissions(self):
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(agent=self.request.user)

    @action(detail=False, methods=['post'], url_path='dial')
    def dial(self, request):
        """POST /voip/calls/dial/ — initiate a click-to-dial call."""
        serializer = ClickToDialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data['phone_number']
        lead_id = serializer.validated_data.get('lead_id')
        lead = None
        if lead_id:
            from apps.leads.models import Lead
            lead = Lead.objects.filter(id=lead_id).first()
        call_log = VoipService.click_to_dial(
            agent=request.user,
            phone_number=phone_number,
            lead=lead,
        )
        return Response(CallLogSerializer(call_log).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def voip_webhook(request):
    """
    POST /voip/webhook/
    Receives incoming call events from the VoIP provider.
    No authentication required — signature verification is done inside VoipService.
    """
    signature = request.headers.get('X-VoIP-Signature', '')
    try:
        call_log = VoipService.process_incoming_webhook(request.data, signature=signature)
        return Response({'status': 'ok', 'call_id': call_log.id})
    except ValueError as e:
        logger.warning('VoIP webhook signature failure: %s', e)
        return Response({'detail': 'Invalid signature.'}, status=status.HTTP_403_FORBIDDEN)
    except Exception as e:
        logger.exception('VoIP webhook error: %s', e)
        return Response({'detail': 'Webhook processing error.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
