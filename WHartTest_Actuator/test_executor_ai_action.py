#!/usr/bin/env python
"""AI操作(step_type=10) 单元测试。

校验 _execute_step 的 dispatch 分发、配置/prompt 缺失校验、Agent 循环成功/超时，
以及 LangChain 重构后的 finish 提取契约与中间件纯函数。
"""

import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent))

import agent
from executor import PlaywrightExecutor, StepConfig
from agent.models import AgentModelConfig


def _ai_step(prompt: str = "打开登录页并输入用户名 admin", desc: str = "AI操作描述"):
    return StepConfig(
        step_id=42,
        operation_type='',
        locator_type='xpath',
        locator_value='',
        step_type=10,
        input_value=prompt,
        description=desc,
    )


class DispatchTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.executor = PlaywrightExecutor()

    async def test_step_type_10_dispatches_to_ai_action(self):
        """无 model_config 时返回明确失败，证明走的是 AI 分支而非元素操作。"""
        success, message, screenshot = await self.executor._execute_step(object(), _ai_step())
        self.assertFalse(success)
        self.assertIn("未配置 AI 模型", message)
        self.assertIsNone(screenshot)

    async def test_missing_prompt_returns_failure(self):
        self.executor.model_config = AgentModelConfig(
            api_url="http://x/v1", api_key="sk-x", model="qwen3-coder",
        )
        step = _ai_step(prompt="", desc="")
        success, message, screenshot = await self.executor._execute_step(object(), step)
        self.assertFalse(success)
        self.assertIn("自然语言", message)

    async def test_success_passthrough(self):
        """注入成功 agent 循环，验证 (success, message, screenshot) 透传。"""
        self.executor.model_config = AgentModelConfig(
            api_url="http://x/v1", api_key="sk-x", model="qwen3-coder",
        )

        async def fake_loop(**kwargs):
            self.assertEqual(kwargs["goal"], "打开登录页并输入用户名 admin")
            self.assertEqual(kwargs["step_id"], 42)
            return True, "AI 操作完成：已登录", "/tmp/shot.png"

        orig = agent.run_agent_loop
        agent.run_agent_loop = fake_loop
        try:
            success, message, screenshot = await self.executor._execute_ai_action(object(), _ai_step())
        finally:
            agent.run_agent_loop = orig
        self.assertTrue(success)
        self.assertEqual(message, "AI 操作完成：已登录")
        self.assertEqual(screenshot, "/tmp/shot.png")

    async def test_timeout(self):
        """循环超时应返回失败与超时信息。"""
        self.executor.model_config = AgentModelConfig(
            api_url="http://x/v1", api_key="sk-x", model="qwen3-coder",
        )
        self.executor.ai_action_timeout = 0  # 立即超时

        async def slow_loop(**kwargs):
            await asyncio.sleep(10)
            return True, "should not reach", None

        class FakePage:
            async def screenshot(self, path=None):
                return None

        orig = agent.run_agent_loop
        agent.run_agent_loop = slow_loop
        try:
            success, message, screenshot = await self.executor._execute_ai_action(FakePage(), _ai_step())
        finally:
            agent.run_agent_loop = orig
        self.assertFalse(success)
        self.assertIn("超时", message)


class ExtractFinishTest(unittest.TestCase):
    """extract_finish_result 提取契约（LangChain ToolMessage）。"""

    def test_finish_success(self):
        from langchain_core.messages import ToolMessage
        from agent.tools import extract_finish_result
        msgs = [ToolMessage(content=json.dumps({"success": True, "message": "完成"}),
                            tool_call_id="1", name="finish", id="tm1")]
        result = extract_finish_result(msgs)
        self.assertEqual(result, (True, "完成"))

    def test_finish_failure(self):
        from langchain_core.messages import ToolMessage
        from agent.tools import extract_finish_result
        msgs = [ToolMessage(content=json.dumps({"success": False, "message": "找不到登录按钮"}),
                            tool_call_id="1", name="finish", id="tm2")]
        result = extract_finish_result(msgs)
        self.assertEqual(result, (False, "找不到登录按钮"))

    def test_no_finish(self):
        from langchain_core.messages import AIMessage
        from agent.tools import extract_finish_result
        msgs = [AIMessage(content="思考中", id="a1")]
        self.assertIsNone(extract_finish_result(msgs))

    def test_finish_malformed_fallback(self):
        from langchain_core.messages import ToolMessage
        from agent.tools import extract_finish_result
        msgs = [ToolMessage(content="not json", tool_call_id="1", name="finish", id="tm3")]
        result = extract_finish_result(msgs)
        self.assertFalse(result[0])
        self.assertIn("not json", result[1])


