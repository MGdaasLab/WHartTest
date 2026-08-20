"""In-process actuator capability registry.

Thin wrapper over SocketUserManager process-local state.
Interface is replaceable later (e.g. Redis) without changing call sites.
"""

from __future__ import annotations

from typing import Any, Optional
import threading

_SLOT_LOCK = threading.RLock()

# lease_id -> {actuator_id, count, created_at, expires_at, meta}
_SLOT_LEASES: dict[str, dict[str, Any]] = {}
# Default lease TTL when no task result/stop arrives (seconds).
DEFAULT_SLOT_LEASE_TTL_SECONDS = 45 * 60
# Optional Redis key prefix for cross-worker lease sharing (falls back to memory).
_REDIS_LEASE_KEY = "ui_auto:slot_leases"
_REDIS_ENABLED_ENV = "UI_AUTOMATION_SLOT_LEASE_REDIS"
_redis_client = None
_redis_checked = False


def _redis():
    """Lazy Redis client; None when unavailable or disabled.

    Multi-worker deployments can set UI_AUTOMATION_SLOT_LEASE_REDIS=1 (default on)
    and CELERY_BROKER_URL / UI_AUTOMATION_REDIS_URL. When Redis is down, memory leases
    still work for single-process mode.
    """
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    _redis_checked = True
    import os
    flag = os.environ.get(_REDIS_ENABLED_ENV, "1").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        _redis_client = None
        return None
    try:
        import redis
        from django.conf import settings
        url = (
            os.environ.get("UI_AUTOMATION_REDIS_URL")
            or getattr(settings, "UI_AUTOMATION_REDIS_URL", None)
            or getattr(settings, "CELERY_BROKER_URL", None)
            or "redis://localhost:6379/0"
        )
        client = redis.from_url(url, socket_connect_timeout=0.5, socket_timeout=0.5, decode_responses=True)
        client.ping()
        _redis_client = client
    except Exception:
        _redis_client = None
    return _redis_client


def _lease_store_load() -> dict[str, dict[str, Any]]:
    """Return lease map: prefer Redis hash, else process memory."""
    client = _redis()
    if client is None:
        return _SLOT_LEASES
    try:
        import json
        raw = client.hgetall(_REDIS_LEASE_KEY) or {}
        out: dict[str, dict[str, Any]] = {}
        for lid, payload in raw.items():
            try:
                data = json.loads(payload)
                if isinstance(data, dict):
                    out[str(lid)] = data
            except Exception:
                continue
        return out
    except Exception:
        return _SLOT_LEASES


def _lease_store_put(lease_id: str, lease: dict[str, Any]) -> bool:
    """Persist one lease. When Redis is enabled it is the source of truth.

    Order: Redis first, then memory mirror. If Redis write fails, do not keep a
    local-only lease that would be wiped by the next Redis reload.
    """
    client = _redis()
    if client is None:
        _SLOT_LEASES[lease_id] = lease
        return True
    try:
        import json
        client.hset(_REDIS_LEASE_KEY, lease_id, json.dumps(lease, ensure_ascii=False))
        _SLOT_LEASES[lease_id] = lease
        return True
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            "slot lease put failed lid=%s: %s", lease_id, exc
        )
        return False


def _lease_store_delete(lease_id: str) -> bool:
    """Delete one lease. When Redis is enabled, delete Redis first then memory."""
    client = _redis()
    if client is None:
        _SLOT_LEASES.pop(lease_id, None)
        return True
    try:
        client.hdel(_REDIS_LEASE_KEY, lease_id)
        _SLOT_LEASES.pop(lease_id, None)
        return True
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            "slot lease delete failed lid=%s: %s", lease_id, exc
        )
        return False


def _leases_view() -> dict[str, dict[str, Any]]:
    """Working copy of leases under lock.

    Redis-on: reload Redis snapshot into memory (Redis is source of truth).
    Redis-off / Redis error: keep process-local map from _lease_store_load.
    """
    loaded = _lease_store_load()
    # keep memory in sync with redis view
    if loaded is not _SLOT_LEASES:
        _SLOT_LEASES.clear()
        _SLOT_LEASES.update(loaded)
    return _SLOT_LEASES


# NOTE: master-ce 分支不存在 runtime_config 模块（该模块属 PE 分支内容）。
# 此处内联 normalize_capability 及其辅助函数，避免引用不存在的模块导致导入崩溃。
SUPPORTED_BROWSERS = ("chromium", "firefox", "webkit")


