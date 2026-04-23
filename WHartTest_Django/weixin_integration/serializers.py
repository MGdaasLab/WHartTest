from rest_framework import serializers

from .models import WeixinBotAccount, WeixinLoginSession


class WeixinLoginStartSerializer(serializers.Serializer):
    project_id = serializers.IntegerField()
    prompt_id = serializers.IntegerField(required=False, allow_null=True)


class WeixinLoginSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeixinLoginSession
        fields = [
            "session_key",
            "status",
            "qr_data_url",
            "raw_account_id",
            "account_id",
            "scanned_user_id",
            "error_message",
            "expires_at",
            "created_at",
            "updated_at",
        ]


class WeixinBotAccountSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    prompt_name = serializers.CharField(source="prompt.name", read_only=True)

    class Meta:
        model = WeixinBotAccount
        fields = [
            "id",
            "raw_account_id",
            "account_id",
            "project",
            "project_name",
            "prompt",
            "prompt_name",
            "scanned_user_id",
            "is_active",
            "worker_running",
            "status",
            "last_error",
            "last_inbound_at",
            "last_outbound_at",
            "created_at",
            "updated_at",
        ]


class WeixinBotAccountToggleSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()


class WeixinPluginInboundSerializer(serializers.Serializer):
    account_id = serializers.CharField()
    peer_user_id = serializers.CharField()
    text = serializers.CharField(required=False, allow_blank=True, default="")
    context_token = serializers.CharField(required=False, allow_blank=True, default="")
    external_message_id = serializers.CharField(required=False, allow_blank=True, default="")
    session_key = serializers.CharField(required=False, allow_blank=True, default="")
    media_path = serializers.CharField(required=False, allow_blank=True, default="")
    media_type = serializers.CharField(required=False, allow_blank=True, default="")
