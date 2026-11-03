# 导入 DRF 默认路由器。
from rest_framework.routers import DefaultRouter
from django.urls import path

# 导入 API Key 视图集。
from .views import APIKeyViewSet, ExchangeTokenView

# 创建 API Key 模块路由器。
router = DefaultRouter()
router.register(r'api-keys', APIKeyViewSet, basename='api-key')  # API Key CRUD 路由。

# 导出路由列表供主路由 include。
# 注意：exchange-token 必须排在 router 之前——DefaultRouter 的 detail 路由
# <pk> 能匹配 "exchange-token" 字符串，放后面会被 detail 路由遮蔽。
urlpatterns = [
    # API Key 兑换 WS 连接用的短时效 JWT（仅 API Key 认证）。
    path('api-keys/exchange-token/', ExchangeTokenView.as_view(), name='api-key-exchange-token'),
] + router.urls
