"""平台内置 Skill 安装时的 API Key 注入。

内部 Skill（依赖平台 API Key 调用后端）在上传/商店安装/Git 导入时，
将用户确认的 Key 写入 Skill 脚本默认值，避免依赖运行时环境变量。
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# 依赖平台 API Key 的内部 Skill 名称（与 SKILL.md / manifest name 对齐）
INTERNAL_PLATFORM_SKILL_NAMES = frozenset(
    {
        "whart-test",
        "api-automation",
        "ui-automation",
    }
)

DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"


def is_internal_platform_skill(skill_name: str) -> bool:
    return (skill_name or "").strip() in INTERNAL_PLATFORM_SKILL_NAMES


def _escape_py_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'")


def inject_api_key_into_skill_dir(
    skill_dir: str,
    skill_name: str,
    api_key: str,
    base_url: str = DEFAULT_BACKEND_URL,
) -> list[str]:
    """将 api_key / base_url 写入内部 Skill 脚本的默认配置。

    Returns:
        被修改的文件相对路径列表。
    """
    if not is_internal_platform_skill(skill_name):
        return []

    api_key = (api_key or "").strip()
    base_url = (base_url or DEFAULT_BACKEND_URL).strip().rstrip("/") or DEFAULT_BACKEND_URL
    if not api_key:
        raise ValueError("api_key 不能为空")

    root = Path(skill_dir)
    if not root.is_dir():
        raise ValueError(f"Skill 目录不存在: {skill_dir}")

    key_esc = _escape_py_string(api_key)
    url_esc = _escape_py_string(base_url)
    modified: list[str] = []

    for path in root.rglob("*.py"):
        if path.name.startswith("__") or "__pycache__" in path.parts:
            continue
        try:
            original = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        updated = original

        # WHARTTEST_API_KEY = os.environ.get("WHARTTEST_API_KEY", "...")
        updated = re.sub(
            r'os\.environ\.get\(\s*["\']WHARTTEST_API_KEY["\']\s*,\s*["\'][^"\']*["\']\s*\)',
            f'os.environ.get("WHARTTEST_API_KEY", "{key_esc}")',
            updated,
        )
        # BASE_URL = os.environ.get("WHARTTEST_BACKEND_URL", "...")
        updated = re.sub(
            r'os\.environ\.get\(\s*["\']WHARTTEST_BACKEND_URL["\']\s*,\s*["\'][^"\']*["\']\s*\)',
            f'os.environ.get("WHARTTEST_BACKEND_URL", "{url_esc}")',
            updated,
        )

        # 硬编码：API_KEY = '...' / API_KEY = "..."
        updated = re.sub(
            r'(?m)^(\s*API_KEY\s*=\s*)([\'"])([^\'"]*)\2',
            rf'\1"{key_esc}"',
            updated,
        )
        # 硬编码：BASE_URL = 'http://...'
        updated = re.sub(
            r'(?m)^(\s*BASE_URL\s*=\s*)([\'"])(https?://[^\'"]*)\2',
            rf'\1"{url_esc}"',
            updated,
        )

        if updated != original:
            path.write_text(updated, encoding="utf-8")
            modified.append(str(path.relative_to(root)).replace("\\", "/"))
            logger.info(
                "已向内部 Skill 注入 API Key: skill=%s file=%s",
                skill_name,
                path.name,
            )

    return modified
