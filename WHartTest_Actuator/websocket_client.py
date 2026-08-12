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
from runtime_env import should_force_headless, is_running_in_container

logger = logging.getLogger('actuator')


def build_websocket_connect_url(url: str, actuator_id: str | None = None) -> str:
    """构建带执行器 ID 的 WebSocket 连接地址。"""
    if not actuator_id:
        return url

    parsed_url = urlsplit(url)
    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed_url.query, keep_blank_values=True)
        if key not in {'id', 'user_id'}
    ]
    query_items.append(('id', actuator_id))
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
    
    def set_message_handler(self, handler: Callable[[SocketDataModel], Any]):
        """设置消息处理器"""
        self._message_handler = handler
    
    async def connect(self) -> bool:
        """建立WebSocket连接"""
        try:
            connect_url = build_websocket_connect_url(self.url, self.actuator_id)
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
            self.connected = True
            logger.info(f"已连接到服务器: {connect_url}")
            
            # 连接成功后发送执行器信息
            await self._send_actuator_info()
            return True
        except Exception as e:
            logger.error(f"连接失败: {e}")
            self.connected = False
            return False
    
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
            'supports_headed': not should_force_headless(),
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
            'log_level': getattr(self.config, 'log_level', 'INFO') if self.config else 'INFO',
            'trace_enabled': bool(getattr(self.config, 'trace_enabled', True)) if self.config else True,
            'trace_screenshots': bool(getattr(self.config, 'trace_screenshots', True)) if self.config else True,
            'trace_snapshots': bool(getattr(self.config, 'trace_snapshots', True)) if self.config else True,
            'trace_sources': bool(getattr(self.config, 'trace_sources', False)) if self.config else False,
            # 无头模式与视口（执行器维护，任务运行时作为默认值）
            'headless': headless,
            'viewport_width': getattr(self.config, 'viewport_width', 1280) if self.config else 1280,
            'viewport_height': getattr(self.config, 'viewport_height', 720) if self.config else 720,
            # 容器部署标识（docker 环境无法启用有头模式）
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
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            self.connected = False
            return False
    
    async def send_result(self, func_name: str, args: dict, user: Optional[str] = None):
        """发送执行结果"""
        await self.send(SocketDataModel(
            code=ResponseCode.SUCCESS,
            msg='result',
            user=user,
            is_notice=NoticeType.WEB,
            data=QueueModel(func_name=func_name, func_args=args)
        ))
    
    async def receive_loop(self):
        """接收消息循环"""
        while not self._stop_event.is_set():
            if not self.connected or not self.websocket:
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
            except websockets.exceptions.ConnectionClosed:
                logger.warning("连接已关闭，准备重连")
                self.connected = False
            except Exception as e:
                logger.error(f"接收消息错误: {e}")
                self.connected = False
    
    async def _reconnect(self):
        """重连逻辑"""
        attempts = 0
        while not self._stop_event.is_set():
            attempts += 1
            logger.info(f"尝试重连 ({attempts})...")
            
            if await self.connect():
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
