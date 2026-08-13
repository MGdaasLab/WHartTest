"""
UI自动化 WebSocket Consumer


提供两个WebSocket端点：
- /ws/ui/web/ - 前端连接，用于接收执行结果和状态更新
- /ws/ui/actuator/ - 执行器连接，用于接收执行任务和返回结果
"""

import json
import logging
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
                UiSocketEnum.PAGE_STEP_RESULT: self.handle_page_step_result,
                UiSocketEnum.CASE_RESULT: self.handle_case_result,
                UiSocketEnum.SET_ACTUATOR_INFO: self.handle_set_actuator_info,
            }
        else:
            # 前端发送执行请求 -> 转发给执行器
            handler_map = {
                UiSocketEnum.PAGE_STEPS: self.handle_execute_page_steps,
                UiSocketEnum.TEST_CASE: self.handle_execute_test_case,
                UiSocketEnum.TEST_CASE_BATCH: self.handle_execute_batch,
                UiSocketEnum.STOP_EXECUTION: self.handle_stop_execution,
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
    def _sanitize_result_args(args: dict) -> dict:
        """Copy result args for frontend broadcast without db secrets."""
        if not isinstance(args, dict):
            return {}
        return dict(args)

    @staticmethod
    def _public_effective(effective):
        return effective or {}

    def _release_actuator_slots(self, args: dict, count: int = 1) -> None:
        from .actuator_registry import adjust_busy_slots
        if count <= 0:
            return
        actuator_id = args.get("actuator_id")
        if not actuator_id and isinstance(args.get("effective_runtime"), dict):
            actuator_id = args.get("effective_runtime", {}).get("actuator_id")
        if not actuator_id and isinstance(args.get("environment"), dict):
            actuator_id = args.get("environment", {}).get("actuator_id")
        if not actuator_id:
            return
        try:
            adjust_busy_slots(str(actuator_id), -count)
        except Exception as exc:
            logger.warning(f"adjust busy_slots -{count} failed: {exc}")

    def _reserve_actuator_slots(self, args: dict, count: int = 1) -> bool:
        from . import actuator_registry
        actuator_id = args.get("actuator_id") or args.get("_selected_actuator_for_slots")
        if not actuator_id or count <= 0:
            return True
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
            return False
        return True

    async def handle_execute_page_steps(self, args: dict, user: str):
        """处理执行页面步骤请求"""
        args, actuator, err = await self._prepare_task_dispatch(args)
        if err:
            await self.send_json(SocketDataModel(
                code=ResponseCode.ERROR,
                msg=self._localize(err)
            ))
            return

        if not self._reserve_actuator_slots(args, 1):
            await self.send_json(SocketDataModel(
                code=ResponseCode.ERROR,
                msg=self._localize("执行器空闲 slot 不足")
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

    async def handle_execute_test_case(self, args: dict, user: str):
        """处理执行测试用例请求"""
        args, actuator, err = await self._prepare_task_dispatch(args)
        if err:
            await self.send_json(SocketDataModel(
                code=ResponseCode.ERROR,
                msg=self._localize(err)
            ))
            return

        if not self._reserve_actuator_slots(args, 1):
            await self.send_json(SocketDataModel(
                code=ResponseCode.ERROR,
                msg=self._localize("执行器空闲 slot 不足")
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
                msg=self._localize("没有选择要执行的用例")
            ))
            return

        args, actuator, err = await self._prepare_task_dispatch(args)
        if err:
            await self.send_json(SocketDataModel(
                code=ResponseCode.ERROR,
                msg=self._localize(err)
            ))
            return

        if not self._reserve_actuator_slots(args, len(case_ids)):
            await self.send_json(SocketDataModel(
                code=ResponseCode.ERROR,
                msg=self._localize("执行器空闲 slot 不足")
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
