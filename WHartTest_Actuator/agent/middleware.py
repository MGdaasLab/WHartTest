"""Agent 上下文管理中间件：根治 100k 上下文超限。

两层保障（每轮模型调用前的 @before_model 钩子）：
1. observation_refresh_middleware：动作工具执行后刷新唯一一条页面快照，
   删除历史里其它 OBS_MARKER 标记的消息——保证任何时刻至多 1 条页面快照。
2. context_budget_middleware：每次模型调用前评估 token，超预算或消息过多时
   保留 system+首条 goal+最近 keep_recent 条，中段折叠为一句规则式摘要（零成本、确定性）。

每个步骤独立构造（闭包绑定 per-run 的 page/config），支持并发 AI 步骤互不干扰。
"""

import json
import logging
from typing import Any
from uuid import uuid4

from langchain.agents.middleware import AgentState, before_model
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    RemoveMessage,
)
from langgraph.runtime import Runtime

from .observation import OBS_MARKER, observe_page

logger = logging.getLogger(__name__)

# 估算倍率（对冲服务端自有 tokenizer 与本端估算的差异）
_MULTIPLIER = 1.2
_HEURISTIC_MULTIPLIER = 1.5  # tiktoken 不可用时用启发式，低估更严重，倍率更大
_IMG_TOKEN_EST = 850
_PER_MSG_OVERHEAD = 8

# 非真实观察/工具，observation_refresh 不应在其后刷新页面快照
_NON_ACTION_TOOLS = {"observe", "finish", "screenshot"}


# ============ token 估算（纯函数）============

_ENCODER = None


def _get_encoder():
    global _ENCODER
    if _ENCODER is None:
        try:
            import tiktoken
            _ENCODER = tiktoken.get_encoding("o200k_base")
        except Exception:
            _ENCODER = False  # 不可用标记
    return _ENCODER


def _encode_len(text: str) -> int:
    enc = _get_encoder()
    if enc:
        try:
            return len(enc.encode(text or ""))
        except Exception:
            pass
    return _heuristic_len(text)


def _heuristic_len(text: str) -> int:
    """CJK ~1 token/字、ASCII ~0.4 token/字 的保守启发式。"""
    if not text:
        return 0
    cjk = 0
    total = 0
    for c in text:
        total += 1
        if "一" <= c <= "鿿" or "㐀" <= c <= "䶿":
            cjk += 1
    ascii_chars = total - cjk
    return int(cjk * 1.0 + ascii_chars * 0.4)


def estimate_input_tokens(messages: list[Any], multiplier: float | None = None) -> int:
    """估算 messages 输入 token 数（乘以安全倍率）。"""
    if multiplier is None:
        multiplier = _HEURISTIC_MULTIPLIER if _get_encoder() is False else _MULTIPLIER
    total = 0
    for m in messages:
        content = getattr(m, "content", "")
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    total += _encode_len(block.get("text", ""))
                elif block.get("type") == "image_url":
                    total += _IMG_TOKEN_EST
        elif isinstance(content, str):
            total += _encode_len(content)
        if getattr(m, "tool_calls", None):
            try:
                total += _encode_len(json.dumps(m.tool_calls, ensure_ascii=False))
            except Exception:
                total += 50
        total += _PER_MSG_OVERHEAD
    return int(total * multiplier)


# ============ 规划裁剪（纯函数）============

def plan_trim(messages: list[Any], keep_recent: int) -> list[Any]:
    """返回 RemoveMessage 消息序列：保留 system+首条 goal+最近 keep_recent，中段折叠为摘要。

    约束：不减 first(SystemMessage) 与 first(HumanMessage goal)，也不减末尾 keep_recent 条。
    """
    if len(messages) <= 3:
        return []

    first_sys_idx = next((i for i, m in enumerate(messages) if isinstance(m, SystemMessage)), None)
    first_human_idx = next((i for i, m in enumerate(messages) if isinstance(m, HumanMessage)), None)

    protected_indices: set[int] = set()
    if first_sys_idx is not None:
        protected_indices.add(first_sys_idx)
    if first_human_idx is not None:
        protected_indices.add(first_human_idx)

    keep_count = min(keep_recent, max(0, len(messages) - len(protected_indices)))
    if keep_count <= 0:
        keep_count = min(len(messages), 4)
    tail_start = max(0, len(messages) - keep_count)
    protected_indices.update(range(tail_start, len(messages)))

    dropped = [m for i, m in enumerate(messages) if i not in protected_indices]
    updates: list[Any] = [RemoveMessage(id=m.id) for m in dropped if getattr(m, "id", None) is not None]
    summary = _summarize(dropped)
    if summary:
        updates.append(HumanMessage(id=str(uuid4()), content=f"[此前动作摘要]: {summary}"))
    return updates


