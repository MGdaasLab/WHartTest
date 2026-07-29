import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from projects.models import Project
from testcases.models import TestSuite
from ui_automation.models import UiTestCase


class ScheduledTask(models.Model):
    """定时任务配置模型"""

    class TaskStatus(models.TextChoices):
        DISABLED = 'disabled', _('未启用')
        RUNNING = 'running', _('运行中')

    class ScheduleType(models.TextChoices):
        ONCE = 'once', _('仅执行一次')
        HOURLY = 'hourly', _('每小时')
        DAILY = 'daily', _('每天')
        WEEKLY = 'weekly', _('每周')

    class TaskModule(models.TextChoices):
        UI_AUTOMATION = 'ui_automation', _('UI 自动化')
        TEST_SUITE = 'test_suite', _('测试套件')

    class ExecutionTarget(models.TextChoices):
        ACTUATOR = 'actuator', _('执行器')

    # 基本信息
    name = models.CharField(_('任务名称'), max_length=50)
    description = models.TextField(_('任务描述'), max_length=200, blank=True, default='')
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE,
        related_name='scheduled_tasks', verbose_name=_('所属项目')
    )
    module = models.CharField(
        _('所属模块'), max_length=20, choices=TaskModule.choices
    )
    execution_target = models.CharField(
        _('执行目标'), max_length=20, choices=ExecutionTarget.choices,
        default=ExecutionTarget.ACTUATOR
    )
    actuator_id = models.CharField(
        _('执行器ID'), max_length=100, blank=True, default='',
        help_text=_('UI自动化模块时选择的执行器')
    )

    # 关联的执行对象
    test_suite = models.ForeignKey(
        TestSuite, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='scheduled_tasks',
        verbose_name=_('关联测试套件'),
        help_text=_('模块为"测试套件"时必填')
    )
    ui_testcases = models.ManyToManyField(
        UiTestCase, blank=True, related_name='scheduled_tasks',
        verbose_name=_('关联UI用例'),
        help_text=_('模块为"UI自动化"时选择要执行的用例')
    )

    # 调度配置
    schedule_type = models.CharField(
        _('调度策略'), max_length=10, choices=ScheduleType.choices
    )
    once_datetime = models.DateTimeField(_('一次性执行时间'), null=True, blank=True)
    daily_time = models.TimeField(_('每日执行时间'), null=True, blank=True)
    weekly_days = models.JSONField(
        _('每周执行日'), default=list, blank=True,
        help_text=_('0=周一, 6=周日')
    )
    weekly_time = models.TimeField(_('每周执行时间'), null=True, blank=True)
    hourly_minute = models.PositiveSmallIntegerField(
        _('每小时第几分钟'), null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(59)]
    )

    # 重试策略
    retry_enabled = models.BooleanField(_('启用失败重试'), default=False)
    retry_count = models.PositiveSmallIntegerField(
        _('重试次数'), default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    retry_interval = models.PositiveSmallIntegerField(
        _('重试间隔(分钟)'), default=2,
        validators=[MinValueValidator(1), MaxValueValidator(30)]
    )

    # 状态
    status = models.CharField(
        _('状态'), max_length=10, choices=TaskStatus.choices,
        default=TaskStatus.DISABLED
    )

    # Celery 任务追踪
    celery_task_id = models.CharField(
        _('Celery任务ID'), max_length=255, blank=True, default=''
    )

    # 审计
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='created_scheduled_tasks', verbose_name=_('创建人')
    )
    last_run_at = models.DateTimeField(_('最近执行时间'), null=True, blank=True)
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('定时任务')
        verbose_name_plural = _('定时任务')
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def get_schedule_display_text(self):
        """获取可读的调度描述"""
        if self.schedule_type == self.ScheduleType.ONCE:
            if self.once_datetime:
                return f"一次性 {self.once_datetime.strftime('%Y-%m-%d %H:%M')}"
            return "一次性（未设置时间）"
        elif self.schedule_type == self.ScheduleType.DAILY:
            if self.daily_time:
                return f"每天 {self.daily_time.strftime('%H:%M')}"
            return "每天"
        elif self.schedule_type == self.ScheduleType.WEEKLY:
            day_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
            days = ', '.join(day_names[d] for d in sorted(self.weekly_days) if 0 <= d <= 6)
            time_str = self.weekly_time.strftime('%H:%M') if self.weekly_time else ''
            return f"每周 {days} {time_str}".strip()
        elif self.schedule_type == self.ScheduleType.HOURLY:
            if self.hourly_minute is not None:
                return f"每小时第 {self.hourly_minute} 分钟"
            return "每小时"
        return str(self.schedule_type)


class TaskExecution(models.Model):
    """任务执行记录模型"""

    class TriggerType(models.TextChoices):
        SCHEDULED = 'scheduled', _('定时调度')
        MANUAL = 'manual', _('手动执行')
        API = 'api', _('API 触发')

    class ExecutionStatus(models.TextChoices):
        RUNNING = 'running', _('执行中')
        SUCCESS = 'success', _('成功')
        FAILED = 'failed', _('失败')

    execution_id = models.CharField(
        _('执行ID'), max_length=50, unique=True, editable=False
    )
    task = models.ForeignKey(
        ScheduledTask, on_delete=models.CASCADE,
        related_name='executions', verbose_name=_('所属任务')
    )
    trigger_type = models.CharField(
        _('触发方式'), max_length=10, choices=TriggerType.choices
    )
    status = models.CharField(
        _('状态'), max_length=10, choices=ExecutionStatus.choices,
        default=ExecutionStatus.RUNNING
    )
    started_at = models.DateTimeField(_('开始时间'), auto_now_add=True)
    finished_at = models.DateTimeField(_('结束时间'), null=True, blank=True)
    log = models.TextField(_('执行日志'), blank=True, default='')
    error_message = models.TextField(_('错误信息'), blank=True, default='')

    # Celery 追踪
    celery_task_id = models.CharField(
        _('Celery任务ID'), max_length=255, blank=True, default=''
    )

    class Meta:
        verbose_name = _('执行记录')
        verbose_name_plural = _('执行记录')
        ordering = ['-started_at']

    def __str__(self):
        return self.execution_id

    def save(self, *args, **kwargs):
        if not self.execution_id:
            from django.utils import timezone
            ts = timezone.now().strftime('%Y%m%d_%H%M%S')
            self.execution_id = f"run_{ts}_{uuid.uuid4().hex[:6]}"
        super().save(*args, **kwargs)

    @property
    def duration_display(self):
        """可读的执行耗时"""
        if not self.finished_at or not self.started_at:
            return '—'
        delta = self.finished_at - self.started_at
        total_seconds = int(delta.total_seconds())
        if total_seconds < 60:
            return f"{total_seconds}s"
        minutes, seconds = divmod(total_seconds, 60)
        if minutes < 60:
            return f"{minutes}m {seconds}s"
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes}m {seconds}s"
