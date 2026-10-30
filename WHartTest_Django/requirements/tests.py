import os
import tempfile
import time
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import Permission, User
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings

try:
    # PE 线存在 LicenseCheckMiddleware，API 测试需 patch 掉授权拦截；
    # CE 开源线无此中间件，探测定为 False 后相关 patch 自动跳过。
    from license_control.middleware import LicenseCheckMiddleware  # noqa: F401

    _HAS_LICENSE_MIDDLEWARE = True
except ImportError:
    _HAS_LICENSE_MIDDLEWARE = False
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from api_keys.models import APIKey
from projects.models import Project, ProjectMember

from .docx_editor_client import DocxEditorClientError, create_docx_editor_session
from .models import DocumentImage, RequirementDocument, RequirementModule, ReviewReport
from .services import DocumentProcessor


class DocxEditorSessionActionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.override_media = override_settings(MEDIA_ROOT=self.temp_dir.name)
        self.override_media.enable()
        self.addCleanup(self.override_media.disable)

        self.user = User.objects.create_user(username="tester", password="password123")
        change_perm = Permission.objects.get(codename="change_requirementdocument")
        self.user.user_permissions.add(change_perm)

        self.project = Project.objects.create(name="Demo Project", creator=self.user)
        ProjectMember.objects.create(project=self.project, user=self.user, role="member")
        self.client.force_authenticate(self.user)

        self.document = RequirementDocument.objects.create(
            project=self.project,
            title="Word Requirement",
            document_type="docx",
            file=SimpleUploadedFile(
                "requirement.docx",
                b"word-content",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            uploader=self.user,
        )
        self.url = reverse(
            "requirement-documents-create-docx-editor-session",
            kwargs={"pk": self.document.id},
        )

    def test_returns_iframe_url_for_word_document(self):
        with patch("requirements.views.create_docx_editor_session") as create_session:
            create_session.return_value = {
                "launch_url": "http://docx.example/embed/binding-1?token=abc",
                "expires_at": "2026-04-03T12:00:00Z",
            }
            response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["iframe_url"],
            "http://docx.example/embed/binding-1?token=abc",
        )
        self.assertEqual(response.data["document_id"], str(self.document.id))
        self.assertEqual(
            create_session.call_args.kwargs["pushback_url"],
            f"/api/requirements/documents/{self.document.id}/upload-edited-file/",
        )

    def test_rejects_non_word_documents(self):
        self.document.document_type = "pdf"
        self.document.file = SimpleUploadedFile(
            "requirement.pdf",
            b"pdf",
            content_type="application/pdf",
        )
        self.document.save(update_fields=["document_type", "file"])

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 400)
        self.assertIn("仅 Word 文档支持在线编辑", response.data["error"])


class DocxEditorClientTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.override_media = override_settings(MEDIA_ROOT=self.temp_dir.name)
        self.override_media.enable()
        self.addCleanup(self.override_media.disable)

        self.user = User.objects.create_user(
            username="docx-client",
            password="password123",
        )
        self.project = Project.objects.create(
            name="Docx Client Project",
            creator=self.user,
        )
        ProjectMember.objects.create(project=self.project, user=self.user, role="member")
        self.document = RequirementDocument.objects.create(
            project=self.project,
            title="Word Requirement",
            document_type="docx",
            file=SimpleUploadedFile(
                "requirement.docx",
                b"word-content",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            uploader=self.user,
        )

    @override_settings(
        DOCX_EDITOR_BASE_URL="http://docx-editor.internal:18080",
        DOCX_EDITOR_PUBLIC_BASE_URL="https://docx.example.com",
        DOCX_EDITOR_SERVICE_KEY="service-key",
    )
    @patch("requirements.docx_editor_client.requests.post")
    def test_sends_public_base_url_header_when_configured(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "launch_url": "https://docx.example.com/embed/binding-1?token=abc",
        }

        payload = create_docx_editor_session(
            self.document,
            pushback_url=f"/api/requirements/documents/{self.document.id}/upload-edited-file/",
        )

        self.assertEqual(
            mock_post.call_args.kwargs["headers"]["X-Docx-Editor-Public-Base-Url"],
            "https://docx.example.com",
        )
        self.assertEqual(
            mock_post.call_args.kwargs["headers"]["Authorization"],
            "Bearer service-key",
        )
        self.assertEqual(
            payload["launch_url"],
            "https://docx.example.com/embed/binding-1?token=abc",
        )

    @override_settings(
        DOCX_EDITOR_BASE_URL="http://docx-editor.internal:18080",
        DOCX_EDITOR_PUBLIC_BASE_URL="https://docx.example.com",
        DOCX_EDITOR_SERVICE_KEY="service-key",
    )
    def test_rejects_missing_source_file_before_upload(self):
        default_storage.delete(self.document.file.name)

        with self.assertRaisesMessage(
            DocxEditorClientError,
            "主项目中的源文件不存在，请重新上传该文档后再试。",
        ):
            create_docx_editor_session(
                self.document,
                pushback_url=f"/api/requirements/documents/{self.document.id}/upload-edited-file/",
            )


class RequirementDocumentDocxEditorTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.override_media = override_settings(MEDIA_ROOT=self.temp_dir.name)
        self.override_media.enable()
        self.addCleanup(self.override_media.disable)

        self.superuser = User.objects.create_superuser(
            username="docx-admin",
            email="docx@example.com",
            password="Secret123!",
        )
        self.api_key = APIKey.objects.create(
            user=self.superuser,
            name="docx-editor-test-key",
            key="docx-editor-test-key",
            is_active=True,
        )
        self.project = Project.objects.create(
            name="docx-editor-project",
            description="demo",
            creator=self.superuser,
        )
        self.document = RequirementDocument.objects.create(
            project=self.project,
            title="需求文档",
            document_type="docx",
            file=SimpleUploadedFile(
                "requirement.docx",
                b"old file body",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            content="旧内容",
            status="ready_for_review",
            uploader=self.superuser,
        )
        self.detail_base = f"/api/requirements/documents/{self.document.id}"

    def test_launch_online_editor_returns_not_integrated_when_config_missing(self):
        self.client.force_authenticate(self.superuser)

        with override_settings(DOCX_EDITOR_BASE_URL="", DOCX_EDITOR_SERVICE_KEY=""):
            response = self.client.post(f"{self.detail_base}/launch-online-editor/")

        payload = response.json()
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(
            payload.get("message") or payload.get("detail"),
            "在线编辑功能未接入，请先在主项目后端配置 DOCX_EDITOR_BASE_URL 和 DOCX_EDITOR_SERVICE_KEY。",
        )

    @override_settings(
        DOCX_EDITOR_BASE_URL="http://127.0.0.1:18080",
        DOCX_EDITOR_PUBLIC_BASE_URL="http://172.16.3.183:18080",
        DOCX_EDITOR_SERVICE_KEY="integration-key",
    )
    @patch("requirements.docx_editor_integration.requests.post")
    def test_launch_online_editor_calls_docx_editor(self, post_mock):
        self.client.force_authenticate(self.superuser)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "launch_url": "http://172.16.3.183:18080/embed/binding-1?token=test-token",
            "bindingId": "binding-1",
            "documentId": "remote-doc-1",
        }
        post_mock.return_value = mock_response

        response = self.client.post(f"{self.detail_base}/launch-online-editor/")

        payload = response.json()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            payload["data"]["launch_url"],
            "http://172.16.3.183:18080/embed/binding-1?token=test-token",
        )

        _, kwargs = post_mock.call_args
        self.assertEqual(
            kwargs["headers"]["Authorization"],
            "Bearer integration-key",
        )
        self.assertEqual(
            kwargs["headers"]["X-Docx-Editor-Public-Base-Url"],
            "http://172.16.3.183:18080",
        )
        self.assertEqual(
            kwargs["data"]["pushback_url"],
            f"/api/requirements/documents/{self.document.id}/upload-edited-file/",
        )

    @override_settings(
        DOCX_EDITOR_BASE_URL="http://127.0.0.1:18080",
        DOCX_EDITOR_PUBLIC_BASE_URL="http://172.16.3.183:18080",
        DOCX_EDITOR_SERVICE_KEY="integration-key",
    )
    def test_launch_online_editor_rejects_missing_source_file(self):
        self.client.force_authenticate(self.superuser)
        default_storage.delete(self.document.file.name)

        response = self.client.post(f"{self.detail_base}/launch-online-editor/")

        payload = response.json()
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(
            payload.get("detail")
            or payload.get("error")
            or ((payload.get("errors") or {}).get("detail")),
            "主项目中的源文件不存在，可能已被删除或丢失，请重新上传该文档后再试。",
        )

    @patch("requirements.docx_editor_integration.DocumentProcessor")
    def test_upload_edited_file_replaces_document_and_resets_review_state(
        self,
        processor_cls,
    ):
        RequirementModule.objects.create(
            document=self.document,
            title="模块1",
            content="旧模块内容",
            order=1,
        )
        ReviewReport.objects.create(
            document=self.document,
            status="completed",
            summary="旧报告",
        )

        mock_processor = processor_cls.return_value
        mock_processor.extract_content.return_value = "更新后的原始内容"
        mock_processor.preprocess_content.return_value = "更新后的处理内容"

        response = self.client.post(
            f"{self.detail_base}/upload-edited-file/",
            data={
                "file": SimpleUploadedFile(
                    "updated.docx",
                    b"new file body",
                    content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            format="multipart",
            HTTP_X_API_KEY=self.api_key.key,
        )

        payload = response.json()
        self.document.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(payload["data"]["status"], "uploaded")
        self.assertEqual(self.document.status, "uploaded")
        self.assertEqual(self.document.content, "更新后的处理内容")
        self.assertEqual(self.document.modules.count(), 0)
        self.assertEqual(self.document.review_reports.count(), 0)
        self.assertTrue(self.document.file.name.endswith("updated.docx"))
        mock_processor.extract_content.assert_called_once()
        mock_processor.preprocess_content.assert_called_once_with("更新后的原始内容")


class DocumentProcessorImageCleanupTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.override_media = override_settings(MEDIA_ROOT=self.temp_dir.name)
        self.override_media.enable()
        self.addCleanup(self.override_media.disable)

        self.user = User.objects.create_user(
            username="image-cleaner",
            password="password123",
        )
        self.project = Project.objects.create(
            name="Image Project",
            creator=self.user,
        )
        ProjectMember.objects.create(project=self.project, user=self.user, role="member")
        self.document = RequirementDocument.objects.create(
            project=self.project,
            title="Image Requirement",
            document_type="docx",
            uploader=self.user,
            has_images=True,
            image_count=2,
        )

    def test_clear_document_images_removes_existing_records_and_resets_stats(self):
        image_one = DocumentImage.objects.create(
            document=self.document,
            image_id="img_000",
            order=0,
            content_type="image/png",
            file_size=3,
            image_file=SimpleUploadedFile(
                "img-000.png",
                b"one",
                content_type="image/png",
            ),
        )
        image_two = DocumentImage.objects.create(
            document=self.document,
            image_id="img_001",
            order=1,
            content_type="image/png",
            file_size=3,
            image_file=SimpleUploadedFile(
                "img-001.png",
                b"two",
                content_type="image/png",
            ),
        )
        image_one_path = image_one.image_file.path
        image_two_path = image_two.image_file.path

        processor = DocumentProcessor()
        processor._clear_document_images(self.document)
        self.document.refresh_from_db()

        self.assertFalse(DocumentImage.objects.filter(document=self.document).exists())
        self.assertFalse(self.document.has_images)
        self.assertEqual(self.document.image_count, 0)
        self.assertFalse(os.path.exists(image_one_path))
        self.assertFalse(os.path.exists(image_two_path))

    def test_append_image_placeholder_skips_consecutive_duplicate_rids(self):
        processor = DocumentProcessor()
        content_parts = []
        image_rids = []
        image_order = 0

        image_order = processor._append_image_placeholder(
            content_parts,
            image_rids,
            "rId10",
            image_order,
        )
        image_order = processor._append_image_placeholder(
            content_parts,
            image_rids,
            "rId10",
            image_order,
        )
        image_order = processor._append_image_placeholder(
            content_parts,
            image_rids,
            "rId11",
            image_order,
        )

        self.assertEqual(image_order, 2)
        self.assertEqual(image_rids, ["rId10", "rId11"])
        self.assertEqual(
            content_parts,
            [
                "\n![图片](docimg://img_000)\n",
                "\n![图片](docimg://img_001)\n",
            ],
        )


class RequirementDocumentImageAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.override_media = override_settings(MEDIA_ROOT=self.temp_dir.name)
        self.override_media.enable()
        self.addCleanup(self.override_media.disable)

        self.user = User.objects.create_user(
            username="image-viewer",
            password="password123",
        )
        self.project = Project.objects.create(
            name="Image Access Project",
            creator=self.user,
        )
        ProjectMember.objects.create(project=self.project, user=self.user, role="member")
        self.document = RequirementDocument.objects.create(
            project=self.project,
            title="Image Access Requirement",
            document_type="docx",
            uploader=self.user,
            has_images=True,
            image_count=1,
        )

    def test_get_image_returns_latest_duplicate_record(self):
        DocumentImage.objects.create(
            document=self.document,
            image_id="img_000",
            order=0,
            content_type="image/png",
            file_size=3,
            image_file=SimpleUploadedFile(
                "old.png",
                b"old",
                content_type="image/png",
            ),
        )
        time.sleep(0.02)
        DocumentImage.objects.create(
            document=self.document,
            image_id="img_000",
            order=0,
            content_type="image/png",
            file_size=3,
            image_file=SimpleUploadedFile(
                "new.png",
                b"new",
                content_type="image/png",
            ),
        )

        url = reverse(
            "requirement-documents-get-image",
            kwargs={"pk": self.document.id, "image_id": "img_000"},
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"new")


class ReviewFailureHonestyTests(TestCase):
    """回归测试：评审失败必须显式暴露，禁止用 70 分兜底伪造结果。

    背景（2026-10-29 真实事故，文档 81d55b9e）：LLM 调用持续报错时，
    旧逻辑把每个失败的专项分析替换成 overall_score=70 的"默认结果"，
    六项全失败仍产出一份看似正常的 70 分报告，用户完全无法感知失败。
    新契约：单项失败返回 status=failed + 原因 + 评分 None；
    全部失败则整个评审置为 failed 并记录原因。
    """

    def setUp(self):
        self.user = User.objects.create_user(username="reviewer", password="password123")
        self.project = Project.objects.create(name="Review Project", creator=self.user)
        self.document = RequirementDocument.objects.create(
            project=self.project,
            title="Review Target",
            document_type="md",
            content="# 需求\n\n## 功能\n描述",
            status="ready_for_review",
            uploader=self.user,
        )

    def _engine(self):
        """构造评审引擎：测试库没有 LLM 配置，打桩绕过配置解析"""
        from .services import RequirementReviewEngine

        with patch("requirements.services.resolve_llm_config") as mock_resolve, patch(
            "requirements.services.create_llm_instance"
        ) as mock_create:
            mock_resolve.return_value = MagicMock(runtime_config=MagicMock(supports_vision=False))
            mock_create.return_value = MagicMock()
            return RequirementReviewEngine(user=self.user)

    def _service(self):
        from .services import RequirementReviewService

        with patch("requirements.services.resolve_llm_config") as mock_resolve, patch(
            "requirements.services.create_llm_instance"
        ) as mock_create:
            mock_resolve.return_value = MagicMock(runtime_config=MagicMock(supports_vision=False))
            mock_create.return_value = MagicMock()
            return RequirementReviewService(user=self.user)

    # -- 单项分析失败：显式失败结果，不再伪造 70 分 -------------------------

    def test_missing_prompt_returns_failed_result_not_fake_score(self):
        engine = self._engine()
        # 用户未配置提示词
        with patch.object(engine, "_get_user_prompt", return_value=None):
            result = engine.analyze_completeness("需求内容", self.document)

        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["overall_score"])
        self.assertIn("提示词", result["error_message"])
        self.assertEqual(result["issues"], [])

    def test_llm_exception_returns_failed_result_with_reason(self):
        engine = self._engine()
        with patch.object(engine, "_get_user_prompt", return_value="分析 {document}"), patch(
            "requirements.services.safe_llm_invoke", side_effect=RuntimeError("API 502")
        ):
            result = engine.analyze_completeness("需求内容", self.document)

        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["overall_score"])
        self.assertIn("API 502", result["error_message"])

    def test_invalid_json_response_returns_failed_result(self):
        engine = self._engine()
        response = MagicMock()
        response.content = "这不是 JSON"
        with patch.object(engine, "_get_user_prompt", return_value="分析 {document}"), patch(
            "requirements.services.safe_llm_invoke", return_value=response
        ):
            result = engine.analyze_completeness("需求内容", self.document)

        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["overall_score"])
        self.assertIn("JSON", result["error_message"])

    # -- 全部失败：评审整体置为 failed 并记录原因 ---------------------------

    def test_all_analyses_failed_fails_review_with_reason(self):
        service = self._service()
        engine = service.review_engine
        with patch.object(engine, "_get_user_prompt", return_value="分析 {document}"), patch(
            "requirements.services.safe_llm_invoke", side_effect=RuntimeError("API 502")
        ):
            with self.assertRaises(ValueError) as ctx:
                service.start_comprehensive_review(self.document)

        self.assertIn("所有专项分析均失败", str(ctx.exception))
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "failed")
        self.assertIn("API 502", self.document.error_message)

        report = self.document.review_reports.order_by("-review_date").first()
        self.assertEqual(report.status, "failed")
        self.assertIn("API 502", report.error_message)
        # 失败报告不保留任何评分，避免 default=0 被当成真实评分展示
        self.assertIsNone(report.completion_score)
        self.assertIsNone(report.completeness_score)
        self.assertIsNone(report.logic_score)

    # -- 部分失败：失败维度为 None、不计入均分、报告如实标注 -----------------

    def test_partial_failure_keeps_null_score_and_excludes_from_average(self):
        service = self._service()
        engine = service.review_engine
        success = {"overall_score": 90, "summary": "完整性良好", "issues": []}
        with patch.object(engine, "analyze_completeness", return_value=success), patch.object(
            engine, "_get_user_prompt", return_value=None
        ):
            report = service.start_comprehensive_review(self.document)

        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "review_completed")
        self.assertEqual(self.document.error_message, "")

        self.assertEqual(report.status, "completed")
        self.assertEqual(report.completion_score, 90)  # 只按成功维度求平均
        self.assertEqual(report.completeness_score, 90)
        # 失败维度保持 None，不再用 70/0 伪造
        self.assertIsNone(report.consistency_score)
        self.assertIsNone(report.testability_score)
        self.assertIsNone(report.feasibility_score)
        self.assertIsNone(report.clarity_score)
        self.assertIsNone(report.logic_score)

        analyses = report.specialized_analyses
        self.assertEqual(analyses["completeness_analysis"]["overall_score"], 90)
        self.assertEqual(analyses["consistency_analysis"]["status"], "failed")
        self.assertIn("提示词", analyses["consistency_analysis"]["error_message"])
        self.assertIn("失败", report.summary)

    # -- 直接评审失败：文档置为 failed 并记录原因 ---------------------------

    def test_direct_review_failure_marks_document_failed(self):
        service = self._service()
        engine = service.review_engine
        with patch.object(engine, "_get_user_prompt", return_value="评审 {content}"), patch(
            "requirements.services.safe_llm_invoke", side_effect=RuntimeError("quota exceeded")
        ):
            with self.assertRaises(RuntimeError):
                service.start_direct_review(self.document)

        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "failed")
        self.assertIn("quota exceeded", self.document.error_message)
        report = self.document.review_reports.order_by("-review_date").first()
        self.assertEqual(report.status, "failed")
        self.assertIn("quota exceeded", report.error_message)

    # -- Celery 任务失败兜底：文档置为 failed 并记录原因 ---------------------

    def test_task_failure_records_error_message(self):
        from .tasks import execute_requirement_review

        self.document.status = "reviewing"
        self.document.save()

        with patch("requirements.services.RequirementReviewService") as mock_service_cls:
            mock_service_cls.return_value.start_comprehensive_review.side_effect = (
                RuntimeError("worker crashed")
            )
            result = execute_requirement_review.run(
                str(self.document.id), {}, "comprehensive", user_id=self.user.id
            )

        self.assertEqual(result["status"], "error")
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "failed")
        self.assertIn("worker crashed", self.document.error_message)

    # -- 序列化契约：error_message 暴露给前端，null 评分如实返回 -------------

    def test_serializers_expose_error_message_and_null_scores(self):
        from .serializers import (
            RequirementDocumentDetailSerializer,
            ReviewReportSerializer,
        )

        self.document.status = "failed"
        self.document.error_message = "配置缺失"
        self.document.save()
        report = ReviewReport.objects.create(
            document=self.document,
            status="failed",
            error_message="所有专项分析均失败",
            consistency_score=None,
            completeness_score=None,
        )

        doc_data = RequirementDocumentDetailSerializer(self.document).data
        self.assertEqual(doc_data["error_message"], "配置缺失")

        report_data = ReviewReportSerializer(report).data
        self.assertEqual(report_data["error_message"], "所有专项分析均失败")
        self.assertIsNone(report_data["scores"]["consistency"])
        self.assertIsNone(report_data["specialized_analyses"]["consistency_analysis"]["overall_score"])
        self.assertIn("未评估", report_data["specialized_analyses"]["consistency_analysis"]["summary"])


