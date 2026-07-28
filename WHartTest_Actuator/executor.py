"""
UI自动化执行器 - Python Playwright执行引擎
使用Python原生Playwright库执行测试，无需Node.js依赖
"""

import asyncio
import gc
import importlib
import json
import logging
import time
import traceback
from pathlib import Path
from typing import Any, Optional, Union
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

from playwright.async_api import async_playwright, Browser, BrowserContext, FrameLocator, Page, Playwright, expect

from models import StepResultModel, CaseResultModel

logger = logging.getLogger('actuator')


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
        trace_enabled: bool = False,
        trace_dir: str = './data/traces',
        trace_screenshots: bool = True,
        trace_snapshots: bool = True,
        trace_sources: bool = False,
    ):
        self.browser_type = browser_type
        self.headless = headless
        self.persistent = persistent
        self.user_data_dir = user_data_dir
        self.launch_timeout = launch_timeout
        self.action_timeout = action_timeout
        self.screenshot_dir = screenshot_dir
        
        # Trace 配置
        self.trace_enabled = trace_enabled
        self.trace_dir = trace_dir
        self.trace_screenshots = trace_screenshots
        self.trace_snapshots = trace_snapshots
        self.trace_sources = trace_sources
        
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._stop_requested = False
        self._current_trace_path: Optional[str] = None
        self._page_errors: list[str] = []
        
        Path(self.user_data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.screenshot_dir).mkdir(parents=True, exist_ok=True)
        if self.trace_enabled:
            Path(self.trace_dir).mkdir(parents=True, exist_ok=True)
    
    async def init_browser(self) -> None:
        """初始化浏览器"""
        # 若上次未正常关闭，先释放，避免叠加启动多个 Chromium
        if self._context is not None or self._browser is not None:
            await self.close()

        if self._playwright is None:
            self._playwright = await async_playwright().start()
        
        browser_launcher = getattr(self._playwright, self.browser_type)
        
        if self.persistent:
            self._context = await browser_launcher.launch_persistent_context(
                self.user_data_dir,
                headless=self.headless,
                timeout=self.launch_timeout,
            )
            pages = self._context.pages
            self._page = pages[0] if pages else await self._context.new_page()
        else:
            self._browser = await browser_launcher.launch(
                headless=self.headless,
                timeout=self.launch_timeout,
            )
            self._context = await self._browser.new_context()
            self._page = await self._context.new_page()
        
        self._page.set_default_timeout(self.action_timeout)
        logger.info(f"浏览器已初始化: {self.browser_type}, headless={self.headless}")
    
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
        self._current_trace_path = None

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
        await self.init_browser()
        self._current_trace_path = None
        
        try:
            # 启动 Trace
            if self.trace_enabled and self._context:
                await self._context.tracing.start(
                    screenshots=self.trace_screenshots,
                    snapshots=self.trace_snapshots,
                    sources=self.trace_sources,
                )
                logger.debug(f"Trace 已启动: screenshots={self.trace_screenshots}, snapshots={self.trace_snapshots}")
            
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
        """请求停止执行"""
        self._stop_requested = True

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

        try:
            await locator.set_input_files(file_path)
            logger.info(f"步骤 {step.step_id}: 已通过 file input 设置上传文件")
            return
        except Exception as exc:
            if not self._is_non_file_input_upload_error(exc):
                raise

            logger.info(f"步骤 {step.step_id}: 当前定位器不是 file input，改用文件选择器事件上传")

        async with page.expect_file_chooser() as file_chooser_info:
            await locator.click()

        file_chooser = await file_chooser_info.value
        await file_chooser.set_files(file_path)
        logger.info(f"步骤 {step.step_id}: 已通过 file chooser 设置上传文件")
    
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

        operation = (step.operation_type or '').lower()
        screenshot_path: str | None = None
        
        # 等待时间（仅当用户明确设置 > 0 时才等待，用于特殊场景）
        # 注意：Playwright 自带 Auto-waiting，一般不需要手动等待
        if step.wait_time > 0:
            logger.debug(f"步骤 {step.step_id}: 强制等待 {step.wait_time}s（建议设为0让Playwright自动等待）")
            await page.wait_for_timeout(int(step.wait_time * 1000))
        
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
            """解析等待时间（毫秒）"""
            if not value:
                return 1000  # 默认 1 秒
            try:
                return int(float(value))
            except ValueError:
                return 1000

        page_operations = {
            'goto': lambda: page.goto(step.input_value),
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
        target = page
        if step.is_iframe and step.iframe_locator:
            logger.info(f"切换至 iframe 上下文, 表达式: {step.iframe_locator}")
            iframe_selectors = [step.iframe_locator]
            if ">>>" in step.iframe_locator:
                iframe_selectors = [s.strip() for s in step.iframe_locator.split(">>>") if s.strip()]
            elif ">>" in step.iframe_locator:
                iframe_selectors = [s.strip() for s in step.iframe_locator.split(">>") if s.strip()]

            for selector in iframe_selectors:
                target = target.frame_locator(selector)

        locators_to_try = [
            (step.locator_type, step.locator_value, step.locator_index),
        ]
        if step.locator_type_2 and step.locator_value_2:
            locators_to_try.append((step.locator_type_2, step.locator_value_2, step.locator_index_2))
        if step.locator_type_3 and step.locator_value_3:
            locators_to_try.append((step.locator_type_3, step.locator_value_3, step.locator_index_3))

        locator = None
        locator_type_used = step.locator_type
        locator_value_used = step.locator_value

        for idx, (locator_type, locator_value, locator_index) in enumerate(locators_to_try, start=1):
            if not locator_value or not locator_value.strip():
                continue

            logger.info(
                f"步骤 {step.step_id}: 尝试定位器 {idx} [{locator_type}={locator_value}]"
                + (f" 下标 {locator_index}" if locator_index is not None else "")
            )
            candidate = self._get_locator(target, locator_type, locator_value)
            if locator_index is not None:
                candidate = candidate.nth(locator_index)

            try:
                await candidate.wait_for(state="visible", timeout=5000 if idx == 1 else 2000)
                locator = candidate
                locator_type_used = locator_type
                locator_value_used = locator_value
                logger.info(f"步骤 {step.step_id}: 定位器 {idx} [{locator_type}={locator_value}] 可见并被成功选中")
                break
            except Exception as exc:
                logger.warning(f"步骤 {step.step_id}: 定位器 {idx} [{locator_type}={locator_value}] 尝试失败或不可见: {exc}")
                if idx == len(locators_to_try):
                    locator = candidate
                    locator_type_used = locator_type
                    locator_value_used = locator_value

        if locator is None:
            return False, f"所有定位器都失效（包含备用定位器，步骤: {step.description or step.step_id}）", None

        locator_time = time.time() - locator_start
        logger.debug(
            f"步骤 {step.step_id}: 定位元素 [{locator_type_used}={locator_value_used}] "
            f"耗时 {locator_time:.2f}s (iframe={step.is_iframe})"
        )
        
        element_operations = {
            'click': lambda: locator.click(),
            'dblclick': lambda: locator.dblclick(),
            'fill': lambda: locator.fill(step.input_value),
            'type': lambda: locator.type(step.input_value),
            'clear': lambda: locator.fill(""),
            'check': lambda: locator.check(),
            'uncheck': lambda: locator.uncheck(),
            'select': lambda: locator.select_option(step.input_value),
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
            }
            if assert_type in assert_operations:
                await assert_operations[assert_type]()
                logger.debug(f"步骤 {step.step_id}: assert_{assert_type} 耗时 {time.time() - op_start:.2f}s")
                return True, f"断言 {assert_type} 通过", None
        
        return False, f"未知操作类型: {operation}", None
    
    async def execute_step(self, step: StepConfig, page_url: str = '') -> StepResultModel:
        """执行单个步骤（独立浏览器会话）"""
        start_time = time.time()
        
        try:
            async with self.browser_session() as page:
                if page_url:
                    await page.goto(page_url)
                
                success, message, step_screenshot = await self._execute_step(page, step)
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
                    await self._page.goto(base_url, wait_until="networkidle")

                for page_step in config.page_steps:
                    if self._stop_requested:
                        raise Exception("用例被手动停止")

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
                            success, message, step_screenshot = await self._execute_step(
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

                    # 页面步骤执行完毕后，等待页面稳定（处理可能的页面跳转）
                    try:
                        await page.wait_for_load_state("load", timeout=10000)
                        await page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        logger.debug(f"页面步骤 {page_step.page_name} 执行后等待页面稳定超时，继续执行")

                duration = time.time() - start_time
                status = 'success' if failed_steps == 0 else 'failed'
                message = f"用例执行{'成功' if status == 'success' else '失败'}: 通过 {passed_steps}/{total_steps}"
                if self._page_errors:
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
        
        try:
            async with self.browser_session() as page:
                logger.info(f"开始执行页面步骤: {config.page_name}")
                self._page_errors = []
                self._setup_page_listeners(page)
                
                # 导航到页面
                if config.page_url:
                    nav_start = time.time()
                    await page.goto(config.page_url)
                    await page.wait_for_load_state("domcontentloaded")
                    logger.debug(f"页面导航 {config.page_name} 耗时 {time.time() - nav_start:.2f}s")
                
                # 执行页面内的所有步骤
                for step in config.steps:
                    step_start = time.time()
                    try:
                        success, message, step_screenshot = await self._execute_step(
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
                await page.goto(base_url, wait_until="networkidle")

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

                # 页面步骤执行完毕后，等待页面稳定（处理可能的页面跳转）
                try:
                    await page.wait_for_load_state("load", timeout=10000)
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    logger.debug(f"[并发] 页面步骤 {page_step.page_name} 执行后等待页面稳定超时，继续执行")

            duration = time.time() - start_time
            status = 'success' if failed_steps == 0 else 'failed'
            message = f"用例执行{'成功' if status == 'success' else '失败'}: 通过 {passed_steps}/{total_steps}"
            if self._page_errors:
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

        # 确保浏览器已初始化（非持久化模式）
        if self._playwright is None:
            self._playwright = await async_playwright().start()

        browser_launcher = getattr(self._playwright, self.browser_type)
        browser = await browser_launcher.launch(
            headless=self.headless,
            timeout=self.launch_timeout,
        )

        logger.info(f"[并发执行] 开始执行 {len(configs)} 个用例, 最大并发数: {max_concurrent}")

        async def run_with_limit(config: TestCaseConfig):
            async with semaphore:
                # 每个用例独立的浏览器上下文
                context = await browser.new_context()
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
            self._release_memory()
