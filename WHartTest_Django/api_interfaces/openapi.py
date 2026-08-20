from __future__ import annotations

import json
import posixpath
import re
from copy import deepcopy
from typing import Any
from urllib.parse import urlparse

try:
    import yaml
except ImportError:  # pragma: no cover - dependency is declared in requirements
    yaml = None

from django.db import transaction
from api_modules.models import ApiModule
from api_environments.models import ApiEnvironment
from projects.models import Project

from .models import ApiInterface
from .payloads import stringify_pair_value
from .serializers import ApiInterfaceSerializer


SUPPORTED_HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}
PATH_ITEM_KEYS = {
    "summary",
    "description",
    "servers",
    "parameters",
    "$ref",
}


class OpenAPIError(ValueError):
    """Raised when an OpenAPI/Swagger document cannot be imported."""


def parse_openapi_document(content: bytes | str | dict[str, Any], filename: str = "") -> dict[str, Any]:
    if isinstance(content, dict):
        document = deepcopy(content)
    else:
        if isinstance(content, bytes):
            text = content.decode("utf-8-sig")
        else:
            text = content

        stripped = text.strip()
        if not stripped:
            raise OpenAPIError("The uploaded document is empty.")

        lower_name = filename.lower()
        parse_as_json = lower_name.endswith(".json") or stripped.startswith("{")

        try:
            if parse_as_json:
                document = json.loads(stripped)
            else:
                if yaml is None:
                    raise OpenAPIError("PyYAML is required to import YAML OpenAPI documents.")
                document = yaml.safe_load(stripped)
        except json.JSONDecodeError as exc:
            raise OpenAPIError(f"Invalid JSON document: {exc}") from exc
        except Exception as exc:
            if isinstance(exc, OpenAPIError):
                raise
            raise OpenAPIError(f"Invalid YAML document: {exc}") from exc

    if not isinstance(document, dict):
        raise OpenAPIError("The OpenAPI document root must be an object.")

    if not (document.get("openapi") or document.get("swagger") == "2.0"):
        raise OpenAPIError("Only OpenAPI 3.x and Swagger 2.0 documents are supported.")

    if not isinstance(document.get("paths"), dict):
        raise OpenAPIError("The document must contain a paths object.")

    return document


def import_openapi_interfaces(
    *,
    document: dict[str, Any],
    project: Project,
    user,
    request,
    view,
    strip_base_url: bool = True,
    create_environments: bool = False,
) -> dict[str, Any]:
    operations = _iter_operations(document, strip_base_url=strip_base_url)

    created_count = 0
    updated_count = 0
    skipped: list[dict[str, Any]] = []
    imported_ids: list[int] = []

    # 整体在一个事务内执行:任一步失败(校验错误、数据库异常等)都全部回滚,
    # 不会出现导入到一半留下部分接口的情况。
    with transaction.atomic():
        module_cache: dict[str, ApiModule] = _existing_module_cache(project)
        existing_by_key, used_names = _existing_interface_index(project)
        touched_modules: set[str] = set()

        for operation in operations:
            method = operation["method"]
            path = operation["path"]

            if method not in SUPPORTED_HTTP_METHODS:
                skipped.append({"method": method, "path": path, "reason": "Unsupported HTTP method."})
                continue

            try:
                payload = _operation_to_interface_payload(document, operation)
            except OpenAPIError as exc:
                skipped.append({"method": method, "path": path, "reason": str(exc)})
                continue

            module_name = payload.pop("_module_name", "")
            if module_name:
                module = _get_or_create_module(
                    project=project,
                    user=user,
                    name=module_name,
                    cache=module_cache,
                )
                payload["module"] = module.id
                touched_modules.add(module.name)

            existing = existing_by_key.get((payload["method"], payload["url"]))
            existing_name = existing.name if existing else None

            payload["name"] = _unique_interface_name(
                name=payload["name"],
                used_names=used_names,
                exclude_name=existing_name,
            )

            serializer = ApiInterfaceSerializer(
                existing,
                data=payload,
                partial=bool(existing),
                context={"request": request, "view": view},
            )
            serializer.is_valid(raise_exception=True)
            if existing:
                instance = serializer.save(project=project)
            else:
                instance = serializer.save(project=project, created_by=user)
            imported_ids.append(instance.id)

            if existing:
                updated_count += 1
            else:
                created_count += 1

            existing_by_key[(payload["method"], payload["url"])] = instance
            if existing_name:
                used_names.discard(existing_name)
            used_names.add(instance.name)

        created_environments: list[dict[str, Any]] = []
        if create_environments:
            created_environments = _create_environments_from_document(
                document=document,
                project=project,
                user=user,
            )

    return {
        "format": "swagger" if document.get("swagger") == "2.0" else "openapi",
        "version": document.get("swagger") or document.get("openapi"),
        "created_count": created_count,
        "updated_count": updated_count,
        "imported_count": created_count + updated_count,
        "skipped_count": len(skipped),
        "skipped": skipped[:50],
        "imported_ids": imported_ids,
        "module_count": len(touched_modules),
        "created_environments": created_environments,
    }