class ReviewErrorMessageSanitizationTests(SimpleTestCase):
    """error_message 会直达前端，凭证类信息必须脱敏"""

    def test_masks_api_tokens_and_bearer_credentials(self):
        from .services import sanitize_error_message

        raw = (
            "Error code: 401 - {'error': {'message': 'Incorrect API key sk-abc123XYZdef456 "
            "provided', Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9}}"
        )
        sanitized = sanitize_error_message(raw)
        self.assertNotIn("sk-abc123XYZdef456", sanitized)
        self.assertNotIn("eyJhbGciOiJI", sanitized)
        self.assertIn("sk-***", sanitized)

    def test_masks_url_credentials_and_query_tokens(self):
        from .services import sanitize_error_message

        raw = (
            "request to https://user:secret123@llm.internal:8080/v1/chat failed, "
            "detail: https://api.example.com/v1?key=topsecretvalue99 timeout"
        )
        sanitized = sanitize_error_message(raw)
        self.assertNotIn("secret123", sanitized)
        self.assertNotIn("topsecretvalue99", sanitized)

    def test_keeps_normal_error_text(self):
        from .services import sanitize_error_message

        raw = "文档状态 uploaded 不允许开始评审"
        self.assertEqual(sanitize_error_message(raw), raw)


class ReviewDispatchFailureTests(TestCase):
    """start-review 派发失败时文档必须立即标记失败，不能停在 reviewing 盲等"""

    def setUp(self):
        # 本机 .env 显式配置 SECRET_KEY 时，LicenseCheckMiddleware 会拦截所有
        # API 请求（测试库无许可记录）。本测试关注派发失败状态机，跳过授权校验。
        # CE 适配：开源线无该中间件时无需 patch。
        if _HAS_LICENSE_MIDDLEWARE:
            self._license_patch = patch(
                "license_control.middleware.LicenseCheckMiddleware._verify_with_cache",
                return_value="OK",
            )
            self._license_patch.start()
            self.addCleanup(self._license_patch.stop)

        self.client = APIClient()
        self.user = User.objects.create_user(username="dispatcher", password="password123")
        add_report = Permission.objects.get(codename="add_reviewreport")
        add_doc = Permission.objects.get(codename="add_requirementdocument")
        self.user.user_permissions.add(add_report, add_doc)
        self.project = Project.objects.create(name="Dispatch Project", creator=self.user)
        ProjectMember.objects.create(project=self.project, user=self.user, role="member")
        self.client.force_authenticate(self.user)
        self.document = RequirementDocument.objects.create(
            project=self.project,
            title="Dispatch Target",
            document_type="md",
            content="# 需求\n## 功能\n描述",
            status="ready_for_review",
            uploader=self.user,
        )
        self.url = reverse(
            "requirement-documents-start-review", kwargs={"pk": self.document.id}
        )

    @patch("requirements.views.resolve_llm_config")
    @patch("requirements.tasks.execute_requirement_review")
    def test_dispatch_failure_marks_document_failed_with_reason(
        self, mock_task, mock_resolve
    ):
        mock_resolve.return_value = MagicMock(bundle=MagicMock(id=6), source="test")
        mock_task.delay.side_effect = ConnectionError("broker unreachable")

        response = self.client.post(self.url, {})

        self.assertEqual(response.status_code, 500)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "failed")
        self.assertIn("派发失败", self.document.error_message)
        self.assertIn("broker unreachable", self.document.error_message)

    def test_direct_review_failure_before_report_creation_leaves_no_report(self):
        from .services import RequirementReviewService

        with patch("requirements.services.resolve_llm_config") as mock_resolve, patch(
            "requirements.services.create_llm_instance"
        ) as mock_create:
            mock_resolve.return_value = MagicMock(
                runtime_config=MagicMock(supports_vision=False)
            )
            mock_create.return_value = MagicMock()
            service = RequirementReviewService(user=self.user)

        # 文档内容为空：报告创建前即抛出，不应留下任何报告记录
        self.document.content = ""
        self.document.save()
        with self.assertRaises(ValueError):
            service.start_direct_review(self.document)

        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "failed")
        self.assertIn("文档内容为空", self.document.error_message)
        self.assertEqual(self.document.review_reports.count(), 0)

    def test_direct_review_failure_after_report_creation_marks_report_failed(self):
        from .services import RequirementReviewService

        with patch("requirements.services.resolve_llm_config") as mock_resolve, patch(
            "requirements.services.create_llm_instance"
        ) as mock_create:
            mock_resolve.return_value = MagicMock(
                runtime_config=MagicMock(supports_vision=False)
            )
            mock_create.return_value = MagicMock()
            service = RequirementReviewService(user=self.user)

        # 未配置直接分析提示词：报告已创建，失败后报告必须标记 failed 且评分为 None
        with patch.object(service.review_engine, "_get_user_prompt", return_value=None):
            with self.assertRaises(ValueError):
                service.start_direct_review(self.document)

        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "failed")
        self.assertIn("提示词", self.document.error_message)
        report = self.document.review_reports.order_by("-review_date").first()
        self.assertEqual(report.status, "failed")
        self.assertIn("提示词", report.error_message)
        self.assertIsNone(report.completion_score)


