from rest_framework import serializers
from projects.models import Project # Assuming your Project model is in the 'projects' app
from .models import RemoteMCPConfig # Import RemoteMCPConfig

class MCPProjectListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing projects for MCP tools.
    Provides a minimal set of fields.
    """
    class Meta:
        model = Project
        fields = ['id', 'name', 'description'] # Added description for more context
        # For more complex scenarios, you might want to add read_only_fields
        # if some fields should not be updatable through other potential MCP tool endpoints
        # read_only_fields = ['id', 'creator']

class RemoteMCPConfigSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username') # Display username instead of user ID

    class Meta:
        model = RemoteMCPConfig
        fields = ['id', 'name', 'url', 'transport', 'headers', 'is_active', 'owner', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']