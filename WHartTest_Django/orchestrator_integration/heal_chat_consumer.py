"""自愈对话实时推送 WebSocket 消费者。

前端通过 /ws/heal/chat/?token=<JWT>&session_id=<自愈会话ID> 订阅指定自愈会话；
Celery worker 消费 agent-loop SSE 时把每个事件转发到通道层 group
``heal_chat.{session_id}``，本消费者收到后推给浏览器实现打字机实时渲染。

认证由 UiWebSocketAuthMiddleware 完成（JWT，同 /ws/ui/web/）。
事件只读不落库——落库仍由自愈任务的批量同步负责。
"""
import json
import logging

from channels.generic.websocket import AsyncJsonWebsocketConsumer

logger = logging.getLogger(__name__)


class HealChatConsumer(AsyncJsonWebsocketConsumer):
    """订阅单个自愈会话的事件流。"""

    async def connect(self):
        from wharttest_django.websocket_auth import SCOPE_AUTH_KEY

        auth_info = self.scope.get(SCOPE_AUTH_KEY) or {}
        if not auth_info.get('authenticated'):
            await self.close(code=4401)
            return

        from urllib.parse import parse_qs

        query = parse_qs(self.scope.get('query_string', b'').decode('utf-8'))
        session_id = (query.get('session_id') or [''])[0]
        if not session_id:
            await self.close(code=4400)
            return

        self.session_id = session_id
        self.group_name = f"heal_chat.{session_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({
            'type': 'subscribed',
            'session_id': session_id,
        })

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        # 单向推送通道：不处理客户端上行消息（保留 ping 以便客户端保活探测）
        if content.get('type') == 'ping':
            await self.send_json({'type': 'pong'})

    async def heal_event(self, event):
        """通道层事件处理：把自愈事件原样推给浏览器。"""
        payload = event.get('payload') or {}
        try:
            await self.send(text_data=json.dumps({'type': 'heal_event', 'event': payload}))
        except Exception:
            # 客户端已断开等发送失败：忽略，group_discard 在 disconnect 兜底
            pass
