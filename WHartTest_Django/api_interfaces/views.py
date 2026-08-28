import json
import logging
from copy import deepcopy
from types import SimpleNamespace

from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from wharttest_django.viewsets import BaseModelViewSet
from wharttest_django.permissions import HasModelPermission, permission_required
from wharttest_django.api_permissions import IsProjectMemberForResource
from wharttest_django.pagination import StandardPagination

from .models import ApiInterface, ApiInterfaceResult
from .serializers import ApiInterfaceSerializer, ApiInterfaceResultSerializer
from .logging_utils import new_trace_id, summarize_for_log
from .openapi import (
    OpenAPIError,
    build_openapi_document,
    import_openapi_interfaces,
)
from .exchange import dump_api_document, fetch_api_document, parse_api_document
from .runner import InterfaceRunner
from api_environments.services import persist_project_extract_variables

logger = logging.getLogger(__name__)


def _parse_bool(value, *, default: bool) -> bool:
    """宽松解析布尔值；无法识别时返回 default。"""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {'true', '1', 'yes', 'on'}:
        return True
    if text in {'false', '0', 'no', 'off', ''}:
        return False
    return default


def _database_config_payload(db_config):
    return {
        'db_type': db_config.db_type,
        'user': db_config.username,
        'password': db_config.password,
        'ip': db_config.host,
        'port': db_config.port,
        'database': db_config.database,
        'psm': db_config.psm,
    }


