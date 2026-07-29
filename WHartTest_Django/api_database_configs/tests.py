from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.contrib.auth.models import Permission, User
from rest_framework.test import APIClient
from rest_framework import status

from projects.models import Project, ProjectMember
from .models import ApiDatabaseConfig


def _grant_db_config_permissions(user):
    """Grant all api_database_configs model permissions to a user."""
    perms = Permission.objects.filter(
        content_type__app_label='api_database_configs',
    )
    user.user_permissions.add(*perms)


class ApiDatabaseConfigModelTest(TestCase):
    """ApiDatabaseConfig 模型测试"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project = Project.objects.create(name='Test Project', creator=self.user)

    def test_create_mysql_config(self):
        config = ApiDatabaseConfig.objects.create(
            name='Test MySQL',
            project=self.project,
            db_type='mysql',
            host='localhost',
            port=3306,
            username='root',
            password='secret',
            database='testdb',
            created_by=self.user,
        )
        self.assertEqual(config.name, 'Test MySQL')
        self.assertEqual(config.db_type, 'mysql')
        self.assertTrue(config.is_active)
        self.assertEqual(config.charset, 'utf8mb4')

    def test_str_representation(self):
        config = ApiDatabaseConfig.objects.create(
            name='MyDB',
            project=self.project,
            db_type='mysql',
            host='localhost',
            port=3306,
            username='root',
            password='secret',
            database='testdb',
            created_by=self.user,
        )
        self.assertEqual(str(config), 'MyDB (Test Project)')

    def test_connection_string_mysql(self):
        config = ApiDatabaseConfig.objects.create(
            name='MySQL',
            project=self.project,
            db_type='mysql',
            host='db.example.com',
            port=3306,
            username='user',
            password='pass',
            database='mydb',
            charset='utf8mb4',
            created_by=self.user,
        )
        self.assertIn('mysql+pymysql://', config.connection_string)
        self.assertIn('user:pass@db.example.com:3306/mydb', config.connection_string)

    def test_connection_string_postgresql(self):
        config = ApiDatabaseConfig.objects.create(
            name='PG',
            project=self.project,
            db_type='postgresql',
            host='pg.example.com',
            port=5432,
            username='pguser',
            password='pgpass',
            database='pgdb',
            created_by=self.user,
        )
        self.assertIn('postgresql://', config.connection_string)
        self.assertIn('pguser:pgpass@pg.example.com:5432/pgdb', config.connection_string)

    def test_connection_string_sqlite(self):
        config = ApiDatabaseConfig.objects.create(
            name='SQLite',
            project=self.project,
            db_type='sqlite',
            host='',
            port=0,
            username='',
            password='',
            database='/tmp/test.db',
            created_by=self.user,
        )
        self.assertEqual(config.connection_string, 'sqlite:////tmp/test.db')

    def test_connection_string_oracle(self):
        config = ApiDatabaseConfig.objects.create(
            name='Oracle',
            project=self.project,
            db_type='oracle',
            host='oracle.example.com',
            port=1521,
            username='orauser',
            password='orapass',
            database='orcl',
            created_by=self.user,
        )
        self.assertIn('oracle://', config.connection_string)

    def test_connection_string_sqlserver(self):
        config = ApiDatabaseConfig.objects.create(
            name='MSSQL',
            project=self.project,
            db_type='sqlserver',
            host='mssql.example.com',
            port=1433,
            username='sa',
            password='sapass',
            database='msdb',
            created_by=self.user,
        )
        self.assertIn('mssql+pymssql://', config.connection_string)

    def test_get_by_key(self):
        ApiDatabaseConfig.objects.create(
            name='active_db',
            project=self.project,
            db_type='mysql',
            host='localhost',
            port=3306,
            username='root',
            password='secret',
            database='testdb',
            is_active=True,
            created_by=self.user,
        )
        result = ApiDatabaseConfig.get_by_key('active_db')
        self.assertIsNotNone(result)
        self.assertEqual(result.name, 'active_db')

    def test_get_by_key_inactive(self):
        ApiDatabaseConfig.objects.create(
            name='inactive_db',
            project=self.project,
            db_type='mysql',
            host='localhost',
            port=3306,
            username='root',
            password='secret',
            database='testdb',
            is_active=False,
            created_by=self.user,
        )
        result = ApiDatabaseConfig.get_by_key('inactive_db')
        self.assertIsNone(result)

    def test_get_by_key_empty(self):
        self.assertIsNone(ApiDatabaseConfig.get_by_key(''))
        self.assertIsNone(ApiDatabaseConfig.get_by_key(None))

    def test_cascade_delete_project(self):
        ApiDatabaseConfig.objects.create(
            name='To Delete',
            project=self.project,
            db_type='mysql',
            host='localhost',
            port=3306,
            username='root',
            password='secret',
            database='testdb',
            created_by=self.user,
        )
        self.project.delete()
        self.assertEqual(ApiDatabaseConfig.objects.count(), 0)

    def test_set_null_on_user_delete(self):
        config = ApiDatabaseConfig.objects.create(
            name='Orphan',
            project=self.project,
            db_type='mysql',
            host='localhost',
            port=3306,
            username='root',
            password='secret',
            database='testdb',
            created_by=self.user,
        )
        self.user.delete()
        config.refresh_from_db()
        self.assertIsNone(config.created_by)

    def test_ordering(self):
        c1 = ApiDatabaseConfig.objects.create(
            name='First', project=self.project, db_type='mysql',
            host='localhost', port=3306, username='root',
            password='secret', database='db1', created_by=self.user,
        )
        c2 = ApiDatabaseConfig.objects.create(
            name='Second', project=self.project, db_type='mysql',
            host='localhost', port=3306, username='root',
            password='secret', database='db2', created_by=self.user,
        )
        configs = list(ApiDatabaseConfig.objects.all())
        self.assertEqual(configs[0], c2)  # newest first
        self.assertEqual(configs[1], c1)


class ApiDatabaseConfigAPITest(TestCase):
    """ApiDatabaseConfig API CRUD 测试"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='apiuser', password='testpass')
        _grant_db_config_permissions(self.user)
        self.project = Project.objects.create(name='API Project', creator=self.user)
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        self.client.force_authenticate(user=self.user)
        self.base_url = f'/api/projects/{self.project.pk}/api-database-configs/'

    def test_list_configs(self):
        ApiDatabaseConfig.objects.create(
            name='DB1', project=self.project, db_type='mysql',
            host='localhost', port=3306, username='root',
            password='secret', database='db1', created_by=self.user,
        )
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_config(self):
        data = {
            'name': 'New DB',
            'type': 'mysql',
            'host': 'db.example.com',
            'port': 3306,
            'username': 'root',
            'password': 'secret',
            'database': 'newdb',
            'project': self.project.pk,
        }
        response = self.client.post(self.base_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        config = ApiDatabaseConfig.objects.get(name='New DB')
        self.assertEqual(config.project, self.project)
        self.assertEqual(config.created_by, self.user)

    def test_retrieve_config_password_masked(self):
        config = ApiDatabaseConfig.objects.create(
            name='Masked', project=self.project, db_type='mysql',
            host='localhost', port=3306, username='root',
            password='realsecret', database='db', created_by=self.user,
        )
        response = self.client.get(f'{self.base_url}{config.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['password'], '******')

    def test_update_config(self):
        config = ApiDatabaseConfig.objects.create(
            name='Old DB', project=self.project, db_type='mysql',
            host='localhost', port=3306, username='root',
            password='secret', database='db', created_by=self.user,
        )
        response = self.client.patch(
            f'{self.base_url}{config.pk}/',
            {'host': 'newhost.example.com'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        config.refresh_from_db()
        self.assertEqual(config.host, 'newhost.example.com')

    def test_delete_config(self):
        config = ApiDatabaseConfig.objects.create(
            name='To Delete', project=self.project, db_type='mysql',
            host='localhost', port=3306, username='root',
            password='secret', database='db', created_by=self.user,
        )
        response = self.client.delete(f'{self.base_url}{config.pk}/')
        self.assertIn(response.status_code, (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT))

    def test_filter_by_db_type(self):
        ApiDatabaseConfig.objects.create(
            name='MySQL DB', project=self.project, db_type='mysql',
            host='localhost', port=3306, username='root',
            password='secret', database='db1', created_by=self.user,
        )
        ApiDatabaseConfig.objects.create(
            name='PG DB', project=self.project, db_type='postgresql',
            host='localhost', port=5432, username='pguser',
            password='secret', database='db2', created_by=self.user,
        )
        response = self.client.get(self.base_url, {'db_type': 'mysql'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch('api_database_configs.views.pymysql')
    def test_test_connection_adhoc(self, mock_pymysql):
        mock_conn = MagicMock()
        mock_pymysql.connect.return_value = mock_conn
        data = {
            'db_type': 'mysql',
            'host': 'localhost',
            'port': 3306,
            'database': 'testdb',
            'user': 'root',
            'password': 'secret',
        }
        response = self.client.post(
            f'{self.base_url}test-connection/', data, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['connected'])

    def test_test_connection_missing_params(self):
        data = {'db_type': 'mysql', 'host': 'localhost'}
        response = self.client.post(
            f'{self.base_url}test-connection/', data, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_test_connection_invalid_port(self):
        data = {
            'db_type': 'mysql',
            'host': 'localhost',
            'port': 'not_a_number',
            'database': 'testdb',
            'user': 'root',
            'password': 'secret',
        }
        response = self.client.post(
            f'{self.base_url}test-connection/', data, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('api_database_configs.views.pymysql')
    def test_test_saved_connection(self, mock_pymysql):
        mock_conn = MagicMock()
        mock_pymysql.connect.return_value = mock_conn
        config = ApiDatabaseConfig.objects.create(
            name='Saved', project=self.project, db_type='mysql',
            host='localhost', port=3306, username='root',
            password='secret', database='db', created_by=self.user,
        )
        response = self.client.post(
            f'{self.base_url}{config.pk}/test-connection/',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['connected'])

    def test_unauthenticated_access(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ApiDatabaseConfigPermissionTest(TestCase):
    """ApiDatabaseConfig 权限测试"""

    def setUp(self):
        self.client = APIClient()
        self.user_a = User.objects.create_user(username='user_a', password='testpass')
        _grant_db_config_permissions(self.user_a)
        self.project_a = Project.objects.create(name='Project A', creator=self.user_a)
        ProjectMember.objects.create(project=self.project_a, user=self.user_a, role='member')

        self.outsider = User.objects.create_user(username='outsider', password='testpass')
        _grant_db_config_permissions(self.outsider)
        self.superuser = User.objects.create_superuser(username='admin', password='adminpass')

    def test_non_member_denied(self):
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(f'/api/projects/{self.project_a.pk}/api-database-configs/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_allowed(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get(f'/api/projects/{self.project_a.pk}/api-database-configs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ApiDatabaseConfigIsolationTest(TestCase):
    """项目隔离测试 — get_by_key with project scope"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.project1 = Project.objects.create(name='P1', creator=self.user)
        self.project2 = Project.objects.create(name='P2', creator=self.user)
        self.config1 = ApiDatabaseConfig.objects.create(
            name='shared_name', project=self.project1, db_type='mysql',
            host='h1', port=3306, username='u1', password='p1',
            database='db1', created_by=self.user,
        )
        self.config2 = ApiDatabaseConfig.objects.create(
            name='shared_name', project=self.project2, db_type='mysql',
            host='h2', port=3306, username='u2', password='p2',
            database='db2', created_by=self.user,
        )

    def test_get_by_key_with_project_scope(self):
        """get_by_key(name, project_id) 只返回本项目的配置"""
        result = ApiDatabaseConfig.get_by_key('shared_name', project_id=self.project1.pk)
        self.assertIsNotNone(result)
        self.assertEqual(result.project, self.project1)

    def test_get_by_key_wrong_project_returns_none(self):
        """get_by_key 指定错误项目返回 None"""
        # project1 中不存在 'only_in_p2'
        ApiDatabaseConfig.objects.create(
            name='only_in_p2', project=self.project2, db_type='mysql',
            host='h', port=3306, username='u', password='p',
            database='db', created_by=self.user,
        )
        result = ApiDatabaseConfig.get_by_key('only_in_p2', project_id=self.project1.pk)
        self.assertIsNone(result)

    def test_get_by_key_without_project_returns_first(self):
        """不指定 project_id 时返回第一个匹配的 active 配置"""
        result = ApiDatabaseConfig.get_by_key('shared_name')
        self.assertIsNotNone(result)


class ApiDatabaseConfigConnectionStringTest(TestCase):
    """connection_string 属性全面测试"""

    def setUp(self):
        self.user = User.objects.create_user(username='connuser', password='testpass')
        self.project = Project.objects.create(name='Conn Project', creator=self.user)

    def _make_config(self, **kwargs):
        defaults = dict(
            project=self.project, host='h', port=3306,
            username='u', password='p', database='db',
            created_by=self.user,
        )
        defaults.update(kwargs)
        return ApiDatabaseConfig.objects.create(**defaults)

    def test_unknown_db_type_falls_back_to_mysql(self):
        """未知 db_type 回退到 MySQL 连接字符串"""
        config = self._make_config(name='unknown', db_type='unknown')
        self.assertIn('mysql+pymysql://', config.connection_string)

    def test_connection_string_contains_all_parts(self):
        """连接字符串包含所有必要部分"""
        config = self._make_config(
            name='full', db_type='mysql',
            host='myhost', port=3307, username='admin',
            password='s3cret', database='production', charset='utf8',
        )
        cs = config.connection_string
        self.assertIn('admin:s3cret', cs)
        self.assertIn('myhost:3307', cs)
        self.assertIn('/production', cs)
        self.assertIn('charset=utf8', cs)

    def test_get_by_key_returns_active_only(self):
        """get_by_key 只返回 is_active=True 的配置"""
        self._make_config(name='active_one', is_active=True)
        self._make_config(name='inactive_one', is_active=False)
        self.assertIsNotNone(ApiDatabaseConfig.get_by_key('active_one'))
        self.assertIsNone(ApiDatabaseConfig.get_by_key('inactive_one'))


class ApiDatabaseConfigPaginationTest(TestCase):
    """ApiDatabaseConfig 分页测试"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='pageuser', password='testpass')
        _grant_db_config_permissions(self.user)
        self.project = Project.objects.create(name='Page Project', creator=self.user)
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        self.client.force_authenticate(user=self.user)
        self.base_url = f'/api/projects/{self.project.pk}/api-database-configs/'
        for i in range(15):
            ApiDatabaseConfig.objects.create(
                name=f'db_{i:03d}', project=self.project, db_type='mysql',
                host='h', port=3306, username='u', password='p',
                database=f'db{i}', created_by=self.user,
            )

    def test_pagination_response_format(self):
        """验证分页响应格式"""
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('results', response.data)
        self.assertEqual(response.data['count'], 15)
