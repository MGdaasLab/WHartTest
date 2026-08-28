from typing import Dict, List, Optional
import copy
import json
import logging
import types
from httprunner import HttpRunner, Config, Step, RunRequest, RunSqlRequest
from httprunner.client import sanitize_json_record
from api_interfaces.logging_utils import new_trace_id, summarize_for_log
from file_management.services import validate_file_ids, serialize_file_for_runtime
from api_interfaces.payloads import (
    flatten_key_value_pairs,
    normalize_request_body,
    prepare_request_body_for_runner,
)
from api_interfaces.validators import prepare_validator_for_runtime
from api_interfaces.runner_uploads import (
    apply_upload_files_to_step,
    collect_file_ids_from_body,
    merge_file_ids,
)
from .models import ApiTestCase, ApiTestCaseStep

logger = logging.getLogger('testrunner')


def load_custom_functions(project_id):
    """Load custom functions for a project."""
    functions = {}
    loaded_count = 0
    error_count = 0

    try:
        from api_functions.models import ApiCustomFunction
        custom_functions = ApiCustomFunction.objects.filter(
            project_id=project_id,
            is_active=True
        ).select_related('project')

        project_name = custom_functions[0].project.name if custom_functions else "Unknown"
        logger.info(f"Loading custom functions for project [{project_name}]")

        for func in custom_functions:
            try:
                module = types.ModuleType(func.name)
                code = compile(func.code, func.name, 'exec')
                exec(code, module.__dict__)

                module_functions = {
                    name: obj for name, obj in module.__dict__.items()
                    if isinstance(obj, types.FunctionType)
                }

                if not module_functions:
                    logger.warning(f"Function [{func.name}] has no callable functions")
                    error_count += 1
                    continue

                for name in module_functions:
                    if name in functions:
                        logger.warning(f"Function name conflict: {name}, using latest definition")

                functions.update(module_functions)
                loaded_count += 1
                logger.debug(f"Loaded function: {func.name}, methods: {list(module_functions.keys())}")

            except SyntaxError as e:
                logger.error(f"Function [{func.name}] syntax error: {str(e)}")
                error_count += 1
            except Exception as e:
                logger.error(f"Failed to load function [{func.name}]: {str(e)}")
                error_count += 1

        logger.info(f"Project [{project_name}] function loading complete: {loaded_count} success, {error_count} failed")

    except Exception as e:
        logger.error(f"Error loading custom functions for project [{project_id}]: {str(e)}")

    return functions



def _resolve_runtime_files(project_id, file_ids):
    if not project_id or not file_ids:
        return []
    try:
        from projects.models import Project
        project = Project.objects.get(id=project_id)
        return [serialize_file_for_runtime(asset) for asset in validate_file_ids(file_ids, project)]
    except Exception as exc:
        raise ValueError(f'附件校验失败: {exc}') from exc


