from rest_framework import serializers

from apps.rewards.models import Reward, SalesTarget


class SalesTargetSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True, default=None)
    team_name = serializers.CharField(source='team.name', read_only=True, default=None)
    achievement = serializers.SerializerMethodField()

    class Meta:
        model = SalesTarget
        fields = [
            'id', 'title', 'target_type', 'user', 'user_name', 'team', 'team_name',
            'target_value', 'period_start', 'period_end', 'description',
            'created_by', 'created_by_name', 'created_at', 'achievement',
        ]
        read_only_fields = ['created_by', 'created_at']

    def get_achievement(self, obj):
        from apps.rewards.services import TargetCalculationService
        return TargetCalculationService.calculate_achievement(obj)

    def validate(self, attrs):
        if not attrs.get('user') and not attrs.get('team'):
            raise serializers.ValidationError('Provide either user or team for the target.')
        if attrs.get('user') and attrs.get('team'):
            raise serializers.ValidationError('Provide user OR team, not both.')
        if attrs.get('period_start') and attrs.get('period_end'):
            if attrs['period_start'] >= attrs['period_end']:
                raise serializers.ValidationError('period_end must be after period_start.')
        return attrs


class RewardSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    granted_by_name = serializers.CharField(source='granted_by.get_full_name', read_only=True)

    class Meta:
        model = Reward
        fields = [
            'id', 'target', 'user', 'user_name', 'amount', 'title', 'description',
            'is_auto', 'granted_by', 'granted_by_name', 'granted_at',
        ]
        read_only_fields = ['is_auto', 'granted_by', 'granted_at']


class RewardCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reward
        fields = ['target', 'user', 'amount', 'title', 'description']

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Reward amount must be positive.')
        return value
