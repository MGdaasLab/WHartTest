from rest_framework import generics, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Count, Q
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

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

        # 条件：超级用户；动作：返回全部项目；结果：平台管理员可跨项目管理。
        if user.is_superuser:
            return Project.objects.all()

        # 非超级用户仅可查看自己参与的项目，避免越权枚举其他项目。
        return Project.objects.filter(members__user=user).distinct()

    def get_serializer_class(self):
        """
        根据操作类型返回不同的序列化器
        """
        # 详情接口需携带成员列表和凭据等扩展信息。
        if self.action == 'retrieve':
            return ProjectDetailSerializer
        # 其余场景使用基础序列化器减少返回负载。
        return ProjectSerializer

    def get_permissions(self):
        """
        根据操作类型设置不同的权限
        """
        # 成员管理操作：先过项目成员模型权限，再校验调用者属于该项目。
        if self.action in ['members', 'add_member', 'remove_member', 'update_member_role']:
            return [HasProjectMemberPermission(), IsProjectMember()]

        # 统计接口只读，要求登录且属于项目即可。
        if self.action == 'statistics':
            return [IsAuthenticated(), IsProjectMember()]

        # 其他操作需要基础权限（用户认证 + Django模型权限）
        base_permissions = super().get_permissions()
        
        # 在基础权限之上叠加项目角色权限，保证“模型权限 + 业务角色”双层防线。
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
            # 条件：创建项目；动作：写入 creator；结果：项目可追溯创建责任人。
            project = serializer.save(creator=self.request.user)
            
            # 创建者默认成为 owner，保证其拥有项目最高管理权限。
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
            
            # 条件：遍历平台管理员；动作：补齐 admin 成员关系；结果：平台管理员自动具备项目接管能力。
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

        # 分页开启时返回分页结构，避免大项目成员列表一次性返回。
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

        # 条件：参数合法；动作：创建成员并返回详情；结果：前端可直接刷新成员列表。
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

        # 条件：缺失 user_id；动作：直接拒绝；结果：避免执行无目标的删除操作。
        if not user_id:
            return Response({"error": "必须提供用户ID"}, status=status.HTTP_400_BAD_REQUEST)

        # 条件：目标是 owner 且操作者非超级用户；动作：拒绝；结果：避免项目失去拥有者。
        member = get_object_or_404(ProjectMember, project=project, user_id=user_id)
        if member.role == 'owner' and not request.user.is_superuser:
            return Response({"error": "不能移除项目拥有者"}, status=status.HTTP_403_FORBIDDEN)

        # 条件：尝试删除自己且非超级用户；动作：拒绝；结果：避免误操作导致无人管理。
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

        # 条件：缺少必要参数；动作：拒绝；结果：阻断不完整角色更新请求。
        if not user_id or not role:
            return Response({"error": "必须提供用户ID和角色"}, status=status.HTTP_400_BAD_REQUEST)

        # 条件：角色不在允许值中；动作：拒绝；结果：避免写入无效角色。
        if role not in [r[0] for r in ProjectMember.ROLE_CHOICES]:
            return Response({"error": f"无效的角色，可选值为: {[r[0] for r in ProjectMember.ROLE_CHOICES]}"},
                           status=status.HTTP_400_BAD_REQUEST)

        member = get_object_or_404(ProjectMember, project=project, user_id=user_id)

        # 条件：目标成员当前是 owner；动作：仅 owner/超级用户可修改；结果：限制关键角色变更入口。
        if member.role == 'owner' and not (request.user.is_superuser or
                                          ProjectMember.objects.filter(project=project, user=request.user, role='owner').exists()):
            return Response({"error": "只有项目拥有者或超级管理员可以修改拥有者角色"}, status=status.HTTP_403_FORBIDDEN)

        # 条件：尝试修改自己角色且非超级用户；动作：拒绝；结果：避免误降权后无法恢复。
        if member.user == request.user and not request.user.is_superuser:
            return Response({"error": "不能修改自己的角色"}, status=status.HTTP_403_FORBIDDEN)

        # 使用事务确保数据一致性
        with transaction.atomic():
            # 条件：目标角色为 owner；动作：先处理旧 owner；结果：确保任一时刻仅有一个 owner。
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

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """
        获取项目统计数据
        """
        project = self.get_object()

        # 导入所需模型
        from testcases.models import TestCase, TestExecution
        from skills.models import Skill
        from mcp_tools.models import RemoteMCPConfig
        from ui_automation.models import UiTestCase, UiExecutionRecord
        from api_testcases.models import ApiTestCase, ApiTestReport
        from api_testtasks.models import ApiTestTaskExecution
        from api_interfaces.models import ApiInterface
        from api_sync.models import ApiSyncConfig

        # 1. 功能用例统计（按审核状态）
        testcase_stats = TestCase.objects.filter(project=project).aggregate(
            total=Count('id'),
            pending_review=Count('id', filter=Q(review_status='pending_review')),
            approved=Count('id', filter=Q(review_status='approved')),
            needs_optimization=Count('id', filter=Q(review_status='needs_optimization')),
            optimization_pending_review=Count('id', filter=Q(review_status='optimization_pending_review')),
            unavailable=Count('id', filter=Q(review_status='unavailable')),
        )

        # 2. 测试执行统计（最近的执行汇总）
        executions = TestExecution.objects.filter(suite__project=project)
        execution_stats = executions.aggregate(
            total_executions=Count('id'),
            total_passed=Count('id', filter=Q(status='completed')),
            total_failed=Count('id', filter=Q(status='failed')),
            total_cancelled=Count('id', filter=Q(status='cancelled')),
        )

        # 计算用例执行结果汇总
        execution_result_stats = executions.aggregate(
            passed_count=Count('passed_count'),
            failed_count=Count('failed_count'),
            skipped_count=Count('skipped_count'),
            error_count=Count('error_count'),
        )

        # 从所有执行记录中汇总实际的用例执行结果
        from django.db.models import Sum
        execution_result_totals = executions.aggregate(
            total_passed_cases=Sum('passed_count'),
            total_failed_cases=Sum('failed_count'),
            total_skipped_cases=Sum('skipped_count'),
            total_error_cases=Sum('error_count'),
            total_cases=Sum('total_count'),
        )

        # 4. 执行历史趋势（近7天和近30天）
        now = timezone.now()
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)

        # 近 7 天按天聚合执行趋势，供前端绘制趋势图。
        daily_stats_7d = []
        for i in range(7):
            day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            day_executions = executions.filter(created_at__gte=day_start, created_at__lt=day_end)
            day_agg = day_executions.aggregate(
                count=Count('id'),
                passed=Sum('passed_count'),
                failed=Sum('failed_count'),
            )
            daily_stats_7d.append({
                'date': day_start.strftime('%Y-%m-%d'),
                'execution_count': day_agg['count'] or 0,
                'passed': day_agg['passed'] or 0,
                'failed': day_agg['failed'] or 0,
            })
        daily_stats_7d.reverse()

        # 近30天统计汇总
        stats_30d = executions.filter(created_at__gte=thirty_days_ago).aggregate(
            execution_count=Count('id'),
            passed=Sum('passed_count'),
            failed=Sum('failed_count'),
        )

        # 5. MCP统计（全局共享的MCP配置）
        mcp_stats = {
            'total': RemoteMCPConfig.objects.count(),
            'active': RemoteMCPConfig.objects.filter(is_active=True).count(),
        }

        # 6. Skills统计（全局共享的Skills）
        skill_stats = {
            'total': Skill.objects.count(),
            'active': Skill.objects.filter(is_active=True).count(),
        }

        # 7. UI自动化统计
        ui_testcases = UiTestCase.objects.filter(project=project)
        ui_executions = UiExecutionRecord.objects.filter(test_case__project=project)
        ui_automation_stats = {
            'total_cases': ui_testcases.count(),
            'total_executions': ui_executions.count(),
            'by_status': {
                'success': ui_executions.filter(status=2).count(),
                'failed': ui_executions.filter(status=3).count(),
                'cancelled': ui_executions.filter(status=4).count(),
            },
        }

        # 8. API 自动化测试统计
        api_testcases = ApiTestCase.objects.filter(project=project)
        api_interfaces = ApiInterface.objects.filter(project=project)
        api_sync_configs = ApiSyncConfig.objects.filter(interface__project=project)
        api_task_executions = ApiTestTaskExecution.objects.filter(
            task_suite__project=project,
        )
        api_reports = ApiTestReport.objects.filter(testcase__project=project)

        api_testing_stats = {
            'total_cases': api_testcases.count(),
            'total_interfaces': api_interfaces.count(),
            'total_sync_configs': api_sync_configs.count(),
            'total_executions': api_task_executions.count(),
            'execution_by_status': {
                'completed': api_task_executions.filter(status='completed').count(),
                'failed': api_task_executions.filter(status='failed').count(),
                'running': api_task_executions.filter(status='running').count(),
                'canceled': api_task_executions.filter(status='canceled').count(),
            },
            'report_summary': api_reports.aggregate(
                total=Count('id'),
                success=Count('id', filter=Q(status='success')),
                failure=Count('id', filter=Q(status='failure')),
                error=Count('id', filter=Q(status='error')),
            ),
        }

        # 构建响应数据
        response_data = {
            'project': {
                'id': project.id,
                'name': project.name,
            },
            'testcases': {
                'total': testcase_stats['total'],
                'by_review_status': {
                    'pending_review': testcase_stats['pending_review'],
                    'approved': testcase_stats['approved'],
                    'needs_optimization': testcase_stats['needs_optimization'],
                    'optimization_pending_review': testcase_stats['optimization_pending_review'],
                    'unavailable': testcase_stats['unavailable'],
                },
            },
            'executions': {
                'total_executions': execution_stats['total_executions'],
                'by_status': {
                    'completed': execution_stats['total_passed'],
                    'failed': execution_stats['total_failed'],
                    'cancelled': execution_stats['total_cancelled'],
                },
                'case_results': {
                    'total': execution_result_totals['total_cases'] or 0,
                    'passed': execution_result_totals['total_passed_cases'] or 0,
                    'failed': execution_result_totals['total_failed_cases'] or 0,
                    'skipped': execution_result_totals['total_skipped_cases'] or 0,
                    'error': execution_result_totals['total_error_cases'] or 0,
                },
            },
            'execution_trend': {
                'daily_7d': daily_stats_7d,
                'summary_30d': {
                    'execution_count': stats_30d['execution_count'] or 0,
                    'passed': stats_30d['passed'] or 0,
                    'failed': stats_30d['failed'] or 0,
                },
            },
            'mcp': mcp_stats,
            'skills': skill_stats,
            'ui_automation': ui_automation_stats,
            'api_testing': api_testing_stats,
        }

        return Response(response_data)
