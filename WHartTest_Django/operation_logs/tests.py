import json
from datetime import timedelta
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import JsonResponse
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from operation_logs.middleware import OperationLogMiddleware
from operation_logs.models import OperationLog, OperationLogSetting
from operation_logs.tasks import cleanup_operation_logs
from operation_logs.views import OperationLogCleanupAPIView, OperationLogSettingAPIView


class PromptAPIView:
    pass


class SystemConfigView:
    pass


class OperationLogViewSet:
    pass


class MyTokenObtainPairView:
    pass


class CurrentUserAPIView:
    pass


PromptAPIView.__module__ = 'prompts.views'
SystemConfigView.__module__ = 'accounts.views'
OperationLogViewSet.__module__ = 'operation_logs.views'
MyTokenObtainPairView.__module__ = 'accounts.views'
CurrentUserAPIView.__module__ = 'accounts.views'


class OperationLogMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.middleware = OperationLogMiddleware(lambda request: JsonResponse({'ok': True}))
        self.user = get_user_model().objects.create_user(
            username='tester',
            password='Secret12345',
        )
        self.admin_user = get_user_model().objects.create_user(
            username='admin-user',
            password='Secret12345',
            is_staff=True,
        )

    def build_resolver_match(self, view_class, url_name, *, actions=None, kwargs=None):
        return SimpleNamespace(
            func=SimpleNamespace(cls=view_class, actions=actions or {}),
            url_name=url_name,
            kwargs=kwargs or {},
        )

    def record_request(self, request, response):
        self.middleware.process_request(request)
        return self.middleware.process_response(request, response)

    def create_operation_log(self, *, created_at=None):
        log = OperationLog.objects.create(
            user=self.user,
            username=self.user.username,
            ip_address='127.0.0.1',
            user_agent='pytest-agent',
            path='/api/test/',
            method='GET',
            module='测试模块',
            action='测试动作',
            request_data='{}',
            response_code=200,
            response_data='{}',
            duration=10,
        )
        if created_at is not None:
            OperationLog.objects.filter(id=log.id).update(created_at=created_at)
            log.refresh_from_db()
        return log

    def test_logs_prompt_get_requests_with_query_and_path_params(self):
        request = self.factory.get(
            '/api/prompts/items/42/',
            {'keyword': '审计', 'page': '2'},
        )
        request.user = self.user
        request.resolver_match = self.build_resolver_match(
            PromptAPIView,
            'prompt-detail',
            kwargs={'prompt_id': '42'},
        )

        self.record_request(request, JsonResponse({'ok': True, 'count': 1}))

        self.assertEqual(OperationLog.objects.count(), 1)
        log = OperationLog.objects.get()
        payload = json.loads(log.request_data)

        self.assertEqual(log.method, 'GET')
        self.assertEqual(log.module, '提示词管理')
        self.assertEqual(payload['query_params']['keyword'], '审计')
        self.assertEqual(payload['query_params']['page'], '2')
        self.assertEqual(payload['path_params']['prompt_id'], '42')

    def test_logs_system_config_write_requests(self):
        request = self.factory.post(
            '/api/accounts/system-config/',
            {'site_name': 'WHartTest'},
            format='json',
        )
        request.user = self.user
        request.resolver_match = self.build_resolver_match(
            SystemConfigView,
            'system-config',
        )

        self.record_request(request, JsonResponse({'ok': True}))

        self.assertEqual(OperationLog.objects.count(), 1)
        log = OperationLog.objects.get()
        payload = json.loads(log.request_data)

        self.assertEqual(log.path, '/api/accounts/system-config/')
        self.assertEqual(log.module, '系统配置')
        self.assertEqual(payload['body']['site_name'], 'WHartTest')

    def test_skips_operation_log_endpoint_to_avoid_recursion(self):
        request = self.factory.get('/api/operation-logs/')
        request.user = self.user
        request.resolver_match = self.build_resolver_match(
            OperationLogViewSet,
            'operation-log-list',
            actions={'get': 'list'},
        )

        self.record_request(request, JsonResponse({'ok': True}))

        self.assertEqual(OperationLog.objects.count(), 0)

    def test_skips_current_user_reads_to_avoid_high_frequency_noise(self):
        request = self.factory.get('/api/accounts/me/')
        request.user = self.user
        request.resolver_match = self.build_resolver_match(
            CurrentUserAPIView,
            'user-me',
        )

        self.record_request(request, JsonResponse({'username': 'tester'}))

        self.assertEqual(OperationLog.objects.count(), 0)

    def test_skips_head_and_options_requests(self):
        request_builders = {
            'HEAD': self.factory.head,
            'OPTIONS': self.factory.options,
        }

        for method, builder in request_builders.items():
            with self.subTest(method=method):
                request = builder('/api/prompts/items/42/')
                request.user = self.user
                request.resolver_match = self.build_resolver_match(
                    PromptAPIView,
                    'prompt-detail',
                    kwargs={'prompt_id': '42'},
                )

                self.record_request(request, JsonResponse({'ok': True}))

        self.assertEqual(OperationLog.objects.count(), 0)

    def test_uses_request_username_for_failed_login_when_user_is_anonymous(self):
        request = self.factory.post(
            '/api/token/',
            {'username': 'login_user', 'password': 'super-secret'},
            format='json',
        )
        request.user = AnonymousUser()
        request.resolver_match = self.build_resolver_match(
            MyTokenObtainPairView,
            'token_obtain_pair',
        )

        self.record_request(
            request,
            JsonResponse({'detail': 'Unauthorized'}, status=401),
        )

        self.assertEqual(OperationLog.objects.count(), 1)
        log = OperationLog.objects.get()
        payload = json.loads(log.request_data)

        self.assertEqual(log.username, 'login_user')
        self.assertEqual(log.module, '用户认证')
        self.assertEqual(log.action, '用户登录')
        self.assertEqual(payload['body']['username'], 'login_user')
        self.assertEqual(payload['body']['password'], '******')

    def test_cleanup_task_uses_configured_operation_log_setting(self):
        setting = OperationLogSetting.get_config()
        setting.retention_days = 15
        setting.save(update_fields=['retention_days'])

        old_log = self.create_operation_log(
            created_at=timezone.now() - timedelta(days=20),
        )
        recent_log = self.create_operation_log(
            created_at=timezone.now() - timedelta(days=5),
        )

        result = cleanup_operation_logs()

        self.assertEqual(result['retention_days'], 15)
        self.assertEqual(result['deleted_count'], 1)
        self.assertFalse(OperationLog.objects.filter(id=old_log.id).exists())
        self.assertTrue(OperationLog.objects.filter(id=recent_log.id).exists())

    def test_operation_log_setting_api_reads_and_updates_retention_days(self):
        request = self.factory.get('/api/operation-logs/settings/')
        force_authenticate(request, user=self.admin_user)
        response = OperationLogSettingAPIView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['retention_days'], 7)

        request = self.factory.patch(
            '/api/operation-logs/settings/',
            {'retention_days': 30},
            format='json',
        )
        force_authenticate(request, user=self.admin_user)
        response = OperationLogSettingAPIView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['retention_days'], 30)
        self.assertEqual(OperationLogSetting.get_config().retention_days, 30)

    def test_cleanup_task_deletes_logs_older_than_retention_days(self):
        old_log = self.create_operation_log(
            created_at=timezone.now() - timedelta(days=9),
        )
        recent_log = self.create_operation_log(
            created_at=timezone.now() - timedelta(days=5),
        )

        result = cleanup_operation_logs()

        self.assertEqual(result['retention_days'], 7)
        self.assertEqual(result['deleted_count'], 1)
        self.assertFalse(OperationLog.objects.filter(id=old_log.id).exists())
        self.assertTrue(OperationLog.objects.filter(id=recent_log.id).exists())

    def test_cleanup_api_triggers_immediate_log_cleanup(self):
        old_log = self.create_operation_log(
            created_at=timezone.now() - timedelta(days=9),
        )
        recent_log = self.create_operation_log(
            created_at=timezone.now() - timedelta(days=2),
        )

        request = self.factory.post('/api/operation-logs/cleanup-now/')
        force_authenticate(request, user=self.admin_user)
        response = OperationLogCleanupAPIView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['deleted_count'], 1)
        self.assertEqual(response.data['retention_days'], 7)
        self.assertFalse(OperationLog.objects.filter(id=old_log.id).exists())
        self.assertTrue(OperationLog.objects.filter(id=recent_log.id).exists())
