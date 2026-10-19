"""skill-runner（第 2 层执行面）单元测试。

覆盖：
1. 执行器复用第 1 层策略（白名单拒绝、env 白名单、非法 skill 目录）；
2. 执行器能真正跑通一条命令，并在作业结束后清理工作目录；
3. HTTP 服务的鉴权（缺 token 一律拒绝、错误 token 拒绝、正确 token 放行）。
"""

import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

# skill_runner 与 backend 共用同一份命令策略模块
sys.path.insert(0, str(Path(__file__).resolve().parent / "builtin_tools"))  # noqa: E402

from orchestrator_integration.builtin_tools.skill_runner_client import (  # noqa: E402
    SkillRunnerUnavailable,
    runner_exec_mode,
    submit_job,
)
from skill_runner.executor import (  # noqa: E402
    JobRequest,
    SkillRunnerError,
    execute_job,
    resolve_isolation,
    wrap_for_isolation,
)
from skill_runner.server import build_server  # noqa: E402


class ExecuteJobTests(SimpleTestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.skill_dir = Path(self.temporary_directory.name) / "skill"
        self.skill_dir.mkdir()
        self.workspace_root = Path(self.temporary_directory.name) / "workspace"
        self.workspace_root.mkdir()

    def test_rejects_non_allowlisted_launcher(self):
        with self.assertRaises(SkillRunnerError):
            execute_job(
                JobRequest(
                    skill_dir=str(self.skill_dir),
                    command="bash -c 'id'",
                )
            )

    def test_rejects_shell_metacharacters(self):
        with self.assertRaises(SkillRunnerError):
            execute_job(
                JobRequest(
                    skill_dir=str(self.skill_dir),
                    command="python x.py; rm -rf /",
                )
            )

    def test_rejects_unexpected_env_prefix(self):
        with self.assertRaises(SkillRunnerError):
            execute_job(
                JobRequest(
                    skill_dir=str(self.skill_dir),
                    command=f"PATH=/tmp/evil {sys.executable} x.py",
                )
            )

    def test_rejects_missing_skill_dir(self):
        with self.assertRaises(SkillRunnerError):
            execute_job(
                JobRequest(
                    skill_dir=str(self.skill_dir / "nope"),
                    command=f"{sys.executable} x.py",
                )
            )

    def test_rejects_skill_dir_outside_allowed_root(self):
        allowed_root = Path(self.temporary_directory.name) / "allowed"
        allowed_root.mkdir()
        outside = Path(self.temporary_directory.name) / "outside"
        outside.mkdir()
        with patch.dict(
            os.environ, {"SKILL_RUNNER_SKILLS_ROOT": str(allowed_root)}, clear=False
        ):
            with self.assertRaises(SkillRunnerError):
                execute_job(
                    JobRequest(skill_dir=str(outside), command=f"{sys.executable} x.py")
                )

    def test_executes_command_without_platform_secrets(self):
        script = self.skill_dir / "echo_env.py"
        script.write_text(
            "import os\n"
            "print('SECRET_PRESENT=' + str('DJANGO_SECRET_KEY' in os.environ))\n",
            encoding="utf-8",
        )
        with patch.dict(
            os.environ,
            {"SKILL_RUNNER_WORKSPACE_ROOT": str(self.workspace_root)},
            clear=False,
        ):
            with patch.dict(
                os.environ,
                {"DJANGO_SECRET_KEY": "should-not-leak"},
                clear=False,
            ):
                result = execute_job(
                    JobRequest(
                        skill_dir=str(self.skill_dir),
                        command=f"{sys.executable} echo_env.py",
                        timeout_seconds=30,
                    )
                )

        self.assertEqual(result.returncode, 0)
        self.assertIn("SECRET_PRESENT=False", result.stdout)

    def test_playwright_cli_runs_in_writable_screenshot_dir(self):
        """runner 里 skill 目录只读：playwright-cli 必须在可写的截图目录执行。"""
        script = self.skill_dir / "cwd.py"
        script.write_text("import os\nprint(os.getcwd())\n", encoding="utf-8")
        shot_dir = Path(self.temporary_directory.name) / "shared-screenshots"
        with patch.dict(
            os.environ,
            {"SKILL_RUNNER_WORKSPACE_ROOT": str(self.workspace_root)},
            clear=False,
        ):
            # 注意：playwright-cli 的 cwd 是截图目录，因此其命令依赖 PATH 解析
            # （真实的 playwright-cli / npx playwright-cli 正是如此），脚本要用绝对路径。
            pw_result = execute_job(
                JobRequest(
                    skill_dir=str(self.skill_dir),
                    command=f"{sys.executable} {script}",
                    timeout_seconds=30,
                    runtime_env={"SCREENSHOT_DIR": str(shot_dir)},
                    skill_name="playwright-cli",
                )
            )
            # 其它 skill 的 cwd 仍是 skill 目录，相对脚本路径可解析
            other_result = execute_job(
                JobRequest(
                    skill_dir=str(self.skill_dir),
                    command=f"{sys.executable} cwd.py",
                    timeout_seconds=30,
                    runtime_env={"SCREENSHOT_DIR": str(shot_dir)},
                    skill_name="wharttest",
                )
            )

        # playwright-cli：cwd 为可写截图目录
        self.assertEqual(pw_result.returncode, 0)
        self.assertEqual(pw_result.stdout.strip(), str(shot_dir))
        # 其它 skill：cwd 仍是 skill 目录（相对脚本路径依赖它）
        self.assertEqual(other_result.stdout.strip(), str(self.skill_dir))

    def test_artifacts_returned_inline_when_no_shared_dir(self):
        """未提供共享产物目录时，工作目录里的小文件应以 base64 随响应回传。"""
        import base64

        script = self.skill_dir / "make_art.py"
        script.write_text(
            "import os\n"
            "os.makedirs(os.environ['ARTIFACT_DIR'], exist_ok=True)\n"
            "open(os.path.join(os.environ['ARTIFACT_DIR'], 'r.txt'), 'w').write('payload')\n",
            encoding="utf-8",
        )
        with patch.dict(
            os.environ,
            {"SKILL_RUNNER_WORKSPACE_ROOT": str(self.workspace_root)},
            clear=False,
        ):
            result = execute_job(
                JobRequest(
                    skill_dir=str(self.skill_dir),
                    command=f"{sys.executable} make_art.py",
                    timeout_seconds=30,
                )
            )

        self.assertEqual(result.returncode, 0)
        names = [item["name"] for item in result.artifacts]
        self.assertIn("artifacts/r.txt", names)
        payload = next(a for a in result.artifacts if a["name"] == "artifacts/r.txt")
        self.assertFalse(payload.get("truncated"))
        self.assertEqual(
            base64.b64decode(payload["data_b64"]).decode("utf-8"), "payload"
        )
        # 工作目录仍然被清理
        self.assertEqual(list(self.workspace_root.iterdir()), [])

    def test_job_workspace_is_removed_after_run(self):
        script = self.skill_dir / "write_file.py"
        script.write_text(
            "import os\n"
            "target = os.path.join(os.environ['ARTIFACT_DIR'], 'out.txt')\n"
            "os.makedirs(os.environ['ARTIFACT_DIR'], exist_ok=True)\n"
            "open(target, 'w').write('data')\n"
            "print(os.environ['ARTIFACT_DIR'])\n",
            encoding="utf-8",
        )
        with patch.dict(
            os.environ,
            {"SKILL_RUNNER_WORKSPACE_ROOT": str(self.workspace_root)},
            clear=False,
        ):
            result = execute_job(
                JobRequest(
                    skill_dir=str(self.skill_dir),
                    command=f"{sys.executable} write_file.py",
                    timeout_seconds=30,
                )
            )

        self.assertEqual(result.returncode, 0)
        artifacts_dir = result.stdout.strip().splitlines()[-1]
        # 未提供共享产物目录时落在作业私有工作目录，作业结束后应被清理
        self.assertIn(str(self.workspace_root), artifacts_dir)
        self.assertFalse(os.path.exists(artifacts_dir))
        self.assertEqual(list(self.workspace_root.iterdir()), [])


class RunnerServerAuthTests(SimpleTestCase):
    TOKEN = "runner-shared-secret"

    def setUp(self):
        self.server = build_server("127.0.0.1", 0, self.TOKEN)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._stop_server)

    def _stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def _post(self, path: str, payload: dict, token: str = "") -> tuple[int, dict]:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_health_needs_no_token(self):
        with urllib.request.urlopen(
            f"http://127.0.0.1:{self.port}/health", timeout=10
        ) as response:
            self.assertEqual(response.status, 200)
            self.assertTrue(json.loads(response.read().decode("utf-8"))["ok"])

    def test_execute_requires_token(self):
        status, body = self._post("/execute", {"skill_dir": "/tmp", "command": "echo"})
        self.assertEqual(status, 401)
        self.assertFalse(body["ok"])

    def test_execute_rejects_wrong_token(self):
        status, _ = self._post(
            "/execute", {"skill_dir": "/tmp", "command": "echo"}, token="wrong"
        )
        self.assertEqual(status, 401)

    def test_execute_rejects_policy_violation_with_400(self):
        status, body = self._post(
            "/execute",
            {"skill_dir": tempfile.gettempdir(), "command": "bash -c 'id'"},
            token=self.TOKEN,
        )
        self.assertEqual(status, 400)
        self.assertFalse(body["ok"])

    def test_unknown_path_returns_404(self):
        status, _ = self._post("/nope", {}, token=self.TOKEN)
        self.assertEqual(status, 404)