def normalize_browser(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text in SUPPORTED_BROWSERS:
        return text
    aliases = {
        "chrome": "chromium",
        "google-chrome": "chromium",
        "msedge": "chromium",
        "edge": "chromium",
    }
    return aliases.get(text)


def normalize_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on", "y"}:
            return True
        if text in {"0", "false", "no", "off", "n"}:
            return False
    return None


def normalize_positive_int(value: Any, *, minimum: int = 1) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number < minimum:
        return None
    return number


def normalize_capability(actuator_info: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Normalize online actuator capability for matching / UI."""
    info = actuator_info or {}
    supported = info.get("supported_browsers")
    browsers: list[str] = []
    if isinstance(supported, (list, tuple)):
        for item in supported:
            browser = normalize_browser(item)
            if browser and browser not in browsers:
                browsers.append(browser)
    if not browsers:
        legacy = normalize_browser(
            info.get("browser_type") or info.get("browser") or info.get("default_browser")
        )
        if legacy:
            browsers = [legacy]
        else:
            browsers = ["chromium"]

    default_browser = normalize_browser(
        info.get("default_browser") or info.get("browser_type") or browsers[0]
    )
    # Keep supported_browsers as the declared capability set.
    # If default is outside that set, fall back rather than inventing support.
    if default_browser and default_browser not in browsers:
        default_browser = browsers[0]
    if not default_browser:
        default_browser = browsers[0]

    supports_headless = normalize_bool(info.get("supports_headless"))
    if supports_headless is None:
        supports_headless = True
    supports_headed = normalize_bool(info.get("supports_headed"))
    if supports_headed is None:
        supports_headed = True

    max_slots = normalize_positive_int(
        info.get("max_slots") or info.get("max_concurrent"), minimum=1
    ) or 1
    busy_slots = normalize_positive_int(info.get("busy_slots"), minimum=0)
    if busy_slots is None:
        busy_slots = 0
    busy_slots = min(busy_slots, max_slots)

    is_open = normalize_bool(info.get("is_open"))
    if is_open is None:
        is_open = True

    return {
        "id": info.get("id") or info.get("actuator_id"),
        "name": info.get("name") or info.get("id") or "actuator",
        "supported_browsers": browsers,
        "default_browser": default_browser,
        "supports_headed": supports_headed,
        "supports_headless": supports_headless,
        "max_slots": max_slots,
        "busy_slots": busy_slots,
        "is_open": is_open,
        "version": info.get("version"),
        "labels": info.get("labels") if isinstance(info.get("labels"), list) else [],
        "os": info.get("os"),
        "browser_type": default_browser,
        "headless": normalize_bool(info.get("headless")),
    }


def _list_raw_actuators() -> list[dict[str, Any]]:
    from .consumers import SocketUserManager

    items: list[dict[str, Any]] = []
    for actuator_id, consumer in list(SocketUserManager._actuator_users.items()):
        info = dict(getattr(consumer, "actuator_info", {}) or {})
        info["id"] = actuator_id
        info.setdefault("name", info.get("name") or actuator_id)
        items.append(info)
    return items


def get_capability(actuator_id: str) -> Optional[dict[str, Any]]:
    reclaim_expired_leases()
    for item in _list_raw_actuators():
        if item.get("id") == actuator_id:
            return normalize_capability(item)
    return None


def get_raw_consumer(actuator_id: Optional[str] = None):
    from .consumers import SocketUserManager

    if actuator_id:
        return SocketUserManager.get_actuator_by_id(actuator_id)
    return SocketUserManager.get_actuator()


def update_capability(actuator_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    # busy_slots is server-owned; never take client payload as source of truth.
    # Hold _SLOT_LOCK so concurrent reserve/release cannot be clobbered by heartbeat.
    from .consumers import SocketUserManager

    with _SLOT_LOCK:
        consumer = SocketUserManager.get_actuator_by_id(actuator_id)
        if consumer is None:
            raise KeyError(actuator_id)
        info = getattr(consumer, "actuator_info", None)
        if info is None:
            info = {}
            consumer.actuator_info = info
        # Re-read under lock; do not restore a pre-update snapshot of busy_slots.
        for key, value in (payload or {}).items():
            if key == "busy_slots":
                continue  # server-owned
            if value is not None:
                info[key] = value
        # 浏览器类型变更时同步默认浏览器，避免 normalize_capability 按 default_browser 优先回退旧值
        if payload.get("browser_type") and payload.get("browser_type") != info.get("default_browser"):
            info["default_browser"] = payload["browser_type"]
        # Normalize capability fields only; never overwrite busy from payload/normalize alone.
        cap = normalize_capability({**info, "id": actuator_id})
        info.update(
            {
                "supported_browsers": cap["supported_browsers"],
                "default_browser": cap["default_browser"],
                "supports_headed": cap["supports_headed"],
                "supports_headless": cap["supports_headless"],
                "max_slots": cap["max_slots"],
                "browser_type": cap["browser_type"],
            }
        )
        # Keep server-owned busy from leases; clamp after max_slots change.
        consumer.actuator_info = info
        synced = _sync_busy_from_leases(actuator_id)
        if synced is None:
            info["busy_slots"] = 0
            consumer.actuator_info = info
            return normalize_capability({**info, "id": actuator_id})
        return synced


def _now() -> float:
    import time
    return time.time()


def _sync_busy_from_leases(actuator_id: str) -> Optional[dict[str, Any]]:
    """Recompute busy_slots for one actuator from live leases. Caller holds _SLOT_LOCK."""
    from .consumers import SocketUserManager

    consumer = SocketUserManager.get_actuator_by_id(actuator_id)
    if consumer is None:
        return None
    info = getattr(consumer, "actuator_info", {}) or {}
    cap = normalize_capability({**info, "id": actuator_id})
    busy = 0
    for lease in _leases_view().values():
        if lease.get("actuator_id") == actuator_id:
            busy += int(lease.get("count") or 0)
    busy = max(0, min(int(cap["max_slots"] or 1), busy))
    info["busy_slots"] = busy
    info["max_slots"] = cap["max_slots"]
    consumer.actuator_info = info
    return normalize_capability({**info, "id": actuator_id})


def _reclaim_expired_leases_unlocked(now: Optional[float] = None) -> int:
    """Caller must hold _SLOT_LOCK."""
    ts = _now() if now is None else now
    leases = _leases_view()
    expired = [
        lease_id
        for lease_id, lease in list(leases.items())
        if float(lease.get("expires_at") or 0) <= ts
    ]
    if not expired:
        return 0
    affected: set[str] = set()
    reclaimed = 0
    for lease_id in expired:
        lease = leases.get(lease_id)
        _lease_store_delete(lease_id)
        if not lease:
            continue
        reclaimed += int(lease.get("count") or 0)
        actuator_id = lease.get("actuator_id")
        if actuator_id:
            affected.add(str(actuator_id))
    for actuator_id in affected:
        _sync_busy_from_leases(actuator_id)
    if reclaimed:
        import logging
        logging.getLogger(__name__).warning(
            "reclaimed %s expired slot lease(s) across %s actuator(s)",
            reclaimed,
            len(affected),
        )
    return reclaimed


def reclaim_expired_leases(now: Optional[float] = None) -> int:
    """Drop timed-out leases and resync busy_slots. Returns reclaimed slot count."""
    with _SLOT_LOCK:
        return _reclaim_expired_leases_unlocked(now)


def _clear_actuator_leases_unlocked(actuator_id: str) -> int:
    """Caller must hold _SLOT_LOCK."""
    removed = 0
    for lease_id, lease in list(_leases_view().items()):
        if lease.get("actuator_id") == actuator_id:
            removed += int(lease.get("count") or 0)
            _lease_store_delete(lease_id)
    _sync_busy_from_leases(actuator_id)
    return removed


def clear_actuator_leases(actuator_id: str) -> int:
    """Remove all leases for an actuator (disconnect/stop). Returns released slots."""
    with _SLOT_LOCK:
        return _clear_actuator_leases_unlocked(str(actuator_id))


def release_all_slots(actuator_id: Optional[str] = None) -> int:
    """Force-release leases. If actuator_id is None, release for all online actuators."""
    with _SLOT_LOCK:
        if actuator_id:
            return _clear_actuator_leases_unlocked(str(actuator_id))
        from .consumers import SocketUserManager
        total = 0
        ids = list(SocketUserManager._actuator_users.keys())
        # also clear orphan leases for offline ids
        for lease_id, lease in list(_leases_view().items()):
            aid = str(lease.get("actuator_id") or "")
            if aid and aid not in ids:
                total += int(lease.get("count") or 0)
                _lease_store_delete(lease_id)
        for aid in ids:
            total += _clear_actuator_leases_unlocked(aid)
        return total


def adjust_busy_slots(actuator_id: str, delta: int) -> Optional[dict[str, Any]]:
    """Adjust busy slots. Negative delta releases oldest leases first."""
    with _SLOT_LOCK:
        _reclaim_expired_leases_unlocked()
        from .consumers import SocketUserManager

        consumer = SocketUserManager.get_actuator_by_id(actuator_id)
        if consumer is None:
            # still drop leases for offline actuator
            if delta < 0:
                _clear_actuator_leases_unlocked(actuator_id)
            return None

        if delta > 0:
            # create anonymous lease so timeout reclaim still works
            import uuid
            lease_id = str(uuid.uuid4())
            expires = _now() + DEFAULT_SLOT_LEASE_TTL_SECONDS
            if not _lease_store_put(lease_id, {
                "lease_id": lease_id,
                "actuator_id": actuator_id,
                "count": int(delta),
                "created_at": _now(),
                "expires_at": expires,
                "meta": {},
            }):
                return _sync_busy_from_leases(actuator_id)
            return _sync_busy_from_leases(actuator_id)

        if delta == 0:
            return _sync_busy_from_leases(actuator_id)

        # release: consume leases FIFO
        remaining = -int(delta)
        ordered = sorted(
            (
                (lid, lease)
                for lid, lease in _leases_view().items()
                if lease.get("actuator_id") == actuator_id
            ),
            key=lambda item: float(item[1].get("created_at") or 0),
        )
        for lid, lease in ordered:
            if remaining <= 0:
                break
            have = int(lease.get("count") or 0)
            take = min(have, remaining)
            lease["count"] = have - take
            remaining -= take
            if lease["count"] <= 0:
                _lease_store_delete(lid)
            else:
                _lease_store_put(lid, lease)
        return _sync_busy_from_leases(actuator_id)


def reserve_slots(
    actuator_id: str,
    count: int = 1,
    *,
    ttl_seconds: Optional[int] = None,
    meta: Optional[dict[str, Any]] = None,
) -> tuple[bool, str]:
    """Atomically reserve N slots with a timeout lease."""
    if count <= 0:
        return True, ""
    with _SLOT_LOCK:
        _reclaim_expired_leases_unlocked()
        from .consumers import SocketUserManager
        import uuid

        consumer = SocketUserManager.get_actuator_by_id(actuator_id)
        if consumer is None:
            return False, f"执行器 {actuator_id} 不在线"
        info = getattr(consumer, "actuator_info", {}) or {}
        cap = normalize_capability({**info, "id": actuator_id})
        # Prefer lease-derived busy (cross-worker when Redis is on)
        lease_busy = 0
        for lease in _leases_view().values():
            if lease.get("actuator_id") == actuator_id:
                lease_busy += int(lease.get("count") or 0)
        busy_now = max(int(cap.get("busy_slots") or 0), lease_busy)
        free = int(cap.get("max_slots") or 1) - busy_now
        if free < count:
            return False, (
                f"执行器 {cap.get('name') or actuator_id} 空闲 slot 不足（需要 {count}，剩余 {free}）"
            )
        ttl = int(ttl_seconds) if ttl_seconds and ttl_seconds > 0 else DEFAULT_SLOT_LEASE_TTL_SECONDS
        # clamp TTL: at least 5 minutes, at most 6 hours
        ttl = max(5 * 60, min(ttl, 6 * 60 * 60))
        lease_id = str(uuid.uuid4())
        now = _now()
        ok = _lease_store_put(lease_id, {
            "lease_id": lease_id,
            "actuator_id": actuator_id,
            "count": int(count),
            "created_at": now,
            "expires_at": now + ttl,
            "meta": dict(meta or {}),
        })
        if not ok:
            return False, "slot lease persist failed, please retry"
        _sync_busy_from_leases(actuator_id)
        return True, ""


def list_capabilities() -> list[dict[str, Any]]:
    reclaim_expired_leases()
    return [normalize_capability(item) for item in _list_raw_actuators()]


def resolve_and_select(
    *,
    env=None,
    run_options: Optional[dict[str, Any]] = None,
    preferred_actuator_id: Optional[str] = None,
) -> tuple[Optional[dict[str, Any]], Optional[dict[str, Any]], str]:
    """选择在线执行器并生成简化 effective_runtime。

    供 WebSocket 执行请求与 HTTP 批量执行共用，返回 (effective, selected, err)：
    - err 非空表示失败，selected 为 None；
    - 成功时 selected 为规范化能力字典（含 "id"），可直接用于 get_raw_consumer/reserve_slots。
    """
    actuators = list_capabilities()
    if not actuators:
        return None, None, "没有可用的执行器，请先启动执行器服务"

    if preferred_actuator_id:
        selected = next(
            (cap for cap in actuators if cap.get("id") == preferred_actuator_id),
            None,
        )
        if selected is None:
            return None, None, f"执行器 {preferred_actuator_id} 不在线"
    else:
        selected = actuators[0]

    # master-ce 无 runtime_config，直接以选中执行器的能力生成简化 effective_runtime
    effective = {
        "actuator_id": selected["id"],
        "actuator_name": selected.get("name"),
        "browser_type": selected.get("default_browser"),
        "headless": not bool(selected.get("supports_headed", True)),
        "source_mode": "backend_resolve",
    }
    return effective, selected, ""

