import unittest

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


if __name__ == '__main__':
    unittest.main()