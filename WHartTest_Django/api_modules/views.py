import logging

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from wharttest_django.viewsets import BaseModelViewSet
from wharttest_django.permissions import HasModelPermission
from wharttest_django.api_permissions import IsProjectMemberForResource
from wharttest_django.pagination import StandardPagination

from .models import ApiModule
from .serializers import (
    ApiModuleSerializer,
    ApiModuleCreateSerializer,
    ApiModuleUpdateSerializer,
)

logger = logging.getLogger(__name__)


class ApiModuleViewSet(BaseModelViewSet):
    serializer_class = ApiModuleSerializer

    def get_permissions(self):
        return [IsAuthenticated(), HasModelPermission(), IsProjectMemberForResource()]

    def get_serializer_class(self):
        if self.action == 'create':
            return ApiModuleCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ApiModuleUpdateSerializer
        return ApiModuleSerializer

    def get_queryset(self):
        project_pk = self.kwargs.get('project_pk')
        queryset = ApiModule.objects.filter(project_id=project_pk)
        if self.action == 'list':
            queryset = queryset.filter(parent=None)
        return queryset

    def perform_create(self, serializer):
        from projects.models import Project
        project = get_object_or_404(Project, pk=self.kwargs.get('project_pk'))
        serializer.save(created_by=self.request.user, project=project)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.children.exists():
            return Response(
                {'detail': 'Cannot delete a module that has child modules.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from api_interfaces.models import ApiInterface

        deleted_interface_ids = list(
            ApiInterface.objects.filter(module=instance).values_list('id', flat=True)
        )
        if deleted_interface_ids:
            ApiInterface.objects.filter(id__in=deleted_interface_ids).delete()

        self.perform_destroy(instance)
        return Response(
            {
                'deleted_interface_ids': deleted_interface_ids,
                'deleted_interface_count': len(deleted_interface_ids),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=['get'])
    def tree(self, request, *args, **kwargs):
        project_pk = self.kwargs.get('project_pk')
        root_modules = ApiModule.objects.filter(
            project_id=project_pk, parent=None
        ).order_by('order', 'id')
        serializer = ApiModuleSerializer(root_modules, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def move(self, request, project_pk=None, pk=None, **kwargs):
        """
        移动模块：支持移动到另一个模块的之前、之后或作为其子模块。
        """
        from django.db import transaction
        from django.db.models import Max

        instance = self.get_object()
        target_id = request.data.get("target_id")
        drop_position = request.data.get("drop_position")  # -1 (before), 1 (after), 0 (inside)

        if drop_position is None:
            return Response(
                {"error": "参数 drop_position 必填。"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            drop_position = int(drop_position)
            if drop_position not in [-1, 0, 1]:
                raise ValueError()
        except (TypeError, ValueError):
            return Response(
                {"error": "参数 drop_position 必须为 -1、0 或 1。"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # 如果 target_id 为 None，说明移动到根节点层级
            if target_id is None:
                if drop_position == 0:
                    return Response(
                        {"error": "无法将模块拖入空位置中。"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                instance.parent = None
                instance.level = 1
                instance.save()

                # 重新排序根节点模块
                root_modules = ApiModule.objects.filter(
                    project_id=project_pk, parent=None
                ).exclude(id=instance.id).order_by("order", "id")

                reordered = list(root_modules)
                reordered.append(instance)

                for index, m in enumerate(reordered, start=1):
                    m.order = index
                    m.save(update_fields=["order"])

                serializer = self.get_serializer(instance)
                return Response(serializer.data)

            # 如果 target_id 不为 None
            try:
                target_module = ApiModule.objects.get(
                    id=target_id, project_id=project_pk
                )
            except ApiModule.DoesNotExist:
                return Response(
                    {"error": "目标模块不存在。"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # 循环引用校验：目标模块不能是自己或自己的子模块
            descendant_ids = instance.get_all_descendant_ids()
            if target_module.id in descendant_ids:
                return Response(
                    {"error": "无法移动模块到自身或其子模块下。"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if drop_position == 0:
                # 移动到目标模块内部，作为其子模块
                if target_module.level >= 5:
                    return Response(
                        {"error": "模块级别不能超过5级。"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # 校验子树最大深度
                subtree_depth = instance.get_max_depth()
                if target_module.level + subtree_depth > 5:
                    return Response(
                        {"error": f"移动后模块层级将超过5级限制（当前子树深度: {subtree_depth}）。"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                instance.parent = target_module
                instance.level = target_module.level + 1

                # 获取目标模块下已有子模块的最大 order
                max_order = ApiModule.objects.filter(
                    parent=target_module
                ).aggregate(Max("order"))["order__max"] or 0

                instance.order = max_order + 1
                instance.save()

            else:
                # 移动到目标模块的前面或后面，成为同级模块
                parent = target_module.parent

                # 校验子树最大深度
                target_parent_level = target_module.parent.level if target_module.parent else 0
                subtree_depth = instance.get_max_depth()
                if target_parent_level + subtree_depth > 5:
                    return Response(
                        {"error": f"移动后模块层级将超过5级限制（当前子树深度: {subtree_depth}）。"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                instance.parent = parent
                instance.level = target_module.level
                instance.save()

                # 重新排序所有同级模块
                siblings = ApiModule.objects.filter(
                    project_id=project_pk, parent=parent
                ).exclude(id=instance.id).order_by("order", "id")

                reordered = []
                for s in siblings:
                    if s.id == target_module.id and drop_position == -1:
                        reordered.append(instance)
                        reordered.append(s)
                    elif s.id == target_module.id and drop_position == 1:
                        reordered.append(s)
                        reordered.append(instance)
                    else:
                        reordered.append(s)

                # 防御，如果目标模块没在 siblings 里（理论上不可能）
                if instance not in reordered:
                    reordered.append(instance)

                for index, m in enumerate(reordered, start=1):
                    m.order = index
                    m.save(update_fields=["order"])

            serializer = self.get_serializer(instance)
            return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def search(self, request, *args, **kwargs):
        project_pk = self.kwargs.get('project_pk')
        keyword = request.query_params.get('keyword', '')
        queryset = ApiModule.objects.filter(
            Q(name__icontains=keyword) | Q(description__icontains=keyword),
            project_id=project_pk,
        )
        serializer = ApiModuleSerializer(queryset, many=True)
        return Response(serializer.data)
