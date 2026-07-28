"""
Playwright 持久化会话管理

提供跨多次 execute_skill_script 调用的浏览器会话保持能力。
通过 stdin/stdout JSON-RPC 与长驻 Node.js 进程通信。
"""

from __future__ import annotations

import atexit
import json
import os
import queue
import shlex
import subprocess
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


import logging

from .output_sanitizer import strip_terminal_control_sequences

logger = logging.getLogger("orchestrator_integration")


class PlaywrightPersistentSessionError(RuntimeError):
    pass


def _strip_outer_quotes(s: str) -> str:
    """去除字符串外层的引号（Windows shlex 保留引号问题）"""
    if len(s) >= 2:
        if (s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'"):
            return s[1:-1]
    return s


def _unescape_js_string(s: str) -> str:
    """
    反转义 JavaScript/shell 字符串中的转义序列。

    转义链: LLM -> tool call -> Python string -> JSON -> JS

    命令行传递时会添加转义层：
    - 原始 JS: await page.fill("input[type=\"text\"]", "admin");
    - 命令行包装后: await page.fill(\"input[type=\\\"text\\\"]\", \"admin\");

    我们需要：
    1. 保留 JS 需要的内部转义 \\\" -> \"
    2. 去除命令行层的外部转义 \" -> "
    """
    result = s
    # 使用临时标记保护 JS 需要的三层转义
    result = result.replace('\\\\\\"', "\x00JS_ESCAPED_DQUOTE\x00")
    result = result.replace("\\\\'", "\x00JS_ESCAPED_SQUOTE\x00")

    # 去除命令行层的两层转义
    result = result.replace('\\"', '"')
    result = result.replace("\\'", "'")

    # 恢复 JS 需要的转义
    result = result.replace("\x00JS_ESCAPED_DQUOTE\x00", '\\"')
    result = result.replace("\x00JS_ESCAPED_SQUOTE\x00", "\\'")

    # 处理反斜杠本身
    result = result.replace("\\\\", "\\")
    return result


def _filter_misplaced_options(args: List[str]) -> List[str]:
    """
    过滤 LLM 误放在命令中的选项参数。

    LLM 有时会将 session_id 等参数错误地放在命令字符串中：
    node run.js --session_id case_11 "actual code..."
    而正确用法是作为 execute_skill_script 的工具参数。
    """
    filtered = []
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg.startswith("--session_id") or arg.startswith("--session-id"):
            if "=" not in arg:
                skip_next = True
            continue
        filtered.append(arg)
    return filtered


def extract_runjs_args(command: str) -> Optional[List[str]]:
    """
    解析 `node run.js ...` 命令，提取 run.js 后的代码。

    使用正则表达式直接提取，避免 shlex 在 Windows 下的转义问题。

    Returns:
        - list[str]: 包含单个代码字符串的列表
        - None: 非 run.js 调用或解析失败
    """
    import re

    raw = (command or "").strip()
    if not raw:
        return None

    # 方法1: 尝试用正则直接提取 run.js 后面的代码
    # 匹配 node run.js "..." 或 node run.js '...'
    match = re.search(r'run\.js\s+["\'](.+)["\']$', raw, re.DOTALL)
    if match:
        code = match.group(1)
        code = _unescape_js_string(code)
        return [code]

    # 方法1.5: 处理 LLM 误放 --session_id 在命令中的情况
    # 示例：node run.js --session_id xxx "code..."
    match = re.search(
        r'run\.js\s+--session[-_]id\s+\S+\s+["\'](.+)["\']$', raw, re.DOTALL
    )
    if match:
        code = match.group(1)
        code = _unescape_js_string(code)
        logger.warning(
            "[extract_runjs_args] LLM 误将 --session_id 放在命令中，已自动过滤"
        )
        return [code]

    # 方法2: 回退到 shlex 解析（保持向后兼容）
    split_modes = [False, True] if os.name == "nt" else [True, False]
    parts: Optional[List[str]] = None
    for posix in split_modes:
        try:
            parts = shlex.split(raw, posix=posix)
            break
        except ValueError:
            continue

    if not parts:
        return None

    for idx, token in enumerate(parts):
        name = os.path.basename(token).lower()
        if name == "run.js" or token.lower().endswith("run.js"):
            args = parts[idx + 1 :]
            processed = [_strip_outer_quotes(a) for a in args]
            processed = [_unescape_js_string(a) for a in processed]
            processed = _filter_misplaced_options(processed)
            return processed

    return None


@dataclass
class _SessionEntry:
    session_key: str
    skill_dir: str
    proc: "_PlaywrightNodeProcess"
    last_used_monotonic: float


class _PlaywrightNodeProcess:
    """
    单个长驻 Node.js 进程，托管 Playwright browser/context/page。
    通过 stdin/stdout 进行 JSON-RPC 通信。
    """

    def __init__(self, skill_dir: str):
        self.skill_dir = os.path.abspath(skill_dir)
        self._proc: Optional[subprocess.Popen[str]] = None
        self._start_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._pending: Dict[str, "queue.Queue[Dict[str, Any]]"] = {}
        self._pending_lock = threading.Lock()
        self._stderr_tail: "deque[str]" = deque(maxlen=200)
        self._stdout_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None

    def _server_script_path(self) -> str:
        return str(Path(__file__).with_name("playwright_persistent_server.js"))

    def _start(self, env: Dict[str, str]) -> None:
        with self._start_lock:
            if self._proc is not None and self._proc.poll() is None:
                return

            cmd = ["node", self._server_script_path(), "--skill-dir", self.skill_dir]

            merged_env = os.environ.copy()
            merged_env.update(env)

            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.skill_dir,
                env=merged_env,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )

            self._stdout_thread = threading.Thread(
                target=self._stdout_reader,
                name=f"pw-stdout[{self.skill_dir[-30:]}]",
                daemon=True,
            )
            self._stderr_thread = threading.Thread(
                target=self._stderr_reader,
                name=f"pw-stderr[{self.skill_dir[-30:]}]",
                daemon=True,
            )
            self._stdout_thread.start()
            self._stderr_thread.start()

            # 增加超时时间以容纳首次 npm install（如果需要）
            resp = self.request("ping", params={}, timeout_seconds=120)
            if not resp.get("ok", False):
                raise PlaywrightPersistentSessionError(
                    self._format_response_error(resp)
                )

        logger.info(f"[persistent_playwright] Node.js 进程启动成功: {self.skill_dir}")

    def _stdout_reader(self) -> None:
        assert self._proc is not None
        assert self._proc.stdout is not None

        for line in self._proc.stdout:
            raw = (line or "").strip()
            if not raw:
                continue

            try:
                msg = json.loads(raw)
            except Exception:
                self._stderr_tail.append(
                    strip_terminal_control_sequences(f"[stdout] {raw}")
                )
                continue

            req_id = msg.get("id")
            if not req_id:
                continue

            with self._pending_lock:
                q = self._pending.get(req_id)
            if q is not None:
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    pass

        self._fail_all_pending("Playwright persistent process exited")

    def _stderr_reader(self) -> None:
        assert self._proc is not None
        assert self._proc.stderr is not None

        for line in self._proc.stderr:
            raw = (line or "").rstrip("\n")
            if raw:
                self._stderr_tail.append(strip_terminal_control_sequences(raw))

    def _fail_all_pending(self, reason: str) -> None:
        with self._pending_lock:
            items = list(self._pending.items())
            self._pending.clear()
        for req_id, q in items:
            try:
                q.put_nowait(
                    {
                        "id": req_id,
                        "ok": False,
                        "error": reason,
                        "stderr": list(self._stderr_tail),
                    }
                )
            except Exception:
                continue

    def _ensure_alive(self) -> None:
        if self._proc is None:
            raise PlaywrightPersistentSessionError(
                "Playwright persistent process not started"
            )
        if self._proc.poll() is not None:
            raise PlaywrightPersistentSessionError(
                "Playwright persistent process is not running"
            )

    def request(
        self, method: str, params: Dict[str, Any], timeout_seconds: int
    ) -> Dict[str, Any]:
        self._ensure_alive()
        assert self._proc is not None
        assert self._proc.stdin is not None

        req_id = uuid.uuid4().hex
        q: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=1)

        with self._pending_lock:
            self._pending[req_id] = q

        payload = {"id": req_id, "method": method, "params": params or {}}
        data = json.dumps(payload, ensure_ascii=False)

        try:
            with self._write_lock:
                self._proc.stdin.write(data + "\n")
                self._proc.stdin.flush()
        except Exception as exc:
            with self._pending_lock:
                self._pending.pop(req_id, None)
            raise PlaywrightPersistentSessionError(
                f"Failed to write to Playwright session: {exc}"
            ) from exc

        try:
            resp = q.get(timeout=timeout_seconds)
        except queue.Empty:
            self.terminate(graceful=False)
            raise TimeoutError(
                f"Playwright persistent request timed out after {timeout_seconds}s"
            )
        finally:
            with self._pending_lock:
                self._pending.pop(req_id, None)

        return resp

    def exec_run_js(
        self, run_js_args: List[str], env: Dict[str, str], timeout_seconds: int
    ) -> str:
        params: Dict[str, Any] = {"args": run_js_args or [], "env": env or {}}
        resp = self.request("exec", params=params, timeout_seconds=timeout_seconds)

        stdout_lines = resp.get("stdout") or []
        stderr_lines = resp.get("stderr") or []
        if isinstance(stdout_lines, str):
            stdout_lines = [stdout_lines]
        if isinstance(stderr_lines, str):
            stderr_lines = [stderr_lines]

        output = ""
        if stdout_lines:
            output += "\n".join(
                strip_terminal_control_sequences(str(x))
                for x in stdout_lines
                if x is not None
            )
        if stderr_lines:
            if output:
                output += "\n--- stderr ---\n"
            output += "\n".join(
                strip_terminal_control_sequences(str(x))
                for x in stderr_lines
                if x is not None
            )

        if not resp.get("ok", False):
            err = resp.get("error")
            if err:
                if output:
                    output = f"{err}\n{output}"
                else:
                    output = strip_terminal_control_sequences(str(err))

        return output

    def terminate(self, graceful: bool = True) -> None:
        if self._proc is None:
            self._join_io_threads()
            return

        if self._proc.poll() is not None:
            self._proc = None
            self._join_io_threads()
            return

        if graceful:
            try:
                self.request("close", params={}, timeout_seconds=5)
            except Exception:
                pass

        try:
            self._proc.terminate()
        except Exception:
            pass

        try:
            self._proc.wait(timeout=3)
        except Exception:
            try:
                self._proc.kill()
            except Exception:
                pass
            try:
                self._proc.wait(timeout=3)
            except Exception:
                pass

        self._proc = None
        self._join_io_threads()
        # Drop pending responses so large payloads can be GC'ed promptly.
        with self._pending_lock:
            self._pending.clear()
        self._stderr_tail.clear()
        logger.info(f"[persistent_playwright] Node.js process terminated: {self.skill_dir}")

    def _join_io_threads(self) -> None:
        for th in (self._stdout_thread, self._stderr_thread):
            if th is None:
                continue
            try:
                if th.is_alive():
                    th.join(timeout=2)
            except Exception:
                pass
        self._stdout_thread = None
        self._stderr_thread = None

    def _format_response_error(self, resp: Dict[str, Any]) -> str:
        pieces: List[str] = []
        if resp.get("error"):
            pieces.append(str(resp["error"]))
        stderr = resp.get("stderr")
        if stderr:
            if isinstance(stderr, list):
                pieces.append("\n".join(str(x) for x in stderr[-50:]))
            else:
                pieces.append(str(stderr))
        tail = list(self._stderr_tail)
        if tail:
            pieces.append("\n".join(tail[-50:]))
        return "\n".join(pieces).strip() or "Unknown Playwright session error"


