"""UI automation effective runtime config resolve.

Merge priority (all endpoints share this rule):
  run_options > env_policy > actuator_default > hard_default

timeout is always milliseconds in the public contract.
launch_timeout remains node-private and is not part of env policy.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional


SUPPORTED_BROWSERS = ("chromium", "firefox", "webkit")

HARD_DEFAULTS: dict[str, Any] = {
    "browser": "chromium",
    "headless": True,
    "viewport_width": 1280,
    "viewport_height": 720,
    "timeout": 30000,
}

SOURCE_RUN = "run_options"
SOURCE_ENV = "env"
SOURCE_ACTUATOR = "actuator_default"
SOURCE_HARD = "hard_default"
SOURCE_FORCED = "forced_by_runtime"

RUNTIME_BROWSER_KEYS = (
    "browser",
    "headless",
    "viewport_width",
    "viewport_height",
    "timeout",
)


class RuntimeConfigError(ValueError):
    """Raised when runtime config cannot be resolved or matched."""


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


def normalize_timeout_ms(value: Any, *, unit_hint: Optional[str] = None) -> Optional[int]:
    """Normalize timeout to milliseconds.

    unit_hint:
      - "ms": treat value as ms
      - "s": treat value as seconds
    """
    number = normalize_positive_int(value, minimum=1)
    if number is None:
        return None

    hint = (unit_hint or "").strip().lower()
    if hint in {"s", "sec", "secs", "second", "seconds"}:
        return number * 1000
    return number


def _pick_layer(
    key: str,
    run_options: dict[str, Any],
    env_policy: dict[str, Any],
    actuator_default: dict[str, Any],
) -> tuple[Any, str]:
    if key in run_options and run_options[key] is not None:
        return run_options[key], SOURCE_RUN
    if key in env_policy and env_policy[key] is not None:
        return env_policy[key], SOURCE_ENV
    if key in actuator_default and actuator_default[key] is not None:
        return actuator_default[key], SOURCE_ACTUATOR
    return deepcopy(HARD_DEFAULTS[key]), SOURCE_HARD


def normalize_run_options(run_options: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not run_options:
        return {}
    if not isinstance(run_options, dict):
        raise RuntimeConfigError("run_options must be an object")

    normalized: dict[str, Any] = {}
    if "browser" in run_options:
        browser = normalize_browser(run_options.get("browser"))
        if run_options.get("browser") is not None and browser is None:
            raise RuntimeConfigError(
                f"unsupported browser in run_options: {run_options.get('browser')}"
            )
        if browser is not None:
            normalized["browser"] = browser
    if "headless" in run_options:
        headless = normalize_bool(run_options.get("headless"))
        if run_options.get("headless") is not None and headless is None:
            raise RuntimeConfigError("invalid headless in run_options")
        if headless is not None:
            normalized["headless"] = headless
    if "viewport_width" in run_options:
        width = normalize_positive_int(run_options.get("viewport_width"), minimum=1)
        if run_options.get("viewport_width") is not None and width is None:
            raise RuntimeConfigError("invalid viewport_width in run_options")
        if width is not None:
            normalized["viewport_width"] = width
    if "viewport_height" in run_options:
        height = normalize_positive_int(run_options.get("viewport_height"), minimum=1)
        if run_options.get("viewport_height") is not None and height is None:
            raise RuntimeConfigError("invalid viewport_height in run_options")
        if height is not None:
            normalized["viewport_height"] = height
    if "timeout" in run_options:
        timeout = normalize_timeout_ms(run_options.get("timeout"), unit_hint="ms")
        if run_options.get("timeout") is not None and timeout is None:
            raise RuntimeConfigError("invalid timeout in run_options")
        if timeout is not None:
            normalized["timeout"] = timeout
    return normalized


def extract_env_policy(env_config: Optional[Any]) -> dict[str, Any]:
    """Extract browser policy fields from env config dict or model-like object."""
    if env_config is None:
        return {}

    def _get(key: str, default: Any = None) -> Any:
        if isinstance(env_config, dict):
            return env_config.get(key, default)
        return getattr(env_config, key, default)

    policy: dict[str, Any] = {}
    browser = normalize_browser(_get("browser"))
    if browser is not None:
        policy["browser"] = browser
    headless = normalize_bool(_get("headless"))
    if headless is not None:
        policy["headless"] = headless
    width = normalize_positive_int(_get("viewport_width"), minimum=1)
    if width is not None:
        policy["viewport_width"] = width
    height = normalize_positive_int(_get("viewport_height"), minimum=1)
    if height is not None:
        policy["viewport_height"] = height
    timeout = normalize_timeout_ms(_get("timeout"), unit_hint="ms")
    if timeout is not None:
        policy["timeout"] = timeout
    return policy


def extract_actuator_default(actuator_info: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Node defaults from capability / local config (not business policy)."""
    if not actuator_info:
        return {}

    defaults: dict[str, Any] = {}
    browser = normalize_browser(
        actuator_info.get("default_browser")
        or actuator_info.get("browser_type")
        or actuator_info.get("browser")
    )
    if browser is not None:
        defaults["browser"] = browser

    headless = normalize_bool(actuator_info.get("headless"))
    if headless is not None:
        defaults["headless"] = headless

    width = normalize_positive_int(actuator_info.get("viewport_width"), minimum=1)
    if width is not None:
        defaults["viewport_width"] = width
    height = normalize_positive_int(actuator_info.get("viewport_height"), minimum=1)
    if height is not None:
        defaults["viewport_height"] = height

    if "action_timeout_ms" in actuator_info:
        timeout = normalize_timeout_ms(actuator_info.get("action_timeout_ms"), unit_hint="ms")
    elif "timeout" in actuator_info:
        timeout = normalize_timeout_ms(actuator_info.get("timeout"), unit_hint="ms")
    elif "action_timeout" in actuator_info:
        timeout = normalize_timeout_ms(actuator_info.get("action_timeout"), unit_hint="s")
    else:
        timeout = None
    if timeout is not None:
        defaults["timeout"] = timeout
    return defaults


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


