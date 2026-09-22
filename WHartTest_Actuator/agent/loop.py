"""AI Agent 主循环：观察-思考-行动（基于 LangChain create_agent）。

驱动 Playwright `page` 完成自然语言目标，返回与 `_execute_step` 一致的
`(success, message, screenshot_path)` 契约。入口签名保持不变。
"""

import logging
import os

logger = logging.getLogger(__name__)


async def run_agent_loop(
    page,
    goal: str,
    model_config,
    step_id: int,
    screenshot_dir: str,
) -> tuple[bool, str, str | None]:
    """运行 Agent 循环。

    Args:
        page: Playwright async_api.Page
        goal: 自然语言任务描述
        model_config: AgentModelConfig
        step_id: 步骤 id（用于命名截图）
        screenshot_dir: 截图保存目录

    Returns:
        (success, message, screenshot_path)
    """
    from .agent import build_agent, format_initial_messages
    from .middleware import configure_middleware
    from .observation import observe_page
    from .tools import build_tools, extract_finish_result

    try:
        tools = build_tools(page, model_config.supports_vision, screenshot_dir, step_id)
        middleware = configure_middleware(
            page=page,
            supports_vision=model_config.supports_vision,
            context_limit=model_config.context_limit,
            token_budget_ratio=getattr(model_config, "token_budget_ratio", 0.60),
            hard_message_cap=getattr(model_config, "hard_message_cap", 40),
            keep_recent=getattr(model_config, "keep_recent", 32),
        )
        agent = build_agent(model_config, tools, middleware)

        # 首次观察：注入为「当前页面状态」条；后续由 observation_refresh 刷新替换。
        first_obs = await observe_page(page, model_config.supports_vision)
        initial = format_initial_messages(goal, first_obs, model_config.supports_vision)

        max_steps = max(1, int(getattr(model_config, "max_steps", 25) or 25))
        # LangGraph 硬上限兜底（一轮约对应若干次图节点流转）
        recursion_limit = 4 * max_steps + 10

        logger.info(f"[AI Agent step {step_id}] 开始，目标: {goal[:200]}")
        result = await agent.ainvoke(
            {"messages": initial},
            config={"recursion_limit": recursion_limit},
        )

        messages = result.get("messages", []) if isinstance(result, dict) else []
        finish = extract_finish_result(messages)
        sp = await _save_screenshot(page, step_id, screenshot_dir, suffix="_finish")
        if finish is not None:
            success, message = finish
            logger.info(f"[AI Agent step {step_id}] finish: success={success} message={message[:120]}")
            return bool(success), message, sp

        # 未调用 finish：可能达步数上限或模型自行停止
        last = messages[-1] if messages else None
        last_content = getattr(last, "content", "") if last else ""
        reason = (str(last_content)[:200] if last_content else "未报告完成结果")
        logger.warning(f"[AI Agent step {step_id}] 未调用 finish: {reason}")
        return False, f"AI 代理未调用 finish（可能已达步数上限）: {reason}", sp

    except Exception as e:
        logger.error(f"AI Agent 循环异常(step {step_id}): {e}", exc_info=True)
        return False, f"AI Agent 内部错误: {e}", None


async def _save_screenshot(page, step_id: int, screenshot_dir: str, suffix: str = "") -> str | None:
    try:
        os.makedirs(screenshot_dir, exist_ok=True)
        path = os.path.join(screenshot_dir, f"ai_step_{step_id}{suffix}.png")
        await page.screenshot(path=path)
        return path
    except Exception as e:
        logger.warning(f"保存截图失败: {e}")
        return None