from django.db import models
from django.conf import settings
from django.utils import timezone


class LLMConfig(models.Model):
    """
    LLM配置模型 - 管理大语言模型的配置信息
    """
    
    PROVIDER_CHOICES = [
        ('openai', 'OpenAI'),
        ('anthropic', 'Anthropic/Claude'),
        ('gemini', 'Google Gemini'),
        ('qwen', 'Alibaba Qwen'),
        ('ollama', 'Ollama'),
        ('openai_compatible', 'OpenAI Compatible'),
    ]
    
    # 配置标识字段（新增）
    config_name = models.CharField(max_length=255, unique=True, verbose_name="配置名称",
                                  help_text="用户自定义的配置名称，如'生产环境OpenAI'、'测试Claude配置'")
    
    # 供应商字段（新增）
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES, default='openai', verbose_name="供应商",
                               help_text="LLM服务供应商")
    
    # 模型名称字段（原来的name字段，现在表示具体模型）
    name = models.CharField(max_length=255, verbose_name="模型名称",
                           help_text="具体的模型名称，如 gpt-4, claude-3-sonnet, gpt-3.5-turbo")
    
    # API连接配置（保持不变）
    api_url = models.URLField(verbose_name="API地址", help_text="LLM服务的API端点URL")
    api_key = models.CharField(max_length=512, verbose_name="API密钥", help_text="访问LLM服务的API密钥")
    
    # 提示词配置（保持不变）
    system_prompt = models.TextField(blank=True, null=True, verbose_name="系统提示词",
                                    help_text="指导LLM行为的系统级提示词")
    
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
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "对话会话"
        verbose_name_plural = "对话会话"
        ordering = ['-updated_at']
        
    def __str__(self):
        return f"{self.user.username} - {self.title}"


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
