"""
Performance reporting service — aggregation queries for dashboards and exports.
"""
import logging
from collections import defaultdict
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
from django.db.utils import OperationalError, ProgrammingError
from django.db.models.functions import ExtractWeekDay, TruncMonth, TruncWeek
from django.utils import timezone

from apps.leads.models import Lead, LeadStatus
from apps.payments.models import OnlinePayment, PaymentStatus
from apps.sales.models import Invoice, InvoiceStatus, ManualPayment
from apps.users.models import CustomUser, Role

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
        total_revenue = sum(invoice.total_amount for invoice in paid_invoices.prefetch_related('items'))

        # Conversion rate: paid / total leads assigned in period
        leads_qs = Lead.objects.filter(
            assigned_to_id=expert_id,
            assigned_at__date__gte=date_from,
            assigned_at__date__lte=date_to,
        )
        leads_count = leads_qs.count()
        leads_won = leads_qs.filter(status=LeadStatus.WON).count()

        conversion_rate = round((paid_count / leads_count * 100), 2) if leads_count > 0 else 0.0

        # Collection rate: paid / total invoices
        collection_rate = round((paid_count / total_invoices * 100), 2) if total_invoices > 0 else 0.0

        return {
            'expert_id': expert_id,
            'date_from': str(date_from),
            'date_to': str(date_to),
            'leads': {
                'total': leads_count,
                'won': leads_won,
            },
            'invoices': {
                'total': total_invoices,
                'paid': paid_count,
                'total_revenue': float(total_revenue),
            },
            'total_invoices': total_invoices,
            'paid_invoices': paid_count,
            'first_invoice_at': first_invoice.isoformat() if first_invoice else None,
            'last_invoice_at': last_invoice.isoformat() if last_invoice else None,
            'time_diff_seconds': time_diff_seconds,
            'leads_assigned': leads_count,
            'leads_won': leads_won,


            'total_revenue': float(total_revenue),
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
        experts_data = []
        total_leads = 0
        total_won = 0
        total_invoices = 0
        total_revenue = 0.0
        for expert in experts:
            data = ExpertPerformanceService.get_performance(expert.id, date_from, date_to)
            data['expert_name'] = expert.get_full_name()
            data['expert_email'] = expert.email
            experts_data.append(data)
            total_leads += data.get('leads', {}).get('total', 0)
            total_won += data.get('leads', {}).get('won', 0)
            total_invoices += data.get('invoices', {}).get('total', 0)
            total_revenue += data.get('invoices', {}).get('total_revenue', 0) or 0

        return {
            'team_id': team_id,
            'date_from': str(date_from),
            'date_to': str(date_to),
            'leads': {
                'total': total_leads,
                'won': total_won,
            },
            'invoices': {
                'total': total_invoices,
                'total_revenue': float(total_revenue),
            },
            'experts': experts_data,
        }


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

        if user.can_manage_all:
            leads_qs = Lead.objects.all()
            invoices_qs = Invoice.objects.all()
        elif user.is_supervisor and user.team_id:
            leads_qs = Lead.objects.filter(
                Q(assigned_to__team_id=user.team_id) | Q(created_by__team_id=user.team_id) | Q(assigned_to__isnull=True)
            ).distinct()
            invoices_qs = Invoice.objects.filter(created_by__team_id=user.team_id)
        else:
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
            paid_this_month=Count('id', filter=Q(status=InvoiceStatus.PAID, created_at__date__gte=month_start)),
        )

        # Payment widgets must reflect actual transactions (manual + online), not invoice creation dates.
        if user.can_manage_all:
            manual_payments_qs = ManualPayment.objects.all()
            online_payments_qs = OnlinePayment.objects.all()
        elif user.is_supervisor and user.team_id:
            manual_payments_qs = ManualPayment.objects.filter(invoice__created_by__team_id=user.team_id)
            online_payments_qs = OnlinePayment.objects.filter(invoice__created_by__team_id=user.team_id)
        else:
            manual_payments_qs = ManualPayment.objects.filter(invoice__created_by_id__in=accessible_ids)
            online_payments_qs = OnlinePayment.objects.filter(invoice__created_by_id__in=accessible_ids)

        manual_stats = manual_payments_qs.filter(
            is_confirmed=True,
            payment_date__gte=month_start,
        ).aggregate(
            count=Count('id'),
            amount=Sum('amount'),
        )

        try:
            online_stats = online_payments_qs.filter(
                status__in=(PaymentStatus.VERIFIED, PaymentStatus.SUCCESS),
                verified_at__date__gte=month_start,
            ).aggregate(
                count=Count('id'),
                amount=Sum('amount'),
            )
        except (OperationalError, ProgrammingError):
            online_stats = {'count': 0, 'amount': 0}

        monthly_paid_count = (manual_stats.get('count') or 0) + (online_stats.get('count') or 0)
        monthly_paid_amount = (manual_stats.get('amount') or 0) + (online_stats.get('amount') or 0)

        invoice_stats['paid_this_month'] = monthly_paid_count

        return {
            'leads': lead_stats,
            'invoices': invoice_stats,
            'payments': {
                'verified_this_month': monthly_paid_count,
                'amount_this_month': float(monthly_paid_amount),
            },
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

        # Always build a fixed month axis so charts remain visible even with zero data.
        today = timezone.now().date()
        current_month_start = today.replace(day=1)
        month_keys = []
        for offset in range(months - 1, -1, -1):
            year = current_month_start.year
            month = current_month_start.month - offset
            while month <= 0:
                month += 12
                year -= 1
            month_keys.append(f'{year}-{month:02d}')

        first_year, first_month = month_keys[0].split('-')
        start_date = today.replace(year=int(first_year), month=int(first_month), day=1)

        if user.can_manage_all:
            invoice_base_qs = Invoice.objects.all()
            lead_base_qs = Lead.objects.all()
        elif user.is_supervisor and user.team_id:
            invoice_base_qs = Invoice.objects.filter(created_by__team_id=user.team_id)
            lead_base_qs = Lead.objects.filter(
                Q(assigned_to__team_id=user.team_id) | Q(created_by__team_id=user.team_id) | Q(assigned_to__isnull=True)
            ).distinct()
        else:
            invoice_base_qs = Invoice.objects.filter(created_by_id__in=accessible_ids)
            lead_base_qs = Lead.objects.filter(assigned_to_id__in=accessible_ids)

        invoice_monthly = (
            invoice_base_qs.filter(created_at__date__gte=start_date)
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(total=Count('id'))
            .order_by('month')
        )

        if user.can_manage_all:
            manual_payments_base_qs = ManualPayment.objects.all()
            online_payments_base_qs = OnlinePayment.objects.all()
        elif user.is_supervisor and user.team_id:
            manual_payments_base_qs = ManualPayment.objects.filter(invoice__created_by__team_id=user.team_id)
            online_payments_base_qs = OnlinePayment.objects.filter(invoice__created_by__team_id=user.team_id)
        else:
            manual_payments_base_qs = ManualPayment.objects.filter(invoice__created_by_id__in=accessible_ids)
            online_payments_base_qs = OnlinePayment.objects.filter(invoice__created_by_id__in=accessible_ids)

        manual_payment_monthly = (
            manual_payments_base_qs
            .filter(is_confirmed=True, payment_date__gte=start_date)
            .annotate(month=TruncMonth('payment_date'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )

        try:
            online_payment_monthly = (
                online_payments_base_qs
                .filter(
                    verified_at__date__gte=start_date,
                    status__in=(PaymentStatus.VERIFIED, PaymentStatus.SUCCESS),
                )
                .annotate(month=TruncMonth('verified_at'))
                .values('month')
                .annotate(count=Count('id'))
                .order_by('month')
            )
        except (OperationalError, ProgrammingError):
            online_payment_monthly = []

        lead_monthly = (
            lead_base_qs.filter(created_at__date__gte=start_date)
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(total=Count('id'))
            .order_by('month')
        )

        invoice_map = {r['month'].strftime('%Y-%m'): r for r in invoice_monthly}
        payment_map = {}
        for r in manual_payment_monthly:
            key = r['month'].strftime('%Y-%m')
            payment_map[key] = (payment_map.get(key) or 0) + (r.get('count') or 0)
        for r in online_payment_monthly:
            key = r['month'].strftime('%Y-%m')
            payment_map[key] = (payment_map.get(key) or 0) + (r.get('count') or 0)
        lead_map = {r['month'].strftime('%Y-%m'): r for r in lead_monthly}
        all_month_keys = month_keys

        labels = []
        invoice_total = []
        invoice_paid = []
        lead_total = []
        for month_key in all_month_keys:
            year, month = month_key.split('-')
            labels.append(f'{year}/{month}')
            invoice_total.append(invoice_map.get(month_key, {}).get('total', 0))
            invoice_paid.append(payment_map.get(month_key, 0))
            lead_total.append(lead_map.get(month_key, {}).get('total', 0))

        return {
            'labels': labels,
            'invoices': {
                'total': invoice_total,
                'paid': invoice_paid,
            },
            'leads': {
                'total': lead_total,
            },
        }


class LiveSalesBoardService:
    """Live competitive boards for experts, supervisors, and managers."""

    @staticmethod
    def _base_rows(date_from, date_to):
        issued_rows = defaultdict(lambda: {
            'expert_id': None,
            'expert_name': '',
            'supervisor_id': None,
            'supervisor_name': 'بدون سوپروایزر',
            'issued_amount': 0.0,
            'collected_amount': 0.0,
            'invoice_count': 0,
            'payment_count': 0,
        })

        invoices = (
            Invoice.objects
            .filter(
                created_at__date__gte=date_from,
                created_at__date__lte=date_to,
                created_by__role=Role.SALES_EXPERT,
            )
            .select_related('created_by', 'created_by__team__supervisor')
            .prefetch_related('items')
        )
        for inv in invoices:
            expert = inv.created_by
            key = expert.id
            row = issued_rows[key]
            row['expert_id'] = expert.id
            row['expert_name'] = expert.get_full_name() or expert.email
            sup = getattr(getattr(expert, 'team', None), 'supervisor', None)
            if sup:
                row['supervisor_id'] = sup.id
                row['supervisor_name'] = sup.get_full_name() or sup.email
            row['issued_amount'] += float(inv.total_amount or 0)
            row['invoice_count'] += 1

        manual_payments = (
            ManualPayment.objects
            .filter(
                is_confirmed=True,
                payment_date__gte=date_from,
                payment_date__lte=date_to,
                invoice__created_by__role=Role.SALES_EXPERT,
            )
            .select_related('invoice__created_by', 'invoice__created_by__team__supervisor')
        )
        for p in manual_payments:
            expert = p.invoice.created_by
            key = expert.id
            row = issued_rows[key]
            row['expert_id'] = expert.id
            row['expert_name'] = expert.get_full_name() or expert.email
            sup = getattr(getattr(expert, 'team', None), 'supervisor', None)
            if sup:
                row['supervisor_id'] = sup.id
                row['supervisor_name'] = sup.get_full_name() or sup.email
            row['collected_amount'] += float(p.amount or 0)
            row['payment_count'] += 1

        online_payments = (
            OnlinePayment.objects
            .filter(
                status__in=(PaymentStatus.VERIFIED, PaymentStatus.SUCCESS),
                verified_at__date__gte=date_from,
                verified_at__date__lte=date_to,
                invoice__created_by__role=Role.SALES_EXPERT,
            )
            .select_related('invoice__created_by', 'invoice__created_by__team__supervisor')
        )
        for p in online_payments:
            expert = p.invoice.created_by
            key = expert.id
            row = issued_rows[key]
            row['expert_id'] = expert.id
            row['expert_name'] = expert.get_full_name() or expert.email
            sup = getattr(getattr(expert, 'team', None), 'supervisor', None)
            if sup:
                row['supervisor_id'] = sup.id
                row['supervisor_name'] = sup.get_full_name() or sup.email
            row['collected_amount'] += float(p.amount or 0)
            row['payment_count'] += 1

        rows = []
        for row in issued_rows.values():
            row['total_amount'] = row['issued_amount'] + row['collected_amount']
            rows.append(row)
        return rows

    @staticmethod
    def _to_payload(rows, label_key):
        sorted_rows = sorted(rows, key=lambda r: (r.get('total_amount') or 0), reverse=True)
        labels = [r.get(label_key) or '—' for r in sorted_rows]
        issued = [round(r.get('issued_amount') or 0, 2) for r in sorted_rows]
        collected = [round(r.get('collected_amount') or 0, 2) for r in sorted_rows]
        totals = [round(r.get('total_amount') or 0, 2) for r in sorted_rows]
        top_three = sorted_rows[:3]

        return {
            'participants': sorted_rows,
            'top_three': top_three,
            'chart': {
                'labels': labels,
                'issued': issued,
                'collected': collected,
                'totals': totals,
            },
            'summary': {
                'total_issued': round(sum(issued), 2),
                'total_collected': round(sum(collected), 2),
                'grand_total': round(sum(totals), 2),
            },
        }

    @classmethod
    def experts_board(cls, date_from, date_to):
        rows = cls._base_rows(date_from, date_to)
        payload = cls._to_payload(rows, 'expert_name')
        payload['date_from'] = str(date_from)
        payload['date_to'] = str(date_to)
        payload['scope'] = 'experts'
        return payload

    @classmethod
    def supervisors_board(cls, date_from, date_to):
        rows = cls._base_rows(date_from, date_to)
        grouped = defaultdict(lambda: {
            'supervisor_id': None,
            'supervisor_name': 'بدون سوپروایزر',
            'issued_amount': 0.0,
            'collected_amount': 0.0,
            'invoice_count': 0,
            'payment_count': 0,
        })
        for row in rows:
            key = row.get('supervisor_id') or 0
            g = grouped[key]
            g['supervisor_id'] = row.get('supervisor_id')
            g['supervisor_name'] = row.get('supervisor_name') or 'بدون سوپروایزر'
            g['issued_amount'] += row.get('issued_amount') or 0
            g['collected_amount'] += row.get('collected_amount') or 0
            g['invoice_count'] += row.get('invoice_count') or 0
            g['payment_count'] += row.get('payment_count') or 0

        result_rows = []
        for g in grouped.values():
            g['total_amount'] = g['issued_amount'] + g['collected_amount']
            result_rows.append(g)

        payload = cls._to_payload(result_rows, 'supervisor_name')
        payload['date_from'] = str(date_from)
        payload['date_to'] = str(date_to)
        payload['scope'] = 'supervisors'
        return payload

    @classmethod
    def managers_board(cls, date_from, date_to):
        rows = cls._base_rows(date_from, date_to)
        manager_by_team_id = {
            m.team_id: m
            for m in CustomUser.objects.filter(role=Role.SALES_MANAGER, is_active=True).select_related('team')
            if m.team_id
        }

        grouped = defaultdict(lambda: {
            'manager_id': None,
            'manager_name': 'بدون سرپرست',
            'issued_amount': 0.0,
            'collected_amount': 0.0,
            'invoice_count': 0,
            'payment_count': 0,
        })

        for row in rows:
            supervisor_id = row.get('supervisor_id')
            manager = None
            if supervisor_id:
                sup = CustomUser.objects.filter(id=supervisor_id).only('id', 'team_id').first()
                if sup and sup.team_id:
                    manager = manager_by_team_id.get(sup.team_id)

            key = manager.id if manager else 0
            g = grouped[key]
            g['manager_id'] = manager.id if manager else None
            g['manager_name'] = manager.get_full_name() if manager else 'بدون سرپرست'
            g['issued_amount'] += row.get('issued_amount') or 0
            g['collected_amount'] += row.get('collected_amount') or 0
            g['invoice_count'] += row.get('invoice_count') or 0
            g['payment_count'] += row.get('payment_count') or 0

        result_rows = []
        for g in grouped.values():
            g['total_amount'] = g['issued_amount'] + g['collected_amount']
            result_rows.append(g)

        payload = cls._to_payload(result_rows, 'manager_name')
        payload['date_from'] = str(date_from)
        payload['date_to'] = str(date_to)
        payload['scope'] = 'managers'
        return payload
