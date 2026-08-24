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

# 断言模式 → ope_key（执行器 assert_* 集合）
_ASSERT_KEY = {
    'visible': 'assert_visible',
    'contain_text': 'assert_contain_text',
    'enabled': 'assert_enabled',
    'url': 'assert_url',
}

_MAX_NAME = 64

_VALID_LOCATOR_TYPES = {t for t, _label in UiElement.LOCATOR_TYPE_CHOICES}


def _element_name(action_type: str, selector: dict | None) -> str:
    label = 'element'
    if selector:
        label = str(selector.get('name') or selector.get('locator_value') or 'element')
    label = ' '.join(label.split())
    op = {'click': '点击', 'fill': '输入', 'check': '勾选', 'uncheck': '取消勾选',
          'press': '按键'}.get(action_type, action_type)
    name = f'录制-{op}-{label}'
    return name[:_MAX_NAME]


def _get_or_create_element(*, page: UiPage, user, action_type: str, selector: dict) -> tuple[UiElement, bool]:
    """按 (page, locator_type, locator_value) 复用元素。"""
    locator_type = str(selector.get('locator_type') or 'xpath')
    locator_value = str(selector.get('locator_value') or '')
    locator_type = locator_type if locator_type in _VALID_LOCATOR_TYPES else 'xpath'
    if not locator_value:
        return None, False  # 无选择器的动作（如 goto）不走元素

    existing = UiElement.objects.filter(
        page=page,
        locator_type=locator_type,
        locator_value=locator_value,
    ).order_by('id').first()
    if existing:
        return existing, False

    element = UiElement.objects.create(
        page=page,
        name=_element_name(action_type, selector),
        locator_type=locator_type,
        locator_value=locator_value,
        creator=user,
    )
    return element, True


@transaction.atomic
def apply_recorded_actions(
    *,
    page: UiPage,
    page_step: UiPageSteps,
    user,
    actions: list[dict[str, Any]],
) -> dict[str, Any]:
    """把录制动作解析入库：元素（复用/新建）+ 步骤明细（追加）。

    返回统计：
        {'elements_created', 'elements_updated', 'steps_created', 'actions_count'}
    """
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