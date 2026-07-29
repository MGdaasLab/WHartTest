import importlib.util
import time
import unittest
import uuid
from pathlib import Path

from skill_test_support import API_KEY, BASE_URL, BackendAdmin, ResultReader, SkillCLI

SKILL_PATH = Path(__file__).resolve().with_name('api_automation_tools.py')
SQLITE_PATH = Path('/tmp') / f'wharttest_api_skill_full_{uuid.uuid4().hex[:8]}.sqlite3'


def load_action_names():
    spec = importlib.util.spec_from_file_location('api_automation_tools', SKILL_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return set(module.ACTIONS)


class ApiAutomationSkillIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.all_actions = load_action_names()
        cls.admin = BackendAdmin()
        cls.project = cls.admin.create_project()
        cls.project_id = cls.project['id']
        cls.skill = SkillCLI(cls.project_id)
        cls.ids = {}
        cls.names = {}
        cls.addClassCleanup(cls._cleanup_project)
        cls.addClassCleanup(cls._cleanup_sqlite)

    @classmethod
    def _cleanup_project(cls):
        try:
            cls.admin.delete_project(cls.project_id)
        except Exception as exc:
            print(f'cleanup project failed: {exc}')

    @classmethod
    def _cleanup_sqlite(cls):
        try:
            SQLITE_PATH.unlink(missing_ok=True)
        except Exception as exc:
            print(f'cleanup sqlite failed: {exc}')

    def run_action(self, action, payload=None, params=None, **id_args):
        return self.skill.run(action, payload=payload, params=params, **id_args)

    def unique_name(self, prefix):
        return f'{prefix}-{uuid.uuid4().hex[:8]}'

    def wait_until(self, callback, timeout=60, interval=1, message='等待条件满足超时'):
        end_time = time.time() + timeout
        last_value = None
        while time.time() < end_time:
            last_value = callback()
            if last_value:
                return last_value
            time.sleep(interval)
        raise AssertionError(f'{message}，最后一次结果: {last_value}')

    def extract_testcase_steps(self, testcase_result):
        def walk(node):
            if isinstance(node, dict):
                for key in ('steps', 'steps_info', 'test_steps'):
                    value = node.get(key)
                    if isinstance(value, list) and value and all(isinstance(item, dict) and 'id' in item for item in value):
                        return value
                for value in node.values():
                    found = walk(value)
                    if found:
                        return found
            elif isinstance(node, list):
                for item in node:
                    found = walk(item)
                    if found:
                        return found
            return []

        steps = walk(ResultReader.data(testcase_result))
        if not steps:
            raise AssertionError(f'未从测试用例结果中找到步骤列表: {testcase_result}')
        return steps

    def ensure_list_has_id(self, action, field_name, **id_args):
        result = self.run_action(action, **id_args)
        item_id = ResultReader.latest_id(result)
        self.ids[field_name] = item_id
        return item_id

    def test_full_action_coverage(self):
        module_root_name = self.unique_name('module-root')
        module_child_name = self.unique_name('module-child')
        db_name = self.unique_name('sqlite-db')
        env_name = self.unique_name('env')
        cloned_env_name = self.unique_name('env-clone')
        header_name = self.unique_name('X-Skill-Test')
        function_name = self.unique_name('fn')
        interface_name = self.unique_name('iface')
        tag_name = self.unique_name('tag')
        group_root_name = self.unique_name('group-root')
        group_child_name = self.unique_name('group-child')
        testcase_name = self.unique_name('tc-main')
        slow_testcase_name = self.unique_name('tc-slow')
        suite_name = self.unique_name('suite-main')
        cancel_suite_name = self.unique_name('suite-cancel')
        sync_name = self.unique_name('sync')
        global_sync_name = self.unique_name('global-sync')

        root_module = self.run_action('create_module', payload={'name': module_root_name})
        self.ids['module_root'] = ResultReader.extract_id(root_module)
        child_module = self.run_action(
            'create_module',
            payload={'name': module_child_name, 'parent': self.ids['module_root']},
        )
        self.ids['module_child'] = ResultReader.extract_id(child_module)
        self.run_action('list_modules')
        self.run_action('get_module', module_id=self.ids['module_root'])
        self.run_action('update_module', payload={'description': 'updated root module'}, module_id=self.ids['module_root'])
        self.run_action('get_module_tree')
        self.run_action('search_modules', params={'keyword': module_child_name})

        database_config = self.run_action(
            'create_database_config',
            payload={
                'name': db_name,
                'type': 'sqlite',
                'host': 'local',
                'port': 0,
                'username': 'tester',
                'password': 'secret',
                'database': str(SQLITE_PATH),
            },
        )
        self.ids['database_config'] = ResultReader.extract_id(database_config)
        self.run_action('list_database_configs')
        self.run_action('get_database_config', database_config_id=self.ids['database_config'])
        self.run_action(
            'update_database_config',
            payload={'host': 'local-updated'},
            database_config_id=self.ids['database_config'],
        )
        self.run_action('test_database_connection', payload={'db_type': 'sqlite', 'database': str(SQLITE_PATH)})
        self.run_action('test_saved_database_connection', database_config_id=self.ids['database_config'])

        environment = self.run_action(
            'create_environment',
            payload={
                'name': env_name,
                'base_url': BASE_URL,
                'database_config': self.ids['database_config'],
            },
        )
        self.ids['environment'] = ResultReader.extract_id(environment)
        self.run_action('list_environments')
        self.run_action('get_environment', environment_id=self.ids['environment'])
        self.run_action(
            'update_environment',
            payload={'description': 'updated environment'},
            environment_id=self.ids['environment'],
        )

        variable = self.run_action(
            'create_environment_variable',
            payload={
                'environment': self.ids['environment'],
                'name': self.unique_name('var-single'),
                'value': 'alpha',
                'type': 'string',
            },
        )
        self.ids['variable_single'] = ResultReader.extract_id(variable)
        self.run_action('list_environment_variables')
        self.run_action('get_environment_variable', variable_id=self.ids['variable_single'])
        self.run_action(
            'update_environment_variable',
            payload={'value': 'beta'},
            variable_id=self.ids['variable_single'],
        )

        batch_var_name = self.unique_name('var-batch')
        self.run_action(
            'batch_create_environment_variables',
            payload={
                'environment_id': self.ids['environment'],
                'variables': [{'name': batch_var_name, 'value': 'gamma', 'type': 'string'}],
            },
        )
        variables_after_batch = self.run_action('list_environment_variables')
        batch_var = ResultReader.find_by_name(variables_after_batch, batch_var_name)
        self.ids['variable_batch'] = batch_var['id']
        self.run_action(
            'batch_update_environment_variables',
            payload={'variables': [{'id': self.ids['variable_batch'], 'value': 'delta'}]},
        )
        cloned_environment = self.run_action(
            'clone_environment',
            payload={'name': cloned_env_name},
            environment_id=self.ids['environment'],
        )
        self.ids['environment_clone'] = ResultReader.extract_id(cloned_environment)

        header = self.run_action(
            'create_global_header',
            payload={'name': header_name, 'value': API_KEY},
        )
        self.ids['header'] = ResultReader.extract_id(header)
        self.run_action('list_global_headers')
        self.run_action('get_global_header', header_id=self.ids['header'])
        self.run_action('update_global_header', payload={'value': 'updated-header'}, header_id=self.ids['header'])

        function = self.run_action(
            'create_function',
            payload={'name': function_name, 'code': 'def add(a, b):\n    return a + b'},
        )
        self.ids['function'] = ResultReader.extract_id(function)
        self.run_action('list_functions')
        self.run_action('get_function', function_id=self.ids['function'])
        self.run_action(
            'update_function',
            payload={'description': 'updated function'},
            function_id=self.ids['function'],
        )
        self.run_action('generate_debugtalk')
        self.run_action(
            'execute_function',
            payload={'code': 'def add(a, b):\n    return a + b', 'test_args': {'a': 1, 'b': 2}},
        )

        interface_url_a = f'{BASE_URL}/api/projects/{self.project_id}/api-modules/'
        interface_url_b = f'{BASE_URL}/api/projects/{self.project_id}/api-modules/?page=1'
        interface_url_c = f'{BASE_URL}/api/projects/{self.project_id}/api-modules/?page=2'
        interface = self.run_action(
            'create_interface',
            payload={
                'name': interface_name,
                'type': 'http',
                'method': 'GET',
                'url': interface_url_a,
                'module': self.ids['module_child'],
                'headers': {'X-API-Key': API_KEY},
            },
        )
        self.ids['interface'] = ResultReader.extract_id(interface)
        self.run_action('list_interfaces')
        self.run_action('get_interface', interface_id=self.ids['interface'])
        self.run_action(
            'update_interface',
            payload={'description': 'updated interface'},
            interface_id=self.ids['interface'],
        )
        self.run_action(
            'quick_debug_interface',
            payload={
                'name': self.unique_name('quick-debug'),
                'type': 'http',
                'method': 'GET',
                'url': f'{BASE_URL}/api/projects/',
                'headers': {'X-API-Key': API_KEY},
            },
        )
        self.run_action('run_interface', interface_id=self.ids['interface'])
        interface_result_id = self.ensure_list_has_id('list_interface_results', 'interface_result')
        self.run_action('get_interface_result', interface_result_id=interface_result_id)

        tag = self.run_action('create_testcase_tag', payload={'name': tag_name})
        self.ids['tag'] = ResultReader.extract_id(tag)
        self.run_action('list_testcase_tags')
        self.run_action('get_testcase_tag', tag_id=self.ids['tag'])
        self.run_action('update_testcase_tag', payload={'color': '#ff0000'}, tag_id=self.ids['tag'])
        self.run_action('get_tag_statistics')

        group_root = self.run_action('create_testcase_group', payload={'name': group_root_name})
        self.ids['group_root'] = ResultReader.extract_id(group_root)
        group_child = self.run_action(
            'create_testcase_group',
            payload={'name': group_child_name, 'parent': self.ids['group_root']},
        )
        self.ids['group_child'] = ResultReader.extract_id(group_child)
        self.run_action('list_testcase_groups')
        self.run_action('get_testcase_group', group_id=self.ids['group_child'])
        self.run_action(
            'update_testcase_group',
            payload={'description': 'updated group'},
            group_id=self.ids['group_child'],
        )
        self.run_action('get_testcase_group_tree')

        testcase = self.run_action(
            'create_testcase',
            payload={
                'name': testcase_name,
                'group': self.ids['group_child'],
                'tags': [self.ids['tag']],
                'steps_info': [
                    {'name': 'step-one', 'interface_id': self.ids['interface']},
                    {'name': 'step-two', 'interface_id': self.ids['interface']},
                ],
            },
        )
        self.ids['testcase'] = ResultReader.extract_id(testcase)

        slow_testcase = self.run_action(
            'create_testcase',
            payload={
                'name': slow_testcase_name,
                'steps_info': [
                    {'name': f'slow-step-{index}', 'interface_id': self.ids['interface']}
                    for index in range(1, 61)
                ],
            },
        )
        self.ids['slow_testcase'] = ResultReader.extract_id(slow_testcase)
        self.run_action('list_testcases')
        testcase_detail = self.run_action('get_testcase', testcase_id=self.ids['testcase'])
        self.run_action('update_testcase', payload={'name': f'{testcase_name}-updated'}, testcase_id=self.ids['testcase'])
        self.run_action('get_available_interfaces')
        self.run_action('get_referenced_interfaces', testcase_id=self.ids['testcase'])
        self.run_action('get_group_testcases', group_id=self.ids['group_child'])
        copied_testcase = self.run_action('copy_testcase', testcase_id=self.ids['testcase'])
        self.ids['copied_testcase'] = ResultReader.extract_id(copied_testcase)

        steps = self.extract_testcase_steps(testcase_detail)
        steps = sorted(steps, key=lambda item: item.get('order', 0))
        self.ids['step_first'] = steps[0]['id']
        self.ids['step_second'] = steps[1]['id']
        self.run_action(
            'update_testcase_step',
            payload={'step_id': self.ids['step_first'], 'name': 'step-one-updated'},
            testcase_id=self.ids['testcase'],
        )
        self.run_action(
            'reorder_testcase_steps',
            payload={
                'steps': [
                    {'step_id': self.ids['step_second'], 'order': 1},
                    {'step_id': self.ids['step_first'], 'order': 2},
                ]
            },
            testcase_id=self.ids['testcase'],
        )
        self.run_action(
            'delete_testcase_step',
            testcase_id=self.ids['testcase'],
            step_id=self.ids['step_second'],
        )
        self.run_action('run_testcase', payload={'environment_id': self.ids['environment']}, testcase_id=self.ids['testcase'])
        self.run_action(
            'batch_run_testcases',
            payload={'testcase_ids': [self.ids['testcase'], self.ids['copied_testcase']], 'environment_id': self.ids['environment']},
        )
        self.run_action('get_history_reports', testcase_id=self.ids['testcase'])
        test_report_id = self.ensure_list_has_id('list_test_reports', 'test_report')
        self.run_action('get_test_report', test_report_id=test_report_id)

        suite = self.run_action('create_task_suite', payload={'name': suite_name})
        self.ids['task_suite'] = ResultReader.extract_id(suite)
        cancel_suite = self.run_action('create_task_suite', payload={'name': cancel_suite_name})
        self.ids['cancel_task_suite'] = ResultReader.extract_id(cancel_suite)
        self.run_action('list_task_suites')
        self.run_action('get_task_suite', task_suite_id=self.ids['task_suite'])
        self.run_action('update_task_suite', payload={'fail_fast': True}, task_suite_id=self.ids['task_suite'])
        self.run_action(
            'add_suite_testcases',
            payload={'testcase_ids': [self.ids['testcase'], self.ids['copied_testcase']]},
            task_suite_id=self.ids['task_suite'],
        )
        self.run_action(
            'add_suite_testcases',
            payload={'testcase_ids': [self.ids['slow_testcase']]},
            task_suite_id=self.ids['cancel_task_suite'],
        )
        execution = self.run_action('execute_task_suite', payload={'task_suite_id': self.ids['task_suite']})
        execution_id = ResultReader.extract_id(execution)
        self.ids['task_execution'] = execution_id
        self.run_action('list_task_executions')
        self.run_action('get_task_execution', task_execution_id=execution_id)
        self.run_action('get_task_case_results', task_execution_id=execution_id)

        cancel_execution = self.run_action('execute_task_suite', payload={'task_suite_id': self.ids['cancel_task_suite']})
        self.ids['cancel_execution'] = ResultReader.extract_id(cancel_execution)
        self.run_action('cancel_task_execution', task_execution_id=self.ids['cancel_execution'])
        self.run_action(
            'remove_suite_testcase',
            task_suite_id=self.ids['task_suite'],
            testcase_id=self.ids['copied_testcase'],
        )

        self.run_action(
            'update_interface',
            payload={'url': interface_url_b},
            interface_id=self.ids['interface'],
        )
        sync_config = self.run_action(
            'create_sync_config',
            payload={
                'name': sync_name,
                'interface': self.ids['interface'],
                'testcase': self.ids['testcase'],
                'step': self.ids['step_first'],
                'sync_fields': ['url'],
            },
        )
        self.ids['sync_config'] = ResultReader.extract_id(sync_config)
        self.run_action('list_sync_configs')
        self.run_action('get_sync_config', sync_config_id=self.ids['sync_config'])
        self.run_action(
            'update_sync_config',
            payload={'sync_fields': ['url', 'headers']},
            sync_config_id=self.ids['sync_config'],
        )
        global_sync = self.run_action(
            'create_global_sync_config',
            payload={
                'name': global_sync_name,
                'sync_fields': ['url'],
                'sync_enabled': True,
                'sync_mode': 'manual',
                'is_active': False,
            },
        )
        self.ids['global_sync_config'] = ResultReader.extract_id(global_sync)
        self.run_action('list_global_sync_configs')
        self.run_action('get_global_sync_config', global_sync_config_id=self.ids['global_sync_config'])
        self.run_action(
            'update_global_sync_config',
            payload={'sync_fields': ['url', 'method']},
            global_sync_config_id=self.ids['global_sync_config'],
        )
        self.run_action(
            'set_active_global_sync_config',
            global_sync_config_id=self.ids['global_sync_config'],
        )
        self.run_action('get_current_global_sync_config')
        self.run_action('sync_now', sync_config_id=self.ids['sync_config'])

        def first_sync_history():
            result = self.run_action('list_sync_histories')
            items = ResultReader.items(result)
            return items[0] if items else None

        sync_history = self.wait_until(
            first_sync_history,
            timeout=90,
            interval=2,
            message='等待 sync_now 生成同步历史超时，请先启动 celery worker',
        )
        self.ids['sync_history'] = sync_history['id']

        self.run_action(
            'update_interface',
            payload={'url': interface_url_c},
            interface_id=self.ids['interface'],
        )
        self.run_action('batch_sync', payload={'config_ids': [self.ids['sync_config']]})

        def enough_sync_histories():
            result = self.run_action('list_sync_histories')
            items = ResultReader.items(result)
            return items if len(items) >= 2 else None

        sync_histories = self.wait_until(
            enough_sync_histories,
            timeout=90,
            interval=2,
            message='等待 batch_sync 生成第二条同步历史超时，请先启动 celery worker',
        )
        self.ids['sync_history_second'] = sync_histories[0]['id']
        self.run_action('get_sync_history', sync_history_id=self.ids['sync_history'])
        self.run_action('rollback_sync_history', sync_history_id=self.ids['sync_history_second'])

        self.run_action('delete_global_sync_config', global_sync_config_id=self.ids['global_sync_config'])
        self.run_action('delete_sync_config', sync_config_id=self.ids['sync_config'])
        self.run_action('delete_task_suite', task_suite_id=self.ids['cancel_task_suite'])
        self.run_action('delete_task_suite', task_suite_id=self.ids['task_suite'])
        self.run_action('delete_testcase', testcase_id=self.ids['copied_testcase'])
        self.run_action('delete_testcase', testcase_id=self.ids['slow_testcase'])
        self.run_action('delete_testcase', testcase_id=self.ids['testcase'])
        self.run_action('delete_testcase_group', group_id=self.ids['group_child'])
        self.run_action('delete_testcase_group', group_id=self.ids['group_root'])
        self.run_action('delete_testcase_tag', tag_id=self.ids['tag'])
        self.run_action('delete_interface', interface_id=self.ids['interface'])
        self.run_action('delete_function', function_id=self.ids['function'])
        self.run_action('delete_global_header', header_id=self.ids['header'])
        self.run_action('delete_environment_variable', variable_id=self.ids['variable_single'])
        self.run_action('delete_environment_variable', variable_id=self.ids['variable_batch'])
        self.run_action('delete_environment', environment_id=self.ids['environment_clone'])
        self.run_action('delete_environment', environment_id=self.ids['environment'])
        self.run_action('delete_database_config', database_config_id=self.ids['database_config'])
        self.run_action('delete_module', module_id=self.ids['module_child'])
        self.run_action('delete_module', module_id=self.ids['module_root'])

        missing_actions = sorted(self.all_actions - self.skill.executed_actions)
        self.assertFalse(missing_actions, f'以下 actions 未被覆盖: {missing_actions}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
