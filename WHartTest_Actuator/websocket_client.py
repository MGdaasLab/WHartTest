"""
UI自动化执行器 - WebSocket客户端

"""

import asyncio
import json
import logging
from typing import Optional, Callable, Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import websockets
from websockets.client import WebSocketClientProtocol

from models import SocketDataModel, QueueModel, ResponseCode, NoticeType, UiSocketEnum
from runtime_env import is_running_in_container

logger = logging.getLogger('actuator')


def build_websocket_connect_url(
    url: str,
    actuator_id: str | None = None,
    token: str | None = None,
) -> str:
    """构建带执行器 ID 与认证 token 的 WebSocket 连接地址。

    token 为后端 UI_WS_ACTUATOR_TOKEN 共享密钥（wharttest_django/websocket_auth.py），
    经查询参数传递（与 JWT 同一通道，WS 握手不便自定义头）。
    """
    parsed_url = urlsplit(url)
    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed_url.query, keep_blank_values=True)
        if key not in {'id', 'user_id', 'token'}
    ]
    if actuator_id:
        query_items.append(('id', actuator_id))
    if token:
        query_items.append(('token', token))
    return urlunsplit(parsed_url._replace(query=urlencode(query_items)))


def build_websocket_origin(url: str) -> str | None:
    """根据 WebSocket 地址推导握手所需的 HTTP Origin。"""
    parsed_url = urlsplit(url)
    if not parsed_url.scheme or not parsed_url.netloc:
        return None

    origin_scheme = 'https' if parsed_url.scheme == 'wss' else 'http'
    return urlunsplit((origin_scheme, parsed_url.netloc, '', '', ''))