def build_openapi_document(project: Project, queryset) -> dict[str, Any]:
    paths: dict[str, Any] = {}
    tags: dict[str, dict[str, str]] = {}

    for interface in queryset.filter(type=ApiInterface.TYPE_HTTP).order_by("module__name", "name", "id"):
        method = (interface.method or "GET").lower()
        if method.upper() not in SUPPORTED_HTTP_METHODS:
            continue

        path = _normalize_export_path(interface.url or "/")
        operation: dict[str, Any] = {
            "summary": interface.name,
            "operationId": f"interface_{interface.id}",
            "responses": _build_responses(interface),
        }

        if interface.module_id and interface.module:
            operation["tags"] = [interface.module.name]
            tags[interface.module.name] = {
                "name": interface.module.name,
                "description": interface.module.description or "",
            }

        parameters = _build_parameters(interface)
        if parameters:
            operation["parameters"] = parameters

        request_body = _build_request_body(interface)
        if request_body:
            operation["requestBody"] = request_body

        paths.setdefault(path, {})[method] = operation

    return {
        "openapi": "3.0.3",
        "info": {
            "title": f"{project.name} API Interfaces",
            "version": "1.0.0",
        },
        "servers": [{"url": "/"}],
        "tags": list(tags.values()),
        "paths": paths,
    }


def dump_openapi_document(document: dict[str, Any], export_format: str) -> tuple[str, str, str]:
    normalized_format = (export_format or "json").lower()
    if normalized_format in {"yaml", "yml"}:
        if yaml is None:
            raise OpenAPIError("PyYAML is required to export YAML OpenAPI documents.")
        return (
            yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
            "application/yaml; charset=utf-8",
            "yaml",
        )

    return (
        json.dumps(document, ensure_ascii=False, indent=2),
        "application/json; charset=utf-8",
        "json",
    )


def _iter_operations(
    document: dict[str, Any],
    *,
    strip_base_url: bool = True,
) -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = []
    is_swagger = document.get("swagger") == "2.0"
    if strip_base_url:
        root_prefix = _swagger_base_path(document) if is_swagger else _openapi_server_path(document)
    else:
        root_prefix = _swagger_full_prefix(document) if is_swagger else _openapi_server_full_prefix(document)

    for raw_path, path_item in document.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        path_parameters = path_item.get("parameters", [])
        for method_key, operation in path_item.items():
            method = method_key.upper()
            if method_key in PATH_ITEM_KEYS or not isinstance(operation, dict):
                continue
            raw_path_text = str(raw_path)
            parsed_raw = urlparse(raw_path_text)
            # strip_base_url 模式下，完整 URL 路径先剥离 origin，
            # 避免拼出 "/http:/host/..." 垃圾路径（也导致模块名变成 "http:"）
            if strip_base_url and (parsed_raw.scheme or parsed_raw.netloc):
                raw_path_text = parsed_raw.path or "/"
            # 当保留完整 URL 且路径本身已含 scheme/netloc（Postman/HAR/cURL 等），
            # 不再拼接 root_prefix，直接使用原始路径。
            if not strip_base_url and (parsed_raw.scheme or parsed_raw.netloc):
                full_path = raw_path_text
            elif not strip_base_url and root_prefix and _is_url_prefix(root_prefix):
                # root_prefix 是完整 URL（保留 origin 模式），用字符串拼接而非 posixpath
                full_path = _join_full_url_path(root_prefix, raw_path_text)
            else:
                full_path = _join_url_path(root_prefix, raw_path_text)
            operations.append({
                "method": method,
                "path": full_path,
                "raw_path": raw_path_text,
                "path_parameters": path_parameters,
                "operation": operation,
                "is_swagger": is_swagger,
            })

    return operations


