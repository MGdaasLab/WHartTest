from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from projects.models import Project, ProjectMember
from api_interfaces.models import ApiInterface
from api_testcases.models import (
    ApiInterfaceCase,
    ApiInterfaceCaseReport,
    ApiTestCase,
    ApiTestReport,
)
from .models import (
    ApiTestTaskSuite, ApiTestTaskCase,
    ApiTestTaskExecution, ApiTestTaskCaseResult,
)
from .services import ApiTestTaskService, ApiTestTaskExecutionService


def _grant_model_perms(user, model_class):
    ct = ContentType.objects.get_for_model(model_class)
    perms = Permission.objects.filter(content_type=ct)
    user.user_permissions.add(*perms)


def _grant_all_testtask_perms(user):
    for model_cls in [
        ApiTestTaskSuite, ApiTestTaskCase,
        ApiTestTaskExecution, ApiTestTaskCaseResult,
    ]:
        _grant_model_perms(user, model_cls)
    for attr in ('_perm_cache', '_user_perm_cache'):
        try:
            delattr(user, attr)
        except AttributeError:
            pass


class ApiTestTaskSuiteModelTest(TestCase):
    """ApiTestTaskSuite model tests"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)

    def test_create_suite(self):
        suite = ApiTestTaskSuite.objects.create(
            name='Smoke Suite', project=self.project, created_by=self.user,
        )
        self.assertEqual(suite.name, 'Smoke Suite')
        self.assertEqual(suite.priority, 'P2')
        self.assertFalse(suite.fail_fast)

    def test_str_representation(self):
        suite = ApiTestTaskSuite.objects.create(
            name='My Suite', project=self.project, created_by=self.user,
        )
        self.assertEqual(str(suite), 'My Suite')

    def test_unique_name_per_project(self):
        ApiTestTaskSuite.objects.create(
            name='Dup', project=self.project, created_by=self.user,
        )
        with self.assertRaises(Exception):
            ApiTestTaskSuite.objects.create(
                name='Dup', project=self.project, created_by=self.user,
            )

    def test_same_name_different_project(self):
        other = Project.objects.create(name='Other Project', creator=self.user)
        ApiTestTaskSuite.objects.create(
            name='Same Name', project=self.project, created_by=self.user,
        )
        suite2 = ApiTestTaskSuite.objects.create(
            name='Same Name', project=other, created_by=self.user,
        )
        self.assertEqual(suite2.name, 'Same Name')

    def test_priority_choices(self):
        for code in ['P0', 'P1', 'P2', 'P3']:
            suite = ApiTestTaskSuite.objects.create(
                name=f'Suite {code}', priority=code,
                project=self.project, created_by=self.user,
            )
            self.assertEqual(suite.priority, code)

    def test_cascade_delete_project(self):
        ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        self.project.delete()
        self.assertEqual(ApiTestTaskSuite.objects.count(), 0)

    def test_set_null_on_user_delete(self):
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        self.user.delete()
        suite.refresh_from_db()
        self.assertIsNone(suite.created_by)

    def test_ordering_newest_first(self):
        s1 = ApiTestTaskSuite.objects.create(
            name='First', project=self.project, created_by=self.user,
        )
        s2 = ApiTestTaskSuite.objects.create(
            name='Second', project=self.project, created_by=self.user,
        )
        suites = list(ApiTestTaskSuite.objects.filter(project=self.project))
        self.assertEqual(suites[0], s2)
        self.assertEqual(suites[1], s1)


class ApiTestTaskExecutionModelTest(TestCase):
    """ApiTestTaskExecution model tests — status machine, duration, success_rate"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)
        self.suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )

    def test_create_execution_defaults(self):
        execution = ApiTestTaskExecution.objects.create(
            task_suite=self.suite, executed_by=self.user, total_count=3,
        )
        self.assertEqual(execution.status, 'pending')
        self.assertEqual(execution.total_count, 3)
        self.assertEqual(execution.success_count, 0)
        self.assertEqual(execution.fail_count, 0)
        self.assertEqual(execution.error_count, 0)
        self.assertIsNone(execution.start_time)
        self.assertIsNone(execution.end_time)

    # -- status machine --

    def test_start_sets_running(self):
        execution = ApiTestTaskExecution.objects.create(
            task_suite=self.suite, executed_by=self.user,
        )
        execution.start()
        execution.refresh_from_db()
        self.assertEqual(execution.status, 'running')
        self.assertIsNotNone(execution.start_time)

    def test_complete_sets_counts(self):
        execution = ApiTestTaskExecution.objects.create(
            task_suite=self.suite, executed_by=self.user,
        )
        execution.start()
        execution.complete(success_count=5, fail_count=2, error_count=1)
        execution.refresh_from_db()
        self.assertEqual(execution.status, 'completed')
        self.assertEqual(execution.success_count, 5)
        self.assertEqual(execution.fail_count, 2)
        self.assertEqual(execution.error_count, 1)
        self.assertIsNotNone(execution.end_time)

    def test_fail_sets_failed(self):
        execution = ApiTestTaskExecution.objects.create(
            task_suite=self.suite, executed_by=self.user,
        )
        execution.start()
        execution.fail()
        execution.refresh_from_db()
        self.assertEqual(execution.status, 'failed')
        self.assertIsNotNone(execution.end_time)

    def test_cancel_sets_canceled(self):
        execution = ApiTestTaskExecution.objects.create(
            task_suite=self.suite, executed_by=self.user,
        )
        execution.start()
        execution.cancel()
        execution.refresh_from_db()
        self.assertEqual(execution.status, 'canceled')
        self.assertIsNotNone(execution.end_time)

    # -- duration property --

    def test_duration_zero_when_no_times(self):
        execution = ApiTestTaskExecution.objects.create(
            task_suite=self.suite, executed_by=self.user,
        )
        self.assertEqual(execution.duration, 0)

    def test_duration_calculated(self):
        execution = ApiTestTaskExecution.objects.create(
            task_suite=self.suite, executed_by=self.user,
        )
        execution.start_time = timezone.now()
        execution.end_time = execution.start_time + timezone.timedelta(seconds=42)
        execution.save()
        self.assertAlmostEqual(execution.duration, 42.0, places=0)

    # -- success_rate property --

    def test_success_rate_with_results(self):
        execution = ApiTestTaskExecution.objects.create(
            task_suite=self.suite, executed_by=self.user,
            total_count=4, success_count=3,
        )
        self.assertEqual(execution.success_rate, 0.75)

    def test_success_rate_perfect(self):
        execution = ApiTestTaskExecution.objects.create(
            task_suite=self.suite, executed_by=self.user,
            total_count=5, success_count=5,
        )
        self.assertEqual(execution.success_rate, 1.0)

    def test_success_rate_zero_total(self):
        execution = ApiTestTaskExecution.objects.create(
            task_suite=self.suite, executed_by=self.user, total_count=0,
        )
        self.assertEqual(execution.success_rate, 0.00)

    def test_str_contains_suite_name(self):
        execution = ApiTestTaskExecution.objects.create(
            task_suite=self.suite, executed_by=self.user,
        )
        self.assertIn('Suite', str(execution))

    def test_task_case_result_cascade_delete(self):
        execution = ApiTestTaskExecution.objects.create(
            task_suite=self.suite, executed_by=self.user, total_count=1,
        )
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        ApiTestTaskCaseResult.objects.create(
            execution=execution, testcase=tc,
        )
        execution.delete()
        self.assertEqual(ApiTestTaskCaseResult.objects.count(), 0)

    def test_case_result_report_set_null(self):
        execution = ApiTestTaskExecution.objects.create(
            task_suite=self.suite, executed_by=self.user, total_count=1,
        )
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        report = ApiTestReport.objects.create(
            name='Report', status='success',
            success_count=1, fail_count=0, error_count=0,
            duration=0.5, summary={},
            testcase=tc, executed_by=self.user,
        )
        result = ApiTestTaskCaseResult.objects.create(
            execution=execution, testcase=tc, report=report,
        )
        report.delete()
        result.refresh_from_db()
        self.assertIsNone(result.report)


