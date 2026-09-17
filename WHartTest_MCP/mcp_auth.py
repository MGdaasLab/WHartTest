"""
WHartTest MCP 共享密钥鉴权（复用模块）

两个 MCP 入口（WHartTest_tools / ms_mcp_api）此前以 root 绑定 0.0.0.0 且无任何鉴权，
任何能触达端口的人都可以调用全部工具（含本地文件读取与后端 API 代理）。

这里提供一个统一入口：

- ``build_mcp_auth()``：构造 fastmcp 的 ``AuthProvider``（基于共享密钥的静态 token 校验）。
  未配置 ``MCP_SHARED_TOKEN`` 时返回 ``None`` 并告警——是否"裸奔"由入口显式决定，
  避免静默降级。
- ``enforce_auth_or_exit()``：生产安全口径。未配置密钥时直接退出进程（fail closed），
  除非显式设置 ``MCP_ALLOW_UNAUTHENTICATED=true``（仅限本机联调）。

客户端用法（与 Claude Code / DSH 的 MCP 配置一致）：在请求头加
``Authorization: Bearer <MCP_SHARED_TOKEN>``。
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("wharttest_mcp")

_TOKEN_ENV = "MCP_SHARED_TOKEN"
_ALLOW_OPEN_ENV = "MCP_ALLOW_UNAUTHENTICATED"


def get_shared_token() -> str:
    """读取共享密钥（环境变量），返回去除首尾空白后的值。"""
    return (os.getenv(_TOKEN_ENV, "") or "").strip()


def unauthenticated_allowed() -> bool:
    """是否显式允许无鉴权（仅限本机联调）。"""
    return (os.getenv(_ALLOW_OPEN_ENV, "") or "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def build_mcp_auth():
    """构造 fastmcp 鉴权提供者；未配置密钥时返回 ``None``。

    返回 ``None`` 不等于允许裸奔：调用方应配合 ``enforce_auth_or_exit``
    或明确记录告警。这里拆开是为了让入口能区分「未配置」与「配置错误」。
    """
    token = get_shared_token()
    if not token:
        return None

    try:
        from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
    except ImportError:  # fastmcp 版本较旧或未安装
        logger.error(
            "已配置 %s，但当前 fastmcp 版本不支持 StaticTokenVerifier；"
            "请升级 fastmcp>=2.11 后重试，或移除该变量并改用网络层隔离",
            _TOKEN_ENV,
        )
        raise

    # 单租户共享密钥：一个 token 对应固定身份；scopes 留空表示不参与授权细分
    return StaticTokenVerifier(
        tokens={
            token: {
                "client_id": "wharttest-mcp-client",
                "scopes": [],
            }
        }
    )


def enforce_auth_or_exit(service_name: str) -> None:
    """生产安全口径：未配置共享密钥且未显式允许裸奔时，直接退出。"""
    if get_shared_token():
        return
    if unauthenticated_allowed():
        logger.warning(
            "[%s] %s 未配置，且 %s=true：MCP 服务将以无鉴权模式启动。"
            "仅允许在本机联调环境使用，严禁暴露到任何网络。",
            service_name,
            _TOKEN_ENV,
            _ALLOW_OPEN_ENV,
        )
        return

    logger.error(
        "[%s] 检测到 MCP 服务将以 root 绑定 0.0.0.0 且无任何鉴权，已拒绝启动。"
        "请设置 %s=<随机长密钥>（客户端请求头用 Authorization: Bearer <同一密钥>）；"
        "若确属本机联调，可临时设置 %s=true。",
        service_name,
        _TOKEN_ENV,
        _ALLOW_OPEN_ENV,
    )
    raise SystemExit(2)
