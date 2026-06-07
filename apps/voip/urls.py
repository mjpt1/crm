from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.voip.views import CallLogViewSet, voip_webhook

router = DefaultRouter()
router.register('calls', CallLogViewSet, basename='call-log')

urlpatterns = [
    path('', include(router.urls)),
    path('webhook/', voip_webhook, name='voip-webhook'),
]
