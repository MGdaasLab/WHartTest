import logging
from datetime import timedelta
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from projects.models import Project
from .models import ScheduledTask, TaskExecution
from .serializers import ScheduledTaskSerializer, TaskExecutionSerializer
from .scheduler import register_periodic_task, unregister_periodic_task

logger = logging.getLogger(__name__)


class ScheduledTaskViewSet(viewsets.ModelViewSet):
    """定时任务视图集"""
    serializer_class = ScheduledTaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['name']
    filterset_fields = ['status', 'module']

    def get_queryset(self):
        project_pk = self.kwargs.get('project_pk')
        if project_pk:
            return ScheduledTask.objects.filter(project_id=project_pk)
        return ScheduledTask.objects.none()

    def perform_create(self, serializer):
        project_pk = self.kwargs.get('project_pk')
        project = get_object_or_404(Project, pk=project_pk)
        instance = serializer.save(
            project=project,
            creator=self.request.user,
            status=ScheduledTask.TaskStatus.RUNNING,
        )
        register_periodic_task(instance)

    def perform_update(self, serializer):
        instance = serializer.save()
        if instance.status == ScheduledTask.TaskStatus.RUNNING:
            register_periodic_task(instance)

    def perform_destroy(self, instance):
        if instance.status == ScheduledTask.TaskStatus.RUNNING:
            unregister_periodic_task(instance)
        instance.delete()

    @action(detail=True, methods=['post'], url_path='enable')
    def enable(self, request, **kwargs):
        """启用任务 → 运行中"""
        task = self.get_object()
        if task.status != ScheduledTask.TaskStatus.DISABLED:
            return Response({'error': '只有未启用的任务可以开启'}, status=status.HTTP_400_BAD_REQUEST)

        task.status = ScheduledTask.TaskStatus.RUNNING
        task.save(update_fields=['status'])
        register_periodic_task(task)
        return Response(ScheduledTaskSerializer(task).data)

    @action(detail=True, methods=['post'], url_path='disable')
    def disable(self, request, **kwargs):
        """关闭任务 → 未启用"""
        task = self.get_object()
        if task.status != ScheduledTask.TaskStatus.RUNNING:
            return Response({'error': '只有运行中的任务可以关闭'}, status=status.HTTP_400_BAD_REQUEST)

        unregister_periodic_task(task)
        task.status = ScheduledTask.TaskStatus.DISABLED
        task.save(update_fields=['status'])
        return Response(ScheduledTaskSerializer(task).data)

    @action(detail=True, methods=['post'], url_path='run-now')
    def run_now(self, request, **kwargs):
        """立即执行（手动触发，不影响原调度计划）"""
        task = self.get_object()

        from .tasks import execute_scheduled_task
        result = execute_scheduled_task.apply_async(args=[task.id, 'manual'])

        return Response({
            'message': '任务已提交执行',
            'celery_task_id': result.id,
        })

    @action(detail=True, methods=['get'], url_path='executions')
    def executions(self, request, **kwargs):
        """获取任务的执行记录"""
        task = self.get_object()
        # 默认只返回最近一个月的记录
        one_month_ago = timezone.now() - timedelta(days=30)
        queryset = task.executions.filter(started_at__gte=one_month_ago)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = TaskExecutionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = TaskExecutionSerializer(queryset, many=True)
        return Response(serializer.data)


class TaskExecutionViewSet(viewsets.ReadOnlyModelViewSet):
    """执行记录视图集（只读）"""
    serializer_class = TaskExecutionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        project_pk = self.kwargs.get('project_pk')
        if project_pk:
            return TaskExecution.objects.filter(task__project_id=project_pk)
        return TaskExecution.objects.none()

    @action(detail=True, methods=['get'], url_path='log')
    def get_log(self, request, **kwargs):
        """获取执行日志详情"""
        execution = self.get_object()
        return Response({
            'execution_id': execution.execution_id,
            'log': execution.log,
            'error_message': execution.error_message,
            'status': execution.status,
            'duration': execution.duration_display,
        })

    @action(detail=True, methods=['delete'], url_path='remove')
    def remove(self, request, **kwargs):
        """删除执行记录"""
        execution = self.get_object()
        execution.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
