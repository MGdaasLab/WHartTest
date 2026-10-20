import os
import tempfile
import time
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.test import TestCase
from django.test.utils import override_settings

from . import agent_loop_view
from .agent_loop_view import (
    _extract_linked_image_urls,
    _is_linked_image_url_allowed,
    _normalize_uploaded_image_base64_list,
    _prepare_agent_loop_human_message,
)
from .builtin_tools.skill_tools import (
    _build_skill_artifacts_dir,
    _collect_skill_artifacts,
    _build_skill_screenshots_dir,
    _finalize_skill_result,
    _prepare_skill_screenshots_dir,
    _SKILL_DIR_STALE_SECONDS,
    _sanitize_runtime_path_segment,
)
from .builtin_tools.output_sanitizer import strip_terminal_control_sequences
from .middleware_config import get_user_friendly_llm_error, _model_retry_should_retry
from projects.models import Project, ProjectMember
from requirements.models import DocumentImage, RequirementDocument


class LLMFriendlyErrorTests(SimpleTestCase):
    def test_model_cooldown_error_returns_friendly_payload(self):
        exc = Exception(
            "Error code: 429 - {'error': {'code': 'model_cooldown', 'message': 'All credentials for model coder-model are cooling down', 'model': 'coder-model', 'reset_seconds': 27211, 'reset_time': '7h33m31s'}}"
        )

        result = get_user_friendly_llm_error(exc)

        if result is None:
            raise AssertionError("expected friendly error payload")
        self.assertEqual(result["status_code"], 429)
        self.assertEqual(result["error_code"], "model_cooldown")
        self.assertEqual(result["model"], "coder-model")
        self.assertEqual(result["reset_seconds"], 27211)
        self.assertEqual(result["reset_time"], "7h33m31s")
        self.assertIn("coder-model", result["message"])
        self.assertIn("7h33m31s", result["message"])

    def test_generic_rate_limit_error_returns_friendly_payload(self):
        exc = Exception("HTTP 429 Too Many Requests")

        result = get_user_friendly_llm_error(exc)

        if result is None:
            raise AssertionError("expected friendly error payload")
        self.assertEqual(result["status_code"], 429)
        self.assertEqual(result["error_code"], "rate_limit")
        self.assertEqual(result["message"], "当前模型服务请求过于频繁，请稍后重试。")

    def test_model_cooldown_error_will_not_retry(self):
        exc = Exception(
            "Error code: 429 - {'error': {'code': 'model_cooldown', 'message': 'All credentials for model coder-model are cooling down', 'model': 'coder-model', 'reset_seconds': 27211, 'reset_time': '7h33m31s'}}"
        )

        self.assertFalse(_model_retry_should_retry(exc))

    def test_cooling_down_text_without_code_still_maps_to_model_cooldown(self):
        exc = Exception(
            "RateLimitError: provider says model service is cooling down, retry-after: 6m0s"
        )

        result = get_user_friendly_llm_error(exc)

        if result is None:
            raise AssertionError("expected friendly cooldown payload")
        self.assertEqual(result["status_code"], 429)
        self.assertEqual(result["error_code"], "model_cooldown")
        self.assertIn("冷却中", result["message"])


class LinkedImageUrlExtractionTests(SimpleTestCase):
    def test_extract_plain_http_url_stops_before_chinese_description(self):
        text = "请访问 https://localhost:8080，准备注册信息：用户名testuser010、密码abcdef123"

        self.assertEqual(_extract_linked_image_urls(text), ["https://localhost:8080"])

    def test_extract_markdown_image_url_trims_wrapping_punctuation(self):
        text = "参考截图 ![image](https://example.com/demo.png)，然后继续分析"

        self.assertEqual(
            _extract_linked_image_urls(text),
            ["https://example.com/demo.png"],
        )

    def test_extract_invalid_unicode_netloc_does_not_raise(self):
        text = "异常链接 https://localhost:8080：准备注册信息：用户名testuser014"

        self.assertEqual(_extract_linked_image_urls(text), ["https://localhost:8080"])

    def test_extract_plain_http_url_stops_before_ascii_comma_description(self):
        text = "Open http://localhost:8080,then fill the registration form"

        self.assertEqual(_extract_linked_image_urls(text), ["http://localhost:8080"])

    def test_extract_plain_http_url_stops_before_closing_parenthesis_text(self):
        text = "查看截图 https://example.com/demo.png)后继续分析"

        self.assertEqual(
            _extract_linked_image_urls(text),
            ["https://example.com/demo.png"],
        )

    def test_allowlist_check_rejects_invalid_url_without_raising(self):
        with patch.object(
            agent_loop_view, "_LINKED_IMAGE_URL_ALLOWLIST", {"example.com"}
        ):
            self.assertFalse(
                _is_linked_image_url_allowed(
                    "https://localhost:8080：准备注册信息：用户名testuser014"
                )
            )


