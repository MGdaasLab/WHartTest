from datetime import timedelta
import logging

from celery import shared_task
from django.utils import timezone

from .models import OperationLog, OperationLogSetting

logger = logging.getLogger(__name__)


@shared_task(name='operation_logs.tasks.cleanup_operation_logs')
def cleanup_operation_logs():
    """按配置的保留天数清理过期操作日志，默认保留 7 天。"""
    retention_days = max(int(OperationLogSetting.get_config().retention_days or 7), 1)
    cutoff_time = timezone.now() - timedelta(days=retention_days)

    deleted_count, _ = OperationLog.objects.filter(created_at__lt=cutoff_time).delete()
    logger.info(
        '操作日志清理完成: retention_days=%s, cutoff_time=%s, deleted=%s',
        retention_days,
        cutoff_time.isoformat(),
        deleted_count,
    )
    return {
        'status': 'success',
        'retention_days': retention_days,
        'cutoff_time': cutoff_time.isoformat(),
        'deleted_count': deleted_count,
    }
