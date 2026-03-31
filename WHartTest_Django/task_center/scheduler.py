"""
任务调度服务 - 使用 django-celery-beat 数据库调度管理定时任务
"""
import json
import logging

from django.utils import timezone
from django_celery_beat.models import ClockedSchedule, CrontabSchedule, PeriodicTask

from .models import ScheduledTask

logger = logging.getLogger(__name__)


def _beat_name(task: ScheduledTask) -> str:
    return f"scheduled_task_{task.id}"


def _build_crontab_kwargs(task: ScheduledTask) -> dict | None:
    """根据任务配置构建 CrontabSchedule 字段"""
    if task.schedule_type == ScheduledTask.ScheduleType.DAILY:
        return {
            'minute': str(task.daily_time.minute),
            'hour': str(task.daily_time.hour),
            'day_of_week': '*',
            'day_of_month': '*',
            'month_of_year': '*',
        }
    if task.schedule_type == ScheduledTask.ScheduleType.WEEKLY:
        dow = ','.join(str((d + 1) % 7) for d in task.weekly_days)
        return {
            'minute': str(task.weekly_time.minute),
            'hour': str(task.weekly_time.hour),
            'day_of_week': dow or '*',
            'day_of_month': '*',
            'month_of_year': '*',
        }
    if task.schedule_type == ScheduledTask.ScheduleType.HOURLY:
        return {
            'minute': str(task.hourly_minute),
            'hour': '*',
            'day_of_week': '*',
            'day_of_month': '*',
            'month_of_year': '*',
        }
    return None


def register_periodic_task(task: ScheduledTask):
    """将任务注册到 django-celery-beat 调度表（数据库持久化）"""
    name = _beat_name(task)
    defaults = {
        'task': 'task_center.tasks.execute_scheduled_task',
        'args': json.dumps([task.id, 'scheduled']),
        'queue': 'task_center',
        'enabled': True,
    }

    if task.schedule_type == ScheduledTask.ScheduleType.ONCE:
        if not task.once_datetime or task.once_datetime <= timezone.now():
            logger.warning(f"一次性任务 [{task.name}] 时间已过，跳过注册")
            return
        clocked, _ = ClockedSchedule.objects.get_or_create(clocked_time=task.once_datetime)
        defaults.update(clocked=clocked, crontab=None, interval=None, one_off=True)
    else:
        crontab_kwargs = _build_crontab_kwargs(task)
        if not crontab_kwargs:
            return
        crontab_kwargs['timezone'] = timezone.get_current_timezone()
        crontab_schedule, _ = CrontabSchedule.objects.get_or_create(**crontab_kwargs)
        defaults.update(crontab=crontab_schedule, clocked=None, interval=None, one_off=False)

    PeriodicTask.objects.update_or_create(name=name, defaults=defaults)
    logger.info(f"任务 [{task.name}] 已注册到 django-celery-beat")


def unregister_periodic_task(task: ScheduledTask):
    """从 django-celery-beat 调度表移除任务"""
    deleted, _ = PeriodicTask.objects.filter(name=_beat_name(task)).delete()
    if deleted:
        logger.info(f"任务 [{task.name}] 已从 django-celery-beat 移除")
