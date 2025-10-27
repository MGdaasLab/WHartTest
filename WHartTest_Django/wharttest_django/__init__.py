"""
确保Celery应用在Django启动时被加载
"""
# 这将确保应用始终被导入，以便shared_task能够使用它
from .celery import app as celery_app

__all__ = ('celery_app',)