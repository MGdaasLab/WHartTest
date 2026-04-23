import json
import logging
import time

import httpx
from celery import shared_task
from django.db import IntegrityError
from django.utils import timezone

from .models import WeixinBotAccount
from .services import (
    build_headers,
    build_timeout,
    create_base_info,
    ensure_trailing_slash,
    extract_weixin_numeric_field,
    extract_weixin_payload_error,
    extract_text_from_items,
    generate_reply,
    get_or_create_conversation,
    persist_message,
    send_text_message,
    WEIXIN_SESSION_EXPIRED_ERRCODE,
    DEFAULT_LONG_POLL_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
def poll_weixin_account(account_id: int):
    locked = WeixinBotAccount.objects.filter(
        id=account_id,
        is_active=True,
        worker_running=False,
    ).update(worker_running=True, status="running", last_error="")

    if not locked:
        return

    try:
        next_long_poll_timeout_seconds = DEFAULT_LONG_POLL_TIMEOUT_SECONDS
        with httpx.Client(timeout=build_timeout(read_timeout=next_long_poll_timeout_seconds + 5)) as client:
            while True:
                account = (
                    WeixinBotAccount.objects.select_related("user", "project", "prompt")
                    .filter(id=account_id)
                    .first()
                )
                if not account or not account.is_active:
                    break

                WeixinBotAccount.objects.filter(id=account_id).update(
                    worker_running=True,
                    status="running",
                    updated_at=timezone.now(),
                )

                body_dict = {
                    "get_updates_buf": account.sync_cursor or "",
                    "base_info": create_base_info(),
                }
                body = json.dumps(body_dict, ensure_ascii=False)
                url = f"{ensure_trailing_slash(account.base_url)}ilink/bot/getupdates"

                try:
                    response = client.post(
                        url,
                        content=body.encode("utf-8"),
                        headers=build_headers(token=account.token, body=body),
                        timeout=build_timeout(
                            read_timeout=max(5, next_long_poll_timeout_seconds + 5)
                        ),
                    )
                    response.raise_for_status()
                    payload = response.json()
                except httpx.TimeoutException:
                    WeixinBotAccount.objects.filter(id=account_id).update(
                        status="running",
                        last_error="",
                        updated_at=timezone.now(),
                    )
                    continue
                except Exception as exc:
                    logger.exception("Weixin getupdates failed for account %s", account.raw_account_id)
                    WeixinBotAccount.objects.filter(id=account_id).update(
                        status="error",
                        last_error=str(exc),
                        updated_at=timezone.now(),
                    )
                    time.sleep(5)
                    continue

                next_timeout_ms = extract_weixin_numeric_field(
                    payload, "longpolling_timeout_ms"
                )
                if next_timeout_ms and next_timeout_ms > 0:
                    next_long_poll_timeout_seconds = max(
                        5,
                        min(int(next_timeout_ms / 1000), 60),
                    )

                payload_error = extract_weixin_payload_error(payload)
                if payload_error:
                    code, message = payload_error
                    if code == WEIXIN_SESSION_EXPIRED_ERRCODE:
                        logger.error(
                            "Weixin session expired for account %s payload=%s",
                            account.raw_account_id,
                            json.dumps(payload, ensure_ascii=False)[:500],
                        )
                        WeixinBotAccount.objects.filter(id=account_id).update(
                            status="error",
                            last_error=f"微信会话已失效（errcode {code}），请重新扫码绑定。",
                            worker_running=False,
                            updated_at=timezone.now(),
                        )
                        return

                    logger.error(
                        "Weixin getupdates business error for account %s code=%s message=%s payload=%s",
                        account.raw_account_id,
                        code,
                        message,
                        json.dumps(payload, ensure_ascii=False)[:500],
                    )
                    WeixinBotAccount.objects.filter(id=account_id).update(
                        status="error",
                        last_error=f"微信消息轮询失败：{message}",
                        updated_at=timezone.now(),
                    )
                    time.sleep(2)
                    continue

                cursor = payload.get("get_updates_buf")
                if cursor is not None and cursor != account.sync_cursor:
                    WeixinBotAccount.objects.filter(id=account_id).update(
                        sync_cursor=cursor,
                        updated_at=timezone.now(),
                    )
                else:
                    WeixinBotAccount.objects.filter(id=account_id).update(
                        updated_at=timezone.now(),
                    )

                messages = payload.get("msgs") or []
                if not messages:
                    continue

                for raw_message in messages:
                    if raw_message.get("message_type") != 1:
                        continue

                    peer_user_id = (raw_message.get("from_user_id") or "").strip()
                    if not peer_user_id:
                        continue

                    text = extract_text_from_items(raw_message.get("item_list") or [])
                    if not text:
                        continue

                    context_token = (raw_message.get("context_token") or "").strip()
                    conversation = get_or_create_conversation(account, peer_user_id, context_token)
                    external_message_id = str(
                        raw_message.get("message_id")
                        or raw_message.get("seq")
                        or f"in-{int(time.time() * 1000)}"
                    )

                    try:
                        persist_message(conversation, "user", text, external_message_id)
                    except IntegrityError:
                        continue

                    WeixinBotAccount.objects.filter(id=account_id).update(last_inbound_at=timezone.now())

                    try:
                        reply = generate_reply(account, conversation, text)
                    except Exception as exc:
                        logger.exception("Weixin reply generation failed")
                        reply = f"当前处理消息失败：{exc}"

                    persist_message(conversation, "assistant", reply)

                    try:
                        send_text_message(
                            account=account,
                            to_user_id=peer_user_id,
                            context_token=context_token,
                            text=reply,
                        )
                        WeixinBotAccount.objects.filter(id=account_id).update(
                            last_outbound_at=timezone.now(),
                            status="running",
                            last_error="",
                            updated_at=timezone.now(),
                        )
                    except Exception as exc:
                        logger.exception("Weixin sendmessage failed")
                        WeixinBotAccount.objects.filter(id=account_id).update(
                            status="error",
                            last_error=str(exc),
                            updated_at=timezone.now(),
                        )
    finally:
        WeixinBotAccount.objects.filter(id=account_id).update(
            worker_running=False,
            status="stopped",
            updated_at=timezone.now(),
        )