class UploadedImageNormalizationTests(SimpleTestCase):
    def test_normalize_uploaded_images_merges_legacy_and_array_fields(self):
        result = _normalize_uploaded_image_base64_list(
            ["img-a", " img-b ", "", "img-a"],
            "img-c",
        )

        self.assertEqual(result, ["img-a", "img-b", "img-c"])

    def test_normalize_uploaded_images_accepts_legacy_single_image_only(self):
        result = _normalize_uploaded_image_base64_list(None, " legacy-img ")

        self.assertEqual(result, ["legacy-img"])


class AgentLoopRequirementImageMessageTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.override_media = override_settings(MEDIA_ROOT=self.temp_dir.name)
        self.override_media.enable()
        self.addCleanup(self.override_media.disable)

        self.user = get_user_model().objects.create_user(
            username="agent-loop-user",
            password="password123",
        )
        self.project = Project.objects.create(
            name="Agent Loop Image Project",
            creator=self.user,
        )
        ProjectMember.objects.create(
            project=self.project,
            user=self.user,
            role="member",
        )
        self.document = RequirementDocument.objects.create(
            project=self.project,
            title="Requirement With Images",
            document_type="docx",
            uploader=self.user,
            has_images=True,
            image_count=1,
        )
        DocumentImage.objects.create(
            document=self.document,
            image_id="img_000",
            order=0,
            content_type="image/png",
            file_size=3,
            image_file=SimpleUploadedFile(
                "img-000.png",
                b"png",
                content_type="image/png",
            ),
        )

    def test_prepare_agent_loop_human_message_rewrites_requirement_placeholders(self):
        message = (
            "请分析以下需求\n\n"
            "![图片](docimg://img_000)\n\n"
            f"(这些需求模块来源于需求文档ID: {self.document.id})"
        )

        human_message_content, additional_kwargs, display_message = async_to_sync(
            _prepare_agent_loop_human_message
        )(
            message,
            project=self.project,
            supports_vision=False,
            uploaded_images_base64=[],
        )

        expected_url = (
            f"/api/requirements/documents/{self.document.id}/images/img_000/"
        )
        self.assertEqual(human_message_content, display_message)
        self.assertIn(expected_url, display_message)
        self.assertEqual(
            additional_kwargs["requirement_document_id"], str(self.document.id)
        )

    def test_prepare_agent_loop_human_message_attaches_requirement_images_for_vision(self):
        message = (
            "请分析以下需求\n\n"
            "![图片](docimg://img_000)\n\n"
            f"(这些需求模块来源于需求文档ID: {self.document.id})"
        )

        human_message_content, additional_kwargs, display_message = async_to_sync(
            _prepare_agent_loop_human_message
        )(
            message,
            project=self.project,
            supports_vision=True,
            uploaded_images_base64=[],
        )

        self.assertIsInstance(human_message_content, list)
        self.assertEqual(human_message_content[0]["type"], "text")
        self.assertIn(
            f"/api/requirements/documents/{self.document.id}/images/img_000/",
            human_message_content[0]["text"],
        )
        self.assertEqual(human_message_content[1]["type"], "image_url")
        self.assertTrue(
            human_message_content[1]["image_url"]["url"].startswith(
                "data:image/png;base64,"
            )
        )
        self.assertEqual(
            additional_kwargs["requirement_document_id"], str(self.document.id)
        )
        self.assertEqual(additional_kwargs["image_source"], "requirement_document")
        self.assertIn(
            f"/api/requirements/documents/{self.document.id}/images/img_000/",
            display_message,
        )


