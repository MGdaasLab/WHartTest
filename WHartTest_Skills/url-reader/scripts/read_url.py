#!/usr/bin/env python3
"""Fetch a URL and summarize web, text, JSON/YAML, and API documentation content."""

from __future__ import annotations

import argparse
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_TIMEOUT = 20
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_TEXT_CHARS = 6000
USER_AGENT = "Codex URL Reader/1.0"


try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None


@dataclass
class FetchResult:
    url: str
    final_url: str
    status: int | None
    content_type: str
    body: bytes
    error: str | None = None


def fetch_url(url: str, timeout: int, max_bytes: int) -> FetchResult:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                body = body[:max_bytes]
            return FetchResult(
                url=url,
                final_url=response.geturl(),
                status=getattr(response, "status", None),
                content_type=response.headers.get("Content-Type", ""),
                body=body,
            )
    except urllib.error.HTTPError as exc:
        body = exc.read(min(max_bytes, 65536))
        return FetchResult(
            url=url,
            final_url=exc.geturl(),
            status=exc.code,
            content_type=exc.headers.get("Content-Type", ""),
            body=body,
            error=f"HTTP {exc.code}: {exc.reason}",
        )
    except Exception as exc:
        return FetchResult(
            url=url,
            final_url=url,
            status=None,
            content_type="",
            body=b"",
            error=str(exc),
        )


