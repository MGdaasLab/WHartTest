from rest_framework import viewsets, status, filters, permissions
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.urls import reverse
from django.shortcuts import get_object_or_404
import logging
import os

from wharttest_django.viewsets import BaseModelViewSet
from wharttest_django.permissions import permission_required
from prompts.models import UserPrompt
from .docx_editor_client import DocxEditorClientError, DocxEditorNotConfiguredError, create_docx_editor_session
from .models import (
    RequirementDocument,
    RequirementModule,
    ReviewReport,
    ReviewIssue,
    ModuleReviewResult,
    DocumentImage,
)
from .serializers import (
    RequirementDocumentSerializer,
    RequirementDocumentDetailSerializer,
    RequirementDocumentUploadSerializer,
    RequirementModuleSerializer,
    ReviewReportSerializer,
    ReviewIssueSerializer,
    ModuleReviewResultSerializer,
    ModuleAdjustmentSerializer,
    ReviewAnalysisRequestSerializer,
    ReviewProgressSerializer,
)
from .filters import (
    RequirementDocumentFilter,
    RequirementModuleFilter,
    ReviewReportFilter,
    ReviewIssueFilter,
    ModuleReviewResultFilter,
)
from .docx_editor_integration import (
    DocxEditorIntegrationError,
    DocxEditorNotConfiguredError,
    launch_requirement_document_in_docx_editor,
    replace_requirement_document_with_edited_file,
)
from .permissions import (
    IsProjectMemberForRequirement,
    IsProjectAdminForRequirement,
    CanManageRequirementDocument,
    CanStartReview,
)
from .services import (
    RequirementModuleService,
    ModuleOperationService,
    RequirementReviewService,
)

logger = logging.getLogger(__name__)


