"""Agent Loop SSE 流事件 → Channels 通道层桥接。

供后端程序化消费 agent-loop SSE 的场景（定时自愈、测试套件执行）把事件
实时转发给对话页 WS 订阅（打字机效果）。best-effort：通道层不可用时
静默跳过，消费方退化为各自的兜底展示。

调用上下文自适应：
- 异步上下文（套件执行的 async 消费循环）：await publish_stream_event_async；
- 同步上下文（自愈 Celery 任务）：publish_stream_event 内部用 async_to_sync
  复用线程局部事件循环（channels_redis 按事件循环缓存连接池，避免每事件
  新建连接池）。注意 async_to_sync 不能在运行中的事件循环内调用。
"""
import asyncio
import json
import logging
import os
import time

logger = logging.getLogger(__name__)

_GROUP_PREFIX = "heal_chat."


def _get_channel_layer():
    from channels.layers import get_channel_layer

    return get_channel_layer()


def _touch_active_session(session_id: str) -> None:
    """维护「活跃任务会话」Redis 标记（前端 task-session 接口查询）。best-effort。"""
    try:
        import redis as _redis
        from django.conf import settings as _settings

        url = (
            os.environ.get("UI_AUTOMATION_REDIS_URL")
            or getattr(_settings, "UI_AUTOMATION_REDIS_URL", None)
            or getattr(_settings, "CELERY_BROKER_URL", None)
            or "redis://localhost:8911/0"
        )
        client = _redis.from_url(url, socket_connect_timeout=0.5, socket_timeout=0.5)
        client.setex(f"task_session_active:{session_id}", 7200, json.dumps({"ts": time.time()}))
    except Exception:
        pass


def publish_stream_event(session_id: str, payload: dict) -> None:
    """同步上下文入口（自愈 Celery 任务）。"""
    try:
        from asgiref.sync import async_to_sync

        channel_layer = _get_channel_layer()
        if channel_layer is None:
            return
        _touch_active_session(session_id)
        async_to_sync(channel_layer.group_send)(
            f"{_GROUP_PREFIX}{session_id}",
            {"type": "heal.event", "payload": payload},
        )
    except Exception:
        logger.debug("[stream-bridge] 流事件转发通道层失败（前端将走轮询兜底）", exc_info=True)


async def publish_stream_event_async(session_id: str, payload: dict) -> None:
    """异步上下文入口（套件执行的 async 消费循环）：直接 await，异常静默。"""
    try:
        channel_layer = _get_channel_layer()
        if channel_layer is None:
            return
        await asyncio.to_thread(_touch_active_session, session_id)
        await channel_layer.group_send(
            f"{_GROUP_PREFIX}{session_id}",
            {"type": "heal.event", "payload": payload},
        )
    except Exception:
        logger.debug("[stream-bridge] 协程内流事件发送失败", exc_info=True)
