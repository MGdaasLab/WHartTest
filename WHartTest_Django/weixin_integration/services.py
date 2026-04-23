import base64
import json
import logging
import mimetypes
import os
import re
import secrets
from datetime import datetime, timedelta, timezone as dt_timezone
from types import SimpleNamespace
from typing import Any, Iterable, Optional

import httpx
from asgiref.sync import async_to_sync
from django.contrib.auth.models import User
from django.utils import timezone

from langgraph_integration.models import ChatMessage, ChatSession
from orchestrator_integration.agent_loop_view import (
    AgentLoopStreamAPIView,
)

from .models import (
    WeixinBotAccount,
    WeixinConversation,
    WeixinConversationMessage,
    WeixinLoginSession,
    normalize_weixin_account_id,
)

logger = logging.getLogger(__name__)

DEFAULT_WEIXIN_API_BASE_URL = "https://ilinkai.weixin.qq.com"
DEFAULT_WEIXIN_BOT_TYPE = "3"
DEFAULT_LOGIN_TTL_MINUTES = 5
DEFAULT_WEIXIN_REQUEST_TIMEOUT_SECONDS = 15
DEFAULT_WEIXIN_STATUS_READ_TIMEOUT_SECONDS = 35
DEFAULT_LONG_POLL_TIMEOUT_SECONDS = 35
DEFAULT_WORKER_STALE_SECONDS = 150
DEFAULT_WEIXIN_PLUGIN_HOST_URL = "http://127.0.0.1:3001"
WEIXIN_SESSION_EXPIRED_ERRCODE = -14
WEIXIN_MESSAGE_TYPE_BOT = 2
WEIXIN_MESSAGE_STATE_FINISH = 2
BASE_INFO = {"channel_version": "wharttest-weixin-1.0"}
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
_MULTI_BLANK_LINE_RE = re.compile(r"\n{3,}")


class WeixinServiceError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


async def _run_weixin_agent_loop_non_stream(
    *,
    request: Any,
    user_message: str,
    session_id: str,
    project_id: str,
    project,
    prompt_id: Optional[int] = None,
    uploaded_images_base64: Optional[list[str]] = None,
    api_view: Optional[AgentLoopStreamAPIView] = None,
) -> dict[str, Any]:
    if api_view is None:
        api_view = AgentLoopStreamAPIView()

    final_content = ""
    final_session_id = session_id
    tool_results: list[dict[str, Any]] = []
    total_steps = 0
    context_token_count = 0
    context_limit = 128000
    error_message = ""
    error_status_code = 500
    interrupt_info = None

    async for chunk in api_view._create_stream_generator(
        request,
        user_message,
        session_id,
        project_id,
        project,
        None,
        True,
        prompt_id,
        uploaded_images_base64,
        False,
        None,
        True,
    ):
        if not (isinstance(chunk, str) and chunk.startswith("data: ")):
            continue

        data_str = chunk[6:].strip()
        if data_str == "[DONE]":
            continue

        try:
            event = json.loads(data_str)
        except json.JSONDecodeError:
            continue

        event_type = event.get("type")
        if event_type == "start":
            final_session_id = event.get("session_id", session_id)
        elif event_type == "stream":
            final_content += event.get("data", "")
        elif event_type == "tool_result":
            tool_results.append(
                {
                    "summary": event.get("summary", ""),
                    "tool_output": event.get("tool_output"),
                    "tool_name": event.get("tool_name"),
                    "step": event.get("step", 0),
                }
            )
        elif event_type == "step_complete":
            total_steps = max(total_steps, event.get("step", 0))
        elif event_type == "context_update":
            context_token_count = event.get("context_token_count", 0)
            context_limit = event.get("context_limit", 128000)
        elif event_type == "interrupt":
            interrupt_info = {
                "interrupt_id": event.get("interrupt_id"),
                "action_requests": event.get("action_requests", []),
            }
        elif event_type == "error":
            error_message = str(event.get("message", "Unknown error"))
            error_status_code = int(event.get("code", 500) or 500)

    if error_message:
        raise WeixinServiceError(error_message, error_status_code)

    response_data = {
        "session_id": final_session_id,
        "content": final_content,
        "total_steps": total_steps,
        "tool_results": tool_results,
        "context_token_count": context_token_count,
        "context_limit": context_limit,
    }
    if interrupt_info:
        response_data["interrupt"] = interrupt_info
    return response_data


