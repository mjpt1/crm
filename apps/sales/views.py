"""
Invoice and Manual Payment views with full approval workflow.
"""
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.sales.models import Invoice, ManualPayment
from apps.sales.permissions import CanAccessInvoice, CanApproveInvoice, CanCreateInvoice
from apps.sales.serializers import (
    InvoiceCreateSerializer,
    InvoiceDetailSerializer,
    InvoiceListSerializer,
    InvoiceUpdateSerializer,
    ManualPaymentCreateSerializer,
    ManualPaymentSerializer,
)
from apps.sales.services import InvoiceService, ManualPaymentService


class InvoiceViewSet(viewsets.ModelViewSet):
    """
    Invoice CRUD + workflow actions (submit, approve, reject, cancel).
    """
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        qs = Invoice.objects.select_related('created_by', 'approved_by', 'lead').prefetch_related('items')
        if user.can_manage_all or user.is_finance:
            pass
        elif user.is_supervisor and user.team_id:
            qs = qs.filter(created_by__team=user.team)
        else:
            qs = qs.filter(created_by=user)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def get_serializer_class(self):
        if self.action == 'create':
            return InvoiceCreateSerializer
        if self.action in ('update', 'partial_update'):
            return InvoiceUpdateSerializer
        if self.action == 'list':
            return InvoiceListSerializer
        return InvoiceDetailSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [CanCreateInvoice()]
        if self.action in ('approve', 'reject'):
            return [CanApproveInvoice()]
        return [permissions.IsAuthenticated(), CanAccessInvoice()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    # ─── Workflow Actions ─────────────────────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='submit')
    def submit(self, request, pk=None):
        """Submit draft invoice for finance approval."""
        invoice = self.get_object()
        try:
            invoice = InvoiceService.submit_for_approval(invoice, request.user)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(InvoiceDetailSerializer(invoice).data)

    @action(detail=True, methods=['post'], url_path='approve',
            permission_classes=[CanApproveInvoice])
    def approve(self, request, pk=None):
        """Finance approves pending invoice."""
        invoice = self.get_object()
        try:
            invoice = InvoiceService.approve_invoice(invoice, request.user)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(InvoiceDetailSerializer(invoice).data)

    @action(detail=True, methods=['post'], url_path='reject',
            permission_classes=[CanApproveInvoice])
    def reject(self, request, pk=None):
        """Finance rejects pending invoice (reverts to draft)."""
        invoice = self.get_object()
        try:
            invoice = InvoiceService.reject_invoice(invoice, request.user)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(InvoiceDetailSerializer(invoice).data)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        """Cancel an invoice."""
        invoice = self.get_object()
        try:
            invoice = InvoiceService.cancel_invoice(invoice, request.user)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(InvoiceDetailSerializer(invoice).data)


class ManualPaymentViewSet(viewsets.ModelViewSet):
    """
    Record and manage manual payments.
    Finance can confirm them.
    """
    serializer_class = ManualPaymentSerializer
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        qs = ManualPayment.objects.select_related('invoice', 'recorded_by', 'confirmed_by')
        if user.can_manage_all or user.is_finance:
            return qs
        if user.is_supervisor and user.team_id:
            return qs.filter(recorded_by__team=user.team)
        return qs.filter(recorded_by=user)

    def get_serializer_class(self):
        if self.action == 'create':
            return ManualPaymentCreateSerializer
        return ManualPaymentSerializer

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='confirm',
            permission_classes=[CanApproveInvoice])
    def confirm(self, request, pk=None):
        """Finance confirms a manual payment."""
        payment = self.get_object()
        try:
            payment = ManualPaymentService.confirm_payment(payment, request.user)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ManualPaymentSerializer(payment).data)
