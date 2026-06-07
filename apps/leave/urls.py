from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.leave.views import LeaveRequestViewSet, LeaveTypeViewSet

router = DefaultRouter()
router.register('types', LeaveTypeViewSet, basename='leave-type')
router.register('requests', LeaveRequestViewSet, basename='leave-request')

urlpatterns = [path('', include(router.urls))]
