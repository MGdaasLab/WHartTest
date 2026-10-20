"""
Celery 任务定义 - 定时任务执行入口
"""
import logging
from celery import shared_task
from django.utils import timezone

# 显式导入自愈任务模块：celery autodiscover 只加载各 app 的 tasks.py，
# heal_tasks.py 中的 @shared_task 需要随本模块导入才会注册到 worker
from . import heal_tasks  # noqa: F401

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

            # 使用任务创建者身份获取 token。必须携带当前 session_version：
            # SingleDeviceJWTAuthentication 会校验 token 与用户最新会话版本，
            # RefreshToken.for_user 默认不写入该声明（按 0 处理），
            # 创建者只要登录过就会被判为旧会话而 401。
            from accounts.models import UserLoginState

            token = RefreshToken.for_user(task.creator).access_token
            state, _ = UserLoginState.objects.get_or_create(user=task.creator)
            token["session_version"] = state.session_version
            token = str(token)
            resp = requests.post(
                f"{django_settings.BASE_URL}/api/ui-automation/trigger-batch/",
                json={
                    'case_ids': ui_case_ids,
                    'actuator_id': task.actuator_id,
                    'batch_name': f"定时任务-{task.name}",
                    'trigger_type': 'scheduled',
                    'scheduled_task_id': task.id,
                    'executor_id': task.creator.id,
                },
                headers={'Authorization': f'Bearer {token}'},
                timeout=30,
            )
            if resp.status_code >= 400:
                error_msg = resp.json().get('error', resp.text)
                raise ValueError(f"触发批量执行失败: {error_msg}")

            # UnifiedResponseRenderer 会把视图返回体包装为 {status, code, message, data: <视图返回体>}，
            # 因此取 batch_id 需要两层 data：外层 data = 视图的 {'status','data':{batch_id,...}}
            resp_body = resp.json()
            batch_data = resp_body.get('data') or {}
            if isinstance(batch_data.get('data'), dict):
                batch_data = batch_data['data']
            batch_id = batch_data.get('batch_id')
            log_lines.append(f"[{timezone.now().isoformat()}] 批量执行已触发: batch_id={batch_id}")

            if not batch_id:
                raise ValueError("触发批量执行未返回批次 ID")

            # 先持久化批次关联再进入后续流程：批次若秒级完结（执行器极快/单用例秒失败），
            # consumers 回写按 batch_record_id 过滤时关联必须已落库，否则执行记录永久停在 running
            execution.batch_record_id = batch_id
            execution.save(update_fields=['batch_record'])

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
                scheduled_task=task,
            )
            # 先持久化套件执行关联再入队：套件 worker 可能先于本任务后续 save() 完成
            # （空套件/秒失败），回写按 suite_execution_id 过滤时关联必须已落库，
            # 否则执行记录永久停在 running
            execution.suite_execution = suite_execution
            execution.save(update_fields=['suite_execution'])
            run_suite.delay(suite_execution.id)
            log_lines.append(f"[{timezone.now().isoformat()}] 套件执行已提交: execution_id={suite_execution.id}")

        log_lines.append(f"[{timezone.now().isoformat()}] 任务执行完成")

        ui_pending_result = (
            task.module == ScheduledTask.TaskModule.UI_AUTOMATION and bool(batch_id)
        )
        suite_pending_result = (
            task.module == ScheduledTask.TaskModule.TEST_SUITE
            and suite_execution.status == 'pending'
        )
        if ui_pending_result or suite_pending_result:
            # 触发成功但测试结果未出：执行记录保持 running，由下游完结处回写成败
            # （UI → consumers 批次完结回写；套件 → execute_test_suite 完结回写）
            execution.log = '\n'.join(log_lines)
            execution.save()
        else:
            # 异常兜底（UI 未取到批次 ID 等）：无法回写测试结果，按触发结果落成功
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
