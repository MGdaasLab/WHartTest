"""
UI自动化 WebSocket Consumer


提供两个WebSocket端点：
- /ws/ui/web/ - 前端连接，用于接收执行结果和状态更新
- /ws/ui/actuator/ - 执行器连接，用于接收执行任务和返回结果
"""

import asyncio
import json
import logging
import os
from typing import Optional
from urllib.parse import parse_qs
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async

from .socket_models import (
    SocketDataModel, QueueModel, NoticeType, ResponseCode,
    UiSocketEnum, ExecutionTaskModel, StepResultModel, CaseResultModel
)
from wharttest_django.i18n import translate_app_text

logger = logging.getLogger('ui_automation')

# 录制器浏览器作为"本地虚拟执行器"：无可用执行器时用于步骤调试与单用例执行
RECORDER_BROWSER_ID = 'recorder-browser'
RECORDER_BROWSER_NAME = '录制器浏览器（本地）'


class SocketUserManager:
    """WebSocket用户管理器"""
    
    _web_users: dict[str, 'UiAutomationConsumer'] = {}      # 前端用户连接
    _actuator_users: dict[str, 'UiAutomationConsumer'] = {} # 执行器连接
    
    @classmethod
    def add_web_user(cls, user_id: str, consumer: 'UiAutomationConsumer'):
        cls._web_users[user_id] = consumer
        logger.info(f"Web用户连接: {user_id}, 当前连接数: {len(cls._web_users)}")
    
    @classmethod
    def remove_web_user(cls, user_id: str):
        if user_id in cls._web_users:
            del cls._web_users[user_id]
            logger.info(f"Web用户断开: {user_id}, 当前连接数: {len(cls._web_users)}")
    
    @classmethod
    def add_actuator(cls, actuator_id: str, consumer: 'UiAutomationConsumer'):
        cls._actuator_users[actuator_id] = consumer
        logger.info(f"执行器连接: {actuator_id}, 当前执行器数: {len(cls._actuator_users)}")
    
    @classmethod
    def remove_actuator(cls, actuator_id: str):
        if actuator_id in cls._actuator_users:
            del cls._actuator_users[actuator_id]
            logger.info(f"执行器断开: {actuator_id}, 当前执行器数: {len(cls._actuator_users)}")
    
    @classmethod
    def get_actuator(cls, actuator_id: Optional[str] = None) -> Optional['UiAutomationConsumer']:
        """获取执行器，如果不指定则返回第一个可用的"""
        if actuator_id and actuator_id in cls._actuator_users:
            return cls._actuator_users[actuator_id]
        if cls._actuator_users:
            return list(cls._actuator_users.values())[0]
        return None
    
    @classmethod
    def get_actuator_by_id(cls, actuator_id: str) -> Optional['UiAutomationConsumer']:
        """根据ID获取指定执行器"""
        return cls._actuator_users.get(actuator_id)
    
    @classmethod
    def get_web_user(cls, user_id: str) -> Optional['UiAutomationConsumer']:
        return cls._web_users.get(user_id)
    
    @classmethod
    def has_actuator(cls) -> bool:
        return bool(cls._actuator_users)
    
    @classmethod
    def get_actuator_count(cls) -> int:
        return len(cls._actuator_users)
    
    @classmethod
    def get_all_actuators(cls) -> list['UiAutomationConsumer']:
        return list(cls._actuator_users.values())
    
    @classmethod
    def get_actuator_info(cls, actuator_id: str) -> dict:
        """获取执行器详细信息"""
        if actuator_id in cls._actuator_users:
            consumer = cls._actuator_users[actuator_id]
            return getattr(consumer, 'actuator_info', {})
        return {}