class WebSocketClient:
    """WebSocket客户端 - 连接Django后端"""

    VERSION = '1.0.0'

    # 后端认证失败时 accept 握手后立即以该码关闭（wharttest_django/websocket_auth.py）
    WS_CLOSE_UNAUTHENTICATED = 4401
    # 握手层确定性认证拒绝的 HTTP 状态码（401/403/407）：配置错误，重连不会成功。
    # 其余非 101 响应（如后端重启时代理返回的 502/503）属瞬时故障，继续重连。
    AUTH_REJECT_HTTP_STATUS = {401, 403, 407}

    def __init__(self, url: str, actuator_id: str = 'default', config: Any = None):
        self.url = url
        self.actuator_id = actuator_id
        self.config = config
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.connected = False
        self.reconnect_interval = 5  # 重连间隔(秒)
        self.max_reconnect_attempts = 0  # 0表示无限重试
        self._message_handler: Optional[Callable] = None
        self._stop_event = asyncio.Event()
        # 认证被拒（close 4401 / HTTP 403）：确定性配置错误，重连不会成功
        self._auth_rejected = False
    
    def set_message_handler(self, handler: Callable[[SocketDataModel], Any]):
        """设置消息处理器"""
        self._message_handler = handler

    @staticmethod
    def _extract_close_code(e: Exception) -> int | None:
        """从 ConnectionClosed 异常中提取服务端发来的关闭码。

        服务端 close 后客户端未再发送时 rcvd 有值；优先取 rcvd，
        e.code 在 rcvd 为空时会退回 1006 造成误判。
        """
        if not isinstance(e, websockets.exceptions.ConnectionClosed):
            return None
        if e.rcvd is not None:
            return e.rcvd.code
        if e.sent is not None:
            return e.sent.code
        return None

    def _mark_auth_rejected(self, reason: str) -> None:
        """记录认证被拒并给出可操作的修复提示。"""
        if self._auth_rejected:
            return
        self._auth_rejected = True
        logger.error(
            "WS 认证失败（%s）：本执行器未配置或配置了错误的 ws_token。"
            "请在 config.toml [server] 段配置 ws_token（值同后端 UI_WS_ACTUATOR_TOKEN，"
            "可查看项目根目录 .env），或运行 run_compose.sh 自动同步。停止重连。",
            reason,
        )

    async def connect(self) -> bool:
        """建立WebSocket连接"""
        if self._auth_rejected:
            return False
        try:
            # WS 认证 token：config.ws_token（TOML [server] ws_token 或环境变量
            # WHARTTEST_ACTUATOR_WS_TOKEN），与后端 UI_WS_ACTUATOR_TOKEN 一致
            token = getattr(self.config, 'ws_token', '') or None if self.config else None
            connect_url = build_websocket_connect_url(self.url, self.actuator_id, token)
            origin = build_websocket_origin(self.url)
            connect_kwargs = {
                'ping_interval': 30,
                'ping_timeout': 10,
                'close_timeout': 10,
            }
            if origin:
                connect_kwargs['origin'] = origin

            self.websocket = await websockets.connect(
                connect_url,
                **connect_kwargs,
            )

            # 认证失败时后端 accept 握手后立即 close 4401（浏览器 WS 无法在
            # 握手前传码），HTTP 状态看不到业务码。此处借「连接后立即探测」
            # 识别：若连接已被服务端关闭则读取关闭码判定。
            close_code = await self._probe_immediate_close()
            if close_code == self.WS_CLOSE_UNAUTHENTICATED:
                self.connected = False
                self.websocket = None
                self._mark_auth_rejected("服务端关闭码 4401")
                return False

            self.connected = True
            logger.info(f"已连接到服务器: {connect_url}")

            # 连接成功后发送执行器信息
            await self._send_actuator_info()
            return True
        except websockets.exceptions.InvalidStatus as e:
            status_code = e.response.status_code
            if status_code in self.AUTH_REJECT_HTTP_STATUS:
                # 握手层认证拒绝（401/403/407）：确定性配置错误，重连不会成功
                logger.error("连接被服务端拒绝（HTTP %s）", status_code)
                self._mark_auth_rejected(f"HTTP {status_code}")
                self.connected = False
                return False
            # 其余非 101 响应（如后端重启瞬间代理返回的 502/503）：
            # 瞬时故障，保留重连
            logger.error("连接被服务端拒绝（HTTP %s），稍后重试", status_code)
            self.connected = False
            return False
        except Exception as e:
            logger.error(f"连接失败: {e}")
            self.connected = False
            return False

    async def _probe_immediate_close(self) -> int | None:
        """连接建立后短等待，探测服务端是否已立即关闭（认证拒绝模式）。

        返回服务端关闭码；连接保持打开则返回 None。
        """
        try:
            await asyncio.wait_for(self.websocket.ping(), timeout=0.5)
            return None
        except asyncio.TimeoutError:
            # ping 无响应：服务端可能已关闭但未到达，继续按打开处理，
            # 后续 send/recv 捕获 ConnectionClosed 后再判定
            return None
        except websockets.exceptions.ConnectionClosed as e:
            return self._extract_close_code(e)
    
    async def _send_actuator_info(self):
        """发送执行器信息到服务端（连接/重连/配置更新后调用）"""
        browser_type = getattr(self.config, 'browser_type', 'chromium') if self.config else 'chromium'
        max_slots = getattr(self.config, 'max_concurrent', 3) if self.config else 3
        headless = getattr(self.config, 'headless', False) if self.config else False
        actuator_info = {
            'name': getattr(self.config, 'actuator_name', None) or self.actuator_id,
            'type': 'web_ui',
            'is_open': True,
            'debug': False,
            'version': self.VERSION,
            'browser_type': browser_type,
            'default_browser': browser_type,
            'headless': headless,
            # 上报实际已安装的浏览器，供平台执行器列表/编辑弹窗选择
            'supported_browsers': self._detect_supported_browsers(),
            # 无显示环境（docker）下浏览器启动层自动回退无头，观看模式经画布帧流可用
            'supports_headed': True,
            'supports_headless': True,
            'max_slots': max_slots,
            'max_concurrent': max_slots,
            'busy_slots': 0,
            # 运行配置（供平台列表/编辑弹窗预填当前值）
            'persistent': bool(getattr(self.config, 'persistent', True)) if self.config else True,
            'launch_timeout': getattr(self.config, 'launch_timeout', 30) if self.config else 30,
            'action_timeout': getattr(self.config, 'action_timeout', 30) if self.config else 30,
            'retry_count': getattr(self.config, 'retry_count', 3) if self.config else 3,
            'step_interval': getattr(self.config, 'step_interval', 500) if self.config else 500,
            'fail_fast': bool(getattr(self.config, 'fail_fast', False)) if self.config else False,
            'log_level': getattr(self.config, 'log_level', 'INFO') if self.config else 'INFO',
            'trace_enabled': bool(getattr(self.config, 'trace_enabled', True)) if self.config else True,
            'trace_screenshots': bool(getattr(self.config, 'trace_screenshots', True)) if self.config else True,
            'trace_snapshots': bool(getattr(self.config, 'trace_snapshots', True)) if self.config else True,
            'trace_sources': bool(getattr(self.config, 'trace_sources', False)) if self.config else False,
            # 无头模式与视口（执行器维护，任务运行时作为默认值）
            'headless': headless,
            'viewport_width': getattr(self.config, 'viewport_width', 1280) if self.config else 1280,
            'viewport_height': getattr(self.config, 'viewport_height', 720) if self.config else 720,
            # 容器部署标识（供平台展示；观看模式经画布帧流，容器同样可用）
            'in_container': is_running_in_container(),
        }
        
        await self.send(SocketDataModel(
            code=ResponseCode.SUCCESS,
            msg='设置执行器信息',
            data=QueueModel(
                func_name=UiSocketEnum.SET_ACTUATOR_INFO,
                func_args=actuator_info
            )
        ))
        logger.info(f"已发送执行器信息: {actuator_info}")

    @staticmethod
    def _detect_supported_browsers() -> list[str]:
        """检测本机实际安装的 Playwright 浏览器列表"""
        try:
            from browser_installer import is_browser_installed
            installed = [
                b for b in ('chromium', 'firefox', 'webkit')
                if is_browser_installed(b)
            ]
            return installed or ['chromium']
        except Exception:
            return ['chromium']
    
    async def disconnect(self):
        """断开连接"""
        self._stop_event.set()
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        self.connected = False
        logger.info("已断开连接")
    
    async def send(self, data: SocketDataModel):
        """发送消息"""
        if not self.websocket or not self.connected:
            logger.error("未连接，无法发送消息")
            return False

        try:
            await self.websocket.send(data.model_dump_json())
            return True
        except websockets.exceptions.ConnectionClosed as e:
            close_code = self._extract_close_code(e)
            self.connected = False
            if close_code == self.WS_CLOSE_UNAUTHENTICATED:
                self._mark_auth_rejected("服务端关闭码 4401")
            else:
                logger.error(f"发送消息失败: {e}")
            return False
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            self.connected = False
            return False
    
    async def send_result(self, func_name: str, args: dict, user: Optional[str] = None,
                          task_token: Optional[str] = None):
        """发送执行结果。

        task_token：任务来源令牌回显。调用方未显式传入时自动取
        consumer 挂在 ws_client 上的当前任务令牌（execute 期间通过
        set_task_token 设置），保证所有结果消息（步骤/用例/帧）统一携带。
        """
        if task_token is None:
            task_token = getattr(self, '_outbound_task_token', None)
        if task_token and isinstance(args, dict) and not args.get('task_token'):
            args = {**args, 'task_token': task_token}
        await self.send(SocketDataModel(
            code=ResponseCode.SUCCESS,
            msg='result',
            user=user,
            is_notice=NoticeType.WEB,
            data=QueueModel(func_name=func_name, func_args=args)
        ))

    def set_task_token(self, token: Optional[str]) -> None:
        """设置当前任务来源令牌（execute 开始/结束时由 consumer 调用）。"""
        self._outbound_task_token = token
    
    async def receive_loop(self):
        """接收消息循环"""
        while not self._stop_event.is_set():
            if not self.connected or not self.websocket:
                if self._auth_rejected:
                    # 认证被拒是确定性配置错误，重连不会成功，停止循环
                    logger.error("WS 认证被拒，已停止重连。请修正 ws_token 配置后重启执行器")
                    self._stop_event.set()
                    continue
                # 尝试重连
                await self._reconnect()
                continue

            try:
                message = await asyncio.wait_for(
                    self.websocket.recv(),
                    timeout=1.0
                )
                await self._handle_message(message)
            except asyncio.TimeoutError:
                continue
            except websockets.exceptions.ConnectionClosed as e:
                close_code = self._extract_close_code(e)
                if close_code == self.WS_CLOSE_UNAUTHENTICATED:
                    self._mark_auth_rejected("服务端关闭码 4401")
                else:
                    logger.warning("连接已关闭，准备重连")
                self.connected = False
            except Exception as e:
                logger.error(f"接收消息错误: {e}")
                self.connected = False

    async def _reconnect(self):
        """重连逻辑"""
        attempts = 0
        while not self._stop_event.is_set():
            if self._auth_rejected:
                return
            attempts += 1
            logger.info(f"尝试重连 ({attempts})...")

            if await self.connect():
                return

            if self._auth_rejected:
                logger.error("WS 认证被拒，已停止重连。请修正 ws_token 配置后重启执行器")
                return

            if self.max_reconnect_attempts > 0 and attempts >= self.max_reconnect_attempts:
                logger.error("达到最大重连次数，停止重连")
                self._stop_event.set()
                return

            await asyncio.sleep(self.reconnect_interval)
    
    async def _handle_message(self, message: str):
        """处理接收到的消息"""
        try:
            data = json.loads(message)
            socket_data = SocketDataModel(**data)
            
            if self._message_handler:
                await self._message_handler(socket_data)
            else:
                logger.warning(f"收到消息但没有处理器: {socket_data.msg}")
        except json.JSONDecodeError as e:
            logger.error(f"消息JSON解析错误: {e}")
        except Exception as e:
            logger.error(f"处理消息错误: {e}")
    
    async def run(self):
        """运行客户端"""
        if not await self.connect():
            logger.error("初始连接失败")
        
        await self.receive_loop()
