"""OrcaRouter provider integration for WHartTest.

This module is the single place that knows how to talk to OrcaRouter:

- credential acquisition (a pasted API key, or an OAuth 2.0 + PKCE login)
- the model catalog used to build capability-filtered model pickers

Both credential paths are adapters on one small ``CredentialProvider``
interface and both yield the same :class:`CredentialResult`, so the LLM
adapter and the model discovery code below never need to know where a
credential came from.

Origins are deliberately separate: authentication lives on
``https://www.orcarouter.ai`` (its API endpoints are under ``/api/v1/auth``)
while inference and model discovery live on ``https://api.orcarouter.ai/v1``.
Note that ``https://api.orcarouter.ai/v1/auth/keys`` is a 404 -- the auth
endpoints are not on the relay.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Protocol, Sequence

import requests

logger = logging.getLogger(__name__)

# --- Public origins -------------------------------------------------------
# Authentication and inference use different public origins. Never derive one
# from the other by swapping a hostname or blindly appending ``/v1``.
ORCA_PUBLIC_AUTH_BASE = "https://www.orcarouter.ai"
ORCA_PUBLIC_API_BASE = "https://api.orcarouter.ai/v1"

# Paths are fixed by the protocol.
ORCA_AUTHORIZE_PATH = "/auth"
ORCA_EXCHANGE_PATH = "/api/v1/auth/keys"
ORCA_MODELS_PATH = "/models"

# OAuth scope this integration needs: plain inference access.
ORCA_REQUIRED_SCOPE = "api"

ORCA_PROVIDER_ID = "orcarouter"
ORCA_OAUTH_PROVIDER_ID = "orcarouter_oauth"
ORCA_DISPLAY_NAME = "OrcaRouter"
ORCA_OAUTH_DISPLAY_NAME = "OrcaRouter - Auth"
ORCA_API_DISPLAY_NAME = "OrcaRouter - API"

# Console link shown next to the API-key entry.
ORCA_KEY_DASHBOARD_URL = "https://www.orcarouter.ai/console/authorized-apps"
ORCA_LOGO_URL = "https://www.orcarouter.ai/orca-logo-classic.png"

# Lightweight format check only -- an ``sk-orca-`` prefix is not proof that a
# credential is valid, so we never spend a paid inference request to "verify".
ORCA_KEY_PREFIX = "sk-orca-"

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1"}

# Catalog requests are bounded so a hostile or broken catalog response cannot
# consume unbounded memory.
CATALOG_TIMEOUT_SECONDS = 15
CATALOG_DETAIL_TIMEOUT_SECONDS = 8
CATALOG_MAX_BYTES = 2_000_000
CATALOG_MAX_ITEMS = 2000
# Enrichment reads one detail record per model; bounded so a slow catalog
# cannot hold a request open.
CATALOG_ENRICH_WORKERS = 12
CATALOG_ENRICH_BUDGET_SECONDS = 20.0
CATALOG_CACHE_TTL_SECONDS = 300

# Endpoint types the client can actually speak for plain text chat.
CHAT_ENDPOINT_TYPES = {"openai", "anthropic", "gemini", "openai-response"}
# Endpoint types that are never usable for a text chat turn, even if a model
# advertises a chat capability.
NON_CHAT_ENDPOINT_TYPES = {"image-generation", "openai-video", "jina-rerank"}

CAPABILITY_CHAT = "chat"
CAPABILITY_EMBEDDING = "embedding"
CAPABILITY_IMAGE = "image"
CAPABILITY_VIDEO = "video"
CAPABILITY_RERANK = "rerank"

MODALITY_IMAGE = "image"
MODALITY_AUDIO = "audio"
MODALITY_VIDEO = "video"
MODALITY_TEXT = "text"


class OrcaRouterError(Exception):
    """Base class for OrcaRouter failures that are safe to show to a user."""

    def __init__(self, message: str, *, status: int | None = None, code: str = "error"):
        super().__init__(message)
        self.status = status
        self.code = code


class OrcaRouterAuthError(OrcaRouterError):
    """A credential could not be obtained or is no longer usable."""


class OrcaRouterCatalogError(OrcaRouterError):
    """The live model catalog could not be read."""


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


# --- Origin resolution ----------------------------------------------------


def validate_origin(value: str, *, what: str) -> str:
    """Require HTTPS for non-loopback origins; permit HTTP only on loopback."""
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in ("http", "https"):
        raise OrcaRouterError(f"{what} must be an absolute http(s) URL", code="bad_origin")
    if parsed.scheme == "http" and (parsed.hostname or "") not in _LOOPBACK_HOSTS:
        raise OrcaRouterError(
            f"{what} must use HTTPS unless it points at loopback", code="insecure_origin"
        )
    return value.rstrip("/")


def resolve_auth_base() -> str:
    """Auth origin. Explicit override wins over the shared self-hosted base."""
    raw = (
        os.environ.get("ORCA_AUTH_BASE_URL")
        or os.environ.get("ORCA_BASE_URL")
        or ORCA_PUBLIC_AUTH_BASE
    )
    return validate_origin(raw.strip(), what="ORCA_AUTH_BASE_URL")


def resolve_api_base() -> str:
    """Inference origin (already includes ``/v1``)."""
    raw = (
        os.environ.get("ORCA_API_BASE_URL")
        or os.environ.get("ORCA_BASE_URL")
        or ORCA_PUBLIC_API_BASE
    )
    return validate_origin(raw.strip(), what="ORCA_API_BASE_URL")


def default_api_base_for_auth_base(auth_base: str) -> str:
    """Fallback inference base when only a shared self-hosted origin is set."""
    if auth_base.rstrip("/") == ORCA_PUBLIC_AUTH_BASE:
        return ORCA_PUBLIC_API_BASE
    return auth_base.rstrip("/") + "/v1"


# --- PKCE -----------------------------------------------------------------


@dataclass(frozen=True)
class PkceChallenge:
    """A fresh PKCE attempt. The verifier must not leave the process."""

    verifier: str
    challenge: str
    state: str

    def __repr__(self) -> str:  # pragma: no cover - defensive, keeps secrets out
        return "PkceChallenge(verifier=<redacted>, challenge=%s, state=%s)" % (
            self.challenge,
            self.state,
        )


def generate_verifier() -> str:
    """Fresh 256-bit verifier from a cryptographic RNG."""
    return _b64url(secrets.token_bytes(32))


def challenge_for(verifier: str) -> str:
    """``base64url(sha256(verifier))`` with no padding."""
    return _b64url(hashlib.sha256(verifier.encode("ascii")).digest())


def generate_state() -> str:
    return _b64url(secrets.token_bytes(16))


def verify_state(expected: str | None, received: str | None) -> bool:
    """Constant-time comparison of the CSRF token sent with an authorization.

    Flow B has no redirect for the consent screen to echo ``state`` back on,
    but the client still returns the value it was given, so a code pasted into
    the wrong login can never be redeemed against another attempt.
    """
    if not expected or not received:
        return False
    return hmac.compare_digest(str(expected), str(received))


def new_pkce() -> PkceChallenge:
    """A fresh verifier/state for every authorization attempt."""
    verifier = generate_verifier()
    return PkceChallenge(verifier=verifier, challenge=challenge_for(verifier), state=generate_state())


def build_authorize_url(
    auth_base: str,
    *,
    challenge: str,
    state: str,
    app_name: str,
    callback_url: str = "oob",
    scope: str = ORCA_REQUIRED_SCOPE,
) -> str:
    """Build the consent-screen URL.

    ``S256`` is always sent: even with a real callback URL the user may pick
    "show me a code" on the consent screen, and a code that passes through
    human hands must be redeemable only by the process holding the verifier.
    """
    params = {
        "callback_url": callback_url,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "app_name": app_name,
        "scope": scope,
    }
    return "%s%s?%s" % (
        auth_base.rstrip("/"),
        ORCA_AUTHORIZE_PATH,
        urllib.parse.urlencode(params),
    )


# --- Credential seam ------------------------------------------------------


@dataclass(frozen=True)
class CredentialResult:
    """What every credential adapter produces.

    Downstream consumers (the LLM adapter, model discovery) only ever see this
    object, so they cannot depend on *how* the credential was obtained.
    """

    api_key: str
    scope: str
    source: str
    user_id: str | None = None
    account_ref: str | None = None
    generation: int = 0
    extra: Mapping[str, Any] = field(default_factory=dict)


class CredentialProvider(Protocol):
    """One way of obtaining an OrcaRouter credential."""

    source: str

    def authorize_url(self) -> str | None:
        """URL the user must visit, or ``None`` when nothing to visit."""

    def resolve(self, **payload: Any) -> CredentialResult:
        """Turn whatever this adapter collected into a credential."""


class ApiKeyCredentialProvider:
    """Adapter for a key the user already holds and typed/pasted themselves."""

    source = "api_key"

    def authorize_url(self) -> str | None:
        return None

    def resolve(self, **payload: Any) -> CredentialResult:
        raw_key = (payload.get("api_key") or "").strip()
        if not raw_key:
            raise OrcaRouterAuthError("OrcaRouter API key is required", code="missing_key")
        if not raw_key.startswith(ORCA_KEY_PREFIX):
            raise OrcaRouterAuthError(
                f"OrcaRouter API keys start with {ORCA_KEY_PREFIX}", code="bad_key_format"
            )
        return CredentialResult(
            api_key=raw_key, scope=ORCA_REQUIRED_SCOPE, source=self.source
        )


class PkceCredentialProvider:
    """Adapter for "Connect with OrcaRouter" (OAuth 2.0 + PKCE, Flow B).

    Flow B (out-of-band code) is used because WHartTest is self-hosted and its
    install address differs on every deployment, and because the browser that
    approves the request is not necessarily on the machine running Django --
    a loopback listener here would often be unreachable. The consent screen
    shows the code and the user pastes it back.
    """

    source = "pkce"

    def __init__(self, auth_base: str, *, app_name: str = "WHartTest", timeout: int = 30):
        self.auth_base = auth_base
        self.app_name = app_name
        self.timeout = timeout

    def authorize_url(self) -> str | None:
        raise NotImplementedError("use begin() to obtain a fresh PKCE attempt")

    def begin(self) -> tuple[PkceChallenge, str]:
        """Create a fresh attempt and return ``(pkce, authorize_url)``."""
        pkce = new_pkce()
        url = build_authorize_url(
            self.auth_base,
            challenge=pkce.challenge,
            state=pkce.state,
            app_name=self.app_name,
            callback_url="oob",
        )
        return pkce, url

    def resolve(self, **payload: Any) -> CredentialResult:
        """Exchange the displayed code for a durable API key."""
        code = (payload.get("code") or "").strip()
        verifier = payload.get("code_verifier") or ""
        if not code:
            raise OrcaRouterAuthError("Authorization code is required", code="missing_code")
        if not verifier:
            raise OrcaRouterAuthError("Missing code verifier", code="missing_verifier")

        url = "%s%s" % (self.auth_base.rstrip("/"), ORCA_EXCHANGE_PATH)
        body = {
            "code": code,
            "code_verifier": verifier,
            "code_challenge_method": "S256",
        }
        try:
            response = requests.post(url, json=body, timeout=self.timeout)
        except requests.Timeout as exc:
            raise OrcaRouterAuthError(
                "Timed out contacting OrcaRouter. Check your network and try again.",
                code="timeout",
            ) from exc
        except requests.RequestException as exc:
            raise OrcaRouterAuthError(
                f"Could not reach OrcaRouter: {type(exc).__name__}", code="network"
            ) from exc

        status = response.status_code
        if status == 400:
            raise OrcaRouterAuthError(
                "OrcaRouter rejected the code challenge method. Please retry the login.",
                status=status,
                code="bad_challenge_method",
            )
        if status == 403:
            raise OrcaRouterAuthError(
                "This authorization code is unknown, expired, or already used. "
                "Start the login again.",
                status=status,
                code="code_rejected",
            )
        if status == 429:
            raise OrcaRouterAuthError(
                "Too many OrcaRouter logins in the last 24 hours. "
                "Use an existing API key or try again later.",
                status=status,
                code="rate_limited",
            )
        if status >= 400:
            raise OrcaRouterAuthError(
                f"OrcaRouter login failed (HTTP {status}).", status=status, code="exchange_failed"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise OrcaRouterAuthError(
                "OrcaRouter returned an unreadable response.", code="bad_response"
            ) from exc

        key = (data.get("key") or "").strip()
        if not key:
            raise OrcaRouterAuthError(
                "OrcaRouter did not return a key for this authorization.", code="no_key"
            )

        # The response reports what was *granted*, not what we asked for.
        granted_scope = (data.get("scope") or "").strip()
        if granted_scope != ORCA_REQUIRED_SCOPE:
            raise OrcaRouterAuthError(
                f"OrcaRouter granted scope '{granted_scope or 'unknown'}', but this integration "
                f"needs '{ORCA_REQUIRED_SCOPE}'. Ask a workspace admin for access.",
                code="scope_downgrade",
            )

        user_id = data.get("user_id")
        return CredentialResult(
            api_key=key,
            scope=granted_scope,
            source=self.source,
            user_id=str(user_id) if user_id is not None else None,
            account_ref=str(user_id) if user_id is not None else None,
        )


def credential_provider_for_source(source: str, auth_base: str | None = None) -> CredentialProvider:
    """Factory used by the API layer so both entries share one seam."""
    if source == "pkce":
        return PkceCredentialProvider(auth_base or resolve_auth_base())
    if source == "api_key":
        return ApiKeyCredentialProvider()
    raise OrcaRouterError(f"Unknown credential source '{source}'", code="bad_source")


# --- Redaction ------------------------------------------------------------


def mask_secret(value: str | None) -> str:
    """Mask a credential for logs, errors and UI status."""
    if not value:
        return ""
    tail = value[-4:] if len(value) > 8 else ""
    return f"{ORCA_KEY_PREFIX}****{tail}"


def scrub(text: str, *secrets_to_hide: str | None) -> str:
    """Remove any credential material from a string before logging it."""
    out = text
    for secret in secrets_to_hide:
        if secret:
            out = out.replace(secret, "<redacted>")
    return out


# --- Model catalog --------------------------------------------------------

# Verified cold-start seed. Used only until live discovery succeeds, and again
# if it fails. Metadata is preserved so reasoning/context/modality support does
# not regress while the catalog is unavailable.
VERIFIED_FALLBACK_MODELS: tuple[dict[str, Any], ...] = (
    {
        "id": "openai/gpt-5.5",
        "name": "GPT-5.5",
        "context_length": 400000,
        "architecture": {"input_modalities": ["text", "image"], "output_modalities": ["text"]},
        "supported_endpoint_types": ["openai", "openai-response"],
        "reasoning": {"supported_efforts": ["low", "medium", "high", "xhigh"]},
    },
    {
        "id": "anthropic/claude-opus-4.8",
        "name": "Claude Opus 4.8",
        "context_length": 200000,
        "architecture": {"input_modalities": ["text", "image"], "output_modalities": ["text"]},
        "supported_endpoint_types": ["anthropic"],
    },
    {
        "id": "google/gemini-3.5-flash",
        "name": "Gemini 3.5 Flash",
        "context_length": 1000000,
        "architecture": {"input_modalities": ["text", "image"], "output_modalities": ["text"]},
        "supported_endpoint_types": ["gemini"],
    },
    {
        "id": "deepseek/deepseek-v4-pro",
        "name": "DeepSeek V4 Pro",
        "context_length": 128000,
        "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
        "supported_endpoint_types": ["openai"],
    },
    {
        "id": "orcarouter/auto",
        "name": "OrcaRouter Auto",
        "context_length": 128000,
        "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
        "supported_endpoint_types": ["openai"],
    },
)

REASONING_EFFORTS = ("low", "medium", "high", "xhigh")


@dataclass(frozen=True)
class CatalogModel:
    """Minimal model metadata the frontend needs to render a picker."""

    id: str
    name: str
    context_length: int | None = None
    input_modalities: tuple[str, ...] = (MODALITY_TEXT,)
    endpoint_types: tuple[str, ...] = ()
    reasoning_efforts: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "context_length": self.context_length,
            "input_modalities": list(self.input_modalities),
            "endpoint_types": list(self.endpoint_types),
            "reasoning_efforts": list(self.reasoning_efforts),
        }


def _as_str_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item) for item in value if isinstance(item, (str, int)))
    return ()


def parse_catalog_model(raw: Any) -> CatalogModel | None:
    """Parse one catalog record. Returns ``None`` for unusable records."""
    if not isinstance(raw, Mapping):
        return None
    model_id = raw.get("id")
    if not isinstance(model_id, str) or not model_id.strip():
        return None

    architecture = raw.get("architecture")
    modalities: tuple[str, ...] = ()
    if isinstance(architecture, Mapping):
        modalities = _as_str_tuple(architecture.get("input_modalities"))
    if not modalities:
        modalities = _as_str_tuple(raw.get("input_modalities"))
    if not modalities:
        # Unknown modality metadata must fail closed for multimodal pickers.
        modalities = ()

    endpoint_types = _as_str_tuple(raw.get("supported_endpoint_types"))
    reasoning_efforts: tuple[str, ...] = ()
    reasoning = raw.get("reasoning")
    if isinstance(reasoning, Mapping):
        reasoning_efforts = _as_str_tuple(
            reasoning.get("supported_efforts") or reasoning.get("efforts")
        )

    context_length = raw.get("context_length") or raw.get("context_window")
    if not isinstance(context_length, int):
        context_length = None

    name = raw.get("name")
    return CatalogModel(
        id=model_id.strip(),
        name=name.strip() if isinstance(name, str) and name.strip() else model_id.strip(),
        context_length=context_length,
        input_modalities=modalities,
        endpoint_types=endpoint_types,
        reasoning_efforts=reasoning_efforts,
    )


def parse_catalog_payload(payload: Any) -> list[CatalogModel]:
    """Parse a ``/v1/models`` payload, bounded in item count."""
    records: Iterable[Any]
    if isinstance(payload, Mapping):
        data = payload.get("data")
        records = data if isinstance(data, list) else []
    elif isinstance(payload, list):
        records = payload
    else:
        records = []

    models: list[CatalogModel] = []
    for raw in list(records)[:CATALOG_MAX_ITEMS]:
        parsed = parse_catalog_model(raw)
        if parsed is not None:
            models.append(parsed)
    return models


def _is_chat_capable(model: CatalogModel) -> bool:
    endpoints = set(model.endpoint_types)
    if endpoints & NON_CHAT_ENDPOINT_TYPES and not (endpoints & CHAT_ENDPOINT_TYPES):
        return False
    if endpoints and not (endpoints & CHAT_ENDPOINT_TYPES):
        return False
    return True


def filter_models(
    models: Sequence[CatalogModel],
    capability: str = CAPABILITY_CHAT,
    *,
    input_modalities: Sequence[str] = (),
) -> list[CatalogModel]:
    """Filter a catalog down to models usable for one entry point.

    Models with no capability metadata fail closed: we never guess a
    capability from a model's name.
    """
    wanted_modalities = {m for m in input_modalities if m and m != MODALITY_TEXT}
    out: list[CatalogModel] = []
    for model in models:
        endpoints = set(model.endpoint_types)
        if capability == CAPABILITY_CHAT:
            if not _is_chat_capable(model):
                continue
            declared = set(model.input_modalities)
            # A model that declares no modalities at all only qualifies for a
            # text-only picker.
            if wanted_modalities and not wanted_modalities.issubset(declared):
                continue
        elif capability == CAPABILITY_EMBEDDING:
            if "embeddings" not in endpoints and "embedding" not in endpoints:
                continue
        elif capability == CAPABILITY_IMAGE:
            if "image-generation" not in endpoints:
                continue
        elif capability == CAPABILITY_VIDEO:
            if "openai-video" not in endpoints:
                continue
        elif capability == CAPABILITY_RERANK:
            if "jina-rerank" not in endpoints:
                continue
        else:
            continue
        out.append(model)
    return out


def _fallback_models(
    capability: str, input_modalities: Sequence[str]
) -> list[CatalogModel]:
    seed = [parse_catalog_model(item) for item in VERIFIED_FALLBACK_MODELS]
    parsed = [model for model in seed if model is not None]
    return filter_models(parsed, capability, input_modalities=input_modalities)


def fetch_catalog(
    api_base: str,
    api_key: str | None,
    *,
    capability: str = CAPABILITY_CHAT,
    input_modalities: Sequence[str] = (),
    timeout: int = CATALOG_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Read ``GET {api_base}/models`` and return capability-filtered models.

    Live discovery is authoritative. On failure we fall back to the small
    verified seed and mark the result ``degraded`` so the UI can say so rather
    than silently presenting a stale list as complete.
    """
    base = api_base.rstrip("/")
    params = {"capability": capability} if capability else None
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        response = requests.get(
            f"{base}{ORCA_MODELS_PATH}",
            headers=headers,
            params=params,
            timeout=timeout,
            stream=True,
        )
        response.raise_for_status()
        # Bound the response size before parsing it.
        raw = response.raw.read(CATALOG_MAX_BYTES + 1, decode_content=True)
        if len(raw) > CATALOG_MAX_BYTES:
            raise OrcaRouterCatalogError("Model catalog response was too large", code="too_large")
        payload = json.loads(raw.decode("utf-8"))
    except OrcaRouterCatalogError as exc:
        return _degraded(capability, input_modalities, exc.code, str(exc))
    except requests.Timeout as exc:
        return _degraded(capability, input_modalities, "timeout", str(exc))
    except requests.RequestException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        code = "auth_error" if status in (401, 403) else "network_error"
        return _degraded(capability, input_modalities, code, type(exc).__name__)
    except (ValueError, UnicodeDecodeError) as exc:
        return _degraded(capability, input_modalities, "bad_response", str(exc))

    models = parse_catalog_payload(payload)
    filtered = filter_models(models, capability, input_modalities=input_modalities)
    return {
        "models": [model.to_dict() for model in filtered],
        "total": len(models),
        "filtered": len(filtered),
        "source": "live",
        "degraded": False,
        "capability": capability,
        "base_url": base,
    }