def _operation_to_interface_payload(
    document: dict[str, Any],
    operation_info: dict[str, Any],
) -> dict[str, Any]:
    operation = operation_info["operation"]
    method = operation_info["method"]
    path = operation_info["path"]
    path_parameters = operation_info.get("path_parameters") or []
    is_swagger = operation_info.get("is_swagger", False)

    parameters = _resolve_parameters(document, path_parameters) + _resolve_parameters(
        document,
        operation.get("parameters", []),
    )

    headers = _parameters_to_pairs(document, parameters, "header")
    query_params = _parameters_to_pairs(document, parameters, "query")

    body = (
        _swagger_request_body(document, operation, parameters)
        if is_swagger
        else _openapi_request_body(document, operation)
    )

    content_type = body.pop("_content_type", "")
    if content_type and not _has_pair(headers, "Content-Type"):
        headers.append({
            "key": "Content-Type",
            "value": content_type,
            "description": "",
            "enabled": True,
        })

    return {
        "name": _operation_name(operation, method, path),
        "type": ApiInterface.TYPE_HTTP,
        "method": method,
        "url": path,
        "headers": headers,
        "params": query_params,
        "body": body,
        "setup_hooks": [],
        "teardown_hooks": [],
        "variables": {},
        "validators": _validators_from_responses(operation.get("responses", {})),
        "extract": {},
        "extract_meta": {},
        "file_ids": [],
        "_module_name": _module_name_from_operation(operation, path, document),
    }


def _resolve_parameters(document: dict[str, Any], parameters: Any) -> list[dict[str, Any]]:
    resolved = []
    if not isinstance(parameters, list):
        return resolved
    for parameter in parameters:
        item = _resolve_ref(document, parameter)
        if isinstance(item, dict):
            resolved.append(item)
    return resolved


def _parameters_to_pairs(document: dict[str, Any], parameters: list[dict[str, Any]], location: str) -> list[dict[str, Any]]:
    pairs = []
    seen = set()
    for parameter in parameters:
        if parameter.get("in") != location:
            continue
        name = parameter.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        pairs.append({
            "key": str(name),
            "value": stringify_pair_value(_sample_from_parameter(document, parameter)),
            "description": stringify_pair_value(parameter.get("description", "")),
            "enabled": True,
        })
    return pairs