class ReviewEngineStreamingTests(TestCase):
    """评审引擎应按槽位 enable_streaming 配置启用底层流式接收。

    背景：大文档评审经 newapi 网关（nginx）长生成超时返回 504，
    流式接收可避免网关空闲超时；槽位默认开启。
    """

    def _resolve_mock(self, enable_streaming=True):
        from unittest.mock import MagicMock

        runtime = MagicMock(
            provider="openai_compatible",
            name="glm-5.3-flash",
            api_url="http://gw.example.com/v1",
            api_key="test-key",
            supports_vision=False,
            enable_streaming=enable_streaming,
        )
        resolution = MagicMock(runtime_config=runtime)
        return resolution

    @patch("requirements.services.resolve_llm_config")
    @patch("requirements.services.create_llm_instance")
    def test_review_engine_passes_streaming_from_slot(self, mock_create, mock_resolve):
        from .services import RequirementReviewEngine

        mock_resolve.return_value = self._resolve_mock(enable_streaming=True)
        RequirementReviewEngine(user=None)
        mock_create.assert_called_once()
        self.assertTrue(mock_create.call_args.kwargs.get("streaming"))

    @patch("requirements.services.resolve_llm_config")
    @patch("requirements.services.create_llm_instance")
    def test_review_engine_respects_streaming_disabled_slot(self, mock_create, mock_resolve):
        from .services import RequirementReviewEngine

        mock_resolve.return_value = self._resolve_mock(enable_streaming=False)
        RequirementReviewEngine(user=None)
        self.assertFalse(mock_create.call_args.kwargs.get("streaming"))

    @patch("requirements.services.resolve_llm_config")
    @patch("requirements.services.create_llm_instance")
    def test_module_splitter_passes_streaming_from_slot(self, mock_create, mock_resolve):
        from .services import ModuleSplitter

        mock_resolve.return_value = self._resolve_mock(enable_streaming=True)
        ModuleSplitter(user=None)
        mock_create.assert_called_once()
        self.assertTrue(mock_create.call_args.kwargs.get("streaming"))