def resolve_effective_runtime(
    *,
    env_policy: Optional[dict[str, Any]] = None,
    actuator_default: Optional[dict[str, Any]] = None,
    run_options: Optional[dict[str, Any]] = None,
    env_config_id: Optional[int] = None,
    env_name: Optional[str] = None,
    base_url: Optional[str] = None,
    db: Optional[dict[str, Any]] = None,
    actuator_id: Optional[str] = None,
    actuator_name: Optional[str] = None,
    force_headless: bool = False,
    source_mode: str = "backend_resolve",
) -> dict[str, Any]:
    """Resolve effective browser runtime config with source tracking."""
    policy = extract_env_policy(env_policy)
    defaults = extract_actuator_default(actuator_default or {})
    options = normalize_run_options(run_options)

    effective: dict[str, Any] = {}
    source: dict[str, str] = {}
    forced_by_runtime: list[str] = []

    for key in RUNTIME_BROWSER_KEYS:
        value, layer = _pick_layer(key, options, policy, defaults)
        effective[key] = value
        source[key] = layer

    if force_headless and not effective.get("headless"):
        effective["headless"] = True
        source["headless"] = SOURCE_FORCED
        forced_by_runtime.append("headless")

    viewport_explicit = (
        source.get("viewport_width") in {SOURCE_RUN, SOURCE_ENV}
        or source.get("viewport_height") in {SOURCE_RUN, SOURCE_ENV}
    )

    return {
        "env_config_id": env_config_id,
        "env_name": env_name,
        "base_url": base_url or "",
        "browser": effective["browser"],
        "headless": bool(effective["headless"]),
        "viewport_width": int(effective["viewport_width"]),
        "viewport_height": int(effective["viewport_height"]),
        "timeout": int(effective["timeout"]),
        "db": db or {},
        "actuator_id": actuator_id,
        "actuator_name": actuator_name,
        "source": source,
        "forced_by_runtime": forced_by_runtime,
        "viewport_explicit": viewport_explicit,
        "source_mode": source_mode,
    }


