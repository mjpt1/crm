"""
Target achievement calculation and auto-reward service.
"""
import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Sum

from apps.rewards.models import Reward, SalesTarget, TargetType
from apps.sales.models import Invoice, InvoiceStatus

logger = logging.getLogger(__name__)


class TargetCalculationService:

    @staticmethod
    def calculate_achievement(target: SalesTarget) -> dict:
        """
        Computes the current achievement value and percentage for a target.
        Returns {'achieved_value': Decimal, 'percentage': float, 'is_met': bool}
        """
        if target.user:
            invoices = Invoice.objects.filter(
                created_by=target.user,
                created_at__date__gte=target.period_start,
                created_at__date__lte=target.period_end,
                status=InvoiceStatus.PAID,
            )
        else:
            invoices = Invoice.objects.filter(
                created_by__team=target.team,
                created_at__date__gte=target.period_start,
                created_at__date__lte=target.period_end,
                status=InvoiceStatus.PAID,
            )

        if target.target_type == TargetType.REVENUE:
            agg = invoices.aggregate(total=Sum('items__unit_price'))
            achieved = agg['total'] or Decimal('0')
        elif target.target_type == TargetType.INVOICE_COUNT:
            achieved = Decimal(invoices.count())
        elif target.target_type == TargetType.LEAD_CONVERSION:
            from apps.leads.models import Lead
            leads_filter = {'assigned_to': target.user} if target.user else {'assigned_to__team': target.team}
            total_leads = Lead.objects.filter(
                **leads_filter,
                assigned_at__date__gte=target.period_start,
                assigned_at__date__lte=target.period_end,
            ).count()
            paid = invoices.count()
            achieved = Decimal(round((paid / total_leads * 100), 2)) if total_leads > 0 else Decimal('0')
        else:
            achieved = Decimal('0')

        percentage = float(round((achieved / target.target_value * 100), 2)) if target.target_value > 0 else 0.0
        is_met = achieved >= target.target_value

        return {
            'target_id': target.id,
            'target_type': target.target_type,
            'target_value': float(target.target_value),
            'achieved_value': float(achieved),
            'percentage': percentage,
            'is_met': is_met,
        }

    @staticmethod
    @transaction.atomic
    def auto_grant_reward(target: SalesTarget, reward_amount: Decimal, granted_by):
        """
        Automatically grant a reward to the target owner when the target is met.
        Only applicable to user targets.
        """
        if not target.user:
            logger.warning('Auto reward only supported for user targets, not teams.')
            return None

        achievement = TargetCalculationService.calculate_achievement(target)
        if not achievement['is_met']:
            return None

        # Prevent duplicate auto rewards for same target
        if Reward.objects.filter(target=target, is_auto=True).exists():
            return None

        reward = Reward.objects.create(
            target=target,
            user=target.user,
            amount=reward_amount,
            title=f'Auto reward for: {target.title}',
            description=f'Target met at {achievement["percentage"]}%',
            is_auto=True,
            granted_by=granted_by,
        )
        logger.info('Auto reward granted to %s for target %s', target.user.email, target.id)
        return reward
