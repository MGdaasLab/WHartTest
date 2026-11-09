#!/usr/bin/env python
"""Config environment override tests for Docker actuator runtime."""

import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

from main import Config, check_ws_token_config


class ConfigEnvOverrideTest(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "WHARTTEST_ACTUATOR_WS_URL": "ws://backend:8000/ws/ui/actuator/",
            "WHARTTEST_ACTUATOR_API_URL": "http://backend:8000",
            "WHARTTEST_ACTUATOR_USE_GUI": "false",
            "WHARTTEST_ACTUATOR_HEADLESS": "true",
            "WHARTTEST_ACTUATOR_PERSISTENT": "false",
            "WHARTTEST_ACTUATOR_API_USERNAME": "admin",
            "WHARTTEST_ACTUATOR_API_PASSWORD": "  admin123456\n",
        },
        clear=True,
    )
    def test_config_load_from_env_overrides_compose_values(self):
        config = Config()
        config.use_gui = True
        config.headless = False
        config.persistent = True

        config.load_from_env()

        self.assertEqual(config.ws_url, "ws://backend:8000/ws/ui/actuator/")
        self.assertEqual(config.api_url, "http://backend:8000")
        self.assertFalse(config.use_gui)
        self.assertTrue(config.headless)
        self.assertFalse(config.persistent)
        self.assertEqual(config.api_username, "admin")
        self.assertEqual(config.api_password, "admin123456")
        self.assertNotIn("WHARTTEST_ACTUATOR_API_PASSWORD", os.environ)

    @patch.dict(os.environ, {"WHARTTEST_ACTUATOR_DOCKER": "true"}, clear=True)
    def test_config_normalize_for_runtime_disables_gui_in_container(self):
        config = Config()
        config.use_gui = True
        config.headless = False

        config.normalize_for_runtime()

        self.assertFalse(config.use_gui)
        # 无头开关不再被强制开启：观看模式（headless=False）保留，
        # 无显示环境由 executor 启动层回退无头，执行画面走画布帧流
        self.assertFalse(config.headless)

    @patch.dict(
        os.environ,
        {"WHARTTEST_ACTUATOR_DOCKER": "true", "DISPLAY": ":0"},
        clear=True,
    )
    def test_config_normalize_for_runtime_keeps_gui_when_display_available(self):
        config = Config()
        config.use_gui = True
        config.headless = False

        config.normalize_for_runtime()

        self.assertTrue(config.use_gui)
        self.assertFalse(config.headless)


class WsTokenConfigCheckTest(unittest.TestCase):
    """check_ws_token_config 检测逻辑测试。"""

    TOKEN = "a" * 64

    def _write_env(self, directory: Path, token: str | None) -> Path:
        env_path = directory / ".env"
        lines = ["# test env"]
        if token is not None:
            lines.append(f"UI_WS_ACTUATOR_TOKEN={token}")
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return env_path

    def _run_check(self, config: Config, config_dir: Path) -> None:
        check_ws_token_config(config, config_dir / "config.toml")

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_ws_token_field_warns(self):
        """config.toml 无 ws_token 字段（旧版升级场景）时提示添加字段。"""
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            self._write_env(config_dir, self.TOKEN)
            config = Config()
            config.ws_token = ""

            with self.assertLogs("actuator", level="WARNING") as captured:
                self._run_check(config, config_dir)

            message = "\n".join(captured.output)
            self.assertIn("ws_token", message)
            self.assertIn("UI_WS_ACTUATOR_TOKEN", message)

    @patch.dict(os.environ, {}, clear=True)
    def test_mismatched_ws_token_warns(self):
        """ws_token 与 .env 期望值不一致时提示保持一致。"""
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            self._write_env(config_dir, self.TOKEN)
            config = Config()
            config.ws_token = "b" * 64

            with self.assertLogs("actuator", level="WARNING") as captured:
                self._run_check(config, config_dir)

            message = "\n".join(captured.output)
            self.assertIn("不一致", message)
            self.assertIn("UI_WS_ACTUATOR_TOKEN", message)

    @patch.dict(os.environ, {}, clear=True)
    def test_matching_ws_token_passes_silently(self):
        """ws_token 与期望值一致时不输出任何告警。"""
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            self._write_env(config_dir, self.TOKEN)
            config = Config()
            config.ws_token = self.TOKEN

            with self.assertNoLogs("actuator", level="WARNING"):
                self._run_check(config, config_dir)

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_env_file_skips_check(self):
        """找不到 .env（exe 独立部署等场景）时跳过比对，不告警。"""
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            config = Config()
            config.ws_token = ""

            with self.assertNoLogs("actuator", level="WARNING"):
                self._run_check(config, config_dir)

    def test_env_injection_skips_check(self):
        """容器部署经环境变量注入 token 时跳过检测。

        注意：load_from_env 会 pop 环境变量，检测逻辑依赖
        config.ws_token_from_env 标志而非环境变量本身。
        """
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            self._write_env(config_dir, self.TOKEN)
            config = Config()
            config.ws_token = ""
            # 复刻 main() 真实时序：load_from_env 先执行（pop 后标志置位）
            with patch.dict(os.environ, {"WHARTTEST_ACTUATOR_WS_TOKEN": "injected"}):
                config.load_from_env()
            self.assertTrue(config.ws_token_from_env)
            self.assertNotIn("WHARTTEST_ACTUATOR_WS_TOKEN", os.environ)

            with self.assertNoLogs("actuator", level="WARNING"):
                self._run_check(config, config_dir)

    @patch.dict(os.environ, {}, clear=True)
    def test_env_injection_flag_default_off(self):
        """未注入环境变量时标志默认关闭，检测正常执行。"""
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            self._write_env(config_dir, self.TOKEN)
            config = Config()
            config.ws_token = "wrong"

            self.assertFalse(config.ws_token_from_env)
            with self.assertLogs("actuator", level="WARNING"):
                self._run_check(config, config_dir)

    @patch.dict(os.environ, {"WHARTTEST_ACTUATOR_ENV_FILE": ""}, clear=True)
    def test_empty_env_token_skips_comparison(self):
        """.env 中 UI_WS_ACTUATOR_TOKEN 为空时后端本身会拒绝所有连接，跳过比对。"""
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            self._write_env(config_dir, "")
            config = Config()
            config.ws_token = ""

            with self.assertNoLogs("actuator", level="WARNING"):
                self._run_check(config, config_dir)

    @patch.dict(os.environ, {}, clear=True)
    def test_env_file_override_respected(self):
        """WHARTTEST_ACTUATOR_ENV_FILE 指定的 .env 路径优先生效。"""
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            # config.toml 旁不放 .env，期望值只能从覆盖路径读取
            override_path = Path(tmp) / "custom.env"
            override_path.write_text(f"UI_WS_ACTUATOR_TOKEN={self.TOKEN}\n", encoding="utf-8")

            config = Config()
            config.ws_token = "wrong"

            with patch.dict(os.environ, {"WHARTTEST_ACTUATOR_ENV_FILE": str(override_path)}):
                with self.assertLogs("actuator", level="WARNING"):
                    self._run_check(config, config_dir)


if __name__ == "__main__":
    unittest.main()
