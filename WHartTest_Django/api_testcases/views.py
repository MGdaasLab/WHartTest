from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as django_filters
from django.db import transaction, models
from django.db.models import Count, Max
from django.shortcuts import get_object_or_404

from wharttest_django.pagination import StandardPagination

from wharttest_django.viewsets import BaseModelViewSet
from wharttest_django.permissions import HasModelPermission
from wharttest_django.api_permissions import IsProjectMemberForResource

from .models import (
    ApiTestCase, ApiTestCaseStep, ApiTestReport, ApiTestReportDetail,
    ApiTestCaseTag, ApiTestCaseGroup,
    ApiInterfaceCase, ApiInterfaceCaseStep, ApiInterfaceCaseReport
)
from .serializers import (
    ApiTestCaseSerializer, ApiTestCaseStepSerializer,
    ApiTestReportSerializer, ApiTestReportDetailSerializer,
    ApiTestCaseTagSerializer, ApiTestCaseGroupSerializer,
    InterfaceOptionSerializer, ApiTestReportListSerializer,
    ApiInterfaceCaseSerializer, ApiInterfaceCaseStepSerializer,
    ApiInterfaceCaseReportSerializer, ApiInterfaceCaseReportListSerializer
)
from .services import TestCaseService, TestExecutionService, InterfaceCaseExecutionService


class ApiTestCaseFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    description = django_filters.CharFilter(lookup_expr='icontains')
    tags = django_filters.ModelMultipleChoiceFilter(
        field_name='tags',
        queryset=ApiTestCaseTag.objects.all(),
        conjoined=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request:
            project_pk = self.request.parser_context.get('kwargs', {}).get('project_pk')
            if project_pk:
                self.filters['tags'].queryset = ApiTestCaseTag.objects.filter(
                    project_id=project_pk
                )

    class Meta:
        model = ApiTestCase
        fields = {
            'priority': ['exact'],
            'group': ['exact']
        }


class ApiInterfaceCaseFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    description = django_filters.CharFilter(lookup_expr='icontains')
    interface_id = django_filters.NumberFilter(field_name='interface_id')
    tags = django_filters.ModelMultipleChoiceFilter(
        field_name='tags',
        queryset=ApiTestCaseTag.objects.all(),
        conjoined=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request:
            project_pk = self.request.parser_context.get('kwargs', {}).get('project_pk')
            if project_pk:
                self.filters['tags'].queryset = ApiTestCaseTag.objects.filter(
                    project_id=project_pk
                )

    class Meta:
        model = ApiInterfaceCase
        fields = {
            'priority': ['exact'],
            'group': ['exact'],
            'interface': ['exact'],
        }


class ApiTestReportFilter(django_filters.FilterSet):
    project = django_filters.NumberFilter(field_name='testcase__project')
    project_id = django_filters.NumberFilter(field_name='testcase__project')

    class Meta:
        model = ApiTestReport
        fields = {
            'status': ['exact'],
            'testcase': ['exact'],
            'environment': ['exact'],
            'executed_by': ['exact'],
            'testcase__project': ['exact']
        }


class ApiInterfaceCaseReportFilter(django_filters.FilterSet):
    project = django_filters.NumberFilter(field_name='interface_case__project')
    project_id = django_filters.NumberFilter(field_name='interface_case__project')

    class Meta:
        model = ApiInterfaceCaseReport
        fields = {
            'status': ['exact'],
            'interface_case': ['exact'],
            'environment': ['exact'],
            'executed_by': ['exact'],
            'interface_case__project': ['exact'],
        }


class ApiTestCaseTagViewSet(BaseModelViewSet):
    queryset = ApiTestCaseTag.objects.all()
    serializer_class = ApiTestCaseTagSerializer
    filterset_fields = ['project']
    search_fields = ['name']
    ordering = ['name']

    def get_permissions(self):
        return [IsAuthenticated(), HasModelPermission(), IsProjectMemberForResource()]

    def get_queryset(self):
        project_pk = self.kwargs.get('project_pk')
        return ApiTestCaseTag.objects.filter(project_id=project_pk)

    def perform_create(self, serializer):
        from projects.models import Project
        project = get_object_or_404(Project, pk=self.kwargs.get('project_pk'))
        serializer.save(created_by=self.request.user, project=project)

    @action(detail=False)
    def statistics(self, request, **kwargs):
        tags = self.get_queryset().annotate(
            usage_count=Count('api_testcases')
        ).values('id', 'name', 'color', 'usage_count')
        return Response(list(tags))


class ApiTestCaseGroupViewSet(BaseModelViewSet):
    queryset = ApiTestCaseGroup.objects.all()
    serializer_class = ApiTestCaseGroupSerializer
    filterset_fields = ['parent']
    search_fields = ['name']
    ordering = ['name']

    def get_permissions(self):
        return [IsAuthenticated(), HasModelPermission(), IsProjectMemberForResource()]

    def get_queryset(self):
        project_pk = self.kwargs.get('project_pk')
        return ApiTestCaseGroup.objects.filter(project_id=project_pk)

    def perform_create(self, serializer):
        from projects.models import Project
        project = get_object_or_404(Project, pk=self.kwargs.get('project_pk'))
        serializer.save(created_by=self.request.user, project=project)

    @action(detail=False)
    def tree(self, request, **kwargs):
        root_groups = self.get_queryset().filter(parent=None)
        serializer = self.get_serializer(root_groups, many=True)
        return Response(serializer.data)

    @action(detail=True)
    def testcases(self, request, pk=None, **kwargs):
        group = self.get_object()
        testcases = group.api_testcases.all()
        serializer = ApiTestCaseSerializer(testcases, many=True)
        return Response(serializer.data)


class ApiTestCaseViewSet(BaseModelViewSet):
    queryset = ApiTestCase.objects.all()
    serializer_class = ApiTestCaseSerializer
    pagination_class = StandardPagination
    filterset_class = ApiTestCaseFilter
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    def get_permissions(self):
        return [IsAuthenticated(), HasModelPermission(), IsProjectMemberForResource()]

    def get_queryset(self):
        project_pk = self.kwargs.get('project_pk')
        return ApiTestCase.objects.filter(project_id=project_pk)

    def perform_create(self, serializer):
        from projects.models import Project
        project = get_object_or_404(Project, pk=self.kwargs.get('project_pk'))
        serializer.save(created_by=self.request.user, project=project)

    @staticmethod
    def _build_single_step_order_map(testcase, target_step, new_order):
        all_steps = list(testcase.steps.all().order_by('order'))
        new_orders = {}
        current_position = 1

        for step in all_steps:
            if step.id == target_step.id:
                continue
            if current_position == new_order:
                new_orders[target_step.id] = new_order
                current_position += 1
            new_orders[step.id] = current_position
            current_position += 1

        if target_step.id not in new_orders:
            new_orders[target_step.id] = current_position

        return all_steps, new_orders

    @staticmethod
    def _apply_step_order_map(testcase, all_steps, new_orders):
        for step in all_steps:
            step.order = step.order + 1000
            step.save(update_fields=['order'])

        for step_id_to_update, final_order in new_orders.items():
            ApiTestCaseStep.objects.filter(
                id=step_id_to_update,
                testcase=testcase
            ).update(order=final_order)

    @action(detail=False)
    def available_interfaces(self, request, **kwargs):
        from api_interfaces.models import ApiInterface
        project_pk = self.kwargs.get('project_pk')
        interfaces = ApiInterface.objects.filter(
            project_id=project_pk
        ).select_related('project', 'module')
        serializer = InterfaceOptionSerializer(interfaces, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['GET'])
    def referenced_interfaces(self, request, pk=None, **kwargs):
        testcase = self.get_object()
        steps = testcase.steps.filter(
            origin_interface__isnull=False
        ).select_related('origin_interface', 'origin_interface__module')

        interfaces = {}
        for step in steps:
            interface = step.origin_interface
            if interface.id not in interfaces:
                interfaces[interface.id] = {
                    'interface': interface,
                    'steps': []
                }
            interfaces[interface.id]['steps'].append(step)

        data = []
        for interface_info in interfaces.values():
            interface = interface_info['interface']
            steps_list = interface_info['steps']
            data.append({
                'id': interface.id,
                'name': interface.name,
                'method': interface.method,
                'url': interface.url,
                'module': interface.module.name if interface.module else "Uncategorized",
                'steps': [{
                    'id': s.id,
                    'name': s.name,
                    'order': s.order,
                    'sync_fields': s.sync_fields,
                    'last_sync_time': s.last_sync_time
                } for s in steps_list]
            })

        return Response(data)

    @action(detail=True, methods=['post'])
    def copy(self, request, pk=None, **kwargs):
        source = self.get_object()
        project_pk = self.kwargs.get('project_pk')

        with transaction.atomic():
            base_name = request.data.get('name') or f"{source.name}_copy"
            candidate_name = base_name
            suffix = 2
            while ApiTestCase.objects.filter(project_id=project_pk, name=candidate_name).exists():
                candidate_name = f"{base_name}{suffix}"
                suffix += 1

            testcase = ApiTestCase.objects.create(
                name=candidate_name,
                description=source.description,
                priority=source.priority,
                config=source.config,
                file_ids=source.file_ids,
                project=source.project,
                group=source.group,
                created_by=request.user,
            )
            testcase.tags.set(source.tags.all())

            steps = ApiTestCaseStep.objects.filter(testcase=source).order_by('order')
            for step in steps:
                ApiTestCaseStep.objects.create(
                    name=step.name,
                    order=step.order,
                    interface_data=step.interface_data,
                    config=step.config,
                    file_ids=step.file_ids,
                    testcase=testcase,
                    origin_interface=step.origin_interface,
                    sync_fields=step.sync_fields,
                    last_sync_time=step.last_sync_time,
                )

        serializer = self.get_serializer(testcase)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None, **kwargs):
        testcase = self.get_object()
        environment_id = request.data.get('environment_id') or request.data.get('environment')

        environment_config = None
        if environment_id is not None:
            try:
                from api_environments.models import ApiEnvironment
                project_pk = self.kwargs.get('project_pk')
                env = ApiEnvironment.objects.get(id=environment_id, project_id=project_pk)
                environment_config = {
                    'id': env.id,
                    'base_url': env.base_url,
                    'verify_ssl': env.verify_ssl,
                    'variables': env.get_all_variables()
                }
            except Exception:
                return Response(
                    {'detail': f'Environment ID {environment_id} not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

        try:
            report = TestExecutionService.run_testcase(
                testcase=testcase,
                environment=environment_config,
                user=request.user
            )

            return Response({
                'report_id': report.id,
                'status': report.status,
                'success_count': report.success_count,
                'fail_count': report.fail_count,
                'error_count': report.error_count,
                'duration': report.duration,
                'config': environment_config
            })

        except Exception as e:
            return Response(
                {'detail': f'Test case execution failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def batch_run(self, request, **kwargs):
        testcase_ids = request.data.get('testcase_ids', [])
        if not testcase_ids:
            return Response(
                {'detail': 'testcase_ids parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        project_pk = self.kwargs.get('project_pk')
        environment_id = request.data.get('environment_id') or request.data.get('environment')

        environment_config = None
        if environment_id is not None:
            try:
                from api_environments.models import ApiEnvironment
                env = ApiEnvironment.objects.get(id=environment_id, project_id=project_pk)
                environment_config = {
                    'id': env.id,
                    'base_url': env.base_url,
                    'verify_ssl': env.verify_ssl,
                    'variables': env.get_all_variables()
                }
            except Exception:
                return Response(
                    {'detail': f'Environment ID {environment_id} not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

        try:
            testcases = ApiTestCase.objects.filter(id__in=testcase_ids, project_id=project_pk)
            reports = TestExecutionService.run_batch(
                testcases=testcases,
                environment=environment_config,
                user=request.user
            )

            statistics = TestExecutionService.get_statistics(reports)

            return Response({
                'statistics': statistics,
                'report_ids': [report.id for report in reports],
                'config': environment_config
            })

        except Exception as e:
            return Response(
                {'detail': f'Batch execution failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['delete'])
    def delete_step(self, request, pk=None, **kwargs):
        testcase = self.get_object()
        step_id = request.query_params.get('step_id')

        if not step_id:
            return Response(
                {'detail': 'step_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                step = testcase.steps.get(id=step_id)
                step.delete()

                for index, s in enumerate(
                    testcase.steps.all().order_by('order'), start=1
                ):
                    if s.order != index:
                        s.order = index
                        s.save()

            serializer = self.get_serializer(testcase)
            return Response(serializer.data)

        except ApiTestCaseStep.DoesNotExist:
            return Response(
                {'detail': 'Test step not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        update_mode = request.data.get('update_mode', 'auto')
        data = request.data.copy()

        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data['update_mode'] = update_mode
        result = serializer.save()

        if isinstance(result, dict) and 'status' in result:
            return Response(result)

        return Response(serializer.data)

    @action(detail=True)
    def history_reports(self, request, pk=None, **kwargs):
        testcase = self.get_object()
        reports = testcase.api_reports.all().select_related(
            'environment', 'executed_by'
        ).order_by('-start_time')

        page = self.paginate_queryset(reports)
        if page is not None:
            serializer = ApiTestReportListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ApiTestReportListSerializer(reports, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['put'])
    def update_step(self, request, pk=None, **kwargs):
        testcase = self.get_object()
        step_id = request.data.get('step_id')

        if not step_id:
            return Response(
                {'detail': 'step_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            step = testcase.steps.get(id=step_id)
            old_order = step.order
            new_order = request.data.get('order')

            data_without_order = request.data.copy()
            if 'order' in data_without_order:
                data_without_order.pop('order')

            serializer = ApiTestCaseStepSerializer(
                instance=step,
                data=data_without_order,
                context={'request': request},
                partial=True
            )
            serializer.is_valid(raise_exception=True)

            with transaction.atomic():
                if new_order is not None and int(new_order) != old_order:
                    new_order = int(new_order)
                    all_steps, new_orders = self._build_single_step_order_map(
                        testcase=testcase,
                        target_step=step,
                        new_order=new_order,
                    )
                    self._apply_step_order_map(testcase, all_steps, new_orders)

                    step.refresh_from_db()

                if data_without_order:
                    serializer.save()

            return Response(serializer.data)

        except ApiTestCaseStep.DoesNotExist:
            return Response(
                {'detail': 'Test step not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'])
    def reorder_steps(self, request, pk=None, **kwargs):
        testcase = self.get_object()
        steps_data = request.data.get('steps')
        single_step_id = request.data.get('step_id')
        new_order = request.data.get('new_order')

        try:
            with transaction.atomic():
                if steps_data:
                    step_ids = [s['step_id'] for s in steps_data]
                    existing_steps = testcase.steps.filter(id__in=step_ids)

                    if existing_steps.count() != len(step_ids):
                        return Response(
                            {'detail': 'Some step IDs are invalid'},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    order_map = {s['step_id']: s['order'] for s in steps_data}
                    all_steps = list(testcase.steps.all().order_by('order', 'id'))

                    for step in all_steps:
                        step.order = step.order + 1000
                        step.save(update_fields=['order'])

                    for step in existing_steps:
                        if step.id in order_map:
                            step.order = order_map[step.id]
                            step.save(update_fields=['order'])

                    normalized_steps = testcase.steps.all().order_by('order', 'id')
                    for index, step in enumerate(normalized_steps, start=1):
                        if step.order != index:
                            step.order = index
                            step.save(update_fields=['order'])

                    serializer = self.get_serializer(testcase)
                    return Response(serializer.data)

                elif single_step_id and new_order is not None:
                    try:
                        step = testcase.steps.get(id=single_step_id)
                    except ApiTestCaseStep.DoesNotExist:
                        return Response(
                            {'detail': 'Test step not found'},
                            status=status.HTTP_404_NOT_FOUND
                        )

                    old_order = step.order
                    new_order = int(new_order)

                    if old_order == new_order:
                        return Response(
                            ApiTestCaseStepSerializer(step).data
                        )

                    all_steps, new_orders = self._build_single_step_order_map(
                        testcase=testcase,
                        target_step=step,
                        new_order=new_order,
                    )
                    self._apply_step_order_map(testcase, all_steps, new_orders)
                    step.refresh_from_db()

                    return Response(
                        ApiTestCaseStepSerializer(step).data
                    )

                else:
                    return Response(
                        {'detail': 'Provide steps array or step_id with new_order'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

        except Exception as e:
            return Response(
                {'detail': f'Failed to reorder steps: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ApiInterfaceCaseViewSet(BaseModelViewSet):
    queryset = ApiInterfaceCase.objects.all()
    serializer_class = ApiInterfaceCaseSerializer
    pagination_class = StandardPagination
    filterset_class = ApiInterfaceCaseFilter
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    def get_permissions(self):
        return [IsAuthenticated(), HasModelPermission(), IsProjectMemberForResource()]

    def get_queryset(self):
        project_pk = self.kwargs.get('project_pk')
        queryset = ApiInterfaceCase.objects.filter(project_id=project_pk).select_related(
            'interface', 'interface__module', 'group', 'created_by'
        ).prefetch_related('tags', 'steps', 'steps__origin_interface')

        interface_id = self.request.query_params.get('interface_id')
        if interface_id:
            queryset = queryset.filter(interface_id=interface_id)

        module_id = self.request.query_params.get('module_id')
        if module_id:
            queryset = queryset.filter(interface__module_id=module_id)

        no_module = self.request.query_params.get('no_module')
        if no_module and no_module.lower() in ('true', '1', 'yes'):
            queryset = queryset.filter(interface__module__isnull=True)

        return queryset

    def perform_create(self, serializer):
        from projects.models import Project
        project = get_object_or_404(Project, pk=self.kwargs.get('project_pk'))
        serializer.save(created_by=self.request.user, project=project)

    @action(detail=True, methods=['post'])
    def copy(self, request, pk=None, **kwargs):
        source = self.get_object()
        project_pk = self.kwargs.get('project_pk')

        with transaction.atomic():
            base_name = request.data.get('name') or f"{source.name}_copy"
            candidate_name = base_name
            suffix = 2
            while ApiInterfaceCase.objects.filter(project_id=project_pk, name=candidate_name).exists():
                candidate_name = f"{base_name}{suffix}"
                suffix += 1

            interface_case = ApiInterfaceCase.objects.create(
                name=candidate_name,
                description=source.description,
                priority=source.priority,
                config=source.config,
                file_ids=source.file_ids,
                project=source.project,
                interface=source.interface,
                group=source.group,
                created_by=request.user,
            )
            interface_case.tags.set(source.tags.all())

            steps = ApiInterfaceCaseStep.objects.filter(interface_case=source).order_by('order')
            for step in steps:
                ApiInterfaceCaseStep.objects.create(
                    name=step.name,
                    role=step.role,
                    order=step.order,
                    interface_data=step.interface_data,
                    config=step.config,
                    file_ids=step.file_ids,
                    interface_case=interface_case,
                    origin_interface=step.origin_interface,
                    sync_fields=step.sync_fields,
                    last_sync_time=step.last_sync_time,
                )

        serializer = self.get_serializer(interface_case)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None, **kwargs):
        interface_case = self.get_object()
        environment_id = request.data.get('environment_id') or request.data.get('environment')

        environment_config = None
        if environment_id is not None:
            try:
                from api_environments.models import ApiEnvironment
                project_pk = self.kwargs.get('project_pk')
                env = ApiEnvironment.objects.get(id=environment_id, project_id=project_pk)
                environment_config = {
                    'id': env.id,
                    'base_url': env.base_url,
                    'verify_ssl': env.verify_ssl,
                    'variables': env.get_all_variables()
                }
                db_config = env.get_database_config()
                if db_config:
                    environment_config['db_config'] = _database_config_payload(db_config)
            except Exception:
                return Response(
                    {'detail': f'Environment ID {environment_id} not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

        try:
            report = InterfaceCaseExecutionService.run_interface_case(
                interface_case=interface_case,
                environment=environment_config,
                user=request.user,
            )

            extract_persistence = {}
            if isinstance(getattr(report, 'summary', None), dict):
                extract_persistence = report.summary.get('extract_persistence', {})

            return Response({
                'report_id': report.id,
                'status': report.status,
                'success_count': report.success_count,
                'fail_count': report.fail_count,
                'error_count': report.error_count,
                'duration': report.duration,
                'config': environment_config,
                'extract_persistence': extract_persistence,
            })

        except Exception as e:
            return Response(
                {'detail': f'Interface case execution failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True)
    def history_reports(self, request, pk=None, **kwargs):
        interface_case = self.get_object()
        reports = interface_case.api_reports.all().select_related(
            'interface_case', 'interface_case__interface', 'environment', 'executed_by'
        ).order_by('-start_time')

        page = self.paginate_queryset(reports)
        if page is not None:
            serializer = ApiInterfaceCaseReportListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ApiInterfaceCaseReportListSerializer(reports, many=True)
        return Response(serializer.data)


class ApiTestReportViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ApiTestReport.objects.all()
    serializer_class = ApiTestReportSerializer
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ApiTestReportFilter
    search_fields = ['name', 'testcase__name']
    ordering_fields = ['start_time', 'duration', 'success_count', 'fail_count', 'error_count']
    ordering = ['-start_time']

    def get_permissions(self):
        return [IsAuthenticated(), HasModelPermission(), IsProjectMemberForResource()]

    def get_serializer_class(self):
        if self.action == 'list':
            return ApiTestReportListSerializer
        return ApiTestReportSerializer

    def get_queryset(self):
        project_pk = self.kwargs.get('project_pk')
        queryset = ApiTestReport.objects.filter(testcase__project_id=project_pk)

        if self.action == 'list':
            return queryset.select_related(
                'testcase', 'environment', 'executed_by'
            )

        return queryset.select_related(
            'testcase', 'environment', 'environment__project', 'executed_by'
        ).prefetch_related('details', 'details__step')


class ApiInterfaceCaseReportViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ApiInterfaceCaseReport.objects.all()
    serializer_class = ApiInterfaceCaseReportSerializer
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ApiInterfaceCaseReportFilter
    search_fields = ['name', 'interface_case__name', 'interface_case__interface__name']
    ordering_fields = ['start_time', 'duration', 'success_count', 'fail_count', 'error_count']
    ordering = ['-start_time']

    def get_permissions(self):
        return [IsAuthenticated(), HasModelPermission(), IsProjectMemberForResource()]

    def get_serializer_class(self):
        if self.action == 'list':
            return ApiInterfaceCaseReportListSerializer
        return ApiInterfaceCaseReportSerializer

    def get_queryset(self):
        project_pk = self.kwargs.get('project_pk')
        queryset = ApiInterfaceCaseReport.objects.filter(interface_case__project_id=project_pk)

        if self.action == 'list':
            return queryset.select_related(
                'interface_case', 'interface_case__interface',
                'environment', 'executed_by'
            )

        return queryset.select_related(
            'interface_case', 'interface_case__interface',
            'environment', 'environment__project', 'executed_by'
        ).prefetch_related('details', 'details__step')
