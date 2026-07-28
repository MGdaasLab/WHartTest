# -*- coding: utf-8 -*-
import argparse
import io
import json
import sys
from pathlib import Path
from urllib import error, parse, request

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os

_DEFAULT_BASE_URL = 'http://127.0.0.1:8000'
_DEFAULT_API_KEY = 'wharttest-default-mcp-key-2025'


def _base_url():
    return (os.environ.get('WHARTTEST_BACKEND_URL') or _DEFAULT_BASE_URL).rstrip('/')


def _api_key():
    return (os.environ.get('WHARTTEST_API_KEY') or _DEFAULT_API_KEY).strip()


def _headers():
    return {
        'accept': 'application/json',
        'Content-Type': 'application/json',
        'X-API-Key': _api_key(),
    }


# 兼容旧引用；真正请求请使用 _headers()/_base_url()
BASE_URL = _base_url()
API_KEY = _api_key()
HEADERS = _headers()
TIMEOUT = 60

CRUD_RESOURCES = [
    ('module', 'modules', 'api-modules', 'module_id'),
    ('database_config', 'database_configs', 'api-database-configs', 'database_config_id'),
    ('environment', 'environments', 'api-environments', 'environment_id'),
    ('environment_variable', 'environment_variables', 'api-environment-variables', 'variable_id'),
    ('global_header', 'global_headers', 'api-global-headers', 'header_id'),
    ('function', 'functions', 'api-functions', 'function_id'),
    ('interface', 'interfaces', 'api-interfaces', 'interface_id'),
    ('testcase_tag', 'testcase_tags', 'api-testcase-tags', 'tag_id'),
    ('testcase_group', 'testcase_groups', 'api-testcase-groups', 'group_id'),
    ('testcase', 'testcases', 'api-testcases', 'testcase_id'),
    ('sync_config', 'sync_configs', 'api-sync-configs', 'sync_config_id'),
    ('global_sync_config', 'global_sync_configs', 'api-global-sync-configs', 'global_sync_config_id'),
    ('task_suite', 'task_suites', 'api-task-suites', 'task_suite_id'),
]
READ_ONLY_RESOURCES = [
    ('interface_result', 'interface_results', 'api-interface-results', 'interface_result_id'),
    ('test_report', 'test_reports', 'api-test-reports', 'test_report_id'),
    ('sync_history', 'sync_histories', 'api-sync-histories', 'sync_history_id'),
    ('task_execution', 'task_executions', 'api-task-executions', 'task_execution_id'),
]
ID_ARGUMENTS = [
    ('module_id', '模块 ID'),
    ('database_config_id', '数据库配置 ID'),
    ('environment_id', '环境 ID'),
    ('variable_id', '环境变量 ID'),
    ('header_id', '全局请求头 ID'),
    ('function_id', '自定义函数 ID'),
    ('interface_id', '接口 ID'),
    ('interface_result_id', '接口调试结果 ID'),
    ('tag_id', '用例标签 ID'),
    ('group_id', '用例分组 ID'),
    ('testcase_id', '测试用例 ID'),
    ('test_report_id', '测试报告 ID'),
    ('step_id', '测试步骤 ID'),
    ('sync_config_id', '同步配置 ID'),
    ('sync_history_id', '同步历史 ID'),
    ('global_sync_config_id', '全局同步配置 ID'),
    ('task_suite_id', '任务套件 ID'),
    ('task_execution_id', '任务执行 ID'),
]


def _error(message, data=None, code=None):
    result = {'status': 'error', 'message': message}
    if code is not None:
        result['code'] = code
    if data not in (None, '', {}):
        result['data'] = data
    return result


def _read_json_source(raw_value):
    if raw_value is None or raw_value == '':
        return None
    if raw_value.startswith('@'):
        return Path(raw_value[1:]).read_text(encoding='utf-8')
    return raw_value


def _load_json(raw_value, default):
    content = _read_json_source(raw_value)
    if content is None:
        return default
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f'JSON 解析失败: {exc}') from exc


def _extract_message(body, fallback):
    if isinstance(body, dict):
        for key in ('message', 'detail', 'error', 'msg'):
            value = body.get(key)
            if value:
                return value
    if isinstance(body, str) and body.strip():
        return body.strip()
    return fallback


def _build_url(url, params=None):
    if not params:
        return url
    parsed = parse.urlsplit(url)
    existing_query = parse.parse_qsl(parsed.query, keep_blank_values=True)
    extra_query = []
    for key, value in params.items():
        if isinstance(value, (list, tuple)):
            for item in value:
                extra_query.append((key, item))
        else:
            extra_query.append((key, value))
    merged_query = parse.urlencode(existing_query + extra_query, doseq=True)
    return parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, merged_query, parsed.fragment))


def _decode_response_body(raw_body):
    text = raw_body.decode('utf-8', errors='replace')
    try:
        return json.loads(text)
    except ValueError:
        return text


