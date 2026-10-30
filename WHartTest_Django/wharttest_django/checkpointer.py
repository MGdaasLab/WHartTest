"""
LangGraph Checkpointer 工厂模块

根据 DATABASE_TYPE 环境变量自动选择合适的 Checkpointer：
- sqlite: 使用 SqliteSaver/AsyncSqliteSaver（默认，本地开发）
- postgres: 使用 PostgresSaver/AsyncPostgresSaver（生产环境）
"""
import os
from contextlib import asynccontextmanager, contextmanager
from typing import Optional
from django.conf import settings

from wharttest_django.data_variant import (
    get_checkpoint_sqlite_path,
    get_postgres_db_name,
)


def get_database_type() -> str:
    """获取数据库类型配置（每次调用时读取，确保环境变量已加载）"""
    return os.environ.get('DATABASE_TYPE', 'postgres')


def get_db_connection_string() -> str:
    """获取数据库连接字符串"""
    database_type = get_database_type()
    if database_type == 'postgres':
        user = os.environ.get('POSTGRES_USER', 'postgres')
        password = os.environ.get('POSTGRES_PASSWORD', 'postgres')
        host = os.environ.get('POSTGRES_HOST', '127.0.0.1')
        # 与 settings.DATABASES 的默认端口保持一致（该处默认 8919，此处此前默认 5432 导致独立进程/干净环境下连不上）
        port = os.environ.get('POSTGRES_PORT', '8919')
        db = get_postgres_db_name(settings.BASE_DIR)
        return f"postgresql://{user}:{password}@{host}:{port}/{db}"
    else:
        return get_checkpoint_sqlite_path(settings.BASE_DIR)


def get_sqlite_path() -> str:
    """获取 SQLite 文件路径（仅用于 SQLite 模式的文件存在性检查）"""
    return get_checkpoint_sqlite_path(settings.BASE_DIR)


@asynccontextmanager
async def get_async_checkpointer():
    """
    获取异步 Checkpointer 的上下文管理器
    
    用法:
        async with get_async_checkpointer() as checkpointer:
            # 使用 checkpointer
    """
    conn_string = get_db_connection_string()
    
    if get_database_type() == 'postgres':
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        async with AsyncPostgresSaver.from_conn_string(conn_string) as checkpointer:
            await checkpointer.setup()
            yield checkpointer
    else:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        async with AsyncSqliteSaver.from_conn_string(conn_string) as checkpointer:
            yield checkpointer


@contextmanager
def get_sync_checkpointer():
    """
    获取同步 Checkpointer 的上下文管理器
    
    用法:
        with get_sync_checkpointer() as checkpointer:
            # 使用 checkpointer
    """
    conn_string = get_db_connection_string()
    
    if get_database_type() == 'postgres':
        from langgraph.checkpoint.postgres import PostgresSaver
        with PostgresSaver.from_conn_string(conn_string) as checkpointer:
            checkpointer.setup()
            yield checkpointer
    else:
        from langgraph.checkpoint.sqlite import SqliteSaver
        with SqliteSaver.from_conn_string(conn_string) as checkpointer:
            yield checkpointer


def delete_checkpoints_by_thread_id(thread_id: str) -> int:
    """
    根据 thread_id 删除 checkpoints
    
    返回删除的记录数
    """
    if get_database_type() == 'postgres':
        import psycopg2
        conn_string = get_db_connection_string()
        try:
            conn = psycopg2.connect(conn_string)
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM checkpoints WHERE thread_id = %s", (thread_id,))
                deleted_count = cursor.rowcount
                conn.commit()
                return deleted_count
            finally:
                conn.close()
        except psycopg2.errors.UndefinedTable:
            return 0
        except Exception:
            return 0
    else:
        import sqlite3
        db_path = get_sqlite_path()
        if not os.path.exists(db_path):
            return 0
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count
        finally:
            conn.close()


def delete_checkpoints_batch(thread_ids: list) -> int:
    """
    批量删除多个 thread_id 的 checkpoints
    
    返回删除的总记录数
    """
    if not thread_ids:
        return 0
    
    if get_database_type() == 'postgres':
        import psycopg2
        conn_string = get_db_connection_string()
        try:
            conn = psycopg2.connect(conn_string)
            try:
                cursor = conn.cursor()
                # PostgreSQL 使用 ANY 语法
                cursor.execute("DELETE FROM checkpoints WHERE thread_id = ANY(%s)", (thread_ids,))
                deleted_count = cursor.rowcount
                conn.commit()
                return deleted_count
            finally:
                conn.close()
        except psycopg2.errors.UndefinedTable:
            return 0
        except Exception:
            return 0
    else:
        import sqlite3
        db_path = get_sqlite_path()
        if not os.path.exists(db_path):
            return 0
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            # SQLite 使用 IN 语法
            placeholders = ','.join('?' * len(thread_ids))
            cursor.execute(f"DELETE FROM checkpoints WHERE thread_id IN ({placeholders})", thread_ids)
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count
        finally:
            conn.close()


