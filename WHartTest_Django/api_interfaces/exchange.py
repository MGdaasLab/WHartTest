from __future__ import annotations

import json
import re
import shlex
import time
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlparse
from urllib.request import Request, urlopen

try:
    import yaml
except ImportError:  # pragma: no cover - dependency is declared in requirements
    yaml = None

from .openapi import (
    OpenAPIError,
    _resolve_ref,
    _sample_from_media,
    _sample_from_schema,
    _schema_from_value,
    _select_media_type,
    dump_openapi_document,
    parse_openapi_document,
)


HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}
EXPORT_FORMATS = {"json", "yaml", "yml", "apifox", "apipost", "yapi"}
IMPORT_FORMATS = {
    "swagger",
    "openapi",
    "postman",
    "curl",
    "markdown",
    "har",
    "insomnia",
    "apidoc",
    "apifox",
    "apipost",
    "yapi",
    "apizza",
    "eolink",
}
MAX_REMOTE_DOCUMENT_BYTES = 10 * 1024 * 1024
REMOTE_FETCH_CONNECT_TIMEOUT_SECONDS = 10.0
REMOTE_FETCH_READ_TIMEOUT_SECONDS = 60.0
_CHUNK_SIZE = 64 * 1024


@dataclass(frozen=True)
class ParsedApiDocument:
    document: dict[str, Any]
    source_format: str
    source_version: str


def parse_api_document(
    content: bytes | str | dict[str, Any] | list[Any],
    filename: str = "",
    source_type: str = "",
    *,
    strip_base_url: bool = True,
) -> ParsedApiDocument:
    keep_full_url = not strip_base_url
    normalized_type = _normalize_source_type(source_type)
    text_content = _text_content(content)
    if normalized_type == "curl" or (
        not normalized_type and text_content.lstrip().lower().startswith("curl ")
    ):
        document = parse_openapi_document(_curl_to_openapi(text_content, keep_full_url=keep_full_url))
        return ParsedApiDocument(document=document, source_format="curl", source_version="command")
    if normalized_type == "markdown" or filename.lower().endswith((".md", ".markdown")):
        document = parse_openapi_document(_markdown_to_openapi(text_content, keep_full_url=keep_full_url))
        return ParsedApiDocument(document=document, source_format="markdown", source_version="text")

    raw_document = _load_document(content, filename)

    if isinstance(raw_document, dict) and (
        raw_document.get("openapi") or raw_document.get("swagger") == "2.0"
    ):
        document = parse_openapi_document(raw_document)
        is_swagger = document.get("swagger") == "2.0"
        return ParsedApiDocument(
            document=document,
            source_format="swagger" if is_swagger else "openapi",
            source_version=str(document.get("swagger") or document.get("openapi") or ""),
        )

    if isinstance(raw_document, dict) and raw_document.get("apifoxProject"):
        document = parse_openapi_document(_apifox_to_openapi(raw_document, keep_full_url=keep_full_url))
        return ParsedApiDocument(
            document=document,
            source_format="apifox",
            source_version=str(raw_document.get("apifoxProject") or "1.0.0"),
        )

    if normalized_type == "postman" or _looks_like_postman(raw_document):
        document = parse_openapi_document(_postman_to_openapi(_require_dict(raw_document, "Postman"), keep_full_url=keep_full_url))
        postman_info = raw_document.get("info") if isinstance(raw_document.get("info"), dict) else {}
        schema = postman_info.get("schema", "")
        return ParsedApiDocument(document=document, source_format="postman", source_version=str(schema or "2.x"))

    if normalized_type == "har" or _looks_like_har(raw_document):
        document = parse_openapi_document(_har_to_openapi(_require_dict(raw_document, "HAR"), keep_full_url=keep_full_url))
        return ParsedApiDocument(document=document, source_format="har", source_version="1.2")

    if normalized_type == "insomnia" or _looks_like_insomnia(raw_document):
        source = _require_dict(raw_document, "Insomnia")
        document = parse_openapi_document(_insomnia_to_openapi(source, keep_full_url=keep_full_url))
        return ParsedApiDocument(
            document=document,
            source_format="insomnia",
            source_version=str(source.get("__export_format") or "4"),
        )

    if normalized_type == "apidoc" or _looks_like_apidoc(raw_document):
        document = parse_openapi_document(_apidoc_to_openapi(raw_document, keep_full_url=keep_full_url))
        return ParsedApiDocument(document=document, source_format="apidoc", source_version="0.29")

    if _looks_like_apipost(raw_document):
        document = parse_openapi_document(_apipost_to_openapi(raw_document, keep_full_url=keep_full_url))
        return ParsedApiDocument(
            document=document,
            source_format="apipost",
            source_version=str(raw_document.get("version") or "json"),
        )

    if _looks_like_yapi(raw_document):
        document = parse_openapi_document(_yapi_to_openapi(raw_document, keep_full_url=keep_full_url))
        return ParsedApiDocument(
            document=document,
            source_format="yapi",
            source_version="json",
        )

    if normalized_type == "eolink" or _looks_like_eolink(raw_document):
        document = parse_openapi_document(_eolink_to_openapi(raw_document, keep_full_url=keep_full_url))
        return ParsedApiDocument(document=document, source_format="eolink", source_version="json")

    if normalized_type == "apizza" or _looks_like_apizza(raw_document):
        document = parse_openapi_document(_apizza_to_openapi(raw_document, keep_full_url=keep_full_url))
        return ParsedApiDocument(document=document, source_format="apizza", source_version="json")

    raise OpenAPIError(
        "Unsupported API document. Select the matching import type and verify the exported file."
    )


