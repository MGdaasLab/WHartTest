from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class OperationLog(models.Model):
    """
    用户操作日志模型
    """
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="操作用户",
        related_name="operation_logs"
    )
    username = models.CharField(max_length=150, blank=True, verbose_name="用户名")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP地址")
    user_agent = models.TextField(blank=True, verbose_name="User-Agent")
    path = models.CharField(max_length=255, verbose_name="请求路径")
    method = models.CharField(max_length=10, verbose_name="请求方法")
    module = models.CharField(max_length=100, blank=True, verbose_name="操作模块")
    action = models.CharField(max_length=255, blank=True, verbose_name="操作描述")
    request_data = models.TextField(blank=True, verbose_name="请求数据")
    response_code = models.IntegerField(null=True, blank=True, verbose_name="响应状态码")
    response_data = models.TextField(blank=True, verbose_name="响应数据")
    duration = models.IntegerField(verbose_name="执行耗时(毫秒)", default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="操作时间")

    class Meta:
        verbose_name = "操作日志"
        verbose_name_plural = "操作日志"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.username} - {self.action} ({self.created_at})"


class OperationLogSetting(models.Model):
    """操作日志自动清理设置（单例）。"""

    retention_days = models.PositiveIntegerField(
        default=7,
        verbose_name="操作日志保留天数",
        help_text="自动清理超过保留天数的操作日志，默认 7 天",
        validators=[MinValueValidator(1), MaxValueValidator(3650)],
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "操作日志设置"
        verbose_name_plural = "操作日志设置"

    def __str__(self):
        return f"操作日志保留 {self.retention_days} 天"

    @classmethod
    def get_config(cls):
        config, _ = cls.objects.get_or_create(id=1, defaults={"retention_days": 7})
        return config
