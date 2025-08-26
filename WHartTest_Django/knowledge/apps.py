from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class KnowledgeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'knowledge'
    verbose_name = '知识库管理'

    def ready(self):
        """应用启动时的初始化"""
        # 预热向量存储缓存（在后台线程中执行，避免阻塞启动）
        import threading
        thread = threading.Thread(target=self.warmup_vector_stores)
        thread.daemon = True
        thread.start()

    def warmup_vector_stores(self):
        """预热向量存储缓存"""
        try:
            import time
            # 等待Django完全启动
            time.sleep(5)

            from .models import KnowledgeBase
            from .services import KnowledgeBaseService

            # 获取活跃的知识库（有文档的）
            active_kbs = KnowledgeBase.objects.filter(
                is_active=True,
                documents__status='completed'
            ).distinct()[:3]  # 只预热前3个，避免启动过慢

            logger.info(f"开始预热 {active_kbs.count()} 个知识库的向量存储...")

            for kb in active_kbs:
                try:
                    service = KnowledgeBaseService(kb)
                    # 触发向量存储初始化
                    _ = service.vector_manager.vector_store
                    logger.info(f"知识库 {kb.name} 预热完成")
                except Exception as e:
                    logger.warning(f"知识库 {kb.name} 预热失败: {e}")

            logger.info("向量存储预热完成")

        except Exception as e:
            logger.warning(f"向量存储预热失败: {e}")
