from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.payments.views import OnlinePaymentViewSet, zibal_callback

router = DefaultRouter()
router.register('online', OnlinePaymentViewSet, basename='online-payment')

urlpatterns = [
    path('', include(router.urls)),
    # Zibal callback — must be accessible without authentication
    path('zibal/callback/', zibal_callback, name='zibal-callback'),
]
