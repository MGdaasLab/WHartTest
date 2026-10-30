"""执行记录 running 看门狗的 beat 注册（apps.ready 时调用，best-effort）。"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

BEAT_TASK_NAME = "task_center.watchdog_stale_executions"


def ensure_watchdog_beat_task() -> None:
    """在 django_celery_beat 中注册每小时一次的看门狗巡检任务。"""
    try:
        from django.db import connection
        from django_celery_beat.models import IntervalSchedule, PeriodicTask

        # Avoid running during migrate when tables may not exist.
        tables = set(connection.introspection.table_names())
        if "django_celery_beat_periodictask" not in tables:
            return

        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=1,
            period=IntervalSchedule.HOURS,
        )
        PeriodicTask.objects.update_or_create(
            name=BEAT_TASK_NAME,
            defaults={
                "interval": schedule,
                "task": BEAT_TASK_NAME,
                "enabled": True,
            },
        )
    except Exception as exc:
        logger.debug("ensure celery beat watchdog task skipped: %s", exc)
