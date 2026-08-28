
"""Orchestrator相关接口"""
import logging
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import OrchestratorTask
from .serializers import OrchestratorTaskSerializer

logger = logging.getLogger(__name__)


class OrchestratorTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """只读视图 - 用于查看历史任务记录"""
    permission_classes = [IsAuthenticated]
    queryset = OrchestratorTask.objects.all()
    serializer_class = OrchestratorTaskSerializer

    def get_queryset(self):
        """只返回当前用户的任务"""
        return OrchestratorTask.objects.filter(user=self.request.user)
