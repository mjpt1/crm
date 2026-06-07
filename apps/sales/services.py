"""
Invoice business logic — approval workflow, payment confirmation, status sync.
"""
import logging

from django.db import transaction
from django.utils import timezone

from apps.sales.models import Invoice, InvoiceStatus, ManualPayment

logger = logging.getLogger(__name__)


class InvoiceService:

    @staticmethod
    @transaction.atomic
    def submit_for_approval(invoice, submitted_by):
        if invoice.status != InvoiceStatus.DRAFT:
            raise ValueError('Only draft invoices can be submitted for approval.')
        if not invoice.items.exists():
            raise ValueError('Invoice must have at least one item.')
        invoice.status = InvoiceStatus.PENDING_APPROVAL
        invoice.save(update_fields=['status', 'updated_at'])
        logger.info('Invoice %s submitted for approval by %s', invoice.number, submitted_by.email)
        return invoice

    @staticmethod
    @transaction.atomic
    def approve_invoice(invoice, approved_by):
        if invoice.status != InvoiceStatus.PENDING_APPROVAL:
            raise ValueError('Only pending invoices can be approved.')
        invoice.status = InvoiceStatus.APPROVED
        invoice.approved_by = approved_by
        invoice.approved_at = timezone.now()
        invoice.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])
        logger.info('Invoice %s approved by %s', invoice.number, approved_by.email)
        return invoice

    @staticmethod
    @transaction.atomic
    def reject_invoice(invoice, rejected_by):
        if invoice.status != InvoiceStatus.PENDING_APPROVAL:
            raise ValueError('Only pending invoices can be rejected.')
        invoice.status = InvoiceStatus.DRAFT
        invoice.save(update_fields=['status', 'updated_at'])
        logger.info('Invoice %s rejected by %s', invoice.number, rejected_by.email)
        return invoice

    @staticmethod
    @transaction.atomic
    def cancel_invoice(invoice, cancelled_by):
        if invoice.status in (InvoiceStatus.PAID, InvoiceStatus.REFUNDED):
            raise ValueError('Paid or refunded invoices cannot be cancelled.')
        invoice.status = InvoiceStatus.CANCELLED
        invoice.save(update_fields=['status', 'updated_at'])
        return invoice

    @staticmethod
    @transaction.atomic
    def recalculate_payment_status(invoice):
        """Recalculate invoice paid/partial/unpaid status after payment changes."""
        if invoice.status in (InvoiceStatus.CANCELLED, InvoiceStatus.REFUNDED):
            return invoice
        paid = invoice.paid_amount
        total = invoice.total_amount
        if paid >= total:
            invoice.status = InvoiceStatus.PAID
        elif paid > 0:
            invoice.status = InvoiceStatus.PARTIALLY_PAID
        else:
            if invoice.status not in (InvoiceStatus.DRAFT, InvoiceStatus.PENDING_APPROVAL):
                invoice.status = InvoiceStatus.APPROVED
        invoice.save(update_fields=['status', 'updated_at'])
        return invoice


class ManualPaymentService:

    @staticmethod
    @transaction.atomic
    def confirm_payment(payment, confirmed_by):
        if payment.is_confirmed:
            raise ValueError('Payment is already confirmed.')
        payment.is_confirmed = True
        payment.confirmed_by = confirmed_by
        payment.confirmed_at = timezone.now()
        payment.save(update_fields=['is_confirmed', 'confirmed_by', 'confirmed_at'])
        # Recalculate invoice status
        InvoiceService.recalculate_payment_status(payment.invoice)
        return payment
