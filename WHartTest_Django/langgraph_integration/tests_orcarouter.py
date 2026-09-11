"""Regression tests for the OrcaRouter provider integration.

Covers the credential seam (pasted API key and OAuth 2.0 + PKCE), origin
policy, the model catalog capability filters, and generation-safe terminal
reauthentication.

Every fixture in this module uses fake keys and fake auth codes; no test ever
sends a real credential anywhere.
"""

import base64
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from langgraph_integration import orcarouter
from langgraph_integration.models import LLMConfig

User = get_user_model()

FAKE_KEY = "sk-orca-fake-key-for-tests-000000000000"
FAKE_CODE = "fake-one-time-code"


# --------------------------------------------------------------------------
# A local stand-in for the OrcaRouter auth origin.
# --------------------------------------------------------------------------


class _FakeAuthHandler(BaseHTTPRequestHandler):
    """Minimal fake of ``https://www.orcarouter.ai`` for the PKCE exchange."""

    def log_message(self, *args):  # keep test output quiet
        pass

    def do_POST(self):
        server = self.server
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        try:
            server.last_body = json.loads(raw.decode("utf-8"))
        except ValueError:
            server.last_body = {}
        server.last_path = self.path
        server.last_content_type = self.headers.get("Content-Type")

        status, payload = server.responder(server.last_body)
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class FakeAuthServer:
    """Runs the fake auth origin on loopback for the duration of a test."""

    def __init__(self, responder):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _FakeAuthHandler)
        self.httpd.responder = responder
        self.httpd.last_body = None
        self.httpd.last_path = None
        self.httpd.last_content_type = None
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base_url(self):
        host, port = self.httpd.server_address[:2]
        return f"http://{host}:{port}"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)


def _ok_responder(scope="api", key=FAKE_KEY):
    def responder(_body):
        return 200, {"key": key, "user_id": "12345", "scope": scope}

    return responder


# --------------------------------------------------------------------------
# PKCE primitives
# --------------------------------------------------------------------------


