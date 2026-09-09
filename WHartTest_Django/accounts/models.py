from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

class UserLoginState(models.Model):
    """单设备登录状态：每次登录递增 session_version，旧 token 立即失效。"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="login_state",
        verbose_name="用户",
    )
    session_version = models.PositiveBigIntegerField(
        default=0,
        verbose_name="会话版本号",
        help_text="每次登录 +1；旧版本 access/refresh token 均失效",
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "用户登录状态"
        verbose_name_plural = "用户登录状态"

    def __str__(self):
        return f"UserLoginState(user={self.user_id}, version={self.session_version})"


class SystemConfig(models.Model):
    """
    系统全局配置模型，存储平台品牌标识相关的动态配置。
    采用单例模式，系统中只有一条配置记录。
    """
    title = models.CharField(
        max_length=255, 
        default='WHartTest', 
        verbose_name='平台浏览器标题',
        help_text='显示在浏览器标签页上的文字'
    )
    name = models.CharField(
        max_length=255, 
        default='WHartTest', 
        verbose_name='平台名称',
        help_text='侧边栏和主界面显示的平台Logo旁文本'
    )
    login_title = models.CharField(
        max_length=255, 
        default='WHartTest', 
        verbose_name='登录页标题',
        help_text='登录页面主标题'
    )
    login_subtitle = models.CharField(
        max_length=500, 
        default='小麦智测自动化平台', 
        verbose_name='登录页副标题',
        help_text='登录页面标题下方的描述文字'
    )
    login_tags = models.TextField(
        default='AI 智能生成, RAG 知识库, MCP 工具调用, Skills 技能库, Playwright 自动化, LangGraph, 接口自动化', 
        verbose_name='登录页特色标签',
        help_text='登录页面显示的平台特色标签，用逗号或中文逗号分隔'
    )
    logo_url = models.TextField(
        blank=True, 
        default='', 
        verbose_name='自定义Logo图片Base64或URL',
        help_text='若为空则展示系统默认Logo，支持完整HTTP图片地址或data:image/png;base64,...'
    )
    brand_badge_enabled = models.BooleanField(
        default=True,
        verbose_name='品牌角标是否显示',
        help_text='控制登录页标题右侧及系统导航栏品牌文字右侧的角标是否显示'
    )
    brand_badge_url = models.TextField(
        blank=True,
        default='/PE.svg',
        verbose_name='品牌角标图片Base64或URL',
        help_text='用于登录页标题右侧及系统导航栏品牌文字右侧的角标，支持完整HTTP图片地址、站内路径或data:image/svg+xml;base64,...'
    )
    operation_log_retention_days = models.PositiveIntegerField(
        default=7,
        verbose_name='操作日志自动清理天数',
        help_text='自动清理超过保留天数的操作日志，默认 7 天',
        validators=[MinValueValidator(1), MaxValueValidator(3650)],
    )

    class Meta:
        verbose_name = '系统全局配置'
        verbose_name_plural = '系统全局配置'

    @classmethod
    def get_config(cls):
        config, created = cls.objects.get_or_create(pk=1)
        return config

    def __str__(self):
        return f"SystemConfig(name={self.name})"

