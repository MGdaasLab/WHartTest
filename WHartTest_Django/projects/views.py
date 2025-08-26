from rest_framework import generics, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.contrib.auth.models import User

from .models import Project, ProjectMember
from .serializers import (
    ProjectSerializer, ProjectDetailSerializer,
    ProjectMemberSerializer, ProjectMemberCreateSerializer
)
from .permissions import (
    IsProjectMember, 
    IsProjectAdmin, 
    IsProjectOwner,
    HasProjectMemberPermission
)
from accounts.serializers import UserDetailSerializer
from wharttest_django.viewsets import BaseModelViewSet


class ProjectViewSet(BaseModelViewSet):
    """
    项目视图集，提供项目的CRUD操作
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']

    def get_queryset(self):
        """
        只返回用户有权限访问的项目
        """
        user = self.request.user

        # 超级管理员可以看到所有项目
        if user.is_superuser:
            return Project.objects.all()

        # 普通用户只能看到自己是成员的项目
        return Project.objects.filter(members__user=user).distinct()

    def get_serializer_class(self):
        """
        根据操作类型返回不同的序列化器
        """
        if self.action == 'retrieve':
            return ProjectDetailSerializer
        return ProjectSerializer

    def get_permissions(self):
        """
        根据操作类型设置不同的权限
        """
        # 成员管理操作需要 ProjectMember 模型权限 + 项目成员身份
        if self.action in ['members', 'add_member', 'remove_member', 'update_member_role']:
            return [HasProjectMemberPermission(), IsProjectMember()]
        
        # 其他操作需要基础权限（用户认证 + Django模型权限）
        base_permissions = super().get_permissions()
        
        # 在基础权限之上添加项目特定的权限检查
        if self.action in ['update', 'partial_update']:
            return base_permissions + [IsProjectAdmin()]
        elif self.action == 'destroy':
            return base_permissions + [IsProjectOwner()]
        elif self.action == 'retrieve':
            return base_permissions + [IsProjectMember()]
        elif self.action == 'create':
            # 创建项目需要基础权限（包含Django模型的add权限）
            return base_permissions
        elif self.action == 'list':
            # 列表操作需要基础权限（包含Django模型的view权限）
            return base_permissions

        # 对于其他操作，使用基础权限
        return base_permissions

    def perform_create(self, serializer):
        """
        创建项目时，自动将当前用户添加为项目拥有者和创建人，
        并将所有平台管理员（超级用户和staff用户）添加为项目管理者
        """
        with transaction.atomic():
            # 保存项目，设置创建人
            project = serializer.save(creator=self.request.user)
            
            # 添加当前用户为项目拥有者
            ProjectMember.objects.create(
                project=project,
                user=self.request.user,
                role='owner'
            )
            
            # 获取所有平台管理员（超级用户和staff用户）
            from django.db import models
            platform_admins = User.objects.filter(
                models.Q(is_superuser=True) | models.Q(is_staff=True),
                is_active=True
            )
            
            # 为每个平台管理员添加项目管理者角色（如果不是当前用户）
            for admin in platform_admins:
                if admin != self.request.user:  # 避免重复添加当前用户
                    ProjectMember.objects.get_or_create(
                        project=project,
                        user=admin,
                        defaults={'role': 'admin'}
                    )

    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        """
        获取项目成员列表
        """
        project = self.get_object()
        members = project.members.all()

        page = self.paginate_queryset(members)
        if page is not None:
            serializer = ProjectMemberSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ProjectMemberSerializer(members, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_member(self, request, pk=None):
        """
        添加项目成员
        """
        project = self.get_object()

        serializer = ProjectMemberCreateSerializer(
            data=request.data,
            context={'project': project}
        )

        if serializer.is_valid():
            member = serializer.save()
            member_serializer = ProjectMemberSerializer(member)
            return Response(member_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'])
    def remove_member(self, request, pk=None):
        """
        移除项目成员
        """
        project = self.get_object()
        user_id = request.data.get('user_id')

        if not user_id:
            return Response({"error": "必须提供用户ID"}, status=status.HTTP_400_BAD_REQUEST)

        # 不能移除项目拥有者
        member = get_object_or_404(ProjectMember, project=project, user_id=user_id)
        if member.role == 'owner' and not request.user.is_superuser:
            return Response({"error": "不能移除项目拥有者"}, status=status.HTTP_403_FORBIDDEN)

        # 不能移除自己（除非是超级管理员）
        if member.user == request.user and not request.user.is_superuser:
            return Response({"error": "不能移除自己"}, status=status.HTTP_403_FORBIDDEN)

        member.delete()
        # 使用HTTP_200_OK而不是HTTP_204_NO_CONTENT，并返回一个简单的消息
        return Response({"message": "成员已成功移除"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['patch'])
    def update_member_role(self, request, pk=None):
        """
        更新项目成员角色
        """
        project = self.get_object()
        user_id = request.data.get('user_id')
        role = request.data.get('role')

        if not user_id or not role:
            return Response({"error": "必须提供用户ID和角色"}, status=status.HTTP_400_BAD_REQUEST)

        if role not in [r[0] for r in ProjectMember.ROLE_CHOICES]:
            return Response({"error": f"无效的角色，可选值为: {[r[0] for r in ProjectMember.ROLE_CHOICES]}"},
                           status=status.HTTP_400_BAD_REQUEST)

        member = get_object_or_404(ProjectMember, project=project, user_id=user_id)

        # 只有拥有者或超级管理员可以修改拥有者角色
        if member.role == 'owner' and not (request.user.is_superuser or
                                          ProjectMember.objects.filter(project=project, user=request.user, role='owner').exists()):
            return Response({"error": "只有项目拥有者或超级管理员可以修改拥有者角色"}, status=status.HTTP_403_FORBIDDEN)

        # 不能修改自己的角色（除非是超级管理员）
        if member.user == request.user and not request.user.is_superuser:
            return Response({"error": "不能修改自己的角色"}, status=status.HTTP_403_FORBIDDEN)

        # 使用事务确保数据一致性
        with transaction.atomic():
            # 如果要将成员设置为拥有者
            if role == 'owner':
                # 查找当前的项目拥有者
                current_owners = ProjectMember.objects.filter(project=project, role='owner')

                # 如果存在拥有者且不是当前要修改的成员
                if current_owners.exists() and current_owners.first().user_id != int(user_id):
                    # 将原拥有者降级为管理员
                    for owner in current_owners:
                        owner.role = 'admin'
                        owner.save()

            # 更新当前成员的角色
            member.role = role
            member.save()

        serializer = ProjectMemberSerializer(member)
        return Response(serializer.data)
