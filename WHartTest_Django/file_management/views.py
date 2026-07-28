import mimetypes
import os
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.views.decorators.clickjacking import xframe_options_exempt
from django.utils.decorators import method_decorator
from rest_framework.filters import SearchFilter, OrderingFilter

from projects.models import Project
from wharttest_django.permissions import HasModelPermission
from wharttest_django.api_permissions import IsProjectMemberForResource
from wharttest_django.pagination import StandardPagination
from .models import FileAsset, FileManagementSetting
from .serializers import FileAssetSerializer, FileUploadSerializer, FileManagementSettingSerializer
from .services import validate_file_ids, extract_file_text, cleanup_unreferenced_files, resolve_file_reference_detail


from rest_framework_simplejwt.authentication import JWTAuthentication
from api_keys.authentication import APIKeyAuthentication


class QueryParamJWTAuthentication(JWTAuthentication):
    """
    Allow authentication using token in query parameters (e.g. ?token=...)
    specifically to support file download and iframe preview requests which
    cannot send standard HTTP Authorization headers.
    """
    def authenticate(self, request):
        header = self.get_header(request)
        if header is not None:
            raw_token = self.get_raw_token(header)
            if raw_token is not None:
                validated_token = self.get_validated_token(raw_token)
                return self.get_user(validated_token), validated_token

        token = request.query_params.get('token')
        if token:
            validated_token = self.get_validated_token(token)
            return self.get_user(validated_token), validated_token
        return None


class FileAssetViewSet(viewsets.ModelViewSet):
    authentication_classes = [QueryParamJWTAuthentication, APIKeyAuthentication]
    serializer_class = FileAssetSerializer
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['original_name', 'mime_type', 'extension']
    filterset_fields = ['status', 'extension', 'mime_type']
    ordering_fields = ['created_at', 'size', 'original_name']
    ordering = ['-created_at']
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_permissions(self):
        return [IsAuthenticated(), HasModelPermission(), IsProjectMemberForResource()]

    def get_project(self):
        return get_object_or_404(Project, pk=self.kwargs.get('project_pk'))

    def get_queryset(self):
        return FileAsset.objects.filter(
            project_id=self.kwargs.get('project_pk'),
            is_deleted=False,
        ).select_related('project', 'owner').prefetch_related('references')

    def create(self, request, *args, **kwargs):
        project = self.get_project()
        files = request.FILES.getlist('files') or request.FILES.getlist('file')
        if not files and 'file' in request.FILES:
            files = [request.FILES['file']]
        if not files:
            return Response({'detail': '请上传文件。'}, status=status.HTTP_400_BAD_REQUEST)
        created = []
        for uploaded in files:
            serializer = FileUploadSerializer(
                data={'file': uploaded},
                context={'request': request, 'project': project},
            )
            serializer.is_valid(raise_exception=True)
            created.append(serializer.save())
        data = FileAssetSerializer(created, many=True, context=self.get_serializer_context()).data
        return Response(data[0] if len(data) == 1 else data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get', 'post'], url_path='settings')
    def file_settings(self, request, *args, **kwargs):
        project = self.get_project()
        setting, _ = FileManagementSetting.objects.get_or_create(project=project)
        if request.method == 'POST':
            serializer = FileManagementSettingSerializer(setting, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
        else:
            serializer = FileManagementSettingSerializer(setting)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='cleanup-unreferenced')
    def cleanup_unreferenced(self, request, *args, **kwargs):
        project = self.get_project()
        deleted_count = cleanup_unreferenced_files(project)
        return Response({'deleted_count': deleted_count})

    @action(detail=False, methods=['post'])
    def validate(self, request, *args, **kwargs):
        project = self.get_project()
        files = validate_file_ids(request.data.get('file_ids', []), project, request.user)
        serializer = self.get_serializer(files, many=True)
        return Response({'valid': True, 'files': serializer.data})

    @action(detail=True, methods=['get'])
    def references(self, request, *args, **kwargs):
        asset = self.get_object()
        data = [resolve_file_reference_detail(ref) for ref in asset.references.select_related('created_by').order_by('-created_at')]
        return Response({'count': len(data), 'results': data})

    @action(detail=True, methods=['get'])
    def download(self, request, *args, **kwargs):
        asset = self.get_object()
        if not asset.file or not asset.file.storage.exists(asset.file.name):
            return Response({'detail': '文件不存在或物理文件已损坏。'}, status=status.HTTP_404_NOT_FOUND)
        filename = asset.original_name
        response = FileResponse(asset.file.open('rb'), as_attachment=True, filename=filename)
        response['Content-Type'] = asset.mime_type or mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        response['Content-Security-Policy'] = "default-src 'none';"
        # Help remote actuators invalidate local upload cache / verify integrity.
        if asset.sha256:
            response['ETag'] = f'"{asset.sha256}"'
            response['X-File-Sha256'] = asset.sha256
        if asset.size is not None:
            response['X-File-Size'] = str(asset.size)
        return response

    @method_decorator(xframe_options_exempt)
    @action(detail=True, methods=['get'])
    def preview(self, request, *args, **kwargs):
        asset = self.get_object()
        if not asset.file or not asset.file.storage.exists(asset.file.name):
            return Response({'detail': '文件不存在或物理文件已损坏。'}, status=status.HTTP_404_NOT_FOUND)
        mime = asset.mime_type or mimetypes.guess_type(asset.original_name)[0] or ''
        # Block image/svg+xml from inline rendering to prevent SVG XSS vulnerabilities
        if (mime.startswith('image/') and mime != 'image/svg+xml') or mime == 'application/pdf':
            response = FileResponse(asset.file.open('rb'), as_attachment=False, filename=asset.original_name)
            response['Content-Type'] = mime
            response['Content-Security-Policy'] = "default-src 'none';"
            return response
        text = extract_file_text(asset, max_chars=50000)
        return HttpResponse(text, content_type='text/plain; charset=utf-8')

    def destroy(self, request, *args, **kwargs):
        asset = self.get_object()
        if asset.references.exists():
            asset.is_deleted = True
            asset.status = FileAsset.STATUS_DELETED
            asset.save(update_fields=['is_deleted', 'status', 'updated_at'])
            return Response({'detail': '文件已被引用，已执行软删除。'}, status=status.HTTP_200_OK)
        asset.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
