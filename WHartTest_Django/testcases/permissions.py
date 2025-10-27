from rest_framework import permissions
from projects.models import ProjectMember # 用于检查项目成员

class IsProjectMemberForTestCase(permissions.BasePermission):
    """
    自定义权限，用于检查用户是否是与 TestCase 关联的项目的成员。
    允许项目所有者、管理员和普通成员访问。
    """

    def has_permission(self, request, view):
        """
        检查用户是否有权限访问列表视图或创建操作。
        对于列表视图，通常在 get_queryset 中进一步过滤。
        对于创建操作，需要确保 project_pk 在 URL 中。
        """
        if not request.user or not request.user.is_authenticated:
            return False

        # 对于创建操作，project_pk 应该在 view.kwargs 中
        project_pk = view.kwargs.get('project_pk')
        if not project_pk:
            # 如果没有 project_pk (例如，非嵌套的顶级列表视图，这不符合我们的设计)
            # 或者如果 project_pk 无法从 URL 获取，则拒绝权限。
            # 在我们的设计中，所有 testcase 操作都应嵌套在 project下。
            return False # 或者根据具体情况决定是否允许超级用户等

        # 检查用户是否是该项目的成员
        return ProjectMember.objects.filter(
            project_id=project_pk,
            user=request.user,
            role__in=['owner', 'admin', 'member'] # 任何角色的成员都可以
        ).exists()

    def has_object_permission(self, request, view, obj):
        """
        检查用户是否对单个对象（TestCase 实例）有权限。
        obj 是 TestCase 实例。
        """
        if not request.user or not request.user.is_authenticated:
            return False

        # TestCase 对象应该有一个 project 属性
        if not hasattr(obj, 'project'):
            return False # 对象没有关联项目，不应该发生

        # 检查用户是否是该 TestCase 所属项目的成员
        return ProjectMember.objects.filter(
            project=obj.project,
            user=request.user,
            role__in=['owner', 'admin', 'member']
        ).exists()

# 如果需要更细致的权限，例如“只有创建者才能修改/删除”，可以添加如下权限：
# class IsOwnerOrReadOnlyForTestCase(permissions.BasePermission):
#     """
#     对象级权限，只允许对象的所有者编辑它。
#     假设 TestCase 模型有一个 'creator' 字段。
#     """
#     def has_object_permission(self, request, view, obj):
#         # 读取权限允许任何请求，
#         # 所以我们总是允许 GET, HEAD 或 OPTIONS 请求。
#         if request.method in permissions.SAFE_METHODS:
#             return True
#
#         # 写入权限只授予用例的创建者。
#         return obj.creator == request.user


class IsProjectMemberForTestCaseModule(permissions.BasePermission):
    """
    自定义权限，用于检查用户是否是与 TestCaseModule 关联的项目的成员。
    允许项目所有者、管理员和普通成员访问。
    """

    def has_permission(self, request, view):
        """
        检查用户是否有权限访问列表视图或创建操作。
        对于列表视图，通常在 get_queryset 中进一步过滤。
        对于创建操作，需要确保 project_pk 在 URL 中。
        """
        if not request.user or not request.user.is_authenticated:
            return False

        # 对于创建操作，project_pk 应该在 view.kwargs 中
        project_pk = view.kwargs.get('project_pk')
        if not project_pk:
            # 如果没有 project_pk (例如，非嵌套的顶级列表视图，这不符合我们的设计)
            # 或者如果 project_pk 无法从 URL 获取，则拒绝权限。
            # 在我们的设计中，所有 testcase_module 操作都应嵌套在 project下。
            return False # 或者根据具体情况决定是否允许超级用户等

        # 检查用户是否是该项目的成员
        return ProjectMember.objects.filter(
            project_id=project_pk,
            user=request.user,
            role__in=['owner', 'admin', 'member'] # 任何角色的成员都可以
        ).exists()

    def has_object_permission(self, request, view, obj):
        """
        检查用户是否对单个对象（TestCaseModule 实例）有权限。
        obj 是 TestCaseModule 实例。
        """
        if not request.user or not request.user.is_authenticated:
            return False

        # TestCaseModule 对象应该有一个 project 属性
        if not hasattr(obj, 'project'):
            return False # 对象没有关联项目，不应该发生

        # 检查用户是否是该 TestCaseModule 所属项目的成员
        return ProjectMember.objects.filter(
            project=obj.project,
            user=request.user,
            role__in=['owner', 'admin', 'member']
        ).exists()


class IsProjectMemberForTestSuite(permissions.BasePermission):
    """
    自定义权限，用于检查用户是否是与 TestSuite 关联的项目的成员。
    """

    def has_permission(self, request, view):
        """检查用户是否有权限访问列表视图或创建操作"""
        if not request.user or not request.user.is_authenticated:
            return False

        project_pk = view.kwargs.get('project_pk')
        if not project_pk:
            return False

        return ProjectMember.objects.filter(
            project_id=project_pk,
            user=request.user,
            role__in=['owner', 'admin', 'member']
        ).exists()

    def has_object_permission(self, request, view, obj):
        """检查用户是否对单个TestSuite实例有权限"""
        if not request.user or not request.user.is_authenticated:
            return False

        if not hasattr(obj, 'project'):
            return False

        return ProjectMember.objects.filter(
            project=obj.project,
            user=request.user,
            role__in=['owner', 'admin', 'member']
        ).exists()


class IsProjectMemberForTestExecution(permissions.BasePermission):
    """
    自定义权限，用于检查用户是否是与 TestExecution 关联的项目的成员。
    """

    def has_permission(self, request, view):
        """检查用户是否有权限访问列表视图或创建操作"""
        if not request.user or not request.user.is_authenticated:
            return False

        project_pk = view.kwargs.get('project_pk')
        if not project_pk:
            return False

        return ProjectMember.objects.filter(
            project_id=project_pk,
            user=request.user,
            role__in=['owner', 'admin', 'member']
        ).exists()

    def has_object_permission(self, request, view, obj):
        """检查用户是否对单个TestExecution实例有权限"""
        if not request.user or not request.user.is_authenticated:
            return False

        # TestExecution通过suite关联到project
        if not hasattr(obj, 'suite') or not hasattr(obj.suite, 'project'):
            return False

        return ProjectMember.objects.filter(
            project=obj.suite.project,
            user=request.user,
            role__in=['owner', 'admin', 'member']
        ).exists()