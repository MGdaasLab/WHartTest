#!/usr/bin/env python
"""Config environment override tests for Docker actuator runtime."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

from main import Config


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
        self.assertTrue(config.headless)

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


if __name__ == "__main__":
    unittest.main()
