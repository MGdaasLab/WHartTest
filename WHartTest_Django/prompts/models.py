from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


from django.utils.translation import gettext_lazy as _

class PromptType(models.TextChoices):
    GENERAL = 'general', _('通用对话')
    DOCUMENT_STRUCTURE = 'document_structure', _('文档结构分析')
    DIRECT_ANALYSIS = 'direct_analysis', _('直接分析')
    GLOBAL_ANALYSIS = 'global_analysis', _('全局分析')
    MODULE_ANALYSIS = 'module_analysis', _('模块分析')
    CONSISTENCY_ANALYSIS = 'consistency_analysis', _('一致性分析')
    TEST_CASE_EXECUTION = 'test_case_execution', _('测试用例执行')

class UserPrompt(models.Model):
    """
    用户级别的提示词管理模型
    每个用户可以创建和管理自己的提示词
    """

    PROGRAM_CALL_TYPES = [
        PromptType.DOCUMENT_STRUCTURE,
        PromptType.DIRECT_ANALYSIS,
        PromptType.GLOBAL_ANALYSIS,
        PromptType.MODULE_ANALYSIS,
        PromptType.CONSISTENCY_ANALYSIS,
        PromptType.TEST_CASE_EXECUTION,
    ]


    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='prompts',
        verbose_name='用户'
    )
    name = models.CharField(
        max_length=255,
        verbose_name='提示词名称',
        help_text='提示词的显示名称'
    )
    content = models.TextField(
        verbose_name='提示词内容',
        help_text='系统提示词的具体内容，将在对话开始时发送给AI'
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name='描述',
        help_text='提示词的用途和说明'
    )
    prompt_type = models.CharField(
        max_length=50,
        choices=PromptType.choices,
        default=PromptType.GENERAL,
        verbose_name='提示词类型',
        help_text='提示词的使用类型'
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name='默认提示词',
        help_text='是否为该用户的默认提示词（仅对通用对话类型有效）'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='是否启用',
        help_text='是否启用此提示词'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )

    class Meta:
        verbose_name = '用户提示词'
        verbose_name_plural = '用户提示词'
        ordering = ['-updated_at']
        # 确保每个用户的提示词名称唯一
        unique_together = ['user', 'name']
        # 添加索引以提高查询性能
        indexes = [
            models.Index(fields=['user', 'is_default']),
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['user', 'prompt_type']),
        ]
        # 添加约束：程序调用类型每用户只能有一个
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'prompt_type'],
                condition=models.Q(prompt_type__in=[
                    PromptType.DOCUMENT_STRUCTURE.value,
                    PromptType.DIRECT_ANALYSIS.value,
                    PromptType.GLOBAL_ANALYSIS.value,
                    PromptType.MODULE_ANALYSIS.value,
                    PromptType.CONSISTENCY_ANALYSIS.value,
                    PromptType.TEST_CASE_EXECUTION.value,
                ]),
                name='unique_user_program_prompt_type'
            )
        ]

    def __str__(self):
        return f"{self.user.username} - {self.name}"

    def clean(self):
        """模型验证"""
        super().clean()

        # 验证提示词内容不能为空
        if not self.content or not self.content.strip():
            raise ValidationError({'content': '提示词内容不能为空'})

        # 程序调用类型不允许设为默认
        if self.is_default and self.prompt_type in self.PROGRAM_CALL_TYPES:
            raise ValidationError({
                'is_default': '程序调用类型的提示词不能设为默认，会影响对话功能'
            })

        # 如果设置为默认提示词，确保该用户只有一个默认提示词（仅限通用对话类型）
        if self.is_default and self.prompt_type == PromptType.GENERAL:
            existing_default = UserPrompt.objects.filter(
                user=self.user,
                is_default=True,
                prompt_type='general'
            ).exclude(pk=self.pk)

            if existing_default.exists():
                raise ValidationError({
                    'is_default': '每个用户只能有一个默认提示词'
                })

        # 验证程序调用类型的唯一性
        if self.prompt_type in self.PROGRAM_CALL_TYPES:
            existing_program_prompt = UserPrompt.objects.filter(
                user=self.user,
                prompt_type=self.prompt_type
            ).exclude(pk=self.pk)

            if existing_program_prompt.exists():
                raise ValidationError({
                    'prompt_type': f'每个用户只能有一个{self.get_prompt_type_display()}类型的提示词'
                })

    def save(self, *args, **kwargs):
        """保存时的额外逻辑"""
        # 如果设置为默认提示词，先将其他默认提示词取消（仅限通用对话类型）
        if self.is_default and self.prompt_type == PromptType.GENERAL:
            UserPrompt.objects.filter(
                user=self.user,
                is_default=True,
                prompt_type=PromptType.GENERAL
            ).exclude(pk=self.pk).update(is_default=False)

        # 验证提示词内容不能为空
        if not self.content or not self.content.strip():
            raise ValidationError({'content': '提示词内容不能为空'})

        super().save(*args, **kwargs)

    @classmethod
    def get_user_prompt_by_type(cls, user, prompt_type):
        """根据类型获取用户提示词"""
        try:
            return cls.objects.get(
                user=user,
                prompt_type=prompt_type,
                is_active=True
            )
        except cls.DoesNotExist:
            return None

    @classmethod
    def get_user_default_prompt(cls, user):
        """获取用户默认提示词（仅限通用对话类型）"""
        try:
            return cls.objects.get(
                user=user,
                prompt_type=PromptType.GENERAL,
                is_default=True,
                is_active=True
            )
        except cls.DoesNotExist:
            return None

    @classmethod
    def get_user_prompts(cls, user, active_only=True):
        """获取用户的所有提示词"""
        queryset = cls.objects.filter(user=user)
        if active_only:
            queryset = queryset.filter(is_active=True)
        return queryset.order_by('-updated_at')
