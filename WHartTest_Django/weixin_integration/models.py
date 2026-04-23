import re

from django.contrib.auth.models import User
from django.db import models


def normalize_weixin_account_id(raw_account_id: str) -> str:
    value = (raw_account_id or "").strip()
    if not value:
        return ""
    normalized = re.sub(r"[^0-9A-Za-z]+", "-", value).strip("-")
    return normalized.lower()


class WeixinLoginSession(models.Model):
    STATUS_CHOICES = [
        ("wait", "等待扫码"),
        ("scaned", "已扫码"),
        ("confirmed", "已确认"),
        ("expired", "已过期"),
        ("failed", "失败"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="weixin_login_sessions"
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="weixin_login_sessions",
    )
    prompt = models.ForeignKey(
        "prompts.UserPrompt",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="weixin_login_sessions",
    )
    session_key = models.CharField(max_length=100, unique=True, db_index=True)
    qrcode = models.TextField(blank=True, default="")
    qr_data_url = models.TextField(blank=True, default="")
    base_url = models.URLField(default="https://ilinkai.weixin.qq.com")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="wait")
    raw_account_id = models.CharField(max_length=255, blank=True, default="")
    account_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    bot_token = models.CharField(max_length=1024, blank=True, default="")
    scanned_user_id = models.CharField(max_length=255, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "微信登录会话"
        verbose_name_plural = "微信登录会话"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.project.name} - {self.session_key}"


class WeixinBotAccount(models.Model):
    STATUS_CHOICES = [
        ("connected", "已连接"),
        ("running", "运行中"),
        ("stopped", "已停止"),
        ("error", "异常"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="weixin_bot_accounts"
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="weixin_bot_accounts",
    )
    prompt = models.ForeignKey(
        "prompts.UserPrompt",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="weixin_bot_accounts",
    )
    raw_account_id = models.CharField(max_length=255, unique=True)
    account_id = models.CharField(max_length=255, unique=True, db_index=True)
    token = models.CharField(max_length=1024)
    base_url = models.URLField(default="https://ilinkai.weixin.qq.com")
    scanned_user_id = models.CharField(max_length=255, blank=True, default="")
    sync_cursor = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    worker_running = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="connected")
    last_error = models.TextField(blank=True, default="")
    last_inbound_at = models.DateTimeField(null=True, blank=True)
    last_outbound_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "微信机器人账号"
        verbose_name_plural = "微信机器人账号"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.user.username} - {self.raw_account_id}"


class WeixinConversation(models.Model):
    account = models.ForeignKey(
        WeixinBotAccount,
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    peer_user_id = models.CharField(max_length=255, db_index=True)
    context_token = models.TextField(blank=True, default="")
    chat_session = models.OneToOneField(
        "langgraph_integration.ChatSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="weixin_conversation",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "微信会话"
        verbose_name_plural = "微信会话"
        unique_together = ("account", "peer_user_id")
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.account.account_id} -> {self.peer_user_id}"


class WeixinConversationMessage(models.Model):
    ROLE_CHOICES = [
        ("user", "用户"),
        ("assistant", "助手"),
        ("system", "系统"),
    ]

    conversation = models.ForeignKey(
        WeixinConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    external_message_id = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "微信会话消息"
        verbose_name_plural = "微信会话消息"
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "external_message_id"],
                condition=models.Q(external_message_id__gt=""),
                name="unique_weixin_conversation_external_message",
            )
        ]

    def __str__(self):
        return f"{self.conversation_id} - {self.role}"
