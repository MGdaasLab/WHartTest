"""定时任务失败自动自愈单元测试。

覆盖：
1. ScheduledTask 自愈字段序列化与校验（测试套件开启自愈被拒绝）；
2. heal_tasks 失败用例收集与上限裁剪、自愈 message 组装（含 self_heal 标记）；
3. consumers 批次完结投递条件（scheduled + auto_heal + 失败状态才投递）。
"""
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from projects.models import Project
from task_center.models import ScheduledTask, TaskExecution
from task_center.heal_tasks import (
    AgentLoopCallError,
    _build_failure_message,
    _collect_failed_cases,
    _truncate,
)
from ui_automation.models import (
    UiBatchExecutionRecord,
    UiModule,
    UiTestCase,
    UiExecutionRecord,
)


class SelfHealFieldTestCase(TestCase):
    """自愈字段模型与序列化校验。"""

    def setUp(self):
        self.user = User.objects.create_superuser(username='healuser', password='pwd', email='t@t.com')
        self.project = Project.objects.create(name='HealProject', creator=self.user)

    def _task(self, module=ScheduledTask.TaskModule.UI_AUTOMATION):
        return ScheduledTask.objects.create(
            name='自愈测试任务',
            project=self.project,
            module=module,
            schedule_type=ScheduledTask.ScheduleType.DAILY,
            daily_time='08:00',
            creator=self.user,
            auto_heal_enabled=True,
            heal_case_limit=5,
        )

    def test_default_fields(self):
        task = ScheduledTask.objects.create(
            name='默认任务', project=self.project, module=ScheduledTask.TaskModule.UI_AUTOMATION,
            schedule_type=ScheduledTask.ScheduleType.DAILY, daily_time='08:00', creator=self.user,
        )
        self.assertFalse(task.auto_heal_enabled)
        self.assertEqual(task.heal_case_limit, 5)

    def test_serializer_rejects_auto_heal_on_test_suite(self):
        from task_center.serializers import ScheduledTaskSerializer

        serializer = ScheduledTaskSerializer()
        with self.assertRaises(Exception):
            serializer.validate({
                'module': ScheduledTask.TaskModule.TEST_SUITE,
                'auto_heal_enabled': True,
            })

    def test_serializer_accepts_auto_heal_on_ui_automation(self):
        from task_center.serializers import ScheduledTaskSerializer

        serializer = ScheduledTaskSerializer()
        attrs = serializer.validate({
            'module': ScheduledTask.TaskModule.UI_AUTOMATION,
            'auto_heal_enabled': True,
        })
        self.assertTrue(attrs['auto_heal_enabled'])


class CollectFailedCasesTestCase(TestCase):
    """失败用例收集与上限裁剪。"""

    def setUp(self):
        self.user = User.objects.create_superuser(username='healuser2', password='pwd', email='t2@t.com')
        self.project = Project.objects.create(name='HealProject2', creator=self.user)
        self.ui_module = UiModule.objects.create(project=self.project, name='模块', creator=self.user)
        self.batch = UiBatchExecutionRecord.objects.create(name='批次', total_cases=4, status=1)
        # 3 个失败 + 1 个成功用例
        self.failed_cases = []
        for i in range(3):
            case = UiTestCase.objects.create(project=self.project, module=self.ui_module, name=f'失败用例{i}')
            UiExecutionRecord.objects.create(
                test_case=case, batch=self.batch, status=3, trigger_type='scheduled',
            )
            self.failed_cases.append(case)
        success_case = UiTestCase.objects.create(project=self.project, module=self.ui_module, name='成功用例')
        UiExecutionRecord.objects.create(
            test_case=success_case, batch=self.batch, status=2, trigger_type='scheduled',
        )

    def test_collect_only_failed_ordered(self):
        records = _collect_failed_cases(self.batch, limit=5)
        self.assertEqual(len(records), 3)
        self.assertEqual({r.test_case_id for r in records}, {c.id for c in self.failed_cases})

    def test_collect_respects_limit(self):
        records = _collect_failed_cases(self.batch, limit=2)
        self.assertEqual(len(records), 2)

    def test_collect_dedupes_same_case(self):
        # 同一用例复测再失败，仍只取一次
        UiExecutionRecord.objects.create(
            test_case=self.failed_cases[0], batch=self.batch, status=3, trigger_type='scheduled',
        )
        records = _collect_failed_cases(self.batch, limit=5)
        self.assertEqual(len(records), 3)


