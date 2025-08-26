from rest_framework import serializers
from .models import UserPrompt


class UserPromptSerializer(serializers.ModelSerializer):
    """用户提示词序列化器"""

    class Meta:
        model = UserPrompt
        fields = [
            'id', 'name', 'content', 'description', 'prompt_type',
            'is_default', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_content(self, value):
        """验证提示词内容"""
        if not value or not value.strip():
            raise serializers.ValidationError("提示词内容不能为空")

        # 检查内容长度（可根据需要调整）
        if len(value.strip()) < 10:
            raise serializers.ValidationError("提示词内容至少需要10个字符")

        if len(value) > 10000:
            raise serializers.ValidationError("提示词内容不能超过10000个字符")

        return value.strip()

    def validate(self, attrs):
        """整体验证"""
        # 程序调用类型不允许设为默认
        if attrs.get('is_default') and attrs.get('prompt_type') in UserPrompt.PROGRAM_CALL_TYPES:
            raise serializers.ValidationError({
                'is_default': '程序调用类型的提示词不能设为默认，会影响对话功能'
            })

        # 检查名称唯一性
        if 'name' in attrs:
            user = self.context['request'].user
            name = attrs['name']
            
            existing_prompt = UserPrompt.objects.filter(user=user, name=name)
            if self.instance:
                existing_prompt = existing_prompt.exclude(pk=self.instance.pk)
            
            if existing_prompt.exists():
                raise serializers.ValidationError({
                    'name': '该名称的提示词已存在，请使用其他名称'
                })

        return attrs


class UserPromptListSerializer(serializers.ModelSerializer):
    """用户提示词列表序列化器"""
    prompt_type_display = serializers.CharField(source='get_prompt_type_display', read_only=True)

    class Meta:
        model = UserPrompt
        fields = [
            'id', 'name', 'description', 'prompt_type', 'prompt_type_display',
            'is_default', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'prompt_type_display']

    def validate_name(self, value):
        """验证提示词名称"""
        if not value or not value.strip():
            raise serializers.ValidationError("提示词名称不能为空")
        
        # 检查名称长度
        if len(value.strip()) < 2:
            raise serializers.ValidationError("提示词名称至少需要2个字符")
        
        if len(value.strip()) > 255:
            raise serializers.ValidationError("提示词名称不能超过255个字符")
        
        return value.strip()

    def validate(self, attrs):
        """整体验证"""
        # 如果设置为默认提示词，检查用户是否已有默认提示词
        if attrs.get('is_default', False):
            user = self.context['request'].user
            existing_default = UserPrompt.objects.filter(
                user=user, 
                is_default=True
            )
            
            # 如果是更新操作，排除当前实例
            if self.instance:
                existing_default = existing_default.exclude(pk=self.instance.pk)
            
            if existing_default.exists():
                raise serializers.ValidationError({
                    'is_default': '您已经有一个默认提示词，请先取消其他默认提示词'
                })
        
        return attrs

    def create(self, validated_data):
        """创建提示词时自动关联当前用户"""
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class UserPromptListSerializer(serializers.ModelSerializer):
    """用户提示词列表序列化器（简化版）"""
    prompt_type_display = serializers.CharField(source='get_prompt_type_display', read_only=True)
    
    class Meta:
        model = UserPrompt
        fields = [
            'id', 'name', 'description', 'prompt_type', 'prompt_type_display',
            'is_default', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'prompt_type_display']


class SetDefaultPromptSerializer(serializers.Serializer):
    """设置默认提示词的序列化器"""
    prompt_id = serializers.IntegerField(help_text="要设置为默认的提示词ID")
    
    def validate_prompt_id(self, value):
        """验证提示词ID"""
        user = self.context['request'].user
        
        try:
            prompt = UserPrompt.objects.get(id=value, user=user, is_active=True)
        except UserPrompt.DoesNotExist:
            raise serializers.ValidationError("指定的提示词不存在或您没有权限访问")
        
        return value
