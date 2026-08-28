#!/usr/bin/env python
"""PlaywrightExecutor 浏览器参数构建测试。"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

from executor import DEFAULT_STEALTH_USER_AGENT, PlaywrightExecutor


class PlaywrightExecutorOptionsTest(unittest.TestCase):
    @patch('executor.is_running_in_container', return_value=False)
    def test_chromium_stealth_launch_args_are_enabled_by_default(self, _mock_container):
        executor = PlaywrightExecutor(browser_type='chromium')

        options = executor._build_browser_launch_options()

        self.assertIn('--disable-blink-features=AutomationControlled', options['args'])
        self.assertIn('--start-maximized', options['args'])

    @patch('executor.is_running_in_container', return_value=False)
    def test_stealth_can_be_disabled(self, _mock_container):
        executor = PlaywrightExecutor(browser_type='chromium', stealth_enabled=False)

        launch_options = executor._build_browser_launch_options()
        context_options = executor._build_browser_context_options()

        self.assertNotIn('args', launch_options)
        # 任务未指定视口时回退到执行器节点默认视口（默认 1280x720）
        self.assertEqual(context_options, {'viewport': {'width': 1280, 'height': 720}})

    def test_chromium_stealth_context_options(self):
        executor = PlaywrightExecutor(browser_type='chromium')

        options = executor._build_browser_context_options()

        self.assertTrue(options['ignore_https_errors'])
        self.assertEqual(options['viewport'], {'width': 1280, 'height': 720})
        self.assertEqual(options['user_agent'], DEFAULT_STEALTH_USER_AGENT)

    def test_custom_user_agent_is_used(self):
        user_agent = 'custom-agent'
        executor = PlaywrightExecutor(
            browser_type='chromium',
            stealth_user_agent=user_agent,
        )

        options = executor._build_browser_context_options()

        self.assertEqual(options['user_agent'], user_agent)


if __name__ == '__main__':
    unittest.main()
