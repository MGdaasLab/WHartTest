import unittest
from unittest.mock import Mock, patch

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from langchain_core.messages import AIMessage, HumanMessage
from rest_framework.test import APIClient


class AutoSummarizeSessionTitleTests(TestCase):
    class _DummyTitleLLM:
        async def ainvoke(self, messages):
            return type(
                "TitleResponse",
                (),
                {
                    "content": '"自动标题"',
                    "usage_metadata": {
                        "input_tokens": 11,
                        "output_tokens": 3,
                        "input_token_details": {"cache_read": 2},
                    },
                },
            )()

    def setUp(self):
        from projects.models import Project

        self.user = get_user_model().objects.create_user(
            username="title-summary-user",
            password="password123",
        )
        self.project = Project.objects.create(
            name="Title Summary Project",
            creator=self.user,
        )

    def _create_session(self, title):
        from .models import ChatSession

        return ChatSession.objects.create(
            user=self.user,
            session_id=f"title-summary-{title}",
            title=title,
            project=self.project,
        )

    def test_auto_summarize_updates_new_conversation_title_and_records_tokens(self):
        from .models import TokenUsageRecord
        from .views import auto_summarize_session_title

        session = self._create_session("新对话 - 原始问题")

        result = async_to_sync(auto_summarize_session_title)(
            self._DummyTitleLLM(),
            session,
            "帮我生成测试用例",
        )

        self.assertEqual(result, "自动标题")
        session.refresh_from_db()
        self.assertEqual(session.title, "自动标题")
        self.assertEqual(session.total_input_tokens, 11)
        self.assertEqual(session.total_output_tokens, 3)
        self.assertEqual(session.total_tokens, 14)
        self.assertEqual(session.total_cache_read_tokens, 2)
        self.assertEqual(session.request_count, 1)
        self.assertTrue(
            TokenUsageRecord.objects.filter(
                session_id=session.session_id,
                input_tokens=11,
                output_tokens=3,
                cache_read_tokens=2,
            ).exists()
        )

    def test_auto_summarize_does_not_overwrite_manual_title_but_records_tokens(self):
        from .models import TokenUsageRecord
        from .views import auto_summarize_session_title

        session = self._create_session("用户手动标题")

        result = async_to_sync(auto_summarize_session_title)(
            self._DummyTitleLLM(),
            session,
            "帮我生成测试用例",
        )

        self.assertIsNone(result)
        session.refresh_from_db()
        self.assertEqual(session.title, "用户手动标题")
        self.assertEqual(session.total_input_tokens, 11)
        self.assertEqual(session.total_output_tokens, 3)
        self.assertEqual(session.total_tokens, 14)
        self.assertEqual(session.total_cache_read_tokens, 2)
        self.assertEqual(session.request_count, 1)
        self.assertTrue(
            TokenUsageRecord.objects.filter(
                session_id=session.session_id,
                input_tokens=11,
                output_tokens=3,
                cache_read_tokens=2,
            ).exists()
        )


try:
    from .bundle_runtime import LLMConfigResolutionError, resolve_llm_config
    from .models import (
        DEFAULT_LLM_BUNDLE_SLOT_KEY,
        LLMConfigBundle,
        LLMConfigBundleSlot,
        LLMGlobalBundleRotationState,
    )
    BUNDLE_RUNTIME_AVAILABLE = True
except (ImportError, AttributeError):
    BUNDLE_RUNTIME_AVAILABLE = False
    LLMConfigResolutionError = Exception
    resolve_llm_config = None
    DEFAULT_LLM_BUNDLE_SLOT_KEY = 'llm_chat'
    LLMConfigBundle = None
    LLMConfigBundleSlot = None
    LLMGlobalBundleRotationState = None


