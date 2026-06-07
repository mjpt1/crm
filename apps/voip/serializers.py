from rest_framework import serializers

from apps.voip.models import CallLog


class CallLogSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source='agent.get_full_name', read_only=True, default=None)
    lead_name = serializers.SerializerMethodField()
    duration_formatted = serializers.CharField(read_only=True)

    class Meta:
        model = CallLog
        fields = [
            'id', 'agent', 'agent_name', 'lead', 'lead_name', 'phone_number',
            'direction', 'status', 'duration_seconds', 'duration_formatted',
            'started_at', 'ended_at', 'recording_url', 'external_call_id',
            'notes', 'created_at',
        ]
        read_only_fields = [
            'agent', 'duration_formatted', 'external_call_id', 'created_at',
        ]

    def get_lead_name(self, obj):
        if obj.lead:
            return obj.lead.full_name
        return None


class ClickToDialSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)
    lead_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_phone_number(self, value):
        cleaned = ''.join(c for c in value if c.isdigit() or c in '+-')
        if len(cleaned) < 7:
            raise serializers.ValidationError('Invalid phone number.')
        return cleaned
