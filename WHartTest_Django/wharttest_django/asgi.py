"""
wharttest_django 项目的 ASGI 配置。

对外暴露模块级变量 ``application`` 作为 ASGI 可调用入口。

更多说明见：
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

# 导入 os 模块，用于设置进程级环境变量与 umask。
import os

# 设置 umask，确保新建文件权限便于同组协作。
os.umask(0o002)

# 指定 Django 配置模块路径（若未提前设置）。
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wharttest_django.settings")

# 导入 Django 主模块，准备初始化应用注册表。
import django

# 提前初始化 Django，确保后续 Channels 路由导入可访问模型与配置。
django.setup()

# 导入 Channels 协议分发器与 URL 路由器。
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import (
    AllowedHostsOriginValidator,
)

# 导入 Django ASGI 应用工厂。
from django.core.asgi import get_asgi_application

# 导入 WebSocket 路由
# 导入 UI 自动化模块的 WebSocket 路由清单。
from ui_automation.routing import websocket_urlpatterns as ui_ws_patterns

# 导入 UI 自动化 WebSocket 认证中间件（JWT / 执行器共享密钥）。
from wharttest_django.websocket_auth import UiWebSocketAuthMiddleware

# 创建 Django HTTP ASGI 应用实例。
django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter(
    {
        # HTTP 请求使用 Django ASGI 处理
        # 将 HTTP 请求交给 Django 标准 ASGI 应用处理。
        "http": django_asgi_app,
        # WebSocket 请求使用 Channels 处理
        # 对 WebSocket 连接启用认证与主机来源校验。
        "websocket": AllowedHostsOriginValidator(
            UiWebSocketAuthMiddleware(
                # 使用 UI 自动化路由表匹配并分发 WebSocket 连接。
                URLRouter(ui_ws_patterns)
            )
        ),
    }
)