class UiAutomationConsumer(AsyncWebsocketConsumer):
    """UI自动化WebSocket消费者"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id: Optional[str] = None
        self.is_actuator: bool = False
        self.group_name: str = 'ui_automation'
        self.actuator_info: dict = {}  # 执行器信息
        self.language: str = 'zh-Hans'
        # 录制器浏览器执行状态（步骤调试/用例执行兜底；支持关闭画布即中断）
        self._recorder_exec_task = None
        self._recorder_exec_session = None
        self._recorder_exec_user: Optional[str] = None
        # 录制器状态
        self._recorder_session_id: Optional[str] = None
        self._recorder_relay_task: Optional[asyncio.Task] = None
        self._recorder_closed: bool = False

    def _get_query_params(self) -> dict[str, list[str]]:
        query_string = self.scope.get('query_string', b'').decode('utf-8')
        if not query_string:
            return {}
        if '=' not in query_string:
            return {'id': [query_string]}
        return parse_qs(query_string)

    def _localize(self, message: str) -> str:
        return translate_app_text(message, self.language)
    
    async def connect(self):
        """建立连接"""
        import datetime
        path = self.scope.get('path', '')
        query_params = self._get_query_params()
        self.language = query_params.get('lang', ['zh-Hans'])[0]

        # 获取客户端IP
        client = self.scope.get('client', ['unknown', 0])
        client_ip = client[0] if client else 'unknown'
        
        # 根据路径判断是前端还是执行器
        if '/actuator/' in path:
            self.is_actuator = True
            self.user_id = query_params.get('id', [None])[0] or query_params.get('user_id', [None])[0]
            if not self.user_id:
                self.user_id = f"actuator_{id(self)}"
            
            # 初始化执行器信息
            self.actuator_info = {
                'id': self.user_id,
                'name': self.user_id,
                'ip': client_ip,
                'type': 'web_ui',
                'is_open': True,
                'debug': False,
                'browser_type': 'chromium',
                'headless': False,
                'supported_browsers': ['chromium'],
                'default_browser': 'chromium',
                'supports_headed': True,
                'supports_headless': True,
                'max_slots': 1,
                'busy_slots': 0,
                'connected_at': datetime.datetime.now().isoformat(),
            }
            SocketUserManager.add_actuator(self.user_id, self)
        else:
            self.is_actuator = False
            # 从用户认证获取ID
            user = self.scope.get('user')
            if user and hasattr(user, 'username'):
                self.user_id = user.username
            else:
                self.user_id = f"web_{id(self)}"
            SocketUserManager.add_web_user(self.user_id, self)
        
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        
        # 发送连接成功消息
        await self.send_json(SocketDataModel(
            code=ResponseCode.SUCCESS,
            msg=self._localize(f"{'执行器' if self.is_actuator else 'Web客户端'}连接成功"),
            user=self.user_id
        ))
        
        logger.info(f"{'执行器' if self.is_actuator else 'Web'}连接: {self.user_id}")
    
    async def disconnect(self, close_code):
        """断开连接"""
        # 清理录制器：停止帧中继并关闭录制会话（避免遗留无头浏览器进程）
        self._recorder_closed = True
        if self._recorder_relay_task and not self._recorder_relay_task.done():
            self._recorder_relay_task.cancel()
        self._recorder_relay_task = None
        if self._recorder_session_id:
            try:
                from .recorder.session_manager import recorder_manager
                recorder_manager.close(self._recorder_session_id, graceful=False)
            except Exception as exc:
                logger.warning('[recorder] disconnect cleanup error: %s', exc)
            self._recorder_session_id = None

        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        
        if self.is_actuator:
            try:
                from .actuator_registry import clear_actuator_leases
                cleared = clear_actuator_leases(self.user_id)
                if cleared:
                    logger.warning(
                        f"执行器断开，已释放 {cleared} 个 slot lease: {self.user_id}"
                    )
            except Exception as exc:
                logger.warning(f"clear leases on disconnect failed: {exc}")
            SocketUserManager.remove_actuator(self.user_id)
        else:
            SocketUserManager.remove_web_user(self.user_id)
        
        logger.info(f"{'执行器' if self.is_actuator else 'Web'}断开: {self.user_id}, code: {close_code}")
    
    async def receive(self, text_data=None, bytes_data=None):
        """接收消息"""
        if not text_data:
            return
        
        try:
            data = json.loads(text_data)
            socket_data = SocketDataModel(**data)
            
            # 如果有func_name，进行路由处理
            if socket_data.data and socket_data.data.func_name:
                await self.route_message(socket_data)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析错误: {e}")
            await self.send_json(SocketDataModel(
                code=ResponseCode.ERROR,
                msg=self._localize(f"消息格式错误: {str(e)}")
            ))
        except Exception as e:
            logger.error(f"处理消息错误: {e}", exc_info=True)
            await self.send_json(SocketDataModel(
                code=ResponseCode.ERROR,
                msg=self._localize(f"处理错误: {str(e)}")
            ))
    
    async def route_message(self, socket_data: SocketDataModel):
        """路由消息到对应处理器"""
        func_name = socket_data.data.func_name
        func_args = socket_data.data.func_args
        
        # 前端发送的执行请求 -> 转发给执行器
        if self.is_actuator:
            # 执行器返回的结果 -> 转发给前端
            handler_map = {
                UiSocketEnum.STEP_RESULT: self.handle_step_result,
                UiSocketEnum.TEST_CASE_ACK: self.handle_test_case_ack,
                UiSocketEnum.PAGE_STEP_RESULT: self.handle_page_step_result,
                UiSocketEnum.CASE_RESULT: self.handle_case_result,
                UiSocketEnum.EXEC_FRAME: self.handle_exec_frame,
                UiSocketEnum.SET_ACTUATOR_INFO: self.handle_set_actuator_info,
            }
        else:
            # 前端发送执行请求 -> 转发给执行器
            handler_map = {
                UiSocketEnum.PAGE_STEPS: self.handle_execute_page_steps,
                UiSocketEnum.TEST_CASE: self.handle_execute_test_case,
                UiSocketEnum.TEST_CASE_BATCH: self.handle_execute_batch,
                UiSocketEnum.STOP_EXECUTION: self.handle_stop_execution,
                UiSocketEnum.RECORDER_START: self.handle_recorder_start,
                UiSocketEnum.RECORDER_INPUT: self.handle_recorder_input,
                UiSocketEnum.RECORDER_ASSERT: self.handle_recorder_assert,
                UiSocketEnum.RECORDER_REMOVE_ACTION: self.handle_recorder_remove_action,
                UiSocketEnum.RECORDER_ADD_WAIT: self.handle_recorder_add_wait,
                UiSocketEnum.RECORDER_LOCATE_UPLOAD: self.handle_recorder_locate_upload,
                UiSocketEnum.RECORDER_ADD_UPLOAD: self.handle_recorder_add_upload,
                UiSocketEnum.RECORDER_SWITCH_ACCOUNT: self.handle_recorder_switch_account,
                UiSocketEnum.RECORDER_STOP: self.handle_recorder_stop,
            }
        
        handler = handler_map.get(func_name)
        if handler:
            await handler(func_args, socket_data.user)
        else:
            logger.warning(f"未知的func_name: {func_name}")
            await self.send_json(SocketDataModel(
                code=ResponseCode.ERROR,
                msg=self._localize(f"未知的操作: {func_name}")
            ))
    

    # ------------------------------------------------------------------
    # 录制器（Playwright 无头浏览器录制：帧推流 / 输入转发 / 动作中继）
    # ------------------------------------------------------------------

    async def _send_recorder(self, func_name: str, func_args: dict, msg: str = 'ok'):
        await self.send_json(SocketDataModel(
            code=ResponseCode.SUCCESS,
            msg=msg,
            user=self.user_id,
            is_notice=NoticeType.WEB,
            data=QueueModel(func_name=func_name, func_args=func_args),
        ))

    async def _send_recorder_error(self, message: str):
        await self.send_json(SocketDataModel(
            code=ResponseCode.ERROR,
            msg=message,
            user=self.user_id,
            is_notice=NoticeType.WEB,
            data=QueueModel(
                func_name=UiSocketEnum.RECORDER_STATUS,
                func_args={'status': 'error', 'message': message},
            ),
        ))

    async def handle_recorder_start(self, args, user):
        """绑定录制会话并启动帧中继任务。args: {session_id}"""
        from .recorder.session_manager import recorder_manager

        session_id = args.get('session_id')
        session = recorder_manager.get(session_id)
        meta = recorder_manager.get_meta(session_id)
        if session is None or meta is None:
            await self._send_recorder_error('录制会话不存在或已结束')
            return
        # WS 层通常为匿名 web_xxx，无法精确匹配用户时仅依赖 uuid 防猜测
        if not self.user_id.startswith('web_') and meta.user_id != self.user_id:
            await self._send_recorder_error('无权访问该录制会话')
            return

        self._recorder_session_id = session_id
        if self._recorder_relay_task is None or self._recorder_relay_task.done():
            self._recorder_closed = False
            self._recorder_relay_task = asyncio.create_task(self._recorder_relay(session_id))
        await self._send_recorder(UiSocketEnum.RECORDER_STATUS, {'status': 'started'})

    async def _recorder_relay(self, session_id: str):
        """帧/动作中继：轮询会话事件队列并推给前端（丢帧合并，不积压）。"""
        from .recorder.session_manager import recorder_manager

        while not self._recorder_closed:
            try:
                session = recorder_manager.get(session_id)
                if session is None:
                    await self._send_recorder(
                        UiSocketEnum.RECORDER_STATUS, {'status': 'ended', 'message': '录制会话已结束'}
                    )
                    break
                frame = session.take_latest_frame()
                if frame is not None:
                    await self._send_recorder(UiSocketEnum.RECORDER_FRAME, {'frame': frame})
                for ev in session.drain_events():
                    if ev.get('type') == 'actions':
                        await self._send_recorder(UiSocketEnum.RECORDER_ACTION, {'action': ev.get('data')})
                    elif ev.get('type') == 'status':
                        await self._send_recorder(UiSocketEnum.RECORDER_STATUS, ev.get('data') or {})
            except Exception as exc:
                logger.warning('[recorder] relay error: %s', exc)
            await asyncio.sleep(0.02)

    async def handle_recorder_input(self, args, user):
        """转发前端输入事件到录制进程（fire-and-forget）。"""
        from .recorder.session_manager import recorder_manager

        session = recorder_manager.get(self._recorder_session_id or '')
        if session is None:
            await self._send_recorder_error('录制会话不存在或已结束')
            return
        try:
            session.notify('input', args)
        except Exception as exc:
            await self._send_recorder_error(f'输入转发失败: {exc}')

    async def handle_recorder_assert(self, args, user):
        """请求录制进程记录断言动作（转发模式/坐标/期望值）。"""
        from .recorder.session_manager import recorder_manager

        session = recorder_manager.get(self._recorder_session_id or '')
        if session is None:
            await self._send_recorder_error('录制会话不存在或已结束')
            return
        try:
            result = await sync_to_async(session.request)(
                'assert',
                {
                    'mode': args.get('mode') or 'visible',
                    'x': args.get('x'),
                    'y': args.get('y'),
                    'value': args.get('value') or '',
                },
                timeout=20,
            )
        except Exception as exc:
            await self._send_recorder_error(f'断言记录失败: {exc}')
            return
        state = result.get('state') or {}
        await self._send_recorder(
            UiSocketEnum.RECORDER_STATUS,
            {'status': 'asserted', 'action': state.get('action')},
            msg='断言已记录',
        )

    async def handle_recorder_add_wait(self, args, user):
        """录制位置插入等待动作。args: {seconds}"""
        from .recorder.session_manager import recorder_manager

        session = recorder_manager.get(self._recorder_session_id or '')
        if session is None:
            await self._send_recorder_error('录制会话不存在或已结束')
            return
        try:
            await sync_to_async(session.request)(
                'add_wait', {'seconds': args.get('seconds') or 3}, timeout=10,
            )
        except Exception as exc:
            await self._send_recorder_error(f'插入等待失败: {exc}')

    async def handle_recorder_locate_upload(self, args, user):
        """定位上传控件：传入画布坐标，返回可执行选择器。"""
        from .recorder.session_manager import recorder_manager

        session = recorder_manager.get(self._recorder_session_id or '')
        if session is None:
            await self._send_recorder_error('录制会话不存在或已结束')
            return
        try:
            result = await sync_to_async(session.request)(
                'locate_upload',
                {'x': args.get('x'), 'y': args.get('y')},
                timeout=15,
            )
        except Exception as exc:
            await self._send_recorder_error(f'上传控件定位失败: {exc}')
            return
        state = result.get('state') or {}
        await self._send_recorder(
            UiSocketEnum.RECORDER_STATUS,
            {'status': 'upload_located', 'selector': state.get('selector')},
            msg='上传控件已定位',
        )

    async def handle_recorder_switch_account(self, args, user):
        """无痕切换账号：销毁当前录制上下文并新开干净上下文。

        切换账号不点目标系统"退出登录"（退出会在服务端作废旧账号会话，
        使已保存的登录态失效），而是整个上下文重建——旧账号会话原样保留。
        """
        from .recorder.session_manager import recorder_manager, RecorderSessionError

        session = recorder_manager.get(self._recorder_session_id or '')
        if session is None:
            await self._send_recorder_error('录制会话不存在或已结束')
            return
        try:
            result = await sync_to_async(session.request)(
                'reset_context',
                {'url': args.get('url') or ''},
                timeout=60,
            )
        except Exception as exc:
            await self._send_recorder_error(f'切换账号失败: {exc}')
            return
        if not (isinstance(result, dict) and result.get('ok')):
            await self._send_recorder_error(
                (result or {}).get('error') or '切换账号失败'
            )
            return
        await self._send_recorder(
            UiSocketEnum.RECORDER_STATUS,
            {'status': 'context_reset', 'url': args.get('url') or ''},
        )

    async def handle_recorder_add_upload(self, args, user):
        """插入上传动作：selector + 平台文件 file_id。"""
        from .recorder.session_manager import recorder_manager

        session = recorder_manager.get(self._recorder_session_id or '')
        if session is None:
            await self._send_recorder_error('录制会话不存在或已结束')
            return
        try:
            await sync_to_async(session.request)(
                'add_upload',
                {
                    'selector': args.get('selector'),
                    'file_id': args.get('file_id'),
                    'file_name': args.get('file_name'),
                },
                timeout=10,
            )
        except Exception as exc:
            await self._send_recorder_error(f'插入上传动作失败: {exc}')

    async def handle_recorder_stop(self, args, user):
        """停止帧中继（结束录制走 REST finish）。"""
        self._recorder_closed = True
        if self._recorder_relay_task and not self._recorder_relay_task.done():
            self._recorder_relay_task.cancel()
        self._recorder_relay_task = None
        self._recorder_session_id = None
        await self._send_recorder(UiSocketEnum.RECORDER_STATUS, {'status': 'stopped'})

    async def handle_recorder_remove_action(self, args, user):
        """删除已录动作（录制中误触时手动清理）。args: {seq}"""
        from .recorder.session_manager import recorder_manager

        session = recorder_manager.get(self._recorder_session_id or '')
        if session is None:
            await self._send_recorder_error('录制会话不存在或已结束')
            return
        try:
            await sync_to_async(session.request)(
                'remove_action', {'seq': args.get('seq')}, timeout=10,
            )
        except Exception as exc:
            await self._send_recorder_error(f'删除操作失败: {exc}')

    async def _load_env_config(self, env_config_id):
        """Load UiEnvironmentConfig by id (async)."""
        if not env_config_id:
            return None
        from .models import UiEnvironmentConfig

        def _fetch():
            return UiEnvironmentConfig.objects.filter(id=env_config_id).first()

        return await sync_to_async(_fetch)()

    async def _prepare_task_dispatch(self, args: dict):
        """Resolve effective_runtime + select actuator. Returns (args, actuator, error)."""
        from . import actuator_registry

        args = dict(args or {})
        run_options = args.get("run_options") or {}
        preferred = args.get("actuator_id") or None
        env_config_id = args.get("env_config_id")

        env = await self._load_env_config(env_config_id)
        effective, selected, err = actuator_registry.resolve_and_select(
            env=env,
            run_options=run_options if run_options else None,
            preferred_actuator_id=preferred,
        )
        if err:
            return args, None, err

        actuator = actuator_registry.get_raw_consumer(selected["id"])
        if actuator is None:
            return args, None, f"执行器 {selected['id']} 不在线"

        args["actuator_id"] = selected["id"]
        args["effective_runtime"] = effective
        # Slot reservation is done by callers with the correct task size.
        args["_selected_actuator_for_slots"] = selected["id"]
        if effective.get("env_config_id") and not args.get("env_config_id"):
            args["env_config_id"] = effective["env_config_id"]
        return args, actuator, ""

    @staticmethod
    def _force_batch_headless(args: dict):
        """批量执行一律无头：并发多浏览器、不展示执行画面（执行器优先采用
        后端下发的 effective_runtime，headless 需同时覆盖 run_options 双保险）。
        单用例/单页面步骤执行不强制：是否弹画布由执行器无头开关决定
        （关闭无头=观看模式，执行画面经画布帧流直播）。"""
        run_options = args.get("run_options")
        if isinstance(run_options, dict):
            run_options["headless"] = True
        effective = args.get("effective_runtime")
        if isinstance(effective, dict) and effective.get("browser"):
            effective["headless"] = True





    @staticmethod
    def _sanitize_result_args(args: dict) -> dict:
        """Copy result args for frontend broadcast without db secrets."""
        if not isinstance(args, dict):
            return {}
        return dict(args)

    @staticmethod
    def _public_effective(effective):
        return effective or {}

    def _release_actuator_slots(self, args: dict, count: int = 1) -> None:
        from .actuator_registry import adjust_busy_slots, resolve_actuator_id_for_result
        if count <= 0:
            return
        actuator_id = args.get("actuator_id")
        if not actuator_id and isinstance(args.get("effective_runtime"), dict):
            actuator_id = args.get("effective_runtime", {}).get("actuator_id")
        if not actuator_id and isinstance(args.get("environment"), dict):
            actuator_id = args.get("environment", {}).get("actuator_id")
        if not actuator_id and getattr(self, "is_actuator", False):
            # 结果由执行器自己回传，当前连接即持有槽位的执行器
            actuator_id = self.user_id
        if not actuator_id:
            # 兜底：按预留时写入 lease 的 case_id/batch_id 元数据反查
            actuator_id = resolve_actuator_id_for_result(args)
        if not actuator_id:
            return
        try:
            adjust_busy_slots(str(actuator_id), -count)
        except Exception as exc:
            logger.warning(f"adjust busy_slots -{count} failed: {exc}")

    def _reserve_actuator_slots(self, args: dict, count: int = 1) -> tuple[bool, str]:
        from . import actuator_registry
        actuator_id = args.get("actuator_id") or args.get("_selected_actuator_for_slots")
        if not actuator_id or count <= 0:
            return True, ""
        ttl = None
        effective = args.get("effective_runtime") if isinstance(args.get("effective_runtime"), dict) else {}
        try:
            timeout_ms = int(effective.get("timeout") or 0)
        except (TypeError, ValueError):
            timeout_ms = 0
        if timeout_ms > 0:
            # headroom for multi-step tasks; clamp 15min..6h
            ttl = max(15 * 60, min(int(timeout_ms / 1000) * 3 * max(count, 1), 6 * 60 * 60))
        ok, err = actuator_registry.reserve_slots(
            str(actuator_id),
            count,
            ttl_seconds=ttl,
            meta={
                "case_id": args.get("case_id"),
                "batch_id": args.get("batch_id"),
                "case_ids": args.get("case_ids"),
            },
        )
        if not ok:
            logger.warning(f"reserve slots failed: {err}")
            return False, err
        return True, ""

    # ------------------------------------------------------------------
    # 录制器浏览器（本地虚拟执行器）：无执行器时步骤调试 / 单用例执行
    # ------------------------------------------------------------------

    def _recorder_exec_result_name(self, kind: str) -> str:
        return UiSocketEnum.PAGE_STEP_RESULT if kind == 'page_steps' else UiSocketEnum.CASE_RESULT

    async def _stop_recorder_trace_safe(self, session, kind: str) -> Optional[str]:
        """异常/中断路径的 trace 兜底：停止并落盘 zip，入库后返回相对路径；失败静默返回 None。"""
        if session is None or kind == 'page_steps':
            return None
        try:
            resp = await asyncio.to_thread(session.request, 'stop_trace', {}, 30)
            local_path = (resp.get('state') or {}).get('trace_path')
            if local_path and os.path.exists(local_path):
                stored = await self._upload_recorder_trace(local_path, self._recorder_exec_user or '')
                return stored
        except Exception:
            pass
        return None

    @staticmethod
    def _case_step_results_payload(all_step_results: list) -> list[dict]:
        """把录制器逐步结果转成执行记录 step_results 形状（与成功路径同构）。"""
        out: list[dict] = []
        for entry in all_step_results or []:
            try:
                duration = round(float(entry.get('duration') or 0), 2)
            except (TypeError, ValueError):
                duration = 0
            out.append({
                'step_id': f"group{entry.get('group')}_{entry.get('index')}",
                'status': entry.get('status') or 'success',
                'message': entry.get('message') or '',
                'description': entry.get('description') or entry.get('ope_key') or '',
                'duration': duration,
                'element_found': (entry.get('status') == 'success'),
                'screenshot': entry.get('screenshot'),
            })
        return out

    async def _upload_recorder_trace(self, local_path: str, user: str) -> Optional[str]:
        """把录制器产生的 trace.zip 收进平台媒体目录（与 traces/upload 接口同规则）。

        Django 与录制 Node 进程同机（node 由 Django spawn），直接落盘即可，
        无需回环 HTTP。返回数据库存储的相对路径 ui_traces/{date}/{file}.zip。
        """
        import os
        import shutil
        import uuid
        from datetime import datetime

        from django.conf import settings

        try:
            date_dir = datetime.now().strftime('%Y%m%d')
            upload_dir = os.path.join(settings.MEDIA_ROOT, 'ui_traces', date_dir)
            os.makedirs(upload_dir, exist_ok=True)
            filename = f"{uuid.uuid4().hex[:12]}.zip"
            target = os.path.join(upload_dir, filename)
            shutil.move(local_path, target)
            relative = f"ui_traces/{date_dir}/{filename}"
            logger.info('[recorder-exec] trace 已入库: %s', relative)
            return relative
        except Exception as exc:
            logger.warning('[recorder-exec] trace 入库失败: %s', exc)
            return None

    async def _resolve_executor(self, args: dict, user: str) -> tuple[Optional[int], str]:
        """解析执行记录的执行人 (id, username)。

        优先取前端任务参数里的 executor_id/executor_name（auth store 的当前
        登录用户——WS 连接本身匿名（user_id 形如 web_xxx），不可靠）；
        兜底按连接 user 名查库。
        """
        from django.contrib.auth.models import User

        async def _lookup(uid=None, uname=None):
            try:
                def _q():
                    qs = User.objects.all()
                    if uid is not None:
                        qs = qs.filter(id=int(uid))
                    elif uname:
                        qs = qs.filter(username=uname)
                    else:
                        return None
                    return qs.values_list('id', 'username').first()
                return await sync_to_async(_q)()
            except Exception as exc:
                logger.warning('[recorder-exec] 解析执行人失败: %s', exc)
                return None

        exec_id = args.get('executor_id')
        exec_name = str(args.get('executor_name') or '').strip()
        if exec_id or exec_name:
            found = await _lookup(uid=exec_id, uname=exec_name or None)
            if found:
                return found[0], found[1]
        # 回退：连接名（登录用户名或匿名）
        found = await _lookup(uname=None if user.startswith('web_') else user)
        if found:
            return found[0], found[1]
        return None, (exec_name or user)

    async def _resolve_executor_id(self, user: str) -> Optional[int]:
        """按用户名解析执行人 User.id（兼容匿名连接返回 None）。"""
        exec_id, _ = await self._resolve_executor({}, user)
        return exec_id

    async def _recorder_exec_error(
        self,
        kind: str,
        args: dict,
        user: str,
        message: str,
        *,
        steps: Optional[list[dict]] = None,
        trace_path: Optional[str] = None,
        total_steps: int = 0,
        passed_steps: int = 0,
        failed_steps: int = 0,
    ):
        """录制器执行失败：按对应结果消息形状直推发起用户。

        case 模式同时落一条失败执行记录（对齐执行器路径）——否则录制器浏览器
        执行失败时执行记录列表无任何痕迹。透传已收集的步骤结果与 trace，
        执行记录详情可查看失败现场。
        """
        if kind == 'page_steps':
            payload = {
                'page_step_id': args.get('page_step_id'),
                'status': 'failed',
                'message': message,
                'total_steps': total_steps, 'passed_steps': passed_steps, 'failed_steps': failed_steps,
            }
        else:
            exec_id, exec_name = await self._resolve_executor(args, user)
            payload = {
                'case_id': args.get('case_id'),
                'execution_request_id': args.get('execution_request_id'),
                'status': 'failed',
                'message': message,
                'steps': steps or [],
                'passed_steps': passed_steps,
                'total_steps': total_steps,
                'failed_steps': failed_steps or (len(steps) if steps else 0),
                'executor_name': exec_name,
                'executor_id': exec_id,
                'trigger_type': 'manual',
                'trace_path': trace_path,
                'log': message,
            }
            try:
                await self.save_execution_result(dict(payload))
            except Exception as exc:
                logger.warning('[recorder-exec] 失败执行记录落库失败: %s', exc)
        web_user = SocketUserManager.get_web_user(user)
        if web_user:
            await web_user.send_json(SocketDataModel(
                code=ResponseCode.SUCCESS,
                msg='exec_result',
                user=user,
                is_notice=NoticeType.WEB,
                data=QueueModel(func_name=self._recorder_exec_result_name(kind), func_args=payload),
            ))

    async def _recorder_exec_frame_relay(self, session, user: str):
        """执行期间把浏览器画面帧直推发起用户（与录制画布同一事件）。"""
        while True:
            await asyncio.sleep(0.02)
            try:
                frame = session.take_latest_frame()
                if not frame:
                    continue
                web_user = SocketUserManager.get_web_user(user)
                if web_user:
                    await web_user.send_json(SocketDataModel(
                        code=ResponseCode.SUCCESS,
                        msg='recorder_frame',
                        user=user,
                        is_notice=NoticeType.WEB,
                        data=QueueModel(
                            func_name=UiSocketEnum.RECORDER_FRAME,
                            func_args={'frame': frame},
                        ),
                    ))
            except Exception as exc:
                logger.debug('[recorder-exec] 帧转发暂停: %s', exc)
                return

    async def _execute_via_recorder(self, kind: str, args: dict, user: str):
        logger.info(
            '[recorder-exec] 开始执行 kind=%s user=%s args=%s',
            kind, user, {k: args.get(k) for k in ('page_step_id', 'case_id', 'env_config_id')},
        )
        """用录制器浏览器执行步骤调试 / 单用例执行（无执行器兜底）。

        - 复用录制器 run_steps 执行引擎（与前置步骤同款），每组先 goto 再跑动作；
        - 执行过程向发起用户直播画面帧（u_recorder_frame）；
        - 结果按 u_page_step_result / u_case_result 形状回传（页面步骤更新状态、
          用例落 UiExecutionRecord）。
        """
        # 记录发起用户：异常兜底路径（_stop_recorder_trace_safe）trace 入库时使用
        self._recorder_exec_user = user
        from .views import _resolve_recorder_skill_dir, _serialize_page_step_for_recorder, _auth_state_by_id
        from .recorder.session_manager import recorder_manager, RecorderSessionError
        from .models import UiEnvironmentConfig, UiPageSteps, UiTestCase, UiCaseStepsDetailed
        import time as _time

        env_config = None
        env_config_id = args.get('env_config_id')
        if env_config_id:
            env_config = await sync_to_async(
                UiEnvironmentConfig.objects.filter(id=env_config_id).first
            )()
        groups = []
        project_id = 0
        if kind == 'page_steps':
            page_step = await sync_to_async(
                UiPageSteps.objects.filter(id=args.get('page_step_id')).first
            )()
            if page_step is None:
                await self._recorder_exec_error(kind, args, user, '页面步骤不存在')
                return
            project_id = page_step.project_id or 0
            groups = [page_step]
        else:
            case = await sync_to_async(
                UiTestCase.objects.filter(id=args.get('case_id')).first
            )()
            if case is None:
                await self._recorder_exec_error(kind, args, user, '测试用例不存在')
                return
            project_id = case.project_id or 0
            case_steps = await sync_to_async(lambda: list(
                UiCaseStepsDetailed.objects.filter(test_case=case)
                .select_related('page_step', 'page_step__page')
                .order_by('case_sort')
            ))()
            groups = [cs.page_step for cs in case_steps if cs.page_step is not None]
            if not groups:
                await self._recorder_exec_error(kind, args, user, '用例没有可执行的页面步骤')
                return

        # 仅注入显式绑定的登录态（取首个步骤的绑定）；未绑定 → 无痕启动
        storage_state = None
        first_auth_id = getattr(groups[0], 'auth_state_id', None) if groups else None
        if first_auth_id:
            bound = await sync_to_async(_auth_state_by_id)(first_auth_id)
            if bound is not None:
                storage_state = bound.state_json

        try:
            skill_dir = _resolve_recorder_skill_dir()
        except Exception as exc:
            logger.error('[recorder-exec] 解析 skill 目录异常: %s', exc, exc_info=True)
            await self._recorder_exec_error(kind, args, user, f'录制器浏览器不可用: {exc}')
            return
        logger.info('[recorder-exec] skill_dir=%s groups=%d', skill_dir, len(groups))
        if not skill_dir:
            await self._recorder_exec_error(kind, args, user, '录制器浏览器不可用：未找到 playwright skill 目录')
            return

        # 预加载每组导航地址（页面外键在异步上下文中不可触发）
        from .models import UiPage as _UiPage

        def _load_group_urls(page_steps) -> list:
            urls = []
            for ps in page_steps:
                url = ''
                if env_config is not None and env_config.base_url:
                    url = env_config.base_url
                elif ps.page_id:
                    page_obj = _UiPage.objects.filter(id=ps.page_id).values_list('url', flat=True).first()
                    url = page_obj or ''
                urls.append(str(url or '').strip())
            return urls

        group_bases = await sync_to_async(_load_group_urls)(groups)
        start_url = group_bases[0] if group_bases else ''

        session = None
        frame_task = None
        started = _time.time()
        # 失败/异常路径透传用的执行统计（在 try 外预声明，避免会话启动失败时 NameError）
        total_steps = 0
        passed_steps = 0
        failed_steps = 0
        all_step_results: list[dict] = []
        trace_local_path: Optional[str] = None
        # 执行任务引用已在入口赋值（生成时），前端关闭执行画布时据此中断
        try:
            logger.info('[recorder-exec] 创建录制会话 user=%s project=%s', user, project_id)
            session = recorder_manager.create_session(
                user_id=user, project_id=project_id, skill_dir=skill_dir,
            )
            self._recorder_exec_session = session
            session.start(timeout=120)
            logger.info('[recorder-exec] 会话已启动 %s url=%s', session.session_id, start_url or 'about:blank')
            # start 不带 url 导航（about:blank 起步）：首个组的前置 goto 负责导航。
            # 若 start 直接导航到 start_url，紧跟的组前置 goto 同址重复导航会与
            # 站点自身跳转竞争，导致 net::ERR_ABORTED 中止（执行器路径无此问题）
            start_params = {
                'url': 'about:blank',
                'viewport': {'width': 1400, 'height': 900},
            }
            if storage_state:
                start_params['storage_state'] = storage_state
            # 同步 request 移出事件循环（to_thread），执行期间帧转发/中断仍可响应
            await asyncio.to_thread(session.request, 'start', start_params, 90)
            logger.info('[recorder-exec] start 请求完成，开始逐组执行')
            # case 模式采集 Playwright trace：执行前开启，结束后 stop 落盘 zip
            if kind != 'page_steps':
                try:
                    await asyncio.to_thread(session.request, 'start_trace', {'name': f'case_{args.get("case_id")}'}, 15)
                except Exception as exc:
                    logger.warning('[recorder-exec] 开启 trace 失败（不影响执行）: %s', exc)
            # 回执生效运行时（headless=false 观看模式）→ 前端据此自动打开执行画布
            web_user = SocketUserManager.get_web_user(user)
            if web_user:
                await web_user.send_json(SocketDataModel(
                    code=ResponseCode.SUCCESS,
                    msg='effective_runtime',
                    user=user,
                    is_notice=NoticeType.WEB,
                    data=QueueModel(
                        func_name='effective_runtime',
                        func_args={
                            'headless': False,
                            'actuator_id': RECORDER_BROWSER_ID,
                            'executor_name': RECORDER_BROWSER_NAME,
                            'env_config_id': env_config_id,
                        },
                    ),
                ))
            frame_task = asyncio.ensure_future(self._recorder_exec_frame_relay(session, user))

            message = ''
            group_index = 0
            # 组间登录态切换与执行器同语义："向上匹配"——未绑定步骤沿用上一个
            # 已绑定步骤的登录态（不清理），仅生效登录态变化时才切换上下文
            pending_auth = getattr(groups[0], 'auth_state_id', None) if groups else None
            current_auth = pending_auth  # start 时按首个生效登录态注入
            for page_step in groups:
                group_index += 1
                if getattr(page_step, 'auth_state_id', None):
                    pending_auth = getattr(page_step, 'auth_state_id', None) or None
                if pending_auth != current_auth:
                    group_storage = None
                    if pending_auth:
                        bound = await sync_to_async(_auth_state_by_id)(pending_auth)
                        if bound is not None:
                            group_storage = bound.state_json
                    switch_resp = await asyncio.to_thread(
                        session.request, 'switch_context', {'storage_state': group_storage}, 60,
                    )
                    if not (isinstance(switch_resp, dict) and switch_resp.get('ok')):
                        raise RecorderSessionError(
                            (switch_resp or {}).get('error') or f'第 {group_index} 组切换登录态失败'
                        )
                    current_auth = pending_auth
                steps = await sync_to_async(_serialize_page_step_for_recorder)(page_step)
                logger.info(
                    '[recorder-exec] 第 %d/%d 组执行 page_step=%s steps=%d base_url=%s',
                    group_index, len(groups), page_step.id, len(steps), group_bases[group_index - 1],
                )
                # 步骤统计只算库里存储的操作步骤；goto 仅导航用不计数
                #（与执行器 total_steps 口径一致：sum(len(ps.steps))）
                group_step_count = len(steps)
                base_url = group_bases[group_index - 1]
                if base_url:
                    steps = [{
                        'ope_key': 'goto',
                        'ope_value': {'url': base_url},
                        'step_type': 0,
                        'element': None,
                    }] + steps
                total_steps += group_step_count
                resp = await asyncio.to_thread(
                    session.request, 'run_steps', {'steps': steps}, 180,
                )
                resp_state = resp.get('state', {}) if isinstance(resp, dict) else {}
                # 收集本组逐步结果（标注组序号，供执行记录展示）
                for entry in (resp_state.get('step_results') or []):
                    entry['group'] = group_index
                    all_step_results.append(entry)
                logger.info(
                    '[recorder-exec] 第 %d 组完成 ok=%s failed=%s',
                    group_index, resp.get('ok'), resp_state.get('failed'),
                )
                if not resp.get('ok') or resp_state.get('failed'):
                    failed_steps += group_step_count
                    # 失败信息在 state.error（cmdRunSteps 失败时返回 ok:true + failed 标记，
                    # 保证 state.step_results 能随响应带回）
                    message = resp_state.get('error') or f'第 {group_index} 组步骤执行失败'
                    break
                passed_steps += group_step_count
                await asyncio.sleep(0.1)

            duration = round(_time.time() - started, 2)
            status = 'success' if failed_steps == 0 else 'failed'
            # 停止 trace 落盘 zip，并入库（与执行器路径一致）；同时收集页面 JS 错误
            page_errors: list[str] = []
            trace_local_path: Optional[str] = None
            if kind != 'page_steps':
                try:
                    stop_resp = await asyncio.to_thread(session.request, 'stop_trace', {}, 60)
                    trace_local_path = (stop_resp.get('state') or {}).get('trace_path')
                    page_errors = list((stop_resp.get('state') or {}).get('page_errors') or [])
                except Exception as exc:
                    logger.warning('[recorder-exec] 停止 trace 失败: %s', exc)
                if trace_local_path and os.path.exists(trace_local_path):
                    try:
                        uploaded = await self._upload_recorder_trace(trace_local_path, user)
                        if uploaded:
                            trace_local_path = uploaded
                    except Exception as exc:
                        logger.warning('[recorder-exec] trace 上传失败: %s', exc)
                else:
                    trace_local_path = None
            # 执行日志与执行器同款格式："用例执行成功: 通过 5/5 (捕获 N 个页面 JS 错误: …)"
            page_error_note = ''
            if page_errors:
                page_error_note = f" (捕获 {len(page_errors)} 个页面 JS 错误: {'; '.join(page_errors[:3])})"
            if status == 'success':
                message = f"用例执行成功: 通过 {passed_steps}/{total_steps}{page_error_note}"
            elif message:
                message = f"用例执行失败: 通过 {passed_steps}/{total_steps}{page_error_note}; {message}"
            else:
                message = f"用例执行失败: 通过 {passed_steps}/{total_steps}{page_error_note}"
            # 汇总每组的逐步结果（录制器 run_steps 返回，含失败现场截图），
            # 存入执行记录 step_results——与执行器路径展示对齐
            case_step_results: list[dict] = []
            if kind != 'page_steps':
                for entry in all_step_results:
                    try:
                        step_duration = round(float(entry.get('duration') or 0), 2)
                    except (TypeError, ValueError):
                        step_duration = 0
                    case_step_results.append({
                        'step_id': f"group{entry.get('group')}_{entry.get('index')}",
                        'status': entry.get('status') or 'success',
                        'message': entry.get('message') or '',
                        'description': entry.get('description') or entry.get('ope_key') or '',
                        'duration': step_duration,
                        'element_found': (entry.get('status') == 'success'),
                        'screenshot': entry.get('screenshot'),
                    })
            if kind == 'page_steps':
                result_args = {
                    'page_step_id': groups[0].id,
                    'status': status,
                    'message': message,
                    'total_steps': total_steps,
                    'passed_steps': passed_steps,
                    'failed_steps': failed_steps,
                    'duration': duration,
                    'steps': [],
                }
                if groups[0].id:
                    await self.update_page_step_status(
                        groups[0].id, 2 if status == 'success' else 3, result_args,
                    )
                web_user = SocketUserManager.get_web_user(user)
                if web_user:
                    await web_user.send_json(SocketDataModel(
                        code=ResponseCode.SUCCESS,
                        msg='exec_result', user=user, is_notice=NoticeType.WEB,
                        data=QueueModel(func_name=UiSocketEnum.PAGE_STEP_RESULT, func_args=result_args),
                    ))
            else:
                # 执行人取前端任务参数携带的当前登录用户（WS 连接匿名不可靠）
                exec_id, exec_name = await self._resolve_executor(args, user)
                result_args = {
                    'case_id': args.get('case_id'),
                    'execution_request_id': args.get('execution_request_id'),
                    'status': status,
                    'message': message,
                    'duration': duration,
                    # 逐步执行结果（含失败截图 base64），落执行记录 step_results
                    'steps': case_step_results,
                    # 前端用例结果提示展示 通过/总数（与执行器 CaseResultModel 字段对齐）
                    'passed_steps': passed_steps,
                    'total_steps': total_steps,
                    'failed_steps': failed_steps,
                    'executor_name': exec_name,
                    'executor_id': exec_id,
                    'trigger_type': 'manual',
                    # Playwright trace.zip 的平台存储相对路径（与执行器路径一致）
                    'trace_path': trace_local_path,
                }
                await self.save_execution_result(result_args)
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        'type': 'broadcast_result',
                        'data': {
                            'func_name': UiSocketEnum.CASE_RESULT,
                            'args': self._sanitize_result_args(result_args),
                            'user': user,
                        },
                    },
                )
        except asyncio.CancelledError:
            # 前端关闭画布触发的主动中断：作为正常终止回传"已中断"，
            # 不重抛（否则取消异常穿透到 ASGI 应用层）
            trace_stored = await self._stop_recorder_trace_safe(session, kind)
            await self._recorder_exec_error(
                kind, args, user, '执行已中断',
                steps=self._case_step_results_payload(all_step_results),
                trace_path=trace_stored,
                total_steps=total_steps, passed_steps=passed_steps,
                failed_steps=failed_steps or (len(all_step_results) if kind != 'page_steps' else 0),
            )
        except RecorderSessionError as exc:
            trace_stored = await self._stop_recorder_trace_safe(session, kind)
            await self._recorder_exec_error(
                kind, args, user, f'录制器浏览器执行失败: {exc}',
                steps=self._case_step_results_payload(all_step_results),
                trace_path=trace_stored,
                total_steps=total_steps, passed_steps=passed_steps,
                failed_steps=failed_steps or (len(all_step_results) if kind != 'page_steps' else 0),
            )
        except Exception as exc:
            logger.error('[recorder-exec] 执行异常: %s', exc, exc_info=True)
            trace_stored = await self._stop_recorder_trace_safe(session, kind)
            await self._recorder_exec_error(
                kind, args, user, f'录制器浏览器执行异常: {exc}',
                steps=self._case_step_results_payload(all_step_results),
                trace_path=trace_stored,
                total_steps=total_steps, passed_steps=passed_steps,
                failed_steps=failed_steps or (len(all_step_results) if kind != 'page_steps' else 0),
            )
        finally:
            self._recorder_exec_task = None
            self._recorder_exec_session = None
            if frame_task is not None:
                frame_task.cancel()
                try:
                    await frame_task
                except BaseException:
                    # CancelledError 继承自 BaseException，须显式吞掉，
                    # 否则取消异常会穿透到 ASGI 应用层（uvicorn Exception in ASGI）
                    pass
            if session is not None:
                try:
                    recorder_manager.close(session.session_id, graceful=False)
                except Exception:
                    pass

    async def handle_execute_page_steps(self, args: dict, user: str):
        """处理执行页面步骤请求"""
        if args.get('actuator_id') == RECORDER_BROWSER_ID:
            # 前端消息不带 user 字段：用连接注册键定位回执/帧的目标。
            # 独立任务执行：接收循环保持空闲，前端关闭画布的停止请求才能被及时处理
            self._recorder_exec_task = asyncio.ensure_future(self._execute_via_recorder('page_steps', args, user or self.user_id))
            return
        args, actuator, err = await self._prepare_task_dispatch(args)
        if err:
            await self.send_json(SocketDataModel(
                code=ResponseCode.ERROR,
                msg=self._localize(err),
                data=QueueModel(
                    func_name=UiSocketEnum.PAGE_STEPS,
                    func_args={"page_step_id": args.get("page_step_id"), "error": err},
                ),
            ))
            return

        ok, err = self._reserve_actuator_slots(args, 1)
        if not ok:
            await self.send_json(SocketDataModel(
                code=ResponseCode.ERROR,
                msg=err or self._localize("执行器空闲 slot 不足"),
                data=QueueModel(
                    func_name=UiSocketEnum.PAGE_STEPS,
                    func_args={"page_step_id": args.get("page_step_id"), "error": err or ""},
                ),
            ))
            return

        try:
            await actuator.send_json(SocketDataModel(
                code=ResponseCode.SUCCESS,
                msg="execute",
                user=self.user_id,
                is_notice=NoticeType.ACTUATOR,
                data=QueueModel(
                    func_name=UiSocketEnum.PAGE_STEPS,
                    func_args=args
                )
            ))
        except Exception:
            self._release_actuator_slots(args, 1)
            raise

        await self.send_json(SocketDataModel(
            code=ResponseCode.SUCCESS,
            msg=self._localize("任务已发送给执行器"),
            data=QueueModel(
                func_name="effective_runtime",
                func_args=self._public_effective(args.get("effective_runtime"))
            )
        ))

    async def _send_test_case_ack(self, args: dict):
        await self.send_json(SocketDataModel(
            code=ResponseCode.SUCCESS,
            msg=self._localize("任务已发送给执行器"),
            data=QueueModel(
                func_name=UiSocketEnum.TEST_CASE_ACK,
                func_args={
                    "case_id": args.get("case_id"),
                    "execution_request_id": args.get("execution_request_id"),
                    "actuator_id": args.get("actuator_id"),
                    "env_config_id": args.get("env_config_id"),
                },
            ),
        ))

    async def handle_execute_test_case(self, args: dict, user: str):
        """处理执行测试用例请求"""
        if args.get('actuator_id') == RECORDER_BROWSER_ID:
            # 前端消息不带 user 字段：用连接注册键定位回执/帧的目标。
            # 独立任务执行：接收循环保持空闲，前端关闭画布的停止请求才能被及时处理
            self._recorder_exec_task = asyncio.ensure_future(self._execute_via_recorder('case', args, user or self.user_id))
            await self._send_test_case_ack(args)
            return
        args, actuator, err = await self._prepare_task_dispatch(args)
        if err:
            await self.send_json(SocketDataModel(
                code=ResponseCode.ERROR,
                msg=self._localize(err),
                data=QueueModel(
                    func_name=UiSocketEnum.TEST_CASE,
                    func_args={
                        "case_id": args.get("case_id"),
                        "execution_request_id": args.get("execution_request_id"),
                        "error": err,
                    },
                ),
            ))
            return

        ok, err = self._reserve_actuator_slots(args, 1)
        if not ok:
            await self.send_json(SocketDataModel(
                code=ResponseCode.ERROR,
                msg=err or self._localize("执行器空闲 slot 不足"),
                data=QueueModel(
                    func_name=UiSocketEnum.TEST_CASE,
                    func_args={
                        "case_id": args.get("case_id"),
                        "execution_request_id": args.get("execution_request_id"),
                        "error": err or "",
                    },
                ),
            ))
            return

        try:
            case_id = args.get("case_id")
            if case_id:
                await self.update_testcase_status(case_id, 1)

            await actuator.send_json(SocketDataModel(
                code=ResponseCode.SUCCESS,
                msg="execute",
                user=self.user_id,
                is_notice=NoticeType.ACTUATOR,
                data=QueueModel(
                    func_name=UiSocketEnum.TEST_CASE,
                    func_args=args
                )
            ))
        except Exception:
            self._release_actuator_slots(args, 1)
            raise

        await self.send_json(SocketDataModel(
            code=ResponseCode.SUCCESS,
            msg=self._localize("任务已发送给执行器"),
            data=QueueModel(
                func_name="effective_runtime",
                func_args=self._public_effective(args.get("effective_runtime"))
            )
        ))

    async def handle_execute_batch(self, args: dict, user: str):
        """处理批量执行请求"""
        case_ids = args.get("case_ids", [])
        if not case_ids:
            await self.send_json(SocketDataModel(
                code=ResponseCode.ERROR,
                msg=self._localize("没有选择要执行的用例"),
                data=QueueModel(
                    func_name=UiSocketEnum.TEST_CASE_BATCH,
                    func_args={"case_ids": [], "error": self._localize("没有选择要执行的用例")},
                ),
            ))
            return

        args, actuator, err = await self._prepare_task_dispatch(args)
        if err:
            await self.send_json(SocketDataModel(
                code=ResponseCode.ERROR,
                msg=self._localize(err),
                data=QueueModel(
                    func_name=UiSocketEnum.TEST_CASE_BATCH,
                    func_args={"case_ids": case_ids, "error": err},
                ),
            ))
            return

        ok, err = self._reserve_actuator_slots(args, len(case_ids))
        if not ok:
            await self.send_json(SocketDataModel(
                code=ResponseCode.ERROR,
                msg=err or self._localize("执行器空闲 slot 不足"),
                data=QueueModel(
                    func_name=UiSocketEnum.TEST_CASE_BATCH,
                    func_args={"case_ids": case_ids, "error": err or ""},
                ),
            ))
            return
        batch_id = await self.create_batch_record(case_ids)
        if not batch_id:
            self._release_actuator_slots(args, len(case_ids))
            await self.send_json(SocketDataModel(
                code=ResponseCode.ERROR,
                msg=self._localize("创建批量执行记录失败")
            ))
            return
        args["batch_id"] = batch_id
        # 批量执行不展示执行画面：强制无头
        self._force_batch_headless(args)

        try:
            for case_id in case_ids:
                await self.update_testcase_status(case_id, 1)

            await actuator.send_json(SocketDataModel(
                code=ResponseCode.SUCCESS,
                msg="execute_batch",
                user=self.user_id,
                is_notice=NoticeType.ACTUATOR,
                data=QueueModel(
                    func_name=UiSocketEnum.TEST_CASE_BATCH,
                    func_args=args
                )
            ))
        except Exception:
            self._release_actuator_slots(args, len(case_ids))
            raise

        await self.send_json(SocketDataModel(
            code=ResponseCode.SUCCESS,
            msg=self._localize("批量任务已发送给执行器"),
            data=QueueModel(
                func_name="batch_created",
                func_args={
                    "batch_id": batch_id,
                    "total_cases": len(case_ids),
                    "effective_runtime": self._public_effective(args.get("effective_runtime")),
                }
            )
        ))

    async def handle_stop_execution(self, args: dict, user: str):
        """处理停止执行请求"""
        # 录制器浏览器执行：前端关闭执行画布时直接中断（取消任务 + 关闭会话）
        task = getattr(self, '_recorder_exec_task', None)
        if task is not None and not task.done():
            session = getattr(self, '_recorder_exec_session', None)
            if session is not None:
                try:
                    from .recorder.session_manager import recorder_manager
                    recorder_manager.close(session.session_id, graceful=False)
                except Exception:
                    pass
                self._recorder_exec_session = None
            task.cancel()
        from .actuator_registry import release_all_slots, clear_actuator_leases

        target_id = None
        if isinstance(args, dict):
            target_id = args.get("actuator_id")
            if not target_id and isinstance(args.get("effective_runtime"), dict):
                target_id = args.get("effective_runtime", {}).get("actuator_id")

        actuators = SocketUserManager.get_all_actuators()
        if target_id:
            target = SocketUserManager.get_actuator_by_id(str(target_id))
            actuators = [target] if target else actuators
        for actuator in actuators:
            if actuator is None:
                continue
            await actuator.send_json(SocketDataModel(
                code=ResponseCode.SUCCESS,
                msg="stop",
                user=self.user_id,
                is_notice=NoticeType.ACTUATOR,
                data=QueueModel(
                    func_name=UiSocketEnum.STOP_EXECUTION,
                    func_args=args or {}
                )
            ))

        # 停止时立即释放 lease，避免执行器无回执导致 slot 长期占用
        try:
            if target_id:
                released = clear_actuator_leases(str(target_id))
            else:
                released = release_all_slots()
            if released:
                logger.warning(f"stop 已强制释放 {released} 个 slot lease")
        except Exception as exc:
            logger.warning(f"stop release slots failed: {exc}")
        
        await self.send_json(SocketDataModel(
            code=ResponseCode.SUCCESS,
            msg=self._localize("停止信号已发送")
        ))


    async def handle_test_case_ack(self, args: dict, user: str):
        """执行器确认单用例任务已进入其本地队列。"""
        web_user = SocketUserManager.get_web_user(user)
        if web_user:
            await web_user.send_json(SocketDataModel(
                code=ResponseCode.SUCCESS,
                msg=self._localize("执行器已接收任务"),
                user=user,
                is_notice=NoticeType.WEB,
                data=QueueModel(
                    func_name=UiSocketEnum.TEST_CASE_ACK,
                    func_args=self._sanitize_result_args(args),
                ),
            ))

    async def handle_step_result(self, args: dict, user: str):
        """处理步骤执行结果（来自执行器）"""
        logger.info(f"收到步骤结果, 目标用户: {user}, 当前Web用户: {list(SocketUserManager._web_users.keys())}")
        
        # 转发给对应的前端用户
        web_user = SocketUserManager.get_web_user(user)
        if web_user:
            await web_user.send_json(SocketDataModel(
                code=ResponseCode.SUCCESS,
                msg="step_result",
                user=user,
                is_notice=NoticeType.WEB,
                data=QueueModel(
                    func_name=UiSocketEnum.STEP_RESULT,
                    func_args=self._sanitize_result_args(args)
                )
            ))
            logger.info(f"步骤结果已发送给用户: {user}")
        else:
            logger.warning(f"找不到Web用户: {user}")
        
        # 同时广播给所有前端（用于多人协作）
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'broadcast_result',
                'data': {
                    'func_name': UiSocketEnum.STEP_RESULT,
                    'args': self._sanitize_result_args(args)
                }
            }
        )

    async def handle_exec_frame(self, args: dict, user: str):
        """处理执行画面帧（来自执行器，直播）：直推发起用户，不落库、不广播。

        帧频率高（默认 5fps）且只属于发起人，广播与持久化均无必要；
        发起人不在线时直接丢弃（不积压）。大 payload（base64 jpeg）不经脱敏，
        与录制器帧的 _send_recorder 直推路径一致。
        """
        if not args:
            return
        web_user = SocketUserManager.get_web_user(user)
        if not web_user:
            return  # 发起人不在线，丢弃本帧
        await web_user.send_json(SocketDataModel(
            code=ResponseCode.SUCCESS,
            msg='exec_frame',
            user=user,
            is_notice=NoticeType.WEB,
            data=QueueModel(
                func_name=UiSocketEnum.EXEC_FRAME,
                func_args=args,
            )
        ))
    
    async def handle_page_step_result(self, args: dict, user: str):
        """处理页面步骤执行结果（来自执行器）"""
        self._release_actuator_slots(args, 1)
        logger.info(f"收到页面步骤结果, 执行用户: {user}")

        # 更新页面步骤状态到数据库
        page_step_id = args.get('page_step_id')
        if page_step_id:
            status_str = args.get('status', 'unknown')
            status = 2 if status_str == 'success' else 3  # 2=成功, 3=失败
            await self.update_page_step_status(page_step_id, status, args)

        # 广播给所有前端
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'broadcast_result',
                'data': {
                    'func_name': UiSocketEnum.PAGE_STEP_RESULT,
                    'args': self._sanitize_result_args(args),
                    'user': user
                }
            }
        )
    
    async def handle_case_result(self, args: dict, user: str):
        """处理用例执行结果（来自执行器）"""
        logger.info(f"收到用例结果, 执行用户: {user}")
        
        # 保存执行结果到数据库
        await self.save_execution_result(args)
        
        # 广播给所有前端（避免重复发送）
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'broadcast_result',
                'data': {
                    'func_name': UiSocketEnum.CASE_RESULT,
                    'args': self._sanitize_result_args(args),
                    'user': user  # 携带执行用户信息
                }
            }
        )
    
    async def broadcast_result(self, event):
        """Broadcast results to web clients (sanitize secrets)."""
        if not self.is_actuator:
            raw_args = event["data"].get("args") or {}
            safe_args = self._sanitize_result_args(raw_args) if isinstance(raw_args, dict) else raw_args
            await self.send_json(SocketDataModel(
                code=ResponseCode.SUCCESS,
                msg="broadcast",
                is_notice=NoticeType.WEB,
                data=QueueModel(
                    func_name=event["data"]["func_name"],
                    func_args=safe_args
                )
            ))
    
    @sync_to_async
    def update_testcase_status(self, case_id: int, status: int):
        """更新测试用例状态"""
        from .models import UiTestCase
        try:
            UiTestCase.objects.filter(id=case_id).update(status=status)
            logger.info(f"测试用例状态更新: case_id={case_id}, status={status}")
        except Exception as e:
            logger.error(f"更新测试用例状态失败: {e}")

    @sync_to_async
    def update_page_step_status(self, page_step_id: int, status: int, result_data: dict):
        """更新页面步骤状态"""
        from .models import UiPageSteps
        try:
            UiPageSteps.objects.filter(id=page_step_id).update(
                status=status,
                result_data=result_data
            )
            logger.info(f"页面步骤状态更新: page_step_id={page_step_id}, status={status}")
        except Exception as e:
            logger.error(f"更新页面步骤状态失败: {e}")
    
    @sync_to_async
    def save_execution_result(self, args: dict):
        """保存执行结果到数据库"""
        from .models import UiExecutionRecord, UiTestCase, UiBatchExecutionRecord
        from django.contrib.auth.models import User
        from datetime import datetime, timedelta

        logger.info(f">>> save_execution_result 被调用, args: {args}")

        # 状态映射: string -> int
        status_map = {'success': 2, 'failed': 3, 'skipped': 4}
        status_str = args.get('status', 'unknown')
        status = status_map.get(status_str, 3)  # 默认失败

        duration = args.get('duration', 0)
        end_time = datetime.now()
        start_time = end_time - timedelta(seconds=duration) if duration else end_time

        # 提取步骤结果
        steps = args.get('steps', [])
        screenshots = []
        for step in steps:
            if step.get('screenshot'):
                screenshots.append(step['screenshot'])

        # 提取 trace 路径
        trace_path = args.get('trace_path')

        # 提取 batch_id
        batch_id = args.get('batch_id')
        
        # 提取执行人信息
        executor_id = args.get('executor_id')
        executor = None
        if executor_id:
            try:
                executor = User.objects.get(id=executor_id)
                logger.info(f"找到执行人: id={executor_id}, username={executor.username}")
            except User.DoesNotExist:
                logger.warning(f"执行人不存在: id={executor_id}")

        case_id = args.get('case_id')
        try:
            self._release_actuator_slots(args, 1)
            environment_snapshot = args.get('environment') or args.get('effective_runtime')
            if not (environment_snapshot and isinstance(environment_snapshot, dict)):
                environment_snapshot = None

            record = UiExecutionRecord.objects.create(
                test_case_id=case_id,
                batch_id=batch_id,
                executor=executor,
                status=status,
                trigger_type=args.get('trigger_type') or 'manual',
                step_results=steps,
                screenshots=screenshots,
                trace_path=trace_path,
                log=args.get('message', ''),
                error_message=args.get('message') if status == 3 else None,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                environment=environment_snapshot,
            )
            logger.info(f"执行记录已保存: id={record.id}, case_id={case_id}, batch_id={batch_id}, status={status}")

            # 同时更新测试用例的状态
            if case_id:
                UiTestCase.objects.filter(id=case_id).update(
                    status=status,
                    result_data={'last_execution': record.id, 'steps': steps},
                    error_message=args.get('message') if status == 3 else None
                )
                logger.info(f"测试用例状态已更新: case_id={case_id}, status={status}")

            # 更新批量执行记录统计
            if batch_id:
                try:
                    batch = UiBatchExecutionRecord.objects.get(id=batch_id)
                    batch.update_statistics()
                    logger.info(f"批量执行记录统计已更新: batch_id={batch_id}")
                except UiBatchExecutionRecord.DoesNotExist:
                    logger.warning(f"批量执行记录不存在: batch_id={batch_id}")
        except Exception as e:
            logger.error(f"保存执行结果失败: {e}", exc_info=True)

    @sync_to_async
    def create_batch_record(self, case_ids: list) -> int:
        """创建批量执行记录"""
        from .models import UiBatchExecutionRecord, UiTestCase
        from django.utils import timezone

        try:
            # 获取用例名称用于批次命名
            case_names = list(UiTestCase.objects.filter(id__in=case_ids).values_list('name', flat=True)[:3])
            batch_name = f"批量执行: {', '.join(case_names)}"
            if len(case_ids) > 3:
                batch_name += f" 等{len(case_ids)}个用例"

            batch = UiBatchExecutionRecord.objects.create(
                name=batch_name,
                total_cases=len(case_ids),
                status=1,  # 执行中
                start_time=timezone.now()
            )
            logger.info(f"批量执行记录已创建: id={batch.id}, total={len(case_ids)}")
            return batch.id
        except Exception as e:
            logger.error(f"创建批量执行记录失败: {e}", exc_info=True)
            return None
    
    async def handle_set_actuator_info(self, args: dict, user: str):
        """处理执行器信息更新（仅执行器可调用）"""
        if not self.is_actuator:
            return
        
        # 更新执行器信息
        if 'name' in args:
            self.actuator_info['name'] = args['name']
        if 'type' in args:
            self.actuator_info['type'] = args['type']
        if 'is_open' in args:
            self.actuator_info['is_open'] = args['is_open']
        if 'debug' in args:
            self.actuator_info['debug'] = args['debug']
        if 'browser_type' in args:
            self.actuator_info['browser_type'] = args['browser_type']
        if 'headless' in args:
            self.actuator_info['headless'] = args['headless']
        if 'version' in args:
            self.actuator_info['version'] = args['version']
        capability_keys = (
            'supported_browsers', 'default_browser', 'supports_headed', 'supports_headless',
            'max_slots', 'max_concurrent', 'labels', 'os',
        )
        for key in capability_keys:
            if key in args and args[key] is not None:
                self.actuator_info[key] = args[key]
        # 运行配置字段（供平台列表/编辑弹窗预填当前值）
        config_keys = (
            'persistent', 'launch_timeout', 'action_timeout', 'retry_count',
            'step_interval', 'log_level',
            'trace_enabled', 'trace_screenshots', 'trace_snapshots', 'trace_sources',
            'headless', 'viewport_width', 'viewport_height', 'in_container',
            # HTTPS 客户端证书路径（不含 passphrase：口令只留在执行器本机）。
            # 必须在此白名单内，否则 list_actuators 取不到值 → 前端以 '' 预填 →
            # 保存时把执行器上已配置的路径清空。
            'client_cert_enabled', 'client_cert_pfx_path', 'client_cert_cert_path',
            'client_cert_key_path', 'client_cert_origins',
        )
        for key in config_keys:
            if key in args and args[key] is not None:
                self.actuator_info[key] = args[key]
        # busy_slots is server-owned accounting; ignore client-provided values.
        if 'busy_slots' in args:
            args = {k: v for k, v in args.items() if k != 'busy_slots'}
        try:
            from .actuator_registry import update_capability
            update_capability(self.user_id, self.actuator_info)
        except Exception as exc:
            logger.warning(f"normalize actuator capability failed: {exc}")
        
        logger.info(f"执行器 {self.user_id} 信息已更新: {self.actuator_info}")
        
        await self.send_json(SocketDataModel(
            code=ResponseCode.SUCCESS,
            msg="执行器信息已更新"
        ))
    
    async def send_json(self, data: SocketDataModel):
        """发送JSON消息"""
        await self.send(text_data=data.model_dump_json())
    
    @classmethod
    async def send_to_actuator(cls, task: ExecutionTaskModel, user: str) -> bool:
        """发送任务给执行器（供视图调用）"""
        actuator = SocketUserManager.get_actuator()
        if not actuator:
            return False
        
        func_name = UiSocketEnum.TEST_CASE
        if task.task_type == 'page_steps':
            func_name = UiSocketEnum.PAGE_STEPS
        elif task.task_type == 'batch':
            func_name = UiSocketEnum.TEST_CASE_BATCH
        
        await actuator.send_json(SocketDataModel(
            code=ResponseCode.SUCCESS,
            msg="execute",
            user=user,
            is_notice=NoticeType.ACTUATOR,
            data=QueueModel(
                func_name=func_name,
                func_args=task.model_dump()
            )
        ))
        return True
