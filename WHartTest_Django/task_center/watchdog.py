"""
执行记录 running 看门狗：兜底清理因执行器中途断开 / worker 崩溃而永久停在
running 的任务中心执行记录与 UI 批次。

正常链路由完结处回写（UI → consumers 批次完结；套件 → execute_test_suite 完结），
本巡检只处理"下游永远没有回写"的孤儿记录，避免误伤仍在正常执行的长时间任务：
- TaskExecution：running 超时（默认 2 小时）且已关联批次/套件执行——若关联对象
  已完结则按其结果补回写；未关联（触发端回填失败）直接按超时失败处理。
- UiBatchExecutionRecord：执行中(status=1)超过 2 小时按全部失败收尾。
"""
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

# running 视为孤儿的超时：远大于正常 UI 用例/套件执行时长（timeout 上限 6 小时下发 TTL，
# 但批次的正常完成判定以回写为准；此处取 4 小时兜底，宁迟勿误杀）
RUNNING_STALE_SECONDS = 4 * 60 * 60


@shared_task(name="task_center.watchdog_stale_executions")
def watchdog_stale_executions() -> dict:
    """周期巡检：清理永久 running 的执行记录与批次（Celery beat 每小时）。"""
    from datetime import timedelta

    from .models import TaskExecution

    now = timezone.now()
    stale_before = now - timedelta(seconds=RUNNING_STALE_SECONDS)
    fixed = {"task_executions": 0, "batches": 0}

    # 1. 关联了 UI 批次的执行记录：批次已完结 → 按批次结果补回写；批次自身卡死 → 一并收尾
    stale_batch_executions = TaskExecution.objects.filter(
        status=TaskExecution.ExecutionStatus.RUNNING,
        started_at__lt=stale_before,
        batch_record__isnull=False,
    ).select_related("batch_record")
    for execution in stale_batch_executions:
        batch = execution.batch_record
        if batch.status == 1:  # 批次仍执行中且超时 → 按全部失败收尾
            batch.status = 4
            batch.end_time = now
            if batch.start_time:
                batch.duration = (batch.end_time - batch.start_time).total_seconds()
            batch.save(update_fields=["status", "end_time", "duration"])
            fixed["batches"] += 1
            logger.warning(f"[看门狗] 批次 {batch.id} 执行中超时，已按全部失败收尾")
        result_status = (
            TaskExecution.ExecutionStatus.SUCCESS if batch.status == 2
            else TaskExecution.ExecutionStatus.FAILED
        )
        execution.status = result_status
        execution.test_status = result_status
        execution.finished_at = now
        execution.error_message = (
            f"{execution.error_message or ''}"
            f"[看门狗] 批次 {batch.id} 未在时限内回写结果，已按 {result_status} 兜底"
        ).strip()
        execution.save(update_fields=["status", "test_status", "finished_at", "error_message"])
        fixed["task_executions"] += 1
        logger.warning(f"[看门狗] 执行记录 {execution.execution_id} 超时兜底: {result_status}")

    # 2. 关联了套件执行的执行记录：套件已完结 → 按套件结果补回写（复用既有归一逻辑）
    stale_suite_executions = TaskExecution.objects.filter(
        status=TaskExecution.ExecutionStatus.RUNNING,
        started_at__lt=stale_before,
        suite_execution__isnull=False,
    ).select_related("suite_execution")
    for execution in stale_suite_executions:
        suite_exec = execution.suite_execution
        if suite_exec.status in ("pending", "running"):
            # 套件执行自身也卡死 → 套件记录置 failed，再走归一回写
            suite_exec.status = "failed"
            suite_exec.completed_at = now
            suite_exec.save(update_fields=["status", "completed_at", "updated_at"])
        from testcases.tasks import sync_scheduled_task_result

        sync_scheduled_task_result(suite_exec)
        execution.refresh_from_db()
        if execution.status == TaskExecution.ExecutionStatus.RUNNING:
            # sync 未覆盖（如 cancelled）：直接按失败兜底
            execution.status = TaskExecution.ExecutionStatus.FAILED
            execution.test_status = TaskExecution.ExecutionStatus.FAILED
            execution.finished_at = now
            execution.save(update_fields=["status", "test_status", "finished_at"])
        fixed["task_executions"] += 1
        logger.warning(f"[看门狗] 套件执行记录 {execution.execution_id} 超时兜底完成")

    # 3. 未关联任何下游的 running 执行记录（触发端回填失败的孤儿）：直接失败
    orphans = TaskExecution.objects.filter(
        status=TaskExecution.ExecutionStatus.RUNNING,
        started_at__lt=stale_before,
        batch_record__isnull=True,
        suite_execution__isnull=True,
    )
    for execution in orphans:
        execution.status = TaskExecution.ExecutionStatus.FAILED
        execution.test_status = TaskExecution.ExecutionStatus.FAILED
        execution.finished_at = now
        execution.error_message = (
            f"{execution.error_message or ''}"
            f"[看门狗] 执行记录超时且无下游关联，按失败兜底"
        ).strip()
        execution.save(update_fields=["status", "test_status", "finished_at", "error_message"])
        fixed["task_executions"] += 1
        logger.warning(f"[看门狗] 孤儿执行记录 {execution.execution_id} 按失败兜底")

    if fixed["task_executions"] or fixed["batches"]:
        logger.info(f"[看门狗] 本轮清理: {fixed}")
    return fixed
