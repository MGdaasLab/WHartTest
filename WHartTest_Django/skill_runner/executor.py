"""
skill-runner 的作业执行器

职责：在受控工作目录内，用与 backend 完全相同的策略执行一条 skill 命令。

与 backend 内进程内执行的区别（也是本层的安全价值）：

1. 运行环境由 runner 容器提供：无平台机密、无业务网段、只读根文件系统 + tmpfs 工作区；
2. 每次作业使用独立临时工作目录，结束即销毁——模型写入的任何文件都不会留存；
3. skill 目录以只读方式使用，产物统一落在作业工作目录内，由调用方按需取回。

策略复用 ``skill_exec_guard``：启动器白名单、env 白名单、资源上限、进程组回收。
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# 复用 backend 侧的同一份命令策略：直接按模块路径加载，避免依赖 Django 包结构。
_GUARD_DIR = Path(__file__).resolve().parent.parent / "orchestrator_integration" / "builtin_tools"
if str(_GUARD_DIR) not in sys.path:
    sys.path.insert(0, str(_GUARD_DIR))

from skill_exec_guard import (  # noqa: E402 - 需先补 sys.path
    SkillCommandError,
    audit_skill_execution,
    build_skill_env,
    build_preexec_fn,  # noqa: F401 - 供调用方/测试检查策略可用性
    parse_skill_command,
    run_skill_command,
    validate_skill_command,
)

logger = logging.getLogger("skill_runner")

# 单次作业返回给调用方的输出上限，避免大输出撑爆 HTTP 响应或调用方内存。
MAX_CAPTURED_OUTPUT_BYTES = 256 * 1024

# 第 3 层：可选的 syscall 级隔离包装器。
# 容器本身已是「无机密 + 无业务网段 + 只读根 + tmpfs」的沙箱；若客户内核允许，
# 可再叠加 nsjail/gVisor 做 syscall 级隔离。未安装时自动退化为容器隔离（不报错），
# 因为容器隔离已经是本层必须保证的下限。
_ISOLATION_WRAPPERS = {
    "nsjail": lambda argv, skill_dir: [
        "nsjail", "--quiet", "--mode", "o",
        "--chroot", "/",
        "--cwd", skill_dir,
        "--disable_proc",
        "--time_limit", "0",
        "--rlimit_as", "4096",
        "--rlimit_nproc", "256",
        "--", *argv,
    ],
}


def _which(program: str) -> Optional[str]:
    from shutil import which

    return which(program)


def resolve_isolation(configured: Optional[str] = None) -> str:
    """解析实际生效的隔离级别：``container`` 或 ``nsjail``。

    ``SKILL_RUNNER_ISOLATION`` 可选值：``auto``（默认，有 nsjail 就用）、
    ``none``/``container``（只用容器隔离）、``nsjail``（强制，缺失即报错）。
    """
    raw = (configured or os.environ.get("SKILL_RUNNER_ISOLATION", "auto") or "auto")
    mode = raw.strip().lower()

    if mode in {"nsjail"}:
        if not _which("nsjail"):
            raise SkillRunnerError(
                "SKILL_RUNNER_ISOLATION=nsjail 但未安装 nsjail（镜像需预装，或改为 auto）"
            )
        return "nsjail"

    if mode in {"none", "container", "off"}:
        return "container"

    # auto：能用就用，用不了不报错（容器隔离仍生效）
    return "nsjail" if _which("nsjail") else "container"


def wrap_for_isolation(argv: list, *, skill_dir: str) -> list:
    """按生效的隔离级别包装 argv。"""
    if resolve_isolation() != "nsjail":
        return list(argv)
    wrapper = _ISOLATION_WRAPPERS["nsjail"]
    wrapped = wrapper(list(argv), skill_dir)
    logger.info("[skill_runner] 使用 nsjail 隔离执行: %s", " ".join(wrapped[:8]))
    return wrapped


class SkillRunnerError(RuntimeError):
    """作业无法执行（策略拒绝、skill 不存在、超时等）。"""


@dataclass
class JobRequest:
    """一次 skill 执行请求。"""

    skill_dir: str
    command: str
    timeout_seconds: int = 120
    runtime_env: dict = field(default_factory=dict)
    user_id: object = None
    project_id: object = None
    chat_session_id: object = None
    test_case_id: object = None
    skill_id: object = None
    skill_name: object = None


@dataclass
class JobResult:
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int
    workspace_files: list = field(default_factory=list)
    # 产物回传：仅当作业未提供共享 ARTIFACT_DIR 时，runner 把作业工作目录里的
    # 小文件以 base64 回传（后端用临时目录落盘并走既有产物收集逻辑）。
    # 形如 {"name": "相对路径", "data_b64": "...", "size": n}。
    artifacts: list = field(default_factory=list)


def _resolve_skill_dir(raw_dir: str) -> str:
    """校验 skill 目录存在且位于允许的根目录内。"""
    if not raw_dir:
        raise SkillRunnerError("skill_dir 不能为空")

    allowed_root = os.environ.get("SKILL_RUNNER_SKILLS_ROOT", "").strip()
    resolved = os.path.abspath(raw_dir)

    if allowed_root:
        root = os.path.abspath(allowed_root)
        try:
            if os.path.commonpath([root, resolved]) != root:
                raise SkillRunnerError("skill_dir 超出允许的 skills 根目录")
        except ValueError:
            raise SkillRunnerError("skill_dir 超出允许的 skills 根目录") from None

    if not os.path.isdir(resolved):
        raise SkillRunnerError("skill 目录不存在")

    return resolved


_MAX_ARTIFACT_INLINE_BYTES = 8 * 1024 * 1024
_MAX_ARTIFACT_INLINE_FILES = 20


def _read_returnable_artifacts(workspace_dir: str) -> list:
    """读取作业工作目录里的小文件，打包为可回传载荷（总数与总大小受限）。"""
    import base64

    payloads: list = []
    total = 0
    if not os.path.isdir(workspace_dir):
        return payloads
    for relative in _collect_workspace_files(workspace_dir):
        full_path = os.path.join(workspace_dir, relative)
        try:
            size = os.path.getsize(full_path)
        except OSError:
            continue
        if size > _MAX_ARTIFACT_INLINE_BYTES or total + size > _MAX_ARTIFACT_INLINE_BYTES:
            payloads.append({"name": relative, "data_b64": "", "size": size,
                             "truncated": True})
            continue
        if len(payloads) >= _MAX_ARTIFACT_INLINE_FILES:
            break
        try:
            with open(full_path, "rb") as fh:
                data = fh.read()
        except OSError:
            continue
        total += size
        payloads.append({
            "name": relative,
            "data_b64": base64.b64encode(data).decode("ascii"),
            "size": size,
            "truncated": False,
        })
    return payloads


def _collect_workspace_files(workspace_dir: str) -> list:
    """列出工作目录内产生的文件（相对路径），供调用方取回产物。"""
    collected = []
    for current_root, dirs, files in os.walk(workspace_dir):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "node_modules")]
        for name in files:
            full_path = os.path.join(current_root, name)
            if os.path.islink(full_path):
                continue
            relative = os.path.relpath(full_path, workspace_dir).replace(os.sep, "/")
            collected.append(relative)
    return sorted(collected)


def execute_job(request: JobRequest) -> JobResult:
    """执行一次作业。策略不通过时抛 ``SkillRunnerError``。"""
    skill_dir = _resolve_skill_dir(request.skill_dir)
    timeout_seconds = max(1, min(int(request.timeout_seconds or 120), 600))

    try:
        invocation = parse_skill_command(request.command)
        validate_skill_command(invocation.argv, skill_dir=skill_dir)
    except SkillCommandError as exc:
        audit_skill_execution(
            decision="deny",
            user_id=request.user_id,
            project_id=request.project_id,
            chat_session_id=request.chat_session_id,
            test_case_id=request.test_case_id,
            skill_id=request.skill_id,
            skill_name=request.skill_name,
            argv=[request.command],
            reason=str(exc),
        )
        raise SkillRunnerError(str(exc)) from exc

    # 工作目录：容器内通常是 tmpfs；作业结束即删除，杜绝跨会话持久化。
    workspace_root = os.environ.get("SKILL_RUNNER_WORKSPACE_ROOT", tempfile.gettempdir())
    workspace_dir = tempfile.mkdtemp(prefix="skill-job-", dir=workspace_root)

    # 调用方（backend）通常传入共享的截图/产物目录（两侧同一挂载路径），
    # 这样 backend 的产物收集逻辑无需改动；未提供时退回到作业私有工作目录。
    runtime_env = dict(request.runtime_env or {})
    runtime_env.setdefault("SCREENSHOT_DIR", os.path.join(workspace_dir, "screenshots"))
    runtime_env.setdefault("ARTIFACT_DIR", os.path.join(workspace_dir, "artifacts"))
    runtime_env.setdefault("SKILL_OUTPUT_DIR", runtime_env["ARTIFACT_DIR"])
    runtime_env.update(invocation.env_overrides or {})

    env = build_skill_env(runtime_env=runtime_env)
    os.makedirs(runtime_env["SCREENSHOT_DIR"], exist_ok=True)
    os.makedirs(runtime_env["ARTIFACT_DIR"], exist_ok=True)

    # 工作目录与 backend 进程内模式保持一致：
    # runner 里 skill 目录是只读挂载，而 playwright-cli 会以相对文件名保存截图
    # （只读目录下 EACCES），因此它改在可写的截图目录执行，让截图默认落进
    # SCREENSHOT_DIR；其它 skill 用 skill 目录，保证 `python scripts/x.py`
    # 这类相对路径仍能解析。
    if request.skill_name == "playwright-cli":
        exec_cwd = runtime_env["SCREENSHOT_DIR"]
    else:
        exec_cwd = skill_dir

    started_at = time.monotonic()
    try:
        result = run_skill_command(
            wrap_for_isolation(invocation.argv, skill_dir=skill_dir),
            cwd=exec_cwd,
            env=env,
            timeout_seconds=timeout_seconds,
            stdin_text=invocation.stdin_text,
        )
    except Exception as exc:  # 含 subprocess.TimeoutExpired
        audit_skill_execution(
            decision="deny",
            user_id=request.user_id,
            project_id=request.project_id,
            chat_session_id=request.chat_session_id,
            test_case_id=request.test_case_id,
            skill_id=request.skill_id,
            skill_name=request.skill_name,
            argv=list(invocation.argv),
            reason=f"执行异常: {type(exc).__name__}",
            duration_ms=int((time.monotonic() - started_at) * 1000),
        )
        raise SkillRunnerError(f"命令执行失败: {type(exc).__name__}") from exc
    finally:
        # 作业工作目录只是暂存：无论成功失败都销毁，避免沙箱里留下跨作业残留。
        # 需要持久化的产物由调用方提供的共享 ARTIFACT_DIR / SCREENSHOT_DIR 承载；
        # 未提供共享目录时，把小产物以 base64 随响应回传给后端落盘。
        workspace_files = _collect_workspace_files(workspace_dir)
        artifacts = _read_returnable_artifacts(workspace_dir)
        shutil.rmtree(workspace_dir, ignore_errors=True)

    duration_ms = int((time.monotonic() - started_at) * 1000)

    audit_skill_execution(
        decision="allow",
        user_id=request.user_id,
        project_id=request.project_id,
        chat_session_id=request.chat_session_id,
        test_case_id=request.test_case_id,
        skill_id=request.skill_id,
        skill_name=request.skill_name,
        argv=list(invocation.argv),
        returncode=result.returncode,
        duration_ms=duration_ms,
        output_bytes=len(result.stdout or b"") + len(result.stderr or b""),
    )

    stdout = (result.stdout or b"")[:MAX_CAPTURED_OUTPUT_BYTES].decode("utf-8", errors="replace")
    stderr = (result.stderr or b"")[:MAX_CAPTURED_OUTPUT_BYTES].decode("utf-8", errors="replace")

    return JobResult(
        returncode=result.returncode,
        stdout=stdout,
        stderr=stderr,
        duration_ms=duration_ms,
        workspace_files=workspace_files,
        artifacts=artifacts,
    )
