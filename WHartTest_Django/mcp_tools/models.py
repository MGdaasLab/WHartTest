from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
import json

User = get_user_model()

class RemoteMCPConfig(models.Model):
    """
    Model to store configurations for remote MCP servers.
    """
    name = models.CharField(max_length=255, unique=True, help_text="远程 MCP 服务器的名称")
    # 使用 CharField 而不是 URLField，以支持 Docker 容器名等非标准主机名
    url = models.CharField(max_length=2048, help_text="远程 MCP 服务器的 URL")
    transport = models.CharField(
        max_length=50,
        default="streamable-http", # 默认使用 streamable-http
        help_text="MCP 服务器的传输协议，例如 'streamable-http'"
    )
    headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="可选的认证头，例如 {'Authorization': 'Bearer YOUR_TOKEN'}"
    )
    is_active = models.BooleanField(default=True, help_text="是否启用此远程 MCP 服务器")
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='remote_mcp_configs',
        help_text="此远程 MCP 配置的拥有者"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "远程 MCP 配置"
        verbose_name_plural = "远程 MCP 配置"
        ordering = ['name']

    def __str__(self):
        return self.name

    def clean(self):
        """
        Custom validation for headers field.
        Ensures headers is a valid JSON object.
        """
        if not isinstance(self.headers, dict):
            raise ValidationError({'headers': 'Headers must be a valid JSON object.'})
        # Optionally, add more specific validation for header keys/values if needed
        super().clean()

    def save(self, *args, **kwargs):
        self.full_clean() # Call full_clean to run all validations including clean()
        super().save(*args, **kwargs)
