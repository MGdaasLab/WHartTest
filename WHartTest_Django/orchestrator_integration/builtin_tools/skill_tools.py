"""
Skill 工具

提供渐进式加载的 Skill 系统：
- read_skill_content: 读取 Skill 的 SKILL.md 内容（按需加载）
- execute_skill_script: 执行 Skill 的 shell 命令（支持持久化浏览器会话）
"""

import logging
import subprocess
import os
import shutil
import threading
import json
import time
import mimetypes
import re
from typing import Optional

from pydantic import BaseModel, Field
from langchain_core.tools import tool as langchain_tool
from django.conf import settings

from .output_sanitizer import strip_terminal_control_sequences
from .persistent_playwright import PlaywrightSessionManager, extract_runjs_args
from .skill_exec_guard import (
    SkillCommandError,
    SkillCommandResult,
    audit_skill_execution,
    build_skill_env,
    contains_unsafe_shell_syntax,
    legacy_shell_exec_enabled,
    parse_skill_command,
    run_skill_command,
    run_skill_command_via_shell,
    validate_skill_command,
)
from .skill_runner_client import (
    SkillRunnerUnavailable,
    runner_exec_mode,
    submit_job,
)

logger = logging.getLogger("orchestrator_integration")

_playwright_session_manager: Optional[PlaywrightSessionManager] = None
_playwright_session_manager_lock = threading.Lock()
_ARTIFACT_EXTENSIONS = {
    ".drawio",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".pdf",
    ".html",
    ".htm",
    ".txt",
    ".json",
    ".csv",
    ".xml",
    ".zip",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
}
_MAX_ARTIFACT_SIZE_BYTES = 50 * 1024 * 1024
# 批量执行上限：命令条数与并发数都由模型指定，必须有硬上限，
# 否则一次调用即可在 backend 容器内扇出大量子进程。
_MAX_SKILL_BATCH_COMMANDS = 50
_MAX_SKILL_BATCH_WORKERS = 16
_ARTIFACT_TOKEN_RE = re.compile(
    r"(?P<path>(?:[A-Za-z]:)?[^\s<>\"'`|]+?\.(?:drawio|png|jpe?g|gif|svg|pdf|html?|txt|json|csv|xml|zip|docx?|xlsx?|pptx?))",
    re.IGNORECASE,
)
_QUOTED_ARTIFACT_TOKEN_RE = re.compile(
    r"[`'\"](?P<path>[^`'\"]+?\.(?:drawio|png|jpe?g|gif|svg|pdf|html?|txt|json|csv|xml|zip|docx?|xlsx?|pptx?))[`'\"]",
    re.IGNORECASE,
)
_PLAYWRIGHT_CLI_LAUNCHER_RE = re.compile(
    r"^(?P<launcher>\s*(?:playwright-cli|npx(?:\s+--no-install)?\s+playwright-cli))(?=\s|$)",
    re.IGNORECASE,
)
_PLAYWRIGHT_CLI_TOKEN_RE = re.compile(
    r"\s+(?P<token>(?:\"(?:\\.|[^\"\\])*\"|'[^']*'|[^\s\"'\\]+|\\.)+)"
)
_BROWSER_USE_COMMAND_RE = re.compile(r"(?:^|\s)browser-use(?:\s|$)")
_BROWSER_USE_LOCAL_ENV_OVERRIDE_RE = re.compile(
    r"(?:^|\s)(?:BU_CDP_URL|BU_CDP_WS|BU_BROWSER_ID|BH_AGENT_WORKSPACE|LLM_BROWSER_AUTO_CHROME)=[^\s]+"
)
_BROWSER_USE_CLOUD_NAME_RE = re.compile(r"(?:^|\s)BU_NAME=[^\s]+")


class PlaywrightCliIsolationError(ValueError):
    """Raised when a playwright-cli command cannot be safely isolated."""


def _strip_matching_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _contains_unsafe_shell_syntax(command: str) -> bool:
    """兼容既有调用点；实现已收口到 skill_exec_guard.contains_unsafe_shell_syntax。"""
    return contains_unsafe_shell_syntax(command)


def _build_playwright_cli_session_name(
    *,
    user_id: object,
    project_id: object,
    chat_session_id: object,
    explicit_session: Optional[str] = None,
) -> str:
    context_payload = json.dumps(
        [user_id, project_id, chat_session_id],
        ensure_ascii=True,
        separators=(",", ":"),
        default=str,
    )
    context_digest = hashlib.sha256(context_payload.encode("utf-8")).hexdigest()[:16]
    session_name = f"whart-{context_digest}"
    if explicit_session is None:
        return session_name

    explicit_session = explicit_session.strip()
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "-", explicit_session)
    sanitized = sanitized.strip("-._")[:24] or "session"
    explicit_digest = hashlib.sha256(explicit_session.encode("utf-8")).hexdigest()[:8]
    return f"{session_name}-{sanitized}-{explicit_digest}"


