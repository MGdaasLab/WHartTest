"""
skill-runner 客户端（backend 侧）

当 ``SKILL_EXEC_MODE=runner`` 时，skill 命令不再在 backend 进程内执行，而是提交给
独立 runner 容器；``SKILL_EXEC_MODE=inprocess``（默认）保持第 1 层的进程内加固行为。

设计要点：

- runner 不可达时**不静默回退**到进程内执行：回退等于绕开隔离，必须显式失败并提示运维；
- 只在容器网络内调用，凭 ``SKILL_RUNNER_TOKEN`` 共享密钥鉴权；
- 只把必要的作业字段传过去，不传任何平台机密。
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("orchestrator_integration")


class SkillRunnerUnavailable(RuntimeError):
    """runner 未配置或不可达。"""


@dataclass
class RunnerJobOutcome:
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int
    workspace_files: list
    artifacts: list = field(default_factory=list)


def runner_exec_mode() -> str:
    """当前执行模式：``runner`` 或 ``inprocess``（默认）。"""
    mode = (
        getattr(_settings(), "SKILL_EXEC_MODE", None)
        or os.environ.get("SKILL_EXEC_MODE")
        or "inprocess"
    )
    mode = str(mode).strip().lower()
    return "runner" if mode == "runner" else "inprocess"


def _settings():
    try:
        from django.conf import settings

        return settings
    except Exception:  # pragma: no cover - 独立运行时无 Django
        return None


def _setting(name: str, default=None):
    settings = _settings()
    if settings is not None:
        try:
            value = getattr(settings, name, None)
            if value not in (None, ""):
                return value
        except Exception:
            pass
    value = os.environ.get(name)
    return default if value in (None, "") else value


def _runner_endpoint() -> tuple[str, str]:
    url = str(_setting("SKILL_RUNNER_URL", "") or "").strip().rstrip("/")
    token = str(_setting("SKILL_RUNNER_TOKEN", "") or "").strip()
    if not url:
        raise SkillRunnerUnavailable(
            "SKILL_EXEC_MODE=runner 但未配置 SKILL_RUNNER_URL"
        )
    if not token:
        raise SkillRunnerUnavailable(
            "SKILL_EXEC_MODE=runner 但未配置 SKILL_RUNNER_TOKEN"
        )
    return url, token


def submit_job(
    *,
    skill_dir: str,
    command: str,
    timeout_seconds: int,
    runtime_env: Optional[dict] = None,
    user_id: object = None,
    project_id: object = None,
    chat_session_id: object = None,
    test_case_id: object = None,
    skill_id: object = None,
    skill_name: object = None,
) -> RunnerJobOutcome:
    """把作业提交给 runner 并等待结果。"""
    base_url, token = _runner_endpoint()
    payload = {
        "skill_dir": skill_dir,
        "command": command,
        "timeout_seconds": int(timeout_seconds),
        # runtime_env 只应包含用户级 API Key 与产物目录等按会话注入的变量。
        "runtime_env": dict(runtime_env or {}),
        "user_id": user_id,
        "project_id": project_id,
        "chat_session_id": chat_session_id,
        "test_case_id": test_case_id,
        "skill_id": skill_id,
        "skill_name": skill_name,
    }
    request = urllib.request.Request(
        f"{base_url}/execute",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )

    # 作业超时 + 宽限：runner 侧是内核级超时，这里多给 30 秒等它把结果写完。
    http_timeout = max(30, int(timeout_seconds) + 30)
    try:
        with urllib.request.urlopen(request, timeout=http_timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("error", "")
        except Exception:
            detail = ""
        if exc.code == 400:
            # 策略拒绝/目录非法等业务性失败，交给上层按错误返回给模型。
            return RunnerJobOutcome(
                returncode=-1,
                stdout="",
                stderr=detail or "runner 拒绝了该命令",
                duration_ms=0,
                workspace_files=[],
            )
        raise SkillRunnerUnavailable(f"runner 返回 HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise SkillRunnerUnavailable(f"runner 不可达: {exc}") from exc

    return RunnerJobOutcome(
        returncode=int(body.get("returncode") or 0),
        stdout=str(body.get("stdout") or ""),
        stderr=str(body.get("stderr") or ""),
        duration_ms=int(body.get("duration_ms") or 0),
        workspace_files=list(body.get("workspace_files") or []),
        artifacts=list(body.get("artifacts") or []),
    )