def fetch_api_document(source_url: str) -> tuple[bytes, str]:
    """Fetch a remote Swagger/OpenAPI document with bounded time and memory use.

    The whole download (connect + read) is capped by an overall deadline so a slow
    remote server cannot hold the request open indefinitely. The document is read in
    chunks and capped by ``MAX_REMOTE_DOCUMENT_BYTES``.
    """
    parsed = urlparse(str(source_url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise OpenAPIError("Swagger URL must be a valid HTTP or HTTPS URL.")

    request = Request(
        parsed.geturl(),
        headers={"Accept": "application/json, application/yaml, text/yaml, */*"},
    )
    deadline = time.monotonic() + REMOTE_FETCH_READ_TIMEOUT_SECONDS
    try:
        with urlopen(
            request,
            timeout=REMOTE_FETCH_CONNECT_TIMEOUT_SECONDS,
        ) as response:
            declared_size = response.headers.get("Content-Length")
            if declared_size:
                try:
                    declared_size = int(declared_size)
                except ValueError:
                    declared_size = None
                if declared_size is not None and declared_size > MAX_REMOTE_DOCUMENT_BYTES:
                    raise OpenAPIError(
                        f"The remote API document is too large "
                        f"({declared_size} bytes, limit {MAX_REMOTE_DOCUMENT_BYTES} bytes). "
                        "Download the document and import it as a file instead."
                    )

            chunks: list[bytes] = []
            total = 0
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise OpenAPIError(
                        f"Fetching the Swagger URL timed out after "
                        f"{int(REMOTE_FETCH_READ_TIMEOUT_SECONDS)} seconds. "
                        "The remote server may be generating a large document on demand. "
                        "Try importing a downloaded copy of the document as a file instead."
                    )
                chunk = response.read(_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_REMOTE_DOCUMENT_BYTES:
                    raise OpenAPIError(
                        f"The remote API document is too large "
                        f"(exceeds {MAX_REMOTE_DOCUMENT_BYTES} bytes). "
                        "Download the document and import it as a file instead."
                    )
                chunks.append(chunk)

            content = b"".join(chunks)
            final_url = response.geturl()
    except OpenAPIError:
        raise
    except TimeoutError as exc:
        raise OpenAPIError(
            f"Fetching the Swagger URL timed out after "
            f"{int(REMOTE_FETCH_READ_TIMEOUT_SECONDS)} seconds. "
            "The remote server may be slow or unresponsive. "
            "Try importing a downloaded copy of the document as a file instead."
        ) from exc
    except (HTTPError, URLError, OSError, ValueError) as exc:
        raise OpenAPIError(f"Unable to fetch Swagger URL: {exc}") from exc

    if len(content) > MAX_REMOTE_DOCUMENT_BYTES:
        raise OpenAPIError(
            f"The remote API document is too large "
            f"({len(content)} bytes, limit {MAX_REMOTE_DOCUMENT_BYTES} bytes). "
            "Download the document and import it as a file instead."
        )
    filename = urlparse(final_url).path.rsplit("/", 1)[-1] or "openapi.json"
    return content, filename


def _normalize_source_type(value: str) -> str:
    normalized = str(value or "").strip().lower().replace("_", "-")
    aliases = {
        "swagger-file": "swagger",
        "swagger-url": "swagger",
        "openapi-file": "openapi",
        "api-doc": "apidoc",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in IMPORT_FORMATS else ""


def _text_content(content: Any) -> str:
    if isinstance(content, bytes):
        try:
            return content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise OpenAPIError("The uploaded document must use UTF-8 encoding.") from exc
    return content if isinstance(content, str) else ""


def _require_dict(document: Any, label: str) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise OpenAPIError(f"Invalid {label} document structure.")
    return document


def dump_api_document(
    document: dict[str, Any],
    export_format: str,
    *,
    project_name: str = "",
) -> tuple[str, str, str, str]:
    normalized_format = (export_format or "json").lower()
    if normalized_format not in EXPORT_FORMATS:
        raise OpenAPIError(f"Unsupported export format: {export_format}")

    if normalized_format in {"json", "yaml", "yml"}:
        body, content_type, extension = dump_openapi_document(document, normalized_format)
        return body, content_type, extension, "openapi"

    builders = {
        "apifox": _openapi_to_apifox,
        "apipost": _openapi_to_apipost,
        "yapi": _openapi_to_yapi,
    }
    exported = builders[normalized_format](document, project_name=project_name)
    return (
        json.dumps(exported, ensure_ascii=False, indent=2),
        "application/json; charset=utf-8",
        "json",
        normalized_format,
    )


def _load_document(
    content: bytes | str | dict[str, Any] | list[Any],
    filename: str,
) -> dict[str, Any] | list[Any]:
    if isinstance(content, (dict, list)):
        return deepcopy(content)

    try:
        text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
    except UnicodeDecodeError as exc:
        raise OpenAPIError("The uploaded document must use UTF-8 encoding.") from exc
    stripped = text.strip()
    if not stripped:
        raise OpenAPIError("The uploaded document is empty.")

    if filename.lower().endswith(".js"):
        wrapper_match = re.match(
            r"^(?:define\s*\(|(?:window\.)?[A-Za-z_$][\w$]*\s*=)\s*([\[{].*[\]}])\s*\)?\s*;?\s*$",
            stripped,
            flags=re.DOTALL,
        )
        if wrapper_match:
            stripped = wrapper_match.group(1)

    lower_name = filename.lower()
    parse_as_json = lower_name.endswith(".json") or stripped.startswith(("{", "["))
    try:
        if parse_as_json:
            return json.loads(stripped)
        if yaml is None:
            raise OpenAPIError("PyYAML is required to import YAML OpenAPI documents.")
        return yaml.safe_load(stripped)
    except json.JSONDecodeError as exc:
        raise OpenAPIError(f"Invalid JSON document: {exc}") from exc
    except Exception as exc:
        if isinstance(exc, OpenAPIError):
            raise
        raise OpenAPIError(f"Invalid YAML document: {exc}") from exc


def _looks_like_postman(document: Any) -> bool:
    if not isinstance(document, dict) or not isinstance(document.get("item"), list):
        return False
    info = document.get("info") if isinstance(document.get("info"), dict) else {}
    return "postman" in str(info.get("schema") or "").lower() or "_postman_id" in info


def _looks_like_har(document: Any) -> bool:
    if not isinstance(document, dict) or not isinstance(document.get("log"), dict):
        return False
    return isinstance(document["log"].get("entries"), list)


def _looks_like_insomnia(document: Any) -> bool:
    if not isinstance(document, dict) or not isinstance(document.get("resources"), list):
        return False
    return any(
        isinstance(item, dict) and item.get("_type") in {"workspace", "request", "request_group"}
        for item in document["resources"]
    )


def _apidoc_items(document: Any) -> list[dict[str, Any]]:
    if isinstance(document, list):
        return [item for item in document if isinstance(item, dict)]
    if not isinstance(document, dict):
        return []
    for key in ("api", "apis", "api_data", "data"):
        value = document.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _looks_like_apidoc(document: Any) -> bool:
    items = _apidoc_items(document)
    return bool(items) and any(
        item.get("group") and item.get("type") and item.get("url")
        for item in items
    )


def _looks_like_apipost(document: Any) -> bool:
    if not isinstance(document, dict) or not isinstance(document.get("apis"), list):
        return False
    if document.get("apifoxProject"):
        return False
    return any(
        isinstance(item, dict)
        and (item.get("target_type") in {"api", "folder"} or "request" in item)
        for item in document["apis"]
    )


def _looks_like_yapi(document: Any) -> bool:
    if not isinstance(document, list):
        return False
    if not document:
        return True
    return all(isinstance(item, dict) for item in document) and any(
        isinstance(item.get("list"), list) for item in document
    )


def _looks_like_eolink(document: Any) -> bool:
    if not isinstance(document, (dict, list)):
        return False
    serialized_keys = set(document.keys()) if isinstance(document, dict) else set()
    if serialized_keys & {"apiGroupList", "api_group_list", "projectInfo"}:
        return True
    return any(
        key in serialized_keys
        for key in ("eolink", "eolinker", "groupList")
    )


def _looks_like_apizza(document: Any) -> bool:
    def contains_apizza_api(value: Any) -> bool:
        if isinstance(value, list):
            return any(contains_apizza_api(item) for item in value)
        if not isinstance(value, dict):
            return False
        if value.get("method") and value.get("url") and any(
            key in value for key in ("body_type", "body_raw", "query_params", "header_params")
        ):
            return True
        return any(
            contains_apizza_api(value.get(key))
            for key in ("data", "api_list", "apis", "folders", "list")
        )

    return contains_apizza_api(document)


def _new_openapi(title: str, description: str = "") -> dict[str, Any]:
    return {
        "openapi": "3.0.3",
        "info": {
            "title": title or "Imported API",
            "version": "1.0.0",
            "description": description or "",
        },
        "tags": [],
        "paths": {},
    }


def _add_operation(
    document: dict[str, Any],
    *,
    path: Any,
    method: Any,
    operation: dict[str, Any],
    keep_full_url: bool = False,
) -> None:
    normalized_method = str(method or "GET").upper()
    if normalized_method not in HTTP_METHODS:
        return
    normalized_path = _normalize_import_path(path, keep_full_url=keep_full_url)
    path_item = document["paths"].setdefault(normalized_path, {})
    path_item.setdefault(normalized_method.lower(), operation)

    for tag in operation.get("tags", []):
        if tag and not any(item.get("name") == tag for item in document["tags"]):
            document["tags"].append({"name": tag, "description": ""})


def _normalize_import_path(value: Any, *, keep_full_url: bool = False) -> str:
    raw_value = str(value or "/").strip() or "/"
    parsed = urlparse(raw_value)
    if parsed.scheme or parsed.netloc:
        if keep_full_url:
            # 保留完整 URL：scheme://netloc + path（去掉 query），不强制前导 /
            origin = f"{parsed.scheme}://{parsed.netloc}"
            path_part = parsed.path or "/"
            return f"{origin}{path_part}"
        raw_value = parsed.path or "/"
    else:
        raw_value = raw_value.split("?", 1)[0] or "/"
    if not raw_value.startswith("/"):
        raw_value = f"/{raw_value}"
    return raw_value


def _coerce_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return ""
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return value


def _json_object(value: Any) -> dict[str, Any]:
    parsed = _coerce_json(value)
    return parsed if isinstance(parsed, dict) else {}


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _external_value(item: dict[str, Any]) -> Any:
    for key in ("example", "value", "paramValue", "defaultValue", "default", "initialValue"):
        if key in item and item.get(key) is not None:
            return item.get(key)
    schema = item.get("schema")
    if isinstance(schema, dict):
        for key in ("example", "default"):
            if key in schema:
                return schema.get(key)
    return ""


def _external_schema(item: dict[str, Any], value: Any) -> dict[str, Any]:
    if isinstance(item.get("schema"), dict):
        schema = deepcopy(item["schema"])
    else:
        raw_type = str(item.get("type") or item.get("paramType") or item.get("field_type") or "string").lower()
        type_map = {
            "string": "string",
            "file": "string",
            "integer": "integer",
            "int": "integer",
            "number": "number",
            "float": "number",
            "boolean": "boolean",
            "bool": "boolean",
            "array": "array",
            "object": "object",
        }
        schema = {"type": type_map.get(raw_type, "string")}
        if raw_type == "file":
            schema["format"] = "binary"

    if value not in (None, "") and "example" not in schema:
        schema["example"] = value
    return schema


def _external_parameters(items: Any, location: str) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    parameters = []
    for item in items:
        if not isinstance(item, dict):
            continue
        enabled = item.get("enable", item.get("defaultEnable", item.get("is_checked", 1)))
        if enabled in (False, -1, "-1", 0, "0"):
            continue
        name = item.get("name", item.get("key", item.get("paramKey", item.get("field", item.get("relatedName")))))
        if not name:
            continue
        value = _external_value(item)
        required = item.get("required", item.get("require", item.get("paramNotNull", item.get("not_null", False))))
        parameters.append({
            "name": str(name),
            "in": location,
            "required": location == "path" or required in (True, 1, "1"),
            "description": str(item.get("description", item.get("desc", item.get("paramName", ""))) or ""),
            "schema": _external_schema(item, value),
            "example": value,
        })
    return parameters


def _form_media(items: Any) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []
    example: dict[str, Any] = {}
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            enabled = item.get("enable", item.get("defaultEnable", item.get("is_checked", 1)))
            if enabled in (False, -1, "-1", 0, "0"):
                continue
            name = item.get("name", item.get("key", item.get("paramKey", item.get("field"))))
            if not name:
                continue
            value = _external_value(item)
            properties[str(name)] = _external_schema(item, value)
            if item.get("required", item.get("require", item.get("paramNotNull", item.get("not_null")))) in (True, 1, "1"):
                required.append(str(name))
            if value not in (None, ""):
                example[str(name)] = value

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    media: dict[str, Any] = {"schema": schema}
    if example:
        media["example"] = example
    return media


def _response_content_type(value: Any) -> str:
    normalized = str(value or "json").lower()
    return {
        "json": "application/json",
        "xml": "application/xml",
        "html": "text/html",
        "text": "text/plain",
        "raw": "text/plain",
        "binary": "application/octet-stream",
    }.get(normalized, normalized if "/" in normalized else "application/json")


def _apifox_to_openapi(source: dict[str, Any], *, keep_full_url: bool = False) -> dict[str, Any]:
    info = source.get("info") if isinstance(source.get("info"), dict) else {}
    document = _new_openapi(str(info.get("name") or "Apifox Project"), str(info.get("description") or ""))

    def visit(items: Any, module_name: str = "") -> None:
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("items"), list) and not isinstance(item.get("api"), dict):
                visit(item["items"], str(item.get("name") or module_name))
                continue

            api = item.get("api") or item.get("customHttpRequest")
            if not isinstance(api, dict):
                continue
            parameters = api.get("parameters") if isinstance(api.get("parameters"), dict) else {}
            operation_parameters = []
            for location in ("header", "query", "path", "cookie"):
                operation_parameters.extend(_external_parameters(parameters.get(location), location))

            operation: dict[str, Any] = {
                "summary": str(item.get("name") or api.get("name") or "Imported API"),
                "description": str(api.get("description") or ""),
                "tags": [module_name] if module_name else [],
                "parameters": operation_parameters,
                "responses": _apifox_responses(api),
            }
            request_body = _apifox_request_body(api.get("requestBody"))
            if request_body:
                operation["requestBody"] = request_body
            _add_operation(document, path=api.get("path"), method=api.get("method"), operation=operation, keep_full_url=keep_full_url)

    collections = source.get("apiCollection")
    if isinstance(collections, list):
        for collection in collections:
            if isinstance(collection, dict):
                visit(collection.get("items"), "")
    return document


def _apifox_request_body(request_body: Any) -> dict[str, Any] | None:
    if not isinstance(request_body, dict):
        return None
    body_type = str(request_body.get("type") or "").lower()
    if body_type in {"", "none"}:
        return None
    if body_type == "multipart/form-data":
        return {"content": {body_type: _form_media(request_body.get("parameters"))}}
    if body_type == "application/x-www-form-urlencoded":
        return {"content": {body_type: _form_media(request_body.get("parameters"))}}

    media_type = {
        "json": "application/json",
        "xml": "application/xml",
        "text": "text/plain",
        "plain": "text/plain",
        "binary": "application/octet-stream",
    }.get(body_type, body_type if "/" in body_type else "application/json")
    raw_example = request_body.get("example", request_body.get("data", ""))
    if isinstance(request_body.get("examples"), list):
        matching = next(
            (
                item for item in request_body["examples"]
                if isinstance(item, dict) and item.get("mediaType") == media_type
            ),
            None,
        )
        if matching:
            raw_example = matching.get("value", raw_example)
    example = _coerce_json(raw_example)
    schema = _json_object(request_body.get("jsonSchema")) or _schema_from_value(example)
    return {"content": {media_type: {"schema": schema, "example": example}}}


def _apifox_responses(api: dict[str, Any]) -> dict[str, Any]:
    responses: dict[str, Any] = {}
    examples = api.get("responseExamples") if isinstance(api.get("responseExamples"), list) else []
    source_responses = api.get("responses") if isinstance(api.get("responses"), list) else []
    for index, item in enumerate(source_responses):
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or 200)
        response: dict[str, Any] = {"description": str(item.get("name") or item.get("description") or "Response")}
        media_type = _response_content_type(item.get("contentType"))
        schema = _json_object(item.get("jsonSchema"))
        matching = next(
            (
                example for example in examples
                if isinstance(example, dict) and str(example.get("responseId")) == str(item.get("id"))
            ),
            None,
        )
        raw_example = ""
        if matching:
            raw_example = matching.get("data", matching.get("content", matching.get("value", "")))
        example = _coerce_json(raw_example)
        if schema or example not in (None, ""):
            response["content"] = {
                media_type: {
                    "schema": schema or _schema_from_value(example),
                    "example": example,
                },
            }
        responses.setdefault(code, response)
    return responses or {"200": {"description": "Successful response"}}


def _apipost_to_openapi(source: dict[str, Any], *, keep_full_url: bool = False) -> dict[str, Any]:
    project = source.get("project") if isinstance(source.get("project"), dict) else {}
    title = source.get("name") or project.get("name") or "Apipost Project"
    description = source.get("intro") or project.get("description") or ""
    document = _new_openapi(str(title), str(description))

    for item, module_name in _iter_apipost_apis(source.get("apis")):
        request = item.get("request") if isinstance(item.get("request"), dict) else {}
        operation_parameters = []
        for location, source_key in (
            ("header", "header"),
            ("query", "query"),
            ("path", "restful"),
            ("cookie", "cookie"),
        ):
            container = request.get(source_key) if isinstance(request.get(source_key), dict) else {}
            operation_parameters.extend(_external_parameters(container.get("parameter"), location))

        operation: dict[str, Any] = {
            "summary": str(item.get("name") or "Imported API"),
            "description": str(item.get("description") or ""),
            "tags": [module_name] if module_name else [],
            "parameters": operation_parameters,
            "responses": _apipost_responses(item.get("response")),
        }
        request_body = _apipost_request_body(request.get("body"))
        if request_body:
            operation["requestBody"] = request_body
        _add_operation(document, path=item.get("url"), method=item.get("method"), operation=operation, keep_full_url=keep_full_url)
    return document


def _iter_apipost_apis(items: Any) -> Iterable[tuple[dict[str, Any], str]]:
    if not isinstance(items, list):
        return []

    flat_items = [item for item in items if isinstance(item, dict)]
    if any("parent_id" in item for item in flat_items):
        folders = {
            str(item.get("target_id")): item
            for item in flat_items
            if item.get("target_type") == "folder"
        }

        def folder_name(item: dict[str, Any]) -> str:
            parent_id = str(item.get("parent_id") or "0")
            seen = set()
            while parent_id not in {"", "0", "None"} and parent_id not in seen:
                seen.add(parent_id)
                parent = folders.get(parent_id)
                if not parent:
                    break
                if parent.get("name"):
                    return str(parent["name"])
                parent_id = str(parent.get("parent_id") or "0")
            return ""

        return [
            (item, folder_name(item))
            for item in flat_items
            if item.get("target_type") == "api"
        ]

    result: list[tuple[dict[str, Any], str]] = []

    def visit(nodes: Any, module_name: str = "") -> None:
        if not isinstance(nodes, list):
            return
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if node.get("target_type") == "folder" or isinstance(node.get("children"), list):
                visit(node.get("children"), str(node.get("name") or module_name))
            elif node.get("target_type") == "api":
                result.append((node, module_name))

    visit(flat_items)
    return result


def _apipost_request_body(body: Any) -> dict[str, Any] | None:
    if not isinstance(body, dict):
        return None
    mode = str(body.get("mode") or "none").lower()
    if mode in {"", "none"}:
        return None
    if mode == "form-data":
        return {"content": {"multipart/form-data": _form_media(body.get("parameter"))}}
    if mode == "urlencoded":
        return {"content": {"application/x-www-form-urlencoded": _form_media(body.get("parameter"))}}
    if mode == "binary":
        return {
            "content": {
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"},
                },
            },
        }

    media_type = {
        "json": "application/json",
        "xml": "application/xml",
        "plain": "text/plain",
        "raw": "text/plain",
        "html": "text/html",
    }.get(mode, "application/json")
    example = _coerce_json(body.get("raw", ""))
    schema = _json_object(body.get("raw_schema")) or _schema_from_value(example)
    return {"content": {media_type: {"schema": schema, "example": example}}}


def _apipost_responses(response_container: Any) -> dict[str, Any]:
    if not isinstance(response_container, dict):
        return {"200": {"description": "Successful response"}}
    examples = response_container.get("example")
    if not isinstance(examples, list):
        return {"200": {"description": "Successful response"}}

    responses: dict[str, Any] = {}
    for item in examples:
        if not isinstance(item, dict):
            continue
        expect = item.get("expect") if isinstance(item.get("expect"), dict) else {}
        code = str(expect.get("code") or 200)
        raw = _coerce_json(item.get("raw", ""))
        schema = _json_object(expect.get("schema"))
        response: dict[str, Any] = {"description": str(expect.get("name") or "Response")}
        if schema or raw not in (None, ""):
            response["content"] = {
                _response_content_type(expect.get("content_type")): {
                    "schema": schema or _schema_from_value(raw),
                    "example": raw,
                },
            }
        responses.setdefault(code, response)
    return responses or {"200": {"description": "Successful response"}}


def _yapi_to_openapi(source: list[Any], *, keep_full_url: bool = False) -> dict[str, Any]:
    document = _new_openapi("YApi Project")

    def visit(nodes: Any, module_name: str = "") -> None:
        if not isinstance(nodes, list):
            return
        for item in nodes:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("list"), list):
                visit(item["list"], str(item.get("name") or module_name))
                continue

            operation_parameters = []
            operation_parameters.extend(_external_parameters(item.get("req_headers"), "header"))
            operation_parameters.extend(_external_parameters(item.get("req_query"), "query"))
            operation_parameters.extend(_external_parameters(item.get("req_params"), "path"))
            operation: dict[str, Any] = {
                "summary": str(item.get("title") or "Imported API"),
                "description": str(item.get("desc") or ""),
                "tags": [module_name] if module_name else [],
                "parameters": operation_parameters,
                "responses": _yapi_responses(item),
            }
            request_body = _yapi_request_body(item)
            if request_body:
                operation["requestBody"] = request_body
            _add_operation(document, path=item.get("path"), method=item.get("method"), operation=operation, keep_full_url=keep_full_url)

    visit(source)
    return document


