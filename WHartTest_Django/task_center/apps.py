from django.apps import AppConfig


class TaskCenterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'task_center'
    verbose_name = '任务中心'

    def ready(self):
        import task_center.signals  # noqa: F401
