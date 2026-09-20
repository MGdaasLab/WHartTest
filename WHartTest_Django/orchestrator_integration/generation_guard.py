"""AI 生成接口测试用例会话的工具守护中间件。

单 message 批量生成场景下，模型可能发生两类漂移：
1. 工具漂移：把单接口用例调 create_testcase（场景用例工具）保存，落错模块；
2. 参数漂移：create_interface_case 时误传 group 字段，导致用例落进分组而非主接口归属。

本中间件在执行层（wrap_tool_call）拦截上述调用：
- 禁用工具直接返回错误消息（模型收到后可立即自愈改用正确工具）；
- 参数漂移静默剥除后放行（无需打断模型）。

标记来源：前端在 message 头部注入 ``wharttest:generation_mode=interface_case``，
agent_loop_view 检测后通过 should_guard_generation_prompt 判定并挂载本中间件。
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from langchain.agents.middleware import AgentMiddleware

logger = logging.getLogger(__name__)

# 前端注入的生成模式标记
GENERATION_MODE_MARKER = "wharttest:generation_mode=interface_case"

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
            return self._build_error_tool_message(
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
            return self._build_error_tool_message(
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

    @staticmethod
    def _build_error_tool_message(request: Any, tool_name: str, text: str) -> Any:
        """构造工具错误消息（ToolMessage 兼容结构），让模型收到后自愈。"""
        from langchain_core.messages import ToolMessage

        tool_call = getattr(request, "tool_call", None) or {}
        call_id = tool_call.get("id") or ""
        return ToolMessage(content=text, tool_call_id=call_id, name=tool_name or "tool", status="error")
