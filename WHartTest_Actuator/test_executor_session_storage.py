#!/usr/bin/env python
"""登录态 sessionStorage 扩展字段测试。

回归背景：部分系统（如 RuoYi 系）登录凭据存于 sessionStorage，而 Playwright
storageState 只含 cookies + localStorage，快照缺失导致登录态复用被重定向回
登录页。平台在快照上扩展 session_storage 字段采集/回放 sessionStorage：
- new_context 路径：storage_state 传入 Playwright 前必须剥离扩展字段（非法入参），
  回放脚本经 _apply_context_init_scripts 注入；
- 持久化路径：_apply_storage_state 注入原生字段，回放脚本同样经 init script。
"""

import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent))

from executor import PlaywrightExecutor


SS_ORIGIN = {
    "origin": "https://office.mojiedoc.com:4430",
    "sessionStorage": [
        {"name": "luckysheet_access_token", "value": "jwt-xxx"},
        {"name": "Admin-Expires-In", "value": "720"},
    ],
}
STATE_WITH_SS = {
    "cookies": [{"name": "Admin-Expires-In", "value": "720",
                 "domain": "office.mojiedoc.com", "path": "/"}],
    "origins": [{"origin": SS_ORIGIN["origin"],
                 "localStorage": [{"name": "iconify-count", "value": "0"}]}],
    "session_storage": [SS_ORIGIN],
}
STATE_LEGACY = {
    "cookies": [{"name": "c", "value": "1", "domain": "a.local", "path": "/"}],
    "origins": [],
}


class StripSessionStorageTest(unittest.TestCase):
    """new_context 前剥离 session_storage 扩展字段。"""

    def test_strip_removes_extension_only(self):
        stripped = PlaywrightExecutor._strip_session_storage(STATE_WITH_SS)
        self.assertNotIn("session_storage", stripped)
        self.assertEqual(stripped["cookies"], STATE_WITH_SS["cookies"])
        self.assertEqual(stripped["origins"], STATE_WITH_SS["origins"])
        # 原快照不被修改
        self.assertIn("session_storage", STATE_WITH_SS)

    def test_legacy_state_untouched(self):
        self.assertEqual(
            PlaywrightExecutor._strip_session_storage(STATE_LEGACY), STATE_LEGACY,
        )

    def test_path_like_passthrough(self):
        self.assertEqual(
            PlaywrightExecutor._strip_session_storage("data/auth.json"), "data/auth.json",
        )

    def test_context_options_use_stripped_state(self):
        with patch('executor.Path'):
            executor = PlaywrightExecutor(browser_type='chromium')
        executor._auth_config = {'storage_state': STATE_WITH_SS}
        options = executor._build_browser_context_options()
        self.assertNotIn("session_storage", options["storage_state"])
        self.assertIn("cookies", options["storage_state"])


class SessionStorageInitScriptTest(unittest.TestCase):
    """sessionStorage 回放 init script 生成。"""

    def test_script_contains_origin_and_entries(self):
        script = PlaywrightExecutor._build_session_storage_init_script([SS_ORIGIN])
        self.assertIn(SS_ORIGIN["origin"], script)
        self.assertIn("luckysheet_access_token", script)
        self.assertIn("sessionStorage.setItem", script)
        self.assertIn("location.origin", script)

    def test_empty_and_invalid_inputs_return_empty(self):
        self.assertEqual(PlaywrightExecutor._build_session_storage_init_script([]), "")
        self.assertEqual(PlaywrightExecutor._build_session_storage_init_script(None), "")
        self.assertEqual(
            PlaywrightExecutor._build_session_storage_init_script(
                [{"origin": "https://x.local", "sessionStorage": []}]
            ),
            "",
        )
        self.assertEqual(
            PlaywrightExecutor._build_session_storage_init_script([{"origin": 1}]), "",
        )

    def test_script_is_valid_js(self):
        import subprocess
        import tempfile
        script = PlaywrightExecutor._build_session_storage_init_script([SS_ORIGIN])
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
            f.write(script)
            js_path = f.name
        proc = subprocess.run(
            ["node", "--check", js_path], capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)


