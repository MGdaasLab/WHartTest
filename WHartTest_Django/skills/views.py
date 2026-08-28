import logging

from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from wharttest_django.viewsets import BaseModelViewSet
from projects.models import Project
from .models import Skill
from .serializers import SkillSerializer, SkillUploadSerializer, SkillGitImportSerializer, SkillListSerializer, SkillToggleSerializer, SkillZipUrlImportSerializer

logger = logging.getLogger(__name__)


class SkillViewSet(BaseModelViewSet):
    """
    Skill 视图集

    支持：
    - GET /projects/{project_id}/skills/ - 列表
    - POST /projects/{project_id}/skills/upload/ - 上传
    - POST /projects/{project_id}/skills/import-git/ - 从 Git 导入
    - GET /projects/{project_id}/skills/{id}/ - 详情
    - PATCH /projects/{project_id}/skills/{id}/ - 更新（仅 is_active）
    - DELETE /projects/{project_id}/skills/{id}/ - 删除
    """
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        # Skills 当前设计为全局共享资源，不按项目过滤查询集。
        return Skill.objects.all()

    def get_permissions(self):
        # store_config / store_manifest / store_readme 仅做配置返回或远程代理拉取，不读写 Skill 数据。
        if getattr(self, 'action', None) in ('store_config', 'store_manifest', 'store_readme'):
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_serializer_class(self):
        # 按动作切换序列化器，确保每个接口只暴露必要字段与校验规则。
        if self.action == 'list':
            return SkillListSerializer
        if self.action == 'upload':
            return SkillUploadSerializer
        if self.action == 'import_git':
            return SkillGitImportSerializer
        if self.action == 'import_zip_url':
            return SkillZipUrlImportSerializer
        if self.action == 'partial_update':
            return SkillToggleSerializer
        return SkillSerializer

    def get_project(self):
        # 解析嵌套路由中的项目 ID；不存在时返回 404。
        project_id = self.kwargs.get('project_pk')
        return get_object_or_404(Project, id=project_id)

    def list(self, request, *args, **kwargs):
        """获取项目下的所有 Skills"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'code': 200,
            'message': '获取成功',
            'data': serializer.data
        })

    def retrieve(self, request, *args, **kwargs):
        """获取 Skill 详情"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            'code': 200,
            'message': '获取成功',
            'data': serializer.data
        })

    def partial_update(self, request, *args, **kwargs):
        """更新 Skill（仅支持 is_active）"""
        instance = self.get_object()
        # 条件：缺少 is_active；动作：拒绝；结果：避免误改其它只读字段。
        if 'is_active' not in request.data:
            return Response({
                'code': 400,
                'message': '缺少 is_active 字段',
                'data': None
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({
            'code': 200,
            'message': '更新成功',
            'data': SkillSerializer(instance).data
        })

    def destroy(self, request, *args, **kwargs):
        """删除 Skill"""
        instance = self.get_object()
        name = instance.name
        # 删除数据库记录会触发模型 delete() 中的文件清理逻辑。
        instance.delete()
        return Response({
            'code': 200,
            'message': f"Skill '{name}' 已删除"
        })

    @action(detail=False, methods=['post'], url_path='upload')
    def upload(self, request, *args, **kwargs):
        """
        上传 Skill zip 文件

        请求：multipart/form-data, file 字段为 zip 文件
        """
        serializer = SkillUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        zip_file = serializer.validated_data['file']
        api_key = (serializer.validated_data.get('api_key') or '').strip() or None
        project = self.get_project()

        try:
            # 条件：上传包合法；动作：解压并创建一个或多个 Skill；结果：返回新 Skills 的完整信息。
            skills = Skill.create_from_zip(
                zip_file=zip_file,
                project=project,
                creator=request.user,
                api_key=api_key,
            )
            names = ', '.join(s.name for s in skills)
            return Response({
                'code': 201,
                'message': f"成功上传 {len(skills)} 个 Skill: {names}",
                'data': SkillSerializer(skills, many=True).data
            }, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            # 参数/文件内容校验失败返回 400，便于前端直接提示用户修正输入。
            msg = e.messages[0] if hasattr(e, 'messages') and e.messages else str(e)
            return Response({
                'code': 400,
                'message': msg,
                'data': None
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # 未预期异常记录堆栈并返回 500，避免将内部错误细节暴露给客户端。
            logger.exception("Skill upload failed: %s", e)
            return Response({
                'code': 500,
                'message': '上传失败',
                'data': None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='import-git')
    def import_git(self, request, *args, **kwargs):
        """
        从 Git 仓库导入 Skills（支持仓库包含多个 Skill）

        请求：application/json，包含 git_url（必填）和 branch（可选）
        """
        serializer = SkillGitImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        git_url = serializer.validated_data['git_url']
        branch = serializer.validated_data.get('branch', 'main')
        api_key = (serializer.validated_data.get('api_key') or '').strip() or None
        project = self.get_project()

        try:
            skills = Skill.create_from_git(
                git_url=git_url,
                branch=branch,
                project=project,
                creator=request.user,
                api_key=api_key,
            )
            names = ', '.join(s.name for s in skills)
            return Response({
                'code': 201,
                'message': f"成功导入 {len(skills)} 个 Skill: {names}",
                'data': SkillSerializer(skills, many=True).data
            }, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            msg = e.messages[0] if hasattr(e, 'messages') and e.messages else str(e)
            return Response({
                'code': 400,
                'message': msg,
                'data': None
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Skill git import failed: %s", e)
            return Response({
                'code': 500,
                'message': '导入失败',
                'data': None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'], url_path='content')
    def content(self, request, *args, **kwargs):
        """获取 Skill 的 SKILL.md 内容"""
        instance = self.get_object()
        return Response({
            'code': 200,
            'message': '获取成功',
            'data': {
                'name': instance.name,
                'description': instance.description,
                'content': instance.skill_content
            }
        })

    @action(detail=False, methods=['post'], url_path='import-zip-url')
    def import_zip_url(self, request, *args, **kwargs):
        """
        从远程 zip URL 导入 Skill（用于 Skill 商店）

        请求：application/json，包含 zip_url（必填）和 sha256（可选）
        """
        serializer = SkillZipUrlImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        zip_url = serializer.validated_data['zip_url']
        sha256 = serializer.validated_data.get('sha256') or None
        api_key = (serializer.validated_data.get('api_key') or '').strip() or None
        project = self.get_project()

        try:
            skills = Skill.create_from_zip_url(
                zip_url=zip_url,
                project=project,
                creator=request.user,
                expected_sha256=sha256,
                api_key=api_key,
            )
            names = ', '.join(s.name for s in skills)
            return Response({
                'code': 201,
                'message': f"成功导入 {len(skills)} 个 Skill: {names}",
                'data': SkillSerializer(skills, many=True).data
            }, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            msg = e.messages[0] if hasattr(e, 'messages') and e.messages else str(e)
            return Response({
                'code': 400,
                'message': msg,
                'data': None
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Skill zip-url import failed: %s", e)
            return Response({
                'code': 500,
                'message': '导入失败',
                'data': None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='store-config')
    def store_config(self, request, *args, **kwargs):
        """
        获取 Skill 商店配置（默认源、是否允许自定义源）

        前端启动时拉取一次，用于决定默认商店源 URL
        """
        from django.conf import settings as dj_settings
        return Response({
            'code': 200,
            'message': '获取成功',
            'data': {
                'default_source': getattr(dj_settings, 'SKILL_STORE_DEFAULT_SOURCE', ''),
                'default_source_name': getattr(dj_settings, 'SKILL_STORE_DEFAULT_SOURCE_NAME', ''),
                'allow_custom_source': bool(getattr(dj_settings, 'SKILL_STORE_ALLOW_CUSTOM_SOURCE', True)),
                'max_zip_size': int(getattr(dj_settings, 'SKILL_STORE_MAX_ZIP_SIZE', 10 * 1024 * 1024)),
            }
        })

    @staticmethod
    def _proxy_fetch_text(url: str, max_size: int, timeout: float = 15.0) -> str:
        """代理拉取远程文本资源（含 SSRF 校验、大小限制、超时）。"""
        try:
            import httpx
        except ImportError:
            raise ValidationError('服务器未安装 httpx')

        url = Skill._validate_remote_url(url)

        chunks: list[bytes] = []
        total = 0
        try:
            with httpx.stream(
                'GET', url,
                timeout=httpx.Timeout(timeout, connect=10.0),
                follow_redirects=True,
            ) as resp:
                if resp.status_code != 200:
                    raise ValidationError(f'上游响应异常：HTTP {resp.status_code}')
                # Content-Length 在头部时先做预判，避免无谓下载。
                cl = resp.headers.get('content-length')
                if cl and cl.isdigit() and int(cl) > max_size:
                    raise ValidationError(f'文件过大，超过 {max_size // 1024}KB 限制')
                for chunk in resp.iter_bytes(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_size:
                        raise ValidationError(f'文件过大，超过 {max_size // 1024}KB 限制')
                    chunks.append(chunk)
        except httpx.TimeoutException:
            raise ValidationError(f'上游请求超时（{int(timeout)}秒）')
        except httpx.RequestError as e:
            raise ValidationError(f'上游请求失败：{e}')

        raw = b''.join(chunks)
        try:
            return raw.decode('utf-8')
        except UnicodeDecodeError:
            raise ValidationError('上游响应不是 UTF-8 文本')

    @action(detail=False, methods=['get'], url_path='store-manifest')
    def store_manifest(self, request, *args, **kwargs):
        """
        代理拉取商店 manifest.json，绕过浏览器 CORS 限制

        请求：?url=https://.../manifest.json
        """
        import json

        url = (request.query_params.get('url') or '').strip()
        if not url:
            return Response({
                'code': 400, 'message': '缺少 url 参数', 'data': None
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            text = self._proxy_fetch_text(url, max_size=1 * 1024 * 1024)
        except ValidationError as e:
            msg = e.messages[0] if hasattr(e, 'messages') and e.messages else str(e)
            return Response({
                'code': 400, 'message': msg, 'data': None
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            return Response({
                'code': 400, 'message': f'manifest.json 解析失败：{e}', 'data': None
            }, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(data, dict) or not isinstance(data.get('skills'), list):
            return Response({
                'code': 400, 'message': 'manifest.json 必须是包含 skills 数组的对象', 'data': None
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({'code': 200, 'message': '获取成功', 'data': data})

    @action(detail=False, methods=['get'], url_path='store-readme')
    def store_readme(self, request, *args, **kwargs):
        """
        代理拉取商店 README 文本，绕过浏览器 CORS 限制

        请求：?url=https://.../README.md
        """
        url = (request.query_params.get('url') or '').strip()
        if not url:
            return Response({
                'code': 400, 'message': '缺少 url 参数', 'data': None
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            content = self._proxy_fetch_text(url, max_size=1 * 1024 * 1024)
        except ValidationError as e:
            msg = e.messages[0] if hasattr(e, 'messages') and e.messages else str(e)
            return Response({
                'code': 400, 'message': msg, 'data': None
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({'code': 200, 'message': '获取成功', 'data': {'content': content}})
