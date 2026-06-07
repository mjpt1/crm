from django.urls import path

from apps.reports import views

urlpatterns = [
    path('dashboard/', views.dashboard_overview, name='report-dashboard'),
    path('charts/', views.dashboard_charts, name='report-charts'),
    path('expert/<int:expert_id>/', views.expert_performance, name='report-expert'),
    path('team/<int:team_id>/', views.team_performance, name='report-team'),
]