def check_history_exists() -> bool:
    """
    检查聊天历史存储是否存在（SQLite 文件或 PostgreSQL 表）
    """
    if get_database_type() == 'postgres':
        import psycopg2
        conn_string = get_db_connection_string()
        try:
            conn = psycopg2.connect(conn_string)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'checkpoints')")
                result = cursor.fetchone()
                return result[0] if result else False
            finally:
                conn.close()
        except Exception:
            return False
    else:
        db_path = get_sqlite_path()
        return os.path.exists(db_path)


def get_thread_ids_by_prefix(prefix: str) -> list:
    """
    根据前缀查询所有匹配的 thread_id

    返回 thread_id 列表
    """
    if get_database_type() == 'postgres':
        import psycopg2
        conn_string = get_db_connection_string()
        try:
            conn = psycopg2.connect(conn_string)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT thread_id FROM checkpoints WHERE thread_id LIKE %s", (prefix + '%',))
                rows = cursor.fetchall()
                return [row[0] for row in rows]
            finally:
                conn.close()
        except psycopg2.errors.UndefinedTable:
            # checkpoints 表不存在，返回空列表
            return []
        except Exception:
            return []
    else:
        import sqlite3
        db_path = get_sqlite_path()
        if not os.path.exists(db_path):
            return []
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT thread_id FROM checkpoints WHERE thread_id LIKE ?", (prefix + '%',))
            rows = cursor.fetchall()
            return [row[0] for row in rows]
        finally:
            conn.close()


def rollback_checkpoints_to_count(thread_id: str, keep_count: int) -> int:
    """
    回滚对话历史，只保留前 keep_count 条消息

    LangGraph PostgreSQL 的存储结构：
    - checkpoints 表：存储 checkpoint 元数据，channel_versions.messages 指向 blob 版本
    - checkpoint_blobs 表：存储实际的消息数据（msgpack 格式）

    回滚策略：找到消息数量 <= keep_count 的最近版本，删除之后的版本

    参数:
        thread_id: 会话线程ID
        keep_count: 要保留的消息数量

    返回:
        删除的消息数量
    """
    import logging

    logger = logging.getLogger(__name__)

    if keep_count < 0:
        keep_count = 0

    try:
        # 使用 LangGraph 的官方 API 获取 checkpoints
        with get_sync_checkpointer() as checkpointer:
            config = {"configurable": {"thread_id": thread_id}}
            checkpoints = list(checkpointer.list(config))

            if not checkpoints:
                logger.warning(f"[rollback] No checkpoints found for thread_id={thread_id}")
                return 0

            # 获取最新 checkpoint 的消息数量
            latest = checkpoints[0]
            latest_checkpoint = latest.checkpoint

            if not latest_checkpoint or 'channel_values' not in latest_checkpoint:
                logger.warning(f"[rollback] Latest checkpoint has no channel_values")
                return 0

            messages = latest_checkpoint.get('channel_values', {}).get('messages', [])
            original_count = len(messages)
            logger.info(f"[rollback] thread_id={thread_id}, original_count={original_count}, keep_count={keep_count}")

            if original_count <= keep_count:
                logger.info(f"[rollback] No need to truncate, original_count({original_count}) <= keep_count({keep_count})")
                return 0

            # 查找消息数量 <= keep_count 的最近 checkpoint
            target_checkpoint = None
            for cp in checkpoints:
                cp_data = cp.checkpoint
                if cp_data and 'channel_values' in cp_data:
                    cp_messages = cp_data.get('channel_values', {}).get('messages', [])
                    cp_msg_count = len(cp_messages)
                    # 只有当消息数量刚好等于 keep_count 时才使用该 checkpoint
                    # 否则需要通过修改 blob 来精确截断
                    if cp_msg_count == keep_count:
                        target_checkpoint = cp
                        break

            if not target_checkpoint:
                # 没有找到完全匹配的 checkpoint，需要直接操作数据库来精确截断
                logger.info(f"[rollback] No exact checkpoint found for keep_count={keep_count}, modifying blobs directly")
                return _rollback_by_modifying_blobs(thread_id, keep_count, original_count, logger)

            # 找到了目标 checkpoint，删除它之后的所有 checkpoints
            target_config = target_checkpoint.config
            target_checkpoint_id = target_config.get('configurable', {}).get('checkpoint_id')
            logger.info(f"[rollback] Found target checkpoint: {target_checkpoint_id}")

            # 使用数据库操作删除目标之后的 checkpoints
            deleted = _delete_checkpoints_after(thread_id, target_checkpoint_id, logger)

            return original_count - len(target_checkpoint.checkpoint.get('channel_values', {}).get('messages', []))

    except Exception as e:
        logger.error(f"[rollback] Error: {e}", exc_info=True)
        return 0


