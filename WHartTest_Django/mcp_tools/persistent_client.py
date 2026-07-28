"""
持久化MCP客户端实现
解决LangChain MCP适配器每次工具调用都创建新会话的问题
"""
import asyncio
import time
from typing import Dict, Any, Optional, List
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_core.tools import BaseTool
import logging
import atexit

try:
    import httpx
    _CONNECTION_ERRORS = (ConnectionError, OSError, httpx.HTTPStatusError, httpx.ConnectError)
except ImportError:
    _CONNECTION_ERRORS = (ConnectionError, OSError)

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int, *, minimum: int | None = None) -> int:
    """Parse positive int env vars safely; fall back to default on bad values."""
    import os
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        value = default
    else:
        try:
            value = int(str(raw).strip())
        except (TypeError, ValueError):
            logger.warning("Invalid %s=%r, using default %s", name, raw, default)
            value = default
    if minimum is not None:
        value = max(minimum, value)
    return value


def _is_connection_error(exc: BaseException) -> bool:
    """判断是否为连接类错误（服务未启动/不可达）"""
    if isinstance(exc, _CONNECTION_ERRORS):
        return True
    if isinstance(exc, ExceptionGroup):
        return all(_is_connection_error(e) for e in exc.exceptions)
    return False


class _PersistentSessionEntry:
    """管理长寿命MCP会话，在单独任务中处理上下文进入/退出。"""

    def __init__(self, server_name: str, session_context):
        self.server_name = server_name
        self.session_context = session_context
        self.loop = asyncio.get_running_loop()

        self.session = None
        self._ready_event = asyncio.Event()
        self._close_requested = asyncio.Event()
        self._closed_event = asyncio.Event()
        self._error: Optional[BaseException] = None
        self.load_lock = asyncio.Lock()

        self._task = asyncio.create_task(
            self._run(),
            name=f"mcp-session[{server_name}]",
        )

    async def _run(self):
        try:
            async with self.session_context as session:
                self.session = session
                self._ready_event.set()
                await self._close_requested.wait()
        except Exception as exc:
            self._error = exc
            if not self._ready_event.is_set():
                self._ready_event.set()
            if _is_connection_error(exc):
                logger.warning(
                    "MCP 服务 [%s] 不可达，跳过（服务可能未启动）",
                    self.server_name,
                )
            else:
                logger.error(
                    "MCP 会话 [%s] 异常: %s",
                    self.server_name,
                    exc,
                    exc_info=True,
                )
        finally:
            self.session = None
            self._closed_event.set()

    async def get_session(self):
        await self._ready_event.wait()
        if self._error is not None:
            raise self._error
        if self.session is None:
            raise RuntimeError(f"Session {self.server_name} is not available")
        return self.session

    def _request_close(self):
        if self._close_requested.is_set():
            return

        if self.loop.is_running():
            try:
                running_loop = asyncio.get_running_loop()
            except RuntimeError:
                running_loop = None

            if running_loop is self.loop:
                self._close_requested.set()
            else:
                try:
                    self.loop.call_soon_threadsafe(self._close_requested.set)
                except RuntimeError:
                    self._close_requested.set()
        else:
            self._close_requested.set()

    async def close(self):
        self._request_close()

        if self._closed_event.is_set():
            await self._task
            return

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop is self.loop:
            await self._task
            return

        try:
            future = asyncio.run_coroutine_threadsafe(self._await_task(), self.loop)
        except RuntimeError:
            return

        await asyncio.wrap_future(future)

    async def _await_task(self):
        await self._task