def _configure_request_settings(base_url, api_key):
    """用命令行参数覆盖运行时配置（写入 env，供 _base_url/_api_key/_headers 读取）。"""
    global API_KEY, BASE_URL, HEADERS
    resolved_url = (base_url or _DEFAULT_BASE_URL).rstrip('/')
    resolved_key = (api_key or _DEFAULT_API_KEY).strip()
    os.environ['WHARTTEST_BACKEND_URL'] = resolved_url
    os.environ['WHARTTEST_API_KEY'] = resolved_key
    BASE_URL = resolved_url
    API_KEY = resolved_key
    HEADERS = _headers()


def _request(method, url, payload=None, params=None):
    request_url = _build_url(url, params)
    request_data = None
    if payload is not None and method in {'POST', 'PUT', 'PATCH'}:
        request_data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = request.Request(request_url, data=request_data, headers=_headers(), method=method)

    try:
        with request.urlopen(req, timeout=TIMEOUT) as response:
            status_code = response.status
            body = _decode_response_body(response.read())
    except error.HTTPError as exc:
        status_code = exc.code
        body = _decode_response_body(exc.read())
    except error.URLError as exc:
        reason = getattr(exc, 'reason', exc)
        return _error(str(reason))
    except Exception as exc:
        return _error(str(exc))

    if status_code == 204:
        return {'status': 'success', 'message': '操作成功'}

    if 200 <= status_code < 300:
        if isinstance(body, dict) and 'status' in body:
            return body
        return {'status': 'success', 'data': body}

    if isinstance(body, dict) and body.get('status') == 'error':
        return body
    return _error(
        _extract_message(body, f'HTTP {status_code}'),
        data=body if isinstance(body, (dict, list)) else None,
        code=status_code,
    )


def _project_url(project_id, path):
    return f'{_base_url()}/api/projects/{project_id}/{path.lstrip("/")}'


def _require(value, label):
    if value in (None, ''):
        raise ValueError(f'{label} 不能为空')
    return value


def _list_resource(args, base_path):
    return _request('GET', _project_url(args.project_id, f'{base_path}/'), params=args.params_obj)


def _get_resource(args, base_path, id_arg):
    item_id = _require(getattr(args, id_arg), id_arg)
    return _request('GET', _project_url(args.project_id, f'{base_path}/{item_id}/'))


def _create_resource(args, base_path):
    return _request('POST', _project_url(args.project_id, f'{base_path}/'), payload=args.payload_obj)


def _update_resource(args, base_path, id_arg):
    item_id = _require(getattr(args, id_arg), id_arg)
    return _request('PATCH', _project_url(args.project_id, f'{base_path}/{item_id}/'), payload=args.payload_obj)


def _delete_resource(args, base_path, id_arg):
    item_id = _require(getattr(args, id_arg), id_arg)
    return _request('DELETE', _project_url(args.project_id, f'{base_path}/{item_id}/'))


def _get_action(args, path):
    return _request('GET', _project_url(args.project_id, path), params=args.params_obj)


def _post_action(args, path):
    return _request('POST', _project_url(args.project_id, path), payload=args.payload_obj, params=args.params_obj)


def _put_action(args, path):
    return _request('PUT', _project_url(args.project_id, path), payload=args.payload_obj, params=args.params_obj)


def _delete_action(args, path):
    return _request('DELETE', _project_url(args.project_id, path), params=args.params_obj)


