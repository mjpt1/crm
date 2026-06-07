from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.rewards.models import Reward, SalesTarget
from apps.rewards.serializers import RewardCreateSerializer, RewardSerializer, SalesTargetSerializer
from apps.rewards.services import TargetCalculationService
from apps.users.permissions import IsSalesManager, IsSupervisorOrAbove


class SalesTargetViewSet(viewsets.ModelViewSet):
    serializer_class = SalesTargetSerializer
    ordering = ['-period_start']

    def get_queryset(self):
        user = self.request.user
        qs = SalesTarget.objects.select_related('user', 'team', 'created_by')
        if user.can_manage_all:
            return qs
        if user.is_supervisor and user.team_id:
            return qs.filter(team=user.team) | qs.filter(user__team=user.team)
        return qs.filter(user=user)

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsSalesManager()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['get'], url_path='achievement')
    def achievement(self, request, pk=None):
        target = self.get_object()
        data = TargetCalculationService.calculate_achievement(target)
        return Response(data)


class RewardViewSet(viewsets.ModelViewSet):
    ordering = ['-granted_at']

    def get_queryset(self):
        user = self.request.user
        qs = Reward.objects.select_related('user', 'granted_by', 'target')
        if user.can_manage_all:
            return qs
        if user.is_supervisor and user.team_id:
            return qs.filter(user__team=user.team)
        return qs.filter(user=user)

    def get_serializer_class(self):
        if self.action == 'create':
            return RewardCreateSerializer
        return RewardSerializer

    def get_permissions(self):
        if self.action in ('create', 'destroy'):
            return [IsSalesManager()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(granted_by=self.request.user, is_auto=False)
