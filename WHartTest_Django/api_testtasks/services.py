import logging

from django.db import transaction, models
from django.utils import timezone

from .models import (
    ApiTestTaskSuite,
    ApiTestTaskCase,
    ApiTestTaskExecution,
    ApiTestTaskCaseResult,
)

logger = logging.getLogger(__name__)


class ApiTestTaskService:
    """Service class for test task suite operations."""

    @staticmethod
    def add_cases(task_suite, testcase_ids=None, interface_case_ids=None, project_pk=None):
        from api_testcases.models import ApiInterfaceCase, ApiTestCase

        def unique_ids(ids):
            seen = set()
            result = []
            for item_id in ids or []:
                if item_id in seen:
                    continue
                seen.add(item_id)
                result.append(item_id)
            return result

        testcase_ids = unique_ids(testcase_ids)
        interface_case_ids = unique_ids(interface_case_ids)

        existing_ids = set(
            task_suite.api_task_cases.filter(
                case_type=ApiTestTaskCase.CASE_TYPE_SCENARIO
            ).values_list('testcase_id', flat=True)
        )
        new_ids = [tid for tid in testcase_ids if tid not in existing_ids]
        existing_interface_ids = set(
            task_suite.api_task_cases.filter(
                case_type=ApiTestTaskCase.CASE_TYPE_INTERFACE
            ).values_list('interface_case_id', flat=True)
        )
        new_interface_ids = [
            tid for tid in interface_case_ids if tid not in existing_interface_ids
        ]
        max_order = (
            task_suite.api_task_cases.aggregate(
                max_order=models.Max('order')
            )['max_order'] or 0
        )

        task_cases = []
        with transaction.atomic():
            next_order = max_order
            for i, testcase_id in enumerate(new_ids, 1):
                try:
                    lookup = {'id': testcase_id}
                    if project_pk:
                        lookup['project_id'] = project_pk
                    testcase = ApiTestCase.objects.get(**lookup)
                    task_case = ApiTestTaskCase.objects.create(
                        task_suite=task_suite,
                        case_type=ApiTestTaskCase.CASE_TYPE_SCENARIO,
                        testcase=testcase,
                        order=max_order + i,
                    )
                    next_order = max(next_order, task_case.order)
                    task_cases.append(task_case)
                except ApiTestCase.DoesNotExist:
                    logger.warning(f"Test case [ID={testcase_id}] does not exist, skipping")
                    continue

            for i, interface_case_id in enumerate(new_interface_ids, 1):
                try:
                    lookup = {'id': interface_case_id}
                    if project_pk:
                        lookup['project_id'] = project_pk
                    interface_case = ApiInterfaceCase.objects.get(**lookup)
                    task_case = ApiTestTaskCase.objects.create(
                        task_suite=task_suite,
                        case_type=ApiTestTaskCase.CASE_TYPE_INTERFACE,
                        interface_case=interface_case,
                        order=next_order + i,
                    )
                    task_cases.append(task_case)
                except ApiInterfaceCase.DoesNotExist:
                    logger.warning(
                        f"Interface case [ID={interface_case_id}] does not exist, skipping"
                    )
                    continue
        return task_cases

    @staticmethod
    def add_testcases(task_suite, testcase_ids, project_pk=None):
        return ApiTestTaskService.add_cases(
            task_suite,
            testcase_ids=testcase_ids,
            interface_case_ids=[],
            project_pk=project_pk,
        )

    @staticmethod
    def remove_case(task_suite, case_type, case_id):
        filters = {
            'task_suite': task_suite,
            'case_type': case_type,
        }
        if case_type == ApiTestTaskCase.CASE_TYPE_INTERFACE:
            filters['interface_case_id'] = case_id
        else:
            filters['testcase_id'] = case_id

        try:
            task_case = ApiTestTaskCase.objects.get(**filters)
            task_case.delete()
            for i, tc in enumerate(
                task_suite.api_task_cases.all().order_by('order'), 1
            ):
                tc.order = i
                tc.save()
            return True
        except ApiTestTaskCase.DoesNotExist:
            return False

    @staticmethod
    def remove_testcase(task_suite, testcase_id):
        return ApiTestTaskService.remove_case(
            task_suite,
            ApiTestTaskCase.CASE_TYPE_SCENARIO,
            testcase_id,
        )