def env_model_to_policy_dict(env) -> dict[str, Any]:
    """Build env payload used by resolve from UiEnvironmentConfig model."""
    if env is None:
        return {}
    if isinstance(env, dict):
        return env
    db: dict[str, Any] = {
        "db_type": getattr(env, "db_type", None),
        "db_c_status": getattr(env, "db_c_status", False),
        "db_rud_status": getattr(env, "db_rud_status", False),
        "mysql_config": getattr(env, "mysql_config", None),
    }
    return {
        "id": getattr(env, "id", None),
        "name": getattr(env, "name", None),
        "base_url": getattr(env, "base_url", None) or "",
        "browser": getattr(env, "browser", None),
        "headless": getattr(env, "headless", None),
        "viewport_width": getattr(env, "viewport_width", None),
        "viewport_height": getattr(env, "viewport_height", None),
        "timeout": getattr(env, "timeout", None),
        "extra_config": getattr(env, "extra_config", None),
        "db": db,
        "db_type": db["db_type"],
        "db_c_status": db["db_c_status"],
        "db_rud_status": db["db_rud_status"],
        "mysql_config": db["mysql_config"],
    }


def resolve_from_env_and_actuator(
    env=None,
    actuator_info: Optional[dict[str, Any]] = None,
    run_options: Optional[dict[str, Any]] = None,
    *,
    actuator_id: Optional[str] = None,
    force_headless: bool = False,
    source_mode: str = "backend_resolve",
) -> dict[str, Any]:
    env_payload = env_model_to_policy_dict(env)
    capability = normalize_capability(actuator_info)
    actuator_default = extract_actuator_default(actuator_info or {})
    db = env_payload.get("db") if isinstance(env_payload.get("db"), dict) else {
        "db_type": env_payload.get("db_type"),
        "db_c_status": env_payload.get("db_c_status"),
        "db_rud_status": env_payload.get("db_rud_status"),
        "mysql_config": env_payload.get("mysql_config"),
    }
    return resolve_effective_runtime(
        env_policy=env_payload,
        actuator_default=actuator_default,
        run_options=run_options,
        env_config_id=env_payload.get("id") or env_payload.get("env_config_id"),
        env_name=env_payload.get("name") or env_payload.get("env_name"),
        base_url=env_payload.get("base_url"),
        db=db,
        actuator_id=actuator_id or capability.get("id"),
        actuator_name=capability.get("name"),
        force_headless=force_headless,
        source_mode=source_mode,
    )


def match_capability(
    effective: dict[str, Any],
    capability: dict[str, Any],
    *,
    require_slot: bool = True,
) -> tuple[bool, str]:
    """Return (ok, error_message)."""
    cap = normalize_capability(capability)
    if not cap.get("is_open", True):
        return False, f"执行器 {cap.get('name')} 未开放接单"

    browser = effective.get("browser")
    if browser not in cap.get("supported_browsers", []):
        return False, (
            f"执行器 {cap.get('name')} 不支持浏览器 {browser}，"
            f"支持: {', '.join(cap.get('supported_browsers') or [])}"
        )

    headless = bool(effective.get("headless"))
    if headless and not cap.get("supports_headless", True):
        return False, f"执行器 {cap.get('name')} 不支持 headless 模式"
    if not headless and not cap.get("supports_headed", True):
        return False, f"执行器 {cap.get('name')} 不支持有头模式"

    if require_slot:
        max_slots = int(cap.get("max_slots") or 1)
        busy = int(cap.get("busy_slots") or 0)
        if busy >= max_slots:
            return False, f"执行器 {cap.get('name')} 已无空闲 slot（{busy}/{max_slots}）"

    return True, ""