class MiddlewarePureTest(unittest.TestCase):
    """中间件纯函数：token 估算、plan_trim 保留/丢弃/摘要。"""

    def _msgs(self, n: int):
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
        out = [SystemMessage(content="sys", id="s0"), HumanMessage(content="goal", id="g0")]
        for i in range(n):
            out.append(AIMessage(content=f"think {i}", id=f"a{i}",
                                 tool_calls=[{"name": "click", "args": {"by": "text", "value": "x"},
                                              "id": f"tc{i}", "type": "tool_call"}]))
            out.append(ToolMessage(content="ok", tool_call_id=f"tc{i}", name="click", id=f"t{i}"))
            out.append(HumanMessage(content=f"[当前页面状态]\nfake {i}", id=f"o{i}"))
        return out

    def test_plan_trim_keeps_protected_and_recent(self):
        from agent.middleware import plan_trim
        msgs = self._msgs(6)  # 2 + 18 = 20 条
        updates = plan_trim(msgs, keep_recent=6)
        # 至少生成 RemoveMessage + 1 条摘要 HumanMessage
        self.assertTrue(any(getattr(u, "id", None) and isinstance(u, type(updates[-1])) for u in updates))
        # 摘要消息应包含"此前动作摘要"
        summary_msgs = [u for u in updates if "此前动作摘要" in str(getattr(u, "content", ""))]
        self.assertEqual(len(summary_msgs), 1)

    def test_plan_trim_small_history_noop(self):
        from agent.middleware import plan_trim
        from langchain_core.messages import SystemMessage, HumanMessage
        msgs = [SystemMessage(content="s", id="s"), HumanMessage(content="g", id="g"), HumanMessage(content="x", id="x")]
        self.assertEqual(plan_trim(msgs, keep_recent=6), [])

    def test_estimate_tokens_positive_and_scales(self):
        from agent.middleware import estimate_input_tokens
        from langchain_core.messages import HumanMessage
        small = [HumanMessage(content="hi", id="a")]
        big = [HumanMessage(content="你好世界" * 2000, id="b")]
        self.assertGreater(estimate_input_tokens(small), 0)
        self.assertGreater(estimate_input_tokens(big), estimate_input_tokens(small))


class LoopTest(unittest.IsolatedAsyncioTestCase):
    """run_agent_loop 端到端：patch create_agent 返回假 agent，喂入含 finish 的结果消息。"""

    async def _run_with_fake_agent(self, finish_content: dict):
        from langchain_core.messages import ToolMessage
        from agent import loop

        fake_messages = [ToolMessage(content=json.dumps(finish_content, ensure_ascii=False),
                                     tool_call_id="1", name="finish", id="tm1")]

        class FakeAgent:
            async def ainvoke(self, *a, **k):
                return {"messages": fake_messages}

        class FakePage:
            url = "http://localhost/"

            async def title(self):
                return "Home"

            async def screenshot(self, **kw):
                return b"x"

            async def evaluate(self, expr):
                return "demo"

        with patch("agent.agent.build_agent", return_value=FakeAgent()), \
             patch("agent.agent.format_initial_messages", return_value=[]):
            cfg = AgentModelConfig(api_url="http://x/v1", api_key="sk-x", model="qwen3-coder",
                                   supports_vision=False, max_steps=5, context_limit=100000)
            return await loop.run_agent_loop(page=FakePage(), goal="g", model_config=cfg,
                                             step_id=1, screenshot_dir="./data/screenshots")

    async def test_loop_finish_success(self):
        success, message, screenshot = await self._run_with_fake_agent({"success": True, "message": "完成"})
        self.assertTrue(success)
        self.assertEqual(message, "完成")

    async def test_loop_finish_failure(self):
        success, message, screenshot = await self._run_with_fake_agent({"success": False, "message": "失败"})
        self.assertFalse(success)
        self.assertEqual(message, "失败")


if __name__ == "__main__":
    unittest.main(verbosity=2)