"""
GUI 登录窗口模块

提供 CustomTkinter 图形界面登录功能，支持：
- 用户名/密码输入
- 服务器地址配置
- 登录验证
- 配置记忆
- 执行器设置（浏览器类型、无头模式等）
"""

from __future__ import annotations

import queue
import sys
import tkinter as tk
import threading
from pathlib import Path
from typing import Any

import customtkinter as ctk
import httpx
import tomli
import tomli_w


PAGE_BG = "#f5f7fa"
SURFACE = "#ffffff"
SECTION_BG = "#f8fafc"
CONTROL_BG = "#ffffff"
CONTROL_HOVER = "#f1f5f9"
CONTROL_BORDER = "#d7dee8"
CONTROL_BORDER_SOFT = "#e5e7eb"
TEXT = "#111827"
TEXT_MUTED = "#475569"
TEXT_SUBTLE = "#7f8ea3"
ACCENT = "#2563eb"
ACCENT_HOVER = "#1d4ed8"
ERROR = "#dc2626"
SUCCESS = "#16a34a"
INFO = "#2563eb"
FONT_FAMILY = "Microsoft YaHei UI"


def _patched_ctk_button_on_release(self, event=None) -> None:
    # WSLg/Wayland（Tk 9.0）下 <Enter> 跨越事件可能丢失或乱序，原生实现
    # 依赖 _mouse_inside 标志会静默吞掉真实点击，这里放宽为只要按钮可用即触发。
    if self._state != tk.DISABLED:
        self._on_leave()
        self._click_animation_running = True
        self.after(100, self._click_animation)
        if self._command is not None:
            self._command()


# 必须在实例化任何 CTkButton 之前替换：Tk bind 保存的是绑定时刻的绑定方法。
ctk.CTkButton._on_release = _patched_ctk_button_on_release

I18N: dict[str, dict[str, str]] = {
    "zh": {
        "window_title": "WHartTest 执行器",
        "language_toggle": "EN",
        "connection_title": "连接配置",
        "connection_subtitle": "后端 API、登录账号和执行器标识",
        "actuator_name": "执行器名称（留空则自动生成）",
        "actuator_name_placeholder": "例如: WHartTest-001",
        "server_url": "服务器地址",
        "username": "用户名",
        "password": "密码",
        "password_placeholder": "请输入密码",
        "show_password": "显示密码",
        "browser_title": "浏览器设置",
        "browser_subtitle": "Playwright 浏览器、超时和重试",
        "browser_type": "浏览器类型",
        "log_level": "日志级别",
        "launch_timeout": "启动超时（秒）",
        "action_timeout": "操作超时（秒）",
        "retry_count": "失败重试次数",
        "step_interval": "步骤间隔（毫秒）",
        "execution_title": "执行设置",
        "execution_subtitle": "运行方式、批量并发和 Trace 录制",
        "max_concurrent": "批量并发",
        "headless": "无头",
        "persistent": "持久化",
        "trace_screenshots": "截图",
        "trace_sources": "源码",
        "login_start": "登录并启动",
        "logging_in_short": "登录中...",
        "logging_in": "正在登录...",
        "login_success": "登录成功",
        "enter_server": "请输入服务器地址",
        "server_url_invalid": "服务器地址必须以 http:// 或 https:// 开头",
        "enter_username": "请输入用户名",
        "enter_password": "请输入密码",
        "login_response_error": "登录响应格式错误",
        "invalid_credentials": "用户名或密码错误",
        "server_error": "服务器错误: {detail}",
        "connect_error": "无法连接到服务器，请检查地址是否正确",
        "timeout_error": "连接超时，请检查网络",
        "login_failed": "登录失败: {detail}",
        "field_int": "{label}必须是整数",
        "field_range": "{label}范围必须是 {minimum}-{maximum}",
    },
    "en": {
        "window_title": "WHartTest Actuator",
        "language_toggle": "中文",
        "connection_title": "Connection",
        "connection_subtitle": "Backend API, account and actuator identity",
        "actuator_name": "Actuator name (auto if empty)",
        "actuator_name_placeholder": "e.g. WHartTest-001",
        "server_url": "Server URL",
        "username": "Username",
        "password": "Password",
        "password_placeholder": "Enter password",
        "show_password": "Show password",
        "browser_title": "Browser",
        "browser_subtitle": "Playwright browser, timeouts and retries",
        "browser_type": "Browser",
        "log_level": "Log level",
        "launch_timeout": "Launch (s)",
        "action_timeout": "Action (s)",
        "retry_count": "Retries",
        "step_interval": "Step gap (ms)",
        "execution_title": "Execution",
        "execution_subtitle": "Runtime mode, concurrency and Trace",
        "max_concurrent": "Concurrent",
        "headless": "Headless",
        "persistent": "Persist",
        "trace_screenshots": "Screens",
        "trace_sources": "Source",
        "login_start": "Login & Start",
        "logging_in_short": "Logging in...",
        "logging_in": "Logging in...",
        "login_success": "Login successful",
        "enter_server": "Enter server URL",
        "server_url_invalid": "Server URL must start with http:// or https://",
        "enter_username": "Enter username",
        "enter_password": "Enter password",
        "login_response_error": "Invalid login response",
        "invalid_credentials": "Invalid username or password",
        "server_error": "Server error: {detail}",
        "connect_error": "Cannot connect to server. Check the address.",
        "timeout_error": "Connection timed out. Check the network.",
        "login_failed": "Login failed: {detail}",
        "field_int": "{label} must be an integer",
        "field_range": "{label} must be between {minimum} and {maximum}",
    },
}


