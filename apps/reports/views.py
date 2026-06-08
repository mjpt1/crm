"""
Report views — performance analytics, dashboard data.
"""
from datetime import date

from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.reports.services import (
    DashboardService,
    ExpertPerformanceService,
    LiveSalesBoardService,
    TeamPerformanceService,
)
from apps.users.models import CustomUser
from apps.users.permissions import IsSupervisorOrAbove


def _parse_date_range(request):
    """Helper to parse date_from / date_to from query params."""
    today = date.today()
    date_from_str = request.query_params.get('date_from')
    date_to_str = request.query_params.get('date_to')
    try:
        date_from = date.fromisoformat(date_from_str) if date_from_str else date(today.year, today.month, 1)
        date_to = date.fromisoformat(date_to_str) if date_to_str else today
    except ValueError:
        date_from = date(today.year, today.month, 1)
        date_to = today
    return date_from, date_to


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def dashboard_overview(request):
    """GET /reports/dashboard/ — widget data for the home dashboard."""
    data = DashboardService.get_overview(request.user)
    return Response(data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def dashboard_charts(request):
    """GET /reports/charts/ — Chart.js-ready time series data."""
    months = int(request.query_params.get('months', 6))
    months = max(1, min(months, 24))  # clamp between 1–24
    data = DashboardService.get_chart_data(request.user, months=months)
    return Response(data)


@api_view(['GET'])
@permission_classes([IsSupervisorOrAbove])
def expert_performance(request, expert_id):
    """GET /reports/expert/{expert_id}/ — KPIs for a single expert."""
    date_from, date_to = _parse_date_range(request)
    # Scope check
    user = request.user
    if not user.can_manage_all:
        expert = CustomUser.objects.filter(id=expert_id, team=user.team).first()
        if not expert:
            return Response({'detail': 'Expert not found in your team.'}, status=404)

    data = ExpertPerformanceService.get_performance(expert_id, date_from, date_to)
    weekday = ExpertPerformanceService.get_weekday_breakdown(expert_id, date_from, date_to)
    monthly = ExpertPerformanceService.get_monthly_breakdown(expert_id, date_from, date_to)

    data['weekday_breakdown'] = weekday
    data['monthly_breakdown'] = monthly
    return Response(data)


@api_view(['GET'])
@permission_classes([IsSupervisorOrAbove])
def team_performance(request, team_id):
    """GET /reports/team/{team_id}/ — aggregated KPIs for all experts in a team."""
    date_from, date_to = _parse_date_range(request)
    user = request.user
    if not user.can_manage_all and user.team_id != int(team_id):
        return Response({'detail': 'Access denied.'}, status=403)
    data = TeamPerformanceService.get_team_summary(team_id, date_from, date_to)
    return Response(data)


def _target_date(request):
    raw = request.query_params.get('date')
    if not raw:
        return date.today()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return date.today()


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def live_experts_report(request):
    target = _target_date(request)
    return Response(LiveSalesBoardService.experts_board(target))


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def live_supervisors_report(request):
    target = _target_date(request)
    return Response(LiveSalesBoardService.supervisors_board(target))


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def live_managers_report(request):
    target = _target_date(request)
    return Response(LiveSalesBoardService.managers_board(target))
