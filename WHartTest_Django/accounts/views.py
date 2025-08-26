from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from wharttest_django.permissions import HasModelPermission, permission_required

from rest_framework_simplejwt.views import TokenObtainPairView as BaseTokenObtainPairView
from .serializers import (
    UserSerializer, UserDetailSerializer, UserUpdateSerializer,
    GroupSerializer, PermissionSerializer, ContentTypeSerializer,
    UserGroupOperationSerializer,
    PermissionAssignToUserSerializer, PermissionAssignToGroupSerializer,
    BatchUserPermissionOperationSerializer, BatchGroupPermissionOperationSerializer,
    UpdateUserPermissionsSerializer, UpdateGroupPermissionsSerializer,
    MyTokenObtainPairSerializer
)

class UserCreateAPIView(generics.CreateAPIView):
    """
    API endpoint for user registration.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)


class CurrentUserAPIView(APIView):
    """
    API endpoint to get current authenticated user's details.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserDetailSerializer # For schema generation

    def get(self, request):
        serializer = UserDetailSerializer(request.user)
        return Response(serializer.data)


class GroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    Provides actions to manage group members and group permissions.
    """
    queryset = Group.objects.all().order_by('name')
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated, HasModelPermission]

    # 全局权限类会自动检查相应的模型权限
    # 例如，list 和 retrieve 操作会检查 auth.view_group 权限
    # create 操作会检查 auth.add_group 权限
    # update 和 partial_update 操作会检查 auth.change_group 权限
    # destroy 操作会检查 auth.delete_group 权限

    @action(detail=True, methods=['get'], url_path='users')
    def list_users(self, request, pk=None):
        """
        Lists all users in this group.
        """
        group = self.get_object()
        users = group.user_set.all()
        page = self.paginate_queryset(users)
        if page is not None:
            serializer = UserDetailSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = UserDetailSerializer(users, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='add_users', serializer_class=UserGroupOperationSerializer)
    def add_users(self, request, pk=None):
        """
        Adds specified users to this group.
        Expects a list of user_ids in the request body.
        """
        group = self.get_object()
        serializer = UserGroupOperationSerializer(data=request.data)
        if serializer.is_valid():
            user_ids = serializer.validated_data['user_ids']
            users_to_add = User.objects.filter(id__in=user_ids)
            group.user_set.add(*users_to_add)
            return Response({'status': 'success', 'message': f'{users_to_add.count()} 用户已添加到组 {group.name}。'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='remove_users', serializer_class=UserGroupOperationSerializer)
    def remove_users(self, request, pk=None):
        """
        Removes specified users from this group.
        Expects a list of user_ids in the request body.
        """
        group = self.get_object()
        serializer = UserGroupOperationSerializer(data=request.data)
        if serializer.is_valid():
            user_ids = serializer.validated_data['user_ids']
            users_to_remove = User.objects.filter(id__in=user_ids)
            group.user_set.remove(*users_to_remove)
            return Response({'status': 'success', 'message': f'{users_to_remove.count()} 用户已从组 {group.name} 移除。'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], url_path='permissions')
    def get_group_permissions(self, request, pk=None):
        """
        Lists all permissions assigned to this group.
        """
        group = self.get_object()
        permissions = group.permissions.all()
        serializer = PermissionSerializer(permissions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='batch-assign-permissions', serializer_class=BatchGroupPermissionOperationSerializer)
    @permission_required('auth.change_group')
    def batch_assign_permissions(self, request, pk=None):
        """
        批量分配权限给用户组
        请求体格式: {"permission_ids": [1, 2, 3, 4]}
        """
        group = self.get_object()
        serializer = BatchGroupPermissionOperationSerializer(data=request.data)

        if serializer.is_valid():
            permission_ids = serializer.validated_data['permission_ids']
            permissions = Permission.objects.filter(id__in=permission_ids)

            # 批量添加权限
            group.permissions.add(*permissions)

            return Response({
                'status': 'success',
                'message': f'成功为用户组 {group.name} 分配了 {permissions.count()} 个权限。',
                'assigned_permissions': [{'id': p.id, 'name': p.name, 'codename': p.codename} for p in permissions]
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='batch-remove-permissions', serializer_class=BatchGroupPermissionOperationSerializer)
    @permission_required('auth.change_group')
    def batch_remove_permissions(self, request, pk=None):
        """
        批量移除用户组权限
        请求体格式: {"permission_ids": [1, 2, 3, 4]}
        """
        group = self.get_object()
        serializer = BatchGroupPermissionOperationSerializer(data=request.data)

        if serializer.is_valid():
            permission_ids = serializer.validated_data['permission_ids']
            permissions = Permission.objects.filter(id__in=permission_ids)

            # 批量移除权限
            group.permissions.remove(*permissions)

            return Response({
                'status': 'success',
                'message': f'成功从用户组 {group.name} 移除了 {permissions.count()} 个权限。',
                'removed_permissions': [{'id': p.id, 'name': p.name, 'codename': p.codename} for p in permissions]
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['put'], url_path='update-permissions', serializer_class=UpdateGroupPermissionsSerializer)
    @permission_required('auth.change_group')
    def update_group_permissions(self, request, pk=None):
        """
        更新用户组权限 - 完全替换用户组的权限列表
        请求体格式: {"permission_ids": [1, 2, 3, 4]}

        注意：
        - 此操作将完全替换用户组的权限列表
        - 传入空列表将清空用户组的所有权限
        - 需要 auth.change_group 权限
        """
        group = self.get_object()
        serializer = UpdateGroupPermissionsSerializer(data=request.data)

        if serializer.is_valid():
            permission_ids = serializer.validated_data['permission_ids']

            # 获取更新前的权限信息
            old_permissions = list(group.permissions.all())
            old_permission_data = [
                {'id': p.id, 'name': p.name, 'codename': p.codename}
                for p in old_permissions
            ]

            # 获取新的权限对象
            if permission_ids:
                new_permissions = Permission.objects.filter(id__in=permission_ids)
            else:
                new_permissions = Permission.objects.none()

            # 使用 set() 方法原子性地替换用户组的权限
            group.permissions.set(new_permissions)

            # 获取更新后的权限信息
            new_permission_data = [
                {'id': p.id, 'name': p.name, 'codename': p.codename}
                for p in new_permissions
            ]

            # 计算变更统计
            old_ids = set(p.id for p in old_permissions)
            new_ids = set(permission_ids) if permission_ids else set()
            added_ids = new_ids - old_ids
            removed_ids = old_ids - new_ids

            return Response({
                'status': 'success',
                'message': f'成功更新用户组 {group.name} 的权限。添加了 {len(added_ids)} 个权限，移除了 {len(removed_ids)} 个权限。',
                'group_id': group.id,
                'group_name': group.name,
                'changes': {
                    'added_count': len(added_ids),
                    'removed_count': len(removed_ids),
                    'total_permissions': len(new_ids)
                },
                'permissions': {
                    'before': old_permission_data,
                    'after': new_permission_data
                }
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ContentTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows content types (models) to be viewed.

    内容类型（模型）列表，用于在权限管理界面中选择模型。
    """
    queryset = ContentType.objects.exclude(
        app_label__in=['admin', 'contenttypes', 'sessions']
    ).order_by('app_label', 'model')
    serializer_class = ContentTypeSerializer
    permission_classes = [IsAuthenticated, HasModelPermission]
    filterset_fields = ['app_label']  # 允许按应用标签筛选
    search_fields = ['app_label', 'model']  # 允许搜索应用标签和模型名称