class ApiInterfaceViewSet(BaseModelViewSet):
    serializer_class = ApiInterfaceSerializer
    pagination_class = StandardPagination

    def get_permissions(self):
        return [IsAuthenticated(), HasModelPermission(), IsProjectMemberForResource()]

    def get_queryset(self):
        project_pk = self.kwargs.get('project_pk')
        queryset = ApiInterface.objects.filter(project_id=project_pk).select_related(
            'module', 'created_by'
        )

        no_module = self.request.query_params.get('no_module')
        if no_module and no_module.lower() in ('true', '1', 'yes'):
            queryset = queryset.filter(module__isnull=True)
        else:
            module_id = self.request.query_params.get('module_id')
            if module_id:
                queryset = queryset.filter(module_id=module_id)

        status_value = self.request.query_params.get('status')
        if status_value:
            queryset = queryset.filter(status=status_value)

        search = (self.request.query_params.get('search') or '').strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(url__icontains=search)
                | Q(method__icontains=search)
            )

        # 排序：支持 created_at / updated_at / id / name，前缀 - 表示降序
        ordering = (self.request.query_params.get('ordering') or '').strip()
        allowed_ordering = {
            'created_at', '-created_at',
            'updated_at', '-updated_at',
            'id', '-id',
            'name', '-name',
        }
        if ordering in allowed_ordering:
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by('-created_at')

        return queryset

    def perform_create(self, serializer):
        from projects.models import Project
        project = get_object_or_404(Project, pk=self.kwargs.get('project_pk'))
        serializer.save(created_by=self.request.user, project=project)

    @action(
        detail=False,
        methods=['post'],
        url_path='import-openapi',
        parser_classes=[MultiPartParser, FormParser, JSONParser],
    )
    def import_openapi(self, request, *args, **kwargs):
        """Import HTTP interfaces from a supported API document."""
        from projects.models import Project

        project = get_object_or_404(Project, pk=self.kwargs.get('project_pk'))
        upload = request.FILES.get('file')
        filename = getattr(upload, 'name', '') if upload else ''
        source_type = str(request.data.get('source_type') or '')
        source_url = request.data.get('source_url')
        strip_base_url = _parse_bool(request.data.get('strip_base_url'), default=True)
        create_environments = _parse_bool(request.data.get('create_environments'), default=False)

        try:
            if source_url:
                content, filename = fetch_api_document(str(source_url))
                source_type = 'swagger'
            elif upload:
                content = upload.read()
            else:
                content = request.data.get('document', request.data.get('content'))

            if content in (None, ''):
                return Response(
                    {'detail': 'Please provide an API document, Swagger URL, or cURL command.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            parsed = parse_api_document(
                content,
                filename=filename,
                source_type=source_type,
                strip_base_url=strip_base_url,
            )
            result = import_openapi_interfaces(
                document=parsed.document,
                project=project,
                user=request.user,
                request=request,
                view=self,
                strip_base_url=strip_base_url,
                create_environments=create_environments,
            )
            result['format'] = parsed.source_format
            result['version'] = parsed.source_version
        except OpenAPIError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        response_status = status.HTTP_201_CREATED if result['created_count'] else status.HTTP_200_OK
        return Response(result, status=response_status)

    @action(detail=False, methods=['get'], url_path='export-openapi')
    def export_openapi(self, request, *args, **kwargs):
        """Export project HTTP interfaces in a supported exchange format."""
        from projects.models import Project

        project = get_object_or_404(Project, pk=self.kwargs.get('project_pk'))
        export_format = request.query_params.get(
            'export_format',
            request.query_params.get('format', 'json'),
        )
        queryset = self.get_queryset()

        try:
            document = build_openapi_document(project, queryset)
            body, content_type, extension, format_name = dump_api_document(
                document,
                export_format,
                project_name=project.name,
            )
        except OpenAPIError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        filename = f"project-{project.id}-{format_name}.{extension}"
        response = HttpResponse(body, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


    @action(detail=False, methods=['post'], url_path='batch-delete')
    @permission_required('api_interfaces.delete_apiinterface')
    def batch_delete(self, request, *args, **kwargs):
        """批量删除接口。POST: {"ids": [1, 2, 3]}"""
        ids_data = request.data.get('ids', [])
        if not ids_data:
            return Response(
                {'error': '请提供要删除的接口ID列表'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            interface_ids = [int(item) for item in ids_data]
        except (ValueError, TypeError):
            return Response(
                {'error': 'ids参数格式错误，应为数字列表'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not interface_ids:
            return Response(
                {'error': '接口ID列表不能为空'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = self.get_queryset()
        interfaces_to_delete = queryset.filter(id__in=interface_ids)
        found_ids = list(interfaces_to_delete.values_list('id', flat=True))
        not_found_ids = [item_id for item_id in interface_ids if item_id not in found_ids]

        if not_found_ids:
            return Response(
                {
                    'error': f'以下接口ID不存在或不属于当前项目: {not_found_ids}',
                    'not_found_ids': not_found_ids,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        deleted_interfaces_info = [
            {
                'id': item.id,
                'name': item.name,
                'module': item.module.name if item.module else None,
            }
            for item in interfaces_to_delete
        ]

        try:
            with transaction.atomic():
                interfaces_to_delete.delete()
            return Response(
                {
                    'message': f'成功删除 {len(deleted_interfaces_info)} 个接口',
                    'deleted_count': len(deleted_interfaces_info),
                    'deleted_ids': found_ids,
                    'deleted_interfaces': deleted_interfaces_info,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            logger.exception('batch delete interfaces failed: %s', exc)
            return Response(
                {'error': f'批量删除失败: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=['post'])
    def duplicate(self, request, *args, **kwargs):
        """Duplicate an interface in the same project/module."""
        source = self.get_object()
        project_pk = self.kwargs.get('project_pk')

        base_name = request.data.get('name') or f"{source.name} 副本"
        candidate_name = base_name
        suffix = 2
        while ApiInterface.objects.filter(project_id=project_pk, name=candidate_name).exists():
            candidate_name = f"{base_name} {suffix}"
            suffix += 1

        duplicate_data = {
            'name': candidate_name,
            'type': source.type,
            'method': source.method,
            'url': source.url,
            'headers': deepcopy(source.headers),
            'params': deepcopy(source.params),
            'body': deepcopy(source.body),
            'sql_method': source.sql_method,
            'sql': source.sql,
            'sql_params': deepcopy(source.sql_params),
            'sql_size': source.sql_size,
            'setup_hooks': deepcopy(source.setup_hooks),
            'teardown_hooks': deepcopy(source.teardown_hooks),
            'variables': deepcopy(source.variables),
            'validators': deepcopy(source.validators),
            'extract': deepcopy(source.extract),
            'extract_meta': deepcopy(source.extract_meta),
            'file_ids': deepcopy(source.file_ids),
            'module': source.module_id,
            'status': source.status,
        }

        serializer = self.get_serializer(data=duplicate_data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=['post'])
    def run(self, request, *args, **kwargs):
        """Run an interface with optional environment configuration."""
        interface = self.get_object()
        environment_id = request.data.get('environment_id')

        interface_type = interface.type
        environment = None
        env_config = {}

        if environment_id:
            try:
                from api_environments.models import ApiEnvironment as Environment
                project_pk = self.kwargs.get('project_pk')
                environment = get_object_or_404(Environment, id=environment_id, project_id=project_pk)

                if hasattr(environment, 'get_all_variables') and callable(
                    environment.get_all_variables
                ):
                    env_config['variables'] = environment.get_all_variables()

                if interface_type == 'sql' and hasattr(environment, 'get_database_config'):
                    db_config = environment.get_database_config()
                    if db_config:
                        env_config['db_config'] = _database_config_payload(db_config)
            except Exception as e:
                logger.error(f"Failed to load environment {environment_id}: {str(e)}")
                return Response(
                    {'detail': f'Failed to load environment: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Build interface data
        interface_data = interface.get_interface_data()
        interface_data['project_id'] = interface.project_id
        trace_id = new_trace_id('ifc-run')
        interface_data['trace_id'] = trace_id
        interface_data['body_source'] = 'db_interface'
        override_fields = [
            field for field in (
                'method', 'url', 'headers', 'params', 'body',
                'setup_hooks', 'teardown_hooks', 'extract', 'validators',
            )
            if field in request.data
        ]
        logger.info(
            "Interface run request received: trace_id=%s project_id=%s interface_id=%s "
            "name=%s type=%s method=%s url=%s environment_id=%s body_source=%s "
            "db_body_summary=%s request_override_fields=%s "
            "request_body_override_present=%s ignored_by_run_endpoint=%s "
            "request_body_override_summary=%s",
            trace_id,
            interface.project_id,
            interface.id,
            interface.name,
            interface.type,
            interface_data.get('method'),
            interface_data.get('url'),
            environment_id,
            interface_data['body_source'],
            summarize_for_log(interface_data.get('body')),
            override_fields,
            'body' in request.data,
            bool(override_fields),
            summarize_for_log(request.data.get('body')) if 'body' in request.data else None,
        )

        if environment:
            interface_data['base_url'] = getattr(environment, 'base_url', '') or ''
            interface_data['verify'] = getattr(environment, 'verify_ssl', None)
        if env_config.get('db_config') and interface_type == 'sql':
            interface_data['db_config'] = env_config['db_config']

        try:
            runner = InterfaceRunner(interface_data)

            if env_config.get('variables'):
                runner.variables = runner.variables or {}
                runner.variables.update(env_config['variables'])

            runner.run_interface(env_config)
            response_data = runner.get_response()
            response_data['extract_persistence'] = persist_project_extract_variables(
                project_id=interface.project_id,
                environment_id=environment.id if environment else None,
                extracted_variables=response_data.get('extracted_variables', {}),
                extract_meta=interface_data.get('extract_meta', {}),
            )

            # Save result
            interface_result = ApiInterfaceResult.objects.create(
                interface=interface,
                environment_id=environment_id,
                success=response_data.get('success', False),
                elapsed=response_data.get('elapsed', 0),
                request_data=response_data.get('request', {}),
                response_data=response_data.get('response', {}),
                validation_results=response_data.get('validation_results', []),
                extracted_variables=response_data.get('extracted_variables', {}),
                executed_by=request.user,
            )
            request_body = response_data.get('request', {}).get('body')
            status_code = response_data.get('status_code')
            logger.info(
                "Interface run result saved: trace_id=%s result_id=%s interface_id=%s "
                "status_code=%s success=%s recorded_request_body_summary=%s "
                "transport_failure_record_body_may_be_empty=%s",
                trace_id,
                interface_result.id,
                interface.id,
                status_code,
                response_data.get('success', False),
                summarize_for_log(request_body),
                status_code == 0 and request_body is None,
            )

            return Response(response_data)

        except Exception as e:
            logger.error(f"Interface run failed: {str(e)}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=['post'])
    def quick_debug(self, request, *args, **kwargs):
        """Quick debug an interface without saving it first."""
        project_pk = self.kwargs.get('project_pk')
        interface_type = request.data.get('type', 'http')

        if interface_type == 'http':
            method = request.data.get('method')
            url = request.data.get('url')
            if not method:
                return Response(
                    {'detail': 'The "method" field is required.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not url:
                return Response(
                    {'detail': 'The "url" field is required.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif interface_type == 'sql':
            method = request.data.get('method', request.data.get('sql_method'))
            sql = request.data.get('sql')
            if not method:
                return Response(
                    {'detail': 'The "method" (sql_method) field is required.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not sql:
                return Response(
                    {'detail': 'The "sql" field is required.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        environment_id = request.data.get('environment_id')
        environment = None
        env_config = {}

        if environment_id:
            try:
                from api_environments.models import ApiEnvironment as Environment
                environment = get_object_or_404(Environment, id=environment_id, project_id=project_pk)

                if hasattr(environment, 'get_all_variables') and callable(
                    environment.get_all_variables
                ):
                    env_config['variables'] = environment.get_all_variables()

                if interface_type == 'sql' and hasattr(environment, 'get_database_config'):
                    db_config = environment.get_database_config()
                    if db_config:
                        env_config['db_config'] = _database_config_payload(db_config)
            except Exception as e:
                logger.error(f"Failed to load environment {environment_id}: {str(e)}")
                return Response(
                    {'detail': f'Failed to load environment: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Build interface data from request
        interface_data = {
            'name': request.data.get('name', 'Quick Debug'),
            'type': interface_type,
            'project_id': int(project_pk),
            'trace_id': new_trace_id('ifc-debug'),
            'body_source': 'request_payload',
            'setup_hooks': request.data.get('setup_hooks', []),
            'teardown_hooks': request.data.get('teardown_hooks', []),
            'variables': request.data.get('variables', {}),
            'validators': request.data.get('validators', []),
            'extract': request.data.get('extract', {}),
            'extract_meta': request.data.get('extract_meta', {}),
            'file_ids': request.data.get('file_ids', []),
        }

        if interface_type == 'http':
            interface_data.update({
                'method': request.data.get('method', 'GET'),
                'url': request.data.get('url', ''),
                'headers': request.data.get('headers', {}),
                'params': request.data.get('params', {}),
                'body': request.data.get('body', {}),
            })
        elif interface_type == 'sql':
            interface_data.update({
                'method': request.data.get('method', request.data.get('sql_method', 'fetchone')),
                'sql': request.data.get('sql', ''),
                'params': request.data.get('sql_params', {}),
                'size': request.data.get('sql_size', 10),
            })

        logger.info(
            "Interface quick_debug request received: trace_id=%s project_id=%s "
            "type=%s method=%s url=%s environment_id=%s body_source=%s "
            "request_body_summary=%s",
            interface_data['trace_id'],
            project_pk,
            interface_type,
            interface_data.get('method'),
            interface_data.get('url'),
            environment_id,
            interface_data['body_source'],
            summarize_for_log(interface_data.get('body')),
        )

        if environment:
            interface_data['base_url'] = getattr(environment, 'base_url', '') or ''
            interface_data['verify'] = getattr(environment, 'verify_ssl', None)
        if env_config.get('db_config') and interface_type == 'sql':
            interface_data['db_config'] = env_config['db_config']

        try:
            runner = InterfaceRunner(interface_data)

            if env_config.get('variables'):
                runner.variables = runner.variables or {}
                runner.variables.update(env_config['variables'])

            runner.run_interface(env_config)
            response_data = runner.get_response()
            response_data['extract_persistence'] = persist_project_extract_variables(
                project_id=int(project_pk),
                environment_id=environment.id if environment else None,
                extracted_variables=response_data.get('extracted_variables', {}),
                extract_meta=interface_data.get('extract_meta', {}),
            )
            request_body = response_data.get('request', {}).get('body')
            status_code = response_data.get('status_code')
            logger.info(
                "Interface quick_debug result generated: trace_id=%s status_code=%s "
                "success=%s recorded_request_body_summary=%s "
                "transport_failure_record_body_may_be_empty=%s",
                interface_data['trace_id'],
                status_code,
                response_data.get('success', False),
                summarize_for_log(request_body),
                status_code == 0 and request_body is None,
            )

            return Response(response_data)

        except Exception as e:
            logger.error(f"Quick debug failed: {str(e)}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ApiInterfaceResultViewSet(BaseModelViewSet):
    serializer_class = ApiInterfaceResultSerializer
    http_method_names = ['get', 'head', 'options']

    def get_permissions(self):
        return [IsAuthenticated(), HasModelPermission(), IsProjectMemberForResource()]

    def get_queryset(self):
        project_pk = self.kwargs.get('project_pk')
        queryset = ApiInterfaceResult.objects.filter(
            interface__project_id=project_pk
        )
        interface_id = self.request.query_params.get('interface_id')
        if interface_id:
            queryset = queryset.filter(interface_id=interface_id)
        return queryset