class ApplyContextInitScriptsTest(unittest.TestCase):
    """context 初始化脚本注入：sessionStorage 回放经 _apply_context_init_scripts。"""

    def _make_executor(self):
        with patch('executor.Path'):
            executor = PlaywrightExecutor(browser_type='chromium')
        return executor

    def test_session_script_injected_when_present(self):
        executor = self._make_executor()
        executor._auth_config = {'storage_state': STATE_WITH_SS}
        context = MagicMock()
        context.add_init_script = AsyncMock()
        asyncio.run(executor._apply_context_init_scripts(context))
        scripts = [c.args[0] for c in context.add_init_script.await_args_list]
        self.assertTrue(
            any("sessionStorage.setItem" in s and "luckysheet_access_token" in s
                for s in scripts),
            f"未注入 sessionStorage 回放脚本: {scripts}",
        )

    def test_no_session_script_for_legacy_state(self):
        executor = self._make_executor()
        executor._auth_config = {'storage_state': STATE_LEGACY}
        context = MagicMock()
        context.add_init_script = AsyncMock()
        asyncio.run(executor._apply_context_init_scripts(context))
        scripts = [c.args[0] for c in context.add_init_script.await_args_list]
        self.assertFalse(any("sessionStorage.setItem" in s for s in scripts))

    def test_file_path_state_loaded_for_session_script(self):
        import tempfile
        executor = self._make_executor()
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
            json.dump(STATE_WITH_SS, f)
            path = f.name
        executor._auth_config = {'storage_state': path}
        context = MagicMock()
        context.add_init_script = AsyncMock()
        asyncio.run(executor._apply_context_init_scripts(context))
        scripts = [c.args[0] for c in context.add_init_script.await_args_list]
        self.assertTrue(any("sessionStorage.setItem" in s for s in scripts))

    def test_apply_storage_state_manual_path_no_session_leak(self):
        """持久化路径：_apply_storage_state 注入原生字段，不重复注入 sessionStorage。"""
        executor = self._make_executor()
        context = MagicMock()
        context.add_cookies = AsyncMock()
        context.add_init_script = AsyncMock()
        asyncio.run(executor._apply_storage_state(context, STATE_WITH_SS))
        cookies = context.add_cookies.await_args_list[0].args[0]
        self.assertEqual(cookies, STATE_WITH_SS["cookies"])
        scripts = [c.args[0] for c in context.add_init_script.await_args_list]
        # localStorage 回放脚本存在，sessionStorage 回放由 _apply_context_init_scripts 负责
        self.assertTrue(any("localStorage.setItem" in s for s in scripts))
        self.assertFalse(any("sessionStorage.setItem" in s for s in scripts))


class LogAuthInjectionTest(unittest.TestCase):
    """注入摘要日志包含 sessionStorage 计数（不含凭据明文）。"""

    def test_log_contains_session_keys(self):
        with patch('executor.Path'):
            executor = PlaywrightExecutor(browser_type='chromium')
        executor._auth_config = {'storage_state': STATE_WITH_SS}
        with self.assertLogs('root', level='INFO') as captured:
            executor._log_auth_injection()
        text = "\n".join(captured.output)
        self.assertIn("sessionStorage_keys=2", text)
        self.assertNotIn("jwt-xxx", text)

    def test_log_without_session_field(self):
        with patch('executor.Path'):
            executor = PlaywrightExecutor(browser_type='chromium')
        executor._auth_config = {'storage_state': STATE_LEGACY}
        with self.assertLogs('root', level='INFO') as captured:
            executor._log_auth_injection()
        self.assertNotIn("sessionStorage_keys", "\n".join(captured.output))


if __name__ == '__main__':
    unittest.main()
