from typing import Dict, List, Optional, Tuple
import logging
from django.utils import timezone
from django.db import transaction
from api_interfaces.logging_utils import summarize_for_log
from .models import (
    ApiTestCase, ApiTestCaseStep, ApiTestReport, ApiTestReportDetail,
    ApiInterfaceCase, ApiInterfaceCaseReport, ApiInterfaceCaseReportDetail,
)
from .runner import TestCaseRunner

logger = logging.getLogger('testrunner')


class TestCaseService:
    """Test case service class."""

    @staticmethod
    def create_testcase(data: Dict, user) -> ApiTestCase:
        from api_interfaces.models import ApiInterface

        steps_data = data.pop('steps_info', [])

        with transaction.atomic():
            testcase = ApiTestCase.objects.create(
                created_by=user,
                **data
            )

            for index, step_data in enumerate(steps_data, 1):
                interface_id = step_data.pop('interface_id')
                interface = ApiInterface.objects.get(id=interface_id, project_id=data.get('project_id') or testcase.project_id)

                interface_data = {
                    'method': interface.method,
                    'url': interface.url,
                    'headers': interface.headers,
                    'params': interface.params,
                    'body': interface.body,
                    'validators': interface.validators,
                    'extract': interface.extract,
                    'setup_hooks': interface.setup_hooks,
                    'teardown_hooks': interface.teardown_hooks,
                    'variables': interface.variables
                }

                ApiTestCaseStep.objects.create(
                    testcase=testcase,
                    order=index,
                    interface_data=interface_data,
                    origin_interface=interface,
                    **step_data
                )

        return testcase

    @staticmethod
    def validate_testcase_data(data: Dict) -> Tuple[bool, Optional[str]]:
        required_fields = ['name', 'project']
        for field in required_fields:
            if field not in data:
                return False, f'Missing required field: {field}'

        steps = data.get('steps_info', [])
        if not steps:
            return False, 'At least one test step is required'

        for index, step in enumerate(steps):
            if 'name' not in step:
                return False, f'Step {index + 1} is missing a name'
            if 'interface_id' not in step:
                return False, f'Step {index + 1} is missing an interface_id'

        return True, None


