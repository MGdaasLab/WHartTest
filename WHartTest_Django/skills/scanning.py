"""
Skill 包静态扫描（第 3 层：供应链）

Skill 包来自用户上传 / Git / Skill 商店，属于外部投递物；导入前做一次静态体检，
把「明显不是测试脚本该干的事」拦在入库之前：

- 凭据硬编码（私钥、各类 API Key、默认口令）
- 安装钩子（npm pre/postinstall）——导入即执行，是最典型的供应链入口
- 运行期装包（pip/npm install）——在目标环境落地持久化依赖
- 读取平台机密（SECRET_KEY / DB 口令 / machine-id / 授权私钥）
- 访问内网地址（SSRF 之外的主动外联）

扫描结果分级：``high`` 表示应当拒绝导入，``medium``/``low`` 仅提示。
策略由 ``SKILL_IMPORT_SCAN_MODE`` 控制：``warn``（默认，记录并放行）、``block``（拒绝 high）。
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger("skills")

# 只扫这些文本类文件，避免把二进制内容当代码读
_SCANNABLE_SUFFIXES = {
    ".py", ".js", ".mjs", ".cjs", ".ts", ".sh", ".bash", ".ps1",
    ".json", ".yaml", ".yml", ".toml", ".md", ".txt", ".cfg", ".ini", ".env",
}
_MAX_FILE_BYTES = 2 * 1024 * 1024
# 跳过集合必须与落盘阶段（models._create_skill_from_dir 只排除 .git/__pycache__/node_modules）
# 一致：落盘会复制的目录若在这里被跳过，等于给恶意 Skill 留出「放进 dist/ 就不被扫描」的盲区。
_SKIP_DIRS = {".git", "__pycache__", "node_modules"}
# 无扩展名但含凭据的常见文件名（pathlib 对 ".env" 的 suffix 为空，需按名字匹配）
_SCANNABLE_NAMES = {".env", ".env.local", ".env.production", ".npmrc", ".pypirc"}


@dataclass
class ScanFinding:
    severity: str
    rule: str
    path: str
    line: Optional[int] = None
    detail: str = ""


@dataclass
class ScanReport:
    findings: list = field(default_factory=list)

    @property
    def high_findings(self) -> list:
        return [item for item in self.findings if item.severity == "high"]

    def summary(self) -> str:
        if not self.findings:
            return "未发现可疑内容"
        counts: dict[str, int] = {}
        for item in self.findings:
            counts[item.severity] = counts.get(item.severity, 0) + 1
        return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


# (规则名, 严重级, 正则) —— 正则刻意收窄，避免误伤正常测试脚本
_PATTERNS: tuple[tuple[str, str, re.Pattern], ...] = (
    (
        "hardcoded_private_key",
        "high",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
    ),
    (
        "hardcoded_api_key",
        "high",
        re.compile(
            r"""(?i)\b(?:api[_-]?key|apikey|secret[_-]?key|access[_-]?token|password)\b"""
            r"""\s*[:=]\s*["'][A-Za-z0-9_\-]{16,}["']"""
        ),
    ),
    (
        "hardcoded_cloud_key",
        "high",
        re.compile(r"\b(?:AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,})\b"),
    ),
    (
        "npm_install_hook",
        "high",
        re.compile(r"""(?i)["'](?:pre|post)?install["']\s*:"""),
    ),
    (
        "runtime_package_install",
        "medium",
        re.compile(r"(?i)\b(?:pip3?\s+install|npm\s+(?:install|i|ci|add)|npx\s+--yes)\b"),
    ),
    (
        "platform_secret_access",
        "high",
        re.compile(
            r"(?i)(?:DJANGO_SECRET_KEY|POSTGRES_PASSWORD|LICENSE_PRIVATE_KEY"
            r"|/etc/machine-id|LICENSE_SERVER_URL)"
        ),
    ),
    (
        "internal_network_target",
        "medium",
        re.compile(
            r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
            r"|192\.168\.\d{1,3}\.\d{1,3}"
            r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
            r"|169\.254\.\d{1,3}\.\d{1,3}"
            r"|127\.0\.0\.1)\b"
        ),
    ),
    (
        "shell_pipe_download",
        "high",
        re.compile(r"(?i)\b(?:curl|wget)\b[^\n|]{0,200}\|\s*(?:sh|bash|python)"),
    ),
)


