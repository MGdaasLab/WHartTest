import json
import re
import time
from typing import Any, Dict, List, Text, Union

import jmespath
import requests
from jmespath.exceptions import JMESPathError
from loguru import logger

from httprunner import utils
from httprunner.exceptions import ValidationFailure
from httprunner.ext.uploader import prepare_upload_step
from httprunner.models import (
    Hooks,
    IStep,
    MethodEnum,
    StepResult,
    TRequest,
    TStep,
    VariablesMapping,
)
from httprunner.parser import build_url, parse_variables_mapping
from httprunner.response import ResponseObject
from httprunner.runner import ALLURE, HttpRunner


def call_hooks(
    runner: HttpRunner, hooks: Hooks, step_variables: VariablesMapping, hook_msg: Text
):
    """call hook actions.

    Args:
        hooks (list): each hook in hooks list maybe in two format.

            format1 (str): only call hook functions.
                ${func()}
            format2 (dict): assignment, the value returned by hook function will be assigned to variable.
                {"var": "${func()}"}
            format3 (dict): SQL operation with type="sql".
                {"type": "sql", "db_key": "db_name", "sql": "SELECT * FROM table", "var_name": "result"}

        step_variables: current step variables to call hook, include two special variables

            request: parsed request dict
            response: ResponseObject for current response

        hook_msg: setup/teardown request/testcase

    """
    logger.info(f"call hook actions: {hook_msg}")

    if not isinstance(hooks, List):
        logger.error(f"Invalid hooks format: {hooks}")
        return

    for hook in hooks:
        if isinstance(hook, Text):
            # 检查是否是函数ID（纯数字字符串）
            if hook.isdigit():
                # 尝试根据ID加载自定义函数
                try:
                    # 动态导入CustomFunction模型
                    from api_functions.models import ApiCustomFunction as CustomFunction
                    function_id = int(hook)
                    custom_function = CustomFunction.objects.filter(id=function_id, is_active=True).first()
                    if custom_function:
                        logger.info(f"根据ID执行钩子函数: {function_id} -> {custom_function.name}")
                        # 加载函数代码
                        import types
                        module = types.ModuleType(custom_function.name)
                        code = compile(custom_function.code, custom_function.name, 'exec')
                        exec(code, module.__dict__)

                        # 获取模块中定义的所有函数
                        module_functions = {
                            name: obj for name, obj in module.__dict__.items()
                            if isinstance(obj, types.FunctionType)
                        }

                        if module_functions:
                            # 将函数添加到runner的functions_mapping中
                            for func_name, func_obj in module_functions.items():
                                runner.parser.functions_mapping[func_name] = func_obj
                                logger.info(f"添加函数到运行时: {func_name}")

                            # 执行函数（默认执行第一个函数）
                            first_func_name = list(module_functions.keys())[0]
                            first_func = module_functions[first_func_name]

                            # 构造函数调用表达式
                            func_call_expr = f"${{{first_func_name}()}}"  # 默认无参数调用
                            logger.debug(f"call hook function by ID: {hook} -> {func_call_expr}")
                            runner.parser.parse_data(func_call_expr, step_variables)
                        else:
                            logger.warning(f"函数ID {hook} 对应的代码中没有定义可调用的函数")
                    else:
                        logger.warning(f"找不到ID为{function_id}的钩子函数或函数未启用")
                except Exception as e:
                    logger.error(f"根据ID执行钩子函数失败: {hook}, 错误: {str(e)}")
            else:
                # format 1: ["${func()}"]
                logger.debug(f"call hook function: {hook}")
                runner.parser.parse_data(hook, step_variables)
        elif isinstance(hook, Dict):
            # 处理SQL类型的钩子
            if "type" in hook and hook["type"] == "sql":
                execute_sql_hook(runner, hook, step_variables)
            elif len(hook) == 1:
                # format 2: {"var": "${func()}"}
                var_name, hook_content = list(hook.items())[0]

                # 检查hook_content是否为字典且包含type=sql
                if isinstance(hook_content, Dict) and hook_content.get("type") == "sql":
                    # 这是SQL类型钩子的另一种格式: {"var_name": {"type": "sql", ...}}
                    sql_hook = hook_content.copy()
                    sql_hook["var_name"] = var_name
                    execute_sql_hook(runner, sql_hook, step_variables)
                else:
                    # 常规的钩子处理
                    hook_content_eval = runner.parser.parse_data(hook_content, step_variables)
                    logger.debug(f"call hook function: {hook_content}, got value: {hook_content_eval}")
                    logger.debug(f"assign variable: {var_name} = {hook_content_eval}")
                    step_variables[var_name] = hook_content_eval
            else:
                logger.error(f"Invalid hook format: {hook}")
        else:
            logger.error(f"Invalid hook format: {hook}")