class RunnerClientTests(SimpleTestCase):
    def test_default_mode_is_runner(self):
        # 默认执行面是第 2 层 runner 沙箱：未显式配置时必须走 runner，不得静默退化到进程内。
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SKILL_EXEC_MODE", None)
            self.assertEqual(runner_exec_mode(), "runner")

    def test_explicit_inprocess_mode(self):
        # 仅显式配置时才允许第 1 层进程内执行（本地开发/轻量部署的逃生场景）。
        with patch.dict(os.environ, {"SKILL_EXEC_MODE": "inprocess"}, clear=False):
            self.assertEqual(runner_exec_mode(), "inprocess")

    def test_runner_mode_requires_url_and_token(self):
        with patch.dict(os.environ, {"SKILL_EXEC_MODE": "runner"}, clear=False):
            os.environ.pop("SKILL_RUNNER_URL", None)
            os.environ.pop("SKILL_RUNNER_TOKEN", None)
            with self.assertRaises(SkillRunnerUnavailable):
                submit_job(skill_dir="/tmp", command="echo", timeout_seconds=5)

    def test_runner_mode_with_token_but_no_url_fails_loudly(self):
        with patch.dict(
            os.environ,
            {"SKILL_EXEC_MODE": "runner", "SKILL_RUNNER_TOKEN": "t"},
            clear=False,
        ):
            os.environ.pop("SKILL_RUNNER_URL", None)
            with self.assertRaises(SkillRunnerUnavailable):
                submit_job(skill_dir="/tmp", command="echo", timeout_seconds=5)


