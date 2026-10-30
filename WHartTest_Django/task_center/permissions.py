from rest_framework import permissions

from projects.models import ProjectMember


class IsProjectMemberForTaskCenter(permissions.BasePermission):
    """
    检查用户是否是任务中心所属项目的成员。

    任务对象直接关联 project，执行记录对象通过 task.project 关联项目，
    这里统一兼容两种对象结构。
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        project_pk = view.kwargs.get("project_pk")
        if not project_pk or str(project_pk).lower() in ("none", "null", "undefined"):
            return False

        try:
            project_pk = int(project_pk)
        except (TypeError, ValueError):
            return False

        return ProjectMember.objects.filter(
            project_id=project_pk,
            user=request.user,
            role__in=["owner", "admin", "member"],
        ).exists()

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        project_id = None
        if hasattr(obj, "project_id"):
            project_id = obj.project_id
        elif hasattr(obj, "task") and hasattr(obj.task, "project_id"):
            project_id = obj.task.project_id

        if not project_id:
            return False

        return ProjectMember.objects.filter(
            project_id=project_id,
            user=request.user,
            role__in=["owner", "admin", "member"],
        ).exists()