class PersistentMCPClient:
    """
    持久化MCP客户端，维持长连接会话
    解决PlaywrightMCP等有状态工具的会话问题
    """

    def __init__(self, server_configs: Dict[str, Any]):
        self.server_configs = server_configs
        self.client = MultiServerMCPClient(server_configs)
        self.sessions: Dict[str, _PersistentSessionEntry] = {}
        self.tools_cache: Dict[str, List[BaseTool]] = {}
        self._sessions_lock = asyncio.Lock()
        self._closed = False

        # 注册清理函数
        atexit.register(self._cleanup_sync)

    async def get_persistent_tools(self, server_name: str) -> List[BaseTool]:
        """获取指定服务器的持久会话工具；在会话失效时自动重建一次"""
        if self._closed:
            raise RuntimeError("Client has been closed")

        # 内部函数：创建新的会话项
        async def _create_new_session_entry() -> _PersistentSessionEntry:
            logger.info(f"Creating persistent session for server: {server_name}")
            session_context = self.client.session(server_name)
            return _PersistentSessionEntry(server_name, session_context)

        # 获取或创建 session_entry
        session_entry = self.sessions.get(server_name)
        if session_entry is None:
            async with self._sessions_lock:
                session_entry = self.sessions.get(server_name)
                if session_entry is None:
                    session_entry = await _create_new_session_entry()
                    self.sessions[server_name] = session_entry

        # 第一次尝试获取session
        try:
            session = await session_entry.get_session()
        except Exception as exc:
            if _is_connection_error(exc):
                logger.warning(
                    "MCP 服务 [%s] 连接失败，尝试重连...",
                    server_name,
                )
            else:
                logger.error(
                    "MCP 会话 [%s] 异常，尝试重建: %s",
                    server_name,
                    exc,
                    exc_info=True,
                )
            # 移除旧的并重建一次
            async with self._sessions_lock:
                if self.sessions.get(server_name) is session_entry:
                    self.sessions.pop(server_name, None)
            # 重建
            session_entry = await _create_new_session_entry()
            async with self._sessions_lock:
                self.sessions[server_name] = session_entry
            # 第二次尝试
            session = await session_entry.get_session()

        # 加载工具（带双重检查并发保护）
        if server_name not in self.tools_cache:
            async with session_entry.load_lock:
                if server_name not in self.tools_cache:
                    try:
                        tools = await load_mcp_tools(session)
                    except Exception as exc:
                        logger.error(
                            f"Failed to load tools for {server_name}: {exc}",
                            exc_info=True,
                        )
                        # 关闭并移除当前失效会话
                        await session_entry.close()
                        async with self._sessions_lock:
                            if self.sessions.get(server_name) is session_entry:
                                self.sessions.pop(server_name, None)
                        raise
                    self.tools_cache[server_name] = tools
                    logger.info(
                        f"Created persistent session for {server_name} with {len(tools)} tools"
                    )

        return self.tools_cache.get(server_name, [])

    async def get_all_persistent_tools(self) -> List[BaseTool]:
        """获取所有服务器的持久工具"""
        all_tools = []
        for server_name in self.server_configs.keys():
            try:
                tools = await self.get_persistent_tools(server_name)
                all_tools.extend(tools)
            except Exception as exc:
                if _is_connection_error(exc):
                    logger.warning(
                        "MCP 服务 [%s] 不可用，已跳过（如需使用请启动该服务）",
                        server_name,
                    )
                else:
                    logger.error(
                        "加载 MCP 服务 [%s] 工具失败: %s",
                        server_name,
                        exc,
                    )
                continue

        logger.info(f"Total persistent tools loaded: {len(all_tools)}")
        return all_tools

    async def refresh_session(self, server_name: str) -> List[BaseTool]:
        """刷新指定服务器的会话（用于错误恢复）"""
        logger.info(f"Refreshing session for server: {server_name}")
        await self._close_single_session(server_name)
        return await self.get_persistent_tools(server_name)

    async def _close_single_session(self, server_name: str):
        """关闭单个会话"""
        async with self._sessions_lock:
            session_entry = self.sessions.pop(server_name, None)
            self.tools_cache.pop(server_name, None)

        if session_entry is None:
            return

        try:
            await session_entry.close()
            logger.info(f"Closed session for {server_name}")
        except Exception as exc:
            logger.error(f"Error closing session for {server_name}: {exc}", exc_info=True)

    async def close_sessions(self):
        """关闭所有持久会话"""
        if self._closed:
            return

        logger.info("Closing all persistent MCP sessions...")

        async with self._sessions_lock:
            sessions_snapshot = list(self.sessions.items())
            self.sessions.clear()
            self.tools_cache.clear()

        for server_name, session_entry in sessions_snapshot:
            try:
                await session_entry.close()
                logger.info(f"Closed session for {server_name}")
            except Exception as exc:
                logger.error(
                    f"Error closing session for {server_name}: {exc}",
                    exc_info=True,
                )

        self._closed = True
        logger.info("All MCP sessions closed")

    def _cleanup_sync(self):
        """同步清理函数（用于atexit）"""
        if not self._closed and self.sessions:
            logger.warning(
                f"MCP sessions were not properly closed: {list(self.sessions.keys())}. "
                f"Please call close_sessions() before application shutdown."
            )
            self._closed = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_sessions()

    def __del__(self):
        if not self._closed and self.sessions:
            logger.warning(
                f"PersistentMCPClient was not properly closed. "
                f"{len(self.sessions)} sessions may leak. "
                f"Always use 'async with' or call close_sessions() explicitly."
            )