def _summarize(turns: list[Any]) -> str:
    """规则式摘要：从 AIMessage.tool_calls 与 ToolMessage.content 中提炼。"""
    actions: list[str] = []
    for t in turns:
        if isinstance(t, AIMessage) and getattr(t, "tool_calls", None):
            for tc in t.tool_calls or []:
                try:
                    name = tc.get("name", "?")
                    args = tc.get("args", {}) or {}
                except Exception:
                    continue
                if name == "click":
                    actions.append(f"点击({args.get('by')}={args.get('value')!r})")
                elif name == "fill":
                    actions.append(f"输入({args.get('by')}={args.get('value')!r})")
                elif name == "navigate":
                    actions.append(f"导航({args.get('url')})")
                elif name == "assert_condition":
                    actions.append(f"断言({args.get('type')}={args.get('expected')!r})")
                elif name == "select_option":
                    actions.append(f"选择({args.get('option')!r})")
                elif name == "finish":
                    actions.append(f"结束(success={args.get('success')})")
                else:
                    actions.append(name)
        elif isinstance(t, ToolMessage):
            content = str(getattr(t, "content", ""))[:60]
            actions.append(f"→{content}")
    return "; ".join(actions)[:1500] or "(无)"


# ============ per-run 工厂（闭包，支持并发）============

def configure_middleware(
    *,
    page,
    supports_vision: bool,
    context_limit: int,
    token_budget_ratio: float = 0.60,
    hard_message_cap: int = 40,
    keep_recent: int = 32,
    refresh_cap: int = 6000,
) -> list:
    """构造每步骤独立的 middleware 列表（闭包绑定 page/config）。

    顺序：先刷新快照（让最新观察进入上下文与「最近」段），再做预算裁剪。
    """

    @before_model
    async def observation_refresh_middleware(state: AgentState, runtime: Runtime):
        msgs = list(state.get("messages", []))
        if not msgs:
            return None
        last = msgs[-1]
        # 仅在真实动作工具执行后才刷新（exclude observe/finish/screenshot）
        if not (isinstance(last, ToolMessage) and last.name not in _NON_ACTION_TOOLS):
            return None
        try:
            obs = await observe_page(page, bool(supports_vision), cap_chars=refresh_cap)
            new_text = OBS_MARKER + obs.text
        except Exception as e:
            logger.warning(f"观察刷新失败: {e}")
            return None

        updates: list[BaseMessage] = []
        for m in msgs:
            content = getattr(m, "content", "")
            if isinstance(m, HumanMessage) and isinstance(content, str) and content.startswith(OBS_MARKER):
                updates.append(RemoveMessage(id=m.id))
        updates.append(HumanMessage(id=str(uuid4()), content=new_text))
        return {"messages": updates}

    @before_model
    async def context_budget_middleware(state: AgentState, runtime: Runtime):
        msgs = list(state.get("messages", []))
        if not msgs:
            return None
        est = estimate_input_tokens(msgs)
        budget = max(1, int(int(context_limit) * float(token_budget_ratio)))
        if est <= budget and len(msgs) <= int(hard_message_cap):
            return None
        logger.debug(
            f"[context_budget] est={est} msgs={len(msgs)} budget={budget} cap={hard_message_cap} → 触发裁剪"
        )
        updates = plan_trim(msgs, int(keep_recent))
        return {"messages": updates} if updates else None

    return [observation_refresh_middleware, context_budget_middleware]