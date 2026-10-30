"""
内置工具管理模块

提供 AI Agent 可调用的持久化工具，包括：
- Skill 脚本执行工具（执行用户上传的 Python 脚本）

注意：Diagram 工具（display_diagram, edit_diagram）已移至 WHartTest-Tools MCP
"""

from .skill_tools import get_skill_tools

import logging

logger = logging.getLogger('orchestrator_integration')


def get_builtin_tools(
    user_id: int,
    project_id: int,
    test_case_id: int = None,
    chat_session_id: str = None,
    ui_credential_context: dict = None,
) -> list:
    """获取所有内置工具

    ui_credential_context：UI 一键生成会话的凭据上下文（auth_state_id / username /
    password 等），仅透传给 Skill 工具用于平台侧 env 注入，不进 LLM 上下文。
    """
    tools = []

    skill_tools = get_skill_tools(
        user_id=user_id,
        project_id=project_id,
        test_case_id=test_case_id,
        chat_session_id=chat_session_id,
        ui_credential_context=ui_credential_context,
    )
    tools.extend(skill_tools)
    logger.info(f"[BuiltinTools] 加载 {len(skill_tools)} 个 Skill 工具")

    return tools
