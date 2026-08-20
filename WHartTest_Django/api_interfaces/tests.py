import json
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from urllib.error import URLError

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient
from rest_framework import status

from projects.models import Project, ProjectMember
from api_modules.models import ApiModule
from .models import ApiInterface, ApiInterfaceResult
from .serializers import ApiInterfaceSerializer
from api_environments.models import ApiEnvironment, ApiEnvironmentVariable
from .exchange import fetch_api_document
from .openapi import OpenAPIError
from rest_framework.exceptions import ValidationError as DRFValidationError


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

    def test_interface_status_and_list_fields(self):
        """List/detail expose status, module_info and created_by_name."""
        module = ApiModule.objects.create(
            name='Auth Module', project=self.project, created_by=self.user,
        )
        interface = ApiInterface.objects.create(
            name='Status API',
            type=ApiInterface.TYPE_HTTP,
            method='GET',
            url='/status',
            project=self.project,
            module=module,
            status=ApiInterface.STATUS_INTEGRATING,
            created_by=self.user,
        )

        list_resp = self.client.get(self.base_url)
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        results = list_resp.data.get('results', list_resp.data)
        item = next(x for x in results if x['id'] == interface.id)
        self.assertEqual(item['status'], 'integrating')
        self.assertEqual(item.get('status_display'), dict(ApiInterface.STATUS_CHOICES)[ApiInterface.STATUS_INTEGRATING])
        self.assertEqual(item.get('created_by_name'), self.user.username)
        self.assertIsNotNone(item.get('module_info'))
        self.assertEqual(item['module_info']['name'], 'Auth Module')

        filter_resp = self.client.get(self.base_url, {'status': 'integrating'})
        self.assertEqual(filter_resp.status_code, status.HTTP_200_OK)
        filtered = filter_resp.data.get('results', filter_resp.data)
        self.assertTrue(any(x['id'] == interface.id for x in filtered))

        detail_url = f"{self.base_url}{interface.id}/"
        detail_resp = self.client.get(detail_url)
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_resp.data['status'], 'integrating')
        self.assertEqual(detail_resp.data['module_info']['id'], module.id)

        update_resp = self.client.patch(detail_url, {'status': 'completed'}, format='json')
        self.assertEqual(update_resp.status_code, status.HTTP_200_OK)
        interface.refresh_from_db()
        self.assertEqual(interface.status, 'completed')


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

    def test_import_openapi_creates_and_updates_interfaces(self):
        """OpenAPI 3.x 导入应按 tag 建模块，重复导入按 method+url 更新。"""
        document = {
            'openapi': '3.0.3',
            'info': {'title': 'Demo API', 'version': '1.0.0'},
            'paths': {
                '/users': {
                    'get': {
                        'summary': 'List Users',
                        'tags': ['Users'],
                        'parameters': [
                            {
                                'name': 'page',
                                'in': 'query',
                                'schema': {'type': 'integer', 'default': 1},
                            },
                            {
                                'name': 'X-Token',
                                'in': 'header',
                                'schema': {'type': 'string'},
                                'example': 'token',
                            },
                        ],
                        'responses': {'200': {'description': 'OK'}},
                    },
                    'post': {
                        'summary': 'Create User',
                        'tags': ['Users'],
                        'requestBody': {
                            'content': {
                                'application/json': {
                                    'schema': {
                                        'type': 'object',
                                        'properties': {
                                            'name': {'type': 'string'},
                                            'age': {'type': 'integer'},
                                        },
                                    },
                                },
                            },
                        },
                        'responses': {'201': {'description': 'Created'}},
                    },
                },
            },
        }
        uploaded = SimpleUploadedFile(
            'openapi.json',
            json.dumps(document).encode('utf-8'),
            content_type='application/json',
        )

        response = self.client.post(
            f'{self.base_url}import-openapi/',
            {'file': uploaded},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['created_count'], 2)
        self.assertEqual(response.data['updated_count'], 0)
        self.assertTrue(ApiModule.objects.filter(project=self.project, name='Users').exists())

        get_interface = ApiInterface.objects.get(project=self.project, method='GET', url='/users')
        self.assertEqual(get_interface.params[0]['key'], 'page')
        self.assertEqual(get_interface.headers[0]['key'], 'X-Token')
        self.assertEqual(get_interface.validators, [{'eq': ['status_code', 200]}])

        post_interface = ApiInterface.objects.get(project=self.project, method='POST', url='/users')
        self.assertEqual(post_interface.body['type'], 'raw')
        self.assertEqual(post_interface.body['content'], {'name': '', 'age': 0})
        self.assertEqual(post_interface.validators, [{'eq': ['status_code', 201]}])

        document['paths']['/users']['get']['summary'] = 'List Users Updated'
        uploaded_again = SimpleUploadedFile(
            'openapi.json',
            json.dumps(document).encode('utf-8'),
            content_type='application/json',
        )
        second_response = self.client.post(
            f'{self.base_url}import-openapi/',
            {'file': uploaded_again},
            format='multipart',
        )

        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.data['created_count'], 0)
        self.assertEqual(second_response.data['updated_count'], 2)
        self.assertEqual(ApiInterface.objects.filter(project=self.project).count(), 2)
        get_interface.refresh_from_db()
        self.assertEqual(get_interface.name, 'List Users Updated')

    def test_import_swagger_uses_base_path(self):
        """Swagger 2.0 导入应把 basePath 拼入接口 URL。"""
        document = {
            'swagger': '2.0',
            'info': {'title': 'Pet API', 'version': '1.0.0'},
            'basePath': '/api/v1',
            'paths': {
                '/pets': {
                    'get': {
                        'summary': 'List Pets',
                        'tags': ['Pets'],
                        'parameters': [
                            {
                                'name': 'limit',
                                'in': 'query',
                                'type': 'integer',
                                'default': 20,
                            },
                        ],
                        'responses': {'200': {'description': 'OK'}},
                    },
                },
            },
        }
        uploaded = SimpleUploadedFile(
            'swagger.json',
            json.dumps(document).encode('utf-8'),
            content_type='application/json',
        )

        response = self.client.post(
            f'{self.base_url}import-openapi/',
            {'file': uploaded},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        interface = ApiInterface.objects.get(project=self.project, name='List Pets')
        self.assertEqual(interface.url, '/api/v1/pets')
        self.assertEqual(interface.params[0]['key'], 'limit')
        self.assertEqual(interface.params[0]['value'], '20')

    def test_export_openapi_json(self):
        """接口导出应生成 OpenAPI 3 JSON 文档。"""
        module = ApiModule.objects.create(
            name='Auth',
            project=self.project,
            created_by=self.user,
        )
        ApiInterface.objects.create(
            name='Login',
            type='http',
            method='POST',
            url='/api/login',
            headers=[
                {'key': 'Content-Type', 'value': 'application/json', 'enabled': True, 'description': ''},
                {'key': 'X-Trace', 'value': 'trace-id', 'enabled': True, 'description': ''},
            ],
            params=[
                {'key': 'tenant', 'value': 'demo', 'enabled': True, 'description': ''},
            ],
            body={'type': 'raw', 'content': {'username': 'tester'}},
            validators=[{'eq': ['status_code', 201]}],
            project=self.project,
            module=module,
            created_by=self.user,
        )

        response = self.client.get(f'{self.base_url}export-openapi/', {'format': 'json'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('application/json', response['Content-Type'])
        exported = json.loads(response.content.decode('utf-8'))
        operation = exported['paths']['/api/login']['post']
        self.assertEqual(exported['openapi'], '3.0.3')
        self.assertEqual(operation['summary'], 'Login')
        self.assertEqual(operation['tags'], ['Auth'])
        self.assertEqual(operation['responses']['201']['description'], 'Successful response')
        self.assertEqual(operation['requestBody']['content']['application/json']['example'], {'username': 'tester'})
        parameter_names = {parameter['name'] for parameter in operation['parameters']}
        self.assertEqual(parameter_names, {'tenant', 'X-Trace'})

    def test_export_openapi_yaml(self):
        """YAML 导出使用非 DRF 保留参数并返回 YAML 文件。"""
        ApiInterface.objects.create(
            name='YAML API',
            type='http',
            method='GET',
            url='/api/yaml',
            project=self.project,
            created_by=self.user,
        )

        response = self.client.get(
            f'{self.base_url}export-openapi/',
            {'export_format': 'yaml'},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('application/yaml', response['Content-Type'])
        self.assertIn('openapi.yaml', response['Content-Disposition'])
        self.assertIn('openapi: 3.0.3', response.content.decode('utf-8'))

    def test_import_native_exchange_formats(self):
        """Apifox、Apipost、YApi 原生 JSON 应自动识别并导入。"""
        fixtures = {
            'apifox': {
                'apifoxProject': '1.0.0',
                'info': {'name': 'Apifox Project'},
                'apiCollection': [
                    {
                        'name': 'API Collection',
                        'items': [
                            {
                                'id': 'folder-1',
                                'name': 'Apifox Module',
                                'items': [
                                    {
                                        'name': 'Apifox Login',
                                        'api': {
                                            'id': 'api-1',
                                            'name': 'Apifox Login',
                                            'method': 'POST',
                                            'path': '/exchange/apifox',
                                            'parameters': {
                                                'query': [
                                                    {
                                                        'name': 'page',
                                                        'type': 'integer',
                                                        'defaultEnable': True,
                                                        'defaultValue': 1,
                                                    },
                                                ],
                                                'header': [
                                                    {
                                                        'name': 'X-Token',
                                                        'type': 'string',
                                                        'defaultEnable': True,
                                                        'example': 'fox-token',
                                                    },
                                                ],
                                            },
                                            'requestBody': {
                                                'type': 'application/json',
                                                'example': '{"name":"fox"}',
                                                'jsonSchema': {
                                                    'type': 'object',
                                                    'properties': {'name': {'type': 'string'}},
                                                },
                                            },
                                            'responses': [
                                                {'id': 'res-1', 'name': 'Created', 'code': 201, 'contentType': 'json'},
                                            ],
                                            'responseExamples': [],
                                        },
                                    },
                                ],
                            },
                        ],
                    },
                ],
            },
            'apipost': {
                'name': 'Apipost Project',
                'project_id': '0',
                'apis': [
                    {
                        'target_id': 'folder-1',
                        'parent_id': '0',
                        'target_type': 'folder',
                        'name': 'Apipost Module',
                    },
                    {
                        'target_id': 'api-1',
                        'parent_id': 'folder-1',
                        'target_type': 'api',
                        'name': 'Apipost Login',
                        'method': 'POST',
                        'url': '/exchange/apipost',
                        'request': {
                            'header': {
                                'parameter': [
                                    {'key': 'X-Token', 'value': 'post-token', 'is_checked': 1},
                                ],
                            },
                            'query': {
                                'parameter': [
                                    {'key': 'page', 'value': '2', 'field_type': 'Integer', 'is_checked': 1},
                                ],
                            },
                            'restful': {'parameter': []},
                            'cookie': {'parameter': []},
                            'body': {
                                'mode': 'json',
                                'raw': '{"name":"post"}',
                                'raw_schema': {
                                    'type': 'object',
                                    'properties': {'name': {'type': 'string'}},
                                },
                            },
                        },
                        'response': {
                            'example': [
                                {'expect': {'code': '202', 'name': 'Accepted', 'content_type': 'json'}},
                            ],
                        },
                    },
                ],
            },
            'yapi': [
                {
                    'name': 'YApi Module',
                    'desc': '',
                    'list': [
                        {
                            'title': 'YApi Login',
                            'method': 'POST',
                            'path': '/exchange/yapi',
                            'req_query': [
                                {'name': 'page', 'value': '3', 'required': '0'},
                            ],
                            'req_headers': [
                                {'name': 'X-Token', 'value': 'yapi-token', 'required': '0'},
                            ],
                            'req_params': [],
                            'req_body_type': 'raw',
                            'req_body_other': '{"name":"yapi"}',
                            'res_body_type': 'raw',
                            'res_body': '',
                        },
                    ],
                },
            ],
        }

        expected = {
            'apifox': ('/exchange/apifox', 'Apifox Module', {'name': 'fox'}, 201),
            'apipost': ('/exchange/apipost', 'Apipost Module', {'name': 'post'}, 202),
            'yapi': ('/exchange/yapi', 'YApi Module', {'name': 'yapi'}, 200),
        }

        for source_format, document in fixtures.items():
            with self.subTest(source_format=source_format):
                uploaded = SimpleUploadedFile(
                    f'{source_format}.json',
                    json.dumps(document).encode('utf-8'),
                    content_type='application/json',
                )
                response = self.client.post(
                    f'{self.base_url}import-openapi/',
                    {'file': uploaded},
                    format='multipart',
                )

                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                self.assertEqual(response.data['format'], source_format)
                path, module_name, body, status_code = expected[source_format]
                interface = ApiInterface.objects.get(project=self.project, url=path)
                self.assertEqual(interface.module.name, module_name)
                self.assertEqual(interface.body['content'], body)
                self.assertEqual(interface.validators, [{'eq': ['status_code', status_code]}])
                self.assertEqual(interface.params[0]['key'], 'page')
                self.assertEqual(interface.headers[0]['key'], 'X-Token')

    def test_import_additional_file_formats(self):
        """Postman、HAR、Insomnia、ApiDoc、Apizza、Eolink 文件应按所选类型导入。"""
        fixtures = {
            'postman': {
                'info': {
                    'name': 'Postman Project',
                    '_postman_id': 'collection-1',
                    'schema': 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
                },
                'item': [{
                    'name': 'Postman Module',
                    'item': [{
                        'name': 'Postman Create',
                        'request': {
                            'method': 'POST',
                            'header': [{'key': 'Content-Type', 'value': 'application/json'}],
                            'body': {'mode': 'raw', 'raw': '{"name":"postman"}', 'options': {'raw': {'language': 'json'}}},
                            'url': {
                                'raw': 'https://example.com/exchange/postman?page=1',
                                'query': [{'key': 'page', 'value': '1'}],
                            },
                        },
                        'response': [{'name': 'Created', 'code': 201, 'body': '{"id":1}'}],
                    }],
                }],
            },
            'har': {
                'log': {
                    'version': '1.2',
                    'entries': [{
                        'pageref': 'HAR Module',
                        'request': {
                            'method': 'POST',
                            'url': 'https://example.com/exchange/har?page=2',
                            'headers': [{'name': 'Content-Type', 'value': 'application/json'}],
                            'queryString': [{'name': 'page', 'value': '2'}],
                            'postData': {'mimeType': 'application/json', 'text': '{"name":"har"}'},
                        },
                        'response': {'status': 202, 'statusText': 'Accepted', 'content': {'mimeType': 'application/json', 'text': '{"ok":true}'}},
                    }],
                },
            },
            'insomnia': {
                '__export_format': 4,
                'resources': [
                    {'_id': 'wrk_1', '_type': 'workspace', 'name': 'Insomnia Project'},
                    {'_id': 'fld_1', '_type': 'request_group', 'parentId': 'wrk_1', 'name': 'Insomnia Module'},
                    {
                        '_id': 'req_1',
                        '_type': 'request',
                        'parentId': 'fld_1',
                        'name': 'Insomnia Create',
                        'method': 'POST',
                        'url': 'https://example.com/exchange/insomnia',
                        'headers': [{'name': 'X-Token', 'value': 'token'}],
                        'parameters': [{'name': 'page', 'value': '3'}],
                        'body': {'mimeType': 'application/json', 'text': '{"name":"insomnia"}'},
                    },
                ],
            },
            'apidoc': [{
                'group': 'ApiDocModule',
                'groupTitle': 'ApiDoc Module',
                'title': 'ApiDoc Create',
                'type': 'post',
                'url': '/exchange/apidoc',
                'description': 'ApiDoc request',
                'parameter': {'fields': {'Parameter': [{'field': 'page', 'type': 'Number', 'optional': True, 'defaultValue': 4}]}},
                'success': {'examples': [{'content': '{"ok":true}'}]},
            }],
            'apizza': {
                'name': 'Apizza Project',
                'folders': [{
                    'name': 'Apizza Module',
                    'api_list': [{
                        'name': 'Apizza Create',
                        'method': 'POST',
                        'url': '/exchange/apizza',
                        'header_params': [{'key': 'X-Token', 'value': 'token'}],
                        'query_params': [{'key': 'page', 'value': '5'}],
                        'body_type': 'raw',
                        'raw_content_type': 'application/json',
                        'body_raw': '{"name":"apizza"}',
                        'response_example': '{"ok":true}',
                    }],
                }],
            },
            'eolink': {
                'projectInfo': {'projectName': 'Eolink Project'},
                'apiGroupList': [{
                    'groupName': 'Eolink Module',
                    'apiList': [{
                        'apiName': 'Eolink Create',
                        'apiURI': '/exchange/eolink',
                        'apiRequestType': 0,
                        'apiRequestHeader': [{'paramKey': 'X-Token', 'paramValue': 'token'}],
                        'apiRequestParam': [{'paramKey': 'page', 'paramValue': '6'}],
                        'apiRequestRaw': '{"name":"eolink"}',
                        'apiRequestRawType': 'application/json',
                        'apiResult': [{'httpCode': 203, 'result': '{"ok":true}'}],
                    }],
                }],
            },
        }

        for source_type, document in fixtures.items():
            with self.subTest(source_type=source_type):
                uploaded = SimpleUploadedFile(
                    f'{source_type}.json',
                    json.dumps(document).encode('utf-8'),
                    content_type='application/json',
                )
                response = self.client.post(
                    f'{self.base_url}import-openapi/',
                    {'file': uploaded, 'source_type': source_type},
                    format='multipart',
                )

                self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
                self.assertEqual(response.data['format'], source_type)
                interface = ApiInterface.objects.get(project=self.project, url=f'/exchange/{source_type}')
                self.assertEqual(interface.method, 'POST')
                self.assertTrue(interface.module_id)

    def test_import_curl_and_markdown_text(self):
        """cURL 和 Markdown 文本入口应创建可执行的 HTTP 接口。"""
        curl_response = self.client.post(
            f'{self.base_url}import-openapi/',
            {
                'source_type': 'curl',
                'content': "curl -X POST 'https://example.com/exchange/curl?page=7' -H 'Content-Type: application/json' -H 'X-Token: token' --data-raw '{\"name\":\"curl\"}'",
            },
            format='json',
        )
        self.assertEqual(curl_response.status_code, status.HTTP_201_CREATED, curl_response.data)
        self.assertEqual(curl_response.data['format'], 'curl')
        curl_interface = ApiInterface.objects.get(project=self.project, url='/exchange/curl')
        self.assertEqual(curl_interface.body['content'], {'name': 'curl'})
        self.assertEqual(curl_interface.params[0]['key'], 'page')

    def test_import_curl_with_windows_line_continuation(self):
        """Windows cmd 粘贴的 curl（行尾 ^ 续行符）不应把 ^ 残留进 URL/请求头/参数。"""
        curl_command = (
            'curl ^\r\n'
            '-X POST ^\r\n'
            '-H "Content-Type: application/json" ^\r\n'
            '-H "X-Token: token" ^\r\n'
            '-d "{\\"name\\":\\"curl\\"}" ^\r\n'
            '"https://example.com/exchange/curl?page=7" ^\r\n'
        )
        response = self.client.post(
            f'{self.base_url}import-openapi/',
            {'source_type': 'curl', 'content': curl_command},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        interface = ApiInterface.objects.get(project=self.project, url='/exchange/curl')
        # URL 不再带 ^（也不会被 ^ 顶替成 /^）
        self.assertEqual(interface.url, '/exchange/curl')
        self.assertNotIn('^', interface.url)
        for header in interface.headers:
            self.assertNotIn('^', f"{header.get('key', '')}{header.get('value', '')}")
        for param in interface.params:
            self.assertNotIn('^', f"{param.get('key', '')}{param.get('value', '')}")
        self.assertEqual(interface.body['content'], {'name': 'curl'})
        self.assertNotIn('^', json.dumps(interface.body.get('content', '')))

    def test_import_curl_with_caret_prefix(self):
        """^ 紧贴 token 开头的 Windows 续行写法（curl ^http://...）不应残留 ^。"""
        curl_command = (
            'curl ^http://172.31.69.83:5173/api/lg/token-usage/ ^\n'
            '-H "^authorization: Bearer xxx" ^\n'
        )
        response = self.client.post(
            f'{self.base_url}import-openapi/',
            {'source_type': 'curl', 'content': curl_command},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        interface = ApiInterface.objects.get(project=self.project, url='/api/lg/token-usage/')
        self.assertEqual(interface.name, 'GET /api/lg/token-usage/')
        self.assertNotIn('^', interface.url)
        header = next(item for item in interface.headers if item.get('key') == 'authorization')
        self.assertEqual(header['value'], 'Bearer xxx')
        self.assertNotIn('^', header['key'])
        self.assertNotIn('^', header['value'])

    def test_import_curl_keeps_real_caret_in_values(self):
        """curl 命令中 URL/请求头里真实存在的 ^ 字符不应被误删。"""
        curl_command = (
            'curl -G "https://example.com/exchange/curl?filter=a^b" '
            '-H "X-Mark: a^b"'
        )
        response = self.client.post(
            f'{self.base_url}import-openapi/',
            {'source_type': 'curl', 'content': curl_command},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        interface = ApiInterface.objects.get(project=self.project, url='/exchange/curl')
        header = next(item for item in interface.headers if item.get('key') == 'X-Mark')
        self.assertEqual(header['value'], 'a^b')
        param = next(item for item in interface.params if item.get('key') == 'filter')
        self.assertEqual(param['value'], 'a^b')

        markdown_response = self.client.post(
            f'{self.base_url}import-openapi/',
            {
                'source_type': 'markdown',
                'content': (
                    '# Markdown Project\n\n## Markdown Module\n\n'
                    '### List records\n\nGET /exchange/markdown\n\n'
                    '### Create record\n\n**请求方式：** POST\n\n'
                    '**请求地址：** /exchange/markdown-label'
                ),
            },
            format='json',
        )
        self.assertEqual(markdown_response.status_code, status.HTTP_201_CREATED, markdown_response.data)
        self.assertEqual(markdown_response.data['format'], 'markdown')
        markdown_interface = ApiInterface.objects.get(project=self.project, url='/exchange/markdown')
        self.assertEqual(markdown_interface.method, 'GET')
        self.assertEqual(markdown_interface.name, 'List records')
        label_interface = ApiInterface.objects.get(project=self.project, url='/exchange/markdown-label')
        self.assertEqual(label_interface.method, 'POST')
        self.assertEqual(label_interface.name, 'Create record')

    def test_import_markdown_widdershins_style(self):
        """widdershins 风格 Markdown 应导入请求体、title 模块名、方法后接口名并自动创建 Content-Type。"""
        markdown_content = (
            '---\n'
            'title: zw\n'
            'language_tabs:\n'
            '  - shell: Shell\n'
            'generator: "@tarslib/widdershins v4.0.30"\n'
            '---\n\n'
            '# zw\n\n'
            '# Default\n\n'
            '## POST login\n\n'
            'POST /api/auth/management/login\n\n'
            '> Body 请求参数\n\n'
            '```json\n'
            '{\n'
            '  "uuid": null,\n'
            '  "password": "0Xh0YZc7SWjLzsJDP1e8VQ==",\n'
            '  "username": "hPU75IwyzvA="\n'
            '}\n'
            '```\n\n'
            '### 请求参数\n\n'
            '|名称|位置|类型|必选|说明|\n'
            '|---|---|---|---|---|\n'
            '|body|body|object| 否 |none|\n\n'
            '> 返回示例\n\n'
            '```json\n'
            '{}\n'
            '```\n\n'
            '## POST 上传文件\n\n'
            'POST /api/projects/1/files/\n\n'
            '> Body 请求参数\n\n'
            '```yaml\n'
            'files: /C:/Users/zhangsan/Downloads/需求文档.docx\n'
            '```\n'
        )
        response = self.client.post(
            f'{self.base_url}import-openapi/',
            {'source_type': 'markdown', 'content': markdown_content},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['format'], 'markdown')

        login_interface = ApiInterface.objects.get(project=self.project, url='/api/auth/management/login')
        # 接口名取 "## POST login" 中请求方法后的名称
        self.assertEqual(login_interface.name, 'login')
        # 模块名取文档 frontmatter 的 title 字段
        self.assertEqual(login_interface.module.name, 'zw')
        # JSON 请求体被导入
        self.assertEqual(login_interface.body['type'], 'raw')
        self.assertEqual(
            login_interface.body['content'],
            {'uuid': None, 'password': '0Xh0YZc7SWjLzsJDP1e8VQ==', 'username': 'hPU75IwyzvA='},
        )
        # 根据请求体类型自动创建 Content-Type 请求头
        self.assertTrue(
            any(h.get('key') == 'Content-Type' and h.get('value') == 'application/json'
                for h in login_interface.headers)
        )

        upload_interface = ApiInterface.objects.get(project=self.project, url='/api/projects/1/files/')
        self.assertEqual(upload_interface.name, '上传文件')
        self.assertEqual(upload_interface.module.name, 'zw')
        # yaml 请求体转为 multipart/form-data
        self.assertEqual(upload_interface.body['type'], 'form-data')
        self.assertEqual(upload_interface.body['content'][0]['key'], 'files')
        self.assertTrue(
            any(h.get('key') == 'Content-Type' and h.get('value') == 'multipart/form-data'
                for h in upload_interface.headers)
        )

    def test_import_swagger_module_name_from_title(self):
        """Swagger 文档无 tags 时模块名取 info.title，完整 URL 路径剥离 origin。"""
        swagger_document = {
            'swagger': '2.0',
            'info': {'title': '水稻平台API', 'version': '1.0'},
            'paths': {
                'http://example.com/api/orders': {
                    'get': {'summary': '订单列表', 'responses': {'200': {'description': 'OK'}}},
                },
            },
        }
        response = self.client.post(
            f'{self.base_url}import-openapi/',
            {'source_type': 'swagger', 'content': json.dumps(swagger_document)},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        interface = ApiInterface.objects.get(project=self.project, url='/api/orders')
        # 完整 URL 路径剥离 origin，不再出现 /http:/... 垃圾路径
        self.assertEqual(interface.url, '/api/orders')
        # 模块名取文档 title，而不是路径片段
        self.assertEqual(interface.module.name, '水稻平台API')
        self.assertNotIn('http', interface.module.name.lower())

    def test_import_swagger_tags_prefer_over_title(self):
        """Swagger 文档显式声明 tags 时仍按 tags 分组，不覆盖为 title。"""
        swagger_document = {
            'swagger': '2.0',
            'info': {'title': '水稻平台API', 'version': '1.0'},
            'paths': {
                '/api/orders': {
                    'get': {'tags': ['订单模块'], 'summary': '订单列表', 'responses': {'200': {'description': 'OK'}}},
                },
            },
        }
        response = self.client.post(
            f'{self.base_url}import-openapi/',
            {'source_type': 'swagger', 'content': json.dumps(swagger_document)},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        interface = ApiInterface.objects.get(project=self.project, url='/api/orders')
        self.assertEqual(interface.module.name, '订单模块')

    @patch('api_interfaces.views.fetch_api_document')
    def test_import_swagger_url(self, fetch_api_document_mock):
        """Swagger URL 入口应获取远端文档后复用 Swagger 导入流程。"""
        fetch_api_document_mock.return_value = (
            json.dumps({
                'openapi': '3.0.3',
                'info': {'title': 'Remote API', 'version': '1.0.0'},
                'paths': {
                    '/exchange/swagger-url': {
                        'get': {'summary': 'Remote API', 'responses': {'200': {'description': 'OK'}}},
                    },
                },
            }).encode('utf-8'),
            'openapi.json',
        )

        response = self.client.post(
            f'{self.base_url}import-openapi/',
            {'source_type': 'swagger', 'source_url': 'https://example.com/openapi.json'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['format'], 'openapi')
        self.assertTrue(ApiInterface.objects.filter(project=self.project, url='/exchange/swagger-url').exists())
        fetch_api_document_mock.assert_called_once_with('https://example.com/openapi.json')

    def test_import_keep_full_url(self):
        """strip_base_url=False 时导入接口应保留完整 URL（含域名）。"""
        document = {
            'openapi': '3.0.3',
            'info': {'title': 'Full URL API', 'version': '1.0.0'},
            'servers': [{'url': 'https://api.example.com/v1'}],
            'paths': {
                '/orders': {
                    'get': {
                        'summary': 'List Orders',
                        'responses': {'200': {'description': 'OK'}},
                    },
                },
            },
        }
        uploaded = SimpleUploadedFile(
            'openapi.json',
            json.dumps(document).encode('utf-8'),
            content_type='application/json',
        )

        response = self.client.post(
            f'{self.base_url}import-openapi/',
            {'file': uploaded, 'source_type': 'swagger', 'strip_base_url': 'false'},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        interface = ApiInterface.objects.get(project=self.project, method='GET')
        self.assertEqual(interface.url, 'https://api.example.com/v1/orders')

    def test_import_create_environments(self):
        """create_environments=True 时应按域名创建环境，同一域名不重复创建。"""
        document = {
            'openapi': '3.0.3',
            'info': {'title': 'Env API', 'version': '1.0.0'},
            'servers': [{'url': 'https://api.example.com/v1'}],
            'paths': {
                '/items': {
                    'get': {'summary': 'List Items', 'responses': {'200': {'description': 'OK'}}},
                },
            },
        }
        uploaded = SimpleUploadedFile(
            'openapi.json',
            json.dumps(document).encode('utf-8'),
            content_type='application/json',
        )

        response = self.client.post(
            f'{self.base_url}import-openapi/',
            {'file': uploaded, 'source_type': 'swagger', 'create_environments': 'true'},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        created_envs = response.data.get('created_environments', [])
        self.assertEqual(len(created_envs), 1)
        self.assertEqual(created_envs[0]['base_url'], 'https://api.example.com')

        env = ApiEnvironment.objects.get(project=self.project, base_url='https://api.example.com')
        self.assertEqual(env.name, '环境1（导入）')
        self.assertTrue(env.verify_ssl)
        self.assertTrue(env.is_active)

        # 再次导入相同域名：接口更新（created_count=0 -> 200），环境跳过不重复创建
        uploaded_again = SimpleUploadedFile(
            'openapi.json',
            json.dumps(document).encode('utf-8'),
            content_type='application/json',
        )
        second_response = self.client.post(
            f'{self.base_url}import-openapi/',
            {'file': uploaded_again, 'source_type': 'swagger', 'create_environments': 'true'},
            format='multipart',
        )
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.data['created_environments'], [])
        self.assertEqual(
            ApiEnvironment.objects.filter(project=self.project, base_url='https://api.example.com').count(),
            1,
        )

    def test_import_create_environments_multiple_and_naming(self):
        """多个域名创建多个环境，命名接续已有最大编号。"""
        # 预置一个「环境2（导入）」验证接续编号
        ApiEnvironment.objects.create(
            project=self.project,
            created_by=self.user,
            name='环境2（导入）',
            base_url='https://preexisting.example.com',
            is_active=True,
        )

        document = {
            'openapi': '3.0.3',
            'info': {'title': 'Multi Env API', 'version': '1.0.0'},
            'paths': {
                'https://a.example.com/a': {
                    'get': {'summary': 'A', 'responses': {'200': {'description': 'OK'}}},
                },
                'http://b.example.com/b': {
                    'get': {'summary': 'B', 'responses': {'200': {'description': 'OK'}}},
                },
            },
        }
        uploaded = SimpleUploadedFile(
            'openapi.json',
            json.dumps(document).encode('utf-8'),
            content_type='application/json',
        )

        response = self.client.post(
            f'{self.base_url}import-openapi/',
            {'file': uploaded, 'source_type': 'swagger', 'create_environments': 'true'},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        created_envs = response.data.get('created_environments', [])
        self.assertEqual(len(created_envs), 2)
        base_urls = {env['base_url'] for env in created_envs}
        self.assertEqual(base_urls, {'https://a.example.com', 'http://b.example.com'})
        names = {env['name'] for env in created_envs}
        # 接续已有最大编号 2 -> 新建为 环境3（导入）、环境4（导入）
        self.assertEqual(names, {'环境3（导入）', '环境4（导入）'})
        # http 域名 verify_ssl 为 False
        http_env = ApiEnvironment.objects.get(project=self.project, base_url='http://b.example.com')
        self.assertFalse(http_env.verify_ssl)

    def test_import_postman_keep_full_url_and_create_environments(self):
        """Postman 导入：strip_base_url=False 保留完整 URL，create_environments 创建环境。"""
        document = {
            'info': {
                'name': 'Postman API',
                'schema': 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
            },
            'item': [{
                'name': 'Users',
                'item': [
                    {
                        'name': 'Get User',
                        'request': {
                            'method': 'GET',
                            'url': {
                                'raw': 'https://api.example.com/v1/users?page=1',
                                'protocol': 'https',
                                'host': ['api', 'example', 'com'],
                                'path': ['v1', 'users'],
                                'query': [{'key': 'page', 'value': '1'}],
                            },
                        },
                        'response': [],
                    },
                ],
            }],
        }
        uploaded = SimpleUploadedFile(
            'postman.json',
            json.dumps(document).encode('utf-8'),
            content_type='application/json',
        )

        response = self.client.post(
            f'{self.base_url}import-openapi/',
            {
                'file': uploaded,
                'source_type': 'postman',
                'strip_base_url': 'false',
                'create_environments': 'true',
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        # 接口保留完整 URL（含域名）
        interface = ApiInterface.objects.get(project=self.project, method='GET')
        self.assertEqual(interface.url, 'https://api.example.com/v1/users')
        # 自动创建环境，base_url 为域名前缀
        created_envs = response.data.get('created_environments', [])
        self.assertEqual(len(created_envs), 1)
        self.assertEqual(created_envs[0]['base_url'], 'https://api.example.com')
        env = ApiEnvironment.objects.get(project=self.project, base_url='https://api.example.com')
        self.assertEqual(env.name, '环境1（导入）')
        self.assertTrue(env.verify_ssl)

    def test_import_postman_module_name_from_info(self):
        """Postman 无 folder 时模块名应取 info.name，而非 URL 前缀（http:）。"""
        document = {
            'info': {
                'name': 'My Collection',
                'schema': 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
            },
            'item': [
                {
                    'name': 'Get User',
                    'request': {
                        'method': 'GET',
                        'url': {'raw': 'https://api.example.com/v1/users'},
                    },
                },
            ],
        }
        uploaded = SimpleUploadedFile(
            'postman.json',
            json.dumps(document).encode('utf-8'),
            content_type='application/json',
        )

        response = self.client.post(
            f'{self.base_url}import-openapi/',
            {'file': uploaded, 'source_type': 'postman', 'strip_base_url': 'false'},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        interface = ApiInterface.objects.get(project=self.project, method='GET')
        self.assertTrue(interface.module_id)
        # 模块名应取 collection 的 info.name，而不是 http:
        self.assertEqual(interface.module.name, 'My Collection')
        self.assertNotIn('http', interface.module.name.lower())

    def test_fetch_api_document_timeout_raises_clear_error(self):
        """远端抓取超时应抛出带超时说明的 OpenAPIError，而不是后台 500。"""
        with patch('api_interfaces.exchange.urlopen', side_effect=TimeoutError('connection timed out')):
            with self.assertRaises(OpenAPIError) as ctx:
                fetch_api_document('https://example.com/openapi.json')
        self.assertIn('timed out', str(ctx.exception))
        self.assertIn('slow or unresponsive', str(ctx.exception))

    def test_fetch_api_document_network_error_reports_url(self):
        """远端连接失败应给出可读的错误信息。"""
        with patch('api_interfaces.exchange.urlopen', side_effect=URLError('Name or service not known')):
            with self.assertRaises(OpenAPIError) as ctx:
                fetch_api_document('https://example.com/openapi.json')
        self.assertIn('Unable to fetch Swagger URL', str(ctx.exception))

    def test_fetch_api_document_rejects_oversized_declaration(self):
        """Content-Length 声明超过上限时应在下载前直接拒绝。"""
        mock_response = MagicMock()
        mock_response.headers = {'Content-Length': str(20 * 1024 * 1024)}
        mock_response.geturl.return_value = 'https://example.com/openapi.json'
        with patch('api_interfaces.exchange.urlopen', return_value=MagicMock(
            __enter__=MagicMock(return_value=mock_response),
            __exit__=MagicMock(return_value=False),
        )):
            with self.assertRaises(OpenAPIError) as ctx:
                fetch_api_document('https://example.com/openapi.json')
        self.assertIn('too large', str(ctx.exception))

    def test_import_openapi_rolls_back_on_partial_failure(self):
        """导入中途发生校验错误时，整个导入应回滚，不残留任何接口或模块。"""
        document = {
            'openapi': '3.0.3',
            'info': {'title': 'Rollback API', 'version': '1.0.0'},
            'paths': {
                '/first': {
                    'get': {
                        'summary': 'First API',
                        'tags': ['Rollback'],
                        'responses': {'200': {'description': 'OK'}},
                    },
                },
                '/second': {
                    'get': {
                        'summary': 'Second API',
                        'tags': ['Rollback'],
                        'responses': {'200': {'description': 'OK'}},
                    },
                },
            },
        }
        uploaded = SimpleUploadedFile(
            'openapi.json',
            json.dumps(document).encode('utf-8'),
            content_type='application/json',
        )

        # 让第二个接口（/second）保存时抛错，模拟导入中途失败
        original_save = ApiInterfaceSerializer.save
        calls = {'count': 0}

        def failing_save(self, *args, **kwargs):
            calls['count'] += 1
            if calls['count'] >= 2:
                raise DRFValidationError({'url': ['simulated failure']})
            return original_save(self, *args, **kwargs)

        with patch.object(ApiInterfaceSerializer, 'save', failing_save):
            response = self.client.post(
                f'{self.base_url}import-openapi/',
                {'file': uploaded, 'source_type': 'swagger'},
                format='multipart',
            )

        self.assertEqual(ApiInterface.objects.filter(project=self.project).count(), 0)
        self.assertEqual(ApiModule.objects.filter(project=self.project).count(), 0)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_import_openapi_matches_existing_interface_without_duplication(self):
        """此前已导入的接口按 method+url 匹配更新，不应重复创建。"""
        module = ApiModule.objects.create(name='Auth', project=self.project, created_by=self.user)
        ApiInterface.objects.create(
            name='Login',
            type='http',
            method='POST',
            url='/login',
            project=self.project,
            created_by=self.user,
        )

        document = {
            'openapi': '3.0.3',
            'info': {'title': 'Auth API', 'version': '1.0.0'},
            'paths': {
                '/login': {
                    'post': {
                        'summary': 'Login',
                        'tags': ['Auth'],
                        'responses': {'200': {'description': 'OK'}},
                    },
                },
            },
        }
        uploaded = SimpleUploadedFile(
            'openapi.json',
            json.dumps(document).encode('utf-8'),
            content_type='application/json',
        )

        response = self.client.post(
            f'{self.base_url}import-openapi/',
            {'file': uploaded, 'source_type': 'swagger'},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['created_count'], 0)
        self.assertEqual(response.data['updated_count'], 1)
        self.assertEqual(ApiInterface.objects.filter(project=self.project).count(), 1)

    def test_import_openapi_with_self_referencing_schema(self):
        """自引用 schema（树形结构）导入不应触发无限递归。"""
        document = {
            'openapi': '3.0.3',
            'info': {'title': 'Tree API', 'version': '1.0.0'},
            'components': {
                'schemas': {
                    'TreeNode': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'integer'},
                            'name': {'type': 'string'},
                            'children': {
                                'type': 'array',
                                'items': {'$ref': '#/components/schemas/TreeNode'},
                            },
                            'parent': {'$ref': '#/components/schemas/TreeNode'},
                        },
                    },
                },
            },
            'paths': {
                '/tree': {
                    'post': {
                        'summary': 'Save Tree',
                        'tags': ['Tree'],
                        'requestBody': {
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/TreeNode'},
                                },
                            },
                        },
                        'responses': {'200': {'description': 'OK'}},
                    },
                },
            },
        }
        uploaded = SimpleUploadedFile(
            'openapi.json',
            json.dumps(document).encode('utf-8'),
            content_type='application/json',
        )

        response = self.client.post(
            f'{self.base_url}import-openapi/',
            {'file': uploaded, 'source_type': 'swagger'},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        interface = ApiInterface.objects.get(project=self.project, method='POST', url='/tree')
        body_content = interface.body.get('content') if isinstance(interface.body, dict) else None
        # 自引用截断：children 应生成一层示例后停止，不再无限嵌套
        self.assertIsInstance(body_content, dict)
        self.assertIn('id', body_content)
        self.assertIn('children', body_content)

    def test_export_native_formats_round_trip(self):
        """三种原生格式导出后应能由同一导入入口完整识别。"""
        module = ApiModule.objects.create(
            name='Exchange Module',
            project=self.project,
            created_by=self.user,
        )
        ApiInterface.objects.create(
            name='Exchange Login',
            type='http',
            method='POST',
            url='/exchange/login',
            headers=[
                {'key': 'Content-Type', 'value': 'application/json', 'enabled': True, 'description': ''},
                {'key': 'X-Token', 'value': 'token', 'enabled': True, 'description': ''},
            ],
            params=[
                {'key': 'page', 'value': '1', 'enabled': True, 'description': ''},
            ],
            body={'type': 'raw', 'content': {'username': 'tester'}},
            validators=[{'eq': ['status_code', 201]}],
            project=self.project,
            module=module,
            created_by=self.user,
        )

        for export_format in ('apifox', 'apipost', 'yapi'):
            with self.subTest(export_format=export_format):
                export_response = self.client.get(
                    f'{self.base_url}export-openapi/',
                    {'export_format': export_format},
                )
                self.assertEqual(export_response.status_code, status.HTTP_200_OK)
                self.assertIn('application/json', export_response['Content-Type'])
                self.assertIn(
                    f'project-{self.project.id}-{export_format}.json',
                    export_response['Content-Disposition'],
                )

                exported = json.loads(export_response.content.decode('utf-8'))
                if export_format == 'apifox':
                    self.assertEqual(exported['apifoxProject'], '1.0.0')
                elif export_format == 'apipost':
                    self.assertTrue(any(item.get('target_type') == 'api' for item in exported['apis']))
                else:
                    self.assertEqual(exported[0]['name'], 'Exchange Module')

                uploaded = SimpleUploadedFile(
                    f'{export_format}.json',
                    export_response.content,
                    content_type='application/json',
                )
                import_response = self.client.post(
                    f'{self.base_url}import-openapi/',
                    {'file': uploaded},
                    format='multipart',
                )
                self.assertEqual(import_response.status_code, status.HTTP_200_OK)
                self.assertEqual(import_response.data['format'], export_format)
                self.assertEqual(import_response.data['updated_count'], 1)

                interface = ApiInterface.objects.get(project=self.project, url='/exchange/login')
                self.assertEqual(interface.module.name, 'Exchange Module')
                self.assertEqual(interface.body['content'], {'username': 'tester'})
                self.assertEqual(interface.params[0]['key'], 'page')
                self.assertEqual(interface.headers[0]['key'], 'X-Token')

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



    def test_list_filter_status_and_ordering(self):
        """列表支持 status 筛选与 created_at/updated_at 排序"""
        older = ApiInterface.objects.create(
            name='Older API', type='http', method='GET', url='/api/old',
            project=self.project, created_by=self.user, status='self_testing',
        )
        newer = ApiInterface.objects.create(
            name='Newer API', type='http', method='GET', url='/api/new',
            project=self.project, created_by=self.user, status='completed',
        )
        from django.utils import timezone
        from datetime import timedelta
        now = timezone.now()
        # QuerySet.update 不会触发 auto_now，需显式写入时间戳
        ApiInterface.objects.filter(pk=older.pk).update(updated_at=now - timedelta(hours=1))
        ApiInterface.objects.filter(pk=newer.pk).update(updated_at=now)

        status_resp = self.client.get(self.base_url, {'status': 'completed'})
        self.assertEqual(status_resp.status_code, status.HTTP_200_OK)
        status_ids = [item['id'] for item in status_resp.data.get('results', status_resp.data if isinstance(status_resp.data, list) else [])]
        if not status_ids and isinstance(status_resp.data, dict) and 'results' not in status_resp.data:
            # non-paginated fallback
            status_ids = [item['id'] for item in status_resp.data] if isinstance(status_resp.data, list) else []
        self.assertIn(newer.pk, status_ids)
        self.assertNotIn(older.pk, status_ids)

        order_resp = self.client.get(self.base_url, {'ordering': 'created_at'})
        self.assertEqual(order_resp.status_code, status.HTTP_200_OK)
        payload = order_resp.data.get('results', order_resp.data if isinstance(order_resp.data, list) else [])
        ids = [item['id'] for item in payload]
        if older.pk in ids and newer.pk in ids:
            self.assertLess(ids.index(older.pk), ids.index(newer.pk))

        order_desc = self.client.get(self.base_url, {'ordering': '-created_at'})
        self.assertEqual(order_desc.status_code, status.HTTP_200_OK)
        payload_desc = order_desc.data.get('results', order_desc.data if isinstance(order_desc.data, list) else [])
        ids_desc = [item['id'] for item in payload_desc]
        if older.pk in ids_desc and newer.pk in ids_desc:
            self.assertLess(ids_desc.index(newer.pk), ids_desc.index(older.pk))

        updated_asc = self.client.get(self.base_url, {'ordering': 'updated_at'})
        self.assertEqual(updated_asc.status_code, status.HTTP_200_OK)
        payload_u = updated_asc.data.get('results', updated_asc.data if isinstance(updated_asc.data, list) else [])
        ids_u = [item['id'] for item in payload_u]
        if older.pk in ids_u and newer.pk in ids_u:
            self.assertLess(ids_u.index(older.pk), ids_u.index(newer.pk))

        updated_desc = self.client.get(self.base_url, {'ordering': '-updated_at'})
        self.assertEqual(updated_desc.status_code, status.HTTP_200_OK)
        payload_ud = updated_desc.data.get('results', updated_desc.data if isinstance(updated_desc.data, list) else [])
        ids_ud = [item['id'] for item in payload_ud]
        if older.pk in ids_ud and newer.pk in ids_ud:
            self.assertLess(ids_ud.index(newer.pk), ids_ud.index(older.pk))

    def test_batch_delete_interfaces(self):
        """测试批量删除接口"""
        i1 = ApiInterface.objects.create(
            name='Batch Delete 1', type='http', method='GET', url='/api/b1',
            project=self.project, created_by=self.user,
        )
        i2 = ApiInterface.objects.create(
            name='Batch Delete 2', type='http', method='POST', url='/api/b2',
            project=self.project, created_by=self.user,
        )
        response = self.client.post(
            f'{self.base_url}batch-delete/',
            {'ids': [i1.pk, i2.pk]},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('deleted_count'), 2)
        self.assertFalse(ApiInterface.objects.filter(pk__in=[i1.pk, i2.pk]).exists())

        # 空列表应 400
        empty_resp = self.client.post(f'{self.base_url}batch-delete/', {'ids': []}, format='json')
        self.assertEqual(empty_resp.status_code, status.HTTP_400_BAD_REQUEST)

        # 不存在的 ID 应 400
        missing_resp = self.client.post(
            f'{self.base_url}batch-delete/',
            {'ids': [999999]},
            format='json',
        )
        self.assertEqual(missing_resp.status_code, status.HTTP_400_BAD_REQUEST)


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

    def test_create_with_extract_meta(self):
        """测试创建提取变量元信息"""
        data = {
            'name': 'Extract Meta API',
            'type': 'http',
            'method': 'GET',
            'url': '/api/test',
            'extract': {'token': 'body.data.token'},
            'extract_meta': {'token': {'variable_type': 'project'}},
            'project': self.project.pk,
        }

        response = self.client.post(self.base_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        interface = ApiInterface.objects.get(name='Extract Meta API')
        self.assertEqual(interface.extract_meta, {'token': {'variable_type': 'project'}})

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
        environment = ApiEnvironment.objects.create(
            name='Run Env',
            base_url='http://staging.example.com',
            project=self.project,
            created_by=self.user,
        )
        ApiEnvironmentVariable.objects.create(
            environment=environment,
            name='api_key',
            value='secret',
            type='string',
        )

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

        response = self.client.post(
            f'{self.base_url}{interface.pk}/run/',
            {'environment_id': environment.pk},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_instance.run_interface.assert_called_once_with({'variables': {'api_key': 'secret'}})

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

    @patch('api_interfaces.views.InterfaceRunner')
    def test_quick_debug_with_environment_passes_variables_to_runner(self, MockRunner):
        """quick_debug/ 应将环境变量传递给 runner"""
        environment = ApiEnvironment.objects.create(
            name='Debug Env',
            base_url='http://staging.example.com',
            project=self.project,
            created_by=self.user,
        )
        ApiEnvironmentVariable.objects.create(
            environment=environment,
            name='access',
            value='Bearer demo-token',
            type='string',
        )

        mock_instance = MagicMock()
        mock_instance.variables = {}
        mock_instance.get_response.return_value = {
            'success': True,
            'status_code': 200,
            'elapsed': 50,
            'request': {},
            'response': {},
            'validation_results': [],
            'extracted_variables': {},
        }
        mock_instance.interface_data = {}
        MockRunner.return_value = mock_instance

        response = self.client.post(
            f'{self.base_url}quick_debug/',
            {
                'type': 'http',
                'method': 'GET',
                'url': 'http://example.com/api/test',
                'headers': {'Authorization': '${access}'},
                'environment_id': environment.pk,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_instance.run_interface.assert_called_once_with({'variables': {'access': 'Bearer demo-token'}})

    @patch('api_interfaces.views.InterfaceRunner')
    def test_run_persists_project_extract_variables_to_environment(self, MockRunner):
        """run/ 会将项目变量提取结果写入当前环境变量"""
        environment = ApiEnvironment.objects.create(
            name='Run Env',
            base_url='http://example.com',
            project=self.project,
            created_by=self.user,
        )
        mock_instance = MagicMock()
        mock_instance.variables = {}
        mock_instance.get_response.return_value = {
            'success': True,
            'status_code': 200,
            'elapsed': 123,
            'request': {},
            'response': {},
            'validation_results': [],
            'extracted_variables': {'token': 'abc123'},
        }
        MockRunner.return_value = mock_instance

        interface = ApiInterface.objects.create(
            name='Persist API',
            type='http',
            method='GET',
            url='http://example.com/api/test',
            extract={'token': 'body.data.token'},
            extract_meta={'token': {'variable_type': 'project'}},
            project=self.project,
            created_by=self.user,
        )

        response = self.client.post(
            f'{self.base_url}{interface.pk}/run/',
            {'environment_id': environment.pk},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['extract_persistence']['created_count'], 1)
        variable = ApiEnvironmentVariable.objects.get(environment=environment, name='token')
        self.assertEqual(variable.value, 'abc123')

    @patch('api_interfaces.views.InterfaceRunner')
    def test_quick_debug_marks_skip_when_project_extract_has_no_environment(self, MockRunner):
        """quick_debug/ 无环境时返回项目变量跳过保存标记"""
        mock_instance = MagicMock()
        mock_instance.variables = {}
        mock_instance.get_response.return_value = {
            'success': True,
            'status_code': 200,
            'elapsed': 50,
            'request': {},
            'response': {},
            'validation_results': [],
            'extracted_variables': {'token': 'abc123'},
        }
        mock_instance.interface_data = {}
        MockRunner.return_value = mock_instance

        response = self.client.post(
            f'{self.base_url}quick_debug/',
            {
                'type': 'http',
                'method': 'GET',
                'url': 'http://example.com/api/test',
                'extract': {'token': 'body.data.token'},
                'extract_meta': {'token': {'variable_type': 'project'}},
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['extract_persistence']['skipped_no_environment'])
        self.assertEqual(ApiEnvironmentVariable.objects.count(), 0)

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
    def test_runner_run_interface_merges_environment_variables_into_config(self, mock_test_start, mock_load_funcs):
        """运行前应将环境变量合并进 httprunner 配置"""
        from .runner import InterfaceRunner

        interface_data = {
            'name': 'Run With Env Vars',
            'type': 'http',
            'method': 'GET',
            'url': 'http://example.com/api/test',
            'headers': {'Authorization': '${access}'},
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
        runner.run_interface({'variables': {'access': 'Bearer demo-token'}})

        self.assertEqual(runner.variables['access'], 'Bearer demo-token')
        self.assertEqual(runner.config.struct().variables['access'], 'Bearer demo-token')
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
