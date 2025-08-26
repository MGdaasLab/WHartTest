from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProjectViewSet

# 创建路由器并注册视图集
router = DefaultRouter()
router.register(r'', ProjectViewSet, basename='project')

# URL模式
urlpatterns = [
    path('', include(router.urls)),
]
