import logging

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from wharttest_django.viewsets import BaseModelViewSet
from wharttest_django.permissions import HasModelPermission
from wharttest_django.pagination import StandardPagination
from wharttest_django.api_permissions import IsProjectMemberForResource

from .models import (
    ApiTestTaskSuite,
    ApiTestTaskExecution,
)
from .serializers import (
    ApiTestTaskSuiteSerializer,
    ApiTestTaskCaseCreateSerializer,
    ApiTestTaskCaseSimpleSerializer,
    ApiTestTaskExecutionSerializer,
    ApiTestTaskExecutionListSerializer,
    ApiTestTaskExecutionCreateSerializer,
    ApiTestTaskCaseResultSerializer,
)
from .services import ApiTestTaskService, ApiTestTaskExecutionService
from .tasks import execute_api_task_async

logger = logging.getLogger(__name__)


class ApiTestTaskSuiteViewSet(BaseModelViewSet):
    serializer_class = ApiTestTaskSuiteSerializer
    pagination_class = StandardPagination

    def get_permissions(self):
        return [IsAuthenticated(), HasModelPermission(), IsProjectMemberForResource()]

    def get_queryset(self):
        project_pk = self.kwargs.get('project_pk')
        return ApiTestTaskSuite.objects.filter(
            project_id=project_pk
        ).prefetch_related(
            'api_task_cases',
            'api_task_cases__testcase',
            'api_task_cases__interface_case',
            'api_task_cases__interface_case__interface',
        )

    def perform_create(self, serializer):
        from projects.models import Project
        project = get_object_or_404(Project, pk=self.kwargs.get('project_pk'))
        serializer.save(created_by=self.request.user, project=project)

    @action(detail=True, methods=['post'], url_path='add-testcases')
    def add_testcases(self, request, *args, **kwargs):
        task_suite = self.get_object()
        project_pk = self.kwargs.get('project_pk')
        serializer = ApiTestTaskCaseCreateSerializer(
            data=request.data,
            context={'project_pk': project_pk},
        )
        serializer.is_valid(raise_exception=True)

        testcase_ids = serializer.validated_data.get('testcase_ids', [])
        interface_case_ids = serializer.validated_data.get('interface_case_ids', [])
        task_cases = ApiTestTaskService.add_cases(
            task_suite,
            testcase_ids=testcase_ids,
            interface_case_ids=interface_case_ids,
            project_pk=project_pk,
        )

        result_serializer = ApiTestTaskCaseSimpleSerializer(task_cases, many=True)
        return Response(result_serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=['delete'],
        url_path='remove-case/(?P<case_type>[^/.]+)/(?P<case_id>[^/.]+)',
    )
    def remove_case(self, request, case_type=None, case_id=None, *args, **kwargs):
        task_suite = self.get_object()
        if case_type not in ['scenario', 'interface']:
            return Response(
                {'detail': 'Case type must be scenario or interface.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        success = ApiTestTaskService.remove_case(task_suite, case_type, case_id)
        if success:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(
            {'detail': 'Case not found in this suite.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    @action(
        detail=True,
        methods=['delete'],
        url_path='remove-testcase/(?P<testcase_id>[^/.]+)',
    )
    def remove_testcase(self, request, testcase_id=None, *args, **kwargs):
        task_suite = self.get_object()
        success = ApiTestTaskService.remove_testcase(task_suite, testcase_id)
        if success:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(
            {'detail': 'Test case not found in this suite.'},
            status=status.HTTP_404_NOT_FOUND,
        )


class ApiTestTaskExecutionViewSet(BaseModelViewSet):
    serializer_class = ApiTestTaskExecutionSerializer
    pagination_class = StandardPagination
    http_method_names = ['get', 'post', 'head', 'options']

    def get_permissions(self):
        return [IsAuthenticated(), HasModelPermission(), IsProjectMemberForResource()]

    def get_queryset(self):
        project_pk = self.kwargs.get('project_pk')
        queryset = ApiTestTaskExecution.objects.filter(
            task_suite__project_id=project_pk,
        ).select_related(
            'task_suite',
            'environment',
            'executed_by',
        ).prefetch_related(
            'api_case_results',
            'api_case_results__testcase',
            'api_case_results__interface_case',
            'api_case_results__report',
            'api_case_results__interface_report',
        )
        task_suite_id = self.request.query_params.get('task_suite_id')
        if task_suite_id:
            queryset = queryset.filter(task_suite_id=task_suite_id)
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return ApiTestTaskExecutionListSerializer
        return ApiTestTaskExecutionSerializer

    def create(self, request, *args, **kwargs):
        project_pk = self.kwargs.get('project_pk')
        serializer = ApiTestTaskExecutionCreateSerializer(
            data=request.data,
            context={'project_pk': project_pk},
        )
        serializer.is_valid(raise_exception=True)

        task_suite_id = serializer.validated_data['task_suite_id']
        environment_id = serializer.validated_data.get('environment_id')

        project_pk = self.kwargs.get('project_pk')
        task_suite = get_object_or_404(ApiTestTaskSuite, id=task_suite_id, project_id=project_pk)

        # Validate environment belongs to current project
        if environment_id:
            from api_environments.models import ApiEnvironment
            get_object_or_404(ApiEnvironment, id=environment_id, project_id=project_pk)

        execution = ApiTestTaskExecutionService.create_execution(
            task_suite=task_suite,
            environment_id=environment_id,
            user=request.user,
        )

        execute_api_task_async.delay(execution.id)

        result_serializer = ApiTestTaskExecutionSerializer(execution)
        return Response(result_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='case-results')
    def case_results(self, request, *args, **kwargs):
        execution = self.get_object()
        case_results = execution.api_case_results.all().order_by('id')
        serializer = ApiTestTaskCaseResultSerializer(case_results, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, *args, **kwargs):
        execution = self.get_object()
        if execution.status not in ['pending', 'running']:
            return Response(
                {'detail': 'Only pending or running executions can be canceled.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        execution.cancel()
        return Response({'detail': 'Execution canceled.'})