class GlobalMCPSessionManager:
    """
    全局MCP会话管理器
    在Django应用中管理所有MCP会话
    支持跨对话轮次的浏览器状态保持
    """
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.clients = {}  # config_hash -> PersistentMCPClient (legacy shared mode)
            self.session_clients = {}  # session_key -> PersistentMCPClient
            self.session_contexts = {}  # session_key -> session_context
            self.tools_cache = {}  # session_key -> tools
            # Bound cache growth to reduce long-running memory pressure.
            self.max_session_clients = _env_int(
                "MCP_MAX_SESSION_CLIENTS", 50, minimum=1
            )
            self.session_idle_timeout_seconds = _env_int(
                "MCP_SESSION_IDLE_TIMEOUT_SECONDS", 1800, minimum=60
            )
            # Cap close work per prune call; raise under burst to drain faster.
            self.prune_max_close_per_call = _env_int(
                "MCP_PRUNE_MAX_CLOSE_PER_CALL", 10, minimum=1
            )
            self._initialized = True

    async def get_persistent_client(self, server_configs: Dict[str, Any]) -> PersistentMCPClient:
        """获取或创建持久化客户端"""
        config_hash = hash(str(sorted(server_configs.items())))

        async with self._lock:
            if config_hash not in self.clients:
                logger.info(f"Creating new persistent MCP client for config hash: {config_hash}")
                client = PersistentMCPClient(server_configs)
                self.clients[config_hash] = client

            return self.clients[config_hash]

    def _touch_session(self, session_key: str) -> None:
        ctx = self.session_contexts.get(session_key)
        if not isinstance(ctx, dict):
            return
        ctx['last_used'] = time.monotonic()

    async def _prune_idle_and_overflow_sessions(self) -> None:
        """Close idle/overflow session-scoped MCP clients to avoid unbounded growth.

        Snapshot/pop under lock, close outside lock, and cap work per call so
        get_tools_for_session is not blocked closing many browsers at once.
        """
        max_close_per_call = getattr(self, "prune_max_close_per_call", 10)
        to_close = []  # list[(session_key, client)]

        async with self._lock:
            now = time.monotonic()
            idle_keys = []
            for key, ctx in list(self.session_contexts.items()):
                if not isinstance(ctx, dict):
                    continue
                last_used = ctx.get("last_used")
                try:
                    last_used_f = float(last_used) if last_used is not None else 0.0
                except (TypeError, ValueError):
                    last_used_f = 0.0
                # Compat: older code stored event-loop time; treat huge future values as now.
                if last_used_f > now + 3600:
                    last_used_f = now
                    ctx["last_used"] = now
                if (now - last_used_f) > self.session_idle_timeout_seconds:
                    idle_keys.append(key)

            for key in idle_keys:
                if len(to_close) >= max_close_per_call:
                    break
                self.tools_cache.pop(key, None)
                self.session_contexts.pop(key, None)
                client = self.session_clients.pop(key, None)
                if client is not None:
                    to_close.append((key, client))

            overflow = len(self.session_clients) - self.max_session_clients
            if overflow > 0 and len(to_close) < max_close_per_call:
                ranked = []
                for key in list(self.session_clients.keys()):
                    ctx = self.session_contexts.get(key) or {}
                    last_used = 0.0
                    if isinstance(ctx, dict):
                        try:
                            last_used = float(ctx.get("last_used") or 0.0)
                        except (TypeError, ValueError):
                            last_used = 0.0
                    ranked.append((last_used, key))
                ranked.sort(key=lambda item: item[0])
                remaining = min(overflow, max_close_per_call - len(to_close))
                for _, key in ranked[:remaining]:
                    self.tools_cache.pop(key, None)
                    self.session_contexts.pop(key, None)
                    client = self.session_clients.pop(key, None)
                    if client is not None:
                        to_close.append((key, client))

        for session_key, client in to_close:
            try:
                await client.close_sessions()
                logger.info(
                    "Closed MCP session client: %s; remaining=%s",
                    session_key,
                    len(self.session_clients),
                )
            except Exception as exc:
                logger.error(
                    "Error closing MCP session client %s: %s",
                    session_key,
                    exc,
                    exc_info=True,
                )

    async def cleanup_user_session_by_key(self, session_key: str) -> None:
        """Close one session client by exact session_key."""
        async with self._lock:
            self.tools_cache.pop(session_key, None)
            self.session_contexts.pop(session_key, None)
            client = self.session_clients.pop(session_key, None)
        if not client:
            return
        try:
            await client.close_sessions()
            logger.info(
                "Closed MCP session client: %s; remaining=%s",
                session_key,
                len(self.session_clients),
            )
        except Exception as exc:
            logger.error(
                "Error closing MCP session client %s: %s",
                session_key,
                exc,
                exc_info=True,
            )

    async def get_tools_for_session(
        self,
        server_configs: Dict[str, Any],
        user_id: str,
        project_id: str,
        session_id: str = None,
    ) -> List[BaseTool]:
        """
        根据配置和会话ID获取工具
        每个session_id创建独立的MCP客户端，实现真正的并发隔离
        
        Args:
            server_configs: MCP服务器配置
            user_id: 用户ID
            project_id: 项目ID
            session_id: 对话会话ID（可选，如果提供则按session缓存）
        
        Returns:
            工具列表
        """
        # 构建会话键：包含用户、项目和对话会话ID
        if session_id:
            session_key = f"{user_id}_{project_id}_{session_id}"
        else:
            session_key = f"{user_id}_{project_id}"
        
        # 检查是否已有缓存的工具
        await self._prune_idle_and_overflow_sessions()

        if session_key in self.tools_cache:
            logger.info(f"Reusing cached tools for session: {session_key}")
            self._touch_session(session_key)
            return self.tools_cache[session_key]
        
        # 为每个session_key创建独立的MCP客户端
        # 这样每个并发测试用例都有自己的浏览器实例
        async with self._lock:
            if session_key not in self.session_clients:
                logger.info(f"Creating independent MCP client for session: {session_key}")
                client = PersistentMCPClient(server_configs)
                self.session_clients[session_key] = client
                logger.info(f"Independent client created. Total session clients: {len(self.session_clients)}")
        
        client = self.session_clients[session_key]
        tools = await client.get_all_persistent_tools()
        
        # 仅在成功加载到工具时进行缓存，避免缓存空列表导致后续无法恢复
        if tools:
            self.tools_cache[session_key] = tools
            logger.info(f"Cached {len(tools)} tools for session: {session_key}")
        else:
            logger.warning(f"No tools loaded for session: {session_key}; skip caching")
        
        # 记录会话上下文
        self.session_contexts[session_key] = {
            'client': client,
            'last_used': time.monotonic(),
            'user_id': user_id,
            'project_id': project_id,
            'session_id': session_id
        }
        
        return tools

    async def get_tools_for_config(
        self,
        server_configs: Dict[str, Any],
        user_id: str = None,
        project_id: str = None,
        session_id: str = None,
    ) -> List[BaseTool]:
        """
        根据配置获取工具（兼容旧接口）
        支持用户和项目级别的会话隔离
        
        如果提供了session_id，则按会话缓存工具
        否则按用户+项目缓存
        """
        if user_id and project_id:
            return await self.get_tools_for_session(
                server_configs,
                user_id=user_id,
                project_id=project_id,
                session_id=session_id
            )
        
        # 降级到直接获取工具（不缓存）
        client = await self.get_persistent_client(server_configs)
        return await client.get_all_persistent_tools()

    async def get_session_context(self, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        """获取用户项目的会话上下文"""
        session_key = f"{user_id}_{project_id}"
        return self.session_contexts.get(session_key)

    async def cleanup_all(self):
        """清理所有客户端"""
        logger.info("Cleaning up all MCP clients...")

        # 清理共享客户端
        for config_hash, client in list(self.clients.items()):
            try:
                await client.close_sessions()
            except Exception as exc:
                logger.error(f"Error cleaning up shared client {config_hash}: {exc}", exc_info=True)

        # 清理独立的会话客户端
        for session_key, client in list(self.session_clients.items()):
            try:
                await client.close_sessions()
                logger.info(f"Cleaned up session client: {session_key}")
            except Exception as exc:
                logger.error(f"Error cleaning up session client {session_key}: {exc}", exc_info=True)

        self.clients.clear()
        self.session_clients.clear()
        self.session_contexts.clear()
        self.tools_cache.clear()
        logger.info("All MCP clients and session contexts cleaned up")

    async def cleanup_user_session(self, user_id: str, project_id: str, session_id: str = None):
        """
        Close a specific user/project MCP session (and independent client).

        Always attempts to close session_clients even if session_contexts is missing,
        to avoid leaked browser-backed MCP clients.
        """
        if session_id:
            session_key = f"{user_id}_{project_id}_{session_id}"
        else:
            session_key = f"{user_id}_{project_id}"

        await self.cleanup_user_session_by_key(session_key)

    async def cleanup_all_user_sessions(self, user_id: str, project_id: str):
        """清理用户在某个项目下的所有会话，包括关闭所有独立客户端"""
        prefix = f"{user_id}_{project_id}_"

        # Union of both maps so orphan clients without context are also closed.
        matching_keys = sorted(
            {
                key
                for key in list(self.session_contexts.keys()) + list(self.session_clients.keys())
                if key.startswith(prefix) or key == f"{user_id}_{project_id}"
            }
        )

        logger.info(
            f"Cleaning up {len(matching_keys)} sessions for user {user_id}, project {project_id}"
        )

        for session_key in matching_keys:
            await self.cleanup_user_session_by_key(session_key)

        logger.info(f"Cleaned up all sessions for user {user_id}, project {project_id}")


# 全局会话管理器实例
mcp_session_manager = GlobalMCPSessionManager()
