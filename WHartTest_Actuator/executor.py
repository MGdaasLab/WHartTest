"""
UI自动化执行器 - Python Playwright执行引擎
使用Python原生Playwright库执行测试，无需Node.js依赖
"""

import asyncio
import gc
import importlib
import json
import logging
import os
import time
import traceback
from pathlib import Path
from typing import Any, Optional, Union
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright, expect, FrameLocator

from models import StepResultModel, CaseResultModel
from runtime_env import is_running_in_container
import client_cert

logger = logging.getLogger('actuator')

DEFAULT_STEALTH_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

STEALTH_INIT_SCRIPT = """
try {
    Object.defineProperty(navigator, 'webdriver', { get: () => false });
} catch (_) {}

for (const key of [
    'cdc_adoQpoasnfa76pfcZLmcfl_Symbol',
    'cdc_adoQpoasnfa76pfcZLmcfl_Promise',
    'cdc_adoQpoasnfa76pfcZLmcfl_Array',
]) {
    try {
        delete window[key];
    } catch (_) {}
}
"""


class LoginStateError(RuntimeError):
    """登录态失效或未正确注入（页面被重定向到登录页）。"""


# 任务级认证配置（auth）字典结构：
#   storage_state: 登录态快照。Playwright storageState 格式：文件路径(str) 或
#                  {"cookies": [...], "origins": [...]} JSON。同时覆盖两类系统：
#                  JWT 系（token 在 localStorage）与 Cookie/Session 系（会话 cookie）。
#   headers:       可选。注入到上下文所有请求的请求头，如 {"Authorization": "Bearer xxx"}。
#   local_storage: 可选。页面加载前写入 localStorage 的键值（用于 SPA 前端路由守卫校验）。
#   login_check:   可选。登录失效检测：{"url_pattern": "login|signin", "selector": "#login-form"}。
#                  页面导航后若命中被判定为登录页，抛出 LoginStateError 并给出明确提示。
AUTH_CONFIG_KEYS = ("storage_state", "headers", "local_storage", "login_check")


@dataclass
class StepConfig:
    """步骤配置"""
    step_id: int
    operation_type: str      # click, fill, goto, wait, assert等
    locator_type: str        # xpath, css, id等
    locator_value: str
    step_type: int = 0       # 0元素操作, 1断言操作, 2 SQL操作
    input_value: str = ''
    description: str = ''
    wait_time: float = 0
    is_iframe: bool = False
    iframe_locator: str = ''
    locator_index: Optional[int] = None
    locator_type_2: Optional[str] = None
    locator_value_2: Optional[str] = None
    locator_index_2: Optional[int] = None
    locator_type_3: Optional[str] = None
    locator_value_3: Optional[str] = None
    locator_index_3: Optional[int] = None
    sql_execute: Any = None
    # Remote upload metadata used when shared storage path is unavailable
    upload_file_id: Optional[int] = None
    upload_file_name: Optional[str] = None
    upload_download_url: Optional[str] = None
    upload_project_id: Optional[int] = None
    upload_file_sha: Optional[str] = None
    upload_file_size: Optional[int] = None
    ope_value: Any = None
    
    # step details (shared steps)
    details: list['StepConfig'] = field(default_factory=list)


@dataclass 
class PageStepConfig:
    """页面步骤配置"""
    page_step_id: int
    page_url: str
    page_name: str
    steps: list[StepConfig] = field(default_factory=list)
    env_config: Optional[dict] = None
    # 步骤绑定的登录态：auth_state_id 来自平台，auth 为解析后的 storage_state（执行时按组切换）
    auth_state_id: Optional[int] = None
    auth: Optional[dict] = None


@dataclass
class TestCaseConfig:
    """测试用例配置"""
    case_id: int
    case_name: str
    page_steps: list[PageStepConfig] = field(default_factory=list)
    env_config: Optional[dict] = None


