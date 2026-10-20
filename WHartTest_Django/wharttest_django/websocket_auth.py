"""
UI 自动化 WebSocket 认证中间件

为以下两个端点提供连接级认证（未认证连接直接拒绝，close code 4401）：
- /ws/ui/web/      前端浏览器连接：校验 SimpleJWT access token（query 参数 token）
- /ws/ui/actuator/ 执行器连接：校验共享密钥（query 参数 token）

背景：这两个端点此前完全匿名（asgi.py 无认证中间件，consumer.connect() 无条件
accept），任意攻击者可注册执行器抢注任务载荷、接收广播结果并伪造结果/画面帧注入
受害者会话。本中间件是第一层修复；consumer 内的第二层校验见 consumers.py。

设计说明：
- token 经查询参数传递：浏览器 WebSocket API 无法自定义请求头，这是现实做法；
  生产环境应启用 HTTPS 防止 token 出现在代理日志。
- 兼容模式（grace）：UI_WS_AUTH_STRICT=0 时，缺 token 的连接放行（保持与尚未
  改造的旧版前端/执行器兼容），但带了 token 就必须校验通过；=1 时严格拒绝。
  该开关仅为平滑过渡设计，客户端改造完成后应尽快切换为 1 并移除 grace 分支。
"""

import logging
import os
import secrets
from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from django.conf import settings

logger = logging.getLogger('ui_automation')

# WebSocket 自定义关闭码：4000-4999 为应用可用区间
WS_CLOSE_UNAUTHENTICATED = 4401  # 未认证 / 凭据无效
WS_CLOSE_FORBIDDEN = 4403        # 凭据类型与端点不匹配（如 web token 连执行器端点）
WS_CLOSE_CONFLICT = 4409         # 执行器 ID 已在线（防抢注）

# 认证信息在 scope 中的键名（consumer 第二层校验使用）
SCOPE_AUTH_KEY = 'ui_ws_auth'


def _get_setting(name: str, default: str = '') -> str:
    value = getattr(settings, name, None)
    if value is None:
        value = os.environ.get(name, default)
    return str(value)


def auth_strict_mode() -> bool:
    """认证严格模式是否开启（UI_WS_AUTH_STRICT）。

    True：未认证连接一律拒绝；False（默认）：缺 token 的旧客户端放行（带了
    token 则必须有效）。consumer 侧第二层校验同样引用本开关保持行为一致。
    """
    return _get_setting('UI_WS_AUTH_STRICT', '0').strip().lower() in {
        '1', 'true', 'yes', 'on',
    }


class UiWebSocketAuthMiddleware:
    """按路径区分认证方式的 ASGI WebSocket 中间件。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get('type') != 'websocket':
            return await self.app(scope, receive, send)

        path = scope.get('path', '')
        if not (path.startswith('/ws/ui/web/') or path.startswith('/ws/ui/actuator/')):
            return await self.app(scope, receive, send)

        query = parse_qs(scope.get('query_string', b'').decode('utf-8'))
        token = (query.get('token') or [''])[0]

        if path.startswith('/ws/ui/web/'):
            authed, principal = await self._authenticate_web(token)
        else:
            authed, principal = self._authenticate_actuator(token)

        if not authed:
            # grace 模式：未携带凭据的连接放行（兼容旧客户端）；
            # 携带了错误凭据则无论何种模式都拒绝。
            if token == '' and not self._strict_mode():
                logger.warning('UI WS 匿名连接放行（兼容模式）: %s', path)
                return await self.app(scope, receive, send)
            logger.warning(
                'UI WS 认证失败，拒绝连接: path=%s ip=%s',
                path,
                (scope.get('client') or ['unknown'])[0],
            )
            await self._reject(send)
            return

        # 认证结果写入 scope，供 consumer 第二层校验使用
        if principal is not None:
            scope['user'] = principal
        scope[SCOPE_AUTH_KEY] = {
            'kind': 'web' if path.startswith('/ws/ui/web/') else 'actuator',
            'authenticated': True,
            'token_kind': 'jwt' if path.startswith('/ws/ui/web/') else 'shared_secret',
        }
        return await self.app(scope, receive, send)

    @staticmethod
    def _strict_mode() -> bool:
        return auth_strict_mode()

    @staticmethod
    async def _authenticate_web(token: str):
        """校验 SimpleJWT access token，成功返回 (True, User)，失败 (False, None)。"""
        if not token:
            return False, None
        try:
            from rest_framework_simplejwt.exceptions import TokenError
            from rest_framework_simplejwt.tokens import AccessToken

            access = AccessToken(token)
            user_id = access.payload.get('user_id')
            if user_id is None:
                return False, None
            from django.contrib.auth import get_user_model

            def _fetch():
                return get_user_model().objects.filter(pk=user_id).first()

            user = await sync_to_async(_fetch)()
            if user is None or not user.is_active:
                return False, None
            return True, user
        except TokenError:
            return False, None
        except Exception:
            logger.exception('UI WS JWT 校验异常')
            return False, None

    @staticmethod
    def _authenticate_actuator(token: str):
        """校验执行器共享密钥，成功返回 (True, None)。"""
        expected = _get_setting('UI_WS_ACTUATOR_TOKEN')
        if not expected:
            # 未配置密钥：无法校验，视为未认证（grace 模式下仍可匿名放行）
            return False, None
        if not token:
            return False, None
        if secrets.compare_digest(token, expected):
            return True, None
        return False, None

    @staticmethod
    async def _reject(send):
        """拒绝连接：先接受握手再立即以自定义码关闭（浏览器 WS 无法在握手前传码）。"""
        await send({'type': 'websocket.accept'})
        await send({'type': 'websocket.close', 'code': WS_CLOSE_UNAUTHENTICATED})