@unittest.skipIf(os.name == "nt", "POSIX 专用")
class RunnerClientEndToEndTests(SimpleTestCase):
    """backend 客户端 + runner 服务端的真实串通（本机回环）。"""

    TOKEN = "e2e-secret"

    def test_submit_job_round_trip(self):
        server = build_server("127.0.0.1", 0, self.TOKEN)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 5)

        skill_dir = Path(temporary_directory.name) / "skill"
        skill_dir.mkdir()
        (skill_dir / "hi.py").write_text("print('hi from runner')", encoding="utf-8")

        with patch.dict(
            os.environ,
            {
                "SKILL_EXEC_MODE": "runner",
                "SKILL_RUNNER_URL": f"http://127.0.0.1:{port}",
                "SKILL_RUNNER_TOKEN": self.TOKEN,
            },
            clear=False,
        ):
            outcome = submit_job(
                skill_dir=str(skill_dir),
                command=f"{sys.executable} hi.py",
                timeout_seconds=30,
            )

        self.assertEqual(outcome.returncode, 0)
        self.assertIn("hi from runner", outcome.stdout)

class IsolationWrapperTests(SimpleTestCase):
    """第 3 层：syscall 级隔离包装器的解析与退化行为。"""

    def test_explicit_nsjail_requires_binary(self):
        with patch.dict(os.environ, {"SKILL_RUNNER_ISOLATION": "nsjail"}, clear=False):
            with patch("skill_runner.executor._which", return_value=None):
                with self.assertRaises(SkillRunnerError):
                    resolve_isolation()

    def test_explicit_nsjail_used_when_available(self):
        with patch.dict(os.environ, {"SKILL_RUNNER_ISOLATION": "nsjail"}, clear=False):
            with patch("skill_runner.executor._which", return_value="/usr/bin/nsjail"):
                self.assertEqual(resolve_isolation(), "nsjail")
                wrapped = wrap_for_isolation(["python", "a.py"], skill_dir="/srv/skill")
                self.assertEqual(wrapped[0], "nsjail")
                self.assertIn("--", wrapped)
                self.assertEqual(wrapped[-2:], ["python", "a.py"])

    def test_auto_falls_back_to_container_isolation(self):
        with patch.dict(os.environ, {"SKILL_RUNNER_ISOLATION": "auto"}, clear=False):
            with patch("skill_runner.executor._which", return_value=None):
                self.assertEqual(resolve_isolation(), "container")
                self.assertEqual(
                    wrap_for_isolation(["python", "a.py"], skill_dir="/srv/skill"),
                    ["python", "a.py"],
                )

    def test_none_forces_container_isolation(self):
        with patch.dict(os.environ, {"SKILL_RUNNER_ISOLATION": "none"}, clear=False):
            with patch("skill_runner.executor._which", return_value="/usr/bin/nsjail"):
                self.assertEqual(resolve_isolation(), "container")
