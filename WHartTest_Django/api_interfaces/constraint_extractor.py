"""接口文档参数约束提取服务。

从已解析的 API 文档（OpenAPI 3.x / Swagger 2.0 / cURL / Markdown 等可归一化为
OpenAPI 的格式）中，按 path+method 匹配选中的接口定义，提取参数约束清单
（类型/必填/枚举全集/数值范围/长度限制/格式），供 AI 生成接口测试用例时作为
必填校验/类型校验/边界值/长度限制/参数组合校验的证据来源，同时作为接口
预览视图的数据源。纯确定性代码，无 AI 参与。

展示原则（对齐 MeterSphere 导入预览）：所有参数逐行保留——必填缺失校验与
类型校验需要每个参数的 required/type，参数组合校验需要参数的业务说明；
无约束信息的字段约束列留空而不是丢弃或折叠为摘要。
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from .exchange import parse_api_document
from .openapi import _iter_operations, _resolve_ref, _resolve_parameters, _select_media_type

# 递归展开嵌套 schema 的最大深度，防止超深文档拖垮提取耗时与 token 体积
_MAX_SCHEMA_DEPTH = 2  # 递归展开收紧为 2 层：RuoYi 类自引用树形 schema 展开收益为零
# 单接口返回的字段条数上限，超出截断并登记 truncated
_MAX_FIELDS_PER_INTERFACE = 80


def extract_constraints_from_document(
    content,
    interface_targets: list[dict[str, Any]],
    *,
    filename: str = "",
    source_type: str = "",
    strip_base_url: bool = True,
) -> dict[str, Any]:
    """解析文档并提取指定接口的参数约束。

    Args:
        content: 文档内容（bytes/str/dict），透传给 parse_api_document。
        interface_targets: 匹配目标列表，每项形如
            {"interface_id": 1, "name": "登录", "method": "POST", "url": "/api/login"}。
            url 允许带 {var} 或 {var:path} 形式的路径参数模板，也允许是完整 URL。

    Returns:
        {"format": 文档格式, "version": 版本,
         "interfaces": [{interface_id, name, method, url, matched, params: {...}, body_fields: [...],
                         response: {...}, success_codes: [...], notes: [...], truncated: bool}],
         "unmatched": [未匹配的目标摘要]}
    """
    parsed = parse_api_document(
        content,
        filename=filename,
        source_type=source_type,
        strip_base_url=strip_base_url,
    )
    document = parsed.document
    operations = _iter_operations(document, strip_base_url=strip_base_url)

    interfaces: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []

    for target in interface_targets:
        matched = _match_operation(operations, target)
        if matched is None:
            unmatched.append({
                "interface_id": target.get("interface_id"),
                "name": target.get("name"),
                "method": (target.get("method") or "").upper(),
                "url": target.get("url"),
            })
            continue

        method, path, operation_info = matched
        payload = _extract_operation_constraints(document, operation_info)
        interfaces.append({
            "interface_id": target.get("interface_id"),
            "name": target.get("name"),
            "method": method,
            "url": path,
            "matched": True,
            **payload,
        })

    return {
        "format": parsed.source_format,
        "version": parsed.source_version,
        "interfaces": interfaces,
        "unmatched": unmatched,
    }


def _match_operation(
    operations: list[dict[str, Any]],
    target: dict[str, Any],
) -> tuple[str, str, dict[str, Any]] | None:
    """按 method + 归一化 path 匹配文档操作；匹配不到时尝试宽松路径比对与公共前缀容错。"""
    target_method = str(target.get("method") or "").upper()
    target_path = _normalize_path(target.get("url") or "")
    if not target_path:
        return None

    exact: list[tuple[str, str, dict[str, Any]]] = []
    loose: list[tuple[str, str, dict[str, Any]]] = []
    for op in operations:
        method = op["method"]
        path = _normalize_path(op["path"])
        raw_path = _normalize_path(op.get("raw_path") or op["path"])
        if target_method and method != target_method:
            continue
        if path == target_path or raw_path == target_path:
            exact.append((method, op["path"], op))
            continue
        if _loose_path_equal(target_path, path) or _loose_path_equal(target_path, raw_path):
            loose.append((method, op["path"], op))

    if exact:
        return exact[0]
    if len(loose) == 1:
        return loose[0]
    if loose:
        # 多个宽松候选时视为不明确，宁可放弃也不取错
        return None

    # 公共前缀容错：平台 URL 可能带网关前缀（如 /api），文档路径没有（或反之）。
    # 对所有文档路径统一剥离首位网关风格段后重试精确与宽松比对。
    prefix_stripped: list[tuple[str, str, dict[str, Any]]] = []
    prefix_loose: list[tuple[str, str, dict[str, Any]]] = []
    for op in operations:
        method = op["method"]
        if target_method and method != target_method:
            continue
        path = _normalize_path(op["path"])
        raw_path = _normalize_path(op.get("raw_path") or op["path"])
        for op_path in {path, raw_path}:
            if _match_ignoring_gateway_prefix(target_path, op_path):
                prefix_stripped.append((method, op["path"], op))
                break
            if _loose_path_equal(*_strip_first_segment_pair(target_path, op_path)):
                prefix_loose.append((method, op["path"], op))
                break

    if len(prefix_stripped) == 1:
        return prefix_stripped[0]
    if len(prefix_stripped) > 1:
        # 多个候选时再按宽松语义收敛一次
        unique_paths = {op_path for _, _, op_path in {(m, p, o) for m, p, o in prefix_stripped}}
        return prefix_stripped[0] if len(unique_paths) == 1 else None
    if len(prefix_loose) == 1:
        return prefix_loose[0]
    return None


def _strip_first_segment_pair(left: str, right: str) -> tuple[str, str]:
    """两侧各剥掉首个路径段（若存在），用于 /api 前缀差异场景的宽松比对。"""
    left_segments = [seg for seg in left.split("/") if seg != ""]
    right_segments = [seg for seg in right.split("/") if seg != ""]
    if left_segments and right_segments:
        return "/" + "/".join(left_segments[1:]), "/" + "/".join(right_segments[1:])
    return left, right


def _match_ignoring_gateway_prefix(target_path: str, op_path: str) -> bool:
    """剥离任一侧的首段网关前缀后判断路径是否精确相等。"""
    if target_path == op_path:
        return True
    target_segments = [seg for seg in target_path.split("/") if seg != ""]
    op_segments = [seg for seg in op_path.split("/") if seg != ""]
    if target_segments and op_path == "/" + "/".join(target_segments[1:]):
        return True
    if op_segments and target_path == "/" + "/".join(op_segments[1:]):
        return True
    return False


def _normalize_path(url: Any) -> str:
    """去掉 origin 与 query，仅保留路径部分；统一大括号路径参数风格。"""
    text = str(url or "").strip()
    if not text:
        return ""
    parsed = urlparse(text)
    path = parsed.path if (parsed.scheme or parsed.netloc) else text.split("?")[0]
    path = path.rstrip("/") or "/"
    # 统一 :param 与 <param> 风格为 {param}，仅比对形态不做语义校验
    path = re.sub(r"(?<!\{):([A-Za-z_][A-Za-z0-9_]*)", r"{\1}", path)
    path = re.sub(r"<([A-Za-z_][A-Za-z0-9_:]*(?::path)?)>", r"{\1}", path)
    return path


def _loose_path_equal(left: str, right: str) -> bool:
    """路径段数量一致且静态段相同时视为宽松匹配（允许参数段形态差异）。"""
    left_segments = [seg for seg in left.split("/") if seg != ""]
    right_segments = [seg for seg in right.split("/") if seg != ""]
    if len(left_segments) != len(right_segments):
        return False
    for left_seg, right_seg in zip(left_segments, right_segments):
        left_is_param = _is_param_segment(left_seg)
        right_is_param = _is_param_segment(right_seg)
        if left_is_param and right_is_param:
            continue
        if left_seg == right_seg:
            continue
        return False
    return True


def _is_param_segment(segment: str) -> bool:
    return segment.startswith("{") and segment.endswith("}")


def _extract_operation_constraints(
    document: dict[str, Any],
    operation_info: dict[str, Any],
) -> dict[str, Any]:
    operation = operation_info["operation"]
    path_parameters = _resolve_parameters(document, operation_info.get("path_parameters") or [])
    operation_parameters = _resolve_parameters(document, operation.get("parameters") or [])
    parameters = path_parameters + operation_parameters

    notes: list[str] = []
    params: dict[str, list[dict[str, Any]]] = {"path": [], "query": [], "header": []}
    field_count = 0
    truncated = False

    for parameter in parameters:
        if field_count >= _MAX_FIELDS_PER_INTERFACE:
            truncated = True
            break
        location = parameter.get("in")
        if location not in params:
            continue
        constraint = _parameter_constraint(document, parameter)
        params[location].append(constraint)
        field_count += 1

    # body 完整展开：每个接口的快照自包含（预览完整、模型按需读取单接口即可），
    # 不做跨接口共享 schema 去重
    body_payload = (
        _openapi_body_fields(document, operation)
        if not operation_info.get("is_swagger")
        else _swagger_body_fields(document, operation_info, parameters)
    )
    body_fields: list[dict[str, Any]] = []
    required_list: list[str] = []
    if isinstance(body_payload, dict):
        body_fields = body_payload.get("fields", [])
        required_list = body_payload.get("required", [])
        notes.extend(body_payload.get("notes", []))
        remaining = max(0, _MAX_FIELDS_PER_INTERFACE - field_count)
        if len(body_fields) > remaining:
            body_fields = body_fields[:remaining]
            truncated = True
        field_count += len(body_fields)

    response = _response_constraints(document, operation)
    if response.get("truncated"):
        truncated = True
    if field_count >= _MAX_FIELDS_PER_INTERFACE and not body_fields:
        truncated = True

    return {
        "params": params,
        "body_fields": body_fields,
        "body_required": required_list,
        "response": response,
        "notes": notes,
        "truncated": truncated,
    }


def _parameter_constraint(document: dict[str, Any], parameter: dict[str, Any]) -> dict[str, Any]:
    schema = _resolve_ref(document, parameter.get("schema", parameter))
    constraint = _schema_constraint(document, schema, name=str(parameter.get("name") or ""))
    constraint["description"] = str(parameter.get("description") or "")
    return constraint


def _swagger_body_fields(
    document: dict[str, Any],
    operation_info: dict[str, Any],
    parameters: list[dict[str, Any]],
) -> dict[str, Any]:
    """Swagger 2.0 的 body/formData 参数归一化为 body 字段清单。"""
    operation = operation_info["operation"]
    fields: list[dict[str, Any]] = []
    notes: list[str] = []

    body_parameter = next((p for p in parameters if p.get("in") == "body"), None)
    if body_parameter is not None:
        schema = _resolve_ref(document, body_parameter.get("schema"))
        if isinstance(schema, dict):
            fields = _flatten_object_fields(document, schema, notes=notes)
        # 同一操作的 formData 参数也并入 body 字段清单（body+formData 混合声明的老文档）
        for parameter in parameters:
            if parameter.get("in") != "formData" or len(fields) >= _MAX_FIELDS_PER_INTERFACE:
                continue
            item = _parameter_constraint(document, parameter)
            item["required"] = bool(parameter.get("required"))
            fields.append(item)
        required = schema.get("required") if isinstance(schema, dict) else None
        return {"fields": fields, "required": required or [], "notes": notes}

    for parameter in parameters:
        if parameter.get("in") != "formData":
            continue
        if len(fields) >= _MAX_FIELDS_PER_INTERFACE:
            notes.append("formData 字段过多，已截断")
            break
        item = _parameter_constraint(document, parameter)
        item["required"] = bool(parameter.get("required"))
        fields.append(item)

    if not fields and not notes:
        notes.append("该操作未声明请求体")
    required = [item["name"] for item in fields if item.get("required")]
    return {"fields": fields, "required": required, "notes": notes}


def _openapi_body_fields(document: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    """OpenAPI 3.x requestBody 的 schema 展开为字段约束清单。"""
    notes: list[str] = []
    request_body = _resolve_ref(document, operation.get("requestBody"))
    if not isinstance(request_body, dict):
        return {"fields": [], "required": [], "notes": ["该操作未声明请求体"]}

    content = request_body.get("content")
    if not isinstance(content, dict) or not content:
        return {"fields": [], "required": [], "notes": ["该操作未声明请求体"]}

    _, media = _select_media_type(content)
    if not isinstance(media, dict):
        return {"fields": [], "required": [], "notes": ["请求体无可识别的媒体类型"]}

    schema = _resolve_ref(document, media.get("schema"))
    if not isinstance(schema, dict):
        return {"fields": [], "required": [], "notes": ["请求体 schema 缺失"]}

    fields = _flatten_object_fields(document, schema, notes=notes)
    required = schema.get("required") if isinstance(schema.get("required"), list) else []
    return {"fields": fields, "required": required, "notes": notes}


def _schema_constraint(
    document: dict[str, Any],
    schema: Any,
    *,
    name: str,
    depth: int = 0,
) -> dict[str, Any]:
    """把 JSON Schema 归一化为约束四元组 {name, type, required, constraints}。"""
    schema = _resolve_ref(document, schema)
    if not isinstance(schema, dict):
        return {"name": name, "type": "string", "constraints": {}, "description": ""}

    schema_type = schema.get("type")
    if not schema_type and "properties" in schema:
        schema_type = "object"
    if isinstance(schema_type, list):
        schema_type = next((item for item in schema_type if item != "null"), schema_type[0])

    constraint: dict[str, Any] = {"name": name, "type": schema_type or "string", "constraints": {}}
    if isinstance(schema.get("title"), str) and schema["title"]:
        constraint["title"] = schema["title"]

    constraints = constraint["constraints"]
    if isinstance(schema.get("enum"), list) and schema["enum"]:
        constraints["enum"] = schema["enum"][: _MAX_FIELDS_PER_INTERFACE]
    for key in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "minLength", "maxLength", "pattern"):
        if schema.get(key) is not None:
            constraints[key] = schema[key]
    if schema.get("format"):
        constraints["format"] = str(schema["format"])
    if schema.get("nullable") is True:
        constraints["nullable"] = True
    if isinstance(schema.get("default"), (str, int, float, bool)):
        constraint["default"] = schema["default"]

    constraint["description"] = str(schema.get("description") or "")
    return constraint


def _flatten_object_fields(
    document: dict[str, Any],
    schema: Any,
    *,
    notes: list[str],
    depth: int = 0,
) -> list[dict[str, Any]]:
    """递归展开 object schema 的 properties 至叶子字段；array 展开到 items 一层。

    展示原则（对齐 MeterSphere 导入预览）：所有参数逐行保留，不做聚合折叠——
    必填/类型校验需要每个参数的 required 与 type，参数组合校验需要业务说明；
    无约束信息的字段约束列留空。深度截断处仍记折叠说明（自引用树不重复展开）。
    """
    schema = _resolve_ref(document, schema)
    if not isinstance(schema, dict):
        return []
    if depth >= _MAX_SCHEMA_DEPTH:
        notes.append(f"嵌套超过 {_MAX_SCHEMA_DEPTH} 层，更深层子树结构与当前层类似，已折叠")
        return []

    required_names = schema.get("required") if isinstance(schema.get("required"), list) else []
    properties = schema.get("properties")
    if not isinstance(properties, dict) or not properties:
        # 无 properties 的对象（additionalProperties / 自由结构），记录类型即可
        return [{
            "name": "(body)",
            "type": schema.get("type") or "object",
            "required": False,
            "constraints": {},
            "description": "自由结构对象，无字段级约束",
        }]

    fields: list[dict[str, Any]] = []
    for key, child in properties.items():
        if len(fields) >= _MAX_FIELDS_PER_INTERFACE:
            notes.append("字段过多，已截断")
            break
        child_schema = _resolve_ref(document, child)
        if not isinstance(child_schema, dict):
            continue
        child_type = child_schema.get("type")
        if not child_type and "properties" in child_schema:
            child_type = "object"
        constraint = _schema_constraint(document, child_schema, name=str(key), depth=depth)
        constraint["required"] = key in required_names
        fields.append(constraint)

        # 嵌套 object/array 继续展开一层，字段名用点路径表达
        if child_type == "object" and isinstance(child_schema.get("properties"), dict) and child_schema.get("properties"):
            nested = _flatten_object_fields(document, child_schema, notes=notes, depth=depth + 1)
            for item in nested:
                item["name"] = f"{key}.{item['name']}"
            fields.extend(nested[: max(0, _MAX_FIELDS_PER_INTERFACE - len(fields))])
        elif child_type == "array":
            items_schema = _resolve_ref(document, child_schema.get("items"))
            if isinstance(items_schema, dict) and items_schema.get("type") == "object" and isinstance(items_schema.get("properties"), dict):
                nested = _flatten_object_fields(document, items_schema, notes=notes, depth=depth + 1)
                for item in nested:
                    item["name"] = f"{key}[]{item['name']}"
                fields.extend(nested[: max(0, _MAX_FIELDS_PER_INTERFACE - len(fields))])

    return fields


def _response_constraints(document: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    responses = operation.get("responses")
    if not isinstance(responses, dict):
        return {}

    success_codes: list[int] = []
    for code in responses.keys():
        try:
            numeric = int(str(code))
        except ValueError:
            continue
        if 200 <= numeric < 300:
            success_codes.append(numeric)
    success_codes.sort()

    primary_key = None
    for code in responses.keys():
        try:
            if int(str(code)) == (success_codes[0] if success_codes else 200):
                primary_key = code
                break
        except ValueError:
            continue

    if primary_key is None:
        return {"success_codes": success_codes}

    response_item = _resolve_ref(document, responses[primary_key])
    if not isinstance(response_item, dict):
        return {"success_codes": success_codes}

    content = response_item.get("content")
    schema: Any = None
    if isinstance(content, dict) and content:
        media = next(
            (value for key, value in content.items() if str(key).endswith("json")),
            None,
        )
        if media is None:
            media = next(iter(content.values()))
        if isinstance(media, dict):
            schema = media.get("schema")
    elif response_item.get("schema") is not None:
        # Swagger 2.0 的响应 schema 直接挂在 response 上
        schema = response_item.get("schema")

    fields: list[dict[str, Any]] = []
    notes: list[str] = []
    truncated = False
    if schema is not None:
        fields = _flatten_object_fields(document, schema, notes=notes)
        if len(fields) >= _MAX_FIELDS_PER_INTERFACE:
            truncated = True

    return {
        "success_codes": success_codes,
        "success_code": success_codes[0] if success_codes else None,
        "fields": fields,
        "notes": notes,
        "truncated": truncated,
    }