class SkillScreenshotDirectoryTests(SimpleTestCase):
    def test_sanitize_runtime_path_segment_blocks_path_traversal(self):
        self.assertEqual(
            _sanitize_runtime_path_segment("../case/89", "_default"),
            "__case_89",
        )

    def test_build_skill_screenshots_dir_uses_runtime_media_root(self):
        with tempfile.TemporaryDirectory() as temp_media_root:
            with override_settings(MEDIA_ROOT=temp_media_root):
                screenshots_dir = _build_skill_screenshots_dir(1, "89")

        self.assertTrue(screenshots_dir.endswith("skill_runtime/screenshots/1/89"))
        self.assertNotIn("/skills/1/11/", screenshots_dir)

    def test_build_skill_screenshots_dir_keeps_path_inside_media_root(self):
        with tempfile.TemporaryDirectory() as temp_media_root:
            with override_settings(MEDIA_ROOT=temp_media_root):
                screenshots_dir = _build_skill_screenshots_dir(1, "../case/89")

        self.assertTrue(screenshots_dir.startswith(temp_media_root))
        self.assertNotIn("..", screenshots_dir)

    def test_prepare_skill_screenshots_dir_clears_idle_dir(self):
        with tempfile.TemporaryDirectory() as temp_media_root:
            with override_settings(MEDIA_ROOT=temp_media_root):
                screenshots_dir = _prepare_skill_screenshots_dir(1, "89")
                stale_file = os.path.join(screenshots_dir, "old.png")
                with open(stale_file, "w", encoding="utf-8") as f:
                    f.write("old screenshot")

                # 目录仍新鲜：不清理，避免误删当前会话截图
                refreshed_dir = _prepare_skill_screenshots_dir(1, "89")
                self.assertEqual(refreshed_dir, screenshots_dir)
                self.assertTrue(os.path.exists(stale_file))

                # 子目录内文件也参与闲置判定：子目录内容变新则不清空
                sub_file = os.path.join(screenshots_dir, "sub", "recent.png")
                os.makedirs(os.path.dirname(sub_file), exist_ok=True)
                with open(sub_file, "w", encoding="utf-8") as f:
                    f.write("recent")
                refreshed_dir = _prepare_skill_screenshots_dir(1, "89")
                self.assertTrue(os.path.exists(stale_file))

                # 目录树闲置超过阈值后清理
                old = time.time() - _SKILL_DIR_STALE_SECONDS - 60
                os.utime(stale_file, (old, old))
                os.utime(sub_file, (old, old))
                refreshed_dir = _prepare_skill_screenshots_dir(1, "89")
                self.assertEqual(refreshed_dir, screenshots_dir)
                self.assertFalse(os.path.exists(stale_file))

    def test_build_skill_artifacts_dir_uses_runtime_media_root(self):
        with tempfile.TemporaryDirectory() as temp_media_root:
            with override_settings(MEDIA_ROOT=temp_media_root):
                artifacts_dir = _build_skill_artifacts_dir(1, "session-1")

        self.assertTrue(artifacts_dir.endswith("skill_runtime/artifacts/1/session-1"))
        self.assertNotIn("/skills/1/11/", artifacts_dir)

    def test_collect_skill_artifacts_detects_named_generated_file(self):
        with tempfile.TemporaryDirectory() as temp_media_root:
            with override_settings(MEDIA_ROOT=temp_media_root, MEDIA_URL="/media/"):
                skill_dir = os.path.join(temp_media_root, "skills", "1", "11")
                os.makedirs(skill_dir, exist_ok=True)
                generated_file = os.path.join(skill_dir, "order-payment-flow.drawio")
                with open(generated_file, "w", encoding="utf-8") as f:
                    f.write("<mxfile></mxfile>")

                artifacts = _collect_skill_artifacts(
                    "已帮你生成 draw.io 文件：order-payment-flow.drawio",
                    skill_dir=skill_dir,
                    artifacts_dir=os.path.join(temp_media_root, "skill_runtime", "artifacts", "1", "s1"),
                    artifacts_before={},
                )

        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0]["name"], "order-payment-flow.drawio")
        self.assertEqual(artifacts[0]["url"], "/media/skills/1/11/order-payment-flow.drawio")

    def test_finalize_skill_result_wraps_output_with_file_payload(self):
        with tempfile.TemporaryDirectory() as temp_media_root:
            with override_settings(MEDIA_ROOT=temp_media_root, MEDIA_URL="/media/"):
                skill_dir = os.path.join(temp_media_root, "skills", "1", "11")
                os.makedirs(skill_dir, exist_ok=True)
                generated_file = os.path.join(skill_dir, "demo.drawio")
                with open(generated_file, "w", encoding="utf-8") as f:
                    f.write("<mxfile></mxfile>")

                wrapped = _finalize_skill_result(
                    "已生成文件 demo.drawio",
                    skill_dir=skill_dir,
                    artifacts_dir=os.path.join(temp_media_root, "skill_runtime", "artifacts", "1", "s1"),
                    artifacts_before={},
                )

        self.assertIn('"type": "file"', wrapped)
        self.assertIn('/media/skills/1/11/demo.drawio', wrapped)


class TerminalOutputSanitizerTests(SimpleTestCase):
    def test_strip_terminal_control_sequences_removes_ansi_color_codes(self):
        raw = "\x1b[32m✓\x1b[0m Browser closed"

        self.assertEqual(strip_terminal_control_sequences(raw), "✓ Browser closed")


