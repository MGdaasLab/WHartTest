"""
Celery 任务定义 - 定时任务执行入口
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='task_center.tasks.execute_scheduled_task')
def execute_scheduled_task(self, task_id: int, trigger_type: str = 'scheduled'):
    """执行定时任务的 Celery 入口"""
    from .models import ScheduledTask, TaskExecution

    try:
        task = ScheduledTask.objects.get(id=task_id)
    except ScheduledTask.DoesNotExist:
        logger.error(f"任务 ID={task_id} 不存在")
        return {'status': 'error', 'message': f'任务 {task_id} 不存在'}

    # 一次性任务若已被禁用且非手动触发，跳过执行
    if task.status == ScheduledTask.TaskStatus.DISABLED and trigger_type == 'scheduled':
        logger.info(f"任务 [{task.name}] 已禁用，跳过定时执行")
        return {'status': 'skipped', 'message': '任务已禁用'}

    # 创建执行记录
    execution = TaskExecution.objects.create(
        task=task,
        trigger_type=trigger_type,
        status=TaskExecution.ExecutionStatus.RUNNING,
        celery_task_id=self.request.id or '',
    )

    task.last_run_at = timezone.now()
    task.save(update_fields=['last_run_at'])

    log_lines = []
    try:
        log_lines.append(f"[{timezone.now().isoformat()}] 开始执行任务: {task.name}")
        log_lines.append(f"[{timezone.now().isoformat()}] 模块: {task.get_module_display()}")
        log_lines.append(f"[{timezone.now().isoformat()}] 执行目标: {task.get_execution_target_display()}")

        # 根据模块类型执行不同逻辑
        if task.module == ScheduledTask.TaskModule.UI_AUTOMATION:
            log_lines.append(f"[{timezone.now().isoformat()}] 触发 UI 自动化执行...")
            ui_case_ids = list(task.ui_testcases.values_list('id', flat=True))
            if not ui_case_ids:
                raise ValueError("未关联任何 UI 自动化用例")
            log_lines.append(f"[{timezone.now().isoformat()}] 关联用例数: {len(ui_case_ids)}")

            # 通过内部 API 触发批量执行（API 会创建记录并通过 WebSocket 通知执行器）
            import requests
            from rest_framework_simplejwt.tokens import RefreshToken
            from django.conf import settings as django_settings

            # 使用任务创建者身份获取 token
            token = str(RefreshToken.for_user(task.creator).access_token)
            resp = requests.post(
                f"{django_settings.BASE_URL}/api/ui-automation/trigger-batch/",
                json={
                    'case_ids': ui_case_ids,
                    'actuator_id': task.actuator_id,
                    'batch_name': f"定时任务-{task.name}",
                    'trigger_type': 'scheduled',
                },
                headers={'Authorization': f'Bearer {token}'},
                timeout=30,
            )
            if resp.status_code >= 400:
                error_msg = resp.json().get('error', resp.text)
                raise ValueError(f"触发批量执行失败: {error_msg}")

            batch_data = resp.json().get('data', {})
            log_lines.append(f"[{timezone.now().isoformat()}] 批量执行已触发: batch_id={batch_data.get('batch_id')}")

        elif task.module == ScheduledTask.TaskModule.TEST_SUITE:
            log_lines.append(f"[{timezone.now().isoformat()}] 触发测试套件执行...")
            if not task.test_suite:
                raise ValueError("未关联测试套件")
            log_lines.append(f"[{timezone.now().isoformat()}] 套件: {task.test_suite.name}")
            # 创建执行记录并启动 Celery 任务
            from testcases.models import TestExecution
            from testcases.tasks import execute_test_suite as run_suite
            suite_execution = TestExecution.objects.create(
                suite=task.test_suite,
                executor=task.creator,
                status='pending',
            )
            run_suite.delay(suite_execution.id)
            log_lines.append(f"[{timezone.now().isoformat()}] 套件执行已提交: execution_id={suite_execution.id}")

        log_lines.append(f"[{timezone.now().isoformat()}] 任务执行完成")

        execution.status = TaskExecution.ExecutionStatus.SUCCESS
        execution.finished_at = timezone.now()
        execution.log = '\n'.join(log_lines)
        execution.save()

        # 一次性任务执行后自动禁用
        if task.schedule_type == ScheduledTask.ScheduleType.ONCE:
            task.status = ScheduledTask.TaskStatus.DISABLED
            task.save(update_fields=['status'])

        return {'status': 'success', 'execution_id': execution.execution_id}

    except Exception as e:
        logger.exception(f"任务 [{task.name}] 执行失败")
        log_lines.append(f"[{timezone.now().isoformat()}] 执行失败: {str(e)}")

        execution.status = TaskExecution.ExecutionStatus.FAILED
        execution.finished_at = timezone.now()
        execution.log = '\n'.join(log_lines)
        execution.error_message = str(e)
        execution.save()

        # 一次性任务失败后自动禁用
        if task.schedule_type == ScheduledTask.ScheduleType.ONCE:
            task.status = ScheduledTask.TaskStatus.DISABLED
            task.save(update_fields=['status'])

        # 重试逻辑
        if task.retry_enabled and self.request.retries < task.retry_count:
            raise self.retry(
                exc=e,
                countdown=task.retry_interval * 60,
                max_retries=task.retry_count,
            )

        return {'status': 'failed', 'execution_id': execution.execution_id, 'error': str(e)}