class PlaywrightExecutor:
    """Python原生Playwright执行器"""
    
    def __init__(
        self, 
        browser_type: str = 'chromium',
        headless: bool = False,
        persistent: bool = True,
        user_data_dir: str = './data/browser',
        launch_timeout: int = 30000,
        action_timeout: int = 30000,
        screenshot_dir: str = './data/screenshots',
        retry_count: int = 3,
        step_interval: int = 500,
        fail_fast: bool = False,
        viewport_width: int = 1280,
        viewport_height: int = 720,
        trace_enabled: bool = False,
        trace_dir: str = './data/traces',
        trace_screenshots: bool = True,
        trace_snapshots: bool = True,
        trace_sources: bool = False,
        stealth_enabled: bool = True,
        stealth_user_agent: Optional[str] = None,
        client_cert_enabled: bool = False,
        client_cert_pfx_path: Optional[str] = None,
        client_cert_passphrase: Optional[str] = None,
        client_cert_cert_path: Optional[str] = None,
        client_cert_key_path: Optional[str] = None,
        client_cert_origins: Optional[str] = None,
        client_cert_config_dir: Optional[str] = None,
        ignore_https_errors: Optional[bool] = None,
    ):
        self.browser_type = browser_type
        self.headless = headless
        self.persistent = persistent
        self.user_data_dir = user_data_dir
        self.launch_timeout = launch_timeout
        self.action_timeout = action_timeout
        self.screenshot_dir = screenshot_dir
        self.retry_count = retry_count
        self.step_interval = step_interval
        # 失败中断：元素定位失败（主/备用表达式+操作超时均结束仍失败）时
        # 立即中断用例并上报，跳过步骤级重试与后续步骤
        self.fail_fast = fail_fast
        # 节点默认视口（任务级 runtime 未指定视口时使用，由执行器配置维护）
        self.default_viewport: dict = {"width": viewport_width, "height": viewport_height}
        
        # Trace 配置
        self.trace_enabled = trace_enabled
        self.trace_dir = trace_dir
        self.trace_screenshots = trace_screenshots
        self.trace_snapshots = trace_snapshots
        self.trace_sources = trace_sources
        self.stealth_enabled = stealth_enabled
        self.stealth_user_agent = stealth_user_agent

        # HTTPS 客户端证书（节点级配置，详见 client_cert.py）
        # ignore_https_errors 三态：None=auto / True / False
        self.ignore_https_errors: Optional[bool] = ignore_https_errors
        self._client_cert_enabled = bool(client_cert_enabled)
        self._client_cert_pfx_path = client_cert_pfx_path or None
        self._client_cert_passphrase = client_cert_passphrase or None
        self._client_cert_cert_path = client_cert_cert_path or None
        self._client_cert_key_path = client_cert_key_path or None
        self._client_cert_origins = client_cert_origins or None
        # 相对证书路径的基准目录（通常为 config.toml 所在目录）
        self._client_cert_config_dir: Optional[Path] = (
            Path(client_cert_config_dir) if client_cert_config_dir else None
        )
        # 本次任务推导出的 origin（由 set_task_origins 覆盖写入）
        self._task_cert_origins: list[str] = []
        # 依赖缺失类告警只提示一次，避免刷日志
        self._cert_warned: set[str] = set()
        # 解析后的证书文件绝对路径（惰性计算）
        self._client_cert_resolved: Optional[dict] = None
        # 已打印过 info 的证书指纹，避免每次建上下文都刷日志
        self._client_cert_logged: Optional[tuple] = None
        
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._stop_requested = False
        self._current_trace_path: Optional[str] = None
        self._page_errors = []

        # AI Agent 配置（用于 step_type=10「AI操作」），由 consumer 注入
        self.model_config = None
        # AI 单步骤总超时（秒），独立于 Playwright action_timeout
        self.ai_action_timeout = 300
        # 任务级认证配置（auth），通过 apply_runtime_options 注入，执行后随 restore 还原
        self._auth_config: Optional[dict] = None
        self._auth_context_key: Optional[str] = None  # 当前 context 对应 auth 签名（组间切换判断）
        # 执行画面帧采集钩子：browser_session 上下文进入后回调 page（consumer 侧挂 FrameStreamer）
        self.on_execution_page = None
        
        Path(self.user_data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.screenshot_dir).mkdir(parents=True, exist_ok=True)
        if self.trace_enabled:
            Path(self.trace_dir).mkdir(parents=True, exist_ok=True)

    def apply_runtime_options(self, runtime: dict | None) -> dict:
        """Apply per-task effective runtime without permanently mutating node defaults.

        Returns the previous browser-related state for restore.
        """
        previous = {
            "browser_type": self.browser_type,
            "headless": self.headless,
            "action_timeout": self.action_timeout,
            "persistent": self.persistent,
            "user_data_dir": self.user_data_dir,
            "_runtime_viewport": getattr(self, "_runtime_viewport", None),
            "_viewport_explicit": getattr(self, "_viewport_explicit", False),
            "_auth_config": getattr(self, "_auth_config", None),
        }
        if not runtime:
            return previous

        browser = runtime.get("browser") or runtime.get("browser_type")
        if browser:
            browser = str(browser).strip().lower()
            if browser != self.browser_type:
                # Switching browser cannot safely reuse persistent profile.
                self.persistent = False
            self.browser_type = browser

        if runtime.get("headless") is not None:
            self.headless = bool(runtime["headless"])

        timeout = runtime.get("timeout")
        if timeout is not None:
            try:
                self.action_timeout = int(timeout)
            except (TypeError, ValueError):
                pass

        explicit = bool(runtime.get("viewport_explicit"))
        vw = runtime.get("viewport_width")
        vh = runtime.get("viewport_height")
        if explicit and vw and vh:
            self._runtime_viewport = {"width": int(vw), "height": int(vh)}
            self._viewport_explicit = True
        elif vw and vh and not self.stealth_enabled:
            self._runtime_viewport = {"width": int(vw), "height": int(vh)}
            self._viewport_explicit = True
        else:
            # Keep stealth default viewport=None unless explicitly requested.
            self._runtime_viewport = None
            self._viewport_explicit = explicit

        auth = runtime.get("auth")
        if auth is not None:
            # 任务级认证配置原样透传；None 表示无（恢复任务前状态由 restore 负责）
            self._auth_config = auth if isinstance(auth, dict) else None

        return previous

    def restore_runtime_options(self, previous: dict | None) -> None:
        if not previous:
            return
        self.browser_type = previous.get("browser_type", self.browser_type)
        self.headless = previous.get("headless", self.headless)
        self.action_timeout = previous.get("action_timeout", self.action_timeout)
        self.persistent = previous.get("persistent", self.persistent)
        self.user_data_dir = previous.get("user_data_dir", self.user_data_dir)
        self._runtime_viewport = previous.get("_runtime_viewport")
        self._viewport_explicit = previous.get("_viewport_explicit", False)
        self._auth_config = previous.get("_auth_config")

    # ------------------------------------------------------------------
    # HTTPS 客户端证书
    #
    # Playwright 的 client_certificates 要求 origin 精确匹配
    # （https://host[:port]，不支持通配），因此这里分两步：
    #   1. 任务开始时用 set_task_origins() 固定本次任务的 origin 集合
    #   2. 建上下文时 _build_client_certificates() 把它和证书材料组装成 Playwright 参数
    # 详细约束见 client_cert.py 顶部说明。
    # ------------------------------------------------------------------

    def configure_client_cert(
        self,
        *,
        enabled: Optional[bool] = None,
        pfx_path: Optional[str] = None,
        passphrase: Optional[str] = None,
        cert_path: Optional[str] = None,
        key_path: Optional[str] = None,
        origins: Optional[str] = None,
        config_dir: Optional[str] = None,
    ) -> None:
        """配置或热更新客户端证书。

        仅更新显式传入（非 None）的字段，因此可安全地用于「平台只下发部分字段」的场景。
        ``passphrase`` 属敏感信息，只保存在内存中，不写入日志。
        """
        if enabled is not None:
            self._client_cert_enabled = bool(enabled)
        if pfx_path is not None:
            self._client_cert_pfx_path = pfx_path or None
        if passphrase is not None:
            self._client_cert_passphrase = passphrase or None
        if cert_path is not None:
            self._client_cert_cert_path = cert_path or None
        if key_path is not None:
            self._client_cert_key_path = key_path or None
        if origins is not None:
            self._client_cert_origins = origins or None
        if config_dir is not None:
            self._client_cert_config_dir = Path(config_dir) if config_dir else None

        # 证书材料可能有变化，作废缓存与告警去重记录，让下一次建上下文重新评估
        self._client_cert_resolved = None
        self._cert_warned = set()

    def _task_origins(self, *configs) -> list[str]:
        """从任务配置推导出需要匹配的 https origin 集合。

        来源：``env_config['base_url']``、``page_url``（用例级与页面步骤级），
        再追加配置里的额外 origin 列表（``client_cert_origins``）。
        非 https 与无法解析的项会被丢弃 —— Playwright 不支持通配，只能精确匹配。
        """
        candidates: list[str] = []

        for config in configs:
            if config is None:
                continue
            if isinstance(config, str):
                candidates.append(config)
                continue

            env_config = getattr(config, 'env_config', None)
            if isinstance(env_config, dict):
                for key in ('base_url', 'page_url'):
                    value = env_config.get(key)
                    if value:
                        candidates.append(str(value))

            page_url = getattr(config, 'page_url', None)
            if page_url:
                candidates.append(str(page_url))

            for page_step in getattr(config, 'page_steps', None) or []:
                step_env = getattr(page_step, 'env_config', None)
                if isinstance(step_env, dict):
                    for key in ('base_url', 'page_url'):
                        value = step_env.get(key)
                        if value:
                            candidates.append(str(value))
                step_url = getattr(page_step, 'page_url', None)
                if step_url:
                    candidates.append(str(step_url))

        origins = client_cert.parse_origins(*candidates)
        for extra in client_cert.parse_origins(self._client_cert_origins):
            if extra not in origins:
                origins.append(extra)

        return origins

    def set_task_origins(self, origins) -> None:
        """覆盖式设置本次任务的 origin 集合。

        覆盖而非合并是刻意的：每个执行入口都会在开头调用本方法，因此不存在
        「上一个任务的 origin 污染下一个任务」的可能，异常返回路径也无需额外清理。
        """
        if not origins:
            self._task_cert_origins = []
            return
        if isinstance(origins, str):
            origins = [origins]
        self._task_cert_origins = client_cert.parse_origins(
            *[str(item) for item in origins if item]
        )

    def _resolved_cert_files(self) -> dict:
        """解析证书文件绝对路径（结果缓存，configure_client_cert 时作废）。"""
        if self._client_cert_resolved is not None:
            return self._client_cert_resolved

        base_dir = self._client_cert_config_dir
        self._client_cert_resolved = {
            'pfx': client_cert.resolve_cert_path(self._client_cert_pfx_path, base_dir),
            'cert': client_cert.resolve_cert_path(self._client_cert_cert_path, base_dir),
            'key': client_cert.resolve_cert_path(self._client_cert_key_path, base_dir),
        }
        return self._client_cert_resolved

    def _warn_cert_once(self, key: str, message: str) -> None:
        """同一类证书告警只输出一次，避免每个上下文都刷屏。"""
        if key in self._cert_warned:
            return
        self._cert_warned.add(key)
        logger.warning(message)

    def _build_client_certificates(self) -> list[dict]:
        """构造 Playwright ``client_certificates`` 参数；不满足条件时返回 ``[]``。

        注意：日志只输出指纹（证书路径 + origin），**绝不输出 passphrase**。
        """
        if not self._client_cert_enabled:
            return []

        resolved = self._resolved_cert_files()
        pfx = resolved.get('pfx')
        cert = resolved.get('cert')
        key = resolved.get('key')

        if pfx is None and (cert is None or key is None):
            self._warn_cert_once(
                'no-material',
                "客户端证书已启用但未配置完整的证书文件"
                "（需 client_cert_pfx_path，或 client_cert_cert_path + client_cert_key_path），"
                "本次执行不启用客户端证书",
            )
            return []

        for warning in client_cert.validate_cert_files(pfx_path=pfx, cert_path=cert, key_path=key):
            self._warn_cert_once(f'file:{warning}', f"客户端证书配置告警：{warning}")

        origins = self._task_cert_origins or client_cert.parse_origins(self._client_cert_origins)
        if not origins:
            self._warn_cert_once(
                'no-origin',
                "客户端证书已启用但未能推导出 https origin（任务的 base_url / page_url 均非 https，"
                "且未配置 client_cert_origins）；Playwright 要求 origin 精确匹配且不支持通配，"
                "本次执行不启用客户端证书",
            )
            return []

        fingerprint = (str(pfx), str(cert), str(key), tuple(origins))
        if fingerprint != self._client_cert_logged:
            self._client_cert_logged = fingerprint
            logger.info(
                "HTTPS 客户端证书已启用，生效 origin：%s（证书文件：%s）",
                client_cert.summarize_origins(origins),
                pfx or cert,
            )

        return client_cert.build_client_certificates(
            origins,
            pfx_path=pfx,
            passphrase=self._client_cert_passphrase,
            cert_path=cert,
            key_path=key,
        )

    # ------------------------------------------------------------------
    # HTTPS 客户端证书
    #
    # Playwright 的 client_certificates 要求 origin 精确匹配
    # （https://host[:port]，不支持通配），因此这里分两步：
    #   1. 任务开始时用 set_task_origins() 固定本次任务的 origin 集合
    #   2. 建上下文时 _build_client_certificates() 把它和证书材料组装成 Playwright 参数
    # 详细约束见 client_cert.py 顶部说明。
    # ------------------------------------------------------------------

    def configure_client_cert(
        self,
        *,
        enabled: Optional[bool] = None,
        pfx_path: Optional[str] = None,
        passphrase: Optional[str] = None,
        cert_path: Optional[str] = None,
        key_path: Optional[str] = None,
        origins: Optional[str] = None,
        config_dir: Optional[str] = None,
    ) -> None:
        """配置或热更新客户端证书。

        仅更新显式传入（非 None）的字段，因此可安全地用于「平台只下发部分字段」的场景。
        ``passphrase`` 属敏感信息，只保存在内存中，不写入日志。
        """
        if enabled is not None:
            self._client_cert_enabled = bool(enabled)
        if pfx_path is not None:
            self._client_cert_pfx_path = pfx_path or None
        if passphrase is not None:
            self._client_cert_passphrase = passphrase or None
        if cert_path is not None:
            self._client_cert_cert_path = cert_path or None
        if key_path is not None:
            self._client_cert_key_path = key_path or None
        if origins is not None:
            self._client_cert_origins = origins or None
        if config_dir is not None:
            self._client_cert_config_dir = Path(config_dir) if config_dir else None

        # 证书材料可能有变化，作废缓存与告警去重记录，让下一次建上下文重新评估
        self._client_cert_resolved = None
        self._cert_warned = set()

    def _task_origins(self, *configs) -> list[str]:
        """从任务配置推导出需要匹配的 https origin 集合。

        来源：``env_config['base_url']``、``page_url``（用例级与页面步骤级），
        再追加配置里的额外 origin 列表（``client_cert_origins``）。
        非 https 与无法解析的项会被丢弃 —— Playwright 不支持通配，只能精确匹配。
        """
        candidates: list[str] = []

        for config in configs:
            if config is None:
                continue
            if isinstance(config, str):
                candidates.append(config)
                continue

            env_config = getattr(config, 'env_config', None)
            if isinstance(env_config, dict):
                for key in ('base_url', 'page_url'):
                    value = env_config.get(key)
                    if value:
                        candidates.append(str(value))

            page_url = getattr(config, 'page_url', None)
            if page_url:
                candidates.append(str(page_url))

            for page_step in getattr(config, 'page_steps', None) or []:
                step_env = getattr(page_step, 'env_config', None)
                if isinstance(step_env, dict):
                    for key in ('base_url', 'page_url'):
                        value = step_env.get(key)
                        if value:
                            candidates.append(str(value))
                step_url = getattr(page_step, 'page_url', None)
                if step_url:
                    candidates.append(str(step_url))

        origins = client_cert.parse_origins(*candidates)
        for extra in client_cert.parse_origins(self._client_cert_origins):
            if extra not in origins:
                origins.append(extra)

        return origins

    def set_task_origins(self, origins) -> None:
        """覆盖式设置本次任务的 origin 集合。

        覆盖而非合并是刻意的：每个执行入口都会在开头调用本方法，因此不存在
        「上一个任务的 origin 污染下一个任务」的可能，异常返回路径也无需额外清理。
        """
        if not origins:
            self._task_cert_origins = []
            return
        if isinstance(origins, str):
            origins = [origins]
        self._task_cert_origins = client_cert.parse_origins(
            *[str(item) for item in origins if item]
        )

    def _resolved_cert_files(self) -> dict:
        """解析证书文件绝对路径（结果缓存，configure_client_cert 时作废）。"""
        if self._client_cert_resolved is not None:
            return self._client_cert_resolved

        base_dir = self._client_cert_config_dir
        self._client_cert_resolved = {
            'pfx': client_cert.resolve_cert_path(self._client_cert_pfx_path, base_dir),
            'cert': client_cert.resolve_cert_path(self._client_cert_cert_path, base_dir),
            'key': client_cert.resolve_cert_path(self._client_cert_key_path, base_dir),
        }
        return self._client_cert_resolved

    def _warn_cert_once(self, key: str, message: str) -> None:
        """同一类证书告警只输出一次，避免每个上下文都刷屏。"""
        if key in self._cert_warned:
            return
        self._cert_warned.add(key)
        logger.warning(message)

    def _build_client_certificates(self) -> list[dict]:
        """构造 Playwright ``client_certificates`` 参数；不满足条件时返回 ``[]``。

        注意：日志只输出指纹（证书路径 + origin），**绝不输出 passphrase**。
        """
        if not self._client_cert_enabled:
            return []

        resolved = self._resolved_cert_files()
        pfx = resolved.get('pfx')
        cert = resolved.get('cert')
        key = resolved.get('key')

        if pfx is None and (cert is None or key is None):
            self._warn_cert_once(
                'no-material',
                "客户端证书已启用但未配置完整的证书文件"
                "（需 client_cert_pfx_path，或 client_cert_cert_path + client_cert_key_path），"
                "本次执行不启用客户端证书",
            )
            return []

        for warning in client_cert.validate_cert_files(pfx_path=pfx, cert_path=cert, key_path=key):
            self._warn_cert_once(f'file:{warning}', f"客户端证书配置告警：{warning}")

        origins = self._task_cert_origins or client_cert.parse_origins(self._client_cert_origins)
        if not origins:
            self._warn_cert_once(
                'no-origin',
                "客户端证书已启用但未能推导出 https origin（任务的 base_url / page_url 均非 https，"
                "且未配置 client_cert_origins）；Playwright 要求 origin 精确匹配且不支持通配，"
                "本次执行不启用客户端证书",
            )
            return []

        fingerprint = (str(pfx), str(cert), str(key), tuple(origins))
        if fingerprint != self._client_cert_logged:
            self._client_cert_logged = fingerprint
            logger.info(
                "HTTPS 客户端证书已启用，生效 origin：%s（证书文件：%s）",
                client_cert.summarize_origins(origins),
                pfx or cert,
            )

        return client_cert.build_client_certificates(
            origins,
            pfx_path=pfx,
            passphrase=self._client_cert_passphrase,
            cert_path=cert,
            key_path=key,
        )


    def _build_browser_launch_options(self) -> dict:
        """构建浏览器启动参数。

        浏览器一律无头启动：执行画面统一经画布帧流直播（前端 ExecutionScreenModal），
        不打开本地浏览器窗口（docker 无显示；桌面端同样不弹窗）。
        self.headless 仅作为"观看模式"开关控制帧推流（consumer），不再决定启动形态。
        """
        launch_options = {
            'headless': True,
            'timeout': self.launch_timeout,
        }

        launch_args: list[str] = []
        if self.stealth_enabled and self.browser_type == 'chromium':
            launch_args.extend([
                '--disable-blink-features=AutomationControlled',
                '--start-maximized',
            ])

        if is_running_in_container() and self.browser_type == 'chromium':
            launch_args.append('--disable-dev-shm-usage')
            if hasattr(os, 'geteuid') and os.geteuid() == 0:
                launch_args.append('--no-sandbox')

        if launch_args:
            launch_options['args'] = list(dict.fromkeys(launch_args))

        return launch_options

    def _build_browser_context_options(self) -> dict:
        """构建浏览器上下文参数。"""
        context_options: dict = {}

        auth = getattr(self, "_auth_config", None) or {}
        if auth.get("storage_state"):
            # 登录态快照：文件路径(str) 或 storageState JSON(dict)。
            # Playwright new_context 原生支持，Cookie/Session 与 JWT(localStorage) 一并恢复。
            context_options["storage_state"] = auth["storage_state"]
        if auth.get("headers"):
            # 注入到上下文全部请求（含页面导航）的请求头，JWT Bearer 双保险
            context_options["extra_http_headers"] = auth["headers"]

        runtime_viewport = getattr(self, "_runtime_viewport", None)
        viewport_explicit = getattr(self, "_viewport_explicit", False)

        # 任务级未指定视口时，回退到执行器节点默认视口（由平台编辑窗口维护），
        # 默认 1280x720 与 Playwright 默认一致，不改变现有行为
        if runtime_viewport is None:
            runtime_viewport = dict(getattr(self, "default_viewport", None) or {}) or None
            if runtime_viewport:
                viewport_explicit = True

        # HTTPS 客户端证书与 ignore_https_errors 必须在 stealth 早退分支之前计算，
        # 否则 stealth 关闭时既拿不到证书，也失去「容忍自签名服务端证书」的能力
        # （而自签名恰恰是客户端证书最常见的搭配场景）。
        client_certs = self._build_client_certificates()
        if client_certs:
            context_options["client_certificates"] = client_certs

        # ignore_https_errors 三态：None = auto（跟随 stealth 与证书），True/False = 强制覆盖。
        # auto 语义刻意与历史行为保持一致，避免对既有 stealth-off 部署造成安全回归：
        #   stealth 开            -> True（与改动前完全一致）
        #   stealth 关 + 无证书   -> 不设置（与改动前完全一致）
        #   stealth 关 + 有证书   -> True（新增，客户端证书场景需要）
        configured_ignore = getattr(self, "ignore_https_errors", None)
        if configured_ignore is None:
            ignore_https_errors = bool(self.stealth_enabled) or bool(client_certs)
        else:
            ignore_https_errors = bool(configured_ignore)
        if ignore_https_errors:
            context_options["ignore_https_errors"] = True

        if not self.stealth_enabled:
            if runtime_viewport:
                context_options["viewport"] = runtime_viewport
            return context_options

        if self.browser_type == "chromium":
            if viewport_explicit and runtime_viewport:
                context_options["viewport"] = runtime_viewport
            else:
                context_options["viewport"] = None
            context_options["user_agent"] = (
                self.stealth_user_agent or DEFAULT_STEALTH_USER_AGENT
            )
        else:
            if viewport_explicit and runtime_viewport:
                context_options["viewport"] = runtime_viewport
            if self.stealth_user_agent:
                context_options["user_agent"] = self.stealth_user_agent

        return context_options

    @staticmethod
    def _build_local_storage_init_script(entries: dict) -> str:
        """生成页面加载前写入 localStorage 的初始化脚本（SPA 路由守卫/请求拦截器读取用）。"""
        try:
            payload = json.dumps(entries, ensure_ascii=False)
        except (TypeError, ValueError):
            payload = json.dumps({})
        return (
            "(() => {"
            "try { const d = " + payload + ";"
            "for (const k in d) { localStorage.setItem(k, d[k]); }"
            "} catch (_) {}"
            "})();"
        )

    @staticmethod
    def _build_origin_local_storage_init_script(origin: str, entries: dict) -> str:
        """生成按 origin 匹配的 localStorage 初始化脚本（storageState origins 恢复用）。"""
        try:
            payload = json.dumps(entries, ensure_ascii=False)
            target = json.dumps(origin)
        except (TypeError, ValueError):
            return ""
        return (
            "(() => {"
            "try { if (location.origin === " + target + ") { const d = " + payload + ";"
            "for (const k in d) { localStorage.setItem(k, d[k]); }"
            "} } catch (_) {}"
            "})();"
        )

    async def _apply_storage_state(self, context: BrowserContext, state: Any) -> None:
        """手动应用登录态快照（持久化上下文不支持 storage_state 参数，需手动注入）。

        cookies 用 add_cookies 注入；localStorage 用按 origin 匹配的初始化脚本写入，
        与浏览器原生 storage_state 复用的行为一致，覆盖 Cookie/Session 与 JWT 两类系统。
        """
        if isinstance(state, (str, os.PathLike)):
            try:
                with open(os.fspath(state), 'r', encoding='utf-8') as f:
                    state = json.load(f)
            except Exception as e:
                raise ValueError(f"读取登录态文件失败: {os.fspath(state)} ({e})") from e
        if not isinstance(state, dict):
            raise ValueError("登录态 storage_state 必须是文件路径或 storageState JSON 对象")

        cookies = state.get("cookies") or []
        if cookies:
            await context.add_cookies(cookies)

        origins = state.get("origins") or []
        for origin in origins:
            ls = origin.get("localStorage") or []
            if not ls:
                continue
            entries = {item.get("name"): item.get("value") for item in ls if item.get("name") is not None}
            if entries:
                script = self._build_origin_local_storage_init_script(origin.get("origin", ""), entries)
                if script:
                    await context.add_init_script(script)

    async def _apply_context_init_scripts(self, context: BrowserContext) -> None:
        """注入上下文初始化脚本。"""
        if self.stealth_enabled:
            await context.add_init_script(STEALTH_INIT_SCRIPT)

        auth = getattr(self, "_auth_config", None) or {}
        local_storage = auth.get("local_storage")
        if isinstance(local_storage, dict) and local_storage:
            # 手动配置的 localStorage 键值：在任意页面加载前写入（通常为同源应用）
            await context.add_init_script(self._build_local_storage_init_script(local_storage))
    
    def _auth_login_check(self) -> Optional[dict]:
        """当前任务配置的登录失效检测参数（未配置返回 None）。"""
        auth = getattr(self, "_auth_config", None) or {}
        check = auth.get("login_check")
        return check if isinstance(check, dict) else None

    async def _assert_logged_in(self, page: Page) -> None:
        """导航后检测是否被重定向到登录页（登录态失效/未注入时给出明确提示）。

        未配置 login_check 时不进行任何检测，不影响现有行为。
        """
        check = self._auth_login_check()
        if not check:
            return

        url_pattern = str(check.get("url_pattern") or "").strip()
        selector = str(check.get("selector") or "").strip()

        current_url = page.url
        if url_pattern and url_pattern.lower() in current_url.lower():
            raise LoginStateError(
                f"登录态失效或未正确注入：导航后检测到登录页（URL 包含 '{url_pattern}'，当前: {current_url}）。"
                "请重新录制登录并保存登录态，或更新认证配置（storage_state/token 注入）后重试"
            )

        if selector:
            try:
                if await page.locator(selector).count() > 0:
                    raise LoginStateError(
                        f"登录态失效或未正确注入：导航后在页面中检测到登录页元素（{selector}，当前: {current_url}）。"
                        "请重新录制登录并保存登录态，或更新认证配置后重试"
                    )
            except LoginStateError:
                raise
            except Exception:
                # 定位器本身异常（如无权限）不作为登录失效判定
                pass

    async def _goto_with_login_check(self, page: Page, url: str, **kwargs) -> None:
        """导航并执行登录失效检测（等价于 page.goto + _assert_logged_in）。

        ERR_ABORTED/导航被中断：站点自身跳转（302/前端 location）仍在途中时
        插入的 goto 会被 Chromium 中止，等待其稳定后重试一次。
        """
        try:
            await page.goto(url, **kwargs)
        except Exception as e:
            msg = str(e)
            if 'ERR_ABORTED' not in msg and 'Interrupted' not in msg:
                raise
            logger.warning(f'导航被页面跳转中止（{url}），等待稳定后重试')
            try:
                await page.wait_for_load_state('domcontentloaded', timeout=8000)
            except Exception:
                pass
            await page.goto(url, **kwargs)
        await self._assert_logged_in(page)

    async def ensure_auth_context(self, auth: Optional[dict]) -> bool:
        """按组切换登录态注入：auth 与当前 context 一致则直接复用（不清理，
        覆盖"同登录态无需逐步清理"的场景）；不同则关闭旧 context、以新 auth
        重建（保留 browser 复用）。返回是否发生重建。"""
        key = json.dumps(auth or {}, sort_keys=True)
        if key == self._auth_context_key and self._context is not None:
            return False
        if self._context is not None:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None
            self._page = None
        self._auth_config = auth
        await self._init_browser_context()
        self._auth_context_key = key
        # 重建出的新页面须重新挂执行画面帧流：CDP screencast 会话随旧 context
        # 关闭而失效，不重挂会导致画布停留在重建前的最后一帧
        if self.on_execution_page is not None:
            try:
                await self.on_execution_page(self._page)
            except Exception as exc:
                logger.warning(f'执行画面帧流重挂失败（不影响用例执行）: {exc}')
        return True

    async def _init_browser_context(self) -> None:
        """按当前 _auth_config 创建 context/page（init_browser 与 ensure_auth_context 共用）。"""
        browser_launcher = getattr(self._playwright, self.browser_type)
        launch_options = self._build_browser_launch_options()
        context_options = self._build_browser_context_options()
        if self.persistent:
            ctx_options = dict(context_options)
            storage_state = ctx_options.pop("storage_state", None)
            self._context = await browser_launcher.launch_persistent_context(
                self.user_data_dir, **launch_options, **ctx_options,
            )
            if storage_state is not None:
                await self._apply_storage_state(self._context, storage_state)
            await self._apply_context_init_scripts(self._context)
            pages = self._context.pages
            self._page = pages[0] if pages else await self._context.new_page()
        else:
            self._context = await self._browser.new_context(**context_options)
            await self._apply_context_init_scripts(self._context)
            self._page = await self._context.new_page()
        self._page.set_default_timeout(self.action_timeout)
        self._log_auth_injection()

    async def init_browser(self) -> None:
        """初始化浏览器"""
        # 若上次未正常关闭，先释放，避免叠加启动多个 Chromium
        if self._context is not None or self._browser is not None:
            await self.close()

        if self._playwright is None:
            self._playwright = await async_playwright().start()
        
        browser_launcher = getattr(self._playwright, self.browser_type)
        if self.persistent:
            await self._init_browser_context()
        else:
            self._browser = await browser_launcher.launch(**self._build_browser_launch_options())
            await self._init_browser_context()
        self._auth_context_key = json.dumps(self._auth_config or {}, sort_keys=True)
        logger.info(f"浏览器已初始化: {self.browser_type}, headless={self.headless}")

    def _log_auth_injection(self) -> None:
        """打印本次任务的登录态注入摘要（不含凭据明文，便于确认是否生效）。"""
        auth = getattr(self, "_auth_config", None) or {}
        if not auth:
            return
        ss = auth.get("storage_state")
        if isinstance(ss, dict):
            cookies = len(ss.get("cookies") or [])
            ls_keys = sum(
                len(o.get("localStorage") or [])
                for o in (ss.get("origins") or [])
            )
            logger.info(f"已注入登录态: cookies={cookies}, localStorage_keys={ls_keys}, login_check={'on' if auth.get('login_check') else 'off'}")
        elif ss:
            logger.info(f"已注入登录态: storage_state 文件={ss}, login_check={'on' if auth.get('login_check') else 'off'}")
        if auth.get("headers"):
            logger.info(f"已注入请求头: {sorted(auth['headers'].keys())}")
        if auth.get("local_storage"):
            logger.info(f"已注入 localStorage 键: {sorted(auth['local_storage'].keys())}")
    
    def _release_memory(self) -> None:
        """主动回收 Python 对象，并尽量将内存归还操作系统。"""
        try:
            gc.collect()
        except Exception:
            pass

        # Linux glibc: 将已释放堆归还 OS，避免 RSS 长时间居高不下
        libc = getattr(self, "_libc", None)
        if libc is False:
            return
        try:
            if libc is None:
                import platform
                import ctypes
                if platform.system() != "Linux":
                    self._libc = False
                    return
                libc = ctypes.CDLL("libc.so.6")
                self._libc = libc
            libc.malloc_trim(0)
        except Exception:
            self._libc = False


    async def _close_all_pages(self, context: Optional[BrowserContext] = None) -> None:
        """关闭上下文中的全部页面，减少 Chromium 残留占用。"""
        ctx = context or self._context
        if not ctx:
            return
        try:
            pages = list(ctx.pages)
        except Exception:
            return
        for page in pages:
            try:
                await page.close()
            except Exception:
                pass

    def _force_kill_browser(self, browser) -> None:
        """Best-effort kill of Playwright-launched browser process after close timeout."""
        if browser is None:
            return
        try:
            import signal
            proc = None
            if hasattr(browser, 'process') and callable(getattr(browser, 'process')):
                proc = browser.process()
            if proc is None:
                impl = getattr(browser, '_impl_obj', None)
                if impl is not None:
                    proc = getattr(impl, '_process', None) or getattr(impl, 'process', None)
                    if callable(proc):
                        proc = proc()
            if proc is None:
                return
            pid = getattr(proc, 'pid', None)
            if not pid:
                return
            logger.warning(f'force-killing browser process pid={pid}')
            try:
                if hasattr(proc, 'kill'):
                    proc.kill()
                else:
                    os.kill(int(pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            except Exception as e:
                logger.debug(f'force kill failed: {e}')
        except Exception as e:
            logger.debug(f'_force_kill_browser error: {e}')

    async def _await_close(self, coro, label: str, timeout: float = 10.0) -> bool:
        """Await a close coroutine with timeout. Returns True if finished cleanly."""
        try:
            await asyncio.wait_for(coro, timeout=timeout)
            return True
        except asyncio.TimeoutError:
            logger.warning(f'{label} timed out after {timeout}s')
            return False
        except Exception as e:
            logger.warning(f'{label} failed: {e}')
            return False

    async def close(self) -> None:
        """Close browser + Playwright driver with timeouts to avoid orphan Chromium."""
        browser = self._browser
        context = self._context
        playwright = self._playwright
        # Drop refs first so concurrent init cannot reuse half-closed handles.
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        self._page_errors = []

        # Prefer browser.close() which tears down contexts/pages; sequential
        # page->context->browser left orphans when an early close hung.
        if browser is not None:
            ok = await self._await_close(browser.close(), 'browser.close', timeout=10.0)
            if not ok:
                self._force_kill_browser(browser)
        elif context is not None:
            # persistent context has no separate browser handle
            try:
                await self._await_close(self._close_all_pages(context), 'close pages', timeout=5.0)
            except Exception:
                pass
            await self._await_close(context.close(), 'context.close', timeout=10.0)

        if playwright is not None:
            await self._await_close(playwright.stop(), 'playwright.stop', timeout=10.0)

        self._release_memory()
        logger.info('browser closed')


    @asynccontextmanager
    async def browser_session(self):
        """浏览器会话上下文管理器"""
        await self.init_browser()
        try:
            if self.on_execution_page is not None:
                await self.on_execution_page(self._page)
            yield self._page
        finally:
            await self.close()
    
    @asynccontextmanager
    async def browser_session_with_trace(self, trace_name: str = 'trace'):
        """带 Trace 的浏览器会话上下文管理器
        
        Args:
            trace_name: trace 文件名前缀（不含扩展名）
            
        Yields:
            Page: 页面对象
            
        Returns:
            trace 文件路径（通过 self._current_trace_path 获取）
        """
        self._current_trace_path = None
        await self.init_browser()
        
        try:
            # 启动 Trace
            if self.trace_enabled and self._context:
                await self._context.tracing.start(
                    screenshots=self.trace_screenshots,
                    snapshots=self.trace_snapshots,
                    sources=self.trace_sources,
                )
                logger.debug(f"Trace 已启动: screenshots={self.trace_screenshots}, snapshots={self.trace_snapshots}")

            if self.on_execution_page is not None:
                await self.on_execution_page(self._page)

            yield self._page
            
        finally:
            # 停止 Trace 并保存
            if self.trace_enabled and self._context:
                try:
                    timestamp = int(time.time() * 1000)
                    trace_path = f"{self.trace_dir}/{trace_name}_{timestamp}.zip"
                    await self._context.tracing.stop(path=trace_path)
                    self._current_trace_path = trace_path
                    logger.info(f"Trace 已保存: {trace_path}")
                except Exception as e:
                    logger.error(f"保存 Trace 失败: {e}")
            
            await self.close()
    
    def get_current_trace_path(self) -> Optional[str]:
        """获取当前执行的 trace 文件路径"""
        return self._current_trace_path

    def stop(self):
        """请求停止执行（置标志；由调用方决定是否 force 硬中断）"""
        self._stop_requested = True

    async def stop_now(self) -> None:
        """立即硬中断：置标志并关闭浏览器/上下文，使在途 Playwright 调用
        快速失败——用于前端关闭执行画布时直接终止（不用等当前步骤结束）。"""
        self._stop_requested = True
        try:
            await self.close()
        except Exception as e:
            logger.warning('stop_now 关闭浏览器异常: %s', e)

    def _setup_page_listeners(self, page: Page):
        """注册页面基础事件监听（自动处理弹窗、记录控制台 JS 错误）"""
        async def handle_dialog(dialog):
            logger.warning(f"检测到浏览器弹窗 [{dialog.type}]: '{dialog.message}'，已自动 accept。")
            try:
                await dialog.accept()
            except Exception as e:
                logger.error(f"处理浏览器弹窗异常: {e}")

        def handle_pageerror(exception):
            logger.error(f"页面 JS 抛出未捕获异常: {exception}")
            if not hasattr(self, '_page_errors'):
                self._page_errors = []
            self._page_errors.append(str(exception))
            if len(self._page_errors) > 50:
                self._page_errors = self._page_errors[-50:]

        page.on("dialog", handle_dialog)
        page.on("pageerror", handle_pageerror)

    def _get_locator(self, container: Union[Page, FrameLocator], locator_type: str, locator_value: str):
        """根据定位类型获取元素定位器"""
        locator_map = {
            'xpath': lambda: container.locator(f"xpath={locator_value}"),
            'css': lambda: container.locator(locator_value),
            'id': lambda: container.locator(f"#{locator_value}"),
            'name': lambda: container.locator(f"[name='{locator_value}']"),
            'text': lambda: container.get_by_text(locator_value),
            'role': lambda: container.get_by_role(locator_value),
            'placeholder': lambda: container.get_by_placeholder(locator_value),
            'label': lambda: container.get_by_label(locator_value),
            'testid': lambda: container.get_by_test_id(locator_value),
            # 模型/前端词汇表为 test_id（区别于旧数据遗留的 testid，两者等价）
            'test_id': lambda: container.get_by_test_id(locator_value),
        }
        return locator_map.get(locator_type, lambda: container.locator(locator_value))()

    @staticmethod
    def _first_sql_keyword(sql: str) -> str:
        sql = sql.strip()
        while sql.startswith('--'):
            _, _, sql = sql.partition('\n')
            sql = sql.strip()
        return sql.split(None, 1)[0].lower() if sql else ''

    def _normalize_sql_execute(self, step: StepConfig) -> dict[str, Any]:
        """解析 SQL 步骤配置，兼容前端 JSON 文本中的常见字段名。"""
        raw_config = step.sql_execute or {}
        if isinstance(raw_config, str):
            raw_config = {'sql': raw_config}
        if not isinstance(raw_config, dict):
            raise ValueError("SQL执行配置必须是对象或SQL字符串")

        sql = (
            raw_config.get('sql')
            or raw_config.get('statement')
            or raw_config.get('query')
        )
        if not sql or not str(sql).strip():
            raise ValueError("SQL执行配置缺少 sql 字段")
        sql = str(sql)

        configured_method = (
            raw_config.get('method')
            or raw_config.get('sql_method')
            or raw_config.get('action')
            or raw_config.get('execute_type')
        )
        first_keyword = self._first_sql_keyword(sql)
        supported_methods = {
            'fetchone', 'fetchmany', 'fetchall', 'select', 'query',
            'insert', 'update', 'delete', 'execute',
        }
        method = str(configured_method).lower() if configured_method else ''
        if method not in supported_methods:
            if first_keyword in {'select', 'with', 'values'}:
                method = 'fetchall'
            elif first_keyword in {'insert', 'update', 'delete'}:
                method = first_keyword
            else:
                method = 'execute'
        if method in {'select', 'query'}:
            method = 'fetchall'

        params = (
            raw_config.get('params')
            if 'params' in raw_config
            else raw_config.get('sql_params', raw_config.get('parameters'))
        )
        if params is None:
            params = {}
        if not isinstance(params, (dict, list, tuple)):
            raise ValueError("SQL参数必须是对象或数组")

        size = raw_config.get('size', raw_config.get('sql_size', raw_config.get('limit', 10)))
        try:
            size = int(size)
        except (TypeError, ValueError):
            size = 10

        return {
            'sql': sql,
            'method': method,
            'params': params,
            'size': max(size, 1),
            'first_keyword': first_keyword,
            'db_type': raw_config.get('db_type') or raw_config.get('database_type'),
            'connection': raw_config.get('connection'),
            'db_config': raw_config.get('db_config') or raw_config.get('connection_config'),
        }

    def _resolve_sql_connection_config(
        self,
        sql_config: dict[str, Any],
        env_config: Optional[dict],
    ) -> tuple[str, dict[str, Any]]:
        if not env_config:
            raise ValueError("执行SQL步骤需要选择包含数据库配置的执行环境")

        db_type = str(sql_config.get('db_type') or env_config.get('db_type') or 'mysql').lower()
        if db_type != 'mysql':
            raise ValueError(f"不支持的UI自动化数据库类型: {db_type}")

        direct_config = sql_config.get('connection') or sql_config.get('db_config')
        if direct_config is not None and not isinstance(direct_config, dict):
            raise ValueError("SQL连接配置必须是对象")

        db_config = direct_config or env_config.get(f'{db_type}_config') or {}
        if not isinstance(db_config, dict) or not db_config:
            raise ValueError(f"执行环境缺少 {db_type.upper()} 数据库配置")

        required_fields = ['host', 'port', 'database']
        missing = [field for field in required_fields if not db_config.get(field)]
        user = db_config.get('user') or db_config.get('username')
        if not user:
            missing.append('user')
        if not db_config.get('password'):
            missing.append('password')
        if missing:
            raise ValueError(f"{db_type.upper()} 数据库配置缺少字段: {', '.join(missing)}")

        resolved = dict(db_config)
        resolved['user'] = user
        return db_type, resolved

    def _validate_sql_permission(self, sql_config: dict[str, Any], env_config: dict) -> None:
        keyword = sql_config['first_keyword']
        method = sql_config['method']

        if keyword == 'insert' or method == 'insert':
            if not env_config.get('db_c_status', False):
                raise ValueError("当前环境未启用数据库新增操作")
            return

        if not env_config.get('db_rud_status', False):
            raise ValueError("当前环境未启用数据库查改删操作")

    @staticmethod
    def _execute_cursor(cursor: Any, sql: str, params: Any) -> None:
        if params in ({}, [], ()):
            cursor.execute(sql)
        else:
            cursor.execute(sql, params)

    @staticmethod
    def _rows_to_dicts(rows: Any, description: Any) -> list[Any]:
        if rows is None:
            return []
        if isinstance(rows, dict):
            return [rows]
        if not isinstance(rows, list):
            rows = [rows]

        columns = [desc[0] for desc in description] if description else []
        result = []
        for row in rows:
            if isinstance(row, dict):
                result.append(row)
            elif columns and isinstance(row, (list, tuple)):
                result.append(dict(zip(columns, row)))
            else:
                result.append(row)
        return result

    @staticmethod
    def _preview_rows(rows: list[Any]) -> str:
        if not rows:
            return ''
        preview = json.dumps(rows[:3], ensure_ascii=False, default=str)
        if len(preview) > 500:
            preview = preview[:500] + '...'
        return preview

    def _summarize_sql_result(self, method: str, rows: list[Any], affected_rows: int) -> str:
        if method in {'fetchone', 'fetchmany', 'fetchall'}:
            message = f"SQL操作执行成功: 返回 {len(rows)} 行"
            preview = self._preview_rows(rows)
            if preview:
                message += f"，预览: {preview}"
            return message

        if affected_rows is None or affected_rows < 0:
            return "SQL操作执行成功"
        return f"SQL操作执行成功: 影响 {affected_rows} 行"

    def _connect_mysql(self, config: dict[str, Any]):
        try:
            pymysql = importlib.import_module('pymysql')
        except ImportError as exc:
            raise RuntimeError("执行MySQL SQL步骤需要安装依赖 pymysql") from exc

        return pymysql.connect(
            host=config['host'],
            port=int(config['port']),
            user=config['user'],
            password=config['password'],
            database=config['database'],
            charset=config.get('charset') or 'utf8mb4',
            connect_timeout=int(config.get('connect_timeout') or 10),
            cursorclass=pymysql.cursors.DictCursor,
        )


    def _execute_sql_step(
        self,
        step: StepConfig,
        env_config: Optional[dict],
    ) -> tuple[bool, str]:
        sql_config = self._normalize_sql_execute(step)
        if env_config is None:
            raise ValueError("执行SQL步骤需要执行环境")
        self._validate_sql_permission(sql_config, env_config)
        _, db_config = self._resolve_sql_connection_config(sql_config, env_config)

        conn = None
        cursor = None
        try:
            conn = self._connect_mysql(db_config)
            cursor = conn.cursor()


            self._execute_cursor(cursor, sql_config['sql'], sql_config['params'])

            method = sql_config['method']
            rows: list[Any] = []
            description = getattr(cursor, 'description', None)
            if method == 'fetchone':
                rows = self._rows_to_dicts(cursor.fetchone(), description)
            elif method == 'fetchmany':
                rows = self._rows_to_dicts(cursor.fetchmany(sql_config['size']), description)
            elif method == 'fetchall':
                rows = self._rows_to_dicts(cursor.fetchall(), description)
            else:
                conn.commit()

            return True, self._summarize_sql_result(method, rows, getattr(cursor, 'rowcount', -1))
        except Exception:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    @staticmethod
    def _is_non_file_input_upload_error(error: Exception) -> bool:
        message = str(error)
        return "not an HTMLInputElement" in message

    async def _upload_file(self, page: Page, locator: Any, file_path: Any, step: StepConfig) -> None:
        if not file_path or not str(file_path).strip():
            raise ValueError("上传文件路径为空，请选择文件管理中的文件或填写执行器可访问的文件路径")

        payload = file_path
        # 有原始文件名时以原名上传（路径多为平台存储的 hash/临时名，上传后服务端看到的
        # 文件名应保持用户初衷）——读取文件内容并携带 name/mimeType。
        original_name = (step.upload_file_name or '').strip()
        if original_name:
            try:
                with open(str(file_path), 'rb') as fh:
                    file_buffer = fh.read()
                import mimetypes
                mime = mimetypes.guess_type(original_name)[0] or 'application/octet-stream'
                payload = [{'name': original_name, 'mimeType': mime, 'buffer': file_buffer}]
            except Exception:
                payload = file_path  # 读取失败退回路径上传

        try:
            await locator.set_input_files(payload)
            logger.info(f"步骤 {step.step_id}: 已通过 file input 设置上传文件")
            return
        except Exception as exc:
            if not self._is_non_file_input_upload_error(exc):
                raise

            logger.info(f"步骤 {step.step_id}: 当前定位器不是 file input，改用文件选择器事件上传")

        async with page.expect_file_chooser() as file_chooser_info:
            await locator.click()

        file_chooser = await file_chooser_info.value
        await file_chooser.set_files(payload)
        logger.info(f"步骤 {step.step_id}: 已通过 file chooser 设置上传文件")

    def _get_ocr_instance(self):
        """获取 ddddocr 识别引擎单例"""
        if not hasattr(self, '_ocr_instance') or self._ocr_instance is None:
            try:
                import ddddocr
                self._ocr_instance = ddddocr.DdddOcr(show_ad=False)
            except ImportError:
                self._ocr_instance = None
            except Exception as e:
                logger.warning(f"初始化 ddddocr 失败: {e}")
                self._ocr_instance = None
        return self._ocr_instance

    def _resolve_target_locator(self, page: Page, target_info: dict):
        """根据目标信息解析出定位器（支持 iframe 与 下标）"""
        frame = page
        if target_info.get('is_iframe') and target_info.get('iframe_locator'):
            iframe_loc = target_info['iframe_locator']
            if ">>>" in iframe_loc:
                iframe_selectors = [s.strip() for s in iframe_loc.split(">>>") if s.strip()]
            elif ">>" in iframe_loc:
                iframe_selectors = [s.strip() for s in iframe_loc.split(">>") if s.strip()]
            else:
                iframe_selectors = [iframe_loc]
            for selector in iframe_selectors:
                frame = frame.frame_locator(selector)

        l_type = target_info.get('locator_type') or 'xpath'
        l_val = target_info.get('locator_value') or ''
        l_idx = target_info.get('locator_index')
        locator = self._get_locator(frame, l_type, l_val)
        if l_idx is not None:
            locator = locator.nth(l_idx)
        return locator

    async def _execute_captcha_recognize(
        self,
        page: Page,
        img_locator: Any,
        step: StepConfig,
    ) -> tuple[bool, str, str | None]:
        ocr = self._get_ocr_instance()
        if ocr is None:
            return False, "执行器未安装 ddddocr 库，请安装依赖: pip install ddddocr", None

        ope_val = step.ope_value if isinstance(step.ope_value, dict) else {}
        target_info = ope_val.get('target_locator')
        if not target_info or not target_info.get('locator_value'):
            return False, "验证码识别步骤缺少目标输入框定位信息", None

        max_retries = 3
        try:
            if 'retry_count' in ope_val and ope_val['retry_count'] is not None:
                max_retries = int(ope_val['retry_count'])
        except (ValueError, TypeError):
            max_retries = 3
        if max_retries < 1:
            max_retries = 1

        click_refresh = bool(ope_val.get('click_to_refresh', True))
        target_locator = self._resolve_target_locator(page, target_info)

        last_error = ""
        for attempt in range(1, max_retries + 1):
            try:
                # 1. 截取验证码图片元素截图
                img_bytes = await img_locator.screenshot(type="png")
                # 2. 调用 ddddocr 进行识别（放到线程池中避免阻塞 Playwright async 事件循环）
                recognized = await asyncio.to_thread(ocr.classification, img_bytes)
                if isinstance(recognized, str):
                    recognized = recognized.strip()

                logger.info(f"步骤 {step.step_id}: 验证码识别尝试 [{attempt}/{max_retries}] 结果: '{recognized}'")

                if recognized:
                    # 3. 填入目标输入框
                    await target_locator.fill(recognized)
                    return True, f"验证码识别成功并填入: {recognized}", None

                # 若识别为空且允许刷新重试
                if click_refresh and attempt < max_retries:
                    await img_locator.click()
                    await page.wait_for_timeout(600)
            except Exception as exc:
                last_error = str(exc)
                logger.warning(f"步骤 {step.step_id}: 验证码识别第 {attempt} 次尝试异常: {exc}")
                if click_refresh and attempt < max_retries:
                    try:
                        await img_locator.click()
                        await page.wait_for_timeout(600)
                    except Exception:
                        pass

        return False, f"验证码识别重试 {max_retries} 次失败" + (f": {last_error}" if last_error else ""), None

    async def _execute_ai_action(
        self,
        page: Page,
        step: StepConfig,
    ) -> tuple[bool, str, str | None]:
        """执行 AI操作(step_type=10)：把自然语言 prompt 交给 AI Agent 驱动 Playwright。

        Returns:
            tuple: (成功与否, 消息, 截图路径(可选))
        """
        if not self.model_config:
            logger.error(f"步骤 {step.step_id}: AI 模型未配置（缺少 [model] 段）")
            return False, "AI 操作失败：未配置 AI 模型（config.toml 缺少 [model] 段）", None

        goal = (step.input_value or '').strip() or (step.description or '').strip()
        if not goal:
            return False, "AI 操作失败：缺少自然语言描述(ai_prompt)", None

        logger.info(f"步骤 {step.step_id}: 开始 AI 操作 -> {goal[:200]}")
        try:
            from agent import run_agent_loop  # 延迟导入，避免影响启动
        except ImportError as e:
            logger.error(f"agent 模块导入失败: {e}", exc_info=True)
            return False, f"AI 操作失败：agent 模块不可用 ({e})", None

        try:
            success, message, screenshot_path = await asyncio.wait_for(
                run_agent_loop(
                    page=page,
                    goal=goal,
                    model_config=self.model_config,
                    step_id=step.step_id,
                    screenshot_dir=self.screenshot_dir,
                ),
                timeout=self.ai_action_timeout,
            )
            return success, message, screenshot_path
        except asyncio.TimeoutError:
            logger.error(f"步骤 {step.step_id}: AI 操作超时({self.ai_action_timeout}s)")
            screenshot_path = f"{self.screenshot_dir}/ai_timeout_{step.step_id}.png"
            try:
                await page.screenshot(path=screenshot_path)
            except Exception:
                screenshot_path = None
            return False, f"AI 操作超时({self.ai_action_timeout}s)", screenshot_path
        except Exception as e:
            logger.error(f"步骤 {step.step_id}: AI 操作异常: {e}", exc_info=True)
            return False, f"AI 操作异常: {e}", None

    async def _execute_step(
        self,
        page: Page,
        step: StepConfig,
        env_config: Optional[dict] = None,
    ) -> tuple[bool, str, str | None]:
        """执行单个步骤
        
        Returns:
            tuple: (成功与否, 消息, 截图路径(可选))
        """
        if step.step_type == 2:
            success, message = await asyncio.to_thread(self._execute_sql_step, step, env_config)
            return success, message, None

        # step_type == 10：AI操作，交给 AI Agent 驱动 Playwright
        if step.step_type == 10:
            return await self._execute_ai_action(page, step)

        operation = (step.operation_type or '').lower()
        screenshot_path: str | None = None
        
        # 等待时间（仅当用户明确设置 > 0 时才等待，用于特殊场景）
        # 注意：Playwright 自带 Auto-waiting，一般不需要手动等待
        if step.wait_time > 0:
            wait_time = step.wait_time
            # 防呆逻辑：如果设置的时间大于 60，极有可能是毫秒，自动除以 1000 转换为秒
            if wait_time > 60:
                logger.warning(f"步骤 {step.step_id}: wait_time ({wait_time}) 过大，已自动转换为秒 ({wait_time / 1000:.2f}s)")
                wait_time = wait_time / 1000
            
            logger.debug(f"步骤 {step.step_id}: 强制等待 {wait_time}s（建议设为0让Playwright自动等待）")
            await page.wait_for_timeout(int(wait_time * 1000))
        
        # 记录开始时间
        op_start = time.time()
        
        # switch_tab 操作特殊处理
        if operation == 'switch_tab':
            if not page.context:
                return False, "浏览器上下文为空，无法切换页签", None
            
            pages = page.context.pages
            target_idx = None
            try:
                target_idx = int(step.input_value)
            except (ValueError, TypeError):
                pass
            
            if target_idx is not None:
                if 0 <= target_idx < len(pages):
                    self._page = pages[target_idx]
                    logger.info(f"成功切换到页签索引: {target_idx}, URL: {self._page.url}")
                    return True, f"成功切换到页签索引: {target_idx}", None
                else:
                    return False, f"切换页签失败，索引 {target_idx} 越界（当前共有 {len(pages)} 个页签）", None
            else:
                query = step.input_value.strip() if step.input_value else ''
                if not query:
                    return False, "切换页签参数为空，请输入索引、URL或页签标题", None
                
                for p in pages:
                    try:
                        title = await p.title()
                        if query in p.url or query in title:
                            self._page = p
                            logger.info(f"成功切换到页签: title='{title}', url='{p.url}'")
                            return True, f"成功切换到符合条件 '{query}' 的页签", None
                    except Exception as e:
                        logger.warning(f"获取页签属性失败: {e}")
                return False, f"未找到匹配 '{query}' 的页签", None

        # screenshot 操作特殊处理，保存路径
        if operation == 'screenshot':
            screenshot_path = step.input_value or f"{self.screenshot_dir}/step_{step.step_id}.png"
            await page.screenshot(path=screenshot_path)
            logger.debug(f"步骤 {step.step_id}: screenshot 耗时 {time.time() - op_start:.2f}s")
            return True, f"页面操作 {operation} 执行成功", screenshot_path
        
        # 页面操作（不需要定位器）
        def _parse_wait_timeout(value: str) -> int:
            """解析等待时间（单位为秒，转换为毫秒。支持大于60的旧数据向下兼容）"""
            if not value:
                return 1000  # 默认 1 秒
            try:
                val = float(value)
                # 向下兼容：如果大于 60，判定为历史毫秒数据，直接返回
                if val > 60:
                    return int(val)
                # 正常情况：秒转换为毫秒
                return int(val * 1000)
            except ValueError:
                return 1000

        page_operations = {
            'goto': lambda: self._goto_with_login_check(page, step.input_value),
            'reload': lambda: page.reload(),
            'go_back': lambda: page.go_back(),
            'go_forward': lambda: page.go_forward(),
            'wait': lambda: page.wait_for_timeout(_parse_wait_timeout(step.input_value)),
            'wait_load': lambda: page.wait_for_load_state("load"),
            'wait_network': lambda: page.wait_for_load_state("networkidle"),
        }
        
        if operation in page_operations:
            await page_operations[operation]()
            logger.debug(f"步骤 {step.step_id}: {operation} 耗时 {time.time() - op_start:.2f}s")
            return True, f"页面操作 {operation} 执行成功", None
        
        # 元素操作（需要定位器）- 先验证定位器是否有效
        if not step.locator_value or not step.locator_value.strip():
            return False, f"元素定位器为空，请在元素管理中配置定位表达式（步骤: {step.description or step.step_id}）", None
        
        locator_start = time.time()
        
        # iframe 自动切换支持
        frame = page
        if step.is_iframe and step.iframe_locator:
            logger.info(f"切换至 iframe 上下文, 表达式: {step.iframe_locator}")
            
            # 支持多层 iframe 嵌套，以 ">>>" 或 ">>" 分割
            if ">>>" in step.iframe_locator:
                iframe_selectors = [s.strip() for s in step.iframe_locator.split(">>>") if s.strip()]
            elif ">>" in step.iframe_locator:
                iframe_selectors = [s.strip() for s in step.iframe_locator.split(">>") if s.strip()]
            else:
                iframe_selectors = [step.iframe_locator]
                
            for selector in iframe_selectors:
                frame = frame.frame_locator(selector)
        
        # 构建所有可选的定位器序列进行依次尝试：(类型, 表达式, 下标)
        locators_to_try = [
            (step.locator_type, step.locator_value, getattr(step, 'locator_index', None))
        ]
        if getattr(step, 'locator_type_2', None) and getattr(step, 'locator_value_2', None):
            locators_to_try.append((step.locator_type_2, step.locator_value_2, getattr(step, 'locator_index_2', None)))
        if getattr(step, 'locator_type_3', None) and getattr(step, 'locator_value_3', None):
            locators_to_try.append((step.locator_type_3, step.locator_value_3, getattr(step, 'locator_index_3', None)))

        locator = None
        locator_type_used = None
        locator_value_used = None
        
        for idx, (l_type, l_value, l_index) in enumerate(locators_to_try, start=1):
            if not l_value or not l_value.strip():
                continue
            
            logger.info(f"步骤 {step.step_id}: 尝试定位器 {idx} [{l_type}={l_value}]" + (f" 下标 {l_index}" if l_index is not None else ""))
            
            if step.is_iframe and step.iframe_locator:
                locator_cand = self._get_locator(frame, l_type, l_value)
            else:
                locator_cand = self._get_locator(page, l_type, l_value)
                
            if l_index is not None:
                locator_cand = locator_cand.nth(l_index)
                
            try:
                # 给备用定位器更短的等待时间，以便快速进行尝试切换
                wait_timeout = 5000 if idx == 1 else 2000
                await locator_cand.wait_for(state="visible", timeout=wait_timeout)
                # 成功找到并可见！使用该定位器并跳出循环
                locator = locator_cand
                locator_type_used = l_type
                locator_value_used = l_value
                logger.info(f"步骤 {step.step_id}: 定位器 {idx} [{l_type}={l_value}] 可见并被成功选中")
                break
            except Exception as e:
                logger.warning(f"步骤 {step.step_id}: 定位器 {idx} [{l_type}={l_value}] 尝试失败或不可见: {e}")
                # 如果是最后一个定位器，不论成败都必须保留它，以便进行下一步操作或者抛出异常
                if idx == len(locators_to_try):
                    locator = locator_cand
                    locator_type_used = l_type
                    locator_value_used = l_value

        if locator is None:
            return False, f"所有定位器都失效（包含备用定位器，步骤: {step.description or step.step_id}）", None

        locator_time = time.time() - locator_start
        logger.debug(f"步骤 {step.step_id}: 定位元素 [{locator_type_used}={locator_value_used}] 耗时 {locator_time:.2f}s (iframe={step.is_iframe})")
        


        element_operations = {
            'click': lambda: locator.click(),
            'dblclick': lambda: locator.dblclick(),
            'double_click': lambda: locator.dblclick(),
            'right_click': lambda: locator.click(button="right"),
            'fill': lambda: locator.fill(step.input_value),
            'type': lambda: locator.type(step.input_value),
            'clear': lambda: locator.fill(""),
            'check': lambda: locator.check(),
            'uncheck': lambda: locator.uncheck(),
            'select': lambda: locator.select_option(step.input_value),
            'select_option': lambda: locator.select_option(step.input_value),
            'hover': lambda: locator.hover(),
            'focus': lambda: locator.focus(),
            'press': lambda: locator.press(step.input_value),
        }
        
        if operation == 'upload':
            action_start = time.time()
            await self._upload_file(page, locator, step.input_value, step)
            action_time = time.time() - action_start
            logger.debug(f"步骤 {step.step_id}: {operation} 操作耗时 {action_time:.2f}s (总计 {time.time() - op_start:.2f}s)")
            return True, f"元素操作 {operation} 执行成功", None

        if operation == 'captcha_recognize':
            action_start = time.time()
            success, msg, sc = await self._execute_captcha_recognize(page, locator, step)
            action_time = time.time() - action_start
            logger.debug(f"步骤 {step.step_id}: {operation} 操作耗时 {action_time:.2f}s (总计 {time.time() - op_start:.2f}s)")
            return success, msg, sc

        if operation in element_operations:
            action_start = time.time()
            await element_operations[operation]()
            action_time = time.time() - action_start
            logger.debug(f"步骤 {step.step_id}: {operation} 操作耗时 {action_time:.2f}s (总计 {time.time() - op_start:.2f}s)")
            return True, f"元素操作 {operation} 执行成功", None
        
        # 断言操作
        if operation.startswith('assert_'):
            assert_type = operation.replace('assert_', '')
            assert_operations = {
                'visible': lambda: expect(locator).to_be_visible(),
                'hidden': lambda: expect(locator).to_be_hidden(),
                'enabled': lambda: expect(locator).to_be_enabled(),
                'disabled': lambda: expect(locator).to_be_disabled(),
                'checked': lambda: expect(locator).to_be_checked(),
                'text': lambda: expect(locator).to_have_text(step.input_value),
                'value': lambda: expect(locator).to_have_value(step.input_value),
                'contain_text': lambda: expect(locator).to_contain_text(step.input_value),
                'url': lambda: expect(page).to_have_url(step.input_value),
                'title': lambda: expect(page).to_have_title(step.input_value),
                'count': lambda: expect(locator).to_have_count(int(float(step.input_value)) if step.input_value else 0),
            }
            if assert_type in assert_operations:
                await assert_operations[assert_type]()
                logger.debug(f"步骤 {step.step_id}: assert_{assert_type} 耗时 {time.time() - op_start:.2f}s")
                return True, f"断言 {assert_type} 通过", None
        
        return False, f"未知操作类型: {operation}", None

    async def _execute_step_with_retry(
        self,
        page: Page,
        step: StepConfig,
        env_config: Optional[dict] = None,
    ) -> tuple[bool, str, str | None]:
        """执行单个步骤，支持失败重试（retry_count）与步骤间间隔（step_interval）。

        最多执行 retry_count + 1 次，任一次成功即返回；全部失败返回最后一次结果。
        fail_fast 开启时：步骤失败立即返回，不做步骤级重试（由调用方中断用例）。
        Returns:
            tuple: (成功与否, 消息, 截图路径(可选))
        """
        attempts = 1 if getattr(self, 'fail_fast', False) else max(int(getattr(self, 'retry_count', 0)), 0) + 1
        last_result: tuple[bool, str, str | None] = (False, "步骤执行失败", None)

        for attempt in range(attempts):
            if self._stop_requested:
                return False, "用例被手动停止", None
            try:
                success, message, screenshot = await self._execute_step(page, step, env_config)
            except Exception as e:
                success, message, screenshot = False, str(e), None

            if success:
                # 步骤成功后的间隔等待（毫秒）
                step_interval = max(int(getattr(self, 'step_interval', 0)), 0)
                if step_interval > 0:
                    await asyncio.sleep(step_interval / 1000)
                return True, message, screenshot

            last_result = (success, message, screenshot)
            if attempt < attempts - 1:
                logger.warning(
                    f"步骤 {step.step_id} 第 {attempt + 1} 次执行失败，重试: {message}"
                )
                # 重试前短暂等待，避免立即重试同样失败
                await asyncio.sleep(0.5)

        return last_result

    async def execute_step(self, step: StepConfig, page_url: str = '') -> StepResultModel:
        """执行单个步骤（独立浏览器会话）"""
        start_time = time.time()
        
        try:
            async with self.browser_session() as page:
                if page_url:
                    await self._goto_with_login_check(page, page_url)
                
                success, message, step_screenshot = await self._execute_step_with_retry(page, step)
                duration = time.time() - start_time
                
                return StepResultModel(
                    step_id=step.step_id,
                    status='success' if success else 'failed',
                    message=message,
                    description=step.description or step.operation_type,
                    duration=duration,
                    element_found=success,
                    screenshot=step_screenshot
                )
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"步骤执行失败: {e}\n{traceback.format_exc()}")
            return StepResultModel(
                step_id=step.step_id,
                status='failed',
                message=str(e),
                description=step.description or step.operation_type,
                duration=duration,
                element_found=False
            )
    
    async def execute_test_case(self, config: TestCaseConfig) -> CaseResultModel:
        """执行测试用例（支持 Trace 记录）"""
        start_time = time.time()
        step_results = []
        passed_steps = 0
        failed_steps = 0
        total_steps = sum(len(ps.steps) for ps in config.page_steps)
        
        self._stop_requested = False
        trace_name = f"case_{config.case_id}"
        
        try:
            # 先固定本次任务的 origin，供 HTTPS 客户端证书精确匹配
            self.set_task_origins(self._task_origins(config))
            # 使用带 trace 的浏览器会话
            async with self.browser_session_with_trace(trace_name) as page:
                self._page = page
                logger.info(f"开始执行用例: {config.case_name}")
                self._page_errors = []
                self._setup_page_listeners(page)

                # 浏览器启动后，立即导航到环境配置的 base_url
                base_url = ''
                if config.env_config:
                    base_url = config.env_config.get('base_url', '') or ''
                if base_url:
                    logger.info(f"导航到环境 base_url: {base_url}")
                    await self._goto_with_login_check(page, base_url, wait_until="networkidle")

                pending_auth = None
                for page_step in config.page_steps:
                    if self._stop_requested:
                        raise Exception("用例被手动停止")

                    # 组间登录态切换：未绑定步骤"向上匹配"最近绑定的登录态
                    # （沿用 pending_auth，不触发清理）；显式绑定变更时才重建 context
                    if getattr(page_step, 'auth_state_id', None):
                        pending_auth = getattr(page_step, 'auth', None)
                    rebuilt = await self.ensure_auth_context(pending_auth)
                    page = self._page
                    if rebuilt:
                        self._setup_page_listeners(page)
                        nav_url = page_step.page_url or base_url
                        if nav_url:
                            await self._goto_with_login_check(page, nav_url, wait_until="domcontentloaded")

                    logger.info(f"执行页面步骤: {page_step.page_name}")

                    # 确保使用最新的页签引用进行环境跳转检测
                    page = self._page

                    # 检测页面跳转：仅当下一个页面 URL 与当前不同时才等待
                    if page_step.page_url:
                        current_url = page.url
                        expected_url = page_step.page_url.rstrip('/')
                        
                        # 只有当期望的 URL 与当前 URL 不同时，才等待跳转
                        if expected_url not in current_url:
                            try:
                                # 短暂等待，检测是否有 URL 变化
                                await page.wait_for_url(
                                    lambda url: url != current_url,
                                    timeout=2000
                                )
                                logger.debug(f"检测到页面跳转: {current_url} -> {page.url}")
                            except Exception:
                                # 没有页面跳转是正常情况
                                pass
                    
                    # 执行页面内的步骤
                    for step in page_step.steps:
                        if self._stop_requested:
                            raise Exception("用例被手动停止")
                        
                        # 确保总是使用最新的活跃页签进行操作
                        page = self._page
                        
                        step_start = time.time()
                        try:
                            success, message, step_screenshot = await self._execute_step_with_retry(
                                page,
                                step,
                                page_step.env_config or config.env_config,
                            )
                            
                            # 执行后重新同步页签引用，以防步骤内发生了页签切换
                            page = self._page
                            step_duration = time.time() - step_start

                            step_result = StepResultModel(
                                step_id=step.step_id,
                                status='success' if success else 'failed',
                                message=message,
                                description=step.description or step.operation_type,
                                duration=step_duration,
                                element_found=success,
                                screenshot=step_screenshot  # 保存截图操作的路径
                            )

                            if success:
                                passed_steps += 1
                                logger.debug(f"  ✅ {step.description or step.operation_type}")
                            else:
                                failed_steps += 1
                                logger.warning(f"  ❌ {step.description or step.operation_type}: {message}")
                                # 失败时额外截图
                                if not step_screenshot:
                                    screenshot_path = f"{self.screenshot_dir}/fail_{config.case_id}_{step.step_id}.png"
                                    await page.screenshot(path=screenshot_path)
                                    step_result.screenshot = screenshot_path

                        except Exception as step_error:
                            step_duration = time.time() - step_start
                            failed_steps += 1
                            error_msg = str(step_error)
                            logger.error(f"  ❌ {step.description or step.operation_type}: {error_msg}")

                            # 失败时截图
                            try:
                                screenshot_path = f"{self.screenshot_dir}/error_{config.case_id}_{step.step_id}.png"
                                await page.screenshot(path=screenshot_path)
                            except:
                                screenshot_path = None

                            step_result = StepResultModel(
                                step_id=step.step_id,
                                status='failed',
                                message=error_msg,
                                description=step.description or step.operation_type,
                                duration=step_duration,
                                element_found=False,
                                screenshot=screenshot_path
                            )
                        
                        step_results.append(step_result)

                        if not success:
                            # 失败中断模式：元素定位失败即中断整条用例，不再定位后续步骤
                            if getattr(self, 'fail_fast', False):
                                logger.warning(f"  ⏹ 失败中断已开启，用例在步骤 {step.step_id} 处中断")
                                raise Exception(f"失败中断: {step.description or step.operation_type} 执行失败: {message}")

                    # 页面步骤执行完毕后，等待页面稳定（处理可能的页面跳转）
                    try:
                        await page.wait_for_load_state("load", timeout=10000)
                        await page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        logger.debug(f"页面步骤 {page_step.page_name} 执行后等待页面稳定超时，继续执行")

                duration = time.time() - start_time
                status = 'success' if failed_steps == 0 else 'failed'
                message = f"用例执行{'成功' if status == 'success' else '失败'}: 通过 {passed_steps}/{total_steps}"
                if hasattr(self, '_page_errors') and self._page_errors:
                    message += f" (捕获 {len(self._page_errors)} 个页面 JS 错误: {'; '.join(self._page_errors[:3])})"
                logger.info(f"✅ {message}" if status == 'success' else f"❌ {message}")
                
                # 获取 trace 文件路径（会在 browser_session_with_trace 结束时设置）
                trace_path = None
            
            # 会话结束后获取 trace 路径
            trace_path = self.get_current_trace_path()
            if trace_path:
                logger.info(f"用例执行 Trace 已记录: {trace_path}")
            
            return CaseResultModel(
                case_id=config.case_id,
                status=status,
                message=message,
                total_steps=total_steps,
                passed_steps=passed_steps,
                failed_steps=failed_steps,
                duration=duration,
                steps=step_results,
                trace_path=trace_path
            )
                
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            logger.error(f"用例执行异常: {error_msg}\n{traceback.format_exc()}")
            
            # 尝试获取 trace 路径（可能已保存）
            trace_path = self.get_current_trace_path()
            
            return CaseResultModel(
                case_id=config.case_id,
                status='failed',
                message=error_msg,
                total_steps=total_steps,
                passed_steps=passed_steps,
                failed_steps=failed_steps + (total_steps - passed_steps - failed_steps),
                duration=duration,
                steps=step_results,
                trace_path=trace_path
            )

    async def execute_page_step(self, config: PageStepConfig) -> list[StepResultModel]:
        """执行单个页面步骤（包含多个操作）- 使用同一个浏览器会话"""
        step_results = []

        # 新任务开始前清除上一次执行遗留的停止标志：
        # stop_once/stop_now 置位后无人复位，会让后续每次页面步骤调试在第一步误报"手动停止"
        self._stop_requested = False

        try:
            # 先固定本次任务的 origin，供 HTTPS 客户端证书精确匹配
            self.set_task_origins(self._task_origins(config))
            async with self.browser_session() as page:
                logger.info(f"开始执行页面步骤: {config.page_name}")
                self._page_errors = []
                self._setup_page_listeners(page)
                
                # 导航到页面
                if config.page_url:
                    nav_start = time.time()
                    await self._goto_with_login_check(page, config.page_url)
                    await page.wait_for_load_state("domcontentloaded")
                    logger.debug(f"页面导航 {config.page_name} 耗时 {time.time() - nav_start:.2f}s")
                
                # 执行页面内的所有步骤
                for step in config.steps:
                    step_start = time.time()
                    try:
                        success, message, step_screenshot = await self._execute_step_with_retry(
                            page,
                            step,
                            config.env_config,
                        )
                        step_duration = time.time() - step_start

                        step_result = StepResultModel(
                            step_id=step.step_id,
                            status='success' if success else 'failed',
                            message=message,
                            description=step.description or step.operation_type,
                            duration=step_duration,
                            element_found=success,
                            screenshot=step_screenshot
                        )
                        step_results.append(step_result)

                        if success:
                            logger.debug(f"  ✅ {step.description or step.operation_type}")
                        else:
                            logger.warning(f"  ❌ {step.description or step.operation_type}: {message}")
                            # 失败时额外截图
                            if not step_screenshot:
                                screenshot_path = f"{self.screenshot_dir}/fail_ps_{config.page_step_id}_{step.step_id}.png"
                                await page.screenshot(path=screenshot_path)
                                step_result.screenshot = screenshot_path
                            break  # 步骤失败时停止执行后续步骤

                    except Exception as step_error:
                        step_duration = time.time() - step_start
                        error_msg = str(step_error)
                        logger.error(f"  ❌ {step.description or step.operation_type}: {error_msg}")

                        # 失败时截图
                        try:
                            screenshot_path = f"{self.screenshot_dir}/error_ps_{config.page_step_id}_{step.step_id}.png"
                            await page.screenshot(path=screenshot_path)
                        except:
                            screenshot_path = None

                        step_result = StepResultModel(
                            step_id=step.step_id,
                            status='failed',
                            message=error_msg,
                            description=step.description or step.operation_type,
                            duration=step_duration,
                            element_found=False,
                            screenshot=screenshot_path
                        )
                        step_results.append(step_result)
                        break  # 步骤失败时停止执行后续步骤
                        
        except Exception as e:
            logger.error(f"页面步骤执行异常: {e}\n{traceback.format_exc()}")
            # 如果连浏览器都打不开，返回一个失败结果
            if not step_results:
                step_results.append(StepResultModel(
                    step_id=0,
                    status='failed',
                    message=str(e),
                    duration=0,
                    element_found=False
                ))

        return step_results

    async def _execute_case_on_context(
        self,
        context: BrowserContext,
        config: TestCaseConfig,
        trace_enabled: bool = False
    ) -> CaseResultModel:
        """在独立上下文中执行用例（用于并发执行）"""
        start_time = time.time()
        step_results = []
        passed_steps = 0
        failed_steps = 0
        total_steps = sum(len(ps.steps) for ps in config.page_steps)
        # 与 execute_test_case 一致：新用例开始前清除遗留的停止标志
        self._stop_requested = False
        trace_path = None
        page = None

        try:
            # 启动 Trace
            if trace_enabled:
                await context.tracing.start(
                    screenshots=self.trace_screenshots,
                    snapshots=self.trace_snapshots,
                    sources=self.trace_sources,
                )

            page = await context.new_page()
            page.set_default_timeout(self.action_timeout)
            self._page_errors = []
            self._setup_page_listeners(page)

            logger.info(f"[并发] 开始执行用例: {config.case_name}")

            # 浏览器启动后，立即导航到环境配置的 base_url
            base_url = ''
            if config.env_config:
                base_url = config.env_config.get('base_url', '') or ''
            if base_url:
                logger.info(f"[并发] 导航到环境 base_url: {base_url}")
                await self._goto_with_login_check(page, base_url, wait_until="networkidle")

            for page_step in config.page_steps:
                if self._stop_requested:
                    raise Exception("用例被手动停止")

                logger.info(f"[并发] 执行页面步骤: {page_step.page_name}")

                # 检测页面跳转：仅当下一个页面 URL 与当前不同时才等待
                if page_step.page_url:
                    current_url = page.url
                    expected_url = page_step.page_url.rstrip('/')

                    # 只有当期望的 URL 与当前 URL 不同时，才等待跳转
                    if expected_url not in current_url:
                        try:
                            # 短暂等待，检测是否有 URL 变化
                            await page.wait_for_url(
                                lambda url: url != current_url,
                                timeout=2000
                            )
                            logger.debug(f"[并发] 检测到页面跳转: {current_url} -> {page.url}")
                        except Exception:
                            # 没有页面跳转是正常情况
                            pass

                # 执行页面内的步骤
                for step in page_step.steps:
                    if self._stop_requested:
                        raise Exception("用例被手动停止")

                    step_start = time.time()
                    try:
                        success, message, step_screenshot = await self._execute_step(
                            page,
                            step,
                            page_step.env_config or config.env_config,
                        )
                        step_duration = time.time() - step_start

                        step_result = StepResultModel(
                            step_id=step.step_id,
                            status='success' if success else 'failed',
                            message=message,
                            description=step.description or step.operation_type,
                            duration=step_duration,
                            element_found=success,
                            screenshot=step_screenshot
                        )

                        if success:
                            passed_steps += 1
                        else:
                            failed_steps += 1
                            if not step_screenshot:
                                screenshot_path = f"{self.screenshot_dir}/fail_{config.case_id}_{step.step_id}.png"
                                await page.screenshot(path=screenshot_path)
                                step_result.screenshot = screenshot_path

                    except Exception as step_error:
                        step_duration = time.time() - step_start
                        failed_steps += 1
                        error_msg = str(step_error)

                        try:
                            screenshot_path = f"{self.screenshot_dir}/error_{config.case_id}_{step.step_id}.png"
                            await page.screenshot(path=screenshot_path)
                        except:
                            screenshot_path = None

                        step_result = StepResultModel(
                            step_id=step.step_id,
                            status='failed',
                            message=error_msg,
                            description=step.description or step.operation_type,
                            duration=step_duration,
                            element_found=False,
                            screenshot=screenshot_path
                        )

                    step_results.append(step_result)

                    if not success:
                        # 失败中断模式：元素定位失败即中断整条用例，不再定位后续步骤
                        if getattr(self, 'fail_fast', False):
                            logger.warning(f"  ⏹ 失败中断已开启，用例在步骤 {step.step_id} 处中断")
                            raise Exception(f"失败中断: {step.description or step.operation_type} 执行失败: {message}")

                # 页面步骤执行完毕后，等待页面稳定（处理可能的页面跳转）
                try:
                    await page.wait_for_load_state("load", timeout=10000)
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    logger.debug(f"[并发] 页面步骤 {page_step.page_name} 执行后等待页面稳定超时，继续执行")

            duration = time.time() - start_time
            status = 'success' if failed_steps == 0 else 'failed'
            message = f"用例执行{'成功' if status == 'success' else '失败'}: 通过 {passed_steps}/{total_steps}"
            if hasattr(self, '_page_errors') and self._page_errors:
                message += f" (捕获 {len(self._page_errors)} 个页面 JS 错误: {'; '.join(self._page_errors[:3])})"

            # 保存 Trace
            if trace_enabled:
                trace_path = f"{self.trace_dir}/case_{config.case_id}_{int(time.time())}.zip"
                await context.tracing.stop(path=trace_path)

            await page.close()

            logger.info(f"[并发] {'✅' if status == 'success' else '❌'} {message}")

            return CaseResultModel(
                case_id=config.case_id,
                status=status,
                message=message,
                total_steps=total_steps,
                passed_steps=passed_steps,
                failed_steps=failed_steps,
                duration=duration,
                steps=step_results,
                trace_path=trace_path
            )

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            logger.error(f"[并发] 用例执行异常: {error_msg}")

            if trace_enabled:
                try:
                    trace_path = f"{self.trace_dir}/case_{config.case_id}_{int(time.time())}.zip"
                    await context.tracing.stop(path=trace_path)
                except Exception:
                    pass
            try:
                if page is not None:
                    await page.close()
            except Exception:
                pass

            return CaseResultModel(
                case_id=config.case_id,
                status='failed',
                message=error_msg,
                total_steps=total_steps,
                passed_steps=passed_steps,
                failed_steps=failed_steps + (total_steps - passed_steps - failed_steps),
                duration=duration,
                steps=step_results,
                trace_path=trace_path
            )

    async def execute_batch_concurrent(
        self,
        configs: list[TestCaseConfig],
        max_concurrent: int = 3,
        on_result = None
    ) -> list[CaseResultModel]:
        """并发执行多个用例

        Args:
            configs: 用例配置列表
            max_concurrent: 最大并发数
            on_result: 单个用例完成时的回调函数 (可选)

        Returns:
            用例执行结果列表
        """
        if not configs:
            return []

        semaphore = asyncio.Semaphore(max_concurrent)

        # 批量用例共用一个 context 选项，因此这里取全部用例 origin 的并集，
        # 一次性覆盖所有需要的客户端证书 origin（无需改成 per-case 选项）
        self.set_task_origins(self._task_origins(*configs))

        # 确保浏览器已初始化（非持久化模式）
        if self._playwright is None:
            self._playwright = await async_playwright().start()

        browser_launcher = getattr(self._playwright, self.browser_type)
        launch_options = self._build_browser_launch_options()
        context_options = self._build_browser_context_options()
        browser = await browser_launcher.launch(
            **launch_options,
        )

        logger.info(f"[并发执行] 开始执行 {len(configs)} 个用例, 最大并发数: {max_concurrent}")

        async def run_with_limit(config: TestCaseConfig):
            async with semaphore:
                # 每个用例独立的浏览器上下文
                context = await browser.new_context(**context_options)
                await self._apply_context_init_scripts(context)
                try:
                    result = await self._execute_case_on_context(
                        context,
                        config,
                        trace_enabled=self.trace_enabled
                    )
                    if on_result:
                        await on_result(result)
                    return result
                finally:
                    await context.close()

        try:
            # 并发执行所有用例
            results = await asyncio.gather(
                *[run_with_limit(c) for c in configs],
                return_exceptions=True
            )

            # 处理异常结果
            final_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    final_results.append(CaseResultModel(
                        case_id=configs[i].case_id,
                        status='failed',
                        message=str(result),
                        total_steps=0,
                        passed_steps=0,
                        failed_steps=0,
                        duration=0,
                        steps=[]
                    ))
                else:
                    final_results.append(result)

            logger.info(f"[并发执行] 完成, 成功: {sum(1 for r in final_results if r.status == 'success')}/{len(final_results)}")
            return final_results

        finally:
            try:
                await asyncio.wait_for(browser.close(), timeout=10.0)
            except Exception as e:
                logger.warning(f'[batch] browser.close failed: {e}')
                self._force_kill_browser(browser)
            # 只释放本批次 browser/页面状态，保留实例级 Playwright 驱动，
            # 便于 consumer 复用 executor，避免后续单测/单用例冷启动驱动。
            # 完整释放驱动请走 close()。
            self._browser = None
            self._context = None
            self._page = None
            self._page_errors = []
            # 批次结束，清掉本批次累积的 origin，避免影响后续任务
            self.set_task_origins([])
            self._release_memory()