def execute_sql_hook(runner: HttpRunner, sql_hook: Dict, step_variables: VariablesMapping):
    """执行SQL类型的钩子

    Args:
        runner: HttpRunner实例
        sql_hook: SQL钩子配置
        step_variables: 步骤变量
    """
    import time
    import json
    import traceback
    import sys
    from loguru import logger

    # 生成唯一的钩子ID，用于日志跟踪
    sql_hook_id = id(sql_hook)

    # 构建日志前缀
    hook_prefix = f"[SQL钩子:{sql_hook_id}]"

    # 记录开始执行SQL钩子
    logger.info(f"{hook_prefix} ======== 开始执行SQL钩子 ========")

    # 记录详细的钩子配置
    try:
        hook_config = json.dumps(sql_hook, indent=2, ensure_ascii=False)  # 确保不转义中文字符
        logger.debug(f"{hook_prefix} 配置:\n{hook_config}")
        print(f"{hook_prefix} 配置:\n{hook_config}")  # 直接打印配置到控制台
    except Exception as e:
        logger.warning(f"{hook_prefix} 记录配置失败: {str(e)}")

    # 提取SQL钩子参数
    sql = sql_hook.get("sql")
    db_id = sql_hook.get("db_id")
    var_name = sql_hook.get("var_name")

    # 检查SQL语句
    if not sql:
        error_msg = f"{hook_prefix} 缺少'sql'字段"
        logger.error(error_msg)
        print(error_msg)  # 直接打印错误到控制台
        return

    # 记录钩子关键参数
    params_msg = f"{hook_prefix} 参数: db_id={db_id}, var_name={var_name}, sql={sql}"
    logger.info(params_msg)
    print(params_msg)  # 直接打印参数到控制台

    start_time = time.time()
    db_uri = None
    try:
        # 使用工具函数获取数据库连接
        try:
            from utils.db_utils import get_database_connection

            # 使用db_id获取数据库连接，如果db_id为空则使用当前环境数据库
            db_uri = get_database_connection(db_id)
            if db_uri:
                success_msg = f"{hook_prefix} 获取数据库连接成功"
                logger.info(success_msg)
                print(success_msg)
            else:
                error_msg = f"{hook_prefix} 无法获取数据库连接，请检查db_id或当前环境配置"
                logger.error(error_msg)
                print(error_msg)
                return
        except ImportError as ie:
            import_error_msg = f"{hook_prefix} 无法导入数据库工具函数: {str(ie)}"
            logger.warning(import_error_msg)
            print(import_error_msg)
            return

        # 如果有数据库连接字符串，执行SQL
        if db_uri:
            try:
                # 预处理SQL语句，处理数据库前缀问题
                original_sql = sql
                # 只有对SQLite数据库才需要移除数据库前缀
                if db_uri and 'sqlite' in db_uri.lower():
                    # 对于SQLite，可能需要移除数据库名前缀
                    if '.' in sql:
                        # 这里简化处理，只针对明显的 db.table 格式
                        parts = sql.split(' ')
                        for i, part in enumerate(parts):
                            if '.' in part and not part.startswith('"') and not part.startswith("'"):
                                table_parts = part.split('.')
                                if len(table_parts) == 2:
                                    parts[i] = table_parts[1]

                        adjusted_sql = ' '.join(parts)
                        if adjusted_sql != sql:
                            sql = adjusted_sql
                            logger.info(f"{hook_prefix} 为SQLite调整SQL: {original_sql} -> {sql}")
                            print(f"{hook_prefix} 为SQLite调整SQL: {original_sql} -> {sql}")

                # 尝试使用工具函数执行SQL
                try:
                    from utils.db_utils import execute_sql

                    # 记录SQL执行开始
                    exec_start_msg = f"{hook_prefix} 开始执行SQL: {sql}"
                    logger.info(exec_start_msg)
                    print(exec_start_msg)

                    # 确定查询类型
                    fetch_type = "all"  # 默认获取全部
                    if sql.upper().startswith("SELECT"):
                        if "LIMIT 1" in sql.upper() or sql.strip().endswith("LIMIT 1"):
                            fetch_type = "one"
                        else:
                            fetch_type = "all"
                    else:
                        fetch_type = "none"  # 非查询SQL

                    # 记录查询类型
                    type_msg = f"{hook_prefix} 查询类型: {fetch_type}"
                    logger.debug(type_msg)
                    print(type_msg)

                    # 执行SQL
                    query_start = time.time()
                    sql_result = execute_sql(sql, db_uri, fetch_type)
                    query_elapsed = time.time() - query_start

                    # 记录执行结果
                    if isinstance(sql_result, dict) and "error" in sql_result:
                        error_msg = f"{hook_prefix} SQL执行失败: {sql_result['error']}"
                        logger.error(error_msg)
                        print(error_msg)
                    else:
                        result_type = type(sql_result).__name__
                        result_summary = str(sql_result)
                        if len(result_summary) > 500:
                            result_summary = result_summary[:500] + "..."

                        success_msg = f"{hook_prefix} SQL执行成功，耗时: {query_elapsed:.3f}秒，结果类型: {result_type}"
                        logger.info(success_msg)
                        print(success_msg)

                        result_msg = f"{hook_prefix} 结果: {result_summary}"
                        logger.debug(result_msg)
                        if fetch_type == "one" or (isinstance(sql_result, list) and len(sql_result) <= 3):
                            print(result_msg)  # 只打印简短结果

                    # 如果指定了变量名，则保存结果
                    if var_name and sql_result is not None:
                        # 处理SQL结果，根据结果类型提取值
                        if isinstance(sql_result, dict) and len(sql_result) == 1:
                            # 单一结果，直接提取字典中的唯一值
                            key = list(sql_result.keys())[0]
                            step_variables[var_name] = sql_result[key]
                            var_msg = f"{hook_prefix} SQL结果赋值给变量: {var_name} = {sql_result[key]}"
                        elif isinstance(sql_result, list) and sql_result:
                            if len(sql_result) == 1 and isinstance(sql_result[0], dict) and len(sql_result[0]) == 1:
                                # 单行单列的结果，提取值
                                key = list(sql_result[0].keys())[0]
                                step_variables[var_name] = sql_result[0][key]
                                var_msg = f"{hook_prefix} SQL结果赋值给变量: {var_name} = {sql_result[0][key]}"
                            elif all(isinstance(item, dict) and len(item) == 1 for item in sql_result):
                                # 多行单列的结果，提取所有值为列表
                                key = list(sql_result[0].keys())[0]  # 所有行都是相同的列名
                                values = [item[key] for item in sql_result]
                                step_variables[var_name] = values
                                var_msg = f"{hook_prefix} SQL结果(多行)赋值给变量: {var_name} = {values}"
                            else:
                                # 复杂结果，保持原样
                                step_variables[var_name] = sql_result
                                var_msg = f"{hook_prefix} SQL完整结果赋值给变量: {var_name}"

                        logger.info(var_msg)
                        print(var_msg)

                    hook_elapsed = time.time() - start_time
                    complete_msg = f"{hook_prefix} 执行完成，总耗时: {hook_elapsed:.3f}秒"
                    logger.info(complete_msg)
                    print(complete_msg)

                    # 分隔符
                    logger.info(f"{hook_prefix} ======== SQL钩子执行结束 ========")
                    print(f"{hook_prefix} ======== SQL钩子执行结束 ========")
                    return
                except ImportError as ie:
                    import_error_msg = f"{hook_prefix} 无法导入execute_sql函数: {str(ie)}"
                    logger.error(import_error_msg)
                    print(import_error_msg)
                    return
                except Exception as e:
                    exec_error_msg = f"{hook_prefix} 调用execute_sql函数失败: {str(e)}"
                    logger.error(exec_error_msg)
                    print(exec_error_msg)
                    tb_msg = f"{hook_prefix} 异常堆栈:\n{traceback.format_exc()}"
                    logger.error(tb_msg)
                    return

            except Exception as e:
                error_msg = f"{hook_prefix} 执行SQL失败: {str(e)}"
                logger.error(error_msg)
                print(error_msg)
                tb_msg = f"{hook_prefix} 异常堆栈:\n{traceback.format_exc()}"
                logger.error(tb_msg)
                return
    except Exception as e:
        error_msg = f"{hook_prefix} SQL钩子执行出错: {str(e)}"
        logger.error(error_msg)
        print(error_msg)
        tb_msg = f"{hook_prefix} 异常堆栈:\n{traceback.format_exc()}"
        logger.error(tb_msg)
        return


