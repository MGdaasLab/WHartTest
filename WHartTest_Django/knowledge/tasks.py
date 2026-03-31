"""知识库异步任务"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='knowledge.process_document')
def process_document_task(self, document_id):
    """异步处理文档：加载、分块、向量化"""
    from .models import Document
    from .services import KnowledgeBaseService

    try:
        document = Document.objects.select_related('knowledge_base').get(id=document_id)
        service = KnowledgeBaseService(document.knowledge_base)
        service.process_document(document)
        logger.info(f"文档 {document_id} 处理完成")
    except Document.DoesNotExist:
        logger.error(f"文档 {document_id} 不存在")
    except Exception as e:
        logger.error(f"文档 {document_id} 处理失败: {e}", exc_info=True)
        try:
            Document.objects.filter(id=document_id).update(
                status='failed', error_message=str(e)[:500]
            )
        except Exception:
            pass
        raise
