#!/usr/bin/env python
"""PlaywrightExecutor / TaskConsumer memory release tests."""

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent))

from executor import PlaywrightExecutor
from consumer import TaskConsumer
from models import CaseResultModel, StepResultModel


class ExecutorMemoryReleaseTest(unittest.IsolatedAsyncioTestCase):
    async def test_close_continues_when_context_close_fails(self):
        executor = PlaywrightExecutor(persistent=False)
        context = AsyncMock()
        context.pages = []
        context.close = AsyncMock(side_effect=RuntimeError("context boom"))
        browser = AsyncMock()
        browser.close = AsyncMock()
        playwright = AsyncMock()
        playwright.stop = AsyncMock()

        executor._context = context
        executor._browser = browser
        executor._playwright = playwright
        executor._page = MagicMock()
        executor._page_errors = ["err1", "err2"]

        await executor.close()

        # browser-first close path: context.close is not required when browser exists
        browser.close.assert_awaited_once()
        context.close.assert_not_awaited()
        playwright.stop.assert_awaited_once()
        self.assertIsNone(executor._context)
        self.assertIsNone(executor._browser)
        self.assertIsNone(executor._playwright)
        self.assertIsNone(executor._page)
        self.assertEqual(executor._page_errors, [])

    async def test_batch_finally_keeps_playwright_driver(self):
        executor = PlaywrightExecutor(persistent=False, headless=True)
        playwright = AsyncMock()
        browser = AsyncMock()
        browser.new_context = AsyncMock()
        browser.close = AsyncMock()
        playwright.chromium = MagicMock()
        playwright.chromium.launch = AsyncMock(return_value=browser)
        playwright.stop = AsyncMock()
        executor._playwright = playwright

        # empty configs still hits early return; use one config with mocked path
        config = MagicMock()
        config.case_id = 1
        config.case_name = "c1"
        config.page_steps = []
        config.env_config = None

        context = AsyncMock()
        context.pages = []
        context.close = AsyncMock()
        browser.new_context = AsyncMock(return_value=context)

        async def fake_execute(ctx, cfg, trace_enabled=False):
            return CaseResultModel(case_id=cfg.case_id, status="success")

        with patch.object(executor, "_execute_case_on_context", side_effect=fake_execute):
            # CE may not have stealth init scripts helper; patch only if present.
            if hasattr(executor, "_apply_context_init_scripts"):
                with patch.object(executor, "_apply_context_init_scripts", new=AsyncMock()):
                    results = await executor.execute_batch_concurrent([config], max_concurrent=1)
            else:
                results = await executor.execute_batch_concurrent([config], max_concurrent=1)

        self.assertEqual(len(results), 1)
        browser.close.assert_awaited_once()
        playwright.stop.assert_not_awaited()
        self.assertIs(executor._playwright, playwright)

    async def test_close_force_kills_on_timeout(self):
        executor = PlaywrightExecutor(persistent=False)
        browser = AsyncMock()
        browser.close = AsyncMock()
        playwright = AsyncMock()
        playwright.stop = AsyncMock()
        executor._browser = browser
        executor._context = None
        executor._playwright = playwright
        executor._page = MagicMock()

        import asyncio as _aio
        calls = {"n": 0}

        async def wait_for_mixed(coro, timeout=None):
            calls["n"] += 1
            # Always close the coroutine to avoid "never awaited" warnings.
            if hasattr(coro, "close"):
                try:
                    coro.close()
                except Exception:
                    pass
            if calls["n"] == 1:
                raise _aio.TimeoutError()
            return None

        with patch("executor.asyncio.wait_for", side_effect=wait_for_mixed), patch.object(
            executor, "_force_kill_browser"
        ) as kill:
            await executor.close()
            kill.assert_called_once_with(browser)
        self.assertIsNone(executor._browser)
        self.assertIsNone(executor._playwright)

    def test_release_memory_skips_libc_on_non_linux(self):
        executor = PlaywrightExecutor(persistent=False)
        with patch("platform.system", return_value="Windows"), patch(
            "ctypes.CDLL", side_effect=AssertionError("should not load libc")
        ):
            # Force re-init path
            if hasattr(executor, "_libc"):
                delattr(executor, "_libc")
            executor._release_memory()
        self.assertIs(executor._libc, False)


class ConsumerMemoryReleaseTest(unittest.TestCase):
    def test_release_result_payloads_clears_base64_screenshots(self):
        consumer = TaskConsumer(ws_client=MagicMock(), api_base_url="http://x")
        result = CaseResultModel(
            case_id=1,
            status="failed",
            steps=[
                StepResultModel(
                    step_id=1,
                    status="failed",
                    screenshot="data:image/png;base64,AAAA",
                ),
                StepResultModel(
                    step_id=2,
                    status="success",
                    screenshot="/tmp/a.png",
                ),
            ],
        )

        consumer._release_result_payloads(result)

        self.assertIsNone(result.steps[0].screenshot)
        self.assertEqual(result.steps[1].screenshot, "/tmp/a.png")



class ConsumerFinallyReleaseTest(unittest.IsolatedAsyncioTestCase):
    async def test_execute_test_case_releases_on_send_error(self):
        consumer = TaskConsumer(ws_client=MagicMock(), api_base_url="http://x")
        consumer.ws_client.send_result = AsyncMock(side_effect=RuntimeError("ws down"))
        consumer._current_user = "u1"

        result = CaseResultModel(
            case_id=9,
            status="success",
            steps=[
                StepResultModel(
                    step_id=1,
                    status="success",
                    screenshot="data:image/png;base64,AAAA",
                )
            ],
        )

        consumer.executor = MagicMock()
        consumer.executor.execute_test_case = AsyncMock(return_value=result)
        consumer._fetch_test_case = AsyncMock(return_value={"project": 1, "name": "c"})
        consumer._fetch_env_config = AsyncMock(return_value=None)
        consumer._fetch_default_env_config = AsyncMock(return_value=None)
        consumer._init_data_processor = AsyncMock(return_value=None)
        consumer._build_test_case_config = MagicMock(return_value=MagicMock(case_name="c"))
        consumer._process_result_screenshots = AsyncMock(side_effect=lambda r: r)
        consumer._upload_trace_file = AsyncMock(return_value=None)
        consumer._release_memory_after_task = AsyncMock()

        with self.assertRaises(RuntimeError):
            await consumer.execute_test_case({"case_id": 9})

        self.assertIsNone(result.steps[0].screenshot)
        consumer._release_memory_after_task.assert_awaited()


if __name__ == "__main__":
    unittest.main()
