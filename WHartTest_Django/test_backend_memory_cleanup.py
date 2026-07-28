#!/usr/bin/env python
"""Backend memory cleanup unit tests (MCP session + Playwright process terminate)."""

from __future__ import annotations

import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent))


class FakeClient:
    def __init__(self):
        self.closed = False

    async def close_sessions(self):
        self.closed = True


class GlobalMCPSessionManagerCleanupTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Fresh singleton state for each test
        from mcp_tools.persistent_client import GlobalMCPSessionManager

        self._mgr_cls = GlobalMCPSessionManager
        self._prev_instance = GlobalMCPSessionManager._instance
        GlobalMCPSessionManager._instance = None
        self.mgr = GlobalMCPSessionManager()
        self.mgr.max_session_clients = 2
        self.mgr.session_idle_timeout_seconds = 1

    def tearDown(self):
        # Restore singleton so other tests/modules keep module-level manager.
        self._mgr_cls._instance = self._prev_instance

    async def test_cleanup_closes_client_even_without_context(self):
        client = FakeClient()
        key = "1_2_sess"
        self.mgr.session_clients[key] = client
        # No session_contexts entry on purpose (old bug path)
        await self.mgr.cleanup_user_session("1", "2", "sess")
        self.assertTrue(client.closed)
        self.assertNotIn(key, self.mgr.session_clients)

    async def test_cleanup_all_closes_orphan_clients(self):
        client = FakeClient()
        key = "1_2_orphan"
        self.mgr.session_clients[key] = client
        await self.mgr.cleanup_all_user_sessions("1", "2")
        self.assertTrue(client.closed)
        self.assertNotIn(key, self.mgr.session_clients)

    async def test_idle_and_overflow_pruning(self):
        c1, c2, c3 = FakeClient(), FakeClient(), FakeClient()
        now = time.monotonic()
        # All recently used: overflow path (not idle) should prune down to max=2.
        self.mgr.session_clients = {
            "u_p_a": c1,
            "u_p_b": c2,
            "u_p_c": c3,
        }
        self.mgr.session_contexts = {
            "u_p_a": {"last_used": now - 0.1, "client": c1},
            "u_p_b": {"last_used": now - 0.05, "client": c2},
            "u_p_c": {"last_used": now, "client": c3},
        }
        self.mgr.tools_cache = {
            "u_p_a": ["t1"],
            "u_p_b": ["t2"],
            "u_p_c": ["t3"],
        }
        self.mgr.session_idle_timeout_seconds = 3600

        await self.mgr._prune_idle_and_overflow_sessions()

        self.assertLessEqual(len(self.mgr.session_clients), 2)
        # Least recently used (a) should be closed first.
        self.assertTrue(c1.closed)
        self.assertNotIn("u_p_a", self.mgr.session_clients)

    async def test_idle_pruning(self):
        c1, c2 = FakeClient(), FakeClient()
        now = time.monotonic()
        self.mgr.max_session_clients = 10
        self.mgr.session_idle_timeout_seconds = 1
        self.mgr.session_clients = {"u_p_a": c1, "u_p_b": c2}
        self.mgr.session_contexts = {
            "u_p_a": {"last_used": now - 100, "client": c1},
            "u_p_b": {"last_used": now, "client": c2},
        }
        self.mgr.tools_cache = {"u_p_a": ["t1"], "u_p_b": ["t2"]}

        await self.mgr._prune_idle_and_overflow_sessions()
        self.assertTrue(c1.closed)
        self.assertNotIn("u_p_a", self.mgr.session_clients)
        self.assertIn("u_p_b", self.mgr.session_clients)
        self.assertFalse(c2.closed)



    async def test_prune_max_close_respects_config(self):
        # Create more overflow than default cap; with prune_max_close_per_call=2
        # only 2 should close in one prune call.
        self.mgr.max_session_clients = 1
        self.mgr.prune_max_close_per_call = 2
        self.mgr.session_idle_timeout_seconds = 3600
        now = time.monotonic()
        clients = {f"u_p_{i}": FakeClient() for i in range(5)}
        self.mgr.session_clients = dict(clients)
        self.mgr.session_contexts = {
            k: {"last_used": now - (10 - i), "client": c}
            for i, (k, c) in enumerate(clients.items())
        }
        await self.mgr._prune_idle_and_overflow_sessions()
        closed = sum(1 for c in clients.values() if c.closed)
        self.assertEqual(closed, 2)
        self.assertEqual(len(self.mgr.session_clients), 3)


class PlaywrightTerminateJoinTest(unittest.TestCase):
    def test_terminate_joins_io_threads(self):
        from orchestrator_integration.builtin_tools.persistent_playwright import (
            _PlaywrightNodeProcess,
        )

        proc = _PlaywrightNodeProcess(skill_dir="/tmp/fake-skill")

        # Threads exit quickly on their own (simulate pipe EOF after process exit).
        def _reader():
            time.sleep(0.05)

        t1 = threading.Thread(target=_reader, daemon=True)
        t2 = threading.Thread(target=_reader, daemon=True)
        t1.start()
        t2.start()
        proc._stdout_thread = t1
        proc._stderr_thread = t2

        fake_popen = MagicMock()
        fake_popen.poll.return_value = None
        fake_popen.wait.side_effect = [None]
        proc._proc = fake_popen

        with patch.object(proc, "request", side_effect=RuntimeError("no server")):
            proc.terminate(graceful=True)

        self.assertIsNone(proc._stdout_thread)
        self.assertIsNone(proc._stderr_thread)
        self.assertIsNone(proc._proc)
        fake_popen.terminate.assert_called()
        self.assertFalse(t1.is_alive())
        self.assertFalse(t2.is_alive())


if __name__ == "__main__":
    unittest.main()
