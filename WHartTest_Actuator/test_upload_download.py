#!/usr/bin/env python
"""Tests for remote upload file materialization in TaskConsumer."""

import asyncio
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent))

from consumer import TaskConsumer
from executor import StepConfig


class _FakeStreamResponse:
    def __init__(self, status_code=200, content=b"hello-upload", headers=None):
        self.status_code = status_code
        self._content = content
        self.headers = headers or {}

    async def aread(self):
        return self._content

    async def aiter_bytes(self):
        yield self._content

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeAsyncClient:
    def __init__(self, response):
        self._response = response
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def stream(self, method, url, headers=None):
        self.requests.append((method, url, headers))
        return self._response


class UploadDownloadTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.tmpdir.name) / "runtime_uploads"
        config = MagicMock()
        config.upload_cache_dir = str(self.cache_dir)
        for attr in (
            "browser_type", "headless", "persistent", "user_data_dir",
            "launch_timeout", "action_timeout", "screenshot_dir", "trace_dir",
            "trace_enabled", "trace_screenshots", "trace_snapshots", "trace_sources",
        ):
            if not hasattr(config, attr) or isinstance(getattr(config, attr), MagicMock):
                setattr(config, attr, {
                    "browser_type": "chromium",
                    "headless": True,
                    "persistent": False,
                    "user_data_dir": str(Path(self.tmpdir.name) / "browser"),
                    "launch_timeout": 30,
                    "action_timeout": 30,
                    "screenshot_dir": str(Path(self.tmpdir.name) / "screenshots"),
                    "trace_dir": str(Path(self.tmpdir.name) / "traces"),
                    "trace_enabled": False,
                    "trace_screenshots": False,
                    "trace_snapshots": False,
                    "trace_sources": False,
                }.get(attr))
        self.consumer = TaskConsumer(
            ws_client=MagicMock(),
            api_base_url="http://backend.example",
            config=config,
            api_username="admin",
            api_password="secret",
        )
        self.consumer._get_api_token = AsyncMock(return_value="token-xyz")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_uses_existing_local_path_without_download(self):
        local = Path(self.tmpdir.name) / "local.txt"
        local.write_bytes(b"local-data")

        async def run():
            return await self.consumer._ensure_local_upload_file(
                file_path=str(local),
                file_id=12,
                project_id=3,
                download_url="/api/projects/3/files/12/download/",
                file_name="local.txt",
            )

        result = asyncio.run(run())
        self.assertEqual(result, str(local))

    def test_downloads_when_local_path_missing(self):
        fake_response = _FakeStreamResponse(content=b"remote-bytes")
        fake_client = _FakeAsyncClient(fake_response)

        async def run():
            with patch("consumer.httpx.AsyncClient", return_value=fake_client):
                return await self.consumer._ensure_local_upload_file(
                    file_path="/not/exist/on/actuator/media/a.txt",
                    file_id=12,
                    project_id=3,
                    download_url="/api/projects/3/files/12/download/",
                    file_name="a.txt",
                )

        result = asyncio.run(run())
        self.assertTrue(Path(result).exists())
        self.assertEqual(Path(result).read_bytes(), b"remote-bytes")
        self.assertIn("12_", Path(result).name)
        self.assertTrue(Path(result).name.endswith("a.txt"))
        self.assertEqual(fake_client.requests[0][0], "GET")
        self.assertEqual(
            fake_client.requests[0][1],
            "http://backend.example/api/projects/3/files/12/download/",
        )
        self.assertEqual(
            fake_client.requests[0][2]["Authorization"],
            "Bearer token-xyz",
        )

    def test_materialize_updates_step_input_value(self):
        fake_response = _FakeStreamResponse(content=b"case-bytes")
        fake_client = _FakeAsyncClient(fake_response)
        step = StepConfig(
            step_id=1,
            operation_type="upload",
            locator_type="xpath",
            locator_value="//input",
            input_value="/backend/only/path/file.png",
            upload_file_id=99,
            upload_file_name="file.png",
            upload_download_url="/api/projects/7/files/99/download/",
            upload_project_id=7,
        )

        async def run():
            with patch("consumer.httpx.AsyncClient", return_value=fake_client):
                await self.consumer._materialize_upload_files([step], default_project_id=7)

        asyncio.run(run())
        self.assertTrue(Path(step.input_value).exists())
        self.assertEqual(Path(step.input_value).read_bytes(), b"case-bytes")


    def test_ignores_malicious_download_url(self):
        """case_data must not force actuator JWT to arbitrary hosts (SSRF)."""
        fake_response = _FakeStreamResponse(content=b"safe-bytes")
        fake_client = _FakeAsyncClient(fake_response)
        client_ctor = MagicMock(return_value=fake_client)

        async def run():
            with patch("consumer.httpx.AsyncClient", client_ctor):
                return await self.consumer._ensure_local_upload_file(
                    file_path="/missing/on/actuator/x.bin",
                    file_id=12,
                    project_id=3,
                    download_url="https://evil.example/steal?token=1",
                    file_name="x.bin",
                )

        result = asyncio.run(run())
        self.assertTrue(Path(result).exists())
        self.assertEqual(Path(result).read_bytes(), b"safe-bytes")
        self.assertEqual(
            fake_client.requests[0][1],
            "http://backend.example/api/projects/3/files/12/download/",
        )
        # Absolute untrusted URL must never be requested.
        for _, url, _ in fake_client.requests:
            self.assertNotIn("evil.example", url)
        # Constructor must disable redirect following so JWT cannot leave origin.
        kwargs = client_ctor.call_args.kwargs
        self.assertFalse(kwargs.get("follow_redirects", True))

    def test_ignores_mismatched_relative_download_url(self):
        fake_response = _FakeStreamResponse(content=b"ok")
        fake_client = _FakeAsyncClient(fake_response)

        async def run():
            with patch("consumer.httpx.AsyncClient", return_value=fake_client):
                return await self.consumer._download_managed_file(
                    file_id=5,
                    project_id=9,
                    download_url="/api/projects/1/files/999/download/",
                    file_name="a.txt",
                )

        result = asyncio.run(run())
        self.assertEqual(
            fake_client.requests[0][1],
            "http://backend.example/api/projects/9/files/5/download/",
        )
        self.assertTrue(Path(result).exists())

    def test_requires_project_id_for_remote_download(self):
        async def run():
            return await self.consumer._ensure_local_upload_file(
                file_path="/not/local/missing.txt",
                file_id=12,
                project_id=None,
                download_url="https://evil.example/x",
                file_name="missing.txt",
            )

        with self.assertRaises(FileNotFoundError) as ctx:
            asyncio.run(run())
        self.assertIn("project_id", str(ctx.exception))

    def test_download_requires_file_id_and_project_id(self):
        async def run_missing_file():
            await self.consumer._download_managed_file(
                file_id=None,
                project_id=3,
                download_url="/api/projects/3/files/1/download/",
            )

        async def run_missing_project():
            await self.consumer._download_managed_file(
                file_id=12,
                project_id=None,
            )

        with self.assertRaises(ValueError):
            asyncio.run(run_missing_file())
        with self.assertRaises(ValueError):
            asyncio.run(run_missing_project())


    def test_cache_reused_when_sha_matches(self):
        content = b"cached-bytes"
        sha = hashlib.sha256(content).hexdigest()
        # Pre-seed cache at the expected path
        path = self.consumer._upload_cache_path(12, "a.txt", sha)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        self.consumer._write_upload_cache_meta(path, file_id=12, sha256=sha, size=len(content))
        fake_client = _FakeAsyncClient(_FakeStreamResponse(content=b"should-not-download"))

        async def run():
            with patch("consumer.httpx.AsyncClient", return_value=fake_client):
                return await self.consumer._ensure_local_upload_file(
                    file_path="/missing/x",
                    file_id=12,
                    project_id=3,
                    file_name="a.txt",
                    file_sha=sha,
                    file_size=len(content),
                )

        result = asyncio.run(run())
        self.assertEqual(Path(result).read_bytes(), content)
        self.assertEqual(fake_client.requests, [])

    def test_cache_invalidates_on_sha_change(self):
        old_content = b"old-content"
        old_sha = hashlib.sha256(old_content).hexdigest()
        new_content = b"new-content-xx"
        new_sha = hashlib.sha256(new_content).hexdigest()
        old_path = self.consumer._upload_cache_path(12, "a.txt", old_sha)
        old_path.parent.mkdir(parents=True, exist_ok=True)
        old_path.write_bytes(old_content)
        self.consumer._write_upload_cache_meta(old_path, file_id=12, sha256=old_sha, size=len(old_content))

        fake_client = _FakeAsyncClient(
            _FakeStreamResponse(
                content=new_content,
                headers={"X-File-Sha256": new_sha},
            )
        )

        async def run():
            with patch("consumer.httpx.AsyncClient", return_value=fake_client):
                return await self.consumer._ensure_local_upload_file(
                    file_path="/missing/x",
                    file_id=12,
                    project_id=3,
                    file_name="a.txt",
                    file_sha=new_sha,
                    file_size=len(new_content),
                )

        result = asyncio.run(run())
        self.assertEqual(Path(result).read_bytes(), new_content)
        self.assertTrue(str(result).endswith(f"{new_sha[:16]}_a.txt") or new_sha[:16] in Path(result).name)
        self.assertFalse(old_path.exists())
        self.assertEqual(len(fake_client.requests), 1)

    def test_cache_expires_by_ttl(self):
        content = b"stale"
        sha = hashlib.sha256(content).hexdigest()
        path = self.consumer._upload_cache_path(8, "s.txt", sha)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        self.consumer._write_upload_cache_meta(path, file_id=8, sha256=sha, size=len(content))
        # Backdate mtime beyond TTL
        import os, time
        old_mtime = time.time() - (self.consumer.UPLOAD_CACHE_TTL_SECONDS + 100)
        os.utime(path, (old_mtime, old_mtime))

        fake_client = _FakeAsyncClient(_FakeStreamResponse(content=b"fresh"))

        async def run():
            with patch("consumer.httpx.AsyncClient", return_value=fake_client):
                return await self.consumer._ensure_local_upload_file(
                    file_path="/missing/s",
                    file_id=8,
                    project_id=1,
                    file_name="s.txt",
                    # No expected sha: TTL expiry alone must force re-download.
                )

        result = asyncio.run(run())
        self.assertEqual(Path(result).read_bytes(), b"fresh")
        self.assertEqual(len(fake_client.requests), 1)

    def test_parse_file_id_from_value(self):
        self.assertEqual(TaskConsumer._parse_file_id("file_id:42"), 42)
        self.assertEqual(TaskConsumer._parse_file_id(42), 42)
        self.assertIsNone(TaskConsumer._parse_file_id("not-a-id"))


if __name__ == "__main__":
    unittest.main()
