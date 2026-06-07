"""
User, Role, Team and Audit Log models.
Custom AbstractUser with email-based authentication and full RBAC support.
"""
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


# ─── Role Choices ─────────────────────────────────────────────────────────────
class Role(models.TextChoices):
    SUPER_ADMIN = 'super_admin', _('مدیرارشد')
    SALES_MANAGER = 'sales_manager', _('مدیر فروش')
    SUPERVISOR = 'supervisor', _('سرپرست')
    SALES_EXPERT = 'sales_expert', _('کارشناس فروش')
    FINANCE = 'finance', _('مالی')


# ─── Custom User Manager ──────────────────────────────────────────────────────
class CustomUserManager(BaseUserManager):
    """Manager for email-based authentication."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('Email address is required'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', Role.SUPER_ADMIN)
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        return self.create_user(email, password, **extra_fields)


# ─── Team ─────────────────────────────────────────────────────────────────────
class Team(models.Model):
    name = models.CharField(max_length=100, unique=True)
    supervisor = models.ForeignKey(
        'CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supervised_teams',
        limit_choices_to={'role': Role.SUPERVISOR},
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'teams'
        ordering = ['name']
        verbose_name = 'تیم'
        verbose_name_plural = 'تیم‌ها'

    def __str__(self):
        return self.name


# ─── Custom User ──────────────────────────────────────────────────────────────
class CustomUser(AbstractUser):
    username = None  # remove username field; use email instead
    email = models.EmailField(_('email address'), unique=True)
    first_name = models.CharField(_('first name'), max_length=150)
    last_name = models.CharField(_('last name'), max_length=150)
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to='avatars/%Y/%m/', blank=True, null=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.SALES_EXPERT,
        db_index=True,
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = CustomUserManager()

    class Meta:
        db_table = 'users'
        ordering = ['first_name', 'last_name']
        verbose_name = 'کاربر'
        verbose_name_plural = 'کاربران'

    def __str__(self):
        return f'{self.get_full_name()} <{self.email}>'

    # ─── Role Checks ──────────────────────────────────────────────────────────
    @property
    def is_super_admin(self):
        return self.role == Role.SUPER_ADMIN

    @property
    def is_sales_manager(self):
        return self.role == Role.SALES_MANAGER

    @property
    def is_supervisor(self):
        return self.role == Role.SUPERVISOR

    @property
    def is_sales_expert(self):
        return self.role == Role.SALES_EXPERT

    @property
    def is_finance(self):
        return self.role == Role.FINANCE

    @property
    def can_manage_all(self):
        return self.role in (Role.SUPER_ADMIN, Role.SALES_MANAGER)

    def get_accessible_user_ids(self):
        """
        Returns a queryset of user IDs this user is allowed to see data for.
        - Super Admin / Sales Manager → all users
        - Supervisor → their own team members
        - Others → only themselves
        """
        if self.can_manage_all:
            return CustomUser.objects.values_list('id', flat=True)
        if self.is_supervisor and self.team_id:
            return CustomUser.objects.filter(team=self.team).values_list('id', flat=True)
        return CustomUser.objects.filter(id=self.id).values_list('id', flat=True)


# ─── Audit Log ────────────────────────────────────────────────────────────────
class AuditLog(models.Model):
    ACTION_CREATE = 'CREATE'
    ACTION_UPDATE = 'UPDATE'
    ACTION_DELETE = 'DELETE'
    ACTION_LOGIN = 'LOGIN'
    ACTION_LOGOUT = 'LOGOUT'
    ACTION_VIEW = 'VIEW'
    ACTION_CHOICES = [
        (ACTION_CREATE, 'Create'),
        (ACTION_UPDATE, 'Update'),
        (ACTION_DELETE, 'Delete'),
        (ACTION_LOGIN, 'Login'),
        (ACTION_LOGOUT, 'Logout'),
        (ACTION_VIEW, 'View'),
    ]

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, db_index=True)
    model_name = models.CharField(max_length=100, db_index=True)
    object_id = models.CharField(max_length=100, blank=True)
    data = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['model_name', 'object_id']),
        ]

    def __str__(self):
        return f'{self.user} | {self.action} | {self.model_name} | {self.timestamp}'