class LocalLLMWrapperStreamingTests(SimpleTestCase):
    """services.create_llm_instance 必须接受 streaming 参数并落到 ChatOpenAI 构造。

    回归背景：2026-10-29 验证评审时，调用方已传 streaming=True 而本地工厂
    签名未接受该参数，导致评审任务瞬间失败（unexpected keyword argument）。

    CE 适配：CE 线无 wharttest_core 加密核心，本地工厂直接构造 ChatOpenAI，
    故断言 streaming 进入 ChatOpenAI 构造参数（PE 线测的是透传给加密工厂）。
    """

    @patch("requirements.services.ChatOpenAI")
    def test_wrapper_forwards_streaming_true(self, mock_chat):
        from .services import create_llm_instance

        cfg = MagicMock(name="reg-model", api_key="k", api_url="http://reg")
        create_llm_instance(cfg, temperature=0.1, streaming=True)

        self.assertIs(mock_chat.call_args.kwargs.get("streaming"), True)

    @patch("requirements.services.ChatOpenAI")
    def test_wrapper_keeps_streaming_default_false(self, mock_chat):
        from .services import create_llm_instance

        cfg = MagicMock(name="reg-model", api_key="k", api_url="http://reg")
        create_llm_instance(cfg, temperature=0.2)

        self.assertIs(mock_chat.call_args.kwargs.get("streaming"), False)