def pretty_format(v) -> str:
    if isinstance(v, dict):
        return json.dumps(v, indent=4, ensure_ascii=False)

    if isinstance(v, requests.structures.CaseInsensitiveDict):
        return json.dumps(dict(v.items()), indent=4, ensure_ascii=False)

    return repr(utils.omit_long_data(v))


def normalize_extract_source(meta: Any) -> Text:
    if isinstance(meta, dict):
        source = meta.get("source") or meta.get("data_source") or meta.get("dataSource")
    else:
        source = meta
    return "request" if str(source or "").lower() == "request" else "response"


def search_request_jmespath(
    expr: Text,
    request_data: Dict[Text, Any],
    runner: HttpRunner,
    variables_mapping: VariablesMapping = None,
) -> Any:
    field = expr
    if isinstance(field, str) and "$" in field:
        field = runner.parser.parse_data(field, variables_mapping)
    if not isinstance(field, str):
        return field

    try:
        return jmespath.search(field, request_data)
    except JMESPathError as ex:
        logger.error(
            f"failed to search request with jmespath\n"
            f"expression: {field}\n"
            f"data: {request_data}\n"
            f"exception: {ex}"
        )
        raise


def extract_variables_by_source(
    resp_obj: ResponseObject,
    extractors: Dict[Text, Text],
    extract_meta: Dict[Text, Any],
    request_data: Dict[Text, Any],
    runner: HttpRunner,
    variables_mapping: VariablesMapping = None,
) -> Dict[Text, Any]:
    if not extractors:
        return {}

    response_extractors: Dict[Text, Text] = {}
    extract_mapping: Dict[Text, Any] = {}
    for var_name, expr in extractors.items():
        source = normalize_extract_source((extract_meta or {}).get(var_name))
        if source == "request":
            extract_mapping[var_name] = search_request_jmespath(
                expr,
                request_data,
                runner,
                variables_mapping,
            )
        else:
            response_extractors[var_name] = expr

    extract_mapping.update(resp_obj.extract(response_extractors, variables_mapping))
    logger.info(f"extract mapping by source: {extract_mapping}")
    return extract_mapping


