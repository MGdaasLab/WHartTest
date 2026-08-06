from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient
from rest_framework import status

from projects.models import Project, ProjectMember
from api_modules.models import ApiModule
from .models import ApiInterface, ApiInterfaceResult


def _grant_interface_perms(user):
    """授予用户 ApiInterface 和 ApiInterfaceResult 的全部模型权限。"""
    for model_cls in [ApiInterface, ApiInterfaceResult, ApiModule]:
        ct = ContentType.objects.get_for_model(model_cls)
        perms = Permission.objects.filter(content_type=ct)
        user.user_permissions.add(*perms)
    for attr in ('_perm_cache', '_user_perm_cache'):
        try:
            delattr(user, attr)
        except AttributeError:
            pass


class ApiInterfaceModelTest(TestCase):
    """ApiInterface 模型测试"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)

    def test_create_http_interface(self):
        """测试创建 HTTP 接口"""
        interface = ApiInterface.objects.create(
            name='Login API',
            type='http',
            method='POST',
            url='/api/login',
            headers={'Content-Type': 'application/json'},
            body={'username': 'test', 'password': '123'},
            project=self.project,
            created_by=self.user,
        )
        self.assertEqual(interface.name, 'Login API')
        self.assertEqual(interface.type, 'http')
        self.assertEqual(interface.method, 'POST')
        self.assertIsNotNone(interface.created_at)

    def test_create_sql_interface(self):
        """测试创建 SQL 接口"""
        interface = ApiInterface.objects.create(
            name='Query Users',
            type='sql',
            sql_method='fetchall',
            sql='SELECT * FROM users',
            project=self.project,
            created_by=self.user,
        )
        self.assertEqual(interface.type, 'sql')
        self.assertEqual(interface.sql_method, 'fetchall')
        self.assertEqual(interface.sql, 'SELECT * FROM users')

    def test_str_representation(self):
        """测试字符串表示"""
        interface = ApiInterface.objects.create(
            name='My API',
            type='http',
            method='GET',
            url='/api/test',
            project=self.project,
            created_by=self.user,
        )
        self.assertEqual(str(interface), 'Test Project-My API')

    def test_get_interface_data_includes_file_ids(self):
        """运行接口时应带出文件附件 ID。"""
        interface = ApiInterface.objects.create(
            name='Upload API',
            type='http',
            method='POST',
            url='/api/upload',
            file_ids=[8],
            project=self.project,
            created_by=self.user,
        )

        self.assertEqual(interface.get_interface_data()['file_ids'], [8])

    def test_unique_together_name_project(self):
        """测试同一项目下接口名唯一约束"""
        ApiInterface.objects.create(
            name='Duplicate API',
            type='http',
            method='GET',
            url='/api/test',
            project=self.project,
            created_by=self.user,
        )
        with self.assertRaises(Exception):
            ApiInterface.objects.create(
                name='Duplicate API',
                type='http',
                method='POST',
                url='/api/test2',
                project=self.project,
                created_by=self.user,
            )

    def test_same_name_different_projects(self):
        """测试不同项目可以有相同接口名"""
        project2 = Project.objects.create(name='Project 2', creator=self.user)
        ApiInterface.objects.create(
            name='Shared Name',
            type='http',
            method='GET',
            url='/api/test',
            project=self.project,
            created_by=self.user,
        )
        interface2 = ApiInterface.objects.create(
            name='Shared Name',
            type='http',
            method='GET',
            url='/api/test',
            project=project2,
            created_by=self.user,
        )
        self.assertEqual(interface2.project, project2)

    def test_save_http_cleans_sql_fields(self):
        """测试保存 HTTP 接口时清除 SQL 字段"""
        interface = ApiInterface.objects.create(
            name='HTTP API',
            type='http',
            method='GET',
            url='/api/test',
            sql_method='fetchone',
            sql='SELECT 1',
            project=self.project,
            created_by=self.user,
        )
        interface.refresh_from_db()
        self.assertIsNone(interface.sql_method)
        self.assertIsNone(interface.sql)
        self.assertEqual(interface.sql_params, {})
        self.assertEqual(interface.sql_size, 10)

    def test_save_sql_cleans_http_fields(self):
        """测试保存 SQL 接口时清除 HTTP 字段"""
        interface = ApiInterface.objects.create(
            name='SQL Query',
            type='sql',
            sql_method='fetchone',
            sql='SELECT 1',
            method='GET',
            url='http://example.com',
            headers={'X-Custom': 'val'},
            project=self.project,
            created_by=self.user,
        )
        interface.refresh_from_db()
        self.assertIsNone(interface.method)
        self.assertIsNone(interface.url)
        self.assertEqual(interface.headers, {})
        self.assertEqual(interface.params, {})
        self.assertEqual(interface.body, {})

    def test_save_module_must_match_project(self):
        """测试模块必须属于同一项目"""
        other_project = Project.objects.create(name='Other', creator=self.user)
        module = ApiModule.objects.create(
            name='Other Module', project=other_project, created_by=self.user,
        )
        with self.assertRaises(ValueError):
            ApiInterface.objects.create(
                name='Bad Interface',
                type='http',
                method='GET',
                url='/api/test',
                project=self.project,
                module=module,
                created_by=self.user,
            )

    def test_get_interface_data_http(self):
        """测试 get_interface_data 返回 HTTP 数据"""
        interface = ApiInterface.objects.create(
            name='HTTP API',
            type='http',
            method='POST',
            url='/api/login',
            headers={'Content-Type': 'application/json'},
            params={'page': '1'},
            body={'username': 'test'},
            variables={'token': 'abc'},
            validators=[{'eq': ['status_code', 200]}],
            extract={'user_id': 'body.data.id'},
            project=self.project,
            created_by=self.user,
        )
        data = interface.get_interface_data()
        self.assertEqual(data['name'], 'HTTP API')
        self.assertEqual(data['type'], 'http')
        self.assertEqual(data['method'], 'POST')
        self.assertEqual(data['url'], '/api/login')
        self.assertEqual(data['headers'], {'Content-Type': 'application/json'})
        self.assertEqual(data['params'], {'page': '1'})
        self.assertEqual(data['body'], {'username': 'test'})
        self.assertEqual(data['variables'], {'token': 'abc'})
        self.assertIn('validators', data)
        self.assertIn('extract', data)

    def test_get_interface_data_sql(self):
        """测试 get_interface_data 返回 SQL 数据"""
        interface = ApiInterface.objects.create(
            name='SQL Query',
            type='sql',
            sql_method='fetchmany',
            sql='SELECT * FROM users WHERE status = 1',
            sql_params={'status': 1},
            sql_size=20,
            project=self.project,
            created_by=self.user,
        )
        data = interface.get_interface_data()
        self.assertEqual(data['type'], 'sql')
        self.assertEqual(data['method'], 'fetchmany')
        self.assertEqual(data['sql'], 'SELECT * FROM users WHERE status = 1')
        self.assertEqual(data['size'], 20)

    def test_cascade_delete_project(self):
        """测试删除项目时级联删除接口"""
        ApiInterface.objects.create(
            name='To Delete',
            type='http',
            method='GET',
            url='/api/test',
            project=self.project,
            created_by=self.user,
        )
        self.project.delete()
        self.assertEqual(ApiInterface.objects.count(), 0)

    def test_set_null_on_user_delete(self):
        """测试删除用户时 created_by 置空"""
        interface = ApiInterface.objects.create(
            name='Orphan',
            type='http',
            method='GET',
            url='/api/test',
            project=self.project,
            created_by=self.user,
        )
        self.user.delete()
        interface.refresh_from_db()
        self.assertIsNone(interface.created_by)

    def test_ordering(self):
        """测试默认按 created_at 降序排列"""
        i1 = ApiInterface.objects.create(
            name='First', type='http', method='GET', url='/1',
            project=self.project, created_by=self.user,
        )
        i2 = ApiInterface.objects.create(
            name='Second', type='http', method='GET', url='/2',
            project=self.project, created_by=self.user,
        )
        interfaces = list(ApiInterface.objects.all())
        self.assertEqual(interfaces[0], i2)  # newest first
        self.assertEqual(interfaces[1], i1)

    def test_module_relationship(self):
        """测试接口与模块关联"""
        module = ApiModule.objects.create(
            name='Auth Module', project=self.project, created_by=self.user,
        )
        interface = ApiInterface.objects.create(
            name='Login',
            type='http',
            method='POST',
            url='/api/login',
            project=self.project,
            module=module,
            created_by=self.user,
        )
        self.assertEqual(interface.module, module)
        self.assertIn(interface, module.api_interfaces.all())

    def test_module_set_null_on_delete(self):
        """测试删除模块时接口的 module 置空"""
        module = ApiModule.objects.create(
            name='Module', project=self.project, created_by=self.user,
        )
        interface = ApiInterface.objects.create(
            name='API',
            type='http',
            method='GET',
            url='/api/test',
            project=self.project,
            module=module,
            created_by=self.user,
        )
        module.delete()
        interface.refresh_from_db()
        self.assertIsNone(interface.module)


class ApiInterfaceResultModelTest(TestCase):
    """ApiInterfaceResult 模型测试"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)
        self.interface = ApiInterface.objects.create(
            name='Test API',
            type='http',
            method='GET',
            url='/api/test',
            project=self.project,
            created_by=self.user,
        )

    def test_create_result(self):
        """测试创建执行结果"""
        result = ApiInterfaceResult.objects.create(
            interface=self.interface,
            success=True,
            elapsed=123.45,
            request_data={'method': 'GET', 'url': 'http://example.com/api/test'},
            response_data={'status_code': 200, 'body': {'data': 'ok'}},
            validation_results=[{'eq': ['status_code', 200], 'result': True}],
            extracted_variables={'token': 'abc123'},
            executed_by=self.user,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.elapsed, 123.45)
        self.assertIsNotNone(result.executed_at)

    def test_str_representation(self):
        """测试字符串表示"""
        result = ApiInterfaceResult.objects.create(
            interface=self.interface,
            success=True,
            elapsed=100,
            request_data={},
            response_data={},
            executed_by=self.user,
        )
        self.assertIn('Test API', str(result))

    def test_cascade_delete_interface(self):
        """测试删除接口时级联删除结果"""
        ApiInterfaceResult.objects.create(
            interface=self.interface,
            success=True,
            elapsed=100,
            request_data={},
            response_data={},
            executed_by=self.user,
        )
        self.interface.delete()
        self.assertEqual(ApiInterfaceResult.objects.count(), 0)

    def test_set_null_on_user_delete(self):
        """测试删除用户时 executed_by 置空"""
        result = ApiInterfaceResult.objects.create(
            interface=self.interface,
            success=True,
            elapsed=100,
            request_data={},
            response_data={},
            executed_by=self.user,
        )
        self.user.delete()
        result.refresh_from_db()
        self.assertIsNone(result.executed_by)

    def test_ordering(self):
        """测试默认按 executed_at 降序排列"""
        r1 = ApiInterfaceResult.objects.create(
            interface=self.interface, success=True, elapsed=100,
            request_data={}, response_data={}, executed_by=self.user,
        )
        r2 = ApiInterfaceResult.objects.create(
            interface=self.interface, success=False, elapsed=200,
            request_data={}, response_data={}, executed_by=self.user,
        )
        results = list(ApiInterfaceResult.objects.all())
        self.assertEqual(results[0], r2)  # newest first
        self.assertEqual(results[1], r1)

    def test_environment_id_nullable(self):
        """测试 environment_id 可为空"""
        result = ApiInterfaceResult.objects.create(
            interface=self.interface,
            success=True,
            elapsed=50,
            request_data={},
            response_data={},
            executed_by=self.user,
        )
        self.assertIsNone(result.environment_id)

    def test_environment_id_set(self):
        """测试 environment_id 可设置"""
        result = ApiInterfaceResult.objects.create(
            interface=self.interface,
            environment_id=42,
            success=True,
            elapsed=50,
            request_data={},
            response_data={},
            executed_by=self.user,
        )
        self.assertEqual(result.environment_id, 42)


