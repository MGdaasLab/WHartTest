"""MCP 共享密钥鉴权决策逻辑测试（不依赖 fastmcp，只测入口守卫）。"""

import importlib
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

mcp_auth = importlib.import_module("mcp_auth")


class McpAuthGuardTests(unittest.TestCase):
    def setUp(self):
        self._snapshot = {
            k: os.environ.get(k) for k in (mcp_auth._TOKEN_ENV, mcp_auth._ALLOW_OPEN_ENV)
        }
        os.environ.pop(mcp_auth._TOKEN_ENV, None)
        os.environ.pop(mcp_auth._ALLOW_OPEN_ENV, None)

    def tearDown(self):
        for key, value in self._snapshot.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_missing_token_fails_closed(self):
        self.assertEqual(mcp_auth.get_shared_token(), "")
        self.assertFalse(mcp_auth.unauthenticated_allowed())
        with self.assertRaises(SystemExit) as ctx:
            mcp_auth.enforce_auth_or_exit("test")
        self.assertEqual(ctx.exception.code, 2)

    def test_explicit_open_mode_is_allowed_but_flagged(self):
        os.environ[mcp_auth._ALLOW_OPEN_ENV] = "true"
        self.assertTrue(mcp_auth.unauthenticated_allowed())
        mcp_auth.enforce_auth_or_exit("test")  # 不应退出

    def test_configured_token_passes_guard(self):
        os.environ[mcp_auth._TOKEN_ENV] = "  shared-secret  "
        self.assertEqual(mcp_auth.get_shared_token(), "shared-secret")
        mcp_auth.enforce_auth_or_exit("test")  # 不应退出

    def test_build_mcp_auth_requires_fastmcp_when_token_set(self):
        os.environ[mcp_auth._TOKEN_ENV] = "shared-secret"
        try:
            provider = mcp_auth.build_mcp_auth()
        except ImportError:
            self.skipTest("当前环境未安装 fastmcp>=2.11")
        else:
            self.assertIsNotNone(provider)


if __name__ == "__main__":
    unittest.main()