class ApiTestTaskExecutionService:
    """Service class for test task execution operations."""

    @staticmethod
    def create_execution(task_suite, environment_id=None, user=None):
        with transaction.atomic():
            execution = ApiTestTaskExecution.objects.create(
                task_suite=task_suite,
                environment_id=environment_id,
                executed_by=user,
                total_count=task_suite.api_task_cases.count(),
            )
            for task_case in task_suite.api_task_cases.all().order_by('order'):
                result_kwargs = {
                    'execution': execution,
                    'case_type': task_case.case_type,
                }
                if task_case.case_type == ApiTestTaskCase.CASE_TYPE_INTERFACE:
                    result_kwargs['interface_case'] = task_case.interface_case
                else:
                    result_kwargs['testcase'] = task_case.testcase
                ApiTestTaskCaseResult.objects.create(**result_kwargs)
        return execution

    @staticmethod
    def execute_task(execution):
        """Execute a test task synchronously."""
        from api_testcases.services import InterfaceCaseExecutionService, TestExecutionService

        execution.start()

        # Get environment configuration
        environment = None
        if execution.environment:
            try:
                env = execution.environment
                env_variables = env.get_all_variables()
                if isinstance(env_variables, str):
                    try:
                        import json
                        env_variables = json.loads(env_variables)
                    except (json.JSONDecodeError, ValueError):
                        env_variables = {}
                elif not isinstance(env_variables, dict):
                    env_variables = {}

                environment = {
                    'id': env.id,
                    'name': env.name,
                    'base_url': env.base_url,
                    'variables': env_variables,
                    'verify_ssl': env.verify_ssl
                }
            except Exception as e:
                logger.error(f"Error getting environment info: {str(e)}")
                environment = None

        task_suite = execution.task_suite
        case_results = execution.api_case_results.all().order_by('id')

        success_count = 0
        fail_count = 0
        error_count = 0

        for case_result in case_results:
            case_result.status = 'running'
            case_result.start_time = timezone.now()
            case_result.save()

            try:
                case_obj = case_result.case_object
                if case_result.case_type == ApiTestTaskCase.CASE_TYPE_INTERFACE:
                    report = InterfaceCaseExecutionService.run_interface_case(
                        case_obj, environment, execution.executed_by
                    )
                    case_result.interface_report = report
                else:
                    report = TestExecutionService.run_testcase(
                        case_obj, environment, execution.executed_by
                    )
                    case_result.report = report

                case_result.end_time = timezone.now()
                case_result.duration = (
                    case_result.end_time - case_result.start_time
                ).total_seconds()

                if report.status == 'success':
                    case_result.status = 'success'
                    success_count += 1
                else:
                    case_result.status = 'failure'
                    fail_count += 1

                case_result.save()

                if task_suite.fail_fast and report.status != 'success':
                    logger.info(
                        f"Task suite [{task_suite.name}] fail_fast enabled, "
                        f"case [{case_obj.name}] failed, stopping"
                    )
                    for remaining in case_results.filter(status='pending'):
                        remaining.status = 'skipped'
                        remaining.save()
                    break

            except Exception as e:
                case_name = case_result.case_name or f"ID={case_result.id}"
                logger.error(
                    f"Error executing case [{case_name}]: {str(e)}"
                )
                case_result.status = 'error'
                case_result.end_time = timezone.now()
                case_result.duration = (
                    case_result.end_time - case_result.start_time
                ).total_seconds()
                case_result.error_message = str(e)
                case_result.save()
                error_count += 1

                if task_suite.fail_fast:
                    for remaining in case_results.filter(status='pending'):
                        remaining.status = 'skipped'
                        remaining.save()
                    break

        execution.complete(success_count, fail_count, error_count)

    @staticmethod
    def execute_task_async(execution_id):
        try:
            execution = ApiTestTaskExecution.objects.get(id=execution_id)
            ApiTestTaskExecutionService.execute_task(execution)
        except ApiTestTaskExecution.DoesNotExist:
            logger.error(f"Execution [ID={execution_id}] does not exist")
        except Exception as e:
            logger.error(f"Async task execution error: {str(e)}")
            try:
                execution = ApiTestTaskExecution.objects.get(id=execution_id)
                execution.fail()
            except Exception:
                pass