class ApiTestTaskAPITest(TestCase):
    """Suite CRUD, add-testcases/remove-testcase, Execution create/cancel, case-results"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='apiuser', password='testpass')
        self.project = Project.objects.create(name='API Project', creator=self.user)
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        _grant_all_testtask_perms(self.user)
        self.client.force_authenticate(user=self.user)
        self.suite_url = f'/api/projects/{self.project.pk}/api-task-suites/'
        self.exec_url = f'/api/projects/{self.project.pk}/api-task-executions/'

    def _create_interface_case(self, name='IC'):
        interface = ApiInterface.objects.create(
            name=f'{name} Interface',
            type='http',
            method='GET',
            url='/api/demo',
            project=self.project,
            created_by=self.user,
        )
        return ApiInterfaceCase.objects.create(
            name=name,
            project=self.project,
            interface=interface,
            created_by=self.user,
        )

    # --- Suite CRUD ---

    def test_list_suites(self):
        ApiTestTaskSuite.objects.create(
            name='Suite 1', project=self.project, created_by=self.user,
        )
        response = self.client.get(self.suite_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_suite(self):
        data = {
            'name': 'New Suite',
            'priority': 'P1',
            'fail_fast': True,
            'project': self.project.pk,
        }
        response = self.client.post(self.suite_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        suite = ApiTestTaskSuite.objects.get(name='New Suite')
        self.assertEqual(suite.project, self.project)
        self.assertEqual(suite.created_by, self.user)
        self.assertTrue(suite.fail_fast)

    def test_retrieve_suite(self):
        suite = ApiTestTaskSuite.objects.create(
            name='Detail Suite', project=self.project, created_by=self.user,
        )
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        ApiTestTaskCase.objects.create(task_suite=suite, testcase=tc, order=1)
        response = self.client.get(f'{self.suite_url}{suite.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['task_cases']), 1)

    def test_update_suite(self):
        suite = ApiTestTaskSuite.objects.create(
            name='Old Name', project=self.project, created_by=self.user,
        )
        response = self.client.patch(
            f'{self.suite_url}{suite.pk}/',
            {'name': 'New Name'}, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        suite.refresh_from_db()
        self.assertEqual(suite.name, 'New Name')

    def test_delete_suite(self):
        suite = ApiTestTaskSuite.objects.create(
            name='To Delete', project=self.project, created_by=self.user,
        )
        response = self.client.delete(f'{self.suite_url}{suite.pk}/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])
        self.assertEqual(ApiTestTaskSuite.objects.count(), 0)

    def test_create_suite_with_testcases(self):
        tc = ApiTestCase.objects.create(
            name='TC1', project=self.project, created_by=self.user,
        )
        data = {'name': 'Suite with TCs', 'test_cases': [tc.pk], 'project': self.project.pk}
        response = self.client.post(self.suite_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        suite = ApiTestTaskSuite.objects.get(name='Suite with TCs')
        self.assertEqual(suite.api_task_cases.count(), 1)

    def test_create_suite_with_interface_cases(self):
        interface_case = self._create_interface_case('IC1')
        data = {
            'name': 'Suite with ICs',
            'interface_cases': [interface_case.pk],
            'project': self.project.pk,
        }
        response = self.client.post(self.suite_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        suite = ApiTestTaskSuite.objects.get(name='Suite with ICs')
        task_case = suite.api_task_cases.get()
        self.assertEqual(task_case.case_type, ApiTestTaskCase.CASE_TYPE_INTERFACE)
        self.assertEqual(task_case.interface_case, interface_case)

    # --- add-testcases / remove-testcase ---

    def test_add_testcases_action(self):
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        tc1 = ApiTestCase.objects.create(
            name='TC1', project=self.project, created_by=self.user,
        )
        tc2 = ApiTestCase.objects.create(
            name='TC2', project=self.project, created_by=self.user,
        )
        data = {'testcase_ids': [tc1.pk, tc2.pk]}
        response = self.client.post(
            f'{self.suite_url}{suite.pk}/add-testcases/', data, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(suite.api_task_cases.count(), 2)

    def test_add_testcases_action_accepts_interface_cases(self):
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        interface_case = self._create_interface_case('IC2')
        data = {'interface_case_ids': [interface_case.pk]}
        response = self.client.post(
            f'{self.suite_url}{suite.pk}/add-testcases/', data, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(suite.api_task_cases.count(), 1)
        self.assertEqual(response.data[0]['case_type'], 'interface')
        self.assertEqual(response.data[0]['interface_case_id'], interface_case.pk)

    def test_add_testcases_skip_duplicates(self):
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        ApiTestTaskCase.objects.create(task_suite=suite, testcase=tc, order=1)
        data = {'testcase_ids': [tc.pk]}
        response = self.client.post(
            f'{self.suite_url}{suite.pk}/add-testcases/', data, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(suite.api_task_cases.count(), 1)  # not duplicated

    def test_remove_testcase_action(self):
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        ApiTestTaskCase.objects.create(task_suite=suite, testcase=tc, order=1)
        response = self.client.delete(
            f'{self.suite_url}{suite.pk}/remove-testcase/{tc.pk}/',
        )
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])
        self.assertEqual(suite.api_task_cases.count(), 0)

    def test_remove_case_action_removes_interface_case(self):
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        interface_case = self._create_interface_case('IC3')
        ApiTestTaskCase.objects.create(
            task_suite=suite,
            case_type=ApiTestTaskCase.CASE_TYPE_INTERFACE,
            interface_case=interface_case,
            order=1,
        )
        response = self.client.delete(
            f'{self.suite_url}{suite.pk}/remove-case/interface/{interface_case.pk}/',
        )
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])
        self.assertEqual(suite.api_task_cases.count(), 0)

    def test_remove_testcase_not_found(self):
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        response = self.client.delete(
            f'{self.suite_url}{suite.pk}/remove-testcase/99999/',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_remove_testcase_reorders(self):
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        tc1 = ApiTestCase.objects.create(
            name='TC1', project=self.project, created_by=self.user,
        )
        tc2 = ApiTestCase.objects.create(
            name='TC2', project=self.project, created_by=self.user,
        )
        ApiTestTaskCase.objects.create(task_suite=suite, testcase=tc1, order=1)
        ApiTestTaskCase.objects.create(task_suite=suite, testcase=tc2, order=2)
        self.client.delete(f'{self.suite_url}{suite.pk}/remove-testcase/{tc1.pk}/')
        remaining = suite.api_task_cases.first()
        self.assertEqual(remaining.order, 1)

    # --- Execution create ---

    @patch('api_testtasks.views.execute_api_task_async')
    def test_create_execution(self, mock_task):
        mock_task.delay.return_value = MagicMock(id='celery-task-id')
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        ApiTestTaskCase.objects.create(task_suite=suite, testcase=tc, order=1)
        data = {'task_suite_id': suite.pk}
        response = self.client.post(self.exec_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        execution = ApiTestTaskExecution.objects.first()
        self.assertEqual(execution.total_count, 1)
        self.assertEqual(execution.executed_by, self.user)
        mock_task.delay.assert_called_once_with(execution.id)

    @patch('api_testtasks.views.execute_api_task_async')
    def test_create_execution_with_interface_case(self, mock_task):
        mock_task.delay.return_value = MagicMock(id='celery-task-id')
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        interface_case = self._create_interface_case('IC4')
        ApiTestTaskCase.objects.create(
            task_suite=suite,
            case_type=ApiTestTaskCase.CASE_TYPE_INTERFACE,
            interface_case=interface_case,
            order=1,
        )
        response = self.client.post(self.exec_url, {'task_suite_id': suite.pk}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        execution = ApiTestTaskExecution.objects.first()
        self.assertEqual(execution.total_count, 1)
        result = execution.api_case_results.get()
        self.assertEqual(result.case_type, ApiTestTaskCase.CASE_TYPE_INTERFACE)
        self.assertEqual(result.interface_case, interface_case)

    def test_create_execution_empty_suite(self):
        empty = ApiTestTaskSuite.objects.create(
            name='Empty', project=self.project, created_by=self.user,
        )
        data = {'task_suite_id': empty.pk}
        response = self.client.post(self.exec_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_execution_invalid_suite(self):
        data = {'task_suite_id': 99999}
        response = self.client.post(self.exec_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Execution cancel ---

    def test_cancel_pending_execution(self):
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        execution = ApiTestTaskExecution.objects.create(
            task_suite=suite, executed_by=self.user,
            total_count=1, status='pending',
        )
        response = self.client.post(f'{self.exec_url}{execution.pk}/cancel/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        execution.refresh_from_db()
        self.assertEqual(execution.status, 'canceled')

    def test_cancel_running_execution(self):
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        execution = ApiTestTaskExecution.objects.create(
            task_suite=suite, executed_by=self.user,
            total_count=1, status='running',
        )
        response = self.client.post(f'{self.exec_url}{execution.pk}/cancel/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        execution.refresh_from_db()
        self.assertEqual(execution.status, 'canceled')

    def test_cancel_completed_rejected(self):
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        execution = ApiTestTaskExecution.objects.create(
            task_suite=suite, executed_by=self.user,
            total_count=1, status='completed',
        )
        response = self.client.post(f'{self.exec_url}{execution.pk}/cancel/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- case-results ---

    def test_case_results_action(self):
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        execution = ApiTestTaskExecution.objects.create(
            task_suite=suite, executed_by=self.user, total_count=1,
        )
        ApiTestTaskCaseResult.objects.create(execution=execution, testcase=tc)
        response = self.client.get(f'{self.exec_url}{execution.pk}/case-results/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['testcase_name'], 'TC')

    # --- Execution viewset is read-only for delete/put ---

    def test_execution_no_delete(self):
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        execution = ApiTestTaskExecution.objects.create(
            task_suite=suite, executed_by=self.user, total_count=1,
        )
        response = self.client.delete(f'{self.exec_url}{execution.pk}/')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # --- filter by task_suite_id ---

    def test_list_executions_filter_by_suite(self):
        suite1 = ApiTestTaskSuite.objects.create(
            name='S1', project=self.project, created_by=self.user,
        )
        suite2 = ApiTestTaskSuite.objects.create(
            name='S2', project=self.project, created_by=self.user,
        )
        ApiTestTaskExecution.objects.create(
            task_suite=suite1, executed_by=self.user, total_count=1,
        )
        ApiTestTaskExecution.objects.create(
            task_suite=suite2, executed_by=self.user, total_count=1,
        )
        response = self.client.get(self.exec_url, {'task_suite_id': suite1.pk})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        items = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertEqual(len(items), 1)

    def test_unauthenticated_suite(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.suite_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_execution(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.exec_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ApiTestTaskCeleryTest(TestCase):
    """Mock the runner, verify execute_api_task_async task status flow and count updates"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)
        self.suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        self.tc1 = ApiTestCase.objects.create(
            name='TC1', project=self.project, created_by=self.user,
        )
        self.tc2 = ApiTestCase.objects.create(
            name='TC2', project=self.project, created_by=self.user,
        )
        self.tc3 = ApiTestCase.objects.create(
            name='TC3', project=self.project, created_by=self.user,
        )
        ApiTestTaskCase.objects.create(task_suite=self.suite, testcase=self.tc1, order=1)
        ApiTestTaskCase.objects.create(task_suite=self.suite, testcase=self.tc2, order=2)
        ApiTestTaskCase.objects.create(task_suite=self.suite, testcase=self.tc3, order=3)

    def _create_interface_case(self, name='IC'):
        interface = ApiInterface.objects.create(
            name=f'{name} Interface',
            type='http',
            method='GET',
            url='/api/demo',
            project=self.project,
            created_by=self.user,
        )
        return ApiInterfaceCase.objects.create(
            name=name,
            project=self.project,
            interface=interface,
            created_by=self.user,
        )

    @patch('api_testcases.services.TestExecutionService')
    def test_all_success(self, mock_exec_svc):
        """All cases succeed -> status=completed, success_count=3"""
        def make_report(*args, **kwargs):
            return ApiTestReport.objects.create(
                name='Report', status='success',
                success_count=1, fail_count=0, error_count=0,
                duration=0.5, summary={},
                testcase=args[0], executed_by=self.user,
            )
        mock_exec_svc.run_testcase.side_effect = make_report

        execution = ApiTestTaskExecutionService.create_execution(
            task_suite=self.suite, user=self.user,
        )
        self.assertEqual(execution.api_case_results.count(), 3)

        ApiTestTaskExecutionService.execute_task(execution)

        execution.refresh_from_db()
        self.assertEqual(execution.status, 'completed')
        self.assertEqual(execution.success_count, 3)
        self.assertEqual(execution.fail_count, 0)
        self.assertEqual(execution.error_count, 0)
        self.assertIsNotNone(execution.start_time)
        self.assertIsNotNone(execution.end_time)

        for cr in execution.api_case_results.all():
            self.assertEqual(cr.status, 'success')
            self.assertIsNotNone(cr.report)
            self.assertGreater(cr.duration, 0)

    @patch('api_testcases.services.TestExecutionService')
    def test_mixed_results(self, mock_exec_svc):
        """2 success + 1 failure -> counts updated correctly"""
        testcases = [self.tc1, self.tc2, self.tc3]
        statuses = ['success', 'success', 'failure']
        call_idx = [0]

        def make_report(testcase, environment, user):
            idx = call_idx[0]
            call_idx[0] += 1
            return ApiTestReport.objects.create(
                name=f'Report {idx}', status=statuses[idx],
                success_count=1 if statuses[idx] == 'success' else 0,
                fail_count=1 if statuses[idx] == 'failure' else 0,
                error_count=0, duration=0.5, summary={},
                testcase=testcase, executed_by=self.user,
            )
        mock_exec_svc.run_testcase.side_effect = make_report

        execution = ApiTestTaskExecutionService.create_execution(
            task_suite=self.suite, user=self.user,
        )
        ApiTestTaskExecutionService.execute_task(execution)

        execution.refresh_from_db()
        self.assertEqual(execution.status, 'completed')
        self.assertEqual(execution.success_count, 2)
        self.assertEqual(execution.fail_count, 1)
        self.assertEqual(execution.error_count, 0)

    @patch('api_testcases.services.TestExecutionService')
    def test_fail_fast_stops_at_first_failure(self, mock_exec_svc):
        """fail_fast=True -> first failure skips remaining"""
        self.suite.fail_fast = True
        self.suite.save()

        statuses = ['success', 'failure']
        call_idx = [0]

        def make_report(testcase, environment, user):
            idx = call_idx[0]
            call_idx[0] += 1
            return ApiTestReport.objects.create(
                name=f'Report {idx}', status=statuses[idx],
                success_count=1 if statuses[idx] == 'success' else 0,
                fail_count=1 if statuses[idx] == 'failure' else 0,
                error_count=0, duration=0.5, summary={},
                testcase=testcase, executed_by=self.user,
            )
        mock_exec_svc.run_testcase.side_effect = make_report

        execution = ApiTestTaskExecutionService.create_execution(
            task_suite=self.suite, user=self.user,
        )
        ApiTestTaskExecutionService.execute_task(execution)

        execution.refresh_from_db()
        self.assertEqual(execution.status, 'completed')
        self.assertEqual(execution.success_count, 1)
        self.assertEqual(execution.fail_count, 1)
        self.assertEqual(execution.error_count, 0)

        statuses = list(
            execution.api_case_results.order_by('id').values_list('status', flat=True)
        )
        self.assertEqual(statuses, ['success', 'failure', 'skipped'])

    @patch('api_testcases.services.TestExecutionService')
    def test_fail_fast_on_error(self, mock_exec_svc):
        """fail_fast=True + exception -> error + skip remaining"""
        self.suite.fail_fast = True
        self.suite.save()

        mock_exec_svc.run_testcase.side_effect = Exception('Connection timeout')

        execution = ApiTestTaskExecutionService.create_execution(
            task_suite=self.suite, user=self.user,
        )
        ApiTestTaskExecutionService.execute_task(execution)

        execution.refresh_from_db()
        self.assertEqual(execution.status, 'completed')
        self.assertEqual(execution.error_count, 1)

        statuses = list(
            execution.api_case_results.order_by('id').values_list('status', flat=True)
        )
        self.assertEqual(statuses[0], 'error')
        self.assertEqual(statuses[1], 'skipped')
        self.assertEqual(statuses[2], 'skipped')

        error_result = execution.api_case_results.filter(status='error').first()
        self.assertIn('Connection timeout', error_result.error_message)

    @patch('api_testcases.services.TestExecutionService')
    def test_exception_records_error(self, mock_exec_svc):
        """Exception without fail_fast -> error_count incremented, others still run"""
        call_idx = [0]

        def make_report_or_raise(testcase, environment, user):
            idx = call_idx[0]
            call_idx[0] += 1
            if idx == 0:
                raise Exception('Boom')
            return ApiTestReport.objects.create(
                name=f'Report {idx}', status='success',
                success_count=1, fail_count=0, error_count=0,
                duration=0.5, summary={},
                testcase=testcase, executed_by=self.user,
            )
        mock_exec_svc.run_testcase.side_effect = make_report_or_raise

        execution = ApiTestTaskExecutionService.create_execution(
            task_suite=self.suite, user=self.user,
        )
        ApiTestTaskExecutionService.execute_task(execution)

        execution.refresh_from_db()
        self.assertEqual(execution.status, 'completed')
        self.assertEqual(execution.success_count, 2)
        self.assertEqual(execution.error_count, 1)

        statuses = list(
            execution.api_case_results.order_by('id').values_list('status', flat=True)
        )
        self.assertEqual(statuses, ['error', 'success', 'success'])

    @patch('api_testcases.services.TestExecutionService')
    def test_execute_task_async_delegates(self, mock_exec_svc):
        """execute_task_async -> calls execute_task -> status completed"""
        def make_report(testcase, environment, user):
            return ApiTestReport.objects.create(
                name='Report', status='success',
                success_count=1, fail_count=0, error_count=0,
                duration=0.5, summary={},
                testcase=testcase, executed_by=self.user,
            )
        mock_exec_svc.run_testcase.side_effect = make_report

        execution = ApiTestTaskExecutionService.create_execution(
            task_suite=self.suite, user=self.user,
        )
        ApiTestTaskExecutionService.execute_task_async(execution.id)

        execution.refresh_from_db()
        self.assertEqual(execution.status, 'completed')

    def test_execute_task_async_nonexistent(self):
        """Nonexistent execution_id -> no crash"""
        ApiTestTaskExecutionService.execute_task_async(99999)

    @patch('api_testtasks.services.ApiTestTaskExecutionService.execute_task')
    def test_execute_task_async_unexpected_error_marks_failed(self, mock_execute):
        """Unexpected error in execute_task -> execution marked failed"""
        mock_execute.side_effect = RuntimeError('Unexpected')

        execution = ApiTestTaskExecutionService.create_execution(
            task_suite=self.suite, user=self.user,
        )
        ApiTestTaskExecutionService.execute_task_async(execution.id)

        execution.refresh_from_db()
        self.assertEqual(execution.status, 'failed')

    @patch('api_testcases.services.TestExecutionService')
    def test_case_result_has_duration(self, mock_exec_svc):
        """Each case_result records a non-negative duration"""
        def make_report(testcase, environment, user):
            return ApiTestReport.objects.create(
                name='Report', status='success',
                success_count=1, fail_count=0, error_count=0,
                duration=0.5, summary={},
                testcase=testcase, executed_by=self.user,
            )
        mock_exec_svc.run_testcase.side_effect = make_report

        execution = ApiTestTaskExecutionService.create_execution(
            task_suite=self.suite, user=self.user,
        )
        ApiTestTaskExecutionService.execute_task(execution)

        for cr in execution.api_case_results.all():
            self.assertGreaterEqual(cr.duration, 0)
            self.assertIsNotNone(cr.start_time)
            self.assertIsNotNone(cr.end_time)

    @patch('api_testcases.services.InterfaceCaseExecutionService')
    def test_execute_interface_case_result(self, mock_interface_exec_svc):
        interface_case = self._create_interface_case('IC Task')
        suite = ApiTestTaskSuite.objects.create(
            name='Interface Suite', project=self.project, created_by=self.user,
        )
        ApiTestTaskCase.objects.create(
            task_suite=suite,
            case_type=ApiTestTaskCase.CASE_TYPE_INTERFACE,
            interface_case=interface_case,
            order=1,
        )

        def make_report(case_obj, environment, user):
            return ApiInterfaceCaseReport.objects.create(
                name='Interface Report',
                status='success',
                success_count=1,
                fail_count=0,
                error_count=0,
                duration=0.5,
                summary={},
                interface_case=case_obj,
                executed_by=user,
            )

        mock_interface_exec_svc.run_interface_case.side_effect = make_report

        execution = ApiTestTaskExecutionService.create_execution(
            task_suite=suite, user=self.user,
        )
        ApiTestTaskExecutionService.execute_task(execution)

        execution.refresh_from_db()
        result = execution.api_case_results.get()
        self.assertEqual(result.case_type, ApiTestTaskCase.CASE_TYPE_INTERFACE)
        self.assertEqual(result.status, 'success')
        self.assertIsNone(result.report)
        self.assertIsNotNone(result.interface_report)
        self.assertEqual(execution.success_count, 1)


