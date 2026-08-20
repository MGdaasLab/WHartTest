from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from django.db.utils import OperationalError
from django.db.models import Q
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from wharttest_django.permissions import HasModelPermission, permission_required

from rest_framework_simplejwt.views import (
    TokenObtainPairView as BaseTokenObtainPairView,
)
from .serializers import (
    UserSerializer,
    UserRegistrationSerializer,
    UserDetailSerializer,
    UserUpdateSerializer,
    GroupSerializer,
    PermissionSerializer,
    ContentTypeSerializer,
    UserGroupOperationSerializer,
    PermissionAssignToUserSerializer,
    PermissionAssignToGroupSerializer,
    BatchUserPermissionOperationSerializer,
    BatchGroupPermissionOperationSerializer,
    UpdateUserPermissionsSerializer,
    UpdateGroupPermissionsSerializer,
    MyTokenObtainPairSerializer,
)


class UserCreateAPIView(generics.CreateAPIView):
    """
    用户注册接口。
    """

    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        # 直接复用通用创建流程，保持注册接口与统一序列化逻辑一致。
        return super().create(request, *args, **kwargs)


class CurrentUserAPIView(APIView):
    """
    获取当前已认证用户详情。
    """

    permission_classes = [IsAuthenticated]
    # 该属性仅用于接口文档生成，实际序列化在详情查询方法中显式执行。
    serializer_class = UserDetailSerializer

    def get(self, request):
        # 认证通过后直接返回当前用户详情，避免客户端再额外请求用户编号。
        serializer = UserDetailSerializer(request.user)
        return Response(serializer.data)


