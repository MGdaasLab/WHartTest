import os
import tempfile
import time
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import Permission, User
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
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
