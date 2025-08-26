"""
持久化MCP客户端实现
解决LangChain MCP适配器每次工具调用都创建新会话的问题
"""
import asyncio
from typing import Dict, Any, Optional, List
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_core.tools import BaseTool
import logging
import weakref
import atexit

logger = logging.getLogger(__name__)

class PersistentMCPClient:
    """
    持久化MCP客户端，维持长连接会话
    解决PlaywrightMCP等有状态工具的会话问题
    """

    def __init__(self, server_configs: Dict[str, Any]):
        self.server_configs = server_configs
        self.client = MultiServerMCPClient(server_configs)
        self.sessions = {}
        self.tools_cache = {}
        self._closed = False

        # 注册清理函数
        atexit.register(self._cleanup_sync)

    async def get_persistent_tools(self, server_name: str) -> List[BaseTool]:
        """获取指定服务器的持久会话工具"""
        if self._closed:
            raise RuntimeError("Client has been closed")

        if server_name not in self.sessions:
            try:
                logger.info(f"Creating persistent session for server: {server_name}")

                # 创建持久会话
                session_context = self.client.session(server_name)
                session = await session_context.__aenter__()

                # 保存会话上下文管理器，用于后续清理
                self.sessions[server_name] = {
                    'session': session,
                    'context': session_context
                }

                # 加载工具并缓存
                tools = await load_mcp_tools(session)
                self.tools_cache[server_name] = tools

                logger.info(f"Created persistent session for {server_name} with {len(tools)} tools")

            except Exception as e:
                logger.error(f"Failed to create persistent session for {server_name}: {e}")
                raise

        return self.tools_cache.get(server_name, [])

    async def get_all_persistent_tools(self) -> List[BaseTool]:
        """获取所有服务器的持久工具"""
        all_tools = []
        for server_name in self.server_configs.keys():
            try:
                tools = await self.get_persistent_tools(server_name)
                all_tools.extend(tools)
            except Exception as e:
                logger.error(f"Failed to get tools from server {server_name}: {e}")
                continue

        logger.info(f"Total persistent tools loaded: {len(all_tools)}")
        return all_tools

    async def refresh_session(self, server_name: str) -> List[BaseTool]:
        """刷新指定服务器的会话（用于错误恢复）"""
        logger.info(f"Refreshing session for server: {server_name}")

        # 先关闭现有会话
        if server_name in self.sessions:
            await self._close_single_session(server_name)

        # 重新创建会话
        return await self.get_persistent_tools(server_name)

    async def _close_single_session(self, server_name: str):
        """关闭单个会话"""
        if server_name in self.sessions:
            session_info = self.sessions[server_name]
            try:
                await session_info['context'].__aexit__(None, None, None)
                logger.info(f"Closed session for {server_name}")
            except Exception as e:
                logger.error(f"Error closing session for {server_name}: {e}")
            finally:
                del self.sessions[server_name]
                if server_name in self.tools_cache:
                    del self.tools_cache[server_name]

    async def close_sessions(self):
        """关闭所有持久会话"""
        if self._closed:
            return

        logger.info("Closing all persistent MCP sessions...")

        for server_name in list(self.sessions.keys()):
            await self._close_single_session(server_name)

        self._closed = True
        logger.info("All MCP sessions closed")

    def _cleanup_sync(self):
        """同步清理函数（用于atexit）"""
        if not self._closed and self.sessions:
            logger.warning("Cleaning up unclosed MCP sessions...")
            # 在同步上下文中无法直接调用异步函数
            # 这里只是记录警告，实际清理需要在异步上下文中进行

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_sessions()

    def __del__(self):
        if not self._closed and self.sessions:
            logger.warning(f"PersistentMCPClient was not properly closed. {len(self.sessions)} sessions may leak.")


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
            self.clients = {}  # config_hash -> PersistentMCPClient
            self.session_contexts = {}  # user_project_key -> session_context
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

    async def get_tools_for_config(self, server_configs: Dict[str, Any],
                                   user_id: str = None, project_id: str = None) -> List[BaseTool]:
        """
        根据配置获取工具
        支持用户和项目级别的会话隔离
        """
        client = await self.get_persistent_client(server_configs)
        tools = await client.get_all_persistent_tools()

        # 如果提供了用户和项目信息，记录会话上下文
        if user_id and project_id:
            session_key = f"{user_id}_{project_id}"
            self.session_contexts[session_key] = {
                'config_hash': hash(str(sorted(server_configs.items()))),
                'client': client,
                'last_used': asyncio.get_event_loop().time()
            }
            logger.info(f"Recorded session context for user {user_id}, project {project_id}")

        return tools

    async def get_session_context(self, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        """获取用户项目的会话上下文"""
        session_key = f"{user_id}_{project_id}"
        return self.session_contexts.get(session_key)

    async def cleanup_all(self):
        """清理所有客户端"""
        logger.info("Cleaning up all MCP clients...")

        for config_hash, client in self.clients.items():
            try:
                await client.close_sessions()
            except Exception as e:
                logger.error(f"Error cleaning up client {config_hash}: {e}")

        self.clients.clear()
        self.session_contexts.clear()
        logger.info("All MCP clients and session contexts cleaned up")

    async def cleanup_user_session(self, user_id: str, project_id: str):
        """清理特定用户项目的会话"""
        session_key = f"{user_id}_{project_id}"
        if session_key in self.session_contexts:
            context = self.session_contexts[session_key]
            try:
                client = context['client']
                await client.close_sessions()
                logger.info(f"Cleaned up session for user {user_id}, project {project_id}")
            except Exception as e:
                logger.error(f"Error cleaning up session for {session_key}: {e}")
            finally:
                del self.session_contexts[session_key]


# 全局会话管理器实例
mcp_session_manager = GlobalMCPSessionManager()
