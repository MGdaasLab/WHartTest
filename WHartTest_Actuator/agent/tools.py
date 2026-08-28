"""LangChain 工具定义：把对 Playwright 页面的操作暴露给 AI Agent。

设计要点：
- 不写 XPath/CSS 选择器，优先按可见文本/角色/标签定位，提升健壮性（css 仅兜底）。
- 非视觉模型下 `screenshot` 返回文件路径而非 base64（避免 base64 成为 token 炸弹）。
- `finish` 工具用 `return_direct=True`，结束循环并通过其 ToolMessage 提取最终结果。
"""

import base64
import json
import logging
import os
from typing import Any, Optional

from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from .observation import observe_page

logger = logging.getLogger(__name__)

# observe 工具返回的文本快照上限（小于 initial 8000，控制单条体量）
_OBSERVE_CAP = 4000


# ============ args_schema ============

class _ByValueModel(BaseModel):
    by: str = Field(
        ...,
        description="如何定位元素。text=可见文本；role=ARIA 角色并可用 name 指定可访问名；"
                    "label=关联标签文本；placeholder=占位文本；testid=data-testid；css=简单 CSS 选择器(兜底)。",
    )
    value: str = Field(..., description="定位值（可见文本/角色名/标签文本等）。")


class NavigateArgs(BaseModel):
    url: str = Field(..., description="完整 URL，如 https://example.com/login")


class ClickArgs(_ByValueModel):
    name: Optional[str] = Field(None, description="当 by=role 时，角色的可访问名，如 'Submit'。")


class FillArgs(_ByValueModel):
    text: str = Field(..., description="要输入的文本。")


class SelectOptionArgs(_ByValueModel):
    by: str = Field("label", description="定位方式：label/text/role。")
    option: str = Field(..., description="要选中的选项可见文本或值。")


class HoverArgs(_ByValueModel):
    pass


class PressKeyArgs(BaseModel):
    key: str = Field(..., description="按键名，如 'Enter'、'Tab'、'Escape'、'ArrowDown'。")


class ScrollArgs(BaseModel):
    delta_x: int = Field(0, description="水平滚动像素（默认0）。")
    delta_y: int = Field(..., description="垂直滚动像素，正=向下。")


class WaitArgs(BaseModel):
    ms: int = Field(..., description="等待毫秒数。")


class ScreenshotArgs(BaseModel):
    full_page: bool = Field(False, description="是否全页截图。")


class AssertConditionArgs(BaseModel):
    type: str = Field(
        ...,
        description="断言类型：text_present | text_absent | url_contains | title_contains",
    )
    expected: str = Field(..., description="期望值。")


class FinishArgs(BaseModel):
    success: bool = Field(..., description="整体任务是否成功。")
    message: str = Field(..., description="人类可读的总结与结果说明。")


# ============ 定位与工具实现 ============

def _resolve_locator(page, by: str, value: str, name: str | None = None):
    """把模型的 by/value 映射到 Playwright locator。"""
    by = (by or "text").lower()
    value = value or ""
    if by == "role":
        if name:
            return page.get_by_role(value, name=name)
        return page.get_by_role(value)
    if by == "label":
        return page.get_by_label(value)
    if by == "placeholder":
        return page.get_by_placeholder(value)
    if by == "text":
        return page.get_by_text(value)
    if by == "testid":
        return page.get_by_test_id(value)
    if by == "css":
        return page.locator(value)
    return page.get_by_text(value)


async def _save_screenshot(page, path: str) -> str:
    """保存截图到 path，返回 path（失败返回空串）。"""
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        await page.screenshot(path=path)
        return path
    except Exception as e:
        logger.warning(f"保存截图失败: {e}")
        return ""


