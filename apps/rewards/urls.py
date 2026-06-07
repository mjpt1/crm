from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.rewards.views import RewardViewSet, SalesTargetViewSet

router = DefaultRouter()
router.register('targets', SalesTargetViewSet, basename='target')
router.register('rewards', RewardViewSet, basename='reward')

urlpatterns = [path('', include(router.urls))]
