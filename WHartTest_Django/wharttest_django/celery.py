"""
Celery配置文件
"""
import os
import platform
from celery import Celery

# 设置默认的Django settings模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wharttest_django.settings')

# 创建Celery应用实例
app = Celery('wharttest_django')

# 使用字符串配置,这样worker就不需要序列化配置对象
# namespace='CELERY'意味着所有celery相关的配置键都应该有一个`CELERY_`前缀
app.config_from_object('django.conf:settings', namespace='CELERY')

# 自动从所有已注册的Django app中加载任务
app.autodiscover_tasks()

# 针对Windows平台的兼容性修复
if platform.system() == 'Windows':
    app.conf.update(
        CELERY_WORKER_POOL='solo',
        CELERY_BROKER_TRANSPORT_OPTIONS={'visibility_timeout': 3600},
        CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS={'visibility_timeout': 3600},
    )

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """调试任务"""
    print(f'Request: {self.request!r}')