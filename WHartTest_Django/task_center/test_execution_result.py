"""任务中心执行记录归一结果回写单元测试。

覆盖：
1. UI 链路：批次完结（全部成功/部分失败/全部失败）→ 执行记录归一 success/failed；
2. 套件链路：套件执行完结（completed 无失败 / completed 有失败 / failed）→ 执行记录归一；
3. 防重与边界：running 才回写、无关联不处理、cancelled 不回写。
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from projects.models import Project
from task_center.models import ScheduledTask, TaskExecution
from testcases.tasks import sync_scheduled_task_result
from ui_automation.consumers import UiAutomationConsumer
from ui_automation.models import UiBatchExecutionRecord
from testcases.models import TestExecution, TestSuite


class ExecutionResultTestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='resultuser', password='pwd', email='r@t.com')
        self.project = Project.objects.create(name='ResultProject', creator=self.user)
        self.task = ScheduledTask.objects.create(
            name='归一结果任务', project=self.project,
            module=ScheduledTask.TaskModule.UI_AUTOMATION,
            schedule_type=ScheduledTask.ScheduleType.DAILY, daily_time='08:00',
            creator=self.user,
        )

    def _execution(self, status=TaskExecution.ExecutionStatus.RUNNING, **kwargs):
        return TaskExecution.objects.create(
            task=self.task, trigger_type=TaskExecution.TriggerType.SCHEDULED,
            status=status, **kwargs,
        )


class UiBatchResultSyncTests(ExecutionResultTestBase):
    def _batch(self, status, with_task=True):
        return UiBatchExecutionRecord.objects.create(
            name='批次', total_cases=2, status=status,
            trigger_type='scheduled',
            scheduled_task=self.task if with_task else None,
        )

    def test_all_success_batch_marks_execution_success(self):
        batch = self._batch(status=2)
        execution = self._execution(batch_record=batch)
        UiAutomationConsumer()._sync_task_execution_result(batch)
        execution.refresh_from_db()
        self.assertEqual(execution.status, TaskExecution.ExecutionStatus.SUCCESS)
        self.assertEqual(execution.test_status, TaskExecution.ExecutionStatus.SUCCESS)
        self.assertIsNotNone(execution.finished_at)

    def test_partial_failure_batch_marks_execution_failed(self):
        batch = self._batch(status=3)
        execution = self._execution(batch_record=batch)
        UiAutomationConsumer()._sync_task_execution_result(batch)
        execution.refresh_from_db()
        self.assertEqual(execution.status, TaskExecution.ExecutionStatus.FAILED)
        self.assertEqual(execution.test_status, TaskExecution.ExecutionStatus.FAILED)

    def test_all_failed_batch_marks_execution_failed(self):
        batch = self._batch(status=4)
        execution = self._execution(batch_record=batch)
        UiAutomationConsumer()._sync_task_execution_result(batch)
        execution.refresh_from_db()
        self.assertEqual(execution.status, TaskExecution.ExecutionStatus.FAILED)

    def test_does_not_overwrite_finished_execution(self):
        batch = self._batch(status=3)
        execution = self._execution(status=TaskExecution.ExecutionStatus.SUCCESS, batch_record=batch)
        UiAutomationConsumer()._sync_task_execution_result(batch)
        execution.refresh_from_db()
        self.assertEqual(execution.status, TaskExecution.ExecutionStatus.SUCCESS)

    def test_unlinked_batch_ignored(self):
        batch = self._batch(status=3, with_task=False)
        execution = self._execution()
        UiAutomationConsumer()._sync_task_execution_result(batch)
        execution.refresh_from_db()
        self.assertEqual(execution.status, TaskExecution.ExecutionStatus.RUNNING)


class SuiteResultSyncTests(ExecutionResultTestBase):
    def setUp(self):
        super().setUp()
        self.suite = TestSuite.objects.create(
            name='套件', project=self.project, creator=self.user,
        )

    def test_completed_without_failure_marks_success(self):
        suite_exec = TestExecution.objects.create(
            suite=self.suite, executor=self.user, status='completed',
            total_count=2, failed_count=0, completed_at=timezone.now(),
            scheduled_task=self.task,
        )
        execution = self._execution(suite_execution=suite_exec)
        sync_scheduled_task_result(suite_exec)
        execution.refresh_from_db()
        self.assertEqual(execution.status, TaskExecution.ExecutionStatus.SUCCESS)
        self.assertEqual(execution.test_status, TaskExecution.ExecutionStatus.SUCCESS)

    def test_completed_with_failure_marks_failed(self):
        suite_exec = TestExecution.objects.create(
            suite=self.suite, executor=self.user, status='completed',
            total_count=2, failed_count=1, completed_at=timezone.now(),
            scheduled_task=self.task,
        )
        execution = self._execution(suite_execution=suite_exec)
        sync_scheduled_task_result(suite_exec)
        execution.refresh_from_db()
        self.assertEqual(execution.status, TaskExecution.ExecutionStatus.FAILED)
        self.assertEqual(execution.test_status, TaskExecution.ExecutionStatus.FAILED)

    def test_suite_failed_marks_execution_failed(self):
        suite_exec = TestExecution.objects.create(
            suite=self.suite, executor=self.user, status='failed',
            total_count=2, completed_at=timezone.now(),
            scheduled_task=self.task,
        )
        execution = self._execution(suite_execution=suite_exec)
        sync_scheduled_task_result(suite_exec)
        execution.refresh_from_db()
        self.assertEqual(execution.status, TaskExecution.ExecutionStatus.FAILED)

    def test_cancelled_suite_not_synced(self):
        suite_exec = TestExecution.objects.create(
            suite=self.suite, executor=self.user, status='cancelled',
            total_count=2, scheduled_task=self.task,
        )
        execution = self._execution(suite_execution=suite_exec)
        sync_scheduled_task_result(suite_exec)
        execution.refresh_from_db()
        self.assertEqual(execution.status, TaskExecution.ExecutionStatus.RUNNING)

    def test_unlinked_suite_ignored(self):
        suite_exec = TestExecution.objects.create(
            suite=self.suite, executor=self.user, status='completed',
            total_count=2, failed_count=1, completed_at=timezone.now(),
        )
        execution = self._execution()
        sync_scheduled_task_result(suite_exec)
        execution.refresh_from_db()
        self.assertEqual(execution.status, TaskExecution.ExecutionStatus.RUNNING)
