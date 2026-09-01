from django.db import models
from django.db.models import Q
from django.conf import settings
from django.utils import timezone


LLM_BUNDLE_SLOT_CHOICES = [
    ("llm_chat", "LLM对话"),
    ("requirement_review", "需求评审"),
    ("testcase_generation", "测试用例生成"),
    ("testcase_execution", "测试用例执行"),
]

DEFAULT_LLM_BUNDLE_SLOT_KEY = "llm_chat"

LLM_RESOLUTION_SOURCE_CHOICES = [
    ("personal_slot", "个人配置槽位"),
    ("personal_fallback_chat", "个人默认槽位继承"),
    ("global_slot", "全局配置槽位"),
    ("global_fallback_chat", "全局默认槽位继承"),
]

LLM_PROVIDER_CHOICES = [
    ("openai_compatible", "OpenAI 兼容"),
    ("deepseek", "DeepSeek"),
    ("qwen", "Qwen/通义千问"),
]

LLM_RUNTIME_MODE_CHOICES = [
    ("standard", "标准模式"),
    ("deep", "Deep Agent 模式"),
    ("auto", "自动模式"),
]

DEFAULT_LLM_RUNTIME_MODE = "standard"


class ChatSession(models.Model):
    """
    对话会话模型 - 用于权限管理，不存储实际聊天数据
    实际聊天数据存储在 chat_history.sqlite 中，此模型仅用于Django权限系统
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="用户")
    session_id = models.CharField(max_length=255, unique=True, verbose_name="会话ID",
                                  help_text="LangGraph会话的唯一标识符")
    title = models.CharField(max_length=200, verbose_name="对话标题", default="新对话")
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, null=True, blank=True, verbose_name="关联项目")
    prompt = models.ForeignKey('prompts.UserPrompt', on_delete=models.SET_NULL, null=True, blank=True,
                               verbose_name="关联提示词", help_text="该会话使用的提示词")
    resolved_bundle = models.ForeignKey(
        "LLMConfigBundle",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_sessions",
        verbose_name="已解析配置",
    )
    resolved_module_key = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name="已解析模块键",
    )
    resolved_source = models.CharField(
        max_length=32,
        choices=LLM_RESOLUTION_SOURCE_CHOICES,
        blank=True,
        default="",
        verbose_name="已解析来源",
    )
    resolved_runtime_mode = models.CharField(
        max_length=16,
        choices=LLM_RUNTIME_MODE_CHOICES,
        blank=True,
        default="",
        verbose_name="已解析运行模式",
    )


    # Token 使用统计
    total_input_tokens = models.BigIntegerField(default=0, verbose_name="累计输入 Token",
                                                help_text="该会话累计消耗的输入 Token 数")
    total_output_tokens = models.BigIntegerField(default=0, verbose_name="累计输出 Token",
                                                 help_text="该会话累计消耗的输出 Token 数")
    total_tokens = models.BigIntegerField(default=0, verbose_name="累计总 Token",
                                          help_text="该会话累计消耗的总 Token 数（输入+输出）")
    total_cache_read_tokens = models.BigIntegerField(default=0, verbose_name="累计缓存命中 Token",
                                                      help_text="该会话累计缓存命中的 Token 数")
    request_count = models.IntegerField(default=0, verbose_name="请求次数",
                                        help_text="该会话的 LLM 请求次数")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "对话会话"
        verbose_name_plural = "对话会话"
        ordering = ['-updated_at']
        
    def __str__(self):
        return f"{self.user.username} - {self.title}"


class LLMConfigBundle(models.Model):
    """LLM 配置，按用户维护固定模块槽位。"""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="llm_config_bundles",
        verbose_name="所属用户",
    )
    config_name = models.CharField(max_length=255, verbose_name="配置名称")
    is_active = models.BooleanField(default=False, verbose_name="是否激活")
    is_global = models.BooleanField(default=False, verbose_name="是否全局可见")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "LLM配置"
        verbose_name_plural = "LLM配置"
        ordering = ["-updated_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner"],
                condition=Q(is_active=True),
                name="unique_active_llm_bundle_per_user",
            ),
            models.UniqueConstraint(
                fields=["owner", "config_name"],
                name="unique_llm_bundle_name_per_owner",
            ),
        ]

    def __str__(self):
        return f"{self.owner.username} - {self.config_name}"

    def save(self, *args, **kwargs):
        if self.is_active:
            LLMConfigBundle.objects.filter(owner=self.owner, is_active=True).exclude(
                pk=self.pk
            ).update(is_active=False)
        if self.is_global and not self.is_active:
            raise ValueError("仅激活的配置可以开启全局开关")
        super().save(*args, **kwargs)


class LLMConfigBundleSlot(models.Model):
    """配置中的单个模块槽位。"""

    bundle = models.ForeignKey(
        LLMConfigBundle,
        on_delete=models.CASCADE,
        related_name="slots",
        verbose_name="所属配置",
    )
    slot_key = models.CharField(
        max_length=64,
        choices=LLM_BUNDLE_SLOT_CHOICES,
        verbose_name="模块槽位",
    )
    is_configured = models.BooleanField(default=False, verbose_name="是否已配置")

    provider = models.CharField(
        max_length=50,
        choices=LLM_PROVIDER_CHOICES,
        default="openai_compatible",
        verbose_name="供应商",
    )
    name = models.CharField(max_length=255, blank=True, default="", verbose_name="模型名称")
    api_url = models.URLField(blank=True, default="", verbose_name="API地址")
    api_key = models.CharField(
        max_length=512,
        blank=True,
        default="",
        verbose_name="API密钥",
    )
    system_prompt = models.TextField(blank=True, null=True, verbose_name="系统提示词")
    supports_vision = models.BooleanField(default=False, verbose_name="支持图片输入")
    context_limit = models.IntegerField(default=128000, verbose_name="上下文限制")
    request_timeout = models.IntegerField(default=120, verbose_name="请求超时(秒)")
    max_retries = models.IntegerField(default=3, verbose_name="最大重试次数")
    enable_summarization = models.BooleanField(default=True, verbose_name="启用上下文摘要")
    enable_hitl = models.BooleanField(default=False, verbose_name="启用人工审批")
    enable_streaming = models.BooleanField(default=True, verbose_name="启用流式输出")
    default_runtime_mode = models.CharField(
        max_length=16,
        choices=LLM_RUNTIME_MODE_CHOICES,
        default=DEFAULT_LLM_RUNTIME_MODE,
        verbose_name="默认运行模式",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "LLM配置槽位"
        verbose_name_plural = "LLM配置槽位"
        ordering = ["slot_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["bundle", "slot_key"],
                name="unique_llm_bundle_slot_key",
            )
        ]

    def __str__(self):
        return f"{self.bundle.config_name} - {self.slot_key}"


class LLMGlobalBundleRotationState(models.Model):
    """全局配置轮询状态。"""

    rotation_key = models.CharField(
        max_length=64,
        unique=True,
        default="global_bundle_pool",
        verbose_name="轮询键",
    )
    current_index = models.PositiveIntegerField(default=0, verbose_name="当前轮询下标")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "LLM全局配置轮询状态"
        verbose_name_plural = "LLM全局配置轮询状态"

    def __str__(self):
        return f"{self.rotation_key}: {self.current_index}"


class TokenUsageRecord(models.Model):
    """
    独立的 Token 使用记录 — 不随会话删除而丢失

    每次 LLM 请求产生一条记录。session_id 仅存字符串，不依赖 ChatSession 外键，
    因此删除对话不影响统计数据。
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        verbose_name="用户",
    )
    project = models.ForeignKey(
        'projects.Project', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="关联项目",
    )
    session_id = models.CharField(
        max_length=255, verbose_name="会话ID",
        help_text="关联的会话标识（非外键）",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    input_tokens = models.IntegerField(default=0, verbose_name="输入 Token")
    output_tokens = models.IntegerField(default=0, verbose_name="输出 Token")
    total_tokens = models.IntegerField(default=0, verbose_name="总 Token")
    cache_read_tokens = models.IntegerField(default=0, verbose_name="缓存命中 Token")

    class Meta:
        verbose_name = "Token 使用记录"
        verbose_name_plural = "Token 使用记录"
        ordering = ['-created_at']
        # 索引名与迁移 0023 保持一致（原 :104 重复定义的显式名，删除后保留于此）
        indexes = [
            models.Index(
                fields=['user', 'created_at'],
                name='langgraph_i_user_id_6bb484_idx',
            ),
            models.Index(
                fields=['created_at'],
                name='langgraph_i_created_30561a_idx',
            ),
        ]

    def __str__(self):
        return f"{self.user_id} - {self.session_id} - {self.total_tokens} tokens"


class UserToolApproval(models.Model):
    """
    用户工具审批偏好 - 记住用户对高风险工具的审批选择

    当 HITL（Human-in-the-Loop）启用时，用户可以选择"记住此选择"，
    后续相同工具的调用将自动应用之前的决策。
    """

    POLICY_CHOICES = [
        ('always_allow', '始终允许'),
        ('always_reject', '始终拒绝'),
        ('ask_every_time', '每次询问'),
    ]

    SCOPE_CHOICES = [
        ('session', '仅本次会话'),
        ('permanent', '永久生效'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tool_approvals',
        verbose_name="用户"
    )
    tool_name = models.CharField(
        max_length=100,
        verbose_name="工具名称",
        help_text="需要审批的工具名称，如 execute_script, run_playwright"
    )
    policy = models.CharField(
        max_length=20,
        choices=POLICY_CHOICES,
        default='ask_every_time',
        verbose_name="审批策略"
    )
    scope = models.CharField(
        max_length=20,
        choices=SCOPE_CHOICES,
        default='permanent',
        verbose_name="生效范围"
    )
    session_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="会话ID",
        help_text="当 scope='session' 时，仅在此会话内生效"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "用户工具审批偏好"
        verbose_name_plural = "用户工具审批偏好"
        # 每个用户对每个工具只能有一个偏好（永久）或每个会话一个偏好
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'tool_name', 'scope', 'session_id'],
                name='unique_user_tool_approval'
            )
        ]
        indexes = [
            models.Index(fields=['user', 'tool_name']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.tool_name}: {self.policy}"


class ChatMessage(models.Model):
    """
    对话消息模型 - 用于持久化保存聊天消息内容与元数据，支持极速加载历史。
    """
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, verbose_name="对话会话")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="用户")
    message_id = models.CharField(
        max_length=255, 
        verbose_name="消息ID", 
        help_text="LangGraph消息的唯一标识符",
        db_index=True
    )
    role = models.CharField(
        max_length=20, 
        verbose_name="角色/类型", 
        choices=[
            ('system', '系统'),
            ('human', '用户'),
            ('ai', '助手'),
            ('tool', '工具'),
            ('unknown', '未知')
        ]
    )
    content = models.TextField(blank=True, default="", verbose_name="消息内容")
    images = models.JSONField(blank=True, default=list, verbose_name="图片列表")
    image = models.TextField(blank=True, null=True, verbose_name="单张图片(兼容)")
    metadata = models.JSONField(blank=True, default=dict, verbose_name="元数据")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="创建时间")

    class Meta:
        verbose_name = "对话消息"
        verbose_name_plural = "对话消息"
        ordering = ['created_at', 'id']
        constraints = [
            models.UniqueConstraint(fields=['session', 'message_id'], name='unique_session_chat_message')
        ]
        
    def __str__(self):
        return f"{self.session.session_id} - {self.role} [{self.created_at}]"