def decode_body(body: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
        try:
            return body.decode(encoding)
        except UnicodeDecodeError:
            continue
    return body.decode("utf-8", errors="replace")


def load_structured(text: str, content_type: str, url: str) -> tuple[Any | None, str | None, str | None]:
    lowered = content_type.lower()
    path = urllib.parse.urlparse(url).path.lower()

    if "json" in lowered or path.endswith(".json"):
        try:
            return json.loads(text), "json", None
        except json.JSONDecodeError as exc:
            return None, "json", f"JSON parse failed: {exc}"

    if "yaml" in lowered or "yml" in lowered or path.endswith((".yaml", ".yml")):
        if yaml is None:
            return None, "yaml", "YAML document found but PyYAML is not installed."
        try:
            return yaml.safe_load(text), "yaml", None
        except Exception as exc:
            return None, "yaml", f"YAML parse failed: {exc}"

    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            return json.loads(text), "json", None
        except json.JSONDecodeError:
            pass

    if re.search(r"(?m)^\s*(openapi|swagger)\s*:", text):
        if yaml is None:
            return None, "yaml", "YAML-like document found but PyYAML is not installed."
        try:
            return yaml.safe_load(text), "yaml", None
        except Exception as exc:
            return None, "yaml", f"YAML parse failed: {exc}"

    return None, None, None


def is_openapi_doc(data: Any) -> bool:
    return isinstance(data, dict) and ("openapi" in data or "swagger" in data) and "paths" in data


def structured_summary(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        keys = list(data.keys())
        return {
            "type": "object",
            "top_level_keys": keys[:80],
            "top_level_key_count": len(keys),
        }
    if isinstance(data, list):
        return {
            "type": "array",
            "item_count": len(data),
            "first_item_type": type(data[0]).__name__ if data else None,
        }
    return {"type": type(data).__name__, "value_preview": str(data)[:500]}


def normalize_candidate(candidate: str, page_url: str) -> str | None:
    candidate = candidate.strip().strip("\"' ")
    if not candidate or candidate.startswith(("javascript:", "#", "data:")):
        return None
    if "\\/" in candidate:
        candidate = candidate.replace("\\/", "/")
    return urllib.parse.urljoin(page_url, candidate)


def page_has_api_hints(text: str, page_url: str) -> bool:
    haystack = f"{page_url}\n{text[:200000]}".lower()
    return any(
        token in haystack
        for token in (
            "swagger-ui",
            "swagger.json",
            "openapi.json",
            "redoc",
            "api-docs",
            "swagger-resources",
            "openapi",
        )
    )


def discover_spec_urls(text: str, page_url: str, include_common_paths: bool) -> list[str]:
    candidates: list[str] = []
    patterns = [
        r"""(?i)\bspec-url\s*=\s*["']([^"']+)["']""",
        r"""(?i)\b(?:url|configUrl)\s*:\s*["']([^"']+)["']""",
        r"""(?i)\burl\s*=\s*["']([^"']+)["']""",
        r"""(?i)["']([^"']*(?:openapi|swagger)[^"']*\.(?:json|ya?ml)(?:\?[^"']*)?)["']""",
        r"""(?i)["']([^"']*(?:v3/api-docs|api-docs|swagger-resources)[^"']*)["']""",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            normalized = normalize_candidate(match.group(1), page_url)
            if normalized:
                candidates.append(normalized)

    if include_common_paths:
        parsed = urllib.parse.urlparse(page_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        common_paths = [
            "/openapi.json",
            "/swagger.json",
            "/v3/api-docs",
            "/api-docs",
            "/swagger/v1/swagger.json",
            "/swagger/docs/v1",
        ]
        candidates.extend(urllib.parse.urljoin(base, path) for path in common_paths)

    seen: set[str] = set()
    unique: list[str] = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def short_schema(schema: Any) -> Any:
    if not isinstance(schema, dict):
        return schema
    keys = ["type", "format", "enum", "required", "properties", "$ref", "items", "description"]
    result: dict[str, Any] = {}
    for key in keys:
        if key not in schema:
            continue
        value = schema[key]
        if key == "properties" and isinstance(value, dict):
            result[key] = {name: short_schema(prop) for name, prop in list(value.items())[:30]}
        elif key == "items":
            result[key] = short_schema(value)
        else:
            result[key] = value
    return result


def summarize_openapi(data: dict[str, Any], source_url: str) -> dict[str, Any]:
    info = data.get("info") if isinstance(data.get("info"), dict) else {}
    servers = data.get("servers") if isinstance(data.get("servers"), list) else []
    security_schemes = (
        data.get("components", {}).get("securitySchemes", {})
        if isinstance(data.get("components"), dict)
        else data.get("securityDefinitions", {})
    )

    endpoints: list[dict[str, Any]] = []
    for path, path_item in (data.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        path_params = path_item.get("parameters", [])
        for method, operation in path_item.items():
            method_lower = str(method).lower()
            if method_lower not in {"get", "post", "put", "delete", "patch", "head", "options", "trace"}:
                continue
            if not isinstance(operation, dict):
                continue
            parameters = []
            for parameter in list(path_params or []) + list(operation.get("parameters") or []):
                if not isinstance(parameter, dict):
                    continue
                parameters.append(
                    {
                        "name": parameter.get("name"),
                        "in": parameter.get("in"),
                        "required": parameter.get("required"),
                        "schema": short_schema(parameter.get("schema")),
                        "description": parameter.get("description"),
                    }
                )

            request_body = operation.get("requestBody")
            if isinstance(request_body, dict):
                content = request_body.get("content") if isinstance(request_body.get("content"), dict) else {}
                request_body = {
                    "required": request_body.get("required"),
                    "content_types": list(content.keys()),
                    "schema": {
                        content_type: short_schema(media.get("schema"))
                        for content_type, media in content.items()
                        if isinstance(media, dict)
                    },
                }

            responses = {}
            for status, response in (operation.get("responses") or {}).items():
                if not isinstance(response, dict):
                    responses[status] = response
                    continue
                content = response.get("content") if isinstance(response.get("content"), dict) else {}
                responses[status] = {
                    "description": response.get("description"),
                    "content_types": list(content.keys()),
                    "schema": {
                        content_type: short_schema(media.get("schema"))
                        for content_type, media in content.items()
                        if isinstance(media, dict)
                    },
                }

            endpoints.append(
                {
                    "method": method_lower.upper(),
                    "path": path,
                    "operationId": operation.get("operationId"),
                    "summary": operation.get("summary"),
                    "description": operation.get("description"),
                    "tags": operation.get("tags", []),
                    "parameters": parameters,
                    "requestBody": request_body,
                    "responses": responses,
                }
            )

    return {
        "document_kind": "openapi" if "openapi" in data else "swagger",
        "fetched_url": source_url,
        "api": {
            "title": info.get("title"),
            "version": info.get("version"),
            "description": info.get("description"),
            "openapi": data.get("openapi"),
            "swagger": data.get("swagger"),
            "servers": servers,
            "host": data.get("host"),
            "basePath": data.get("basePath"),
            "schemes": data.get("schemes"),
            "security": data.get("security"),
            "securitySchemes": security_schemes,
        },
        "endpoint_count": len(endpoints),
        "endpoints": endpoints,
    }


def strip_html_text(text: str) -> str:
    text = re.sub(r"(?is)<(script|style|noscript|svg|canvas)[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?is)<!--.*?-->", " ", text)
    text = re.sub(r"(?i)</?(p|div|section|article|main|header|footer|br|li|tr|h[1-6])[^>]*>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def first_match(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return re.sub(r"\s+", " ", html.unescape(match.group(1))).strip()


def extract_headings(text: str) -> list[dict[str, str]]:
    headings: list[dict[str, str]] = []
    for match in re.finditer(r"(?is)<(h[1-3])[^>]*>(.*?)</\1>", text):
        value = strip_html_text(match.group(2))
        if value:
            headings.append({"level": match.group(1).lower(), "text": value})
        if len(headings) >= 40:
            break
    return headings


def extract_links(text: str, page_url: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for match in re.finditer(r"""(?is)<a\b[^>]*href\s*=\s*["']([^"']+)["'][^>]*>(.*?)</a>""", text):
        href = normalize_candidate(match.group(1), page_url)
        label = strip_html_text(match.group(2))[:160]
        if href:
            links.append({"text": label, "url": href})
        if len(links) >= 80:
            break
    return links


def summarize_html(
    fetch_result: FetchResult,
    text: str,
    timeout: int,
    max_bytes: int,
    text_chars: int,
    api_discovery: str,
) -> dict[str, Any]:
    include_common = api_discovery == "always" or (
        api_discovery == "auto" and page_has_api_hints(text, fetch_result.final_url)
    )
    discovered = discover_spec_urls(text, fetch_result.final_url, include_common_paths=include_common)
    attempts = []
    best_summary = None

    if api_discovery != "never":
        for candidate in discovered[:30]:
            spec_result = fetch_url(candidate, timeout=timeout, max_bytes=max_bytes)
            spec_text = decode_body(spec_result.body)
            data, _, parse_error = load_structured(spec_text, spec_result.content_type, spec_result.final_url)
            attempt = {
                "url": candidate,
                "status": spec_result.status,
                "content_type": spec_result.content_type,
                "error": spec_result.error or parse_error,
            }
            attempts.append(attempt)
            if is_openapi_doc(data):
                summary = summarize_openapi(data, spec_result.final_url)
                summary["source_page_url"] = fetch_result.final_url
                summary["status"] = spec_result.status
                summary["content_type"] = spec_result.content_type
                summary["discovered_specs"] = discovered
                summary["spec_attempts"] = attempts
                if best_summary is None or summary["endpoint_count"] > best_summary["endpoint_count"]:
                    best_summary = summary

    if best_summary:
        return best_summary

    title = first_match(r"<title[^>]*>(.*?)</title>", text)
    description = first_match(
        r"""<meta\s+[^>]*(?:name|property)\s*=\s*["'](?:description|og:description)["'][^>]*content\s*=\s*["']([^"']*)["'][^>]*>""",
        text,
    )
    if description is None:
        description = first_match(
            r"""<meta\s+[^>]*content\s*=\s*["']([^"']*)["'][^>]*(?:name|property)\s*=\s*["'](?:description|og:description)["'][^>]*>""",
            text,
        )

    visible_text = strip_html_text(text)
    return {
        "document_kind": "html",
        "fetched_url": fetch_result.final_url,
        "status": fetch_result.status,
        "content_type": fetch_result.content_type,
        "size_bytes": len(fetch_result.body),
        "title": title,
        "description": description,
        "headings": extract_headings(text),
        "links": extract_links(text, fetch_result.final_url),
        "text_preview": visible_text[:text_chars],
        "discovered_specs": discovered,
        "spec_attempts": attempts,
    }


def looks_binary(content_type: str, body: bytes) -> bool:
    lowered = content_type.lower()
    if any(token in lowered for token in ("image/", "audio/", "video/", "application/pdf", "application/octet-stream")):
        return True
    sample = body[:2048]
    return bool(sample and b"\x00" in sample)


def summarize_url(url: str, timeout: int, max_bytes: int, text_chars: int, api_discovery: str) -> dict[str, Any]:
    result = fetch_url(url, timeout=timeout, max_bytes=max_bytes)
    if result.error and not result.body:
        return {
            "document_kind": "error",
            "fetched_url": result.final_url,
            "status": result.status,
            "error": result.error,
        }

    if looks_binary(result.content_type, result.body):
        return {
            "document_kind": "binary",
            "fetched_url": result.final_url,
            "status": result.status,
            "content_type": result.content_type,
            "size_bytes": len(result.body),
            "notes": ["Binary content detected. Use a file-specific reader for full content extraction."],
        }

    text = decode_body(result.body)
    data, structured_kind, parse_error = load_structured(text, result.content_type, result.final_url)
    if is_openapi_doc(data):
        summary = summarize_openapi(data, result.final_url)
        summary["status"] = result.status
        summary["content_type"] = result.content_type
        summary["size_bytes"] = len(result.body)
        return summary
    if data is not None:
        return {
            "document_kind": structured_kind or "structured",
            "fetched_url": result.final_url,
            "status": result.status,
            "content_type": result.content_type,
            "size_bytes": len(result.body),
            "structured_summary": structured_summary(data),
            "preview": text[:text_chars],
        }

    lowered_type = result.content_type.lower()
    if "html" in lowered_type or re.search(r"(?is)<html|<body|<!doctype html|swagger-ui|redoc", text):
        summary = summarize_html(
            result,
            text,
            timeout=timeout,
            max_bytes=max_bytes,
            text_chars=text_chars,
            api_discovery=api_discovery,
        )
        if parse_error:
            summary.setdefault("notes", []).append(parse_error)
        return summary

    return {
        "document_kind": "text",
        "fetched_url": result.final_url,
        "status": result.status,
        "content_type": result.content_type,
        "size_bytes": len(result.body),
        "parse_error": parse_error,
        "text_preview": text[:text_chars],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="URL to fetch and summarize")
    parser.add_argument("--output", "-o", help="Write JSON summary to this file")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--text-chars", type=int, default=DEFAULT_TEXT_CHARS)
    parser.add_argument(
        "--api-discovery",
        choices=("auto", "always", "never"),
        default="auto",
        help="OpenAPI/Swagger discovery mode for HTML pages",
    )
    args = parser.parse_args(argv)

    summary = summarize_url(
        args.url,
        timeout=args.timeout,
        max_bytes=args.max_bytes,
        text_chars=args.text_chars,
        api_discovery=args.api_discovery,
    )
    rendered = json.dumps(summary, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered)
            handle.write("\n")
    else:
        print(rendered)

    return 0 if summary.get("document_kind") != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
