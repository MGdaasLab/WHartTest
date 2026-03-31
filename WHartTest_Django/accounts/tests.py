from unittest.mock import patch
from types import SimpleNamespace

from django.db.utils import OperationalError
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from accounts.serializers import ContentTypeSerializer
from accounts.views import MyTokenObtainPairView


class MyTokenObtainPairViewTests(SimpleTestCase):
    def setUp(self):
        # 构造 DRF 请求工厂，模拟 token 登录请求。
        self.factory = APIRequestFactory()

    def test_returns_503_when_database_not_ready(self):
        # 模拟数据库尚未就绪时的登录请求，验证接口返回 503 而不是 500 traceback。
        request = self.factory.post(
            '/api/token/',
            {'username': 'tester', 'password': 'secret'},
            format='json'
        )

        # 条件：认证流程抛出 OperationalError；动作：调用视图；结果：返回友好错误提示。
        with patch(
            'accounts.views.BaseTokenObtainPairView.post',
            side_effect=OperationalError('database is not ready')
        ):
            response = MyTokenObtainPairView.as_view()(request)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['detail'], '认证服务正在启动，请稍后重试。')


class ContentTypeSerializerMenuGroupingTests(SimpleTestCase):
    def setUp(self):
        self.serializer = ContentTypeSerializer()

    def test_task_center_is_grouped_as_top_level_task_center_menu(self):
        content_type = SimpleNamespace(app_label='task_center', model='scheduledtask')

        self.assertEqual(self.serializer.get_app_label_cn(content_type), '任务中心')
        self.assertEqual(self.serializer.get_app_label_subcategory(content_type), '任务调度')
        self.assertEqual(self.serializer.get_app_label_sort(content_type), 5)

    def test_django_celery_beat_is_grouped_under_task_center(self):
        content_type = SimpleNamespace(app_label='django_celery_beat', model='periodictask')

        self.assertEqual(self.serializer.get_app_label_cn(content_type), '任务中心')
        self.assertEqual(self.serializer.get_app_label_subcategory(content_type), '任务调度')
