from rest_framework import viewsets, permissions, filters, status
from django_filters.rest_framework import DjangoFilterBackend
import django_filters
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import OperationLog, OperationLogSetting
from .serializers import OperationLogSerializer, OperationLogSettingSerializer
from .tasks import cleanup_operation_logs

class OperationLogFilter(django_filters.FilterSet):
    username = django_filters.CharFilter(lookup_expr='icontains')
    module = django_filters.CharFilter(lookup_expr='icontains')
    action = django_filters.CharFilter(lookup_expr='icontains')
    method = django_filters.CharFilter(lookup_expr='iexact')
    response_code = django_filters.NumberFilter()
    start_time = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    end_time = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    class Meta:
        model = OperationLog
        fields = ['username', 'module', 'action', 'method', 'response_code']

from wharttest_django.pagination import StandardPagination


class OperationLogReadPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or request.user.is_anonymous:
            return False
        return (
            request.user.is_staff or
            request.user.has_perm('operation_logs.view_operationlog') or
            request.user.has_perm('accounts.view_operationlog')
        )


class OperationLogCleanupPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or request.user.is_anonymous:
            return False
        return (
            request.user.is_staff or
            request.user.has_perm('operation_logs.delete_operationlog')
        )

class OperationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    操作日志只读查询接口
    """
    queryset = OperationLog.objects.all()
    serializer_class = OperationLogSerializer
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = OperationLogFilter
    search_fields = ['username', 'module', 'action', 'path']
    ordering_fields = ['created_at', 'duration', 'response_code']
    ordering = ['-created_at']

    def get_permissions(self):
        """
        进行严格的权限检查：必须为管理员(is_staff)或拥有操作日志查看权限(operation_logs.view_operationlog / accounts.view_operationlog)
        """
        return [permissions.IsAuthenticated(), OperationLogReadPermission()]


class OperationLogCleanupAPIView(APIView):
    """手动立即清理一次过期操作日志。"""

    permission_classes = [permissions.IsAuthenticated, OperationLogCleanupPermission]

    def post(self, request):
        result = cleanup_operation_logs()
        return Response(result, status=status.HTTP_200_OK)


class OperationLogSettingAPIView(APIView):
    """操作日志自动清理设置。"""

    permission_classes = [permissions.IsAuthenticated, OperationLogReadPermission]

    def get(self, request):
        serializer = OperationLogSettingSerializer(OperationLogSetting.get_config())
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        cleanup_permission = OperationLogCleanupPermission()
        if not cleanup_permission.has_permission(request, self):
            return Response({'detail': '无权修改操作日志清理设置'}, status=status.HTTP_403_FORBIDDEN)

        config = OperationLogSetting.get_config()
        serializer = OperationLogSettingSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
