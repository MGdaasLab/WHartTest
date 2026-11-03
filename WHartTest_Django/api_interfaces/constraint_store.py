"""接口参数约束的持久化服务。

导入/更新接口文档时，把文档解析出的参数约束（constraint_extractor 的输出）
按接口固化到 ApiInterfaceConstraint；AI 生成用例时通过 skill 工具按接口查询，
无需再次上传文档。纯确定性代码，无 AI 参与。
"""
from __future__ import annotations

import logging
from typing import Any

from .constraint_extractor import extract_constraints_from_document
from .models import ApiInterface, ApiInterfaceConstraint

logger = logging.getLogger(__name__)


def build_constraint_payload(
    extract_result: dict[str, Any],
    interface: ApiInterface,
) -> dict[str, Any] | None:
    """从 extract_constraints_from_document 结果中取出指定接口的约束载荷。

    未匹配文档时返回 None（调用方应删除旧约束，避免陈旧数据误导生成）。
    """
    for item in extract_result.get('interfaces', []):
        if item.get('interface_id') == interface.id and item.get('matched'):
            payload = {key: value for key, value in item.items() if key != 'matched'}
            if payload.get('truncated'):
                logger.info(
                    'constraints truncated for interface %s (field limit reached)',
                    interface.id,
                )
            return payload
    return None


def store_interface_constraints(
    *,
    project,
    document,
    document_format: str = '',
    document_version: str = '',
    document_name: str = '',
    interface_ids: list[int] | None = None,
) -> int:
    """解析文档并把约束写入/更新 ApiInterfaceConstraint。

    Args:
        project: 项目实例，约束只作用于该项目下的 HTTP 接口。
        document: 已归一化为 OpenAPI 的文档 dict。
        interface_ids: 只处理这些接口；为空时处理项目下全部 HTTP 接口。

    Returns:
        写入的约束条数。
    """
    from .constraint_extractor import extract_constraints_from_document

    queryset = ApiInterface.objects.filter(project=project, type=ApiInterface.TYPE_HTTP)
    if interface_ids is not None:
        queryset = queryset.filter(id__in=interface_ids)
    interfaces = list(queryset)
    if not interfaces:
        return 0

    targets = [
        {
            'interface_id': item.id,
            'name': item.name,
            'method': (item.method or '').upper(),
            'url': item.url or '',
        }
        for item in interfaces
    ]
    try:
        result = extract_constraints_from_document(
            document,
            targets,
            filename=document_name,
            source_type=document_format,
        )
    except Exception as exc:
        # 约束提取失败不阻断导入主流程，接口本体已落库
        logger.warning('extract constraints during import failed: %s', exc)
        return 0

    stored = 0
    matched_ids: set[int] = set()
    by_id = {item.id: item for item in interfaces}
    for item in result.get('interfaces', []):
        interface_id = item.get('interface_id')
        interface = by_id.get(interface_id)
        if interface is None or not item.get('matched'):
            continue
        matched_ids.add(interface_id)
        payload = {key: value for key, value in item.items() if key != 'matched'}
        ApiInterfaceConstraint.objects.update_or_create(
            interface=interface,
            defaults={
                'document_format': document_format or result.get('format', ''),
                'document_version': document_version or result.get('version', ''),
                'document_name': document_name[:255],
                'matched': True,
                'constraints': payload,
            },
        )
        stored += 1

    # 本次文档中未匹配到的接口：删除陈旧约束，防止文档变更后残留旧结构
    stale_ids = [item.id for item in interfaces if item.id not in matched_ids]
    if stale_ids:
        deleted, _ = ApiInterfaceConstraint.objects.filter(interface_id__in=stale_ids).delete()
        if deleted:
            logger.info('removed %s stale constraint records: %s', deleted, stale_ids)

    return stored
