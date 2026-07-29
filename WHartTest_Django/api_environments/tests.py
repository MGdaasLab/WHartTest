import json

from django.contrib.auth.models import Permission, User
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from projects.models import Project, ProjectMember
from api_database_configs.models import ApiDatabaseConfig
from .models import ApiEnvironment, ApiEnvironmentVariable, ApiGlobalRequestHeader


def _grant_api_env_permissions(user):
    """Grant all api_environments / api_database_configs model permissions to a user."""
    perms = Permission.objects.filter(
        content_type__app_label__in=[
            'api_environments',
            'api_database_configs',
        ],
    )
    user.user_permissions.add(*perms)


class ApiEnvironmentModelTest(TestCase):
    """ApiEnvironment 模型测试"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)

    def test_create_environment(self):
        env = ApiEnvironment.objects.create(
            name='Staging',
            base_url='https://staging.example.com',
            project=self.project,
            created_by=self.user,
        )
        self.assertEqual(env.name, 'Staging')
        self.assertFalse(env.verify_ssl)
        self.assertTrue(env.is_active)

    def test_str_representation(self):
        env = ApiEnvironment.objects.create(
            name='Dev',
            base_url='http://localhost:8000',
            project=self.project,
            created_by=self.user,
        )
        self.assertEqual(str(env), 'Test Project-Dev')

    def test_unique_together_name_project(self):
        ApiEnvironment.objects.create(
            name='Duplicate',
            base_url='http://example.com',
            project=self.project,
            created_by=self.user,
        )
        with self.assertRaises(Exception):
            ApiEnvironment.objects.create(
                name='Duplicate',
                base_url='http://example2.com',
                project=self.project,
                created_by=self.user,
            )

    def test_clean_parent_different_project(self):
        other_project = Project.objects.create(name='Other', creator=self.user)
        parent = ApiEnvironment.objects.create(
            name='Other Env',
            base_url='http://other.example.com',
            project=other_project,
            created_by=self.user,
        )
        env = ApiEnvironment(
            name='Child',
            base_url='http://child.example.com',
            project=self.project,
            parent=parent,
            created_by=self.user,
        )
        with self.assertRaises(ValidationError):
            env.clean()

    def test_clean_self_parent(self):
        env = ApiEnvironment.objects.create(
            name='Self Parent',
            base_url='http://example.com',
            project=self.project,
            created_by=self.user,
        )
        env.parent = env
        with self.assertRaises(ValidationError):
            env.clean()

    def test_clean_circular_inheritance(self):
        env_a = ApiEnvironment.objects.create(
            name='A', base_url='http://a.com', project=self.project, created_by=self.user,
        )
        env_b = ApiEnvironment.objects.create(
            name='B', base_url='http://b.com', project=self.project, parent=env_a, created_by=self.user,
        )
        env_a.parent = env_b
        with self.assertRaises(ValidationError):
            env_a.clean()

    def test_clean_db_config_different_project(self):
        other_project = Project.objects.create(name='Other', creator=self.user)
        db_config = ApiDatabaseConfig.objects.create(
            name='Other DB', project=other_project, db_type='mysql',
            host='localhost', port=3306, username='root',
            password='secret', database='db', created_by=self.user,
        )
        env = ApiEnvironment(
            name='Bad Env',
            base_url='http://example.com',
            project=self.project,
            database_config=db_config,
            created_by=self.user,
        )
        with self.assertRaises(ValidationError):
            env.clean()

    def test_clean_valid_environment(self):
        parent = ApiEnvironment.objects.create(
            name='Parent', base_url='http://parent.com',
            project=self.project, created_by=self.user,
        )
        db_config = ApiDatabaseConfig.objects.create(
            name='Same Project DB', project=self.project, db_type='mysql',
            host='localhost', port=3306, username='root',
            password='secret', database='db', created_by=self.user,
        )
        env = ApiEnvironment(
            name='Valid',
            base_url='http://valid.com',
            project=self.project,
            parent=parent,
            database_config=db_config,
            created_by=self.user,
        )
        env.clean()  # Should not raise

    def test_get_all_variables(self):
        env = ApiEnvironment.objects.create(
            name='Env', base_url='http://example.com',
            project=self.project, created_by=self.user,
        )
        ApiEnvironmentVariable.objects.create(
            environment=env, name='token', value='abc123', type='string',
        )
        ApiEnvironmentVariable.objects.create(
            environment=env, name='port', value='8080', type='integer',
        )
        variables = env.get_all_variables()
        self.assertEqual(variables['token'], 'abc123')
        self.assertEqual(variables['port'], 8080)

    def test_get_all_variables_with_inheritance(self):
        parent_env = ApiEnvironment.objects.create(
            name='Parent', base_url='http://parent.com',
            project=self.project, created_by=self.user,
        )
        ApiEnvironmentVariable.objects.create(
            environment=parent_env, name='shared_var', value='parent_val', type='string',
        )
        child_env = ApiEnvironment.objects.create(
            name='Child', base_url='http://child.com',
            project=self.project, parent=parent_env, created_by=self.user,
        )
        ApiEnvironmentVariable.objects.create(
            environment=child_env, name='shared_var', value='child_val', type='string',
        )
        variables = child_env.get_all_variables()
        # Child overrides parent
        self.assertEqual(variables['shared_var'], 'child_val')

    def test_get_all_variables_three_levels(self):
        grandparent = ApiEnvironment.objects.create(
            name='Grandparent', base_url='http://gp.com',
            project=self.project, created_by=self.user,
        )
        ApiEnvironmentVariable.objects.create(
            environment=grandparent, name='level', value='gp', type='string',
        )
        ApiEnvironmentVariable.objects.create(
            environment=grandparent, name='gp_only', value='gp_val', type='string',
        )
        parent = ApiEnvironment.objects.create(
            name='Parent', base_url='http://parent.com',
            project=self.project, parent=grandparent, created_by=self.user,
        )
        ApiEnvironmentVariable.objects.create(
            environment=parent, name='level', value='parent', type='string',
        )
        child = ApiEnvironment.objects.create(
            name='Child', base_url='http://child.com',
            project=self.project, parent=parent, created_by=self.user,
        )
        ApiEnvironmentVariable.objects.create(
            environment=child, name='child_only', value='child_val', type='string',
        )
        variables = child.get_all_variables()
        self.assertEqual(variables['level'], 'parent')  # parent overrides grandparent
        self.assertEqual(variables['gp_only'], 'gp_val')  # inherited from grandparent
        self.assertEqual(variables['child_only'], 'child_val')

    def test_get_all_variables_no_parent(self):
        env = ApiEnvironment.objects.create(
            name='Solo', base_url='http://solo.com',
            project=self.project, created_by=self.user,
        )
        ApiEnvironmentVariable.objects.create(
            environment=env, name='key', value='val', type='string',
        )
        variables = env.get_all_variables()
        self.assertEqual(variables, {'key': 'val'})

    def test_get_database_config(self):
        db_config = ApiDatabaseConfig.objects.create(
            name='DB', project=self.project, db_type='mysql',
            host='localhost', port=3306, username='root',
            password='secret', database='db', created_by=self.user,
        )
        env = ApiEnvironment.objects.create(
            name='Env', base_url='http://example.com',
            project=self.project, database_config=db_config, created_by=self.user,
        )
        self.assertEqual(env.get_database_config(), db_config)

    def test_get_database_config_from_parent(self):
        db_config = ApiDatabaseConfig.objects.create(
            name='DB', project=self.project, db_type='mysql',
            host='localhost', port=3306, username='root',
            password='secret', database='db', created_by=self.user,
        )
        parent = ApiEnvironment.objects.create(
            name='Parent', base_url='http://parent.com',
            project=self.project, database_config=db_config, created_by=self.user,
        )
        child = ApiEnvironment.objects.create(
            name='Child', base_url='http://child.com',
            project=self.project, parent=parent, created_by=self.user,
        )
        self.assertEqual(child.get_database_config(), db_config)

    def test_get_database_config_none(self):
        env = ApiEnvironment.objects.create(
            name='No DB', base_url='http://example.com',
            project=self.project, created_by=self.user,
        )
        self.assertIsNone(env.get_database_config())

    def test_ordering(self):
        e1 = ApiEnvironment.objects.create(
            name='First', base_url='http://first.com',
            project=self.project, created_by=self.user,
        )
        e2 = ApiEnvironment.objects.create(
            name='Second', base_url='http://second.com',
            project=self.project, created_by=self.user,
        )
        envs = list(ApiEnvironment.objects.all())
        self.assertEqual(envs[0], e2)  # newest first
        self.assertEqual(envs[1], e1)

    def test_cascade_delete_project(self):
        ApiEnvironment.objects.create(
            name='Env', base_url='http://example.com',
            project=self.project, created_by=self.user,
        )
        self.project.delete()
        self.assertEqual(ApiEnvironment.objects.count(), 0)

    def test_set_null_on_user_delete(self):
        env = ApiEnvironment.objects.create(
            name='Orphan', base_url='http://example.com',
            project=self.project, created_by=self.user,
        )
        self.user.delete()
        env.refresh_from_db()
        self.assertIsNone(env.created_by)


class ApiEnvironmentVariableModelTest(TestCase):
    """ApiEnvironmentVariable 模型测试"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)
        self.env = ApiEnvironment.objects.create(
            name='Test Env', base_url='http://example.com',
            project=self.project, created_by=self.user,
        )

    def test_create_variable(self):
        var = ApiEnvironmentVariable.objects.create(
            environment=self.env, name='api_key', value='secret123', type='string',
        )
        self.assertEqual(var.name, 'api_key')
        self.assertFalse(var.is_sensitive)

    def test_str_representation(self):
        var = ApiEnvironmentVariable.objects.create(
            environment=self.env, name='token', value='abc', type='string',
        )
        self.assertEqual(str(var), 'Test Env-token')

    def test_unique_together(self):
        ApiEnvironmentVariable.objects.create(
            environment=self.env, name='dup_var', value='v1', type='string',
        )
        with self.assertRaises(Exception):
            ApiEnvironmentVariable.objects.create(
                environment=self.env, name='dup_var', value='v2', type='string',
            )

    def test_get_typed_value_string(self):
        var = ApiEnvironmentVariable.objects.create(
            environment=self.env, name='s', value='hello', type='string',
        )
        self.assertEqual(var.get_typed_value(), 'hello')

    def test_get_typed_value_integer(self):
        var = ApiEnvironmentVariable.objects.create(
            environment=self.env, name='i', value='42', type='integer',
        )
        self.assertEqual(var.get_typed_value(), 42)

    def test_get_typed_value_float(self):
        var = ApiEnvironmentVariable.objects.create(
            environment=self.env, name='f', value='3.14', type='float',
        )
        self.assertAlmostEqual(var.get_typed_value(), 3.14)

    def test_get_typed_value_boolean(self):
        var = ApiEnvironmentVariable.objects.create(
            environment=self.env, name='b', value='true', type='boolean',
        )
        self.assertTrue(var.get_typed_value())

    def test_get_typed_value_boolean_false(self):
        var = ApiEnvironmentVariable.objects.create(
            environment=self.env, name='bf', value='false', type='boolean',
        )
        self.assertFalse(var.get_typed_value())

    def test_get_typed_value_json(self):
        var = ApiEnvironmentVariable.objects.create(
            environment=self.env, name='j', value='{"key": "val"}', type='json',
        )
        self.assertEqual(var.get_typed_value(), {'key': 'val'})

    def test_get_typed_value_list(self):
        var = ApiEnvironmentVariable.objects.create(
            environment=self.env, name='l', value='[1, 2, 3]', type='list',
        )
        self.assertEqual(var.get_typed_value(), [1, 2, 3])

    def test_get_typed_value_dict(self):
        var = ApiEnvironmentVariable.objects.create(
            environment=self.env, name='d', value='{"a": 1}', type='dict',
        )
        self.assertEqual(var.get_typed_value(), {'a': 1})

    def test_get_typed_value_invalid_integer_fallback(self):
        var = ApiEnvironmentVariable(
            environment=self.env, name='bad', value='not_int', type='integer',
        )
        # get_typed_value returns raw value on conversion error
        self.assertEqual(var.get_typed_value(), 'not_int')

    def test_clean_invalid_integer(self):
        var = ApiEnvironmentVariable(
            environment=self.env, name='bad_int', value='notanumber', type='integer',
        )
        with self.assertRaises(ValidationError):
            var.clean()

    def test_clean_invalid_boolean(self):
        var = ApiEnvironmentVariable(
            environment=self.env, name='bad_bool', value='maybe', type='boolean',
        )
        with self.assertRaises(ValidationError):
            var.clean()

    def test_clean_invalid_json(self):
        var = ApiEnvironmentVariable(
            environment=self.env, name='bad_json', value='{not json', type='json',
        )
        with self.assertRaises(ValidationError):
            var.clean()

    def test_sensitive_field(self):
        var = ApiEnvironmentVariable.objects.create(
            environment=self.env, name='secret', value='real_secret',
            type='string', is_sensitive=True,
        )
        self.assertTrue(var.is_sensitive)
        self.assertEqual(var.value, 'real_secret')  # raw value is still stored

    def test_ordering(self):
        v_b = ApiEnvironmentVariable.objects.create(
            environment=self.env, name='beta', value='b', type='string',
        )
        v_a = ApiEnvironmentVariable.objects.create(
            environment=self.env, name='alpha', value='a', type='string',
        )
        variables = list(ApiEnvironmentVariable.objects.filter(environment=self.env))
        self.assertEqual(variables[0], v_a)  # ordered by name
        self.assertEqual(variables[1], v_b)