def _openapi_request_body(document: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    request_body = _resolve_ref(document, operation.get("requestBody"))
    if not isinstance(request_body, dict):
        return {"type": "none", "content": None}

    content = request_body.get("content")
    if not isinstance(content, dict) or not content:
        return {"type": "none", "content": None}

    selected_type, media = _select_media_type(content)
    if not isinstance(media, dict):
        return {"type": "none", "content": None}

    schema = _resolve_ref(document, media.get("schema"))
    example = _sample_from_media(document, media, schema)

    if selected_type == "application/json" or selected_type.endswith("+json"):
        return {"type": "raw", "content": example, "_content_type": selected_type}

    if selected_type == "multipart/form-data":
        return {
            "type": "form-data",
            "content": _schema_to_form_pairs(document, schema),
            "_content_type": selected_type,
        }

    if selected_type == "application/x-www-form-urlencoded":
        return {
            "type": "x-www-form-urlencoded",
            "content": _schema_to_form_pairs(document, schema),
            "_content_type": selected_type,
        }

    return {"type": "raw", "content": example, "_content_type": selected_type}


def _swagger_request_body(
    document: dict[str, Any],
    operation: dict[str, Any],
    parameters: list[dict[str, Any]],
) -> dict[str, Any]:
    consumes = operation.get("consumes") or document.get("consumes") or []
    content_type = consumes[0] if isinstance(consumes, list) and consumes else "application/json"

    body_parameter = next((p for p in parameters if p.get("in") == "body"), None)
    if body_parameter:
        schema = _resolve_ref(document, body_parameter.get("schema"))
        return {
            "type": "raw",
            "content": _sample_from_schema(document, schema),
            "_content_type": content_type,
        }

    form_parameters = [p for p in parameters if p.get("in") == "formData"]
    if form_parameters:
        form_type = "form-data" if "multipart/form-data" in consumes else "x-www-form-urlencoded"
        return {
            "type": form_type,
            "content": [
                {
                    "key": str(parameter.get("name", "")),
                    "value": stringify_pair_value(_sample_from_parameter(document, parameter)),
                    "description": stringify_pair_value(parameter.get("description", "")),
                    "enabled": True,
                    "value_type": "file" if str(parameter.get("type") or "").lower() == "file" else "text",
                }
                for parameter in form_parameters
                if parameter.get("name")
            ],
            "_content_type": "multipart/form-data" if form_type == "form-data" else "application/x-www-form-urlencoded",
        }

    return {"type": "none", "content": None}


def _select_media_type(content: dict[str, Any]) -> tuple[str, Any]:
    for preferred in (
        "application/json",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
        "text/plain",
    ):
        if preferred in content:
            return preferred, content[preferred]

    for media_type, media in content.items():
        if str(media_type).endswith("+json"):
            return str(media_type), media

    media_type, media = next(iter(content.items()))
    return str(media_type), media


def _sample_from_parameter(document: dict[str, Any], parameter: dict[str, Any]) -> Any:
    if "example" in parameter:
        return parameter.get("example")
    if isinstance(parameter.get("examples"), dict) and parameter["examples"]:
        first = next(iter(parameter["examples"].values()))
        if isinstance(first, dict) and "value" in first:
            return first["value"]
    if "default" in parameter:
        return parameter.get("default")
    return _sample_from_schema(document, parameter.get("schema", parameter))


def _sample_from_media(document: dict[str, Any], media: dict[str, Any], schema: Any) -> Any:
    if "example" in media:
        return media.get("example")
    if isinstance(media.get("examples"), dict) and media["examples"]:
        first = next(iter(media["examples"].values()))
        if isinstance(first, dict) and "value" in first:
            return first["value"]
    return _sample_from_schema(document, schema)


def _sample_from_schema(document: dict[str, Any], schema: Any, seen_refs: set[str] | None = None) -> Any:
    seen = set(seen_refs or set())
    if isinstance(schema, dict) and isinstance(schema.get("$ref"), str) and schema["$ref"].startswith("#/"):
        ref = schema["$ref"]
        if ref in seen:
            # 循环引用（如树形/父子结构 schema 引用自身）：截断展开，避免无限递归。
            return {}
        schema = _resolve_ref(document, schema)
        seen.add(ref)
    else:
        schema = _resolve_ref(document, schema, seen_refs=seen)

    if not isinstance(schema, dict):
        return ""

    if "example" in schema:
        return schema.get("example")
    if "default" in schema:
        return schema.get("default")
    if isinstance(schema.get("enum"), list) and schema["enum"]:
        return schema["enum"][0]

    schema_type = schema.get("type")
    if not schema_type and "properties" in schema:
        schema_type = "object"
    if isinstance(schema_type, list):
        schema_type = next((item for item in schema_type if item != "null"), schema_type[0])

    if schema_type == "object":
        properties = schema.get("properties") or {}
        if not isinstance(properties, dict):
            return {}
        return {
            key: _sample_from_schema(document, value, seen_refs=seen)
            for key, value in properties.items()
        }

    if schema_type == "array":
        return [_sample_from_schema(document, schema.get("items", {}), seen_refs=seen)]

    if schema_type in {"integer", "number"}:
        return 0
    if schema_type == "boolean":
        return False
    if schema.get("format") == "binary":
        return ""

    return ""


def _schema_to_form_pairs(document: dict[str, Any], schema: Any) -> list[dict[str, Any]]:
    schema = _resolve_ref(document, schema)
    if not isinstance(schema, dict):
        return []

    properties = schema.get("properties")
    if not isinstance(properties, dict):
        sample = _sample_from_schema(document, schema)
        if isinstance(sample, dict):
            properties = {key: {"example": value} for key, value in sample.items()}
        else:
            return []

    pairs = []
    for key, value in properties.items():
        item = _resolve_ref(document, value)
        value_type = "file" if isinstance(item, dict) and item.get("format") == "binary" else "text"
        pairs.append({
            "key": str(key),
            "value": stringify_pair_value(_sample_from_schema(document, item)),
            "description": stringify_pair_value(item.get("description", "")) if isinstance(item, dict) else "",
            "enabled": True,
            "value_type": value_type,
        })
    return pairs


def _validators_from_responses(responses: Any) -> list[dict[str, Any]]:
    if not isinstance(responses, dict):
        return [{"eq": ["status_code", 200]}]

    numeric_codes = []
    for code in responses.keys():
        try:
            numeric_codes.append(int(str(code)))
        except ValueError:
            continue

    preferred = [code for code in numeric_codes if 200 <= code < 300]
    expected = min(preferred or numeric_codes or [200])
    return [{"eq": ["status_code", expected]}]


def _operation_name(operation: dict[str, Any], method: str, path: str) -> str:
    raw_name = operation.get("summary") or operation.get("operationId") or f"{method} {path}"
    name = re.sub(r"\s+", " ", str(raw_name)).strip()
    return name[:100] or f"{method} {path}"[:100]


def _module_name_from_operation(operation: dict[str, Any], path: str, document: dict[str, Any] | None = None) -> str:
    tags = operation.get("tags")
    if isinstance(tags, list):
        for tag in tags:
            if tag not in (None, ""):
                return str(tag).strip()[:100]

    # 无显式 tags 时取文档 title 作为模块名
    if isinstance(document, dict):
        info = document.get("info")
        if isinstance(info, dict) and info.get("title"):
            return str(info["title"]).strip()[:100]

    # 兜底：从路径第一段提取；完整 URL（保留域名模式）需先提取 path 部分，
    # 避免把 "http:" 之类的 origin 片段当成模块名
    parsed = urlparse(str(path))
    if parsed.scheme or parsed.netloc:
        path = parsed.path or "/"

    parts = [part for part in path.split("/") if part and not part.startswith("{")]
    return parts[0][:100] if parts else ""


def _normalize_module_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip()[:100]


def _existing_module_cache(project: Project) -> dict[str, ApiModule]:
    """预取项目下全部顶层模块,避免导入循环内逐条查询。"""
    cache: dict[str, ApiModule] = {}
    for module in ApiModule.objects.filter(project=project, parent__isnull=True).order_by("id"):
        cache.setdefault(_normalize_module_name(module.name), module)
    return cache


def _existing_interface_index(project: Project) -> tuple[dict[tuple[str, str], ApiInterface], set[str]]:
    """预取项目下的接口数据,返回 (HTTP 接口 method+url 索引, 项目全部接口的已用名称集合)。"""
    index: dict[tuple[str, str], ApiInterface] = {}
    used_names: set[str] = set()

    for interface in (
        ApiInterface.objects.filter(project=project)
        .only("id", "type", "method", "url", "name")
        .iterator(chunk_size=1000)
    ):
        used_names.add(interface.name)
        if interface.type == ApiInterface.TYPE_HTTP:
            index.setdefault((interface.method.upper(), interface.url), interface)

    return index, used_names


def _get_or_create_module(
    *,
    project: Project,
    user,
    name: str,
    cache: dict[str, ApiModule],
) -> ApiModule:
    normalized_name = _normalize_module_name(name)
    if normalized_name in cache:
        return cache[normalized_name]

    module = ApiModule.objects.filter(
        project=project,
        parent__isnull=True,
        name=normalized_name,
    ).order_by("id").first()

    if module is None:
        module = ApiModule.objects.create(
            project=project,
            created_by=user,
            name=normalized_name,
        )

    cache[normalized_name] = module
    return module


def _unique_interface_name(
    *,
    name: str,
    used_names: set[str],
    exclude_name: str | None = None,
) -> str:
    base = re.sub(r"\s+", " ", name).strip() or "Imported API"
    base = base[:100]

    def available(candidate: str) -> bool:
        return candidate not in used_names or candidate == exclude_name

    if available(base):
        return base

    suffix = 2
    while True:
        suffix_text = f" {suffix}"
        candidate = f"{base[:100 - len(suffix_text)]}{suffix_text}"
        if available(candidate):
            return candidate
        suffix += 1


def _resolve_ref(
    document: dict[str, Any],
    value: Any,
    seen_refs: set[str] | None = None,
) -> Any:
    if not isinstance(value, dict) or "$ref" not in value:
        return value

    ref = value.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return value

    seen = set(seen_refs or set())
    if ref in seen:
        return {}
    seen.add(ref)

    current: Any = document
    for part in ref[2:].split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or key not in current:
            return value
        current = current[key]

    resolved = deepcopy(current)
    if isinstance(resolved, dict):
        return _resolve_ref(document, resolved, seen_refs=seen)
    return resolved


def _openapi_server_path(document: dict[str, Any]) -> str:
    servers = document.get("servers")
    if not isinstance(servers, list) or not servers:
        return ""

    first = servers[0]
    if not isinstance(first, dict):
        return ""

    url = first.get("url")
    if not isinstance(url, str) or not url:
        return ""

    parsed = urlparse(url)
    if parsed.scheme or parsed.netloc:
        return parsed.path or ""
    return url if url.startswith("/") else ""


def _swagger_base_path(document: dict[str, Any]) -> str:
    base_path = document.get("basePath")
    if isinstance(base_path, str):
        return base_path
    return ""


def _openapi_server_full_prefix(document: dict[str, Any]) -> str:
    """保留 origin 的 OpenAPI3 server 前缀：scheme://netloc + path。"""
    servers = document.get("servers")
    if not isinstance(servers, list) or not servers:
        return ""

    first = servers[0]
    if not isinstance(first, dict):
        return ""

    url = first.get("url")
    if not isinstance(url, str) or not url:
        return ""

    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        path_part = parsed.path or ""
        return f"{parsed.scheme}://{parsed.netloc}{path_part}"
    return url if url.startswith("/") else ""


def _swagger_full_prefix(document: dict[str, Any]) -> str:
    """保留 origin 的 Swagger2 前缀：scheme://host + basePath。"""
    host = document.get("host")
    if not isinstance(host, str) or not host:
        return _swagger_base_path(document)

    schemes = document.get("schemes")
    scheme = ""
    if isinstance(schemes, list) and schemes:
        scheme = str(schemes[0])
    if scheme not in {"http", "https"}:
        scheme = "http"

    base_path = document.get("basePath")
    path_part = base_path if isinstance(base_path, str) else ""
    return f"{scheme}://{host}{path_part}"


def extract_document_base_urls(document: dict[str, Any]) -> list[str]:
    """收集导入文档中出现的去重域名前缀（scheme://netloc）。

    覆盖 OpenAPI3 servers、Swagger2 host+schemes，以及被各转换器折叠进
    paths 中的完整 URL（Postman/HAR/Insomnia/cURL 等）。
    """
    origins: list[str] = []

    def add_origin(url: Any) -> None:
        parsed = urlparse(str(url or "").strip())
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            origin = f"{parsed.scheme}://{parsed.netloc}"
            if origin not in origins:
                origins.append(origin)

    # OpenAPI3 servers
    servers = document.get("servers")
    if isinstance(servers, list):
        for server in servers:
            if isinstance(server, dict):
                add_origin(server.get("url"))

    # Swagger2 host + schemes
    host = document.get("host")
    if isinstance(host, str) and host:
        schemes = document.get("schemes")
        if isinstance(schemes, list) and schemes:
            for scheme in schemes:
                add_origin(f"{scheme}://{host}")
        else:
            add_origin(f"http://{host}")

    # paths 中含 scheme/netloc 的完整 URL（转换器折叠进来的）
    paths = document.get("paths")
    if isinstance(paths, dict):
        for raw_path in paths.keys():
            add_origin(raw_path)

    return origins


_ENV_NAME_PATTERN = re.compile(r"^环境(\d+)（导入）$")


def _next_environment_name(project: Project) -> str:
    """生成下一个不冲突的「环境N（导入）」名称，接续已有最大编号。"""
    existing_names = set(
        ApiEnvironment.objects.filter(project=project).values_list("name", flat=True)
    )
    max_index = 0
    for name in existing_names:
        match = _ENV_NAME_PATTERN.match(str(name))
        if match:
            max_index = max(max_index, int(match.group(1)))
    return f"环境{max_index + 1}（导入）"


def _create_environments_from_document(
    *,
    document: dict[str, Any],
    project: Project,
    user,
) -> list[dict[str, Any]]:
    """根据导入文档中的域名前缀创建环境，按 base_url 去重，跳过已存在。"""
    origins = extract_document_base_urls(document)
    if not origins:
        return []

    created: list[dict[str, Any]] = []
    for origin in origins:
        # 按域名去重：项目内已有相同 base_url 的环境则跳过
        if ApiEnvironment.objects.filter(project=project, base_url=origin).exists():
            continue

        parsed = urlparse(origin)
        environment = ApiEnvironment.objects.create(
            project=project,
            created_by=user,
            name=_next_environment_name(project),
            base_url=origin,
            verify_ssl=(parsed.scheme == "https"),
            is_active=True,
        )
        created.append({
            "id": environment.id,
            "name": environment.name,
            "base_url": environment.base_url,
        })
    return created


def _join_url_path(prefix: str, path: str) -> str:
    clean_prefix = (prefix or "").strip()
    clean_path = (path or "").strip() or "/"
    if not clean_prefix or clean_prefix == "/":
        return clean_path if clean_path.startswith("/") else f"/{clean_path}"

    joined = posixpath.join(f"/{clean_prefix.strip('/')}", clean_path.lstrip("/"))
    return joined if joined.startswith("/") else f"/{joined}"


def _is_url_prefix(value: str) -> bool:
    """判断前缀是否为含 scheme://netloc 的完整 URL。"""
    parsed = urlparse(value or "")
    return bool(parsed.scheme in {"http", "https"} and parsed.netloc)


def _join_full_url_path(prefix: str, path: str) -> str:
    """将完整 URL 前缀与路径拼接：https://host/v1 + /orders -> https://host/v1/orders。"""
    clean_prefix = (prefix or "").rstrip("/")
    clean_path = (path or "").strip() or "/"
    if not clean_path.startswith("/"):
        clean_path = f"/{clean_path}"
    return f"{clean_prefix}{clean_path}"


def _has_pair(pairs: list[dict[str, Any]], key: str) -> bool:
    return any(str(item.get("key", "")).lower() == key.lower() for item in pairs)


def _normalize_export_path(url: str) -> str:
    value = url.strip() or "/"
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        value = parsed.path or "/"
        if parsed.query:
            value = f"{value}?{parsed.query}"
    if not value.startswith("/"):
        value = f"/{value}"
    return value


def _enabled_pairs(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    pairs = []
    for item in value:
        if isinstance(item, dict) and item.get("enabled", True) and item.get("key"):
            pairs.append(item)
    return pairs


def _build_parameters(interface: ApiInterface) -> list[dict[str, Any]]:
    parameters = []
    for item in _enabled_pairs(interface.params):
        parameters.append({
            "name": str(item.get("key")),
            "in": "query",
            "required": False,
            "description": item.get("description", ""),
            "schema": _schema_from_value(item.get("value", "")),
            "example": item.get("value", ""),
        })

    for item in _enabled_pairs(interface.headers):
        key = str(item.get("key"))
        if key.lower() == "content-type":
            continue
        parameters.append({
            "name": key,
            "in": "header",
            "required": False,
            "description": item.get("description", ""),
            "schema": _schema_from_value(item.get("value", "")),
            "example": item.get("value", ""),
        })

    return parameters


def _build_request_body(interface: ApiInterface) -> dict[str, Any] | None:
    body = interface.body if isinstance(interface.body, dict) else {}
    body_type = body.get("type", "none")
    content = body.get("content")

    if body_type == "none":
        return None

    if body_type == "form-data":
        return {
            "required": False,
            "content": {
                "multipart/form-data": _content_from_form_pairs(content),
            },
        }

    if body_type == "x-www-form-urlencoded":
        return {
            "required": False,
            "content": {
                "application/x-www-form-urlencoded": _content_from_form_pairs(content),
            },
        }

    if body_type == "binary":
        return {
            "required": False,
            "content": {
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"},
                },
            },
        }

    media_type = _content_type_from_headers(interface.headers) or _media_type_for_raw_content(content)
    return {
        "required": False,
        "content": {
            media_type: {
                "schema": _schema_from_value(content),
                "example": content,
            },
        },
    }


def _content_from_form_pairs(content: Any) -> dict[str, Any]:
    properties = {}
    example = {}
    for item in _enabled_pairs(content):
        key = str(item.get("key"))
        value = item.get("value", "")
        if item.get("value_type") == "file":
            properties[key] = {"type": "string", "format": "binary"}
        else:
            properties[key] = _schema_from_value(value)
            example[key] = value

    payload = {"schema": {"type": "object", "properties": properties}}
    if example:
        payload["example"] = example
    return payload


def _build_responses(interface: ApiInterface) -> dict[str, Any]:
    status_code = 200
    validators = interface.validators if isinstance(interface.validators, list) else []
    for validator in validators:
        if not isinstance(validator, dict):
            continue
        expected = None
        if "eq" in validator and isinstance(validator["eq"], list) and len(validator["eq"]) == 2:
            check, expected = validator["eq"]
            if check != "status_code":
                continue
        elif validator.get("check") == "status_code" and "expect" in validator:
            expected = validator.get("expect")
        try:
            status_code = int(expected)
            break
        except (TypeError, ValueError):
            continue

    return {str(status_code): {"description": "Successful response"}}


def _schema_from_value(value: Any) -> dict[str, Any]:
    parsed = value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                parsed = value

    if isinstance(parsed, dict):
        return {
            "type": "object",
            "properties": {
                str(key): _schema_from_value(item)
                for key, item in parsed.items()
            },
        }
    if isinstance(parsed, list):
        first = parsed[0] if parsed else ""
        return {"type": "array", "items": _schema_from_value(first)}
    if isinstance(parsed, bool):
        return {"type": "boolean"}
    if isinstance(parsed, int):
        return {"type": "integer"}
    if isinstance(parsed, float):
        return {"type": "number"}
    return {"type": "string"}


def _content_type_from_headers(headers: Any) -> str:
    for item in _enabled_pairs(headers):
        if str(item.get("key", "")).lower() == "content-type" and item.get("value"):
            return str(item.get("value"))
    return ""


def _media_type_for_raw_content(content: Any) -> str:
    if isinstance(content, (dict, list)):
        return "application/json"
    if isinstance(content, str):
        stripped = content.strip()
        if stripped:
            try:
                json.loads(stripped)
                return "application/json"
            except json.JSONDecodeError:
                return "text/plain"
    return "application/json"