def _yapi_request_body(item: dict[str, Any]) -> dict[str, Any] | None:
    body_type = str(item.get("req_body_type") or "").lower()
    if body_type in {"", "none"}:
        return None
    if body_type in {"form", "file"}:
        media_type = "multipart/form-data"
        headers = item.get("req_headers") if isinstance(item.get("req_headers"), list) else []
        for header in headers:
            if not isinstance(header, dict):
                continue
            if str(header.get("name", header.get("key", ""))).lower() != "content-type":
                continue
            if "x-www-form-urlencoded" in str(header.get("value", "")):
                media_type = "application/x-www-form-urlencoded"
        return {"content": {media_type: _form_media(item.get("req_body_form"))}}

    raw = item.get("req_body_other", "")
    if body_type == "json" and item.get("req_body_is_json_schema"):
        schema = _json_object(raw)
        example = _sample_from_schema({}, schema)
        return {"content": {"application/json": {"schema": schema, "example": example}}}

    example = _coerce_json(raw)
    media_type = "application/json" if isinstance(example, (dict, list)) else "text/plain"
    return {
        "content": {
            media_type: {
                "schema": _schema_from_value(example),
                "example": example,
            },
        },
    }


def _yapi_responses(item: dict[str, Any]) -> dict[str, Any]:
    raw = item.get("res_body", "")
    if not raw:
        return {"200": {"description": "Successful response"}}
    if item.get("res_body_type") == "json" and item.get("res_body_is_json_schema"):
        schema = _json_object(raw)
        example = _sample_from_schema({}, schema)
        media_type = "application/json"
    else:
        example = _coerce_json(raw)
        schema = _schema_from_value(example)
        media_type = "application/json" if isinstance(example, (dict, list)) else "text/plain"
    return {
        "200": {
            "description": "Successful response",
            "content": {media_type: {"schema": schema, "example": example}},
        },
    }