def scan_mode() -> str:
    """扫描策略：``warn``（默认）或 ``block``。"""
    raw = os.environ.get("SKILL_IMPORT_SCAN_MODE", "")
    if not raw:
        try:
            from django.conf import settings

            raw = getattr(settings, "SKILL_IMPORT_SCAN_MODE", "") or ""
        except Exception:
            raw = ""
    raw = str(raw).strip().lower()
    return "block" if raw == "block" else "warn"


def _iter_scannable_files(skill_root: str) -> Iterable[Path]:
    root = Path(skill_root).resolve()
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        # 只按「相对 skill 根目录」的路径片段判定跳过：否则 skill 恰好位于
        # /srv/build/... 这类父目录下时，全部文件都会被跳过、扫描静默失效。
        try:
            relative_parts = path.relative_to(root).parts
        except ValueError:
            continue
        if any(part in _SKIP_DIRS for part in relative_parts):
            continue
        if (
            path.suffix.lower() not in _SCANNABLE_SUFFIXES
            and path.name not in _SCANNABLE_NAMES
        ):
            continue
        try:
            if path.stat().st_size > _MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        yield path


def _scan_package_json_hooks(path: Path) -> list:
    """单独解析 package.json 的 scripts：安装钩子是导入即执行的入口。"""
    if path.name != "package.json":
        return []
    findings: list = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    scripts = payload.get("scripts") if isinstance(payload, dict) else None
    if not isinstance(scripts, dict):
        return []
    for name in ("preinstall", "install", "postinstall", "prepare"):
        if name in scripts:
            findings.append(
                ScanFinding(
                    severity="high",
                    rule="npm_install_hook",
                    path=path.name,
                    detail=f"package.json 含 {name} 脚本，导入后可能被执行",
                )
            )
    return findings


def scan_skill_package(skill_root: str) -> ScanReport:
    """扫描一个 Skill 目录，返回分级结果。"""
    report = ScanReport()
    if not skill_root or not os.path.isdir(skill_root):
        return report

    seen: set[tuple[str, str]] = set()
    for path in _iter_scannable_files(skill_root):
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        relative = path.relative_to(skill_root).as_posix()

        for finding in _scan_package_json_hooks(path):
            finding.path = relative
            report.findings.append(finding)

        for rule, severity, pattern in _PATTERNS:
            for match in pattern.finditer(content):
                # 同一文件同类规则只报一次，避免噪声淹没真实信号
                key = (relative, rule)
                if key in seen:
                    break
                seen.add(key)
                line = content.count("\n", 0, match.start()) + 1
                report.findings.append(
                    ScanFinding(
                        severity=severity,
                        rule=rule,
                        path=relative,
                        line=line,
                        detail=match.group(0)[:120],
                    )
                )
                break

    if report.findings:
        logger.warning(
            "[skill.scan] 扫描到可疑内容: %s（%s）",
            report.summary(),
            "; ".join(
                f"{item.severity}:{item.rule}@{item.path}"
                for item in report.findings[:10]
            ),
        )
    return report


def enforce_scan_policy(skill_name: str, report: ScanReport) -> None:
    """按策略决定是否拒绝导入。``block`` 模式下 high 级发现会抛 ValidationError。"""
    if not report.high_findings:
        return

    if scan_mode() != "block":
        logger.warning(
            "[skill.scan] Skill '%s' 含 %d 条高风险发现，当前策略为 warn，仅记录不拦截：%s",
            skill_name,
            len(report.high_findings),
            "; ".join(f"{item.rule}@{item.path}" for item in report.high_findings[:5]),
        )
        return

    from django.core.exceptions import ValidationError

    rules = sorted({item.rule for item in report.high_findings})
    raise ValidationError(
        f"Skill '{skill_name}' 未通过导入安全检查（{', '.join(rules)}）；"
        "如确属误报，可由运维将 SKILL_IMPORT_SCAN_MODE 设为 warn 后重试"
    )