placeholder_function_regex_compile = re.compile(r"\$\{([a-zA-Z_]\w*)\(")
placeholder_variable_regex_compile = re.compile(r"\$\{([a-zA-Z_]\w*)\}|\$([a-zA-Z_]\w*)")


def _limited_names(mapping: Dict, limit: int = 30) -> List[Text]:
    if not isinstance(mapping, dict):
        return []

    names = [str(name) for name in mapping.keys()]
    if len(names) > limit:
        return names[:limit] + [f"...(+{len(names) - limit})"]
    return names


def _summarize_value_for_parse_log(value: Any) -> Dict:
    if value is None:
        return {"type": "NoneType", "is_empty": True}

    if isinstance(value, bytes):
        return {"type": "bytes", "length": len(value), "is_empty": len(value) == 0}

    if isinstance(value, str):
        return {"type": "str", "length": len(value), "is_empty": value == ""}

    if isinstance(value, dict):
        keys = [str(key) for key in list(value.keys())[:20]]
        return {
            "type": type(value).__name__,
            "size": len(value),
            "is_empty": len(value) == 0,
            "keys": keys,
            "truncated_keys": len(value) > 20,
        }

    if isinstance(value, list):
        return {
            "type": "list",
            "length": len(value),
            "is_empty": len(value) == 0,
            "item_types": [type(item).__name__ for item in value[:5]],
            "truncated_items": len(value) > 5,
        }

    return {"type": type(value).__name__, "is_empty": False}


def _placeholder_labels(raw_value: Text) -> List[Text]:
    labels = []
    for match in placeholder_function_regex_compile.finditer(raw_value):
        labels.append(f"function:{match.group(1)}")
    for match in placeholder_variable_regex_compile.finditer(raw_value):
        labels.append(f"variable:{match.group(1) or match.group(2)}")
    return sorted(set(labels))