class ApiTestTaskSerializerFieldTest(TestCase):
    """Verify serializer field names and computed fields match frontend expectations.

    These tests validate the serializer changes made during the TestRunner integration:
    - task_cases (not api_task_cases) in suite response
    - case_results (not api_case_results) in execution detail response
    - project_name computed field in suite response
    - environment_name computed field in execution response
    - description/priority in task case simple serializer
    - nested report object in case results
    - success_rate string format in report serializer
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='seruser', password='testpass')
        self.project = Project.objects.create(name='Serializer Project', creator=self.user)
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        _grant_all_testtask_perms(self.user)
        self.client.force_authenticate(user=self.user)
        self.suite_url = f'/api/projects/{self.project.pk}/api-task-suites/'
        self.exec_url = f'/api/projects/{self.project.pk}/api-task-executions/'

    # --- Suite serializer field names ---

    def test_suite_response_uses_task_cases_field_name(self):
        """Suite detail response uses 'task_cases' key, not 'api_task_cases'."""
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        ApiTestTaskCase.objects.create(task_suite=suite, testcase=tc, order=1)
        response = self.client.get(f'{self.suite_url}{suite.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('task_cases', response.data)
        self.assertNotIn('api_task_cases', response.data)
        self.assertEqual(len(response.data['task_cases']), 1)

    def test_suite_response_includes_project_name(self):
        """Suite response includes project_name computed field."""
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        response = self.client.get(f'{self.suite_url}{suite.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('project_name', response.data)
        self.assertEqual(response.data['project_name'], 'Serializer Project')

    # --- Task case simple serializer fields ---

    def test_task_case_includes_description_and_priority(self):
        """Task case in suite response includes testcase description and priority."""
        tc = ApiTestCase.objects.create(
            name='TC with desc', project=self.project, created_by=self.user,
            description='A test case description', priority='P1',
        )
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        ApiTestTaskCase.objects.create(task_suite=suite, testcase=tc, order=1)
        response = self.client.get(f'{self.suite_url}{suite.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        task_case = response.data['task_cases'][0]
        self.assertEqual(task_case['testcase_name'], 'TC with desc')
        self.assertEqual(task_case['description'], 'A test case description')
        self.assertEqual(task_case['priority'], 'P1')
        self.assertIn('testcase_id', task_case)
        self.assertIn('order', task_case)

    # --- Execution serializer field names ---

    @patch('api_testtasks.views.execute_api_task_async')
    def test_execution_detail_uses_case_results_field_name(self, mock_task):
        """Execution detail response uses 'case_results' key, not 'api_case_results'."""
        mock_task.delay.return_value = MagicMock(id='celery-task-id')
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        ApiTestTaskCase.objects.create(task_suite=suite, testcase=tc, order=1)
        # Create execution
        data = {'task_suite_id': suite.pk}
        create_resp = self.client.post(self.exec_url, data, format='json')
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        exec_id = create_resp.data['id']
        # Retrieve execution detail
        response = self.client.get(f'{self.exec_url}{exec_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('case_results', response.data)
        self.assertNotIn('api_case_results', response.data)

    @patch('api_testtasks.views.execute_api_task_async')
    def test_execution_response_includes_environment_name(self, mock_task):
        """Execution response includes environment_name computed field."""
        from api_environments.models import ApiEnvironment
        mock_task.delay.return_value = MagicMock(id='celery-task-id')
        env = ApiEnvironment.objects.create(
            name='Staging Env', base_url='https://staging.example.com',
            project=self.project,
        )
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        ApiTestTaskCase.objects.create(task_suite=suite, testcase=tc, order=1)
        data = {'task_suite_id': suite.pk, 'environment_id': env.pk}
        create_resp = self.client.post(self.exec_url, data, format='json')
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('environment_name', create_resp.data)
        self.assertEqual(create_resp.data['environment_name'], 'Staging Env')

    @patch('api_testtasks.views.execute_api_task_async')
    def test_execution_response_environment_name_empty_when_no_env(self, mock_task):
        """Execution response returns '' for environment_name when no environment."""
        mock_task.delay.return_value = MagicMock(id='celery-task-id')
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        ApiTestTaskCase.objects.create(task_suite=suite, testcase=tc, order=1)
        data = {'task_suite_id': suite.pk}
        create_resp = self.client.post(self.exec_url, data, format='json')
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_resp.data['environment_name'], '')

    def test_execution_list_includes_environment_name(self):
        """Execution list serializer also includes environment_name."""
        from api_environments.models import ApiEnvironment
        env = ApiEnvironment.objects.create(
            name='Production', base_url='https://prod.example.com',
            project=self.project,
        )
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        ApiTestTaskExecution.objects.create(
            task_suite=suite, executed_by=self.user,
            total_count=1, environment=env,
        )
        response = self.client.get(self.exec_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        items = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertEqual(len(items), 1)
        self.assertIn('environment_name', items[0])
        self.assertEqual(items[0]['environment_name'], 'Production')

    # --- Nested report in case results ---

    def test_case_result_includes_nested_report_object(self):
        """Case result includes nested report object, not just FK ID."""
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        report = ApiTestReport.objects.create(
            name='Report', status='success',
            success_count=8, fail_count=1, error_count=1,
            duration=1.5, summary={},
            testcase=tc, executed_by=self.user,
        )
        execution = ApiTestTaskExecution.objects.create(
            task_suite=suite, executed_by=self.user, total_count=1,
        )
        ApiTestTaskCaseResult.objects.create(
            execution=execution, testcase=tc, report=report,
            status='success',
        )
        response = self.client.get(f'{self.exec_url}{execution.pk}/case-results/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = response.data[0]
        self.assertIsInstance(result['report'], dict)
        self.assertEqual(result['report']['id'], report.pk)
        self.assertEqual(result['report']['name'], 'Report')
        self.assertEqual(result['report']['status'], 'success')
        self.assertEqual(result['report']['success_count'], 8)
        self.assertEqual(result['report']['fail_count'], 1)
        self.assertEqual(result['report']['error_count'], 1)
        self.assertIn('success_rate', result['report'])
        self.assertIn('duration', result['report'])

    def test_case_result_report_null_when_no_report(self):
        """Case result returns null for report when no report is attached."""
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        execution = ApiTestTaskExecution.objects.create(
            task_suite=suite, executed_by=self.user, total_count=1,
        )
        ApiTestTaskCaseResult.objects.create(
            execution=execution, testcase=tc, status='pending',
        )
        response = self.client.get(f'{self.exec_url}{execution.pk}/case-results/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = response.data[0]
        self.assertIsNone(result['report'])

    # --- Report serializer success_rate format ---

    def test_report_success_rate_format_partial(self):
        """Report success_rate returns string like '0.80' for 80% success."""
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        report = ApiTestReport.objects.create(
            name='Report', status='success',
            success_count=8, fail_count=1, error_count=1,
            duration=1.5, summary={},
            testcase=tc, executed_by=self.user,
        )
        execution = ApiTestTaskExecution.objects.create(
            task_suite=suite, executed_by=self.user, total_count=1,
        )
        ApiTestTaskCaseResult.objects.create(
            execution=execution, testcase=tc, report=report,
            status='success',
        )
        response = self.client.get(f'{self.exec_url}{execution.pk}/case-results/')
        rate = response.data[0]['report']['success_rate']
        self.assertEqual(rate, '0.80')

    def test_report_success_rate_format_perfect(self):
        """Report success_rate returns '1' for 100% success."""
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        report = ApiTestReport.objects.create(
            name='Report', status='success',
            success_count=5, fail_count=0, error_count=0,
            duration=1.0, summary={},
            testcase=tc, executed_by=self.user,
        )
        execution = ApiTestTaskExecution.objects.create(
            task_suite=suite, executed_by=self.user, total_count=1,
        )
        ApiTestTaskCaseResult.objects.create(
            execution=execution, testcase=tc, report=report,
            status='success',
        )
        response = self.client.get(f'{self.exec_url}{execution.pk}/case-results/')
        rate = response.data[0]['report']['success_rate']
        self.assertEqual(rate, '1')

    def test_report_success_rate_format_zero(self):
        """Report success_rate returns '0' when all counts are zero."""
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        report = ApiTestReport.objects.create(
            name='Report', status='error',
            success_count=0, fail_count=0, error_count=0,
            duration=0.0, summary={},
            testcase=tc, executed_by=self.user,
        )
        execution = ApiTestTaskExecution.objects.create(
            task_suite=suite, executed_by=self.user, total_count=1,
        )
        ApiTestTaskCaseResult.objects.create(
            execution=execution, testcase=tc, report=report,
            status='error',
        )
        response = self.client.get(f'{self.exec_url}{execution.pk}/case-results/')
        rate = response.data[0]['report']['success_rate']
        self.assertEqual(rate, '0')

    # --- Execution creation with task_suite_id / environment_id ---

    @patch('api_testtasks.views.execute_api_task_async')
    def test_create_execution_with_environment_id(self, mock_task):
        """Create execution using task_suite_id and environment_id field names."""
        from api_environments.models import ApiEnvironment
        mock_task.delay.return_value = MagicMock(id='celery-task-id')
        env = ApiEnvironment.objects.create(
            name='Test Env', base_url='https://test.example.com',
            project=self.project,
        )
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        ApiTestTaskCase.objects.create(task_suite=suite, testcase=tc, order=1)
        data = {'task_suite_id': suite.pk, 'environment_id': env.pk}
        response = self.client.post(self.exec_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        execution = ApiTestTaskExecution.objects.first()
        self.assertEqual(execution.environment, env)

    @patch('api_testtasks.views.execute_api_task_async')
    def test_create_execution_without_environment_id(self, mock_task):
        """Create execution with just task_suite_id, no environment_id."""
        mock_task.delay.return_value = MagicMock(id='celery-task-id')
        suite = ApiTestTaskSuite.objects.create(
            name='Suite', project=self.project, created_by=self.user,
        )
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        ApiTestTaskCase.objects.create(task_suite=suite, testcase=tc, order=1)
        data = {'task_suite_id': suite.pk}
        response = self.client.post(self.exec_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        execution = ApiTestTaskExecution.objects.first()
        self.assertIsNone(execution.environment)


class ApiTestTaskPermissionTest(TestCase):
    """Project isolation — non-member denied, superuser allowed, cross-project invisible"""

    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username='owner', password='testpass')
        self.project_a = Project.objects.create(name='Project A', creator=self.owner)
        ProjectMember.objects.create(project=self.project_a, user=self.owner, role='admin')

        self.outsider = User.objects.create_user(username='outsider', password='testpass')
        self.superuser = User.objects.create_superuser(username='admin', password='adminpass')

        self.project_b = Project.objects.create(name='Project B', creator=self.outsider)
        ProjectMember.objects.create(project=self.project_b, user=self.outsider, role='admin')

    def test_non_member_denied_suites(self):
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(f'/api/projects/{self.project_a.pk}/api-task-suites/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_member_denied_executions(self):
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(f'/api/projects/{self.project_a.pk}/api-task-executions/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_allowed_suites(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get(f'/api/projects/{self.project_a.pk}/api-task-suites/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_superuser_allowed_executions(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get(f'/api/projects/{self.project_a.pk}/api-task-executions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_project_isolation_suites(self):
        """Suite in project A is NOT visible from project B"""
        ApiTestTaskSuite.objects.create(
            name='A Suite', project=self.project_a, created_by=self.owner,
        )
        self.client.force_authenticate(user=self.outsider)
        _grant_all_testtask_perms(self.outsider)
        response = self.client.get(f'/api/projects/{self.project_b.pk}/api-task-suites/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        items = response.data['results'] if isinstance(response.data, dict) else response.data
        suite_names = [s['name'] for s in items]
        self.assertNotIn('A Suite', suite_names)

    def test_project_isolation_executions(self):
        """Execution in project A is NOT visible from project B"""
        suite_a = ApiTestTaskSuite.objects.create(
            name='A Suite', project=self.project_a, created_by=self.owner,
        )
        ApiTestTaskExecution.objects.create(
            task_suite=suite_a, executed_by=self.owner, total_count=1,
        )
        self.client.force_authenticate(user=self.outsider)
        _grant_all_testtask_perms(self.outsider)
        response = self.client.get(f'/api/projects/{self.project_b.pk}/api-task-executions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        items = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertEqual(len(items), 0)

    def test_member_can_access_own_project(self):
        _grant_all_testtask_perms(self.owner)
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(f'/api/projects/{self.project_a.pk}/api-task-suites/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ApiTestTaskIsolationTest(TestCase):
    """测试任务模块项目隔离测试"""

    def setUp(self):
        self.client = APIClient()
        self.user_a = User.objects.create_user(username='user_a', password='testpass')
        _grant_all_testtask_perms(self.user_a)
        self.project_a = Project.objects.create(name='Project A', creator=self.user_a)
        ProjectMember.objects.create(project=self.project_a, user=self.user_a, role='admin')

        self.user_b = User.objects.create_user(username='user_b', password='testpass')
        self.project_b = Project.objects.create(name='Project B', creator=self.user_b)
        ProjectMember.objects.create(project=self.project_b, user=self.user_b, role='admin')

        self.suite_a = ApiTestTaskSuite.objects.create(
            name='Suite A', project=self.project_a, created_by=self.user_a,
        )
        self.suite_b = ApiTestTaskSuite.objects.create(
            name='Suite B', project=self.project_b, created_by=self.user_b,
        )
        self.testcase_b = ApiTestCase.objects.create(
            name='TC B', project=self.project_b, created_by=self.user_b,
        )

        from api_environments.models import ApiEnvironment
        self.env_b = ApiEnvironment.objects.create(
            name='Env B', base_url='http://b.com',
            project=self.project_b, created_by=self.user_b,
        )

        self.client.force_authenticate(user=self.user_a)
        self.exec_url = f'/api/projects/{self.project_a.pk}/api-task-executions/'
        self.suite_url = f'/api/projects/{self.project_a.pk}/api-task-suites/'

    @patch('api_testtasks.views.execute_api_task_async')
    def test_create_execution_with_cross_project_suite(self, mock_task):
        """创建执行时使用跨项目的 suite 应被拒绝（serializer 校验 400）"""
        # Add a testcase to suite_b so it's not empty
        tc_b = ApiTestCase.objects.create(
            name='TC for B', project=self.project_b, created_by=self.user_b,
        )
        from api_testtasks.models import ApiTestTaskCase
        ApiTestTaskCase.objects.create(
            task_suite=self.suite_b, testcase=tc_b, order=1,
        )
        response = self.client.post(
            self.exec_url,
            {'task_suite_id': self.suite_b.pk},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('api_testtasks.views.execute_api_task_async')
    def test_create_execution_with_cross_project_environment(self, mock_task):
        """创建执行时使用跨项目的 environment 应被拒绝"""
        # Add a testcase to suite_a first
        tc_a = ApiTestCase.objects.create(
            name='TC for A', project=self.project_a, created_by=self.user_a,
        )
        from api_testtasks.models import ApiTestTaskCase
        ApiTestTaskCase.objects.create(
            task_suite=self.suite_a, testcase=tc_a, order=1,
        )
        response = self.client.post(
            self.exec_url,
            {'task_suite_id': self.suite_a.pk, 'environment_id': self.env_b.pk},
            format='json',
        )
        # get_object_or_404 raises Http404 → DRF returns 404
        self.assertIn(response.status_code, [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        ])

    def test_add_testcases_cross_project(self):
        """添加跨项目的 testcase 应被 serializer 拒绝"""
        response = self.client.post(
            f'{self.suite_url}{self.suite_a.pk}/add-testcases/',
            {'testcase_ids': [self.testcase_b.pk]},
            format='json',
        )
        # Serializer validates testcase_ids with project scope → 400
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ApiTestTaskExecutionModelTest(TestCase):
    """ApiTestTaskExecution 模型层补充测试"""

    def setUp(self):
        self.user = User.objects.create_user(username='execuser', password='testpass')
        self.project = Project.objects.create(name='Exec Project', creator=self.user)
        self.suite = ApiTestTaskSuite.objects.create(
            name='Exec Suite', project=self.project, created_by=self.user,
        )

    def test_execution_state_pending_to_running(self):
        """pending → running 状态转换"""
        execution = ApiTestTaskExecution.objects.create(
            task_suite=self.suite, executed_by=self.user,
        )
        self.assertEqual(execution.status, 'pending')
        execution.start()
        execution.refresh_from_db()
        self.assertEqual(execution.status, 'running')
        self.assertIsNotNone(execution.start_time)

    def test_execution_state_running_to_completed(self):
        """running → completed 状态转换"""
        execution = ApiTestTaskExecution.objects.create(
            task_suite=self.suite, executed_by=self.user,
        )
        execution.start()
        execution.complete(success_count=3, fail_count=1, error_count=0)
        execution.refresh_from_db()
        self.assertEqual(execution.status, 'completed')
        self.assertEqual(execution.success_count, 3)
        self.assertEqual(execution.fail_count, 1)
        self.assertIsNotNone(execution.end_time)

    def test_execution_fail_sets_status(self):
        """fail() 设置 status=failed"""
        execution = ApiTestTaskExecution.objects.create(
            task_suite=self.suite, executed_by=self.user,
        )
        execution.start()
        execution.fail()
        execution.refresh_from_db()
        self.assertEqual(execution.status, 'failed')
        self.assertIsNotNone(execution.end_time)

    def test_execution_cancel(self):
        """cancel() 设置 status=canceled"""
        execution = ApiTestTaskExecution.objects.create(
            task_suite=self.suite, executed_by=self.user,
        )
        execution.start()
        execution.cancel()
        execution.refresh_from_db()
        self.assertEqual(execution.status, 'canceled')

    def test_duration_property(self):
        """duration 属性计算正确"""
        execution = ApiTestTaskExecution.objects.create(
            task_suite=self.suite, executed_by=self.user,
        )
        execution.start()
        import time
        time.sleep(0.01)  # small delay
        execution.complete(1, 0, 0)
        self.assertGreater(execution.duration, 0)

    def test_duration_zero_when_not_started(self):
        """未启动时 duration 为 0"""
        execution = ApiTestTaskExecution.objects.create(
            task_suite=self.suite, executed_by=self.user,
        )
        self.assertEqual(execution.duration, 0)

    def test_success_rate_property(self):
        """success_rate 属性计算正确"""
        execution = ApiTestTaskExecution.objects.create(
            task_suite=self.suite, executed_by=self.user,
            total_count=4, success_count=3,
        )
        self.assertEqual(execution.success_rate, 0.75)

    def test_success_rate_zero_when_empty(self):
        """total_count=0 时 success_rate 为 0"""
        execution = ApiTestTaskExecution.objects.create(
            task_suite=self.suite, executed_by=self.user,
        )
        self.assertEqual(execution.success_rate, 0.00)

    def test_execution_project_property(self):
        """execution.project 返回 suite 的 project"""
        execution = ApiTestTaskExecution.objects.create(
            task_suite=self.suite, executed_by=self.user,
        )
        self.assertEqual(execution.project, self.project)

    def test_suite_cascade_delete_executions(self):
        """删除 suite 级联删除 executions"""
        ApiTestTaskExecution.objects.create(
            task_suite=self.suite, executed_by=self.user,
        )
        self.suite.delete()
        self.assertEqual(ApiTestTaskExecution.objects.count(), 0)

    def test_case_result_str(self):
        """ApiTestTaskCaseResult __str__ 格式正确"""
        tc = ApiTestCase.objects.create(
            name='TC1', project=self.project, created_by=self.user,
        )
        execution = ApiTestTaskExecution.objects.create(
            task_suite=self.suite, executed_by=self.user,
        )
        result = ApiTestTaskCaseResult.objects.create(
            execution=execution, testcase=tc,
        )
        self.assertIn('TC1', str(result))


class ApiTestTaskServiceTest(TestCase):
    """ApiTestTaskService 单元测试"""

    def setUp(self):
        self.user = User.objects.create_user(username='tasksvcuser', password='testpass')
        self.project = Project.objects.create(name='TaskSvc Project', creator=self.user)
        self.suite = ApiTestTaskSuite.objects.create(
            name='Svc Suite', project=self.project, created_by=self.user,
        )
        self.tc1 = ApiTestCase.objects.create(
            name='TC1', project=self.project, created_by=self.user,
        )
        self.tc2 = ApiTestCase.objects.create(
            name='TC2', project=self.project, created_by=self.user,
        )
        self.tc3 = ApiTestCase.objects.create(
            name='TC3', project=self.project, created_by=self.user,
        )

    def test_add_testcases_success(self):
        """正常添加，order 正确"""
        result = ApiTestTaskService.add_testcases(
            self.suite, [self.tc1.pk, self.tc2.pk], self.project.pk,
        )
        self.assertEqual(len(result), 2)
        orders = [tc.order for tc in result]
        self.assertEqual(orders, [1, 2])

    def test_add_testcases_skip_duplicates(self):
        """已存在的 testcase 不重复添加"""
        ApiTestTaskService.add_testcases(
            self.suite, [self.tc1.pk], self.project.pk,
        )
        result = ApiTestTaskService.add_testcases(
            self.suite, [self.tc1.pk, self.tc2.pk], self.project.pk,
        )
        # Only tc2 should be newly added
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].testcase_id, self.tc2.pk)

    def test_add_testcases_order_continues(self):
        """追加时 order 从已有最大值继续"""
        ApiTestTaskService.add_testcases(
            self.suite, [self.tc1.pk], self.project.pk,
        )
        result = ApiTestTaskService.add_testcases(
            self.suite, [self.tc2.pk], self.project.pk,
        )
        self.assertEqual(result[0].order, 2)

    def test_remove_testcase_reorders(self):
        """移除后剩余 case 重新排序"""
        ApiTestTaskService.add_testcases(
            self.suite, [self.tc1.pk, self.tc2.pk, self.tc3.pk], self.project.pk,
        )
        success = ApiTestTaskService.remove_testcase(self.suite, self.tc2.pk)
        self.assertTrue(success)
        remaining = list(
            self.suite.api_task_cases.all().order_by('order')
        )
        self.assertEqual(len(remaining), 2)
        self.assertEqual(remaining[0].order, 1)
        self.assertEqual(remaining[1].order, 2)

    def test_remove_nonexistent_returns_false(self):
        """不存在的 testcase → False"""
        success = ApiTestTaskService.remove_testcase(self.suite, 999999)
        self.assertFalse(success)

    def test_add_testcases_nonexistent_id_skipped(self):
        """不存在的 testcase_id 被跳过"""
        result = ApiTestTaskService.add_testcases(
            self.suite, [999999, self.tc1.pk], self.project.pk,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].testcase_id, self.tc1.pk)


class ApiTestTaskExecutionServiceTest(TestCase):
    """ApiTestTaskExecutionService 单元测试"""

    def setUp(self):
        self.user = User.objects.create_user(username='execsvcuser', password='testpass')
        self.project = Project.objects.create(name='ExecSvc Project', creator=self.user)
        self.suite = ApiTestTaskSuite.objects.create(
            name='ExecSvc Suite', project=self.project, created_by=self.user,
        )
        self.tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        from api_testtasks.models import ApiTestTaskCase
        ApiTestTaskCase.objects.create(
            task_suite=self.suite, testcase=self.tc, order=1,
        )

    def test_create_execution(self):
        """创建 execution + case_results"""
        execution = ApiTestTaskExecutionService.create_execution(
            self.suite, user=self.user,
        )
        self.assertEqual(execution.status, 'pending')
        self.assertEqual(execution.total_count, 1)
        self.assertEqual(execution.api_case_results.count(), 1)
        case_result = execution.api_case_results.first()
        self.assertEqual(case_result.testcase, self.tc)
        self.assertEqual(case_result.status, 'pending')

    def test_create_execution_with_environment(self):
        """创建带环境的 execution"""
        from api_environments.models import ApiEnvironment
        env = ApiEnvironment.objects.create(
            name='Test Env', base_url='http://test.com',
            project=self.project, created_by=self.user,
        )
        execution = ApiTestTaskExecutionService.create_execution(
            self.suite, environment_id=env.pk, user=self.user,
        )
        self.assertEqual(execution.environment_id, env.pk)

    @patch('api_testcases.services.TestExecutionService')
    def test_execute_task_success(self, mock_exec_svc):
        """execute_task 全部通过"""
        # Need a real report for FK assignment in case_result.save()
        report = ApiTestReport.objects.create(
            name='Mock Report', status='success',
            success_count=1, fail_count=0, error_count=0,
            duration=0.5, summary={}, testcase=self.tc,
            executed_by=self.user,
        )
        mock_exec_svc.run_testcase.return_value = report

        execution = ApiTestTaskExecutionService.create_execution(
            self.suite, user=self.user,
        )
        ApiTestTaskExecutionService.execute_task(execution)
        execution.refresh_from_db()
        self.assertEqual(execution.status, 'completed')
        self.assertEqual(execution.success_count, 1)
        self.assertEqual(execution.fail_count, 0)

    @patch('api_testcases.services.TestExecutionService')
    def test_execute_task_error_handling(self, mock_exec_svc):
        """异常时 execution 状态更新为 error"""
        mock_exec_svc.run_testcase.side_effect = Exception('Runner crash')

        execution = ApiTestTaskExecutionService.create_execution(
            self.suite, user=self.user,
        )
        ApiTestTaskExecutionService.execute_task(execution)
        execution.refresh_from_db()
        self.assertEqual(execution.status, 'completed')
        self.assertEqual(execution.error_count, 1)

    def test_execute_task_async_not_found(self):
        """execute_task_async 传入不存在的 ID 不崩溃"""
        # Should log error but not raise
        ApiTestTaskExecutionService.execute_task_async(999999)


class ApiTestTaskSerializerTest(TestCase):
    """ApiTestTask serializer 验证测试"""

    def setUp(self):
        self.user = User.objects.create_user(username='seruser', password='testpass')
        self.project = Project.objects.create(name='Ser Project', creator=self.user)
        self.tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )

    def test_validate_testcase_ids_empty(self):
        """空 testcase_ids 通过 serializer 验证但计数匹配"""
        from api_testtasks.serializers import ApiTestTaskCaseCreateSerializer
        serializer = ApiTestTaskCaseCreateSerializer(
            data={'testcase_ids': []},
            context={'project_pk': self.project.pk},
        )
        # Empty list is valid per serializer (count=0 == len([])=0)
        # The view layer handles this by returning an empty result
        self.assertTrue(serializer.is_valid())

    def test_validate_testcase_ids_nonexistent(self):
        """不存在的 testcase_ids 被拒绝"""
        from api_testtasks.serializers import ApiTestTaskCaseCreateSerializer
        serializer = ApiTestTaskCaseCreateSerializer(
            data={'testcase_ids': [999999]},
            context={'project_pk': self.project.pk},
        )
        self.assertFalse(serializer.is_valid())

    def test_validate_testcase_ids_success(self):
        """有效的 testcase_ids 通过验证"""
        from api_testtasks.serializers import ApiTestTaskCaseCreateSerializer
        serializer = ApiTestTaskCaseCreateSerializer(
            data={'testcase_ids': [self.tc.pk]},
            context={'project_pk': self.project.pk},
        )
        self.assertTrue(serializer.is_valid())

    def test_validate_suite_id_cross_project(self):
        """校验 project2 的 suite_id 失败"""
        from api_testtasks.serializers import ApiTestTaskExecutionCreateSerializer
        other_project = Project.objects.create(name='Other', creator=self.user)
        other_suite = ApiTestTaskSuite.objects.create(
            name='Other Suite', project=other_project, created_by=self.user,
        )
        serializer = ApiTestTaskExecutionCreateSerializer(
            data={'task_suite_id': other_suite.pk},
            context={'project_pk': self.project.pk},
        )
        self.assertFalse(serializer.is_valid())
