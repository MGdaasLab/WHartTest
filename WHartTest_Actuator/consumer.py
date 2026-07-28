"""
UI自动化执行器 - 任务消费者
"""

import asyncio
import hashlib
import gc
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Optional, Any
import httpx

from models import (
    SocketDataModel, QueueModel, UiSocketEnum, 
    StepResultModel, CaseResultModel, ResponseCode, NoticeType
)
from websocket_client import WebSocketClient
from executor import (
    PlaywrightExecutor, StepConfig, PageStepConfig, TestCaseConfig
)
from data_processor import reset_data_processor, DataProcessor
from runtime_env import resolve_runtime_file_path

logger = logging.getLogger('actuator')


class TaskConsumer:
    """任务消费者 - 处理从服务器接收的执行任务"""
    
    def __init__(self, ws_client: WebSocketClient, api_base_url: str, 
                 config: Any = None,
                 api_username: str = 'admin', api_password: str = 'admin123'):
        self.ws_client = ws_client
        self.api_base_url = api_base_url.rstrip('/')
        self.api_username = api_username
        self.api_password = api_password
        self._api_token: Optional[str] = None
        self.config = config
        
        # 从配置创建执行器
        executor_config = {}
        if config:
            # 超时配置：config中是秒，executor需要毫秒
            launch_timeout = getattr(config, 'launch_timeout', 30)
            action_timeout = getattr(config, 'action_timeout', 30)
            executor_config = {
                'browser_type': getattr(config, 'browser_type', 'chromium'),
                'headless': getattr(config, 'headless', False),
                'persistent': getattr(config, 'persistent', True),
                'user_data_dir': getattr(config, 'user_data_dir', './data/browser'),
                'launch_timeout': launch_timeout * 1000,  # 转毫秒
                'action_timeout': action_timeout * 1000,  # 转毫秒
                'screenshot_dir': getattr(config, 'screenshot_dir', './data/screenshots'),
                # Trace 配置
                'trace_enabled': getattr(config, 'trace_enabled', False),
                'trace_dir': getattr(config, 'trace_dir', './data/traces'),
                'trace_screenshots': getattr(config, 'trace_screenshots', True),
                'trace_snapshots': getattr(config, 'trace_snapshots', True),
                'trace_sources': getattr(config, 'trace_sources', False),
            }
        self.executor = PlaywrightExecutor(**executor_config)
        self.task_queue: asyncio.Queue[QueueModel] = asyncio.Queue()
        self._stop_event = asyncio.Event()
        self._current_user: Optional[str] = None

        # 启动时清理过期文件（超过7天）
        self._cleanup_expired_files(
            [
                getattr(config, 'screenshot_dir', './data/screenshots') if config else './data/screenshots',
                getattr(config, 'trace_dir', './data/traces') if config else './data/traces',
                getattr(config, 'upload_cache_dir', './data/runtime_uploads') if config else './data/runtime_uploads',
            ],
            max_age_days=7
        )

    def _cleanup_expired_files(self, directories, max_age_days: int = 7):
        """清理超过指定天数的本地临时文件"""
        import os
        from pathlib import Path

        now = time.time()
        max_age_seconds = max_age_days * 24 * 60 * 60
        cleaned_count = 0

        for directory in directories:
            dir_path = Path(directory)
            if not dir_path.exists():
                continue

            for file_path in dir_path.iterdir():
                if not file_path.is_file():
                    continue
                try:
                    file_age = now - file_path.stat().st_mtime
                    if file_age > max_age_seconds:
                        file_path.unlink()
                        cleaned_count += 1
                except Exception as e:
                    logger.warning(f"清理过期文件失败 {file_path}: {e}")

        if cleaned_count > 0:
            logger.info(f"已清理 {cleaned_count} 个超过 {max_age_days} 天的过期文件")
    
    async def _get_api_token(self) -> Optional[str]:
        """获取API认证token"""
        if self._api_token:
            return self._api_token
        
        url = f"{self.api_base_url}/api/token/"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json={
                    "username": self.api_username,
                    "password": self.api_password
                })
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'success' and data.get('data'):
                        self._api_token = data['data'].get('access')
                    else:
                        self._api_token = data.get('access')
                    logger.info("获取API Token成功")
                    return self._api_token
                else:
                    logger.error(f"获取Token失败: {response.status_code}")
                    return None
        except Exception as e:
            logger.error(f"获取Token请求失败: {e}")
            return None
    
    async def _api_get(self, path: str) -> Optional[dict]:
        """带认证的API GET请求"""
        token = await self._get_api_token()
        if not token:
            return None
        
        url = f"{self.api_base_url}{path}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers={"Authorization": f"Bearer {token}"})
                if response.status_code == 200:
                    data = response.json()
                    # 提取data字段
                    if data.get('status') == 'success' and 'data' in data:
                        return data['data']
                    return data
                elif response.status_code == 401:
                    # Token过期，重新获取
                    self._api_token = None
                    return await self._api_get(path)
                else:
                    logger.error(f"API请求失败: {response.status_code} - {path}")
                    return None
        except Exception as e:
            logger.error(f"API请求异常: {e}")
            return None
    
    async def _encode_screenshot_base64(self, file_path: str) -> Optional[str]:
        """将截图文件编码为 Base64 数据 URL"""
        import os
        import base64
        
        # 处理相对路径
        if file_path.startswith('./'):
            file_path = os.path.abspath(file_path)
        
        if not file_path or not os.path.exists(file_path):
            logger.warning(f"截图文件不存在: {file_path}")
            return None
        
        try:
            with open(file_path, 'rb') as f:
                data = base64.b64encode(f.read()).decode('utf-8')
            # 返回 data URL 格式
            return f"data:image/png;base64,{data}"
        except Exception as e:
            logger.warning(f"截图编码失败: {e}")
            return None
    
    async def _process_result_screenshots(self, result: CaseResultModel) -> CaseResultModel:
        """处理结果中的截图，转为 Base64 数据 URL，并清理本地文件"""
        import os
        for step in result.steps:
            if step.screenshot:
                local_path = step.screenshot
                base64_url = await self._encode_screenshot_base64(local_path)
                if base64_url:
                    step.screenshot = base64_url
                    # 清理本地截图文件
                    try:
                        abs_path = os.path.abspath(local_path) if local_path.startswith('./') else local_path
                        if os.path.exists(abs_path):
                            os.remove(abs_path)
                            logger.debug(f"已清理本地截图: {abs_path}")
                    except Exception as e:
                        logger.warning(f"清理截图失败: {e}")
                else:
                    step.screenshot = None
        return result
    
    async def _upload_trace_file(self, trace_path: str) -> Optional[str]:
        """上传 Trace 文件到服务器，成功后清理本地文件

        Returns:
            服务器返回的相对路径（用于存储到数据库）
        """
        import os

        if not trace_path or not os.path.exists(trace_path):
            logger.warning(f"Trace 文件不存在: {trace_path}")
            return None

        token = await self._get_api_token()
        if not token:
            logger.error("无法获取 API Token，跳过 Trace 上传")
            return None

        url = f"{self.api_base_url}/api/ui-automation/traces/upload/"
        try:
            async with httpx.AsyncClient() as client:
                with open(trace_path, 'rb') as f:
                    files = {'file': (os.path.basename(trace_path), f, 'application/zip')}
                    response = await client.post(
                        url,
                        headers={"Authorization": f"Bearer {token}"},
                        files=files,
                        timeout=60.0  # Trace 文件可能较大
                    )
                    if response.status_code == 201:
                        resp_data = response.json()
                        # 响应被中间件包装，path 在 data 字段中
                        inner_data = resp_data.get('data', resp_data)
                        server_path = inner_data.get('path')
                        logger.info(f"Trace 上传成功: {server_path}")
                        # 清理本地 Trace 文件
                        try:
                            os.remove(trace_path)
                            logger.debug(f"已清理本地 Trace: {trace_path}")
                        except Exception as e:
                            logger.warning(f"清理 Trace 失败: {e}")
                        return server_path
                    else:
                        logger.error(f"Trace 上传失败: {response.status_code}")
                        return None
        except Exception as e:
            logger.error(f"Trace 上传异常: {e}")
            return None


    def _release_result_payloads(self, result=None, steps=None) -> None:
        """发送结果后释放内存中的截图 base64（支持 CaseResult 或步骤列表）。"""
        if steps is None:
            steps = getattr(result, 'steps', None) or []
        for step in steps:
            screenshot = getattr(step, 'screenshot', None)
            if isinstance(screenshot, str) and screenshot.startswith('data:image'):
                step.screenshot = None

    def _release_memory_after_task_sync(self) -> None:
        """Blocking memory reclaim; call from a worker thread when on async path."""
        try:
            if hasattr(self.executor, '_release_memory'):
                self.executor._release_memory()
                return
        except Exception as e:
            logger.debug(f'executor._release_memory failed, fallback local reclaim: {e}')
        try:
            gc.collect()
        except Exception as e:
            logger.debug(f'gc.collect failed: {e}')
        try:
            import platform
            import ctypes
            if platform.system() != 'Linux':
                return
            libc = ctypes.CDLL('libc.so.6')
            libc.malloc_trim(0)
        except Exception:
            # Non-Linux or libc unavailable.
            pass

    async def _release_memory_after_task(self) -> None:
        """任务结束后尽量回收内存，避免在事件循环线程上阻塞。"""
        try:
            await asyncio.to_thread(self._release_memory_after_task_sync)
        except Exception as e:
            logger.debug(f'_release_memory_after_task failed: {e}')

    async def handle_message(self, socket_data: SocketDataModel):
        """处理接收到的消息"""
        if socket_data.code != ResponseCode.SUCCESS:
            logger.warning(f"收到错误消息: {socket_data.msg}")
            return
        
        if not socket_data.data:
            logger.debug(f"收到通知消息: {socket_data.msg}")
            return
        
        # 记录发起用户
        self._current_user = socket_data.user
        
        # 添加到任务队列
        await self.add_task(socket_data.data)
    
    async def add_task(self, task: QueueModel):
        """添加任务到队列"""
        await self.task_queue.put(task)
        logger.info(f"任务已入队: {task.func_name}")
    
    async def process_tasks(self):
        """处理任务队列"""
        while not self._stop_event.is_set():
            try:
                # 等待任务
                task = await asyncio.wait_for(
                    self.task_queue.get(),
                    timeout=1.0
                )
                
                # 路由任务到对应处理器
                await self._route_task(task)
                self.task_queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"处理任务错误: {e}", exc_info=True)
    
    async def _route_task(self, task: QueueModel):
        """路由任务到对应处理器"""
        handlers = {
            UiSocketEnum.PAGE_STEPS: self.execute_page_steps,
            UiSocketEnum.TEST_CASE: self.execute_test_case,
            UiSocketEnum.TEST_CASE_BATCH: self.execute_batch,
            UiSocketEnum.STOP_EXECUTION: self.stop_execution,
        }
        
        handler = handlers.get(task.func_name)
        if handler:
            await handler(task.func_args)
        else:
            logger.warning(f"未知任务类型: {task.func_name}")
    
    async def execute_page_steps(self, args: dict):
        """执行页面步骤"""
        page_step_id = args.get('page_step_id')
        env_config_id = args.get('env_config_id')
        
        if not page_step_id:
            logger.error("缺少page_step_id参数")
            return
        
        # 从API获取页面步骤详情
        page_step_data = await self._fetch_page_step(page_step_id)
        if not page_step_data:
            return
        
        # 初始化数据处理器，加载项目公共变量
        project_id = page_step_data.get('project')
        data_processor = await self._init_data_processor(project_id)
        
        # 获取环境配置
        env_config = None
        base_url = ''
        if env_config_id:
            env_config = await self._fetch_env_config(env_config_id)
        else:
            # 尝试获取项目的默认环境配置
            if project_id:
                env_config = await self._fetch_default_env_config(project_id)
        
        if env_config:
            base_url = env_config.get('base_url', '') or ''
            logger.info(f"使用环境配置: {env_config.get('name')}, base_url: {base_url}")
        
        # 构建配置，传入 base_url 和数据处理器
        config = self._build_page_step_config(page_step_data, base_url, data_processor, env_config)
        
        # 执行（使用同一浏览器会话）
        logger.info(f"开始执行页面步骤: {config.page_name}")
        
        step_results = None
        summary_result = None
        try:
            start_time = time.time()
            try:
                await self._materialize_page_step_uploads(config, project_id)
            except Exception as e:
                logger.error(f'准备上传文件失败: {e}', exc_info=True)
                summary_result = {
                    'page_step_id': page_step_id,
                    'status': 'failed',
                    'message': f'准备上传文件失败: {e}',
                    'total_steps': len(config.steps),
                    'passed_steps': 0,
                    'failed_steps': len(config.steps),
                    'duration': time.time() - start_time,
                    'steps': [],
                }
                await self.ws_client.send_result(
                    'u_page_step_result',
                    summary_result,
                    self._current_user,
                )
                return
            step_results = await self.executor.execute_page_step(config)
            
            # 统计结果
            passed_steps = sum(1 for r in step_results if r.status == 'success')
            failed_steps = len(step_results) - passed_steps
            
            # 处理截图为 Base64 并发送步骤结果
            import os
            for result in step_results:
                if result.screenshot:
                    local_path = result.screenshot
                    base64_url = await self._encode_screenshot_base64(local_path)
                    if base64_url:
                        result.screenshot = base64_url
                        # 清理本地截图文件
                        try:
                            abs_path = os.path.abspath(local_path) if local_path.startswith('./') else local_path
                            if os.path.exists(abs_path):
                                os.remove(abs_path)
                                logger.debug(f"已清理本地截图: {abs_path}")
                        except Exception as e:
                            logger.warning(f"清理截图失败: {e}")

                # 发送步骤结果
                await self.ws_client.send_result(
                    UiSocketEnum.STEP_RESULT,
                    result.model_dump(),
                    self._current_user
                )
            
            # 发送页面步骤执行汇总结果
            summary_result = {
                'page_step_id': page_step_id,
                'status': 'success' if failed_steps == 0 else 'failed',
                'message': '执行成功' if failed_steps == 0 else '执行失败',
                'total_steps': len(config.steps),
                'passed_steps': passed_steps,
                'failed_steps': failed_steps,
                'duration': time.time() - start_time,
                'steps': [r.model_dump() for r in step_results],
            }
            
            await self.ws_client.send_result(
                'u_page_step_result',  # 新增的结果类型
                summary_result,
                self._current_user
            )
            logger.info("页面步骤执行完成")
        finally:
            # 异常路径也必须释放 base64 / 主动回收，避免 worker RSS 居高不下
            if step_results is not None:
                self._release_result_payloads(steps=step_results)
            summary_result = None
            await self._release_memory_after_task()
    
    async def execute_test_case(self, args: dict):
        """执行测试用例"""
        case_id = args.get('case_id')
        env_config_id = args.get('env_config_id')
        batch_id = args.get('batch_id')
        executor_id = args.get('executor_id')
        executor_name = args.get('executor_name')
        
        if not case_id:
            logger.error("缺少case_id参数")
            return

        # 从API获取用例详情
        case_data = await self._fetch_test_case(case_id)
        if not case_data:
            return

        # 获取环境配置
        env_config = None
        project_id = case_data.get('project')
        if env_config_id:
            env_config = await self._fetch_env_config(env_config_id)
        else:
            # 尝试获取项目的默认环境配置
            if project_id:
                env_config = await self._fetch_default_env_config(project_id)

        # 日志：确认环境配置
        if env_config:
            logger.info(f"环境配置已获取: name={env_config.get('name')}, base_url={env_config.get('base_url')}")
        else:
            logger.warning(f"未获取到环境配置 (env_config_id={env_config_id}, project_id={project_id})")

        # 初始化数据处理器，加载项目公共变量
        data_processor = await self._init_data_processor(project_id)

        # 构建配置（传入数据处理器进行变量替换）
        config = self._build_test_case_config(case_data, env_config, data_processor)

        # 执行
        logger.info(f"开始执行用例: {config.case_name}")
        result = None
        result_data = None
        try:
            try:
                await self._materialize_test_case_uploads(config, project_id)
            except Exception as e:
                logger.error(f'准备上传文件失败: {e}', exc_info=True)
                await self.ws_client.send_result(
                    UiSocketEnum.CASE_RESULT,
                    {
                        'case_id': case_id,
                        'status': 'failed',
                        'message': f'准备上传文件失败: {e}',
                        'batch_id': batch_id,
                        'executor_id': executor_id,
                        'executor_name': executor_name,
                    },
                    self._current_user,
                )
                return
            result = await self.executor.execute_test_case(config)

            # 上传截图并替换路径
            result = await self._process_result_screenshots(result)

            # 上传 Trace 文件并替换路径
            if result.trace_path:
                server_trace_path = await self._upload_trace_file(result.trace_path)
                if server_trace_path:
                    result.trace_path = server_trace_path
                else:
                    result.trace_path = None  # 上传失败则清空

            # 发送用例结果（包含 batch_id 和执行人信息）
            result_data = result.model_dump()
            if batch_id:
                result_data['batch_id'] = batch_id
            # 添加执行人信息
            if executor_id:
                result_data['executor_id'] = executor_id
            if executor_name:
                result_data['executor_name'] = executor_name
                
            await self.ws_client.send_result(
                UiSocketEnum.CASE_RESULT,
                result_data,
                self._current_user
            )

            logger.info(f"用例执行完成: {result.status}")
        finally:
            # 结果已发送（或中途失败）：释放截图 base64 等大对象并回收内存
            if result is not None:
                self._release_result_payloads(result)
            result_data = None
            await self._release_memory_after_task()
    
    async def execute_batch(self, args: dict):
        """批量执行用例（支持并发）"""
        case_ids = args.get('case_ids', [])
        env_config_id = args.get('env_config_id')
        batch_id = args.get('batch_id')
        executor_id = args.get('executor_id')
        executor_name = args.get('executor_name')
        # 从配置获取并发数
        max_concurrent = getattr(self.config, 'max_concurrent', 3) if self.config else 3
        if not case_ids:
            logger.error("缺少case_ids参数")
            return

        logger.info(f"开始批量执行 {len(case_ids)} 个用例, 并发数: {max_concurrent}")

        # 预先获取所有用例数据并构建配置
        configs = []
        config_batch_map = {}  # case_id -> batch_id 映射

        for case_id in case_ids:
            if self._stop_event.is_set():
                logger.info("批量执行准备阶段被停止")
                return

            case_data = await self._fetch_test_case(case_id)
            if not case_data:
                logger.warning(f"用例 {case_id} 数据获取失败，跳过")
                continue

            # 获取环境配置
            env_config = None
            project_id = case_data.get('project')
            if env_config_id:
                env_config = await self._fetch_env_config(env_config_id)
            elif project_id:
                env_config = await self._fetch_default_env_config(project_id)

            # 初始化数据处理器
            data_processor = await self._init_data_processor(project_id)

            # 构建配置
            config = self._build_test_case_config(case_data, env_config, data_processor)
            try:
                await self._materialize_test_case_uploads(config, project_id)
            except Exception as e:
                logger.error(f'batch prepare upload failed case_id={case_id}: {e}', exc_info=True)
                await self.ws_client.send_result(
                    UiSocketEnum.CASE_RESULT,
                    {
                        'case_id': case_id,
                        'status': 'failed',
                        'message': f'prepare upload file failed: {e}',
                        'batch_id': batch_id,
                        'executor_id': executor_id,
                        'executor_name': executor_name,
                    },
                    self._current_user,
                )
                continue
            configs.append(config)
            config_batch_map[config.case_id] = batch_id

        if not configs:
            logger.warning("没有可执行的用例")
            return

        # 定义结果回调 - 每个用例完成后立即发送结果
        async def on_result(result):
            try:
                # 上传截图
                result = await self._process_result_screenshots(result)

                # 上传 Trace
                if result.trace_path:
                    server_trace_path = await self._upload_trace_file(result.trace_path)
                    result.trace_path = server_trace_path if server_trace_path else None

                # 发送结果
                result_data = result.model_dump()
                if batch_id:
                    result_data['batch_id'] = batch_id
                # 添加执行人信息
                if executor_id:
                    result_data['executor_id'] = executor_id
                if executor_name:
                    result_data['executor_name'] = executor_name
                await self.ws_client.send_result(
                    UiSocketEnum.CASE_RESULT,
                    result_data,
                    self._current_user
                )
                logger.info(f"用例 {result.case_id} 执行完成: {result.status}")
            finally:
                self._release_result_payloads(result)

        # 并发执行
        try:
            await self.executor.execute_batch_concurrent(
                configs,
                max_concurrent=max_concurrent,
                on_result=on_result
            )
            logger.info("批量执行完成")
        finally:
            await self._release_memory_after_task()
    
    async def stop_execution(self, args: dict):
        """停止执行"""
        logger.info("收到停止执行请求")
        self.executor.stop()
        # 清空任务队列
        while not self.task_queue.empty():
            try:
                self.task_queue.get_nowait()
                self.task_queue.task_done()
            except asyncio.QueueEmpty:
                break
    

    def _upload_cache_dir(self) -> Path:
        raw = getattr(self.config, 'upload_cache_dir', './data/runtime_uploads') if self.config else './data/runtime_uploads'
        path = Path(raw)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _parse_file_id(value: Any) -> Optional[int]:
        if value is None or value == '':
            return None
        if isinstance(value, int):
            return value
        text = str(value).strip()
        if text.startswith('file_id:'):
            text = text.split(':', 1)[1].strip()
        try:
            return int(text)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_filename(name: Optional[str], file_id: Optional[int] = None) -> str:
        base = Path(name or '').name.strip() if name else ''
        if not base:
            base = f'file_{file_id}' if file_id is not None else 'upload.bin'
        # Keep the original extension; scrub path separators / control chars only.
        base = re.sub(r'[\\/\x00-\x1f]', '_', base)
        return base or 'upload.bin'


    # Upload runtime cache: invalidate by sha256 / size / TTL (seconds).
    UPLOAD_CACHE_TTL_SECONDS = int(os.environ.get('WHART_UPLOAD_CACHE_TTL', str(7 * 24 * 3600)))

    def _upload_cache_path(self, file_id: int, file_name: Optional[str], sha256: Optional[str] = None) -> Path:
        safe_name = self._safe_filename(file_name, file_id)
        sha_part = (sha256 or 'na')[:16]
        return self._upload_cache_dir() / f'{file_id}_{sha_part}_{safe_name}'

    def _upload_cache_meta_path(self, local_path: Path) -> Path:
        return local_path.with_suffix(local_path.suffix + '.meta.json')

    def _is_upload_cache_valid(
        self,
        local_path: Path,
        *,
        expected_sha: Optional[str] = None,
        expected_size: Optional[int] = None,
    ) -> bool:
        if not local_path.exists() or not local_path.is_file():
            return False
        try:
            st = local_path.stat()
        except OSError:
            return False
        if st.st_size <= 0:
            return False
        if expected_size is not None and int(expected_size) > 0 and st.st_size != int(expected_size):
            logger.info('upload cache size mismatch path=%s local=%s expected=%s', local_path, st.st_size, expected_size)
            return False
        age = time.time() - st.st_mtime
        if age > self.UPLOAD_CACHE_TTL_SECONDS:
            logger.info('upload cache expired path=%s age=%ss', local_path, int(age))
            return False
        meta_path = self._upload_cache_meta_path(local_path)
        meta_sha = None
        if meta_path.exists():
            try:
                import json as _json
                meta = _json.loads(meta_path.read_text(encoding='utf-8'))
                meta_sha = meta.get('sha256') or None
            except Exception:
                meta_sha = None
        if expected_sha:
            if meta_sha and meta_sha.lower() != str(expected_sha).lower():
                logger.info('upload cache sha mismatch path=%s', local_path)
                return False
            # If no meta, compute sha of cached file when expected_sha present.
            if not meta_sha:
                try:
                    h = hashlib.sha256()
                    with open(local_path, 'rb') as fh:
                        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
                            h.update(chunk)
                    if h.hexdigest().lower() != str(expected_sha).lower():
                        return False
                except Exception:
                    return False
        return True

    def _write_upload_cache_meta(self, local_path: Path, *, file_id: int, sha256: Optional[str], size: int) -> None:
        try:
            import json as _json
            meta = {
                'file_id': file_id,
                'sha256': sha256 or '',
                'size': size,
                'saved_at': time.time(),
            }
            self._upload_cache_meta_path(local_path).write_text(
                _json.dumps(meta, ensure_ascii=False),
                encoding='utf-8',
            )
        except Exception as e:
            logger.debug('write upload cache meta failed: %s', e)

    def _prune_upload_cache(self) -> None:
        """Remove expired runtime upload cache files (lazy, best-effort)."""
        try:
            cache_dir = self._upload_cache_dir()
            now = time.time()
            ttl = self.UPLOAD_CACHE_TTL_SECONDS
            for p in cache_dir.iterdir():
                try:
                    if not p.is_file():
                        continue
                    if now - p.stat().st_mtime > ttl:
                        p.unlink(missing_ok=True)
                except Exception:
                    pass
        except Exception as e:
            logger.debug('prune upload cache failed: %s', e)

    async def _download_managed_file(
        self,
        *,
        file_id: Optional[int],
        project_id: Optional[int],
        download_url: Optional[str] = None,
        file_name: Optional[str] = None,
        file_sha: Optional[str] = None,
        file_size: Optional[int] = None,
    ) -> str:
        """Download a managed file to local cache and return the local path.

        Security: never follow client-supplied absolute URLs. Always build a
        same-origin relative path from file_id + project_id so case_data cannot
        redirect the actuator JWT to arbitrary hosts (SSRF / token leak).
        download_url is accepted only when it matches that expected path.
        """
        if not file_id or not project_id:
            raise ValueError(
                f'upload step missing file_id/project_id for remote download: '
                f'file_id={file_id}, project_id={project_id}'
            )

        expected_path = f'/api/projects/{int(project_id)}/files/{int(file_id)}/download/'
        if download_url:
            candidate = str(download_url).strip()
            api_base = self.api_base_url.rstrip('/')
            allowed = {
                expected_path,
                f'{api_base}{expected_path}',
            }
            if candidate not in allowed and not (
                candidate.startswith(api_base + '/') and candidate.rstrip('/').endswith(expected_path.rstrip('/'))
            ):
                logger.warning(
                    'Ignoring untrusted download_url=%r; using %s',
                    candidate,
                    expected_path,
                )
        url_path = expected_path
        url = f'{self.api_base_url.rstrip("/")}{url_path}'

        self._prune_upload_cache()
        local_path = self._upload_cache_path(int(file_id), file_name, file_sha)
        if self._is_upload_cache_valid(local_path, expected_sha=file_sha, expected_size=file_size):
            logger.info(f'using cached upload file: {local_path}')
            return str(local_path)
        # Drop stale cache for this file_id (any sha/name variant)
        try:
            for stale in self._upload_cache_dir().glob(f'{int(file_id)}_*'):
                if stale == local_path:
                    continue
                try:
                    if stale.is_file():
                        stale.unlink(missing_ok=True)
                except Exception:
                    pass
        except Exception:
            pass

        token = await self._get_api_token()
        if not token:
            raise RuntimeError('failed to get API token for managed file download')

        tmp_path = local_path.with_name(f'{local_path.name}.{uuid.uuid4().hex}.part')
        headers = {'Authorization': f'Bearer {token}'}
        logger.info(f'downloading managed file: {url} -> {local_path}')
        response_sha = None

        try:
            # Do not follow redirects: a 3xx could send the JWT off-origin.
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=False) as client:
                async with client.stream('GET', url, headers=headers) as response:
                    response_sha = (
                        response.headers.get('X-File-Sha256')
                        or response.headers.get('x-file-sha256')
                        or ''
                    ).strip().strip('"') or None
                    etag = (response.headers.get('ETag') or response.headers.get('etag') or '').strip().strip('"')
                    if not response_sha and etag and len(etag) == 64:
                        response_sha = etag
                    if response.status_code == 401:
                        self._api_token = None
                        token = await self._get_api_token()
                        if not token:
                            raise RuntimeError('Token 刷新失败，无法下载上传文件')
                        headers = {'Authorization': f'Bearer {token}'}
                        async with client.stream('GET', url, headers=headers) as retry_response:
                            if retry_response.status_code != 200:
                                body = (await retry_response.aread())[:300]
                                raise RuntimeError(
                                    f'下载上传文件失败: HTTP {retry_response.status_code}, body={body!r}'
                                )
                            with open(tmp_path, 'wb') as fh:
                                async for chunk in retry_response.aiter_bytes():
                                    fh.write(chunk)
                    elif response.status_code != 200:
                        body = (await response.aread())[:300]
                        raise RuntimeError(
                            f'下载上传文件失败: HTTP {response.status_code}, body={body!r}'
                        )
                    else:
                        with open(tmp_path, 'wb') as fh:
                            async for chunk in response.aiter_bytes():
                                fh.write(chunk)
            if not tmp_path.exists() or tmp_path.stat().st_size <= 0:
                raise RuntimeError(f'下载上传文件为空: {url}')
            if local_path.exists() and local_path.is_file() and local_path.stat().st_size > 0:
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
                return str(local_path)
            tmp_path.replace(local_path)
            size_on_disk = local_path.stat().st_size
            # Prefer server-declared sha; else compute when expected.
            actual_sha = response_sha or file_sha
            if file_sha or not actual_sha:
                try:
                    h = hashlib.sha256()
                    with open(local_path, 'rb') as fh:
                        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
                            h.update(chunk)
                    dig = h.hexdigest()
                    if file_sha and dig.lower() != str(file_sha).lower():
                        try:
                            local_path.unlink(missing_ok=True)
                        except Exception:
                            pass
                        raise RuntimeError(
                            f'upload file sha256 mismatch: expected={file_sha}, actual={dig}'
                        )
                    actual_sha = dig
                except RuntimeError:
                    raise
                except Exception as e:
                    logger.debug('sha verify skipped: %s', e)
            self._write_upload_cache_meta(
                local_path,
                file_id=int(file_id),
                sha256=actual_sha,
                size=size_on_disk,
            )
            return str(local_path)
        except Exception:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass
            raise

    async def _ensure_local_upload_file(
        self,
        *,
        file_path: str,
        file_id: Optional[int] = None,
        file_name: Optional[str] = None,
        download_url: Optional[str] = None,
        project_id: Optional[int] = None,
        file_sha: Optional[str] = None,
        file_size: Optional[int] = None,
    ) -> str:
        """Resolve a local path for Playwright upload, downloading when needed."""
        candidates = []
        if file_path:
            mapped = resolve_runtime_file_path(str(file_path))
            candidates.append(mapped)
            if mapped != file_path:
                candidates.append(str(file_path))

        for candidate in candidates:
            if candidate and os.path.isfile(candidate):
                return candidate

        # Backend may still return file_id:N when path resolve failed.
        parsed_id = self._parse_file_id(file_path)
        if parsed_id is not None:
            file_id = file_id or parsed_id

        if file_id and project_id:
            return await self._download_managed_file(
                file_id=file_id,
                project_id=project_id,
                download_url=download_url,
                file_name=file_name,
                file_sha=file_sha,
                file_size=file_size,
            )

        if file_id and not project_id:
            raise FileNotFoundError(
                f'local upload file missing and project_id absent; refuse unsafe download file_id={file_id}'
            )


        tried = ', '.join(candidates) if candidates else '(empty)'
        raise FileNotFoundError(
            f'上传文件本地不存在且缺少 file_id/download_url，无法远程拉取。已尝试路径: {tried}'
        )

    async def _materialize_upload_files(self, steps: list[StepConfig], default_project_id: Optional[int] = None) -> None:
        """Ensure every upload step points to a local file path Playwright can read."""
        for step in steps:
            if (step.operation_type or '').lower() != 'upload':
                continue
            project_id = step.upload_project_id or default_project_id
            original = step.input_value
            local_path = await self._ensure_local_upload_file(
                file_path=step.input_value or '',
                file_id=step.upload_file_id,
                file_name=step.upload_file_name,
                download_url=step.upload_download_url,
                project_id=project_id,
                file_sha=getattr(step, 'upload_file_sha', None),
                file_size=getattr(step, 'upload_file_size', None),
            )
            if original != local_path:
                logger.info(f'上传文件已就绪: step={step.step_id}, {original!r} -> {local_path!r}')
            step.input_value = local_path

    async def _materialize_page_step_uploads(self, config: PageStepConfig, project_id: Optional[int] = None) -> None:
        await self._materialize_upload_files(config.steps, project_id)

    async def _materialize_test_case_uploads(self, config: TestCaseConfig, project_id: Optional[int] = None) -> None:
        for page_step in config.page_steps:
            await self._materialize_upload_files(page_step.steps, project_id)

    async def _fetch_page_step(self, page_step_id: int) -> Optional[dict]:
        """从API获取页面步骤详情（含元素定位信息，用于执行）"""
        return await self._api_get(f"/api/ui-automation/page-steps/{page_step_id}/execute-data/")
    
    async def _fetch_test_case(self, case_id: int) -> Optional[dict]:
        """从API获取测试用例详情（含完整步骤详情）"""
        return await self._api_get(f"/api/ui-automation/testcases/{case_id}/execute-data/")
    
    async def _fetch_env_config(self, env_config_id: int) -> Optional[dict]:
        """从API获取环境配置"""
        return await self._api_get(f"/api/ui-automation/env-configs/{env_config_id}/")
    
    async def _fetch_default_env_config(self, project_id: int) -> Optional[dict]:
        """从API获取项目的默认环境配置"""
        result = await self._api_get(f"/api/ui-automation/env-configs/?project={project_id}&is_default=true")
        logger.debug(f"获取默认环境配置: project_id={project_id}, result={result}")

        if not result:
            logger.warning(f"未找到项目 {project_id} 的默认环境配置")
            return None

        # 处理不同的返回格式
        if isinstance(result, list):
            # API 直接返回列表
            if len(result) > 0:
                logger.info(f"使用默认环境配置: {result[0].get('name')}")
                return result[0]
        elif isinstance(result, dict):
            # API 返回分页格式 {"items": [...]} 或 {"results": [...]}
            items = result.get('items', result.get('results', []))
            if items and len(items) > 0:
                logger.info(f"使用默认环境配置: {items[0].get('name')}")
                return items[0]
            # 可能直接就是配置对象
            if result.get('id') and result.get('base_url'):
                logger.info(f"使用默认环境配置: {result.get('name')}")
                return result

        logger.warning(f"未找到项目 {project_id} 的默认环境配置")
        return None

    async def _fetch_public_data(self, project_id: int) -> list[dict]:
        """从API获取项目的公共数据（用于变量替换）"""
        result = await self._api_get(f"/api/ui-automation/public-data/by-project/{project_id}/")
        logger.debug(f"获取公共数据原始结果 (project_id={project_id}): type={type(result)}, value={result}")
        if result and isinstance(result, list):
            logger.debug(f"公共数据是列表，长度: {len(result)}")
            return result
        logger.warning(f"公共数据格式不正确: type={type(result)}")
        return []

    async def _init_data_processor(self, project_id: int) -> DataProcessor:
        """初始化数据处理器，加载项目公共变量"""
        data_processor = reset_data_processor()
        
        if project_id:
            public_data = await self._fetch_public_data(project_id)
            logger.info(f"已加载 {len(public_data)} 个公共变量")
            if public_data:
                data_processor.load_public_data(public_data)
                logger.debug(f"变量缓存: {data_processor.get_all()}")
        else:
            logger.warning("project_id 为空，无法加载公共变量")
        
        return data_processor

    def _build_page_step_config(
        self,
        data: dict,
        base_url: str = '',
        data_processor: Optional[DataProcessor] = None,
        case_data_override: Optional[dict] = None,
        env_config: Optional[dict] = None,
    ) -> PageStepConfig:
        """构建页面步骤配置
        
        Args:
            data: 页面步骤数据
            base_url: 环境基础URL
            data_processor: 变量处理器，用于替换 ${{变量名}} 语法
            case_data_override: 用例步骤的覆盖数据
            env_config: 执行环境配置，用于 SQL 步骤获取数据库连接
        """
        steps = []
        
        for detail in data.get('step_details', []):
            step_type = detail.get('step_type', 0)
            detail_id = str(detail.get('id', ''))
            operation_type = detail.get('ope_key') or ''
            
            # 从 ope_value 中提取输入值
            ope_value = detail.get('ope_value', {})
            sql_execute = detail.get('sql_execute') or {}
            
            # 应用用例步骤的覆盖数据
            if case_data_override and detail_id in case_data_override:
                val = case_data_override[detail_id]
                if isinstance(val, dict):
                    # 如果覆盖数据本身是字典，直接合并
                    if isinstance(ope_value, dict):
                        ope_value = {**ope_value, **val}
                    else:
                        ope_value = val
                else:
                    # 否则，如果是字符串等简单类型，覆盖已有的主要参数
                    if isinstance(ope_value, dict):
                        for key in ['text', 'value', 'timeout', 'url', 'key', 'expected']:
                            if key in ope_value:
                                ope_value[key] = val
                                break
                        else:
                            # 没找到已知键，且字典不为空，取第一个键
                            if ope_value:
                                first_key = next(iter(ope_value.keys()))
                                ope_value[first_key] = val
                            else:
                                ope_value = {'text': val}
                    else:
                        ope_value = val
            
            # 支持多种格式：{"text": "admin"}, {"value": "xxx"}, {"timeout": 3000}, 或纯字符串/数字
            if isinstance(ope_value, dict):
                # 按优先级尝试提取常见字段
                input_value = (
                    ope_value.get('text') or
                    ope_value.get('value') or
                    ope_value.get('timeout') or  # wait 操作使用 timeout
                    ope_value.get('url') or      # goto 操作可能使用 url
                    ope_value.get('key') or      # press 操作可能使用 key
                    ope_value.get('expected') or # 断言使用 expected
                    ''
                )
                # 如果所有已知字段都没有，且字典不为空，取第一个值
                if not input_value and ope_value:
                    input_value = next(iter(ope_value.values()), '')
                # 确保转换为字符串
                input_value = str(input_value) if input_value else ''
            else:
                input_value = str(ope_value) if ope_value else ''
            
            # 定位器值也可能包含变量
            locator_value = detail.get('locator_value', '')
            locator_value_2 = detail.get('locator_value_2', '')
            locator_value_3 = detail.get('locator_value_3', '')
            
            # 变量替换：替换 input_value 和 locator_value 中的 ${{变量名}}
            if data_processor:
                sql_execute = data_processor.replace(sql_execute)
                if not isinstance(sql_execute, (dict, str)):
                    sql_execute = {}

                original_input = input_value
                input_value = data_processor.replace(input_value)
                if original_input != input_value:
                    logger.info(f"变量替换: '{original_input}' -> '{input_value}'")
                
                original_locator = locator_value
                locator_value = data_processor.replace(locator_value)
                if original_locator != locator_value:
                    logger.info(f"变量替换 (定位器): '{original_locator}' -> '{locator_value}'")

                if locator_value_2:
                    original_locator_2 = locator_value_2
                    locator_value_2 = data_processor.replace(locator_value_2)
                    if original_locator_2 != locator_value_2:
                        logger.info(f"变量替换 (定位器2): '{original_locator_2}' -> '{locator_value_2}'")

                if locator_value_3:
                    original_locator_3 = locator_value_3
                    locator_value_3 = data_processor.replace(locator_value_3)
                    if original_locator_3 != locator_value_3:
                        logger.info(f"变量替换 (定位器3): '{original_locator_3}' -> '{locator_value_3}'")
                
                # 确保替换后的值是字符串类型
                if not isinstance(input_value, str):
                    input_value = str(input_value)
                if not isinstance(locator_value, str):
                    locator_value = str(locator_value)
                if locator_value_2 and not isinstance(locator_value_2, str):
                    locator_value_2 = str(locator_value_2)
                if locator_value_3 and not isinstance(locator_value_3, str):
                    locator_value_3 = str(locator_value_3)
            else:
                logger.warning(f"data_processor 为 None，跳过变量替换")
            
            # iframe 定位器也可能包含变量
            is_iframe = detail.get('is_iframe', False)
            iframe_locator = detail.get('iframe_locator', '') or ''
            if data_processor and iframe_locator:
                original_iframe = iframe_locator
                iframe_locator = data_processor.replace(iframe_locator)
                if original_iframe != iframe_locator:
                    logger.info(f"变量替换 (iframe 定位器): '{original_iframe}' -> '{iframe_locator}'")
                if not isinstance(iframe_locator, str):
                    iframe_locator = str(iframe_locator)

            def _parse_index(value):
                if value is None or value == '':
                    return None
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None


            upload_file_id = None
            upload_file_name = None
            upload_download_url = None
            upload_project_id = None
            if operation_type.lower() == 'upload' and isinstance(ope_value, dict):
                upload_file_id = self._parse_file_id(ope_value.get('file_id') or ope_value.get('value'))
                upload_file_name = ope_value.get('file_name') or ope_value.get('name') or ope_value.get('filename')
                upload_download_url = ope_value.get('download_url') or ''
                upload_project_id = self._parse_file_id(ope_value.get('project_id')) or (
                    self._parse_file_id(data.get('project')) if isinstance(data, dict) else None
                )
                # sha/size used for remote cache invalidation (handled in StepConfig below)
                # Prefer explicit file_path from backend runtime resolve when value is still file_id:N
                preferred_path = ope_value.get('file_path') or ''
                if preferred_path and (not input_value or str(input_value).startswith('file_id:')):
                    input_value = preferred_path
                original_input = input_value
                input_value = resolve_runtime_file_path(input_value)
                if original_input != input_value:
                    logger.info(f"上传文件路径映射: '{original_input}' -> '{input_value}'")

            steps.append(StepConfig(
                step_id=detail.get('id', 0),
                operation_type=operation_type,  # 操作类型如 click, type
                locator_type=detail.get('locator_type') or 'xpath',  # 定位方式
                locator_value=locator_value or '',  # 定位表达式
                step_type=step_type,
                input_value=input_value,  # 输入值
                description=detail.get('description') or detail.get('element_name') or ('SQL操作' if step_type == 2 else ''),
                wait_time=detail.get('wait_time', 0),
                is_iframe=is_iframe,
                iframe_locator=iframe_locator,
                locator_index=detail.get('locator_index'),
                locator_type_2=detail.get('locator_type_2'),
                locator_value_2=locator_value_2 or None,
                locator_index_2=_parse_index(detail.get('locator_index_2')),
                locator_type_3=detail.get('locator_type_3'),
                locator_value_3=locator_value_3 or None,
                locator_index_3=_parse_index(detail.get('locator_index_3')),
                sql_execute=sql_execute,
                upload_file_id=upload_file_id,
                upload_file_name=upload_file_name,
                upload_download_url=upload_download_url,
                upload_project_id=upload_project_id,
                upload_file_sha=(ope_value.get('sha256') or ope_value.get('file_sha') or None) if isinstance(ope_value, dict) else None,
                upload_file_size=self._parse_file_id(ope_value.get('size')) if isinstance(ope_value, dict) else None,
            ))
        
        # 页面URL处理：支持相对路径与 base_url 拼接
        page_url = data.get('page_url', '') or ''
        if page_url:
            # 如果是相对路径，与 base_url 拼接
            if page_url.startswith('/') and base_url:
                page_url = base_url.rstrip('/') + page_url
            elif not page_url.startswith(('http://', 'https://')) and base_url:
                # 既不是绝对路径也不是完整URL，与 base_url 拼接
                page_url = base_url.rstrip('/') + '/' + page_url.lstrip('/')
        else:
            # page_url 为空，使用 base_url
            page_url = base_url
        
        # URL也可能包含变量
        if data_processor and page_url:
            page_url = data_processor.replace(page_url)
            if not isinstance(page_url, str):
                page_url = str(page_url)
        
        return PageStepConfig(
            page_step_id=data.get('id', 0),
            page_url=page_url,
            page_name=data.get('name', ''),  # 页面步骤名称
            steps=steps,
            env_config=env_config,
        )
    
    def _build_test_case_config(self, data: dict, env_config: Optional[dict] = None, data_processor: Optional[DataProcessor] = None) -> TestCaseConfig:
        """构建测试用例配置
        
        Args:
            data: 用例数据
            env_config: 环境配置
            data_processor: 变量处理器
        """
        # 从环境配置获取base_url
        base_url = ''
        if env_config:
            base_url = env_config.get('base_url', '') or ''
            logger.info(f"使用环境配置: {env_config.get('name')}, base_url: {base_url}")
        
        page_steps = []
        
        for case_step in data.get('case_step_details', []):
            page_step_data = case_step.get('page_step', {})
            case_data_override = case_step.get('case_data') or {}
            if page_step_data:
                page_steps.append(self._build_page_step_config(page_step_data, base_url, data_processor, case_data_override, env_config))
        
        return TestCaseConfig(
            case_id=data.get('id', 0),
            case_name=data.get('name', ''),
            page_steps=page_steps,
            env_config=env_config,
        )
    
    def stop(self):
        """停止消费者"""
        self._stop_event.set()
        try:
            self.executor.stop()
        except Exception as e:
            logger.warning(f'executor.stop failed: {e}')

    async def close_executor(self) -> None:
        """关闭浏览器与 Playwright 驱动。"""
        try:
            await self.executor.close()
        except Exception as e:
            logger.warning(f'关闭执行器失败: {e}')


    async def run(self):
        """运行消费者"""
        self.ws_client.set_message_handler(self.handle_message)
        
        # 启动任务处理协程
        process_task = asyncio.create_task(self.process_tasks())
        
        # 启动WebSocket客户端
        await self.ws_client.run()
        
        # 停止任务处理
        self.stop()
        await process_task
