import unittest

from models import SocketDataModel, QueueModel
from websocket_client import WebSocketClient, build_websocket_connect_url, build_websocket_origin


class WebSocketClientUrlTests(unittest.TestCase):
    def test_build_origin_for_ws_url(self):
        self.assertEqual(
            build_websocket_origin('ws://127.0.0.1:8000/ws/ui/actuator/'),
            'http://127.0.0.1:8000',
        )

    def test_build_origin_for_wss_url(self):
        self.assertEqual(
            build_websocket_origin('wss://example.com/ws/ui/actuator/'),
            'https://example.com',
        )

    def test_build_connect_url_adds_id_query_param(self):
        self.assertEqual(
            build_websocket_connect_url(
                'ws://127.0.0.1:8000/ws/ui/actuator/',
                'actuator-1',
            ),
            'ws://127.0.0.1:8000/ws/ui/actuator/?id=actuator-1',
        )

    def test_build_connect_url_preserves_existing_query(self):
        self.assertEqual(
            build_websocket_connect_url(
                'ws://127.0.0.1:8000/ws/ui/actuator/?lang=en',
                'actuator-1',
            ),
            'ws://127.0.0.1:8000/ws/ui/actuator/?lang=en&id=actuator-1',
        )

    def test_build_connect_url_replaces_existing_identity_query(self):
        self.assertEqual(
            build_websocket_connect_url(
                'ws://127.0.0.1:8000/ws/ui/actuator/?user_id=old&id=older&lang=en',
                'actuator-1',
            ),
            'ws://127.0.0.1:8000/ws/ui/actuator/?lang=en&id=actuator-1',
        )

    def test_build_connect_url_appends_token(self):
        self.assertEqual(
            build_websocket_connect_url(
                'ws://127.0.0.1:8000/ws/ui/actuator/',
                'actuator-1',
                token='secret',
            ),
            'ws://127.0.0.1:8000/ws/ui/actuator/?id=actuator-1&token=secret',
        )

    def test_build_connect_url_replaces_existing_token(self):
        self.assertEqual(
            build_websocket_connect_url(
                'ws://127.0.0.1:8000/ws/ui/actuator/?token=stale',
                'actuator-1',
                token='fresh',
            ),
            'ws://127.0.0.1:8000/ws/ui/actuator/?id=actuator-1&token=fresh',
        )

    def test_build_connect_url_no_token_keeps_query_clean(self):
        self.assertEqual(
            build_websocket_connect_url(
                'ws://127.0.0.1:8000/ws/ui/actuator/',
                'actuator-1',
                token=None,
            ),
            'ws://127.0.0.1:8000/ws/ui/actuator/?id=actuator-1',
        )


class TaskTokenEchoTests(unittest.IsolatedAsyncioTestCase):
    """send_result 自动回显任务来源令牌（端到端强校验的执行器侧）。"""

    def _capture_client(self) -> WebSocketClient:
        client = WebSocketClient('ws://127.0.0.1:8000/ws/ui/actuator/', 'act-1')
        captured = {}

        async def fake_send(data):
            captured['data'] = data

        client.send = fake_send  # type: ignore[method-assign]
        client.connected = True
        client.websocket = object()  # 非 None 即可
        return client, captured

    async def test_send_result_echoes_task_token(self):
        client, captured = self._capture_client()
        client.set_task_token('tok-123')
        await client.send_result('u_case_result', {'case_id': 1}, 'web_1')
        self.assertEqual(captured['data'].data.func_args.get('task_token'), 'tok-123')
        self.assertEqual(captured['data'].data.func_args['case_id'], 1)

    async def test_send_result_without_token_leaves_args_clean(self):
        client, captured = self._capture_client()
        client.set_task_token(None)
        await client.send_result('u_case_result', {'case_id': 1}, 'web_1')
        self.assertNotIn('task_token', captured['data'].data.func_args)

    async def test_send_result_explicit_token_wins_and_no_double_inject(self):
        client, captured = self._capture_client()
        client.set_task_token('tok-auto')
        await client.send_result(
            'u_case_result', {'case_id': 1, 'task_token': 'tok-explicit'}, 'web_1'
        )
        self.assertEqual(captured['data'].data.func_args.get('task_token'), 'tok-explicit')

    async def test_set_task_token_clear(self):
        client, captured = self._capture_client()
        client.set_task_token('tok-x')
        client.set_task_token(None)
        await client.send_result('u_case_result', {'case_id': 1}, 'web_1')
        self.assertNotIn('task_token', captured['data'].data.func_args)


