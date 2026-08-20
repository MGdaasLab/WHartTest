import json
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient
from rest_framework import status

from projects.models import Project, ProjectMember
from api_interfaces.models import ApiInterface
from .models import (
    ApiTestCaseTag, ApiTestCaseGroup, ApiTestCase,
    ApiTestCaseStep, ApiTestReport, ApiTestReportDetail,
    ApiInterfaceCase, ApiInterfaceCaseStep,
    ApiInterfaceCaseReport, ApiInterfaceCaseReportDetail,
)
from .runner import TestCaseRunner
from .services import TestCaseService, TestExecutionService, InterfaceCaseExecutionService


def _grant_model_perms(user, model_class):
    """授予用户对指定模型的全部权限。"""
    ct = ContentType.objects.get_for_model(model_class)
    perms = Permission.objects.filter(content_type=ct)
    user.user_permissions.add(*perms)


def _grant_all_testcase_perms(user):
    """授予用户 api_testcases 和相关模型的全部权限。"""
    for model_cls in [
        ApiTestCaseTag, ApiTestCaseGroup, ApiTestCase,
        ApiTestCaseStep, ApiTestReport, ApiTestReportDetail,
        ApiInterfaceCase, ApiInterfaceCaseStep,
        ApiInterfaceCaseReport, ApiInterfaceCaseReportDetail,
    ]:
        _grant_model_perms(user, model_cls)
    _grant_model_perms(user, ApiInterface)
    # Clear Django's permission cache
    for attr in ('_perm_cache', '_user_perm_cache'):
        try:
            delattr(user, attr)
        except AttributeError:
            pass


class ApiTestCaseTagModelTest(TestCase):
    """ApiTestCaseTag model tests"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)

    def test_create_tag(self):
        tag = ApiTestCaseTag.objects.create(
            name='smoke', project=self.project, created_by=self.user,
        )
        self.assertEqual(tag.name, 'smoke')
        self.assertEqual(tag.color, '#1890ff')

    def test_str_representation(self):
        tag = ApiTestCaseTag.objects.create(
            name='regression', project=self.project, created_by=self.user,
        )
        self.assertEqual(str(tag), 'regression')

    def test_unique_together_name_project(self):
        ApiTestCaseTag.objects.create(
            name='dup', project=self.project, created_by=self.user,
        )
        with self.assertRaises(Exception):
            ApiTestCaseTag.objects.create(
                name='dup', project=self.project, created_by=self.user,
            )

    def test_ordering(self):
        t2 = ApiTestCaseTag.objects.create(
            name='zzz', project=self.project, created_by=self.user,
        )
        t1 = ApiTestCaseTag.objects.create(
            name='aaa', project=self.project, created_by=self.user,
        )
        tags = list(ApiTestCaseTag.objects.filter(project=self.project))
        self.assertEqual(tags[0], t1)
        self.assertEqual(tags[1], t2)


class ApiTestCaseGroupModelTest(TestCase):
    """ApiTestCaseGroup model tests"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)

    def test_create_group(self):
        group = ApiTestCaseGroup.objects.create(
            name='Auth Tests', project=self.project, created_by=self.user,
        )
        self.assertEqual(group.name, 'Auth Tests')
        self.assertIsNone(group.parent)

    def test_str_representation(self):
        group = ApiTestCaseGroup.objects.create(
            name='API Tests', project=self.project, created_by=self.user,
        )
        self.assertEqual(str(group), 'API Tests')

    def test_get_full_path(self):
        parent = ApiTestCaseGroup.objects.create(
            name='Root', project=self.project, created_by=self.user,
        )
        child = ApiTestCaseGroup.objects.create(
            name='Child', parent=parent, project=self.project, created_by=self.user,
        )
        self.assertEqual(child.get_full_path(), 'Root / Child')

    def test_get_full_path_three_levels(self):
        root = ApiTestCaseGroup.objects.create(
            name='A', project=self.project, created_by=self.user,
        )
        mid = ApiTestCaseGroup.objects.create(
            name='B', parent=root, project=self.project, created_by=self.user,
        )
        leaf = ApiTestCaseGroup.objects.create(
            name='C', parent=mid, project=self.project, created_by=self.user,
        )
        self.assertEqual(leaf.get_full_path(), 'A / B / C')

    def test_unique_together(self):
        parent = ApiTestCaseGroup.objects.create(
            name='Root', project=self.project, created_by=self.user,
        )
        ApiTestCaseGroup.objects.create(
            name='Dup', parent=parent, project=self.project, created_by=self.user,
        )
        with self.assertRaises(Exception):
            ApiTestCaseGroup.objects.create(
                name='Dup', parent=parent, project=self.project, created_by=self.user,
            )

    def test_cascade_delete_parent(self):
        parent = ApiTestCaseGroup.objects.create(
            name='Parent', project=self.project, created_by=self.user,
        )
        ApiTestCaseGroup.objects.create(
            name='Child', parent=parent, project=self.project, created_by=self.user,
        )
        parent.delete()
        self.assertEqual(
            ApiTestCaseGroup.objects.filter(project=self.project).count(), 0
        )


class ApiTestCaseModelTest(TestCase):
    """ApiTestCase model tests"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)

    def test_create_testcase(self):
        tc = ApiTestCase.objects.create(
            name='Login Test', project=self.project, created_by=self.user,
        )
        self.assertEqual(tc.name, 'Login Test')
        self.assertEqual(tc.priority, 'P2')
        self.assertEqual(tc.config, {})

    def test_str_representation(self):
        tc = ApiTestCase.objects.create(
            name='My Test', project=self.project, created_by=self.user,
        )
        self.assertEqual(str(tc), 'My Test')

    def test_unique_together_name_project(self):
        ApiTestCase.objects.create(
            name='Dup', project=self.project, created_by=self.user,
        )
        with self.assertRaises(Exception):
            ApiTestCase.objects.create(
                name='Dup', project=self.project, created_by=self.user,
            )

    def test_priority_choices(self):
        tc = ApiTestCase.objects.create(
            name='P0 Test', priority='P0',
            project=self.project, created_by=self.user,
        )
        self.assertEqual(tc.priority, 'P0')

    def test_tags_many_to_many(self):
        tag1 = ApiTestCaseTag.objects.create(
            name='smoke', project=self.project, created_by=self.user,
        )
        tag2 = ApiTestCaseTag.objects.create(
            name='regression', project=self.project, created_by=self.user,
        )
        tc = ApiTestCase.objects.create(
            name='Tagged Test', project=self.project, created_by=self.user,
        )
        tc.tags.add(tag1, tag2)
        self.assertEqual(tc.tags.count(), 2)

    def test_group_set_null(self):
        group = ApiTestCaseGroup.objects.create(
            name='Group', project=self.project, created_by=self.user,
        )
        tc = ApiTestCase.objects.create(
            name='Grouped Test', group=group,
            project=self.project, created_by=self.user,
        )
        group.delete()
        tc.refresh_from_db()
        self.assertIsNone(tc.group)


class ApiTestCaseStepModelTest(TestCase):
    """ApiTestCaseStep model tests"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)
        self.testcase = ApiTestCase.objects.create(
            name='Test Case', project=self.project, created_by=self.user,
        )
        self.interface = ApiInterface.objects.create(
            name='API', type='http', method='GET',
            url='http://example.com', project=self.project,
            created_by=self.user,
        )

    def test_create_step(self):
        step = ApiTestCaseStep.objects.create(
            name='Step 1', order=1,
            interface_data={'method': 'GET', 'url': 'http://example.com'},
            testcase=self.testcase, origin_interface=self.interface,
        )
        self.assertEqual(step.name, 'Step 1')
        self.assertEqual(step.sync_fields, [])

    def test_str_representation(self):
        step = ApiTestCaseStep.objects.create(
            name='Login Step', order=1,
            interface_data={'method': 'POST'},
            testcase=self.testcase,
        )
        self.assertEqual(str(step), 'Test Case-Login Step')

    def test_unique_together_testcase_order(self):
        ApiTestCaseStep.objects.create(
            name='Step 1', order=1,
            interface_data={'method': 'GET'},
            testcase=self.testcase,
        )
        with self.assertRaises(Exception):
            ApiTestCaseStep.objects.create(
                name='Step 2', order=1,
                interface_data={'method': 'POST'},
                testcase=self.testcase,
            )

    def test_origin_interface_set_null(self):
        step = ApiTestCaseStep.objects.create(
            name='Step 1', order=1,
            interface_data={'method': 'GET'},
            testcase=self.testcase, origin_interface=self.interface,
        )
        self.interface.delete()
        step.refresh_from_db()
        self.assertIsNone(step.origin_interface)

    def test_cascade_delete_testcase(self):
        ApiTestCaseStep.objects.create(
            name='Step 1', order=1,
            interface_data={'method': 'GET'},
            testcase=self.testcase,
        )
        self.testcase.delete()
        self.assertEqual(ApiTestCaseStep.objects.count(), 0)