def _normalize_playwright_cli_command(
    command: str,
    *,
    user_id: object,
    project_id: object,
    chat_session_id: object,
) -> str:
    """Namespace one supported playwright-cli command to its chat context."""
    launcher_match = _PLAYWRIGHT_CLI_LAUNCHER_RE.match(command)
    if launcher_match is None:
        raise PlaywrightCliIsolationError(
            "playwright-cli Skill 只允许直接调用 playwright-cli、"
            "npx playwright-cli 或 npx --no-install playwright-cli"
        )

    if _contains_unsafe_shell_syntax(command):
        raise PlaywrightCliIsolationError(
            "playwright-cli 每次只允许执行单条命令，请使用 execute_skill_batch 执行多条命令"
        )

    tail = command[launcher_match.end() :]
    tokens: list[tuple[int, int, str]] = []
    cursor = 0
    while cursor < len(tail):
        token_match = _PLAYWRIGHT_CLI_TOKEN_RE.match(tail, cursor)
        if token_match is None:
            break
        tokens.append(
            (token_match.start(), token_match.end(), token_match.group("token"))
        )
        cursor = token_match.end()

    session_options: list[tuple[int, int, str, set[int]]] = []
    index = 0
    while index < len(tokens):
        start, end, raw = tokens[index]
        normalized_raw = _strip_matching_quotes(raw)
        equals_match = re.match(
            r"^(?:-s|--session)=(.*)$", normalized_raw, re.IGNORECASE
        )
        if equals_match is not None:
            explicit_value = _strip_matching_quotes(equals_match.group(1))
            session_options.append((start, end, explicit_value, {index}))
            index += 1
            continue
        if normalized_raw.lower() in {"-s", "--session"}:
            if index + 1 >= len(tokens):
                raise PlaywrightCliIsolationError(
                    "playwright-cli 会话参数缺少会话名称"
                )
            _, value_end, value_raw = tokens[index + 1]
            explicit_value = _strip_matching_quotes(value_raw)
            session_options.append(
                (start, value_end, explicit_value, {index, index + 1})
            )
            index += 2
            continue
        index += 1

    if len(session_options) > 1:
        raise PlaywrightCliIsolationError(
            "playwright-cli 命令包含多个会话参数，无法安全确定目标会话"
        )

    session_token_indexes = session_options[0][3] if session_options else set()
    command_name = ""
    for token_index, (_, _, raw) in enumerate(tokens):
        if token_index in session_token_indexes:
            continue
        normalized_token = _strip_matching_quotes(raw)
        if normalized_token.startswith("-"):
            continue
        command_name = normalized_token.lower()
        break

    if command_name in {"close-all", "kill-all"}:
        raise PlaywrightCliIsolationError(
            f"playwright-cli {command_name} 是宿主机全局操作，平台已拒绝执行"
        )
    normalized_tokens = [_strip_matching_quotes(raw).lower() for _, _, raw in tokens]
    if command_name == "attach" and any(
        token in {"--cdp", "--extension"}
        or token.startswith("--cdp=")
        or token.startswith("--extension=")
        for token in normalized_tokens
    ):
        raise PlaywrightCliIsolationError(
            "playwright-cli attach 会连接共享浏览器，无法保证多用户隔离，平台已拒绝执行"
        )

    explicit_session = session_options[0][2] if session_options else None
    session_name = _build_playwright_cli_session_name(
        user_id=user_id,
        project_id=project_id,
        chat_session_id=chat_session_id,
        explicit_session=explicit_session,
    )
    launcher = command[: launcher_match.end()]
    if session_options:
        session_start, session_end, _, _ = session_options[0]
        tail = f"{tail[:session_start]}{tail[session_end:]}"

    # 平台默认浏览器注入：
    # @playwright/cli 不指定 --browser 时默认走 Google Chrome 渠道（找 /opt/google/chrome/chrome），
    # 而镜像里只有自带的 Chromium，会报 "Chromium distribution 'chrome' is not found"。
    # 这里在 open 子命令缺省时补 --browser chromium（镜像自带、可离线、无 Chrome 授权问题）；
    # 显式传了 --browser / --browser= 则尊重调用方。可用 PLAYWRIGHT_CLI_DEFAULT_BROWSER 覆盖。
    default_browser = str(
        getattr(settings, "PLAYWRIGHT_CLI_DEFAULT_BROWSER", None) or "chromium"
    ).strip()
    if command_name == "open" and default_browser:
        has_browser_flag = any(
            token == "--browser" or token.startswith("--browser=")
            for _, _, token in tokens
        ) or "--browser" in command
        if not has_browser_flag:
            tail = f"{tail} --browser {default_browser}"

    normalized_tail = f" -s={session_name}{tail}"
    return f"{launcher}{normalized_tail}"


class ExecuteSkillScriptInput(BaseModel):
    skill_name: str = Field(
        ...,
        min_length=1,
        description="要执行的 Skill 名称。先用 read_skill_content 获取完整说明。",
    )
    command: str = Field(
        ...,
        min_length=1,
        description="要在 Skill 目录中执行的单条 shell 命令。",
    )
    session_id: str = Field(
        default="",
        description="可选会话 ID。仅在 playwright-cli 多步骤执行时使用；留空表示不复用浏览器会话。",
    )


class SkillBatchCommandInput(BaseModel):
    skill_name: str = Field(..., min_length=1, description="Skill 名称。")
    command: str = Field(..., min_length=1, description="单条 shell 命令。")
    session_id: str = Field(
        default="",
        description="可选会话 ID。留空表示不复用浏览器会话。",
    )


class ExecuteSkillBatchInput(BaseModel):
    commands: list[SkillBatchCommandInput] = Field(
        ...,
        min_length=1,
        max_length=_MAX_SKILL_BATCH_COMMANDS,
        description="待执行的结构化命令列表。不要传 JSON 字符串。",
    )
    parallel: bool = Field(
        default=True,
        description="是否并发执行。多个彼此独立的命令推荐开启。",
    )
    max_workers: int = Field(
        default=10,
        ge=1,
        le=_MAX_SKILL_BATCH_WORKERS,
        description="批量模式下的最大并发数。",
    )


def _normalize_optional_session_id(session_id: Optional[str]) -> Optional[str]:
    normalized = (session_id or "").strip()
    return normalized or None


