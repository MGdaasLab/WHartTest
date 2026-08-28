# 导入 include/path 以挂载路由器与显式端点。
from django.urls import include, path

# 导入 DRF 默认路由器用于自动生成 ViewSet 路由。
from rest_framework.routers import DefaultRouter

# 导入账户模块下的视图。
from .views import (
    UserCreateAPIView, CurrentUserAPIView,
    GroupViewSet, PermissionViewSet, UserViewSet, ContentTypeViewSet
)

# 创建账户模块路由器实例。
router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')  # 用户管理路由。
router.register(r'groups', GroupViewSet, basename='group')  # 组织/用户组管理路由。
router.register(r'permissions', PermissionViewSet, basename='permission')  # 权限查询与分配路由。
router.register(r'content-types', ContentTypeViewSet, basename='content-type')  # 模型内容类型查询路由。

# 声明账户模块 URL 列表。
urlpatterns = [
    path('', include(router.urls)),  # 挂载 ViewSet 自动路由。
    path('register/', UserCreateAPIView.as_view(), name='user-register'),  # 用户注册端点。
    path('me/', CurrentUserAPIView.as_view(), name='user-me'),  # 当前登录用户信息端点。
]
