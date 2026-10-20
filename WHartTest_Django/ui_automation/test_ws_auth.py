"""UI 自动化 WebSocket 认证（第一层中间件 + 第二层 consumer 校验）测试。

覆盖：
- 中间件：web JWT 校验、执行器共享密钥校验、grace/strict 模式、错误凭据拒绝
- consumer：执行器 ID 防抢注、结果回传来源校验（严格/兼容模式）
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator

from ui_automation import consumers as cons
from ui_automation.routing import websocket_urlpatterns
from wharttest_django.websocket_auth import (
    WS_CLOSE_UNAUTHENTICATED,
    UiWebSocketAuthMiddleware,
)


def _middleware_app():
    return UiWebSocketAuthMiddleware(URLRouter(websocket_urlpatterns))


class MiddlewareWebAuthTests(TestCase):
    """web 端点 JWT 认证。"""

    def setUp(self):
        self.user = User.objects.create_user(username='wsuser', password='x')
        from rest_framework_simplejwt.tokens import AccessToken
        self.token = str(AccessToken.for_user(self.user))

    async def _connect_and_first_message(self, path):
        communicator = WebsocketCommunicator(_middleware_app(), path)
        try:
            accepted = await communicator.connect()
            first = None
            if accepted:
                first = await communicator.receive_output(timeout=2)
            return accepted, first, communicator
        except Exception:
            await communicator.disconnect()
            raise

    async def test_valid_jwt_connects_as_authenticated_user(self):
        accepted, first, communicator = await self._connect_and_first_message(
            f'/ws/ui/web/?token={self.token}'
        )
        try:
            self.assertTrue(accepted)
            self.assertEqual(first['type'], 'websocket.send')
            self.assertIn('"user":"wsuser"', first['text'])
        finally:
            await communicator.disconnect()

    async def test_garbage_token_rejected_even_in_grace_mode(self):
        communicator = WebsocketCommunicator(_middleware_app(), '/ws/ui/web/?token=not-a-jwt')
        try:
            self.assertTrue(await communicator.connect())
            close = await communicator.receive_output(timeout=2)
            self.assertEqual(close['type'], 'websocket.close')
            self.assertEqual(close['code'], WS_CLOSE_UNAUTHENTICATED)
        finally:
            await communicator.disconnect()

    async def test_no_token_allowed_in_grace_mode(self):
        accepted, first, communicator = await self._connect_and_first_message('/ws/ui/web/')
        try:
            self.assertTrue(accepted)
            self.assertEqual(first['type'], 'websocket.send')
            # 匿名连接：user 为 web_xxx 形式
            self.assertIn('web_', first['text'])
        finally:
            await communicator.disconnect()

    @override_settings(UI_WS_AUTH_STRICT='1')
    async def test_no_token_rejected_in_strict_mode(self):
        communicator = WebsocketCommunicator(_middleware_app(), '/ws/ui/web/')
        try:
            self.assertTrue(await communicator.connect())
            close = await communicator.receive_output(timeout=2)
            self.assertEqual(close['type'], 'websocket.close')
            self.assertEqual(close['code'], WS_CLOSE_UNAUTHENTICATED)
        finally:
            await communicator.disconnect()


class MiddlewareActuatorAuthTests(TestCase):
    """执行器端点共享密钥认证。"""

    SECRET = 'test-actuator-secret'

    async def _connect(self, path):
        communicator = WebsocketCommunicator(_middleware_app(), path)
        try:
            accepted = await communicator.connect()
            first = None
            if accepted:
                first = await communicator.receive_output(timeout=2)
            return accepted, first, communicator
        except Exception:
            await communicator.disconnect()
            raise

    @override_settings(UI_WS_ACTUATOR_TOKEN=SECRET)
    async def test_correct_secret_connects(self):
        accepted, first, communicator = await self._connect(
            f'/ws/ui/actuator/?id=act-1&token={self.SECRET}'
        )
        try:
            self.assertTrue(accepted)
            self.assertEqual(first['type'], 'websocket.send')
            self.assertIn('"user":"act-1"', first['text'])
        finally:
            await communicator.disconnect()

    @override_settings(UI_WS_ACTUATOR_TOKEN=SECRET)
    async def test_wrong_secret_rejected(self):
        communicator = WebsocketCommunicator(
            _middleware_app(), '/ws/ui/actuator/?id=act-1&token=wrong'
        )
        try:
            self.assertTrue(await communicator.connect())
            close = await communicator.receive_output(timeout=2)
            self.assertEqual(close['code'], WS_CLOSE_UNAUTHENTICATED)
        finally:
            await communicator.disconnect()

    @override_settings(UI_WS_ACTUATOR_TOKEN=SECRET, UI_WS_AUTH_STRICT='1')
    async def test_missing_secret_rejected_in_strict_mode(self):
        communicator = WebsocketCommunicator(_middleware_app(), '/ws/ui/actuator/?id=act-1')
        try:
            self.assertTrue(await communicator.connect())
            close = await communicator.receive_output(timeout=2)
            self.assertEqual(close['code'], WS_CLOSE_UNAUTHENTICATED)
        finally:
            await communicator.disconnect()

    @override_settings(UI_WS_ACTUATOR_TOKEN=SECRET)
    async def test_missing_secret_allowed_in_grace_mode(self):
        accepted, first, communicator = await self._connect('/ws/ui/actuator/?id=act-grace')
        try:
            self.assertTrue(accepted)
            self.assertIn('act-grace', first['text'])
        finally:
            await communicator.disconnect()


class ActuatorHijackTests(TestCase):
    """执行器 ID 防抢注。"""

    def test_duplicate_actuator_id_rejected(self):
        first = cons.UiAutomationConsumer()
        second = cons.UiAutomationConsumer()
        self.assertTrue(cons.SocketUserManager.add_actuator('dup-1', first))
        self.assertFalse(cons.SocketUserManager.add_actuator('dup-1', second))
        # 原连接不被顶掉
        self.assertIs(cons.SocketUserManager.get_actuator_by_id('dup-1'), first)
        cons.SocketUserManager.remove_actuator('dup-1')

    def test_reconnect_same_instance_allowed(self):
        consumer = cons.UiAutomationConsumer()
        try:
            self.assertTrue(cons.SocketUserManager.add_actuator('dup-2', consumer))
            self.assertTrue(cons.SocketUserManager.add_actuator('dup-2', consumer))
        finally:
            cons.SocketUserManager.remove_actuator('dup-2')


class ResultSourceVerificationTests(TestCase):
    """执行器结果回传来源校验。"""

    def _actuator_consumer(self) -> cons.UiAutomationConsumer:
        consumer = cons.UiAutomationConsumer()
        consumer.is_actuator = True
        consumer.user_id = 'act-test'
        return consumer

    def test_registered_user_passes(self):
        consumer = self._actuator_consumer()
        consumer.actuator_recent_users['web_1'] = 1.0
        self.assertTrue(consumer.verify_result_source('web_1'))

    def test_unregistered_user_rejected_in_strict_mode(self):
        consumer = self._actuator_consumer()
        with override_settings(UI_WS_AUTH_STRICT='1'):
            self.assertFalse(consumer.verify_result_source('web_victim'))

    def test_unregistered_user_allowed_in_grace_mode(self):
        consumer = self._actuator_consumer()
        self.assertTrue(consumer.verify_result_source('web_anyone'))

    def test_empty_user_rejected_in_strict_mode(self):
        consumer = self._actuator_consumer()
        with override_settings(UI_WS_AUTH_STRICT='1'):
            self.assertFalse(consumer.verify_result_source(''))

    def test_web_connection_always_passes(self):
        consumer = cons.UiAutomationConsumer()
        consumer.is_actuator = False
        with override_settings(UI_WS_AUTH_STRICT='1'):
            self.assertTrue(consumer.verify_result_source('nobody'))

    def test_register_task_records_user_and_token(self):
        consumer = self._actuator_consumer()
        args: dict = {}
        consumer.register_actuator_task(consumer, args, 'web_9')
        self.assertTrue(args.get('task_token'))
        self.assertIn('web_9', consumer.actuator_recent_users)
        # 登记 token 后可被校验通过
        self.assertIn(args['task_token'], consumer.actuator_task_tokens)

    def test_recent_users_cleanup_prunes_expired(self):
        consumer = self._actuator_consumer()
        consumer.actuator_recent_users['web_old'] = -10_000.0
        consumer.register_actuator_task(consumer, {}, 'web_new')
        self.assertNotIn('web_old', consumer.actuator_recent_users)
        self.assertIn('web_new', consumer.actuator_recent_users)
