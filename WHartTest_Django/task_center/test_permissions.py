"""任务中心跨项目越权（IDOR）回归测试。

覆盖：非成员用户不能读写其他项目的定时任务与执行记录，
项目成员正常访问不受影响（三层权限：IsAuthenticated + HasModelPermission + IsProjectMemberForTaskCenter）。
"""
from django.contrib.auth.models import Permission, User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from projects.models import Project, ProjectMember
from task_center.models import ScheduledTask, TaskExecution


class CrossProjectAccessTestCase(TestCase):
    """跨项目访问控制回归测试。"""

    def setUp(self):
        self.client = APIClient()

        # 项目 1 的 owner（攻击者模拟角色：只属于自己项目的普通用户）
        self.owner_a = User.objects.create_user(username='user_a', password='pwd12345')
        self.project_a = Project.objects.create(name='项目A', creator=self.owner_a)
        ProjectMember.objects.create(project=self.project_a, user=self.owner_a, role='owner')
        self._grant_task_center_perms(self.owner_a)

        # 项目 2 的 owner（受害者）
        self.owner_b = User.objects.create_user(username='user_b', password='pwd12345')
        self.project_b = Project.objects.create(name='项目B', creator=self.owner_b)
        ProjectMember.objects.create(project=self.project_b, user=self.owner_b, role='owner')
        self._grant_task_center_perms(self.owner_b)

        self.task_b = ScheduledTask.objects.create(
            name='项目B的任务',
            project=self.project_b,
            module=ScheduledTask.TaskModule.UI_AUTOMATION,
            schedule_type=ScheduledTask.ScheduleType.DAILY,
            daily_time='08:00',
            creator=self.owner_b,
        )
        self.execution_b = TaskExecution.objects.create(
            task=self.task_b,
            trigger_type=TaskExecution.TriggerType.SCHEDULED,
            status=TaskExecution.ExecutionStatus.FAILED,
            log='机密执行日志',
            error_message='机密错误信息',
        )

    @staticmethod
    def _grant_task_center_perms(user):
        """授予任务中心全部模型权限，隔离出项目成员资格这一层变量。"""
        perms = Permission.objects.filter(content_type__app_label='task_center')
        user.user_permissions.set(perms)

    def _login(self, user):
        self.client.force_authenticate(user=user)

    def test_non_member_cannot_list_tasks(self):
        """项目A成员列举项目B定时任务应被拒绝。"""
        self._login(self.owner_a)
        response = self.client.get(f'/api/projects/{self.project_b.id}/scheduled-tasks/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_member_cannot_read_task(self):
        """项目A成员读取项目B任务详情应被拒绝。"""
        self._login(self.owner_a)
        response = self.client.get(f'/api/projects/{self.project_b.id}/scheduled-tasks/{self.task_b.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_member_cannot_create_task(self):
        """项目A成员不能往项目B创建定时任务。"""
        self._login(self.owner_a)
        response = self.client.post(
            f'/api/projects/{self.project_b.id}/scheduled-tasks/',
            {
                'name': '越权任务',
                'module': ScheduledTask.TaskModule.UI_AUTOMATION,
                'schedule_type': ScheduledTask.ScheduleType.DAILY,
                'daily_time': '09:00',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(ScheduledTask.objects.filter(project=self.project_b, name='越权任务').exists())

    def test_non_member_cannot_update_or_delete_task(self):
        """项目A成员不能修改或删除项目B任务。"""
        self._login(self.owner_a)
        response = self.client.patch(
            f'/api/projects/{self.project_b.id}/scheduled-tasks/{self.task_b.id}/',
            {'name': '被篡改'}, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.client.delete(
            f'/api/projects/{self.project_b.id}/scheduled-tasks/{self.task_b.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(ScheduledTask.objects.filter(pk=self.task_b.pk).exists())

    def test_non_member_cannot_trigger_run_now(self):
        """项目A成员不能立即触发项目B任务执行。"""
        self._login(self.owner_a)
        response = self.client.post(
            f'/api/projects/{self.project_b.id}/scheduled-tasks/{self.task_b.id}/run-now/'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_member_cannot_list_or_read_executions(self):
        """项目A成员不能列举或读取项目B执行记录。"""
        self._login(self.owner_a)
        response = self.client.get(f'/api/projects/{self.project_b.id}/task-executions/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.client.get(
            f'/api/projects/{self.project_b.id}/task-executions/{self.execution_b.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_member_cannot_read_execution_log(self):
        """项目A成员不能读取项目B执行日志与错误信息。"""
        self._login(self.owner_a)
        response = self.client.get(
            f'/api/projects/{self.project_b.id}/task-executions/{self.execution_b.id}/log/'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn('机密执行日志', response.content.decode())

    def test_non_member_cannot_delete_execution(self):
        """项目A成员不能删除项目B执行记录。"""
        self._login(self.owner_a)
        response = self.client.delete(
            f'/api/projects/{self.project_b.id}/task-executions/{self.execution_b.id}/remove/'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(TaskExecution.objects.filter(pk=self.execution_b.pk).exists())

    def test_member_can_access_own_project(self):
        """项目B成员正常访问自己项目的任务与执行记录不受影响。"""
        self._login(self.owner_b)
        response = self.client.get(f'/api/projects/{self.project_b.id}/scheduled-tasks/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tasks = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertEqual(len(tasks), 1)

        response = self.client.get(
            f'/api/projects/{self.project_b.id}/task-executions/{self.execution_b.id}/log/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['log'], '机密执行日志')

    def test_unauthenticated_access_denied(self):
        """未登录用户访问任务中心接口应被拒绝。"""
        response = self.client.get(f'/api/projects/{self.project_b.id}/scheduled-tasks/')
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