class TestCaseRunner(HttpRunner):
    """Test case runner extending HttpRunner."""

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
    def _validators_indicate_failure(validators: Optional[Dict]) -> bool:
        """Return True when validators explicitly mark the step as failed."""
        if not isinstance(validators, dict) or not validators:
            return False

        if validators.get('success') is False:
            return True

        validate_extractor = validators.get('validate_extractor')
        if not isinstance(validate_extractor, list):
            return False

        return any(
            isinstance(validator, dict) and validator.get('check_result') == 'fail'
            for validator in validate_extractor
        )

    def _create_http_step(self, step_name: str, interface_data: Dict) -> RunRequest:
        """Create an HTTP request step."""
        step_obj = RunRequest(step_name)

        method = interface_data['method'].lower()
        url = interface_data['url']
        if not url.startswith(('http://', 'https://')):
            url = f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"

        if interface_data.get('setup_hooks'):
            for hook in interface_data['setup_hooks']:
                step_obj = step_obj.setup_hook(hook)

        step_obj = getattr(step_obj, method)(url)

        if interface_data.get('teardown_hooks'):
            for hook in interface_data['teardown_hooks']:
                step_obj = step_obj.teardown_hook(hook)

        return step_obj

    def _create_sql_step(self, step_name: str, interface_data: Dict) -> RunSqlRequest:
        """Create a SQL request step."""
        step_obj = RunSqlRequest(step_name)

        if interface_data.get('db_config'):
            db_config = interface_data['db_config']
            step_obj = step_obj.with_db_config(
                user=db_config.get('user'),
                password=db_config.get('password'),
                ip=db_config.get('ip'),
                port=db_config.get('port'),
                database=db_config.get('database'),
                psm=db_config.get('psm')
            )

        if interface_data.get('setup_hooks'):
            for hook in interface_data['setup_hooks']:
                step_obj = step_obj.setup_hook(hook)

        sql_method = interface_data.get('sql_method', 'fetchone').upper()
        sql = interface_data.get('sql', '')

        if sql_method == 'FETCHONE':
            step_obj = step_obj.fetchone(sql)
        elif sql_method == 'FETCHMANY':
            size = interface_data.get('sql_size', 10)
            step_obj = step_obj.fetchmany(sql, size)
        elif sql_method == 'FETCHALL':
            step_obj = step_obj.fetchall(sql)
        elif sql_method == 'INSERT':
            step_obj = step_obj.insert(sql)
        elif sql_method == 'UPDATE':
            step_obj = step_obj.update(sql)
        elif sql_method == 'DELETE':
            step_obj = step_obj.delete(sql)
        else:
            logger.warning(f"Unsupported SQL method: {sql_method}, using fetchone")
            step_obj = step_obj.fetchone(sql)

        if interface_data.get('teardown_hooks'):
            for hook in interface_data['teardown_hooks']:
                step_obj = step_obj.teardown_hook(hook)

        return step_obj

    def __init__(self, testcase: ApiTestCase):
        super().__init__()
        self.testcase = testcase
        self.teststeps = []
        self.trace_id = new_trace_id('tc')
        self.step_body_diagnostics = []
        self.step_request_snapshots = []

        # Load and register custom functions
        try:
            custom_functions = load_custom_functions(testcase.project_id)
            if custom_functions:
                self.functions = custom_functions
                from httprunner.parser import Parser
                self.parser = Parser(functions_mapping=custom_functions)
                logger.info(
                    "Test case loaded custom functions: trace_id=%s testcase_id=%s "
                    "testcase_name=%s functions=%s",
                    self.trace_id,
                    testcase.id,
                    testcase.name,
                    list(custom_functions.keys()),
                )
            else:
                logger.warning(
                    "Project has no available custom functions: trace_id=%s project=%s",
                    self.trace_id,
                    testcase.project.name,
                )
        except Exception as e:
            logger.error(
                "Failed to load custom functions: trace_id=%s project=%s error=%s",
                self.trace_id,
                testcase.project.name,
                str(e),
            )

        # Build config
        try:
            self.config = Config(self.testcase.name)

            if isinstance(testcase.config, str):
                try:
                    testcase.config = json.loads(testcase.config)
                except (json.JSONDecodeError, ValueError):
                    testcase.config = {}
            elif not isinstance(testcase.config, dict):
                testcase.config = {}

            self.base_url = self.testcase.config.get('base_url', '')
            raw_verify = self.testcase.config.get('verify', None)
            parsed_verify = self._coerce_bool(raw_verify)
            self.case_verify_explicit = getattr(
                testcase,
                '_case_verify_explicit',
                parsed_verify is not None,
            )
            self.verify = parsed_verify
            variables = self.testcase.config.get('variables', {})
            if isinstance(variables, str):
                try:
                    variables = json.loads(variables)
                except (json.JSONDecodeError, ValueError):
                    variables = {}
            elif not isinstance(variables, dict):
                variables = {}
            self.variables = variables

            if self.base_url:
                self.config.base_url(self.base_url)
            if self.verify is not None:
                self.config.verify(self.verify)
            if self.variables and isinstance(self.variables, dict):
                self.config.variables(**self.variables)

        except Exception as e:
            logger.error(f"Test case [{testcase.name}] config initialization failed: {str(e)}")
            raise

        # Build test steps
        steps = []
        for step in self.testcase.steps.all().order_by('order'):
            interface_data = step.interface_data
            step_file_ids = merge_file_ids(
                step.file_ids,
                interface_data.get('file_ids') if isinstance(interface_data, dict) else [],
                collect_file_ids_from_body(interface_data.get('body') if isinstance(interface_data, dict) else None),
            )
            if isinstance(interface_data, dict):
                interface_data['file_ids'] = step_file_ids
            step_runtime_files = _resolve_runtime_files(self.testcase.project_id, step_file_ids)
            if step_runtime_files:
                self.variables = self.variables or {}
                self.variables['file_ids'] = [item['id'] for item in step_runtime_files]
                self.variables['files'] = step_runtime_files
            step_type = interface_data.get('type', 'http').lower()

            if step_type == 'sql':
                step_obj = self._create_sql_step(step.name, interface_data)
                request_snapshot = None
            else:
                step_obj = self._create_http_step(step.name, interface_data)
                snapshot_url = interface_data.get('url', '')
                if not snapshot_url.startswith(('http://', 'https://')):
                    snapshot_url = f"{self.base_url.rstrip('/')}/{snapshot_url.lstrip('/')}"
                request_snapshot = {
                    'method': interface_data.get('method'),
                    'url': snapshot_url,
                    'headers': {},
                    'body': None,
                }

            # Add params for HTTP requests
            if step_type != 'sql' and interface_data.get('params'):
                params = {}
                if not isinstance(self.variables, dict):
                    self.variables = {}
                for k, v in flatten_key_value_pairs(interface_data['params']).items():
                    if isinstance(v, str) and v.startswith('$'):
                        var_name = v[1:]
                        if var_name in self.variables:
                            params[k] = self.variables[var_name]
                        else:
                            params[k] = v
                    else:
                        params[k] = v
                step_obj = step_obj.with_params(**params)

            # Add headers for HTTP requests
            if step_type != 'sql':
                try:
                    headers = interface_data.get('headers')
                    if headers:
                        headers_dict = flatten_key_value_pairs(headers)

                        if headers_dict:
                            step_obj = step_obj.with_headers(**headers_dict)
                            if request_snapshot is not None:
                                request_snapshot['headers'] = copy.deepcopy(headers_dict)
                except Exception as e:
                    logger.error(f"Error processing headers for step [{step.name}]: {str(e)}")

            # Add request body for HTTP requests
            if step_type != 'sql':
                raw_body = interface_data.get('body')
                body_diagnostic = {
                    'trace_id': self.trace_id,
                    'body_source': 'testcase_step_interface_data',
                    'testcase_id': self.testcase.id,
                    'step_id': step.id,
                    'step_order': step.order,
                    'step_name': step.name,
                    'body_present': 'body' in interface_data,
                    'raw_summary': summarize_for_log(raw_body),
                    'prepared': False,
                    'skipped_reason': None,
                }
                logger.info(
                    "Testcase step body source: trace_id=%s testcase_id=%s "
                    "testcase_name=%s step_id=%s step_order=%s step_name=%s "
                    "method=%s url=%s body_source=%s body_present=%s body_summary=%s",
                    self.trace_id,
                    self.testcase.id,
                    self.testcase.name,
                    step.id,
                    step.order,
                    step.name,
                    interface_data.get('method'),
                    interface_data.get('url'),
                    body_diagnostic['body_source'],
                    'body' in interface_data,
                    summarize_for_log(raw_body),
                )
            else:
                body_diagnostic = None

            if step_type != 'sql' and interface_data.get('body'):
                try:
                    normalized_body = normalize_request_body(interface_data['body'])
                    body = prepare_request_body_for_runner(normalized_body)
                except Exception:
                    logger.exception(
                        "Testcase step body normalization failed: trace_id=%s "
                        "testcase_id=%s testcase_name=%s step_id=%s step_name=%s "
                        "body_summary=%s",
                        self.trace_id,
                        self.testcase.id,
                        self.testcase.name,
                        step.id,
                        step.name,
                        summarize_for_log(interface_data.get('body')),
                    )
                    raise

                if isinstance(body, str) and body.startswith('$'):
                    var_name = body[1:]
                    if isinstance(self.variables, dict) and var_name in self.variables:
                        body = self.variables[var_name]

                if body is not None:
                    target = (
                        'data'
                        if normalized_body['type'] in {'form-data', 'x-www-form-urlencoded', 'binary'}
                        else 'json'
                    )
                    logger.info(
                        "Testcase step body prepared: trace_id=%s testcase_id=%s "
                        "testcase_name=%s step_id=%s step_order=%s step_name=%s "
                        "body_type=%s target=%s "
                        "prepared_summary=%s",
                        self.trace_id,
                        self.testcase.id,
                        self.testcase.name,
                        step.id,
                        step.order,
                        step.name,
                        normalized_body['type'],
                        target,
                        summarize_for_log(body),
                    )
                    if body_diagnostic is not None:
                        body_diagnostic.update({
                            'prepared': True,
                            'body_type': normalized_body['type'],
                            'target': target,
                            'prepared_summary': summarize_for_log(body),
                        })
                    if request_snapshot is not None:
                        request_snapshot['body'] = copy.deepcopy(body)
                    step_obj, upload_applied = apply_upload_files_to_step(
                        step_obj,
                        normalized_body,
                        step_runtime_files,
                    )
                    if request_snapshot is not None:
                        request_snapshot['headers'] = copy.deepcopy(
                            step_obj.struct().request.headers,
                        )
                    if normalized_body['type'] in {'form-data', 'x-www-form-urlencoded', 'binary'}:
                        if not upload_applied:
                            step_obj = step_obj.with_data(body)
                    else:
                        step_obj = step_obj.with_json(body)
                else:
                    logger.info(
                        "Testcase step body normalized to empty payload: trace_id=%s "
                        "testcase_id=%s testcase_name=%s step_id=%s step_order=%s "
                        "step_name=%s body_type=%s",
                        self.trace_id,
                        self.testcase.id,
                        self.testcase.name,
                        step.id,
                        step.order,
                        step.name,
                        normalized_body['type'],
                    )
                    if body_diagnostic is not None:
                        body_diagnostic.update({
                            'body_type': normalized_body['type'],
                            'skipped_reason': 'normalized_body_is_none',
                        })
            elif step_type != 'sql':
                if body_diagnostic is not None:
                    body_diagnostic['skipped_reason'] = (
                        'missing_or_falsey_body_by_current_runner_condition'
                    )
                logger.info(
                    "Testcase step body skipped by current runner condition: "
                    "trace_id=%s testcase_id=%s testcase_name=%s step_id=%s "
                    "step_order=%s step_name=%s skipped_reason=%s body_summary=%s",
                    self.trace_id,
                    self.testcase.id,
                    self.testcase.name,
                    step.id,
                    step.order,
                    step.name,
                    body_diagnostic['skipped_reason'] if body_diagnostic else None,
                    summarize_for_log(interface_data.get('body')),
                )

            # Set export variables
            if interface_data.get('export'):
                step_obj.struct().export = interface_data['export']

            # Add variable extractors
            if interface_data.get('extract'):
                step_obj = step_obj.extract()
                extract_meta = interface_data.get('extract_meta')
                extract_meta = extract_meta if isinstance(extract_meta, dict) else {}
                for var_name, expr in interface_data['extract'].items():
                    meta = extract_meta.get(var_name, {})
                    source = meta.get('source') if isinstance(meta, dict) else 'response'
                    step_obj = step_obj.with_jmespath(expr, var_name, source=source)

            # Create Step object
            step = Step(step_obj)

            # Add validators
            if interface_data.get('validators'):
                step_obj = step_obj.validate()
                for validator in interface_data['validators']:
                    runtime_validator = prepare_validator_for_runtime(validator)
                    if not runtime_validator:
                        logger.warning(f"Unsupported validator format: {validator}")
                        continue
                    step_obj.struct().validators.append(runtime_validator)

            self.teststeps.append(step)
            if body_diagnostic is not None:
                self.step_body_diagnostics.append(body_diagnostic)
            if request_snapshot is not None:
                self.step_request_snapshots.append(request_snapshot)

    def run_testcase(self, environment: Optional[Dict] = None) -> "TestCaseRunner":
        """Execute the test case."""
        logger.info(
            "Starting test case execution: trace_id=%s testcase_id=%s testcase_name=%s",
            self.trace_id,
            self.testcase.id,
            self.testcase.name,
        )

        case_variables = self.variables.copy() if isinstance(self.variables, dict) else {}

        if environment:
            if environment.get('base_url'):
                self.config.base_url(environment['base_url'])
                logger.info(
                    "Using environment base_url: trace_id=%s testcase_id=%s base_url=%s",
                    self.trace_id,
                    self.testcase.id,
                    environment['base_url'],
                )

            verify_value = None
            if 'verify_ssl' in environment:
                verify_value = self._coerce_bool(environment.get('verify_ssl'))
            elif 'verify' in environment:
                verify_value = self._coerce_bool(environment.get('verify'))

            if verify_value is not None and not getattr(self, 'case_verify_explicit', False):
                self.verify = verify_value
                self.config.verify(verify_value)
                logger.info(
                    "Using environment verify setting: trace_id=%s testcase_id=%s verify=%s",
                    self.trace_id,
                    self.testcase.id,
                    verify_value,
                )
            elif verify_value is not None:
                logger.info(
                    "Keeping testcase verify setting over environment: "
                    "trace_id=%s testcase_id=%s testcase_verify=%s environment_verify=%s",
                    self.trace_id,
                    self.testcase.id,
                    self.verify,
                    verify_value,
                )

            if environment.get('variables'):
                env_variables = environment.get('variables', {})
                if not isinstance(env_variables, dict):
                    env_variables = {}
                if not isinstance(self.variables, dict):
                    self.variables = {}
                case_variables = self.variables.copy()
                case_variables.update(env_variables)
                self.config.variables(**case_variables)
        elif isinstance(self.variables, dict):
            self.config.variables(**case_variables)

        # Apply global request headers
        try:
            from api_environments.models import ApiGlobalRequestHeader
            if self.testcase.project_id:
                global_headers = ApiGlobalRequestHeader.objects.filter(
                    project_id=self.testcase.project_id,
                    is_enabled=True
                )

                for header in global_headers:
                    header_name = header.name
                    header_value = header.value

                    try:
                        if header_value.startswith('${') and header_value.endswith('}'):
                            var_name = header_value[2:-1]
                            if var_name in case_variables:
                                header_value = case_variables[var_name]
                        elif header_value.startswith('$') and len(header_value) > 1:
                            var_name = header_value[1:]
                            if var_name in case_variables:
                                header_value = case_variables[var_name]
                    except Exception:
                        pass

                    for step in self.testcase.steps.all().order_by('order'):
                        interface_data = step.interface_data
                        if 'headers' not in interface_data:
                            interface_data['headers'] = {}
                        headers_dict = interface_data['headers']
                        if isinstance(headers_dict, dict) and header_name not in headers_dict:
                            headers_dict[header_name] = header_value
        except Exception as e:
            logger.error(f"Error applying global request headers: {str(e)}")

        try:
            self.test_start()
            logger.info(
                "Test case execution complete: trace_id=%s testcase_id=%s testcase_name=%s",
                self.trace_id,
                self.testcase.id,
                self.testcase.name,
            )
        except Exception as e:
            logger.error(
                "Test case execution error: trace_id=%s testcase_id=%s error=%s",
                self.trace_id,
                self.testcase.id,
                str(e),
            )
            raise

        return self

    @staticmethod
    def _apply_prepared_request_fallback(
        request_data: Dict,
        status_code,
        request_snapshot: Optional[Dict],
    ) -> bool:
        """Recover display request data when httprunner safe mode drops it."""
        if status_code != 0 or not request_snapshot:
            return False

        fallback_used = False

        if not request_data.get('method') and request_snapshot.get('method'):
            request_data['method'] = request_snapshot['method']
            fallback_used = True

        if not request_data.get('url') and request_snapshot.get('url'):
            request_data['url'] = request_snapshot['url']
            fallback_used = True

        if not request_data.get('headers') and request_snapshot.get('headers'):
            request_data['headers'] = copy.deepcopy(request_snapshot['headers'])
            fallback_used = True

        if request_data.get('body') is None and request_snapshot.get('body') is not None:
            request_data['body'] = copy.deepcopy(request_snapshot['body'])
            fallback_used = True

        return fallback_used

    def get_step_results(self) -> List[Dict]:
        """Get step execution results."""
        summary = super().get_summary()
        results = []
        request_result_index = 0
        trace_id = getattr(self, 'trace_id', 'unknown')
        testcase = getattr(self, 'testcase', None)
        testcase_id = getattr(testcase, 'id', None)
        step_body_diagnostics = getattr(self, 'step_body_diagnostics', [])
        step_request_snapshots = getattr(self, 'step_request_snapshots', [])

        for index, step_result in enumerate(summary.step_results):
            step_type = step_result.step_type
            validators = sanitize_json_record(getattr(step_result.data, 'validators', {}))
            success = step_result.success and not self._validators_indicate_failure(validators)

            result = {
                'name': step_result.name,
                'success': success,
                'elapsed': step_result.elapsed,
                'step_type': step_type,
                'data': {
                    'extracted_variables': sanitize_json_record(step_result.export_vars),
                    'validators': validators
                },
                'attachment': sanitize_json_record(step_result.attachment)
            }

            if step_type == 'request':
                req_resp = step_result.data.req_resps[-1] if step_result.data.req_resps else None
                body_diagnostic = None
                if request_result_index < len(step_body_diagnostics):
                    body_diagnostic = step_body_diagnostics[request_result_index]
                request_snapshot = None
                if request_result_index < len(step_request_snapshots):
                    request_snapshot = step_request_snapshots[request_result_index]
                request_result_index += 1
                request_data = sanitize_json_record({
                    'method': req_resp.request.method if req_resp else None,
                    'url': req_resp.request.url if req_resp else None,
                    'headers': req_resp.request.headers if req_resp else {},
                    'body': req_resp.request.body if req_resp else None
                })
                status_code = req_resp.response.status_code if req_resp else None
                response_error = (
                    getattr(req_resp.response, 'error', None)
                    if req_resp else None
                )
                response_error_type = (
                    getattr(req_resp.response, 'error_type', None)
                    if req_resp else None
                )
                is_transport_error = bool(
                    getattr(req_resp.response, 'is_transport_error', False)
                    if req_resp else False
                )
                if is_transport_error:
                    success = False
                    result['success'] = False
                recorded_body = request_data['body']
                fallback_used = self._apply_prepared_request_fallback(
                    request_data,
                    status_code,
                    request_snapshot,
                )
                request_data = sanitize_json_record(request_data)
                result['data'].update({
                    'request': request_data,
                    'response': sanitize_json_record({
                        'status_code': status_code,
                        'headers': req_resp.response.headers if req_resp else {},
                        'body': req_resp.response.body if req_resp else None,
                        'content_size': step_result.data.stat.content_size,
                        'response_time_ms': step_result.data.stat.response_time_ms,
                        'error': response_error,
                        'error_type': response_error_type,
                        'is_transport_error': is_transport_error,
                    })
                })
                logger.info(
                    "Testcase step result assembled: trace_id=%s testcase_id=%s "
                    "step_index=%s step_name=%s status_code=%s success=%s "
                    "recorded_request_body_summary=%s display_request_body_summary=%s "
                    "request_display_fallback_used=%s is_transport_error=%s "
                    "response_error_type=%s response_error_summary=%s body_diagnostic=%s",
                    trace_id,
                    testcase_id,
                    index + 1,
                    step_result.name,
                    status_code,
                    success,
                    summarize_for_log(recorded_body),
                    summarize_for_log(result['data']['request']['body']),
                    fallback_used,
                    is_transport_error,
                    response_error_type,
                    summarize_for_log(response_error),
                    body_diagnostic,
                )
                if status_code == 0 and recorded_body is None:
                    if fallback_used:
                        logger.warning(
                            "Testcase recorded request body recovered from prepared request: "
                            "trace_id=%s testcase_id=%s step_index=%s step_name=%s "
                            "status_code=%s reason=request_failed_before_response "
                            "note=httprunner_safe_mode_rebuilds_request_record_without_json_or_data "
                            "display_request_body_summary=%s body_diagnostic=%s",
                            trace_id,
                            testcase_id,
                            index + 1,
                            step_result.name,
                            status_code,
                            summarize_for_log(result['data']['request']['body']),
                            body_diagnostic,
                        )
                    else:
                        logger.warning(
                            "Testcase recorded request body is empty after transport failure: "
                            "trace_id=%s testcase_id=%s step_index=%s step_name=%s "
                            "status_code=%s reason=request_failed_before_response "
                            "note=httprunner_safe_mode_rebuilds_request_record_without_json_or_data "
                            "body_diagnostic=%s",
                            trace_id,
                            testcase_id,
                            index + 1,
                            step_result.name,
                            status_code,
                            body_diagnostic,
                        )
            elif step_type == 'sql':
                sql_result = None
                if hasattr(step_result.data, 'sql_response'):
                    sql_result = step_result.data.sql_response
                result['data'].update(sanitize_json_record({
                    'sql_request': {
                        'sql': getattr(step_result.data, 'sql', None),
                        'method': getattr(step_result.data, 'method', None),
                        'db_config': getattr(step_result.data, 'db_config', {})
                    },
                    'sql_response': sql_result
                }))

            results.append(result)

        return results

    def get_summary(self) -> Dict:
        """Get execution summary."""
        summary = super().get_summary()
        step_results = self.get_step_results()

        success = True
        export_vars = {}
        for step in step_results:
            if not step['success']:
                success = False
                break
            if step['data'].get('extracted_variables'):
                export_vars.update(step['data']['extracted_variables'])

        return {
            'success': success,
            'name': summary.name,
            'time': {
                'start_at': summary.time.start_at,
                'duration': summary.time.duration
            },
            'in_out': {
                'config_vars': summary.in_out.config_vars,
                'export_vars': export_vars
            },
            'log': summary.log,
            'step_results': step_results
        }


class BatchRunner:
    """Batch test case runner."""

    def __init__(self, testcases: List[ApiTestCase]):
        self.testcases = testcases
        self.results = []

    def run(self, environment: Optional[Dict] = None) -> List[Dict]:
        for testcase in self.testcases:
            runner = TestCaseRunner(testcase)
            runner.run_testcase(environment)
            self.results.append({
                'testcase_id': testcase.id,
                'testcase_name': testcase.name,
                'summary': runner.get_summary()
            })
        return self.results

    def get_statistics(self) -> Dict:
        if not self.results:
            return {}
        total = len(self.results)
        success = len([r for r in self.results if r['summary']['success']])
        return {
            'total': total,
            'success': success,
            'fail': total - success,
            'success_rate': f"{(success / total * 100):.2f}%"
        }