class DimensionRetryTests(TestCase):
    """单维度重试：原位更新报告，不推翻其余维度的既有结果"""

    def setUp(self):
        self.user = User.objects.create_user(username="retrier", password="password123")
        self.project = Project.objects.create(name="Retry Project", creator=self.user)
        self.document = RequirementDocument.objects.create(
            project=self.project,
            title="Retry Target",
            document_type="md",
            content="# 需求\n## 功能\n描述",
            status="ready_for_review",
            uploader=self.user,
        )

    def _service(self):
        from .services import RequirementReviewService

        with patch("requirements.services.resolve_llm_config") as mock_resolve, patch(
            "requirements.services.create_llm_instance"
        ) as mock_create:
            mock_resolve.return_value = MagicMock(
                runtime_config=MagicMock(supports_vision=False)
            )
            mock_create.return_value = MagicMock()
            return RequirementReviewService(user=self.user)

    def _success(self, score, issues=None):
        return {
            "overall_score": score,
            "summary": "分析正常",
            "issues": issues if issues is not None else [
                {"title": "样例问题", "description": "描述", "priority": "high"}
            ],
            "recommendations": [],
        }

    def _report_with_failed_clarity(self):
        """构造五维成功(80) + 清晰度失败的已完成报告"""
        service = self._service()
        engine = service.review_engine
        patches = [
            patch.object(engine, "analyze_completeness", return_value=self._success(80)),
            patch.object(engine, "analyze_consistency", return_value=self._success(80)),
            patch.object(engine, "analyze_testability", return_value=self._success(80)),
            patch.object(engine, "analyze_feasibility", return_value=self._success(80)),
            patch.object(engine, "analyze_logic", return_value=self._success(80)),
            patch.object(engine, "_get_user_prompt", return_value=None),
        ]
        for p in patches:
            p.start()
        try:
            report = service.start_comprehensive_review(self.document)
        finally:
            for p in patches:
                p.stop()
        return service, report

    def test_retry_updates_report_in_place(self):
        service, report = self._report_with_failed_clarity()
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "review_completed")
        self.assertIsNone(report.clarity_score)
        self.assertEqual(report.completion_score, 80)
        old_report_id = report.id

        engine = service.review_engine
        with patch.object(
            engine,
            "analyze_clarity",
            return_value=self._success(90, issues=[
                {"title": "清晰度问题1", "description": "d", "priority": "medium"},
                {"title": "清晰度问题2", "description": "d", "priority": "low"},
            ]),
        ):
            updated = service.retry_dimension_analysis(self.document, "clarity")

        self.assertEqual(updated.id, old_report_id)  # 原位更新而非新建报告
        self.assertEqual(updated.status, "completed")
        self.assertEqual(updated.clarity_score, 90)
        self.assertEqual(updated.completion_score, 81)  # (80*5+90)/6
        self.assertNotIn("失败", updated.summary)
        self.assertNotEqual(
            (updated.specialized_analyses["clarity_analysis"] or {}).get("status"),
            "failed",
        )
        # 问题记录整体重建: 5 维各 1 条 + 清晰度 2 条
        self.assertEqual(updated.issues.count(), 7)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "review_completed")
        self.assertEqual(self.document.error_message, "")

    def test_retry_failing_again_keeps_failed_dimension_honest(self):
        service, report = self._report_with_failed_clarity()
        engine = service.review_engine
        with patch.object(
            engine,
            "analyze_clarity",
            return_value=engine._failed_analysis_result(
                "clarity_analysis", "重试仍然失败"
            ),
        ):
            updated = service.retry_dimension_analysis(self.document, "clarity")

        self.assertEqual(updated.status, "completed")
        self.assertIsNone(updated.clarity_score)
        self.assertEqual(updated.completion_score, 80)  # 仍按五维平均
        self.assertIn("失败", updated.summary)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "review_completed")

    def test_retry_guards(self):
        service, _ = self._report_with_failed_clarity()
        with self.assertRaises(ValueError):
            service.retry_dimension_analysis(self.document, "not_a_dimension")

        no_report_doc = RequirementDocument.objects.create(
            project=self.project, title="无报告", document_type="md",
            content="# x", status="ready_for_review", uploader=self.user,
        )
        with self.assertRaises(ValueError):
            service.retry_dimension_analysis(no_report_doc, "clarity")

    def test_retry_task_restores_status_on_crash(self):
        from .tasks import retry_dimension_analysis

        service, report = self._report_with_failed_clarity()
        self.document.refresh_from_db()
        self.document.status = "reviewing"
        self.document.save()

        with patch("requirements.services.RequirementReviewService") as mock_cls:
            mock_cls.return_value.retry_dimension_analysis.side_effect = RuntimeError(
                "boom"
            )
            result = retry_dimension_analysis.run(
                str(self.document.id), "clarity", user_id=self.user.id
            )

        self.assertEqual(result["status"], "error")
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "review_completed")  # 回滚占用