class GenerationModeGuardTests(SimpleTestCase):
    """UI/接口一键生成模式检测与守护中间件行为。"""

    def test_detect_generation_mode(self):
        from .generation_guard import (
            GENERATION_MODE_INTERFACE_CASE,
            GENERATION_MODE_UI_CASE,
            detect_generation_mode,
        )

        self.assertIsNone(detect_generation_mode(None))
        self.assertIsNone(detect_generation_mode('普通消息'))
        self.assertEqual(
            detect_generation_mode('<!-- wharttest:generation_mode=interface_case --> msg'),
            GENERATION_MODE_INTERFACE_CASE,
        )
        self.assertEqual(
            detect_generation_mode('<!-- wharttest:generation_mode=ui_case --> msg'),
            GENERATION_MODE_UI_CASE,
        )
        # interface_case 标记优先，保持历史行为
        self.assertEqual(
            detect_generation_mode('wharttest:generation_mode=ui_case wharttest:generation_mode=interface_case'),
            GENERATION_MODE_INTERFACE_CASE,
        )

    def test_should_guard_generation_prompt_backward_compatible(self):
        from .generation_guard import should_guard_generation_prompt

        self.assertTrue(should_guard_generation_prompt('x wharttest:generation_mode=interface_case y'))
        self.assertFalse(should_guard_generation_prompt('x wharttest:generation_mode=ui_case y'))

    @staticmethod
    def _make_tool_request(action: str, payload: dict | None = None):
        from types import SimpleNamespace

        args = {'command': f'python ui_automation_tools.py --action {action}'}
        if payload is not None:
            import json

            args['command'] += f" --payload '{json.dumps(payload, ensure_ascii=False)}'"
        return SimpleNamespace(tool_call={'name': 'execute_skill_script', 'args': args, 'id': 'call_1'})

    def test_ui_case_guard_blocks_api_case_tools(self):
        from .generation_guard import GenerationUiCaseGuardMiddleware

        middleware = GenerationUiCaseGuardMiddleware()
        for action in ('create_interface_case', 'run_interface_case', 'update_interface_case'):
            handled = []

            def handler(request):
                handled.append(request)
                return 'passed'

            result = middleware.wrap_tool_call(self._make_tool_request(action), handler)
            self.assertEqual(result.status, 'error')
            self.assertIn('UI 自动化用例生成', str(result.content))
            self.assertFalse(handled)
        self.assertEqual(middleware.drift_count, 3)

    def test_ui_case_guard_allows_ui_tools(self):
        from .generation_guard import GenerationUiCaseGuardMiddleware

        middleware = GenerationUiCaseGuardMiddleware()
        for action in ('create_ui_page', 'create_element', 'create_page_step', 'create_testcase'):
            result = middleware.wrap_tool_call(
                self._make_tool_request(action), lambda request: 'passed'
            )
            self.assertEqual(result, 'passed')
        self.assertEqual(middleware.drift_count, 0)

    def test_interface_case_guard_still_blocks_scenario_tools(self):
        from .generation_guard import GenerationInterfaceCaseGuardMiddleware

        middleware = GenerationInterfaceCaseGuardMiddleware()
        result = middleware.wrap_tool_call(
            self._make_tool_request('create_testcase'), lambda request: 'passed'
        )
        self.assertEqual(result.status, 'error')

    def test_parse_ui_generation_context(self):
        from .agent_loop_view import _parse_ui_generation_context

        self.assertIsNone(_parse_ui_generation_context(None))
        self.assertIsNone(_parse_ui_generation_context('bad'))
        self.assertIsNone(_parse_ui_generation_context({'start_url': 'https://x.com'}))
        context = _parse_ui_generation_context(
            {
                'auth_state_id': '7',
                'env_config_id': 3,
                'username': ' admin ',
                'password': 'p',
                'start_url': 'https://x.com',
            }
        )
        self.assertEqual(
            context,
            {
                'auth_state_id': 7,
                'env_config_id': 3,
                'username': 'admin',
                'password': 'p',
                'start_url': 'https://x.com',
            },
        )