def ensure_trailing_slash(url: str) -> str:
    return url if url.endswith("/") else f"{url}/"


def random_wechat_uin() -> str:
    uint32 = int.from_bytes(secrets.token_bytes(4), "big")
    return base64.b64encode(str(uint32).encode("utf-8")).decode("utf-8")


def build_headers(token: Optional[str] = None, body: Optional[str] = None) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        "X-WECHAT-UIN": random_wechat_uin(),
    }
    if body is not None:
        headers["Content-Length"] = str(len(body.encode("utf-8")))
    if token:
        headers["Authorization"] = f"Bearer {token.strip()}"
    return headers


def build_timeout(read_timeout: float = DEFAULT_WEIXIN_REQUEST_TIMEOUT_SECONDS) -> httpx.Timeout:
    return httpx.Timeout(
        connect=5.0,
        read=read_timeout,
        write=10.0,
        pool=5.0,
    )


def get_weixin_plugin_host_url() -> str:
    return (os.getenv("WEIXIN_PLUGIN_HOST_URL") or DEFAULT_WEIXIN_PLUGIN_HOST_URL).rstrip("/")


def build_weixin_plugin_host_timeout(
    read_timeout: float = DEFAULT_WEIXIN_REQUEST_TIMEOUT_SECONDS,
) -> httpx.Timeout:
    return httpx.Timeout(connect=3.0, read=read_timeout, write=10.0, pool=5.0)


