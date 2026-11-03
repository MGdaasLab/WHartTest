from django.apps import AppConfig


class TaskCenterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'task_center'
    verbose_name = '任务中心'

    def ready(self):
        import task_center.signals  # noqa: F401
        # 执行记录 running 看门狗：每小时巡检兜底（best-effort，不阻塞启动）
        try:
            from .watchdog_schedule import ensure_watchdog_beat_task
            ensure_watchdog_beat_task()
        except Exception:
            pass
