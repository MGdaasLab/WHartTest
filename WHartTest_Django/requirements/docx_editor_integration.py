from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Any

import requests
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction

from .models import RequirementDocument
from .services import DocumentProcessor


logger = logging.getLogger(__name__)


class DocxEditorIntegrationError(RuntimeError):
    """Raised when the docx-editor integration request cannot be completed."""


class DocxEditorNotConfiguredError(DocxEditorIntegrationError):
    """Raised when the main project has not configured docx-editor access."""


def _setting_str(name: str) -> str:
    return str(getattr(settings, name, "") or "").strip()


def _normalize_base_url(url: str) -> str:
    return str(url or "").strip().rstrip("/")


def _extract_message(payload: Any, fallback: str) -> str:
    if isinstance(payload, dict):
        for key in ("detail", "error", "message"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        errors = payload.get("errors")
        if isinstance(errors, dict):
            for key in ("detail", "error", "message"):
                value = errors.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

        nested = payload.get("data")
        if isinstance(nested, dict):
            for key in ("detail", "error", "message"):
                value = nested.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

    if isinstance(payload, str) and payload.strip():
        return payload.strip()

    return fallback


def _ensure_source_file_exists(document: RequirementDocument) -> None:
    file_name = str(getattr(document.file, "name", "") or "").strip()
    if not file_name:
        raise DocxEditorIntegrationError("当前文档没有源文件，无法发起在线编辑。")

    try:
        exists = document.file.storage.exists(file_name)
    except Exception:
        exists = False

    if not exists:
        raise DocxEditorIntegrationError(
            "主项目中的源文件不存在，可能已被删除或丢失，请重新上传该文档后再试。"
        )


def _extract_launch_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        nested = payload.get("data")
        if isinstance(nested, dict) and nested.get("launch_url"):
            return nested
        return payload
    return {}


def launch_requirement_document_in_docx_editor(
    document: RequirementDocument,
) -> dict[str, Any]:
    base_url = _normalize_base_url(_setting_str("DOCX_EDITOR_BASE_URL"))
    service_key = _setting_str("DOCX_EDITOR_SERVICE_KEY")
    public_base_url = _normalize_base_url(_setting_str("DOCX_EDITOR_PUBLIC_BASE_URL"))

    if not base_url or not service_key:
        raise DocxEditorNotConfiguredError(
            "在线编辑功能未接入，请先在主项目后端配置 DOCX_EDITOR_BASE_URL 和 DOCX_EDITOR_SERVICE_KEY。"
        )

    if document.document_type not in {"doc", "docx"}:
        raise DocxEditorIntegrationError("当前文档类型不支持在线编辑，仅支持 .doc / .docx。")

    if not document.file:
        raise DocxEditorIntegrationError("当前文档没有源文件，无法发起在线编辑。")
    _ensure_source_file_exists(document)

    request_url = f"{base_url}/api/integration/external-documents/upsert-and-launch"
    filename = Path(document.file.name).name
    content_type = (
        mimetypes.guess_type(filename)[0]
        or "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    headers = {"Authorization": f"Bearer {service_key}"}
    if public_base_url:
        headers["X-Docx-Editor-Public-Base-Url"] = public_base_url

    data = {
        "source_system": "wharttest",
        "source_document_id": str(document.id),
        "title": document.title,
        "filename": filename,
        "pushback_url": f"/api/requirements/documents/{document.id}/upload-edited-file/",
    }
    if document.updated_at:
        data["source_updated_at"] = document.updated_at.isoformat()

    try:
        document.file.open("rb")
        response = requests.post(
            request_url,
            headers=headers,
            data=data,
            files={"file": (filename, document.file.file, content_type)},
            timeout=60,
        )
    except requests.RequestException as exc:
        logger.exception("docx-editor launch request failed")
        raise DocxEditorIntegrationError(
            "DOCX Editor 服务不可达，请检查 DOCX_EDITOR_BASE_URL 配置和 docx-editor 服务状态。"
        ) from exc
    finally:
        try:
            document.file.close()
        except Exception:
            pass

    try:
        payload = response.json()
    except ValueError:
        payload = response.text

    if response.status_code >= 400:
        detail = _extract_message(payload, "")
        if not detail and response.status_code in (502, 503):
            raise DocxEditorIntegrationError(
                "在线编辑服务不可用，请确认 DOCX Editor 服务已部署并正常运行。"
            )
        raise DocxEditorIntegrationError(
            detail or f"docx-editor 返回异常状态码: {response.status_code}"
        )

    launch_payload = _extract_launch_payload(payload)
    launch_url = str(launch_payload.get("launch_url") or "").strip()
    if not launch_url:
        raise DocxEditorIntegrationError("docx-editor 未返回可访问的 launch_url。")

    return launch_payload


def replace_requirement_document_with_edited_file(
    document: RequirementDocument,
    upload: UploadedFile,
) -> RequirementDocument:
    suffix = Path(upload.name).suffix.lower()
    if suffix not in {".doc", ".docx"}:
        raise ValueError("仅支持回传 .doc / .docx 文件。")

    processor = DocumentProcessor()
    old_file_name = str(document.file.name or "").strip() if document.file else ""
    old_image_names = [
        image_name
        for image_name in document.images.values_list("image_file", flat=True)
        if image_name
    ]

    with transaction.atomic():
        document.review_reports.all().delete()
        document.modules.all().delete()
        document.images.all().delete()

        filename = Path(upload.name).name
        document.file.save(filename, upload, save=False)
        document.document_type = suffix.lstrip(".")
        document.content = ""
        document.word_count = 0
        document.page_count = 0
        document.has_images = False
        document.image_count = 0
        document.last_split_level = 0
        document.status = "uploaded"

        extracted_content = processor.extract_content(document)
        processed_content = (
            processor.preprocess_content(extracted_content) if extracted_content else ""
        )
        document.content = processed_content
        document.word_count = len(processed_content)
        document.page_count = max(1, (len(processed_content) // 500) + 1) if processed_content else 0
        document.save()

    if old_file_name and old_file_name != document.file.name:
        default_storage.delete(old_file_name)

    current_image_names = {
        image_name
        for image_name in document.images.values_list("image_file", flat=True)
        if image_name
    }
    for image_name in old_image_names:
        if image_name not in current_image_names:
            default_storage.delete(image_name)

    return document
