"""
skill-runner HTTP 服务

只暴露一个作业接口，用共享密钥鉴权；供 backend 在容器网络内调用。

接口：

- ``GET /health``：存活探针，不需要鉴权
- ``POST /execute``：提交作业，需要 ``Authorization: Bearer <SKILL_RUNNER_TOKEN>``
  请求体：``{"skill_dir": "...", "command": "...", "timeout_seconds": 120, ...}``
  响应体：``{"ok": true, "returncode": 0, "stdout": "...", "stderr": "...", ...}``

安全约束（与容器配置配合）：

- 除 ``/health`` 外一律要求密钥；密钥只在运维侧配置，不写入镜像；
- 只允许执行 ``skill_exec_guard`` 白名单内的命令；
- 请求体大小与并发都有上限；
- 服务自身不读取任何平台机密（runner 容器的环境里就没有）。
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .executor import JobRequest, SkillRunnerError, execute_job

logger = logging.getLogger("skill_runner")

MAX_REQUEST_BYTES = 1024 * 1024
MAX_CONCURRENT_JOBS = int(os.environ.get("SKILL_RUNNER_MAX_CONCURRENT_JOBS", "4"))


class _JobGate:
    """限制并发作业数：超限直接拒绝，避免 runner 被打满。"""

    def __init__(self, capacity: int):
        self._semaphore = threading.BoundedSemaphore(max(1, capacity))

    def acquire(self) -> bool:
        return self._semaphore.acquire(blocking=False)

    def release(self) -> None:
        try:
            self._semaphore.release()
        except ValueError:  # pragma: no cover - 释放次数异常时忽略
            pass


def _json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


class SkillRunnerHandler(BaseHTTPRequestHandler):
    server_version = "skill-runner/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - 对齐基类签名
        logger.info("%s - %s", self.address_string(), format % args)

    # ---------------------------------------------------------------- helpers

    def _send_json(self, status_code: int, payload: dict) -> None:
        body = _json_bytes(payload)
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        expected = (getattr(self.server, "expected_token", "") or "").strip()
        if not expected:
            # 未配置密钥时拒绝一切作业请求（fail closed），避免裸奔暴露。
            logger.error("[skill_runner] SKILL_RUNNER_TOKEN 未配置，拒绝作业请求")
            return False
        header = self.headers.get("Authorization", "")
        prefix = "Bearer "
        if not header.startswith(prefix):
            return False
        return hmac.compare_digest(header[len(prefix):].strip(), expected)

    def _read_json_body(self) -> dict:
        length_header = self.headers.get("Content-Length")
        if not length_header or not length_header.isdigit():
            raise ValueError("缺少 Content-Length")
        length = int(length_header)
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("请求体大小不合法")
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("请求体必须是合法 JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("请求体必须是 JSON 对象")
        return payload

    # ---------------------------------------------------------------- routing

    def do_GET(self) -> None:  # noqa: N802 - 基类约定
        if self.path.split("?")[0] == "/health":
            self._send_json(200, {"ok": True, "service": "skill-runner"})
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 - 基类约定
        if self.path.split("?")[0] != "/execute":
            self._send_json(404, {"ok": False, "error": "not found"})
            return

        if not self._authorized():
            self._send_json(401, {"ok": False, "error": "unauthorized"})
            return

        try:
            payload = self._read_json_body()
        except ValueError as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})
            return

        gate: _JobGate = self.server.job_gate
        if not gate.acquire():
            self._send_json(429, {"ok": False, "error": "runner 繁忙，请稍后重试"})
            return

        try:
            request = JobRequest(
                skill_dir=str(payload.get("skill_dir") or ""),
                command=str(payload.get("command") or ""),
                timeout_seconds=int(payload.get("timeout_seconds") or 120),
                runtime_env=payload.get("runtime_env") or {},
                user_id=payload.get("user_id"),
                project_id=payload.get("project_id"),
                chat_session_id=payload.get("chat_session_id"),
                test_case_id=payload.get("test_case_id"),
                skill_id=payload.get("skill_id"),
                skill_name=payload.get("skill_name"),
            )
            result = execute_job(request)
        except SkillRunnerError as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})
            return
        except Exception as exc:  # pragma: no cover - 兜底，避免 500 带出内部细节
            logger.exception("[skill_runner] 作业执行异常")
            self._send_json(500, {"ok": False, "error": type(exc).__name__})
            return
        finally:
            gate.release()

        self._send_json(
            200,
            {
                "ok": True,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration_ms": result.duration_ms,
                "workspace_files": result.workspace_files,
                "artifacts": result.artifacts,
            },
        )


def build_server(host: str, port: int, token: str) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), SkillRunnerHandler)
    server.expected_token = token
    server.job_gate = _JobGate(MAX_CONCURRENT_JOBS)
    return server


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("SKILL_RUNNER_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    host = os.environ.get("SKILL_RUNNER_HOST", "0.0.0.0")
    port = int(os.environ.get("SKILL_RUNNER_PORT", "8010"))
    token = (os.environ.get("SKILL_RUNNER_TOKEN", "") or "").strip()

    if not token:
        logger.error("SKILL_RUNNER_TOKEN 未配置：服务将启动，但所有作业请求都会被拒绝")

    server = build_server(host, port, token)
    logger.info("skill-runner 监听 %s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