@unittest.skipUnless(BUNDLE_RUNTIME_AVAILABLE, "LLM config bundle runtime source is not available in this checkout")
class LLMConfigBundleRuntimeTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.owner = self.user_model.objects.create_user(
            username="owner",
            password="password123",
        )
        self.other_user = self.user_model.objects.create_user(
            username="other",
            password="password123",
        )
        self.third_user = self.user_model.objects.create_user(
            username="third",
            password="password123",
        )
        self.fourth_user = self.user_model.objects.create_user(
            username="fourth",
            password="password123",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def _slot_payload(self, slot_key, *, configured=None, name_suffix="chat"):
        is_configured = configured if configured is not None else slot_key == DEFAULT_LLM_BUNDLE_SLOT_KEY
        return {
            "slot_key": slot_key,
            "is_configured": is_configured,
            "provider": "openai_compatible",
            "name": f"model-{name_suffix}-{slot_key}" if is_configured else "",
            "api_url": "https://example.com/v1" if is_configured else "",
            "api_key": "secret-key" if is_configured else "",
            "system_prompt": f"prompt-{slot_key}" if is_configured else "",
            "supports_vision": slot_key == DEFAULT_LLM_BUNDLE_SLOT_KEY,
            "context_limit": 128000,
            "request_timeout": 120,
            "max_retries": 3,
            "enable_summarization": True,
            "enable_hitl": True,
            "enable_streaming": True,
            "default_runtime_mode": "standard" if is_configured else "auto",
        }

    def _bundle_payload(self, name="bundle-1", *, is_active=True, is_global=False):
        slot_keys = [
            "llm_chat",
            "requirement_review",
            "testcase_generation",
            "testcase_execution",
        ]
        return {
            "config_name": name,
            "is_active": is_active,
            "is_global": is_global,
            "slots": [
                self._slot_payload(
                    slot_key,
                    configured=slot_key == "llm_chat",
                    name_suffix=name,
                )
                for slot_key in slot_keys
            ],
        }

    def _create_bundle(self, owner, name, *, is_active=True, is_global=False, configured_slots=None):
        configured_slots = configured_slots or {}
        bundle = LLMConfigBundle.objects.create(
            owner=owner,
            config_name=name,
            is_active=is_active,
            is_global=is_global,
        )
        for slot_key in [
            "llm_chat",
            "requirement_review",
            "testcase_generation",
            "testcase_execution",
        ]:
            override = configured_slots.get(slot_key, {})
            slot_data = self._slot_payload(
                slot_key,
                configured=override.get(
                    "is_configured", slot_key == DEFAULT_LLM_BUNDLE_SLOT_KEY
                ),
                name_suffix=override.get("name_suffix", name),
            )
            slot_data.update(override)
            LLMConfigBundleSlot.objects.create(bundle=bundle, **slot_data)
        return bundle

    def test_create_bundle_api_creates_all_required_slots(self):
        response = self.client.post(
            reverse("llmconfigbundle-list"),
            self._bundle_payload("api-bundle"),
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        bundle = LLMConfigBundle.objects.get(config_name="api-bundle")
        self.assertEqual(bundle.slots.count(), 4)
        self.assertTrue(
            bundle.slots.get(slot_key=DEFAULT_LLM_BUNDLE_SLOT_KEY).is_configured
        )
        self.assertFalse(
            bundle.slots.get(slot_key="requirement_review").is_configured
        )

    def test_create_bundle_api_allows_blank_unconfigured_slots(self):
        payload = self._bundle_payload("blank-fallback-bundle")
        for slot in payload["slots"]:
            if slot["slot_key"] == DEFAULT_LLM_BUNDLE_SLOT_KEY:
                continue
            slot.update(
                {
                    "provider": "",
                    "name": "",
                    "api_url": "",
                    "api_key": "",
                    "system_prompt": "",
                }
            )

        response = self.client.post(
            reverse("llmconfigbundle-list"),
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        bundle = LLMConfigBundle.objects.get(config_name="blank-fallback-bundle")
        review_slot = bundle.slots.get(slot_key="requirement_review")
        self.assertFalse(review_slot.is_configured)
        self.assertEqual(review_slot.name, "")
        runtime_response = self.client.get(
            reverse("llmconfigbundle-runtime-current"),
            {"module_key": "requirement_review"},
        )
        self.assertEqual(runtime_response.status_code, 200)
        self.assertEqual(
            runtime_response.data["resolved_source"],
            "personal_fallback_chat",
        )
        self.assertEqual(runtime_response.data["effective_slot_key"], "llm_chat")

    def test_create_bundle_api_accepts_deepseek_provider(self):
        payload = self._bundle_payload("deepseek-bundle")
        payload["slots"][0].update(
            {
                "provider": "deepseek",
                "name": "deepseek-chat",
                "api_url": "https://api.deepseek.com/v1",
            }
        )

        response = self.client.post(
            reverse("llmconfigbundle-list"),
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        bundle = LLMConfigBundle.objects.get(config_name="deepseek-bundle")
        self.assertEqual(
            bundle.slots.get(slot_key=DEFAULT_LLM_BUNDLE_SLOT_KEY).provider,
            "deepseek",
        )

    def test_provider_choices_endpoint_includes_deepseek(self):
        response = self.client.get(reverse("provider_choices_api"))

        self.assertEqual(response.status_code, 200)
        provider_values = [
            item["value"] for item in response.data["data"]["choices"]
        ]
        self.assertIn("deepseek", provider_values)

    @patch("langgraph_integration.deepseek_chat_model.ReasoningCompatibleChatDeepSeek")
    def test_create_llm_instance_uses_chatdeepseek_for_deepseek_provider(
        self, mock_chat_deepseek
    ):
        from .views import create_llm_instance

        active_config = Mock()
        active_config.name = "deepseek-chat"
        active_config.provider = "deepseek"
        active_config.api_url = "https://api.deepseek.com"
        active_config.api_key = "deepseek-key"
        active_config.request_timeout = 90
        active_config.max_retries = 2

        llm = create_llm_instance(active_config, temperature=0.2)

        self.assertEqual(llm, mock_chat_deepseek.return_value)
        mock_chat_deepseek.assert_called_once_with(
            model="deepseek-chat",
            temperature=0.2,
            timeout=90,
            max_retries=2,
            api_key="deepseek-key",
            api_base="https://api.deepseek.com/v1",
        )

    def test_reasoning_compatible_chatdeepseek_round_trips_reasoning_content(self):
        from .deepseek_chat_model import ReasoningCompatibleChatDeepSeek

        model = ReasoningCompatibleChatDeepSeek(
            model="deepseek-chat",
            api_key="deepseek-key",
            api_base="https://api.deepseek.com/v1",
        )

        payload = model._get_request_payload(
            [
                HumanMessage(content="你好"),
                AIMessage(
                    content="这是回答",
                    additional_kwargs={"reasoning_content": "这是推理内容"},
                ),
            ]
        )

        self.assertEqual(payload["messages"][1]["role"], "assistant")
        self.assertEqual(
            payload["messages"][1]["reasoning_content"],
            "这是推理内容",
        )

    @patch("requests.get")
    def test_fetch_models_uses_saved_slot_api_key_when_request_omits_it(self, mock_get):
        bundle = self._create_bundle(
            self.owner,
            "fetch-models-bundle",
            configured_slots={
                "requirement_review": {
                    "is_configured": True,
                    "api_url": "https://example.com/v1",
                    "api_key": "saved-slot-key",
                }
            },
        )
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"data": [{"id": "gpt-4o-mini"}]}
        mock_get.return_value = mock_response

        response = self.client.post(
            reverse("llmconfigbundle-fetch-models"),
            {
                "bundle_id": bundle.id,
                "slot_key": "requirement_review",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["models"], ["gpt-4o-mini"])
        mock_get.assert_called_once_with(
            "https://example.com/v1/models",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer saved-slot-key",
            },
            timeout=10,
        )

    def test_activate_bundle_makes_owner_bundle_unique(self):
        bundle1 = self._create_bundle(self.owner, "bundle-1", is_active=True)
        bundle2 = self._create_bundle(self.owner, "bundle-2", is_active=False)

        response = self.client.post(
            reverse("llmconfigbundle-activate", kwargs={"pk": bundle2.id}),
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        bundle1.refresh_from_db()
        bundle2.refresh_from_db()
        self.assertFalse(bundle1.is_active)
        self.assertTrue(bundle2.is_active)

    def test_personal_bundle_slot_falls_back_to_default_chat_slot(self):
        self._create_bundle(
            self.owner,
            "personal-bundle",
            configured_slots={
                "requirement_review": {"is_configured": False},
            },
        )

        result = resolve_llm_config(
            user=self.owner,
            module_key="requirement_review",
        )

        self.assertEqual(result.source, "personal_fallback_chat")
        self.assertEqual(result.runtime_config.slot_key, "llm_chat")
        self.assertTrue(result.runtime_config.supports_vision)

    def test_unconfigured_slot_inherits_default_slot_runtime_mode(self):
        self._create_bundle(
            self.owner,
            "runtime-inherit-bundle",
            configured_slots={
                "llm_chat": {"default_runtime_mode": "deep"},
                "requirement_review": {
                    "is_configured": False,
                    "default_runtime_mode": "auto",
                },
            },
        )

        result = resolve_llm_config(
            user=self.owner,
            module_key="requirement_review",
        )

        self.assertEqual(result.source, "personal_fallback_chat")
        self.assertEqual(result.runtime_config.slot_key, "llm_chat")
        self.assertEqual(result.runtime_config.default_runtime_mode, "deep")

    def test_unconfigured_slot_can_override_runtime_mode_explicitly(self):
        self._create_bundle(
            self.owner,
            "runtime-override-bundle",
            configured_slots={
                "llm_chat": {"default_runtime_mode": "deep"},
                "requirement_review": {
                    "is_configured": False,
                    "default_runtime_mode": "standard",
                },
            },
        )

        result = resolve_llm_config(
            user=self.owner,
            module_key="requirement_review",
        )

        self.assertEqual(result.runtime_config.slot_key, "llm_chat")
        self.assertEqual(result.runtime_config.default_runtime_mode, "standard")

    def test_personal_bundle_has_priority_over_global_bundle(self):
        self._create_bundle(self.owner, "personal-bundle", is_active=True)
        self._create_bundle(self.other_user, "global-bundle", is_active=True, is_global=True)

        result = resolve_llm_config(user=self.owner, module_key="llm_chat")

        self.assertEqual(result.source, "personal_slot")
        self.assertEqual(result.bundle.owner_id, self.owner.id)

    def test_global_bundle_round_robin_is_stable(self):
        LLMGlobalBundleRotationState.objects.all().delete()
        bundle1 = self._create_bundle(self.other_user, "global-1", is_active=True, is_global=True)
        bundle2 = self._create_bundle(self.third_user, "global-2", is_active=True, is_global=True)
        bundle3 = self._create_bundle(self.fourth_user, "global-3", is_active=True, is_global=True)

        sequence = [
            resolve_llm_config(user=self.owner, module_key="llm_chat").bundle.id
            for _ in range(6)
        ]

        self.assertEqual(
            sequence,
            [bundle1.id, bundle2.id, bundle3.id, bundle1.id, bundle2.id, bundle3.id],
        )

    def test_resolve_llm_config_raises_when_no_bundle_available(self):
        with self.assertRaises(LLMConfigResolutionError):
            resolve_llm_config(user=self.owner, module_key="llm_chat")

    def test_runtime_current_endpoint_returns_404_when_no_bundle_available(self):
        response = self.client.get(
            reverse("llmconfigbundle-runtime-current"),
            {"module_key": "llm_chat"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], "当前没有可用的 LLM 配置")

    def test_runtime_current_endpoint_returns_personal_or_global_resolution(self):
        self._create_bundle(self.owner, "runtime-bundle", is_active=True)

        response = self.client.get(
            reverse("llmconfigbundle-runtime-current"),
            {"module_key": "llm_chat"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["config_name"], "runtime-bundle")
        self.assertEqual(response.data["resolved_source"], "personal_slot")


class ChatSessionAPIViewTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_superuser(
            username="testuser",
            password="password123",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        
        # 导入模型
        from .models import ChatSession
        from projects.models import Project
        
        # 创建项目和会话
        self.project = Project.objects.create(name="Test Project", creator=self.user)
        self.session = ChatSession.objects.create(
            user=self.user,
            session_id="test_session_id_123",
            title="新对话 - 测试",
            project=self.project
        )

    def test_rename_session_success(self):
        url = reverse("user_chat_sessions_api")
        payload = {
            "session_id": "test_session_id_123",
            "title": "更新后的标题",
            "project_id": self.project.id
        }
        response = self.client.put(url, payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["data"]["title"], "更新后的标题")
        
        # 验证数据库是否修改
        self.session.refresh_from_db()
        self.assertEqual(self.session.title, "更新后的标题")

    def test_rename_session_validation_error(self):
        url = reverse("user_chat_sessions_api")
        # 缺失标题
        payload = {
            "session_id": "test_session_id_123",
        }
        response = self.client.put(url, payload, format="json")
        self.assertEqual(response.status_code, 400)

        # 空标题
        payload = {
            "session_id": "test_session_id_123",
            "title": "   "
        }
        response = self.client.put(url, payload, format="json")
        self.assertEqual(response.status_code, 400)

    def test_rename_session_not_found(self):
        url = reverse("user_chat_sessions_api")
        payload = {
            "session_id": "non_existent_id",
            "title": "更新后的标题",
            "project_id": self.project.id
        }
        response = self.client.put(url, payload, format="json")
        self.assertEqual(response.status_code, 404)
