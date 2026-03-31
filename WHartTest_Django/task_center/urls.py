from rest_framework_nested.routers import NestedSimpleRouter
from .views import ScheduledTaskViewSet, TaskExecutionViewSet

# URL 通过嵌套路由注册, 将在 urls.py 中用 projects_router 注册