class AuthRejectionTests(unittest.IsolatedAsyncioTestCase):
    """WS 认证被拒（close 4401）后的行为：提示 + 停止重连，不刷屏。

    背景：后端认证失败时 accept 握手后立即 close 4401（浏览器 WS 无法在
    握手前传码），客户端若当作普通断线会无限重连且每次都被拒。
    """

    def _make_closed_exception(self, code: int):
        from websockets.exceptions import ConnectionClosed
        from websockets.frames import Close
        return ConnectionClosed(Close(code, ''), None)

    def _make_client_with_failing_send(self, code: int) -> WebSocketClient:
        """构造 send 时抛出指定关闭码 ConnectionClosed 的客户端。

        WebSocketClient.send 先序列化再调用 websocket.send，fake 收到的
        已是 JSON 字符串，直接抛出模拟的连接关闭异常即可。
        """
        client = WebSocketClient('ws://127.0.0.1:8000/ws/ui/actuator/', 'act-1')
        client.connected = True

        exc = self._make_closed_exception(code)

        async def raise_closed(data):
            raise exc

        client.websocket = type('FakeWs', (), {'send': staticmethod(raise_closed)})()
        return client

    async def test_send_on_4401_marks_auth_rejected(self):
        """连接被服务端 accept 后立即关闭，send 时收到 4401 → 标记认证被拒。"""
        client = self._make_client_with_failing_send(4401)
        data = SocketDataModel(code=0, msg='t', data=QueueModel(func_name='f', func_args={}))
        with self.assertLogs('actuator', level='ERROR') as captured:
            ok = await client.send(data)
        self.assertFalse(ok)
        self.assertFalse(client.connected)
        self.assertTrue(client._auth_rejected)
        self.assertIn('4401', '\n'.join(captured.output))

    async def test_send_on_normal_close_keeps_reconnectable(self):
        """普通断线（非 4401）不标记认证被拒，保留重连行为。"""
        from models import SocketDataModel, QueueModel

        client = self._make_client_with_failing_send(1006)
        data = SocketDataModel(code=0, msg='t', data=QueueModel(func_name='f', func_args={}))
        with self.assertLogs('actuator', level='ERROR'):
            ok = await client.send(data)
        self.assertFalse(ok)
        self.assertFalse(client._auth_rejected)

    async def test_reconnect_stops_after_auth_rejection(self):
        """认证被拒后 _reconnect 立即返回，不再尝试连接。"""
        client = WebSocketClient('ws://127.0.0.1:8000/ws/ui/actuator/', 'act-1')
        client._auth_rejected = True
        connect_calls = []

        async def fake_connect():
            connect_calls.append(1)
            return False

        client.connect = fake_connect  # type: ignore[method-assign]
        await client._reconnect()
        self.assertEqual(connect_calls, [])

    async def test_connect_skipped_after_auth_rejection(self):
        """认证被拒后 connect 直接返回 False，不再发起握手。"""
        client = WebSocketClient('ws://127.0.0.1:8000/ws/ui/actuator/', 'act-1')
        client._auth_rejected = True
        self.assertFalse(await client.connect())

    async def test_extract_close_code_from_rcvd(self):
        """优先取 rcvd 关闭码；e.code 在 rcvd 为空时会退回 1006，不能用它。"""
        client = WebSocketClient('ws://127.0.0.1:8000/ws/ui/actuator/', 'act-1')
        e = self._make_closed_exception(4401)
        self.assertEqual(client._extract_close_code(e), 4401)


class HandshakeStatusClassificationTests(unittest.IsolatedAsyncioTestCase):
    """握手层 HTTP 状态分类：认证拒绝（401/403/407）停止重连，
    瞬时故障（后端重启时代理返回的 502/503 等）保留重连。"""

    async def _run_connect_with_status(self, status_code: int) -> WebSocketClient:
        from types import SimpleNamespace
        import websockets.exceptions as we
        import websocket_client as wc_module

        client = WebSocketClient('ws://127.0.0.1:8000/ws/ui/actuator/', 'act-1')

        async def fake_connect(url, **kwargs):
            raise we.InvalidStatus(SimpleNamespace(
                status_code=status_code, reason='test', headers=[]))

        original = wc_module.websockets.connect
        wc_module.websockets.connect = fake_connect
        try:
            with self.assertLogs('actuator', level='ERROR'):
                await client.connect()
        finally:
            wc_module.websockets.connect = original
        return client

    async def test_403_marks_auth_rejected(self):
        """403 是确定性认证拒绝：停止重连。"""
        client = await self._run_connect_with_status(403)
        self.assertTrue(client._auth_rejected)
        self.assertFalse(client.connected)

    async def test_401_marks_auth_rejected(self):
        client = await self._run_connect_with_status(401)
        self.assertTrue(client._auth_rejected)

    async def test_502_does_not_stop_reconnect(self):
        """后端重启时代理返回 502：瞬时故障，不标记认证被拒。"""
        client = await self._run_connect_with_status(502)
        self.assertFalse(client._auth_rejected)
        self.assertFalse(client.connected)

    async def test_503_does_not_stop_reconnect(self):
        client = await self._run_connect_with_status(503)
        self.assertFalse(client._auth_rejected)

    async def test_auth_reject_message_mentions_actual_reason(self):
        """403 路径日志应写明 HTTP 403 而非硬编码 4401。"""
        client = await self._run_connect_with_status(403)
        # _mark_auth_rejected 只输出一次，重放日志需重置后触发
        client._auth_rejected = False
        with self.assertLogs('actuator', level='ERROR') as captured:
            client._mark_auth_rejected(f"HTTP 403")
        self.assertIn('HTTP 403', '\n'.join(captured.output))
        self.assertNotIn('关闭码 4401', '\n'.join(captured.output))


if __name__ == '__main__':
    unittest.main()