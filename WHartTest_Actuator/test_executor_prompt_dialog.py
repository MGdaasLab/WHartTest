#!/usr/bin/env python
"""录制 prompt 对话框回放：预载队列与 handle_dialog 出队语义测试。

队列按 page 隔离（WeakKeyDictionary）：并发执行多用例时各 page 队列互不干扰。
"""

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent))

from executor import PlaywrightExecutor, StepConfig


def _prompt_wait_step(prompt_value) -> StepConfig:
    """录制入库后的 prompt 步骤形态：ope_key=wait + ope_value.prompt_value。"""
    return StepConfig(
        step_id=1,
        operation_type='wait',
        locator_type='xpath',
        locator_value='',
        ope_value={'timeout': 1, 'prompt_value': prompt_value},
    )


class PromptDialogQueueTests(unittest.TestCase):
    """_load_prompt_dialog_queue 预载与 handle_dialog 出队语义。"""

    def setUp(self):
        self.executor = PlaywrightExecutor()
        self.page = MagicMock()

    def _dialog(self, type_='prompt'):
        dialog = MagicMock()
        dialog.type = type_
        dialog.message = '输入内容'
        dialog.accept = AsyncMock()
        dialog.dismiss = AsyncMock()
        return dialog

    def _queue(self, page=None):
        return self.executor._prompt_dialog_queues.get(page or self.page)

    def test_load_queue_collects_prompt_values_in_order(self):
        self.executor._load_prompt_dialog_queue(self.page, [
            _prompt_wait_step('默认名'),
            StepConfig(step_id=2, operation_type='wait', locator_type='xpath', locator_value=''),
            _prompt_wait_step('第二个'),
        ])
        self.assertEqual(list(self._queue()), ['默认名', '第二个'])

    def test_load_queue_none_clears_queue(self):
        self.executor._load_prompt_dialog_queue(self.page, [_prompt_wait_step('a')])
        self.executor._load_prompt_dialog_queue(self.page, None)
        self.assertEqual(len(self._queue()), 0)

    def test_cancel_branch_sentinel_false_stays_false(self):
        """取消分支哨兵 False 入队后仍为 False（区别于空串 accept）。"""
        self.executor._load_prompt_dialog_queue(self.page, [_prompt_wait_step(False)])
        self.assertEqual(list(self._queue()), [False])

    def test_queue_isolated_per_page(self):
        """并发场景：不同 page 的队列互不清空、互不串用。"""
        page_a = MagicMock()
        page_b = MagicMock()
        self.executor._load_prompt_dialog_queue(page_a, [_prompt_wait_step('A的值')])
        self.executor._load_prompt_dialog_queue(page_b, [_prompt_wait_step('B的值')])
        # page_b 预载不清掉 page_a 的队列
        self.assertEqual(list(self._queue(page_a)), ['A的值'])
        self.assertEqual(list(self._queue(page_b)), ['B的值'])
        # page_a 清空重载不影响 page_b
        self.executor._load_prompt_dialog_queue(page_a, None)
        self.assertEqual(len(self._queue(page_a)), 0)
        self.assertEqual(list(self._queue(page_b)), ['B的值'])

    def _run_handle_dialog(self, dialog, page=None):
        # handle_dialog 是 _setup_page_listeners 内部闭包，经由 page.on 注册；
        # 直接捕获注册的回调调用
        registered = self.executor._setup_page_listeners
        page = page or self.page
        handlers = {}

        def _on(event, handler):
            handlers[event] = handler

        page.on = _on
        registered(page)
        asyncio.run(handlers['dialog'](dialog))

    def test_handle_dialog_accepts_with_recorded_value(self):
        self.executor._load_prompt_dialog_queue(self.page, [_prompt_wait_step('默认名')])
        dialog = self._dialog()
        self._run_handle_dialog(dialog)
        dialog.accept.assert_awaited_once_with('默认名')
        dialog.dismiss.assert_not_awaited()

    def test_handle_dialog_consumes_own_page_queue_only(self):
        """并发场景：dialog 出队只消费所属 page 的队列。"""
        page_a = MagicMock()
        page_b = MagicMock()
        self.executor._load_prompt_dialog_queue(page_a, [_prompt_wait_step('A的值')])
        self.executor._load_prompt_dialog_queue(page_b, [_prompt_wait_step('B的值')])
        dialog = self._dialog()
        self._run_handle_dialog(dialog, page_a)
        dialog.accept.assert_awaited_once_with('A的值')
        # page_b 的队列不受影响
        self.assertEqual(list(self._queue(page_b)), ['B的值'])

    def test_handle_dialog_dismisses_on_cancel_sentinel(self):
        self.executor._load_prompt_dialog_queue(self.page, [_prompt_wait_step(False)])
        dialog = self._dialog()
        self._run_handle_dialog(dialog)
        dialog.dismiss.assert_awaited_once()
        dialog.accept.assert_not_awaited()

    def test_handle_dialog_empty_queue_falls_back_to_empty_accept(self):
        """无队列数据（手写用例/旧数据）：accept 空串，与旧行为一致。"""
        dialog = self._dialog()
        self._run_handle_dialog(dialog)
        dialog.accept.assert_awaited_once_with('')

    def test_handle_dialog_confirm_bypasses_queue(self):
        """confirm/alert 不消费 prompt 队列：直接 accept 确定分支。"""
        self.executor._load_prompt_dialog_queue(self.page, [_prompt_wait_step('默认名')])
        dialog = self._dialog(type_='confirm')
        self._run_handle_dialog(dialog)
        dialog.accept.assert_awaited_once_with()
        # 队列未被消费
        self.assertEqual(list(self._queue()), ['默认名'])

    def test_handle_dialog_log_does_not_leak_value(self):
        """回放日志只记录值长度，不落明文（敏感信息不写日志）。"""
        secret = '机密密码123'
        self.executor._load_prompt_dialog_queue(self.page, [_prompt_wait_step(secret)])
        dialog = self._dialog()
        with self.assertLogs(level='INFO') as captured:
            self._run_handle_dialog(dialog)
        joined = '\n'.join(captured.output)
        self.assertNotIn(secret, joined)
        self.assertIn('长度', joined)


if __name__ == '__main__':
    unittest.main()