class LoginWindow(ctk.CTk):
    """执行器登录窗口。"""

    def __init__(self, config_path: str = "config.toml"):
        super().__init__()
        self.config_path = Path(config_path)
        self._config = self._load_config()
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._result: dict[str, Any] | None = None
        self._pending_values: dict[str, Any] | None = None
        self._login_queue: queue.Queue[tuple[str, str, str]] = queue.Queue()
        self._logo_image: tk.PhotoImage | None = None
        self._is_loading = False
        self._password_visible = False
        self._language = self._load_language()
        self._i18n_bindings: list[tuple[Any, str, str]] = []
        self._last_status: tuple[str, str, dict[str, Any]] | None = None

        self._init_ui()
        self._load_saved_credentials()

    def _load_config(self) -> dict[str, Any]:
        """加载配置文件。"""
        if self.config_path.exists():
            with open(self.config_path, "rb") as f:
                return tomli.load(f)
        return {}

    def _load_language(self) -> str:
        language = str(self._config.get("gui", {}).get("language", "zh")).lower()
        return language if language in I18N else "zh"

    def _save_config(self) -> None:
        """保存配置文件。"""
        with open(self.config_path, "wb") as f:
            tomli_w.dump(self._config, f)

    def _tr(self, key: str, **kwargs: Any) -> str:
        text = I18N[self._language].get(key, key)
        return text.format(**kwargs) if kwargs else text

    def _bind_i18n(self, widget: Any, option: str, key: str) -> None:
        self._i18n_bindings.append((widget, option, key))

    def _configure_i18n_widget(self, widget: Any, option: str, key: str) -> None:
        widget.configure(**{option: self._tr(key)})

    def _init_ui(self) -> None:
        """初始化界面。"""
        self.title(self._tr("window_title"))
        self.geometry("780x500")
        self.minsize(780, 500)
        self.resizable(True, False)
        self.configure(fg_color=PAGE_BG)
        self.option_add("*Font", f"{{{FONT_FAMILY}}} 10")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._logo_image = self._load_logo_image()
        if self._logo_image:
            self.iconphoto(True, self._logo_image)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_form_panel()

    def _build_form_panel(self) -> None:
        self._i18n_bindings.clear()
        page = ctk.CTkFrame(self, corner_radius=0, fg_color=PAGE_BG)
        page.grid(row=0, column=0, sticky="nsew", padx=10, pady=8)
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(0, weight=1)

        form_card = ctk.CTkFrame(
            page,
            fg_color=SURFACE,
            border_width=1,
            border_color=CONTROL_BORDER_SOFT,
            corner_radius=8,
        )
        form_card.grid(row=0, column=0, sticky="nsew")
        form_card.grid_columnconfigure(0, weight=1)
        form_card.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkFrame(
            form_card,
            fg_color=SURFACE,
        )
        scroll.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 2))
        scroll.grid_columnconfigure(0, weight=1)

        toolbar = ctk.CTkFrame(scroll, fg_color=SURFACE)
        toolbar.grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=(0, 3))
        toolbar.grid_columnconfigure(0, weight=1)
        self.language_btn = ctk.CTkButton(
            toolbar,
            text=self._tr("language_toggle"),
            width=64,
            height=26,
            corner_radius=6,
            fg_color=CONTROL_HOVER,
            hover_color="#e2e8f0",
            text_color=TEXT_MUTED,
            font=self._font(12, "bold"),
            command=self._toggle_language,
        )
        self.language_btn.grid(row=0, column=0, sticky="e")
        self._bind_i18n(self.language_btn, "text", "language_toggle")

        row = 1
        connection_card = self._section_card(
            scroll,
            "connection_title",
            "connection_subtitle",
            row,
            columns=6,
        )
        row += 1
        self.actuator_name_input = self._entry(
            connection_card,
            "actuator_name",
            "actuator_name_placeholder",
            row=0,
            column=0,
            columnspan=3,
        )
        self.api_url_input = self._entry(
            connection_card,
            "server_url",
            "http://127.0.0.1:8000",
            row=0,
            column=3,
            columnspan=3,
        )
        self.username_input = self._entry(connection_card, "username", "admin", row=2, column=0, columnspan=3)
        self.password_input = self._entry(
            connection_card,
            "password",
            "password_placeholder",
            row=2,
            column=3,
            columnspan=3,
            label_columnspan=2,
            show="*",
        )
        self.show_password_checkbox = self._checkbox(
            connection_card,
            "show_password",
            row=2,
            column=5,
            command=self._toggle_password_visibility,
        )
        self.password_input.bind("<Return>", lambda _event: self._on_login_clicked())

        browser_card = self._section_card(scroll, "browser_title", "browser_subtitle", row, columns=6)
        row += 1
        self.browser_type_combo = self._combo(browser_card, "browser_type", ["chromium", "firefox", "webkit"], 0, 0)
        self.log_level_combo = self._combo(browser_card, "log_level", ["DEBUG", "INFO", "WARNING", "ERROR"], 0, 1)
        self.launch_timeout_input = self._entry(browser_card, "launch_timeout", "30", row=0, column=2)
        self.action_timeout_input = self._entry(browser_card, "action_timeout", "30", row=0, column=3)
        self.retry_count_input = self._entry(browser_card, "retry_count", "3", row=0, column=4)
        self.step_interval_input = self._entry(browser_card, "step_interval", "500", row=0, column=5)

        execution_card = self._section_card(scroll, "execution_title", "execution_subtitle", row, columns=7)
        row += 1
        self.max_concurrent_input = self._entry(execution_card, "max_concurrent", "3", row=0, column=0)
        self.headless_switch = self._switch(execution_card, "headless", 1, 1)
        self.persistent_switch = self._switch(execution_card, "persistent", 1, 2)
        self.trace_switch = self._switch(execution_card, "Trace", 1, 3)
        self.trace_screenshots_switch = self._switch(execution_card, "trace_screenshots", 1, 4)
        self.trace_snapshots_switch = self._switch(execution_card, "DOM", 1, 5)
        self.trace_sources_switch = self._switch(execution_card, "trace_sources", 1, 6)

        footer = ctk.CTkFrame(form_card, fg_color=SURFACE)
        footer.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))
        footer.grid_columnconfigure(0, weight=1)
        footer.grid_columnconfigure(1, weight=0)
        footer.grid_columnconfigure(2, weight=1)

        self.status_label = ctk.CTkLabel(
            footer,
            text="",
            anchor="center",
            text_color=ERROR,
            font=self._font(12),
        )
        self.status_label.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(4, 0))

        self.login_btn = ctk.CTkButton(
            footer,
            text=self._tr("login_start"),
            width=140,
            height=34,
            corner_radius=6,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color=SURFACE,
            font=self._font(13, "bold"),
            command=self._on_login_clicked,
        )
        self.login_btn.grid(row=0, column=1, sticky="")
        self._bind_i18n(self.login_btn, "text", "login_start")

    def _font(self, size: int, weight: str = "normal") -> ctk.CTkFont:
        return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)

    def _toggle_language(self) -> None:
        self._language = "en" if self._language == "zh" else "zh"
        self._config.setdefault("gui", {})["language"] = self._language
        self._save_config()
        self._apply_language()

    def _apply_language(self) -> None:
        self.title(self._tr("window_title"))
        for widget, option, key in self._i18n_bindings:
            self._configure_i18n_widget(widget, option, key)

        if self._is_loading:
            self.login_btn.configure(text=self._tr("logging_in_short"))
        else:
            self.login_btn.configure(text=self._tr("login_start"))

        if self._last_status:
            key, color, kwargs = self._last_status
            self.status_label.configure(text=self._tr(key, **kwargs), text_color=color)

    def _entry(
        self,
        parent: ctk.CTkFrame,
        label: str,
        placeholder: str,
        row: int,
        column: int = 0,
        columnspan: int = 1,
        label_columnspan: int | None = None,
        show: str | None = None,
    ) -> ctk.CTkEntry:
        label_span = columnspan if label_columnspan is None else label_columnspan
        label_widget = ctk.CTkLabel(
            parent,
            text=self._tr(label),
            anchor="w",
            text_color=TEXT_MUTED,
            font=self._font(12, "bold"),
        )
        label_widget.grid(row=row, column=column, columnspan=label_span, sticky="ew", pady=(3, 2), padx=5)
        self._bind_i18n(label_widget, "text", label)

        entry = ctk.CTkEntry(
            parent,
            width=1,
            height=30,
            corner_radius=6,
            border_width=1,
            fg_color=CONTROL_BG,
            border_color=CONTROL_BORDER,
            text_color=TEXT,
            placeholder_text_color=TEXT_SUBTLE,
            font=self._font(12),
            placeholder_text=self._tr(placeholder),
            show=show,
        )
        self._bind_i18n(entry, "placeholder_text", placeholder)
        entry.grid(
            row=row + 1,
            column=column,
            columnspan=columnspan,
            sticky="ew",
            padx=5,
            pady=(0, 0),
        )
        return entry

    def _checkbox(
        self,
        parent: ctk.CTkFrame,
        text: str,
        row: int,
        column: int,
        command: Any | None = None,
    ) -> ctk.CTkCheckBox:
        checkbox = ctk.CTkCheckBox(
            parent,
            text=self._tr(text),
            width=110,
            height=20,
            checkbox_width=14,
            checkbox_height=14,
            corner_radius=3,
            border_width=1,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            border_color=CONTROL_BORDER,
            checkmark_color=SURFACE,
            text_color=TEXT_MUTED,
            font=self._font(12),
            command=command,
        )
        checkbox.grid(row=row, column=column, sticky="e", padx=5, pady=(3, 2))
        self._bind_i18n(checkbox, "text", text)
        return checkbox

    def _combo(
        self,
        parent: ctk.CTkFrame,
        label: str,
        values: list[str],
        row: int,
        column: int,
    ) -> ctk.CTkComboBox:
        label_widget = ctk.CTkLabel(
            parent,
            text=self._tr(label),
            anchor="w",
            text_color=TEXT_MUTED,
            font=self._font(12, "bold"),
        )
        label_widget.grid(row=row, column=column, sticky="ew", pady=(3, 2), padx=5)
        self._bind_i18n(label_widget, "text", label)
        combo = ctk.CTkComboBox(
            parent,
            values=values,
            width=1,
            height=30,
            corner_radius=6,
            border_width=1,
            fg_color=CONTROL_BG,
            border_color=CONTROL_BORDER,
            button_color="#e5e7eb",
            button_hover_color="#dbeafe",
            dropdown_fg_color=SURFACE,
            dropdown_hover_color="#eff6ff",
            text_color=TEXT,
            font=self._font(12),
            dropdown_font=self._font(12),
        )
        combo.grid(row=row + 1, column=column, sticky="ew", padx=5, pady=(0, 0))
        self._attach_dropdown_width_sync(combo)
        return combo

    def _attach_dropdown_width_sync(self, combo: ctk.CTkComboBox) -> None:
        # CTk uses a Tk Menu for the dropdown, whose width is character-based.
        # Sync it against the stretched combobox width before the menu opens.
        original_open = combo._open_dropdown_menu

        def sync(_event: tk.Event | None = None) -> None:
            self._sync_combo_dropdown_width(combo)

        def open_with_synced_width() -> None:
            self._sync_combo_dropdown_width(combo)
            original_open()

        combo._open_dropdown_menu = open_with_synced_width
        combo._entry.bind("<Configure>", sync, add="+")
        combo._canvas.bind("<Configure>", sync, add="+")
        self.after_idle(sync)

    def _sync_combo_dropdown_width(self, combo: ctk.CTkComboBox) -> None:
        menu = getattr(combo, "_dropdown_menu", None)
        if menu is None:
            return

        target_width = combo.winfo_width()
        if target_width <= 1:
            return

        values = combo.cget("values") or []
        cache_key = (target_width, tuple(values))
        if getattr(combo, "_dropdown_width_cache_key", None) == cache_key:
            return

        min_chars = max((len(str(value)) for value in values), default=1)
        best_chars = min_chars
        best_delta = float("inf")
        max_chars = max(min_chars + 8, int(target_width / 3) + min_chars)

        for chars in range(min_chars, max_chars + 1):
            menu.configure(min_character_width=chars)
            menu.update_idletasks()
            requested_width = menu.winfo_reqwidth()
            delta = abs(requested_width - target_width)
            if delta < best_delta:
                best_delta = delta
                best_chars = chars
            if requested_width >= target_width and chars > min_chars:
                break

        menu.configure(min_character_width=best_chars)
        combo._dropdown_width_cache_key = cache_key

    def _switch(
        self,
        parent: ctk.CTkFrame,
        text: str,
        row: int,
        column: int,
    ) -> ctk.CTkSwitch:
        switch = ctk.CTkSwitch(
            parent,
            text=self._tr(text),
            font=self._font(12),
            text_color=TEXT_MUTED,
            fg_color="#d1d5db",
            progress_color=ACCENT,
            button_color=SURFACE,
            button_hover_color=CONTROL_HOVER,
        )
        switch.grid(row=row, column=column, sticky="w", padx=5, pady=3)
        self._bind_i18n(switch, "text", text)
        return switch

    def _section_card(
        self,
        parent: ctk.CTkFrame,
        title: str,
        subtitle: str,
        row: int,
        columns: int,
    ) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            parent,
            fg_color=SECTION_BG,
            border_width=1,
            border_color=CONTROL_BORDER_SOFT,
            corner_radius=6,
        )
        card.grid(row=row, column=0, sticky="ew", padx=(0, 8), pady=(0, 4))
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=1)

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(4, 0))
        header.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            header,
            text=self._tr(title),
            anchor="w",
            text_color=TEXT,
            font=self._font(13, "bold"),
        )
        title_label.grid(row=0, column=0, sticky="w")
        self._bind_i18n(title_label, "text", title)
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=(0, 4))
        content.grid_columnconfigure(tuple(range(columns)), weight=1, uniform="form")
        return content

    def _load_logo_image(self) -> tk.PhotoImage | None:
        """加载与 Web 登录页一致的品牌图标，失败时回退到文字 Logo。"""
        if getattr(sys, "frozen", False):
            base_path = Path(sys.executable).parent
        else:
            base_path = Path(__file__).resolve().parents[1]
        candidates = [
            base_path / "data" / "WHartTest.png",
            base_path.parent / "WHartTest_Vue" / "public" / "WHartTest.png",
        ]
        for path in candidates:
            if not path.exists():
                continue
            try:
                return tk.PhotoImage(file=str(path))
            except tk.TclError:
                continue
        return None

    def _load_saved_credentials(self) -> None:
        """加载保存的凭证和设置。"""
        server = self._config.get("server", {})
        self._set_entry(self.api_url_input, server.get("api_url", "http://127.0.0.1:8000"))
        self._set_entry(self.username_input, server.get("api_username", ""))
        self._set_entry(self.password_input, server.get("api_password", ""))

        actuator = self._config.get("actuator", {})
        self._set_entry(self.actuator_name_input, actuator.get("name", ""))

        browser = self._config.get("browser", {})
        self.browser_type_combo.set(browser.get("browser_type", "chromium"))
        self._set_switch(self.headless_switch, browser.get("headless", False))
        self._set_switch(self.persistent_switch, browser.get("persistent", True))
        self._set_entry(self.launch_timeout_input, browser.get("launch_timeout", 30))
        self._set_entry(self.action_timeout_input, browser.get("action_timeout", 30))

        execution = self._config.get("execution", {})
        self._set_entry(self.retry_count_input, execution.get("retry_count", 3))
        self._set_entry(self.step_interval_input, execution.get("step_interval", 500))
        self._set_entry(self.max_concurrent_input, execution.get("max_concurrent", 3))

        trace = self._config.get("trace", {})
        self._set_switch(self.trace_switch, trace.get("enabled", True))
        self._set_switch(self.trace_screenshots_switch, trace.get("screenshots", True))
        self._set_switch(self.trace_snapshots_switch, trace.get("snapshots", True))
        self._set_switch(self.trace_sources_switch, trace.get("sources", False))

        logging_cfg = self._config.get("logging", {})
        self.log_level_combo.set(logging_cfg.get("level", "INFO"))

    def _set_entry(self, entry: ctk.CTkEntry, value: Any) -> None:
        entry.delete(0, "end")
        entry.insert(0, str(value))

    def _set_switch(self, switch: ctk.CTkSwitch, enabled: bool) -> None:
        if enabled:
            switch.select()
        else:
            switch.deselect()

    def _toggle_password_visibility(self) -> None:
        if self._is_loading:
            return
        self._password_visible = bool(self.show_password_checkbox.get())
        self.password_input.configure(show="" if self._password_visible else "*")

    def _on_login_clicked(self) -> None:
        """登录按钮点击处理。"""
        if self._is_loading:
            return

        try:
            values = self._collect_form_values()
        except ValueError as exc:
            self._show_error(str(exc))
            return

        self._pending_values = values
        self._set_loading(True)
        self._show_status_key("logging_in", INFO)

        thread = threading.Thread(
            target=self._login_worker,
            args=(values["api_url"], values["username"], values["password"]),
            daemon=True,
        )
        thread.start()
        self.after(100, self._poll_login_queue)

    def _login_worker(self, api_url: str, username: str, password: str) -> None:
        """后台执行登录验证。"""
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.post(
                    f"{api_url.rstrip('/')}/api/token/",
                    json={"username": username, "password": password},
                )

            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    access = data["data"]["access"]
                    refresh = data["data"].get("refresh", "")
                else:
                    access = data.get("access", "")
                    refresh = data.get("refresh", "")

                if access:
                    self._login_queue.put(("success", access, refresh))
                else:
                    self._login_queue.put(("failed", "login_response_error", ""))
            elif resp.status_code == 401:
                self._login_queue.put(("failed", "invalid_credentials", ""))
            else:
                self._login_queue.put(("failed", "server_error", str(resp.status_code)))
        except httpx.ConnectError:
            self._login_queue.put(("failed", "connect_error", ""))
        except httpx.TimeoutException:
            self._login_queue.put(("failed", "timeout_error", ""))
        except Exception as exc:  # noqa: BLE001 - 登录错误需要展示给用户
            self._login_queue.put(("failed", "login_failed", str(exc)))

    def _poll_login_queue(self) -> None:
        if not self._is_loading:
            return

        try:
            status, first, second = self._login_queue.get_nowait()
        except queue.Empty:
            self.after(100, self._poll_login_queue)
            return

        if status == "success":
            self._on_login_success(first, second)
        else:
            self._on_login_failed(first, second)

    def _on_login_success(self, access_token: str, refresh_token: str) -> None:
        """登录成功处理。"""
        self._access_token = access_token
        self._refresh_token = refresh_token
        values = self._pending_values or self._collect_form_values()

        self._save_config_values(values)
        self._result = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            **values,
        }

        self._show_status_key("login_success", SUCCESS)
        self.after(180, self._close_dialog)

    def _on_login_failed(self, error_key: str, detail: str = "") -> None:
        """登录失败处理。"""
        self._set_loading(False)
        self._show_status_key(error_key, ERROR, detail=detail)

    def _collect_form_values(self) -> dict[str, Any]:
        api_url = self.api_url_input.get().strip()
        username = self.username_input.get().strip()
        password = self.password_input.get()

        if not api_url:
            raise ValueError(self._tr("enter_server"))
        if not api_url.startswith(("http://", "https://")):
            raise ValueError(self._tr("server_url_invalid"))
        if not username:
            raise ValueError(self._tr("enter_username"))
        if not password:
            raise ValueError(self._tr("enter_password"))

        return {
            "api_url": api_url.rstrip("/"),
            "actuator_name": self.actuator_name_input.get().strip(),
            "username": username,
            "password": password,
            "browser_type": self.browser_type_combo.get(),
            "headless": bool(self.headless_switch.get()),
            "persistent": bool(self.persistent_switch.get()),
            "trace_enabled": bool(self.trace_switch.get()),
            "trace_screenshots": bool(self.trace_screenshots_switch.get()),
            "trace_snapshots": bool(self.trace_snapshots_switch.get()),
            "trace_sources": bool(self.trace_sources_switch.get()),
            "launch_timeout": self._read_int(self.launch_timeout_input, "launch_timeout", 10, 120),
            "action_timeout": self._read_int(self.action_timeout_input, "action_timeout", 5, 60),
            "retry_count": self._read_int(self.retry_count_input, "retry_count", 0, 10),
            "step_interval": self._read_int(self.step_interval_input, "step_interval", 0, 5000),
            "max_concurrent": self._read_int(self.max_concurrent_input, "max_concurrent", 1, 10),
            "log_level": self.log_level_combo.get(),
        }

    def _read_int(
        self,
        entry: ctk.CTkEntry,
        label_key: str,
        minimum: int,
        maximum: int,
    ) -> int:
        raw_value = entry.get().strip()
        label = self._tr(label_key)
        try:
            value = int(raw_value)
        except ValueError as exc:
            raise ValueError(self._tr("field_int", label=label)) from exc

        if value < minimum or value > maximum:
            raise ValueError(self._tr("field_range", label=label, minimum=minimum, maximum=maximum))
        return value

    def _save_config_values(self, values: dict[str, Any]) -> None:
        server = self._config.setdefault("server", {})
        server["api_url"] = values["api_url"]
        server["api_username"] = values["username"]
        server["api_password"] = values["password"]

        actuator = self._config.setdefault("actuator", {})
        if values["actuator_name"]:
            actuator["name"] = values["actuator_name"]
        else:
            actuator.pop("name", None)

        browser = self._config.setdefault("browser", {})
        browser["browser_type"] = values["browser_type"]
        browser["headless"] = values["headless"]
        browser["persistent"] = values["persistent"]
        browser["launch_timeout"] = values["launch_timeout"]
        browser["action_timeout"] = values["action_timeout"]

        execution = self._config.setdefault("execution", {})
        execution["retry_count"] = values["retry_count"]
        execution["step_interval"] = values["step_interval"]
        execution["max_concurrent"] = values["max_concurrent"]

        trace = self._config.setdefault("trace", {})
        trace["enabled"] = values["trace_enabled"]
        trace["screenshots"] = values["trace_screenshots"]
        trace["snapshots"] = values["trace_snapshots"]
        trace["sources"] = values["trace_sources"]

        logging_cfg = self._config.setdefault("logging", {})
        logging_cfg["level"] = values["log_level"]

        gui_cfg = self._config.setdefault("gui", {})
        gui_cfg["language"] = self._language

        self._save_config()

    def _set_loading(self, loading: bool) -> None:
        """设置加载状态。"""
        self._is_loading = loading
        state = "disabled" if loading else "normal"
        button_text = self._tr("logging_in_short" if loading else "login_start")
        self.login_btn.configure(state=state, text=button_text)
        for widget in (
            self.api_url_input,
            self.username_input,
            self.password_input,
            self.show_password_checkbox,
        ):
            widget.configure(state=state)

    def _show_error(self, message: str) -> None:
        self._last_status = None
        self._show_status(message, ERROR)

    def _show_status_key(self, key: str, color: str, **kwargs: Any) -> None:
        self._last_status = (key, color, kwargs)
        self._show_status(self._tr(key, **kwargs), color)

    def _show_status(self, message: str, color: str) -> None:
        self.status_label.configure(text=message, text_color=color)

    def _on_close(self) -> None:
        self._result = None
        self._close_dialog()

    def _close_dialog(self) -> None:
        self._is_loading = False
        self.withdraw()
        self.quit()

    @property
    def result(self) -> dict[str, Any] | None:
        return self._result


def show_login_dialog(config_path: str = "config.toml") -> dict[str, Any] | None:
    """
    显示登录对话框。

    Returns:
        成功返回包含登录信息和配置的字典，取消或失败返回 None。
    """
    ctk.set_appearance_mode("Light")
    ctk.set_default_color_theme("blue")
    login_window = LoginWindow(config_path)
    login_window.mainloop()
    result = login_window.result
    login_window.destroy()
    return result


if __name__ == "__main__":
    result = show_login_dialog()
    if result:
        print(f"登录成功: {result['username']} @ {result['api_url']}")
        print(f"执行器名称: {result['actuator_name'] or '(自动生成)'}")
        print(f"Token: {result['access_token'][:20]}...")
        print(f"浏览器: {result['browser_type']}, 无头: {result['headless']}, 持久化: {result['persistent']}")
        print(f"Trace: {result['trace_enabled']}, 截图: {result['trace_screenshots']}, 快照: {result['trace_snapshots']}")
        print(f"超时: {result['launch_timeout']}s/{result['action_timeout']}s, 并发: {result['max_concurrent']}")
        print(f"重试: {result['retry_count']}, 步骤间隔: {result['step_interval']}ms, 日志: {result['log_level']}")
    else:
        print("登录取消或失败")