def _collect_unresolved_placeholders(
    value: Any,
    path: Text = "request",
    limit: int = 20,
) -> List[Dict]:
    findings = []

    def walk(current_value: Any, current_path: Text) -> None:
        if len(findings) >= limit:
            return

        if isinstance(current_value, str):
            labels = _placeholder_labels(current_value)
            if labels:
                findings.append({"path": current_path, "labels": labels})
            return

        if isinstance(current_value, dict):
            for key, item in current_value.items():
                if len(findings) >= limit:
                    return

                if isinstance(key, str):
                    labels = _placeholder_labels(key)
                    if labels:
                        findings.append({
                            "path": f"{current_path}.[key]",
                            "labels": labels,
                        })

                safe_key = str(key).replace("\n", " ")[:80]
                walk(item, f"{current_path}.{safe_key}")
            return

        if isinstance(current_value, (list, tuple)):
            for index, item in enumerate(current_value):
                if len(findings) >= limit:
                    return
                walk(item, f"{current_path}[{index}]")

    walk(value, path)
    return findings


def run_step_request(runner: HttpRunner, step: TStep) -> StepResult:
    """run teststep: request"""
    step_result = StepResult(
        name=step.name,
        step_type="request",
        success=False,
    )
    start_time = time.time()

    # parse
    functions = runner.parser.functions_mapping
    step_variables = runner.merge_step_variables(step.variables)
    prepare_upload_step(step, step_variables, functions)
    # parse variables
    step_variables = parse_variables_mapping(step_variables, functions)

    request_dict = step.request.dict()
    request_dict.pop("upload", None)
    parsed_request_dict = runner.parser.parse_data(request_dict, step_variables)
    unresolved_placeholders = _collect_unresolved_placeholders(parsed_request_dict)
    body_target = "req_json" if parsed_request_dict.get("req_json") not in (None, {}) else "data"
    logger.info(
        "Request parse completed: "
        f"case_id={runner.case_id} step_name={step.name} "
        f"variables_count={len(step_variables)} "
        f"variable_keys={_limited_names(step_variables)} "
        f"functions_count={len(functions)} "
        f"function_names={_limited_names(functions)} "
        f"body_target={body_target} "
        f"body_summary={_summarize_value_for_parse_log(parsed_request_dict.get(body_target))} "
        f"unresolved_count={len(unresolved_placeholders)}"
    )
    if unresolved_placeholders:
        logger.warning(
            "Request placeholders remained after parse: "
            f"case_id={runner.case_id} step_name={step.name} "
            f"unresolved={unresolved_placeholders}"
        )

    request_headers = parsed_request_dict.pop("headers", {})
    # omit pseudo header names for HTTP/1, e.g. :authority, :method, :path, :scheme
    request_headers = {
        key: request_headers[key] for key in request_headers if not key.startswith(":")
    }
    request_headers[
        "HRUN-Request-ID"
    ] = f"HRUN-{runner.case_id}-{str(int(time.time() * 1000))[-6:]}"

    # 获取并处理全局请求头
    try:
        from api_environments.models import ApiGlobalRequestHeader as GlobalRequestHeader

        # 检查当前测试用例是否关联到项目
        if hasattr(runner, 'testcase') and hasattr(runner.testcase, 'project_id'):
            project_id = runner.testcase.project_id

            # 获取项目的全局请求头
            headers_qs = GlobalRequestHeader.objects.filter(
                project_id=project_id,
                is_enabled=True
            )

            for header in headers_qs:
                # 如果请求头已存在，则不覆盖（接口优先级高于全局配置）
                if header.name not in request_headers:
                    value = header.value

                    # 处理变量引用 - 支持两种格式：${var}和$var
                    try:
                        if value.startswith('${') and value.endswith('}'):
                            # ${var} 格式
                            var_name = value[2:-1]
                            if var_name in step_variables:
                                value = step_variables[var_name]
                            else:
                                logger.warning(f"全局请求头 '{header.name}' 引用的变量 '${var_name}' 在当前环境中不存在，将使用原始值")
                        elif value.startswith('$') and len(value) > 1:
                            # $var 格式
                            var_name = value[1:]
                            if var_name in step_variables:
                                value = step_variables[var_name]
                            else:
                                logger.warning(f"全局请求头 '{header.name}' 引用的变量 '${var_name}' 在当前环境中不存在，将使用原始值")
                    except Exception as ve:
                        logger.warning(f"处理全局请求头 '{header.name}' 的变量引用时出错: {str(ve)}")

                    request_headers[header.name] = value
                    logger.info(f"应用全局请求头: {header.name}={value}")
    except Exception as e:
        logger.error(f"应用全局请求头失败: {str(e)}")
        # 继续执行，不中断测试

    parsed_request_dict["headers"] = request_headers

    step_variables["request"] = parsed_request_dict

    # setup hooks
    if step.setup_hooks:
        call_hooks(runner, step.setup_hooks, step_variables, "setup request")

    # prepare arguments
    config = runner.get_config()
    method = parsed_request_dict.pop("method")
    url_path = parsed_request_dict.pop("url")
    url = build_url(config.base_url, url_path)
    parsed_request_dict["verify"] = config.verify
    parsed_request_dict["json"] = parsed_request_dict.pop("req_json", {})
    request_json_body = parsed_request_dict.get("json")
    request_data_body = parsed_request_dict.get("data")
    request_body = request_json_body if request_json_body not in (None, {}) else request_data_body
    request_extract_data = {
        "method": method,
        "url": url,
        "headers": request_headers,
        "params": parsed_request_dict.get("params", {}),
        "cookies": parsed_request_dict.get("cookies", {}),
        "body": request_body,
        "json": request_json_body,
        "data": request_data_body,
    }

    # log request
    request_print = "====== request details ======\n"
    request_print += f"url: {url}\n"
    request_print += f"method: {method}\n"
    for k, v in parsed_request_dict.items():
        request_print += f"{k}: {pretty_format(v)}\n"

    logger.debug(request_print)
    if ALLURE is not None:
        ALLURE.attach(
            request_print,
            name="request details",
            attachment_type=ALLURE.attachment_type.TEXT,
        )
    resp = runner.session.request(method, url, **parsed_request_dict)

    # log response
    response_print = "====== response details ======\n"
    response_print += f"status_code: {resp.status_code}\n"
    response_print += f"headers: {pretty_format(resp.headers)}\n"

    try:
        resp_body = resp.json()
    except (requests.exceptions.JSONDecodeError, json.decoder.JSONDecodeError):
        resp_body = resp.content

    response_print += f"body: {pretty_format(resp_body)}\n"
    logger.debug(response_print)
    if ALLURE is not None:
        ALLURE.attach(
            response_print,
            name="response details",
            attachment_type=ALLURE.attachment_type.TEXT,
        )
    resp_obj = ResponseObject(resp, runner.parser)
    step_variables["response"] = resp_obj

    # teardown hooks
    if step.teardown_hooks:
        call_hooks(runner, step.teardown_hooks, step_variables, "teardown request")

    # extract
    extractors = step.extract
    extract_mapping = extract_variables_by_source(
        resp_obj,
        extractors,
        getattr(step, "extract_meta", {}),
        request_extract_data,
        runner,
        step_variables,
    )
    step_result.export_vars = extract_mapping

    variables_mapping = step_variables
    variables_mapping.update(extract_mapping)

    # validate
    validators = step.validators
    try:
        resp_obj.validate(validators, variables_mapping)
        step_result.success = True
    except ValidationFailure:
        raise
    finally:
        session_data = runner.session.data
        session_data.success = step_result.success
        session_data.validators = resp_obj.validation_results

        # save step data
        step_result.data = session_data
        step_result.elapsed = time.time() - start_time

    return step_result


