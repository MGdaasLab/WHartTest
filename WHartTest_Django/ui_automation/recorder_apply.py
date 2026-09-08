"""录制动作 → 页面元素 / 页面步骤 入库解析。

输入为录制 Node 进程返回的动作列表：
    {'type': 'click'|'fill'|'check'|'uncheck'|'press', 'selector': {...}}
    {'type': 'goto', 'url': '...'}
    {'type': 'assert', 'mode': 'visible'|'contain_text'|'enabled'|'url', 'selector'?, 'value'?}

元素按 (page, locator_type, locator_value) 复用（页面内同一选择器不重复建元素）；
步骤明细追加到目标页面步骤末尾（step_sort 续排），操作类型与执行器
（WHartTest_Actuator executor.py）的 ope_key 词汇表对齐。
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from .models import (
    UiElement,
    UiPage,
    UiPageSteps,
    UiPageStepsDetailed,
)

logger = logging.getLogger('ui_automation')

# 步骤类型（与 UiPageStepsDetailed.STEP_TYPE_CHOICES 对齐）
STEP_TYPE_ELEMENT = 0   # 元素操作
STEP_TYPE_ASSERT = 1    # 断言操作

# 元素操作 → ope_key（执行器 executor.py element_operations）
_OP_KEY = {
    'click': 'click',
    'fill': 'fill',
    'check': 'check',
    'uncheck': 'uncheck',
    'press': 'press',
}

# 断言模式 → ope_key（执行器 assert_* 集合，三类：元素状态/内容校验/页面校验）
_ASSERT_KEY = {
    # 元素状态（无需期望值）
    'visible': 'assert_visible',
    'hidden': 'assert_hidden',
    'enabled': 'assert_enabled',
    'disabled': 'assert_disabled',
    'checked': 'assert_checked',
    # 内容校验（需要期望值 + 元素）
    'text': 'assert_text',
    'contain_text': 'assert_contain_text',
    'value': 'assert_value',
    'count': 'assert_count',
    # 页面校验（需要期望值，无需元素）
    'url': 'assert_url',
    'title': 'assert_title',
}

_MAX_NAME = 64

_VALID_LOCATOR_TYPES = {t for t, _label in UiElement.LOCATOR_TYPE_CHOICES}


def _element_name(action_type: str, selector: dict | None) -> str:
    """元素命名：优先录制端生成的语义名（业务语义+控件类型，如"用户名输入框"），
    无语义名时按操作类型兜底（"点击-提交"）。名称不含用户输入值与页面名。"""
    label = ''
    if selector:
        label = str(selector.get('name') or '').strip()
    if label:
        return label[:_MAX_NAME]
    fallback = 'element'
    if selector:
        fallback = str(selector.get('locator_value') or 'element')[:20]
    op = {'click': '点击', 'fill': '输入', 'check': '勾选', 'uncheck': '取消勾选',
          'press': '按键', 'assert': '断言', 'upload': '上传'}.get(action_type, action_type)
    return f'{op}-{fallback}'[:_MAX_NAME]


def _dedupe_element_name(page: UiPage, name: str) -> str:
    """同页面元素名称唯一：冲突时追加序号（"提交按钮 2"）。"""
    base = name[:_MAX_NAME]
    if not UiElement.objects.filter(page=page, name=base).exists():
        return base
    suffix = 2
    while True:
        text = f'{base} {suffix}'
        if len(text) > _MAX_NAME:
            text = f'{base[:_MAX_NAME - len(text)]}{suffix}'
        if not UiElement.objects.filter(page=page, name=text).exists():
            return text
        suffix += 1


def _get_or_create_element(*, page: UiPage, user, action_type: str, selector: dict) -> tuple[UiElement, bool]:
    """按 (page, locator_type, locator_value) 复用元素。

    录制端候选链的第 2/3 位（locator_type_2/3）作为备用定位一并入库，
    执行器按 主→备1→备2 依次尝试；复用已有元素时仅补全缺失的备用定位，
    不覆盖手工维护的现有值。
    """
    locator_type = str(selector.get('locator_type') or 'xpath')
    locator_value = str(selector.get('locator_value') or '')
    locator_type = locator_type if locator_type in _VALID_LOCATOR_TYPES else 'xpath'
    if not locator_value:
        return None, False  # 无选择器的动作（如 goto/wait）不走元素

    backups: list[tuple[int, str, str]] = []
    for idx in (2, 3):
        l_type = str(selector.get(f'locator_type_{idx}') or '')
        l_value = str(selector.get(f'locator_value_{idx}') or '').strip()
        if l_type in _VALID_LOCATOR_TYPES and l_value:
            backups.append((idx, l_type, l_value))

    # 录制端自动识别的 iframe 元素：启用 is_iframe 并填充 iframe 定位链
    iframe_fields: dict[str, Any] = {}
    if bool(selector.get('is_iframe')):
        iframe_locator = str(selector.get('iframe_locator') or '').strip()
        if iframe_locator:
            iframe_fields = {'is_iframe': True, 'iframe_locator': iframe_locator}

    existing = UiElement.objects.filter(
        page=page,
        locator_type=locator_type,
        locator_value=locator_value,
    ).order_by('id').first()
    if existing:
        updates = {
            f'locator_type_{idx}': l_type
            for idx, l_type, _v in backups
            if not getattr(existing, f'locator_type_{idx}')
        }
        updates.update({
            f'locator_value_{idx}': l_value
            for idx, _t, l_value in backups
            if not getattr(existing, f'locator_type_{idx}')
        })
        # 老数据缺 iframe 标识时补全（手工维护的既有值不覆盖）
        if iframe_fields and not existing.is_iframe:
            updates.update(iframe_fields)
        if updates:
            UiElement.objects.filter(id=existing.id).update(**updates)
        return existing, False

    name = _dedupe_element_name(page, _element_name(action_type, selector))
    element = UiElement.objects.create(
        page=page,
        name=name,
        locator_type=locator_type,
        locator_value=locator_value,
        creator=user,
        **{f'locator_type_{idx}': l_type for idx, l_type, _v in backups},
        **{f'locator_value_{idx}': l_value for idx, _t, l_value in backups},
        **iframe_fields,
    )
    return element, True


def _coalesce_consecutive_fills(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """兜底规整：连续同元素的 fill 动作合并为一条（取最终值）。

    录制端已做实时合并，此处防御极端场景（输入过快/事件乱序等）导致的碎片，
    保证入库的步骤明细不会出现 a→ad→adm… 多条 fill。
    """
    merged: list[dict[str, Any]] = []
    for action in actions:
        if (
            action.get('type') == 'fill'
            and merged
            and merged[-1].get('type') == 'fill'
            and merged[-1].get('selector') == action.get('selector')
        ):
            merged[-1] = {**merged[-1], 'value': action.get('value')}
            continue
        merged.append(action)
    return merged


@transaction.atomic
def _valid_auth_state_id(auth_state_id):
    """校验登录态仍存在（录制过程中可能被删除）：无效返回 None，避免外键 500。"""
    if not auth_state_id:
        return None
    from .models import UiAuthState
    try:
        exists = UiAuthState.objects.filter(id=int(auth_state_id)).exists()
    except (TypeError, ValueError):
        return None
    return int(auth_state_id) if exists else None


def apply_recorded_actions(
    *,
    page: UiPage,
    page_step: UiPageSteps,
    user,
    actions: list[dict[str, Any]],
    auth_state_id: int | None = None,
) -> dict[str, Any]:
    """把录制动作解析入库：元素（复用/新建）+ 步骤明细（追加）。

    返回统计：
        {'elements_created', 'elements_updated', 'steps_created', 'actions_count'}
    """
    actions = _coalesce_consecutive_fills(actions)
    # 录制表单选择的登录态：绑定到本次录制的页面步骤（录制中可能已被删除，无效则不绑定）
    valid_auth = _valid_auth_state_id(auth_state_id)
    if valid_auth and page_step.auth_state_id != valid_auth:
        UiPageSteps.objects.filter(id=page_step.id).update(auth_state_id=valid_auth)
    elements_created = 0
    elements_updated = 0
    steps_created = 0
    actions_count = len(actions)

    last_sort = (
        UiPageStepsDetailed.objects.filter(page_step=page_step)
        .order_by('-step_sort')
        .values_list('step_sort', flat=True)
        .first()
    )
    next_sort = (last_sort if last_sort is not None else -1) + 1

    for action in actions:
        action_type = str(action.get('type') or '')
        if action_type == 'goto':
            UiPageStepsDetailed.objects.create(
                page_step=page_step,
                step_type=STEP_TYPE_ELEMENT,
                ope_key='goto',
                ope_value={'url': str(action.get('url') or '')},
                step_sort=next_sort,
            )
            next_sort += 1
            steps_created += 1
            continue

        if action_type == 'wait':
            seconds = float(action.get('seconds') or 1)
            UiPageStepsDetailed.objects.create(
                page_step=page_step,
                step_type=STEP_TYPE_ELEMENT,
                ope_key='wait',
                # 平台 wait 步骤 timeout 单位为秒（执行器 _parse_wait_timeout）
                ope_value={'timeout': int(seconds)},
                step_sort=next_sort,
            )
            next_sort += 1
            steps_created += 1
            continue

        if action_type == 'upload':
            selector = action.get('selector') or {}
            element, created = _get_or_create_element(
                page=page, user=user, action_type='upload', selector=selector,
            )
            if created:
                elements_created += 1
            elif element is not None:
                elements_updated += 1
            try:
                file_id = int(action.get('file_id'))
            except (TypeError, ValueError):
                file_id = None
            file_name = str(action.get('file_name') or '').strip()
            # 平台 upload 步骤三种数据并存：
            # value=file_id:N 供执行器 input_value 提取并 resolve 文件路径；
            # file_id 供步骤详情表单/引用管理读取；file_name 供执行器以原名上传。
            ope_value = {}
            if file_id:
                ope_value = {
                    'file_id': file_id,
                    'value': f'file_id:{file_id}',
                    'file_name': file_name,
                }
            upload_detail = UiPageStepsDetailed.objects.create(
                page_step=page_step,
                step_type=STEP_TYPE_ELEMENT,
                element=element,
                ope_key='upload',
                ope_value=ope_value,
                step_sort=next_sort,
            )
            next_sort += 1
            steps_created += 1
            # 同步文件引用（延迟导入避免循环），保证删除步骤时能清理平台文件引用
            if file_id:
                try:
                    from .views import _sync_upload_step_file_reference
                    _sync_upload_step_file_reference(upload_detail, user)
                except Exception:
                    pass
            continue

        if action_type == 'assert':
            mode = str(action.get('mode') or 'visible')
            ope_key = _ASSERT_KEY.get(mode, 'assert_visible')
            ope_value = {'expected': str(action.get('value') or '')} if action.get('value') else {}
            selector = action.get('selector') or {}
            element, created = _get_or_create_element(
                page=page, user=user, action_type='assert', selector=selector,
            )
            if created:
                elements_created += 1
            elif element is not None:
                elements_updated += 1
            UiPageStepsDetailed.objects.create(
                page_step=page_step,
                step_type=STEP_TYPE_ASSERT,
                element=element,
                ope_key=ope_key,
                ope_value=ope_value,
                step_sort=next_sort,
            )
            next_sort += 1
            steps_created += 1
            continue

        ope_key = _OP_KEY.get(action_type)
        if not ope_key:
            logger.info('[recorder] 忽略未知动作类型: %s', action_type)
            continue

        selector = action.get('selector') or {}
        element, created = _get_or_create_element(
            page=page, user=user, action_type=action_type, selector=selector,
        )
        if created:
            elements_created += 1
        elif element is not None:
            elements_updated += 1

        ope_value: dict[str, Any] = {}
        if action_type == 'fill':
            ope_value = {'value': str(action.get('value') or '')}
        elif action_type == 'press':
            ope_value = {'key': str(action.get('key') or 'Enter')}

        UiPageStepsDetailed.objects.create(
            page_step=page_step,
            step_type=STEP_TYPE_ELEMENT,
            element=element,
            ope_key=ope_key,
            ope_value=ope_value,
            step_sort=next_sort,
        )
        next_sort += 1
        steps_created += 1

    return {
        'elements_created': elements_created,
        'elements_updated': elements_updated,
        'steps_created': steps_created,
        'actions_count': actions_count,
    }