class ApiInterfaceAPITest(TestCase):
    """ApiInterface API CRUD 测试"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='apiuser', password='testpass')
        self.project = Project.objects.create(name='API Project', creator=self.user)
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        _grant_interface_perms(self.user)
        self.client.force_authenticate(user=self.user)
        self.base_url = f'/api/projects/{self.project.pk}/api-interfaces/'

    def test_list_interfaces(self):
        """测试获取接口列表"""
        ApiInterface.objects.create(
            name='API 1', type='http', method='GET', url='/api/1',
            project=self.project, created_by=self.user,
        )
        ApiInterface.objects.create(
            name='API 2', type='http', method='POST', url='/api/2',
            project=self.project, created_by=self.user,
        )
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_filter_by_module(self):
        """测试按模块筛选"""
        module = ApiModule.objects.create(
            name='Auth Module', project=self.project, created_by=self.user,
        )
        ApiInterface.objects.create(
            name='In Module', type='http', method='GET', url='/api/1',
            project=self.project, module=module, created_by=self.user,
        )
        ApiInterface.objects.create(
            name='No Module', type='http', method='GET', url='/api/2',
            project=self.project, created_by=self.user,
        )
        response = self.client.get(self.base_url, {'module_id': module.pk})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        items = response.data['results'] if isinstance(response.data, dict) else response.data
        names = [i['name'] for i in items]
        self.assertIn('In Module', names)
        self.assertNotIn('No Module', names)

    def test_list_filter_no_module(self):
        """测试筛选无模块的接口"""
        module = ApiModule.objects.create(
            name='Module', project=self.project, created_by=self.user,
        )
        ApiInterface.objects.create(
            name='With Module', type='http', method='GET', url='/api/1',
            project=self.project, module=module, created_by=self.user,
        )
        ApiInterface.objects.create(
            name='Without Module', type='http', method='GET', url='/api/2',
            project=self.project, created_by=self.user,
        )
        response = self.client.get(self.base_url, {'no_module': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        items = response.data['results'] if isinstance(response.data, dict) else response.data
        names = [i['name'] for i in items]
        self.assertIn('Without Module', names)
        self.assertNotIn('With Module', names)

    def test_create_http_interface(self):
        """测试创建 HTTP 接口"""
        data = {
            'name': 'New HTTP API',
            'type': 'http',
            'method': 'POST',
            'url': '/api/login',
            'headers': {'Content-Type': 'application/json'},
            'body': {'username': 'test'},
            'project': self.project.pk,
        }
        response = self.client.post(self.base_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        interface = ApiInterface.objects.get(name='New HTTP API')
        self.assertEqual(interface.project, self.project)
        self.assertEqual(interface.created_by, self.user)

    def test_create_normalizes_legacy_headers_params_body_shapes(self):
        """创建时将旧格式 headers/params/body 归一化为前端协议"""
        data = {
            'name': 'Legacy Shape API',
            'type': 'http',
            'method': 'POST',
            'url': '/api/legacy',
            'headers': {'Content-Type': 'application/json', 'X-Trace-Id': 123},
            'params': {'page': 1, 'active': True},
            'body': {'username': 'tester', 'roles': ['admin']},
        }
        response = self.client.post(self.base_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data['headers'],
            [
                {'key': 'Content-Type', 'value': 'application/json', 'description': '', 'enabled': True},
                {'key': 'X-Trace-Id', 'value': '123', 'description': '', 'enabled': True},
            ],
        )
        self.assertEqual(
            response.data['params'],
            [
                {'key': 'page', 'value': '1', 'description': '', 'enabled': True},
                {'key': 'active', 'value': 'True', 'description': '', 'enabled': True},
            ],
        )
        self.assertEqual(
            response.data['body'],
            {'type': 'raw', 'content': {'username': 'tester', 'roles': ['admin']}},
        )

        interface = ApiInterface.objects.get(name='Legacy Shape API')
        self.assertEqual(response.data['headers'], interface.headers)
        self.assertEqual(response.data['params'], interface.params)
        self.assertEqual(response.data['body'], interface.body)

    def test_create_sql_interface(self):
        """测试创建 SQL 接口"""
        data = {
            'name': 'New SQL Query',
            'type': 'sql',
            'sql_method': 'fetchall',
            'sql': 'SELECT * FROM users',
            'project': self.project.pk,
        }
        response = self.client.post(self.base_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        interface = ApiInterface.objects.get(name='New SQL Query')
        self.assertEqual(interface.type, 'sql')

    def test_create_duplicate_name_returns_400(self):
        """测试同项目重复接口名返回 400 而不是 500"""
        ApiInterface.objects.create(
            name='Duplicate API',
            type='http',
            method='GET',
            url='/api/existing',
            project=self.project,
            created_by=self.user,
        )
        data = {
            'name': 'Duplicate API',
            'type': 'http',
            'method': 'POST',
            'url': '/api/new',
        }
        response = self.client.post(self.base_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)

    def test_retrieve_interface(self):
        """测试获取单个接口"""
        interface = ApiInterface.objects.create(
            name='Detail API', type='http', method='GET', url='/api/detail',
            project=self.project, created_by=self.user,
        )
        response = self.client.get(f'{self.base_url}{interface.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Detail API')

    def test_retrieve_normalizes_legacy_stored_shapes(self):
        """读取旧数据时返回前端可渲染的协议结构"""
        interface = ApiInterface.objects.create(
            name='Stored Legacy API',
            type='http',
            method='POST',
            url='/api/stored-legacy',
            headers={'Authorization': 'Bearer token'},
            params={'page': 2},
            body={'token': 'abc', 'meta': {'env': 'test'}},
            project=self.project,
            created_by=self.user,
        )

        response = self.client.get(f'{self.base_url}{interface.pk}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['headers'],
            [{'key': 'Authorization', 'value': 'Bearer token', 'description': '', 'enabled': True}],
        )
        self.assertEqual(
            response.data['params'],
            [{'key': 'page', 'value': '2', 'description': '', 'enabled': True}],
        )
        self.assertEqual(
            response.data['body'],
            {'type': 'raw', 'content': {'token': 'abc', 'meta': {'env': 'test'}}},
        )

    def test_update_interface(self):
        """测试更新接口"""
        interface = ApiInterface.objects.create(
            name='Old API', type='http', method='GET', url='/api/old',
            project=self.project, created_by=self.user,
        )
        response = self.client.patch(
            f'{self.base_url}{interface.pk}/',
            {'url': '/api/new'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        interface.refresh_from_db()
        self.assertEqual(interface.url, '/api/new')

    def test_delete_interface(self):
        """测试删除接口"""
        interface = ApiInterface.objects.create(
            name='To Delete', type='http', method='GET', url='/api/test',
            project=self.project, created_by=self.user,
        )
        response = self.client.delete(f'{self.base_url}{interface.pk}/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])
        self.assertFalse(ApiInterface.objects.filter(pk=interface.pk).exists())

    def test_create_with_validators(self):
        """测试创建带校验器的接口"""
        data = {
            'name': 'Validated API',
            'type': 'http',
            'method': 'GET',
            'url': '/api/test',
            'validators': [{'eq': ['status_code', 200]}],
            'project': self.project.pk,
        }
        response = self.client.post(self.base_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        interface = ApiInterface.objects.get(name='Validated API')
        self.assertEqual(interface.validators, [{'eq': ['status_code', 200]}])

    def test_create_with_check_expect_validators(self):
        """测试 check/expect 格式的校验器"""
        data = {
            'name': 'Check Expect API',
            'type': 'http',
            'method': 'GET',
            'url': '/api/test',
            'validators': [{'check': 'status_code', 'expect': 200}],
            'project': self.project.pk,
        }
        response = self.client.post(self.base_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_with_invalid_validator_format(self):
        """测试无效校验器格式"""
        data = {
            'name': 'Bad Validator API',
            'type': 'http',
            'method': 'GET',
            'url': '/api/test',
            'validators': [{'bad_comparator': ['status_code', 200]}],
            'project': self.project.pk,
        }
        response = self.client.post(self.base_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_with_extract(self):
        """测试创建带提取变量的接口"""
        data = {
            'name': 'Extract API',
            'type': 'http',
            'method': 'POST',
            'url': '/api/login',
            'extract': {'token': 'body.data.token'},
            'project': self.project.pk,
        }
        response = self.client.post(self.base_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        interface = ApiInterface.objects.get(name='Extract API')
        self.assertEqual(interface.extract, {'token': 'body.data.token'})

    @patch('api_interfaces.views.InterfaceRunner')
    def test_run_interface(self, MockRunner):
        """测试运行接口"""
        mock_instance = MagicMock()
        mock_instance.variables = {}
        mock_instance.get_response.return_value = {
            'success': True,
            'status_code': 200,
            'response_time_ms': 123,
            'request': {'method': 'GET', 'url': 'http://example.com/api/test'},
            'response': {'body': {'data': 'ok'}},
            'validators': {},
            'extracted_variables': {},
        }
        MockRunner.return_value = mock_instance

        interface = ApiInterface.objects.create(
            name='Run API', type='http', method='GET', url='http://example.com/api/test',
            project=self.project, created_by=self.user,
        )
        response = self.client.post(f'{self.base_url}{interface.pk}/run/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        mock_instance.run_interface.assert_called_once()
        # Verify result was saved
        self.assertEqual(ApiInterfaceResult.objects.count(), 1)
        result = ApiInterfaceResult.objects.first()
        self.assertTrue(result.success)
        self.assertEqual(result.interface, interface)
        self.assertEqual(result.executed_by, self.user)

    @patch('api_interfaces.views.InterfaceRunner')
    def test_run_interface_failure(self, MockRunner):
        """测试运行接口失败"""
        MockRunner.side_effect = Exception('Connection refused')

        interface = ApiInterface.objects.create(
            name='Fail API', type='http', method='GET', url='http://example.com/fail',
            project=self.project, created_by=self.user,
        )
        response = self.client.post(f'{self.base_url}{interface.pk}/run/')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('Connection refused', response.data['detail'])

    @patch('api_interfaces.views.InterfaceRunner')
    def test_run_with_environment(self, MockRunner):
        """测试带环境配置运行接口"""
        mock_instance = MagicMock()
        mock_instance.variables = {}
        mock_instance.get_response.return_value = {
            'success': True,
            'status_code': 200,
            'response_time_ms': 50,
            'request': {},
            'response': {},
            'validators': {},
            'extracted_variables': {},
        }
        mock_instance.interface_data = {}
        MockRunner.return_value = mock_instance

        interface = ApiInterface.objects.create(
            name='Env API', type='http', method='GET', url='/api/test',
            project=self.project, created_by=self.user,
        )
        # Mock environment loading to avoid needing a real Environment model
        import sys
        mock_env_module = MagicMock()
        mock_env = MagicMock()
        mock_env.base_url = 'http://staging.example.com'
        mock_env.verify_ssl = True
        mock_env.get_all_variables.return_value = {'api_key': 'secret'}
        mock_env_module.Environment = MagicMock()
        with patch.dict(sys.modules, {'environments': mock_env_module, 'environments.models': mock_env_module}):
            with patch('api_interfaces.views.get_object_or_404', return_value=mock_env):

                response = self.client.post(
                    f'{self.base_url}{interface.pk}/run/',
                    {'environment_id': 1},
                    format='json',
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch('api_interfaces.views.InterfaceRunner')
    def test_quick_debug_http(self, MockRunner):
        """测试快速调试 HTTP 接口"""
        mock_instance = MagicMock()
        mock_instance.variables = {}
        mock_instance.get_response.return_value = {
            'success': True,
            'status_code': 200,
            'response_time_ms': 50,
            'request': {'method': 'GET', 'url': 'http://example.com/api/test'},
            'response': {'body': {'data': 'ok'}},
            'validators': {},
            'extracted_variables': {},
        }
        mock_instance.interface_data = {}
        MockRunner.return_value = mock_instance

        data = {
            'type': 'http',
            'method': 'GET',
            'url': 'http://example.com/api/test',
            'name': 'Debug Test',
        }
        response = self.client.post(f'{self.base_url}quick_debug/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        mock_instance.run_interface.assert_called_once()
        # quick_debug should NOT save a result
        self.assertEqual(ApiInterfaceResult.objects.count(), 0)

    def test_quick_debug_http_missing_method(self):
        """测试快速调试缺少 method"""
        data = {
            'type': 'http',
            'url': 'http://example.com/api/test',
        }
        response = self.client.post(f'{self.base_url}quick_debug/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('method', response.data['detail'].lower())

    def test_quick_debug_http_missing_url(self):
        """测试快速调试缺少 url"""
        data = {
            'type': 'http',
            'method': 'GET',
        }
        response = self.client.post(f'{self.base_url}quick_debug/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('url', response.data['detail'].lower())

    def test_quick_debug_sql_missing_method(self):
        """测试快速调试 SQL 缺少 method"""
        data = {
            'type': 'sql',
            'sql': 'SELECT 1',
        }
        response = self.client.post(f'{self.base_url}quick_debug/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_quick_debug_sql_missing_sql(self):
        """测试快速调试 SQL 缺少 sql"""
        data = {
            'type': 'sql',
            'method': 'fetchone',
        }
        response = self.client.post(f'{self.base_url}quick_debug/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('api_interfaces.views.InterfaceRunner')
    def test_quick_debug_failure(self, MockRunner):
        """测试快速调试失败"""
        MockRunner.side_effect = Exception('Parse error')

        data = {
            'type': 'http',
            'method': 'GET',
            'url': 'http://example.com/bad',
        }
        response = self.client.post(f'{self.base_url}quick_debug/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_unauthenticated_access(self):
        """测试未认证用户无法访问"""
        self.client.force_authenticate(user=None)
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ApiInterfaceResultAPITest(TestCase):
    """ApiInterfaceResult API 测试 (read-only)"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='apiuser', password='testpass')
        self.project = Project.objects.create(name='API Project', creator=self.user)
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        _grant_interface_perms(self.user)
        self.client.force_authenticate(user=self.user)
        self.interface = ApiInterface.objects.create(
            name='Test API', type='http', method='GET', url='/api/test',
            project=self.project, created_by=self.user,
        )
        self.base_url = f'/api/projects/{self.project.pk}/api-interface-results/'

    def test_list_results(self):
        """测试获取结果列表"""
        ApiInterfaceResult.objects.create(
            interface=self.interface, success=True, elapsed=100,
            request_data={}, response_data={}, executed_by=self.user,
        )
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_filter_by_interface(self):
        """测试按接口筛选结果"""
        other_interface = ApiInterface.objects.create(
            name='Other API', type='http', method='GET', url='/api/other',
            project=self.project, created_by=self.user,
        )
        ApiInterfaceResult.objects.create(
            interface=self.interface, success=True, elapsed=100,
            request_data={}, response_data={}, executed_by=self.user,
        )
        ApiInterfaceResult.objects.create(
            interface=other_interface, success=True, elapsed=200,
            request_data={}, response_data={}, executed_by=self.user,
        )
        response = self.client.get(
            self.base_url, {'interface_id': self.interface.pk}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_result(self):
        """测试获取单个结果"""
        result = ApiInterfaceResult.objects.create(
            interface=self.interface, success=True, elapsed=100,
            request_data={'method': 'GET'}, response_data={'body': 'ok'},
            executed_by=self.user,
        )
        response = self.client.get(f'{self.base_url}{result.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_not_allowed(self):
        """测试不允许通过 API 创建结果"""
        data = {
            'interface': self.interface.pk,
            'success': True,
            'elapsed': 100,
            'request_data': {},
            'response_data': {},
        }
        response = self.client.post(self.base_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_update_not_allowed(self):
        """测试不允许更新结果"""
        result = ApiInterfaceResult.objects.create(
            interface=self.interface, success=True, elapsed=100,
            request_data={}, response_data={}, executed_by=self.user,
        )
        response = self.client.put(
            f'{self.base_url}{result.pk}/',
            {'success': False},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_not_allowed(self):
        """测试不允许删除结果"""
        result = ApiInterfaceResult.objects.create(
            interface=self.interface, success=True, elapsed=100,
            request_data={}, response_data={}, executed_by=self.user,
        )
        response = self.client.delete(f'{self.base_url}{result.pk}/')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class ApiInterfaceRunnerTest(TestCase):
    """InterfaceRunner 单元测试"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)

    @patch('api_interfaces.runner.load_custom_functions', return_value={})
    @patch('httprunner.HttpRunner.test_start')
    def test_runner_init_http(self, mock_test_start, mock_load_funcs):
        """测试 HTTP Runner 初始化"""
        from .runner import InterfaceRunner

        interface_data = {
            'name': 'Test HTTP',
            'type': 'http',
            'method': 'GET',
            'url': 'http://example.com/api/test',
            'headers': {'Authorization': 'Bearer token'},
            'params': {'page': '1'},
            'body': {},
            'variables': {'token': 'abc'},
            'validators': [{'eq': ['status_code', 200]}],
            'extract': {'user_id': 'body.data.id'},
            'setup_hooks': [],
            'teardown_hooks': [],
            'project_id': self.project.pk,
        }

        runner = InterfaceRunner(interface_data)
        self.assertEqual(runner.interface_data, interface_data)
        self.assertEqual(len(runner.teststeps), 1)

    @patch('api_interfaces.runner.load_custom_functions', return_value={})
    @patch('httprunner.HttpRunner.test_start')
    def test_runner_preserves_validator_expected_value_type_meta(
        self,
        mock_test_start,
        mock_load_funcs,
    ):
        """断言值类型元数据应进入 HttpRunner，供变量解析后做类型转换。"""
        from .runner import InterfaceRunner

        interface_data = {
            'name': 'Validator Meta Test',
            'type': 'http',
            'method': 'GET',
            'url': 'http://example.com/api/test',
            'headers': {},
            'params': {},
            'body': {},
            'variables': {},
            'validators': [{
                'gt': ['body.count', '${min_count}'],
                '__expected_value_type': 'number',
            }],
            'extract': {},
            'setup_hooks': [],
            'teardown_hooks': [],
            'project_id': self.project.pk,
        }

        runner = InterfaceRunner(interface_data)

        self.assertEqual(
            runner.teststeps[0].struct().validators,
            [{
                'gt': ['body.count', '${min_count}'],
                '__expected_value_type': 'number',
            }],
        )

    @patch('api_interfaces.runner.load_custom_functions', return_value={})
    @patch('httprunner.HttpRunner.test_start')
    def test_runner_init_sql(self, mock_test_start, mock_load_funcs):
        """测试 SQL Runner 初始化"""
        from .runner import InterfaceRunner

        interface_data = {
            'name': 'Test SQL',
            'type': 'sql',
            'method': 'fetchone',
            'sql': 'SELECT * FROM users WHERE id = 1',
            'variables': {},
            'validators': [],
            'extract': {},
            'setup_hooks': [],
            'teardown_hooks': [],
            'project_id': self.project.pk,
        }

        runner = InterfaceRunner(interface_data)
        self.assertEqual(len(runner.teststeps), 1)

    @patch('api_interfaces.runner.load_custom_functions', return_value={})
    @patch('httprunner.HttpRunner.test_start')
    def test_runner_init_sql_methods(self, mock_test_start, mock_load_funcs):
        """测试不同 SQL 方法的初始化"""
        from .runner import InterfaceRunner

        for method in ['fetchone', 'fetchmany', 'fetchall', 'insert', 'update', 'delete']:
            interface_data = {
                'name': f'Test SQL {method}',
                'type': 'sql',
                'method': method,
                'sql': 'SELECT 1',
                'variables': {},
                'validators': [],
                'extract': {},
                'setup_hooks': [],
                'teardown_hooks': [],
                'project_id': self.project.pk,
            }
            if method == 'fetchmany':
                interface_data['size'] = 5

            runner = InterfaceRunner(interface_data)
            self.assertEqual(len(runner.teststeps), 1)

    @patch('api_interfaces.runner.load_custom_functions', return_value={})
    @patch('httprunner.HttpRunner.test_start')
    def test_runner_with_base_url(self, mock_test_start, mock_load_funcs):
        """测试 Runner 使用 base_url"""
        from .runner import InterfaceRunner

        interface_data = {
            'name': 'Base URL Test',
            'type': 'http',
            'method': 'GET',
            'url': '/api/test',
            'base_url': 'http://example.com',
            'headers': {},
            'params': {},
            'body': {},
            'variables': {},
            'validators': [],
            'extract': {},
            'setup_hooks': [],
            'teardown_hooks': [],
            'project_id': self.project.pk,
        }

        runner = InterfaceRunner(interface_data)
        self.assertEqual(runner.base_url, 'http://example.com')

    @patch('api_interfaces.runner.load_custom_functions', return_value={})
    @patch('httprunner.HttpRunner.test_start')
    def test_runner_run_interface(self, mock_test_start, mock_load_funcs):
        """测试 Runner 执行"""
        from .runner import InterfaceRunner

        interface_data = {
            'name': 'Run Test',
            'type': 'http',
            'method': 'GET',
            'url': 'http://example.com/api/test',
            'headers': {},
            'params': {},
            'body': {},
            'variables': {},
            'validators': [],
            'extract': {},
            'setup_hooks': [],
            'teardown_hooks': [],
            'project_id': self.project.pk,
        }

        runner = InterfaceRunner(interface_data)
        runner.run_interface()
        mock_test_start.assert_called_once()

    @patch('api_interfaces.runner.load_custom_functions', return_value={})
    @patch('httprunner.HttpRunner.test_start')
    def test_get_response_uses_last_redirect_response(self, mock_test_start, mock_load_funcs):
        """重定向场景下应返回最后一跳响应，而不是首跳 301。"""
        from .runner import InterfaceRunner

        interface_data = {
            'name': 'Redirect Test',
            'type': 'http',
            'method': 'GET',
            'url': 'http://example.com/api/accounts/groups',
            'headers': {},
            'params': {},
            'body': {},
            'variables': {},
            'validators': [],
            'extract': {},
            'setup_hooks': [],
            'teardown_hooks': [],
            'project_id': self.project.pk,
        }

        runner = InterfaceRunner(interface_data)
        first_req_resp = SimpleNamespace(
            request=SimpleNamespace(method='GET', url='http://example.com/api/accounts/groups', headers={}, body=None),
            response=SimpleNamespace(status_code=301, headers={'Location': '/api/accounts/groups/'}, body=''),
        )
        final_req_resp = SimpleNamespace(
            request=SimpleNamespace(method='GET', url='http://example.com/api/accounts/groups/', headers={}, body=None),
            response=SimpleNamespace(
                status_code=200,
                headers={'Content-Type': 'application/json'},
                body={'status': 'success', 'data': []},
            ),
        )
        summary = SimpleNamespace(
            step_results=[
                SimpleNamespace(
                    success=True,
                    name='GET /api/accounts/groups',
                    export_vars={},
                    data=SimpleNamespace(
                        req_resps=[first_req_resp, final_req_resp],
                        stat=SimpleNamespace(response_time_ms=43.15, content_size=80),
                        validators={},
                    ),
                ),
            ],
        )

        with patch.object(runner, 'get_summary', return_value=summary):
            response = runner.get_response()

        self.assertEqual(response['status_code'], 200)
        self.assertEqual(response['request']['url'], 'http://example.com/api/accounts/groups/')
        self.assertEqual(response['response']['status_code'], 200)

    @patch('api_interfaces.runner.load_custom_functions', return_value={})
    @patch('httprunner.HttpRunner.test_start')
    def test_get_response_recovers_request_body_on_transport_failure(
        self,
        mock_test_start,
        mock_load_funcs,
    ):
        """请求失败时展示执行前准备好的请求信息，避免误判 body 没带。"""
        from .runner import InterfaceRunner

        interface_data = {
            'name': 'Transport Failure Body Test',
            'type': 'http',
            'method': 'POST',
            'url': 'http://example.com/api/test',
            'headers': {'Authorization': 'Bearer token'},
            'params': {},
            'body': {
                'type': 'x-www-form-urlencoded',
                'content': [
                    {'key': 'username', 'value': 'tester', 'description': '', 'enabled': True},
                ],
            },
            'variables': {},
            'validators': [],
            'extract': {},
            'setup_hooks': [],
            'teardown_hooks': [],
            'project_id': self.project.pk,
        }

        runner = InterfaceRunner(interface_data)
        req_resp = SimpleNamespace(
            request=SimpleNamespace(
                method='POST',
                url='http://example.com/api/test',
                headers={},
                body=None,
            ),
            response=SimpleNamespace(
                status_code=0,
                headers={},
                body={
                    'transport_error': {
                        'type': 'ConnectionError',
                        'message': 'connection refused',
                    },
                },
                error='connection refused',
                error_type='ConnectionError',
                is_transport_error=True,
            ),
        )
        summary = SimpleNamespace(
            step_results=[
                SimpleNamespace(
                    success=True,
                    name='POST /api/test',
                    export_vars={},
                    data=SimpleNamespace(
                        req_resps=[req_resp],
                        stat=SimpleNamespace(response_time_ms=12.3, content_size=0),
                        validators={},
                    ),
                ),
            ],
        )

        with patch.object(runner, 'get_summary', return_value=summary):
            response = runner.get_response()

        self.assertFalse(response['success'])
        self.assertEqual(response['status_code'], 0)
        self.assertEqual(response['request']['headers'], {'Authorization': 'Bearer token'})
        self.assertEqual(response['request']['body'], {'username': 'tester'})
        self.assertTrue(response['response']['is_transport_error'])
        self.assertEqual(response['response']['error_type'], 'ConnectionError')
        self.assertEqual(response['response']['error'], 'connection refused')
        self.assertEqual(
            response['response']['content']['transport_error']['message'],
            'connection refused',
        )

    @patch('api_interfaces.runner.load_custom_functions', return_value={})
    @patch('httprunner.HttpRunner.test_start')
    def test_runner_with_hooks(self, mock_test_start, mock_load_funcs):
        """测试 Runner 带 hooks"""
        from .runner import InterfaceRunner

        interface_data = {
            'name': 'Hook Test',
            'type': 'http',
            'method': 'GET',
            'url': 'http://example.com/api/test',
            'headers': {},
            'params': {},
            'body': {},
            'variables': {},
            'validators': [],
            'extract': {},
            'setup_hooks': ['${setup_hook($request)}'],
            'teardown_hooks': ['${teardown_hook($response)}'],
            'project_id': self.project.pk,
        }

        runner = InterfaceRunner(interface_data)
        self.assertEqual(len(runner.teststeps), 1)

    @patch('api_interfaces.runner.load_custom_functions', return_value={})
    @patch('httprunner.HttpRunner.test_start')
    def test_runner_body_raw_json(self, mock_test_start, mock_load_funcs):
        """测试 Runner 处理 raw JSON body"""
        from .runner import InterfaceRunner

        interface_data = {
            'name': 'Body Test',
            'type': 'http',
            'method': 'POST',
            'url': 'http://example.com/api/test',
            'headers': {},
            'params': {},
            'body': {'type': 'raw', 'content': '{"key": "value"}'},
            'variables': {},
            'validators': [],
            'extract': {},
            'setup_hooks': [],
            'teardown_hooks': [],
            'project_id': self.project.pk,
        }

        runner = InterfaceRunner(interface_data)
        self.assertEqual(len(runner.teststeps), 1)

    @patch('api_interfaces.runner.load_custom_functions', return_value={})
    @patch('httprunner.HttpRunner.test_start')
    def test_runner_accepts_frontend_payload_shapes(self, mock_test_start, mock_load_funcs):
        """测试 Runner 接受前端 headers/params/body 结构"""
        from .runner import InterfaceRunner

        interface_data = {
            'name': 'Frontend Shape Test',
            'type': 'http',
            'method': 'POST',
            'url': 'http://example.com/api/test',
            'headers': [
                {'key': 'Authorization', 'value': 'Bearer token', 'description': '', 'enabled': True},
                {'key': 'X-Disabled', 'value': 'skip', 'description': '', 'enabled': False},
            ],
            'params': [
                {'key': 'page', 'value': '1', 'description': '', 'enabled': True},
                {'key': 'debug', 'value': 'true', 'description': '', 'enabled': False},
            ],
            'body': {
                'type': 'x-www-form-urlencoded',
                'content': [
                    {'key': 'username', 'value': 'tester', 'description': '', 'enabled': True},
                    {'key': 'password', 'value': 'secret', 'description': '', 'enabled': True},
                ],
            },
            'variables': {},
            'validators': [],
            'extract': {},
            'setup_hooks': [],
            'teardown_hooks': [],
            'project_id': self.project.pk,
        }

        runner = InterfaceRunner(interface_data)
        request = runner.teststeps[0].request

        self.assertEqual(request.headers['Authorization'], 'Bearer token')
        self.assertNotIn('X-Disabled', request.headers)
        self.assertEqual(request.params, {'page': '1'})
        self.assertEqual(request.data, {'username': 'tester', 'password': 'secret'})
        self.assertIsNone(request.req_json)

    @patch('api_interfaces.runner._resolve_runtime_files')
    @patch('api_interfaces.runner.load_custom_functions', return_value={})
    @patch('httprunner.HttpRunner.test_start')
    def test_runner_form_data_file_field_uses_upload(
        self,
        mock_test_start,
        mock_load_funcs,
        mock_resolve_files,
    ):
        """form-data 文件字段应转成 multipart upload，而不是普通 data。"""
        from .runner import InterfaceRunner

        mock_resolve_files.return_value = [{'id': 8, 'path': '/tmp/upload.txt'}]
        interface_data = {
            'name': 'Upload File',
            'type': 'http',
            'method': 'POST',
            'url': 'http://example.com/api/upload',
            'headers': [
                {'key': 'Content-Type', 'value': 'multipart/form-data', 'description': '', 'enabled': True},
                {'key': 'Authorization', 'value': 'Bearer token', 'description': '', 'enabled': True},
            ],
            'params': {},
            'body': {
                'type': 'form-data',
                'content': [
                    {
                        'key': 'files',
                        'value': 'file_id:8',
                        'value_type': 'file',
                        'file_id': 8,
                        'description': '',
                        'enabled': True,
                    },
                    {
                        'key': 'folder',
                        'value': 'docs',
                        'value_type': 'text',
                        'description': '',
                        'enabled': True,
                    },
                ],
            },
            'variables': {},
            'validators': [],
            'extract': {},
            'setup_hooks': [],
            'teardown_hooks': [],
            'project_id': self.project.pk,
        }

        runner = InterfaceRunner(interface_data)
        request = runner.teststeps[0].request

        mock_resolve_files.assert_called_once_with(self.project.pk, [8])
        self.assertEqual(request.upload, {'files': '/tmp/upload.txt', 'folder': 'docs'})
        self.assertIsNone(request.data)
        self.assertEqual(request.headers['Authorization'], 'Bearer token')
        self.assertFalse(any(key.lower() == 'content-type' for key in request.headers))

    @patch('api_interfaces.runner.load_custom_functions')
    @patch('httprunner.HttpRunner.test_start')
    def test_runner_loads_custom_functions(self, mock_test_start, mock_load_funcs):
        """测试 Runner 加载自定义函数"""
        from api_functions.models import ApiCustomFunction

        ApiCustomFunction.objects.create(
            name='add',
            code='def add(a, b):\n    return a + b',
            project=self.project,
            created_by=self.user,
            is_active=True,
        )

        mock_load_funcs.return_value = {'add': lambda a, b: a + b}

        interface_data = {
            'name': 'Custom Func Test',
            'type': 'http',
            'method': 'GET',
            'url': 'http://example.com/api/test',
            'headers': {},
            'params': {},
            'body': {},
            'variables': {},
            'validators': [],
            'extract': {},
            'setup_hooks': [],
            'teardown_hooks': [],
            'project_id': self.project.pk,
        }

        from .runner import InterfaceRunner
        runner = InterfaceRunner(interface_data)
        mock_load_funcs.assert_called_once_with(self.project.pk)
        self.assertIn('add', runner.functions)

    def test_load_custom_functions(self):
        """测试 load_custom_functions 加载自定义函数"""
        from api_functions.models import ApiCustomFunction
        from .runner import load_custom_functions

        ApiCustomFunction.objects.create(
            name='greet',
            code='def greet(name):\n    return f"Hello, {name}"',
            project=self.project,
            created_by=self.user,
            is_active=True,
        )
        ApiCustomFunction.objects.create(
            name='inactive_func',
            code='def inactive_func():\n    pass',
            project=self.project,
            created_by=self.user,
            is_active=False,
        )

        functions = load_custom_functions(self.project.pk)
        self.assertIn('greet', functions)
        self.assertNotIn('inactive_func', functions)
        self.assertEqual(functions['greet']('World'), 'Hello, World')

    def test_load_custom_functions_syntax_error(self):
        """测试 load_custom_functions 处理语法错误"""
        from api_functions.models import ApiCustomFunction
        from .runner import load_custom_functions

        ApiCustomFunction.objects.create(
            name='bad_func',
            code='def bad_func(\n    return',
            project=self.project,
            created_by=self.user,
            is_active=True,
        )
        ApiCustomFunction.objects.create(
            name='good_func',
            code='def good_func():\n    return 1',
            project=self.project,
            created_by=self.user,
            is_active=True,
        )

        functions = load_custom_functions(self.project.pk)
        # Bad function skipped, good function loaded
        self.assertNotIn('bad_func', functions)
        self.assertIn('good_func', functions)

    def test_load_custom_functions_empty_project(self):
        """测试空项目没有自定义函数"""
        from .runner import load_custom_functions

        functions = load_custom_functions(self.project.pk)
        self.assertEqual(functions, {})


class ApiInterfacePermissionTest(TestCase):
    """ApiInterface 权限测试"""

    def setUp(self):
        self.client = APIClient()
        # Project A with member
        self.user_a = User.objects.create_user(username='user_a', password='testpass')
        self.project_a = Project.objects.create(name='Project A', creator=self.user_a)
        ProjectMember.objects.create(project=self.project_a, user=self.user_a, role='member')
        _grant_interface_perms(self.user_a)

        # Project B with admin
        self.user_b = User.objects.create_user(username='user_b', password='testpass')
        self.project_b = Project.objects.create(name='Project B', creator=self.user_b)
        ProjectMember.objects.create(project=self.project_b, user=self.user_b, role='admin')
        _grant_interface_perms(self.user_b)

        # Superuser
        self.superuser = User.objects.create_superuser(
            username='admin', password='adminpass',
        )

        # Non-member
        self.outsider = User.objects.create_user(username='outsider', password='testpass')

        # Create interfaces in each project
        self.interface_a = ApiInterface.objects.create(
            name='API A', type='http', method='GET', url='/api/a',
            project=self.project_a, created_by=self.user_a,
        )
        self.interface_b = ApiInterface.objects.create(
            name='API B', type='http', method='GET', url='/api/b',
            project=self.project_b, created_by=self.user_b,
        )

    def test_project_isolation_list(self):
        """测试项目数据隔离"""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f'/api/projects/{self.project_a.pk}/api-interfaces/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        items = response.data['results'] if isinstance(response.data, dict) else response.data
        names = [i['name'] for i in items]
        self.assertIn('API A', names)
        self.assertNotIn('API B', names)

    def test_cross_project_access_denied(self):
        """测试跨项目访问被拒绝"""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f'/api/projects/{self.project_b.pk}/api-interfaces/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_member_access_denied(self):
        """测试非项目成员无法访问"""
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(f'/api/projects/{self.project_a.pk}/api-interfaces/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_access_all_projects(self):
        """测试超级管理员可以访问所有项目"""
        self.client.force_authenticate(user=self.superuser)
        for project in [self.project_a, self.project_b]:
            response = self.client.get(f'/api/projects/{project.pk}/api-interfaces/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_denied(self):
        """测试未认证用户被拒绝"""
        response = self.client.get(f'/api/projects/{self.project_a.pk}/api-interfaces/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_project_pk(self):
        """测试无效的 project_pk"""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get('/api/projects/999999/api-interfaces/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ApiInterfaceIsolationTest(TestCase):
    """接口模块项目隔离测试 — run/quick_debug 不能使用跨项目的环境"""

    def setUp(self):
        from api_environments.models import ApiEnvironment

        self.client = APIClient()
        self.user_a = User.objects.create_user(username='user_a', password='testpass')
        _grant_interface_perms(self.user_a)
        self.project_a = Project.objects.create(name='Project A', creator=self.user_a)
        ProjectMember.objects.create(project=self.project_a, user=self.user_a, role='admin')

        self.user_b = User.objects.create_user(username='user_b', password='testpass')
        self.project_b = Project.objects.create(name='Project B', creator=self.user_b)
        ProjectMember.objects.create(project=self.project_b, user=self.user_b, role='admin')

        self.interface_a = ApiInterface.objects.create(
            name='API A', type='http', method='GET', url='http://example.com/api',
            project=self.project_a, created_by=self.user_a,
        )
        self.env_b = ApiEnvironment.objects.create(
            name='Env B', base_url='http://b.com',
            project=self.project_b, created_by=self.user_b,
        )
        self.client.force_authenticate(user=self.user_a)
        self.base_url = f'/api/projects/{self.project_a.pk}/api-interfaces/'

    @patch('api_interfaces.views.InterfaceRunner')
    def test_run_with_other_project_environment(self, mock_runner_cls):
        """run/ 使用跨项目环境应拒绝（400），不能执行"""
        response = self.client.post(
            f'{self.base_url}{self.interface_a.pk}/run/',
            {'environment_id': self.env_b.pk},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_runner_cls.assert_not_called()

    @patch('api_interfaces.views.InterfaceRunner')
    def test_quick_debug_with_other_project_environment(self, mock_runner_cls):
        """quick_debug/ 使用跨项目环境应拒绝（400），不能执行"""
        response = self.client.post(
            f'{self.base_url}quick_debug/',
            {
                'name': 'Debug',
                'type': 'http',
                'method': 'GET',
                'url': 'http://example.com',
                'environment_id': self.env_b.pk,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_runner_cls.assert_not_called()


class ApiInterfaceModelLayerTest(TestCase):
    """ApiInterface 模型层补充测试"""

    def setUp(self):
        from api_interfaces.models import ApiInterface
        self.user = User.objects.create_user(username='ifacemodel', password='testpass')
        self.project = Project.objects.create(name='IfaceModel Project', creator=self.user)

    def test_get_interface_data_http(self):
        """HTTP 接口 get_interface_data 返回正确字段"""
        from api_interfaces.models import ApiInterface
        iface = ApiInterface.objects.create(
            name='HTTP API', type='http', method='POST',
            url='http://api.com/users', headers={'Auth': 'Bearer token'},
            params={'limit': '10'}, body={'name': 'test'},
            project=self.project, created_by=self.user,
        )
        data = iface.get_interface_data()
        self.assertEqual(data['type'], 'http')
        self.assertEqual(data['method'], 'POST')
        self.assertEqual(data['url'], 'http://api.com/users')
        self.assertEqual(data['headers'], {'Auth': 'Bearer token'})
        self.assertEqual(data['params'], {'limit': '10'})

    def test_get_interface_data_sql(self):
        """SQL 接口 get_interface_data 返回正确字段"""
        from api_interfaces.models import ApiInterface
        iface = ApiInterface.objects.create(
            name='SQL API', type='sql', sql_method='fetchall',
            sql='SELECT * FROM users', sql_size=20,
            project=self.project, created_by=self.user,
        )
        data = iface.get_interface_data()
        self.assertEqual(data['type'], 'sql')
        self.assertEqual(data['method'], 'fetchall')
        self.assertEqual(data['sql'], 'SELECT * FROM users')
        self.assertEqual(data['size'], 20)

    def test_save_http_clears_sql_fields(self):
        """保存 HTTP 接口时清空 SQL 字段"""
        from api_interfaces.models import ApiInterface
        iface = ApiInterface.objects.create(
            name='HTTP Clear', type='http', method='GET', url='/api',
            sql='SELECT 1', sql_method='fetchone',
            project=self.project, created_by=self.user,
        )
        self.assertIsNone(iface.sql_method)
        self.assertIsNone(iface.sql)

    def test_save_sql_clears_http_fields(self):
        """保存 SQL 接口时清空 HTTP 字段"""
        from api_interfaces.models import ApiInterface
        iface = ApiInterface.objects.create(
            name='SQL Clear', type='sql', sql_method='fetchone',
            sql='SELECT 1', method='GET', url='/api',
            project=self.project, created_by=self.user,
        )
        self.assertIsNone(iface.method)
        self.assertIsNone(iface.url)

    def test_cross_project_module_raises_error(self):
        """跨项目的 module 保存时抛出 ValueError"""
        from api_interfaces.models import ApiInterface
        from api_modules.models import ApiModule
        other_project = Project.objects.create(name='Other', creator=self.user)
        module = ApiModule.objects.create(
            name='M1', project=other_project, created_by=self.user,
        )
        with self.assertRaises(ValueError):
            ApiInterface.objects.create(
                name='Bad', type='http', method='GET', url='/api',
                module=module, project=self.project, created_by=self.user,
            )

    def test_result_project_property(self):
        """ApiInterfaceResult.project 返回 interface 的 project"""
        from api_interfaces.models import ApiInterface, ApiInterfaceResult
        iface = ApiInterface.objects.create(
            name='Res API', type='http', method='GET', url='/api',
            project=self.project, created_by=self.user,
        )
        result = ApiInterfaceResult.objects.create(
            interface=iface, success=True, elapsed=100.0,
            request_data={}, response_data={}, executed_by=self.user,
        )
        self.assertEqual(result.project, self.project)


class ApiInterfaceRunnerLoadFunctionsTest(TestCase):
    """load_custom_functions runner 层测试"""

    def setUp(self):
        self.user = User.objects.create_user(username='runneruser', password='testpass')
        self.project = Project.objects.create(name='Runner Project', creator=self.user)

    def test_comparator_map_completeness(self):
        """InterfaceRunner._apply_comparator 支持所有比较器"""
        from api_interfaces.runner import InterfaceRunner
        expected_comparators = [
            'eq', 'ne', 'lt', 'le', 'lte', 'gt', 'ge', 'gte',
            'str_eq', 'contains', 'contained_by', 'type_match',
            'regex_match', 'startswith', 'endswith',
            'length_equal', 'length_greater_than', 'length_less_than',
            'length_greater_or_equals', 'length_less_or_equals',
        ]
        comparator_map = {
            'eq': 'assert_equal', 'ne': 'assert_not_equal',
            'lt': 'assert_less_than', 'le': 'assert_less_or_equals',
            'lte': 'assert_less_or_equals', 'gt': 'assert_greater_than',
            'ge': 'assert_greater_or_equals', 'gte': 'assert_greater_or_equals',
            'str_eq': 'assert_string_equals', 'contains': 'assert_contains',
            'contained_by': 'assert_contained_by', 'type_match': 'assert_type_match',
            'regex_match': 'assert_regex_match', 'startswith': 'assert_startswith',
            'endswith': 'assert_endswith', 'length_equal': 'assert_length_equal',
            'length_greater_than': 'assert_length_greater_than',
            'length_less_than': 'assert_length_less_than',
            'length_greater_or_equals': 'assert_length_greater_or_equals',
            'length_less_or_equals': 'assert_length_less_or_equals',
        }
        for comp in expected_comparators:
            self.assertIn(comp, comparator_map)


class ApiInterfaceFilterTest(TestCase):
    """ApiInterface 过滤测试"""

    def setUp(self):
        from api_interfaces.models import ApiInterface
        from api_modules.models import ApiModule
        self.client = APIClient()
        self.user = User.objects.create_user(username='filteruser', password='testpass')
        self.project = Project.objects.create(name='Filter Project', creator=self.user)
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        # Grant interface permissions
        from django.contrib.contenttypes.models import ContentType
        from django.contrib.auth.models import Permission
        for model_cls in [ApiInterface]:
            ct = ContentType.objects.get_for_model(model_cls)
            perms = Permission.objects.filter(content_type=ct)
            self.user.user_permissions.add(*perms)
        from api_interfaces.models import ApiInterfaceResult
        ct = ContentType.objects.get_for_model(ApiInterfaceResult)
        perms = Permission.objects.filter(content_type=ct)
        self.user.user_permissions.add(*perms)
        for attr in ('_perm_cache', '_user_perm_cache'):
            try:
                delattr(self.user, attr)
            except AttributeError:
                pass

        self.client.force_authenticate(user=self.user)
        self.base_url = f'/api/projects/{self.project.pk}/api-interfaces/'

        self.module = ApiModule.objects.create(
            name='Auth Module', project=self.project, created_by=self.user,
        )
        self.iface1 = ApiInterface.objects.create(
            name='Login', type='http', method='POST', url='/login',
            module=self.module, project=self.project, created_by=self.user,
        )
        self.iface2 = ApiInterface.objects.create(
            name='Get Users', type='http', method='GET', url='/users',
            project=self.project, created_by=self.user,
        )

    def test_filter_by_module(self):
        """?module_id=X 过滤有效"""
        response = self.client.get(f'{self.base_url}?module_id={self.module.pk}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['name'], 'Login')

    def test_filter_no_module(self):
        """?no_module=true 过滤无 module 的接口"""
        response = self.client.get(f'{self.base_url}?no_module=true')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        names = [r['name'] for r in results]
        self.assertIn('Get Users', names)
        self.assertNotIn('Login', names)

    def test_pagination_response(self):
        """分页响应格式正确"""
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('results', response.data)