class ApiTestReportModelTest(TestCase):
    """ApiTestReport model tests"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)
        self.testcase = ApiTestCase.objects.create(
            name='Test Case', project=self.project, created_by=self.user,
        )

    def test_create_report(self):
        report = ApiTestReport.objects.create(
            name='Report 1',
            status='success',
            success_count=3, fail_count=0, error_count=0,
            duration=1.5,
            summary={'total': 3},
            testcase=self.testcase,
            executed_by=self.user,
        )
        self.assertEqual(report.status, 'success')
        self.assertEqual(report.duration, 1.5)

    def test_str_representation(self):
        report = ApiTestReport.objects.create(
            name='My Report',
            status='failure',
            success_count=1, fail_count=2, error_count=0,
            duration=2.0,
            summary={},
            testcase=self.testcase,
            executed_by=self.user,
        )
        self.assertEqual(str(report), 'My Report')

    def test_cascade_delete_testcase(self):
        ApiTestReport.objects.create(
            name='Report',
            status='success',
            success_count=1, fail_count=0, error_count=0,
            duration=0.5,
            summary={},
            testcase=self.testcase,
            executed_by=self.user,
        )
        self.testcase.delete()
        self.assertEqual(ApiTestReport.objects.count(), 0)


class ApiTestReportDetailModelTest(TestCase):
    """ApiTestReportDetail model tests"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)
        self.testcase = ApiTestCase.objects.create(
            name='Test Case', project=self.project, created_by=self.user,
        )
        self.step = ApiTestCaseStep.objects.create(
            name='Step 1', order=1,
            interface_data={'method': 'GET'},
            testcase=self.testcase,
        )
        self.report = ApiTestReport.objects.create(
            name='Report',
            status='success',
            success_count=1, fail_count=0, error_count=0,
            duration=0.5,
            summary={},
            testcase=self.testcase,
            executed_by=self.user,
        )

    def test_create_detail(self):
        detail = ApiTestReportDetail.objects.create(
            report=self.report,
            step=self.step,
            success=True,
            elapsed=0.3,
            request={'method': 'GET', 'url': 'http://example.com'},
            response={'status_code': 200, 'body': '{}'},
        )
        self.assertTrue(detail.success)
        self.assertEqual(detail.elapsed, 0.3)

    def test_str_representation(self):
        detail = ApiTestReportDetail.objects.create(
            report=self.report,
            step=self.step,
            success=True,
            elapsed=0.1,
            request={},
            response={},
        )
        self.assertEqual(str(detail), 'Report-Step 1')

    def test_cascade_delete_report(self):
        ApiTestReportDetail.objects.create(
            report=self.report,
            step=self.step,
            success=True,
            elapsed=0.1,
            request={},
            response={},
        )
        self.report.delete()
        self.assertEqual(ApiTestReportDetail.objects.count(), 0)

    def test_step_set_null(self):
        detail = ApiTestReportDetail.objects.create(
            report=self.report,
            step=self.step,
            success=True,
            elapsed=0.1,
            request={},
            response={},
        )
        self.step.delete()
        detail.refresh_from_db()
        self.assertIsNone(detail.step)


class TestCaseServiceTest(TestCase):
    """TestCaseService tests"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)
        self.interface = ApiInterface.objects.create(
            name='API', type='http', method='GET',
            url='http://example.com/api',
            headers={}, params={}, body={'type': 'raw', 'content': ''},
            validators=[], extract={},
            setup_hooks=[], teardown_hooks=[], variables={},
            project=self.project,
            created_by=self.user,
        )

    def test_validate_testcase_data_valid(self):
        data = {
            'name': 'Test',
            'project': self.project.pk,
            'steps_info': [{'name': 'Step 1', 'interface_id': self.interface.pk}],
        }
        valid, error = TestCaseService.validate_testcase_data(data)
        self.assertTrue(valid)
        self.assertIsNone(error)

    def test_validate_testcase_data_missing_name(self):
        data = {
            'project': self.project.pk,
            'steps_info': [{'name': 'Step', 'interface_id': 1}],
        }
        valid, error = TestCaseService.validate_testcase_data(data)
        self.assertFalse(valid)
        self.assertIn('name', error)

    def test_validate_testcase_data_no_steps(self):
        data = {'name': 'Test', 'project': self.project.pk}
        valid, error = TestCaseService.validate_testcase_data(data)
        self.assertFalse(valid)
        self.assertIn('step', error.lower())

    def test_validate_testcase_data_step_missing_name(self):
        data = {
            'name': 'Test',
            'project': self.project.pk,
            'steps_info': [{'interface_id': 1}],
        }
        valid, error = TestCaseService.validate_testcase_data(data)
        self.assertFalse(valid)
        self.assertIn('name', error.lower())

    def test_validate_testcase_data_step_missing_interface_id(self):
        data = {
            'name': 'Test',
            'project': self.project.pk,
            'steps_info': [{'name': 'Step 1'}],
        }
        valid, error = TestCaseService.validate_testcase_data(data)
        self.assertFalse(valid)
        self.assertIn('interface_id', error)

    def test_create_testcase(self):
        data = {
            'name': 'Created Test',
            'project': self.project,
            'steps_info': [
                {'name': 'Step 1', 'interface_id': self.interface.pk},
            ],
        }
        tc = TestCaseService.create_testcase(data, self.user)
        self.assertEqual(tc.name, 'Created Test')
        self.assertEqual(tc.steps.count(), 1)
        step = tc.steps.first()
        self.assertEqual(step.origin_interface, self.interface)


class TestExecutionServiceTest(TestCase):
    """TestExecutionService tests"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)

    def test_prepare_config_defaults(self):
        config = TestExecutionService._prepare_config({}, None)
        self.assertEqual(config['base_url'], '')
        self.assertFalse(config['verify'])
        self.assertEqual(config['variables'], {})

    def test_prepare_config_with_environment(self):
        config = TestExecutionService._prepare_config(
            {'base_url': 'http://case.com'},
            {'base_url': 'http://env.com', 'variables': {'key': 'val'}},
        )
        self.assertEqual(config['base_url'], 'http://case.com')
        self.assertEqual(config['variables']['key'], 'val')

    def test_prepare_config_env_overridden_by_case(self):
        config = TestExecutionService._prepare_config(
            {'variables': {'key': 'case_val'}},
            {'variables': {'key': 'env_val'}},
        )
        self.assertEqual(config['variables']['key'], 'case_val')

    def test_get_statistics_empty(self):
        stats = TestExecutionService.get_statistics([])
        self.assertEqual(stats['total'], 0)
        self.assertEqual(stats['success_rate'], '0%')

    def test_get_statistics_with_reports(self):
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        r1 = ApiTestReport.objects.create(
            name='R1', status='success',
            success_count=1, fail_count=0, error_count=0,
            duration=0.5, summary={}, testcase=tc, executed_by=self.user,
        )
        r2 = ApiTestReport.objects.create(
            name='R2', status='failure',
            success_count=0, fail_count=1, error_count=0,
            duration=0.5, summary={}, testcase=tc, executed_by=self.user,
        )
        stats = TestExecutionService.get_statistics([r1, r2])
        self.assertEqual(stats['total'], 2)
        self.assertEqual(stats['success'], 1)
        self.assertEqual(stats['failure'], 1)
        self.assertEqual(stats['success_rate'], '50.00%')

    @patch('api_testcases.services.TestCaseRunner')
    def test_run_testcase_report_uses_assertions_instead_of_status_code(self, mock_runner_class):
        testcase = ApiTestCase.objects.create(
            name='Expected 500 Test', project=self.project, created_by=self.user,
        )
        step = ApiTestCaseStep.objects.create(
            name='Step 1', order=1,
            interface_data={'method': 'GET', 'url': '/expected-error'},
            testcase=testcase,
        )

        step_results = [{
            'name': step.name,
            'success': True,
            'elapsed': 0.12,
            'step_type': 'request',
            'data': {
                'request': {
                    'method': 'GET',
                    'url': 'http://example.com/expected-error',
                    'headers': {},
                    'body': None,
                },
                'response': {
                    'status_code': 500,
                    'headers': {},
                    'body': {'message': 'expected error'},
                    'content_size': 32,
                    'response_time_ms': 120,
                },
                'validators': {
                    'success': True,
                    'validate_extractor': [{'check_result': 'pass'}],
                },
                'extracted_variables': {},
            },
            'attachment': '',
        }]
        summary = {
            'success': True,
            'name': testcase.name,
            'time': {'start_at': '2026-04-29T00:00:00', 'duration': 0.12},
            'in_out': {'config_vars': {}, 'export_vars': {}},
            'log': '',
            'step_results': step_results,
        }

        mock_runner = MagicMock()
        mock_runner.run_testcase.return_value = mock_runner
        mock_runner.get_summary.return_value = summary
        mock_runner.get_step_results.return_value = step_results
        mock_runner_class.return_value = mock_runner

        report = TestExecutionService.run_testcase(testcase, user=self.user)

        self.assertEqual(report.status, 'success')
        self.assertEqual(report.success_count, 1)
        self.assertEqual(report.fail_count, 0)

        detail = report.details.get()
        self.assertTrue(detail.success)
        self.assertEqual(detail.response['status_code'], 500)


