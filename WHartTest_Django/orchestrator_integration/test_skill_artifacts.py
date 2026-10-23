"""Skill 产物收集的边界约束测试。

背景：产物候选路径来自拼接后的命令输出（模型可控），若只比对 abspath 前缀，
skill 可以在产物目录里放一个指向别处的符号链接，把其它项目/其它用户的文件
伪装成本次产物挂成可下载附件。
"""

import os
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from orchestrator_integration.builtin_tools.skill_tools import (
    _collect_skill_artifacts,
    _is_within_directory,
)


class IsWithinDirectoryTests(SimpleTestCase):
    def test_detects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "root"
            outside = Path(temporary_directory) / "outside"
            root.mkdir()
            outside.mkdir()
            (outside / "secret.txt").write_text("secret", encoding="utf-8")
            link = root / "link"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):  # pragma: no cover - 平台不支持
                self.skipTest("当前环境不支持创建符号链接")

            # 前缀比较会误判为「在 root 内」，realpath 比较必须判否
            self.assertTrue(str(link / "secret.txt").startswith(str(root)))
            self.assertFalse(_is_within_directory(str(link / "secret.txt"), str(root)))

    def test_accepts_real_path_inside_root(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "root"
            root.mkdir()
            (root / "ok.txt").write_text("ok", encoding="utf-8")
            self.assertTrue(_is_within_directory(str(root / "ok.txt"), str(root)))

    def test_missing_arguments_return_false(self):
        self.assertFalse(_is_within_directory("", "/tmp"))
        self.assertFalse(_is_within_directory("/tmp/a.txt", None))


class CollectSkillArtifactsBoundaryTests(SimpleTestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        # 走 MEDIA_ROOT 才能生成可下载 URL，因此把 MEDIA_ROOT 指到临时目录
        self.media_root = Path(self.temporary_directory.name) / "media"
        self.media_root.mkdir()
        self.override = override_settings(
            MEDIA_ROOT=str(self.media_root), MEDIA_URL="/media/"
        )
        self.override.enable()
        self.addCleanup(self.override.disable)

        self.project_dir = self.media_root / "skills" / "1" / "7"
        self.artifacts_dir = self.media_root / "skill_runtime" / "artifacts" / "1" / "c"
        self.screenshots_dir = (
            self.media_root / "skill_runtime" / "screenshots" / "1" / "c"
        )
        self.other_project_dir = self.media_root / "skills" / "2" / "9"
        for path in (
            self.project_dir,
            self.artifacts_dir,
            self.screenshots_dir,
            self.other_project_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

        self.secret = self.other_project_dir / "report.html"
        self.secret.write_text("<html>other tenant</html>", encoding="utf-8")

    def collect(self, output_text: str, *, with_screenshots: bool = True) -> list:
        return _collect_skill_artifacts(
            output_text,
            skill_dir=str(self.project_dir),
            artifacts_dir=str(self.artifacts_dir),
            artifacts_before={},
            screenshots_dir=str(self.screenshots_dir) if with_screenshots else None,
        )

    def test_rejects_absolute_path_outside_session_directories(self):
        collected = self.collect(f"已生成报告：{self.secret}")
        self.assertEqual(collected, [])

    def test_accepts_file_inside_artifacts_dir(self):
        produced = self.artifacts_dir / "out.txt"
        produced.write_text("mine", encoding="utf-8")
        collected = self.collect(f"产物：{produced}")
        self.assertEqual(len(collected), 1)
        self.assertEqual(collected[0]["name"], "out.txt")

    def test_rejects_symlink_pointing_at_another_project(self):
        link = self.artifacts_dir / "link"
        try:
            link.symlink_to(self.other_project_dir)
        except (OSError, NotImplementedError):  # pragma: no cover - 平台不支持
            self.skipTest("当前环境不支持创建符号链接")

        collected = self.collect(f"产物：{link / self.secret.name}")
        self.assertEqual(collected, [])

class ScreenshotCollectionTests(CollectSkillArtifactsBoundaryTests):
    """SCREENSHOT_DIR 内的截图必须能作为可下载附件返回（playwright-cli 主产物）。"""

    def test_screenshot_inside_screenshots_dir_is_collected(self):
        shot = self.screenshots_dir / "step-1.png"
        shot.write_bytes(b"\x89PNG\r\n\x1a\n-fake")

        collected = self.collect(f"已截图：{shot}")

        self.assertEqual(len(collected), 1)
        self.assertEqual(collected[0]["name"], "step-1.png")

    def test_screenshot_collected_by_relative_name(self):
        shot = self.screenshots_dir / "step-2.png"
        shot.write_bytes(b"\x89PNG\r\n\x1a\n-fake")

        collected = self.collect("截图已保存: step-2.png")

        self.assertEqual([item["name"] for item in collected], ["step-2.png"])

    def test_screenshot_rejected_when_screenshots_dir_not_provided(self):
        shot = self.screenshots_dir / "step-3.png"
        shot.write_bytes(b"\x89PNG\r\n\x1a\n-fake")

        # 未传 screenshots_dir 时不属于允许根，仍应拒绝（保持越界防护）
        collected = self.collect(f"已截图：{shot}", with_screenshots=False)

        self.assertEqual(collected, [])
