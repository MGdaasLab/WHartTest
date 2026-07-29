"""URL路由配置"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrchestratorTaskViewSet
from .agent_loop_view import AgentLoopStreamAPIView, AgentLoopStopAPIView, AgentLoopResumeAPIView

router = DefaultRouter()
router.register(r'tasks', OrchestratorTaskViewSet, basename='orchestrator-task')

urlpatterns = [
    path('', include(router.urls)),
    # Agent Loop 流式对话接口 - 解决 Token 累积问题
    path('agent-loop/', AgentLoopStreamAPIView.as_view(), name='agent-loop-stream'),
    # Agent Loop 停止接口 - 中断正在执行的任务
    path('agent-loop/stop/', AgentLoopStopAPIView.as_view(), name='agent-loop-stop'),
    # Agent Loop 恢复接口 - HITL 审批后继续执行
    path('agent-loop/resume/', AgentLoopResumeAPIView.as_view(), name='agent-loop-resume'),
]
