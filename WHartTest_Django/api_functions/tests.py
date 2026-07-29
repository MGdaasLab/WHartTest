from django.test import TestCase
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient
from rest_framework import status

from projects.models import Project, ProjectMember
from .models import ApiCustomFunction


def _grant_all_function_perms(user):
    """授予用户 ApiCustomFunction 的全部模型权限。"""
    ct = ContentType.objects.get_for_model(ApiCustomFunction)
    perms = Permission.objects.filter(content_type=ct)
    user.user_permissions.add(*perms)
    # Clear cached permissions
    user.refresh_from_db()


class ApiCustomFunctionModelTest(TestCase):
    """ApiCustomFunction 模型测试"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)

    def test_create_function(self):
        """测试创建自定义函数"""
        func = ApiCustomFunction.objects.create(
            name='get_token',
            code='def get_token():\n    return "abc123"',
            description='Generate a token',
            project=self.project,
            created_by=self.user,
        )
        self.assertEqual(func.name, 'get_token')
        self.assertEqual(func.project, self.project)
        self.assertTrue(func.is_active)
        self.assertIsNotNone(func.created_at)
        self.assertIsNotNone(func.updated_at)

    def test_str_representation(self):
        """测试字符串表示"""
        func = ApiCustomFunction.objects.create(
            name='my_func',
            code='def my_func():\n    pass',
            project=self.project,
            created_by=self.user,
        )
        self.assertEqual(str(func), 'Test Project-my_func')

    def test_unique_together_name_project(self):
        """测试同一项目下函数名唯一约束"""
        ApiCustomFunction.objects.create(
            name='duplicate_func',
            code='def duplicate_func():\n    pass',
            project=self.project,
            created_by=self.user,
        )
        with self.assertRaises(Exception):
            ApiCustomFunction.objects.create(
                name='duplicate_func',
                code='def duplicate_func():\n    return 1',
                project=self.project,
                created_by=self.user,
            )

    def test_same_name_different_projects(self):
        """测试不同项目可以有相同函数名"""
        project2 = Project.objects.create(name='Project 2', creator=self.user)
        ApiCustomFunction.objects.create(
            name='shared_name',
            code='def shared_name():\n    pass',
            project=self.project,
            created_by=self.user,
        )
        func2 = ApiCustomFunction.objects.create(
            name='shared_name',
            code='def shared_name():\n    return 1',
            project=project2,
            created_by=self.user,
        )
        self.assertEqual(func2.project, project2)

    def test_ordering(self):
        """测试默认按 created_at 降序排列"""
        func1 = ApiCustomFunction.objects.create(
            name='func_a',
            code='def func_a():\n    pass',
            project=self.project,
            created_by=self.user,
        )
        func2 = ApiCustomFunction.objects.create(
            name='func_b',
            code='def func_b():\n    pass',
            project=self.project,
            created_by=self.user,
        )
        functions = list(ApiCustomFunction.objects.all())
        self.assertEqual(functions[0], func2)
        self.assertEqual(functions[1], func1)

    def test_cascade_delete_project(self):
        """测试删除项目时级联删除函数"""
        ApiCustomFunction.objects.create(
            name='to_delete',
            code='def to_delete():\n    pass',
            project=self.project,
            created_by=self.user,
        )
        self.project.delete()
        self.assertEqual(ApiCustomFunction.objects.count(), 0)

    def test_set_null_on_user_delete(self):
        """测试删除用户时 created_by 置空"""
        func = ApiCustomFunction.objects.create(
            name='orphan_func',
            code='def orphan_func():\n    pass',
            project=self.project,
            created_by=self.user,
        )
        self.user.delete()
        func.refresh_from_db()
        self.assertIsNone(func.created_by)


class ApiCustomFunctionAPITest(TestCase):
    """ApiCustomFunction API CRUD 测试"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='apiuser', password='testpass')
        self.project = Project.objects.create(name='API Project', creator=self.user)
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        _grant_all_function_perms(self.user)
        self.client.force_authenticate(user=self.user)
        self.base_url = f'/api/projects/{self.project.pk}/api-functions/'

    def test_list_functions(self):
        """测试获取函数列表"""
        ApiCustomFunction.objects.create(
            name='func1',
            code='def func1():\n    pass',
            project=self.project,
            created_by=self.user,
        )
        ApiCustomFunction.objects.create(
            name='func2',
            code='def func2():\n    pass',
            project=self.project,
            created_by=self.user,
        )
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_function(self):
        """测试创建函数"""
        data = {
            'name': 'new_func',
            'code': 'def new_func():\n    return "hello"',
            'description': 'A new function',
            'project': self.project.pk,
        }
        response = self.client.post(self.base_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        func = ApiCustomFunction.objects.get(name='new_func')
        self.assertEqual(func.project, self.project)
        self.assertEqual(func.created_by, self.user)

    def test_create_duplicate_function_name_returns_validation_error(self):
        """同一项目下函数名重复时返回字段校验错误"""
        ApiCustomFunction.objects.create(
            name='duplicate_func',
            code='def duplicate_func():\n    return "old"',
            project=self.project,
            created_by=self.user,
        )

        response = self.client.post(
            self.base_url,
            {
                'name': 'duplicate_func',
                'code': 'def duplicate_func():\n    return "new"',
                'description': 'Duplicate function',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)
        self.assertEqual(
            ApiCustomFunction.objects.filter(
                project=self.project,
                name='duplicate_func',
            ).count(),
            1,
        )

    def test_retrieve_function(self):
        """测试获取单个函数"""
        func = ApiCustomFunction.objects.create(
            name='detail_func',
            code='def detail_func():\n    pass',
            project=self.project,
            created_by=self.user,
        )
        response = self.client.get(f'{self.base_url}{func.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_function(self):
        """测试更新函数"""
        func = ApiCustomFunction.objects.create(
            name='update_func',
            code='def update_func():\n    pass',
            project=self.project,
            created_by=self.user,
        )
        data = {
            'name': 'update_func',
            'code': 'def update_func():\n    return "updated"',
            'description': 'Updated description',
        }
        response = self.client.put(f'{self.base_url}{func.pk}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        func.refresh_from_db()
        self.assertIn('updated', func.code)

    def test_partial_update_function(self):
        """测试部分更新函数"""
        func = ApiCustomFunction.objects.create(
            name='patch_func',
            code='def patch_func():\n    pass',
            project=self.project,
            created_by=self.user,
        )
        response = self.client.patch(
            f'{self.base_url}{func.pk}/',
            {'is_active': False},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        func.refresh_from_db()
        self.assertFalse(func.is_active)

    def test_delete_function(self):
        """测试删除函数"""
        func = ApiCustomFunction.objects.create(
            name='delete_func',
            code='def delete_func():\n    pass',
            project=self.project,
            created_by=self.user,
        )
        response = self.client.delete(f'{self.base_url}{func.pk}/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])
        self.assertFalse(ApiCustomFunction.objects.filter(pk=func.pk).exists())

    def test_create_code_validation_no_def(self):
        """测试代码必须以 def 开头"""
        data = {
            'name': 'bad_func',
            'code': 'print("hello")',
        }
        response = self.client.post(self.base_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_code_validation_forbidden_keywords(self):
        """测试禁止危险函数"""
        forbidden_codes = [
            'def bad():\n    import os',
            'def bad():\n    import subprocess',
            'def bad():\n    eval("1+1")',
            'def bad():\n    exec("pass")',
            'def bad():\n    open("/etc/passwd")',
        ]
        for code in forbidden_codes:
            data = {'name': 'bad_func', 'code': code}
            response = self.client.post(self.base_url, data, format='json')
            self.assertEqual(
                response.status_code,
                status.HTTP_400_BAD_REQUEST,
                f'Expected 400 for code: {code}',
            )

    def test_create_code_validation_max_length(self):
        """测试代码长度限制"""
        data = {
            'name': 'long_func',
            'code': 'def long_func():\n    pass' + ' ' * 10001,
        }
        response = self.client.post(self.base_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_generate_debugtalk(self):
        """测试生成 debugtalk.py 内容"""
        ApiCustomFunction.objects.create(
            name='func_a',
            code='def func_a():\n    return 1',
            description='Function A',
            project=self.project,
            created_by=self.user,
            is_active=True,
        )
        ApiCustomFunction.objects.create(
            name='func_b',
            code='def func_b():\n    return 2',
            project=self.project,
            created_by=self.user,
            is_active=True,
        )
        # Inactive function should not be included
        ApiCustomFunction.objects.create(
            name='inactive_func',
            code='def inactive_func():\n    pass',
            project=self.project,
            created_by=self.user,
            is_active=False,
        )
        response = self.client.get(f'{self.base_url}generate_debugtalk/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.data['content']
        self.assertIn('func_a', content)
        self.assertIn('func_b', content)
        self.assertNotIn('inactive_func', content)
        self.assertIn('auto-generated', content)

    def test_execute_valid_function(self):
        """测试执行有效函数"""
        data = {
            'code': 'def add(a, b):\n    return a + b',
            'test_args': {'a': 1, 'b': 2},
        }
        response = self.client.post(f'{self.base_url}execute/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['result'], '3')

    def test_execute_no_args(self):
        """测试执行无参数函数"""
        data = {
            'code': 'def hello():\n    return "world"',
        }
        response = self.client.post(f'{self.base_url}execute/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['result'], 'world')

    def test_execute_missing_code(self):
        """测试执行时缺少 code 字段"""
        response = self.client.post(f'{self.base_url}execute/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('code', response.data['detail'].lower())

    def test_execute_invalid_code(self):
        """测试执行语法错误的代码"""
        data = {'code': 'def bad(\n    return'}
        response = self.client.post(f'{self.base_url}execute/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_access(self):
        """测试未认证用户无法访问"""
        self.client.force_authenticate(user=None)
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ApiCustomFunctionPermissionTest(TestCase):
    """ApiCustomFunction 权限测试"""

    def setUp(self):
        self.client = APIClient()
        # Project A with member
        self.user_a = User.objects.create_user(username='user_a', password='testpass')
        self.project_a = Project.objects.create(name='Project A', creator=self.user_a)
        ProjectMember.objects.create(project=self.project_a, user=self.user_a, role='member')
        _grant_all_function_perms(self.user_a)

        # Project B with member
        self.user_b = User.objects.create_user(username='user_b', password='testpass')
        self.project_b = Project.objects.create(name='Project B', creator=self.user_b)
        ProjectMember.objects.create(project=self.project_b, user=self.user_b, role='admin')
        _grant_all_function_perms(self.user_b)

        # Superuser
        self.superuser = User.objects.create_superuser(
            username='admin', password='adminpass'
        )

        # Non-member user
        self.outsider = User.objects.create_user(username='outsider', password='testpass')

        # Create a function in each project
        self.func_a = ApiCustomFunction.objects.create(
            name='func_a',
            code='def func_a():\n    pass',
            project=self.project_a,
            created_by=self.user_a,
        )
        self.func_b = ApiCustomFunction.objects.create(
            name='func_b',
            code='def func_b():\n    pass',
            project=self.project_b,
            created_by=self.user_b,
        )

    def test_project_isolation_list(self):
        """测试项目数据隔离 - 列表只返回当前项目的函数"""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f'/api/projects/{self.project_a.pk}/api-functions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Handle both paginated (dict with 'results') and non-paginated (list) responses
        results = response.data.get('results', response.data) if isinstance(response.data, dict) else response.data
        func_names = [f['name'] for f in results]
        self.assertIn('func_a', func_names)
        self.assertNotIn('func_b', func_names)

    def test_cross_project_access_denied(self):
        """测试跨项目访问被拒绝 - A 项目成员不能访问 B 项目"""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f'/api/projects/{self.project_b.pk}/api-functions/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cross_project_detail_denied(self):
        """测试跨项目访问详情被拒绝"""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(
            f'/api/projects/{self.project_b.pk}/api-functions/{self.func_b.pk}/'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_member_access_denied(self):
        """测试非项目成员无法访问"""
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(f'/api/projects/{self.project_a.pk}/api-functions/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_access_all_projects(self):
        """测试超级管理员可以访问所有项目"""
        self.client.force_authenticate(user=self.superuser)
        for project in [self.project_a, self.project_b]:
            response = self.client.get(f'/api/projects/{project.pk}/api-functions/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_execute_requires_admin(self):
        """测试 execute action 需要项目管理员权限"""
        # Regular member should be denied (requires IsProjectAdminForResource)
        self.client.force_authenticate(user=self.user_a)  # role=member
        data = {'code': 'def test():\n    return 1'}
        response = self.client.post(
            f'/api/projects/{self.project_a.pk}/api-functions/execute/',
            data,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_execute_allowed_for_admin(self):
        """测试项目管理员可以执行函数"""
        self.client.force_authenticate(user=self.user_b)  # role=admin
        data = {'code': 'def test():\n    return 1'}
        response = self.client.post(
            f'/api/projects/{self.project_b.pk}/api-functions/execute/',
            data,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_execute_allowed_for_superuser(self):
        """测试超级管理员可以执行函数"""
        self.client.force_authenticate(user=self.superuser)
        data = {'code': 'def test():\n    return 42'}
        response = self.client.post(
            f'/api/projects/{self.project_a.pk}/api-functions/execute/',
            data,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_invalid_project_pk(self):
        """测试无效的 project_pk"""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get('/api/projects/999999/api-functions/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_none_project_pk(self):
        """测试 project_pk 为 None/null/undefined"""
        self.client.force_authenticate(user=self.user_a)
        for bad_pk in ['none', 'null', 'undefined']:
            response = self.client.get(f'/api/projects/{bad_pk}/api-functions/')
            self.assertIn(
                response.status_code,
                [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND],
            )


class LoadCustomFunctionsTest(TestCase):
    """load_custom_functions 函数测试"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)

    def test_load_active_functions(self):
        """只加载 is_active=True 的函数"""
        ApiCustomFunction.objects.create(
            name='active_func',
            code='def greet(name):\n    return f"Hello {name}"',
            project=self.project,
            created_by=self.user,
            is_active=True,
        )
        ApiCustomFunction.objects.create(
            name='inactive_func',
            code='def bye():\n    return "Goodbye"',
            project=self.project,
            created_by=self.user,
            is_active=False,
        )
        from api_interfaces.runner import load_custom_functions
        functions = load_custom_functions(self.project.pk)
        self.assertIn('greet', functions)
        self.assertNotIn('bye', functions)

    def test_load_function_with_syntax_error(self):
        """语法错误的函数不影响其他函数加载"""
        ApiCustomFunction.objects.create(
            name='good_func',
            code='def good():\n    return 1',
            project=self.project,
            created_by=self.user,
            is_active=True,
        )
        ApiCustomFunction.objects.create(
            name='bad_func',
            code='def bad(\n    return',
            project=self.project,
            created_by=self.user,
            is_active=True,
        )
        from api_interfaces.runner import load_custom_functions
        functions = load_custom_functions(self.project.pk)
        self.assertIn('good', functions)

    def test_no_functions_returns_empty_dict(self):
        """无函数时返回空字典"""
        from api_interfaces.runner import load_custom_functions
        functions = load_custom_functions(self.project.pk)
        self.assertEqual(functions, {})

    def test_function_without_callable_skipped(self):
        """代码中无可调用函数的记录被跳过"""
        ApiCustomFunction.objects.create(
            name='no_callable',
            code='x = 42',
            project=self.project,
            created_by=self.user,
            is_active=True,
        )
        ApiCustomFunction.objects.create(
            name='has_callable',
            code='def add(a, b):\n    return a + b',
            project=self.project,
            created_by=self.user,
            is_active=True,
        )
        from api_interfaces.runner import load_custom_functions
        functions = load_custom_functions(self.project.pk)
        self.assertIn('add', functions)
        self.assertNotIn('x', functions)

    def test_loaded_function_callable(self):
        """加载的函数可以被正常调用"""
        ApiCustomFunction.objects.create(
            name='multiply',
            code='def multiply(a, b):\n    return a * b',
            project=self.project,
            created_by=self.user,
            is_active=True,
        )
        from api_interfaces.runner import load_custom_functions
        functions = load_custom_functions(self.project.pk)
        self.assertEqual(functions['multiply'](3, 4), 12)


class ApiCustomFunctionPaginationTest(TestCase):
    """ApiCustomFunction 分页测试"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='pageuser', password='testpass')
        self.project = Project.objects.create(name='Page Project', creator=self.user)
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        _grant_all_function_perms(self.user)
        self.client.force_authenticate(user=self.user)
        self.base_url = f'/api/projects/{self.project.pk}/api-functions/'
        # Create more than default page size functions
        for i in range(15):
            ApiCustomFunction.objects.create(
                name=f'func_{i:03d}',
                code=f'def func_{i:03d}():\n    return {i}',
                project=self.project,
                created_by=self.user,
            )

    def test_list_pagination_response_format(self):
        """验证分页响应包含 count/next/previous/results"""
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('results', response.data)
        self.assertEqual(response.data['count'], 15)

    def test_list_pagination_page_size(self):
        """验证自定义 page_size 参数"""
        response = self.client.get(f'{self.base_url}?page_size=5')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 5)

    def test_list_pagination_page_navigation(self):
        """验证分页导航"""
        response = self.client.get(f'{self.base_url}?page_size=5&page=2')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 5)
