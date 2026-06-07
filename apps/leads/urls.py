from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.leads.views import LeadViewSet

router = DefaultRouter()
router.register('', LeadViewSet, basename='lead')

urlpatterns = [
    path('', include(router.urls)),
]
