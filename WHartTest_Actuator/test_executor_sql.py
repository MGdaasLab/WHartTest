#!/usr/bin/env python
"""SQL step execution tests for PlaywrightExecutor."""

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

from executor import PlaywrightExecutor, StepConfig


class PlaywrightExecutorSqlTest(unittest.TestCase):
    def setUp(self):
        self.executor = PlaywrightExecutor()

    def _sql_step(self, sql_execute):
        return StepConfig(
            step_id=1,
            operation_type='',
            locator_type='xpath',
            locator_value='',
            step_type=2,
            sql_execute=sql_execute,
        )

    def test_normalize_sql_execute_defaults_select_to_fetchall(self):
        step = self._sql_step({
            'sql': 'SELECT * FROM users WHERE id = %(id)s',
            'params': {'id': 1},
        })

        config = self.executor._normalize_sql_execute(step)

        self.assertEqual(config['method'], 'fetchall')
        self.assertEqual(config['params'], {'id': 1})
        self.assertEqual(config['first_keyword'], 'select')

    def test_sql_step_branch_does_not_need_page_or_locator(self):
        step = self._sql_step({'sql': 'SELECT 1'})
        step.operation_type = None
        env_config = {'db_rud_status': True}

        async def run_step():
            with patch.object(self.executor, '_execute_sql_step', return_value=(True, 'ok')) as run_sql:
                success, message, screenshot = await self.executor._execute_step(None, step, env_config)
                run_sql.assert_called_once_with(step, env_config)
                return success, message, screenshot

        success, message, screenshot = asyncio.run(run_step())

        self.assertTrue(success)
        self.assertEqual(message, 'ok')
        self.assertIsNone(screenshot)


if __name__ == '__main__':
    unittest.main()