class TestExecutionService:
    """Test execution service class."""

    @staticmethod
    def _coerce_bool(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {'true', '1', 'yes', 'on'}:
                return True
            if normalized in {'false', '0', 'no', 'off'}:
                return False
        return None

    @staticmethod
    def _resolve_verify(config: Dict, environment: Dict) -> bool:
        case_verify = TestExecutionService._coerce_bool(config.get('verify'))
        if case_verify is not None:
            return case_verify

        env_verify = None
        if 'verify_ssl' in environment:
            env_verify = TestExecutionService._coerce_bool(environment.get('verify_ssl'))
        elif 'verify' in environment:
            env_verify = TestExecutionService._coerce_bool(environment.get('verify'))

        if env_verify is not None:
            return env_verify

        return False

    @staticmethod
    def _resolve_verify_source(config: Dict, environment: Dict) -> str:
        if TestExecutionService._coerce_bool(config.get('verify')) is not None:
            return 'testcase'

        if 'verify_ssl' in environment:
            env_verify = TestExecutionService._coerce_bool(environment.get('verify_ssl'))
        elif 'verify' in environment:
            env_verify = TestExecutionService._coerce_bool(environment.get('verify'))
        else:
            env_verify = None

        if env_verify is not None:
            return 'environment'

        return 'default'

    @staticmethod
    def _prepare_config(config: Dict, environment: Optional[Dict] = None) -> Dict:
        if not isinstance(config, dict):
            config = {}
        if not isinstance(environment, dict):
            environment = {}

        env_variables = environment.get('variables', {})
        if not isinstance(env_variables, dict):
            if isinstance(env_variables, str) and env_variables.strip():
                try:
                    import json
                    env_variables = json.loads(env_variables)
                    if not isinstance(env_variables, dict):
                        env_variables = {}
                except (json.JSONDecodeError, Exception):
                    env_variables = {}
            else:
                env_variables = {}

        case_variables = config.get('variables', {})
        if not isinstance(case_variables, dict):
            if isinstance(case_variables, str) and case_variables.strip():
                try:
                    import json
                    case_variables = json.loads(case_variables)
                    if not isinstance(case_variables, dict):
                        case_variables = {}
                except (json.JSONDecodeError, Exception):
                    case_variables = {}
            else:
                case_variables = {}

        case_parameters = config.get('parameters', {})
        if not isinstance(case_parameters, dict):
            if isinstance(case_parameters, str) and case_parameters.strip():
                try:
                    import json
                    case_parameters = json.loads(case_parameters)
                    if not isinstance(case_parameters, dict):
                        case_parameters = {}
                except (json.JSONDecodeError, Exception):
                    case_parameters = {}
            else:
                case_parameters = {}

        return {
            "base_url": config.get('base_url') or environment.get('base_url', ''),
            "verify": TestExecutionService._resolve_verify(config, environment),
            "variables": {**env_variables, **case_variables},
            "export": config.get('export', []),
            "parameters": case_parameters
        }

    @staticmethod
    def run_testcase(
        testcase: ApiTestCase,
        environment: Optional[Dict] = None,
        user=None
    ) -> ApiTestReport:
        source_config = testcase.config if isinstance(testcase.config, dict) else {}
        source_environment = environment if isinstance(environment, dict) else {}
        verify_source = TestExecutionService._resolve_verify_source(
            source_config,
            source_environment,
        )
        config = TestExecutionService._prepare_config(testcase.config, environment)
        testcase.config = config
        testcase._case_verify_explicit = verify_source == 'testcase'

        runner = TestCaseRunner(testcase)
        runner.run_testcase(environment)

        summary = runner.get_summary()
        step_results = summary.get('step_results', [])
        logger.info(
            "Testcase execution summary generated: trace_id=%s testcase_id=%s "
            "testcase_name=%s success=%s step_count=%s",
            runner.trace_id,
            testcase.id,
            testcase.name,
            summary['success'],
            len(step_results),
        )

        with transaction.atomic():
            report = ApiTestReport.objects.create(
                name=f"{testcase.name}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                status='success' if summary['success'] else 'failure',
                success_count=len([r for r in step_results if r['success']]),
                fail_count=len([r for r in step_results if not r['success']]),
                error_count=0,
                duration=summary['time']['duration'],
                summary=summary,
                testcase=testcase,
                executed_by=user,
                environment_id=environment.get('id') if environment else None
            )
            logger.info(
                "Testcase report saved: trace_id=%s report_id=%s testcase_id=%s "
                "status=%s success_count=%s fail_count=%s",
                runner.trace_id,
                report.id,
                testcase.id,
                report.status,
                report.success_count,
                report.fail_count,
            )

            steps_by_order = {step.order: step for step in testcase.steps.all()}

            for i, step_result in enumerate(step_results):
                try:
                    step = steps_by_order.get(i + 1)
                    if step is None:
                        ordered_steps = list(testcase.steps.all().order_by('order'))
                        if i < len(ordered_steps):
                            step = ordered_steps[i]
                        else:
                            continue

                    step_success = step_result['success']

                    ApiTestReportDetail.objects.create(
                        report=report,
                        step=step,
                        success=step_success,
                        elapsed=step_result['elapsed'],
                        request=step_result['data']['request'],
                        response=step_result['data']['response'],
                        validators=step_result['data']['validators'],
                        extracted_variables=step_result['data']['extracted_variables'],
                        attachment=step_result['attachment']
                    )
                    request_body = step_result['data']['request'].get('body')
                    status_code = step_result['data']['response'].get('status_code')
                    logger.info(
                        "Testcase report detail saved: trace_id=%s report_id=%s "
                        "testcase_id=%s step_id=%s step_name=%s status_code=%s "
                        "success=%s recorded_request_body_summary=%s "
                        "transport_failure_record_body_may_be_empty=%s",
                        runner.trace_id,
                        report.id,
                        testcase.id,
                        step.id,
                        step.name,
                        status_code,
                        step_success,
                        summarize_for_log(request_body),
                        status_code == 0 and request_body is None,
                    )
                except Exception as e:
                    logger.error(
                        "Failed to create test report detail: trace_id=%s "
                        "testcase_id=%s error=%s",
                        runner.trace_id,
                        testcase.id,
                        str(e),
                    )
                    continue

        return report

    @staticmethod
    def run_batch(
        testcases: List[ApiTestCase],
        environment: Optional[Dict] = None,
        user=None
    ) -> List[ApiTestReport]:
        reports = []
        for testcase in testcases:
            report = TestExecutionService.run_testcase(testcase, environment, user)
            reports.append(report)
        return reports

    @staticmethod
    def get_statistics(reports: List[ApiTestReport]) -> Dict:
        total = len(reports)
        if not total:
            return {
                'total': 0,
                'success': 0,
                'failure': 0,
                'error': 0,
                'success_rate': '0%'
            }

        success = len([r for r in reports if r.status == 'success'])
        failure = len([r for r in reports if r.status == 'failure'])
        error = len([r for r in reports if r.status == 'error'])

        return {
            'total': total,
            'success': success,
            'failure': failure,
            'error': error,
            'success_rate': f"{(success / total * 100):.2f}%"
        }


class InterfaceCaseExecutionService:
    """Execution service for single-interface cases."""

    @staticmethod
    def run_interface_case(
        interface_case: ApiInterfaceCase,
        environment: Optional[Dict] = None,
        user=None,
    ) -> ApiInterfaceCaseReport:
        source_config = interface_case.config if isinstance(interface_case.config, dict) else {}
        source_environment = environment if isinstance(environment, dict) else {}
        verify_source = TestExecutionService._resolve_verify_source(
            source_config,
            source_environment,
        )
        config = TestExecutionService._prepare_config(interface_case.config, environment)
        interface_case.config = config
        interface_case._case_verify_explicit = verify_source == 'testcase'

        runner = TestCaseRunner(interface_case, environment=environment)
        runner.run_testcase(environment)

        summary = runner.get_summary()
        step_results = runner.get_step_results()
        logger.info(
            "Interface case execution summary generated: trace_id=%s interface_case_id=%s "
            "interface_case_name=%s success=%s step_count=%s",
            runner.trace_id,
            interface_case.id,
            interface_case.name,
            summary['success'],
            len(step_results),
        )

        extract_persistence = {
            'matched_count': 0,
            'created_count': 0,
            'updated_count': 0,
            'skipped_no_environment': False,
        }

        environment_id = environment.get('id') if environment else None
        ordered_steps = list(interface_case.steps.all().order_by('order'))

        for index, step_result in enumerate(step_results):
            if index >= len(ordered_steps):
                continue

            step = ordered_steps[index]
            step_data = step.interface_data if isinstance(step.interface_data, dict) else {}
            persistence_result = persist_project_extract_variables(
                project_id=interface_case.project_id,
                environment_id=environment_id,
                extracted_variables=step_result.get('data', {}).get('extracted_variables', {}),
                extract_meta=step_data.get('extract_meta', {}),
            )
            extract_persistence['matched_count'] += persistence_result.get('matched_count', 0)
            extract_persistence['created_count'] += persistence_result.get('created_count', 0)
            extract_persistence['updated_count'] += persistence_result.get('updated_count', 0)
            extract_persistence['skipped_no_environment'] = (
                extract_persistence['skipped_no_environment']
                or persistence_result.get('skipped_no_environment', False)
            )

        summary['extract_persistence'] = extract_persistence

        with transaction.atomic():
            report = ApiInterfaceCaseReport.objects.create(
                name=f"{interface_case.name}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                status='success' if summary['success'] else 'failure',
                success_count=len([r for r in step_results if r['success']]),
                fail_count=len([r for r in step_results if not r['success']]),
                error_count=0,
                duration=summary['time']['duration'],
                summary=summary,
                interface_case=interface_case,
                executed_by=user,
                environment_id=environment_id,
            )
            logger.info(
                "Interface case report saved: trace_id=%s report_id=%s interface_case_id=%s "
                "status=%s success_count=%s fail_count=%s",
                runner.trace_id,
                report.id,
                interface_case.id,
                report.status,
                report.success_count,
                report.fail_count,
            )

            steps_by_order = {step.order: step for step in interface_case.steps.all()}

            for i, step_result in enumerate(step_results):
                try:
                    step = steps_by_order.get(i + 1)
                    if step is None:
                        ordered_steps = list(interface_case.steps.all().order_by('order'))
                        if i < len(ordered_steps):
                            step = ordered_steps[i]
                        else:
                            continue

                    ApiInterfaceCaseReportDetail.objects.create(
                        report=report,
                        step=step,
                        success=step_result['success'],
                        elapsed=step_result['elapsed'],
                        request=step_result['data'].get('request', {}),
                        response=step_result['data'].get('response', {}),
                        validators=step_result['data'].get('validators', []),
                        extracted_variables=step_result['data'].get('extracted_variables', {}),
                        attachment=step_result['attachment'],
                    )
                except Exception as e:
                    logger.error(
                        "Failed to create interface case report detail: trace_id=%s "
                        "interface_case_id=%s error=%s",
                        runner.trace_id,
                        interface_case.id,
                        str(e),
                    )
                    continue

        return report
