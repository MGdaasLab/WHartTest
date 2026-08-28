#!/usr/bin/env python
"""UI自动化登录态采集工具。

在浏览器中打开目标系统登录页，人工完成登录（可包含验证码），
登录成功后保存 Playwright storageState 快照（cookies + localStorage），
供执行任务时通过 auth.storage_state 复用。

一套快照同时兼容两类认证系统，无需关心目标系统类型：
- Cookie/Session 会话系统：快照中的 cookies 恢复会话
- JWT / token 现代系统：快照中的 localStorage 恢复前端 token（路由守卫/请求拦截器）

用法：
    python login_state_capture.py --url https://your-system.com/login --output data/auth.json

检测成功后自动保存；登录后 URL 不含登录关键字时也会检测（--login-pattern）。
验证码/多步登录无法自动判断完成时机时，可改用 --wait-enter 手动按回车保存。
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright

logger = logging.getLogger("login_state_capture")

DEFAULT_LOGIN_PATTERN = r"login|signin|sign_in|auth|sso|passport"


async def _run(
    url: str,
    output: str,
    *,
    browser_type: str = "chromium",
    headless: bool = False,
    login_pattern: str = DEFAULT_LOGIN_PATTERN,
    success_selector: str = "",
    timeout: float = 600.0,
    wait_enter: bool = False,
) -> None:
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    pattern_re = re.compile(login_pattern, re.IGNORECASE)

    playwright = await async_playwright().start()
    try:
        launcher = getattr(playwright, browser_type)
        browser = await launcher.launch(headless=headless)
        try:
            context = await browser.new_context()
            page = await context.new_page()

            print(f"正在打开登录页: {url}")
            print(f"请在弹出的浏览器窗口中完成登录（含验证码）...")
            if wait_enter:
                print("登录完成后，回到本终端按回车保存登录态（Ctrl+C 取消）")
            else:
                print(f"登录成功后自动保存（检测: URL 不再匹配 {login_pattern!r}" +
                      (f" 或出现元素 {success_selector!r}" if success_selector else "") + ")")

            await page.goto(url, wait_until="load")

            if wait_enter:
                try:
                    await asyncio.to_thread(input, "> 登录完成后按回车保存: ")
                except (EOFError, KeyboardInterrupt):
                    raise SystemExit("已取消")
            else:
                deadline = asyncio.get_event_loop().time() + timeout
                while True:
                    current_url = page.url
                    logged_in = not pattern_re.search(current_url)
                    if success_selector:
                        try:
                            logged_in = logged_in and await page.locator(success_selector).count() > 0
                        except Exception:
                            logged_in = False
                    if logged_in:
                        print(f"检测到登录成功，当前 URL: {current_url}")
                        break
                    if asyncio.get_event_loop().time() > deadline:
                        raise SystemExit(
                            f"等待登录超时（{timeout:.0f}s），当前 URL 仍匹配登录页: {current_url}"
                        )
                    await asyncio.sleep(1)

            state = await context.storage_state()
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)

            cookies = len(state.get("cookies") or [])
            origins = state.get("origins") or []
            ls_total = sum(len(o.get("localStorage") or []) for o in origins)
            print(
                f"登录态已保存: {out_path} "
                f"(cookies={cookies}, localStorage origins={len(origins)}, keys={ls_total})"
            )
        finally:
            await browser.close()
    finally:
        await playwright.stop()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="login_state_capture",
        description="采集目标系统登录态（storageState 快照），供 UI 自动化任务复用",
    )
    parser.add_argument("--url", required=True, help="目标系统登录页 URL")
    parser.add_argument("--output", default="data/auth.json", help="快照保存路径（默认 data/auth.json）")
    parser.add_argument("--browser", default="chromium", choices=["chromium", "firefox", "webkit"])
    parser.add_argument("--headless", action="store_true", help="无头模式（无法人工过验证码，一般不用）")
    parser.add_argument("--login-pattern", default=DEFAULT_LOGIN_PATTERN,
                        help="登录页 URL 匹配正则（小写匹配），用于自动判定登录完成")
    parser.add_argument("--success-selector", default="",
                        help="登录成功后必然出现的选择器，与 URL 判定互为补充")
    parser.add_argument("--timeout", type=float, default=600.0, help="等待登录超时秒数（默认 600）")
    parser.add_argument("--wait-enter", action="store_true",
                        help="不自动判定，登录完成后按回车保存（验证码/多步登录场景）")
    args = parser.parse_args(argv)

    try:
        asyncio.run(_run(
            args.url,
            args.output,
            browser_type=args.browser,
            headless=args.headless,
            login_pattern=args.login_pattern,
            success_selector=args.success_selector,
            timeout=args.timeout,
            wait_enter=args.wait_enter,
        ))
        return 0
    except SystemExit as e:
        if e.code:
            print(e.code if isinstance(e.code, str) else f"退出码 {e.code}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"采集失败: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())