def _parameters_from_url(value: Any) -> list[dict[str, Any]]:
    parsed = urlparse(str(value or ""))
    return [
        {
            "name": name,
            "in": "query",
            "required": False,
            "description": "",
            "schema": _schema_from_value(raw_value),
            "example": raw_value,
        }
        for name, raw_value in parse_qsl(parsed.query, keep_blank_values=True)
    ]


def _body_from_raw(raw: Any, media_type: str = "application/json") -> dict[str, Any] | None:
    if raw in (None, ""):
        return None
    example = _coerce_json(raw)
    normalized_media = str(media_type or "application/json").split(";", 1)[0].strip()
    if not normalized_media or "/" not in normalized_media:
        normalized_media = "application/json" if isinstance(example, (dict, list)) else "text/plain"
    return {
        "content": {
            normalized_media: {
                "schema": _schema_from_value(example),
                "example": example,
            },
        },
    }


def _example_response(
    raw: Any = "",
    *,
    status_code: Any = 200,
    media_type: str = "application/json",
    description: str = "Successful response",
) -> dict[str, Any]:
    response: dict[str, Any] = {"description": description or "Response"}
    if raw not in (None, ""):
        example = _coerce_json(raw)
        response["content"] = {
            str(media_type or "application/json").split(";", 1)[0]: {
                "schema": _schema_from_value(example),
                "example": example,
            },
        }
    return {str(status_code or 200): response}


def _postman_to_openapi(source: dict[str, Any], *, keep_full_url: bool = False) -> dict[str, Any]:
    info = source.get("info") if isinstance(source.get("info"), dict) else {}
    collection_name = str(info.get("name") or "").strip()
    document = _new_openapi(collection_name or "Postman Collection", str(info.get("description") or ""))

    def visit(items: Any, module_name: str = "") -> None:
        if not isinstance(items, list):
            return
        # 未传入具体 folder 名时，回退到 collection 的 info.name 作为默认模块名
        effective_module_name = module_name or collection_name
        for item in items:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("item"), list):
                visit(item["item"], str(item.get("name") or effective_module_name))
                continue
            request = item.get("request")
            if isinstance(request, str):
                request = {"url": request, "method": "GET"}
            if not isinstance(request, dict):
                continue
            raw_url, url_query = _postman_url(request.get("url"))
            operation_parameters = _external_parameters(request.get("header"), "header")
            operation_parameters.extend(_external_parameters(url_query, "query"))
            if not url_query:
                operation_parameters.extend(_parameters_from_url(raw_url))
            operation: dict[str, Any] = {
                "summary": str(item.get("name") or _normalize_import_path(raw_url)),
                "description": _postman_description(request.get("description")),
                "tags": [effective_module_name] if effective_module_name else [],
                "parameters": operation_parameters,
                "responses": _postman_responses(item.get("response")),
            }
            request_body = _postman_request_body(request.get("body"), request.get("header"))
            if request_body:
                operation["requestBody"] = request_body
            _add_operation(document, path=raw_url, method=request.get("method"), operation=operation, keep_full_url=keep_full_url)

    visit(source.get("item"))
    return document


def _postman_description(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("content") or "")
    return str(value or "")


def _postman_url(value: Any) -> tuple[str, list[dict[str, Any]]]:
    if isinstance(value, str):
        return value, []
    if not isinstance(value, dict):
        return "/", []
    raw = value.get("raw")
    if not raw:
        protocol = str(value.get("protocol") or "https")
        host = value.get("host")
        path = value.get("path")
        host_text = ".".join(str(part) for part in host) if isinstance(host, list) else str(host or "")
        path_text = "/".join(str(part) for part in path) if isinstance(path, list) else str(path or "")
        raw = f"{protocol}://{host_text}/{path_text}" if host_text else f"/{path_text}"
    return str(raw), value.get("query") if isinstance(value.get("query"), list) else []