class StepRequestValidation(IStep):
    def __init__(self, step: TStep):
        self.__step = step

    def assert_equal(
        self, jmes_path: Text, expected_value: Any, message: Text = ""
    ) -> "StepRequestValidation":
        self.__step.validators.append({"equal": [jmes_path, expected_value, message]})
        return self

    def assert_not_equal(
        self, jmes_path: Text, expected_value: Any, message: Text = ""
    ) -> "StepRequestValidation":
        self.__step.validators.append(
            {"not_equal": [jmes_path, expected_value, message]}
        )
        return self

    def assert_greater_than(
        self, jmes_path: Text, expected_value: Union[int, float], message: Text = ""
    ) -> "StepRequestValidation":
        self.__step.validators.append(
            {"greater_than": [jmes_path, expected_value, message]}
        )
        return self

    def assert_less_than(
        self, jmes_path: Text, expected_value: Union[int, float], message: Text = ""
    ) -> "StepRequestValidation":
        self.__step.validators.append(
            {"less_than": [jmes_path, expected_value, message]}
        )
        return self

    def assert_greater_or_equals(
        self, jmes_path: Text, expected_value: Union[int, float], message: Text = ""
    ) -> "StepRequestValidation":
        self.__step.validators.append(
            {"greater_or_equals": [jmes_path, expected_value, message]}
        )
        return self

    def assert_less_or_equals(
        self, jmes_path: Text, expected_value: Union[int, float], message: Text = ""
    ) -> "StepRequestValidation":
        self.__step.validators.append(
            {"less_or_equals": [jmes_path, expected_value, message]}
        )
        return self

    def assert_length_equal(
        self, jmes_path: Text, expected_value: int, message: Text = ""
    ) -> "StepRequestValidation":
        self.__step.validators.append(
            {"length_equal": [jmes_path, expected_value, message]}
        )
        return self

    def assert_length_greater_than(
        self, jmes_path: Text, expected_value: int, message: Text = ""
    ) -> "StepRequestValidation":
        self.__step.validators.append(
            {"length_greater_than": [jmes_path, expected_value, message]}
        )
        return self

    def assert_length_less_than(
        self, jmes_path: Text, expected_value: int, message: Text = ""
    ) -> "StepRequestValidation":
        self.__step.validators.append(
            {"length_less_than": [jmes_path, expected_value, message]}
        )
        return self

    def assert_length_greater_or_equals(
        self, jmes_path: Text, expected_value: int, message: Text = ""
    ) -> "StepRequestValidation":
        self.__step.validators.append(
            {"length_greater_or_equals": [jmes_path, expected_value, message]}
        )
        return self

    def assert_length_less_or_equals(
        self, jmes_path: Text, expected_value: int, message: Text = ""
    ) -> "StepRequestValidation":
        self.__step.validators.append(
            {"length_less_or_equals": [jmes_path, expected_value, message]}
        )
        return self

    def assert_string_equals(
        self, jmes_path: Text, expected_value: Any, message: Text = ""
    ) -> "StepRequestValidation":
        self.__step.validators.append(
            {"string_equals": [jmes_path, expected_value, message]}
        )
        return self

    def assert_startswith(
        self, jmes_path: Text, expected_value: Text, message: Text = ""
    ) -> "StepRequestValidation":
        self.__step.validators.append(
            {"startswith": [jmes_path, expected_value, message]}
        )
        return self

    def assert_endswith(
        self, jmes_path: Text, expected_value: Text, message: Text = ""
    ) -> "StepRequestValidation":
        self.__step.validators.append(
            {"endswith": [jmes_path, expected_value, message]}
        )
        return self

    def assert_regex_match(
        self, jmes_path: Text, expected_value: Text, message: Text = ""
    ) -> "StepRequestValidation":
        self.__step.validators.append(
            {"regex_match": [jmes_path, expected_value, message]}
        )
        return self

    def assert_contains(
        self, jmes_path: Text, expected_value: Any, message: Text = ""
    ) -> "StepRequestValidation":
        self.__step.validators.append(
            {"contains": [jmes_path, expected_value, message]}
        )
        return self

    def assert_contained_by(
        self, jmes_path: Text, expected_value: Any, message: Text = ""
    ) -> "StepRequestValidation":
        self.__step.validators.append(
            {"contained_by": [jmes_path, expected_value, message]}
        )
        return self

    def assert_type_match(
        self, jmes_path: Text, expected_value: Any, message: Text = ""
    ) -> "StepRequestValidation":
        self.__step.validators.append(
            {"type_match": [jmes_path, expected_value, message]}
        )
        return self

    def struct(self) -> TStep:
        return self.__step

    def name(self) -> Text:
        return self.__step.name

    def type(self) -> Text:
        return f"request-{self.__step.request.method}"

    def run(self, runner: HttpRunner):
        return run_step_request(runner, self.__step)


