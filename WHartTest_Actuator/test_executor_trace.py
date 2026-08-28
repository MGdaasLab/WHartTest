#!/usr/bin/env python
"""Trace path lifecycle tests for PlaywrightExecutor."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent))

from executor import PlaywrightExecutor


class ExecutorTracePathTest(unittest.IsolatedAsyncioTestCase):
    async def test_trace_path_survives_trace_session_close(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = PlaywrightExecutor(
                persistent=False,
                trace_enabled=True,
                trace_dir=tmpdir,
            )

            tracing = AsyncMock()
            tracing.stop = AsyncMock()
            context = AsyncMock()
            context.pages = []
            context.tracing = tracing
            context.close = AsyncMock()
            playwright = AsyncMock()
            playwright.stop = AsyncMock()
            page = MagicMock()

            async def fake_init_browser():
                executor._context = context
                executor._browser = None
                executor._playwright = playwright
                executor._page = page

            with patch.object(executor, "init_browser", new=fake_init_browser):
                async with executor.browser_session_with_trace("case_1") as active_page:
                    self.assertIs(active_page, page)

            trace_path = executor.get_current_trace_path()

            tracing.stop.assert_awaited_once()
            self.assertIsNotNone(trace_path)
            self.assertTrue(trace_path.startswith(f"{tmpdir}/case_1_"))
            self.assertTrue(trace_path.endswith(".zip"))

    async def test_trace_session_clears_stale_path_before_browser_init(self):
        executor = PlaywrightExecutor(persistent=False, trace_enabled=True)
        executor._current_trace_path = "/tmp/old-trace.zip"

        async def failing_init_browser():
            raise RuntimeError("browser failed")

        with patch.object(executor, "init_browser", new=failing_init_browser):
            with self.assertRaisesRegex(RuntimeError, "browser failed"):
                async with executor.browser_session_with_trace("case_2"):
                    pass

        self.assertIsNone(executor.get_current_trace_path())


if __name__ == "__main__":
    unittest.main()
