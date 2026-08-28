"""
LangChain v1 中间件配置模块

提供统一的中间件配置，用于所有 Agent 创建。
包含：
- ModelRetryMiddleware: 模型调用重试（替代手动重试逻辑）
- ToolRetryMiddleware: 工具调用重试
- SummarizationMiddleware: 上下文摘要（替代 ConversationCompressor）
- HumanInTheLoopMiddleware: 人工审批（新增功能）
- 用户审批偏好：支持"记住审批选择"功能
"""

import ast
import logging
import re
from typing import Callable, List, Optional, Dict, Any, Iterable

from langchain.agents.middleware import (
    ModelRetryMiddleware,
    ToolRetryMiddleware,
    SummarizationMiddleware,
    HumanInTheLoopMiddleware,
)

from requirements.context_limits import (
    MODEL_CONTEXT_LIMITS,
    context_checker,
    get_context_limit_from_llm,
)

logger = logging.getLogger(__name__)


# ============== 模型能力分层（强模型/弱模型）==============
#
# 弱模型（如 qwen3-coder 等短上下文模型）启用更激进的上下文压缩与步数限制，
# 避免长循环导致上下文超限、provider 重试、页面卡死。
# 见 issue.md「Agent Loop 对于弱模型优化」。
#
# 默认调优参数（可在 LLMConfig.model_tier 切换，表单不暴露）：
WEAK_MODEL_TRIGGER_RATIO = 0.5       # 摘要触发阈值占 context_limit 的比例（强模型 0.75）
WEAK_MODEL_KEEP_MESSAGES = 2        # 摘要后保留最近消息数（强模型 4）
WEAK_MODEL_TRIM_FLOOR = 4000        # 待摘要消息裁剪下限 token（强模型 8000）
DEFAULT_MODEL_TIER = "strong"
VALID_MODEL_TIERS = ("strong", "weak")


def get_model_tier(llm_config) -> str:
    """
    从 LLMConfig 实例解析模型能力分层。

    返回 'strong' 或 'weak'，默认 'strong'。未知值或缺失字段降级为 'strong'，
    保证已有强模型配置行为零变化。
    """
    tier = getattr(llm_config, "model_tier", DEFAULT_MODEL_TIER)
    if tier not in VALID_MODEL_TIERS:
        return DEFAULT_MODEL_TIER
    return tier


_CONTENT_AUDIT_ERROR_CODES = {"CHAT_HANDLER_INPUT_AUDIT_FAIL"}
_CONTENT_AUDIT_FRIENDLY_MSG = (
    "当前输入内容触发了模型服务商的内容安全审核，请尝试调整输入内容后重试。"
)
_MODEL_COOLDOWN_ERROR_CODES = {"model_cooldown"}
_RATE_LIMIT_HINTS = (
    "rate limit",
    "too many requests",
    "429",
    "cooling down",
)
_HTTP_STATUS_RE = re.compile(
    r"(?:Error code:|HTTP\s+)(?P<status>\d{3})\b", re.IGNORECASE
)
_DURATION_WITH_UNIT_RE = re.compile(
    r"^(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?(?:(?P<seconds>\d+)s)?$",
    re.IGNORECASE,
)


def _fix_mojibake(text: str) -> str:
    """尝试修复 UTF-8 字节被误读为 Latin-1 产生的乱码。"""
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text


def _is_content_audit_error(exc: Exception) -> bool:
    """判断异常是否为内容审核拦截（不可通过重试恢复）。"""
    error_text = str(exc)
    return any(code in error_text for code in _CONTENT_AUDIT_ERROR_CODES)


def _iter_exception_chain(exc: BaseException, max_depth: int = 6):
    current: Optional[BaseException] = exc
    depth = 0
    seen: set[int] = set()

    while current is not None and depth < max_depth:
        current_id = id(current)
        if current_id in seen:
            break
        seen.add(current_id)
        yield current
        current = current.__cause__ or current.__context__
        depth += 1


def _parse_json_like_payload(raw: Any) -> Optional[Dict[str, Any]]:
    if isinstance(raw, dict):
        return raw

    if not isinstance(raw, str):
        return None

    text = raw.strip()
    if not text:
        return None

    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None

    try:
        payload = ast.literal_eval(text[start : end + 1])
    except (SyntaxError, ValueError):
        return None

    return payload if isinstance(payload, dict) else None


def _extract_provider_error_payload(exc: BaseException) -> Optional[Dict[str, Any]]:
    for current in _iter_exception_chain(exc):
        body = getattr(current, "body", None)
        payload = _parse_json_like_payload(body)
        if payload:
            return payload

        response = getattr(current, "response", None)
        if response is not None:
            try:
                response_payload = response.json()
            except Exception:
                response_payload = None
            payload = _parse_json_like_payload(response_payload)
            if payload:
                return payload

            payload = _parse_json_like_payload(getattr(response, "text", None))
            if payload:
                return payload

        payload = _parse_json_like_payload(str(current))
        if payload:
            return payload

    return None


def _extract_http_status_code(exc: BaseException) -> Optional[int]:
    for current in _iter_exception_chain(exc):
        status_code = getattr(current, "status_code", None)
        if isinstance(status_code, int):
            return status_code

        response = getattr(current, "response", None)
        response_status = getattr(response, "status_code", None)
        if isinstance(response_status, int):
            return response_status

        match = _HTTP_STATUS_RE.search(str(current))
        if match:
            return int(match.group("status"))

    return None


def _normalize_provider_error(payload: Dict[str, Any]) -> Dict[str, Any]:
    error = payload.get("error")
    return error if isinstance(error, dict) else payload


def _parse_retry_after_seconds(raw: Any) -> Optional[int]:
    if isinstance(raw, (int, float)):
        return max(1, int(raw))

    if not isinstance(raw, str):
        return None

    text = raw.strip().lower()
    if not text:
        return None

    try:
        return max(1, int(float(text)))
    except ValueError:
        pass

    duration_match = _DURATION_WITH_UNIT_RE.fullmatch(text)
    if not duration_match:
        return None

    hours = int(duration_match.group("hours") or 0)
    minutes = int(duration_match.group("minutes") or 0)
    seconds = int(duration_match.group("seconds") or 0)
    total_seconds = hours * 3600 + minutes * 60 + seconds
    return max(1, total_seconds) if total_seconds > 0 else None