def build_tools(page, supports_vision: bool, screenshot_dir: str, step_id: int) -> list:
    """构建该次运行使用的工具列表（闭包绑定 page/state）。"""

    async def navigate(url: str) -> str:
        if not url:
            return "ERROR: 缺少 url"
        await page.goto(url, wait_until="load")
        return f"已导航到 {url}"

    async def click(by: str, value: str, name: Optional[str] = None) -> str:
        locator = _resolve_locator(page, by, value, name)
        await locator.click(timeout=15000)
        return f"已点击 {by}={value!r}"

    async def fill(by: str, value: str, text: str, name: Optional[str] = None) -> str:
        locator = _resolve_locator(page, by, value, name)
        await locator.fill(text)
        return f"已输入文本到 {by}={value!r}"

    async def select_option(by: str, value: str, option: str) -> str:
        locator = _resolve_locator(page, by or "label", value)
        try:
            await locator.select_option(label=option)
        except Exception:
            await locator.select_option(value=option)
        return f"已选择 {option!r}"

    async def hover(by: str, value: str, name: Optional[str] = None) -> str:
        locator = _resolve_locator(page, by, value, name)
        await locator.hover()
        return f"已悬停 {by}={value!r}"

    async def press_key(key: str) -> str:
        await page.keyboard.press(key or "Enter")
        return f"已按键 {key!r}"

    async def scroll(delta_x: int = 0, delta_y: int = 0) -> str:
        dx = int(delta_x or 0)
        dy = int(delta_y or 0)
        await page.evaluate(f"window.scrollBy({dx}, {dy})")
        return f"已滚动 ({dx}, {dy})"

    async def wait(ms: int) -> str:
        ms = max(0, int(ms or 0))
        await page.wait_for_timeout(ms)
        return f"已等待 {ms}ms"

    async def observe() -> str:
        # 观察工具：返回较短文本快照，由调用方 parse 不再含图片
        obs = await observe_page(page, supports_vision, cap_chars=_OBSERVE_CAP)
        return obs.text

    async def screenshot(full_page: bool = False) -> str:
        if supports_vision:
            shot = await page.screenshot(full_page=bool(full_page), type="jpeg", quality=80)
            data_url = "data:image/jpeg;base64," + base64.b64encode(shot).decode()
            return data_url
        # 非视觉模型：保存文件并返回路径（不让 base64 进上下文成为 token 炸弹）
        path = os.path.join(screenshot_dir, f"ai_step_{step_id}_tool.png")
        real = await _save_screenshot(page, path)
        return real or "截图失败"

    async def get_url() -> str:
        return page.url

    async def get_title() -> str:
        return await page.title()

    async def assert_condition(type: str, expected: str) -> str:
        if type == "text_present":
            text = await page.evaluate("document.body ? (document.body.innerText || '') : ''")
            return "PASS" if expected in (text or "") else f"FAIL: 未找到文本 {expected!r}"
        if type == "text_absent":
            text = await page.evaluate("document.body ? (document.body.innerText || '') : ''")
            return "PASS" if expected not in (text or "") else f"FAIL: 仍存在文本 {expected!r}"
        if type == "url_contains":
            return "PASS" if expected in (page.url or "") else f"FAIL: 当前URL不含 {expected!r}"
        if type == "title_contains":
            title = await page.title()
            return "PASS" if expected in (title or "") else f"FAIL: 标题不含 {expected!r}"
        return f"ERROR: 未知断言类型 {type!r}"

    async def finish(success: bool, message: str) -> str:
        # 终止工具：返回 JSON，由 extract_finish_result 解析
        return json.dumps({"success": bool(success), "message": str(message)}, ensure_ascii=False)

    return [
        StructuredTool.from_function(navigate, name="navigate", coroutine=navigate,
            description="导航到指定 URL，等待页面加载。"),
        StructuredTool.from_function(click, name="click", coroutine=click,
            args_schema=ClickArgs,
            description="点击元素（通过可见文本/角色/标签定位）。先观察页面找到正确元素再点击。"),
        StructuredTool.from_function(fill, name="fill", coroutine=fill,
            args_schema=FillArgs,
            description="清空输入框并输入文本。用于文本输入框、文本域、contenteditable。"),
        StructuredTool.from_function(select_option, name="select_option", coroutine=select_option,
            args_schema=SelectOptionArgs,
            description="在 <select> 下拉框选择一个选项（按可见文本）。"),
        StructuredTool.from_function(hover, name="hover", coroutine=hover,
            args_schema=HoverArgs,
            description="悬停在元素上以触发悬停 UI（工具提示、下拉等）。"),
        StructuredTool.from_function(press_key, name="press_key", coroutine=press_key,
            args_schema=PressKeyArgs,
            description="按下键盘按键，如 Enter、Tab、Escape、ArrowDown 等。"),
        StructuredTool.from_function(scroll, name="scroll", coroutine=scroll,
            args_schema=ScrollArgs,
            description="滚动页面。正 delta_y 向下滚动。"),
        StructuredTool.from_function(wait, name="wait", coroutine=wait,
            args_schema=WaitArgs,
            description="等待若干毫秒。尽量少用，优先等待可见变化。"),
        StructuredTool.from_function(observe, name="observe", coroutine=observe,
            description="重新读取当前页面状态（文本快照）。执行动作后调用以查看变化。"),
        StructuredTool.from_function(screenshot, name="screenshot", coroutine=screenshot,
            args_schema=ScreenshotArgs,
            description="截取当前页面。视觉模型返回截图；非视觉模型保存为文件并返回路径。"),
        StructuredTool.from_function(get_url, name="get_url", coroutine=get_url,
            description="返回当前页面 URL。"),
        StructuredTool.from_function(get_title, name="get_title", coroutine=get_title,
            description="返回当前页面标题。"),
        StructuredTool.from_function(assert_condition, name="assert_condition", coroutine=assert_condition,
            args_schema=AssertConditionArgs,
            description="断言页面当前状态，返回 PASS 或 FAIL。"),
        StructuredTool.from_function(finish, name="finish", coroutine=finish,
            args_schema=FinishArgs, return_direct=True,
            description="终止工具：任务完成（成功或失败）时调用，报告结果并结束循环。"),
    ]


# 终止工具的可见名，用于从结果消息中识别 finish
FINISH_TOOL_NAME = "finish"


def extract_finish_result(messages) -> tuple[bool, str] | None:
    """从 agent 结果消息末尾向前找 finish 工具的 ToolMessage，返回 (success, message)。

    版本无关：无论 create_agent 是否尊重 return_direct，finish 的 ToolMessage 都会出现在结果里。
    """
    for msg in reversed(messages):
        name = getattr(msg, "name", None)
        if name != FINISH_TOOL_NAME:
            continue
        content = getattr(msg, "content", "")
        if isinstance(content, list):
            # 某些实现把内容拆成 blocks，拼接文本部分
            content = "".join(
                b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") in ("text", "input")
            )
        try:
            data = json.loads(content) if isinstance(content, str) else {}
            if isinstance(data, dict) and ("success" in data or "message" in data):
                return bool(data.get("success", False)), str(data.get("message", ""))
        except Exception:
            pass
        return False, str(content)[:500]
    return None