class PlaywrightSessionManager:
    """
    全局会话管理器：
    - session_key 标识一个持久化 Node+Playwright 实例
    - 空闲超时自动清理（后台线程 + 惰性清理）
    """

    def __init__(self, *, idle_timeout_seconds: int = 900, max_sessions: int = 20):
        self.idle_timeout_seconds = max(30, int(idle_timeout_seconds))
        self.max_sessions = max(1, int(max_sessions))
        self._lock = threading.RLock()
        self._entries: Dict[str, _SessionEntry] = {}
        self._cleanup_started = False
        self._shutdown = False
        atexit.register(self.close_all)

    def _ensure_cleanup_thread(self) -> None:
        with self._lock:
            if self._cleanup_started:
                return
            self._cleanup_started = True

        def _loop() -> None:
            while not self._shutdown:
                try:
                    self.cleanup_expired()
                except Exception:
                    pass
                time.sleep(30)

        t = threading.Thread(target=_loop, name="pw-session-cleanup", daemon=True)
        t.start()

    def _prune_lru_if_needed(self) -> None:
        with self._lock:
            if len(self._entries) <= self.max_sessions:
                return
            victims = sorted(
                self._entries.values(), key=lambda e: e.last_used_monotonic
            )
            to_close = victims[: max(0, len(self._entries) - self.max_sessions)]

        for entry in to_close:
            self.close_session(entry.session_key)

    def execute_run_js(
        self,
        *,
        session_key: str,
        skill_dir: str,
        run_js_args: List[str],
        env: Dict[str, str],
        timeout_seconds: int = 120,
    ) -> str:
        self._ensure_cleanup_thread()
        self.cleanup_expired()

        now = time.monotonic()
        skill_dir_abs = os.path.abspath(skill_dir)

        with self._lock:
            entry = self._entries.get(session_key)
            if entry is None or os.path.abspath(entry.skill_dir) != skill_dir_abs:
                if entry is not None:
                    try:
                        entry.proc.terminate(graceful=True)
                    except Exception:
                        pass
                entry = _SessionEntry(
                    session_key=session_key,
                    skill_dir=skill_dir_abs,
                    proc=_PlaywrightNodeProcess(skill_dir_abs),
                    last_used_monotonic=now,
                )
                self._entries[session_key] = entry
            else:
                # 在执行开始时更新时间戳，防止长时间执行被清理
                entry.last_used_monotonic = now

        self._prune_lru_if_needed()

        entry.proc._start(env=env)

        output = entry.proc.exec_run_js(
            run_js_args=run_js_args, env=env, timeout_seconds=int(timeout_seconds)
        )

        # 执行结束后再次更新时间戳
        with self._lock:
            updated = self._entries.get(session_key)
            if updated is not None:
                updated.last_used_monotonic = time.monotonic()

        return output

    def cleanup_expired(self) -> None:
        now = time.monotonic()
        expired: List[str] = []
        with self._lock:
            for key, entry in self._entries.items():
                if (now - entry.last_used_monotonic) > self.idle_timeout_seconds:
                    expired.append(key)
        for key in expired:
            self.close_session(key)

    def close_session(self, session_key: str) -> None:
        with self._lock:
            entry = self._entries.pop(session_key, None)
        if entry is None:
            return
        try:
            entry.proc.terminate(graceful=True)
        except Exception:
            try:
                entry.proc.terminate(graceful=False)
            except Exception:
                pass

    def close_all(self) -> None:
        self._shutdown = True
        with self._lock:
            keys = list(self._entries.keys())
        for k in keys:
            self.close_session(k)
