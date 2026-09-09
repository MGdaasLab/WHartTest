"""UI 自动化录制器会话管理。

管理「录制 Node 进程」（recorder/recorder_server.js）的生命周期：
spawn、stdin/stdout 行分隔 JSON-RPC 请求/响应配对、stdout 事件推送
（frame / actions）分发、最新帧槽位、优雅关闭与超时清理。

会话 Registry 为进程内单例：
    session_id -> RecorderSession（含 Node 进程、事件队列、归属用户）

线程模型：
    - stdin 写线程安全（加锁）
    - stdout 读线程把「响应」按 id 分发到 pending 队列，
      把「事件」写入事件队列（frame 只保留最新一帧，避免积压）
    - 消费者(consumer) 侧 asyncio 任务轮询取出并转发到前端
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger('ui_automation')

RECORDER_SERVER_SCRIPT = Path(__file__).parent / 'recorder_server.js'


def _server_script_path() -> Path:
    """录制服务脚本（可用环境变量 RECORDER_SERVER_SCRIPT 覆盖，测试用）。"""
    override = os.environ.get('RECORDER_SERVER_SCRIPT', '').strip()
    if override:
        return Path(override)
    return RECORDER_SERVER_SCRIPT

# 事件类型
EV_FRAME = 'frame'
EV_ACTIONS = 'actions'


class RecorderSessionError(RuntimeError):
    pass


class RecorderSessionMeta:
    """录制会话的 REST 侧元信息（归属、目标页面/步骤、开关）。"""

    def __init__(
        self,
        *,
        user_id: str,
        project_id: int,
        page_id: Optional[int],
        page_step_id: Optional[int],
        create_elements: bool,
        create_steps: bool,
        base_url: str,
        viewport: dict,
        kind: str = 'record',          # record=步骤录制 / auth=登录态录制
        pre_page_step_id: Optional[int] = None,  # 前置页面步骤（录制启动前自动执行）
        env_config_id: Optional[int] = None,     # 所属环境配置（保存登录态时绑定到该环境）
        auth_state_id: Optional[int] = None,  # 录制表单选择的登录态（绑定录制步骤，启动时按此注入）
    ):
        self.user_id = user_id
        self.project_id = project_id
        self.page_id = page_id
        self.page_step_id = page_step_id
        self.create_elements = create_elements
        self.create_steps = create_steps
        self.base_url = base_url
        self.viewport = dict(viewport)
        self.kind = kind
        self.pre_page_step_id = pre_page_step_id
        self.env_config_id = env_config_id
        self.auth_state_id = auth_state_id


class RecorderSession:
    """单个录制会话（对应一个 Node 录制进程）。"""

    def __init__(
        self,
        session_id: str,
        skill_dir: str,
        user_id: str,
        project_id: int,
        env,
    ):
        self.session_id = session_id
        self.skill_dir = skill_dir
        self.user_id = user_id
        self.project_id = project_id
        self.created_at = time.time()
        self.last_activity = time.time()

        self._proc: Optional[subprocess.Popen] = None
        self._pending: Dict[str, Any] = {}
        self._write_lock = threading.Lock()
        self._events: deque = deque(maxlen=200)      # actions/status 事件
        self._latest_frame: Optional[dict] = None
        self._state_lock = threading.Lock()
        self._closed = False
        self._env = env

        # 顺序写 stdin，避免并发请求乱序
        self._chain = threading.Lock()

    # ------------------------------------------------------------------
    # 进程生命周期
    # ------------------------------------------------------------------

    def start(self, timeout: float = 120.0) -> None:
        """启动 Node 进程并 ping 探活（首次可能触发 npm install）。"""
        if self._proc is not None:
            return
        script_path = _server_script_path()
        if not script_path.exists():
            raise RecorderSessionError(f'录制服务脚本不存在: {script_path}')
        if not self.skill_dir or not os.path.isdir(self.skill_dir):
            raise RecorderSessionError(f'playwright skill 目录无效: {self.skill_dir}')

        merged_env = os.environ.copy()
        merged_env.update({k: str(v) for k, v in (self._env or {}).items()})
        merged_env.setdefault('HEADLESS', 'true')

        cmd = ['node', str(script_path), '--skill-dir', self.skill_dir]
        logger.info('[recorder] spawn: %s', ' '.join(cmd))
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
                env=merged_env,
            )
        except OSError as exc:
            raise RecorderSessionError(f'无法启动 node 录制进程: {exc}') from exc

        t = threading.Thread(target=self._stdout_reader, daemon=True)
        t.start()
        t = threading.Thread(target=self._stderr_reader, daemon=True)
        t.start()

        try:
            self.request('ping', {}, timeout=timeout)
        except RecorderSessionError:
            self.kill()
            raise

    def request(self, method: str, params: dict, timeout: float = 30.0) -> dict:
        """同步发送请求并等待响应（超时则判定进程不可用）。"""
        proc = self._proc
        if proc is None or proc.poll() is not None:
            raise RecorderSessionError('录制进程已退出')

        req_id = uuid.uuid4().hex
        queue: 'queue.Queue[Optional[dict]]' = __import__('queue').Queue(maxsize=1)
        with self._state_lock:
            if self._closed:
                raise RecorderSessionError('录制会话已关闭')
            self._pending[req_id] = queue

        try:
            with self._chain:
                proc.stdin.write(json.dumps({
                    'id': req_id,
                    'method': method,
                    'params': params,
                }) + '\n')
                proc.stdin.flush()
            result = queue.get(timeout=timeout)
        except Exception as exc:
            with self._state_lock:
                self._pending.pop(req_id, None)
            if isinstance(exc, RecorderSessionError):
                raise
            raise RecorderSessionError(f'录制请求超时（{method}）: {exc}') from exc
        finally:
            self.last_activity = time.time()

        if not result.get('ok'):
            raise RecorderSessionError(result.get('error') or f'{method} 失败')
        return result

    def save_login_state(self, timeout: float = 30.0) -> dict:
        """保存当前录制浏览器上下文的登录态快照（storageState）。

        快照包含 cookies + localStorage，同时覆盖 Cookie/Session 会话系统
        与 JWT(localStorage) 现代系统。由平台绑定到录制会话所属的环境配置。
        """
        result = self.request('save_login_state', {}, timeout=timeout)
        storage_state = result.get('state', {}).get('storage_state')
        if not isinstance(storage_state, dict):
            raise RecorderSessionError('录制器未返回有效的登录态快照')
        return storage_state

    def notify(self, method: str, params: dict) -> None:
        """fire-and-forget 写入（输入事件等高频率消息，不等待响应）。"""
        proc = self._proc
        if proc is None or proc.poll() is not None:
            raise RecorderSessionError('录制进程已退出')
        req_id = uuid.uuid4().hex
        try:
            with self._chain:
                proc.stdin.write(json.dumps({
                    'id': req_id,
                    'method': method,
                    'params': params,
                }) + '\n')
                proc.stdin.flush()
            self.last_activity = time.time()
        except Exception as exc:
            raise RecorderSessionError(f'录制消息发送失败: {exc}') from exc

    # ------------------------------------------------------------------
    # 事件读取（供消费者轮询）
    # ------------------------------------------------------------------

    def take_latest_frame(self) -> Optional[dict]:
        """取走最新一帧（陈旧帧直接丢弃），无帧返回 None。"""
        with self._state_lock:
            frame = self._latest_frame
            self._latest_frame = None
            return frame

    def drain_events(self) -> list[dict]:
        """取走全部排队事件（actions / status）。"""
        with self._state_lock:
            items = list(self._events)
            self._events.clear()
            return items

    # ------------------------------------------------------------------
    # stdout/stderr 读取线程
    # ------------------------------------------------------------------

    def _stdout_reader(self) -> None:
        proc = self._proc
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(msg, dict):
                continue

            if 'event' in msg:
                self._dispatch_event(msg['event'], msg.get('data'))
                continue

            req_id = msg.get('id')
            if not req_id:
                continue
            with self._state_lock:
                queue = self._pending.pop(req_id, None)
            if queue is not None:
                queue.put(msg)

        # 进程退出：唤醒所有 pending
        with self._state_lock:
            pending = list(self._pending.values())
            self._pending.clear()
        for queue in pending:
            queue.put({'ok': False, 'error': '录制进程已退出'})

    def _stderr_reader(self) -> None:
        proc = self._proc
        for line in proc.stderr:
            line = line.strip()
            if line:
                logger.debug('[recorder stderr] %s', line)

    def _dispatch_event(self, event: str, data: Any) -> None:
        if event == EV_FRAME and isinstance(data, dict):
            with self._state_lock:
                self._latest_frame = data
        elif event == EV_ACTIONS:
            with self._state_lock:
                self._events.append({'type': EV_ACTIONS, 'data': data})
        elif event == EV_STATUS:
            with self._state_lock:
                self._events.append({'type': EV_STATUS, 'data': data})

    # ------------------------------------------------------------------
    # 关闭
    # ------------------------------------------------------------------

    def close(self, graceful: bool = True) -> None:
        """关闭会话：先优雅 close（若进程存活），再终止。"""
        with self._state_lock:
            if self._closed:
                return
            self._closed = True
        proc = self._proc
        if proc is None:
            return
        try:
            if graceful and proc.poll() is None:
                try:
                    self.request('close', {}, timeout=5.0)
                except Exception:
                    pass
        finally:
            self.kill()

    def kill(self) -> None:
        proc = self._proc
        if proc is None:
            return
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=3)
        except Exception as exc:
            logger.warning('[recorder] kill error: %s', exc)
        finally:
            self._proc = None

    @property
    def alive(self) -> bool:
        proc = self._proc
        return proc is not None and proc.poll() is None


class RecorderSessionManager:
    """录制会话注册表（进程内单例）。"""

    def __init__(self):
        self._sessions: Dict[str, RecorderSession] = {}
        self._metas: Dict[str, RecorderSessionMeta] = {}
        self._lock = threading.RLock()
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    # ------------------------------------------------------------------

    def create_session(
        self,
        *,
        user_id: str,
        project_id: int,
        skill_dir: str,
        env: Optional[dict] = None,
    ) -> RecorderSession:
        session_id = uuid.uuid4().hex
        session = RecorderSession(
            session_id=session_id,
            skill_dir=skill_dir,
            user_id=user_id,
            project_id=project_id,
            env=env,
        )
        with self._lock:
            self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Optional[RecorderSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def list_by_user(self, user_id: str) -> list[RecorderSession]:
        with self._lock:
            return [s for s in self._sessions.values() if s.user_id == user_id]

    def close(self, session_id: str, graceful: bool = True) -> None:
        with self._lock:
            session = self._sessions.pop(session_id, None)
            self._metas.pop(session_id, None)
        if session:
            try:
                session.close(graceful=graceful)
            except Exception as exc:
                logger.warning('[recorder] close session %s error: %s', session_id, exc)

    def close_all_by_user(self, user_id: str) -> int:
        """关闭某用户全部会话（如 WS 断开时清理），返回关闭数量。"""
        with self._lock:
            ids = [sid for sid, s in self._sessions.items() if s.user_id == user_id]
        for sid in ids:
            self.close(sid)
        return len(ids)

    # ------------------------------------------------------------------
    # 元信息（REST 创建时登记，WS/结束阶段读取）
    # ------------------------------------------------------------------

    def set_meta(self, session_id: str, meta: RecorderSessionMeta) -> None:
        with self._lock:
            self._metas[session_id] = meta

    def get_meta(self, session_id: str) -> Optional[RecorderSessionMeta]:
        with self._lock:
            return self._metas.get(session_id)

    def pop_meta(self, session_id: str) -> Optional[RecorderSessionMeta]:
        with self._lock:
            return self._metas.pop(session_id, None)

    # ------------------------------------------------------------------

    def _cleanup_loop(self) -> None:
        """定期清理：空闲超过 30 分钟或进程已死的会话。"""
        idle_timeout = float(os.environ.get('RECORDER_SESSION_IDLE_TIMEOUT_SECONDS', '1800'))
        while True:
            time.sleep(60)
            try:
                now = time.time()
                with self._lock:
                    dead = [
                        sid for sid, s in self._sessions.items()
                        if not s.alive or (now - s.last_activity) > idle_timeout
                    ]
                for sid in dead:
                    logger.info('[recorder] 清理会话 %s', sid)
                    self.close(sid)
            except Exception as exc:
                logger.warning('[recorder] cleanup loop error: %s', exc)


# 进程内单例
recorder_manager = RecorderSessionManager()