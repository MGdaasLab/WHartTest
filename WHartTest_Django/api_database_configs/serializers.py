from rest_framework import serializers

from .models import ApiDatabaseConfig


class ApiDatabaseConfigSerializer(serializers.ModelSerializer):
    # Map db_type -> type for frontend compatibility
    type = serializers.CharField(source='db_type')

    class Meta:
        model = ApiDatabaseConfig
        fields = [
            'id', 'name', 'project', 'type', 'host', 'port',
            'username', 'password', 'database', 'charset',
            'connection_params', 'psm', 'verify_ssl',
            'description', 'is_active', 'created_by',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'project', 'created_by', 'created_at', 'updated_at']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Mask password for security
        if 'password' in data:
            data['password'] = '******'
        if data.get('connection_params') is None:
            data['connection_params'] = {}
        return data