class TestExecutionConfigSslTest(TestCase):
    """SSL verify precedence tests for testcase execution."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)

    def test_prepare_config_testcase_verify_overrides_environment(self):
        config = TestExecutionService._prepare_config(
            {'verify': True},
            {'verify_ssl': False},
        )

        self.assertTrue(config['verify'])

    def test_prepare_config_uses_environment_verify_when_case_missing(self):
        config = TestExecutionService._prepare_config(
            {},
            {'verify_ssl': False},
        )

        self.assertFalse(config['verify'])

    def test_prepare_config_can_enable_verify_from_environment(self):
        config = TestExecutionService._prepare_config(
            {},
            {'verify_ssl': True},
        )

        self.assertTrue(config['verify'])

    @patch('api_testcases.runner.TestCaseRunner.test_start')
    def test_runner_keeps_testcase_verify_over_environment(self, mock_test_start):
        testcase = ApiTestCase.objects.create(
            name='SSL Test',
            project=self.project,
            created_by=self.user,
            config={'verify': True},
        )
        ApiTestCaseStep.objects.create(
            name='Step 1',
            order=1,
            interface_data={'method': 'GET', 'url': '/oauth/token'},
            testcase=testcase,
        )

        runner = TestCaseRunner(testcase)
        runner.run_testcase({'verify_ssl': False})

        self.assertTrue(runner.config.struct().verify)
        mock_test_start.assert_called_once()

    @patch('api_testcases.runner.TestCaseRunner.test_start')
    def test_runner_uses_environment_verify_when_case_missing(self, mock_test_start):
        testcase = ApiTestCase.objects.create(
            name='SSL Env Test',
            project=self.project,
            created_by=self.user,
            config={},
        )
        ApiTestCaseStep.objects.create(
            name='Step 1',
            order=1,
            interface_data={'method': 'GET', 'url': '/oauth/token'},
            testcase=testcase,
        )

        runner = TestCaseRunner(testcase)
        runner.run_testcase({'verify_ssl': False})

        self.assertFalse(runner.config.struct().verify)
        mock_test_start.assert_called_once()

    @patch('api_testcases.runner.TestCaseRunner.test_start')
    def test_runner_can_enable_verify_from_environment(self, mock_test_start):
        testcase = ApiTestCase.objects.create(
            name='SSL Env On Test',
            project=self.project,
            created_by=self.user,
            config={},
        )
        ApiTestCaseStep.objects.create(
            name='Step 1',
            order=1,
            interface_data={'method': 'GET', 'url': '/oauth/token'},
            testcase=testcase,
        )

        runner = TestCaseRunner(testcase)
        runner.run_testcase({'verify_ssl': True})

        self.assertTrue(runner.config.struct().verify)
        mock_test_start.assert_called_once()

    @patch('api_testcases.runner.TestCaseRunner.test_start')
    def test_runner_preserves_validator_expected_value_type_meta(self, mock_test_start):
        testcase = ApiTestCase.objects.create(
            name='Validator Meta Test',
            project=self.project,
            created_by=self.user,
            config={},
        )
        ApiTestCaseStep.objects.create(
            name='Step 1',
            order=1,
            interface_data={
                'method': 'GET',
                'url': '/oauth/token',
                'validators': [{
                    'gt': ['body.count', '${min_count}'],
                    '__expected_value_type': 'number',
                }],
            },
            testcase=testcase,
        )

        runner = TestCaseRunner(testcase)

        self.assertEqual(
            runner.teststeps[0].struct().validators,
            [{
                'gt': ['body.count', '${min_count}'],
                '__expected_value_type': 'number',
            }],
        )


class TestCaseRunnerSummaryTest(TestCase):
    """TestCaseRunner summary/result tests."""

    @staticmethod
    def _build_request_step_result(
        status_code=500,
        success=True,
        validators=None,
        response_body=None,
        response_error=None,
        response_error_type=None,
        is_transport_error=False,
    ):
        if response_body is None:
            response_body = {'message': 'expected'}

        return SimpleNamespace(
            name='Step 1',
            step_type='request',
            success=success,
            elapsed=0.25,
            export_vars={},
            attachment='',
            data=SimpleNamespace(
                validators=validators or {'success': True},
                req_resps=[
                    SimpleNamespace(
                        request=SimpleNamespace(
                            method='GET',
                            url='http://example.com/error',
                            headers={},
                            body=None,
                        ),
                        response=SimpleNamespace(
                            status_code=status_code,
                            headers={},
                            body=response_body,
                            error=response_error,
                            error_type=response_error_type,
                            is_transport_error=is_transport_error,
                        ),
                    )
                ],
                stat=SimpleNamespace(content_size=16, response_time_ms=250),
            ),
        )

    @patch('api_testcases.runner.HttpRunner.get_summary')
    def test_get_step_results_uses_assertions_not_status_code(self, mock_get_summary):
        mock_get_summary.return_value = SimpleNamespace(
            step_results=[self._build_request_step_result(status_code=500, success=True)],
        )

        runner = TestCaseRunner.__new__(TestCaseRunner)
        results = runner.get_step_results()

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]['success'])
        self.assertEqual(results[0]['data']['response']['status_code'], 500)

    @patch('api_testcases.runner.HttpRunner.get_summary')
    def test_get_step_results_recovers_request_body_on_transport_failure(
        self,
        mock_get_summary,
    ):
        mock_get_summary.return_value = SimpleNamespace(
            step_results=[
                self._build_request_step_result(
                    status_code=0,
                    success=True,
                    response_body={
                        'transport_error': {
                            'type': 'ConnectionError',
                            'message': 'connection refused',
                        },
                    },
                    response_error='connection refused',
                    response_error_type='ConnectionError',
                    is_transport_error=True,
                )
            ],
        )

        runner = TestCaseRunner.__new__(TestCaseRunner)
        runner.trace_id = 'tc-test'
        runner.testcase = SimpleNamespace(id=123)
        runner.step_body_diagnostics = [{
            'prepared': True,
            'target': 'data',
            'prepared_summary': {'type': 'dict', 'size': 1},
        }]
        runner.step_request_snapshots = [{
            'method': 'POST',
            'url': 'http://example.com/error',
            'headers': {'Authorization': 'Bearer token'},
            'body': {'username': 'tester'},
        }]

        results = runner.get_step_results()

        self.assertFalse(results[0]['success'])
        self.assertEqual(results[0]['data']['response']['status_code'], 0)
        self.assertEqual(
            results[0]['data']['request']['headers'],
            {'Authorization': 'Bearer token'},
        )
        self.assertEqual(
            results[0]['data']['request']['body'],
            {'username': 'tester'},
        )
        self.assertTrue(results[0]['data']['response']['is_transport_error'])
        self.assertEqual(
            results[0]['data']['response']['error_type'],
            'ConnectionError',
        )
        self.assertEqual(
            results[0]['data']['response']['error'],
            'connection refused',
        )
        self.assertEqual(
            results[0]['data']['response']['body']['transport_error']['message'],
            'connection refused',
        )

    @patch('api_testcases.runner.HttpRunner.get_summary')
    def test_get_summary_uses_step_assertions_not_status_code(self, mock_get_summary):
        mock_get_summary.return_value = SimpleNamespace(
            name='Expected Error Test',
            time=SimpleNamespace(start_at='2026-04-29T00:00:00', duration=0.25),
            in_out=SimpleNamespace(config_vars={}, export_vars={}),
            log='',
            step_results=[self._build_request_step_result(status_code=500, success=True)],
        )

        runner = TestCaseRunner.__new__(TestCaseRunner)
        summary = runner.get_summary()

        self.assertTrue(summary['success'])
        self.assertEqual(summary['step_results'][0]['data']['response']['status_code'], 500)


class ApiTestCaseTagAPITest(TestCase):
    """ApiTestCaseTag API tests"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='apiuser', password='testpass')
        self.project = Project.objects.create(name='API Project', creator=self.user)
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        _grant_all_testcase_perms(self.user)
        self.client.force_authenticate(user=self.user)
        self.base_url = f'/api/projects/{self.project.pk}/api-testcase-tags/'

    def test_list_tags(self):
        ApiTestCaseTag.objects.create(
            name='smoke', project=self.project, created_by=self.user,
        )
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_tag(self):
        data = {'name': 'new_tag', 'color': '#ff0000', 'project': self.project.pk}
        response = self.client.post(self.base_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        tag = ApiTestCaseTag.objects.get(name='new_tag')
        self.assertEqual(tag.project, self.project)
        self.assertEqual(tag.created_by, self.user)

    def test_statistics(self):
        tag = ApiTestCaseTag.objects.create(
            name='smoke', project=self.project, created_by=self.user,
        )
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        tc.tags.add(tag)
        response = self.client.get(f'{self.base_url}statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]['usage_count'], 1)

    def test_delete_tag(self):
        tag = ApiTestCaseTag.objects.create(
            name='to_delete', project=self.project, created_by=self.user,
        )
        response = self.client.delete(f'{self.base_url}{tag.pk}/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])


class ApiTestCaseGroupAPITest(TestCase):
    """ApiTestCaseGroup API tests"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='apiuser', password='testpass')
        self.project = Project.objects.create(name='API Project', creator=self.user)
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        _grant_all_testcase_perms(self.user)
        self.client.force_authenticate(user=self.user)
        self.base_url = f'/api/projects/{self.project.pk}/api-testcase-groups/'

    def test_list_groups(self):
        ApiTestCaseGroup.objects.create(
            name='Group 1', project=self.project, created_by=self.user,
        )
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_group(self):
        data = {'name': 'New Group', 'project': self.project.pk}
        response = self.client.post(self.base_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        group = ApiTestCaseGroup.objects.get(name='New Group')
        self.assertEqual(group.project, self.project)

    def test_tree(self):
        parent = ApiTestCaseGroup.objects.create(
            name='Root', project=self.project, created_by=self.user,
        )
        ApiTestCaseGroup.objects.create(
            name='Child', parent=parent, project=self.project, created_by=self.user,
        )
        response = self.client.get(f'{self.base_url}tree/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)  # only root groups
        self.assertEqual(response.data[0]['name'], 'Root')

    def test_testcases_action(self):
        group = ApiTestCaseGroup.objects.create(
            name='Group', project=self.project, created_by=self.user,
        )
        ApiTestCase.objects.create(
            name='TC in group', group=group,
            project=self.project, created_by=self.user,
        )
        response = self.client.get(f'{self.base_url}{group.pk}/testcases/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class ApiTestCaseAPITest(TestCase):
    """ApiTestCase API tests"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='apiuser', password='testpass')
        self.project = Project.objects.create(name='API Project', creator=self.user)
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        _grant_all_testcase_perms(self.user)
        self.client.force_authenticate(user=self.user)
        self.interface = ApiInterface.objects.create(
            name='API', type='http', method='GET',
            url='http://example.com',
            headers={}, params={}, body={'type': 'raw', 'content': ''},
            validators=[], extract={},
            setup_hooks=[], teardown_hooks=[], variables={},
            project=self.project, created_by=self.user,
        )
        self.base_url = f'/api/projects/{self.project.pk}/api-testcases/'

    def test_list_testcases(self):
        ApiTestCase.objects.create(
            name='TC1', project=self.project, created_by=self.user,
        )
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_testcase(self):
        data = {
            'name': 'New TC',
            'priority': 'P1',
            'project': self.project.pk,
            'steps_info': [
                {'name': 'Step 1', 'interface_id': self.interface.pk},
            ],
        }
        response = self.client.post(self.base_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        tc = ApiTestCase.objects.get(name='New TC')
        self.assertEqual(tc.project, self.project)
        self.assertEqual(tc.created_by, self.user)
        self.assertEqual(tc.steps.count(), 1)

    def test_create_testcase_no_steps(self):
        data = {'name': 'No Steps TC', 'project': self.project.pk}
        response = self.client.post(self.base_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        tc = ApiTestCase.objects.get(name='No Steps TC')
        self.assertEqual(tc.steps.count(), 0)

    def test_retrieve_testcase(self):
        tc = ApiTestCase.objects.create(
            name='Detail TC', project=self.project, created_by=self.user,
        )
        ApiTestCaseStep.objects.create(
            name='Step 1', order=1,
            interface_data={'method': 'GET'},
            testcase=tc, origin_interface=self.interface,
        )
        response = self.client.get(f'{self.base_url}{tc.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['steps']), 1)

    def test_update_testcase_renames_existing_step_without_copying(self):
        tc = ApiTestCase.objects.create(
            name='Edit TC', project=self.project, created_by=self.user,
            priority='P3',
        )
        step = ApiTestCaseStep.objects.create(
            name='Old Step', order=1,
            interface_data={'method': 'GET', 'url': '/old'},
            testcase=tc, origin_interface=self.interface,
        )

        data = {
            'name': 'Edit TC',
            'priority': 'P2',
            'update_mode': 'update',
            'steps_info': [{
                'id': step.pk,
                'name': 'Renamed Step',
                'order': 1,
                'interface_id': self.interface.pk,
                'interface_data': {
                    'method': 'POST',
                    'url': '/changed',
                    'headers': [],
                    'params': [],
                    'body': {'type': 'raw', 'content': '{"ok": true}'},
                    'validators': [],
                    'extract': {},
                    'setup_hooks': [],
                    'teardown_hooks': [],
                    'variables': {},
                },
            }],
        }

        response = self.client.put(f'{self.base_url}{tc.pk}/', data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(tc.steps.count(), 1)
        step.refresh_from_db()
        self.assertEqual(step.name, 'Renamed Step')
        self.assertEqual(step.interface_data['method'], 'POST')
        self.assertEqual(step.interface_data['body']['content'], '{"ok": true}')

    def test_update_testcase_legacy_step_rename_by_order_does_not_copy(self):
        tc = ApiTestCase.objects.create(
            name='Legacy Edit TC', project=self.project, created_by=self.user,
            priority='P3',
        )
        step = ApiTestCaseStep.objects.create(
            name='Old Step', order=1,
            interface_data={'method': 'GET', 'url': '/old'},
            testcase=tc, origin_interface=self.interface,
        )

        data = {
            'name': 'Legacy Edit TC',
            'priority': 'P3',
            'steps_info': [{
                'name': 'Renamed Step',
                'order': 1,
                'interface_id': self.interface.pk,
                'interface_data': {
                    'method': 'GET',
                    'url': '/old',
                    'headers': [],
                    'params': [],
                    'body': {'type': 'raw', 'content': ''},
                    'validators': [],
                    'extract': {},
                    'setup_hooks': [],
                    'teardown_hooks': [],
                    'variables': {},
                },
            }],
        }

        response = self.client.put(f'{self.base_url}{tc.pk}/', data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(tc.steps.count(), 1)
        step.refresh_from_db()
        self.assertEqual(step.name, 'Renamed Step')

    def test_copy_testcase(self):
        tc = ApiTestCase.objects.create(
            name='Original', project=self.project, created_by=self.user,
        )
        tag = ApiTestCaseTag.objects.create(
            name='tag1', project=self.project, created_by=self.user,
        )
        tc.tags.add(tag)
        ApiTestCaseStep.objects.create(
            name='Step 1', order=1,
            interface_data={'method': 'GET'},
            testcase=tc, origin_interface=self.interface,
        )
        response = self.client.post(f'{self.base_url}{tc.pk}/copy/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        copied = ApiTestCase.objects.get(name='Original_copy')
        self.assertEqual(copied.tags.count(), 1)
        self.assertEqual(copied.steps.count(), 1)

    def test_delete_step_action(self):
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        step = ApiTestCaseStep.objects.create(
            name='Step 1', order=1,
            interface_data={'method': 'GET'},
            testcase=tc,
        )
        response = self.client.delete(
            f'{self.base_url}{tc.pk}/delete_step/?step_id={step.pk}'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(tc.steps.count(), 0)

    def test_delete_step_missing_param(self):
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        response = self.client.delete(f'{self.base_url}{tc.pk}/delete_step/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_step_not_found(self):
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        response = self.client.delete(
            f'{self.base_url}{tc.pk}/delete_step/?step_id=99999'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_available_interfaces(self):
        response = self.client.get(f'{self.base_url}available_interfaces/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_referenced_interfaces(self):
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        ApiTestCaseStep.objects.create(
            name='Step 1', order=1,
            interface_data={'method': 'GET'},
            testcase=tc, origin_interface=self.interface,
        )
        response = self.client.get(f'{self.base_url}{tc.pk}/referenced_interfaces/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    @patch('api_testcases.views.TestExecutionService')
    def test_run_testcase(self, mock_service):
        mock_report = MagicMock()
        mock_report.id = 1
        mock_report.status = 'success'
        mock_report.success_count = 1
        mock_report.fail_count = 0
        mock_report.error_count = 0
        mock_report.duration = 0.5
        mock_service.run_testcase.return_value = mock_report

        tc = ApiTestCase.objects.create(
            name='Run TC', project=self.project, created_by=self.user,
        )
        response = self.client.post(f'{self.base_url}{tc.pk}/run/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')

    @patch('api_testcases.views.TestExecutionService')
    def test_batch_run(self, mock_service):
        mock_report = MagicMock()
        mock_report.id = 1
        mock_report.status = 'success'
        mock_service.run_batch.return_value = [mock_report]
        mock_service.get_statistics.return_value = {
            'total': 1, 'success': 1, 'failure': 0, 'error': 0, 'success_rate': '100.00%'
        }

        tc = ApiTestCase.objects.create(
            name='Batch TC', project=self.project, created_by=self.user,
        )
        data = {'testcase_ids': [tc.pk]}
        response = self.client.post(f'{self.base_url}batch_run/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_batch_run_no_ids(self):
        response = self.client.post(f'{self.base_url}batch_run/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_history_reports(self):
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        ApiTestReport.objects.create(
            name='Report',
            status='success',
            success_count=1, fail_count=0, error_count=0,
            duration=0.5, summary={},
            testcase=tc, executed_by=self.user,
        )
        response = self.client.get(f'{self.base_url}{tc.pk}/history_reports/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_testcase(self):
        tc = ApiTestCase.objects.create(
            name='To Delete', project=self.project, created_by=self.user,
        )
        response = self.client.delete(f'{self.base_url}{tc.pk}/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])

    def test_reorder_steps_empty(self):
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        response = self.client.post(
            f'{self.base_url}{tc.pk}/reorder_steps/', {}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reorder_steps_with_step_id_and_new_order(self):
        """Frontend sends {step_id, new_order} for single-step reorder."""
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        s1 = ApiTestCaseStep.objects.create(
            name='Step 1', order=1,
            interface_data={'method': 'GET'}, testcase=tc,
        )
        s2 = ApiTestCaseStep.objects.create(
            name='Step 2', order=2,
            interface_data={'method': 'POST'}, testcase=tc,
        )
        s3 = ApiTestCaseStep.objects.create(
            name='Step 3', order=3,
            interface_data={'method': 'PUT'}, testcase=tc,
        )
        # Move step 3 to position 1
        data = {'step_id': s3.pk, 'new_order': 1}
        response = self.client.post(
            f'{self.base_url}{tc.pk}/reorder_steps/', data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        s3.refresh_from_db()
        self.assertEqual(s3.order, 1)

    def test_reorder_steps_with_step_id_and_new_order_move_down(self):
        """Single-step reorder also works when moving a step later in the sequence."""
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        s1 = ApiTestCaseStep.objects.create(
            name='Step 1', order=1,
            interface_data={'method': 'GET'}, testcase=tc,
        )
        s2 = ApiTestCaseStep.objects.create(
            name='Step 2', order=2,
            interface_data={'method': 'POST'}, testcase=tc,
        )
        s3 = ApiTestCaseStep.objects.create(
            name='Step 3', order=3,
            interface_data={'method': 'PUT'}, testcase=tc,
        )

        response = self.client.post(
            f'{self.base_url}{tc.pk}/reorder_steps/',
            {'step_id': s1.pk, 'new_order': 3},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        s1.refresh_from_db()
        s2.refresh_from_db()
        s3.refresh_from_db()
        self.assertEqual(s1.order, 3)
        self.assertEqual(s2.order, 1)
        self.assertEqual(s3.order, 2)

    def test_reorder_steps_with_steps_array(self):
        """Frontend can also send {steps: [{step_id, order}, ...]} for bulk reorder."""
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        s1 = ApiTestCaseStep.objects.create(
            name='Step 1', order=1,
            interface_data={'method': 'GET'}, testcase=tc,
        )
        s2 = ApiTestCaseStep.objects.create(
            name='Step 2', order=2,
            interface_data={'method': 'POST'}, testcase=tc,
        )
        data = {'steps': [
            {'step_id': s2.pk, 'order': 1},
            {'step_id': s1.pk, 'order': 2},
        ]}
        response = self.client.post(
            f'{self.base_url}{tc.pk}/reorder_steps/', data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        s1.refresh_from_db()
        s2.refresh_from_db()
        self.assertEqual(s2.order, 1)
        self.assertEqual(s1.order, 2)

    def test_delete_step_via_query_param(self):
        """delete_step reads step_id from query params, not request body."""
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        s1 = ApiTestCaseStep.objects.create(
            name='Step 1', order=1,
            interface_data={'method': 'GET'}, testcase=tc,
        )
        s2 = ApiTestCaseStep.objects.create(
            name='Step 2', order=2,
            interface_data={'method': 'POST'}, testcase=tc,
        )
        # Delete via query param
        response = self.client.delete(
            f'{self.base_url}{tc.pk}/delete_step/?step_id={s1.pk}'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(tc.steps.count(), 1)
        remaining = tc.steps.first()
        self.assertEqual(remaining.pk, s2.pk)

    def test_history_reports_returns_list(self):
        """history_reports returns a paginated list with total count."""
        tc = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        for i in range(3):
            ApiTestReport.objects.create(
                name=f'Report {i}',
                status='success',
                success_count=1, fail_count=0, error_count=0,
                duration=0.5, summary={},
                testcase=tc, executed_by=self.user,
            )
        response = self.client.get(f'{self.base_url}{tc.pk}/history_reports/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response should be paginated with count and results
        if isinstance(response.data, dict):
            self.assertGreaterEqual(response.data.get('count', len(response.data.get('results', []))), 3)
        else:
            self.assertGreaterEqual(len(response.data), 3)

    def test_unauthenticated_access(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ApiTestReportAPITest(TestCase):
    """ApiTestReport API tests (read-only viewset)"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='apiuser', password='testpass')
        self.project = Project.objects.create(name='API Project', creator=self.user)
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        _grant_all_testcase_perms(self.user)
        self.client.force_authenticate(user=self.user)
        self.testcase = ApiTestCase.objects.create(
            name='TC', project=self.project, created_by=self.user,
        )
        self.base_url = f'/api/projects/{self.project.pk}/api-test-reports/'

    def test_list_reports(self):
        ApiTestReport.objects.create(
            name='Report 1',
            status='success',
            success_count=1, fail_count=0, error_count=0,
            duration=0.5, summary={},
            testcase=self.testcase, executed_by=self.user,
        )
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_report_with_details(self):
        report = ApiTestReport.objects.create(
            name='Report',
            status='success',
            success_count=1, fail_count=0, error_count=0,
            duration=0.5, summary={},
            testcase=self.testcase, executed_by=self.user,
        )
        step = ApiTestCaseStep.objects.create(
            name='Step', order=1,
            interface_data={'method': 'GET'},
            testcase=self.testcase,
        )
        ApiTestReportDetail.objects.create(
            report=report, step=step,
            success=True, elapsed=0.3,
            request={}, response={},
        )
        response = self.client.get(f'{self.base_url}{report.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['details']), 1)

    def test_read_only_no_create(self):
        data = {'name': 'Should Fail'}
        response = self.client.post(self.base_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_read_only_no_delete(self):
        report = ApiTestReport.objects.create(
            name='No Delete',
            status='success',
            success_count=1, fail_count=0, error_count=0,
            duration=0.5, summary={},
            testcase=self.testcase, executed_by=self.user,
        )
        response = self.client.delete(f'{self.base_url}{report.pk}/')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_report_list_success_rate_format(self):
        """Report list success_rate returns 0-1 string (e.g. '0.80'), not percentage.
        Frontend multiplies by 100 for display, so backend must return decimal."""
        ApiTestReport.objects.create(
            name='Report 80%',
            status='success',
            success_count=8, fail_count=1, error_count=1,
            duration=1.0, summary={},
            testcase=self.testcase, executed_by=self.user,
        )
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        items = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['success_rate'], '0.80')

    def test_report_list_success_rate_perfect(self):
        """success_rate returns '1' for 100% success."""
        ApiTestReport.objects.create(
            name='Report 100%',
            status='success',
            success_count=5, fail_count=0, error_count=0,
            duration=1.0, summary={},
            testcase=self.testcase, executed_by=self.user,
        )
        response = self.client.get(self.base_url)
        items = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertEqual(items[0]['success_rate'], '1')

    def test_report_list_success_rate_zero(self):
        """success_rate returns '0' when all counts are zero."""
        ApiTestReport.objects.create(
            name='Report empty',
            status='error',
            success_count=0, fail_count=0, error_count=0,
            duration=0.0, summary={},
            testcase=self.testcase, executed_by=self.user,
        )
        response = self.client.get(self.base_url)
        items = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertEqual(items[0]['success_rate'], '0')

    def test_report_list_includes_environment_name(self):
        """Report list includes environment_name field."""
        from api_environments.models import ApiEnvironment
        env = ApiEnvironment.objects.create(
            name='Staging', base_url='https://staging.example.com',
            project=self.project,
        )
        ApiTestReport.objects.create(
            name='Report with env',
            status='success',
            success_count=1, fail_count=0, error_count=0,
            duration=0.5, summary={},
            testcase=self.testcase, executed_by=self.user,
            environment=env,
        )
        response = self.client.get(self.base_url)
        items = response.data['results'] if isinstance(response.data, dict) else response.data
        self.assertIn('environment_name', items[0])
        self.assertEqual(items[0]['environment_name'], 'Staging')


class ApiTestCasePermissionTest(TestCase):
    """ApiTestCase permission tests"""

    def setUp(self):
        self.client = APIClient()
        self.user_a = User.objects.create_user(username='user_a', password='testpass')
        self.project_a = Project.objects.create(name='Project A', creator=self.user_a)
        ProjectMember.objects.create(project=self.project_a, user=self.user_a, role='member')
        _grant_all_testcase_perms(self.user_a)

        self.outsider = User.objects.create_user(username='outsider', password='testpass')
        _grant_all_testcase_perms(self.outsider)
        self.superuser = User.objects.create_superuser(username='admin', password='adminpass')

    def test_non_member_denied_testcases(self):
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(f'/api/projects/{self.project_a.pk}/api-testcases/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_member_denied_tags(self):
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(f'/api/projects/{self.project_a.pk}/api-testcase-tags/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_member_denied_groups(self):
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(f'/api/projects/{self.project_a.pk}/api-testcase-groups/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_allowed_testcases(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get(f'/api/projects/{self.project_a.pk}/api-testcases/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_superuser_allowed_tags(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get(f'/api/projects/{self.project_a.pk}/api-testcase-tags/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_superuser_allowed_reports(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get(f'/api/projects/{self.project_a.pk}/api-test-reports/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ApiTestCaseIsolationTest(TestCase):
    """测试用例模块项目隔离测试"""

    def setUp(self):
        self.client = APIClient()
        self.user_a = User.objects.create_user(username='user_a', password='testpass')
        _grant_all_testcase_perms(self.user_a)
        self.project_a = Project.objects.create(name='Project A', creator=self.user_a)
        ProjectMember.objects.create(project=self.project_a, user=self.user_a, role='admin')

        self.user_b = User.objects.create_user(username='user_b', password='testpass')
        self.project_b = Project.objects.create(name='Project B', creator=self.user_b)
        ProjectMember.objects.create(project=self.project_b, user=self.user_b, role='admin')

        # Interface and environment in project B
        self.interface_b = ApiInterface.objects.create(
            name='B API', type='http', method='GET', url='http://b.com/api',
            project=self.project_b, created_by=self.user_b,
        )

        from api_environments.models import ApiEnvironment
        self.env_b = ApiEnvironment.objects.create(
            name='Env B', base_url='http://b.com',
            project=self.project_b, created_by=self.user_b,
        )

        # Interface in project A (for creating testcases)
        self.interface_a = ApiInterface.objects.create(
            name='A API', type='http', method='GET', url='http://a.com/api',
            project=self.project_a, created_by=self.user_a,
        )
        self.testcase_a = ApiTestCase.objects.create(
            name='TC A', project=self.project_a, created_by=self.user_a,
        )
        ApiTestCaseStep.objects.create(
            testcase=self.testcase_a, name='Step 1', order=1,
            origin_interface=self.interface_a,
            interface_data=self.interface_a.get_interface_data(),
        )

        # Testcase in project B
        self.testcase_b = ApiTestCase.objects.create(
            name='TC B', project=self.project_b, created_by=self.user_b,
        )

        self.client.force_authenticate(user=self.user_a)
        self.base_url = f'/api/projects/{self.project_a.pk}/api-testcases/'

    @patch('api_testcases.views.TestExecutionService')
    def test_run_with_cross_project_environment(self, mock_service):
        """run/ 使用跨项目环境应返回 404"""
        response = self.client.post(
            f'{self.base_url}{self.testcase_a.pk}/run/',
            {'environment_id': self.env_b.pk},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch('api_testcases.views.TestExecutionService')
    def test_batch_run_cross_project_environment(self, mock_service):
        """batch_run/ 使用跨项目环境应返回 404"""
        response = self.client.post(
            f'{self.base_url}batch_run/',
            {'testcase_ids': [self.testcase_a.pk], 'environment_id': self.env_b.pk},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch('api_testcases.views.TestExecutionService')
    def test_batch_run_cross_project_testcase_ids(self, mock_service):
        """batch_run/ 传入跨项目的 testcase_ids，不会执行跨项目用例"""
        mock_service.run_batch.return_value = []
        mock_service.get_statistics.return_value = {'total': 0, 'success': 0}
        response = self.client.post(
            f'{self.base_url}batch_run/',
            {'testcase_ids': [self.testcase_b.pk]},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # The view filters by project_id, so cross-project testcases are excluded

    def test_create_step_with_cross_project_interface(self):
        """创建 testcase 时 steps_info 引用跨项目 interface 应报错（DoesNotExist）"""
        from api_interfaces.models import ApiInterface as IfaceModel
        data = {
            'name': 'Bad TC',
            'steps_info': [
                {'name': 'Step1', 'order': 1, 'interface_id': self.interface_b.pk},
            ],
        }
        with self.assertRaises(IfaceModel.DoesNotExist):
            self.client.post(self.base_url, data, format='json')


class ApiTestCaseTaskTest(TestCase):
    """Celery Task 测试"""

    def setUp(self):
        self.user = User.objects.create_user(username='taskuser', password='testpass')
        self.project = Project.objects.create(name='Task Project', creator=self.user)
        self.interface = ApiInterface.objects.create(
            name='Task API', type='http', method='GET', url='http://task.com/api',
            project=self.project, created_by=self.user,
        )
        self.testcase = ApiTestCase.objects.create(
            name='Task TC', project=self.project, created_by=self.user,
        )
        ApiTestCaseStep.objects.create(
            testcase=self.testcase, name='Step 1', order=1,
            origin_interface=self.interface,
            interface_data=self.interface.get_interface_data(),
        )

    @patch('api_testcases.tasks.TestExecutionService')
    def test_run_api_testcase_success(self, mock_service_cls):
        """Celery task run_api_testcase 正常执行"""
        from api_testcases.tasks import run_api_testcase
        mock_report = MagicMock()
        mock_report.id = 999
        mock_report.status = 'success'
        mock_service_cls.run_testcase.return_value = mock_report

        result = run_api_testcase(self.testcase.pk, user_id=self.user.pk)
        self.assertEqual(result['report_id'], 999)
        self.assertEqual(result['status'], 'success')

    @patch('api_testcases.tasks.TestExecutionService')
    def test_run_api_testcase_not_found(self, mock_service_cls):
        """Celery task 传入不存在的 testcase_id"""
        from api_testcases.tasks import run_api_testcase
        result = run_api_testcase(999999, user_id=self.user.pk)
        self.assertIn('error', result)

    @patch('api_testcases.tasks.TestExecutionService')
    def test_run_api_testcase_batch_success(self, mock_service_cls):
        """Celery task batch 正常执行"""
        from api_testcases.tasks import run_api_testcase_batch
        mock_report = MagicMock()
        mock_report.id = 100
        mock_service_cls.run_batch.return_value = [mock_report]
        mock_service_cls.get_statistics.return_value = {
            'total': 1, 'success': 1, 'failure': 0, 'error': 0,
        }
        result = run_api_testcase_batch(
            [self.testcase.pk], user_id=self.user.pk,
        )
        self.assertIn('report_ids', result)
        self.assertEqual(result['report_ids'], [100])
        self.assertIn('statistics', result)


class ApiTestCaseModelLayerTest(TestCase):
    """ApiTestCase 模型层补充测试"""

    def setUp(self):
        self.user = User.objects.create_user(username='modeluser', password='testpass')
        self.project = Project.objects.create(name='Model Project', creator=self.user)
        self.interface = ApiInterface.objects.create(
            name='Model API', type='http', method='GET', url='http://model.com/api',
            project=self.project, created_by=self.user,
        )
        self.testcase = ApiTestCase.objects.create(
            name='Model TC', project=self.project, created_by=self.user,
        )

    def test_step_ordering(self):
        """steps 按 order 字段排序"""
        s3 = ApiTestCaseStep.objects.create(
            testcase=self.testcase, name='Step 3', order=3,
            interface_data={'method': 'GET', 'url': '/3'},
        )
        s1 = ApiTestCaseStep.objects.create(
            testcase=self.testcase, name='Step 1', order=1,
            interface_data={'method': 'GET', 'url': '/1'},
        )
        s2 = ApiTestCaseStep.objects.create(
            testcase=self.testcase, name='Step 2', order=2,
            interface_data={'method': 'GET', 'url': '/2'},
        )
        steps = list(self.testcase.steps.all())
        self.assertEqual([s.order for s in steps], [1, 2, 3])
        self.assertEqual(steps[0].name, 'Step 1')

    def test_step_interface_data_copy(self):
        """创建 step 时 interface_data 从 interface 正确复制"""
        iface_data = self.interface.get_interface_data()
        step = ApiTestCaseStep.objects.create(
            testcase=self.testcase, name='Copy Step', order=1,
            origin_interface=self.interface,
            interface_data=iface_data,
        )
        self.assertEqual(step.interface_data['method'], 'GET')
        self.assertEqual(step.interface_data['url'], 'http://model.com/api')

    def test_testcase_cascade_delete_steps(self):
        """删除 testcase 级联删除 steps"""
        ApiTestCaseStep.objects.create(
            testcase=self.testcase, name='S1', order=1,
            interface_data={'method': 'GET', 'url': '/1'},
        )
        ApiTestCaseStep.objects.create(
            testcase=self.testcase, name='S2', order=2,
            interface_data={'method': 'GET', 'url': '/2'},
        )
        self.testcase.delete()
        self.assertEqual(ApiTestCaseStep.objects.count(), 0)

    def test_testcase_cascade_delete_reports(self):
        """删除 testcase 级联删除 reports"""
        report = ApiTestReport.objects.create(
            name='Report', status='success', success_count=1,
            fail_count=0, error_count=0, duration=1.0,
            summary={}, testcase=self.testcase, executed_by=self.user,
        )
        ApiTestReportDetail.objects.create(
            report=report, success=True, elapsed=0.5,
            request={}, response={},
        )
        self.testcase.delete()
        self.assertEqual(ApiTestReport.objects.count(), 0)
        self.assertEqual(ApiTestReportDetail.objects.count(), 0)

    def test_report_project_property(self):
        """report.project 返回 testcase 的 project"""
        report = ApiTestReport.objects.create(
            name='Report', status='success', success_count=1,
            fail_count=0, error_count=0, duration=1.0,
            summary={}, testcase=self.testcase, executed_by=self.user,
        )
        self.assertEqual(report.project, self.project)

    def test_step_str_representation(self):
        """step __str__ 格式正确"""
        step = ApiTestCaseStep.objects.create(
            testcase=self.testcase, name='Login', order=1,
            interface_data={'method': 'POST', 'url': '/login'},
        )
        self.assertEqual(str(step), 'Model TC-Login')

    def test_tag_unique_together(self):
        """同一项目下 tag 名称唯一"""
        ApiTestCaseTag.objects.create(
            name='smoke', project=self.project, created_by=self.user,
        )
        with self.assertRaises(Exception):
            ApiTestCaseTag.objects.create(
                name='smoke', project=self.project, created_by=self.user,
            )

    def test_group_full_path(self):
        """group get_full_path 正确拼接层级路径"""
        parent = ApiTestCaseGroup.objects.create(
            name='Module A', project=self.project, created_by=self.user,
        )
        child = ApiTestCaseGroup.objects.create(
            name='Sub B', parent=parent, project=self.project,
            created_by=self.user,
        )
        self.assertEqual(child.get_full_path(), 'Module A / Sub B')


class TestCaseServiceTest(TestCase):
    """TestCaseService 单元测试"""

    def setUp(self):
        self.user = User.objects.create_user(username='svcuser', password='testpass')
        self.project = Project.objects.create(name='Svc Project', creator=self.user)
        self.interface = ApiInterface.objects.create(
            name='Svc API', type='http', method='POST',
            url='http://svc.com/api', headers={'Content-Type': 'application/json'},
            project=self.project, created_by=self.user,
        )

    def test_create_testcase_success(self):
        """正常创建含 steps 的 testcase"""
        data = {
            'name': 'SVC TC',
            'project': self.project,
            'steps_info': [
                {'name': 'Login', 'interface_id': self.interface.pk},
            ],
        }
        tc = TestCaseService.create_testcase(data, self.user)
        self.assertEqual(tc.name, 'SVC TC')
        self.assertEqual(tc.steps.count(), 1)
        step = tc.steps.first()
        self.assertEqual(step.name, 'Login')
        self.assertEqual(step.origin_interface, self.interface)

    def test_create_testcase_copies_interface_data(self):
        """step 的 interface_data 从 ApiInterface 复制"""
        data = {
            'name': 'Copy TC',
            'project': self.project,
            'steps_info': [
                {'name': 'S1', 'interface_id': self.interface.pk},
            ],
        }
        tc = TestCaseService.create_testcase(data, self.user)
        step = tc.steps.first()
        self.assertEqual(step.interface_data['method'], 'POST')
        self.assertEqual(step.interface_data['url'], 'http://svc.com/api')
        self.assertEqual(step.interface_data['headers'], {'Content-Type': 'application/json'})

    def test_validate_missing_name(self):
        """缺少 name → (False, error_msg)"""
        valid, msg = TestCaseService.validate_testcase_data({
            'project': self.project,
            'steps_info': [{'name': 'S', 'interface_id': 1}],
        })
        self.assertFalse(valid)
        self.assertIn('name', msg)

    def test_validate_missing_steps(self):
        """无 steps → (False, error_msg)"""
        valid, msg = TestCaseService.validate_testcase_data({
            'name': 'TC', 'project': self.project,
        })
        self.assertFalse(valid)
        self.assertIn('step', msg.lower())

    def test_validate_step_missing_interface(self):
        """step 缺少 interface_id → (False, error_msg)"""
        valid, msg = TestCaseService.validate_testcase_data({
            'name': 'TC', 'project': self.project,
            'steps_info': [{'name': 'S1'}],
        })
        self.assertFalse(valid)
        self.assertIn('interface_id', msg)

    def test_validate_step_missing_name(self):
        """step 缺少 name → (False, error_msg)"""
        valid, msg = TestCaseService.validate_testcase_data({
            'name': 'TC', 'project': self.project,
            'steps_info': [{'interface_id': 1}],
        })
        self.assertFalse(valid)
        self.assertIn('name', msg.lower())

    def test_validate_success(self):
        """正确的数据通过验证"""
        valid, msg = TestCaseService.validate_testcase_data({
            'name': 'TC', 'project': self.project,
            'steps_info': [{'name': 'S1', 'interface_id': 1}],
        })
        self.assertTrue(valid)
        self.assertIsNone(msg)


class TestExecutionServiceTest(TestCase):
    """TestExecutionService 单元测试"""

    def test_prepare_config_merges_env_vars(self):
        """_prepare_config 正确合并环境变量（case 变量覆盖 env 变量）"""
        config = {'variables': {'a': '1', 'b': '2'}, 'base_url': 'http://case.com'}
        environment = {'variables': {'b': '99', 'c': '3'}, 'base_url': 'http://env.com'}
        result = TestExecutionService._prepare_config(config, environment)
        # case variables override env variables
        self.assertEqual(result['variables']['a'], '1')
        self.assertEqual(result['variables']['b'], '2')  # case overrides env
        self.assertEqual(result['variables']['c'], '3')
        # config base_url takes precedence
        self.assertEqual(result['base_url'], 'http://case.com')

    def test_prepare_config_env_base_url_fallback(self):
        """config 无 base_url 时回退到 environment"""
        config = {'variables': {}}
        environment = {'base_url': 'http://env.com', 'variables': {}}
        result = TestExecutionService._prepare_config(config, environment)
        self.assertEqual(result['base_url'], 'http://env.com')

    def test_prepare_config_none_inputs(self):
        """None 输入不崩溃"""
        result = TestExecutionService._prepare_config(None, None)
        self.assertEqual(result['variables'], {})
        self.assertEqual(result['base_url'], '')
        self.assertFalse(result['verify'])

    def test_prepare_config_string_variables(self):
        """字符串格式的变量被正确解析"""
        config = {'variables': '{"x": "1"}'}
        result = TestExecutionService._prepare_config(config, None)
        self.assertEqual(result['variables'], {'x': '1'})

    def test_prepare_config_invalid_string_variables(self):
        """无效 JSON 字符串变量不崩溃"""
        config = {'variables': 'not json'}
        result = TestExecutionService._prepare_config(config, None)
        self.assertEqual(result['variables'], {})

    def test_get_statistics_empty(self):
        """空 reports 列表的统计"""
        stats = TestExecutionService.get_statistics([])
        self.assertEqual(stats['total'], 0)
        self.assertEqual(stats['success_rate'], '0%')

    def test_get_statistics_mixed(self):
        """混合状态的统计"""
        mock_reports = [
            MagicMock(status='success'),
            MagicMock(status='success'),
            MagicMock(status='failure'),
        ]
        stats = TestExecutionService.get_statistics(mock_reports)
        self.assertEqual(stats['total'], 3)
        self.assertEqual(stats['success'], 2)
        self.assertEqual(stats['failure'], 1)
        self.assertEqual(stats['success_rate'], '66.67%')

    def test_get_statistics_all_success(self):
        """全部成功的统计"""
        mock_reports = [MagicMock(status='success')] * 5
        stats = TestExecutionService.get_statistics(mock_reports)
        self.assertEqual(stats['success_rate'], '100.00%')


class TestExecutionServiceBinaryResponseTest(TestCase):
    """Binary response persistence tests for API testcase execution."""

    def setUp(self):
        self.user = User.objects.create_user(username='binaryuser', password='testpass')
        self.project = Project.objects.create(name='Binary Project', creator=self.user)

    @patch('api_testcases.services.TestCaseRunner')
    def test_run_testcase_persists_binary_response_summary(self, mock_runner_class):
        testcase = ApiTestCase.objects.create(
            name='Export Test', project=self.project, created_by=self.user,
        )
        step = ApiTestCaseStep.objects.create(
            name='Export Step',
            order=1,
            interface_data={'method': 'GET', 'url': '/export'},
            testcase=testcase,
        )

        binary_body = {
            'type': 'binary',
            'binary': True,
            'omitted': True,
            'message': 'Binary response body omitted from execution report.',
            'content_type': (
                'application/vnd.openxmlformats-officedocument.'
                'spreadsheetml.sheet'
            ),
            'content_length': 27,
            'sha256': 'ec87bf8d16798a742b068101b3e49f5daa206ee3cee6f7d29234b81df367d1a0',
            'preview_hex': '504b030414000000080066616b652d786c7378',
            'filename': 'report.xlsx',
        }
        step_results = [{
            'name': step.name,
            'success': True,
            'elapsed': 0.12,
            'step_type': 'request',
            'data': {
                'request': {
                    'method': 'GET',
                    'url': 'http://example.com/export',
                    'headers': {},
                    'body': None,
                },
                'response': {
                    'status_code': 200,
                    'headers': {
                        'Content-Type': binary_body['content_type'],
                        'Content-Disposition': 'attachment; filename=report.xlsx',
                    },
                    'body': binary_body,
                    'content_size': 27,
                    'response_time_ms': 120,
                },
                'validators': {
                    'success': True,
                    'validate_extractor': [{'check_result': 'pass'}],
                },
                'extracted_variables': {},
            },
            'attachment': '',
        }]
        summary = {
            'success': True,
            'name': testcase.name,
            'time': {'start_at': '2026-07-08T00:00:00', 'duration': 0.12},
            'in_out': {'config_vars': {}, 'export_vars': {}},
            'log': '',
            'step_results': step_results,
        }

        mock_runner = MagicMock()
        mock_runner.run_testcase.return_value = mock_runner
        mock_runner.get_summary.return_value = summary
        mock_runner.get_step_results.return_value = step_results
        mock_runner_class.return_value = mock_runner

        report = TestExecutionService.run_testcase(testcase, user=self.user)
        detail = report.details.get()

        self.assertEqual(report.status, 'success')
        self.assertTrue(detail.response['body']['binary'])
        self.assertEqual(detail.response['body']['filename'], 'report.xlsx')
        self.assertNotIn('\x00', json.dumps(report.summary, ensure_ascii=False))
        self.assertNotIn('\x00', json.dumps(detail.response, ensure_ascii=False))


class ApiTestCaseFilterTest(TestCase):
    """ApiTestCase 过滤和搜索测试"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='filteruser', password='testpass')
        self.project = Project.objects.create(name='Filter Project', creator=self.user)
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        _grant_all_testcase_perms(self.user)
        self.client.force_authenticate(user=self.user)
        self.base_url = f'/api/projects/{self.project.pk}/api-testcases/'

        self.tag = ApiTestCaseTag.objects.create(
            name='smoke', project=self.project, created_by=self.user,
        )
        self.group = ApiTestCaseGroup.objects.create(
            name='Auth', project=self.project, created_by=self.user,
        )
        self.tc1 = ApiTestCase.objects.create(
            name='Login Test', priority='P0', project=self.project,
            group=self.group, created_by=self.user,
        )
        self.tc1.tags.add(self.tag)
        self.tc2 = ApiTestCase.objects.create(
            name='Register Test', priority='P2', project=self.project,
            created_by=self.user,
        )

    def test_filter_by_priority(self):
        """?priority=P0 过滤有效"""
        response = self.client.get(f'{self.base_url}?priority=P0')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertTrue(all(r['priority'] == 'P0' for r in results))

    def test_filter_by_group(self):
        """?group=X 过滤有效"""
        response = self.client.get(f'{self.base_url}?group={self.group.pk}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['name'], 'Login Test')

    def test_filter_by_tag(self):
        """?tags=X 过滤有效"""
        response = self.client.get(f'{self.base_url}?tags={self.tag.pk}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 1)

    def test_filter_by_name(self):
        """?name=xxx 模糊搜索"""
        response = self.client.get(f'{self.base_url}?name=Login')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertTrue(all('Login' in r['name'] for r in results))

    def test_pagination_response_format(self):
        """分页响应包含 count/next/previous/results"""
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('results', response.data)

    def test_ordering_by_created_at(self):
        """?ordering=created_at 排序正确"""
        response = self.client.get(f'{self.base_url}?ordering=created_at')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertGreaterEqual(len(results), 2)


class ApiInterfaceCaseAPITest(TestCase):
    """ApiInterfaceCase API tests."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='interfacecaseuser', password='testpass')
        self.project = Project.objects.create(name='Interface Case Project', creator=self.user)
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        _grant_all_testcase_perms(self.user)
        self.client.force_authenticate(user=self.user)
        self.base_url = f'/api/projects/{self.project.pk}/api-interface-cases/'

        self.login_interface = ApiInterface.objects.create(
            name='Login API',
            type='http',
            method='POST',
            url='/login',
            headers=[],
            params=[],
            body={'type': 'raw', 'content': '{"username":"demo"}'},
            extract={'token': 'body.token'},
            extract_meta={'token': {'variable_type': 'temporary'}},
            validators=[],
            project=self.project,
            created_by=self.user,
        )
        self.target_interface = ApiInterface.objects.create(
            name='Profile API',
            type='http',
            method='GET',
            url='/profile',
            headers=[{'key': 'Authorization', 'value': 'Bearer $token', 'enabled': True}],
            params=[],
            body={'type': 'none', 'content': None},
            validators=[],
            project=self.project,
            created_by=self.user,
        )

    def test_create_interface_case_creates_precondition_and_main_steps(self):
        data = {
            'name': 'Profile happy path',
            'description': 'single interface case with login precondition',
            'priority': 'P1',
            'interface_id': self.target_interface.pk,
            'steps_info': [
                {
                    'name': 'Login precondition',
                    'role': 'precondition',
                    'order': 1,
                    'interface_id': self.login_interface.pk,
                    'interface_data': {
                        'extract': {'token': 'body.data.token'},
                        'extract_meta': {'token': {'variable_type': 'temporary'}},
                    },
                }
            ],
        }

        response = self.client.post(self.base_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        interface_case = ApiInterfaceCase.objects.get(name='Profile happy path')
        self.assertEqual(interface_case.interface, self.target_interface)
        steps = list(interface_case.steps.order_by('order'))
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0].role, ApiInterfaceCaseStep.ROLE_PRECONDITION)
        self.assertEqual(steps[0].origin_interface, self.login_interface)
        self.assertEqual(steps[0].interface_data['extract']['token'], 'body.data.token')
        self.assertEqual(steps[1].role, ApiInterfaceCaseStep.ROLE_MAIN)
        self.assertEqual(steps[1].origin_interface, self.target_interface)
        self.assertEqual(response.data['precondition_count'], 1)

    def test_filter_interface_cases_by_interface_id(self):
        case = ApiInterfaceCase.objects.create(
            name='Profile filter case',
            project=self.project,
            interface=self.target_interface,
            created_by=self.user,
        )
        ApiInterfaceCaseStep.objects.create(
            interface_case=case,
            name='Main',
            role=ApiInterfaceCaseStep.ROLE_MAIN,
            order=1,
            origin_interface=self.target_interface,
            interface_data=self.target_interface.get_interface_data(),
        )
        other_interface = ApiInterface.objects.create(
            name='Other API',
            type='http',
            method='GET',
            url='/other',
            project=self.project,
            created_by=self.user,
        )
        other_case = ApiInterfaceCase.objects.create(
            name='Other filter case',
            project=self.project,
            interface=other_interface,
            created_by=self.user,
        )
        ApiInterfaceCaseStep.objects.create(
            interface_case=other_case,
            name='Main',
            role=ApiInterfaceCaseStep.ROLE_MAIN,
            order=1,
            origin_interface=other_interface,
            interface_data=other_interface.get_interface_data(),
        )

        response = self.client.get(f'{self.base_url}?interface_id={self.target_interface.pk}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['name'], 'Profile filter case')

    @patch('api_testcases.services.TestCaseRunner')
    def test_run_interface_case_records_precondition_extract_variables(self, mock_runner_class):
        environment = ApiEnvironment.objects.create(
            name='Interface Case Env',
            base_url='http://example.com',
            project=self.project,
            created_by=self.user,
        )
        interface_case = ApiInterfaceCase.objects.create(
            name='Profile with token',
            project=self.project,
            interface=self.target_interface,
            created_by=self.user,
        )
        precondition = ApiInterfaceCaseStep.objects.create(
            interface_case=interface_case,
            name='Login precondition',
            role=ApiInterfaceCaseStep.ROLE_PRECONDITION,
            order=1,
            origin_interface=self.login_interface,
            interface_data={
                'method': 'POST',
                'url': '/login',
                'extract': {'token': 'body.data.token'},
                'extract_meta': {'token': {'variable_type': 'project'}},
            },
        )
        main_step = ApiInterfaceCaseStep.objects.create(
            interface_case=interface_case,
            name='Profile main',
            role=ApiInterfaceCaseStep.ROLE_MAIN,
            order=2,
            origin_interface=self.target_interface,
            interface_data={
                'method': 'GET',
                'url': '/profile',
                'headers': [{'key': 'Authorization', 'value': 'Bearer $token', 'enabled': True}],
            },
        )
        step_results = [
            {
                'name': precondition.name,
                'success': True,
                'elapsed': 0.1,
                'step_type': 'request',
                'data': {
                    'request': {'method': 'POST', 'url': 'http://example.com/login'},
                    'response': {'status_code': 200, 'headers': {}, 'body': {'token': 'abc123'}},
                    'validators': {'success': True},
                    'extracted_variables': {'token': 'abc123'},
                },
                'attachment': '',
            },
            {
                'name': main_step.name,
                'success': True,
                'elapsed': 0.08,
                'step_type': 'request',
                'data': {
                    'request': {
                        'method': 'GET',
                        'url': 'http://example.com/profile',
                        'headers': {'Authorization': 'Bearer abc123'},
                    },
                    'response': {'status_code': 200, 'headers': {}, 'body': {'id': 1}},
                    'validators': {'success': True},
                    'extracted_variables': {},
                },
                'attachment': '',
            },
        ]
        summary = {
            'success': True,
            'name': interface_case.name,
            'time': {'start_at': '2026-07-06T00:00:00', 'duration': 0.18},
            'in_out': {'config_vars': {}, 'export_vars': {'token': 'abc123'}},
            'log': '',
            'step_results': step_results,
        }

        mock_runner = MagicMock()
        mock_runner.trace_id = 'tc-interface-case-test'
        mock_runner.run_testcase.return_value = mock_runner
        mock_runner.get_summary.return_value = summary
        mock_runner.get_step_results.return_value = step_results
        mock_runner_class.return_value = mock_runner

        report = InterfaceCaseExecutionService.run_interface_case(
            interface_case,
            environment={
                'id': environment.id,
                'base_url': environment.base_url,
                'verify_ssl': True,
                'variables': {},
            },
            user=self.user,
        )

        variable = ApiEnvironmentVariable.objects.get(environment=environment, name='token')
        self.assertEqual(variable.value, 'abc123')
        self.assertEqual(report.summary['extract_persistence']['created_count'], 1)
        details = list(report.details.order_by('id'))
        self.assertEqual(len(details), 2)
        self.assertEqual(details[0].step, precondition)
        self.assertEqual(details[0].extracted_variables['token'], 'abc123')
        self.assertEqual(details[1].step, main_step)