def _extract_retry_after_metadata(
    exc: BaseException,
) -> tuple[Optional[int], Optional[str]]:
    for current in _iter_exception_chain(exc):
        response = getattr(current, "response", None)
        headers = getattr(response, "headers", None)
        if not headers:
            continue

        retry_after_ms = headers.get("retry-after-ms")
        if retry_after_ms:
            try:
                retry_after_seconds = max(1, int(float(retry_after_ms) / 1000))
            except (TypeError, ValueError):
                retry_after_seconds = None
            if retry_after_seconds is not None:
                return retry_after_seconds, None

        for header_name in (
            "retry-after",
            "x-ratelimit-reset-requests",
            "x-ratelimit-reset-tokens",
        ):
            header_value = headers.get(header_name)
            retry_after_seconds = _parse_retry_after_seconds(header_value)
            if retry_after_seconds is not None:
                return retry_after_seconds, None

    return None, None


def _format_retry_after_hint(
    reset_time: Optional[str], reset_seconds: Optional[int]
) -> str:
    if reset_time:
        return str(reset_time)

    if not isinstance(reset_seconds, int) or reset_seconds <= 0:
        return "稍后"

    hours, remainder = divmod(reset_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts: List[str] = []
    if hours:
        parts.append(f"{hours}小时")
    if minutes:
        parts.append(f"{minutes}分钟")
    if seconds and not hours:
        parts.append(f"{seconds}秒")
    return "".join(parts) or "稍后"


def get_user_friendly_llm_error(
    exc: Exception, error_field: str = "llm_interaction"
) -> Optional[Dict[str, Any]]:
    if _is_content_audit_error(exc):
        return {
            "status_code": 400,
            "message": _CONTENT_AUDIT_FRIENDLY_MSG,
            "errors": {error_field: [_CONTENT_AUDIT_FRIENDLY_MSG]},
            "error_code": "content_audit",
            "model": None,
            "reset_seconds": None,
            "reset_time": None,
        }

    payload = _extract_provider_error_payload(exc)
    provider_error = _normalize_provider_error(payload) if payload else {}
    status_code = _extract_http_status_code(exc)
    error_code = str(provider_error.get("code") or "").strip().lower() or None
    model = str(provider_error.get("model") or "").strip() or None
    reset_seconds = _parse_retry_after_seconds(provider_error.get("reset_seconds"))
    reset_time = str(provider_error.get("reset_time") or "").strip() or None
    if reset_seconds is None and not reset_time:
        reset_seconds, reset_time = _extract_retry_after_metadata(exc)
    error_text = str(exc).lower()

    is_model_cooldown = (
        error_code in _MODEL_COOLDOWN_ERROR_CODES or "cooling down" in error_text
    )
    is_rate_limit = (
        status_code == 429
        or is_model_cooldown
        or any(hint in error_text for hint in _RATE_LIMIT_HINTS)
        or "rate_limit" in (error_code or "")
    )

    if not is_rate_limit:
        return None

    if is_model_cooldown and error_code is None:
        error_code = "model_cooldown"

    if is_model_cooldown:
        retry_after = _format_retry_after_hint(reset_time, reset_seconds)
        if model:
            message = f"模型 {model} 当前处于冷却中，请在 {retry_after} 后重试，或切换其他可用模型。"
        else:
            message = f"当前模型服务处于冷却中，请在 {retry_after} 后重试，或切换其他可用模型。"
    else:
        message = "当前模型服务请求过于频繁，请稍后重试。"

    errors = {error_field: [message]}
    if error_code:
        errors["provider_code"] = [error_code]
    if model:
        errors["provider_model"] = [model]
    if reset_time:
        errors["retry_after"] = [reset_time]
    if reset_seconds is not None:
        errors["retry_after_seconds"] = [str(reset_seconds)]

    return {
        "status_code": 429,
        "message": message,
        "errors": errors,
        "error_code": error_code or "rate_limit",
        "model": model,
        "reset_seconds": reset_seconds,
        "reset_time": reset_time,
    }


def _format_exception_chain(exc: BaseException, max_depth: int = 4) -> str:
    """格式化异常链路，便于定位被包装/重抛后的真实根因。"""
    chain: List[str] = []
    current: Optional[BaseException] = exc
    depth = 0

    while current is not None and depth < max_depth:
        chain.append(f"{type(current).__name__}: {current}")
        current = current.__cause__ or current.__context__
        depth += 1

    if current is not None:
        chain.append("...")
    return " <- ".join(chain)


def _model_retry_should_retry(exc: Exception) -> bool:
    """记录每次模型调用失败，可重试错误继续重试。"""
    error_text = str(exc)

    if _is_content_audit_error(exc):
        logger.warning(
            "ModelRetryMiddleware: 内容审核拦截，不重试。error=%s",
            _fix_mojibake(error_text),
        )
        return False

    friendly_error = get_user_friendly_llm_error(exc)
    if friendly_error and friendly_error.get("error_code") == "model_cooldown":
        logger.warning(
            "ModelRetryMiddleware: 模型冷却中，不重试。error=%s",
            _fix_mojibake(error_text),
        )
        return False

    if isinstance(exc, ValueError) and "No generations found in stream" in error_text:
        logger.warning(
            "ModelRetryMiddleware: empty stream detected, will retry. "
            "error_type=%s, error=%s, chain=%s",
            type(exc).__name__,
            exc,
            _format_exception_chain(exc),
        )
        return True

    logger.warning(
        "ModelRetryMiddleware: model call attempt failed; retry if attempts remain. "
        "error_type=%s, error=%s, chain=%s",
        type(exc).__name__,
        exc,
        _format_exception_chain(exc),
    )
    return True


def _build_model_retry_failure_handler(
    total_attempts: int,
) -> Callable[[Exception], str]:
    """重试耗尽后的日志与返回文案（保持默认 continue 语义）。"""

    def _on_failure(exc: Exception) -> str:
        friendly_error = get_user_friendly_llm_error(exc)
        if friendly_error:
            logger.warning(
                "ModelRetryMiddleware: 返回友好错误。error_code=%s, error=%s",
                friendly_error.get("error_code"),
                _fix_mojibake(str(exc)),
            )
            return friendly_error["message"]

        logger.error(
            "ModelRetryMiddleware: model call failed after %d attempts. "
            "error_type=%s, error=%s, chain=%s",
            total_attempts,
            type(exc).__name__,
            exc,
            _format_exception_chain(exc),
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return (
            f"Model call failed after {total_attempts} attempts "
            f"with {type(exc).__name__}: {exc}"
        )

    return _on_failure


def _is_unreliable_default_detected_limit(
    model_name: str, detected_limit: Optional[int]
) -> bool:
    """
    判断检测到的上下文上限是否属于“不可靠默认回退”。

    典型场景：未知模型名（如 gpt-5.x）在无 profile 时走到 default=128000。
    这类值不应压制用户手动配置的 context_limit。
    """
    if not isinstance(detected_limit, int) or detected_limit <= 0:
        return False

    default_limit = int(MODEL_CONTEXT_LIMITS.get("default", 128000))
    if detected_limit != default_limit:
        return False

    normalized_name = (model_name or "").lower()
    for model_key in MODEL_CONTEXT_LIMITS.keys():
        if model_key == "default":
            continue
        if model_key in normalized_name:
            return False

    return True


def _calculate_overhead_tokens(
    model_name: str,
    tools: Optional[list] = None,
    system_prompt: Optional[str] = None,
) -> int:
    """
    计算系统提示词 + 工具定义 + 消息结构的真实 token 开销

    这些在整个对话中不变，只需在创建 token_counter 时算一次。

    Args:
        model_name: 模型名称，用于选择 tiktoken 编码器
        tools: 工具对象列表（有 .name, .description, .args_schema 等属性）
        system_prompt: 系统提示词内容
    """
    import json

    overhead = 0

    # 1. 系统提示词
    if system_prompt:
        overhead += context_checker.count_tokens(system_prompt, model_name)

    # 2. 工具定义（JSON Schema）
    if tools:
        for tool in tools:
            try:
                tool_text = getattr(tool, "name", "") or ""
                tool_text += getattr(tool, "description", "") or ""
                args_schema = getattr(tool, "args_schema", None)
                if args_schema:
                    if callable(getattr(args_schema, "model_json_schema", None)):
                        schema_dict = args_schema.model_json_schema()
                    elif callable(getattr(args_schema, "schema", None)):
                        schema_dict = args_schema.schema()
                    else:
                        schema_dict = {}
                    tool_text += json.dumps(schema_dict, ensure_ascii=False)
                overhead += context_checker.count_tokens(tool_text, model_name)
            except Exception:
                overhead += 200

    # 3. 消息结构开销（role token、分隔符等）
    overhead += 200

    return overhead


def _create_token_counter(model_name: str) -> Callable[[Iterable], int]:
    """
    创建纯消息内容的 Token 计数器

    注意：SummarizationMiddleware 内部会将此 counter 用于多个场景：
    1. _should_summarize() — 判断是否触发摘要
    2. _trim_messages_for_summary() — 裁剪待摘要消息
    3. _find_token_based_cutoff() — 二分搜索切割点

    场景 2 和 3 需要准确反映消息本身的大小，不能包含系统提示词和工具定义的开销。
    因此此 counter 只计算消息内容 token，不加 overhead。
    overhead 通过降低 trigger 阈值来补偿（在 get_summarization_middleware 中处理）。

    计算逻辑：
    1. 优先取最后一条有 usage_metadata 的消息的 total_tokens
       （这是 LLM API 返回的真实值，最准确）
    2. 如果没有 usage_metadata，使用 tiktoken 计算消息内容 token

    Args:
        model_name: 模型名称，用于 tiktoken 编码器
    """

    def token_counter(messages: Iterable) -> int:
        """计算当前上下文的 token 数（使用最后一条消息的 usage_metadata）"""
        try:
            messages_list = list(messages)

            # 优先使用最后一条消息的 usage_metadata（LLM API 返回的真实值）
            for msg in reversed(messages_list):
                if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                    usage = msg.usage_metadata
                    total = usage.get("total_tokens", 0) or (
                        usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                    )
                    if total > 0:
                        logger.debug(
                            f"token_counter: usage_metadata total = {total}"
                        )
                        return total

            # 没有 usage_metadata 时，tiktoken 计算消息内容
            content_tokens = 0
            for msg in messages_list:
                if hasattr(msg, "content") and msg.content:
                    content = (
                        msg.content
                        if isinstance(msg.content, str)
                        else str(msg.content)
                    )
                    content_tokens += context_checker.count_tokens(content, model_name)

            logger.debug(
                f"token_counter: tiktoken 估算 = {content_tokens}"
            )
            return content_tokens
        except Exception as e:
            logger.warning(f"Token 计数失败: {e}")
            # 返回保守估算值，避免返回 0 导致摘要永远不触发
            return len(messages_list) * 500 if messages_list else 0

    return token_counter


def _resolve_effective_context_limit(
    llm_config,
    llm=None,
    model_name: str = "gpt-4o",
    default_limit: int = 128000,
) -> int:
    """
    解析最终有效的上下文限制（安全优先）

    规则（用户优先）：
    1. 用户配置 context_limit（若有效）= 最高优先级，直接使用
    2. 无用户配置时，优先模型 profile
    3. profile 不可用时，使用可靠的后备映射
    4. 都不可用时使用默认值
    """
    config_context_limit = getattr(llm_config, "context_limit", None)
    config_limit = (
        int(config_context_limit)
        if isinstance(config_context_limit, int) and config_context_limit > 0
        else None
    )

    # 是否存在可靠的模型 profile 上下文上限
    profile_limit = None
    if llm is not None:
        profile = getattr(llm, "profile", None)
        if isinstance(profile, dict):
            max_input_tokens = profile.get("max_input_tokens")
            if isinstance(max_input_tokens, int) and max_input_tokens > 0:
                profile_limit = max_input_tokens

    detected_limit = None
    if llm is not None:
        try:
            detected = get_context_limit_from_llm(llm, fallback_model_name=model_name)
            if isinstance(detected, int) and detected > 0:
                detected_limit = detected
        except Exception as e:
            logger.warning("获取模型上下文限制失败，回退到配置/默认值: %s", e)

    normalized_name = (model_name or "").lower()
    trusted_fallback_prefixes = ("gpt-", "o1", "o3", "claude", "gemini")
    trusted_fallback = any(
        normalized_name.startswith(prefix) for prefix in trusted_fallback_prefixes
    )
    unreliable_detected_limit = _is_unreliable_default_detected_limit(
        model_name, detected_limit
    )

    # 1) 用户配置最高优先级
    if config_limit:
        if profile_limit and config_limit != profile_limit:
            logger.info(
                "模型 %s 存在 profile 上限=%d，按用户配置优先使用 context_limit=%d",
                model_name,
                profile_limit,
                config_limit,
            )
        elif (
            detected_limit
            and trusted_fallback
            and unreliable_detected_limit
            and config_limit != detected_limit
        ):
            logger.info(
                "模型 %s 无可靠 profile，回退上限=%d 来自默认映射，使用配置 context_limit=%d",
                model_name,
                detected_limit,
                config_limit,
            )
        elif detected_limit and not trusted_fallback and config_limit != detected_limit:
            logger.info(
                "模型 %s 无可靠 profile，使用配置 context_limit=%d（忽略回退估算=%d）",
                model_name,
                config_limit,
                detected_limit,
            )
        return int(config_limit)

    # 2) 无用户配置时，优先 profile（最可靠）
    if profile_limit:
        return int(profile_limit)

    # 3) 使用可靠回退
    if detected_limit and not unreliable_detected_limit:
        return int(detected_limit)

    # 4) 最后兜底
    if detected_limit and unreliable_detected_limit:
        logger.info(
            "模型 %s 无可靠 profile，回退上限=%d 来自默认映射，忽略该值并使用默认 context_limit=%d",
            model_name,
            detected_limit,
            default_limit,
        )

    return int(default_limit)


# ============== 重试中间件配置 ==============


def get_model_retry_middleware(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
) -> ModelRetryMiddleware:
    """
    获取模型调用重试中间件

    替代 agent_loop.py 中的手动重试逻辑：
    - 自动指数退避重试
    - 支持连接错误、API 错误等

    Args:
        max_retries: 最大重试次数
        backoff_factor: 退避因子（每次重试等待时间倍增）
        initial_delay: 初始延迟（秒）
        max_delay: 最大延迟（秒）
        jitter: 是否添加随机抖动
    """
    base_kwargs = {
        "max_retries": max_retries,
        "backoff_factor": backoff_factor,
        "initial_delay": initial_delay,
        "max_delay": max_delay,
        "jitter": jitter,
    }
    total_attempts = max_retries + 1

    try:
        return ModelRetryMiddleware(
            **base_kwargs,
            retry_on=_model_retry_should_retry,
            on_failure=_build_model_retry_failure_handler(total_attempts),
        )
    except TypeError as e:
        # 兼容旧版 langchain：若不支持 retry_on/on_failure 参数，则回退基础配置
        err_msg = str(e)
        if "retry_on" not in err_msg and "on_failure" not in err_msg:
            raise
        logger.warning(
            "ModelRetryMiddleware 当前版本不支持 retry_on/on_failure，"
            "回退为基础重试配置。error=%s",
            e,
        )

    return ModelRetryMiddleware(
        max_retries=max_retries,
        backoff_factor=backoff_factor,
        initial_delay=initial_delay,
        max_delay=max_delay,
        jitter=jitter,
    )


def get_tool_retry_middleware(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    initial_delay: float = 1.0,
    tools: Optional[List[str]] = None,
    on_failure: str = "continue",
) -> ToolRetryMiddleware:
    """
    获取工具调用重试中间件

    替代 graph.py 中 create_knowledge_tool 的手动重试逻辑

    Args:
        max_retries: 最大重试次数
        backoff_factor: 退避因子
        initial_delay: 初始延迟（秒）
        tools: 指定哪些工具需要重试（None 表示所有）
        on_failure: 失败后行为 ("continue" | "raise")
    """
    return ToolRetryMiddleware(
        max_retries=max_retries,
        backoff_factor=backoff_factor,
        initial_delay=initial_delay,
        tools=tools,
        on_failure=on_failure,
    )


# ============== 摘要中间件配置 ==============


def get_summarization_middleware(
    model=None,  # 可以是字符串或 BaseChatModel 实例
    trigger_tokens: int = 96000,  # 128k 的 75%
    keep_messages: int = 4,
    model_name: str = "gpt-4o",  # 用于精确 Token 计数
    tools: Optional[list] = None,  # 工具对象列表，用于计算真实开销
    system_prompt: Optional[str] = None,  # 系统提示词，用于计算真实开销
    trim_floor: int = 8000,  # 待摘要消息裁剪下限 token（弱模型下调）
) -> Optional[SummarizationMiddleware]:
    """
    获取摘要中间件

    替代 ConversationCompressor 的手动上下文压缩逻辑。
    token_counter 只计算消息内容 token（不含系统提示词和工具定义），
    overhead 通过降低 trigger 阈值来补偿，确保 trim 和 cutoff 逻辑不受污染。

    Args:
        model: 用于生成摘要的模型（字符串或 BaseChatModel 实例）
               如果为 None，则返回 None（不使用摘要中间件）
        trigger_tokens: 触发摘要的 Token 阈值（基于完整上下文限制计算）
        keep_messages: 保留最近的消息数量
        model_name: 模型名称，用于精确 Token 计数（基于 tiktoken）
        tools: 工具对象列表，传入后可精确计算工具定义的 token 开销
        system_prompt: 系统提示词内容，传入后可精确计算其 token 开销

    Returns:
        SummarizationMiddleware 实例，如果 model 为 None 则返回 None
    """
    if model is None:
        return None

    # 计算系统提示词 + 工具定义的真实 token 开销
    overhead = _calculate_overhead_tokens(model_name, tools, system_prompt)
    logger.info(
        "SummarizationMiddleware overhead: %d tokens (tools=%d, has_prompt=%s)",
        overhead,
        len(tools) if tools else 0,
        bool(system_prompt),
    )

    # token_counter 只计算消息内容，不含 overhead。
    # 所以 trigger 阈值要减去 overhead，确保在真实上下文接近阈值时触发摘要。
    effective_trigger = max(1, trigger_tokens - overhead)

    # trim_tokens_to_summarize：裁剪待摘要消息的上限。
    # 按 effective_trigger 的 50% 设置，确保摘要 LLM 调用不会超限。
    # 同时不能超过摘要模型自身的上下文能力（保守估计，取 trigger 的 50%）。
    # 弱模型上下文短，8000 下限会撑爆摘要调用，故下限参数化（弱模型传更小值）。
    trim_limit = max(effective_trigger // 2, trim_floor)

    logger.info(
        "SummarizationMiddleware config: trigger=%d (raw=%d - overhead=%d), trim_limit=%d",
        effective_trigger, trigger_tokens, overhead, trim_limit,
    )

    return SummarizationMiddleware(
        model=model,
        trigger=("tokens", effective_trigger),
        keep=("messages", keep_messages),
        token_counter=_create_token_counter(model_name),
        trim_tokens_to_summarize=trim_limit,
    )


# ============== 人工审批中间件配置 ==============

# 默认需要人工审批的高风险工具
DEFAULT_HIGH_RISK_TOOLS = {
    # 自动化脚本执行
    "execute_script": {
        "allowed_decisions": ["approve", "reject"],
        "description": "自动化脚本执行需要审批",
    },
    # 测试用例批量操作
    "batch_delete_testcases": {
        "allowed_decisions": ["approve", "reject"],
        "description": "批量删除测试用例需要审批",
    },
    # 数据库写操作
    "execute_sql": {
        "allowed_decisions": ["approve", "edit", "reject"],
        "description": "SQL 执行需要审批",
    },
    # ============== Playwright MCP 工具 ==============
    # 浏览器导航操作
    "playwright_navigate": {
        "allowed_decisions": ["approve", "reject"],
        "description": "浏览器导航需要审批",
    },
    # 页面点击操作
    "playwright_click": {
        "allowed_decisions": ["approve", "reject"],
        "description": "页面点击操作需要审批",
    },
    # 表单填写
    "playwright_fill": {
        "allowed_decisions": ["approve", "reject"],
        "description": "表单填写需要审批",
    },
    # 脚本执行
    "playwright_evaluate": {
        "allowed_decisions": ["approve", "reject"],
        "description": "JavaScript 脚本执行需要审批",
    },
}


def get_mcp_hitl_tools() -> Dict[str, Any]:
    """
    从 RemoteMCPConfig 动态加载需要 HITL 审批的工具

    Returns:
        Dict[tool_name, config]: 需要审批的工具配置
    """
    from mcp_tools.models import RemoteMCPConfig

    hitl_tools = {}

    mcp_configs = RemoteMCPConfig.objects.filter(is_active=True, require_hitl=True)

    for config in mcp_configs:
        # 如果 hitl_tools 为空，表示该 MCP 的所有工具都需要审批
        # 这种情况在实际触发时由 HumanInTheLoopMiddleware 的通配符逻辑处理
        # 这里我们用 mcp_name 作为前缀标识
        if config.hitl_tools:
            # 有指定工具列表
            for tool_name in config.hitl_tools:
                hitl_tools[tool_name] = {
                    "allowed_decisions": ["approve", "reject"],
                    "description": f"[{config.name}] {tool_name} 需要审批",
                }
        else:
            # 空列表表示该 MCP 所有工具都需要审批
            # 使用特殊标记，后续在中间件中处理
            hitl_tools[f"__mcp_all__{config.name}"] = {
                "allowed_decisions": ["approve", "reject"],
                "description": f"[{config.name}] 所有工具需要审批",
                "_mcp_name": config.name,
                "_all_tools": True,
            }

    logger.debug("从 MCP 配置加载 HITL 工具: %s", list(hitl_tools.keys()))
    return hitl_tools


def get_user_tool_approvals(user, session_id: Optional[str] = None) -> Dict[str, str]:
    """
    获取用户的工具审批偏好

    Args:
        user: Django User 对象
        session_id: 可选的会话ID，用于获取会话级别的偏好

    Returns:
        Dict[tool_name, policy]: 工具名到审批策略的映射
        例如: {"execute_script": "always_allow", "run_playwright": "ask_every_time"}
    """
    from langgraph_integration.models import UserToolApproval

    approvals = {}

    # 先获取永久偏好
    permanent_approvals = UserToolApproval.objects.filter(
        user=user, scope="permanent"
    ).values("tool_name", "policy")

    for approval in permanent_approvals:
        approvals[approval["tool_name"]] = approval["policy"]

    # 如果有会话ID，会话级偏好覆盖永久偏好
    if session_id:
        session_approvals = UserToolApproval.objects.filter(
            user=user, scope="session", session_id=session_id
        ).values("tool_name", "policy")

        for approval in session_approvals:
            approvals[approval["tool_name"]] = approval["policy"]

    return approvals


def build_dynamic_interrupt_on(
    base_tools: Dict[str, Any],
    user=None,
    session_id: Optional[str] = None,
    all_tool_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    根据用户偏好动态构建 interrupt_on 配置

    Args:
        base_tools: 基础的高风险工具配置
        user: Django User 对象（可选）
        session_id: 会话ID（可选）
        all_tool_names: 当前 Agent 的所有工具名列表（可选）
                        如果提供，则默认所有工具都需要审批

    Returns:
        动态生成的 interrupt_on 配置
    """
    # 获取用户偏好
    user_approvals = get_user_tool_approvals(user, session_id) if user else {}
    logger.info(f"[HITL] 用户偏好: {user_approvals}")

    # 如果提供了工具名列表，默认所有工具都需要审批
    if all_tool_names:
        logger.info(f"[HITL] 所有工具默认需要审批: {all_tool_names}")
        dynamic_config = {}
        for tool_name in all_tool_names:
            user_policy = user_approvals.get(tool_name)

            if user_policy == "always_allow":
                # 用户选择"始终允许"，跳过审批
                logger.debug("工具 %s 已被用户设为始终允许，跳过审批", tool_name)
                continue  # 不加入 interrupt_on，即不审批
            elif user_policy == "always_reject":
                # 用户选择"始终拒绝"，保持审批配置
                dynamic_config[tool_name] = {
                    "allowed_decisions": ["approve", "reject"],
                    "description": f"{tool_name} 需要审批",
                }
                logger.debug("工具 %s 已被用户设为始终拒绝", tool_name)
            else:
                # 默认需要审批
                # 优先使用 base_tools 中的配置（如有描述）
                if tool_name in base_tools:
                    dynamic_config[tool_name] = base_tools[tool_name]
                else:
                    dynamic_config[tool_name] = {
                        "allowed_decisions": ["approve", "reject"],
                        "description": f"{tool_name} 需要审批",
                    }

        logger.info(
            f"[HITL] 最终中断配置 (需要审批的工具): {list(dynamic_config.keys())}"
        )
        return dynamic_config

    # 传统模式：只审批 base_tools 中的工具
    if user is None:
        return base_tools

    dynamic_config = {}

    for tool_name, tool_config in base_tools.items():
        user_policy = user_approvals.get(tool_name)

        if user_policy == "always_allow":
            # 用户选择"始终允许"，跳过审批
            dynamic_config[tool_name] = False
            logger.debug("工具 %s 已被用户设为始终允许，跳过审批", tool_name)
        elif user_policy == "always_reject":
            # 用户选择"始终拒绝"，仍需审批但可以在前端自动拒绝
            # 这里仍保持审批配置，让前端处理自动拒绝逻辑
            dynamic_config[tool_name] = tool_config
            logger.debug("工具 %s 已被用户设为始终拒绝", tool_name)
        else:
            # 默认或"每次询问"
            dynamic_config[tool_name] = tool_config

    return dynamic_config


def get_human_in_the_loop_middleware(
    interrupt_on: Optional[Dict[str, Any]] = None,
    description_prefix: str = "工具执行待审批",
    user=None,
    session_id: Optional[str] = None,
    include_mcp_tools: bool = True,
    all_tool_names: Optional[List[str]] = None,
) -> HumanInTheLoopMiddleware:
    """
    获取人工审批中间件

    用于高风险操作前暂停执行，等待用户确认。
    支持根据用户偏好动态跳过已"始终允许"的工具。

    Args:
        interrupt_on: 需要中断的工具配置，格式：
            {
                "tool_name": True,  # 所有决策类型
                "tool_name": {"allowed_decisions": ["approve", "reject"]},
                "tool_name": False,  # 不需要审批
            }
        description_prefix: 中断消息前缀
        user: Django User 对象，用于读取用户审批偏好
        session_id: 会话ID，用于读取会话级别的偏好
        include_mcp_tools: 是否包含 MCP 配置中标记需要审批的工具
        all_tool_names: 当前 Agent 的所有工具名列表（可选）
                        如果提供，则默认所有工具都需要审批，用户可通过偏好跳过
    """
    base_config = dict(interrupt_on or DEFAULT_HIGH_RISK_TOOLS)

    # 动态加载 MCP 配置的 HITL 工具
    if include_mcp_tools:
        mcp_tools = get_mcp_hitl_tools()
        base_config.update(mcp_tools)

    # 根据用户偏好动态调整配置
    config = build_dynamic_interrupt_on(base_config, user, session_id, all_tool_names)

    return HumanInTheLoopMiddleware(
        interrupt_on=config,
        description_prefix=description_prefix,
    )


# ============== 组合中间件 ==============


def get_standard_middleware(
    enable_model_retry: bool = True,
    enable_tool_retry: bool = True,
    enable_summarization: bool = True,
    enable_hitl: bool = False,  # 人工审批默认关闭，按需开启
    hitl_tools: Optional[Dict[str, Any]] = None,
    hitl_user=None,  # 用于动态读取用户审批偏好
    hitl_session_id: Optional[str] = None,  # 用于会话级别偏好
    hitl_all_tool_names: Optional[List[str]] = None,  # 所有工具名，用于默认审批所有工具
    summarization_model=None,  # 需显式传入 LLM 实例或模型名
    summarization_trigger_tokens: int = 96000,
    summarization_keep_messages: int = 4,
    summarization_trim_floor: int = 8000,  # 待摘要消息裁剪下限（弱模型下调）
    model_name: str = "gpt-4o",  # 用于精确 Token 计数
    tools: Optional[list] = None,  # 工具对象列表，用于精确计算 token 开销
    system_prompt: Optional[str] = None,  # 系统提示词，用于精确计算 token 开销
) -> List:
    """
    获取标准中间件组合

    提供开箱即用的中间件配置，适用于大多数 Agent 场景

    Args:
        enable_model_retry: 是否启用模型重试
        enable_tool_retry: 是否启用工具重试
        enable_summarization: 是否启用摘要
        enable_hitl: 是否启用人工审批
        hitl_tools: 人工审批工具配置
        hitl_user: Django User 对象，用于读取用户审批偏好
        hitl_session_id: 会话ID，用于读取会话级别的偏好
        hitl_all_tool_names: 当前 Agent 的所有工具名，用于默认审批所有工具
        summarization_model: 摘要模型
        summarization_trigger_tokens: 摘要触发阈值
        summarization_keep_messages: 保留消息数
        model_name: 模型名称，用于精确 Token 计数

    Returns:
        中间件列表
    """
    middleware = []

    if enable_model_retry:
        middleware.append(get_model_retry_middleware())
        logger.debug("已添加 ModelRetryMiddleware")

    if enable_tool_retry:
        middleware.append(get_tool_retry_middleware())
        logger.debug("已添加 ToolRetryMiddleware")

    if enable_summarization and summarization_model is not None:
        summarization_mw = get_summarization_middleware(
            model=summarization_model,
            trigger_tokens=summarization_trigger_tokens,
            keep_messages=summarization_keep_messages,
            model_name=model_name,
            tools=tools,
            system_prompt=system_prompt,
            trim_floor=summarization_trim_floor,
        )
        if summarization_mw is not None:
            middleware.append(summarization_mw)
            logger.info(
                "✅ 已添加 SummarizationMiddleware (trigger_tokens=%d, keep_messages=%d, model=%s)",
                summarization_trigger_tokens,
                summarization_keep_messages,
                model_name,
            )
        else:
            logger.warning("⚠️ SummarizationMiddleware 创建失败，返回 None")
    else:
        logger.info(
            "⏭️ 跳过 SummarizationMiddleware: enable_summarization=%s, summarization_model=%s",
            enable_summarization,
            summarization_model is not None,
        )

    if enable_hitl:
        logger.info(
            "HITL 已启用，正在添加 HumanInTheLoopMiddleware, all_tool_names=%s",
            hitl_all_tool_names,
        )
        middleware.append(
            get_human_in_the_loop_middleware(
                interrupt_on=hitl_tools,
                user=hitl_user,
                session_id=hitl_session_id,
                all_tool_names=hitl_all_tool_names,
            )
        )
        logger.info(
            "已添加 HumanInTheLoopMiddleware (all_tools=%s)", bool(hitl_all_tool_names)
        )
    else:
        logger.info("HITL 未启用，跳过 HumanInTheLoopMiddleware")

    return middleware


def get_brain_middleware() -> List:
    """
    获取 Brain Agent 专用中间件

    Brain Agent 负责路由决策，不需要摘要和 HITL
    """
    return [
        get_model_retry_middleware(max_retries=2),
    ]


def get_chat_middleware(summarization_model=None) -> List:
    """
    获取 Chat Agent 专用中间件

    Chat Agent 需要上下文摘要支持长对话

    Args:
        summarization_model: 用于摘要的模型（LLM 实例或模型名）
    """
    return get_standard_middleware(
        enable_hitl=False,
        summarization_model=summarization_model,
        summarization_trigger_tokens=96000,
        summarization_keep_messages=4,
    )


def get_requirement_middleware(summarization_model=None) -> List:
    """
    获取 Requirement Agent 专用中间件

    Args:
        summarization_model: 用于摘要的模型（LLM 实例或模型名）
    """
    return get_standard_middleware(
        enable_hitl=False,
        summarization_model=summarization_model,
        summarization_trigger_tokens=96000,
        summarization_keep_messages=4,
    )


def get_testcase_middleware(summarization_model=None) -> List:
    """
    获取 TestCase Agent 专用中间件

    Args:
        summarization_model: 用于摘要的模型（LLM 实例或模型名）
    """
    return get_standard_middleware(
        enable_hitl=False,
        summarization_model=summarization_model,
        summarization_trigger_tokens=96000,
        summarization_keep_messages=4,
    )


def get_automation_middleware(summarization_model=None) -> List:
    """
    获取自动化执行 Agent 专用中间件

    包含人工审批，用于高风险的脚本执行操作

    Args:
        summarization_model: 用于摘要的模型（LLM 实例或模型名）
    """
    return get_standard_middleware(
        enable_hitl=True,
        summarization_model=summarization_model,
        hitl_tools={
            "execute_script": {
                "allowed_decisions": ["approve", "reject"],
                "description": "自动化脚本执行需要审批",
            },
            "run_playwright": {
                "allowed_decisions": ["approve", "reject"],
                "description": "浏览器自动化操作需要审批",
            },
        },
    )


# ============== 从 LLMConfig 构建中间件 ==============


def get_middleware_from_config(
    llm_config,
    llm=None,
    agent_type: str = "standard",
    user=None,
    session_id: Optional[str] = None,
    all_tool_names: Optional[List[str]] = None,
    tools: Optional[list] = None,
    system_prompt: Optional[str] = None,
) -> List:
    """
    从 LLMConfig 模型配置构建中间件列表

    统一的中间件构建入口，根据 LLMConfig 中的配置字段决定启用哪些中间件。

    Args:
        llm_config: LLMConfig 模型实例，包含以下关键字段：
            - enable_summarization: 是否启用上下文摘要
            - enable_hitl: 是否启用人工审批
            - context_limit: 上下文Token限制（用于计算摘要触发阈值）
            - name: 模型名称（用于精确 Token 计数）
        llm: 用于摘要的 LLM 实例（如果 enable_summarization=True 则必须提供）
        agent_type: Agent 类型，决定额外的中间件配置
            - "brain": Brain Agent，只需重试中间件
            - "standard": 标准 Agent
            - "automation": 自动化 Agent，强制启用 HITL
        user: Django User 对象，用于读取用户的审批偏好（"记住此选择"功能）
        session_id: 会话ID，用于读取会话级别的偏好
        all_tool_names: 当前 Agent 的所有工具名列表（可选）
                        如果提供，则默认所有工具都需要审批，用户可通过偏好跳过

    Returns:
        中间件列表

    Example:
        from langgraph_integration.models import LLMConfig
        from orchestrator_integration.middleware_config import get_middleware_from_config

        config = LLMConfig.objects.get(is_active=True)
        tool_names = [t.name for t in tools]  # 获取所有工具名
        middleware = get_middleware_from_config(config, llm=my_llm, user=request.user, all_tool_names=tool_names)
        agent = create_agent(llm, tools, middleware=middleware)
    """
    # Brain Agent 只需要轻量级重试
    if agent_type == "brain":
        return [get_model_retry_middleware(max_retries=2)]

    # 从 LLMConfig 读取配置
    enable_summarization = getattr(llm_config, "enable_summarization", True)
    enable_hitl = getattr(llm_config, "enable_hitl", False)
    model_name = getattr(llm_config, "name", "gpt-4o")

    # 上下文限制：用户配置值与模型检测值取更小值（安全优先）
    context_limit = _resolve_effective_context_limit(
        llm_config=llm_config,
        llm=llm,
        model_name=model_name,
        default_limit=128000,
    )

    # 自动化 Agent 强制启用 HITL
    if agent_type == "automation":
        enable_hitl = True

    # 模型能力分层：弱模型用更激进的摘要触发阈值与保留消息数，避免长循环撑爆上下文
    tier = get_model_tier(llm_config)
    if tier == "weak":
        trigger_ratio = WEAK_MODEL_TRIGGER_RATIO
        keep_messages = WEAK_MODEL_KEEP_MESSAGES
        trim_floor = WEAK_MODEL_TRIM_FLOOR
    else:
        trigger_ratio = 0.75
        keep_messages = 4
        trim_floor = 8000

    # 计算摘要触发阈值
    trigger_tokens = max(1, int(context_limit * trigger_ratio))

    # 决定摘要模型
    summarization_model = llm if enable_summarization else None

    # HITL 工具配置
    hitl_tools = None
    if agent_type == "automation":
        hitl_tools = {
            "execute_script": {
                "allowed_decisions": ["approve", "reject"],
                "description": "自动化脚本执行需要审批",
            },
            "run_playwright": {
                "allowed_decisions": ["approve", "reject"],
                "description": "浏览器自动化操作需要审批",
            },
        }

    logger.info(
        "从 LLMConfig 构建中间件: agent_type=%s, tier=%s, summarization=%s, hitl=%s, context_limit=%d, trigger_tokens=%d, keep_messages=%d, model=%s, user=%s, all_tools=%d",
        agent_type,
        tier,
        enable_summarization,
        enable_hitl,
        context_limit,
        trigger_tokens,
        keep_messages,
        model_name,
        user.username if user else None,
        len(all_tool_names) if all_tool_names else 0,
    )

    return get_standard_middleware(
        enable_model_retry=True,
        enable_tool_retry=True,
        enable_summarization=enable_summarization,
        enable_hitl=enable_hitl,
        hitl_tools=hitl_tools,
        hitl_user=user,
        hitl_session_id=session_id,
        hitl_all_tool_names=all_tool_names,
        summarization_model=summarization_model,
        summarization_trigger_tokens=trigger_tokens,
        summarization_keep_messages=keep_messages,
        summarization_trim_floor=trim_floor,
        model_name=model_name,
        tools=tools,
        system_prompt=system_prompt,
    )


# ============== 异步版本 ==============


async def get_mcp_hitl_tools_async() -> Dict[str, Any]:
    """获取 MCP 配置中标记为需要审批的工具（异步版本）"""
    from asgiref.sync import sync_to_async
    from mcp_tools.models import RemoteMCPConfig

    hitl_tools = {}

    @sync_to_async
    def get_mcp_configs():
        return list(RemoteMCPConfig.objects.filter(is_active=True, require_hitl=True))

    mcp_configs = await get_mcp_configs()

    for config in mcp_configs:
        if config.hitl_tools:
            for tool_name in config.hitl_tools:
                hitl_tools[tool_name] = {
                    "allowed_decisions": ["approve", "reject"],
                    "description": f"[{config.name}] {tool_name} 需要审批",
                }
        else:
            hitl_tools[f"__mcp_all__{config.name}"] = {
                "allowed_decisions": ["approve", "reject"],
                "description": f"[{config.name}] 所有工具需要审批",
                "_mcp_name": config.name,
                "_all_tools": True,
            }

    logger.debug("从 MCP 配置加载 HITL 工具: %s", list(hitl_tools.keys()))
    return hitl_tools


async def get_user_tool_approvals_async(
    user, session_id: Optional[str] = None
) -> Dict[str, str]:
    """获取用户的工具审批偏好（异步版本）"""
    from asgiref.sync import sync_to_async
    from langgraph_integration.models import UserToolApproval

    approvals = {}

    @sync_to_async
    def get_permanent_approvals():
        return list(
            UserToolApproval.objects.filter(user=user, scope="permanent").values(
                "tool_name", "policy"
            )
        )

    @sync_to_async
    def get_session_approvals():
        return list(
            UserToolApproval.objects.filter(
                user=user, scope="session", session_id=session_id
            ).values("tool_name", "policy")
        )

    permanent_approvals = await get_permanent_approvals()
    for approval in permanent_approvals:
        approvals[approval["tool_name"]] = approval["policy"]

    if session_id:
        session_approvals = await get_session_approvals()
        for approval in session_approvals:
            approvals[approval["tool_name"]] = approval["policy"]

    return approvals


async def build_dynamic_interrupt_on_async(
    base_tools: Dict[str, Any],
    user=None,
    session_id: Optional[str] = None,
    all_tool_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """根据用户偏好动态构建 interrupt_on 配置（异步版本）"""
    config = dict(base_tools)

    if all_tool_names:
        for tool_name in all_tool_names:
            if tool_name not in config:
                config[tool_name] = {
                    "allowed_decisions": ["approve", "reject"],
                    "description": f"工具 {tool_name} 需要审批",
                }

    if not user:
        return config

    user_approvals = await get_user_tool_approvals_async(user, session_id)

    for tool_name, policy in user_approvals.items():
        if policy == "always_allow":
            config[tool_name] = False
            logger.debug("用户偏好: %s -> 始终允许，跳过审批", tool_name)
        elif policy == "always_reject":
            config[tool_name] = False
            logger.debug(
                "用户偏好: %s -> 始终拒绝，跳过审批（调用将被阻止）", tool_name
            )

    return config


async def get_human_in_the_loop_middleware_async(
    interrupt_on: Optional[Dict[str, Any]] = None,
    description_prefix: str = "需要审批:",
    user=None,
    session_id: Optional[str] = None,
    include_mcp_tools: bool = True,
    all_tool_names: Optional[List[str]] = None,
) -> HumanInTheLoopMiddleware:
    """获取人工审批中间件（异步版本）"""
    base_config = dict(interrupt_on or DEFAULT_HIGH_RISK_TOOLS)

    if include_mcp_tools:
        mcp_tools = await get_mcp_hitl_tools_async()
        base_config.update(mcp_tools)

    config = await build_dynamic_interrupt_on_async(
        base_config, user, session_id, all_tool_names
    )

    return HumanInTheLoopMiddleware(
        interrupt_on=config,
        description_prefix=description_prefix,
    )


async def get_standard_middleware_async(
    enable_model_retry: bool = True,
    enable_tool_retry: bool = True,
    enable_summarization: bool = True,
    enable_hitl: bool = False,
    hitl_tools: Optional[Dict[str, Any]] = None,
    hitl_user=None,
    hitl_session_id: Optional[str] = None,
    hitl_all_tool_names: Optional[List[str]] = None,
    summarization_model=None,
    summarization_trigger_tokens: int = 96000,
    summarization_keep_messages: int = 4,
    summarization_trim_floor: int = 8000,  # 待摘要消息裁剪下限（弱模型下调）
    model_name: str = "gpt-4o",
    tools: Optional[list] = None,
    system_prompt: Optional[str] = None,
) -> List:
    """获取标准中间件组合（异步版本）"""
    middleware = []

    if enable_model_retry:
        middleware.append(get_model_retry_middleware())
        logger.debug("已添加 ModelRetryMiddleware")

    if enable_tool_retry:
        middleware.append(get_tool_retry_middleware())
        logger.debug("已添加 ToolRetryMiddleware")

    if enable_summarization and summarization_model is not None:
        summarization_mw = get_summarization_middleware(
            model=summarization_model,
            trigger_tokens=summarization_trigger_tokens,
            keep_messages=summarization_keep_messages,
            model_name=model_name,
            tools=tools,
            system_prompt=system_prompt,
            trim_floor=summarization_trim_floor,
        )
        if summarization_mw is not None:
            middleware.append(summarization_mw)
            logger.info(
                "✅ 已添加 SummarizationMiddleware (trigger_tokens=%d, keep_messages=%d, model=%s)",
                summarization_trigger_tokens,
                summarization_keep_messages,
                model_name,
            )
        else:
            logger.warning("⚠️ SummarizationMiddleware 创建失败，返回 None")
    else:
        logger.info(
            "⏭️ 跳过 SummarizationMiddleware: enable_summarization=%s, summarization_model=%s",
            enable_summarization,
            summarization_model is not None,
        )

    if enable_hitl:
        hitl_mw = await get_human_in_the_loop_middleware_async(
            interrupt_on=hitl_tools,
            user=hitl_user,
            session_id=hitl_session_id,
            all_tool_names=hitl_all_tool_names,
        )
        middleware.append(hitl_mw)
        logger.debug("已添加 HumanInTheLoopMiddleware（异步版本）")

    return middleware


async def get_middleware_from_config_async(
    llm_config,
    llm=None,
    agent_type: str = "standard",
    user=None,
    session_id: Optional[str] = None,
    all_tool_names: Optional[List[str]] = None,
    tools: Optional[list] = None,
    system_prompt: Optional[str] = None,
) -> List:
    """从 LLMConfig 模型配置构建中间件列表（异步版本）"""
    if agent_type == "brain":
        return [get_model_retry_middleware(max_retries=2)]

    enable_summarization = getattr(llm_config, "enable_summarization", True)
    enable_hitl = getattr(llm_config, "enable_hitl", False)
    model_name = getattr(llm_config, "name", "gpt-4o")

    context_limit = _resolve_effective_context_limit(
        llm_config=llm_config,
        llm=llm,
        model_name=model_name,
        default_limit=128000,
    )

    if agent_type == "automation":
        enable_hitl = True

    # 模型能力分层：弱模型用更激进的摘要触发阈值与保留消息数
    tier = get_model_tier(llm_config)
    if tier == "weak":
        trigger_ratio = WEAK_MODEL_TRIGGER_RATIO
        keep_messages = WEAK_MODEL_KEEP_MESSAGES
        trim_floor = WEAK_MODEL_TRIM_FLOOR
    else:
        trigger_ratio = 0.75
        keep_messages = 4
        trim_floor = 8000

    trigger_tokens = max(1, int(context_limit * trigger_ratio))
    summarization_model = llm if enable_summarization else None

    hitl_tools = None
    if agent_type == "automation":
        hitl_tools = {
            "execute_script": {
                "allowed_decisions": ["approve", "reject"],
                "description": "自动化脚本执行需要审批",
            },
            "run_playwright": {
                "allowed_decisions": ["approve", "reject"],
                "description": "浏览器自动化操作需要审批",
            },
        }

    logger.info(
        "从 LLMConfig 构建中间件（异步）: agent_type=%s, tier=%s, summarization=%s, hitl=%s, context_limit=%d, trigger_tokens=%d, keep_messages=%d, model=%s, user=%s, all_tools=%d",
        agent_type,
        tier,
        enable_summarization,
        enable_hitl,
        context_limit,
        trigger_tokens,
        keep_messages,
        model_name,
        user.username if user else None,
        len(all_tool_names) if all_tool_names else 0,
    )

    return await get_standard_middleware_async(
        enable_model_retry=True,
        enable_tool_retry=True,
        enable_summarization=enable_summarization,
        enable_hitl=enable_hitl,
        hitl_tools=hitl_tools,
        hitl_user=user,
        hitl_session_id=session_id,
        hitl_all_tool_names=all_tool_names,
        summarization_model=summarization_model,
        summarization_trigger_tokens=trigger_tokens,
        summarization_keep_messages=keep_messages,
        summarization_trim_floor=trim_floor,
        model_name=model_name,
        tools=tools,
        system_prompt=system_prompt,
    )