class UiGenerationCredentialInjectionTests(SimpleTestCase):
    """UI 一键生成凭据注入链路与内置工具装配回归。"""

    def test_get_builtin_tools_without_credential_context(self):
        # 回归：__init__.py 曾无条件把 ui_credential_context 透传给
        # get_skill_tools，导致所有 Agent 会话在此处 TypeError。
        from .builtin_tools import get_builtin_tools

        tools = get_builtin_tools(user_id=1, project_id=1)
        self.assertTrue(tools)
        self.assertIn(
            "execute_skill_script",
            [getattr(tool, "name", "") for tool in tools],
        )

    def test_get_builtin_tools_accepts_ui_credential_context(self):
        from .builtin_tools import get_builtin_tools

        tools = get_builtin_tools(
            user_id=1,
            project_id=1,
            ui_credential_context={"username": "admin", "password": "p"},
        )
        self.assertTrue(tools)

    def test_apply_ui_credential_env(self):
        from .builtin_tools.skill_tools import _apply_ui_credential_env

        env = {}
        _apply_ui_credential_env(
            env,
            {"username": " admin ", "password": "p"},
            "/tmp/state.json",
        )
        self.assertEqual(
            env,
            {
                "WHARTTEST_UI_USERNAME": "admin",
                "WHARTTEST_UI_PASSWORD": "p",
                "WHARTTEST_UI_AUTH_STATE_FILE": "/tmp/state.json",
            },
        )

        empty = {}
        _apply_ui_credential_env(empty, None, None)
        self.assertEqual(empty, {})

    def test_truncate_tool_output(self):
        from .builtin_tools.skill_tools import _truncate_tool_output

        self.assertEqual(_truncate_tool_output("short"), "short")
        truncated = _truncate_tool_output("x" * 20, max_chars=5)
        self.assertTrue(truncated.startswith("xxxxx"))
        self.assertIn("输出已截断", truncated)


class UiAuthStateSnapshotTests(SimpleTestCase):
    """UI 生成登录态快照：项目隔离、权限与文件权限。"""

    @staticmethod
    def _patch_auth_state(auth_state):
        from unittest.mock import MagicMock

        queryset = MagicMock()
        queryset.filter.return_value.first.return_value = auth_state
        manager = MagicMock()
        manager.select_related.return_value = queryset
        model = MagicMock()
        model.objects = manager
        return model, queryset

    def test_prepare_snapshot_scopes_by_project_and_writes_file(self):
        import json
        import os
        import stat
        import tempfile
        from unittest.mock import patch

        from django.test import override_settings

        from .builtin_tools import skill_tools

        state = type("State", (), {})()
        state.state_json = {"cookies": [{"name": "s"}], "origins": []}
        model, queryset = self._patch_auth_state(state)

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                with patch("ui_automation.models.UiAuthState", model):
                    with patch.object(
                        skill_tools, "_skill_exec_uses_runner_sandbox", return_value=False
                    ):
                        file_path = skill_tools._prepare_ui_auth_state_file(
                            {"auth_state_id": 7}, 5, 9, "sess-1"
                        )
            self.assertIsNotNone(file_path)
            self.assertTrue(file_path.startswith(media_root))
            with open(file_path, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh), state.state_json)
            self.assertEqual(
                stat.S_IMODE(os.stat(file_path).st_mode),
                0o600,
            )

        queryset.filter.assert_called_once_with(
            id=7, is_active=True, env_config__project_id=9
        )

    def test_prepare_snapshot_returns_none_for_foreign_or_missing_state(self):
        import tempfile
        from unittest.mock import patch

        from django.test import override_settings

        from .builtin_tools import skill_tools

        model, _queryset = self._patch_auth_state(None)
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                with patch("ui_automation.models.UiAuthState", model):
                    file_path = skill_tools._prepare_ui_auth_state_file(
                        {"auth_state_id": 7}, 5, 9, "sess-1"
                    )
        self.assertIsNone(file_path)

    def test_prepare_snapshot_runner_mode_is_shared_readable(self):
        import os
        import stat
        import tempfile
        from unittest.mock import patch

        from django.test import override_settings

        from .builtin_tools import skill_tools

        state = type("State", (), {})()
        state.state_json = {"cookies": [], "origins": []}
        model, _queryset = self._patch_auth_state(state)

        with tempfile.TemporaryDirectory() as media_root:
            os.makedirs(os.path.join(media_root, "skill_runtime"))
            with override_settings(MEDIA_ROOT=media_root):
                with patch("ui_automation.models.UiAuthState", model):
                    with patch.object(
                        skill_tools, "_skill_exec_uses_runner_sandbox", return_value=True
                    ):
                        file_path = skill_tools._prepare_ui_auth_state_file(
                            {"auth_state_id": 7}, 5, 9, "sess-1"
                        )
            self.assertIsNotNone(file_path)
            self.assertEqual(
                stat.S_IMODE(os.stat(file_path).st_mode),
                0o640,
            )
            state_dir = os.path.dirname(file_path)
            self.assertEqual(
                stat.S_IMODE(os.stat(state_dir).st_mode),
                0o750,
            )
