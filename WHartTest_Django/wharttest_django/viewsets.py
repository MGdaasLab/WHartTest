from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .permissions import HasModelPermission


class BaseModelViewSet(viewsets.ModelViewSet):
    """
    基础视图集，提供统一的权限控制
    
    所有视图集都应该继承自这个类，以确保权限检查的一致性。
    默认情况下，所有操作都需要用户认证和相应的模型权限。
    子类可以通过重写 get_permissions 方法来添加额外的权限检查。
    """
    
    def get_permissions(self):
        """
        返回基础权限列表：用户认证 + 模型权限
        
        子类应该调用 super().get_permissions() 获取基础权限，
        然后根据需要添加额外的权限检查。
        """
        return [IsAuthenticated(), HasModelPermission()]
