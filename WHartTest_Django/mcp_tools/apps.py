from django.apps import AppConfig


class McpToolsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mcp_tools'

    def ready(self):
        """应用准备就绪时的初始化"""
        # 导入信号处理器以注册清理函数
        try:
            import mcp_tools.signals
        except ImportError:
            pass  # 如果signals文件不存在，忽略错误
