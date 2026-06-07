from rest_framework import serializers

from apps.leave.models import LeaveRequest, LeaveStatus, LeaveType


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = ['id', 'name', 'max_days_per_year', 'is_paid', 'description', 'is_active']


class LeaveRequestSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True, default=None)
    duration_days = serializers.IntegerField(read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            'id', 'user', 'user_name', 'leave_type', 'leave_type_name',
            'start_date', 'end_date', 'duration_days', 'reason', 'status',
            'approved_by', 'approved_by_name', 'approved_at', 'rejection_reason',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'user', 'status', 'approved_by', 'approved_at',
            'rejection_reason', 'created_at', 'updated_at',
        ]


class LeaveRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'start_date', 'end_date', 'reason']

    def validate(self, attrs):
        if attrs['end_date'] < attrs['start_date']:
            raise serializers.ValidationError({'end_date': 'End date must be after start date.'})
        # Check for overlapping leave requests
        user = self.context['request'].user
        overlap = LeaveRequest.objects.filter(
            user=user,
            status__in=(LeaveStatus.PENDING, LeaveStatus.APPROVED),
            start_date__lte=attrs['end_date'],
            end_date__gte=attrs['start_date'],
        ).exists()
        if overlap:
            raise serializers.ValidationError('You already have an overlapping leave request.')
        return attrs


class LeaveApprovalSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    rejection_reason = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs['action'] == 'reject' and not attrs.get('rejection_reason'):
            raise serializers.ValidationError({'rejection_reason': 'Reason is required when rejecting.'})
        return attrs


class LeaveCalendarSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    start = serializers.DateField(source='start_date')
    end = serializers.DateField(source='end_date')
    color = serializers.SerializerMethodField()

    class Meta:
        model = LeaveRequest
        fields = ['id', 'title', 'start', 'end', 'color', 'status']

    def get_title(self, obj):
        return f'{obj.user.get_full_name()} — {obj.leave_type.name}'

    def get_color(self, obj):
        colors = {
            LeaveStatus.PENDING: '#FFC107',
            LeaveStatus.APPROVED: '#28A745',
            LeaveStatus.REJECTED: '#DC3545',
            LeaveStatus.CANCELLED: '#6C757D',
        }
        return colors.get(obj.status, '#007BFF')