def _build_actions():
    actions = {}
    for singular, plural, base_path, id_arg in CRUD_RESOURCES:
        actions[f'list_{plural}'] = lambda args, p=base_path: _list_resource(args, p)
        actions[f'get_{singular}'] = lambda args, p=base_path, i=id_arg: _get_resource(args, p, i)
        actions[f'create_{singular}'] = lambda args, p=base_path: _create_resource(args, p)
        actions[f'update_{singular}'] = lambda args, p=base_path, i=id_arg: _update_resource(args, p, i)
        actions[f'delete_{singular}'] = lambda args, p=base_path, i=id_arg: _delete_resource(args, p, i)

    for singular, plural, base_path, id_arg in READ_ONLY_RESOURCES:
        actions[f'list_{plural}'] = lambda args, p=base_path: _list_resource(args, p)
        actions[f'get_{singular}'] = lambda args, p=base_path, i=id_arg: _get_resource(args, p, i)

    actions.update(
        {
            'get_module_tree': lambda args: _get_action(args, 'api-modules/tree/'),
            'search_modules': lambda args: _get_action(args, 'api-modules/search/'),
            'test_saved_database_connection': lambda args: _post_action(
                args, f'api-database-configs/{_require(args.database_config_id, "database_config_id")}/test-connection/'
            ),
            'test_database_connection': lambda args: _post_action(args, 'api-database-configs/test-connection/'),
            'clone_environment': lambda args: _post_action(
                args, f'api-environments/{_require(args.environment_id, "environment_id")}/clone/'
            ),
            'batch_create_environment_variables': lambda args: _post_action(
                args, 'api-environment-variables/batch_create/'
            ),
            'batch_update_environment_variables': lambda args: _post_action(
                args, 'api-environment-variables/batch_update/'
            ),
            'generate_debugtalk': lambda args: _get_action(args, 'api-functions/generate_debugtalk/'),
            'execute_function': lambda args: _post_action(args, 'api-functions/execute/'),
            'run_interface': lambda args: _post_action(
                args, f'api-interfaces/{_require(args.interface_id, "interface_id")}/run/'
            ),
            'quick_debug_interface': lambda args: _post_action(args, 'api-interfaces/quick_debug/'),
            'get_tag_statistics': lambda args: _get_action(args, 'api-testcase-tags/statistics/'),
            'get_testcase_group_tree': lambda args: _get_action(args, 'api-testcase-groups/tree/'),
            'get_group_testcases': lambda args: _get_action(
                args, f'api-testcase-groups/{_require(args.group_id, "group_id")}/testcases/'
            ),
            'get_available_interfaces': lambda args: _get_action(args, 'api-testcases/available_interfaces/'),
            'get_referenced_interfaces': lambda args: _get_action(
                args, f'api-testcases/{_require(args.testcase_id, "testcase_id")}/referenced_interfaces/'
            ),
            'copy_testcase': lambda args: _post_action(
                args, f'api-testcases/{_require(args.testcase_id, "testcase_id")}/copy/'
            ),
            'run_testcase': lambda args: _post_action(
                args, f'api-testcases/{_require(args.testcase_id, "testcase_id")}/run/'
            ),
            'batch_run_testcases': lambda args: _post_action(args, 'api-testcases/batch_run/'),
            'delete_testcase_step': lambda args: _delete_action(
                args,
                f'api-testcases/{_require(args.testcase_id, "testcase_id")}/delete_step/'
                f'?step_id={_require(args.step_id, "step_id")}',
            ),
            'update_testcase_step': lambda args: _put_action(
                args, f'api-testcases/{_require(args.testcase_id, "testcase_id")}/update_step/'
            ),
            'reorder_testcase_steps': lambda args: _post_action(
                args, f'api-testcases/{_require(args.testcase_id, "testcase_id")}/reorder_steps/'
            ),
            'get_history_reports': lambda args: _get_action(
                args, f'api-testcases/{_require(args.testcase_id, "testcase_id")}/history_reports/'
            ),
            'sync_now': lambda args: _post_action(
                args, f'api-sync-configs/{_require(args.sync_config_id, "sync_config_id")}/sync_now/'
            ),
            'batch_sync': lambda args: _post_action(args, 'api-sync-configs/batch_sync/'),
            'rollback_sync_history': lambda args: _post_action(
                args, f'api-sync-histories/{_require(args.sync_history_id, "sync_history_id")}/rollback/'
            ),
            'set_active_global_sync_config': lambda args: _post_action(
                args,
                f'api-global-sync-configs/{_require(args.global_sync_config_id, "global_sync_config_id")}/set_active/',
            ),
            'get_current_global_sync_config': lambda args: _get_action(args, 'api-global-sync-configs/current_config/'),
            'add_suite_testcases': lambda args: _post_action(
                args, f'api-task-suites/{_require(args.task_suite_id, "task_suite_id")}/add-testcases/'
            ),
            'remove_suite_testcase': lambda args: _delete_action(
                args,
                f'api-task-suites/{_require(args.task_suite_id, "task_suite_id")}/remove-testcase/'
                f'{_require(args.testcase_id, "testcase_id")}/',
            ),
            'execute_task_suite': lambda args: _post_action(args, 'api-task-executions/'),
            'get_task_case_results': lambda args: _get_action(
                args, f'api-task-executions/{_require(args.task_execution_id, "task_execution_id")}/case-results/'
            ),
            'cancel_task_execution': lambda args: _post_action(
                args, f'api-task-executions/{_require(args.task_execution_id, "task_execution_id")}/cancel/'
            ),
        }
    )
    return actions


ACTIONS = _build_actions()


def main():
    parser = argparse.ArgumentParser(description='WHartTest 接口自动化 Skill 工具')
    parser.add_argument('--action', required=True, choices=sorted(ACTIONS), help='要执行的动作')
    parser.add_argument('--project_id', type=int, required=True, help='项目 ID')
    parser.add_argument('--base_url', default=BASE_URL, help='后端服务地址')
    parser.add_argument('--api_key', default=API_KEY, help='接口认证 API Key')
    parser.add_argument('--payload', help='请求体 JSON，支持 @文件路径')
    parser.add_argument('--params', help='查询参数 JSON，支持 @文件路径')

    for arg_name, help_text in ID_ARGUMENTS:
        parser.add_argument(f'--{arg_name}', type=int, help=help_text)

    args = parser.parse_args()

    try:
        _configure_request_settings(args.base_url, args.api_key)
        args.payload_obj = _load_json(args.payload, {})
        args.params_obj = _load_json(args.params, {})
        result = ACTIONS[args.action](args)
    except ValueError as exc:
        result = _error(str(exc))
    except FileNotFoundError as exc:
        result = _error(f'文件不存在: {exc.filename}')
    except Exception as exc:
        result = _error(str(exc))

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if isinstance(result, dict) and result.get('status') == 'error':
        sys.exit(1)


if __name__ == '__main__':
    main()
