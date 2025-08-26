from rest_framework import permissions
from .models import ProjectMember
from wharttest_django.permissions import HasModelPermission


class IsProjectMember(permissions.BasePermission):
    """
    检查用户是否是项目成员
    """
    def has_permission(self, request, view):
        # 如果用户是超级管理员，直接允许访问
        if request.user.is_superuser:
            return True
            
        # 获取项目ID
        project_id = view.kwargs.get('pk') or view.kwargs.get('project_pk')
        if not project_id:
            return False
        
        # 检查用户是否是项目成员
        return ProjectMember.objects.filter(
            project_id=project_id,
            user=request.user
        ).exists()
    
    def has_object_permission(self, request, view, obj):
        """
        检查用户是否是项目成员（对象级权限）
        """
        if request.user.is_superuser:
            return True
            
        return ProjectMember.objects.filter(
            project=obj,
            user=request.user
        ).exists()


class IsProjectAdmin(permissions.BasePermission):
    """
    检查用户是否是项目管理员或拥有者
    """
    def has_permission(self, request, view):
        # 如果用户是超级管理员，直接允许访问
        if request.user.is_superuser:
            return True
            
        # 获取项目ID
        project_id = view.kwargs.get('pk') or view.kwargs.get('project_pk')
        if not project_id:
            return False
        
        # 检查用户是否是项目管理员或拥有者
        return ProjectMember.objects.filter(
            project_id=project_id,
            user=request.user,
            role__in=['admin', 'owner']
        ).exists()
    
    def has_object_permission(self, request, view, obj):
        """
        检查用户是否是项目管理员或拥有者（对象级权限）
        """
        if request.user.is_superuser:
            return True
            
        return ProjectMember.objects.filter(
            project=obj,
            user=request.user,
            role__in=['admin', 'owner']
        ).exists()


class IsProjectOwner(permissions.BasePermission):
    """
    检查用户是否是项目拥有者
    """
    def has_permission(self, request, view):
        # 如果用户是超级管理员，直接允许访问
        if request.user.is_superuser:
            return True
            
        # 获取项目ID
        project_id = view.kwargs.get('pk') or view.kwargs.get('project_pk')
        if not project_id:
            return False
            
        # 检查用户是否是项目拥有者
        return ProjectMember.objects.filter(
            project_id=project_id,
            user=request.user,
            role='owner'
        ).exists()
    
    def has_object_permission(self, request, view, obj):
        """
        检查用户是否是项目拥有者（对象级权限）
        """
        if request.user.is_superuser:
            return True
            
        return ProjectMember.objects.filter(
            project=obj,
            user=request.user,
            role='owner'
        ).exists()


class HasProjectMemberPermission(HasModelPermission):
    """
    专门检查 ProjectMember 模型权限的权限类
    用于成员管理相关操作
    """
    def _get_model_info(self, view):
        """
        强制返回 ProjectMember 模型信息
        """
        return ProjectMember, 'projects', 'projectmember'
