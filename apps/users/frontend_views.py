"""Template-based frontend views."""
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.utils import OperationalError, ProgrammingError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.users.models import Role


def _ensure_demo_admin_for_serverless():
    if not getattr(settings, 'AUTO_CREATE_DEMO_ADMIN', False):
        return
    email = getattr(settings, 'DEMO_ADMIN_EMAIL', '').strip().lower()
    password = getattr(settings, 'DEMO_ADMIN_PASSWORD', '')
    if not email or not password:
        return
    User = get_user_model()
    try:
        if not User.objects.filter(email=email).exists():
            User.objects.create_user(
                email=email,
                password=password,
                first_name='System',
                last_name='Admin',
                role=Role.SUPER_ADMIN,
                is_staff=True,
                is_superuser=True,
                is_active=True,
            )
    except (OperationalError, ProgrammingError):
        return


def dashboard_redirect(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return redirect('login')


@require_http_methods(['GET', 'POST'])
def login_page(request):
    _ensure_demo_admin_for_serverless()
    if request.user.is_authenticated:
        return redirect('dashboard')

    error = None
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            next_url = request.GET.get('next', '/dashboard/')
            return redirect(next_url)
        else:
            error = 'ایمیل یا رمز عبور اشتباه است.'

    return render(request, 'users/login.html', {'error': error})


def logout_page(request):
    logout(request)
    return redirect('login')


@login_required
def dashboard(request):
    return render(request, 'dashboard/index.html', {'user': request.user})


@login_required
def profile(request):
    return render(request, 'users/profile.html', {'user': request.user})


@login_required
def leads_list(request):
    return render(request, 'leads/list.html', {'user': request.user})


@login_required
def invoice_list(request):
    return render(request, 'sales/invoice_list.html', {'user': request.user})


@login_required
def payments_page(request):
    return render(request, 'payments/online_list.html', {'user': request.user})


@login_required
def reports_page(request):
    return render(request, 'reports/index.html', {'user': request.user})


@login_required
def rewards_page(request):
    return render(request, 'rewards/index.html', {'user': request.user})


@login_required
def leave_page(request):
    return render(request, 'leave/index.html', {'user': request.user})


@login_required
def calls_page(request):
    return render(request, 'voip/calls.html', {'user': request.user})


@login_required
def users_page(request):
    return render(request, 'users/users_list.html', {'user': request.user})


@login_required
def teams_page(request):
    return render(request, 'users/teams_list.html', {'user': request.user})