class PermissionViewSet(viewsets.ReadOnlyModelViewSet): # Keeping ReadOnly for base Permission model
    """
    API endpoint that allows permissions to be viewed.
    Provides actions to manage permission assignments to users and groups.

    支持按模型筛选权限：
    - 使用 ?content_type=<模型ID> 参数筛选特定模型的权限
    - 例如：/api/accounts/permissions/?content_type=7 只显示用户模型的权限

    支持按应用筛选权限：
    - 使用 ?content_type__app_label=<应用名> 参数筛选特定应用的权限
    - 例如：/api/accounts/permissions/?content_type__app_label=auth 只显示认证应用的权限

    支持搜索权限：
    - 使用 ?search=<关键词> 参数搜索权限名称和代码
    - 例如：/api/accounts/permissions/?search=add 搜索包含"add"的权限

    支持排序：
    - 使用 ?ordering=<字段> 参数按字段排序
    - 例如：/api/accounts/permissions/?ordering=codename 按代码名称排序
    """
    queryset = Permission.objects.exclude(
        content_type__app_label__in=['admin', 'contenttypes', 'sessions']
    ).order_by('content_type__app_label', 'codename')
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated, HasModelPermission]
    filterset_fields = ['content_type', 'content_type__app_label']  # 允许按模型和应用筛选
    search_fields = ['name', 'codename']  # 允许搜索权限名称和代码
    ordering_fields = ['name', 'codename', 'content_type__app_label']  # 允许排序的字段
    # 全局权限类会自动检查 auth.view_permission 权限

    @action(detail=True, methods=['post'], url_path='assign_to_user', serializer_class=PermissionAssignToUserSerializer)
    @permission_required('auth.change_permission')
    def assign_to_user(self, request, pk=None):
        """
        Assigns this permission to a specified user.
        Expects user_id in the request body.
        
        注意：
        - 用户不能修改自己的权限（安全考虑）
        - 只有超级用户或有相应管理权限的用户可以修改其他用户权限
        """
        permission = self.get_object()
        serializer = PermissionAssignToUserSerializer(data=request.data)
        if serializer.is_valid():
            user_id = serializer.validated_data['user_id']
            user = get_object_or_404(User, id=user_id)
            
            # 手动权限检查：禁止用户修改自己的权限
            if request.user == user:
                return Response({
                    'status': 'forbidden',
                    'message': '出于安全考虑，您不能修改自己的权限。请联系管理员进行权限调整。',
                    'code': 'SELF_PERMISSION_UPDATE_FORBIDDEN',
                    'user_id': user.id,
                    'username': user.username
                }, status=status.HTTP_403_FORBIDDEN)
            
            # 检查是否有权限修改其他用户的权限
            if not (request.user.is_superuser or request.user.has_perm('auth.change_permission')):
                return Response({
                    'status': 'forbidden',
                    'message': '您没有权限修改其他用户的权限。',
                    'code': 'INSUFFICIENT_PERMISSIONS',
                    'required_permission': 'auth.change_permission'
                }, status=status.HTTP_403_FORBIDDEN)
            
            user.user_permissions.add(permission)
            return Response({'status': 'success', 'message': f'权限 {permission.codename} 已分配给用户 {user.username}。'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='remove_from_user', serializer_class=PermissionAssignToUserSerializer)
    @permission_required('auth.change_permission')
    def remove_from_user(self, request, pk=None):
        """
        Removes this permission from a specified user.
        Expects user_id in the request body.
        
        注意：
        - 用户不能修改自己的权限（安全考虑）
        - 只有超级用户或有相应管理权限的用户可以修改其他用户权限
        """
        permission = self.get_object()
        serializer = PermissionAssignToUserSerializer(data=request.data)
        if serializer.is_valid():
            user_id = serializer.validated_data['user_id']
            user = get_object_or_404(User, id=user_id)
            
            # 手动权限检查：禁止用户修改自己的权限
            if request.user == user:
                return Response({
                    'status': 'forbidden',
                    'message': '出于安全考虑，您不能修改自己的权限。请联系管理员进行权限调整。',
                    'code': 'SELF_PERMISSION_UPDATE_FORBIDDEN',
                    'user_id': user.id,
                    'username': user.username
                }, status=status.HTTP_403_FORBIDDEN)
            
            # 检查是否有权限修改其他用户的权限
            if not (request.user.is_superuser or request.user.has_perm('auth.change_permission')):
                return Response({
                    'status': 'forbidden',
                    'message': '您没有权限修改其他用户的权限。',
                    'code': 'INSUFFICIENT_PERMISSIONS',
                    'required_permission': 'auth.change_permission'
                }, status=status.HTTP_403_FORBIDDEN)
            
            user.user_permissions.remove(permission)
            return Response({'status': 'success', 'message': f'权限 {permission.codename} 已从用户 {user.username} 移除。'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='assign_to_group', serializer_class=PermissionAssignToGroupSerializer)
    @permission_required('auth.change_group')
    def assign_to_group(self, request, pk=None):
        """
        Assigns this permission to a specified group.
        Expects group_id in the request body.
        """
        permission = self.get_object()
        serializer = PermissionAssignToGroupSerializer(data=request.data)
        if serializer.is_valid():
            group_id = serializer.validated_data['group_id']
            group = get_object_or_404(Group, id=group_id)
            group.permissions.add(permission)
            return Response({'status': 'success', 'message': f'权限 {permission.codename} 已分配给组 {group.name}。'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='remove_from_group', serializer_class=PermissionAssignToGroupSerializer)
    @permission_required('auth.change_group')
    def remove_from_group(self, request, pk=None):
        """
        Removes this permission from a specified group.
        Expects group_id in the request body.
        """
        permission = self.get_object()
        serializer = PermissionAssignToGroupSerializer(data=request.data)
        if serializer.is_valid():
            group_id = serializer.validated_data['group_id']
            group = get_object_or_404(Group, id=group_id)
            group.permissions.remove(permission)
            return Response({'status': 'success', 'message': f'权限 {permission.codename} 已从组 {group.name} 移除。'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed, created, edited or deleted.
    Provides actions to manage user permissions.
    """
    queryset = User.objects.all().order_by('id')
    filter_backends = [SearchFilter]
    search_fields = ['username', 'email', 'first_name', 'last_name']
    permission_classes = [IsAuthenticated, HasModelPermission]

    # 全局权限类会自动检查相应的模型权限
    # 例如，list 和 retrieve 操作会检查 auth.view_user 权限
    # create 操作会检查 auth.add_user 权限
    # update 和 partial_update 操作会检查 auth.change_user 权限
    # destroy 操作会检查 auth.delete_user 权限

    def get_serializer_class(self):
        if self.action == 'create':
            return UserSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        # For 'list', 'retrieve' and custom actions like 'get_user_permissions' if they return user details
        return UserDetailSerializer

    def get_permissions(self):
        """
        为不同的操作设置不同的权限类
        注意：对于特殊操作（如用户查看自己的信息），我们使用自定义的权限检查逻辑
        """
        # 对于retrieve和get_user_permissions操作，
        # 需要特殊处理（允许用户查看自己的信息），所以只进行身份验证
        if self.action in ['retrieve', 'get_user_permissions']:
            return [IsAuthenticated()]
        
        # 其他操作使用基础权限（身份验证 + 模型权限）
        return super().get_permissions()

    def retrieve(self, request, *args, **kwargs):
        """
        重写retrieve方法，允许用户查看自己的详细信息
        """
        instance = self.get_object()
        
        # 手动权限检查：用户只能查看自己的信息，除非是超级用户或有管理权限
        if not (request.user == instance or request.user.is_superuser or request.user.has_perm('auth.view_user')):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("您只能查看自己的用户信息")
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def check_object_permissions(self, request, obj):
        """
        重写对象权限检查，允许用户查看和修改自己的信息
        """
        # 对于查看操作（get_user_permissions等），允许用户查看自己的信息
        if self.action in ['get_user_permissions'] and request.user == obj:
            return  # 用户可以查看自己的信息，跳过权限检查
        
        # 对于修改操作（update, partial_update等），允许用户修改自己的基本信息
        # 但不包括敏感字段如is_staff, is_superuser等
        if self.action in ['update', 'partial_update'] and request.user == obj:
            # 检查是否尝试修改敏感字段
            sensitive_fields = {'is_staff', 'is_superuser', 'is_active', 'groups', 'user_permissions'}
            if hasattr(request, 'data') and any(field in request.data for field in sensitive_fields):
                # 如果尝试修改敏感字段，仍需要相应权限
                super().check_object_permissions(request, obj)
            else:
                return  # 用户可以修改自己的基本信息
        
        # 其他情况使用默认权限检查
        super().check_object_permissions(request, obj)

    @action(detail=True, methods=['get'], url_path='permissions')
    def get_user_permissions(self, request, pk=None):
        """
        Lists all permissions (direct and via groups) for this user.
        """
        user = self.get_object()
        permission_strings = user.get_all_permissions() # set of 'app_label.codename'

        if not permission_strings:
            all_perms_qs = Permission.objects.none()
        else:
            # Build a Q object to filter permissions
            # Example: Q(codename='add_logentry', content_type__app_label='admin') | Q(...)
            q_objects = Q()
            for perm_string in permission_strings:
                try:
                    app_label, codename = perm_string.split('.')
                    q_objects |= (Q(content_type__app_label=app_label) & Q(codename=codename))
                except ValueError:
                    # This case should ideally not happen with valid permission strings
                    # Consider logging if it does
                    pass # Or log an error

            if q_objects: # Check if any valid Q object was created
                all_perms_qs = Permission.objects.filter(q_objects).order_by('content_type__app_label', 'codename')
            else: # If permission_strings was not empty but all entries were malformed
                all_perms_qs = Permission.objects.none()

        # Paginate if needed
        page = self.paginate_queryset(all_perms_qs)
        if page is not None:
            serializer = PermissionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = PermissionSerializer(all_perms_qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='batch-assign-permissions', serializer_class=BatchUserPermissionOperationSerializer)
    @permission_required('auth.change_permission')
    def batch_assign_permissions(self, request, pk=None):
        """
        批量分配权限给用户
        请求体格式: {"permission_ids": [1, 2, 3, 4]}
        
        注意：
        - 用户不能修改自己的权限（安全考虑）
        - 只有超级用户或有相应管理权限的用户可以修改其他用户权限
        """
        user = self.get_object()
        
        # 手动权限检查：禁止用户修改自己的权限
        if request.user == user:
            return Response({
                'status': 'forbidden',
                'message': '出于安全考虑，您不能修改自己的权限。请联系管理员进行权限调整。',
                'code': 'SELF_PERMISSION_UPDATE_FORBIDDEN',
                'user_id': user.id,
                'username': user.username
            }, status=status.HTTP_403_FORBIDDEN)
        
        # 检查是否有权限修改其他用户的权限
        if not (request.user.is_superuser or request.user.has_perm('auth.change_permission')):
            return Response({
                'status': 'forbidden',
                'message': '您没有权限修改其他用户的权限。',
                'code': 'INSUFFICIENT_PERMISSIONS',
                'required_permission': 'auth.change_permission'
            }, status=status.HTTP_403_FORBIDDEN)
            
        serializer = BatchUserPermissionOperationSerializer(data=request.data)

        if serializer.is_valid():
            permission_ids = serializer.validated_data['permission_ids']
            permissions = Permission.objects.filter(id__in=permission_ids)

            # 批量添加权限
            user.user_permissions.add(*permissions)

            return Response({
                'status': 'success',
                'message': f'成功为用户 {user.username} 分配了 {permissions.count()} 个权限。',
                'assigned_permissions': [{'id': p.id, 'name': p.name, 'codename': p.codename} for p in permissions]
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='batch-remove-permissions', serializer_class=BatchUserPermissionOperationSerializer)
    @permission_required('auth.change_permission')
    def batch_remove_permissions(self, request, pk=None):
        """
        批量移除用户权限
        请求体格式: {"permission_ids": [1, 2, 3, 4]}
        
        注意：
        - 用户不能修改自己的权限（安全考虑）
        - 只有超级用户或有相应管理权限的用户可以修改其他用户权限
        """
        user = self.get_object()
        
        # 手动权限检查：禁止用户修改自己的权限
        if request.user == user:
            return Response({
                'status': 'forbidden',
                'message': '出于安全考虑，您不能修改自己的权限。请联系管理员进行权限调整。',
                'code': 'SELF_PERMISSION_UPDATE_FORBIDDEN',
                'user_id': user.id,
                'username': user.username
            }, status=status.HTTP_403_FORBIDDEN)
        
        # 检查是否有权限修改其他用户的权限
        if not (request.user.is_superuser or request.user.has_perm('auth.change_permission')):
            return Response({
                'status': 'forbidden',
                'message': '您没有权限修改其他用户的权限。',
                'code': 'INSUFFICIENT_PERMISSIONS',
                'required_permission': 'auth.change_permission'
            }, status=status.HTTP_403_FORBIDDEN)
            
        serializer = BatchUserPermissionOperationSerializer(data=request.data)

        if serializer.is_valid():
            permission_ids = serializer.validated_data['permission_ids']
            permissions = Permission.objects.filter(id__in=permission_ids)

            # 批量移除权限
            user.user_permissions.remove(*permissions)

            return Response({
                'status': 'success',
                'message': f'成功从用户 {user.username} 移除了 {permissions.count()} 个权限。',
                'removed_permissions': [{'id': p.id, 'name': p.name, 'codename': p.codename} for p in permissions]
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['put'], url_path='update-permissions', serializer_class=UpdateUserPermissionsSerializer)
    @permission_required('auth.change_permission')
    def update_permissions(self, request, pk=None):
        """
        更新用户权限 - 完全替换用户的直接权限列表
        请求体格式: {"permission_ids": [1, 2, 3, 4]}

        注意：
        - 用户不能修改自己的权限（安全考虑）
        - 只有超级用户或有相应管理权限的用户可以修改其他用户权限
        """
        user = self.get_object()
        
        # 手动权限检查：禁止用户修改自己的权限
        if request.user == user:
            return Response({
                'status': 'forbidden',
                'message': '出于安全考虑，您不能修改自己的权限。请联系管理员进行权限调整。',
                'code': 'SELF_PERMISSION_UPDATE_FORBIDDEN',
                'user_id': user.id,
                'username': user.username
            }, status=status.HTTP_403_FORBIDDEN)
        
        # 检查是否有权限修改其他用户的权限
        if not (request.user.is_superuser or request.user.has_perm('auth.change_permission')):
            return Response({
                'status': 'forbidden',
                'message': '您没有权限修改其他用户的权限。',
                'code': 'INSUFFICIENT_PERMISSIONS',
                'required_permission': 'auth.change_permission'
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = UpdateUserPermissionsSerializer(data=request.data)

        if serializer.is_valid():
            permission_ids = serializer.validated_data['permission_ids']

            # 获取更新前的权限信息（仅直接权限）
            old_direct_permissions = list(user.user_permissions.all())
            old_permission_data = [
                {'id': p.id, 'name': p.name, 'codename': p.codename}
                for p in old_direct_permissions
            ]

            # 获取新的权限对象
            if permission_ids:
                new_permissions = Permission.objects.filter(id__in=permission_ids)
            else:
                new_permissions = Permission.objects.none()

            # 使用 set() 方法原子性地替换用户的直接权限
            user.user_permissions.set(new_permissions)

            # 获取更新后的权限信息
            new_permission_data = [
                {'id': p.id, 'name': p.name, 'codename': p.codename}
                for p in new_permissions
            ]

            # 计算变更统计
            old_ids = set(p.id for p in old_direct_permissions)
            new_ids = set(permission_ids) if permission_ids else set()
            added_ids = new_ids - old_ids
            removed_ids = old_ids - new_ids

            return Response({
                'status': 'success',
                'message': f'成功更新用户 {user.username} 的权限。添加了 {len(added_ids)} 个权限，移除了 {len(removed_ids)} 个权限。',
                'user_id': user.id,
                'username': user.username,
                'changes': {
                    'added_count': len(added_ids),
                    'removed_count': len(removed_ids),
                    'total_direct_permissions': len(new_ids)
                },
                'permissions': {
                    'before': old_permission_data,
                    'after': new_permission_data
                }
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class MyTokenObtainPairView(BaseTokenObtainPairView):
    """
    Takes a set of user credentials and returns an access and refresh JSON web
    token pair to prove the authentication of those credentials, and also
    includes user's basic information.
    """
    serializer_class = MyTokenObtainPairSerializer
