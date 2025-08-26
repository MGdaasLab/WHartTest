from rest_framework import permissions
from projects.models import ProjectMember


class IsProjectMemberForRequirement(permissions.BasePermission):
    """
    检查用户是否是需求文档所属项目的成员
    """
    def has_permission(self, request, view):
        # 如果用户是超级管理员，直接允许访问
        if request.user.is_superuser:
            return True
            
        # 获取项目ID
        project_id = None
        
        # 1. 从查询参数获取项目ID (用于列表视图，如 ?project=43)
        if hasattr(request, 'query_params') and 'project' in request.query_params:
            project_id = request.query_params.get('project')
        
        # 2. 从URL参数获取项目ID
        if not project_id and 'project_pk' in view.kwargs:
            project_id = view.kwargs['project_pk']
            
        # 3. 从对象获取项目ID (用于详情视图)
        if not project_id and 'pk' in view.kwargs and hasattr(view, 'get_object'):
            try:
                obj = view.get_object()
                if hasattr(obj, 'project'):
                    project_id = obj.project.id
                elif hasattr(obj, 'document') and hasattr(obj.document, 'project'):
                    project_id = obj.document.project.id
                elif hasattr(obj, 'report') and hasattr(obj.report.document, 'project'):
                    project_id = obj.report.document.project.id
            except:
                pass
        
        # 4. 从请求数据获取项目ID (用于创建和更新操作)
        if not project_id and request.method in ['POST', 'PUT', 'PATCH']:
            project_id = request.data.get('project')
            
        if not project_id:
            return False
            
        # 检查用户是否是项目成员
        return ProjectMember.objects.filter(
            project_id=project_id,
            user=request.user
        ).exists()

    def has_object_permission(self, request, view, obj):
        # 如果用户是超级管理员，直接允许访问
        if request.user.is_superuser:
            return True
            
        # 获取项目ID
        project_id = None
        if hasattr(obj, 'project'):
            project_id = obj.project.id
        elif hasattr(obj, 'document') and hasattr(obj.document, 'project'):
            project_id = obj.document.project.id
        elif hasattr(obj, 'report') and hasattr(obj.report.document, 'project'):
            project_id = obj.report.document.project.id
            
        if not project_id:
            return False
            
        # 检查用户是否是项目成员
        return ProjectMember.objects.filter(
            project_id=project_id,
            user=request.user
        ).exists()


class IsProjectAdminForRequirement(permissions.BasePermission):
    """
    检查用户是否是需求文档所属项目的管理员或拥有者
    """
    def has_permission(self, request, view):
        # 如果用户是超级管理员，直接允许访问
        if request.user.is_superuser:
            return True
            
        # 获取项目ID
        project_id = None
        
        # 从URL参数获取项目ID
        if 'project_pk' in view.kwargs:
            project_id = view.kwargs['project_pk']
        elif 'pk' in view.kwargs and hasattr(view, 'get_object'):
            # 从对象获取项目ID
            try:
                obj = view.get_object()
                if hasattr(obj, 'project'):
                    project_id = obj.project.id
                elif hasattr(obj, 'document') and hasattr(obj.document, 'project'):
                    project_id = obj.document.project.id
            except:
                pass
        
        # 从请求数据获取项目ID
        if not project_id and request.method in ['POST', 'PUT', 'PATCH']:
            project_id = request.data.get('project')
            
        if not project_id:
            return False
            
        # 检查用户是否是项目管理员或拥有者
        return ProjectMember.objects.filter(
            project_id=project_id,
            user=request.user,
            role__in=['admin', 'owner']
        ).exists()

    def has_object_permission(self, request, view, obj):
        # 如果用户是超级管理员，直接允许访问
        if request.user.is_superuser:
            return True
            
        # 获取项目ID
        project_id = None
        if hasattr(obj, 'project'):
            project_id = obj.project.id
        elif hasattr(obj, 'document') and hasattr(obj.document, 'project'):
            project_id = obj.document.project.id
            
        if not project_id:
            return False
            
        # 检查用户是否是项目管理员或拥有者
        return ProjectMember.objects.filter(
            project_id=project_id,
            user=request.user,
            role__in=['admin', 'owner']
        ).exists()


class CanManageRequirementDocument(permissions.BasePermission):
    """
    检查用户是否可以管理需求文档（创建、编辑、删除）
    """
    def has_permission(self, request, view):
        # 基础权限检查
        if not request.user or request.user.is_anonymous:
            return False
            
        # 超级管理员拥有所有权限
        if request.user.is_superuser:
            return True
            
        # 对于创建操作，检查是否是项目成员
        if request.method == 'POST':
            return IsProjectMemberForRequirement().has_permission(request, view)
            
        # 对于其他操作，需要进一步检查对象权限
        return True

    def has_object_permission(self, request, view, obj):
        # 超级管理员拥有所有权限
        if request.user.is_superuser:
            return True
            
        # 文档上传者可以编辑自己的文档
        if hasattr(obj, 'uploader') and obj.uploader == request.user:
            return True
            
        # 项目管理员可以管理项目内的所有文档
        if request.method in ['PUT', 'PATCH', 'DELETE']:
            return IsProjectAdminForRequirement().has_object_permission(request, view, obj)
            
        # 项目成员可以查看文档
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return IsProjectMemberForRequirement().has_object_permission(request, view, obj)
            
        return False


class CanStartReview(permissions.BasePermission):
    """
    检查用户是否可以启动需求评审
    要求：1. 有Django权限 2. 是项目成员
    """
    def has_permission(self, request, view):
        # 基础权限检查
        if not request.user or request.user.is_anonymous:
            return False
            
        # 超级管理员拥有所有权限
        if request.user.is_superuser:
            return True
        
        # 必须有Django权限才能启动评审
        if not request.user.has_perm('requirements.add_reviewreport'):
            return False
            
        # 项目成员可以启动评审
        return IsProjectMemberForRequirement().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        # 超级管理员拥有所有权限
        if request.user.is_superuser:
            return True
        
        # 必须有Django权限才能启动评审    
        if not request.user.has_perm('requirements.add_reviewreport'):
            return False
            
        # 文档上传者可以启动评审
        if hasattr(obj, 'uploader') and obj.uploader == request.user:
            return True
            
        # 项目成员可以启动评审
        return IsProjectMemberForRequirement().has_object_permission(request, view, obj)
