from rest_framework import serializers
from .models import LLMConfig, UserToolApproval


class LLMConfigSerializer(serializers.ModelSerializer):
    """
    LLM配置序列化器，用于创建和更新LLM配置
    注意：为了安全，在读取时不返回 api_key 字段
    """

    class Meta:
        model = LLMConfig
        fields = [
            "id",
            "config_name",
            "provider",
            "name",
            "api_url",
            "api_key",
            "system_prompt",
            "supports_vision",
            "context_limit",
            "enable_summarization",
            "enable_hitl",
            "enable_streaming",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {
            "api_key": {"write_only": True}  # API密钥只允许写入，不允许读取
        }

    def to_representation(self, instance):
        """
        自定义序列化输出，隐藏敏感字段
        """
        data = super().to_representation(instance)
        # 移除 api_key 字段，或者用掩码替换
        if "api_key" in data:
            # 可以选择完全移除
            del data["api_key"]
            # 或者用掩码显示（如果需要显示部分信息用于识别）
            # 如需展示掩码，可在此将 api_key 替换为固定长度星号。
        return data

    def validate_config_name(self, value):
        """验证配置名称"""
        if not value or not value.strip():
            raise serializers.ValidationError("配置名称不能为空")
        return value.strip()

    def validate_name(self, value):
        """验证模型名称（原name字段）"""
        if not value or not value.strip():
            raise serializers.ValidationError("模型名称不能为空")
        return value.strip()

    def validate_api_key(self, value):
        """验证API密钥"""
        if value and len(value.strip()) < 1:
            raise serializers.ValidationError("API密钥长度至少需要1个字符")
        return value.strip() if value else ""

    def validate_api_url(self, value):
        """验证API地址"""
        if not value:
            raise serializers.ValidationError("API地址不能为空")

        # 简单的URL格式验证
        if not (value.startswith("http://") or value.startswith("https://")):
            raise serializers.ValidationError("API地址必须以http://或https://开头")

        return value

    def validate(self, attrs):
        """全局验证"""
        # 检查是否存在同名配置（排除当前实例）
        config_name = attrs.get("config_name")
        if config_name:
            queryset = LLMConfig.objects.filter(config_name=config_name)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError({"config_name": "配置名称已存在"})

        return attrs

    def create(self, validated_data):
        """创建LLM配置"""
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """更新LLM配置"""
        return super().update(instance, validated_data)


class UserToolApprovalSerializer(serializers.ModelSerializer):
    """用户工具审批偏好序列化器"""

    class Meta:
        model = UserToolApproval
        fields = [
            "id",
            "tool_name",
            "policy",
            "scope",
            "session_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_tool_name(self, value):
        """验证工具名称"""
        if not value or not value.strip():
            raise serializers.ValidationError("工具名称不能为空")
        return value.strip()

    def validate(self, attrs):
        """全局验证"""
        scope = attrs.get("scope", "permanent")
        session_id = attrs.get("session_id")

        # 如果是会话级别偏好，必须提供 session_id
        if scope == "session" and not session_id:
            raise serializers.ValidationError(
                {"session_id": "会话级别偏好必须提供 session_id"}
            )

        return attrs


class UserToolApprovalBatchSerializer(serializers.Serializer):
    """批量更新用户工具审批偏好"""

    tool_name = serializers.CharField(max_length=100)
    policy = serializers.ChoiceField(choices=UserToolApproval.POLICY_CHOICES)
    scope = serializers.ChoiceField(
        choices=UserToolApproval.SCOPE_CHOICES, default="permanent"
    )
    session_id = serializers.CharField(max_length=255, required=False, allow_null=True)
