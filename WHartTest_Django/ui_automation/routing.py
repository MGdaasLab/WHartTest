"""
UI自动化 WebSocket 路由配置
"""

from django.urls import re_path
from . import consumers
from orchestrator_integration.heal_chat_consumer import HealChatConsumer

websocket_urlpatterns = [
    # 前端WebSocket连接
    re_path(r'ws/ui/web/$', consumers.UiAutomationConsumer.as_asgi()),
    # 执行器WebSocket连接
    re_path(r'ws/ui/actuator/$', consumers.UiAutomationConsumer.as_asgi()),
    # 自愈对话实时推送（JWT 认证，按 session_id 订阅）
    re_path(r'ws/heal/chat/$', HealChatConsumer.as_asgi()),
]