class ApiGlobalRequestHeaderModelTest(TestCase):
    """ApiGlobalRequestHeader 模型测试"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)

    def test_create_header(self):
        header = ApiGlobalRequestHeader.objects.create(
            name='Authorization',
            value='Bearer token',
            project=self.project,
            created_by=self.user,
        )
        self.assertEqual(header.name, 'Authorization')
        self.assertTrue(header.is_enabled)

    def test_str_representation(self):
        header = ApiGlobalRequestHeader.objects.create(
            name='X-Custom',
            value='custom_val',
            project=self.project,
            created_by=self.user,
        )
        self.assertEqual(str(header), 'Test Project-X-Custom')

    def test_unique_together(self):
        ApiGlobalRequestHeader.objects.create(
            name='Duplicate',
            value='v1',
            project=self.project,
            created_by=self.user,
        )
        with self.assertRaises(Exception):
            ApiGlobalRequestHeader.objects.create(
                name='Duplicate',
                value='v2',
                project=self.project,
                created_by=self.user,
            )


class ApiEnvironmentAPITest(TestCase):
    """ApiEnvironment API 测试"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='apiuser', password='testpass')
        _grant_api_env_permissions(self.user)
        self.project = Project.objects.create(name='API Project', creator=self.user)
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        self.client.force_authenticate(user=self.user)
        self.base_url = f'/api/projects/{self.project.pk}/api-environments/'
        self.var_url = f'/api/projects/{self.project.pk}/api-environment-variables/'
        self.header_url = f'/api/projects/{self.project.pk}/api-global-headers/'

    # --- Environment CRUD ---

    def test_list_environments(self):
        ApiEnvironment.objects.create(
            name='Env1', base_url='http://env1.com',
            project=self.project, created_by=self.user,
        )
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_environment(self):
        data = {
            'name': 'New Env',
            'base_url': 'https://new.example.com',
            'project': self.project.pk,
        }
        response = self.client.post(self.base_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        env = ApiEnvironment.objects.get(name='New Env')
        self.assertEqual(env.project, self.project)
        self.assertEqual(env.created_by, self.user)

    def test_retrieve_environment_with_variables(self):
        env = ApiEnvironment.objects.create(
            name='Detail Env', base_url='http://detail.com',
            project=self.project, created_by=self.user,
        )
        ApiEnvironmentVariable.objects.create(
            environment=env, name='var1', value='val1', type='string',
        )
        response = self.client.get(f'{self.base_url}{env.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['variables']), 1)

    def test_retrieve_parent_info(self):
        parent = ApiEnvironment.objects.create(
            name='Parent', base_url='http://parent.com',
            project=self.project, created_by=self.user,
        )
        child = ApiEnvironment.objects.create(
            name='Child', base_url='http://child.com',
            project=self.project, parent=parent, created_by=self.user,
        )
        response = self.client.get(f'{self.base_url}{child.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data['parent_info'])
        self.assertEqual(response.data['parent_info']['name'], 'Parent')

    def test_retrieve_database_config_info(self):
        db_config = ApiDatabaseConfig.objects.create(
            name='Test DB', project=self.project, db_type='mysql',
            host='localhost', port=3306, username='root',
            password='secret', database='db', created_by=self.user,
        )
        env = ApiEnvironment.objects.create(
            name='DB Env', base_url='http://db.com',
            project=self.project, database_config=db_config, created_by=self.user,
        )
        response = self.client.get(f'{self.base_url}{env.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data['database_config_info'])
        self.assertEqual(response.data['database_config_info']['name'], 'Test DB')

    def test_sensitive_variable_masked(self):
        env = ApiEnvironment.objects.create(
            name='Sensitive Env', base_url='http://s.com',
            project=self.project, created_by=self.user,
        )
        ApiEnvironmentVariable.objects.create(
            environment=env, name='secret', value='real_secret',
            type='string', is_sensitive=True,
        )
        response = self.client.get(f'{self.base_url}{env.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        var_data = response.data['variables'][0]
        self.assertEqual(var_data['value'], '******')

    def test_update_environment(self):
        env = ApiEnvironment.objects.create(
            name='Old Env', base_url='http://old.com',
            project=self.project, created_by=self.user,
        )
        response = self.client.patch(
            f'{self.base_url}{env.pk}/',
            {'base_url': 'http://new.example.com'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        env.refresh_from_db()
        self.assertEqual(env.base_url, 'http://new.example.com')

    def test_delete_environment(self):
        env = ApiEnvironment.objects.create(
            name='To Delete', base_url='http://delete.com',
            project=self.project, created_by=self.user,
        )
        response = self.client.delete(f'{self.base_url}{env.pk}/')
        self.assertIn(response.status_code, (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT))

    # --- Clone action ---

    def test_clone_environment(self):
        env = ApiEnvironment.objects.create(
            name='Original', base_url='http://original.com',
            project=self.project, created_by=self.user,
        )
        ApiEnvironmentVariable.objects.create(
            environment=env, name='var1', value='val1', type='string',
        )
        response = self.client.post(
            f'{self.base_url}{env.pk}/clone/',
            {'name': 'Cloned Env'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Cloned Env')
        cloned = ApiEnvironment.objects.get(name='Cloned Env')
        self.assertEqual(cloned.api_variables.count(), 1)

    def test_clone_default_name(self):
        env = ApiEnvironment.objects.create(
            name='Original', base_url='http://original.com',
            project=self.project, created_by=self.user,
        )
        response = self.client.post(
            f'{self.base_url}{env.pk}/clone/',
            {},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Original_copy')

    def test_clone_duplicate_name(self):
        env = ApiEnvironment.objects.create(
            name='Original', base_url='http://original.com',
            project=self.project, created_by=self.user,
        )
        ApiEnvironment.objects.create(
            name='Exists', base_url='http://exists.com',
            project=self.project, created_by=self.user,
        )
        response = self.client.post(
            f'{self.base_url}{env.pk}/clone/',
            {'name': 'Exists'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Variable CRUD ---

    def test_list_variables(self):
        env = ApiEnvironment.objects.create(
            name='Env', base_url='http://env.com',
            project=self.project, created_by=self.user,
        )
        ApiEnvironmentVariable.objects.create(
            environment=env, name='var1', value='val1', type='string',
        )
        response = self.client.get(self.var_url, {'environment_id': env.pk})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_variable(self):
        env = ApiEnvironment.objects.create(
            name='Env', base_url='http://env.com',
            project=self.project, created_by=self.user,
        )
        data = {
            'environment': env.pk,
            'name': 'new_var',
            'value': 'new_val',
            'type': 'string',
        }
        response = self.client.post(self.var_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_update_variable(self):
        env = ApiEnvironment.objects.create(
            name='Env', base_url='http://env.com',
            project=self.project, created_by=self.user,
        )
        var = ApiEnvironmentVariable.objects.create(
            environment=env, name='var1', value='old_val', type='string',
        )
        response = self.client.patch(
            f'{self.var_url}{var.pk}/',
            {'value': 'new_val'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        var.refresh_from_db()
        self.assertEqual(var.value, 'new_val')

    def test_delete_variable(self):
        env = ApiEnvironment.objects.create(
            name='Env', base_url='http://env.com',
            project=self.project, created_by=self.user,
        )
        var = ApiEnvironmentVariable.objects.create(
            environment=env, name='var1', value='val1', type='string',
        )
        response = self.client.delete(f'{self.var_url}{var.pk}/')
        self.assertIn(response.status_code, (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT))

    # --- Variable batch actions ---

    def test_batch_create_variables(self):
        env = ApiEnvironment.objects.create(
            name='Env', base_url='http://env.com',
            project=self.project, created_by=self.user,
        )
        data = {
            'environment_id': env.pk,
            'variables': [
                {'name': 'var1', 'value': 'val1', 'type': 'string', 'environment': env.pk},
                {'name': 'var2', 'value': '42', 'type': 'integer', 'environment': env.pk},
            ],
        }
        response = self.client.post(
            f'{self.var_url}batch_create/', data, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(env.api_variables.count(), 2)

    def test_batch_create_missing_params(self):
        response = self.client.post(
            f'{self.var_url}batch_create/', {}, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_batch_update_variables(self):
        env = ApiEnvironment.objects.create(
            name='Env', base_url='http://env.com',
            project=self.project, created_by=self.user,
        )
        var1 = ApiEnvironmentVariable.objects.create(
            environment=env, name='var1', value='old1', type='string',
        )
        var2 = ApiEnvironmentVariable.objects.create(
            environment=env, name='var2', value='old2', type='string',
        )
        data = {
            'variables': [
                {'id': var1.pk, 'value': 'new1'},
                {'id': var2.pk, 'value': 'new2'},
            ],
        }
        response = self.client.post(
            f'{self.var_url}batch_update/', data, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        var1.refresh_from_db()
        var2.refresh_from_db()
        self.assertEqual(var1.value, 'new1')
        self.assertEqual(var2.value, 'new2')

    def test_batch_update_empty(self):
        response = self.client.post(
            f'{self.var_url}batch_update/', {'variables': []}, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- GlobalRequestHeader CRUD ---

    def test_list_headers(self):
        ApiGlobalRequestHeader.objects.create(
            name='Authorization', value='Bearer token',
            project=self.project, created_by=self.user,
        )
        response = self.client.get(self.header_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_header(self):
        data = {
            'name': 'X-Custom',
            'value': 'custom_value',
            'project': self.project.pk,
        }
        response = self.client.post(self.header_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        header = ApiGlobalRequestHeader.objects.get(name='X-Custom')
        self.assertEqual(header.project, self.project)
        self.assertEqual(header.created_by, self.user)

    def test_update_header(self):
        header = ApiGlobalRequestHeader.objects.create(
            name='X-Custom', value='old_val',
            project=self.project, created_by=self.user,
        )
        response = self.client.patch(
            f'{self.header_url}{header.pk}/',
            {'value': 'new_val'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        header.refresh_from_db()
        self.assertEqual(header.value, 'new_val')

    def test_delete_header(self):
        header = ApiGlobalRequestHeader.objects.create(
            name='X-Custom', value='val',
            project=self.project, created_by=self.user,
        )
        response = self.client.delete(f'{self.header_url}{header.pk}/')
        self.assertIn(response.status_code, (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT))

    # --- Auth ---

    def test_unauthenticated_access(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ApiEnvironmentPermissionTest(TestCase):
    """ApiEnvironment 权限测试"""

    def setUp(self):
        self.client = APIClient()
        self.user_a = User.objects.create_user(username='user_a', password='testpass')
        _grant_api_env_permissions(self.user_a)
        self.project_a = Project.objects.create(name='Project A', creator=self.user_a)
        ProjectMember.objects.create(project=self.project_a, user=self.user_a, role='member')

        self.user_b = User.objects.create_user(username='user_b', password='testpass')
        _grant_api_env_permissions(self.user_b)
        self.project_b = Project.objects.create(name='Project B', creator=self.user_b)
        ProjectMember.objects.create(project=self.project_b, user=self.user_b, role='member')

        self.outsider = User.objects.create_user(username='outsider', password='testpass')
        _grant_api_env_permissions(self.outsider)
        self.superuser = User.objects.create_superuser(username='admin', password='adminpass')

    def test_non_member_denied(self):
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(f'/api/projects/{self.project_a.pk}/api-environments/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_allowed(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get(f'/api/projects/{self.project_a.pk}/api-environments/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_project_isolation_environment(self):
        """User A cannot see environments from Project B."""
        ApiEnvironment.objects.create(
            name='B Env', base_url='http://b.com',
            project=self.project_b, created_by=self.user_b,
        )
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f'/api/projects/{self.project_b.pk}/api-environments/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_project_isolation_variables(self):
        """User A cannot list variables from Project B."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f'/api/projects/{self.project_b.pk}/api-environment-variables/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_project_isolation_headers(self):
        """User A cannot list headers from Project B."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f'/api/projects/{self.project_b.pk}/api-global-headers/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_denied(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(f'/api/projects/{self.project_a.pk}/api-environments/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_member_can_access_own_project(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f'/api/projects/{self.project_a.pk}/api-environments/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_superuser_can_access_any_project(self):
        self.client.force_authenticate(user=self.superuser)
        for project in [self.project_a, self.project_b]:
            response = self.client.get(f'/api/projects/{project.pk}/api-environments/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)


class ApiEnvironmentIsolationTest(TestCase):
    """环境模块项目隔离测试"""

    def setUp(self):
        self.client = APIClient()
        self.user_a = User.objects.create_user(username='user_a', password='testpass')
        _grant_api_env_permissions(self.user_a)
        self.project_a = Project.objects.create(name='Project A', creator=self.user_a)
        ProjectMember.objects.create(project=self.project_a, user=self.user_a, role='admin')

        self.user_b = User.objects.create_user(username='user_b', password='testpass')
        _grant_api_env_permissions(self.user_b)
        self.project_b = Project.objects.create(name='Project B', creator=self.user_b)
        ProjectMember.objects.create(project=self.project_b, user=self.user_b, role='admin')

        self.env_a = ApiEnvironment.objects.create(
            name='Env A', base_url='http://a.com',
            project=self.project_a, created_by=self.user_a,
        )
        self.env_b = ApiEnvironment.objects.create(
            name='Env B', base_url='http://b.com',
            project=self.project_b, created_by=self.user_b,
        )
        self.var_b = ApiEnvironmentVariable.objects.create(
            environment=self.env_b, name='secret', value='val', type='string',
        )

    def test_clone_always_uses_url_project(self):
        """clone 操作忽略请求体中的 project_id，始终使用 URL 中的 project_pk"""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.post(
            f'/api/projects/{self.project_a.pk}/api-environments/{self.env_a.pk}/clone/',
            {'name': 'Cloned', 'project_id': self.project_b.pk},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cloned = ApiEnvironment.objects.get(name='Cloned')
        self.assertEqual(cloned.project, self.project_a)

    def test_batch_update_cross_project_variable_denied(self):
        """batch_update 不能修改其他项目的变量"""
        self.client.force_authenticate(user=self.user_a)
        data = {
            'variables': [
                {'id': self.var_b.pk, 'value': 'hijacked'},
            ],
        }
        response = self.client.post(
            f'/api/projects/{self.project_a.pk}/api-environment-variables/batch_update/',
            data, format='json',
        )
        # Should get 404 because var_b belongs to project_b
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ApiEnvironmentModelLayerTest(TestCase):
    """ApiEnvironment 模型层补充测试"""

    def setUp(self):
        from api_environments.models import ApiEnvironment, ApiEnvironmentVariable
        self.user = User.objects.create_user(username='envmodel', password='testpass')
        self.project = Project.objects.create(name='EnvModel Project', creator=self.user)
        self.env = ApiEnvironment.objects.create(
            name='Test Env', base_url='http://test.com',
            project=self.project, created_by=self.user,
        )

    def test_get_all_variables(self):
        """环境变量聚合正确"""
        from api_environments.models import ApiEnvironmentVariable
        ApiEnvironmentVariable.objects.create(
            environment=self.env, name='host', value='localhost', type='string',
        )
        ApiEnvironmentVariable.objects.create(
            environment=self.env, name='port', value='8080', type='integer',
        )
        variables = self.env.get_all_variables()
        self.assertEqual(variables['host'], 'localhost')
        self.assertEqual(variables['port'], 8080)  # typed value

    def test_get_all_variables_with_parent_inheritance(self):
        """子环境继承父环境变量"""
        from api_environments.models import ApiEnvironment, ApiEnvironmentVariable
        parent = self.env
        ApiEnvironmentVariable.objects.create(
            environment=parent, name='shared_var', value='parent_val', type='string',
        )
        child = ApiEnvironment.objects.create(
            name='Child Env', base_url='http://child.com',
            project=self.project, parent=parent, created_by=self.user,
        )
        ApiEnvironmentVariable.objects.create(
            environment=child, name='child_only', value='child_val', type='string',
        )
        variables = child.get_all_variables()
        self.assertEqual(variables['shared_var'], 'parent_val')
        self.assertEqual(variables['child_only'], 'child_val')

    def test_child_overrides_parent_variable(self):
        """子环境变量覆盖父环境同名变量"""
        from api_environments.models import ApiEnvironment, ApiEnvironmentVariable
        parent = self.env
        ApiEnvironmentVariable.objects.create(
            environment=parent, name='var', value='parent', type='string',
        )
        child = ApiEnvironment.objects.create(
            name='Override Child', base_url='http://child.com',
            project=self.project, parent=parent, created_by=self.user,
        )
        ApiEnvironmentVariable.objects.create(
            environment=child, name='var', value='child', type='string',
        )
        variables = child.get_all_variables()
        self.assertEqual(variables['var'], 'child')

    def test_environment_cascade_delete_variables(self):
        """删除环境级联删除变量"""
        from api_environments.models import ApiEnvironmentVariable
        ApiEnvironmentVariable.objects.create(
            environment=self.env, name='v1', value='1', type='string',
        )
        self.env.delete()
        self.assertEqual(
            ApiEnvironmentVariable.objects.filter(name='v1').count(), 0,
        )

    def test_variable_get_typed_value_boolean(self):
        """boolean 类型变量正确转换"""
        from api_environments.models import ApiEnvironmentVariable
        var = ApiEnvironmentVariable.objects.create(
            environment=self.env, name='flag', value='true', type='boolean',
        )
        self.assertIs(var.get_typed_value(), True)

    def test_variable_get_typed_value_json(self):
        """json 类型变量正确解析"""
        from api_environments.models import ApiEnvironmentVariable
        var = ApiEnvironmentVariable.objects.create(
            environment=self.env, name='data',
            value='{"key": "value"}', type='json',
        )
        self.assertEqual(var.get_typed_value(), {'key': 'value'})

    def test_variable_get_typed_value_float(self):
        """float 类型变量正确转换"""
        from api_environments.models import ApiEnvironmentVariable
        var = ApiEnvironmentVariable.objects.create(
            environment=self.env, name='rate', value='3.14', type='float',
        )
        self.assertAlmostEqual(var.get_typed_value(), 3.14)

    def test_get_database_config_walks_parent(self):
        """get_database_config 沿父链查找"""
        from api_environments.models import ApiEnvironment
        from api_database_configs.models import ApiDatabaseConfig
        db_config = ApiDatabaseConfig.objects.create(
            name='DB', project=self.project, db_type='mysql',
            host='h', port=3306, username='u', password='p',
            database='db', created_by=self.user,
        )
        self.env.database_config = db_config
        self.env.save()
        child = ApiEnvironment.objects.create(
            name='Child', base_url='http://child.com',
            project=self.project, parent=self.env,
            created_by=self.user,
        )
        self.assertEqual(child.get_database_config(), db_config)

    def test_clean_cross_project_parent_rejected(self):
        """跨项目的 parent 被 clean() 拒绝"""
        from api_environments.models import ApiEnvironment
        from django.core.exceptions import ValidationError
        other_project = Project.objects.create(name='Other', creator=self.user)
        other_env = ApiEnvironment.objects.create(
            name='Other Env', base_url='http://other.com',
            project=other_project, created_by=self.user,
        )
        self.env.parent = other_env
        with self.assertRaises(ValidationError):
            self.env.clean()

    def test_clean_circular_inheritance_rejected(self):
        """循环继承被 clean() 拒绝"""
        from api_environments.models import ApiEnvironment
        from django.core.exceptions import ValidationError
        self.env.parent = self.env
        with self.assertRaises(ValidationError):
            self.env.clean()