def _sanitize_runtime_path_segment(value: Optional[str], default: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return default

    sanitized = raw.replace("..", "_")
    for separator in filter(None, {os.sep, os.altsep}):
        sanitized = sanitized.replace(separator, "_")

    sanitized = sanitized.strip(" .")
    return sanitized or default


def _build_skill_screenshots_dir(
    project_id: Optional[int] = None,
    case_dir_key: Optional[str] = None,
) -> str:
    project_segment = str(project_id if project_id is not None else 0)
    case_segment = _sanitize_runtime_path_segment(case_dir_key, "_default")
    return os.path.abspath(
        os.path.join(
            settings.MEDIA_ROOT,
            "skill_runtime",
            "screenshots",
            project_segment,
            case_segment,
        )
    )


# 截图/产物目录空闲超过该时长（秒）才允许清理，避免 chat_session_id 变化时误删正在使用的截图
_SKILL_DIR_STALE_SECONDS = 5 * 60 * 60


def _dir_latest_mtime(path: str) -> float:
    """目录树内最新文件 mtime；无文件返回 0（目录结构变更不算活跃写入）。"""
    latest = 0.0
    for root, _, files in os.walk(path):
        for name in files:
            try:
                mtime = os.path.getmtime(os.path.join(root, name))
            except OSError:
                continue
            if mtime > latest:
                latest = mtime
    return latest


def _prepare_skill_screenshots_dir(
    project_id: Optional[int] = None,
    case_dir_key: Optional[str] = None,
) -> str:
    screenshots_dir = _build_skill_screenshots_dir(project_id, case_dir_key)
    if not case_dir_key:
        os.makedirs(screenshots_dir, exist_ok=True)
        return screenshots_dir

    should_clear = False
    if os.path.exists(screenshots_dir):
        latest = _dir_latest_mtime(screenshots_dir)
        if latest and time.time() - latest > _SKILL_DIR_STALE_SECONDS:
            should_clear = True

    if should_clear:
        shutil.rmtree(screenshots_dir, ignore_errors=True)
        logger.info(f"[execute_skill_script] 清空旧截图目录: {screenshots_dir}")

    os.makedirs(screenshots_dir, exist_ok=True)
    return screenshots_dir


def _build_skill_artifacts_dir(
    project_id: Optional[int] = None,
    case_dir_key: Optional[str] = None,
) -> str:
    project_segment = str(project_id if project_id is not None else 0)
    case_segment = _sanitize_runtime_path_segment(case_dir_key, "_default")
    return os.path.abspath(
        os.path.join(
            settings.MEDIA_ROOT,
            "skill_runtime",
            "artifacts",
            project_segment,
            case_segment,
        )
    )


def _prepare_skill_artifacts_dir(
    project_id: Optional[int] = None,
    case_dir_key: Optional[str] = None,
) -> str:
    artifacts_dir = _build_skill_artifacts_dir(project_id, case_dir_key)
    if not case_dir_key:
        os.makedirs(artifacts_dir, exist_ok=True)
        return artifacts_dir

    should_clear = False
    if os.path.exists(artifacts_dir):
        latest = _dir_latest_mtime(artifacts_dir)
        if latest and time.time() - latest > _SKILL_DIR_STALE_SECONDS:
            should_clear = True

    if should_clear:
        shutil.rmtree(artifacts_dir, ignore_errors=True)
        logger.info(f"[execute_skill_script] 清空旧产物目录: {artifacts_dir}")

    os.makedirs(artifacts_dir, exist_ok=True)
    return artifacts_dir


def _is_allowed_artifact_file(file_path: str) -> bool:
    if not file_path or not os.path.isfile(file_path) or os.path.islink(file_path):
        return False
    suffix = os.path.splitext(file_path)[1].lower()
    if suffix not in _ARTIFACT_EXTENSIONS:
        return False
    if os.path.basename(file_path).startswith("."):
        return False
    try:
        return os.path.getsize(file_path) <= _MAX_ARTIFACT_SIZE_BYTES
    except OSError:
        return False


def _snapshot_artifact_files(root_dir: str) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    if not root_dir or not os.path.isdir(root_dir):
        return snapshot

    for current_root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules")]
        for name in files:
            full_path = os.path.join(current_root, name)
            if not _is_allowed_artifact_file(full_path):
                continue
            rel_path = os.path.relpath(full_path, root_dir).replace(os.sep, "/")
            snapshot[rel_path] = full_path
    return snapshot


def _path_to_media_url(file_path: str) -> Optional[str]:
    try:
        media_root = os.path.abspath(settings.MEDIA_ROOT)
        candidate = os.path.abspath(file_path)
        if os.path.commonpath([media_root, candidate]) != media_root:
            return None
        relative_path = os.path.relpath(candidate, media_root).replace(os.sep, "/")
        return f"{settings.MEDIA_URL.rstrip('/')}/{relative_path}"
    except Exception:
        return None


def _build_artifact_payload(file_path: str) -> Optional[dict[str, object]]:
    media_url = _path_to_media_url(file_path)
    if not media_url:
        return None

    mime_type, _ = mimetypes.guess_type(file_path)
    if file_path.lower().endswith(".drawio"):
        mime_type = mime_type or "application/vnd.jgraph.mxfile"

    payload: dict[str, object] = {
        "type": "file",
        "name": os.path.basename(file_path),
        "url": media_url,
        "path": os.path.relpath(file_path, settings.MEDIA_ROOT).replace(os.sep, "/"),
        "mime_type": mime_type or "application/octet-stream",
    }
    try:
        payload["size"] = os.path.getsize(file_path)
    except OSError:
        pass
    return payload


def _extract_artifact_candidates(text: str) -> list[str]:
    if not text:
        return []

    seen: set[str] = set()
    candidates: list[str] = []
    strip_chars = " \t\r\n()[]{}<>,;:：。，“”‘’"

    for pattern in (_QUOTED_ARTIFACT_TOKEN_RE, _ARTIFACT_TOKEN_RE):
        for match in pattern.finditer(text):
            candidate = (match.group("path") or "").strip(strip_chars)
            if "：" in candidate:
                candidate = candidate.split("：")[-1].strip(strip_chars)
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            candidates.append(candidate)

    return candidates


def _find_named_file(root_dir: str, candidate: str) -> Optional[str]:
    if not root_dir or not os.path.isdir(root_dir):
        return None

    normalized_candidate = candidate.replace("\\", os.sep)
    joined_path = os.path.join(root_dir, normalized_candidate.lstrip("./"))
    if _is_allowed_artifact_file(joined_path):
        return joined_path

    basename = os.path.basename(normalized_candidate)
    if not basename:
        return None

    for current_root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules")]
        if basename in files:
            full_path = os.path.join(current_root, basename)
            if _is_allowed_artifact_file(full_path):
                return full_path
    return None


def _collect_skill_artifacts(
    output_text: str,
    *,
    skill_dir: str,
    artifacts_dir: str,
    artifacts_before: dict[str, str],
    screenshots_dir: Optional[str] = None,
) -> list[dict[str, object]]:
    collected: list[dict[str, object]] = []
    seen_urls: set[str] = set()

    # 允许收集的根目录：产物目录、skill 自身目录、以及本次会话的截图目录。
    # 截图目录必须在内——playwright-cli 的截图默认落在 SCREENSHOT_DIR，
    # 模型在输出里引用该绝对路径时应能作为可下载附件返回。
    allowed_roots = [root for root in (artifacts_dir, skill_dir, screenshots_dir) if root]

    def add_file(file_path: Optional[str]) -> None:
        if not file_path or not _is_allowed_artifact_file(file_path):
            return
        # 真实路径必须落回上述允许根之一：防止用符号链接把别的项目文件
        # 伪装成本次产物挂成可下载附件。
        if not any(_is_within_directory(file_path, root) for root in allowed_roots):
            logger.warning(
                "[execute_skill_script] 拒绝收集越界产物路径: %s", file_path
            )
            return
        payload = _build_artifact_payload(file_path)
        if not payload:
            return
        media_url = str(payload.get("url") or "")
        if not media_url or media_url in seen_urls:
            return
        seen_urls.add(media_url)
        collected.append(payload)

    artifacts_after = _snapshot_artifact_files(artifacts_dir)
    for rel_path, full_path in artifacts_after.items():
        if rel_path not in artifacts_before:
            add_file(full_path)

    for candidate in _extract_artifact_candidates(output_text):
        if candidate.startswith("/media/"):
            continue
        if os.path.isabs(candidate):
            # 绝对路径统一交给 add_file 做「真实路径必须落在允许根内」的判定，
            # 因为结果文本由模型与命令输出控制。
            add_file(candidate)
            continue
        add_file(_find_named_file(artifacts_dir, candidate))
        add_file(_find_named_file(skill_dir, candidate))
        if screenshots_dir:
            add_file(_find_named_file(screenshots_dir, candidate))

    return collected


def _is_within_directory(file_path: str, root_dir: Optional[str]) -> bool:
    """判断 file_path 的真实路径是否位于 root_dir 之内。

    两侧都过 ``realpath``：只比较 ``abspath`` 时，skill 可以在产物目录里放一个指向
    别处的符号链接，从而让 ``<artifacts>/link/other.txt`` 这类路径通过前缀检查。
    """
    if not file_path or not root_dir:
        return False
    try:
        root = os.path.realpath(root_dir)
        target = os.path.realpath(file_path)
        return os.path.commonpath([root, target]) == root
    except ValueError:
        return False


def _finalize_skill_result(
    result_output: str,
    *,
    skill_dir: str,
    artifacts_dir: str,
    artifacts_before: dict[str, str],
    screenshots_dir: Optional[str] = None,
) -> str:
    artifacts = _collect_skill_artifacts(
        result_output,
        skill_dir=skill_dir,
        artifacts_dir=artifacts_dir,
        artifacts_before=artifacts_before,
        screenshots_dir=screenshots_dir,
    )
    if not artifacts:
        return result_output

    text_content = result_output.strip() if result_output and result_output.strip() else ""
    if not text_content:
        text_content = f"已生成 {len(artifacts)} 个文件，可直接下载。"

    payload = [{"type": "text", "text": text_content}, *artifacts]
    return json.dumps(payload, ensure_ascii=False)


def _get_playwright_session_manager() -> PlaywrightSessionManager:
    """延迟初始化，避免在 import 时启动后台清理线程（线程安全）"""
    global _playwright_session_manager
    if _playwright_session_manager is None:
        with _playwright_session_manager_lock:
            if _playwright_session_manager is None:
                idle_timeout = getattr(
                    settings, "PLAYWRIGHT_BROWSER_SESSION_IDLE_TIMEOUT_SECONDS", 15 * 60
                )
                max_sessions = getattr(settings, "PLAYWRIGHT_BROWSER_MAX_SESSIONS", 20)
                _playwright_session_manager = PlaywrightSessionManager(
                    idle_timeout_seconds=int(idle_timeout),
                    max_sessions=int(max_sessions),
                )
    return _playwright_session_manager


def _resolve_skill_runtime_api_key(user_id: int) -> tuple[str, str]:
    """解析 Skill 运行时使用的 API Key。

    优先级：
    1. 非空的 settings/环境变量 WHARTTEST_API_KEY（运维覆盖）
    2. 当前对话用户名下最新一条有效 API Key
    3. 空字符串（不注入，保留 skill 脚本内默认值）

    Returns:
        (api_key, source_label) source_label 仅用于日志，不含密钥内容。
    """
    configured = (
        getattr(settings, "WHARTTEST_API_KEY", None)
        or os.environ.get("WHARTTEST_API_KEY")
        or ""
    ).strip()
    if configured:
        return configured, "env_or_settings"

    if not user_id:
        return "", "none"

    try:
        from api_keys.models import APIKey
    except ImportError:
        logger.debug(
            "[execute_skill_script] api_keys 应用不可用，跳过用户 Key 解析 user_id=%s",
            user_id,
        )
        return "", "none"

    try:
        for key_obj in APIKey.objects.filter(user_id=user_id, is_active=True).order_by(
            "-created_at"
        ):
            if key_obj.is_valid() and (key_obj.key or "").strip():
                return key_obj.key.strip(), f"user_key_id={key_obj.id}"
    except Exception as e:
        logger.error(
            "[execute_skill_script] 读取用户 API Key 失败 user_id=%s: %s",
            user_id,
            e,
            exc_info=True,
        )
        return "", "error"
    return "", "none"


def _resolve_skill_runtime_backend_url() -> str:
    """Skill 在 backend 进程内执行时，默认回环访问本服务。"""
    configured = (
        getattr(settings, "WHARTTEST_BACKEND_URL", None)
        or os.environ.get("WHARTTEST_BACKEND_URL")
        or ""
    ).strip()
    if configured:
        return configured.rstrip("/")
    # 容器/本机同进程：默认本机 8000，避免 skill 脚本默认 127.0.0.1 与部署端口不一致时无覆盖
    return "http://127.0.0.1:8000"


def _visible_skills_for_user(user_id: Optional[int]):
    """与 ``skills/views.py`` 的可见性口径对齐：本人创建的 + 全局共享的。

    工具层此前用 ``filter(name=..., is_active=True)`` 全库查询，导致任意用户都能
    通过 Agent 读取并执行他人 ``is_global=False`` 的私有 Skill，绕过 API 层授权。
    无用户上下文时仅暴露全局共享 Skill。
    """
    from django.db.models import Q

    from skills.models import Skill

    if user_id:
        return Skill.objects.filter(Q(creator_id=user_id) | Q(is_global=True))
    return Skill.objects.filter(is_global=True)


def get_skill_tools(
    user_id: int,
    project_id: Optional[int] = None,
    test_case_id: Optional[int] = None,
    chat_session_id: Optional[str] = None,
) -> list[object]:
    """获取 Skill 工具列表（Skills 全局共享，不限制项目）"""
    current_user_id = user_id
    current_project_id = project_id if project_id is not None else 0
    current_test_case_id = test_case_id
    current_chat_session_id = chat_session_id

    @langchain_tool
    def read_skill_content(skill_name: str) -> str:
        """
        读取指定 Skill 的完整 SKILL.md 内容。

        当你需要使用某个 Skill 时，先调用此工具获取详细的使用说明。
        系统提示词中只包含 Skill 的名称和简短描述，完整的指令和示例需要通过此工具获取。

        Args:
            skill_name: Skill 名称

        Returns:
            SKILL.md 的完整内容，包含详细的使用说明和示例
        """
        logger.info(f"[read_skill_content] skill_name={skill_name}")
        try:
            visible_skills = _visible_skills_for_user(current_user_id)
            skill = visible_skills.filter(name=skill_name, is_active=True).first()

            if not skill:
                available = visible_skills.filter(is_active=True).values_list(
                    "name", flat=True
                )
                available_list = list(available)
                return f"错误: 未找到名为 '{skill_name}' 的 Skill。可用的 Skills: {available_list}"

            if not skill.skill_content:
                return f"错误: Skill '{skill_name}' 没有 SKILL.md 内容"

            return skill.skill_content

        except Exception as e:
            logger.error(f"[read_skill_content] 读取失败: {e}", exc_info=True)
            return f"错误: {str(e)}"

    def _execute_single_skill_script(
        skill_name: str,
        command: str,
        session_id: Optional[str] = None,
    ) -> str:
        """内部函数：执行单条 Skill 命令"""
        from skills.models import Skill
        skill_name = skill_name.strip()
        command = command.strip()
        session_id = _normalize_optional_session_id(session_id)

        if not skill_name or not command:
            return "错误: skill_name 和 command 必须是非空字符串"

        logger.info(
            f"[execute_skill_script] skill_name={skill_name}, command={command}"
        )

        try:
            visible_skills = _visible_skills_for_user(current_user_id)
            skill = visible_skills.filter(name=skill_name, is_active=True).first()

            if not skill:
                available = visible_skills.filter(is_active=True).values_list(
                    "name", flat=True
                )
                available_list = list(available)
                audit_skill_execution(
                    decision="deny",
                    user_id=current_user_id,
                    project_id=current_project_id,
                    chat_session_id=current_chat_session_id,
                    test_case_id=current_test_case_id,
                    skill_name=skill_name,
                    argv=[command],
                    reason="skill 不可见或未启用",
                )
                return f"错误: 未找到名为 '{skill_name}' 的 Skill。可用的 Skills: {available_list}"

            skill_dir = skill.get_full_path()
            if not skill_dir or not os.path.isdir(skill_dir):
                return f"错误: Skill '{skill_name}' 目录不存在"

            logger.info(f"[execute_skill_script] 在目录 {skill_dir} 执行: {command}")

            # 运行时变量单独收集，稍后与白名单继承的环境合并：平台机密
            # （DJANGO_SECRET_KEY / POSTGRES_PASSWORD / LLM 网关 Key 等）不再进入 skill 子进程。
            runtime_env: dict[str, str] = {}
            # 1) 运维配置 / 2) 当前用户有效 API Key / 3) 不注入（保留脚本默认）
            backend_url = _resolve_skill_runtime_backend_url()
            api_key, key_source = _resolve_skill_runtime_api_key(current_user_id)
            if backend_url:
                runtime_env["WHARTTEST_BACKEND_URL"] = backend_url
            if api_key:
                runtime_env["WHARTTEST_API_KEY"] = api_key
                logger.info(
                    "[execute_skill_script] 已注入运行时 API Key (user_id=%s, source=%s)",
                    current_user_id,
                    key_source,
                )
            else:
                logger.warning(
                    "[execute_skill_script] 未找到可用 API Key (user_id=%s, source=%s)，"
                    "将依赖 skill 脚本内默认值（可能 401）",
                    current_user_id,
                    key_source,
                )

            case_dir_key = None
            if current_test_case_id:
                case_dir_key = str(current_test_case_id)
            elif session_id:
                case_dir_key = session_id

            screenshots_dir = _prepare_skill_screenshots_dir(
                project_id=current_project_id,
                case_dir_key=case_dir_key,
            )
            runtime_env["SCREENSHOT_DIR"] = screenshots_dir
            artifacts_dir = _prepare_skill_artifacts_dir(
                project_id=current_project_id,
                case_dir_key=case_dir_key,
            )
            runtime_env["SKILL_OUTPUT_DIR"] = artifacts_dir
            runtime_env["ARTIFACT_DIR"] = artifacts_dir
            env = build_skill_env(runtime_env=runtime_env)
            artifacts_before = _snapshot_artifact_files(artifacts_dir)

            # Windows 兼容：将单引号包裹的参数转换为双引号（用于 cmd.exe）
            # 同时处理多行字符串，将换行符转换为单行
            import platform
            import re

            exec_command = command
            if platform.system() == "Windows":
                # 处理多行字符串：将双引号内的换行符替换为空格或分号
                def collapse_multiline(m):
                    content = m.group(1)
                    # 将换行替换为空格，保持代码可执行
                    collapsed = " ".join(
                        line.strip() for line in content.split("\n") if line.strip()
                    )
                    return f'"{collapsed}"'

                # 匹配 "..." 形式的多行字符串
                exec_command = re.sub(r'"([^"]*\n[^"]*)"', collapse_multiline, command)

                # 单引号转双引号
                def convert_quotes(m):
                    param = m.group(1)
                    value = m.group(2)
                    escaped = value.replace('"', '\\"')
                    return f'{param}"{escaped}"'

                exec_command = re.sub(
                    r"(--\w+\s+)'([^']*)'", convert_quotes, exec_command
                )

                if exec_command != command:
                    logger.info(f"[execute_skill_script] Windows 命令转换完成")

            # 执行模式前置判定：runner 模式要求所有 skill 命令都进沙箱，因此
            # 持久化浏览器会话（在 backend 进程内长驻 node 执行模型给的 JS）不再启用，
            # 否则 session_id + run.js 这条路径会绕过第 2 层隔离。
            use_runner = runner_exec_mode() == "runner" and not legacy_shell_exec_enabled()
            if use_runner and session_id and skill_name == "playwright-cli":
                logger.info(
                    "[execute_skill_script] SKILL_EXEC_MODE=runner："
                    "跳过 backend 进程内的持久化浏览器会话，命令将提交给 skill-runner 无状态执行"
                )

            # 持久化 Playwright 会话路径
            # 仅当 session_id 存在 + playwright 技能 + run.js 调用，且非 runner 模式时启用
            if (
                session_id
                and skill_name in ("playwright-skill", "playwright-cli")
                and not use_runner
            ):
                run_js_args = extract_runjs_args(exec_command)
                if run_js_args is not None:
                    # 调试日志
                    logger.debug(f"[execute_skill_script] run_js_args: {run_js_args}")
                    # session_key 包含 chat_session_id 以隔离不同对话的浏览器会话
                    chat_id_part = current_chat_session_id or "default"
                    session_key = f"{current_user_id}_{current_project_id}_{chat_id_part}_{session_id}"
                    try:
                        manager = _get_playwright_session_manager()
                        output = manager.execute_run_js(
                            session_key=session_key,
                            skill_dir=skill_dir,
                            run_js_args=run_js_args,
                            env=env,
                            timeout_seconds=120,
                        )
                        logger.info(
                            f"[execute_skill_script] 持久化会话执行完成, session_key={session_key}"
                        )
                        cleaned_output = strip_terminal_control_sequences(output)
                        result_output = (
                            cleaned_output.strip()
                            if cleaned_output.strip()
                            else "(无输出)"
                        )
                        result_output = (
                            f'[PERSISTENT_SESSION] session_id={session_id}\n'
                            f'[SCREENSHOT_DIR] {screenshots_dir}\n'
                            f'{result_output}\n'
                            f'[提示] 后续步骤请继续使用 session_id="{session_id}"；截图已保存在 {screenshots_dir}'
                        )
                        return _finalize_skill_result(
                            result_output,
                            skill_dir=skill_dir,
                            artifacts_dir=artifacts_dir,
                            artifacts_before=artifacts_before,
                            screenshots_dir=screenshots_dir,
                        )
                    except TimeoutError:
                        logger.error(
                            "[execute_skill_script] 持久化 Playwright 执行超时"
                        )
                        return "错误: 命令执行超时（120秒）"
                    except Exception as e:
                        logger.error(
                            f"[execute_skill_script] 持久化 Playwright 执行失败: {e}",
                            exc_info=True,
                        )
                        return f"错误: {str(e)}"

            # Windows 编码处理：cmd.exe 默认使用 GBK (cp936)，需要使用系统默认编码
            import locale

            # playwright-cli 在只读的 skill 目录下以相对文件名保存截图会 EACCES，
            # 改在可写的截图目录执行，使截图默认落入 SCREENSHOT_DIR
            exec_cwd = screenshots_dir if skill_name == "playwright-cli" else skill_dir

            timeout_seconds = int(
                getattr(settings, "SKILL_EXEC_TIMEOUT_SECONDS", 120) or 120
            )
            use_legacy_shell = legacy_shell_exec_enabled()
            if use_legacy_shell:
                logger.warning(
                    "[execute_skill_script] SKILL_LEGACY_SHELL_EXEC 已开启："
                    "命令将经 shell 解释，安全性下降，建议尽快关闭"
                )
                audit_skill_execution(
                    decision="allow-legacy-shell",
                    user_id=current_user_id,
                    project_id=current_project_id,
                    chat_session_id=current_chat_session_id,
                    test_case_id=current_test_case_id,
                    skill_id=getattr(skill, "id", None),
                    skill_name=skill_name,
                    argv=[exec_command],
                    reason="SKILL_LEGACY_SHELL_EXEC=true",
                )
            else:
                # 命令加固：解析为 argv 并过启动器白名单，不再经 shell 解释。
                # shell 结构被显式翻译：NAME=value 前缀 → 子进程环境，heredoc → stdin。
                try:
                    invocation = parse_skill_command(exec_command)
                    validate_skill_command(invocation.argv, skill_dir=skill_dir)
                except SkillCommandError as exc:
                    audit_skill_execution(
                        decision="deny",
                        user_id=current_user_id,
                        project_id=current_project_id,
                        chat_session_id=current_chat_session_id,
                        test_case_id=current_test_case_id,
                        skill_id=getattr(skill, "id", None),
                        skill_name=skill_name,
                        argv=[exec_command],
                        reason=str(exc),
                    )
                    logger.warning(
                        "[execute_skill_script] 拒绝非白名单 skill 命令: %s", exc
                    )
                    return f"错误: {exc}"

                # 命令前缀里的 NAME=value 翻译为子进程环境（原先依赖 shell 的临时赋值语义）
                if invocation.env_overrides:
                    env.update(invocation.env_overrides)
                    logger.info(
                        "[execute_skill_script] 命令前缀环境变量已注入: %s",
                        sorted(invocation.env_overrides),
                    )

            exec_started_at = time.monotonic()

            def _run_exec() -> SkillCommandResult:
                if use_legacy_shell:
                    return run_skill_command_via_shell(
                        exec_command,
                        cwd=exec_cwd,
                        env=env,
                        timeout_seconds=timeout_seconds,
                    )
                return run_skill_command(
                    invocation.argv,
                    cwd=exec_cwd,
                    env=env,
                    timeout_seconds=timeout_seconds,
                    stdin_text=invocation.stdin_text,
                )

            if use_runner:
                # 第 2 层：提交给独立 skill-runner，backend 进程内不再执行 skill 代码。
                # runner 不可达时直接失败，不静默回退到进程内执行（回退等于绕开隔离）。
                try:
                    result = submit_job(
                        skill_dir=skill_dir,
                        command=exec_command,
                        timeout_seconds=timeout_seconds,
                        runtime_env=runtime_env,
                        user_id=current_user_id,
                        project_id=current_project_id,
                        chat_session_id=current_chat_session_id,
                        test_case_id=current_test_case_id,
                        skill_id=getattr(skill, "id", None),
                        skill_name=skill_name,
                    )
                except SkillRunnerUnavailable as exc:
                    logger.error("[execute_skill_script] skill-runner 不可用: %s", exc)
                    return f"错误: skill-runner 不可用（{exc}）"

                stdout = strip_terminal_control_sequences(result.stdout or "")
                stderr = strip_terminal_control_sequences(result.stderr or "")
                if session_id and skill_name == "playwright-cli":
                    # 明确告知：runner 为无状态执行，不保持浏览器会话，
                    # 避免模型反复用同一个 session_id 期待复用而浪费轮次。
                    stderr = (
                        "[提示] 当前为技能沙箱（skill-runner）执行模式，"
                        "不保持浏览器会话；session_id 不会复用浏览器，"
                        "请把多步操作合并为一次调用或在同一命令内完成。\n"
                        + stderr
                    )
            elif platform.system() == "Windows":
                # Windows cmd 默认使用 GBK 编码，使用 None 让 subprocess 自动检测
                result = _run_exec()

                # 智能解码：先尝试 UTF-8（现代工具通常输出 UTF-8），失败再用 GBK（Windows cmd 默认）
                def smart_decode(data: bytes) -> str:
                    if not data:
                        return ""
                    try:
                        return data.decode("utf-8")
                    except UnicodeDecodeError:
                        return data.decode("gbk", errors="replace")

                stdout = strip_terminal_control_sequences(smart_decode(result.stdout))
                stderr = strip_terminal_control_sequences(smart_decode(result.stderr))
            else:
                result = _run_exec()
                stdout = strip_terminal_control_sequences(
                    (result.stdout or b"").decode("utf-8", errors="replace")
                )
                stderr = strip_terminal_control_sequences(
                    (result.stderr or b"").decode("utf-8", errors="replace")
                )

            audit_skill_execution(
                decision="allow",
                user_id=current_user_id,
                project_id=current_project_id,
                chat_session_id=current_chat_session_id,
                test_case_id=current_test_case_id,
                skill_id=getattr(skill, "id", None),
                skill_name=skill_name,
                argv=(
                    ["<legacy-shell>", exec_command]
                    if use_legacy_shell
                    else list(invocation.argv)
                ),
                returncode=result.returncode,
                duration_ms=int((time.monotonic() - exec_started_at) * 1000),
                output_bytes=len(result.stdout or b"") + len(result.stderr or b""),
            )

            output = ""
            if stdout:
                output += stdout
            if stderr:
                if output:
                    output += "\n--- stderr ---\n"
                output += stderr

            if result.returncode != 0:
                output = f"命令执行失败 (退出码: {result.returncode})\n{output}"

            logger.info(
                f"[execute_skill_script] 执行完成, returncode={result.returncode}, output_len={len(output)}"
            )
            if output:
                logger.debug(f"[execute_skill_script] output: {output[:500]}")
            result_output = output.strip() if output.strip() else "(无输出)"

            # 如果是 playwright-skill 的 run.js 调用但没有使用 session_id，提醒 LLM
            if (
                skill_name == "playwright-skill"
                and "run.js" in command
                and not session_id
            ):
                result_output = f"[SCREENSHOT_DIR] {screenshots_dir}\n{result_output}\n\n[注意] 此次执行未使用 session_id，浏览器已关闭。如果这是多步骤测试的一部分，请在后续调用中使用 session_id 参数保持浏览器会话。"
            elif skill_name == "playwright-skill":
                result_output = f"[SCREENSHOT_DIR] {screenshots_dir}\n{result_output}"

            return _finalize_skill_result(
                result_output,
                skill_dir=skill_dir,
                artifacts_dir=artifacts_dir,
                artifacts_before=artifacts_before,
                screenshots_dir=screenshots_dir,
            )

        except subprocess.TimeoutExpired:
            logger.error("[execute_skill_script] 执行超时")
            return "错误: 命令执行超时（120秒）"
        except Exception as e:
            logger.error(f"[execute_skill_script] 执行失败: {e}", exc_info=True)
            return f"错误: {str(e)}"

    @langchain_tool
    def execute_skill_script(
        skill_name: Optional[str] = None,
        command: Optional[str] = None,
        session_id: Optional[str] = None,
        commands: Optional[list[dict[str, str]]] = None,
        parallel: bool = True,
        max_workers: int = 5,
    ) -> str:
        """
        执行 Skill 命令，支持单个执行或批量并发执行。

        **单个执行模式**：传入 skill_name 和 command
        **批量执行模式**：传入 commands 列表（自动并发，大幅提升效率）

        Args:
            skill_name: Skill 名称（单个执行时必填）
            command: shell 命令，如 "python whart_tools.py --action get_projects"（单个执行时必填）
            session_id: 可选会话ID，用于 playwright-skill 保持浏览器会话
            commands: 批量命令列表，每个元素包含 skill_name、command、session_id（可选）
                示例: [
                    {"skill_name": "whart-test", "command": "python whart_tools.py --action add_testcase ..."},
                    {"skill_name": "whart-test", "command": "python whart_tools.py --action add_testcase ..."}
                ]
            parallel: 批量模式下是否并发执行（默认 True）
            max_workers: 批量模式下最大并发数（默认 5）

        Returns:
            单个模式返回命令输出；如执行中生成了文件，会追加可下载附件信息。
            Skills 可将导出文件写入 `SKILL_OUTPUT_DIR`（或 `ARTIFACT_DIR`）以便 Web 端直接下载。
            批量模式返回 JSON 格式结果汇总
        """
        import json
        from concurrent.futures import ThreadPoolExecutor, as_completed

        from django.db import close_old_connections

        # 批量执行模式
        if commands:
            logger.info(
                f"[execute_skill_script] 批量模式: {len(commands)} 条命令, parallel={parallel}, max_workers={max_workers}"
            )

            if not commands:
                return json.dumps({"error": "命令列表为空"}, ensure_ascii=False)

            def execute_single(idx: int, cmd: dict[str, str]) -> dict[str, object]:
                cmd_skill_name = cmd.get("skill_name")
                cmd_command = cmd.get("command")
                cmd_session_id = cmd.get("session_id")

                if not cmd_skill_name or not cmd_command:
                    return {
                        "index": idx,
                        "skill_name": cmd_skill_name,
                        "command": cmd_command,
                        "error": "缺少 skill_name 或 command",
                    }

                try:
                    result = _execute_single_skill_script(
                        cmd_skill_name, cmd_command, cmd_session_id
                    )
                    return {
                        "index": idx,
                        "skill_name": cmd_skill_name,
                        "command": cmd_command,
                        "result": result,
                    }
                except Exception as e:
                    return {
                        "index": idx,
                        "skill_name": cmd_skill_name,
                        "command": cmd_command,
                        "error": str(e),
                    }
                finally:
                    close_old_connections()

            results: list[Optional[dict[str, object]]] = [None] * len(commands)

            if parallel and len(commands) > 1:
                with ThreadPoolExecutor(
                    max_workers=min(max_workers, len(commands))
                ) as executor:
                    future_to_idx = {
                        executor.submit(execute_single, idx, cmd): idx
                        for idx, cmd in enumerate(commands)
                    }
                    for future in as_completed(future_to_idx):
                        idx = future_to_idx[future]
                        results[idx] = future.result()
            else:
                for idx, cmd in enumerate(commands):
                    results[idx] = execute_single(idx, cmd)

            success_count = sum(
                1
                for r in results
                if r is not None and "result" in r and "error" not in r
            )
            error_count = len(results) - success_count

            logger.info(
                f"[execute_skill_script] 批量完成: {success_count} 成功, {error_count} 失败"
            )

            return json.dumps(
                {
                    "summary": {
                        "total": len(commands),
                        "success": success_count,
                        "error": error_count,
                        "parallel": parallel,
                    },
                    "results": [r for r in results if r is not None],
                },
                ensure_ascii=False,
                indent=2,
            )

        # 单个执行模式
        if not skill_name or not command:
            return "错误: 单个执行模式需要提供 skill_name 和 command 参数"

        return _execute_single_skill_script(skill_name, command, session_id)

    return [read_skill_content, execute_skill_script]