class GroupViewSet(viewsets.ModelViewSet):
    """
    用户组管理接口，支持用户组的增删改查。
    同时提供用户组成员与用户组权限的维护能力。
    """


    queryset = Group.objects.all().order_by("name")
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated, HasModelPermission]

    # 条件：访问用户组列表与详情；动作：自动执行查看权限校验；结果：无查看权限的请求会被拒绝。
    # 条件：创建用户组；动作：自动执行新增权限校验；结果：防止未授权创建。
    # 条件：更新用户组；动作：自动执行变更权限校验；结果：防止未授权修改。
    # 条件：删除用户组；动作：自动执行删除权限校验；结果：防止未授权删除。

    @action(detail=True, methods=["get"], url_path="users")
    def list_users(self, request, pk=None):
        """
        获取指定用户组下的成员列表。
        """
        group = self.get_object()
        users = group.user_set.all()

        # 条件：分页器生效；动作：返回分页结构；结果：大用户组列表不会一次性返回全部数据。
        page = self.paginate_queryset(users)
        if page is not None:
            serializer = UserDetailSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        # 条件：未启用分页；动作：返回完整成员列表；结果：保持接口在小数据量场景下简单可用。
        serializer = UserDetailSerializer(users, many=True)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        url_path="add_users",
        serializer_class=UserGroupOperationSerializer,
    )
    def add_users(self, request, pk=None):
        """
        向指定用户组批量添加成员。
        请求体需提供待添加用户编号列表。
        """
        group = self.get_object()
        serializer = UserGroupOperationSerializer(data=request.data)
        if serializer.is_valid():
            user_ids = serializer.validated_data["user_ids"]
            users_to_add = User.objects.filter(id__in=user_ids)

            # 参数校验通过后批量添加成员，减少逐条写入带来的数据库开销。
            group.user_set.add(*users_to_add)
            return Response(
                {
                    "status": "success",
                    "message": f"{users_to_add.count()} 用户已添加到组 {group.name}。",
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=["post"],
        url_path="remove_users",
        serializer_class=UserGroupOperationSerializer,
    )
    def remove_users(self, request, pk=None):
        """
        从指定用户组批量移除成员。
        请求体需提供待移除用户编号列表。
        """
        group = self.get_object()
        serializer = UserGroupOperationSerializer(data=request.data)
        if serializer.is_valid():
            user_ids = serializer.validated_data["user_ids"]
            users_to_remove = User.objects.filter(id__in=user_ids)

            # 参数校验通过后批量移除成员，确保组成员关系与前端操作一致。
            group.user_set.remove(*users_to_remove)
            return Response(
                {
                    "status": "success",
                    "message": f"{users_to_remove.count()} 用户已从组 {group.name} 移除。",
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"], url_path="permissions")
    def get_group_permissions(self, request, pk=None):
        """
        获取指定用户组已分配的权限列表。
        """
        group = self.get_object()
        permissions = group.permissions.all()
        serializer = PermissionSerializer(permissions, many=True)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        url_path="batch-assign-permissions",
        serializer_class=BatchGroupPermissionOperationSerializer,
    )
    @permission_required("auth.change_group")
    def batch_assign_permissions(self, request, pk=None):
        """
        批量分配权限给用户组
        请求体需提供权限编号列表。
        """
        group = self.get_object()
        serializer = BatchGroupPermissionOperationSerializer(data=request.data)

        if serializer.is_valid():
            permission_ids = serializer.validated_data["permission_ids"]
            permissions = Permission.objects.filter(id__in=permission_ids)

            # 条件：参数校验通过且权限对象查询成功；动作：批量追加用户组权限；结果：减少逐条写入开销并保持结果一致。
            group.permissions.add(*permissions)

            return Response(
                {
                    "status": "success",
                    "message": f"成功为用户组 {group.name} 分配了 {permissions.count()} 个权限。",
                    "assigned_permissions": [
                        {"id": p.id, "name": p.name, "codename": p.codename}
                        for p in permissions
                    ],
                },
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=["post"],
        url_path="batch-remove-permissions",
        serializer_class=BatchGroupPermissionOperationSerializer,
    )
    @permission_required("auth.change_group")
    def batch_remove_permissions(self, request, pk=None):
        """
        批量移除用户组权限
        请求体需提供权限编号列表。
        """
        group = self.get_object()
        serializer = BatchGroupPermissionOperationSerializer(data=request.data)

        if serializer.is_valid():
            permission_ids = serializer.validated_data["permission_ids"]
            permissions = Permission.objects.filter(id__in=permission_ids)

            # 条件：参数校验通过且权限对象查询成功；动作：批量移除用户组权限；结果：保证移除操作一次完成。
            group.permissions.remove(*permissions)

            return Response(
                {
                    "status": "success",
                    "message": f"成功从用户组 {group.name} 移除了 {permissions.count()} 个权限。",
                    "removed_permissions": [
                        {"id": p.id, "name": p.name, "codename": p.codename}
                        for p in permissions
                    ],
                },
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=["put"],
        url_path="update-permissions",
        serializer_class=UpdateGroupPermissionsSerializer,
    )
    @permission_required("auth.change_group")
    def update_group_permissions(self, request, pk=None):
        """
        更新用户组权限 - 完全替换用户组的权限列表
        请求体需提供目标权限编号列表。

        注意：
        - 此操作将完全替换用户组的权限列表
        - 传入空列表将清空用户组的所有权限
        - 需要具备用户组权限变更权限
        """
        group = self.get_object()
        serializer = UpdateGroupPermissionsSerializer(data=request.data)

        if serializer.is_valid():
            permission_ids = serializer.validated_data["permission_ids"]

            # 条件：开始执行替换；动作：先缓存更新前权限快照；结果：可用于生成前后对比结果。
            old_permissions = list(group.permissions.all())
            old_permission_data = [
                {"id": p.id, "name": p.name, "codename": p.codename}
                for p in old_permissions
            ]

            # 条件：请求携带目标权限列表；动作：查询目标权限对象集合；结果：为后续整体替换准备输入。
            if permission_ids:
                new_permissions = Permission.objects.filter(id__in=permission_ids)
            else:
                # 条件：请求传入空列表；动作：构造空权限集合；结果：后续整体替换后用户组权限被清空。
                new_permissions = Permission.objects.none()

            # 条件：已得到目标权限集合；动作：一次性替换用户组权限；结果：避免逐条增删造成中间态不一致。
            group.permissions.set(new_permissions)

            # 条件：替换完成；动作：读取替换后权限快照；结果：用于返回更新结果与审计信息。
            new_permission_data = [
                {"id": p.id, "name": p.name, "codename": p.codename}
                for p in new_permissions
            ]

            # 条件：已拿到前后集合；动作：计算新增与移除差集；结果：前端可直接展示变更摘要。
            old_ids = set(p.id for p in old_permissions)
            new_ids = set(permission_ids) if permission_ids else set()
            added_ids = new_ids - old_ids
            removed_ids = old_ids - new_ids

            return Response(
                {
                    "status": "success",
                    "message": f"成功更新用户组 {group.name} 的权限。添加了 {len(added_ids)} 个权限，移除了 {len(removed_ids)} 个权限。",
                    "group_id": group.id,
                    "group_name": group.name,
                    "changes": {
                        "added_count": len(added_ids),
                        "removed_count": len(removed_ids),
                        "total_permissions": len(new_ids),
                    },
                    "permissions": {
                        "before": old_permission_data,
                        "after": new_permission_data,
                    },
                },
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ContentTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    内容类型（模型）只读列表接口。
    用于在权限管理界面中选择模型。
    """

    queryset = ContentType.objects.exclude(
        app_label__in=["admin", "contenttypes", "sessions", "orchestrator_integration"]
    ).order_by("app_label", "model")
    serializer_class = ContentTypeSerializer
    permission_classes = [IsAuthenticated, HasModelPermission]
    filterset_fields = ["app_label"]  # 允许按应用标签筛选
    search_fields = ["app_label", "model"]  # 允许搜索应用标签和模型名称


class PermissionViewSet(
    viewsets.ReadOnlyModelViewSet
):  # 基础权限模型保持只读，避免误改系统权限定义
    """
    权限只读列表接口，并提供用户/用户组权限分配相关动作。

    支持按模型筛选、按应用筛选、按关键词搜索与按字段排序。
    筛选、搜索和排序的可用字段由本类的过滤与排序配置统一定义。
    """

    queryset = Permission.objects.exclude(
        content_type__app_label__in=["admin", "contenttypes", "sessions", "orchestrator_integration"]
    ).order_by("content_type__app_label", "codename")
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated, HasModelPermission]
    filterset_fields = [
        "content_type",
        "content_type__app_label",
    ]  # 允许按模型和应用筛选
    search_fields = ["name", "codename"]  # 允许搜索权限名称和代码
    ordering_fields = ["name", "codename", "content_type__app_label"]  # 允许排序的字段
    # 条件：访问权限列表与详情；动作：自动执行查看权限校验；结果：无查看权限的请求会被拒绝。

    @action(
        detail=True,
        methods=["post"],
        url_path="assign_to_user",
        serializer_class=PermissionAssignToUserSerializer,
    )
    @permission_required("auth.change_permission")
    def assign_to_user(self, request, pk=None):
        """
        将当前权限分配给指定用户。
        请求体需提供用户编号。

        注意：
        - 用户不能修改自己的权限（安全考虑）
        - 只有超级用户或有相应管理权限的用户可以修改其他用户权限
        """
        permission = self.get_object()
        serializer = PermissionAssignToUserSerializer(data=request.data)
        if serializer.is_valid():
            user_id = serializer.validated_data["user_id"]
            user = get_object_or_404(User, id=user_id)

            # 条件：操作目标是当前登录用户；动作：直接拒绝；结果：阻断“给自己加权”风险。
            if request.user == user:
                return Response(
                    {
                        "status": "forbidden",
                        "message": "出于安全考虑，您不能修改自己的权限。请联系管理员进行权限调整。",
                        "code": "SELF_PERMISSION_UPDATE_FORBIDDEN",
                        "user_id": user.id,
                        "username": user.username,
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            # 条件：非超级用户且缺少变更权限；动作：拒绝执行；结果：保证仅授权管理员可改他人权限。
            if not (
                request.user.is_superuser
                or request.user.has_perm("auth.change_permission")
            ):
                return Response(
                    {
                        "status": "forbidden",
                        "message": "您没有权限修改其他用户的权限。",
                        "code": "INSUFFICIENT_PERMISSIONS",
                        "required_permission": "auth.change_permission",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            user.user_permissions.add(permission)
            return Response(
                {
                    "status": "success",
                    "message": f"权限 {permission.codename} 已分配给用户 {user.username}。",
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=["post"],
        url_path="remove_from_user",
        serializer_class=PermissionAssignToUserSerializer,
    )
    @permission_required("auth.change_permission")
    def remove_from_user(self, request, pk=None):
        """
        从指定用户移除当前权限。
        请求体需提供用户编号。

        注意：
        - 用户不能修改自己的权限（安全考虑）
        - 只有超级用户或有相应管理权限的用户可以修改其他用户权限
        """
        permission = self.get_object()
        serializer = PermissionAssignToUserSerializer(data=request.data)
        if serializer.is_valid():
            user_id = serializer.validated_data["user_id"]
            user = get_object_or_404(User, id=user_id)

            # 条件：操作目标是当前登录用户；动作：直接拒绝；结果：阻断“给自己减权再绕过流程”等风险操作。
            if request.user == user:
                return Response(
                    {
                        "status": "forbidden",
                        "message": "出于安全考虑，您不能修改自己的权限。请联系管理员进行权限调整。",
                        "code": "SELF_PERMISSION_UPDATE_FORBIDDEN",
                        "user_id": user.id,
                        "username": user.username,
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            # 条件：非超级用户且缺少变更权限；动作：拒绝执行；结果：保证仅授权管理员可改他人权限。
            if not (
                request.user.is_superuser
                or request.user.has_perm("auth.change_permission")
            ):
                return Response(
                    {
                        "status": "forbidden",
                        "message": "您没有权限修改其他用户的权限。",
                        "code": "INSUFFICIENT_PERMISSIONS",
                        "required_permission": "auth.change_permission",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            user.user_permissions.remove(permission)
            return Response(
                {
                    "status": "success",
                    "message": f"权限 {permission.codename} 已从用户 {user.username} 移除。",
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=["post"],
        url_path="assign_to_group",
        serializer_class=PermissionAssignToGroupSerializer,
    )
    @permission_required("auth.change_group")
    def assign_to_group(self, request, pk=None):
        """
        将当前权限分配给指定用户组。
        请求体需提供用户组编号。
        """
        permission = self.get_object()
        serializer = PermissionAssignToGroupSerializer(data=request.data)
        if serializer.is_valid():
            group_id = serializer.validated_data["group_id"]
            group = get_object_or_404(Group, id=group_id)
            group.permissions.add(permission)
            return Response(
                {
                    "status": "success",
                    "message": f"权限 {permission.codename} 已分配给组 {group.name}。",
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=["post"],
        url_path="remove_from_group",
        serializer_class=PermissionAssignToGroupSerializer,
    )
    @permission_required("auth.change_group")
    def remove_from_group(self, request, pk=None):
        """
        从指定用户组移除当前权限。
        请求体需提供用户组编号。
        """
        permission = self.get_object()
        serializer = PermissionAssignToGroupSerializer(data=request.data)
        if serializer.is_valid():
            group_id = serializer.validated_data["group_id"]
            group = get_object_or_404(Group, id=group_id)
            group.permissions.remove(permission)
            return Response(
                {
                    "status": "success",
                    "message": f"权限 {permission.codename} 已从组 {group.name} 移除。",
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserViewSet(viewsets.ModelViewSet):
    """
    用户管理接口，支持用户增删改查。
    同时提供用户权限查询与批量维护能力。
    """


    queryset = User.objects.all().order_by("id")
    filter_backends = [SearchFilter]
    search_fields = ["username", "email", "first_name", "last_name"]
    permission_classes = [IsAuthenticated, HasModelPermission]

    # 条件：访问用户列表与详情；动作：自动执行查看权限校验；结果：无查看权限的请求会被拒绝。
    # 条件：创建用户；动作：自动执行新增权限校验；结果：防止未授权创建。
    # 条件：更新用户；动作：自动执行变更权限校验；结果：防止未授权修改。
    # 条件：删除用户；动作：自动执行删除权限校验；结果：防止未授权删除。

    def get_serializer_class(self):
        # 条件：创建用户；动作：使用写入型序列化器；结果：强制校验密码等创建字段。
        if self.action == "create":
            return UserSerializer
        # 条件：更新用户；动作：使用可选字段更新序列化器；结果：支持部分更新并区分敏感字段。
        elif self.action in ["update", "partial_update"]:
            return UserUpdateSerializer
        # 其余读取场景统一返回详情序列化器，避免暴露写入字段。
        return UserDetailSerializer

    def get_permissions(self):
        """
        为不同的操作设置不同的权限类
        注意：对于特殊操作（如用户查看自己的信息），我们使用自定义的权限检查逻辑
        """
        # 条件：查看个人信息/个人权限；动作：仅做登录校验；结果：允许进入后续对象级“本人可看”分支。
        if self.action in ["retrieve", "get_user_permissions"]:
            return [IsAuthenticated()]

        # 其他操作走默认模型权限控制，保持与项目权限体系一致。
        return super().get_permissions()

    def retrieve(self, request, *args, **kwargs):
        """
        重写详情读取方法，允许用户查看自己的详细信息。
        """
        instance = self.get_object()



        # 条件：不是本人且无管理员查看权限；动作：拒绝访问；结果：防止普通用户越权读取他人信息。
        if not (
            request.user == instance
            or request.user.is_superuser
            or request.user.has_perm("auth.view_user")
        ):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("您只能查看自己的用户信息")

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def check_object_permissions(self, request, obj):
        """
        重写对象权限检查，允许用户查看和修改自己的信息
        """
        # 条件：查看自己的权限信息；动作：短路返回；结果：绕过通用对象权限限制。
        if self.action in ["get_user_permissions"] and request.user == obj:
            return  # 条件：查看本人权限；动作：直接放行；结果：允许用户读取自己的权限信息。

        # 条件：用户修改自己资料；动作：允许修改非敏感字段；结果：兼顾自助修改与权限安全边界。
        if self.action in ["update", "partial_update"] and request.user == obj:
            # 检查是否触达敏感字段，一旦涉及敏感字段仍回退到标准权限校验。
            sensitive_fields = {
                "is_staff",
                "is_superuser",
                "is_active",
                "groups",
                "user_permissions",
            }
            if hasattr(request, "data") and any(
                field in request.data for field in sensitive_fields
            ):
                # 条件：请求触达敏感字段；动作：回退到标准对象权限检查；结果：敏感字段仍受管理员权限保护。
                super().check_object_permissions(request, obj)
            else:
                return  # 条件：仅修改基础资料；动作：直接放行；结果：用户可自助维护非敏感信息。

        # 条件：不满足任何放行分支；动作：执行默认对象权限检查；结果：保持统一权限边界。
        super().check_object_permissions(request, obj)

    @action(detail=True, methods=["get"], url_path="permissions")
    def get_user_permissions(self, request, pk=None):
        """
        获取用户的全部权限（含直接权限与用户组继承权限）。
        """
        user = self.get_object()
        permission_strings = (
            user.get_all_permissions()
        )  # 返回“应用名.权限代号”格式的权限字符串集合

        # 条件：用户无任何权限；动作：返回空查询集；结果：统一后续分页与序列化分支处理。
        if not permission_strings:
            all_perms_qs = Permission.objects.none()
        else:
            # 条件：存在权限字符串；动作：折叠成“或”查询条件并映射为权限对象；结果：可统一走数据库查询与排序。
            q_objects = Q()
            for perm_string in permission_strings:
                try:
                    app_label, codename = perm_string.split(".")
                    q_objects |= Q(content_type__app_label=app_label) & Q(
                        codename=codename
                    )
                except ValueError:
                    # 条件：权限字符串格式非法；动作：忽略当前条目；结果：单条脏数据不会影响整体权限查询。
                    pass

            # 条件：存在可用查询条件；动作：查询并排序；结果：返回可读性稳定的权限列表。
            if q_objects:
                all_perms_qs = Permission.objects.filter(q_objects).order_by(
                    "content_type__app_label", "codename"
                )
            else:
                # 条件：原始权限字符串非空但全部无法解析；动作：返回空查询集；结果：接口稳定返回空列表而不是报错。
                all_perms_qs = Permission.objects.none()

        # 条件：分页器生效；动作：返回分页响应；结果：权限列表在大数据量下仍可稳定加载。
        page = self.paginate_queryset(all_perms_qs)
        if page is not None:
            serializer = PermissionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = PermissionSerializer(all_perms_qs, many=True)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        url_path="batch-assign-permissions",
        serializer_class=BatchUserPermissionOperationSerializer,
    )
    @permission_required("auth.change_permission")
    def batch_assign_permissions(self, request, pk=None):
        """
        批量分配权限给用户
        请求体需提供权限编号列表。

        注意：
        - 用户不能修改自己的权限（安全考虑）
        - 只有超级用户或有相应管理权限的用户可以修改其他用户权限
        """
        user = self.get_object()

        # 条件：操作目标是当前登录用户；动作：直接拒绝；结果：阻断用户自改权限行为。
        if request.user == user:
            return Response(
                {
                    "status": "forbidden",
                    "message": "出于安全考虑，您不能修改自己的权限。请联系管理员进行权限调整。",
                    "code": "SELF_PERMISSION_UPDATE_FORBIDDEN",
                    "user_id": user.id,
                    "username": user.username,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # 条件：非超级用户且缺少变更权限；动作：拒绝执行；结果：保证仅授权管理员可改他人权限。
        if not (
            request.user.is_superuser or request.user.has_perm("auth.change_permission")
        ):
            return Response(
                {
                    "status": "forbidden",
                    "message": "您没有权限修改其他用户的权限。",
                    "code": "INSUFFICIENT_PERMISSIONS",
                    "required_permission": "auth.change_permission",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = BatchUserPermissionOperationSerializer(data=request.data)

        if serializer.is_valid():
            permission_ids = serializer.validated_data["permission_ids"]
            permissions = Permission.objects.filter(id__in=permission_ids)

            # 条件：参数校验通过且权限对象查询成功；动作：批量追加用户直接权限；结果：减少逐条写入开销并保持一致性。
            user.user_permissions.add(*permissions)

            return Response(
                {
                    "status": "success",
                    "message": f"成功为用户 {user.username} 分配了 {permissions.count()} 个权限。",
                    "assigned_permissions": [
                        {"id": p.id, "name": p.name, "codename": p.codename}
                        for p in permissions
                    ],
                },
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=["post"],
        url_path="batch-remove-permissions",
        serializer_class=BatchUserPermissionOperationSerializer,
    )
    @permission_required("auth.change_permission")
    def batch_remove_permissions(self, request, pk=None):
        """
        批量移除用户权限
        请求体需提供权限编号列表。

        注意：
        - 用户不能修改自己的权限（安全考虑）
        - 只有超级用户或有相应管理权限的用户可以修改其他用户权限
        """
        user = self.get_object()

        # 条件：操作目标是当前登录用户；动作：直接拒绝；结果：阻断用户自改权限行为。
        if request.user == user:
            return Response(
                {
                    "status": "forbidden",
                    "message": "出于安全考虑，您不能修改自己的权限。请联系管理员进行权限调整。",
                    "code": "SELF_PERMISSION_UPDATE_FORBIDDEN",
                    "user_id": user.id,
                    "username": user.username,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # 条件：非超级用户且缺少变更权限；动作：拒绝执行；结果：保证仅授权管理员可改他人权限。
        if not (
            request.user.is_superuser or request.user.has_perm("auth.change_permission")
        ):
            return Response(
                {
                    "status": "forbidden",
                    "message": "您没有权限修改其他用户的权限。",
                    "code": "INSUFFICIENT_PERMISSIONS",
                    "required_permission": "auth.change_permission",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = BatchUserPermissionOperationSerializer(data=request.data)

        if serializer.is_valid():
            permission_ids = serializer.validated_data["permission_ids"]
            permissions = Permission.objects.filter(id__in=permission_ids)

            # 条件：参数校验通过且权限对象查询成功；动作：批量移除用户直接权限；结果：保证移除操作一次完成。
            user.user_permissions.remove(*permissions)

            return Response(
                {
                    "status": "success",
                    "message": f"成功从用户 {user.username} 移除了 {permissions.count()} 个权限。",
                    "removed_permissions": [
                        {"id": p.id, "name": p.name, "codename": p.codename}
                        for p in permissions
                    ],
                },
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=["put"],
        url_path="update-permissions",
        serializer_class=UpdateUserPermissionsSerializer,
    )
    @permission_required("auth.change_permission")
    def update_permissions(self, request, pk=None):
        """
        更新用户权限 - 完全替换用户的直接权限列表
        请求体需提供目标权限编号列表。

        注意：
        - 用户不能修改自己的权限（安全考虑）
        - 只有超级用户或有相应管理权限的用户可以修改其他用户权限
        """
        user = self.get_object()

        # 条件：操作目标是当前登录用户；动作：直接拒绝；结果：阻断用户自改权限行为。
        if request.user == user:
            return Response(
                {
                    "status": "forbidden",
                    "message": "出于安全考虑，您不能修改自己的权限。请联系管理员进行权限调整。",
                    "code": "SELF_PERMISSION_UPDATE_FORBIDDEN",
                    "user_id": user.id,
                    "username": user.username,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # 条件：非超级用户且缺少变更权限；动作：拒绝执行；结果：保证仅授权管理员可改他人权限。
        if not (
            request.user.is_superuser or request.user.has_perm("auth.change_permission")
        ):
            return Response(
                {
                    "status": "forbidden",
                    "message": "您没有权限修改其他用户的权限。",
                    "code": "INSUFFICIENT_PERMISSIONS",
                    "required_permission": "auth.change_permission",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = UpdateUserPermissionsSerializer(data=request.data)

        if serializer.is_valid():
            permission_ids = serializer.validated_data["permission_ids"]

            # 条件：开始执行替换；动作：先缓存更新前直接权限快照；结果：可用于前后对比和变更统计。
            old_direct_permissions = list(user.user_permissions.all())
            old_permission_data = [
                {"id": p.id, "name": p.name, "codename": p.codename}
                for p in old_direct_permissions
            ]

            # 条件：请求携带目标权限列表；动作：查询目标权限对象集合；结果：为后续整体替换准备输入。
            if permission_ids:
                new_permissions = Permission.objects.filter(id__in=permission_ids)
            else:
                # 条件：请求传入空列表；动作：构造空权限集合；结果：后续整体替换后用户直接权限被清空。
                new_permissions = Permission.objects.none()

            # 条件：已得到目标权限集合；动作：一次性替换用户直接权限；结果：避免逐条增删造成中间态不一致。
            user.user_permissions.set(new_permissions)

            # 条件：替换完成；动作：读取替换后权限快照；结果：用于返回更新结果与审计信息。
            new_permission_data = [
                {"id": p.id, "name": p.name, "codename": p.codename}
                for p in new_permissions
            ]

            # 条件：已拿到前后集合；动作：计算新增与移除差集；结果：前端可直接展示变更摘要。
            old_ids = set(p.id for p in old_direct_permissions)
            new_ids = set(permission_ids) if permission_ids else set()
            added_ids = new_ids - old_ids
            removed_ids = old_ids - new_ids

            return Response(
                {
                    "status": "success",
                    "message": f"成功更新用户 {user.username} 的权限。添加了 {len(added_ids)} 个权限，移除了 {len(removed_ids)} 个权限。",
                    "user_id": user.id,
                    "username": user.username,
                    "changes": {
                        "added_count": len(added_ids),
                        "removed_count": len(removed_ids),
                        "total_direct_permissions": len(new_ids),
                    },
                    "permissions": {
                        "before": old_permission_data,
                        "after": new_permission_data,
                    },
                },
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MyTokenObtainPairView(BaseTokenObtainPairView):
    """
    用户登录接口。
    校验账号密码后返回访问令牌、刷新令牌以及用户基础信息。
    """

    serializer_class = MyTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        """
        当数据库尚未就绪时，返回可识别的友好错误，避免直接暴露 500 调试堆栈。
        """
        try:
            return super().post(request, *args, **kwargs)
        except OperationalError:
            return Response(
                {"detail": "认证服务正在启动，请稍后重试。"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
