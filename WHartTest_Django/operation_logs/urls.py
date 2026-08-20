from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OperationLogViewSet, OperationLogCleanupAPIView, OperationLogSettingAPIView

router = DefaultRouter()
router.register(r'', OperationLogViewSet, basename='operation-log')

urlpatterns = [
    path('settings/', OperationLogSettingAPIView.as_view(), name='operation-log-settings'),
    path('cleanup-now/', OperationLogCleanupAPIView.as_view(), name='operation-log-cleanup-now'),
    path('', include(router.urls)),
]