def select_actuator(
    actuators: list[dict[str, Any]],
    effective: dict[str, Any],
    *,
    preferred_id: Optional[str] = None,
) -> tuple[Optional[dict[str, Any]], str]:
    """Select an online actuator that matches effective runtime.

    Returns (capability_dict_with_id, error_message).
    """
    normalized = []
    for item in actuators:
        cap = normalize_capability(item)
        if not cap.get("id"):
            continue
        normalized.append(cap)

    if preferred_id:
        target = next((c for c in normalized if c["id"] == preferred_id), None)
        if target is None:
            return None, f"执行器 {preferred_id} 不在线"
        ok, err = match_capability(effective, target, require_slot=True)
        if not ok:
            return None, err
        return target, ""

    candidates = []
    errors = []
    for cap in normalized:
        ok, err = match_capability(effective, cap, require_slot=True)
        if ok:
            candidates.append(cap)
        else:
            errors.append(err)

    if not candidates:
        if not normalized:
            return None, "没有可用的执行器，请先启动执行器服务"
        browser = effective.get("browser")
        for err in errors:
            if browser and str(browser) in err:
                return None, err
        return None, errors[0] if errors else "没有匹配能力的在线执行器"

    def _score(cap: dict[str, Any]) -> tuple[int, int, str]:
        max_slots = int(cap.get("max_slots") or 1)
        busy = int(cap.get("busy_slots") or 0)
        free = max_slots - busy
        return (-free, busy, str(cap.get("id") or ""))

    candidates.sort(key=_score)
    return candidates[0], ""



def redact_db_config(db: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Return a copy of db config with password-like fields stripped."""
    if not isinstance(db, dict):
        return {}
    sensitive_keys = {
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "access_key",
        "secret_key",
    }

    def _scrub(value: Any) -> Any:
        if isinstance(value, dict):
            cleaned: dict[str, Any] = {}
            for key, item in value.items():
                if str(key).lower() in sensitive_keys:
                    continue
                cleaned[key] = _scrub(item)
            return cleaned
        if isinstance(value, list):
            return [_scrub(item) for item in value]
        return value

    return _scrub(db)


def public_effective_runtime(effective: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Browser/runtime fields safe to return to API/UI clients (no db secrets)."""
    if not isinstance(effective, dict):
        return {}
    return {
        "env_config_id": effective.get("env_config_id"),
        "env_name": effective.get("env_name"),
        "base_url": effective.get("base_url"),
        "browser": effective.get("browser"),
        "headless": effective.get("headless"),
        "viewport_width": effective.get("viewport_width"),
        "viewport_height": effective.get("viewport_height"),
        "timeout": effective.get("timeout"),
        "actuator_id": effective.get("actuator_id"),
        "actuator_name": effective.get("actuator_name"),
        "source": effective.get("source") or {},
        "forced_by_runtime": effective.get("forced_by_runtime") or [],
        "viewport_explicit": effective.get("viewport_explicit", False),
        "source_mode": effective.get("source_mode"),
    }


def build_environment_snapshot(effective: dict[str, Any]) -> dict[str, Any]:
    """Snapshot stored on UiExecutionRecord.environment (db secrets redacted)."""
    return {
        "env_config_id": effective.get("env_config_id"),
        "env_name": effective.get("env_name"),
        "base_url": effective.get("base_url"),
        "browser": effective.get("browser"),
        "headless": effective.get("headless"),
        "viewport_width": effective.get("viewport_width"),
        "viewport_height": effective.get("viewport_height"),
        "timeout": effective.get("timeout"),
        "actuator_id": effective.get("actuator_id"),
        "actuator_name": effective.get("actuator_name"),
        "source": effective.get("source") or {},
        "forced_by_runtime": effective.get("forced_by_runtime") or [],
        "viewport_explicit": effective.get("viewport_explicit", False),
        "source_mode": effective.get("source_mode"),
        "db": redact_db_config(effective.get("db") if isinstance(effective.get("db"), dict) else {}),
    }