def request_weixin_plugin_host(
    method: str,
    path: str,
    *,
    payload: Optional[dict] = None,
    read_timeout: float = DEFAULT_WEIXIN_REQUEST_TIMEOUT_SECONDS,
) -> dict:
    url = f"{get_weixin_plugin_host_url()}{path}"

    try:
        with httpx.Client(timeout=build_weixin_plugin_host_timeout(read_timeout)) as client:
            response = client.request(method.upper(), url, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as exc:
        logger.warning("Weixin plugin host timeout method=%s path=%s", method, path)
        raise WeixinServiceError("官方微信插件宿主响应超时，请稍后重试。", 504) from exc
    except httpx.HTTPError as exc:
        logger.warning(
            "Weixin plugin host request failed method=%s path=%s error=%s",
            method,
            path,
            exc,
        )
        raise WeixinServiceError("官方微信插件宿主不可用，请检查微信宿主服务是否启动。", 502) from exc
    except ValueError as exc:
        logger.warning(
            "Weixin plugin host returned invalid payload method=%s path=%s",
            method,
            path,
        )
        raise WeixinServiceError("官方微信插件宿主返回了无效数据。", 502) from exc

    if not isinstance(data, dict):
        raise WeixinServiceError("官方微信插件宿主返回了无效响应。", 502)

    if data.get("ok") is False:
        message = str(data.get("error") or "官方微信插件宿主返回失败")
        raise WeixinServiceError(message, 502)

    host_data = data.get("data")
    if host_data is None:
        return {}
    if not isinstance(host_data, dict):
        return {"items": host_data}
    return host_data


def _timestamp_ms_to_datetime(value: object):
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(float(value) / 1000.0, tz=dt_timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def sync_account_runtime_status(
    account: WeixinBotAccount,
    runtime_status: Optional[dict],
) -> WeixinBotAccount:
    if not runtime_status:
        return account

    updates: list[str] = []

    configured = bool(runtime_status.get("configured"))
    running = bool(runtime_status.get("running"))
    last_error = str(runtime_status.get("lastError") or "")

    desired_status = "running" if running else ("connected" if configured else "error")
    if account.status != desired_status:
        account.status = desired_status
        updates.append("status")

    if account.worker_running != running:
        account.worker_running = running
        updates.append("worker_running")

    if account.last_error != last_error:
        account.last_error = last_error
        updates.append("last_error")

    last_inbound_at = _timestamp_ms_to_datetime(runtime_status.get("lastInboundAt"))
    if account.last_inbound_at != last_inbound_at:
        account.last_inbound_at = last_inbound_at
        updates.append("last_inbound_at")

    last_outbound_at = _timestamp_ms_to_datetime(runtime_status.get("lastOutboundAt"))
    if account.last_outbound_at != last_outbound_at:
        account.last_outbound_at = last_outbound_at
        updates.append("last_outbound_at")

    if updates:
        account.save(update_fields=updates + ["updated_at"])
    return account


def start_weixin_plugin_account(account: WeixinBotAccount) -> dict:
    data = request_weixin_plugin_host(
        "POST",
        "/api/accounts/start",
        payload={
            "accountId": account.account_id,
            "token": account.token,
            "baseUrl": account.base_url,
            "userId": account.scanned_user_id,
        },
        read_timeout=5,
    )
    return data


def stop_weixin_plugin_account(account: WeixinBotAccount) -> dict:
    data = request_weixin_plugin_host(
        "POST",
        "/api/accounts/stop",
        payload={"accountId": account.account_id},
        read_timeout=5,
    )
    return data


def list_weixin_plugin_accounts_status() -> dict[str, dict]:
    data = request_weixin_plugin_host(
        "GET",
        "/api/accounts/status",
        read_timeout=5,
    )
    items = data.get("items")
    if items is None and isinstance(data, dict):
        items = data
    if not isinstance(items, list):
        items = []
    mapping: dict[str, dict] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        account_id = str(item.get("accountId") or "").strip()
        if account_id:
            mapping[account_id] = item
    return mapping


def persist_login_session_error(
    login_session: WeixinLoginSession,
    message: str,
) -> WeixinLoginSession:
    login_session.error_message = message
    login_session.save(update_fields=["error_message", "updated_at"])
    return login_session


def ensure_weixin_account_worker(account: WeixinBotAccount) -> bool:
    """
    确保官方微信插件宿主已开始监听该账号。
    """
    account = WeixinBotAccount.objects.filter(id=account.id).first()
    if not account or not account.is_active:
        return False

    stale_before = timezone.now() - timedelta(seconds=DEFAULT_WORKER_STALE_SECONDS)

    if account.worker_running and account.updated_at and account.updated_at >= stale_before:
        return False

    if account.worker_running and account.updated_at and account.updated_at < stale_before:
        logger.warning(
            "Weixin plugin host stale detected for account=%s last_updated_at=%s, restarting",
            account.raw_account_id,
            account.updated_at,
        )
        WeixinBotAccount.objects.filter(id=account.id).update(
            worker_running=False,
            status="connected",
            last_error="检测到微信轮询已中断，系统已自动重启监听任务。",
            updated_at=timezone.now(),
        )
    elif not account.worker_running:
        WeixinBotAccount.objects.filter(id=account.id).update(
            status="connected",
            updated_at=timezone.now(),
        )

    runtime_status = start_weixin_plugin_account(account)
    sync_account_runtime_status(account, runtime_status)
    return bool(runtime_status.get("running", True))


def normalize_weixin_reply_text(text: str) -> str:
    normalized = (text or "").strip()
    if not normalized:
        return ""

    normalized = _MARKDOWN_LINK_RE.sub(r"\1 \2", normalized)
    normalized = normalized.replace("`", "")
    normalized = normalized.replace("**", "")
    normalized = normalized.replace("__", "")
    normalized = normalized.replace("\r\n", "\n")
    normalized = _MULTI_BLANK_LINE_RE.sub("\n\n", normalized)
    return normalized.strip()


def generate_weixin_client_id() -> str:
    return f"wharttest-weixin:{int(timezone.now().timestamp() * 1000)}-{secrets.token_hex(4)}"


def extract_weixin_response_error(payload: object) -> Optional[str]:
    if not isinstance(payload, dict):
        return None

    status = str(payload.get("status", "") or "").lower()
    if status in {"error", "failed", "fail"}:
        return str(payload.get("message") or payload.get("errmsg") or "微信接口返回失败")

    success = payload.get("success")
    if success is False:
        return str(payload.get("message") or payload.get("errmsg") or "微信接口返回失败")

    for key in ("errcode", "ret", "code"):
        value = payload.get(key)
        if isinstance(value, int) and value not in {0, 200}:
            return str(payload.get("errmsg") or payload.get("message") or f"微信接口返回错误码 {value}")
        if isinstance(value, str) and value.isdigit() and int(value) not in {0, 200}:
            return str(payload.get("errmsg") or payload.get("message") or f"微信接口返回错误码 {value}")

    base_resp = payload.get("base_resp")
    if isinstance(base_resp, dict):
        ret = base_resp.get("ret")
        if isinstance(ret, int) and ret != 0:
            return str(
                base_resp.get("errmsg")
                or payload.get("message")
                or payload.get("errmsg")
                or f"微信接口返回错误码 {ret}"
            )
        if isinstance(ret, str) and ret.isdigit() and int(ret) != 0:
            return str(
                base_resp.get("errmsg")
                or payload.get("message")
                or payload.get("errmsg")
                or f"微信接口返回错误码 {ret}"
            )

    return None


def extract_weixin_numeric_field(payload: object, key: str) -> Optional[int]:
    if not isinstance(payload, dict):
        return None
    value = payload.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("-") and stripped[1:].isdigit():
            return int(stripped)
        if stripped.isdigit():
            return int(stripped)
    return None


def extract_weixin_payload_error(payload: object) -> Optional[tuple[int, str]]:
    if not isinstance(payload, dict):
        return None

    ret = extract_weixin_numeric_field(payload, "ret")
    errcode = extract_weixin_numeric_field(payload, "errcode")
    base_resp = payload.get("base_resp")
    base_ret = None
    if isinstance(base_resp, dict):
        base_ret = extract_weixin_numeric_field(base_resp, "ret")

    effective_code = next(
        (value for value in (errcode, ret, base_ret) if value not in (None, 0, 200)),
        None,
    )
    if effective_code is None:
        return None

    message = str(
        payload.get("errmsg")
        or payload.get("message")
        or (base_resp.get("errmsg") if isinstance(base_resp, dict) else "")
        or f"微信接口返回错误码 {effective_code}"
    )
    return effective_code, message


def start_login_session(
    *,
    user: User,
    project,
    prompt=None,
    base_url: str = DEFAULT_WEIXIN_API_BASE_URL,
) -> WeixinLoginSession:
    payload = request_weixin_plugin_host(
        "POST",
        "/api/login/start",
        payload={"baseUrl": base_url},
        read_timeout=DEFAULT_WEIXIN_REQUEST_TIMEOUT_SECONDS,
    )

    session_key = str(payload.get("sessionKey") or "").strip()
    if not session_key:
        raise WeixinServiceError("官方微信插件宿主没有返回 sessionKey。", 502)

    expires_at = timezone.now() + timedelta(minutes=DEFAULT_LOGIN_TTL_MINUTES)
    return WeixinLoginSession.objects.create(
        user=user,
        project=project,
        prompt=prompt,
        session_key=session_key,
        qrcode="",
        qr_data_url=str(payload.get("qrDataUrl") or ""),
        base_url=base_url,
        status="wait",
        expires_at=expires_at,
    )


def refresh_login_session(login_session: WeixinLoginSession) -> WeixinLoginSession:
    if login_session.status in {"confirmed", "failed", "expired"}:
        return login_session

    if login_session.expires_at <= timezone.now():
        login_session.status = "expired"
        login_session.error_message = "二维码已过期，请重新生成。"
        login_session.save(update_fields=["status", "error_message", "updated_at"])
        return login_session

    try:
        payload = request_weixin_plugin_host(
            "POST",
            "/api/login/status",
            payload={
                "sessionKey": login_session.session_key,
                "baseUrl": login_session.base_url,
                "timeoutMs": 1000,
            },
            read_timeout=DEFAULT_WEIXIN_STATUS_READ_TIMEOUT_SECONDS,
        )
    except WeixinServiceError as exc:
        if exc.status_code == 504:
            login_session.error_message = ""
            if not login_session.status:
                login_session.status = "wait"
            login_session.save(update_fields=["error_message", "status", "updated_at"])
            return login_session
        return persist_login_session_error(login_session, exc.message)

    status_message = str(payload.get("message") or "")
    if payload.get("connected"):
        login_session.status = "confirmed"
    elif any(keyword in status_message for keyword in ("过期", "expired", "超时", "没有进行中的登录")):
        login_session.status = "expired"
    else:
        login_session.status = "wait"
    login_session.bot_token = payload.get("botToken", "") or ""
    login_session.raw_account_id = payload.get("rawAccountId", "") or ""
    login_session.account_id = normalize_weixin_account_id(login_session.raw_account_id)
    login_session.scanned_user_id = payload.get("userId", "") or ""
    login_session.base_url = payload.get("baseUrl", "") or login_session.base_url
    login_session.error_message = ""

    if login_session.status == "confirmed" and login_session.raw_account_id:
        upsert_weixin_account_from_login(login_session)
    elif status_message:
        login_session.error_message = status_message

    login_session.save()
    return login_session


def upsert_weixin_account_from_login(login_session: WeixinLoginSession) -> WeixinBotAccount:
    account, _ = WeixinBotAccount.objects.update_or_create(
        raw_account_id=login_session.raw_account_id,
        defaults={
            "user": login_session.user,
            "project": login_session.project,
            "prompt": login_session.prompt,
            "account_id": login_session.account_id
            or normalize_weixin_account_id(login_session.raw_account_id),
            "token": login_session.bot_token,
            "base_url": login_session.base_url or DEFAULT_WEIXIN_API_BASE_URL,
            "scanned_user_id": login_session.scanned_user_id,
            "is_active": True,
            "status": "connected",
            "last_error": "",
            "worker_running": False,
        },
    )
    return account


def create_base_info() -> dict[str, str]:
    return dict(BASE_INFO)


def extract_text_from_items(item_list: Iterable[dict]) -> str:
    texts: list[str] = []
    for item in item_list or []:
        if item.get("type") == 1 and item.get("text_item", {}).get("text"):
            texts.append(str(item["text_item"]["text"]))
    return "\n".join(texts).strip()


def get_or_create_conversation(account: WeixinBotAccount, peer_user_id: str, context_token: str):
    conversation, created = WeixinConversation.objects.get_or_create(
        account=account,
        peer_user_id=peer_user_id,
        defaults={"context_token": context_token or ""},
    )
    updates = []
    if context_token and conversation.context_token != context_token:
        conversation.context_token = context_token
        updates.append("context_token")
    if created or conversation.chat_session is None:
        session_id = f"weixin_{account.account_id}_{normalize_weixin_account_id(peer_user_id)}"
        chat_session, _ = ChatSession.objects.get_or_create(
            session_id=session_id,
            defaults={
                "user": account.user,
                "project": account.project,
                "prompt": account.prompt,
                "title": f"Weixin {peer_user_id[:48]}",
            },
        )
        conversation.chat_session = chat_session
        updates.append("chat_session")
    if conversation.chat_session:
        session_updates = []
        if conversation.chat_session.user_id != account.user_id:
            conversation.chat_session.user = account.user
            session_updates.append("user")
        if conversation.chat_session.project_id != account.project_id:
            conversation.chat_session.project = account.project
            session_updates.append("project")
        if conversation.chat_session.prompt_id != account.prompt_id:
            conversation.chat_session.prompt = account.prompt
            session_updates.append("prompt")
        if session_updates:
            conversation.chat_session.save(update_fields=session_updates + ["updated_at"])
    if updates:
        conversation.save(update_fields=updates + ["updated_at"])
    return conversation


def persist_message(
    conversation: WeixinConversation,
    role: str,
    content: str,
    external_message_id: str = "",
) -> WeixinConversationMessage:
    message = WeixinConversationMessage.objects.create(
        conversation=conversation,
        role=role,
        content=content,
        external_message_id=external_message_id,
    )
    if conversation.chat_session:
        ChatMessage.objects.create(
            session=conversation.chat_session,
            user=conversation.account.user,
            message_id=external_message_id or secrets.token_hex(8),
            role="assistant" if role == "assistant" else "user",
        )
    return message


def _build_interrupt_reply(interrupt: dict) -> str:
    action_requests = interrupt.get("action_requests") or []
    tool_names = [
        str(item.get("name", "")).strip()
        for item in action_requests
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    ]
    if tool_names:
        return (
            "这条消息命中了需要人工确认的操作："
            f"{'、'.join(tool_names)}。请到 WHartTest 网页端完成审批后继续。"
        )
    return "这条消息需要在 WHartTest 网页端完成人工审批后才能继续执行。"


def encode_local_image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def build_weixin_multimodal_input(
    *,
    user_message: str,
    media_path: str = "",
    media_type: str = "",
) -> tuple[str, list[str]]:
    text = (user_message or "").strip()
    uploaded_images_base64: list[str] = []

    if media_path:
        guessed_type = (media_type or mimetypes.guess_type(media_path)[0] or "").lower()
        if guessed_type.startswith("image/"):
            try:
                uploaded_images_base64.append(encode_local_image_to_base64(media_path))
                if not text:
                    text = "用户发来了一张图片，请结合图片内容进行回复。"
            except OSError as exc:
                logger.warning("Failed to read inbound Weixin image %s: %s", media_path, exc)
                if not text:
                    text = "用户发送了一张图片，但图片读取失败。"
        elif not text:
            text = "用户发送了一条带附件的微信消息，请基于当前上下文回复。"

    if not text:
        text = "用户发送了一条微信消息。"

    return text, uploaded_images_base64


def generate_reply(
    account: WeixinBotAccount,
    conversation: WeixinConversation,
    user_message: str,
    *,
    uploaded_images_base64: Optional[list[str]] = None,
) -> str:
    if not conversation.chat_session:
        raise RuntimeError("微信会话未绑定 ChatSession")

    request = SimpleNamespace(user=account.user)
    response_data = async_to_sync(_run_weixin_agent_loop_non_stream)(
        request=request,
        user_message=user_message,
        session_id=conversation.chat_session.session_id,
        project_id=str(account.project_id),
        project=account.project,
        prompt_id=account.prompt_id,
        uploaded_images_base64=uploaded_images_base64,
        api_view=AgentLoopStreamAPIView(),
    )

    interrupt = response_data.get("interrupt")
    if interrupt:
        return _build_interrupt_reply(interrupt)

    reply = str(response_data.get("content", "") or "").strip()
    if reply:
        return reply
    return "我收到了你的消息，但这次没有生成有效回复。"


def handle_plugin_inbound_message(
    *,
    account_id: str,
    peer_user_id: str,
    text: str,
    context_token: str = "",
    external_message_id: str = "",
    session_key: str = "",
    media_path: str = "",
    media_type: str = "",
) -> str:
    account = (
        WeixinBotAccount.objects.select_related("user", "project", "prompt")
        .filter(account_id=account_id, is_active=True)
        .first()
    )
    if not account:
        raise WeixinServiceError("未找到已启用的微信账号绑定。", 404)

    conversation = get_or_create_conversation(account, peer_user_id, context_token)

    if external_message_id and conversation.messages.filter(
        role="user",
        external_message_id=external_message_id,
    ).exists():
        logger.info(
            "Skip duplicated Weixin inbound message account=%s peer=%s external_message_id=%s",
            account.account_id,
            peer_user_id,
            external_message_id,
        )
        return ""

    normalized_user_message, uploaded_images_base64 = build_weixin_multimodal_input(
        user_message=text,
        media_path=media_path,
        media_type=media_type,
    )

    persist_message(
        conversation,
        "user",
        normalized_user_message,
        external_message_id=external_message_id,
    )

    WeixinBotAccount.objects.filter(id=account.id).update(
        last_inbound_at=timezone.now(),
        worker_running=True,
        status="running",
        last_error="",
        updated_at=timezone.now(),
    )

    reply = generate_reply(
        account,
        conversation,
        normalized_user_message,
        uploaded_images_base64=uploaded_images_base64 or None,
    )

    persist_message(conversation, "assistant", reply)

    WeixinBotAccount.objects.filter(id=account.id).update(
        last_outbound_at=timezone.now(),
        status="running",
        worker_running=True,
        last_error="",
        updated_at=timezone.now(),
    )
    return reply


def send_text_message(
    *,
    account: WeixinBotAccount,
    to_user_id: str,
    context_token: str,
    text: str,
) -> None:
    normalized_text = normalize_weixin_reply_text(text)
    if not normalized_text:
        raise WeixinServiceError("微信回复内容为空，已跳过发送。", 400)

    client_id = generate_weixin_client_id()
    body_dict = {
        "msg": {
            "from_user_id": "",
            "to_user_id": to_user_id,
            "client_id": client_id,
            "message_type": WEIXIN_MESSAGE_TYPE_BOT,
            "message_state": WEIXIN_MESSAGE_STATE_FINISH,
            "context_token": context_token or None,
            "item_list": [
                {
                    "type": 1,
                    "text_item": {"text": normalized_text},
                }
            ],
        },
        "base_info": create_base_info(),
    }
    body = json.dumps(body_dict, ensure_ascii=False)
    base = ensure_trailing_slash(account.base_url)
    url = f"{base}ilink/bot/sendmessage"
    try:
        with httpx.Client(timeout=build_timeout()) as client:
            response = client.post(
                url,
                content=body.encode("utf-8"),
                headers=build_headers(token=account.token, body=body),
            )
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise WeixinServiceError("微信消息发送超时，请稍后重试。", 504) from exc
    except httpx.HTTPError as exc:
        raise WeixinServiceError("微信消息发送失败，请稍后重试。", 502) from exc

    response_payload = None
    response_text = (response.text or "").strip()
    if response_text:
        try:
            response_payload = response.json()
        except ValueError:
            logger.info(
                "Weixin sendmessage returned non-json body for account=%s to=%s body=%s",
                account.raw_account_id,
                to_user_id,
                response_text[:500],
            )

    response_error = extract_weixin_response_error(response_payload)
    if response_error:
        raise WeixinServiceError(f"微信消息发送失败：{response_error}", 502)

    logger.info(
        "Weixin sendmessage success account=%s to=%s client_id=%s context_token_present=%s response=%s",
        account.raw_account_id,
        to_user_id,
        client_id,
        bool(context_token),
        json.dumps(response_payload, ensure_ascii=False)[:500]
        if response_payload is not None
        else response_text[:500],
    )
