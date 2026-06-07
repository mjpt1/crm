"""API URL routing for the users app."""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenBlacklistView

from apps.users.views import AuditLogViewSet, LoginView, TeamViewSet, UserViewSet

router = DefaultRouter()
router.register('users', UserViewSet, basename='user')
router.register('teams', TeamViewSet, basename='team')
router.register('audit-logs', AuditLogViewSet, basename='audit-log')

urlpatterns = [
    # ─── JWT Auth ─────────────────────────────────────────────────────────────
    path('login/', LoginView.as_view(), name='token-obtain'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('logout/', TokenBlacklistView.as_view(), name='token-blacklist'),

    # ─── User / Team / Audit CRUD ─────────────────────────────────────────────
    path('', include(router.urls)),
]