class StepRequestExtraction(IStep):
    def __init__(self, step: TStep):
        self.__step = step

    def with_jmespath(
        self,
        jmes_path: Text,
        var_name: Text,
        source: Text = "response",
    ) -> "StepRequestExtraction":
        self.__step.extract[var_name] = jmes_path
        self.__step.extract_meta[var_name] = {"source": normalize_extract_source(source)}
        return self

    # def with_regex(self):
    #     # TODO: extract response html with regex
    #     pass
    #
    # def with_jsonpath(self):
    #     # TODO: extract response json with jsonpath
    #     pass

    def validate(self) -> StepRequestValidation:
        return StepRequestValidation(self.__step)

    def struct(self) -> TStep:
        return self.__step

    def name(self) -> Text:
        return self.__step.name

    def type(self) -> Text:
        return f"request-{self.__step.request.method}"

    def run(self, runner: HttpRunner):
        return run_step_request(runner, self.__step)


class RequestWithOptionalArgs(IStep):
    def __init__(self, step: TStep):
        self.__step = step

    def with_params(self, **params) -> "RequestWithOptionalArgs":
        self.__step.request.params.update(params)
        return self

    def with_headers(self, **headers) -> "RequestWithOptionalArgs":
        self.__step.request.headers.update(headers)
        return self

    def with_cookies(self, **cookies) -> "RequestWithOptionalArgs":
        self.__step.request.cookies.update(cookies)
        return self

    def with_data(self, data) -> "RequestWithOptionalArgs":
        self.__step.request.data = data
        return self

    def with_json(self, req_json) -> "RequestWithOptionalArgs":
        self.__step.request.req_json = req_json
        return self

    def set_timeout(self, timeout: float) -> "RequestWithOptionalArgs":
        self.__step.request.timeout = timeout
        return self

    def set_verify(self, verify: bool) -> "RequestWithOptionalArgs":
        self.__step.request.verify = verify
        return self

    def set_allow_redirects(self, allow_redirects: bool) -> "RequestWithOptionalArgs":
        self.__step.request.allow_redirects = allow_redirects
        return self

    def upload(self, **file_info) -> "RequestWithOptionalArgs":
        self.__step.request.upload.update(file_info)
        return self

    def teardown_hook(
        self, hook: Text, assign_var_name: Text = None
    ) -> "RequestWithOptionalArgs":
        if assign_var_name:
            self.__step.teardown_hooks.append({assign_var_name: hook})
        else:
            self.__step.teardown_hooks.append(hook)

        return self

    def extract(self) -> StepRequestExtraction:
        return StepRequestExtraction(self.__step)

    def validate(self) -> StepRequestValidation:
        return StepRequestValidation(self.__step)

    def struct(self) -> TStep:
        return self.__step

    def name(self) -> Text:
        return self.__step.name

    def type(self) -> Text:
        return f"request-{self.__step.request.method}"

    def run(self, runner: HttpRunner):
        return run_step_request(runner, self.__step)


