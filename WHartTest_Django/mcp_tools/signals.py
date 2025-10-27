"""
Django信号处理器
在应用关闭时自动清理MCP会话
"""
import asyncio
import logging
import atexit

logger = logging.getLogger(__name__)


def cleanup_mcp_sessions_on_exit():
    """在应用退出时清理MCP会话"""
    try:
        from mcp_tools.persistent_client import mcp_session_manager

        try:
            asyncio.run(mcp_session_manager.cleanup_all())
            logger.info("MCP sessions cleaned up on application exit")
        except RuntimeError as exc:
            logger.debug(f"MCP cleanup skipped during exit: {exc}")
    except Exception as exc:
        logger.error(f"Error cleaning up MCP sessions on exit: {exc}", exc_info=True)


atexit.register(cleanup_mcp_sessions_on_exit)