def _rollback_by_modifying_blobs(thread_id: str, keep_count: int, original_count: int, logger) -> int:
    """
    通过修改 checkpoint_blobs 来回滚消息
    当没有合适的历史 checkpoint 时使用此方法
    """
    if get_database_type() == 'postgres':
        import psycopg2
        conn_string = get_db_connection_string()

        # 先获取 serde（需要在 checkpointer 上下文中）
        with get_sync_checkpointer() as checkpointer:
            serde = checkpointer.serde

        try:
            conn = psycopg2.connect(conn_string)
            try:
                cursor = conn.cursor()

                # 获取最新的 messages blob（包括 type 列）
                cursor.execute("""
                    SELECT version, type, blob
                    FROM checkpoint_blobs
                    WHERE thread_id = %s AND channel = 'messages'
                    ORDER BY version DESC
                    LIMIT 1
                """, (thread_id,))
                row = cursor.fetchone()

                if not row:
                    logger.warning(f"[rollback] No messages blob found")
                    return 0

                version, blob_type, blob = row
                if isinstance(blob, memoryview):
                    blob = bytes(blob)

                # 使用 LangGraph 的序列化器解析
                messages = serde.loads_typed((blob_type, blob))
                logger.info(f"[rollback] Parsed {len(messages)} messages from blob")

                if len(messages) <= keep_count:
                    return 0

                # 截断消息
                truncated_messages = messages[:keep_count]

                # 重新序列化
                new_blob_type, new_blob = serde.dumps_typed(truncated_messages)
                logger.info(f"[rollback] Re-serialized to {len(truncated_messages)} messages, blob_type={new_blob_type}")

                # 更新 blob
                cursor.execute("""
                    UPDATE checkpoint_blobs
                    SET blob = %s, type = %s
                    WHERE thread_id = %s AND channel = 'messages' AND version = %s
                """, (new_blob, new_blob_type, thread_id, version))

                # 删除其他版本的 messages blobs
                cursor.execute("""
                    DELETE FROM checkpoint_blobs
                    WHERE thread_id = %s AND channel = 'messages' AND version != %s
                """, (thread_id, version))

                # 只保留最新的 checkpoint
                cursor.execute("""
                    DELETE FROM checkpoints
                    WHERE thread_id = %s
                    AND checkpoint_id NOT IN (
                        SELECT checkpoint_id FROM checkpoints
                        WHERE thread_id = %s
                        ORDER BY checkpoint_id DESC
                        LIMIT 1
                    )
                """, (thread_id, thread_id))

                conn.commit()
                deleted_count = original_count - keep_count
                logger.info(f"[rollback] Successfully truncated messages, deleted {deleted_count}")
                return deleted_count

            finally:
                conn.close()
        except Exception as e:
            logger.error(f"[rollback] _rollback_by_modifying_blobs error: {e}", exc_info=True)
            return 0
    else:
        # SQLite 版本暂不支持
        logger.warning("[rollback] SQLite blob modification not implemented")
        return 0


def _delete_checkpoints_after(thread_id: str, keep_checkpoint_id: str, logger) -> int:
    """删除指定 checkpoint 之后的所有 checkpoints"""
    if get_database_type() == 'postgres':
        import psycopg2
        conn_string = get_db_connection_string()

        try:
            conn = psycopg2.connect(conn_string)
            try:
                cursor = conn.cursor()

                # 删除比目标 checkpoint 更新的 checkpoints
                cursor.execute("""
                    DELETE FROM checkpoints
                    WHERE thread_id = %s AND checkpoint_id > %s
                """, (thread_id, keep_checkpoint_id))
                deleted = cursor.rowcount

                # 删除对应的 blobs (根据 checkpoints 中的 channel_versions)
                # 由于 blobs 可能被多个 checkpoints 引用，这里简单起见不删除

                conn.commit()
                logger.info(f"[rollback] Deleted {deleted} checkpoints after {keep_checkpoint_id}")
                return deleted
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"[rollback] _delete_checkpoints_after error: {e}", exc_info=True)
            return 0
    else:
        return 0