class RunRequest(object):
    def __init__(self, name: Text):
        self.__step = TStep(name=name)

    def with_variables(self, **variables) -> "RunRequest":
        self.__step.variables.update(variables)
        return self

    def with_retry(self, retry_times, retry_interval) -> "RunRequest":
        self.__step.retry_times = retry_times
        self.__step.retry_interval = retry_interval
        return self

    def setup_hook(self, hook: Text, assign_var_name: Text = None) -> "RunRequest":
        if assign_var_name:
            self.__step.setup_hooks.append({assign_var_name: hook})
        else:
            self.__step.setup_hooks.append(hook)

        return self

    def get(self, url: Text) -> RequestWithOptionalArgs:
        self.__step.request = TRequest(method=MethodEnum.GET, url=url)
        return RequestWithOptionalArgs(self.__step)

    def post(self, url: Text) -> RequestWithOptionalArgs:
        self.__step.request = TRequest(method=MethodEnum.POST, url=url)
        return RequestWithOptionalArgs(self.__step)

    def put(self, url: Text) -> RequestWithOptionalArgs:
        self.__step.request = TRequest(method=MethodEnum.PUT, url=url)
        return RequestWithOptionalArgs(self.__step)

    def head(self, url: Text) -> RequestWithOptionalArgs:
        self.__step.request = TRequest(method=MethodEnum.HEAD, url=url)
        return RequestWithOptionalArgs(self.__step)

    def delete(self, url: Text) -> RequestWithOptionalArgs:
        self.__step.request = TRequest(method=MethodEnum.DELETE, url=url)
        return RequestWithOptionalArgs(self.__step)

    def options(self, url: Text) -> RequestWithOptionalArgs:
        self.__step.request = TRequest(method=MethodEnum.OPTIONS, url=url)
        return RequestWithOptionalArgs(self.__step)

    def patch(self, url: Text) -> RequestWithOptionalArgs:
        self.__step.request = TRequest(method=MethodEnum.PATCH, url=url)
        return RequestWithOptionalArgs(self.__step)
