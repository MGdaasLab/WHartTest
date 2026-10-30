"""
UI 自动化 WebSocket 认证中间件

为以下端点提供连接级认证（未认证连接一律拒绝，close code 4401）：
- /ws/ui/web/      前端浏览器连接：校验 SimpleJWT access token（query 参数 token）
- /ws/ui/actuator/ 执行器连接：校验共享密钥（query 参数 token）
- /ws/heal/chat/   自愈对话订阅：与 web 同为 JWT 认证

背景：这些端点此前完全匿名（asgi.py 无认证中间件，consumer.connect() 无条件
accept），任意攻击者可注册执行器抢注任务载荷、接收广播结果并伪造结果/画面帧
注入受害者会话。本中间件是第一层修复；consumer 内的第二层校验见 consumers.py。

硬性要求：WS 认证不可关闭——不存在兼容模式开关，未携带有效凭据的连接一律
拒绝。执行器侧密钥由 run_compose.sh 自动生成并同步到 config.toml，前端自动
携带登录 JWT，正常部署下用户无需任何手工配置。

设计说明：token 经查询参数传递（浏览器 WebSocket API 无法自定义请求头），
生产环境应启用 HTTPS 防止 token 出现在代理日志。
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
    """WS 认证严格模式恒为开启（硬性安全要求，不可配置关闭）。

    保留函数形态：consumer 等多处仍以 auth_strict_mode() 表达"未认证即拒绝"
    的判定，收敛在此便于将来如需调整策略只改一处。
    """
    return True


class UiWebSocketAuthMiddleware:
    """按路径区分认证方式的 ASGI WebSocket 中间件。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get('type') != 'websocket':
            return await self.app(scope, receive, send)

        path = scope.get('path', '')
        if not (
            path.startswith('/ws/ui/web/')
            or path.startswith('/ws/ui/actuator/')
            or path.startswith('/ws/heal/chat/')
        ):
            return await self.app(scope, receive, send)

        query = parse_qs(scope.get('query_string', b'').decode('utf-8'))
        token = (query.get('token') or [''])[0]

        if path.startswith('/ws/ui/actuator/'):
            authed, principal = self._authenticate_actuator(token)
        else:
            # /ws/ui/web/ 与 /ws/heal/chat/ 同为 JWT 认证
            authed, principal = await self._authenticate_web(token)

        if not authed:
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
            'kind': 'actuator' if path.startswith('/ws/ui/actuator/') else 'web',
            'authenticated': True,
            'token_kind': 'jwt' if not path.startswith('/ws/ui/actuator/') else 'shared_secret',
        }
        return await self.app(scope, receive, send)

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
            # 未配置密钥：无标准答案可比对，一律拒绝（fail-closed）
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


def warn_insecure_ws_config() -> None:
    """启动时检查 WS 认证配置，关键缺失打 WARNING（只提示，不阻断启动）。"""
    if not _get_setting('UI_WS_ACTUATOR_TOKEN'):
        logger.warning(
            "UI_WS_ACTUATOR_TOKEN 未配置：所有执行器 WS 连接都将被拒绝（4401）。"
            "请运行 run_compose.sh（自动生成并同步密钥），或手动设置该环境变量"
        )
