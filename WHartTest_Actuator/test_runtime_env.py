import os
import unittest
from unittest.mock import patch

from browser_installer import get_browser_path
from main import Config
from runtime_env import parse_bool_env, resolve_runtime_file_path, should_force_headless


class RuntimeEnvTests(unittest.TestCase):
    def test_parse_bool_env(self):
        self.assertTrue(parse_bool_env('true'))
        self.assertFalse(parse_bool_env('false'))
        self.assertIsNone(parse_bool_env('maybe'))

    @patch.dict(os.environ, {'WHARTTEST_ACTUATOR_DOCKER': 'true'}, clear=True)
    def test_force_headless_in_container_without_display(self):
        self.assertTrue(should_force_headless())

    @patch.dict(
        os.environ,
        {'WHARTTEST_ACTUATOR_DOCKER': 'true', 'DISPLAY': ':0'},
        clear=True,
    )
    def test_no_force_headless_when_display_available(self):
        self.assertFalse(should_force_headless())

    @patch.dict(os.environ, {'PLAYWRIGHT_BROWSERS_PATH': '/ms-playwright'}, clear=True)
    def test_browser_path_prefers_environment_variable(self):
        self.assertEqual(str(get_browser_path()), '/ms-playwright')

    @patch('runtime_env.os.path.exists', return_value=False)
    @patch.dict(os.environ, {'WHARTTEST_ACTUATOR_DOCKER': 'true'}, clear=True)
    def test_resolve_runtime_file_path_maps_host_data_to_container_data(self, _mock_exists):
        source = '/home/duanxc/code/wharttest/data/media/file_management/a.txt'

        self.assertEqual(
            resolve_runtime_file_path(source),
            '/app/data/media/file_management/a.txt',
        )

    @patch('runtime_env.os.path.exists', return_value=False)
    @patch.dict(
        os.environ,
        {
            'WHARTTEST_ACTUATOR_DOCKER': 'true',
            'WHARTTEST_ACTUATOR_HOST_DATA_DIR': '/workspace/wharttest/data',
            'WHARTTEST_ACTUATOR_CONTAINER_DATA_DIR': '/mnt/shared-data',
        },
        clear=True,
    )
    def test_resolve_runtime_file_path_uses_explicit_data_dirs(self, _mock_exists):
        source = '/workspace/wharttest/data/media/file_management/a.txt'

        self.assertEqual(
            resolve_runtime_file_path(source),
            '/mnt/shared-data/media/file_management/a.txt',
        )

    @patch.dict(os.environ, {'WHARTTEST_ACTUATOR_DOCKER': 'false'}, clear=True)
    def test_resolve_runtime_file_path_leaves_local_path_unchanged(self):
        source = '/home/duanxc/code/wharttest/data/media/file_management/a.txt'

        self.assertEqual(resolve_runtime_file_path(source), source)


class ConfigEnvTests(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            'WHARTTEST_ACTUATOR_WS_URL': 'ws://host.docker.internal:8000/ws/ui/actuator/',
            'WHARTTEST_ACTUATOR_API_URL': 'http://host.docker.internal:8000',
            'WHARTTEST_ACTUATOR_USE_GUI': 'false',
            'WHARTTEST_ACTUATOR_HEADLESS': 'true',
            'WHARTTEST_ACTUATOR_PERSISTENT': 'false',
            'WHARTTEST_ACTUATOR_API_USERNAME': 'admin',
            'WHARTTEST_ACTUATOR_API_PASSWORD': '  admin123456\n',
        },
        clear=True,
    )
    def test_config_load_from_env_overrides_compose_values(self):
        config = Config()
        config.use_gui = True
        config.headless = False
        config.persistent = True

        config.load_from_env()

        self.assertEqual(config.ws_url, 'ws://host.docker.internal:8000/ws/ui/actuator/')
        self.assertEqual(config.api_url, 'http://host.docker.internal:8000')
        self.assertFalse(config.use_gui)
        self.assertTrue(config.headless)
        self.assertFalse(config.persistent)
        self.assertEqual(config.api_username, 'admin')
        self.assertEqual(config.api_password, 'admin123456')
        self.assertNotIn('WHARTTEST_ACTUATOR_API_PASSWORD', os.environ)

    @patch.dict(os.environ, {'WHARTTEST_ACTUATOR_DOCKER': 'true'}, clear=True)
    def test_config_normalize_for_runtime_disables_gui_in_container(self):
        config = Config()
        config.use_gui = True
        config.headless = False

        config.normalize_for_runtime()

        self.assertFalse(config.use_gui)
        self.assertTrue(config.headless)

    @patch.dict(
        os.environ,
        {'WHARTTEST_ACTUATOR_DOCKER': 'true', 'DISPLAY': ':0'},
        clear=True,
    )
    def test_config_normalize_for_runtime_keeps_gui_when_display_available(self):
        config = Config()
        config.use_gui = True
        config.headless = False

        config.normalize_for_runtime()

        self.assertTrue(config.use_gui)
        self.assertFalse(config.headless)


if __name__ == '__main__':
    unittest.main()
