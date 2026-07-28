#!/usr/bin/env python
"""
UI自动化执行器 - 主入口

启动方式:
    # 使用配置文件
    python main.py
    python main.py --config config.toml
    
    # 使用命令行参数（覆盖配置文件）
    python main.py --server ws://localhost:8000/ws/ui/actuator/
    python main.py --server ws://localhost:8000/ws/ui/actuator/ --id my-actuator
    
    # 打包成 exe 后运行
    WHartTest_Actuator.exe --gui
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any

# 添加当前目录到路径（支持打包后运行）
if getattr(sys, 'frozen', False):
    # 打包后的 exe
    _base_path = Path(sys.executable).parent
    os.chdir(_base_path)
else:
    _base_path = Path(__file__).parent
sys.path.insert(0, str(_base_path))

# 导入浏览器安装模块（必须在其他模块之前）
from browser_installer import setup_playwright_env, ensure_browser

from websocket_client import WebSocketClient
from consumer import TaskConsumer

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # fallback for older Python
    except ImportError:
        tomllib = None


def get_resource_path(relative_path: str) -> Path:
    """获取源码或 PyInstaller onefile 临时目录中的资源路径。"""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / relative_path
    return _base_path / relative_path


def resolve_config_path(config_path: str) -> Path:
    """解析配置文件路径；打包后默认落在 exe 同级目录。"""
    path = Path(config_path)
    if path.is_absolute():
        return path
    if getattr(sys, 'frozen', False):
        return _base_path / path
    return path


def ensure_config_file(config_path: Path) -> None:
    """首次启动时生成配置文件。"""
    if config_path.exists():
        return

    example_path = get_resource_path('config.example.toml')
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if example_path.exists():
        config_path.write_bytes(example_path.read_bytes())
        return

    config_path.write_text(
        """# UI自动化执行器配置文件

[server]
ws_url = "ws://127.0.0.1:8000/ws/ui/actuator/"
api_url = "http://127.0.0.1:8000"
use_gui = true
api_username = "admin"
api_password = "admin123"

[actuator]

[browser]
browser_type = "chromium"
headless = false
persistent = true
user_data_dir = "./data/browser"
launch_timeout = 30
action_timeout = 30

[execution]
retry_count = 3
step_interval = 500
screenshot_dir = "./data/screenshots"
max_concurrent = 3

[trace]
enabled = true
trace_dir = "./data/traces"
screenshots = true
snapshots = true
sources = false

[logging]
level = "INFO"