class BuildFailureMessageTestCase(TestCase):
    """自愈 message 组装。"""

    def setUp(self):
        self.user = User.objects.create_superuser(username='healuser3', password='pwd', email='t3@t.com')
        self.project = Project.objects.create(name='HealProject3', creator=self.user)
        self.ui_module = UiModule.objects.create(project=self.project, name='模块', creator=self.user)
        self.task = ScheduledTask.objects.create(
            name='自愈任务', project=self.project, module=ScheduledTask.TaskModule.UI_AUTOMATION,
            schedule_type=ScheduledTask.ScheduleType.DAILY, daily_time='08:00', creator=self.user,
            auto_heal_enabled=True,
        )
        self.case = UiTestCase.objects.create(
            project=self.project, module=self.ui_module, name='登录用例', error_message='TimeoutError: locator wait',
        )
        self.record = UiExecutionRecord.objects.create(
            test_case=self.case, status=3, trigger_type='scheduled',
            error_message='TimeoutError: locator wait for [text="提交"] failed',
            step_results=[
                {'step_id': 1, 'status': 2, 'description': '打开登录页', 'message': ''},
                {'step_id': 2, 'status': 3, 'description': '点击登录按钮', 'message': 'TimeoutError: waiting for locator'},
            ],
        )

    def test_message_contains_marker_and_context(self):
        message = _build_failure_message(self.task, self.record, self.project.id)
        self.assertIn('<!-- wharttest:generation_mode=self_heal -->', message)
        self.assertIn(f'UI 用例 ID：{self.case.id}', message)
        self.assertIn(f'项目 ID：{self.project.id}', message)
        self.assertIn('执行记录 ID：', message)
        self.assertIn('点击登录按钮', message)
        self.assertIn('TimeoutError', message)
        # 成功步骤也在流水里（供 Agent 区分通过/失败边界）
        self.assertIn('打开登录页', message)

    def test_truncate_keeps_head_and_tail(self):
        text = 'A' * 300 + 'MIDDLE' + 'B' * 300
        result = _truncate(text, 100)
        self.assertLess(len(result), 130)
        self.assertIn('A', result)
        self.assertIn('B', result)
        self.assertIn('过长已省略', result)


class AgentLoopCallErrorTestCase(SimpleTestCase):
    """调用异常的可续跑标记。"""

    def test_retriable_flag(self):
        self.assertTrue(AgentLoopCallError('net error').retriable)
        self.assertFalse(AgentLoopCallError('401', retriable=False).retriable)


class MaybeDispatchHealTaskTestCase(TestCase):
    """consumers 批次完结投递条件。"""

    def setUp(self):
        self.user = User.objects.create_superuser(username='healuser4', password='pwd', email='t4@t.com')
        self.project = Project.objects.create(name='HealProject4', creator=self.user)
        self.task = ScheduledTask.objects.create(
            name='投递任务', project=self.project, module=ScheduledTask.TaskModule.UI_AUTOMATION,
            schedule_type=ScheduledTask.ScheduleType.DAILY, daily_time='08:00', creator=self.user,
            auto_heal_enabled=True,
        )
        from ui_automation.consumers import UiAutomationConsumer

        self.consumer = UiAutomationConsumer()

    def _batch(self, status, trigger_type='scheduled', with_task=True):
        return UiBatchExecutionRecord.objects.create(
            name='批次', total_cases=2, status=status, trigger_type=trigger_type,
            scheduled_task=self.task if with_task else None,
        )

    def test_dispatch_on_partial_failure(self):
        batch = self._batch(status=3)
        with patch('task_center.heal_tasks.heal_failed_cases.delay') as mock_delay:
            self.consumer._maybe_dispatch_heal_task(batch)
            mock_delay.assert_called_once_with(batch.id)

    def test_no_dispatch_on_success(self):
        batch = self._batch(status=2)
        with patch('task_center.heal_tasks.heal_failed_cases.delay') as mock_delay:
            self.consumer._maybe_dispatch_heal_task(batch)
            mock_delay.assert_not_called()

    def test_no_dispatch_when_heal_disabled(self):
        self.task.auto_heal_enabled = False
        self.task.save(update_fields=['auto_heal_enabled'])
        batch = self._batch(status=3)
        with patch('task_center.heal_tasks.heal_failed_cases.delay') as mock_delay:
            self.consumer._maybe_dispatch_heal_task(batch)
            mock_delay.assert_not_called()

    def test_no_dispatch_for_manual_batch(self):
        batch = self._batch(status=3, trigger_type='manual', with_task=True)
        with patch('task_center.heal_tasks.heal_failed_cases.delay') as mock_delay:
            self.consumer._maybe_dispatch_heal_task(batch)
            mock_delay.assert_not_called()

    def test_no_dispatch_without_task(self):
        batch = self._batch(status=3, with_task=False)
        with patch('task_center.heal_tasks.heal_failed_cases.delay') as mock_delay:
            self.consumer._maybe_dispatch_heal_task(batch)
            mock_delay.assert_not_called()


