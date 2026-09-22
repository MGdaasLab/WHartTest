#!/usr/bin/env python
"""Captcha recognition tests for PlaywrightExecutor."""

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent))

from executor import PlaywrightExecutor, StepConfig


class PlaywrightExecutorCaptchaTest(unittest.TestCase):
    def setUp(self):
        self.executor = PlaywrightExecutor()

    def test_captcha_recognize_success(self):
        step = StepConfig(
            step_id=10,
            operation_type='captcha_recognize',
            locator_type='xpath',
            locator_value='//img[@id="captcha"]',
            ope_value={
                'target_locator': {
                    'locator_type': 'xpath',
                    'locator_value': '//input[@name="code"]',
                },
                'retry_count': 2,
                'click_to_refresh': True,
            },
        )

        mock_page = MagicMock()
        mock_img_locator = MagicMock()
        mock_img_locator.screenshot = AsyncMock(return_value=b'fake_image_bytes')
        mock_img_locator.click = AsyncMock()

        mock_target_locator = MagicMock()
        mock_target_locator.fill = AsyncMock()

        mock_page.locator.side_effect = lambda val: (
            mock_img_locator if 'captcha' in val else mock_target_locator
        )
        mock_page.wait_for_timeout = AsyncMock()

        mock_ocr = MagicMock()
        mock_ocr.classification.return_value = 'abcd'

        async def run_test():
            with patch.object(self.executor, '_get_ocr_instance', return_value=mock_ocr):
                success, msg, sc = await self.executor._execute_captcha_recognize(
                    mock_page, mock_img_locator, step
                )
                return success, msg, sc

        success, msg, sc = asyncio.run(run_test())

        self.assertTrue(success)
        self.assertIn('abcd', msg)
        mock_target_locator.fill.assert_awaited_once_with('abcd')

    def test_captcha_recognize_missing_target_locator(self):
        step = StepConfig(
            step_id=11,
            operation_type='captcha_recognize',
            locator_type='xpath',
            locator_value='//img[@id="captcha"]',
            ope_value={},
        )
        mock_page = MagicMock()
        mock_img_locator = MagicMock()

        async def run_test():
            with patch.object(self.executor, '_get_ocr_instance', return_value=MagicMock()):
                success, msg, sc = await self.executor._execute_captcha_recognize(
                    mock_page, mock_img_locator, step
                )
                return success, msg, sc

        success, msg, sc = asyncio.run(run_test())
        self.assertFalse(success)
        self.assertIn('缺少目标输入框定位信息', msg)

    def test_captcha_recognize_missing_ddddocr_returns_error(self):
        step = StepConfig(
            step_id=12,
            operation_type='captcha_recognize',
            locator_type='xpath',
            locator_value='//img[@id="captcha"]',
            ope_value={
                'target_locator': {'locator_type': 'xpath', 'locator_value': '//input'},
            },
        )
        mock_page = MagicMock()
        mock_img_locator = MagicMock()

        async def run_test():
            with patch.object(self.executor, '_get_ocr_instance', return_value=None):
                success, msg, sc = await self.executor._execute_captcha_recognize(
                    mock_page, mock_img_locator, step
                )
                return success, msg, sc

        success, msg, sc = asyncio.run(run_test())
        self.assertFalse(success)
        self.assertIn('未安装 ddddocr', msg)


if __name__ == '__main__':
    unittest.main()
