from rest_framework import serializers
from .models import APIKey

class APIKeySerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source='user.username') # Display username instead of user ID

    class Meta:
        model = APIKey
        fields = ['id', 'name', 'key', 'user', 'created_at', 'expires_at', 'is_active']
        read_only_fields = ['key', 'created_at'] # Key is generated on save, created_at is auto_now_add