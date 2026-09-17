#!/usr/bin/env python
"""SQL step execution tests for PlaywrightExecutor."""

import asyncio
import os
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


class StepSqlConnectionPolicyTests(unittest.TestCase):
    """SQL 步骤自带连接默认必须被忽略（不可信输入）。"""

    def setUp(self):
        self.executor = PlaywrightExecutor()
        self.env_config = {
            'db_type': 'mysql',
            'db_rud_status': True,
            'db_c_status': True,
            'mysql_config': {
                'host': 'db.internal',
                'port': 3306,
                'database': 'app',
                'user': 'env-user',
                'password': 'env-pass',
            },
        }

    def _sql_config(self, *, with_step_connection: bool) -> dict:
        config = {
            'sql': 'SELECT 1',
            'params': None,
            'method': 'fetchall',
            'size': 1,
            'first_keyword': 'select',
            'db_type': 'mysql',
        }
        if with_step_connection:
            config['connection'] = {
                'host': '10.0.0.9',
                'port': 3306,
                'database': 'other',
                'user': 'attacker',
                'password': 'payload',
            }
        return config

    def test_step_connection_ignored_by_default(self):
        db_type, db_config = self.executor._resolve_sql_connection_config(
            self._sql_config(with_step_connection=True), self.env_config
        )
        self.assertEqual(db_config['host'], 'db.internal')
        self.assertEqual(db_config['user'], 'env-user')

    def test_env_config_used_when_no_step_connection(self):
        db_type, db_config = self.executor._resolve_sql_connection_config(
            self._sql_config(with_step_connection=False), self.env_config
        )
        self.assertEqual(db_config['host'], 'db.internal')

    def test_step_connection_allowed_when_explicitly_enabled(self):
        with patch.dict(os.environ, {'WHARTTEST_ACTUATOR_ALLOW_STEP_DB_CONNECTION': 'true'}):
            db_type, db_config = self.executor._resolve_sql_connection_config(
                self._sql_config(with_step_connection=True), self.env_config
            )
        self.assertEqual(db_config['host'], '10.0.0.9')
        self.assertEqual(db_config['user'], 'attacker')

    def test_missing_env_connection_still_errors(self):
        env_without_db = {'db_type': 'mysql', 'db_rud_status': True}
        with self.assertRaises(ValueError):
            self.executor._resolve_sql_connection_config(
                self._sql_config(with_step_connection=True), env_without_db
            )


if __name__ == '__main__':
    unittest.main()
