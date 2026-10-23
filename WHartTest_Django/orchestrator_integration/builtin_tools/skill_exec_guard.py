"""
Skill 命令执行安全护栏（第 1 层进程内加固）

背景：Skill 命令由 LLM 生成，属于不可信输入。改造前 backend 直接以
``subprocess.run(command, shell=True, env=os.environ.copy())`` 执行，等价于把
backend 容器（root）的 shell 交给模型，并把 ``DJANGO_SECRET_KEY`` /
``POSTGRES_PASSWORD`` 等平台机密一并交给被测脚本。

本模块集中收口执行策略：

- ``parse_skill_command`` / ``validate_skill_command``：命令解析 + 启动器白名单
  （不经 shell 解释，内联代码与运行期安装包一律拒绝）
- ``build_skill_env``：环境变量白名单（剥离平台机密）
- ``build_preexec_fn``：子进程资源上限（CPU / 文件大小 / 进程数 / 句柄数）
- ``run_skill_command``：无 shell 执行 + 独立进程组 + 超时整组回收
- ``audit_skill_execution``：结构化审计日志

设计取向：白名单优先于黑名单；宁可让模型换一种表达方式，也不放行无法静态
判定的命令。所有策略均可用 Django settings 覆盖（见各常量旁的注释）。
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import signal
import subprocess
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Optional, Sequence

try:  # 允许在无 Django 的独立进程（skill-runner）中复用同一套策略
    from django.conf import settings as _django_settings
except Exception:  # pragma: no cover - 独立运行时不安装 Django
    _django_settings = None


def _setting(name: str, default=None):
    """读取配置：Django settings 优先，其次环境变量。

    skill-runner 进程不加载 Django，此时策略由环境变量驱动，两侧共用同一份实现。
    """
    if _django_settings is not None:
        try:
            value = getattr(_django_settings, name, None)
        except Exception:
            # Django 可导入但未配置（skill-runner 等独立进程），退回环境变量。
            value = None
        if value not in (None, ""):
            return value
    value = os.environ.get(name)
    return default if value in (None, "") else value

logger = logging.getLogger("orchestrator_integration")
audit_logger = logging.getLogger("orchestrator_integration.skill_audit")


class SkillCommandError(ValueError):
    """命令不满足 Skill 执行安全策略。"""


@dataclass
class SkillCommandResult:
    """子进程执行结果；stdout/stderr 保持 bytes，交由调用方按平台解码。"""

    returncode: int
    stdout: bytes
    stderr: bytes


@dataclass
class SkillInvocation:
    """一条 skill 命令的规范化形式（不依赖 shell 即可执行）。

    - ``argv``：可直接交给 ``subprocess`` 的参数列表
    - ``env_overrides``：命令里 ``NAME=value`` 前缀翻译成的子进程环境变量
    - ``stdin_text``：heredoc 正文，作为子进程 stdin 内容
    """

    argv: list[str]
    env_overrides: dict[str, str]
    stdin_text: Optional[str] = None


# --------------------------------------------------------------------------
# 命令解析与校验
# --------------------------------------------------------------------------

# 允许作为 argv[0] 的启动器（按 basename 比较，大小写不敏感）。
# 刻意不含 bash/sh/curl/wget/git/rm 等通用工具：Skill 只应调用它自带的入口脚本。
_ALLOWED_LAUNCHERS = frozenset(
    {"python", "python3", "node", "playwright-cli", "browser-use", "npx", "npm"}
)

# 解释器内联代码执行参数：等价于「不落盘的任意代码执行」，直接拒绝。
_INLINE_CODE_FLAGS = {
    "python": frozenset({"-c", "-", "-i"}),
    "python3": frozenset({"-c", "-", "-i"}),
    "node": frozenset({"-e", "--eval", "-p", "--print", "-", "-i", "--interactive"}),
}

# 运行期装包会在 /opt/venv、/app 落下持久化后门，并引入供应链风险。
_BLOCKED_NPM_SUBCOMMANDS = frozenset(
    {"install", "i", "add", "ci", "link", "unlink", "publish", "exec", "x", "pack", "update"}
)
_BLOCKED_PY_MODULES = frozenset(
    {"pip", "ensurepip", "venv", "virtualenv", "http.server", "pty", "socket", "socketserver"}
)

# npx 在平台上只承担「启动 skill 目录内已安装的 playwright-cli」这一职责。
_NPX_ALLOWED_PACKAGES = frozenset({"playwright-cli"})

# 单条命令长度上限：正常 skill 调用远小于此值，超长通常是异常负载。
_MAX_COMMAND_LENGTH = 100000


def _strip_matching_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def contains_unsafe_shell_syntax(command: str) -> bool:
    """检测未加引号的 shell 元字符（引号内除 `$`、反引号外视为普通字符）。

    与 playwright-cli 既有判定保持一致：平台不再经 shell 解释命令，命中即拒绝，
    避免「重定向/管道被当成普通参数」这类静默语义变化。
    """
    quote: Optional[str] = None
    escaped_in_double_quotes = False
    for character in command:
        if quote == "'":
            if character == "'":
                quote = None
            elif character in "|&\r\n<>":
                return True
            continue

        if quote == '"':
            if escaped_in_double_quotes:
                escaped_in_double_quotes = False
                continue
            if character == "\\":
                escaped_in_double_quotes = True
                continue
            if character == '"':
                quote = None
                continue
            if character in {"`", "$"}:
                return True
            continue

        if character in {'"', "'"}:
            quote = character
            continue
        if character in ";|&\r\n`<>$":
            return True
    return False


def has_unquoted_shell_metacharacter(command: str) -> bool:
    """检测**未加引号**的 shell 元字符（无 shell 执行路径使用）。

    与 ``contains_unsafe_shell_syntax`` 的区别：单引号与双引号内的内容一律视为
    普通字符。命令不再经 shell 解释，引号内本就是字面量；这样
    ``'https://a.com/p?a=1&b=2'`` 这类合法参数不会被误拒。

    命中只说明「模型按 shell 语义书写了命令」，此时拒绝比静默按字面量执行更安全
    （例如 ``> out.txt`` 会变成普通参数而不是重定向）。
    """
    quote: Optional[str] = None
    for character in command:
        if quote is not None:
            if character == quote:
                quote = None
            continue
        if character in {'"', "'"}:
            quote = character
            continue
        if character in ";|&\r\n`<>$":
            return True
    return False


# 允许作为命令前缀的 ``NAME=value`` 环境变量（等价于 shell 的临时赋值前缀）。
# 只放行业务确实需要的键：PATH / LD_PRELOAD / NODE_OPTIONS 这类一旦放行即可劫持子进程。
_ENV_PREFIX_ALLOWLIST = frozenset({"BU_NAME"})

# heredoc：``<<'EOF'`` / ``<<EOF`` / ``<<-EOF``，正文作为子进程 stdin。
_HEREDOC_PATTERN = re.compile(
    r"<<-?\s*(?P<quote>['\"]?)(?P<delimiter>[A-Za-z_][A-Za-z0-9_]*)(?P=quote)"
    r"[ \t]*\r?\n(?P<body>.*?)\r?\n[ \t]*(?P=delimiter)[ \t]*$",
    re.DOTALL,
)


def split_env_prefix(argv: Sequence[str]) -> tuple[dict[str, str], list[str]]:
    """把 argv 开头的 ``NAME=value`` 前缀拆出来，返回 (环境变量, 剩余 argv)。

    前缀键必须在允许列表内，否则拒绝——避免用 ``PATH=`` 之类劫持后续命令解析。
    """
    env_overrides: dict[str, str] = {}
    index = 0
    for token in argv:
        name, separator, value = token.partition("=")
        if not separator or not name or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            break
        if name not in _env_prefix_allowlist():
            raise SkillCommandError(
                f"不允许在命令前设置环境变量 '{name}'；"
                f"仅支持 {sorted(_env_prefix_allowlist())}"
            )
        env_overrides[name] = value
        index += 1
    return env_overrides, list(argv[index:])


def _env_prefix_allowlist() -> frozenset[str]:
    extra = _allowlist_extra_from_setting("SKILL_ENV_PREFIX_ALLOWLIST")
    if not extra:
        return _ENV_PREFIX_ALLOWLIST
    return frozenset(set(_ENV_PREFIX_ALLOWLIST) | set(extra))


def parse_skill_command(command: str) -> SkillInvocation:
    """把命令字符串解析为不依赖 shell 的可执行形式。

    支持的 shell 结构会被显式翻译而不是拒绝：``NAME=value`` 前缀 → 子进程环境，
    ``<<'EOF' ... EOF`` → 子进程 stdin。其余未加引号的元字符（管道、重定向、链式、
    变量展开）仍然拒绝，因为它们无法在不引入 shell 的前提下等价实现。
    """
    command = (command or "").strip()
    if not command:
        raise SkillCommandError("命令不能为空")

    if len(command) > _MAX_COMMAND_LENGTH:
        raise SkillCommandError(f"命令长度超限（{len(command)} > {_MAX_COMMAND_LENGTH}）")

    stdin_text: Optional[str] = None
    heredoc_match = _HEREDOC_PATTERN.search(command)
    if heredoc_match is not None:
        stdin_text = heredoc_match.group("body")
        command = command[: heredoc_match.start()].strip()
        if not command:
            raise SkillCommandError("heredoc 之前缺少要执行的命令")

    if has_unquoted_shell_metacharacter(command):
        raise SkillCommandError(
            "命令包含未加引号的 shell 元字符（管道、重定向、链式、变量展开或命令替换）。"
            "平台不再经 shell 解释命令：请改用 skill 提供的入口脚本，"
            "或拆分后用 execute_skill_batch 依次执行。"
        )

    try:
        if os.name == "nt":
            # Windows 的 CommandLineToArgvW 不识别单引号，沿用既有的引号归一化语义。
            argv = [_strip_matching_quotes(token) for token in shlex.split(command, posix=False)]
        else:
            argv = shlex.split(command, posix=True)
    except ValueError as exc:
        raise SkillCommandError(f"命令解析失败（引号不匹配）: {exc}") from exc

    if not argv:
        raise SkillCommandError("命令解析结果为空")

    env_overrides, argv = split_env_prefix(argv)
    if not argv:
        raise SkillCommandError("命令缺少可执行程序（只提供了环境变量前缀）")

    return SkillInvocation(
        argv=argv,
        env_overrides=env_overrides,
        stdin_text=stdin_text,
    )


def _is_blocked_inline_flag(token: str, blocked_flags) -> bool:
    """判定 token 是否为被禁的内联代码选项（含短选项粘连与 ``--long=value``）。

    注意：裸 ``-``（读 stdin）只能整 token 匹配，否则会把 ``--x`` 这类长选项
    误判为 ``-`` 的粘连形式。
    """
    lowered = (token or "").lower()
    for flag in blocked_flags:
        if lowered == flag:
            return True
        if flag == "-":
            continue
        if flag.startswith("--"):
            # 长选项：仅 --flag=value 形式
            if lowered.startswith(f"{flag}="):
                return True
            continue
        # 短选项：-cxxx 粘连形式（-c 后紧跟取值）
        if lowered.startswith(flag) and len(lowered) > len(flag):
            return True
    return False


def _normalized_launcher(argv0: str) -> str:
    launcher = os.path.basename(argv0).lower()
    if launcher.endswith(".exe"):
        launcher = launcher[: -len(".exe")]
    return launcher


def validate_skill_command(argv: Sequence[str], *, skill_dir: Optional[str] = None) -> None:
    """校验 argv 是否落在 Skill 执行白名单内；不通过时抛 ``SkillCommandError``。"""
    if not argv:
        raise SkillCommandError("命令不能为空")

    launcher = _normalized_launcher(argv[0])
    if launcher not in _ALLOWED_LAUNCHERS:
        raise SkillCommandError(
            f"不允许执行 '{argv[0]}'。Skill 只能通过 "
            f"{sorted(_ALLOWED_LAUNCHERS)} 启动它自带脚本或已绑定的 CLI。"
        )

    args = list(argv[1:])

    # 内联代码/模块执行必须按「短选项粘连」判定，不能只做整 token 相等：
    # `python -c"import os"`、`python -mhttp.server`、`node --eval=...` 这类写法
    # （选项与其取值同 token）会被 getopt 当作 optarg，绕过相等比对。
    blocked_flags = _INLINE_CODE_FLAGS.get(launcher)
    if blocked_flags:
        for token in args:
            if _is_blocked_inline_flag(token, blocked_flags):
                raise SkillCommandError(
                    f"禁止 {launcher} 的内联代码参数 '{token}'："
                    "请把代码写入 skill 目录内的脚本文件后再执行。"
                )

    if launcher in {"python", "python3"}:
        for index, token in enumerate(args):
            lowered = token.lower()
            # 同时覆盖 `-m mod` 与粘连写法 `-mmod`
            if lowered == "-m":
                module = args[index + 1].lower() if index + 1 < len(args) else ""
            elif lowered.startswith("-m") and len(lowered) > 2:
                module = lowered[2:]
            else:
                continue
            if not module or module in _BLOCKED_PY_MODULES or module.startswith("pip"):
                raise SkillCommandError(
                    f"禁止 python -m {module or '<缺失模块>'}："
                    "模块执行/装包不在 Skill 允许范围内。"
                )

    if launcher == "npx":
        rest = [token for token in args if token != "--no-install"]
        package = os.path.basename(rest[0]).lower() if rest else ""
        if package not in _NPX_ALLOWED_PACKAGES:
            raise SkillCommandError(
                "npx 仅允许启动 playwright-cli（禁止联网下载并执行其它包）。"
            )

    if launcher == "npm":
        subcommand = next((token for token in args if not token.startswith("-")), "")
        if subcommand.lower() in _BLOCKED_NPM_SUBCOMMANDS:
            raise SkillCommandError(
                f"禁止在 Skill 执行期使用 'npm {subcommand}' 安装/发布依赖。"
            )

    if skill_dir:
        # argv[0] 若带路径分隔符，必须是绝对路径的启动器或 skill 目录内的相对路径； 
        # 拒绝 `../` 形式跳出 skill 目录。
        raw_launcher = argv[0]
        if os.sep in raw_launcher or (os.altsep and os.altsep in raw_launcher):
            if not os.path.isabs(raw_launcher):
                resolved = os.path.abspath(os.path.join(skill_dir, raw_launcher))
                skill_root = os.path.abspath(skill_dir)
                if os.path.commonpath([skill_root, resolved]) != skill_root:
                    raise SkillCommandError(
                        f"启动器路径 '{raw_launcher}' 超出 skill 目录范围。"
                    )


# --------------------------------------------------------------------------
# 环境变量白名单
# --------------------------------------------------------------------------

# 允许继承的环境变量：只保留运行脚本与浏览器所必需、且不含平台机密的键。
_ENV_ALLOWLIST = (
    "PATH",
    "HOME",
    "LANG",
    "LANGUAGE",
    "LC_ALL",
    "LC_CTYPE",
    "LC_MESSAGES",
    "TZ",
    "USER",
    "LOGNAME",
    "TMPDIR",
    "TEMP",
    "TMP",
    "DISPLAY",
    "PYTHONUNBUFFERED",
    "PYTHONDONTWRITEBYTECODE",
    "PYTHONIOENCODING",
    "PYTHONUTF8",
    "PLAYWRIGHT_BROWSERS_PATH",
    "PLAYWRIGHT_DOWNLOAD_HOST",
    "LLM_BROWSER_AUTO_CHROME",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
    "NODE_EXTRA_CA_CERTS",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "no_proxy",
    "HF_ENDPOINT",
)

# 二次防线：即使某个键被加入白名单，名称命中机密模式也一律剥离。
_SECRET_NAME_PATTERN = re.compile(
    r"(SECRET|PASSWORD|PASSWD|TOKEN|API_?KEY|PRIVATE|CREDENTIAL|LICENSE|DSN"
    r"|POSTGRES|MYSQL|MONGO|REDIS|SMTP|AWS|OPENAI|ANTHROPIC|DEEPSEEK|GEMINI|GATEWAY)",
    re.IGNORECASE,
)


def _allowlist_extra_from_setting(name: str) -> tuple[str, ...]:
    """读取逗号分隔的名单类配置（settings 或环境变量）。"""
    raw = _setting(name, "")
    if isinstance(raw, str):
        candidates = [item.strip() for item in raw.split(",")]
    elif isinstance(raw, Iterable):
        candidates = [str(item).strip() for item in raw]
    else:
        candidates = []
    return tuple(item for item in candidates if item)


def _allowlist_extra() -> tuple[str, ...]:
    return _allowlist_extra_from_setting("SKILL_ENV_ALLOWLIST_EXTRA")


def build_skill_env(
    *,
    source_env: Optional[Mapping[str, str]] = None,
    runtime_env: Optional[Mapping[str, object]] = None,
    allowlist_extra: Optional[Sequence[str]] = None,
) -> dict[str, str]:
    """构造 Skill 子进程的运行环境。

    ``runtime_env`` 是调用方显式注入的运行时变量（当前用户 API Key、产物目录等），
    属于有意传递，不做名称过滤。
    """
    source = dict(os.environ if source_env is None else source_env)
    extra = list(allowlist_extra if allowlist_extra is not None else _allowlist_extra())

    env: dict[str, str] = {}
    stripped: list[str] = []
    for name in tuple(_ENV_ALLOWLIST) + tuple(extra):
        value = source.get(name)
        if value is None:
            continue
        if _SECRET_NAME_PATTERN.search(name):
            stripped.append(name)
            continue
        env[name] = value

    if stripped:
        audit_logger.warning(
            "[skill.audit] 按机密名模式剥离环境变量: %s", ",".join(sorted(set(stripped)))
        )

    if runtime_env:
        for name, value in runtime_env.items():
            if value is None:
                continue
            env[str(name)] = str(value)

    return env


# --------------------------------------------------------------------------
# 子进程资源上限
# --------------------------------------------------------------------------


def _int_setting(name: str, default: Optional[int]) -> Optional[int]:
    raw = _setting(name, None)
    if raw in (None, ""):
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _bool_setting(name: str, default: bool) -> bool:
    raw = _setting(name, None)
    if raw in (None, ""):
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def build_preexec_fn(timeout_seconds: int) -> Optional[Callable[[], None]]:
    """返回设置资源上限的 preexec 回调；平台不支持或已关闭时返回 None。

    注意：默认不设 RLIMIT_NPROC（按 uid 整机计数，会误伤 Node/Chromium 建线程），进程数兜底交给容器 pids_limit；
    内存上限交由容器 cgroup 处理，这里默认不设 RLIMIT_AS，避免误伤 Chromium
    的大块虚拟地址预留。
    """
    if os.name == "nt":
        return None
    if not _bool_setting("SKILL_RLIMIT_ENABLED", True):
        return None

    try:
        import resource
    except ImportError:  # pragma: no cover - 非 POSIX 平台
        return None

    timeout_seconds = max(1, int(timeout_seconds or 1))
    cpu_seconds = _int_setting("SKILL_RLIMIT_CPU_SECONDS", timeout_seconds + 10)
    file_size = _int_setting("SKILL_RLIMIT_FSIZE_BYTES", 512 * 1024 * 1024)
    open_files = _int_setting("SKILL_RLIMIT_NOFILE", 4096)
    # RLIMIT_NPROC 默认不设置。原因（实测踩坑）：
    #   1. 它按「真实 uid」在**整机范围**计数，不是按容器/作业计数。容器常以
    #      与宿主同 uid 运行（无 userns 重映射）时，宿主该 uid 已有的成百上千个
    #      进程/线程会直接吃掉额度——实测宿主 uid 1000 已有 597 个，而默认值 256
    #      导致 Node 连一个线程都建不出来，libuv 直接断言中止（退出码 -6）。
    #   2. 对 root 本就不生效（root 绕过该限制），起不到兜底作用。
    #   进程数兜底应由容器 cgroup 负责（compose 的 pids_limit / k8s 的 pids 限额）。
    # 如确需设置，用 SKILL_RLIMIT_NPROC 显式指定，并确认目标 uid 的全局进程数。
    processes = _int_setting("SKILL_RLIMIT_NPROC", None)
    address_space = _int_setting("SKILL_RLIMIT_AS_BYTES", None)

    candidates = [
        (getattr(resource, "RLIMIT_CORE", None), 0),
        (getattr(resource, "RLIMIT_CPU", None), max(5, cpu_seconds or 0)),
        (getattr(resource, "RLIMIT_FSIZE", None), file_size),
        (getattr(resource, "RLIMIT_NOFILE", None), open_files),
        (getattr(resource, "RLIMIT_NPROC", None), processes),
        (getattr(resource, "RLIMIT_AS", None), address_space),
    ]

    limits: list[tuple[int, int]] = []
    for resource_id, value in candidates:
        if resource_id is None or value is None:
            continue
        limits.append((resource_id, int(value)))

    if not limits:
        return None

    def _apply_limits() -> None:
        for resource_id, value in limits:
            try:
                # 不允许抬高硬上限：目标值超出当前硬上限时收敛到硬上限（或失败即忽略）。
                _, current_hard = resource.getrlimit(resource_id)
                if current_hard != resource.RLIM_INFINITY and value > current_hard:
                    target = current_hard
                else:
                    target = value
                resource.setrlimit(resource_id, (target, target))
            except (ValueError, OSError):
                continue

    return _apply_limits


def _kill_process_tree(proc: "subprocess.Popen[bytes]") -> None:
    """超时后回收整棵进程树，避免子进程（浏览器、node 等）成为孤儿。"""
    if os.name != "nt":
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            return
        except (ProcessLookupError, PermissionError, OSError):
            pass
    try:
        proc.kill()
    except OSError:
        pass


def run_skill_command(
    argv: Sequence[str],
    *,
    cwd: str,
    env: Mapping[str, str],
    timeout_seconds: int,
    stdin_text: Optional[str] = None,
) -> SkillCommandResult:
    """无 shell 执行命令；超时抛 ``subprocess.TimeoutExpired``（与既有处理路径兼容）。"""
    stdin_bytes = stdin_text.encode("utf-8") if isinstance(stdin_text, str) else None
    if os.name == "nt":
        proc = subprocess.Popen(  # noqa: S603 - argv 已过白名单校验，未经 shell
            list(argv),
            cwd=cwd,
            env=dict(env),
            stdin=subprocess.PIPE if stdin_bytes is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
    else:
        proc = subprocess.Popen(  # noqa: S603 - argv 已过白名单校验，未经 shell
            list(argv),
            cwd=cwd,
            env=dict(env),
            stdin=subprocess.PIPE if stdin_bytes is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            preexec_fn=build_preexec_fn(timeout_seconds),
        )

    return _collect_process_output(proc, timeout_seconds, argv, stdin_bytes)


def legacy_shell_exec_enabled() -> bool:
    """逃生开关：客户环境如需恢复改造前的 shell 语义，可显式打开。默认关闭。"""
    return _bool_setting("SKILL_LEGACY_SHELL_EXEC", False)


def run_skill_command_via_shell(
    command: str,
    *,
    cwd: str,
    env: Mapping[str, str],
    timeout_seconds: int,
) -> SkillCommandResult:
    """经 shell 解释执行命令（legacy 逃生通道）。

    仅在 ``SKILL_LEGACY_SHELL_EXEC`` 显式开启时使用；执行策略其余部分（环境变量
    白名单、资源上限、进程组回收）仍然生效。
    """
    if os.name == "nt":
        proc = subprocess.Popen(  # noqa: S602 - 受显式逃生开关控制
            command,
            shell=True,
            cwd=cwd,
            env=dict(env),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
    else:
        proc = subprocess.Popen(  # noqa: S602 - 受显式逃生开关控制
            command,
            shell=True,
            cwd=cwd,
            env=dict(env),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            preexec_fn=build_preexec_fn(timeout_seconds),
        )

    return _collect_process_output(proc, timeout_seconds, [command])


def _collect_process_output(
    proc: "subprocess.Popen[bytes]",
    timeout_seconds: int,
    argv: Sequence[str],
    stdin_bytes: Optional[bytes] = None,
) -> SkillCommandResult:
    try:
        stdout, stderr = proc.communicate(input=stdin_bytes, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        _kill_process_tree(proc)
        try:
            proc.communicate(timeout=10)
        except Exception:  # pragma: no cover - 回收失败不应掩盖超时语义
            logger.warning("[execute_skill_script] 超时后回收子进程输出失败", exc_info=True)
        raise

    return SkillCommandResult(
        returncode=int(proc.returncode if proc.returncode is not None else -1),
        stdout=stdout or b"",
        stderr=stderr or b"",
    )


# --------------------------------------------------------------------------
# 审计
# --------------------------------------------------------------------------


def audit_skill_execution(
    *,
    decision: str,
    user_id: object = None,
    project_id: object = None,
    chat_session_id: object = None,
    test_case_id: object = None,
    skill_id: object = None,
    skill_name: object = None,
    argv: Optional[Sequence[str]] = None,
    reason: str = "",
    returncode: Optional[int] = None,
    duration_ms: Optional[int] = None,
    output_bytes: Optional[int] = None,
) -> None:
    """一行 JSON 的结构化审计记录，便于日志采集与告警。

    第 2 层引入 skill-runner 后，将由作业表承载同等信息并支持检索。
    """
    payload = {
        "event": "skill_exec",
        "decision": decision,
        "user_id": user_id,
        "project_id": project_id,
        "chat_session_id": chat_session_id,
        "test_case_id": test_case_id,
        "skill_id": skill_id,
        "skill_name": skill_name,
        "argv": list(argv) if argv else None,
        "reason": reason or None,
        "returncode": returncode,
        "duration_ms": duration_ms,
        "output_bytes": output_bytes,
    }
    try:
        message = "[skill.audit] " + json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError):  # pragma: no cover - 兜底，避免审计本身抛错
        message = f"[skill.audit] {payload}"

    if decision == "allow":
        audit_logger.info(message)
    else:
        audit_logger.warning(message)
