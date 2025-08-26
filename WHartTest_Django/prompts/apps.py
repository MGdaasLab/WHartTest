from django.apps import AppConfig


class PromptsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "prompts"
    verbose_name = "提示词管理"

    def ready(self):
        """应用准备就绪时的初始化"""
        pass
