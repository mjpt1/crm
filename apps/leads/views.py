"""
Lead management views — CRUD, status updates, auto-assignment.
"""
from django.shortcuts import get_object_or_404
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.leads.models import Lead, LeadNote, LeadStatusHistory
from apps.leads.permissions import CanAccessLead, CanManageLeads
from apps.leads.serializers import (
    LeadCreateSerializer,
    LeadDetailSerializer,
    LeadListSerializer,
    LeadNoteSerializer,
    LeadStatusUpdateSerializer,
    LeadUpdateSerializer,
    ManualAssignSerializer,
)
from apps.leads.services import LeadAssignmentService, LeadStatusService
from apps.users.models import CustomUser


class LeadViewSet(viewsets.ModelViewSet):
    """
    Complete lead management endpoint.
    Filtering by status, assigned_to, source is supported via query params.
    """
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['first_name', 'last_name', 'phone', 'email', 'company']
    ordering_fields = ['created_at', 'updated_at', 'status', 'priority']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        qs = Lead.objects.select_related('assigned_to', 'created_by')
        if user.can_manage_all:
            pass  # all leads
        elif user.is_supervisor and user.team_id:
            qs = qs.filter(assigned_to__team=user.team)
        else:
            qs = qs.filter(assigned_to=user)

        # Optional filters
        status_filter = self.request.query_params.get('status')
        source_filter = self.request.query_params.get('source')
        assigned_filter = self.request.query_params.get('assigned_to')
        if status_filter:
            qs = qs.filter(status=status_filter)
        if source_filter:
            qs = qs.filter(source=source_filter)
        if assigned_filter:
            qs = qs.filter(assigned_to_id=assigned_filter)
        return qs

    def get_serializer_class(self):
        if self.action == 'create':
            return LeadCreateSerializer
        if self.action in ('update', 'partial_update'):
            return LeadUpdateSerializer
        if self.action == 'list':
            return LeadListSerializer
        return LeadDetailSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [CanManageLeads()]
        if self.action in ('update', 'partial_update', 'destroy'):
            return [permissions.IsAuthenticated(), CanAccessLead()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, status='new')

    # ─── Status Update ────────────────────────────────────────────────────────
    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, pk=None):
        """PATCH /leads/{id}/status/ — auto-save status dropdown."""
        lead = self.get_object()
        serializer = LeadStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lead = LeadStatusService.change_status(
            lead=lead,
            new_status=serializer.validated_data['status'],
            changed_by=request.user,
            notes=serializer.validated_data.get('notes', ''),
        )
        return Response(LeadDetailSerializer(lead).data)

    # ─── Auto-Assignment ──────────────────────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='request-leads')
    def request_leads(self, request):
        """POST /leads/request-leads/ — expert requests a batch of new leads."""
        assigned = LeadAssignmentService.request_leads(expert=request.user)
        if not assigned:
            return Response(
                {'detail': 'No unassigned leads available at this time.'},
                status=status.HTTP_200_OK,
            )
        return Response(
            {'assigned_count': len(assigned), 'leads': LeadListSerializer(assigned, many=True).data},
            status=status.HTTP_200_OK,
        )

    # ─── Manual Assignment ────────────────────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='assign',
            permission_classes=[CanManageLeads])
    def assign(self, request, pk=None):
        """POST /leads/{id}/assign/ — manually assign lead to expert."""
        lead = self.get_object()
        serializer = ManualAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        expert = CustomUser.objects.get(id=serializer.validated_data['expert_id'])
        lead = LeadAssignmentService.manual_assign(
            lead=lead, expert=expert, assigned_by=request.user
        )
        return Response(LeadDetailSerializer(lead).data)

    # ─── Notes ────────────────────────────────────────────────────────────────
    @action(detail=True, methods=['get', 'post'], url_path='notes')
    def notes(self, request, pk=None):
        lead = self.get_object()
        if request.method == 'GET':
            notes = lead.notes.select_related('author')
            return Response(LeadNoteSerializer(notes, many=True).data)
        serializer = LeadNoteSerializer(data={**request.data, 'lead': lead.id})
        serializer.is_valid(raise_exception=True)
        serializer.save(author=request.user, lead=lead)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # ─── History ──────────────────────────────────────────────────────────────
    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None):
        lead = self.get_object()
        from apps.leads.serializers import LeadStatusHistorySerializer
        history = lead.status_history.select_related('changed_by')
        return Response(LeadStatusHistorySerializer(history, many=True).data)
