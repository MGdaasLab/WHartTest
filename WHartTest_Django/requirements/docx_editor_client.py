from __future__ import annotations

from pathlib import Path

import requests
from django.conf import settings


class DocxEditorClientError(RuntimeError):
    pass


class DocxEditorNotConfiguredError(DocxEditorClientError):
    pass


def create_docx_editor_session(document, pushback_url: str) -> dict:
    base_url = str(getattr(settings, "DOCX_EDITOR_BASE_URL", "") or "").strip().rstrip("/")
    public_base_url = str(getattr(settings, "DOCX_EDITOR_PUBLIC_BASE_URL", "") or "").strip().rstrip("/")
    service_key = str(getattr(settings, "DOCX_EDITOR_SERVICE_KEY", "") or "").strip()
    if not base_url:
        raise DocxEditorNotConfiguredError("在线编辑服务未配置，请联系管理员配置 DOCX Editor 服务。")
    if not service_key:
        raise DocxEditorNotConfiguredError("在线编辑服务未配置，请联系管理员配置 DOCX Editor 服务。")
    if not document.file:
        raise DocxEditorClientError("该文档没有原始文件")
    file_name = str(getattr(document.file, "name", "") or "").strip()
    if not file_name:
        raise DocxEditorClientError("该文档没有原始文件")
    try:
        exists = document.file.storage.exists(file_name)
    except Exception:
        exists = False
    if not exists:
        raise DocxEditorClientError("主项目中的源文件不存在，请重新上传该文档后再试。")

    endpoint = f"{base_url}/api/integration/external-documents/upsert-and-launch"
    headers = {
        "Authorization": f"Bearer {service_key}",
        "User-Agent": "wharttest-docx-editor-client",
    }
    if public_base_url:
        headers["X-Docx-Editor-Public-Base-Url"] = public_base_url
    data = {
        "source_system": "wharttest",
        "source_document_id": str(document.id),
        "title": document.title,
        "filename": Path(file_name).name,
        "pushback_url": pushback_url,
    }
    if document.updated_at:
        data["source_updated_at"] = document.updated_at.isoformat()

    content_type = (
        "application/msword"
        if document.document_type == "doc"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    with open(document.file.path, "rb") as handle:
        files = {
            "file": (
                Path(file_name).name,
                handle,
                content_type,
            )
        }
        try:
            response = requests.post(
                endpoint,
                headers=headers,
                data=data,
                files=files,
                timeout=60,
            )
        except requests.RequestException as exc:
            raise DocxEditorClientError(
                "在线编辑服务不可用，请确认 DOCX Editor 服务已部署并正常运行。"
            ) from exc

    try:
        payload = response.json()
    except ValueError:
        payload = None

    if response.status_code >= 400:
        detail = ""
        if isinstance(payload, dict):
            detail = str(payload.get("error") or payload.get("detail") or "").strip()
        if not detail and response.status_code in (502, 503):
            raise DocxEditorClientError(
                "在线编辑服务不可用，请确认 DOCX Editor 服务已部署并正常运行。"
            )
        if not detail:
            detail = (response.text or "").strip()[:1000]
        raise DocxEditorClientError(detail or f"DOCX Editor 返回异常状态码 {response.status_code}")

    if not isinstance(payload, dict):
        raise DocxEditorClientError("DOCX Editor 返回了无法识别的响应")
    if not str(payload.get("launch_url", "")).strip():
        raise DocxEditorClientError("DOCX Editor 未返回 launch_url")
    return payload
