"""
Leave management views — requests, approvals, and calendar.
"""
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.leave.models import LeaveRequest, LeaveStatus, LeaveType
from apps.leave.serializers import (
    LeaveApprovalSerializer,
    LeaveCalendarSerializer,
    LeaveRequestCreateSerializer,
    LeaveRequestSerializer,
    LeaveTypeSerializer,
)
from apps.users.permissions import IsSupervisorOrAbove


class LeaveTypeViewSet(viewsets.ModelViewSet):
    serializer_class = LeaveTypeSerializer

    def get_queryset(self):
        qs = LeaveType.objects.filter(is_active=True)
        if not qs.exists():
            LeaveType.objects.update_or_create(
                name='مرخصی استحقاقی',
                defaults={
                    'max_days_per_year': 20,
                    'is_paid': True,
                    'description': 'نوع پیش فرض برای شروع ثبت درخواست های مرخصی.',
                    'is_active': True,
                },
            )
            qs = LeaveType.objects.filter(is_active=True)
        return qs

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsSupervisorOrAbove()]
        return [permissions.IsAuthenticated()]


class LeaveRequestViewSet(viewsets.ModelViewSet):
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        qs = LeaveRequest.objects.select_related('user', 'leave_type', 'approved_by')
        if user.can_manage_all:
            return qs
        if user.is_supervisor and user.team_id:
            return qs.filter(user__team=user.team)
        return qs.filter(user=user)

    def get_serializer_class(self):
        if self.action == 'create':
            return LeaveRequestCreateSerializer
        return LeaveRequestSerializer

    def get_permissions(self):
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.user != request.user:
            return Response({'detail': 'You can only edit your own requests.'}, status=403)
        if instance.status != LeaveStatus.PENDING:
            return Response({'detail': 'Only pending requests can be edited.'}, status=400)
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='action',
            permission_classes=[IsSupervisorOrAbove])
    def approval_action(self, request, pk=None):
        """POST /leave/requests/{id}/action/ — approve or reject."""
        leave = self.get_object()
        if leave.status != LeaveStatus.PENDING:
            return Response({'detail': 'Only pending requests can be actioned.'}, status=400)

        serializer = LeaveApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        act = serializer.validated_data['action']

        if act == 'approve':
            leave.status = LeaveStatus.APPROVED
            leave.approved_by = request.user
            leave.approved_at = timezone.now()
        else:
            leave.status = LeaveStatus.REJECTED
            leave.approved_by = request.user
            leave.approved_at = timezone.now()
            leave.rejection_reason = serializer.validated_data.get('rejection_reason', '')

        leave.save()
        return Response(LeaveRequestSerializer(leave).data)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        """POST /leave/requests/{id}/cancel/"""
        leave = self.get_object()
        if leave.user != request.user and not request.user.can_manage_all:
            return Response({'detail': 'Permission denied.'}, status=403)
        if leave.status not in (LeaveStatus.PENDING, LeaveStatus.APPROVED):
            return Response({'detail': 'This request cannot be cancelled.'}, status=400)
        leave.status = LeaveStatus.CANCELLED
        leave.save(update_fields=['status', 'updated_at'])
        return Response(LeaveRequestSerializer(leave).data)

    @action(detail=False, methods=['get'], url_path='calendar')
    def calendar(self, request):
        """GET /leave/requests/calendar/ — returns calendar-ready event list."""
        user = request.user
        qs = self.get_queryset().filter(status=LeaveStatus.APPROVED)
        date_from = request.query_params.get('start')
        date_to = request.query_params.get('end')
        if date_from:
            qs = qs.filter(end_date__gte=date_from)
        if date_to:
            qs = qs.filter(start_date__lte=date_to)
        return Response(LeaveCalendarSerializer(qs, many=True).data)
