"""
需求评审异步任务
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='requirements.execute_requirement_review')
def execute_requirement_review(
    self,
    document_id,
    analysis_options=None,
    review_type='comprehensive',
    user_id=None,
    resolved_bundle_id=None,
    resolved_source=None,
):
    """
    异步执行需求评审任务
    
    Args:
        document_id: 文档ID
        analysis_options: 分析选项
        review_type: 评审类型 ('direct' 或 'comprehensive')
        user_id: 用户ID（用于获取用户的提示词配置）
        resolved_bundle_id: PE 线为 LLM 配置包 ID；CE 线无该系统，仅签名兼容，忽略
        resolved_source: PE 线为配置解析来源；CE 线仅签名兼容，忽略
    """
    from .models import RequirementDocument, ReviewReport
    from .services import RequirementReviewService, sanitize_error_message
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
        review_service = RequirementReviewService(
            user=user,
            resolved_bundle_id=resolved_bundle_id,
            module_key='requirement_review',
        )
        
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

        # 更新文档状态为失败，并记录失败原因供前端展示。
        # 服务层通常已经写入过失败状态，这里是兜底（例如服务层标记前进程被杀）。
        try:
            document = RequirementDocument.objects.get(id=document_id)
            document.status = 'failed'
            if not document.error_message:
                document.error_message = sanitize_error_message(str(e))
            document.save(update_fields=['status', 'error_message', 'updated_at'])
        except RequirementDocument.DoesNotExist:
            logger.warning(f"标记失败状态时文档不存在: {document_id}")
        except Exception as mark_error:
            # 标记失败本身出错时必须留痕，禁止静默吞掉
            logger.error(f"标记文档失败状态时出错: {mark_error}", exc_info=True)

        return {
            'status': 'error',
            'message': str(e)
        }


@shared_task(bind=True, name='requirements.retry_dimension_analysis')
def retry_dimension_analysis(
    self,
    document_id,
    dimension,
    analysis_options=None,
    user_id=None,
    resolved_bundle_id=None,
    resolved_source=None,
):
    """
    重试单个专项分析维度，原位更新最新评审报告。

    与整体评审不同：重试意外失败时不把文档标记为 failed——
    报告中其余维度的结果仍然有效，只回滚 reviewing 占用状态。
    """
    from .models import RequirementDocument
    from .services import RequirementReviewService, sanitize_error_message
    from django.contrib.auth import get_user_model

    User = get_user_model()

    try:
        document = RequirementDocument.objects.get(id=document_id)
        user = None
        if user_id:
            user = User.objects.filter(id=user_id).first()

        review_service = RequirementReviewService(
            user=user,
            resolved_bundle_id=resolved_bundle_id,
            module_key='requirement_review',
        )
        report = review_service.retry_dimension_analysis(
            document, dimension, analysis_options or {}
        )
        return {
            'status': 'success',
            'document_id': str(document_id),
            'report_id': str(report.id),
            'dimension': dimension,
        }

    except RequirementDocument.DoesNotExist:
        logger.error(f"重试维度时文档不存在: {document_id}")
        return {'status': 'error', 'message': f'文档不存在: {document_id}'}
    except Exception as e:
        logger.error(f"维度重试任务失败: {e}", exc_info=True)
        # 兜底回滚 reviewing 占用；服务层通常已恢复过状态
        try:
            document = RequirementDocument.objects.get(id=document_id)
            if document.status == 'reviewing':
                document.status = 'review_completed'
                document.save(update_fields=['status', 'updated_at'])
        except Exception as mark_error:
            logger.error(f"回滚文档状态时出错: {mark_error}", exc_info=True)
        return {
            'status': 'error',
            'message': sanitize_error_message(str(e)),
            'dimension': dimension,
        }
