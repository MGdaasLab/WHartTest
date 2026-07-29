from typing import Dict, Optional
import copy
import logging
import json
import types

from httprunner import HttpRunner, Config, Step, RunRequest, RunSqlRequest
from httprunner.client import sanitize_json_record
from httprunner.models import TestCaseSummary
from httprunner.parser import Parser

from api_functions.models import ApiCustomFunction
from .logging_utils import new_trace_id, summarize_for_log
from file_management.services import validate_file_ids, serialize_file_for_runtime
from .payloads import (
    flatten_key_value_pairs,
    normalize_request_body,
    prepare_request_body_for_runner,
)
from .validators import prepare_validator_for_runtime
from .runner_uploads import (
    apply_upload_files_to_step,
    collect_file_ids_from_body,
    merge_file_ids,
)

logger = logging.getLogger(__name__)


def load_custom_functions(project_id):
    """Load custom functions for a project."""
    functions = {}
    loaded_count = 0
    error_count = 0

    try:
        custom_functions = ApiCustomFunction.objects.filter(
            project_id=project_id,
            is_active=True,
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
                    logger.warning(f"Function [{func.name}] did not define any callable functions")
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

        logger.info(
            f"Project [{project_name}] functions loaded: "
            f"{loaded_count} succeeded, {error_count} failed"
        )

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


class InterfaceRunner(HttpRunner):
    """Interface runner based on httprunner."""

    def __init__(self, interface_data: Dict):
        super().__init__()
        self.interface_data = interface_data
        self.db_engine = None
        self.functions = {}
        self.trace_id = self.interface_data.get('trace_id') or new_trace_id('ifc')
        self.interface_data['trace_id'] = self.trace_id
        self.request_body_diagnostic = {}
        self.prepared_request_snapshot = {}

        try:
            self.config = Config(self.interface_data.get('name', 'Interface Request'))
            self.base_url = self.interface_data.get('base_url', '')
            self.verify = self.interface_data.get('verify', None)
            self.variables = self.interface_data.get('variables', {})
            project_id = self.interface_data.get('project_id')
            file_ids = merge_file_ids(
                self.interface_data.get('file_ids'),
                collect_file_ids_from_body(self.interface_data.get('body')),
            )
            self.interface_data['file_ids'] = file_ids
            self.runtime_files = _resolve_runtime_files(project_id, file_ids)
            if self.runtime_files:
                self.variables = self.variables or {}
                self.variables['file_ids'] = [item['id'] for item in self.runtime_files]
                self.variables['files'] = self.runtime_files

            if self.base_url:
                self.config.base_url(self.base_url)
            if self.verify is not None:
                self.config.verify(self.verify)
            if self.variables:
                self.config.variables(**self.variables)

            if project_id:
                try:
                    custom_functions = load_custom_functions(project_id)
                    if custom_functions:
                        self.functions.update(custom_functions)
                        self.parser = Parser(functions_mapping=custom_functions)
                        logger.info(
                            f"Interface [{self.interface_data.get('name')}] "
                            f"loaded custom functions: {list(custom_functions.keys())}"
                        )
                except Exception as e:
                    logger.error(f"Failed to load custom functions: {str(e)}")

            logger.info(
                "Interface config initialized: trace_id=%s base_url=%s verify=%s "
                "variables_summary=%s body_source=%s",
                self.trace_id,
                self.base_url,
                self.verify,
                summarize_for_log(self.variables),
                self.interface_data.get('body_source', 'unknown'),
            )
        except Exception as e:
            logger.error(f"Interface config initialization failed: {str(e)}")
            raise

        interface_type = self.interface_data.get('type', 'http')
        if interface_type == 'sql':
            self._init_sql_step()
        else:
            self._init_http_step()

    def _add_hooks_to_step(self, step_obj, hooks, hook_type='setup'):
        """Add setup or teardown hooks to a step object."""
        method_name = 'setup_hook' if hook_type == 'setup' else 'teardown_hook'
        for hook in hooks:
            if isinstance(hook, dict):
                hook_json = json.dumps(hook, ensure_ascii=False)
                step_obj = getattr(step_obj, method_name)(hook_json)
            else:
                step_obj = getattr(step_obj, method_name)(hook)
        return step_obj

    def _init_http_step(self):
        """Initialize HTTP step."""
        step_obj = RunRequest(self.interface_data.get('name', 'Interface Request'))

        method = self.interface_data.get('method', 'GET').lower()
        url = self.interface_data.get('url', '')

        if not url.startswith(('http://', 'https://')):
            url = f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"
        self.prepared_request_snapshot = {
            'method': method.upper(),
            'url': url,
            'headers': {},
            'body': None,
        }

        # Setup hooks
        if self.interface_data.get('setup_hooks'):
            step_obj = self._add_hooks_to_step(
                step_obj, self.interface_data['setup_hooks'], 'setup'
            )

        # HTTP method
        step_obj = getattr(step_obj, method)(url)

        # Teardown hooks
        if self.interface_data.get('teardown_hooks'):
            step_obj = self._add_hooks_to_step(
                step_obj, self.interface_data['teardown_hooks'], 'teardown'
            )

        # Query params
        if self.interface_data.get('params'):
            params = {}
            for k, v in flatten_key_value_pairs(self.interface_data['params']).items():
                if isinstance(v, str) and v.startswith('$'):
                    var_name = v[1:]
                    params[k] = self.variables.get(var_name, v)
                else:
                    params[k] = v
            step_obj = step_obj.with_params(**params)

        # Headers (global + interface-specific)
        headers_dict = {}
        global_headers = self._get_global_headers()
        if global_headers:
            headers_dict.update(global_headers)

        if self.interface_data.get('headers'):
            headers_dict.update(flatten_key_value_pairs(self.interface_data['headers']))

        if headers_dict:
            step_obj = step_obj.with_headers(**headers_dict)
        self.prepared_request_snapshot['headers'] = copy.deepcopy(headers_dict)

        # Request body
        raw_body = self.interface_data.get('body')
        self.request_body_diagnostic = {
            'body_source': self.interface_data.get('body_source', 'unknown'),
            'body_present': 'body' in self.interface_data,
            'raw_summary': summarize_for_log(raw_body),
            'prepared': False,
            'skipped_reason': None,
        }
        logger.info(
            "Interface request body source: trace_id=%s name=%s project_id=%s "
            "method=%s url=%s body_source=%s body_present=%s body_summary=%s",
            self.trace_id,
            self.interface_data.get('name', 'Interface Request'),
            self.interface_data.get('project_id'),
            method.upper(),
            url,
            self.request_body_diagnostic['body_source'],
            'body' in self.interface_data,
            summarize_for_log(raw_body),
        )
        if self.interface_data.get('body'):
            try:
                normalized_body = normalize_request_body(self.interface_data['body'])
                body = prepare_request_body_for_runner(normalized_body)
            except Exception:
                logger.exception(
                    "Interface request body normalization failed: trace_id=%s name=%s "
                    "project_id=%s body_source=%s body_summary=%s",
                    self.trace_id,
                    self.interface_data.get('name', 'Interface Request'),
                    self.interface_data.get('project_id'),
                    self.request_body_diagnostic['body_source'],
                    summarize_for_log(raw_body),
                )
                raise

            if isinstance(body, str) and body.startswith('$'):
                var_name = body[1:]
                if var_name in self.variables:
                    body = self.variables[var_name]
            if body is not None:
                target = (
                    'data'
                    if normalized_body['type'] in {'form-data', 'x-www-form-urlencoded', 'binary'}
                    else 'json'
                )
                logger.info(
                    "Interface request body prepared: trace_id=%s name=%s project_id=%s "
                    "body_source=%s body_type=%s target=%s prepared_summary=%s",
                    self.trace_id,
                    self.interface_data.get('name', 'Interface Request'),
                    self.interface_data.get('project_id'),
                    self.request_body_diagnostic['body_source'],
                    normalized_body['type'],
                    target,
                    summarize_for_log(body),
                )
                self.request_body_diagnostic.update({
                    'prepared': True,
                    'body_type': normalized_body['type'],
                    'target': target,
                    'prepared_summary': summarize_for_log(body),
                })
                self.prepared_request_snapshot['body'] = copy.deepcopy(body)
                step_obj, upload_applied = apply_upload_files_to_step(
                    step_obj,
                    normalized_body,
                    self.runtime_files,
                )
                self.prepared_request_snapshot['headers'] = copy.deepcopy(
                    step_obj.struct().request.headers,
                )
                if normalized_body['type'] in {'form-data', 'x-www-form-urlencoded', 'binary'}:
                    if not upload_applied:
                        step_obj = step_obj.with_data(body)
                else:
                    step_obj = step_obj.with_json(body)
            else:
                logger.info(
                    "Interface request body normalized to empty payload: trace_id=%s name=%s "
                    "project_id=%s body_source=%s body_type=%s",
                    self.trace_id,
                    self.interface_data.get('name', 'Interface Request'),
                    self.interface_data.get('project_id'),
                    self.request_body_diagnostic['body_source'],
                    normalized_body['type'],
                )
                self.request_body_diagnostic.update({
                    'body_type': normalized_body['type'],
                    'skipped_reason': 'normalized_body_is_none',
                })
        else:
            self.request_body_diagnostic['skipped_reason'] = (
                'missing_or_falsey_body_by_current_runner_condition'
            )
            logger.info(
                "Interface request body skipped by current runner condition: trace_id=%s "
                "name=%s project_id=%s body_source=%s skipped_reason=%s body_summary=%s",
                self.trace_id,
                self.interface_data.get('name', 'Interface Request'),
                self.interface_data.get('project_id'),
                self.request_body_diagnostic['body_source'],
                self.request_body_diagnostic['skipped_reason'],
                summarize_for_log(raw_body),
            )

        # Extract
        if self.interface_data.get('extract'):
            extract_obj = step_obj.extract()
            extract_meta = self.interface_data.get('extract_meta')
            extract_meta = extract_meta if isinstance(extract_meta, dict) else {}
            for var_name, expr in self.interface_data['extract'].items():
                meta = extract_meta.get(var_name, {})
                source = meta.get('source') if isinstance(meta, dict) else 'response'
                extract_obj = extract_obj.with_jmespath(expr, var_name, source=source)
            step_obj = extract_obj

        # Validators
        if self.interface_data.get('validators'):
            step_obj = self._add_validators(step_obj, self.interface_data['validators'])

        step = Step(step_obj)
        self.teststeps.append(step)

    def _init_sql_step(self):
        """Initialize SQL step."""
        step_obj = RunSqlRequest(self.interface_data.get('name', 'SQL Request'))

        sql_method = self.interface_data.get('method', 'fetchone').lower()
        sql = self.interface_data.get('sql', '')

        # Setup hooks
        if self.interface_data.get('setup_hooks'):
            step_obj = self._add_hooks_to_step(
                step_obj, self.interface_data['setup_hooks'], 'setup'
            )

        # SQL method dispatch
        if sql_method == 'fetchone':
            step_obj = step_obj.fetchone(sql)
        elif sql_method == 'fetchmany':
            size = self.interface_data.get('size', 10)
            step_obj = step_obj.fetchmany(sql, size)
        elif sql_method == 'fetchall':
            step_obj = step_obj.fetchall(sql)
        elif sql_method == 'insert':
            step_obj = step_obj.insert(sql)
        elif sql_method == 'update':
            step_obj = step_obj.update(sql)
        elif sql_method == 'delete':
            step_obj = step_obj.delete(sql)
        else:
            logger.warning(f"Unsupported SQL method: {sql_method}, falling back to fetchone")
            step_obj = step_obj.fetchone(sql)

        # Teardown hooks
        if self.interface_data.get('teardown_hooks'):
            step_obj = self._add_hooks_to_step(
                step_obj, self.interface_data['teardown_hooks'], 'teardown'
            )

        # Extract
        if self.interface_data.get('extract'):
            for var_name, expr in self.interface_data['extract'].items():
                step_obj = step_obj.with_jmespath(expr, var_name)

        # Validators
        if self.interface_data.get('validators'):
            step_obj = self._add_validators_sql(step_obj, self.interface_data['validators'])

        step = Step(step_obj)
        self.teststeps.append(step)

    def _add_validators(self, step_obj, validators):
        """Add validators to an HTTP step."""
        validate_obj = step_obj.validate()
        for validator in validators:
            runtime_validator = prepare_validator_for_runtime(validator)
            if not runtime_validator:
                logger.warning(f"Unsupported validator format: {validator}")
                continue

            validate_obj.struct().validators.append(runtime_validator)

        return validate_obj

    def _add_validators_sql(self, step_obj, validators):
        """Add validators to a SQL step."""
        validate_obj = step_obj.validate()
        for validator in validators:
            runtime_validator = prepare_validator_for_runtime(validator)
            if not runtime_validator:
                logger.warning(f"Unsupported validator format: {validator}")
                continue
            validate_obj.struct().validators.append(runtime_validator)
        return validate_obj

    def _apply_comparator(self, validate_obj, comparator, check_item, expected_value):
        """Apply a single comparator to a validation object."""
        comparator_map = {
            'eq': 'assert_equal',
            'ne': 'assert_not_equal',
            'lt': 'assert_less_than',
            'le': 'assert_less_or_equals',
            'lte': 'assert_less_or_equals',
            'gt': 'assert_greater_than',
            'ge': 'assert_greater_or_equals',
            'gte': 'assert_greater_or_equals',
            'str_eq': 'assert_string_equals',
            'contains': 'assert_contains',
            'contained_by': 'assert_contained_by',
            'type_match': 'assert_type_match',
            'regex_match': 'assert_regex_match',
            'startswith': 'assert_startswith',
            'endswith': 'assert_endswith',
            'length_equal': 'assert_length_equal',
            'length_greater_than': 'assert_length_greater_than',
            'length_less_than': 'assert_length_less_than',
            'length_greater_or_equals': 'assert_length_greater_or_equals',
            'length_less_or_equals': 'assert_length_less_or_equals',
        }
        method_name = comparator_map.get(comparator)
        if method_name and hasattr(validate_obj, method_name):
            return getattr(validate_obj, method_name)(check_item, expected_value)
        else:
            logger.warning(f"Unsupported comparator: {comparator}")
            return validate_obj

    def run_interface(self, environment: Optional[Dict] = None) -> "InterfaceRunner":
        """Run the interface request."""
        logger.info(
            "Executing interface: trace_id=%s name=%s type=%s",
            self.trace_id,
            self.interface_data.get('name', 'Interface Request'),
            self.interface_data.get('type', 'http'),
        )

        interface_type = self.interface_data.get('type', 'http')

        # Process environment variables
        try:
            if environment and isinstance(environment, dict) and environment.get('variables'):
                self.variables.update(environment['variables'])
            if self.variables and isinstance(self.variables, dict):
                self.config.variables(**self.variables)
        except Exception as e:
            logger.error(f"Failed to update environment variables: {str(e)}")

        # Process DB config for SQL interfaces
        try:
            if (
                interface_type == 'sql'
                and environment
                and isinstance(environment, dict)
                and environment.get('db_config')
            ):
                db_config = environment['db_config']
                if 'db_config' not in self.interface_data:
                    self.interface_data['db_config'] = {}
                for key in ['user', 'password', 'ip', 'port', 'database']:
                    if key in db_config and db_config[key]:
                        self.interface_data['db_config'][key] = db_config[key]
        except Exception as e:
            logger.error(f"Failed to update DB config: {str(e)}")

        # Execute
        try:
            self.test_start()
        except Exception as e:
            logger.error(
                "Interface execution failed: trace_id=%s error=%s",
                self.trace_id,
                str(e),
            )
            raise

        return self

    def _apply_prepared_request_fallback(self, request_data: Dict, status_code) -> bool:
        """Recover display request data when httprunner safe mode drops it."""
        if status_code != 0:
            return False

        snapshot = self.prepared_request_snapshot or {}
        fallback_used = False

        if not request_data.get('method') and snapshot.get('method'):
            request_data['method'] = snapshot['method']
            fallback_used = True

        if not request_data.get('url') and snapshot.get('url'):
            request_data['url'] = snapshot['url']
            fallback_used = True

        if not request_data.get('headers') and snapshot.get('headers'):
            request_data['headers'] = copy.deepcopy(snapshot['headers'])
            fallback_used = True

        if request_data.get('body') is None and snapshot.get('body') is not None:
            request_data['body'] = copy.deepcopy(snapshot['body'])
            fallback_used = True

        return fallback_used

    def get_summary(self) -> TestCaseSummary:
        """Get execution summary."""
        return super().get_summary()

    def get_response(self) -> Dict:
        """Get interface response result."""
        summary = self.get_summary()
        if not summary.step_results:
            return {"success": False, "error": "No execution results"}

        step_result = summary.step_results[0]
        data = step_result.data  # type: ignore

        req_resp = None
        stat = None
        validators = {}

        if hasattr(data, 'req_resp'):
            req_resp = data.req_resp  # type: ignore
        elif hasattr(data, 'req_resps') and isinstance(data.req_resps, list):  # type: ignore
            req_resps = data.req_resps  # type: ignore
            if req_resps:
                req_resp = req_resps[-1]

        if hasattr(data, 'stat'):
            stat = data.stat  # type: ignore

        if hasattr(data, 'validators'):
            validators = data.validators  # type: ignore

        # 提取 validate_extractor 列表（原项目 views.py 的做法）
        validation_results = []
        if isinstance(validators, dict):
            validation_results = validators.get("validate_extractor", [])
        elif isinstance(validators, list):
            validation_results = validators

        result = {
            "success": step_result.success,
            "name": step_result.name,
            "validation_results": sanitize_json_record(validation_results),
            "extracted_variables": sanitize_json_record(step_result.export_vars),  # type: ignore
        }

        if req_resp:
            status_code = (
                req_resp.response.status_code
                if hasattr(req_resp, 'response') else None
            )  # type: ignore
            elapsed = stat.response_time_ms if stat else 0  # type: ignore
            response_error = (
                getattr(req_resp.response, 'error', None)
                if hasattr(req_resp, 'response') else None
            )
            response_error_type = (
                getattr(req_resp.response, 'error_type', None)
                if hasattr(req_resp, 'response') else None
            )
            is_transport_error = bool(
                getattr(req_resp.response, 'is_transport_error', False)
                if hasattr(req_resp, 'response') else False
            )
            if is_transport_error:
                result['success'] = False
            request_data = sanitize_json_record({
                "method": (
                    req_resp.request.method
                    if hasattr(req_resp, 'request') else None
                ),  # type: ignore
                "url": (
                    req_resp.request.url
                    if hasattr(req_resp, 'request') else None
                ),  # type: ignore
                "headers": (
                    req_resp.request.headers
                    if hasattr(req_resp, 'request') else {}
                ),  # type: ignore
                "body": (
                    req_resp.request.body
                    if hasattr(req_resp, 'request') else None
                ),  # type: ignore
            })
            recorded_request_body = request_data['body']
            fallback_used = self._apply_prepared_request_fallback(request_data, status_code)
            request_data = sanitize_json_record(request_data)
            result.update({
                "status_code": status_code,
                "elapsed": elapsed,
                "request": request_data,
                "response": sanitize_json_record({
                    "status_code": status_code,
                    "headers": (
                        req_resp.response.headers
                        if hasattr(req_resp, 'response') else {}
                    ),  # type: ignore
                    "content": (
                        req_resp.response.body
                        if hasattr(req_resp, 'response') else None
                    ),  # type: ignore
                    "content_size": stat.content_size if stat else 0,  # type: ignore
                    "error": response_error,
                    "error_type": response_error_type,
                    "is_transport_error": is_transport_error,
                }),
            })
            logger.info(
                "Interface response assembled: trace_id=%s status_code=%s success=%s "
                "recorded_request_body_summary=%s display_request_body_summary=%s "
                "request_display_fallback_used=%s is_transport_error=%s "
                "response_error_type=%s response_error_summary=%s body_diagnostic=%s",
                self.trace_id,
                status_code,
                result['success'],
                summarize_for_log(recorded_request_body),
                summarize_for_log(result['request']['body']),
                fallback_used,
                is_transport_error,
                response_error_type,
                summarize_for_log(response_error),
                self.request_body_diagnostic,
            )
            if status_code == 0 and recorded_request_body is None:
                if fallback_used:
                    logger.warning(
                        "Interface recorded request body recovered from prepared request: "
                        "trace_id=%s status_code=%s reason=request_failed_before_response "
                        "note=httprunner_safe_mode_rebuilds_request_record_without_json_or_data "
                        "display_request_body_summary=%s body_diagnostic=%s",
                        self.trace_id,
                        status_code,
                        summarize_for_log(result['request']['body']),
                        self.request_body_diagnostic,
                    )
                else:
                    logger.warning(
                        "Interface recorded request body is empty after transport failure: "
                        "trace_id=%s status_code=%s reason=request_failed_before_response "
                        "note=httprunner_safe_mode_rebuilds_request_record_without_json_or_data "
                        "body_diagnostic=%s",
                        self.trace_id,
                        status_code,
                        self.request_body_diagnostic,
                    )
        else:
            request_data = sanitize_json_record({
                "method": self.prepared_request_snapshot.get('method'),
                "url": self.prepared_request_snapshot.get('url'),
                "headers": copy.deepcopy(self.prepared_request_snapshot.get('headers', {})),
                "body": copy.deepcopy(self.prepared_request_snapshot.get('body')),
            })
            result.update({
                "status_code": None,
                "elapsed": 0,
                "request": request_data,
                "response": {
                    "status_code": None,
                    "headers": {},
                    "content": None,
                    "content_size": 0,
                    "error": "No request/response record was produced.",
                    "error_type": "MissingReqRespRecord",
                    "is_transport_error": True,
                },
            })
            logger.warning(
                "Interface response missing request/response record: trace_id=%s "
                "body_diagnostic=%s",
                self.trace_id,
                self.request_body_diagnostic,
            )

        return result

    def _get_global_headers(self):
        """Get global request headers for the project."""
        global_headers = {}
        try:
            project_id = self.interface_data.get('project_id')
            if project_id:
                from api_environments.models import ApiGlobalRequestHeader as GlobalRequestHeader

                headers = GlobalRequestHeader.objects.filter(
                    project_id=project_id,
                    is_enabled=True,
                )
                for header in headers:
                    header_value = header.value
                    if isinstance(header_value, str):
                        if header_value.startswith('${') and header_value.endswith('}'):
                            var_name = header_value[2:-1]
                            if hasattr(self, 'variables') and var_name in self.variables:
                                header_value = self.variables[var_name]
                        elif header_value.startswith('$') and len(header_value) > 1:
                            var_name = header_value[1:]
                            if hasattr(self, 'variables') and var_name in self.variables:
                                header_value = self.variables[var_name]
                    global_headers[header.name] = header_value

            return global_headers
        except Exception as e:
            logger.error(f"Failed to get global headers: {str(e)}")
            return {}
