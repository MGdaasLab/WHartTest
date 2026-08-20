"""
需求评审异步任务
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='requirements.execute_requirement_review')
def execute_requirement_review(self, document_id, analysis_options=None, review_type='comprehensive', user_id=None):
    """
    异步执行需求评审任务
    
    Args:
        document_id: 文档ID
        analysis_options: 分析选项
        review_type: 评审类型 ('direct' 或 'comprehensive')
        user_id: 用户ID（用于获取用户的提示词配置）
    """
    from .models import RequirementDocument, ReviewReport
    from .services import RequirementReviewService
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    try:
        # 获取文档
        document = RequirementDocument.objects.get(id=document_id)
        
        # 获取用户对象
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                logger.info(f"开始异步评审文档: {document.title}, 类型: {review_type}, 用户: {user.username}")
            except User.DoesNotExist:
                logger.warning(f"用户 {user_id} 不存在，使用默认配置")
        
        # 文档状态应该已经在视图中设置为 reviewing 了，这里不需要重复设置
        
        # 创建评审服务，传入用户对象
        review_service = RequirementReviewService(user=user)
        
        # 根据类型执行评审
        if review_type == 'direct':
            review_report = review_service.start_direct_review(
                document,
                analysis_options or {}
            )
        else:
            review_report = review_service.start_comprehensive_review(
                document,
                analysis_options or {}  # 传递完整的analysis_options
            )
        
        logger.info(f"文档 {document.title} 评审完成, 报告ID: {review_report.id}")
        
        return {
            'status': 'success',
            'document_id': str(document_id),
            'report_id': str(review_report.id),
            'completion_score': review_report.completion_score,
            'total_issues': review_report.total_issues
        }
        
    except RequirementDocument.DoesNotExist:
        logger.error(f"文档不存在: {document_id}")
        return {
            'status': 'error',
            'message': f'文档不存在: {document_id}'
        }
    except Exception as e:
        logger.error(f"评审任务失败: {e}", exc_info=True)
        
        # 更新文档状态为失败
        try:
            document = RequirementDocument.objects.get(id=document_id)
            document.status = 'failed'
            document.save()
        except:
            pass
        
        return {
            'status': 'error',
            'message': str(e)
        }