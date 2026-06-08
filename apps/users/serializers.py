"""
Serializers for the Users app — authentication, user CRUD, and team management.
"""
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.users.models import AuditLog, CustomUser, Team


# ─── JWT Custom Claims ────────────────────────────────────────────────────────
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['role'] = user.role
        token['full_name'] = user.get_full_name()
        token['team_id'] = user.team_id
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = {
            'id': self.user.id,
            'email': self.user.email,
            'full_name': self.user.get_full_name(),
            'role': self.user.role,
            'team_id': self.user.team_id,
        }
        return data


# ─── Team Serializers ─────────────────────────────────────────────────────────
class TeamListSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = ['id', 'name', 'supervisor', 'member_count', 'is_active', 'created_at']

    def get_member_count(self, obj):
        return obj.members.filter(is_active=True).count()


class TeamDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = '__all__'


class TeamWriteSerializer(serializers.ModelSerializer):
    supervisor = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = Team
        fields = ['name', 'supervisor', 'description', 'is_active']

    def validate_supervisor(self, value):
        if value in (None, ''):
            return None
        supervisor = CustomUser.objects.filter(
            id=value,
            is_active=True,
            role__in=('supervisor', 'super_admin', 'sales_manager'),
        ).first()
        # Gracefully ignore stale/invalid supervisor IDs from cached UIs.
        return supervisor


# ─── User Serializers ─────────────────────────────────────────────────────────
class UserListSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source='team.name', read_only=True, default=None)

    class Meta:
        model = CustomUser
        fields = [
            'id', 'email', 'first_name', 'last_name', 'phone',
            'role', 'team', 'team_name', 'is_active', 'created_at',
        ]


class UserDetailSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source='team.name', read_only=True, default=None)

    class Meta:
        model = CustomUser
        fields = [
            'id', 'email', 'first_name', 'last_name', 'phone', 'avatar',
            'role', 'team', 'team_name', 'is_active', 'date_joined', 'created_at', 'updated_at',
        ]
        read_only_fields = ['date_joined', 'created_at', 'updated_at']


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = [
            'email', 'first_name', 'last_name', 'phone',
            'role', 'team', 'password', 'password_confirm',
        ]

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('password_confirm'):
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = CustomUser(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'phone', 'avatar', 'role', 'team', 'is_active']


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({'new_password_confirm': 'Passwords do not match.'})
        return attrs

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Old password is incorrect.')
        return value

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


# ─── Audit Log Serializer ─────────────────────────────────────────────────────
class AuditLogSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'user_email', 'action', 'model_name',
            'object_id', 'data', 'ip_address', 'timestamp',
        ]
        read_only_fields = fields
