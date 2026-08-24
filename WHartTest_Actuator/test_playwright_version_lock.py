#!/usr/bin/env python
"""Ensure Docker and Python Playwright versions stay aligned."""

import re
import unittest
from pathlib import Path

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib


ACTUATOR_DIR = Path(__file__).parent
PLAYWRIGHT_VERSION = "1.61.0"


class PlaywrightVersionLockTest(unittest.TestCase):
    def test_dockerfile_uses_locked_playwright_base_image(self):
        dockerfile = ACTUATOR_DIR / "Dockerfile"

        self.assertTrue(dockerfile.exists())
        content = dockerfile.read_text(encoding="utf-8")

        self.assertIn(f"ARG PLAYWRIGHT_VERSION={PLAYWRIGHT_VERSION}", content)
        self.assertIn(
            "FROM mcr.microsoft.com/playwright/python:v${PLAYWRIGHT_VERSION}-jammy",
            content,
        )
        self.assertIn('line.split("#", 1)[0].strip() == expected', content)
        self.assertIn("ERROR: requirements.txt must pin {expected}", content)

    def test_dockerfile_uses_secret_for_optional_pip_index_url(self):
        content = (ACTUATOR_DIR / "Dockerfile").read_text(encoding="utf-8")

        self.assertNotIn("ARG PIP_INDEX_URL", content)
        self.assertIn("--mount=type=secret,id=pip_index_url,required=false", content)
        self.assertIn('PIP_INDEX_URL="https://pypi.org/simple"', content)

    def test_requirements_pins_playwright_to_locked_version(self):
        requirements = (ACTUATOR_DIR / "requirements.txt").read_text(encoding="utf-8")

        self.assertRegex(
            requirements,
            rf"(?m)^playwright=={re.escape(PLAYWRIGHT_VERSION)}\b",
        )

    def test_pyproject_pins_playwright_to_locked_version(self):
        data = tomllib.loads((ACTUATOR_DIR / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertIn(
            f"playwright=={PLAYWRIGHT_VERSION}",
            data["project"]["dependencies"],
        )

    def test_uv_lock_resolves_locked_playwright_version(self):
        data = tomllib.loads((ACTUATOR_DIR / "uv.lock").read_text(encoding="utf-8"))
        packages = {package["name"]: package for package in data["package"]}

        self.assertEqual(packages["playwright"]["version"], PLAYWRIGHT_VERSION)

    def test_docker_context_excludes_local_config_and_tests(self):
        dockerignore = (ACTUATOR_DIR / ".dockerignore").read_text(encoding="utf-8")

        self.assertRegex(dockerignore, r"(?m)^config\.toml$")
        self.assertRegex(dockerignore, r"(?m)^\.env$")
        self.assertRegex(dockerignore, r"(?m)^\.env\.\*$")
        self.assertRegex(dockerignore, r"(?m)^test_\*\.py$")
        self.assertRegex(dockerignore, r"(?m)^\*_test\.py$")


if __name__ == "__main__":
    unittest.main()
