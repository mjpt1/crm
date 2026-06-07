from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.sales.views import InvoiceViewSet, ManualPaymentViewSet

router = DefaultRouter()
router.register('invoices', InvoiceViewSet, basename='invoice')
router.register('manual-payments', ManualPaymentViewSet, basename='manual-payment')

urlpatterns = [
    path('', include(router.urls)),
]
