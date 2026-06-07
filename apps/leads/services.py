"""
Lead auto-assignment, status tracking, and business logic service.
"""
import logging
import random

from django.db import transaction
from django.utils import timezone

from apps.leads.models import Lead, LeadAssignment, LeadNote, LeadStatus, LeadStatusHistory

logger = logging.getLogger(__name__)


class LeadAssignmentService:
    """
    Handles the auto-assignment workflow:
    - A sales expert requests leads.
    - System assigns 3-5 unassigned NEW leads randomly.
    - Prevents double-assignment.
    """

    MIN_ASSIGN = 3
    MAX_ASSIGN = 5

    @classmethod
    @transaction.atomic
    def request_leads(cls, expert):
        """
        Assigns between MIN_ASSIGN and MAX_ASSIGN unassigned leads to the expert.
        Returns the list of newly-assigned Lead objects.
        """
        # Lock unassigned leads to prevent race conditions
        unassigned = list(
            Lead.objects.select_for_update(skip_locked=True)
            .filter(assigned_to__isnull=True, status=LeadStatus.NEW)
            .order_by('created_at')
        )

        if not unassigned:
            return []

        count = min(random.randint(cls.MIN_ASSIGN, cls.MAX_ASSIGN), len(unassigned))
        selected = random.sample(unassigned, count)
        now = timezone.now()

        for lead in selected:
            lead.assigned_to = expert
            lead.assigned_at = now
            lead.status = LeadStatus.CONTACTED

        Lead.objects.bulk_update(selected, ['assigned_to', 'assigned_at', 'status'])

        # Bulk create assignment records
        LeadAssignment.objects.bulk_create([
            LeadAssignment(
                lead=lead,
                assigned_to=expert,
                assigned_by=expert,
                is_active=True,
            )
            for lead in selected
        ])

        # Record status history
        LeadStatusHistory.objects.bulk_create([
            LeadStatusHistory(
                lead=lead,
                old_status=LeadStatus.NEW,
                new_status=LeadStatus.CONTACTED,
                changed_by=expert,
                notes='Auto-assigned to expert on request.',
            )
            for lead in selected
        ])

        logger.info('Assigned %d leads to expert %s', count, expert.email)
        return selected

    @classmethod
    @transaction.atomic
    def manual_assign(cls, lead, expert, assigned_by):
        """
        Manually assign a lead to a specific expert.
        Deactivates any existing active assignments.
        """
        LeadAssignment.objects.filter(lead=lead, is_active=True).update(is_active=False)
        old_status = lead.status
        lead.assigned_to = expert
        lead.assigned_at = timezone.now()
        lead.save(update_fields=['assigned_to', 'assigned_at'])

        LeadAssignment.objects.create(
            lead=lead,
            assigned_to=expert,
            assigned_by=assigned_by,
            is_active=True,
        )

        if old_status != lead.status:
            LeadStatusHistory.objects.create(
                lead=lead,
                old_status=old_status,
                new_status=lead.status,
                changed_by=assigned_by,
                notes=f'Manually assigned to {expert.get_full_name()}.',
            )
        return lead


class LeadStatusService:
    """Handles status transitions with history tracking."""

    @staticmethod
    @transaction.atomic
    def change_status(lead, new_status, changed_by, notes=''):
        old_status = lead.status
        if old_status == new_status:
            return lead
        lead.status = new_status
        lead.save(update_fields=['status', 'updated_at'])
        LeadStatusHistory.objects.create(
            lead=lead,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by,
            notes=notes,
        )
        return lead
