"""
Performance reporting service — aggregation queries for dashboards and exports.
"""
import logging
from datetime import timedelta

from django.db.models import (
    Avg,
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    FloatField,
    Max,
    Min,
    OuterRef,
    Q,
    Subquery,
    Sum,
)
from django.db.models.functions import ExtractWeekDay, TruncMonth, TruncWeek
from django.utils import timezone

from apps.leads.models import Lead, LeadStatus
from apps.sales.models import Invoice, InvoiceStatus
from apps.users.models import CustomUser

logger = logging.getLogger(__name__)


class ExpertPerformanceService:
    """
    Computes per-expert KPIs for a given date range.
    """

    @staticmethod
    def get_performance(expert_id, date_from, date_to):
        """
        Returns a dict with all KPIs for one expert within the date range.
        """
        invoices_qs = Invoice.objects.filter(
            created_by_id=expert_id,
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
        )

        total_invoices = invoices_qs.count()
        paid_invoices = invoices_qs.filter(status=InvoiceStatus.PAID)
        paid_count = paid_invoices.count()

        # First and last invoice timestamps
        timestamps = invoices_qs.aggregate(
            first_invoice=Min('created_at'),
            last_invoice=Max('created_at'),
        )
        first_invoice = timestamps['first_invoice']
        last_invoice = timestamps['last_invoice']

        time_diff_seconds = None
        if first_invoice and last_invoice and first_invoice != last_invoice:
            time_diff_seconds = int((last_invoice - first_invoice).total_seconds())

        # Revenue metrics
        revenue_data = paid_invoices.aggregate(
            total_revenue=Sum('items__unit_price') or 0,
        )

        # Conversion rate: paid / total leads assigned in period
        leads_count = Lead.objects.filter(
            assigned_to_id=expert_id,
            assigned_at__date__gte=date_from,
            assigned_at__date__lte=date_to,
        ).count()

        conversion_rate = round((paid_count / leads_count * 100), 2) if leads_count > 0 else 0.0

        # Collection rate: paid / total invoices
        collection_rate = round((paid_count / total_invoices * 100), 2) if total_invoices > 0 else 0.0

        return {
            'expert_id': expert_id,
            'date_from': str(date_from),
            'date_to': str(date_to),
            'total_invoices': total_invoices,
            'paid_invoices': paid_count,
            'first_invoice_at': first_invoice.isoformat() if first_invoice else None,
            'last_invoice_at': last_invoice.isoformat() if last_invoice else None,
            'time_diff_seconds': time_diff_seconds,
            'leads_assigned': leads_count,
            'conversion_rate': conversion_rate,
            'collection_rate': collection_rate,
        }

    @staticmethod
    def get_weekday_breakdown(expert_id, date_from, date_to):
        """
        Returns invoice counts grouped by ISO weekday (1=Monday … 7=Sunday).
        """
        results = (
            Invoice.objects.filter(
                created_by_id=expert_id,
                created_at__date__gte=date_from,
                created_at__date__lte=date_to,
                status=InvoiceStatus.PAID,
            )
            .annotate(weekday=ExtractWeekDay('created_at'))
            .values('weekday')
            .annotate(count=Count('id'))
            .order_by('weekday')
        )
        day_names = {1: 'Sunday', 2: 'Monday', 3: 'Tuesday', 4: 'Wednesday',
                     5: 'Thursday', 6: 'Friday', 7: 'Saturday'}
        return [
            {'weekday': r['weekday'], 'name': day_names.get(r['weekday'], ''), 'count': r['count']}
            for r in results
        ]

    @staticmethod
    def get_monthly_breakdown(expert_id, date_from, date_to):
        """
        Returns invoice counts and revenue grouped by month.
        """
        results = (
            Invoice.objects.filter(
                created_by_id=expert_id,
                created_at__date__gte=date_from,
                created_at__date__lte=date_to,
            )
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(
                total=Count('id'),
                paid=Count('id', filter=Q(status=InvoiceStatus.PAID)),
            )
            .order_by('month')
        )
        return [
            {
                'month': r['month'].strftime('%Y-%m'),
                'total_invoices': r['total'],
                'paid_invoices': r['paid'],
            }
            for r in results
        ]


class TeamPerformanceService:
    """Aggregated KPIs across a team or all experts."""

    @staticmethod
    def get_team_summary(team_id, date_from, date_to):
        experts = CustomUser.objects.filter(team_id=team_id, is_active=True)
        summary = []
        for expert in experts:
            data = ExpertPerformanceService.get_performance(expert.id, date_from, date_to)
            data['expert_name'] = expert.get_full_name()
            data['expert_email'] = expert.email
            summary.append(data)
        return summary


class DashboardService:
    """
    High-level dashboard data for the home page widgets.
    """

    @staticmethod
    def get_overview(user):
        """
        Returns aggregated totals for the dashboard panels.
        Scoped by user's accessible data.
        """
        accessible_ids = list(user.get_accessible_user_ids())
        today = timezone.now().date()
        month_start = today.replace(day=1)

        leads_qs = Lead.objects.filter(assigned_to_id__in=accessible_ids)
        invoices_qs = Invoice.objects.filter(created_by_id__in=accessible_ids)

        lead_stats = leads_qs.aggregate(
            total=Count('id'),
            new=Count('id', filter=Q(status=LeadStatus.NEW)),
            won=Count('id', filter=Q(status=LeadStatus.WON)),
            lost=Count('id', filter=Q(status=LeadStatus.LOST)),
        )

        invoice_stats = invoices_qs.aggregate(
            total=Count('id'),
            pending_approval=Count('id', filter=Q(status=InvoiceStatus.PENDING_APPROVAL)),
            paid_this_month=Count(
                'id',
                filter=Q(status=InvoiceStatus.PAID, created_at__date__gte=month_start),
            ),
        )

        return {
            'leads': lead_stats,
            'invoices': invoice_stats,
            'generated_at': timezone.now().isoformat(),
        }

    @staticmethod
    def get_chart_data(user, months=6):
        """
        Returns Chart.js-ready data for the last N months:
        - Monthly invoice counts (paid vs total)
        - Monthly lead acquisition
        """
        accessible_ids = list(user.get_accessible_user_ids())
        start_date = timezone.now().date() - timedelta(days=months * 30)

        invoice_monthly = (
            Invoice.objects.filter(
                created_by_id__in=accessible_ids,
                created_at__date__gte=start_date,
            )
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(
                total=Count('id'),
                paid=Count('id', filter=Q(status=InvoiceStatus.PAID)),
            )
            .order_by('month')
        )

        lead_monthly = (
            Lead.objects.filter(
                assigned_to_id__in=accessible_ids,
                created_at__date__gte=start_date,
            )
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(total=Count('id'))
            .order_by('month')
        )

        labels = [r['month'].strftime('%b %Y') for r in invoice_monthly]

        return {
            'labels': labels,
            'invoices': {
                'total': [r['total'] for r in invoice_monthly],
                'paid': [r['paid'] for r in invoice_monthly],
            },
            'leads': {
                'total': [r['total'] for r in lead_monthly],
            },
        }
