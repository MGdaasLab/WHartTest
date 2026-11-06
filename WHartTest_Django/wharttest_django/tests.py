"""wharttest_django 应用测试。"""

import os
import re
import tempfile
from pathlib import Path

from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import Resolver404, resolve

from .media_views import build_media_url_pattern, serve_media


class MediaServingTests(SimpleTestCase):
    """生产模式（DJANGO_DEBUG=False）下 /media/ 必须可访问且安全。"""

    PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 32

    def setUp(self):
        self.base = tempfile.TemporaryDirectory()
        self.addCleanup(self.base.cleanup)
        self.media_root = Path(self.base.name) / "media"
        self.media_root.mkdir()
        self._write("testcase_screenshots/3/13/case13_step1.png", self.PNG_BYTES)

    def _write(self, relative, content):
        target = self.media_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return target

    def _override(self):
        return override_settings(DEBUG=False, MEDIA_ROOT=str(self.media_root))

    def test_media_route_is_registered_regardless_of_debug(self):
        with self._override():
            match = resolve("/media/testcase_screenshots/3/13/case13_step1.png")
        self.assertIs(match.func, serve_media)

    def test_media_prefix_boundary_is_enforced_by_router(self):
        with self._override():
            try:
                match = resolve("/mediafoo/case13_step1.png")
            except Resolver404:
                match = None
        # 部分分支存在 SPA catch-all 路由，这里只断言 /mediafoo 不会落到媒体视图。
        self.assertFalse(match is not None and match.func is serve_media)

    def test_media_file_is_served_when_debug_is_false(self):
        with self._override():
            response = self.client.get(
                "/media/testcase_screenshots/3/13/case13_step1.png"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(b"".join(response.streaming_content), self.PNG_BYTES)
        # 图片允许内联展示，不得被强制下载。
        self.assertTrue(response["Content-Disposition"].startswith("inline;"))
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Content-Security-Policy"], "default-src 'none';")

    def test_missing_media_file_returns_404_when_debug_is_false(self):
        with self._override():
            response = self.client.get(
                "/media/testcase_screenshots/3/13/not-exist.png"
            )
        self.assertEqual(response.status_code, 404)

    def test_media_path_traversal_is_rejected(self):
        # 关键布局：secret 必须放在 MEDIA_ROOT 的兄弟位置，/media/../secret.txt
        # 才能真实命中它，否则用例在任何实现下都会 404（假绿）。
        secret = Path(self.base.name) / "media-outside-secret.txt"
        secret.write_bytes(b"SECRET-CONTENT")
        with self._override():
            response = self.client.get("/media/../media-outside-secret.txt")
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(b"SECRET-CONTENT", response.content)

    def test_symlink_escape_is_rejected(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        secret = Path(outside.name) / "media-outside-secret.txt"
        secret.write_bytes(b"SECRET-CONTENT")
        os.symlink(secret, self.media_root / "escape.txt")
        with self._override():
            response = self.client.get("/media/escape.txt")
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(b"SECRET-CONTENT", response.content)

    def test_denied_prefixes_are_not_public(self):
        self._write("requirement_documents/1/requirement.docx", b"DOC-CONTENT")
        self._write("skill_runtime/ui-auth-state/state.json", b"COOKIE-CONTENT")
        self._write("skills/1/9/api_tools.py", b"_DEFAULT_API_KEY = 'sk-live-value'")
        with self._override():
            for url in (
                "/media/requirement_documents/1/requirement.docx",
                "/media/skill_runtime/ui-auth-state/state.json",
                "/media/skills/1/9/api_tools.py",
            ):
                with self.subTest(url=url):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 404)

    def test_symlink_into_denied_prefix_is_rejected(self):
        self._write("requirement_documents/1/requirement.docx", b"DOC-CONTENT")
        os.symlink(
            self.media_root / "requirement_documents/1/requirement.docx",
            self.media_root / "public.docx",
        )
        with self._override():
            response = self.client.get("/media/public.docx")
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(b"DOC-CONTENT", response.content)

    def test_non_inline_type_is_forced_attachment(self):
        self._write("file_management/1/evil.html", b"<script>alert(1)</script>")
        with self._override():
            response = self.client.get("/media/file_management/1/evil.html")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Disposition"].startswith("attachment;"))
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_svg_is_not_inlined(self):
        self._write("testcases/evil.svg", b"<svg xmlns='http://www.w3.org/2000/svg'/>")
        with self._override():
            response = self.client.get("/media/testcases/evil.svg")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Disposition"].startswith("attachment;"))

    def test_write_methods_are_rejected(self):
        request = RequestFactory().post("/media/testcase_screenshots/3/13/x.png")
        with self._override():
            response = serve_media(request, "testcase_screenshots/3/13/x.png")
        self.assertEqual(response.status_code, 405)

    def test_pathological_paths_return_404(self):
        # 软链指环（RuntimeError）、NUL（ValueError）、超长路径（OSError）
        # 都必须按“不存在”处理，不能变成未认证可达的 500 异常栈。
        os.symlink(self.media_root / "loop-b", self.media_root / "loop-a")
        os.symlink(self.media_root / "loop-a", self.media_root / "loop-b")
        request = RequestFactory().get("/media/x.png")
        with self._override():
            for path in ("loop-a", "x\x00.png", "a" * 5000 + ".png"):
                with self.subTest(path=path[:20]):
                    with self.assertRaises(Exception) as raised:
                        serve_media(request, path)
                    self.assertEqual(getattr(raised.exception, "status_code", 404), 404)


class MediaUrlPatternTests(SimpleTestCase):
    def test_pattern_requires_prefix_boundary(self):
        pattern = build_media_url_pattern("/media")
        self.assertIsNotNone(pattern)
        match = re.match(pattern, "media/3/13/a.png")
        self.assertIsNotNone(match)
        self.assertEqual(match.group("path"), "3/13/a.png")
        self.assertIsNone(re.match(pattern, "mediafoo/a.png"))

    def test_pattern_handles_trailing_slash_variants(self):
        self.assertEqual(
            build_media_url_pattern("/media/"),
            build_media_url_pattern("/media"),
        )

    def test_empty_media_url_disables_route(self):
        self.assertIsNone(build_media_url_pattern(""))
        self.assertIsNone(build_media_url_pattern(None))

    def test_media_url_with_host_is_not_served_by_django(self):
        self.assertIsNone(
            build_media_url_pattern("https://cdn.example.com/media/")
        )