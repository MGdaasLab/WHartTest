"""页面状态序列化（文本快照 / VLM 截图双模式）。"""

import base64
import logging

from .models import ObservationResult

logger = logging.getLogger(__name__)

# 文本快照截断长度（初始/默认）
_TEXT_SNAPSHOT_LIMIT = 8000

# 当前页面状态的消息前缀标记（中间件据此识别并刷新唯一一条页面快照）
OBS_MARKER = "[当前页面状态]\n"


async def observe_page(page, supports_vision: bool, cap_chars: int = _TEXT_SNAPSHOT_LIMIT) -> ObservationResult:
    """读取当前页面状态。

    - supports_vision=True：截取视口 JPEG 返回 base64 data URL。
    - supports_vision=False：尝试可访问性树，失败回退 document.body.innerText，按 cap_chars 截断。
    """
    url = page.url
    try:
        title = await page.title()
    except Exception:
        title = ""

    if supports_vision:
        try:
            shot = await page.screenshot(full_page=False, type="jpeg", quality=80)
            data_url = "data:image/jpeg;base64," + base64.b64encode(shot).decode()
            return ObservationResult(
                url=url,
                title=title,
                text=f"URL: {url}\nTitle: {title}\n[截图随图片提供]",
                screenshot_data_url=data_url,
                has_image=True,
            )
        except Exception as e:
            logger.warning(f"VLM 截图失败，回退文本模式: {e}")

    text = await _text_snapshot(page, cap_chars)
    return ObservationResult(
        url=url,
        title=title,
        text=f"URL: {url}\nTitle: {title}\n\n页面内容（可交互元素快照）:\n{text}",
    )


async def _text_snapshot(page, cap_chars: int = _TEXT_SNAPSHOT_LIMIT) -> str:
    """优先用可访问性树，失败回退 innerText。"""
    cap = max(1, int(cap_chars or _TEXT_SNAPSHOT_LIMIT))
    try:
        a11y = await page.accessibility.snapshot()
        if a11y:
            lines = _format_a11y(a11y)
            snapshot = "\n".join(lines)
            if snapshot.strip():
                return snapshot[:cap]
    except Exception as e:
        logger.debug(f"可访问性树获取失败，回退 innerText: {e}")

    try:
        text = await page.evaluate("document.body ? (document.body.innerText || '') : ''")
        text = text or ""
        return text[:cap]
    except Exception as e:
        logger.warning(f"innerText 获取失败: {e}")
        return "(无法获取页面文本快照)"


def _format_a11y(node: dict, lines: list[str] | None = None, depth: int = 0) -> list[str]:
    """把可访问性树折叠为带层级的可读文本，仅保留有意义的节点。"""
    if lines is None:
        lines = []

    role = node.get("role")
    name = node.get("name", "")
    name_str = name.strip() if isinstance(name, str) else ""

    # 仅记录有角色且多为可交互或有名称的节点，避免噪声
    interactive_roles = {
        "button", "link", "textbox", "checkbox", "radio", "combobox",
        "menuitem", "tab", "option", "searchbox", "slider", "switch",
        "textbox", "listitem", "heading", "image", "dialog",
    }
    show = role and (role in interactive_roles or name_str)
    if show:
        detail = f"{'  ' * depth}- role={role}"
        if name_str:
            detail += f" name={name_str!r}"
        lines.append(detail)

    for child in node.get("children", []) or []:
        _format_a11y(child, lines, depth + 1)
    return lines