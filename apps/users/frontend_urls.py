"""Frontend (template-based) URL routing for the users app."""
from django.urls import path
from apps.users import frontend_views

urlpatterns = [
    path('', frontend_views.dashboard_redirect, name='home'),
    path('login/', frontend_views.login_page, name='login'),
    path('logout/', frontend_views.logout_page, name='logout'),
    path('dashboard/', frontend_views.dashboard, name='dashboard'),
    path('profile/', frontend_views.profile, name='profile'),
    path('leads/', frontend_views.leads_list, name='leads_list'),
    path('invoices/', frontend_views.invoice_list, name='invoice_list'),
    path('payments/', frontend_views.payments_page, name='payments_page'),
    path('reports/', frontend_views.reports_page, name='reports_page'),
    path('rewards/', frontend_views.rewards_page, name='rewards_page'),
    path('leave/', frontend_views.leave_page, name='leave_page'),
    path('calls/', frontend_views.calls_page, name='calls_page'),
    path('users/', frontend_views.users_page, name='users_page'),
    path('teams/', frontend_views.teams_page, name='teams_page'),
]