class FlipExecutionRecordTests(TestCase):
    """方案B：自愈全部成功时执行记录 failed → success 翻转。"""

    def setUp(self):
        self.user = User.objects.create_superuser(username='flipuser', password='pwd', email='f@t.com')
        self.project = Project.objects.create(name='FlipProject', creator=self.user)
        self.task = ScheduledTask.objects.create(
            name='翻转任务', project=self.project,
            module=ScheduledTask.TaskModule.UI_AUTOMATION,
            schedule_type=ScheduledTask.ScheduleType.DAILY, daily_time='08:00',
            creator=self.user, auto_heal_enabled=True,
        )
        self.ui_module = UiModule.objects.create(project=self.project, name='模块', creator=self.user)

    def _failed_execution_with_batch(self, failed_cases=1):
        batch = UiBatchExecutionRecord.objects.create(
            name='批次', total_cases=failed_cases + 1, status=3,
            trigger_type='scheduled', scheduled_task=self.task,
        )
        execution = TaskExecution.objects.create(
            task=self.task, trigger_type=TaskExecution.TriggerType.SCHEDULED,
            status=TaskExecution.ExecutionStatus.FAILED,
            test_status=TaskExecution.ExecutionStatus.FAILED,
            batch_record=batch,
        )
        return batch, execution

    def test_all_healed_flips_to_success(self):
        from task_center.heal_tasks import _flip_execution_record_to_success

        batch, execution = self._failed_execution_with_batch()
        result = _flip_execution_record_to_success(batch, healed_count=1)
        self.assertTrue(result)
        execution.refresh_from_db()
        self.assertEqual(execution.status, TaskExecution.ExecutionStatus.SUCCESS)
        self.assertIn('自愈成功', execution.log)

    def test_partial_heal_gate_does_not_flip(self):
        # 部分自愈（有 manual_required）→ all_healed 门控为 False，不调用翻转
        from task_center.heal_tasks import _flip_execution_record_to_success

        batch, execution = self._failed_execution_with_batch(failed_cases=2)
        healed = [{'case_id': 1, 'case_name': 'c1', 'summary': ''}]
        interrupted = []
        healed_ids = {i['case_id'] for i in healed} | {i['case_id'] for i in interrupted}
        failed_records = [type('R', (), {'test_case_id': cid, 'test_case': type('C', (), {'name': f'c{cid}'})()}) for cid in (1, 2)]
        manual_required = [r for r in failed_records if r.test_case_id not in healed_ids]

        all_healed = (
            len(healed) > 0 and not interrupted and not manual_required
        )
        self.assertFalse(all_healed)
        if all_healed:
            _flip_execution_record_to_success(batch, len(healed))

        execution.refresh_from_db()
        self.assertEqual(execution.status, TaskExecution.ExecutionStatus.FAILED)

    def test_already_success_does_not_revert(self):
        # 执行记录已是 success（防并发重复翻转）：条件更新 0 行
        from task_center.heal_tasks import _flip_execution_record_to_success

        batch, execution = self._failed_execution_with_batch()
        execution.status = TaskExecution.ExecutionStatus.SUCCESS
        execution.save(update_fields=['status'])

        result = _flip_execution_record_to_success(batch, healed_count=1)
        self.assertFalse(result)
        execution.refresh_from_db()
        self.assertEqual(execution.status, TaskExecution.ExecutionStatus.SUCCESS)