def _fetch_model_detail(api_base: str, api_key: str | None, model_id: str) -> dict[str, Any] | None:
    """Read ``GET /v1/models/{id}`` for the richer per-model metadata.

    The list endpoint only advertises ``supported_endpoint_types``; input
    modalities and context length live on the detail record. A model whose
    detail cannot be read simply contributes no modality metadata, which makes
    it fail closed in every multimodal picker.
    """
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    url = "%s%s/%s" % (api_base.rstrip("/"), ORCA_MODELS_PATH, urllib.parse.quote(model_id, safe=""))
    try:
        response = requests.get(url, headers=headers, timeout=CATALOG_DETAIL_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None
    return payload if isinstance(payload, Mapping) else None


def _enrich_modalities(
    api_base: str,
    api_key: str | None,
    models: Sequence[CatalogModel],
    *,
    max_workers: int = CATALOG_ENRICH_WORKERS,
    budget_seconds: float = CATALOG_ENRICH_BUDGET_SECONDS,
) -> tuple[list[CatalogModel], bool]:
    """Attach input modalities (and context length) to catalog models.

    Bounded by worker count and a wall-clock budget so a slow catalog cannot
    hold a request open. Models we could not enrich keep no modality metadata
    and are therefore excluded from multimodal pickers.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    deadline = time.monotonic() + budget_seconds
    enriched: dict[str, CatalogModel] = {}
    incomplete = False

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_fetch_model_detail, api_base, api_key, model.id): model
            for model in models
        }
        for future in as_completed(futures, timeout=None):
            model = futures[future]
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                incomplete = True
                for pending in futures:
                    pending.cancel()
                break
            detail = future.result()
            if detail is None:
                incomplete = True
                continue
            parsed = parse_catalog_model(detail)
            if parsed is None:
                continue
            parsed_id = detail.get("id") or model.id
            enriched[model.id] = CatalogModel(
                id=model.id,
                name=parsed.name if parsed.name != parsed_id else model.name,
                context_length=parsed.context_length or model.context_length,
                input_modalities=parsed.input_modalities or model.input_modalities,
                endpoint_types=model.endpoint_types or parsed.endpoint_types,
                reasoning_efforts=parsed.reasoning_efforts or model.reasoning_efforts,
            )

    merged = [enriched.get(model.id, model) for model in models]
    return merged, incomplete


class OrcaRouterCatalog:
    """TTL-cached, capability-filtered view of the OrcaRouter model catalog.

    Live discovery is authoritative. The verified seed is used only when live
    discovery fails, and is never merged into a successful live result.
    """

    def __init__(self, ttl_seconds: int = CATALOG_CACHE_TTL_SECONDS):
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}

    def _cache_key(self, api_base: str, capability: str, want_modalities: bool) -> tuple[str, str]:
        return (api_base.rstrip("/"), f"{capability}|{'modality' if want_modalities else 'plain'}")

    def get(
        self,
        api_base: str,
        api_key: str | None,
        *,
        capability: str = CAPABILITY_CHAT,
        input_modalities: Sequence[str] = (),
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        wanted = tuple(m for m in input_modalities if m and m != MODALITY_TEXT)
        needs_modality_data = bool(wanted)
        key = self._cache_key(api_base, capability, needs_modality_data)

        if not force_refresh:
            with self._lock:
                hit = self._cache.get(key)
            if hit and (time.monotonic() - hit[0]) < self.ttl_seconds:
                return self._with_modality_filter(hit[1], wanted)

        result = fetch_catalog(api_base, api_key, capability=capability, input_modalities=())
        enriched_incomplete = False
        if not result["degraded"] and needs_modality_data:
            models = [parse_catalog_model(item) for item in result["models"]]
            present = [model for model in models if model is not None]
            present, enriched_incomplete = _enrich_modalities(api_base, api_key, present)
            result = dict(result)
            result["models"] = [model.to_dict() for model in present]

        if not result["degraded"]:
            with self._lock:
                self._cache[key] = (time.monotonic(), result)

        payload = self._with_modality_filter(result, wanted)
        if enriched_incomplete:
            payload["degraded"] = True
            payload["error_code"] = payload.get("error_code") or "partial_metadata"
        return payload

    @staticmethod
    def _with_modality_filter(result: Mapping[str, Any], wanted: tuple[str, ...]) -> dict[str, Any]:
        payload = dict(result)
        models = [parse_catalog_model(item) for item in result.get("models", [])]
        present = [model for model in models if model is not None]
        payload["models"] = [model.to_dict() for model in present]
        if not wanted:
            return payload
        filtered = filter_models(present, result.get("capability", CAPABILITY_CHAT),
                                 input_modalities=wanted)
        payload["models"] = [model.to_dict() for model in filtered]
        payload["filtered"] = len(filtered)
        return payload


catalog = OrcaRouterCatalog()


def _degraded(
    capability: str,
    input_modalities: Sequence[str],
    code: str,
    detail: str,
) -> dict[str, Any]:
    fallback = _fallback_models(capability, input_modalities)
    logger.warning(
        "OrcaRouter catalog unavailable (%s: %s); serving %d verified fallback model(s)",
        code,
        scrub(detail),
        len(fallback),
    )
    return {
        "models": [model.to_dict() for model in fallback],
        "total": len(fallback),
        "filtered": len(fallback),
        "source": "fallback",
        "degraded": True,
        "error_code": code,
        "capability": capability,
    }


# --- Credential lifecycle -------------------------------------------------

# A PKCE-issued key is durable: there is no refresh grant, so a revoked key
# means reauthentication, never a refresh attempt.
TERMINAL_AUTH_STATUSES = (401, 403)


def classify_auth_failure(status_code: int) -> str:
    """Map an upstream status onto a credential lifecycle action."""
    if status_code in TERMINAL_AUTH_STATUSES:
        return "needs_reauth"
    if status_code == 429:
        return "rate_limited"
    return "transient"


def should_transition_to_needs_reauth(
    *,
    current_generation: int,
    rejected_generation: int,
    status_code: int,
) -> bool:
    """Generation-safe 401 handling.

    A late failure from a request issued under an older credential generation
    must never mark a newly reauthorized credential as broken.
    """
    if current_generation != rejected_generation:
        return False
    return classify_auth_failure(status_code) == "needs_reauth"