class RetryAnalysisViewTests(TestCase):
    """retry-analysis 视图：校验、鉴权、占用状态与派发失败回滚"""

    def setUp(self):
        # CE 适配：开源线无 LicenseCheckMiddleware 时无需 patch 授权拦截。
        if _HAS_LICENSE_MIDDLEWARE:
            self._license_patch = patch(
                "license_control.middleware.LicenseCheckMiddleware._verify_with_cache",
                return_value="OK",
            )
            self._license_patch.start()
            self.addCleanup(self._license_patch.stop)

        self.client = APIClient()
        self.user = User.objects.create_user(username="retryapi", password="password123")
        for codename in ("add_reviewreport", "add_requirementdocument"):
            self.user.user_permissions.add(Permission.objects.get(codename=codename))
        self.project = Project.objects.create(name="RetryApi", creator=self.user)
        ProjectMember.objects.create(project=self.project, user=self.user, role="member")
        self.client.force_authenticate(self.user)
        self.document = RequirementDocument.objects.create(
            project=self.project, title="RetryApiDoc", document_type="md",
            content="# x", status="review_completed", uploader=self.user,
        )
        ReviewReport.objects.create(
            document=self.document, status="completed", review_type="comprehensive",
            progress=1.0,
            specialized_analyses={
                "clarity_analysis": {"status": "failed", "error_message": "x", "overall_score": None},
            },
        )
        self.url = reverse(
            "requirement-documents-retry-analysis", kwargs={"pk": self.document.id}
        )

    @patch("requirements.views.resolve_llm_config")
    @patch("requirements.tasks.retry_dimension_analysis")
    def test_dispatch_ok(self, mock_task, mock_resolve):
        mock_resolve.return_value = MagicMock(bundle=MagicMock(id=6), source="test")
        mock_task.delay.return_value = MagicMock(id="t1")
        response = self.client.post(self.url, {"dimension": "clarity"})
        self.assertEqual(response.status_code, 200)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "reviewing")
        mock_task.delay.assert_called_once()

    def test_invalid_dimension_rejected(self):
        response = self.client.post(self.url, {"dimension": "bogus"})
        self.assertEqual(response.status_code, 400)

    def test_not_completed_document_rejected(self):
        self.document.status = "reviewing"
        self.document.save()
        response = self.client.post(self.url, {"dimension": "clarity"})
        self.assertEqual(response.status_code, 400)

    @patch("requirements.views.resolve_llm_config")
    @patch("requirements.tasks.retry_dimension_analysis")
    def test_dispatch_failure_rolls_back(self, mock_task, mock_resolve):
        mock_resolve.return_value = MagicMock(bundle=MagicMock(id=6), source="test")
        mock_task.delay.side_effect = ConnectionError("broker down")
        response = self.client.post(self.url, {"dimension": "clarity"})
        self.assertEqual(response.status_code, 500)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, "review_completed")
        self.assertIn("派发失败", self.document.error_message)

