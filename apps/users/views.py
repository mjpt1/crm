"""
Views for user management, authentication, and team management.
"""
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.users.models import AuditLog, CustomUser, Team
from apps.users.permissions import CanManageUsers, IsSuperAdmin, IsSupervisorOrAbove
from apps.users.serializers import (
    AuditLogSerializer,
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer,
    TeamDetailSerializer,
    TeamListSerializer,
    TeamWriteSerializer,
    UserCreateSerializer,
    UserDetailSerializer,
    UserListSerializer,
    UserUpdateSerializer,
)
from apps.users.services import AuditService


# ─── Authentication Views ─────────────────────────────────────────────────────
@method_decorator(ratelimit(key='ip', rate='5/m', method='POST', block=True), name='post')
class LoginView(TokenObtainPairView):
    """Rate-limited JWT login endpoint."""
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            # Log successful login
            from apps.users.models import CustomUser as CU
            try:
                email = request.data.get('email', '')
                user = CU.objects.get(email=email)
                AuditService.log(
                    user=user,
                    action=AuditLog.ACTION_LOGIN,
                    model_name='CustomUser',
                    object_id=str(user.id),
                    request=request,
                )
            except CU.DoesNotExist:
                pass
        return response


# ─── User ViewSet ─────────────────────────────────────────────────────────────
class UserViewSet(viewsets.ModelViewSet):
    """
    Full CRUD for users.
    - Super Admin / Sales Manager: full access.
    - Supervisor: read-only for team members.
    - Others: read/update own profile only.
    """
    queryset = CustomUser.objects.select_related('team').order_by('first_name')

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        if self.action in ('update', 'partial_update'):
            return UserUpdateSerializer
        if self.action == 'list':
            return UserListSerializer
        return UserDetailSerializer

    def get_permissions(self):
        if self.action in ('create', 'destroy'):
            return [CanManageUsers()]
        if self.action in ('update', 'partial_update'):
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = CustomUser.objects.select_related('team')
        if user.can_manage_all:
            return qs
        if user.is_supervisor and user.team_id:
            return qs.filter(team=user.team)
        return qs.filter(id=user.id)

    def update(self, request, *args, **kwargs):
        """Non-admins can only update their own profile."""
        instance = self.get_object()
        if not request.user.can_manage_all and instance.id != request.user.id:
            return Response({'detail': 'You can only update your own profile.'}, status=403)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Soft-delete: deactivate instead of hard-delete."""
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        AuditService.log(
            user=request.user,
            action=AuditLog.ACTION_DELETE,
            model_name='CustomUser',
            object_id=str(instance.id),
            request=request,
        )
        return Response({'detail': 'User deactivated successfully.'}, status=204)

    @action(detail=False, methods=['get', 'patch'], url_path='me')
    def me(self, request):
        """Retrieve or update the currently authenticated user's profile."""
        if request.method == 'GET':
            serializer = UserDetailSerializer(request.user)
            return Response(serializer.data)
        serializer = UserUpdateSerializer(
            request.user, data=request.data, partial=True, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserDetailSerializer(request.user).data)

    @action(detail=False, methods=['post'], url_path='change-password')
    def change_password(self, request):
        """Change authenticated user's password."""
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': 'Password changed successfully.'})


# ─── Team ViewSet ─────────────────────────────────────────────────────────────
class TeamViewSet(viewsets.ModelViewSet):
    queryset = Team.objects.prefetch_related('members').select_related('supervisor')

    def get_serializer_class(self):
        if self.action == 'list':
            return TeamListSerializer
        if self.action in ('create', 'update', 'partial_update'):
            return TeamWriteSerializer
        return TeamDetailSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsSupervisorOrAbove()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.can_manage_all:
            return Team.objects.all()
        if user.is_supervisor and user.team_id:
            return Team.objects.filter(id=user.team_id)
        return Team.objects.none()

    def perform_create(self, serializer):
        team = serializer.save()
        AuditService.log(
            user=self.request.user,
            action=AuditLog.ACTION_CREATE,
            model_name='Team',
            object_id=str(team.id),
            request=self.request,
        )


# ─── Audit Log ViewSet (read-only) ────────────────────────────────────────────
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [IsSuperAdmin]
    filterset_fields = ['user', 'action', 'model_name']
    search_fields = ['model_name', 'object_id']
    ordering_fields = ['timestamp']

    def get_queryset(self):
        return AuditLog.objects.select_related('user').order_by('-timestamp')
