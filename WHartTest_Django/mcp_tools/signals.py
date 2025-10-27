"""
Django信号处理器
在应用关闭时自动清理MCP会话
"""
import asyncio
import logging
from django.apps import AppConfig
from django.core.signals import request_finished
from django.dispatch import receiver
import atexit

logger = logging.getLogger(__name__)

def cleanup_mcp_sessions_on_exit():
    """在应用退出时清理MCP会话"""
    try:
        from mcp_tools.persistent_client import mcp_session_manager
        
        # 创建新的事件循环来运行清理
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(mcp_session_manager.cleanup_all())
            logger.info("MCP sessions cleaned up on application exit")
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Error cleaning up MCP sessions on exit: {e}")

# 注册退出时的清理函数
atexit.register(cleanup_mcp_sessions_on_exit)
