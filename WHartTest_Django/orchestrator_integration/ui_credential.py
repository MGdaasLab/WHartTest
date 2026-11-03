"""UI 一键生成会话的凭据标记。

账密登录模式下，平台把表单账号密码以 ``<wharttest:ui-credential .../>`` 标记
注入发给 LLM 的任务消息，模型据此亲自填表登录并生成登录步骤。标记只允许
存在于 LLM 消息：SSE 展示与会话历史存储必须先经 :func:`strip_ui_credential_marker`
脱敏，否则凭据会泄漏到前端与数据库。
"""
from __future__ import annotations

import re

_UI_CREDENTIAL_MARKER_RE = re.compile(
    r"\s*<wharttest:ui-credential\b[^>]*/>\s*", re.IGNORECASE
)

# 供注入处与规范文档保持一致的标记形态
UI_CREDENTIAL_MARKER_TEMPLATE = (
    "\n\n<wharttest:ui-credential username=\"{username}\" password=\"{password}\"/>"
)


def strip_ui_credential_marker(text: str) -> str:
    """剥掉任务消息里的凭据标记（用于 SSE 展示与会话历史存储）。"""
    if not text or "<wharttest:ui-credential" not in text:
        return text
    return _UI_CREDENTIAL_MARKER_RE.sub("\n", text).strip()
