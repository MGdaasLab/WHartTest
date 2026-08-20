from rest_framework import serializers
from .models import OperationLog, OperationLogSetting

class OperationLogSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)

    class Meta:
        model = OperationLog
        fields = [
            'id', 'user', 'username', 'ip_address', 'user_agent', 
            'path', 'method', 'module', 'action', 'request_data', 
            'response_code', 'response_data', 'duration', 'created_at'
        ]


class OperationLogSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationLogSetting
        fields = ['id', 'retention_days', 'updated_at']
        read_only_fields = ['id', 'updated_at']
