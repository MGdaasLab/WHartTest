from rest_framework import status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from wharttest_django.viewsets import BaseModelViewSet
from wharttest_django.permissions import HasModelPermission
from .models import UserPrompt
from .serializers import (
    UserPromptSerializer,
    UserPromptListSerializer
)


class UserPromptViewSet(BaseModelViewSet):
    """
    用户提示词管理视图集
    提供用户级别的提示词CRUD操作
    """
    serializer_class = UserPromptSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_default', 'is_active', 'prompt_type']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'updated_at', 'name']
    ordering = ['-updated_at']

    def get_permissions(self):
        """返回此视图所需权限的实例列表"""
        return [
            HasModelPermission(),
        ]

    def get_queryset(self):
        """只返回当前用户的提示词"""
        return UserPrompt.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        """根据操作类型返回不同的序列化器"""
        if self.action == 'list':
            return UserPromptListSerializer
        return UserPromptSerializer

    def perform_create(self, serializer):
        """创建时自动设置用户"""
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def default(self, request):
        """获取用户的默认提示词"""
        default_prompt = UserPrompt.get_user_default_prompt(request.user)

        if default_prompt:
            serializer = self.get_serializer(default_prompt)
            return Response(serializer.data)
        else:
            return Response({
                "status": "success",
                "code": status.HTTP_200_OK,
                "message": "用户暂无默认提示词",
                "data": None,
                "errors": {}
            })

    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """根据类型获取提示词"""
        prompt_type = request.query_params.get('type')
        if not prompt_type:
            return Response({
                "status": "error",
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "缺少type参数",
                "data": None,
                "errors": {"type": ["此字段是必需的"]}
            }, status=status.HTTP_400_BAD_REQUEST)

        prompt = UserPrompt.get_user_prompt_by_type(request.user, prompt_type)
        if prompt:
            serializer = self.get_serializer(prompt)
            return Response(serializer.data)
        else:
            return Response({
                "status": "success",
                "code": status.HTTP_200_OK,
                "message": f"用户暂无{prompt_type}类型的提示词",
                "data": None,
                "errors": {}
            })

    @action(detail=False, methods=['get'])
    def types(self, request):
        """获取所有提示词类型"""
        types = [
            {
                'value': choice[0],
                'label': choice[1],
                'is_program_call': choice[0] in UserPrompt.PROGRAM_CALL_TYPES
            }
            for choice in UserPrompt.PROMPT_TYPE_CHOICES
        ]
        return Response({
            "status": "success",
            "code": status.HTTP_200_OK,
            "message": "获取成功",
            "data": types,
            "errors": {}
        })

    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """设置指定提示词为默认提示词"""
        prompt = self.get_object()

        # 检查提示词是否属于当前用户且处于激活状态
        if not prompt.is_active:
            return Response({
                "status": "error",
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "无法设置未激活的提示词为默认",
                "data": {},
                "errors": {"prompt": ["提示词未激活"]}
            }, status=status.HTTP_400_BAD_REQUEST)

        # 检查是否为程序调用类型（程序调用类型不允许设为默认）
        if prompt.prompt_type in UserPrompt.PROGRAM_CALL_TYPES:
            return Response({
                "status": "error",
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "程序调用类型的提示词不能设为默认",
                "data": {},
                "errors": {"prompt_type": ["程序调用类型的提示词不能设为默认，会影响对话功能"]}
            }, status=status.HTTP_400_BAD_REQUEST)

        # 取消其他默认提示词
        UserPrompt.objects.filter(
            user=request.user,
            is_default=True
        ).exclude(pk=prompt.pk).update(is_default=False)

        # 设置当前提示词为默认
        prompt.is_default = True
        prompt.save()

        serializer = self.get_serializer(prompt)
        return Response({
            "status": "success",
            "code": status.HTTP_200_OK,
            "message": "默认提示词设置成功",
            "data": serializer.data,
            "errors": {}
        })

    @action(detail=False, methods=['post'])
    def clear_default(self, request):
        """清除用户的默认提示词设置"""
        updated_count = UserPrompt.objects.filter(
            user=request.user,
            is_default=True
        ).update(is_default=False)

        return Response({
            "status": "success",
            "code": status.HTTP_200_OK,
            "message": f"已清除默认提示词设置，影响{updated_count}条记录",
            "data": {"updated_count": updated_count},
            "errors": {}
        })

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """复制提示词"""
        original_prompt = self.get_object()

        # 创建副本
        new_prompt = UserPrompt.objects.create(
            user=request.user,
            name=f"{original_prompt.name} (副本)",
            content=original_prompt.content,
            description=f"复制自: {original_prompt.description}" if original_prompt.description else "复制的提示词",
            is_default=False,  # 副本不设为默认
            is_active=True
        )

        serializer = self.get_serializer(new_prompt)
        return Response({
            "status": "success",
            "code": status.HTTP_201_CREATED,
            "message": "提示词复制成功",
            "data": serializer.data,
            "errors": {}
        }, status=status.HTTP_201_CREATED)
