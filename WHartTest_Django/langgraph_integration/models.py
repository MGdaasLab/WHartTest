from django.db import models
from django.conf import settings
from django.utils import timezone


class LLMConfig(models.Model):
    """
    LLM配置模型 - 管理大语言模型的配置信息
    统一使用OpenAI兼容格式，支持所有兼容的服务商
    """
    
    PROVIDER_CHOICES = [
        ('openai_compatible', 'OpenAI 兼容'),
        ('deepseek', 'DeepSeek'),
        ('qwen', 'Qwen/通义千问'),
    ]
    
    # 配置标识字段（新增）
    config_name = models.CharField(max_length=255, unique=True, verbose_name="配置名称",
                                  help_text="用户自定义的配置名称，如'生产环境OpenAI'、'测试Claude配置'")
    
    # 供应商字段（新增）
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES, default='openai_compatible', verbose_name="供应商",
                               help_text="LLM服务供应商")
    
    # 模型名称字段（原来的name字段，现在表示具体模型）
    name = models.CharField(max_length=255, verbose_name="模型名称",
                           help_text="具体的模型名称，如 gpt-4, claude-3-sonnet, gpt-3.5-turbo")
    
    # API连接配置（保持不变）
    api_url = models.URLField(verbose_name="API地址", help_text="LLM服务的API端点URL")
    api_key = models.CharField(max_length=512, blank=True, default='', verbose_name="API密钥", help_text="访问LLM服务的API密钥（可选）")
    
    # 提示词配置（保持不变）
    system_prompt = models.TextField(blank=True, null=True, verbose_name="系统提示词",
                                    help_text="指导LLM行为的系统级提示词")
    
    # 多模态支持（新增）
    supports_vision = models.BooleanField(default=False, verbose_name="支持图片输入",
                                        help_text="模型是否支持图片/多模态输入（如GPT-4V、Qwen-VL等）")
    
    # 上下文限制（用于Token计数和对话压缩）
    context_limit = models.IntegerField(default=128000, verbose_name="上下文限制",
                                       help_text="模型最大上下文Token数（GPT-4o: 128000, Claude: 200000, Gemini: 1000000）")

    # 请求超时和重试配置
    request_timeout = models.IntegerField(
        default=120,
        verbose_name="请求超时(秒)",
        help_text="单次LLM请求的超时时间，默认120秒。如果模型响应较慢可适当增加"
    )
    max_retries = models.IntegerField(
        default=3,
        verbose_name="最大重试次数",
        help_text="请求失败时的自动重试次数，默认3次。设为0禁用重试"
    )

    # v2.0.0: 中间件配置
    enable_summarization = models.BooleanField(
        default=True,
        verbose_name="启用上下文摘要",
        help_text="启用后，当对话Token超过阈值时自动压缩上下文（需配合SummarizationMiddleware）"
    )
    enable_hitl = models.BooleanField(
        default=True,
        verbose_name="启用人工审批",
        help_text="启用后，执行高风险操作（如自动化脚本）前需用户确认（需配合HumanInTheLoopMiddleware）"
    )
    enable_streaming = models.BooleanField(
        default=True,
        verbose_name="启用流式输出",
        help_text="启用后，AI回复将以流式方式逐字输出；禁用则等待完整回复后一次性返回"
    )

    # 状态字段（保持不变）
    is_active = models.BooleanField(default=False, verbose_name="是否激活",
                                   help_text="是否为当前激活的LLM配置")
    
    # 时间戳字段（保持不变）
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    def __str__(self):
        return f"{self.config_name} ({self.name})"

    class Meta:
        verbose_name = "LLM配置"
        verbose_name_plural = "LLM配置"
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        # 确保只有一个配置可以激活
        if self.is_active:
            LLMConfig.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


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

    # LLM 运行时解析信息。部分历史数据库已通过 bundle 分支迁移把这些列设为 NOT NULL；
    # 模型层必须提供默认值，否则新建 ChatSession 时 ORM 不会写入这些列，PostgreSQL 会报
    # resolved_module_key/resolved_source/resolved_runtime_mode 违反非空约束。
    resolved_module_key = models.CharField(max_length=64, default='llm_chat', verbose_name="解析模块Key")
    resolved_source = models.CharField(max_length=32, default='legacy', verbose_name="LLM配置来源")
    resolved_bundle_id = models.BigIntegerField(null=True, blank=True, verbose_name="解析配置包ID")
    resolved_runtime_mode = models.CharField(max_length=16, default='auto', verbose_name="运行模式")

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
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['created_at']),
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
    对话消息模型 - 用于权限管理，不存储实际消息内容
    实际消息内容存储在 chat_history.sqlite 中，此模型仅用于Django权限系统
    """
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, verbose_name="对话会话")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="用户")
    message_id = models.CharField(max_length=255, verbose_name="消息ID", 
                                 help_text="LangGraph消息的唯一标识符")
    role = models.CharField(max_length=20, verbose_name="角色", 
                           choices=[('user', '用户'), ('assistant', '助手'), ('system', '系统')])
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "对话消息"
        verbose_name_plural = "对话消息"
        ordering = ['created_at']
        
    def __str__(self):
        return f"{self.session.title} - {self.role} [{self.created_at}]"