class RequirementDocumentViewSet(BaseModelViewSet):
    """需求文档视图集"""

    queryset = RequirementDocument.objects.all()
    serializer_class = RequirementDocumentSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = RequirementDocumentFilter
    search_fields = ["title", "description", "content"]
    ordering_fields = ["uploaded_at", "updated_at", "title", "word_count", "page_count"]
    ordering = ["-uploaded_at"]

    def get_permissions(self):
        """根据操作类型设置不同的权限"""
        # 图片访问接口公开，无需认证
        if self.action == "get_image":
            return []

        # 获取基础权限（用户认证 + Django模型权限）
        base_permissions = super().get_permissions()

        # 在基础权限之上添加项目特定的权限检查
        if self.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
            "launch_online_editor",
            "upload_edited_file",
        ]:
            return base_permissions + [CanManageRequirementDocument()]
        else:
            return base_permissions + [IsProjectMemberForRequirement()]

    def get_queryset(self):
        """只返回用户有权限访问的需求文档"""
        user = self.request.user
        if user.is_superuser:
            return RequirementDocument.objects.all()

        # 普通用户只能看到自己是成员的项目的需求文档
        return RequirementDocument.objects.filter(
            project__members__user=user
        ).distinct()

    def get_serializer_class(self):
        """根据操作返回不同的序列化器"""
        if self.action == "create":
            return RequirementDocumentUploadSerializer
        elif self.action == "retrieve":
            return RequirementDocumentDetailSerializer
        return RequirementDocumentSerializer

    def perform_create(self, serializer):
        """创建文档时自动设置上传人并提取内容"""
        document = serializer.save(uploader=self.request.user)

        # 立即提取文档内容
        if document.file and not document.content:
            try:
                from .services import DocumentProcessor

                processor = DocumentProcessor()
                content = processor.extract_content(document)

                if content:
                    document.content = content
                    document.word_count = len(content)
                    document.page_count = max(1, (len(content) // 500) + 1)
                    document.save()
                    logger.info(f"文档内容提取成功: {len(content)} 字符")

            except Exception as e:
                logger.error(f"文档内容提取失败: {e}")

    def destroy(self, request, *args, **kwargs):
        """删除需求文档时同时删除物理文件"""
        document = self.get_object()

        try:
            # 删除物理文件
            if document.file:
                if os.path.exists(document.file.path):
                    os.remove(document.file.path)
                    logger.info(f"已删除文件: {document.file.path}")

            # 删除数据库记录（这会级联删除相关的模块、评审报告等）
            document_title = document.title
            document.delete()

            logger.info(f"需求文档删除成功: {document_title}")
            return Response(status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            logger.error(f"删除需求文档失败: {e}")
            return Response(
                {"error": f"删除失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _get_latest_document_image(self, document, image_id):
        return (
            document.images.filter(image_id=image_id)
            .order_by("-created_at")
            .first()
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="images/(?P<image_id>[^/.]+)",
        authentication_classes=[],
        permission_classes=[],
    )
    def get_image(self, request, pk=None, image_id=None):
        """
        获取文档中的图片（公开访问，无需认证）
        GET /api/requirements/documents/{id}/images/{image_id}/
        """
        from django.http import FileResponse

        try:
            document = RequirementDocument.objects.get(pk=pk)
            image = self._get_latest_document_image(document, image_id)
            if not image:
                return Response({"error": "图片不存在"}, status=status.HTTP_404_NOT_FOUND)
            return FileResponse(
                open(image.image_file.path, "rb"), content_type=image.content_type
            )
        except RequirementDocument.DoesNotExist:
            return Response({"error": "文档不存在"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"获取图片失败: {e}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=["get"], url_path="images-list")
    def list_images(self, request, pk=None):
        """
        获取文档中所有图片的元信息
        GET /api/requirements/documents/{id}/images-list/
        """
        document = self.get_object()
        deduplicated_images = {}
        for image in document.images.all().order_by("order", "-created_at"):
            deduplicated_images.setdefault(image.image_id, image)

        images = list(deduplicated_images.values())
        data = [
            {
                "id": str(img.id),
                "image_id": img.image_id,
                "order": img.order,
                "width": img.width,
                "height": img.height,
                "content_type": img.content_type,
                "file_size": img.file_size,
                "url": f"/api/requirements/documents/{document.id}/images/{img.image_id}/",
            }
            for img in images
        ]
        return Response({"images": data, "total": len(data)})

    @action(detail=True, methods=["get"], url_path="download-file")
    def download_file(self, request, pk=None):
        """
        下载文档原始文件
        GET /api/requirements/documents/{id}/download-file/
        """
        from django.http import FileResponse

        document = self.get_object()
        if not document.file:
            return Response({"error": "该文档没有原始文件"}, status=status.HTTP_404_NOT_FOUND)

        ext = document.document_type or "docx"
        content_type_map = {
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "pdf": "application/pdf",
            "txt": "text/plain",
            "md": "text/markdown",
        }
        content_type = content_type_map.get(ext, "application/octet-stream")
        response = FileResponse(open(document.file.path, "rb"), content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{document.title}.{ext}"'
        return response

    @action(detail=True, methods=["post"], url_path="docx-editor/session")
    @permission_required("requirements.change_requirementdocument")
    def create_docx_editor_session(self, request, pk=None):
        document = self.get_object()

        if document.document_type not in {"doc", "docx"}:
            return Response(
                {"error": "仅 Word 文档支持在线编辑"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not document.file:
            return Response(
                {"error": "该文档没有原始文件，无法发起在线编辑"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pushback_url = reverse(
            "requirement-documents-upload-edited-file",
            kwargs={"pk": document.id},
        )

        try:
            payload = create_docx_editor_session(document, pushback_url=pushback_url)
        except DocxEditorNotConfiguredError as exc:
            logger.error("DOCX Editor not configured for document %s: %s", document.id, exc)
            return Response(
                {"error": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except DocxEditorClientError as exc:
            logger.error("DOCX Editor session creation failed for document %s: %s", document.id, exc)
            return Response(
                {"error": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "iframe_url": payload.get("launch_url"),
                "expires_at": payload.get("expires_at"),
                "document_id": str(document.id),
                "title": document.title,
            }
        )

    @action(detail=True, methods=["post"], url_path="launch-online-editor")
    def launch_online_editor(self, request, pk=None):
        """
        发起 docx-editor 在线编辑
        POST /api/requirements/documents/{id}/launch-online-editor/
        """
        document = self.get_object()

        try:
            launch_payload = launch_requirement_document_in_docx_editor(document)
        except DocxEditorNotConfiguredError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except DocxEditorIntegrationError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as exc:
            logger.exception("发起在线编辑失败")
            return Response(
                {"detail": f"发起在线编辑失败: {str(exc)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "status": "success",
                "code": status.HTTP_200_OK,
                "message": "在线编辑链接已生成",
                "data": launch_payload,
            }
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="upload-edited-file",
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_edited_file(self, request, pk=None):
        """
        接收 docx-editor 回传的编辑结果
        POST /api/requirements/documents/{id}/upload-edited-file/
        """
        document = self.get_object()
        upload = request.FILES.get("file")

        if not upload:
            return Response(
                {"detail": "缺少回传文件，请检查 docx-editor 回调参数。"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            document = replace_requirement_document_with_edited_file(document, upload)
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.exception("同步在线编辑结果失败")
            return Response(
                {"detail": f"同步在线编辑结果失败: {str(exc)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "status": "success",
                "code": status.HTTP_200_OK,
                "message": "编辑稿已同步到主项目",
                "data": {
                    "document_id": str(document.id),
                    "status": document.status,
                    "updated_at": document.updated_at,
                    "word_count": document.word_count,
                    "page_count": document.page_count,
                },
            }
        )

    @action(detail=True, methods=["post"], url_path="split-modules")
    def split_modules(self, request, pk=None):
        """
        智能模块拆分 - 支持多种拆分方式
        POST /api/requirements/documents/{id}/split-modules/

        请求体参数:
        {
            "split_level": "h2",           // h1, h2, h3 或 auto
            "include_context": true,       // 是否包含上级标题作为上下文
            "chunk_size": 2000            // 如果选择auto，按字数拆分的大小
        }
        """
        document = self.get_object()

        if document.status not in ["uploaded", "processing"]:
            return Response(
                {"error": "文档状态不允许进行模块拆分"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # 获取拆分选项
            split_options = {
                "split_level": request.data.get("split_level", "auto"),
                "include_context": request.data.get("include_context", True),
                "chunk_size": request.data.get("chunk_size", 2000),
            }

            logger.info(f"开始拆分文档 {document.id}，选项: {split_options}")

            # 使用模块拆分服务
            module_service = RequirementModuleService(user=request.user)
            modules = module_service.process_document_and_split(document, split_options)

            serializer = RequirementModuleSerializer(modules, many=True)

            # 根据拆分方式生成不同的提示信息
            split_level = split_options["split_level"]
            if split_level == "auto":
                split_method = "按内容长度智能拆分"
            else:
                split_method = f"按{split_level.upper()}级别标题拆分"

            return Response(
                {
                    "message": f"{split_method}完成",
                    "split_options": split_options,
                    "modules": serializer.data,
                    "status": document.status,
                    "total_modules": len(modules),
                    "suggestions": [
                        "请检查模块拆分是否合理",
                        "如果不满意可以选择其他拆分级别重新拆分",
                        "可以手动调整模块边界和内容",
                        "确认无误后可开始评审分析",
                    ],
                }
            )

        except Exception as e:
            logger.error(f"模块拆分失败: {e}")
            return Response(
                {"error": f"模块拆分失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get"], url_path="check-context-limit")
    def check_context_limit(self, request, pk=None):
        """
        检查文档是否超过模型上下文限制
        GET /api/requirements/documents/{id}/check-context-limit/?model=gpt-4
        """
        document = self.get_object()

        # 检查用户是否初始化了所有必需的程序调用提示词
        required_prompt_types = [
            "document_structure",
            "direct_analysis",
            "global_analysis",
            "module_analysis",
            "consistency_analysis",
        ]

        missing_prompts = []
        for p_type in required_prompt_types:
            if not UserPrompt.objects.filter(
                user=request.user, prompt_type=p_type
            ).exists():
                missing_prompts.append(p_type)

        if missing_prompts:
            # 获取提示词类型的中英文映射
            prompt_type_display = dict(UserPrompt.PROMPT_TYPE_CHOICES)

            # 将缺失的提示词类型转换为中文名称
            missing_prompts_display = [
                prompt_type_display.get(pt, pt) for pt in missing_prompts
            ]

            error_message = (
                f"缺少必要的程序调用提示词: {', '.join(missing_prompts_display)}。"
                "请在“提示词管理”页面中，点击“初始化程序调用提示词”按钮来完成配置。"
            )

            return Response(
                {"error": error_message}, status=status.HTTP_400_BAD_REQUEST
            )

        # 如果文档内容为空，尝试提取
        if not document.content and document.file:
            try:
                from .services import DocumentProcessor

                processor = DocumentProcessor()
                content = processor.extract_content(document)

                if content:
                    document.content = content
                    document.word_count = len(content)
                    document.page_count = max(1, (len(content) // 500) + 1)
                    document.save()
                    logger.info(f"文档内容提取成功: {len(content)} 字符")

            except Exception as e:
                logger.error(f"文档内容提取失败: {e}")

        if not document.content:
            return Response(
                {"error": "文档内容为空，请检查文件是否正确上传"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # 获取模型名称
            model_name = request.query_params.get("model", "gpt-3.5-turbo")

            # 检查上下文限制
            context_result = document.check_context_limit(model_name)

            # 如果超出限制，计算最优拆分大小
            if context_result["exceeds_limit"]:
                optimal_size = document.get_optimal_split_size(model_name)
                context_result["optimal_chunk_size"] = optimal_size

            return Response(
                {
                    "document_info": {
                        "title": document.title,
                        "content_length": len(document.content),
                        "word_count": document.word_count,
                        "page_count": document.page_count,
                    },
                    "context_analysis": context_result,
                    "recommendations": self._get_split_recommendations(context_result),
                }
            )

        except Exception as e:
            logger.error(f"上下文检测失败: {e}")
            return Response(
                {"error": f"上下文检测失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _get_split_recommendations(self, context_result: dict) -> list:
        """根据上下文分析结果生成拆分建议"""
        recommendations = []

        if context_result["suggestion"] == "SPLIT_REQUIRED":
            recommendations.extend(
                [
                    "文档超出模型上下文限制，必须进行拆分",
                    "建议使用智能拆分或按标题拆分",
                    f"推荐分块大小: {context_result.get('optimal_chunk_size', 2000)} 字符",
                ]
            )
        elif context_result["suggestion"] == "SPLIT_RECOMMENDED":
            recommendations.extend(
                [
                    "文档接近上下文限制，建议拆分以获得更好的分析效果",
                    "可以选择按H2或H3级别拆分",
                ]
            )
        else:
            recommendations.extend(
                [
                    "文档大小适中，可以直接进行分析",
                    "如需要更细粒度的分析，也可以选择拆分",
                ]
            )

        return recommendations

    @action(detail=True, methods=["put"], url_path="adjust-modules")
    def adjust_modules(self, request, pk=None):
        """
        用户调整模块拆分结果
        PUT /api/requirements/documents/{id}/adjust-modules/
        """
        document = self.get_object()

        if document.status != "user_reviewing":
            return Response(
                {"error": "文档状态不允许调整模块"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ModuleAdjustmentSerializer(data=request.data)
        if serializer.is_valid():
            try:
                # 删除现有模块
                document.modules.all().delete()

                # 创建新模块
                modules_data = serializer.validated_data["modules"]
                modules = []
                for module_data in modules_data:
                    module = RequirementModule.objects.create(
                        document=document, **module_data
                    )
                    modules.append(module)

                # 更新文档状态
                document.status = "ready_for_review"
                document.save()

                response_serializer = RequirementModuleSerializer(modules, many=True)
                return Response(
                    {
                        "message": "模块调整完成",
                        "modules": response_serializer.data,
                        "status": "ready_for_review",
                    }
                )

            except Exception as e:
                logger.error(f"模块调整失败: {e}")
                return Response(
                    {"error": f"模块调整失败: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="confirm-modules")
    def confirm_modules(self, request, pk=None):
        """
        确认模块拆分结果，将状态设置为可评审
        POST /api/requirements/documents/{id}/confirm-modules/
        """
        document = self.get_object()

        if document.status not in ["user_reviewing", "uploaded", "processing"]:
            return Response(
                {"error": f"文档状态 {document.status} 不允许确认模块"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # 检查是否有模块
            modules_count = document.modules.count()
            if modules_count == 0:
                return Response(
                    {"error": "文档还没有模块，请先进行模块拆分"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # 更新文档状态为可评审
            document.status = "ready_for_review"
            document.save()

            return Response(
                {
                    "message": "模块确认完成，文档已准备好进行评审",
                    "status": document.status,
                    "modules_count": modules_count,
                }
            )

        except Exception as e:
            logger.error(f"确认模块失败: {e}")
            return Response(
                {"error": f"确认模块失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(
        detail=True,
        methods=["post"],
        url_path="restart-review",
        permission_classes=[CanStartReview],
    )
    def restart_review(self, request, pk=None):
        """
        重新开始需求评审
        POST /api/requirements/documents/{id}/restart-review/
        """
        document = self.get_object()

        # 允许在"评审完成"或"处理失败"的状态下重新评审
        if document.status not in ["review_completed", "failed"]:
            return Response(
                {"error": f'文档状态 "{document.get_status_display()}" 不允许重新评审'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 清理旧的评审数据
        # 如需清理历史评审报告，可在此启用删除逻辑。
        # logger.info(f"已清理文档 {document.id} 的旧评审报告。")

        # 重置文档状态
        document.status = "ready_for_review"
        document.save()

        # 为了简化，我们直接调用现有的 start_review 方法
        # 这样可以重用所有的逻辑和参数处理
        return self.start_review(request, pk)

    @action(
        detail=True,
        methods=["post"],
        url_path="start-review",
        permission_classes=[CanStartReview],
    )
    def start_review(self, request, pk=None):
        """
        开始需求评审 - 支持直接评审和模块评审（异步处理）
        POST /api/requirements/documents/{id}/start-review/

        参数:
        - direct_review: 是否直接评审整个文档 (默认: false)
        - analysis_type: 分析类型 (默认: comprehensive)
        - parallel_processing: 是否并行处理 (默认: true)
        """
        document = self.get_object()

        # 获取评审类型
        direct_review = request.data.get("direct_review", False)

        # 检查文档状态
        if direct_review:
            # 直接评审：文档有内容即可
            if not document.content:
                return Response(
                    {"error": "文档内容为空，无法进行评审"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # 允许的状态：uploaded, processing, user_reviewing, ready_for_review
            allowed_statuses = [
                "uploaded",
                "processing",
                "user_reviewing",
                "ready_for_review",
            ]
            if document.status not in allowed_statuses:
                return Response(
                    {"error": f"文档状态 {document.status} 不允许直接评审"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            # 模块评审：必须是ready_for_review或failed状态（允许重新评审）
            if document.status not in ["ready_for_review", "failed"]:
                return Response(
                    {"error": "文档状态不允许开始评审，请先完成模块拆分"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # 检查权限
        if not CanStartReview().has_object_permission(request, self, document):
            return Response(
                {"error": "没有权限启动评审"}, status=status.HTTP_403_FORBIDDEN
            )

        try:
            # 准备评审参数
            analysis_options = {
                "analysis_type": request.data.get("analysis_type", "comprehensive"),
                "parallel_processing": request.data.get("parallel_processing", True),
                "priority_modules": request.data.get("priority_modules", []),
                "custom_requirements": request.data.get("custom_requirements", ""),
                "max_workers": request.data.get("max_workers", 3),  # 新增：并发数
                "direct_review": direct_review,
            }

            # 立即更新文档状态为评审中
            document.status = "reviewing"
            document.save()

            # 启动异步评审任务
            from .tasks import execute_requirement_review



            review_type = "direct" if direct_review else "comprehensive"
            task = execute_requirement_review.delay(
                str(document.id),
                analysis_options,
                review_type,
                user_id=request.user.id,  # 传递用户ID用于获取提示词配置
            )

            # 立即返回，不等待任务完成
            return Response(
                {
                    "message": f"评审任务已启动",
                    "task_id": task.id,
                    "review_type": "直接评审" if direct_review else "模块评审",
                    "direct_review": direct_review,
                    "status": "reviewing",
                    "document_id": str(document.id),
                }
            )

        except Exception as e:
            logger.error(f"启动评审失败: {e}")
            return Response(
                {"error": f"启动评审失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"], url_path="module-operations")
    def module_operations(self, request, pk=None):
        """
        模块操作接口 - 支持合并、拆分、重排序等操作
        POST /api/requirements/documents/{id}/module-operations/
        """
        document = self.get_object()

        if document.status not in ["user_reviewing", "ready_for_review"]:
            return Response(
                {"error": "当前文档状态不允许模块操作"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from .serializers import ModuleOperationSerializer, ModuleBatchUpdateSerializer

        # 检查是单个操作还是批量操作
        if "operations" in request.data:
            # 批量操作
            serializer = ModuleBatchUpdateSerializer(data=request.data)
            if serializer.is_valid():
                try:
                    operation_service = ModuleOperationService(document)
                    result = operation_service.execute_batch_operations(
                        serializer.validated_data["operations"]
                    )

                    if result["success"]:
                        # 返回更新后的模块列表
                        modules = document.modules.order_by("order")
                        modules_serializer = RequirementModuleSerializer(
                            modules, many=True
                        )

                        return Response(
                            {
                                "message": result["message"],
                                "operations_count": result["operations_count"],
                                "modules": modules_serializer.data,
                                "status": document.status,
                            }
                        )
                    else:
                        return Response(
                            {"error": result["error"]},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                except Exception as e:
                    logger.error(f"批量模块操作失败: {e}")
                    return Response(
                        {"error": f"操作失败: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        else:
            # 单个操作
            serializer = ModuleOperationSerializer(data=request.data)
            if serializer.is_valid():
                try:
                    operation_service = ModuleOperationService(document)
                    result = operation_service.execute_operation(
                        serializer.validated_data
                    )

                    # 返回更新后的模块列表
                    modules = document.modules.order_by("order")
                    modules_serializer = RequirementModuleSerializer(modules, many=True)

                    return Response(
                        {
                            "message": result["message"],
                            "operation_result": result,
                            "modules": modules_serializer.data,
                            "status": document.status,
                        }
                    )

                except Exception as e:
                    logger.error(f"模块操作失败: {e}")
                    return Response(
                        {"error": f"操作失败: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RequirementModuleViewSet(BaseModelViewSet):
    """需求模块视图集"""

    queryset = RequirementModule.objects.all()
    serializer_class = RequirementModuleSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = RequirementModuleFilter
    search_fields = ["title", "content"]
    ordering_fields = ["order", "created_at", "updated_at"]
    ordering = ["document", "order"]

    def get_permissions(self):
        """返回此视图所需权限的实例列表"""
        # 获取基础权限（用户认证 + Django模型权限）
        base_permissions = super().get_permissions()
        # 在基础权限之上添加项目特定的权限检查
        return base_permissions + [IsProjectMemberForRequirement()]

    def get_queryset(self):
        """只返回用户有权限访问的模块"""
        user = self.request.user
        if user.is_superuser:
            return RequirementModule.objects.all()

        # 普通用户只能看到自己是成员的项目的模块
        return RequirementModule.objects.filter(
            document__project__members__user=user
        ).distinct()


class ReviewReportViewSet(BaseModelViewSet):
    """评审报告视图集"""

    queryset = ReviewReport.objects.all()
    serializer_class = ReviewReportSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = ReviewReportFilter
    search_fields = ["summary", "recommendations"]
    ordering_fields = ["review_date", "completion_score", "total_issues"]
    ordering = ["-review_date"]

    def get_permissions(self):
        """返回此视图所需权限的实例列表"""
        # 获取基础权限（用户认证 + Django模型权限）
        base_permissions = super().get_permissions()
        # 在基础权限之上添加项目特定的权限检查
        return base_permissions + [IsProjectMemberForRequirement()]

    def get_queryset(self):
        """只返回用户有权限访问的评审报告"""
        user = self.request.user
        if user.is_superuser:
            return ReviewReport.objects.all()

        # 普通用户只能看到自己是成员的项目的评审报告
        return ReviewReport.objects.filter(
            document__project__members__user=user
        ).distinct()


class ReviewIssueViewSet(BaseModelViewSet):
    """评审问题视图集"""

    queryset = ReviewIssue.objects.all()
    serializer_class = ReviewIssueSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = ReviewIssueFilter
    search_fields = ["title", "description", "suggestion"]
    ordering_fields = ["priority", "created_at", "page_number"]
    ordering = ["priority", "-created_at"]

    def get_permissions(self):
        """返回此视图所需权限的实例列表"""
        # 获取基础权限（用户认证 + Django模型权限）
        base_permissions = super().get_permissions()
        # 在基础权限之上添加项目特定的权限检查
        return base_permissions + [IsProjectMemberForRequirement()]

    def get_queryset(self):
        """只返回用户有权限访问的评审问题"""
        user = self.request.user
        if user.is_superuser:
            return ReviewIssue.objects.all()

        # 普通用户只能看到自己是成员的项目的评审问题
        return ReviewIssue.objects.filter(
            report__document__project__members__user=user
        ).distinct()



class ModuleReviewResultViewSet(BaseModelViewSet):
    """模块评审结果视图集"""

    queryset = ModuleReviewResult.objects.all()
    serializer_class = ModuleReviewResultSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = ModuleReviewResultFilter
    search_fields = ["analysis_content", "strengths", "weaknesses", "recommendations"]
    ordering_fields = ["module__order", "issues_count", "severity_score"]
    ordering = ["module__order"]

    def get_permissions(self):
        """返回此视图所需权限的实例列表"""
        # 获取基础权限（用户认证 + Django模型权限）
        base_permissions = super().get_permissions()
        # 在基础权限之上添加项目特定的权限检查
        return base_permissions + [IsProjectMemberForRequirement()]

    def get_queryset(self):
        """只返回用户有权限访问的模块评审结果"""
        user = self.request.user
        if user.is_superuser:
            return ModuleReviewResult.objects.all()

        # 普通用户只能看到自己是成员的项目的模块评审结果
        return ModuleReviewResult.objects.filter(
            report__document__project__members__user=user
        ).distinct()
