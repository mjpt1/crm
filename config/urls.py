"""Main URL configuration."""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

api_v1_patterns = [
    path('auth/', include('apps.users.urls')),
    path('leads/', include('apps.leads.urls')),
    path('sales/', include('apps.sales.urls')),
    path('payments/', include('apps.payments.urls')),
    path('reports/', include('apps.reports.urls')),
    path('rewards/', include('apps.rewards.urls')),
    path('leave/', include('apps.leave.urls')),
    path('voip/', include('apps.voip.urls')),
]

urlpatterns = [
    # ─── Admin ────────────────────────────────────────────────────────────────
    path('admin/', admin.site.urls),

    # ─── API v1 ───────────────────────────────────────────────────────────────
    path('api/v1/', include(api_v1_patterns)),

    # ─── API Schema & Documentation ───────────────────────────────────────────
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # ─── Frontend (Dashboard) ─────────────────────────────────────────────────
    path('', include('apps.users.frontend_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