[gui]
language = "zh"
""",
        encoding='utf-8',
    )


class Config:
    """配置类"""
    
    def __init__(self):
        # 默认配置
        self.ws_url = "ws://127.0.0.1:8000/ws/ui/actuator/"
        self.api_url = "http://127.0.0.1:8000"
        # 打包成 exe 时默认启用 GUI 登录，开发模式默认关闭
        self.use_gui = getattr(sys, 'frozen', False)
        self.api_username = "admin"
        self.api_password = "admin123"
        self.actuator_id: str | None = None
        self.actuator_name: str | None = None
        self.actuator_description: str | None = None
        
        # 浏览器配置
        self.browser_type = "chromium"
        self.headless = False
        self.persistent = True
        self.user_data_dir = "./data/browser"
        self.launch_timeout = 30
        self.action_timeout = 30
        
        # 执行配置
        self.retry_count = 3
        self.step_interval = 500
        self.screenshot_dir = "./data/screenshots"
        self.max_concurrent = 3  # 批量执行最大并发数
        
        # Trace 配置
        self.trace_enabled = True
        self.trace_dir = "./data/traces"
        self.trace_screenshots = True
        self.trace_snapshots = True
        self.trace_sources = False
        
        # 日志配置
        self.log_level = "INFO"
        self.log_file: str | None = None
    
    def load_from_toml(self, filepath: str) -> None:
        """从TOML文件加载配置"""
        if not tomllib:
            logging.warning("tomllib/tomli 未安装，跳过配置文件加载")
            return
            
        path = Path(filepath)
        if not path.exists():
            logging.info(f"配置文件不存在: {filepath}")
            return
            
        with open(path, 'rb') as f:
            data = tomllib.load(f)
        
        # 服务器配置
        if 'server' in data:
            self.ws_url = data['server'].get('ws_url', self.ws_url)
            self.api_url = data['server'].get('api_url', self.api_url)
            self.use_gui = data['server'].get('use_gui', self.use_gui)
            self.api_username = data['server'].get('api_username', self.api_username)
            self.api_password = data['server'].get('api_password', self.api_password)
        
        # 执行器配置
        if 'actuator' in data:
            self.actuator_name = data['actuator'].get('name')
            self.actuator_description = data['actuator'].get('description')
        
        # 浏览器配置
        if 'browser' in data:
            browser = data['browser']
            self.browser_type = browser.get('browser_type', self.browser_type)
            self.headless = browser.get('headless', self.headless)
            self.persistent = browser.get('persistent', self.persistent)
            self.user_data_dir = browser.get('user_data_dir', self.user_data_dir)
            self.launch_timeout = browser.get('launch_timeout', self.launch_timeout)
            self.action_timeout = browser.get('action_timeout', self.action_timeout)
        
        # 执行配置
        if 'execution' in data:
            execution = data['execution']
            self.retry_count = execution.get('retry_count', self.retry_count)
            self.step_interval = execution.get('step_interval', self.step_interval)
            self.screenshot_dir = execution.get('screenshot_dir', self.screenshot_dir)
            self.max_concurrent = execution.get('max_concurrent', self.max_concurrent)
        
        # Trace 配置
        if 'trace' in data:
            trace = data['trace']
            self.trace_enabled = trace.get('enabled', self.trace_enabled)
            self.trace_dir = trace.get('trace_dir', self.trace_dir)
            self.trace_screenshots = trace.get('screenshots', self.trace_screenshots)
            self.trace_snapshots = trace.get('snapshots', self.trace_snapshots)
            self.trace_sources = trace.get('sources', self.trace_sources)
        
        # 日志配置
        if 'logging' in data:
            self.log_level = data['logging'].get('level', self.log_level)
            self.log_file = data['logging'].get('file')
    
    def apply_args(self, args: argparse.Namespace) -> None:
        """应用命令行参数（覆盖配置文件）"""
        if args.server:
            self.ws_url = args.server
        if args.api:
            self.api_url = args.api
        if args.id:
            self.actuator_id = args.id
        if args.gui:
            self.use_gui = True
        if args.no_gui:
            self.use_gui = False
        if args.log_level:
            self.log_level = args.log_level


def setup_logging(level: str = 'INFO', log_file: str | None = None):
    """配置日志"""
    handlers = [logging.StreamHandler()]
    
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
    
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=handlers
    )


def ensure_runtime_dirs(config: Config) -> None:
    """创建运行时目录。"""
    for dir_path in (
        config.user_data_dir,
        config.screenshot_dir,
        config.trace_dir,
    ):
        Path(dir_path).mkdir(parents=True, exist_ok=True)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='UI自动化执行器')
    parser.add_argument(
        '--config', '-c',
        default='config.toml',
        help='配置文件路径 (默认: config.toml)'
    )
    parser.add_argument(
        '--server', '-s',
        default=None,
        help='WebSocket服务器地址 (覆盖配置文件)'
    )
    parser.add_argument(
        '--api', '-a',
        default=None,
        help='API服务器地址 (覆盖配置文件)'
    )
    parser.add_argument(
        '--id', '-i',
        default=None,
        help='执行器ID (覆盖配置文件)'
    )
    parser.add_argument(
        '--gui', '-g',
        action='store_true',
        default=None,
        help='启用 GUI 登录窗口 (覆盖配置文件)'
    )
    parser.add_argument(
        '--no-gui',
        action='store_true',
        default=None,
        help='禁用 GUI 登录窗口 (覆盖配置文件)'
    )
    parser.add_argument(
        '--log-level', '-l',
        default=None,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='日志级别 (覆盖配置文件)'
    )
    parser.add_argument(
        '--skip-browser-check',
        action='store_true',
        default=False,
        help='跳过浏览器安装检查'
    )
    return parser.parse_args()


async def main():
    """主函数"""
    args = parse_args()
    config_path = resolve_config_path(args.config)
    ensure_config_file(config_path)

    # 加载配置
    config = Config()
    config.load_from_toml(str(config_path))
    config.apply_args(args)

    # 配置日志
    setup_logging(config.log_level, config.log_file)
    ensure_runtime_dirs(config)
    logger = logging.getLogger('actuator')
    
    # 检查并安装浏览器（首次运行时需要）
    if not args.skip_browser_check:
        logger.info("检查浏览器安装状态...")
        if not ensure_browser(config.browser_type):
            logger.error(f"浏览器 {config.browser_type} 安装失败，请检查网络连接后重试")
            logger.error("或者手动运行: playwright install chromium")
            sys.exit(1)
    
    # GUI 登录模式
    if config.use_gui:
        try:
            from gui import show_login_dialog
        except ImportError as e:
            logger.error("GUI 模式需要安装 CustomTkinter: pip install customtkinter")
            logger.error(f"或者设置 use_gui = false 使用配置文件中的账号密码")
            logger.error(f"导入错误: {e}")
            sys.exit(1)

        logger.info("启动 GUI 登录窗口...")
        login_result = show_login_dialog(str(config_path))
        
        if not login_result:
            logger.info("用户取消登录")
            sys.exit(0)
        
        # 使用 GUI 登录获取的凭证更新配置
        config.api_url = login_result['api_url']
        # 根据 API URL 自动生成 WebSocket URL
        api_url = login_result['api_url'].rstrip('/')
        if api_url.startswith('https://'):
            ws_url = api_url.replace('https://', 'wss://', 1)
        else:
            ws_url = api_url.replace('http://', 'ws://', 1)
        config.ws_url = f"{ws_url}/ws/ui/actuator/"
        
        config.api_username = login_result['username']
        config.api_password = login_result['password']
        # 更新执行器名称
        if login_result.get('actuator_name'):
            config.actuator_name = login_result['actuator_name']
        # 更新浏览器配置
        config.browser_type = login_result.get('browser_type', config.browser_type)
        config.headless = login_result.get('headless', config.headless)
        config.persistent = login_result.get('persistent', config.persistent)
        config.launch_timeout = login_result.get('launch_timeout', config.launch_timeout)
        config.action_timeout = login_result.get('action_timeout', config.action_timeout)
        # 更新执行配置
        config.retry_count = login_result.get('retry_count', config.retry_count)
        config.step_interval = login_result.get('step_interval', config.step_interval)
        config.max_concurrent = login_result.get('max_concurrent', config.max_concurrent)
        # 更新 Trace 配置
        config.trace_enabled = login_result.get('trace_enabled', config.trace_enabled)
        config.trace_screenshots = login_result.get('trace_screenshots', config.trace_screenshots)
        config.trace_snapshots = login_result.get('trace_snapshots', config.trace_snapshots)
        config.trace_sources = login_result.get('trace_sources', config.trace_sources)
        # 更新日志配置
        config.log_level = login_result.get('log_level', config.log_level)
        
        logger.info(f"登录成功: {config.api_username} @ {config.api_url}")
    
    # 生成执行器ID
    actuator_id = config.actuator_id or f"actuator-{os.getpid()}"
    
    logger.info("=" * 50)
    logger.info("UI自动化执行器启动")
    logger.info(f"执行器ID: {actuator_id}")
    if config.actuator_name:
        logger.info(f"执行器名称: {config.actuator_name}")
    logger.info(f"WebSocket服务器: {config.ws_url}")
    logger.info(f"API服务器: {config.api_url}")
    logger.info(f"浏览器类型: {config.browser_type}")
    logger.info(f"无头模式: {config.headless}")
    logger.info("=" * 50)
    
    # 创建WebSocket客户端，传递配置
    ws_client = WebSocketClient(config.ws_url, actuator_id, config)
    
    # 创建任务消费者，传递配置
    consumer = TaskConsumer(
        ws_client, 
        config.api_url, 
        config,
        api_username=config.api_username,
        api_password=config.api_password
    )
    
    # 设置信号处理（Windows 不支持 add_signal_handler，使用 try/except 处理）
    if sys.platform != 'win32':
        loop = asyncio.get_event_loop()
        
        def signal_handler():
            logger.info("收到停止信号，正在关闭...")
            consumer.stop()
            asyncio.create_task(ws_client.disconnect())
        
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, signal_handler)
            except NotImplementedError:
                pass
    
    try:
        await consumer.run()
    except KeyboardInterrupt:
        logger.info("用户中断")
    except Exception as e:
        logger.error(f"执行器异常: {e}", exc_info=True)
    finally:
        # close_executor already logs failures internally
        await consumer.close_executor()
        await ws_client.disconnect()
        logger.info("执行器已停止")


if __name__ == '__main__':
    asyncio.run(main())
