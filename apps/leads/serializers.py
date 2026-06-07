from rest_framework import serializers

from apps.leads.models import Lead, LeadAssignment, LeadNote, LeadStatus, LeadStatusHistory
from apps.users.serializers import UserListSerializer


class LeadNoteSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)

    class Meta:
        model = LeadNote
        fields = ['id', 'lead', 'author', 'author_name', 'content', 'is_pinned', 'created_at', 'updated_at']
        read_only_fields = ['author', 'created_at', 'updated_at']


class LeadStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source='changed_by.get_full_name', read_only=True)

    class Meta:
        model = LeadStatusHistory
        fields = ['id', 'old_status', 'new_status', 'changed_by', 'changed_by_name', 'changed_at', 'notes']
        read_only_fields = fields


class LeadAssignmentSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True)
    assigned_by_name = serializers.CharField(source='assigned_by.get_full_name', read_only=True)

    class Meta:
        model = LeadAssignment
        fields = ['id', 'lead', 'assigned_to', 'assigned_to_name', 'assigned_by',
                  'assigned_by_name', 'assigned_at', 'is_active']
        read_only_fields = fields


class LeadListSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            'id', 'first_name', 'last_name', 'phone', 'email',
            'company', 'source', 'status', 'priority',
            'assigned_to', 'assigned_to_name', 'assigned_at', 'created_at',
        ]

    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return obj.assigned_to.get_full_name()
        return None


class LeadDetailSerializer(serializers.ModelSerializer):
    assigned_to_detail = UserListSerializer(source='assigned_to', read_only=True)
    status_history = LeadStatusHistorySerializer(many=True, read_only=True)
    notes = LeadNoteSerializer(many=True, read_only=True)

    class Meta:
        model = Lead
        fields = [
            'id', 'first_name', 'last_name', 'phone', 'email',
            'company', 'address', 'source', 'status', 'priority',
            'assigned_to', 'assigned_to_detail', 'assigned_at',
            'created_by', 'created_at', 'updated_at',
            'status_history', 'notes',
        ]
        read_only_fields = ['assigned_to', 'assigned_at', 'created_by', 'created_at', 'updated_at']


class LeadCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = [
            'first_name', 'last_name', 'phone', 'email',
            'company', 'address', 'source', 'priority',
        ]

    def validate_phone(self, value):
        # Normalize phone number
        cleaned = ''.join(c for c in value if c.isdigit() or c in '+-')
        if len(cleaned) < 7:
            raise serializers.ValidationError('Invalid phone number.')
        return cleaned


class LeadUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = ['first_name', 'last_name', 'phone', 'email', 'company', 'address', 'source', 'priority']


class LeadStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=LeadStatus.choices)
    notes = serializers.CharField(required=False, allow_blank=True)


class ManualAssignSerializer(serializers.Serializer):
    expert_id = serializers.IntegerField()

    def validate_expert_id(self, value):
        from apps.users.models import CustomUser, Role
        try:
            user = CustomUser.objects.get(id=value, role=Role.SALES_EXPERT, is_active=True)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError('Active sales expert not found.')
        return value
