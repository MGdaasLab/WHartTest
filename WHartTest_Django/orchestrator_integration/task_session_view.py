"""任务会话查询接口：前端判断当前会话是否为外部任务会话（套件执行/自愈）
以及是否仍有实时事件在推送，据此决定是否建立打字机 WS 订阅与轮询兜底。
"""
import json
import logging
import os

from django.conf import settings
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class TaskSessionAPIView(APIView):
    """GET /api/orchestrator/agent-loop/task-session/?session_id=xxx

    返回：
    - is_task_session: 会话是否为外部任务会话（module_key=testcase_execution）
    - active: Redis 活跃标记是否仍在（流事件最近 2 小时内有过推送）
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        session_id = request.query_params.get("session_id")
        if not session_id:
            return Response(
                {"status": "error", "code": 400, "message": "session_id is required", "data": None, "errors": None},
                status=400,
            )

        # CE 无槽位绑定机制（ChatSession.resolved_module_key 不存在）。
        # 任务会话判定改为：Redis 活跃标记是否存在——该标记仅由自愈/套件执行的
        # 流桥接写入（stream_bridge），天然限定外部任务场景。
        import redis

        url = (
            os.environ.get("UI_AUTOMATION_REDIS_URL")
            or getattr(settings, "UI_AUTOMATION_REDIS_URL", None)
            or getattr(settings, "CELERY_BROKER_URL", None)
            or "redis://localhost:8911/0"
        )
        is_task_session = False
        active = False
        try:
            client = redis.from_url(url, socket_connect_timeout=0.5, socket_timeout=0.5)
            raw = client.get(f"task_session_active:{session_id}")
            if raw:
                json.loads(raw)
                is_task_session = True
                active = True
        except Exception:
            logger.debug("[task-session] 活跃标记查询失败", exc_info=True)

        return Response({
            "status": "success",
            "code": 200,
            "message": "ok",
            "data": {"session_id": session_id, "is_task_session": is_task_session, "active": active},
            "errors": None,
        })
