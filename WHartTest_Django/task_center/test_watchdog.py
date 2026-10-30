"""执行记录 running 看门狗与批次关联精确回填单元测试。"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from projects.models import Project
from task_center.models import ScheduledTask, TaskExecution
from task_center.watchdog import watchdog_stale_executions
from ui_automation.models import UiBatchExecutionRecord, UiModule, UiTestCase


class WatchdogTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='wduser', password='pwd', email='w@t.com')
        self.project = Project.objects.create(name='WatchdogProject', creator=self.user)
        self.ui_module = UiModule.objects.create(project=self.project, name='模块', creator=self.user)
        self.task = ScheduledTask.objects.create(
            name='看门狗任务', project=self.project,
            module=ScheduledTask.TaskModule.UI_AUTOMATION,
            schedule_type=ScheduledTask.ScheduleType.DAILY, daily_time='08:00',
            creator=self.user,
        )

    def _stale_execution(self, **kwargs):
        execution = TaskExecution.objects.create(
            task=self.task,
            trigger_type=TaskExecution.TriggerType.SCHEDULED,
            status=TaskExecution.ExecutionStatus.RUNNING,
            **kwargs,
        )
        # 手动把 started_at 拨到超时线之前
        TaskExecution.objects.filter(id=execution.id).update(
            started_at=timezone.now() - timedelta(seconds=5 * 60 * 60)
        )
        return TaskExecution.objects.get(id=execution.id)

    def test_stale_batch_execution_recovered_from_completed_batch(self):
        batch = UiBatchExecutionRecord.objects.create(
            name='批次', total_cases=2, status=3, trigger_type='scheduled',
            scheduled_task=self.task, start_time=timezone.now(),
        )
        execution = self._stale_execution(batch_record=batch)

        watchdog_stale_executions()

        execution.refresh_from_db()
        self.assertEqual(execution.status, TaskExecution.ExecutionStatus.FAILED)
        self.assertEqual(execution.test_status, TaskExecution.ExecutionStatus.FAILED)
        self.assertIsNotNone(execution.finished_at)
        self.assertIn('看门狗', execution.error_message)

    def test_stuck_batch_finalized_as_failed(self):
        batch = UiBatchExecutionRecord.objects.create(
            name='卡死批次', total_cases=1, status=1, trigger_type='scheduled',
            scheduled_task=self.task, start_time=timezone.now() - timedelta(hours=5),
        )
        execution = self._stale_execution(batch_record=batch)

        watchdog_stale_executions()

        batch.refresh_from_db()
        execution.refresh_from_db()
        self.assertEqual(batch.status, 4)  # 全部失败
        self.assertEqual(execution.status, TaskExecution.ExecutionStatus.FAILED)

    def test_orphan_execution_marked_failed(self):
        execution = self._stale_execution()  # 无任何关联

        watchdog_stale_executions()

        execution.refresh_from_db()
        self.assertEqual(execution.status, TaskExecution.ExecutionStatus.FAILED)

    def test_fresh_running_execution_untouched(self):
        batch = UiBatchExecutionRecord.objects.create(
            name='新批次', total_cases=1, status=1, trigger_type='scheduled',
            scheduled_task=self.task, start_time=timezone.now(),
        )
        execution = TaskExecution.objects.create(
            task=self.task,
            trigger_type=TaskExecution.TriggerType.SCHEDULED,
            status=TaskExecution.ExecutionStatus.RUNNING,
            batch_record=batch,
        )  # 刚创建，未超时

        watchdog_stale_executions()

        execution.refresh_from_db()
        batch.refresh_from_db()
        self.assertEqual(execution.status, TaskExecution.ExecutionStatus.RUNNING)
        self.assertEqual(batch.status, 1)

    def test_healthy_completed_batch_syncs_success(self):
        batch = UiBatchExecutionRecord.objects.create(
            name='已完成批次', total_cases=2, status=2, trigger_type='scheduled',
            scheduled_task=self.task, start_time=timezone.now(),
        )
        execution = self._stale_execution(batch_record=batch)

        watchdog_stale_executions()

        execution.refresh_from_db()
        self.assertEqual(execution.status, TaskExecution.ExecutionStatus.SUCCESS)


class ExecutionIdBackfillTests(TestCase):
    """trigger-batch 精确回填：execution_id 优先于启发式匹配。"""

    def setUp(self):
        self.user = User.objects.create_superuser(username='bfuser', password='pwd', email='b@t.com')
        self.project = Project.objects.create(name='BackfillProject', creator=self.user)
        self.task = ScheduledTask.objects.create(
            name='回填任务', project=self.project,
            module=ScheduledTask.TaskModule.UI_AUTOMATION,
            schedule_type=ScheduledTask.ScheduleType.DAILY, daily_time='08:00',
            creator=self.user,
        )

    def test_explicit_execution_id_wins_over_heuristic(self):
        from ui_automation.views import _resolve_task_execution_for_batch

        # 两条 running 记录：旧的一条（启发式会选它）与显式指定的新的一条
        older = TaskExecution.objects.create(
            task=self.task, trigger_type=TaskExecution.TriggerType.SCHEDULED,
            status=TaskExecution.ExecutionStatus.RUNNING,
        )
        TaskExecution.objects.filter(id=older.id).update(started_at=timezone.now() - timedelta(minutes=5))
        newer = TaskExecution.objects.create(
            task=self.task, trigger_type=TaskExecution.TriggerType.MANUAL,
            status=TaskExecution.ExecutionStatus.RUNNING,
        )

        resolved = _resolve_task_execution_for_batch(
            task_execution_id=newer.id, scheduled_task_id=self.task.id,
        )
        self.assertEqual(resolved.id, newer.id)

    def test_falls_back_to_heuristic_without_execution_id(self):
        from ui_automation.views import _resolve_task_execution_for_batch

        older = TaskExecution.objects.create(
            task=self.task, trigger_type=TaskExecution.TriggerType.SCHEDULED,
            status=TaskExecution.ExecutionStatus.RUNNING,
        )
        TaskExecution.objects.filter(id=older.id).update(started_at=timezone.now() - timedelta(minutes=5))
        newer = TaskExecution.objects.create(
            task=self.task, trigger_type=TaskExecution.TriggerType.MANUAL,
            status=TaskExecution.ExecutionStatus.RUNNING,
        )

        resolved = _resolve_task_execution_for_batch(
            task_execution_id=None, scheduled_task_id=self.task.id,
        )
        self.assertEqual(resolved.id, older.id)  # 启发式取最早的一条（先触发先关联）

    def test_skips_finished_execution_for_explicit_id(self):
        from ui_automation.views import _resolve_task_execution_for_batch

        finished = TaskExecution.objects.create(
            task=self.task, trigger_type=TaskExecution.TriggerType.SCHEDULED,
            status=TaskExecution.ExecutionStatus.SUCCESS,
        )
        resolved = _resolve_task_execution_for_batch(
            task_execution_id=finished.id, scheduled_task_id=self.task.id,
        )
        self.assertIsNone(resolved)
