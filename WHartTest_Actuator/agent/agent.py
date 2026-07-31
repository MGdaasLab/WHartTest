"""LangChain 模型与 Agent 构造。

- `build_model`：用 init_chat_model 接入 OpenAI 兼容端点（vLLM/qwen），含 max_tokens 输出上限与并行工具禁用。
- `build_agent`：用 create_agent 装配 tools + before_model 中间件，system_prompt 由 create_agent 注入（不塞进 messages）。
- `format_initial_messages`：构造首轮消息（goal 单独成条；页面状态单独成条，便于中间件刷新替换）。
"""

import logging
from uuid import uuid4

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage

from .models import AgentModelConfig
from .observation import ObservationResult
from .schema import get_system_prompt

logger = logging.getLogger(__name__)


def build_model(cfg: AgentModelConfig):
    """构造 OpenAI 兼容的 chat model。"""
    return init_chat_model(
        model=cfg.model,
        model_provider="openai",
        base_url=cfg.api_url,
        api_key=cfg.api_key or "sk-placeholder",   # openai SDK 对 None 在某些端点会报错，占位即可
        temperature=cfg.temperature,
        max_tokens=2048,                          # 限制输出，服务端按 input+output 计
        timeout=60,
        max_retries=3,
        model_kwargs={"parallel_tool_calls": False},  # vLLM/qwen 对并行工具调用可能不稳
    )


def build_agent(cfg: AgentModelConfig, tools, middleware):
    """装配 LangChain create_agent。"""
    llm = build_model(cfg)
    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=get_system_prompt(cfg.supports_vision),
        middleware=middleware,
    )


def format_initial_messages(goal: str, obs: ObservationResult, supports_vision: bool) -> list[HumanMessage]:
    """首轮消息：goal 与当前页面状态分两条，便于中间件只替换状态条而不丢失 goal。"""
    goal_msg = HumanMessage(id=str(uuid4()), content=f"任务: {goal}")
    state_text = f"[当前页面状态]\n{obs.text}"

    if supports_vision and obs.has_image and obs.screenshot_data_url:
        # VLM：把页面截图随状态消息一同发出
        state_msg = HumanMessage(
            id=str(uuid4()),
            content=[
                {"type": "text", "text": state_text},
                {"type": "image_url", "image_url": {"url": obs.screenshot_data_url}},
            ],
        )
    else:
        state_msg = HumanMessage(id=str(uuid4()), content=state_text)
    return [goal_msg, state_msg]