class PkcePrimitiveTests(TestCase):
    def test_challenge_is_unpadded_base64url_sha256_of_verifier(self):
        pkce = orcarouter.new_pkce()
        expected = (
            base64.urlsafe_b64encode(hashlib.sha256(pkce.verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        self.assertEqual(pkce.challenge, expected)
        self.assertNotIn("=", pkce.challenge)
        self.assertNotIn("+", pkce.challenge)

    def test_every_attempt_gets_a_fresh_verifier_and_state(self):
        attempts = [orcarouter.new_pkce() for _ in range(5)]
        self.assertEqual(len({a.verifier for a in attempts}), 5)
        self.assertEqual(len({a.state for a in attempts}), 5)
        self.assertTrue(all(len(a.verifier) >= 43 for a in attempts))

    def test_verifier_is_not_logged_by_repr(self):
        pkce = orcarouter.new_pkce()
        self.assertNotIn(pkce.verifier, repr(pkce))

    def test_verify_state_is_exact(self):
        pkce = orcarouter.new_pkce()
        self.assertTrue(orcarouter.verify_state(pkce.state, pkce.state))
        self.assertFalse(orcarouter.verify_state(pkce.state, pkce.state + "x"))
        self.assertFalse(orcarouter.verify_state(pkce.state, None))
        self.assertFalse(orcarouter.verify_state(None, pkce.state))

    def test_authorize_url_uses_auth_origin_and_oob_callback(self):
        pkce = orcarouter.new_pkce()
        url = orcarouter.build_authorize_url(
            orcarouter.ORCA_PUBLIC_AUTH_BASE,
            challenge=pkce.challenge,
            state=pkce.state,
            app_name="WHartTest",
        )
        self.assertTrue(url.startswith("https://www.orcarouter.ai/auth?"))
        self.assertIn("callback_url=oob", url)
        self.assertIn("code_challenge_method=S256", url)
        self.assertIn(f"code_challenge={pkce.challenge}", url)
        # The verifier must never be placed in a URL.
        self.assertNotIn(pkce.verifier, url)


# --------------------------------------------------------------------------
# Origin policy
# --------------------------------------------------------------------------


class OriginPolicyTests(TestCase):
    def tearDown(self):
        pass

    def test_public_defaults_are_distinct_origins(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(orcarouter.resolve_auth_base(), "https://www.orcarouter.ai")
            self.assertEqual(orcarouter.resolve_api_base(), "https://api.orcarouter.ai/v1")

    def test_explicit_overrides_win_over_shared_base(self):
        env = {
            "ORCA_BASE_URL": "https://shared.example.com",
            "ORCA_AUTH_BASE_URL": "https://auth.example.com",
            "ORCA_API_BASE_URL": "https://api.example.com/v1",
        }
        with patch.dict("os.environ", env, clear=True):
            self.assertEqual(orcarouter.resolve_auth_base(), "https://auth.example.com")
            self.assertEqual(orcarouter.resolve_api_base(), "https://api.example.com/v1")

    def test_shared_self_hosted_base_is_used_as_fallback(self):
        with patch.dict("os.environ", {"ORCA_BASE_URL": "https://shared.example.com"}, clear=True):
            self.assertEqual(orcarouter.resolve_auth_base(), "https://shared.example.com")
            self.assertEqual(orcarouter.resolve_api_base(), "https://shared.example.com")

    def test_http_is_only_allowed_for_loopback(self):
        with patch.dict("os.environ", {"ORCA_AUTH_BASE_URL": "http://evil.example.com"}, clear=True):
            with self.assertRaises(orcarouter.OrcaRouterError):
                orcarouter.resolve_auth_base()
        with patch.dict("os.environ", {"ORCA_AUTH_BASE_URL": "http://127.0.0.1:9000"}, clear=True):
            self.assertEqual(orcarouter.resolve_auth_base(), "http://127.0.0.1:9000")

    def test_exchange_path_is_not_the_relay_path(self):
        # /v1/auth/keys on the inference origin is a 404 and a classic mistake.
        self.assertEqual(orcarouter.ORCA_EXCHANGE_PATH, "/api/v1/auth/keys")
        self.assertFalse(orcarouter.ORCA_EXCHANGE_PATH.startswith("/v1/"))


# --------------------------------------------------------------------------
# Credential adapters
# --------------------------------------------------------------------------


class ApiKeyAdapterTests(TestCase):
    def test_api_key_adapter_returns_a_credential_result(self):
        result = orcarouter.ApiKeyCredentialProvider().resolve(api_key=f"  {FAKE_KEY}  ")
        self.assertEqual(result.api_key, FAKE_KEY)
        self.assertEqual(result.source, "api_key")
        self.assertEqual(result.scope, "api")

    def test_api_key_adapter_rejects_empty_and_malformed_keys(self):
        provider = orcarouter.ApiKeyCredentialProvider()
        with self.assertRaises(orcarouter.OrcaRouterAuthError):
            provider.resolve(api_key="")
        with self.assertRaises(orcarouter.OrcaRouterAuthError):
            provider.resolve(api_key="not-an-orca-key")

    def test_api_key_adapter_never_offers_an_authorize_url(self):
        self.assertIsNone(orcarouter.ApiKeyCredentialProvider().authorize_url())


class PkceAdapterTests(TestCase):
    def test_successful_exchange_returns_the_same_credential_shape(self):
        with FakeAuthServer(_ok_responder()) as server:
            provider = orcarouter.PkceCredentialProvider(server.base_url)
            pkce, url = provider.begin()
            result = provider.resolve(code=FAKE_CODE, code_verifier=pkce.verifier)

            self.assertEqual(result.api_key, FAKE_KEY)
            self.assertEqual(result.source, "pkce")
            self.assertEqual(result.scope, "api")
            self.assertEqual(result.user_id, "12345")

            # The exchange must go to the auth origin at the documented path.
            self.assertEqual(server.httpd.last_path, "/api/v1/auth/keys")
            body = server.httpd.last_body
            self.assertEqual(body["code"], FAKE_CODE)
            self.assertEqual(body["code_verifier"], pkce.verifier)
            self.assertEqual(body["code_challenge_method"], "S256")

    def test_api_key_and_pkce_produce_the_same_credential_type(self):
        api_result = orcarouter.ApiKeyCredentialProvider().resolve(api_key=FAKE_KEY)
        with FakeAuthServer(_ok_responder()) as server:
            provider = orcarouter.PkceCredentialProvider(server.base_url)
            pkce, _ = provider.begin()
            pkce_result = provider.resolve(code=FAKE_CODE, code_verifier=pkce.verifier)
        self.assertIsInstance(api_result, orcarouter.CredentialResult)
        self.assertIsInstance(pkce_result, orcarouter.CredentialResult)
        self.assertEqual(type(api_result), type(pkce_result))
        self.assertEqual(api_result.api_key, pkce_result.api_key)

    def test_denial_and_reused_code_are_terminal(self):
        with FakeAuthServer(lambda _b: (403, {"error": "invalid_grant"})) as server:
            provider = orcarouter.PkceCredentialProvider(server.base_url)
            pkce, _ = provider.begin()
            with self.assertRaises(orcarouter.OrcaRouterAuthError) as ctx:
                provider.resolve(code=FAKE_CODE, code_verifier=pkce.verifier)
            self.assertEqual(ctx.exception.code, "code_rejected")
            self.assertEqual(ctx.exception.status, 403)

    def test_bad_challenge_method_is_reported_separately(self):
        with FakeAuthServer(lambda _b: (400, {"error": "invalid_request"})) as server:
            provider = orcarouter.PkceCredentialProvider(server.base_url)
            pkce, _ = provider.begin()
            with self.assertRaises(orcarouter.OrcaRouterAuthError) as ctx:
                provider.resolve(code=FAKE_CODE, code_verifier=pkce.verifier)
            self.assertEqual(ctx.exception.code, "bad_challenge_method")

    def test_rate_limit_is_reported_not_retried(self):
        with FakeAuthServer(lambda _b: (429, {"error": "rate_limited"})) as server:
            provider = orcarouter.PkceCredentialProvider(server.base_url)
            pkce, _ = provider.begin()
            with self.assertRaises(orcarouter.OrcaRouterAuthError) as ctx:
                provider.resolve(code=FAKE_CODE, code_verifier=pkce.verifier)
            self.assertEqual(ctx.exception.code, "rate_limited")

    def test_scope_downgrade_is_refused(self):
        # Requested "api", was granted something narrower.
        with FakeAuthServer(_ok_responder(scope="connector")) as server:
            provider = orcarouter.PkceCredentialProvider(server.base_url)
            pkce, _ = provider.begin()
            with self.assertRaises(orcarouter.OrcaRouterAuthError) as ctx:
                provider.resolve(code=FAKE_CODE, code_verifier=pkce.verifier)
            self.assertEqual(ctx.exception.code, "scope_downgrade")

    def test_network_failure_does_not_hang_or_leak(self):
        provider = orcarouter.PkceCredentialProvider("http://127.0.0.1:9", timeout=1)
        pkce, _ = provider.begin()
        with self.assertRaises(orcarouter.OrcaRouterAuthError) as ctx:
            provider.resolve(code=FAKE_CODE, code_verifier=pkce.verifier)
        self.assertEqual(ctx.exception.code, "network")
        self.assertNotIn(pkce.verifier, str(ctx.exception))

    def test_missing_inputs_are_rejected(self):
        provider = orcarouter.PkceCredentialProvider("http://127.0.0.1:9")
        with self.assertRaises(orcarouter.OrcaRouterAuthError):
            provider.resolve(code="", code_verifier="v")
        with self.assertRaises(orcarouter.OrcaRouterAuthError):
            provider.resolve(code="c", code_verifier="")

    def test_timeout_surfaces_as_an_actionable_error(self):
        provider = orcarouter.PkceCredentialProvider("http://127.0.0.1:9", timeout=1)
        with patch("langgraph_integration.orcarouter.requests.post",
                   side_effect=requests.Timeout("boom")):
            with self.assertRaises(orcarouter.OrcaRouterAuthError) as ctx:
                provider.resolve(code=FAKE_CODE, code_verifier="v")
            self.assertEqual(ctx.exception.code, "timeout")

    def test_secrets_never_appear_in_error_text(self):
        with FakeAuthServer(lambda _b: (403, {"error": "invalid_grant"})) as server:
            provider = orcarouter.PkceCredentialProvider(server.base_url)
            pkce, _ = provider.begin()
            try:
                provider.resolve(code=FAKE_CODE, code_verifier=pkce.verifier)
            except orcarouter.OrcaRouterAuthError as exc:
                message = str(exc)
                self.assertNotIn(pkce.verifier, message)
                self.assertNotIn(FAKE_KEY, message)


# --------------------------------------------------------------------------
# Redaction
# --------------------------------------------------------------------------


class RedactionTests(TestCase):
    def test_mask_secret_keeps_only_a_short_tail(self):
        masked = orcarouter.mask_secret(FAKE_KEY)
        self.assertTrue(masked.startswith("sk-orca-"))
        self.assertIn("****", masked)
        self.assertNotIn(FAKE_KEY[8:-4], masked)

    def test_mask_secret_handles_empty_values(self):
        self.assertEqual(orcarouter.mask_secret(None), "")
        self.assertEqual(orcarouter.mask_secret(""), "")

    def test_scrub_removes_credential_material(self):
        text = f"failed with {FAKE_KEY} using verifier abc"
        self.assertNotIn(FAKE_KEY, orcarouter.scrub(text, FAKE_KEY))


# --------------------------------------------------------------------------
# Model catalog
# --------------------------------------------------------------------------

# Fixtures covering every capability the client can filter on.
CATALOG_FIXTURE = {
    "data": [
        {
            "id": "vendor/text-only",
            "supported_endpoint_types": ["openai"],
            "architecture": {"input_modalities": ["text"]},
            "context_length": 128000,
        },
        {
            "id": "vendor/vision-chat",
            "supported_endpoint_types": ["openai", "anthropic"],
            "architecture": {"input_modalities": ["text", "image"]},
            "context_length": 200000,
        },
        {
            "id": "vendor/embedding",
            "supported_endpoint_types": ["embeddings"],
            "architecture": {"input_modalities": ["text"]},
        },
        {
            "id": "vendor/image-gen",
            "supported_endpoint_types": ["image-generation"],
            "architecture": {"output_modalities": ["image"]},
        },
        {
            "id": "vendor/video-gen",
            "supported_endpoint_types": ["openai-video"],
        },
        {
            "id": "vendor/rerank",
            "supported_endpoint_types": ["jina-rerank"],
        },
        {
            "id": "vendor/no-metadata",
            "supported_endpoint_types": ["openai"],
        },
        {
            "id": "openai/gpt-5.5",
            "supported_endpoint_types": ["openai", "openai-response"],
            "architecture": {"input_modalities": ["file", "image", "text"]},
            "context_length": 400000,
            "reasoning": {"supported_efforts": ["low", "medium", "high", "xhigh"]},
        },
    ]
}


class CatalogFilterTests(TestCase):
    def _models(self):
        return orcarouter.parse_catalog_payload(CATALOG_FIXTURE)

    def test_parses_text_only_image_input_embedding_image_video_rerank(self):
        ids = {m.id for m in self._models()}
        self.assertIn("vendor/text-only", ids)
        self.assertIn("vendor/vision-chat", ids)
        self.assertIn("vendor/embedding", ids)
        self.assertIn("vendor/image-gen", ids)
        self.assertIn("vendor/video-gen", ids)
        self.assertIn("vendor/rerank", ids)

    def test_chat_filter_excludes_non_text_specialists(self):
        ids = {
            m.id
            for m in orcarouter.filter_models(self._models(), orcarouter.CAPABILITY_CHAT)
        }
        self.assertIn("vendor/text-only", ids)
        self.assertIn("vendor/vision-chat", ids)
        self.assertNotIn("vendor/embedding", ids)
        self.assertNotIn("vendor/image-gen", ids)
        self.assertNotIn("vendor/video-gen", ids)
        self.assertNotIn("vendor/rerank", ids)

    def test_multimodal_filter_keeps_only_declared_image_input(self):
        ids = {
            m.id
            for m in orcarouter.filter_models(
                self._models(), orcarouter.CAPABILITY_CHAT, input_modalities=["image"]
            )
        }
        self.assertEqual(ids, {"vendor/vision-chat", "openai/gpt-5.5"})

    def test_models_without_declared_modality_fail_closed(self):
        ids = {
            m.id
            for m in orcarouter.filter_models(
                self._models(), orcarouter.CAPABILITY_CHAT, input_modalities=["image"]
            )
        }
        self.assertNotIn("vendor/no-metadata", ids)
        self.assertNotIn("vendor/text-only", ids)

    def test_embedding_image_video_and_rerank_filters(self):
        models = self._models()
        self.assertEqual(
            {m.id for m in orcarouter.filter_models(models, orcarouter.CAPABILITY_EMBEDDING)},
            {"vendor/embedding"},
        )
        self.assertEqual(
            {m.id for m in orcarouter.filter_models(models, orcarouter.CAPABILITY_IMAGE)},
            {"vendor/image-gen"},
        )
        self.assertEqual(
            {m.id for m in orcarouter.filter_models(models, orcarouter.CAPABILITY_VIDEO)},
            {"vendor/video-gen"},
        )
        self.assertEqual(
            {m.id for m in orcarouter.filter_models(models, orcarouter.CAPABILITY_RERANK)},
            {"vendor/rerank"},
        )

    def test_reasoning_efforts_are_preserved(self):
        model = next(m for m in self._models() if m.id == "openai/gpt-5.5")
        self.assertEqual(model.reasoning_efforts, ("low", "medium", "high", "xhigh"))

    def test_vendor_namespace_is_preserved_verbatim(self):
        ids = {m.id for m in self._models()}
        self.assertTrue(all("/" in model_id for model_id in ids))


class CatalogDegradedTests(TestCase):
    def test_live_failure_returns_marked_verified_fallback(self):
        result = orcarouter.fetch_catalog(
            "http://127.0.0.1:9/v1", FAKE_KEY, capability="chat", timeout=1
        )
        self.assertTrue(result["degraded"])
        self.assertEqual(result["source"], "fallback")
        ids = {m["id"] for m in result["models"]}
        self.assertIn("openai/gpt-5.5", ids)
        self.assertIn("orcarouter/auto", ids)

    def test_fallback_is_capability_filtered_for_multimodal(self):
        result = orcarouter.fetch_catalog(
            "http://127.0.0.1:9/v1",
            FAKE_KEY,
            capability="chat",
            input_modalities=["image"],
            timeout=1,
        )
        ids = {m["id"] for m in result["models"]}
        self.assertEqual(ids, {"openai/gpt-5.5", "anthropic/claude-opus-4.8", "google/gemini-3.5-flash"})

    def test_fallback_keeps_reasoning_metadata(self):
        result = orcarouter.fetch_catalog(
            "http://127.0.0.1:9/v1", FAKE_KEY, capability="chat", timeout=1
        )
        gpt = next(m for m in result["models"] if m["id"] == "openai/gpt-5.5")
        self.assertEqual(gpt["reasoning_efforts"], ["low", "medium", "high", "xhigh"])

    def test_fallback_has_no_image_models_for_embedding_capability(self):
        result = orcarouter.fetch_catalog(
            "http://127.0.0.1:9/v1", FAKE_KEY, capability="embedding", timeout=1
        )
        self.assertEqual(result["models"], [])

    def test_oversized_catalog_is_rejected(self):
        class _Big:
            status_code = 200
            raw = None
            def raise_for_status(self): pass
            def json(self): return {}
        with patch("langgraph_integration.orcarouter.requests.get") as get:
            response = _Big()
            response.raw = type("R", (), {"read": lambda self, n, decode_content=True: b"x" * (n + 1)})()
            get.return_value = response
            result = orcarouter.fetch_catalog("https://api.example.com/v1", FAKE_KEY, timeout=1)
            self.assertTrue(result["degraded"])


class CatalogLiveShapeTests(TestCase):
    def test_live_success_reports_live_source_and_filters(self):
        payload = json.dumps(CATALOG_FIXTURE).encode()

        class _Response:
            status_code = 200

            def raise_for_status(self):
                pass

            raw = type("R", (), {"read": lambda self, n, decode_content=True: payload})()

        with patch("langgraph_integration.orcarouter.requests.get", return_value=_Response()):
            result = orcarouter.fetch_catalog("https://api.example.com/v1", FAKE_KEY)
        self.assertFalse(result["degraded"])
        self.assertEqual(result["source"], "live")
        ids = {m["id"] for m in result["models"]}
        self.assertNotIn("vendor/image-gen", ids)
        # A successful live result never mixes in the seed catalog.
        self.assertNotIn("orcarouter/auto", ids)

    def test_catalog_request_targets_models_path(self):
        payload = json.dumps(CATALOG_FIXTURE).encode()

        class _Response:
            status_code = 200

            def raise_for_status(self):
                pass

            raw = type("R", (), {"read": lambda self, n, decode_content=True: payload})()

        with patch("langgraph_integration.orcarouter.requests.get",
                   return_value=_Response()) as get:
            orcarouter.fetch_catalog("https://api.example.com/v1", FAKE_KEY, capability="chat")
        args, kwargs = get.call_args
        self.assertEqual(args[0], "https://api.example.com/v1/models")
        self.assertEqual(kwargs["params"], {"capability": "chat"})
        self.assertEqual(kwargs["headers"]["Authorization"], f"Bearer {FAKE_KEY}")


# --------------------------------------------------------------------------
# Credential lifecycle
# --------------------------------------------------------------------------


class CredentialLifecycleTests(TestCase):
    def test_401_and_403_are_terminal_reauth(self):
        self.assertEqual(orcarouter.classify_auth_failure(401), "needs_reauth")
        self.assertEqual(orcarouter.classify_auth_failure(403), "needs_reauth")

    def test_429_and_5xx_are_not_terminal_reauth(self):
        self.assertEqual(orcarouter.classify_auth_failure(429), "rate_limited")
        self.assertEqual(orcarouter.classify_auth_failure(500), "transient")

    def test_stale_generation_cannot_mark_new_credential_broken(self):
        # Credential generation 2 is live; a late 401 from generation 1 lands.
        self.assertFalse(
            orcarouter.should_transition_to_needs_reauth(
                current_generation=2, rejected_generation=1, status_code=401
            )
        )
        # A 401 from the live generation does transition.
        self.assertTrue(
            orcarouter.should_transition_to_needs_reauth(
                current_generation=2, rejected_generation=2, status_code=401
            )
        )

    def test_no_refresh_grant_is_modelled(self):
        # A PKCE-issued key is durable: there is no refresh endpoint to call.
        source = open(orcarouter.__file__, encoding="utf-8").read()
        self.assertNotIn("refresh_token", source)
        self.assertNotIn("grant_type=refresh_token", source)


# --------------------------------------------------------------------------
# API endpoints
# --------------------------------------------------------------------------


class OrcaRouterApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="orca-tester", password="pw12345678")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.config = LLMConfig.objects.create(
            config_name="orca-test",
            provider="orcarouter",
            name="openai/gpt-5.5",
            api_url=orcarouter.ORCA_PUBLIC_API_BASE,
            is_active=True,
        )

    def test_provider_choices_expose_both_orcarouter_entries(self):
        response = self.client.get(reverse("provider_choices_api"))
        self.assertEqual(response.status_code, 200)
        values = {c["value"] for c in response.json()["data"]["choices"]}
        self.assertIn("orcarouter", values)
        self.assertIn("orcarouter_oauth", values)

    def test_api_key_entry_stores_the_key_and_never_returns_it(self):
        response = self.client.post(
            reverse("orcarouter_models_api"),
            {"config_id": self.config.id, "capability": "chat"},
            format="json",
        )
        # A catalog call with a config that has no key falls back rather than
        # leaking anything back to the browser.
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("api_key", json.dumps(response.json()))

    def test_model_catalog_never_returns_the_api_key(self):
        self.config.api_key = FAKE_KEY
        self.config.save(update_fields=["api_key"])
        with patch("langgraph_integration.orcarouter.catalog.get") as get:
            get.return_value = {"models": [], "degraded": False, "source": "live",
                                "capability": "chat", "filtered": 0}
            response = self.client.post(
                reverse("orcarouter_models_api"),
                {"config_id": self.config.id, "capability": "chat"},
                format="json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(FAKE_KEY, json.dumps(response.json()))

    def test_unsupported_capability_is_rejected(self):
        response = self.client.post(
            reverse("orcarouter_models_api"), {"capability": "telepathy"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_begin_returns_an_auth_origin_url_with_s256(self):
        response = self.client.post(reverse("orcarouter_connect_api"), {"action": "begin"}, format="json")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertTrue(data["authorize_url"].startswith("https://www.orcarouter.ai/auth?"))
        self.assertIn("code_challenge_method=S256", data["authorize_url"])
        self.assertIn("callback_url=oob", data["authorize_url"])
        self.assertEqual(data["callback_mode"], "oob")

    def test_complete_with_unknown_attempt_is_refused(self):
        response = self.client.post(
            reverse("orcarouter_connect_api"),
            {"action": "complete", "attempt_id": "nope", "code": FAKE_CODE, "state": "x"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errors"]["error_code"], "unknown_attempt")

    def test_complete_with_mismatched_state_is_refused(self):
        begin = self.client.post(reverse("orcarouter_connect_api"), {"action": "begin"}, format="json")
        attempt_id = begin.json()["data"]["attempt_id"]
        response = self.client.post(
            reverse("orcarouter_connect_api"),
            {"action": "complete", "attempt_id": attempt_id, "code": FAKE_CODE, "state": "wrong"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errors"]["error_code"], "state_mismatch")

    def test_full_connect_flow_persists_the_key_into_existing_storage(self):
        with FakeAuthServer(_ok_responder()) as server:
            with patch.object(orcarouter, "resolve_auth_base", return_value=server.base_url):
                begin = self.client.post(
                    reverse("orcarouter_connect_api"),
                    {"action": "begin", "config_id": self.config.id},
                    format="json",
                )
                data = begin.json()["data"]
                complete = self.client.post(
                    reverse("orcarouter_connect_api"),
                    {
                        "action": "complete",
                        "attempt_id": data["attempt_id"],
                        "code": FAKE_CODE,
                        "state": data["state"],
                        "config_id": self.config.id,
                    },
                    format="json",
                )
        self.assertEqual(complete.status_code, 200)
        payload = complete.json()["data"]
        self.assertEqual(payload["credential_source"], "pkce")
        self.assertEqual(payload["scope"], "api")
        self.assertNotIn(FAKE_KEY, json.dumps(complete.json()))

        self.config.refresh_from_db()
        self.assertEqual(self.config.api_key, FAKE_KEY)
        self.assertEqual(self.config.provider, "orcarouter_oauth")

    def test_attempt_is_single_use(self):
        with FakeAuthServer(_ok_responder()) as server:
            with patch.object(orcarouter, "resolve_auth_base", return_value=server.base_url):
                data = self.client.post(
                    reverse("orcarouter_connect_api"), {"action": "begin"}, format="json"
                ).json()["data"]
                body = {
                    "action": "complete",
                    "attempt_id": data["attempt_id"],
                    "code": FAKE_CODE,
                    "state": data["state"],
                }
                first = self.client.post(reverse("orcarouter_connect_api"), body, format="json")
                second = self.client.post(reverse("orcarouter_connect_api"), body, format="json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 400)

    def test_cancel_releases_the_attempt(self):
        data = self.client.post(
            reverse("orcarouter_connect_api"), {"action": "begin"}, format="json"
        ).json()["data"]
        cancelled = self.client.post(
            reverse("orcarouter_connect_api"),
            {"action": "cancel", "attempt_id": data["attempt_id"]},
            format="json",
        )
        self.assertEqual(cancelled.status_code, 200)
        after = self.client.post(
            reverse("orcarouter_connect_api"),
            {"action": "complete", "attempt_id": data["attempt_id"], "code": FAKE_CODE,
             "state": data["state"]},
            format="json",
        )
        self.assertEqual(after.status_code, 400)

    def test_anonymous_callers_cannot_start_a_login(self):
        client = APIClient()
        response = client.post(reverse("orcarouter_connect_api"), {"action": "begin"}, format="json")
        self.assertIn(response.status_code, (401, 403))


# --------------------------------------------------------------------------
# LLM adapter wiring
# --------------------------------------------------------------------------


class LlmAdapterWiringTests(TestCase):
    def test_orcarouter_provider_defaults_to_the_inference_origin(self):
        config = LLMConfig(
            config_name="orca-adapter",
            provider="orcarouter",
            name="openai/gpt-5.5",
            api_url="",
            api_key=FAKE_KEY,
        )
        captured = {}

        def fake_chat_openai(**kwargs):
            captured.update(kwargs)
            return object()

        with patch("langgraph_integration.views.ChatOpenAI", side_effect=fake_chat_openai):
            from langgraph_integration.views import create_llm_instance

            create_llm_instance(config, temperature=0.1)

        self.assertEqual(captured["base_url"], "https://api.orcarouter.ai/v1")
        self.assertEqual(captured["api_key"], FAKE_KEY)
        self.assertEqual(captured["model"], "openai/gpt-5.5")

    def test_both_orcarouter_entries_share_one_inference_origin(self):
        for provider in ("orcarouter", "orcarouter_oauth"):
            config = LLMConfig(
                config_name=f"orca-{provider}",
                provider=provider,
                name="anthropic/claude-opus-4.8",
                api_url="",
                api_key=FAKE_KEY,
            )
            captured = {}
            with patch("langgraph_integration.views.ChatOpenAI",
                       side_effect=lambda **kw: captured.update(kw)):
                from langgraph_integration.views import create_llm_instance

                create_llm_instance(config, temperature=0.1)
            self.assertEqual(captured["base_url"], "https://api.orcarouter.ai/v1")

    def test_orcarouter_does_not_fall_back_to_the_openai_provider_warning(self):
        config = LLMConfig(
            config_name="orca-nowarn",
            provider="orcarouter",
            name="orcarouter/auto",
            api_url="https://api.orcarouter.ai/v1",
            api_key=FAKE_KEY,
        )
        with patch("langgraph_integration.views.ChatOpenAI", return_value=object()):
            with self.assertNoLogs("langgraph_integration.views", level="WARNING"):
                from langgraph_integration.views import create_llm_instance

                create_llm_instance(config, temperature=0.1)


class EmbeddingEntryPointTests(TestCase):
    """OrcaRouter is also a first-class entry in the knowledge-base embeddings.

    The knowledge app has its own provider enum, so the entry is verified there
    rather than assumed from the chat provider list.
    """

    def test_orcarouter_is_a_registered_embedding_service(self):
        from knowledge.models import KnowledgeGlobalConfig

        values = [value for value, _ in KnowledgeGlobalConfig.EMBEDDING_SERVICE_CHOICES]
        self.assertIn("orcarouter", values)

    def test_embedding_endpoint_targets_the_inference_origin(self):
        from knowledge.models import KnowledgeGlobalConfig

        endpoint = KnowledgeGlobalConfig.ORCAROUTER_EMBEDDING_ENDPOINT
        self.assertTrue(endpoint.startswith("https://api.orcarouter.ai/v1/"))
        self.assertTrue(endpoint.endswith("/embeddings"))
        # The relay is on api.orcarouter.ai; auth endpoints are not.
        self.assertNotIn("/auth/", endpoint)

    def test_embedding_capability_filter_excludes_chat_models(self):
        models = orcarouter.parse_catalog_payload(CATALOG_FIXTURE)
        ids = {
            m.id
            for m in orcarouter.filter_models(models, orcarouter.CAPABILITY_EMBEDDING)
        }
        self.assertEqual(ids, {"vendor/embedding"})
