"""AI 生成接口测试用例会话的工具守护中间件。

单 message 批量生成场景下，模型可能发生两类漂移：
1. 工具漂移：把单接口用例调 create_testcase（场景用例工具）保存，落错模块；
2. 参数漂移：create_interface_case 时误传 group 字段，导致用例落进分组而非主接口归属。

本中间件在执行层（wrap_tool_call）拦截上述调用：
- 禁用工具直接返回错误消息（模型收到后可立即自愈改用正确工具）；
- 参数漂移静默剥除后放行（无需打断模型）。

- 标记来源：前端在 message 头部注入 ``wharttest:generation_mode=interface_case``，
agent_loop_view 检测后通过 detect_generation_mode 判定模式并挂载对应中间件。
UI 模式（``wharttest:generation_mode=ui_case``）挂载 GenerationUiCaseGuardMiddleware，
拦截模型把 UI 用例误存到接口自动化的工具漂移。
自愈模式（``wharttest:generation_mode=self_heal``）挂载 SelfHealGuardMiddleware，
约束自愈会话只能做查询与最小化修复编辑，禁止删除与结构级变更。
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from langchain.agents.middleware import AgentMiddleware

logger = logging.getLogger(__name__)

# 前端注入的生成模式标记
GENERATION_MODE_MARKER = "wharttest:generation_mode=interface_case"
UI_CASE_GENERATION_MARKER = "wharttest:generation_mode=ui_case"
SELF_HEAL_MARKER = "wharttest:generation_mode=self_heal"

# 生成模式检测结果
GENERATION_MODE_INTERFACE_CASE = "interface_case"
GENERATION_MODE_UI_CASE = "ui_case"
GENERATION_MODE_SELF_HEAL = "self_heal"

# 单接口生成会话中禁用的场景用例工具（工具名 -> 提示改用的正确工具）
FORBIDDEN_TOOL_ALTERNATIVES = {
    "create_testcase": "create_interface_case",
    "update_testcase": "update_interface_case",
    "run_testcase": "run_interface_case",
    "batch_run_testcases": "run_interface_case",
    "copy_testcase": "copy_interface_case",
    "delete_testcase": "delete_interface_case",
    "delete_testcase_step": "（单接口用例步骤直接通过 update_interface_case 整体更新 steps_info）",
    "update_testcase_step": "update_interface_case",
    "reorder_testcase_steps": "update_interface_case",
}


def should_guard_generation_prompt(message_text: str | None) -> bool:
    """检测 message 是否携带单接口生成模式标记。"""
    if not message_text:
        return False
    return GENERATION_MODE_MARKER in str(message_text)


def detect_generation_mode(message_text: str | None) -> str | None:
    """检测 message 携带的生成模式标记，返回模式名或 None。

    同时携带多个标记时按 interface_case 优先处理（历史行为保持不变）。
    """
    if not message_text:
        return None
    text = str(message_text)
    if GENERATION_MODE_MARKER in text:
        return GENERATION_MODE_INTERFACE_CASE
    if UI_CASE_GENERATION_MARKER in text:
        return GENERATION_MODE_UI_CASE
    if SELF_HEAL_MARKER in text:
        return GENERATION_MODE_SELF_HEAL
    return None


def _extract_action_and_payload(request: Any) -> tuple[str, dict[str, Any]]:
    """从工具调用请求中提取动作名与 payload 参数（适配 execute_skill_script 系工具）。"""
    tool_call = getattr(request, "tool_call", None) or {}
    args = tool_call.get("args") or {}
    command = str(args.get("command") or "")

    action = ""
    payload: dict[str, Any] = {}
    if command:
        # 解析 --action xxx 与 --payload '{"..."}'（payload 支持 @文件，此处仅处理内联 JSON）
        import json
        import shlex

        try:
            tokens = shlex.split(command)
        except ValueError:
            tokens = command.split()
        for index, token in enumerate(tokens):
            if token == "--action" and index + 1 < len(tokens):
                action = tokens[index + 1]
            if token == "--payload" and index + 1 < len(tokens):
                raw = tokens[index + 1]
                if raw.startswith("{"):
                    try:
                        parsed = json.loads(raw)
                        if isinstance(parsed, dict):
                            payload = parsed
                    except json.JSONDecodeError:
                        pass
    return action, payload


class GenerationInterfaceCaseGuardMiddleware(AgentMiddleware):
    """单接口用例生成会话的工具守护：拦截工具漂移与参数漂移。"""

    def __init__(self) -> None:
        super().__init__()
        self._drift_counts = {"tool": 0, "param": 0}

    @property
    def drift_counts(self) -> dict[str, int]:
        return dict(self._drift_counts)

    def wrap_tool_call(
        self,
        request: Any,
        handler: Callable[[Any], Any],
    ) -> Any:
        action, payload = _extract_action_and_payload(request)
        if not action:
            return handler(request)

        # 1. 工具漂移：禁用场景用例工具，返回可自愈的错误消息
        alternative = FORBIDDEN_TOOL_ALTERNATIVES.get(action)
        if alternative:
            self._drift_counts["tool"] += 1
            logger.warning(
                "[GenerationGuard] 拦截工具漂移: %s（单接口生成会话禁用）",
                action,
            )
            tool_name = getattr(getattr(request, "tool_call", None), "get", lambda *_: "")("name") or "tool"
            return _build_error_tool_message(
                request,
                tool_name,
                (
                    f"当前会话是【单接口用例生成】任务，禁止使用 {action}（场景用例工具）。"
                    f"请改用 {alternative} 保存单接口用例（ApiInterfaceCase）。"
                ),
            )

        # 2. 参数漂移：create/update_interface_case 带了 group 字段 → 剥除后放行
        if action in ("create_interface_case", "update_interface_case") and "group" in payload:
            self._drift_counts["param"] += 1
            payload.pop("group", None)
            logger.warning(
                "[GenerationGuard] 剥除 create/update_interface_case 的 group 字段（单接口用例按主接口归属）",
            )
            import json
            import shlex

            tool_call = getattr(request, "tool_call", None) or {}
            args = dict(tool_call.get("args") or {})
            command = str(args.get("command") or "")
            if command and "--payload" in command:
                try:
                    tokens = shlex.split(command)
                    for index, token in enumerate(tokens):
                        if token == "--payload" and index + 1 < len(tokens):
                            tokens[index + 1] = json.dumps(payload, ensure_ascii=False)
                            break
                    new_command = " ".join(tokens)
                    args["command"] = new_command
                    request = request.override(tool_call={**tool_call, "args": args})
                except Exception:  # noqa: BLE001 - 剥除失败时按原样放行
                    logger.warning("[GenerationGuard] group 剥除改写失败，按原 payload 放行")

        return handler(request)

    async def awrap_tool_call(
        self,
        request: Any,
        handler: Callable[[Any], Any],
    ) -> Any:
        action, payload = _extract_action_and_payload(request)
        if not action:
            return await handler(request)

        alternative = FORBIDDEN_TOOL_ALTERNATIVES.get(action)
        if alternative:
            self._drift_counts["tool"] += 1
            logger.warning(
                "[GenerationGuard] 拦截工具漂移: %s（单接口生成会话禁用）",
                action,
            )
            tool_name = getattr(getattr(request, "tool_call", None), "get", lambda *_: "")("name") or "tool"
            return _build_error_tool_message(
                request,
                tool_name,
                (
                    f"当前会话是【单接口用例生成】任务，禁止使用 {action}（场景用例工具）。"
                    f"请改用 {alternative} 保存单接口用例（ApiInterfaceCase）。"
                ),
            )

        if action in ("create_interface_case", "update_interface_case") and "group" in payload:
            self._drift_counts["param"] += 1
            payload.pop("group", None)
            logger.warning(
                "[GenerationGuard] 剥除 create/update_interface_case 的 group 字段（单接口用例按主接口归属）",
            )
            import json
            import shlex

            tool_call = getattr(request, "tool_call", None) or {}
            args = dict(tool_call.get("args") or {})
            command = str(args.get("command") or "")
            if command and "--payload" in command:
                try:
                    tokens = shlex.split(command)
                    for index, token in enumerate(tokens):
                        if token == "--payload" and index + 1 < len(tokens):
                            tokens[index + 1] = json.dumps(payload, ensure_ascii=False)
                            break
                    new_command = " ".join(tokens)
                    args["command"] = new_command
                    request = request.override(tool_call={**tool_call, "args": args})
                except Exception:  # noqa: BLE001
                    logger.warning("[GenerationGuard] group 剥除改写失败，按原 payload 放行")

        return await handler(request)

def _build_error_tool_message(request: Any, tool_name: str, text: str) -> Any:
    """构造工具错误消息（ToolMessage 兼容结构），让模型收到后自愈。"""
    from langchain_core.messages import ToolMessage

    tool_call = getattr(request, "tool_call", None) or {}
    call_id = tool_call.get("id") or ""
    return ToolMessage(content=text, tool_call_id=call_id, name=tool_name or "tool", status="error")


# UI 用例生成会话中禁用的接口自动化工具（工具名 -> 引导提示）
UI_CASE_FORBIDDEN_TOOL_HINTS = {
    "create_interface_case": "UI 用例禁止调用 create_interface_case，页面步骤/用例请用 create_page_step / create_testcase 保存",
    "update_interface_case": "UI 用例禁止调用 update_interface_case，请用 update_element / update_page_step / update_testcase 修改 UI 对象",
    "run_interface_case": "UI 用例禁止调用 run_interface_case，试跑请用当前浏览器会话回放用例步骤",
    "copy_interface_case": "UI 用例禁止调用 copy_interface_case",
    "delete_interface_case": "UI 用例禁止调用 delete_interface_case，且本会话禁止删除任何已保存对象",
}


class GenerationUiCaseGuardMiddleware(AgentMiddleware):
    """UI 用例一键生成会话的工具守护：拦截接口自动化工具漂移。

    ui_case 会话中模型可能把 UI 用例误存到接口自动化（create_interface_case /
    run_interface_case 等），此处直接返回可自愈的错误消息引导模型改用
    ui-automation-skill 工具。
    """

    def __init__(self) -> None:
        super().__init__()
        self._drift_count = 0

    @property
    def drift_count(self) -> int:
        return self._drift_count

    def _check(self, request: Any) -> tuple[bool, str]:
        """判定是否拦截。返回 (是否放行, 拦截提示文本)。"""
        action, _ = _extract_action_and_payload(request)
        hint = UI_CASE_FORBIDDEN_TOOL_HINTS.get(action)
        if not hint:
            return True, ""
        self._drift_count += 1
        logger.warning("[GenerationGuard] 拦截 UI 生成会话工具漂移: %s", action)
        tool_call = getattr(request, "tool_call", None) or {}
        tool_name = tool_call.get("name") or "tool"
        return False, f"当前会话是【UI 自动化用例生成】任务，{hint}。"

    def wrap_tool_call(
        self,
        request: Any,
        handler: Callable[[Any], Any],
    ) -> Any:
        allowed, text = self._check(request)
        if allowed:
            return handler(request)
        tool_call = getattr(request, "tool_call", None) or {}
        return _build_error_tool_message(request, tool_call.get("name") or "tool", text)

    async def awrap_tool_call(
        self,
        request: Any,
        handler: Callable[[Any], Any],
    ) -> Any:
        allowed, text = self._check(request)
        if allowed:
            return await handler(request)
        tool_call = getattr(request, "tool_call", None) or {}
        return _build_error_tool_message(request, tool_call.get("name") or "tool", text)


# 自愈会话中禁止的动作（execute_skill_script 的 --action / 接口自动化 MCP 工具名 -> 引导提示）
SELF_HEAL_FORBIDDEN_TOOL_HINTS = {
    # 删除类：自愈会话禁止删除任何对象
    "delete_element": "自愈会话禁止删除元素，修正定位请用 update_element",
    "batch_delete_elements": "自愈会话禁止删除元素，修正定位请用 update_element",
    "delete_page": "自愈会话禁止删除页面",
    "batch_delete_pages": "自愈会话禁止删除页面",
    "delete_page_step": "自愈会话禁止删除页面步骤，修正内容请用 update_page_step / set_step_details",
    "delete_testcase": "自愈会话禁止删除测试用例",
    "batch_delete_testcases": "自愈会话禁止删除测试用例",
    "delete_case_step": "自愈会话禁止删除用例步骤，请用 set_case_steps 调整",
    "delete_interface_case": "自愈会话禁止调用接口自动化删除工具",
    # 结构级创建：自愈只做最小化修复，禁止扩充用例范围
    "create_testcase": "自愈会话禁止新建测试用例，仅修复目标用例现有资产",
    "create_page_step": "自愈会话禁止新建页面步骤，仅修复目标用例现有步骤",
    "create_page": "自愈会话禁止新建页面",
    "set_case_steps": "自愈会话禁止重组用例步骤编排，仅修复现有步骤的元素绑定与参数",
    "copy_testcase": "自愈会话禁止复制用例",
    "batch_create_elements": "自愈会话禁止批量创建元素，缺元素时用 create_element 单个创建",
    # 接口自动化工具漂移
    "create_interface_case": "自愈会话禁止调用接口自动化工具",
    "update_interface_case": "自愈会话禁止调用接口自动化工具",
    "run_interface_case": "自愈会话禁止调用接口自动化工具，复测请用 execute_testcase",
    "copy_interface_case": "自愈会话禁止调用接口自动化工具",
}


class SelfHealGuardMiddleware(AgentMiddleware):
    """UI 用例自愈会话的工具守护：拦截删除/结构级创建/工具漂移。

    自愈会话的目标是最小化修复目标用例资产并复测验证，删除类与结构级
    变更一律返回可自愈的错误消息引导模型改用修复类工具。
    """

    def __init__(self) -> None:
        super().__init__()
        self._drift_count = 0

    @property
    def drift_count(self) -> int:
        return self._drift_count

    def _check(self, request: Any) -> tuple[bool, str]:
        """判定是否拦截。返回 (是否放行, 拦截提示文本)。"""
        action, _ = _extract_action_and_payload(request)
        if not action:
            return True, ""
        hint = SELF_HEAL_FORBIDDEN_TOOL_HINTS.get(action)
        if not hint:
            return True, ""
        self._drift_count += 1
        logger.warning("[GenerationGuard] 拦截自愈会话工具漂移: %s", action)
        tool_call = getattr(request, "tool_call", None) or {}
        tool_name = tool_call.get("name") or "tool"
        return False, f"当前会话是【UI 自动化用例自愈】任务，{hint}。"

    def wrap_tool_call(
        self,
        request: Any,
        handler: Callable[[Any], Any],
    ) -> Any:
        allowed, text = self._check(request)
        if allowed:
            return handler(request)
        tool_call = getattr(request, "tool_call", None) or {}
        return _build_error_tool_message(request, tool_call.get("name") or "tool", text)

    async def awrap_tool_call(
        self,
        request: Any,
        handler: Callable[[Any], Any],
    ) -> Any:
        allowed, text = self._check(request)
        if allowed:
            return await handler(request)
        tool_call = getattr(request, "tool_call", None) or {}
        return _build_error_tool_message(request, tool_call.get("name") or "tool", text)
