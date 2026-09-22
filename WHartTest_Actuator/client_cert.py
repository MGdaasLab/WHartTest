"""
HTTPS 客户端证书支持 - 纯函数工具集

设计要点（勿随意改动，均为 Playwright 实际行为约束）：

1. Playwright Python 侧 ``client_certificates`` 接受的是 **dict**，且键名必须是
   **camelCase**（``origin`` / ``pfxPath`` / ``passphrase`` / ``certPath`` / ``keyPath``）。
   核实：``playwright/_impl/_network.py::to_client_certificates_protocol()``
   直接硬索引 ``clientCertificate["origin"]``，**不做 snake_case -> camelCase 转换**。
   写成 ``pfx_path`` 会被静默忽略 —— 证书不生效且不报错。这是本模块存在的首要原因。

2. ``origin`` 是必填项，且 Playwright 要求**精确匹配** ``https://host[:port]``，
   不支持通配。因此本模块只从真实 URL 推导 origin，推导不出就放弃（返回 ``[]``）。

3. 证书文件是在 ``new_context()`` 时才真正读取的。这里只做存在性/扩展名校验并返回
   告警，**不抛异常** —— 让调用方决定是降级还是阻断，避免因为一个可选特性把整个执行器搞挂。

本模块刻意不 import playwright、不 import 本项目其他模块，保持纯函数与零副作用，
以便单元测试可以零依赖直接运行。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlsplit

logger = logging.getLogger('actuator')

# 扩展名约定：仅用于给出告警，不做硬性阻断
PFX_EXTENSIONS = ('.pfx', '.p12', '.pfx.bin')
CERT_EXTENSIONS = ('.pem', '.crt', '.cer', '.cert')
KEY_EXTENSIONS = ('.key', '.pem')

DEFAULT_HTTPS_PORT = 443


def normalize_origin(url: Optional[str]) -> Optional[str]:
    """把任意 URL 归一化成 Playwright 需要的 origin（``https://host[:port]``）。

    仅接受 https；丢弃 path / query / fragment / userinfo；非 443 端口保留，
    443 显式端口去掉（``https://a.com:443`` 与 ``https://a.com`` 等价，统一为后者）。
    IPv6 主机重新加方括号。

    无法解析或非 https 时返回 ``None``。
    """
    if not url or not isinstance(url, str):
        return None

    raw = url.strip()
    if not raw:
        return None

    try:
        parts = urlsplit(raw)
    except ValueError:
        return None

    if parts.scheme.lower() != 'https':
        return None

    hostname = parts.hostname
    if not hostname:
        return None

    # urlsplit.hostname 会把 IPv6 的方括号剥掉，这里补回来
    if ':' in hostname:
        host = f'[{hostname}]'
    else:
        host = hostname

    try:
        port = parts.port
    except ValueError:
        return None

    if port is None or port == DEFAULT_HTTPS_PORT:
        return f'https://{host}'

    return f'https://{host}:{port}'


def parse_origins(*values: Optional[str]) -> list[str]:
    """把若干「逗号分隔的 origin 字符串」合并解析为去重、保序的 origin 列表。

    非 https 项与无法解析项被静默丢弃（调用方可通过返回值是否为空来判断）。
    """
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        if not value or not isinstance(value, str):
            continue
        for chunk in value.split(','):
            origin = normalize_origin(chunk)
            if origin and origin not in seen:
                seen.add(origin)
                result.append(origin)

    return result


def resolve_cert_path(path: Optional[str], base_dir: Optional[Path] = None) -> Optional[Path]:
    """解析证书文件路径。

    绝对路径原样返回；相对路径以 ``base_dir``（通常是 config.toml 所在目录）为基准拼接。
    ``base_dir`` 未提供时退回当前工作目录 —— 注意 frozen(exe) 场景 cwd 不可预期，
    因此调用方应始终显式传入 ``base_dir``。

    空值返回 ``None``。
    """
    if not path or not isinstance(path, str):
        return None

    raw = path.strip()
    if not raw:
        return None

    # 兼容 Windows 风格路径中的 ~
    expanded = os.path.expanduser(raw)
    candidate = Path(expanded)

    if candidate.is_absolute():
        return candidate

    base = Path(base_dir) if base_dir else Path.cwd()
    return (base / candidate).resolve()


def _extension_warning(path: Path, kind: str, allowed: tuple[str, ...]) -> Optional[str]:
    suffix = path.suffix.lower()
    if suffix in allowed:
        return None
    return (
        f"客户端证书 {kind} 文件扩展名 {suffix or '(无)'} 不在建议范围 "
        f"{'/'.join(allowed)} 内：{path}"
    )


def validate_cert_files(
    pfx_path: Optional[Path] = None,
    cert_path: Optional[Path] = None,
    key_path: Optional[Path] = None,
) -> list[str]:
    """校验证书文件是否存在、扩展名是否符合约定。

    返回告警字符串列表，**从不抛异常**。空列表表示无告警。
    """
    warnings: list[str] = []

    if pfx_path is not None:
        if not pfx_path.exists():
            warnings.append(f"客户端证书 pfx 文件不存在：{pfx_path}")
        else:
            warning = _extension_warning(pfx_path, 'pfx', PFX_EXTENSIONS)
            if warning:
                warnings.append(warning)

    if cert_path is not None:
        if not cert_path.exists():
            warnings.append(f"客户端证书 cert 文件不存在：{cert_path}")
        else:
            warning = _extension_warning(cert_path, 'cert', CERT_EXTENSIONS)
            if warning:
                warnings.append(warning)

    if key_path is not None:
        if not key_path.exists():
            warnings.append(f"客户端证书 key 文件不存在：{key_path}")
        else:
            warning = _extension_warning(key_path, 'key', KEY_EXTENSIONS)
            if warning:
                warnings.append(warning)

    return warnings


def build_client_certificates(
    origins: Iterable[Optional[str]],
    pfx_path: Optional[Path] = None,
    passphrase: Optional[str] = None,
    cert_path: Optional[Path] = None,
    key_path: Optional[Path] = None,
) -> list[dict]:
    """构造 Playwright ``client_certificates`` 参数。

    产出 **camelCase** 键的 dict 列表，每个 origin 一条：

    - pfx 方案：``{"origin": ..., "pfxPath": ..., "passphrase": ...}``
      （``passphrase`` 为空时**不带该键**，Playwright 对空口令的 pfx 会报错）
    - PEM 方案：``{"origin": ..., "certPath": ..., "keyPath": ...}``

    pfx 与 PEM 同时提供时**优先 pfx**，并给出告警。

    origin 列表为空、或没有任何可用证书文件时返回 ``[]``
    （Playwright 的 origin 必填且不支持通配，宁可不生效也不要传非法参数）。
    """
    normalized: list[str] = []
    seen: set[str] = set()
    for origin in origins:
        value = normalize_origin(origin)
        if value and value not in seen:
            seen.add(value)
            normalized.append(value)

    if not normalized:
        return []

    use_pfx = pfx_path is not None
    if use_pfx and (cert_path is not None or key_path is not None):
        logger.warning(
            "同时配置了客户端证书 pfx 与 PEM(cert/key) 文件，将优先使用 pfx：%s", pfx_path
        )
        cert_path = None
        key_path = None

    common: dict = {}
    if use_pfx:
        common['pfxPath'] = str(pfx_path)
        # 纯空白视为「未设置」：多来自复制粘贴/表单残留，带上会让 Playwright 解密失败；
        # 而含非空白字符的口令原样传递（不 strip），以免破坏带前后空格的真实口令。
        if passphrase and str(passphrase).strip():
            common['passphrase'] = str(passphrase)
    elif cert_path is not None and key_path is not None:
        common['certPath'] = str(cert_path)
        common['keyPath'] = str(key_path)
    else:
        # 未提供任何完整证书材料
        return []

    return [{'origin': origin, **common} for origin in normalized]


def summarize_origins(origins: Iterable[str]) -> str:
    """把 origin 列表转成可安全写入日志的字符串（不含任何凭据）。"""
    items = [str(item) for item in origins if item]
    return ', '.join(items) if items else '(无)'