def _postman_request_body(body: Any, headers: Any) -> dict[str, Any] | None:
    if not isinstance(body, dict) or body.get("disabled"):
        return None
    mode = str(body.get("mode") or "").lower()
    if mode == "formdata":
        return {"content": {"multipart/form-data": _form_media(body.get("formdata"))}}
    if mode == "urlencoded":
        return {"content": {"application/x-www-form-urlencoded": _form_media(body.get("urlencoded"))}}
    if mode == "file":
        return {"content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}}}
    if mode == "graphql":
        graphql = body.get("graphql") if isinstance(body.get("graphql"), dict) else {}
        return _body_from_raw(graphql, "application/json")
    if mode != "raw":
        return None
    language = ""
    options = body.get("options") if isinstance(body.get("options"), dict) else {}
    raw_options = options.get("raw") if isinstance(options.get("raw"), dict) else {}
    language = str(raw_options.get("language") or "")
    media_type = {
        "json": "application/json",
        "xml": "application/xml",
        "html": "text/html",
        "text": "text/plain",
        "javascript": "application/javascript",
    }.get(language, "")
    if not media_type and isinstance(headers, list):
        for header in headers:
            if isinstance(header, dict) and str(header.get("key", header.get("name", ""))).lower() == "content-type":
                media_type = str(header.get("value") or "")
                break
    return _body_from_raw(body.get("raw"), media_type or "application/json")


def _postman_responses(items: Any) -> dict[str, Any]:
    if not isinstance(items, list):
        return _example_response()
    responses: dict[str, Any] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        headers = item.get("header") if isinstance(item.get("header"), list) else []
        media_type = "application/json"
        for header in headers:
            if isinstance(header, dict) and str(header.get("key", "")).lower() == "content-type":
                media_type = str(header.get("value") or media_type)
        responses.update(_example_response(
            item.get("body", ""),
            status_code=item.get("code") or 200,
            media_type=media_type,
            description=str(item.get("name") or item.get("status") or "Response"),
        ))
    return responses or _example_response()


def _har_to_openapi(source: dict[str, Any], *, keep_full_url: bool = False) -> dict[str, Any]:
    log = source.get("log") if isinstance(source.get("log"), dict) else {}
    document = _new_openapi("HAR Import", str(log.get("comment") or ""))
    for entry in log.get("entries", []):
        if not isinstance(entry, dict) or not isinstance(entry.get("request"), dict):
            continue
        request = entry["request"]
        raw_url = request.get("url") or "/"
        operation_parameters = _external_parameters(request.get("headers"), "header")
        operation_parameters.extend(_external_parameters(request.get("queryString"), "query"))
        response = entry.get("response") if isinstance(entry.get("response"), dict) else {}
        response_content = response.get("content") if isinstance(response.get("content"), dict) else {}
        operation: dict[str, Any] = {
            "summary": str(entry.get("comment") or _normalize_import_path(raw_url)),
            "description": str(request.get("comment") or ""),
            "tags": [str(entry.get("pageref") or "HAR")],
            "parameters": operation_parameters,
            "responses": _example_response(
                response_content.get("text", ""),
                status_code=response.get("status") or 200,
                media_type=str(response_content.get("mimeType") or "application/json"),
                description=str(response.get("statusText") or "Response"),
            ),
        }
        post_data = request.get("postData") if isinstance(request.get("postData"), dict) else {}
        mime_type = str(post_data.get("mimeType") or "")
        if isinstance(post_data.get("params"), list) and "multipart/form-data" in mime_type:
            operation["requestBody"] = {"content": {"multipart/form-data": _form_media(post_data["params"])}}
        elif isinstance(post_data.get("params"), list) and "x-www-form-urlencoded" in mime_type:
            operation["requestBody"] = {"content": {"application/x-www-form-urlencoded": _form_media(post_data["params"])}}
        else:
            request_body = _body_from_raw(post_data.get("text"), mime_type)
            if request_body:
                operation["requestBody"] = request_body
        _add_operation(document, path=raw_url, method=request.get("method"), operation=operation, keep_full_url=keep_full_url)
    return document


def _insomnia_to_openapi(source: dict[str, Any], *, keep_full_url: bool = False) -> dict[str, Any]:
    resources = source.get("resources") if isinstance(source.get("resources"), list) else []
    workspace = next((item for item in resources if isinstance(item, dict) and item.get("_type") == "workspace"), {})
    document = _new_openapi(str(workspace.get("name") or "Insomnia Export"), str(workspace.get("description") or ""))
    groups = {
        str(item.get("_id")): item
        for item in resources
        if isinstance(item, dict) and item.get("_type") == "request_group"
    }
    for item in resources:
        if not isinstance(item, dict) or item.get("_type") != "request":
            continue
        parent_id = str(item.get("parentId") or "")
        module_name = str(groups.get(parent_id, {}).get("name") or "")
        raw_url = item.get("url") or "/"
        operation: dict[str, Any] = {
            "summary": str(item.get("name") or _normalize_import_path(raw_url)),
            "description": str(item.get("description") or ""),
            "tags": [module_name] if module_name else [],
            "parameters": (
                _external_parameters(item.get("headers"), "header")
                + _external_parameters(item.get("parameters"), "query")
            ),
            "responses": _example_response(),
        }
        body = item.get("body") if isinstance(item.get("body"), dict) else {}
        mime_type = str(body.get("mimeType") or "")
        if isinstance(body.get("params"), list) and mime_type in {"multipart/form-data", "application/x-www-form-urlencoded"}:
            operation["requestBody"] = {"content": {mime_type: _form_media(body["params"])}}
        else:
            request_body = _body_from_raw(body.get("text"), mime_type)
            if request_body:
                operation["requestBody"] = request_body
        _add_operation(document, path=raw_url, method=item.get("method"), operation=operation, keep_full_url=keep_full_url)
    return document


def _apidoc_fields(container: Any, preferred_group: str = "") -> list[dict[str, Any]]:
    if not isinstance(container, dict):
        return []
    fields = container.get("fields") if isinstance(container.get("fields"), dict) else {}
    result: list[dict[str, Any]] = []
    for group, items in fields.items():
        if preferred_group and str(group).lower() != preferred_group.lower():
            continue
        if isinstance(items, list):
            result.extend(item for item in items if isinstance(item, dict))
    return result


def _apidoc_to_openapi(source: Any, *, keep_full_url: bool = False) -> dict[str, Any]:
    document = _new_openapi("ApiDoc Import")
    for item in _apidoc_items(source):
        module_name = str(item.get("groupTitle") or item.get("group") or "")
        operation_parameters = _external_parameters(_apidoc_fields(item.get("header")), "header")
        operation_parameters.extend(_external_parameters(_apidoc_fields(item.get("parameter")), "query"))
        responses: dict[str, Any] = {}
        for status_code, key in ((200, "success"), (400, "error")):
            container = item.get(key) if isinstance(item.get(key), dict) else {}
            examples = container.get("examples") if isinstance(container.get("examples"), list) else []
            raw = examples[0].get("content", "") if examples and isinstance(examples[0], dict) else ""
            if container:
                responses.update(_example_response(raw, status_code=status_code, description=key.title()))
        operation: dict[str, Any] = {
            "summary": str(item.get("title") or "Imported API"),
            "description": str(item.get("description") or ""),
            "tags": [module_name] if module_name else [],
            "parameters": operation_parameters,
            "responses": responses or _example_response(),
        }
        body_fields = item.get("body") if isinstance(item.get("body"), list) else []
        if body_fields:
            operation["requestBody"] = {"content": {"multipart/form-data": _form_media(body_fields)}}
        _add_operation(document, path=item.get("url"), method=item.get("type"), operation=operation, keep_full_url=keep_full_url)
    return document


def _curl_to_openapi(command: str, *, keep_full_url: bool = False) -> dict[str, Any]:
    # 兼容 Windows cmd 粘贴的 curl：^ 是续行符，可能独立成 token（被误当 URL）
    # 或紧贴 token 末尾（粘进 header/参数值）；同时兼容 CRLF 与 Linux 的 \ 续行符
    command = command.replace("\\\r\n", " ").replace("\\\n", " ")
    try:
        tokens = shlex.split(command)
    except ValueError as exc:
        raise OpenAPIError(f"Invalid cURL command: {exc}") from exc
    if not tokens or tokens[0].lower() != "curl":
        raise OpenAPIError("The content must start with a cURL command.")
    # 去掉 Windows cmd 续行符残留：^ 可能独立成 token，或紧贴 token 首尾
    # （如 "curl ^http://..."），统一剥离；引号内数据中间的 ^（如 URL 的 a^b）不受影响
    tokens = [token.strip("^") for token in tokens]
    tokens = [token for token in tokens if token]

    method = ""
    raw_url = ""
    headers: list[dict[str, Any]] = []
    data_parts: list[str] = []
    forms: list[dict[str, Any]] = []
    use_get = False
    index = 1
    value_options = {
        "-x", "--proxy", "-u", "--user", "-A", "--user-agent", "-b", "--cookie",
        "--connect-timeout", "--max-time", "-o", "--output", "--cacert", "--cert", "--key",
    }
    while index < len(tokens):
        token = tokens[index]
        if token in {"-X", "--request"} and index + 1 < len(tokens):
            method = tokens[index + 1].upper()
            index += 2
            continue
        if token in {"--url"} and index + 1 < len(tokens):
            raw_url = tokens[index + 1]
            index += 2
            continue
        if token in {"-H", "--header"} and index + 1 < len(tokens):
            name, separator, value = tokens[index + 1].partition(":")
            if separator and name:
                headers.append({"name": name.strip(), "value": value.strip()})
            index += 2
            continue
        if token in {"-d", "--data", "--data-raw", "--data-binary", "--data-urlencode"} and index + 1 < len(tokens):
            data_parts.append(tokens[index + 1])
            index += 2
            continue
        if token in {"-F", "--form"} and index + 1 < len(tokens):
            name, separator, value = tokens[index + 1].partition("=")
            if separator:
                forms.append({"name": name, "value": value, "type": "file" if value.startswith("@") else "string"})
            index += 2
            continue
        if token in {"-G", "--get"}:
            use_get = True
            index += 1
            continue
        if token in value_options and index + 1 < len(tokens):
            index += 2
            continue
        if not token.startswith("-") and not raw_url:
            raw_url = token
        index += 1

    if not raw_url:
        raise OpenAPIError("The cURL command does not contain a request URL.")
    if not method:
        method = "GET" if use_get or (not data_parts and not forms) else "POST"
    if method not in HTTP_METHODS:
        raise OpenAPIError(f"Unsupported cURL HTTP method: {method}")

    query_parameters = _parameters_from_url(raw_url)
    if use_get and data_parts:
        query_parameters.extend(
            {
                "name": name,
                "in": "query",
                "required": False,
                "description": "",
                "schema": _schema_from_value(value),
                "example": value,
            }
            for part in data_parts
            for name, value in parse_qsl(part, keep_blank_values=True)
        )
    operation: dict[str, Any] = {
        "summary": f"{method} {_normalize_import_path(raw_url)}",
        "description": "Imported from cURL",
        "tags": ["cURL"],
        "parameters": _external_parameters(headers, "header") + query_parameters,
        "responses": _example_response(),
    }
    if forms:
        operation["requestBody"] = {"content": {"multipart/form-data": _form_media(forms)}}
    elif data_parts and not use_get:
        media_type = "application/x-www-form-urlencoded"
        for header in headers:
            if str(header.get("name", "")).lower() == "content-type":
                media_type = str(header.get("value") or media_type)
        operation["requestBody"] = _body_from_raw("&".join(data_parts), media_type)
    document = _new_openapi("cURL Import")
    _add_operation(document, path=raw_url, method=method, operation=operation, keep_full_url=keep_full_url)
    return document


def _markdown_frontmatter_title(text: str) -> str:
    """从 Markdown 文档开头的 YAML frontmatter 中提取 title 字段。"""
    frontmatter_match = re.match(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n?", text.lstrip("\ufeff"), re.DOTALL)
    if not frontmatter_match:
        return ""
    raw = frontmatter_match.group(1)
    if yaml is not None:
        try:
            parsed = yaml.safe_load(raw)
        except Exception:
            parsed = None
        if isinstance(parsed, dict) and parsed.get("title") not in (None, ""):
            return str(parsed["title"]).strip()
    title_match = re.search(r"(?m)^\s*title\s*[:：]\s*(.+?)\s*$", raw)
    if title_match:
        return title_match.group(1).strip().strip("'\"")
    return ""


def _markdown_body_from_code(content: str, language: str) -> dict[str, Any] | None:
    """把 Markdown 文档中 Body 代码块转换为 OpenAPI requestBody。

    json/xml/text 等原始体按原始内容导入；yaml 块通常是 Postman 导出的
    form-data 键值（如 files: /path），转换为 multipart/form-data。
    """
    if not content.strip():
        return None
    lang = str(language or "").strip().lower()
    if lang in {"yaml", "yml"}:
        if yaml is None:
            return None
        try:
            parsed = yaml.safe_load(content)
        except Exception:
            parsed = None
        if isinstance(parsed, dict) and parsed:
            properties: dict[str, Any] = {}
            for key, value in parsed.items():
                name = str(key)
                item: dict[str, Any] = {"type": "string", "example": value}
                text_value = str(value or "")
                # 字段名含 file 或值为带扩展名的文件路径时按二进制文件处理
                if "file" in name.lower() or (
                    ("/" in text_value or "\\" in text_value)
                    and re.search(r"\.(?:[A-Za-z0-9]{1,8})$", text_value.strip())
                ):
                    item["format"] = "binary"
                properties[name] = item
            return {
                "content": {
                    "multipart/form-data": {
                        "schema": {"type": "object", "properties": properties},
                    },
                },
            }
        return None
    media_type = {
        "json": "application/json",
        "xml": "application/xml",
        "html": "text/html",
        "text": "text/plain",
        "plain": "text/plain",
    }.get(lang, "application/json")
    return _body_from_raw(content, media_type)


def _markdown_to_openapi(text: str, *, keep_full_url: bool = False) -> dict[str, Any]:
    if not text.strip():
        raise OpenAPIError("The uploaded Markdown document is empty.")
    frontmatter_title = _markdown_frontmatter_title(text)
    document = _new_openapi(frontmatter_title or "Markdown Import")
    heading = ""
    # 文档 frontmatter 的 title 字段作为整个文档的模块名
    module_name = frontmatter_title or "Markdown"
    module_from_title = bool(frontmatter_title)
    pending_method = ""
    pending_title = ""
    last_operation: dict[str, Any] | None = None
    body_pending = False
    fence_language = ""
    fence_lines: list[str] = []
    endpoint_pattern = re.compile(
        r"^\s*(?:[-*]\s*)?(?:\*\*)?(GET|POST|PUT|DELETE|PATCH)(?:\*\*)?\s*[:：]?\s*`?(https?://[^\s`]+|/[^\s`]*)`?",
        flags=re.IGNORECASE,
    )
    label_method_pattern = re.compile(r"(?:请求方式|method)\s*[:：|]\s*`?(?:\*\*)?(GET|POST|PUT|DELETE|PATCH)", re.IGNORECASE)
    label_url_pattern = re.compile(r"(?:请求地址|请求路径|url|path)\s*[:：|]\s*`?(?:\*\*)?(https?://[^\s`*]+|/[^\s`*]+)", re.IGNORECASE)
    body_marker_pattern = re.compile(r"^>\s*(?:body\b|请求体|request\s*body)", re.IGNORECASE)

    def add_endpoint(method: str, raw_url: str, title: str) -> None:
        nonlocal last_operation
        operation = {
            # 优先取 "## POST 上传文件" 头部中请求方法后的名称作为接口名
            "summary": pending_title or title or f"{method.upper()} {_normalize_import_path(raw_url)}",
            "description": "Imported from Markdown",
            "tags": [module_name] if module_name else [],
            "parameters": _parameters_from_url(raw_url),
            "responses": _example_response(),
        }
        _add_operation(document, path=raw_url, method=method, operation=operation, keep_full_url=keep_full_url)
        last_operation = operation

    for raw_line in text.splitlines():
        line = raw_line.strip()
        plain_line = line.replace("**", "")

        # 代码块：收集内容，跟在 "> Body" 标记后的代码块作为请求体
        if line.startswith(("```", "~~~")):
            if fence_language:
                if body_pending and last_operation:
                    request_body = _markdown_body_from_code("\n".join(fence_lines), fence_language)
                    if request_body:
                        last_operation["requestBody"] = request_body
                fence_language = ""
                body_pending = False
                fence_lines = []
            else:
                fence_language = line.lstrip("`~").strip() or "text"
                fence_lines = []
            continue
        if fence_language:
            fence_lines.append(raw_line)
            continue

        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            heading = line[level:].strip().strip("`*")
            if not module_from_title and level <= 2 and not re.search(
                r"\b(?:GET|POST|PUT|DELETE|PATCH)\b", heading, re.IGNORECASE
            ):
                module_name = heading or module_name
            last_operation = None
            body_pending = False
            method_heading = re.match(r"^(GET|POST|PUT|DELETE|PATCH)\s+(.+)$", heading, re.IGNORECASE)
            if method_heading and not method_heading.group(2).lstrip("`*").startswith(("/", "http")):
                # "## POST 上传文件"：记录请求方法与名称，等待下一行 URL 形成接口
                pending_method = method_heading.group(1)
                pending_title = method_heading.group(2).strip().strip("`*")
            else:
                pending_method = ""
                pending_title = ""

        if line.startswith(">"):
            body_pending = bool(body_marker_pattern.match(line))
            continue

        endpoint_match = endpoint_pattern.match(line.lstrip("# "))
        if endpoint_match:
            method, raw_url = endpoint_match.groups()
            # 偏移量相对去掉 "# " 前缀后的行计算，避免 heading 行索引错位
            matched_line = line.lstrip("# ")
            suffix = matched_line[endpoint_match.end():].strip(" `*-:：")
            add_endpoint(method, raw_url, suffix or heading)
            pending_method = ""
            pending_title = ""
            continue
        method_match = label_method_pattern.search(plain_line)
        if method_match:
            pending_method = method_match.group(1)
            pending_title = heading
        url_match = label_url_pattern.search(plain_line)
        if url_match and pending_method:
            add_endpoint(pending_method, url_match.group(1), pending_title)
            pending_method = ""
            pending_title = ""

    if not document["paths"]:
        raise OpenAPIError("No HTTP method and path pairs were found in the Markdown document.")
    return document


def _walk_external_apis(value: Any, list_keys: tuple[str, ...], module_name: str = "") -> Iterable[tuple[dict[str, Any], str]]:
    if isinstance(value, list):
        for item in value:
            yield from _walk_external_apis(item, list_keys, module_name)
        return
    if not isinstance(value, dict):
        return
    method = value.get("method", value.get("apiRequestType"))
    url = value.get("url", value.get("apiURI", value.get("uri")))
    if method is not None and url:
        yield value, module_name
        return
    next_module = str(
        value.get("groupName")
        or value.get("folderName")
        or value.get("categoryName")
        or value.get("name")
        or module_name
    )
    for key in list_keys:
        if key in value:
            yield from _walk_external_apis(value[key], list_keys, next_module)


def _apizza_to_openapi(source: Any, *, keep_full_url: bool = False) -> dict[str, Any]:
    title = source.get("name") if isinstance(source, dict) else ""
    document = _new_openapi(str(title or "Apizza Project"))
    items = list(_walk_external_apis(source, ("data", "folders", "categories", "api_list", "apis", "list")))
    for item, module_name in items:
        operation: dict[str, Any] = {
            "summary": str(item.get("name") or "Imported API"),
            "description": str(item.get("response_doc") or item.get("description") or ""),
            "tags": [str(item.get("folderName") or module_name)] if (item.get("folderName") or module_name) else [],
            "parameters": (
                _external_parameters(item.get("header_params"), "header")
                + _external_parameters(item.get("query_params"), "query")
            ),
            "responses": _example_response(item.get("response_example", "")),
        }
        body_type = str(item.get("body_type") or "").lower()
        if isinstance(item.get("body_params"), list) and body_type in {"form", "form-data", "multipart/form-data"}:
            operation["requestBody"] = {"content": {"multipart/form-data": _form_media(item["body_params"])}}
        elif isinstance(item.get("body_params"), list) and body_type in {"urlencoded", "x-www-form-urlencoded"}:
            operation["requestBody"] = {"content": {"application/x-www-form-urlencoded": _form_media(item["body_params"])}}
        else:
            request_body = _body_from_raw(
                item.get("body_raw", item.get("body_raw_example", "")),
                str(item.get("raw_content_type") or "application/json"),
            )
            if request_body:
                operation["requestBody"] = request_body
        _add_operation(document, path=item.get("url"), method=item.get("method"), operation=operation, keep_full_url=keep_full_url)
    return document


def _eolink_method(value: Any) -> str:
    if isinstance(value, int) or str(value).isdigit():
        return {0: "POST", 1: "GET", 2: "PUT", 3: "DELETE", 6: "PATCH"}.get(int(value), "GET")
    return str(value or "GET").upper()


def _eolink_to_openapi(source: Any, *, keep_full_url: bool = False) -> dict[str, Any]:
    project_info = source.get("projectInfo") if isinstance(source, dict) and isinstance(source.get("projectInfo"), dict) else {}
    title = project_info.get("projectName") or (source.get("projectName") if isinstance(source, dict) else "")
    document = _new_openapi(str(title or "Eolink Project"))
    items = list(_walk_external_apis(
        source,
        ("apiGroupList", "api_group_list", "groupList", "groups", "apiList", "api_list", "apis", "children", "data"),
    ))
    for item, module_name in items:
        method = _eolink_method(item.get("method", item.get("apiRequestType")))
        raw_url = item.get("url", item.get("apiURI", item.get("uri", "/")))
        headers = item.get("apiRequestHeader", item.get("requestHeaders", item.get("headers")))
        query = item.get("apiRequestParam", item.get("requestParams", item.get("queryParams")))
        operation: dict[str, Any] = {
            "summary": str(item.get("apiName") or item.get("name") or "Imported API"),
            "description": str(item.get("apiNote") or item.get("description") or ""),
            "tags": [module_name] if module_name else [],
            "parameters": _external_parameters(headers, "header") + _external_parameters(query, "query"),
            "responses": _eolink_responses(item),
        }
        body = item.get("apiRequestRaw", item.get("requestBody", item.get("body")))
        if isinstance(body, dict):
            body = body.get("raw", body.get("content", body))
        request_body = _body_from_raw(body, str(item.get("apiRequestRawType") or "application/json"))
        if request_body:
            operation["requestBody"] = request_body
        _add_operation(document, path=raw_url, method=method, operation=operation, keep_full_url=keep_full_url)
    return document


def _eolink_responses(item: dict[str, Any]) -> dict[str, Any]:
    results = item.get("apiResult", item.get("responses"))
    if isinstance(results, list):
        responses: dict[str, Any] = {}
        for result in results:
            if not isinstance(result, dict):
                continue
            responses.update(_example_response(
                result.get("result", result.get("body", result.get("content", ""))),
                status_code=result.get("httpCode", result.get("statusCode", 200)),
                description=str(result.get("name") or "Response"),
            ))
        if responses:
            return responses
    return _example_response()


def _iter_openapi_operations(
    document: dict[str, Any],
) -> Iterable[tuple[str, str, dict[str, Any], str]]:
    for path, path_item in document.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if str(method).upper() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            tags = operation.get("tags") if isinstance(operation.get("tags"), list) else []
            module_name = str(tags[0]) if tags else "Uncategorized"
            yield str(path), str(method).upper(), operation, module_name


def _project_title(document: dict[str, Any], project_name: str) -> str:
    if project_name:
        return project_name
    info = document.get("info") if isinstance(document.get("info"), dict) else {}
    return str(info.get("title") or "API Project")


def _openapi_parameters(
    document: dict[str, Any],
    operation: dict[str, Any],
    location: str,
) -> list[dict[str, Any]]:
    result = []
    parameters = operation.get("parameters") if isinstance(operation.get("parameters"), list) else []
    for raw_parameter in parameters:
        parameter = _resolve_ref(document, raw_parameter)
        if not isinstance(parameter, dict) or parameter.get("in") != location:
            continue
        schema = _resolve_ref(document, parameter.get("schema"))
        schema = schema if isinstance(schema, dict) else {"type": "string"}
        value = parameter.get("example")
        if value is None:
            value = _sample_from_schema(document, schema)
        result.append({
            "name": str(parameter.get("name") or ""),
            "description": str(parameter.get("description") or ""),
            "required": bool(parameter.get("required")),
            "schema": deepcopy(schema),
            "value": value,
        })
    return result


def _openapi_body(
    document: dict[str, Any],
    operation: dict[str, Any],
) -> tuple[str, dict[str, Any], Any] | None:
    request_body = _resolve_ref(document, operation.get("requestBody"))
    if not isinstance(request_body, dict):
        return None
    content = request_body.get("content")
    if not isinstance(content, dict) or not content:
        return None
    media_type, media = _select_media_type(content)
    if not isinstance(media, dict):
        return None
    schema = _resolve_ref(document, media.get("schema"))
    schema = schema if isinstance(schema, dict) else {}
    example = _sample_from_media(document, media, schema)
    return media_type, deepcopy(schema), example


def _schema_properties_to_external(schema: dict[str, Any], example: Any) -> list[dict[str, Any]]:
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    required = schema.get("required") if isinstance(schema.get("required"), list) else []
    example_values = example if isinstance(example, dict) else {}
    result = []
    for name, property_schema in properties.items():
        item_schema = property_schema if isinstance(property_schema, dict) else {"type": "string"}
        result.append({
            "name": str(name),
            "description": str(item_schema.get("description") or ""),
            "required": name in required,
            "schema": deepcopy(item_schema),
            "value": example_values.get(name, _sample_from_schema({}, item_schema)),
        })
    return result


def _openapi_to_apifox(document: dict[str, Any], *, project_name: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    api_index = 0
    for path, method, operation, module_name in _iter_openapi_operations(document):
        api_index += 1
        parameters = {
            location: [
                {
                    "id": f"parameter-{api_index}-{location}-{index}",
                    "name": item["name"],
                    "description": item["description"],
                    "type": str(item["schema"].get("type") or "string"),
                    "required": item["required"],
                    "defaultEnable": True,
                    "defaultValue": item["value"],
                    "example": item["value"],
                }
                for index, item in enumerate(_openapi_parameters(document, operation, location), start=1)
            ]
            for location in ("header", "query", "path", "cookie")
        }

        api: dict[str, Any] = {
            "id": f"api-{api_index}",
            "name": str(operation.get("summary") or f"{method} {path}"),
            "method": method,
            "path": path,
            "description": str(operation.get("description") or ""),
            "status": "released",
            "parameters": parameters,
            "responses": [],
            "responseExamples": [],
        }
        body = _openapi_body(document, operation)
        if body:
            media_type, schema, example = body
            request_body: dict[str, Any] = {
                "type": media_type,
                "parameters": [],
                "jsonSchema": schema,
                "example": _dump_raw(example),
            }
            if media_type in {"multipart/form-data", "application/x-www-form-urlencoded"}:
                request_body["parameters"] = [
                    {
                        "id": f"body-{api_index}-{index}",
                        "name": item["name"],
                        "description": item["description"],
                        "type": str(item["schema"].get("type") or "string"),
                        "required": item["required"],
                        "defaultEnable": True,
                        "defaultValue": item["value"],
                        "example": item["value"],
                    }
                    for index, item in enumerate(
                        _schema_properties_to_external(schema, example),
                        start=1,
                    )
                ]
            api["requestBody"] = request_body

        responses = operation.get("responses") if isinstance(operation.get("responses"), dict) else {}
        for response_index, (code, raw_response) in enumerate(responses.items(), start=1):
            response = _resolve_ref(document, raw_response)
            response = response if isinstance(response, dict) else {}
            response_id = f"response-{api_index}-{response_index}"
            media_type = "application/json"
            schema: dict[str, Any] = {}
            example: Any = ""
            content = response.get("content")
            if isinstance(content, dict) and content:
                media_type, media = _select_media_type(content)
                if isinstance(media, dict):
                    resolved_schema = _resolve_ref(document, media.get("schema"))
                    schema = resolved_schema if isinstance(resolved_schema, dict) else {}
                    example = _sample_from_media(document, media, schema)
            api["responses"].append({
                "id": response_id,
                "name": str(response.get("description") or f"HTTP {code}"),
                "code": int(code) if str(code).isdigit() else str(code),
                "contentType": _apifox_content_type(media_type),
                "jsonSchema": schema,
            })
            api["responseExamples"].append({
                "id": f"response-example-{api_index}-{response_index}",
                "responseId": response_id,
                "name": "Default",
                "data": _dump_raw(example),
                "ordering": 0,
            })

        groups.setdefault(module_name, []).append({
            "id": f"api-item-{api_index}",
            "name": api["name"],
            "api": api,
        })

    folder_items = [
        {
            "id": f"folder-{index}",
            "name": module_name,
            "description": "",
            "items": items,
        }
        for index, (module_name, items) in enumerate(groups.items(), start=1)
    ]
    info = document.get("info") if isinstance(document.get("info"), dict) else {}
    return {
        "apifoxProject": "1.0.0",
        "info": {
            "name": _project_title(document, project_name),
            "description": str(info.get("description") or ""),
        },
        "apiCollection": [
            {
                "id": "api-collection-root",
                "name": "API Collection",
                "items": folder_items,
            },
        ],
        "schemaCollection": [{"id": "schema-root", "name": "Schemas", "items": []}],
        "projectSetting": {"servers": [{"id": "default", "name": "Default"}]},
    }


def _apifox_content_type(media_type: str) -> str:
    if media_type.endswith("+json") or media_type == "application/json":
        return "json"
    if "xml" in media_type:
        return "xml"
    if media_type == "text/html":
        return "html"
    if media_type.startswith("text/"):
        return "text"
    if media_type == "application/octet-stream":
        return "binary"
    return "json"


def _openapi_to_apipost(document: dict[str, Any], *, project_name: str) -> dict[str, Any]:
    apis: list[dict[str, Any]] = []
    folder_ids: dict[str, str] = {}
    operations = list(_iter_openapi_operations(document))
    for folder_index, module_name in enumerate(dict.fromkeys(item[3] for item in operations), start=1):
        folder_id = str(1000000000000 + folder_index)
        folder_ids[module_name] = folder_id
        apis.append({
            "target_id": folder_id,
            "project_id": "0",
            "parent_id": "0",
            "target_type": "folder",
            "name": module_name,
            "description": "",
            "sort": folder_index,
            "request": _apipost_request_container(),
        })

    for api_index, (path, method, operation, module_name) in enumerate(operations, start=1):
        request = _apipost_request_container()
        for location, target_key in (
            ("header", "header"),
            ("query", "query"),
            ("path", "restful"),
            ("cookie", "cookie"),
        ):
            request[target_key]["parameter"] = [
                _apipost_parameter(item, api_index, location, index)
                for index, item in enumerate(
                    _openapi_parameters(document, operation, location),
                    start=1,
                )
            ]

        body = _openapi_body(document, operation)
        if body:
            media_type, schema, example = body
            mode = {
                "application/json": "json",
                "multipart/form-data": "form-data",
                "application/x-www-form-urlencoded": "urlencoded",
                "application/xml": "xml",
                "text/plain": "plain",
                "text/html": "html",
                "application/octet-stream": "binary",
            }.get(media_type, "json" if media_type.endswith("+json") else "plain")
            request["body"] = {
                "mode": mode,
                "parameter": [
                    _apipost_parameter(item, api_index, "body", index)
                    for index, item in enumerate(
                        _schema_properties_to_external(schema, example),
                        start=1,
                    )
                ] if mode in {"form-data", "urlencoded"} else [],
                "raw": _dump_raw(example),
                "raw_parameter": [],
                "raw_schema": schema or {"type": "object", "properties": {}},
                "binary": None,
            }

        response_examples = []
        responses = operation.get("responses") if isinstance(operation.get("responses"), dict) else {}
        for response_index, (code, raw_response) in enumerate(responses.items(), start=1):
            response = _resolve_ref(document, raw_response)
            response = response if isinstance(response, dict) else {}
            content_type = "json"
            schema: dict[str, Any] = {"type": "object", "properties": {}}
            example: Any = ""
            content = response.get("content")
            if isinstance(content, dict) and content:
                media_type, media = _select_media_type(content)
                content_type = _apifox_content_type(media_type)
                if isinstance(media, dict):
                    resolved_schema = _resolve_ref(document, media.get("schema"))
                    if isinstance(resolved_schema, dict):
                        schema = resolved_schema
                    example = _sample_from_media(document, media, schema)
            response_examples.append({
                "example_id": str(3000000000000 + api_index * 100 + response_index),
                "raw": _dump_raw(example),
                "raw_parameter": [],
                "expect": {
                    "name": str(response.get("description") or f"HTTP {code}"),
                    "code": str(code),
                    "content_type": content_type,
                    "is_default": 1 if response_index == 1 else -1,
                    "mock": "",
                    "schema": schema,
                    "verify_type": "schema",
                },
            })

        apis.append({
            "target_id": str(2000000000000 + api_index),
            "project_id": "0",
            "parent_id": folder_ids[module_name],
            "target_type": "api",
            "name": str(operation.get("summary") or f"{method} {path}"),
            "description": str(operation.get("description") or ""),
            "method": method,
            "url": path,
            "mark_id": "2",
            "protocol": "http/1.1",
            "sort": api_index,
            "request": request,
            "response": {"is_check_result": 1, "example": response_examples},
            "tags": [],
            "attribute_info": {},
            "is_force": -1,
        })

    info = document.get("info") if isinstance(document.get("info"), dict) else {}
    return {
        "name": _project_title(document, project_name),
        "project_id": "0",
        "intro": str(info.get("description") or ""),
        "config": {"host": "", "base_path": "", "folder": "0"},
        "global": {
            "envs": [],
            "servers": [],
            "global_vars": {},
            "global_param": {},
        },
        "apis": apis,
        "models": [],
    }


def _apipost_request_container() -> dict[str, Any]:
    return {
        "auth": {"type": "noauth"},
        "pre_tasks": [],
        "post_tasks": [],
        "header": {"parameter": []},
        "query": {"parameter": []},
        "cookie": {"parameter": []},
        "restful": {"parameter": []},
        "body": {
            "mode": "none",
            "parameter": [],
            "raw": "",
            "raw_parameter": [],
            "raw_schema": {"type": "object", "properties": {}},
            "binary": None,
        },
    }


def _apipost_parameter(
    item: dict[str, Any],
    api_index: int,
    location: str,
    parameter_index: int,
) -> dict[str, Any]:
    schema_type = str(item["schema"].get("type") or "string")
    field_type = schema_type[:1].upper() + schema_type[1:]
    if item["schema"].get("format") == "binary":
        field_type = "File"
    return {
        "param_id": f"{api_index}-{location}-{parameter_index}",
        "description": item["description"],
        "field_type": field_type,
        "is_checked": 1,
        "key": item["name"],
        "value": _string_value(item["value"]),
        "not_null": 1 if item["required"] else -1,
    }


def _openapi_to_yapi(document: dict[str, Any], *, project_name: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for api_index, (path, method, operation, module_name) in enumerate(
        _iter_openapi_operations(document),
        start=1,
    ):
        headers = [
            _yapi_parameter(item)
            for item in _openapi_parameters(document, operation, "header")
        ]
        query = [
            _yapi_parameter(item)
            for item in _openapi_parameters(document, operation, "query")
        ]
        path_parameters = [
            _yapi_parameter(item)
            for item in _openapi_parameters(document, operation, "path")
        ]
        req_body_type = "raw"
        req_body_other = ""
        req_body_form: list[dict[str, Any]] = []
        body = _openapi_body(document, operation)
        if body:
            media_type, schema, example = body
            if media_type in {"multipart/form-data", "application/x-www-form-urlencoded"}:
                req_body_type = "form"
                req_body_form = [
                    _yapi_parameter(item, include_type=True)
                    for item in _schema_properties_to_external(schema, example)
                ]
            else:
                req_body_type = "raw"
                req_body_other = _dump_raw(example)
            if not any(str(item.get("name", "")).lower() == "content-type" for item in headers):
                headers.append({
                    "name": "Content-Type",
                    "value": media_type,
                    "desc": "",
                    "required": "0",
                })

        groups.setdefault(module_name, []).append({
            "index": api_index,
            "title": str(operation.get("summary") or f"{method} {path}"),
            "path": path,
            "method": method,
            "desc": str(operation.get("description") or ""),
            "status": "done",
            "type": "static",
            "tag": [],
            "api_opened": False,
            "query_path": {"path": path, "params": path_parameters},
            "req_params": path_parameters,
            "req_query": query,
            "req_headers": headers,
            "req_body_type": req_body_type,
            "req_body_form": req_body_form,
            "req_body_other": req_body_other,
            "req_body_is_json_schema": False,
            "res_body_type": "raw",
            "res_body": "",
            "res_body_is_json_schema": False,
        })

    return [
        {
            "index": index,
            "name": module_name,
            "desc": f"{_project_title(document, project_name)} - {module_name}",
            "list": items,
        }
        for index, (module_name, items) in enumerate(groups.items(), start=1)
    ]


def _yapi_parameter(item: dict[str, Any], include_type: bool = False) -> dict[str, Any]:
    result = {
        "name": item["name"],
        "value": _string_value(item["value"]),
        "desc": item["description"],
        "required": "1" if item["required"] else "0",
    }
    if include_type:
        result["type"] = "file" if item["schema"].get("format") == "binary" else "text"
    return result


def _dump_raw(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)
