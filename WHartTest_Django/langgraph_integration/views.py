from rest_framework import status, permissions, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django.db.models import Q
from django.utils import timezone
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import LLMConfig, ChatSession, ChatMessage
from .serializers import LLMConfigSerializer
import logging
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)

# 项目相关导入
from projects.models import Project, ProjectMember
from projects.permissions import IsProjectMember

# 导入统一的权限系统
from wharttest_django.viewsets import BaseModelViewSet
from wharttest_django.permissions import HasModelPermission

# 导入提示词管理
from prompts.models import UserPrompt

# v2.0.0: 导入中间件配置（已替代手动上下文压缩）
from orchestrator_integration.middleware_config import (
    get_standard_middleware,
    get_middleware_from_config,
    get_user_friendly_llm_error,
)


# ============== 公共工具函数 ==============


def check_project_permission(user, project_id):
    """
    检查用户是否有访问指定项目的权限

    v2.0.1: 提取为公共函数，供多个 View 复用

    Args:
        user: 当前用户对象
        project_id: 项目ID

    Returns:
        Project 对象（如果有权限），否则返回 None
    """
    try:
        project = Project.objects.get(id=project_id)
        # 超级用户可以访问所有项目
        if user.is_superuser:
            return project
        # 检查用户是否是项目成员
        if ProjectMember.objects.filter(project=project, user=user).exists():
            return project
        return None
    except Project.DoesNotExist:
        return None


# --- 新增导入 ---
from typing import TypedDict, Annotated, List, Optional
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage,
)
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages  # Correct import for add_messages
from langchain.agents import create_agent  # For agent with tools (v1 API)
import os
import uuid  # Import uuid module
import re
import base64  # For requirement doc images (multimodal)


# 知识库集成
from knowledge.langgraph_integration import (
    KnowledgeRAGService,
    ConversationalRAGService,
    LangGraphKnowledgeIntegration,
)
from knowledge.models import KnowledgeBase
from django.conf import settings
import logging  # Import logging
from asgiref.sync import sync_to_async  # For async operations in sync context

# 统一的 Checkpointer 工厂
from wharttest_django.checkpointer import (
    get_async_checkpointer,
    get_sync_checkpointer,
    delete_checkpoints_by_thread_id,
    delete_checkpoints_batch,
    check_history_exists,
    get_thread_ids_by_prefix,
    rollback_checkpoints_to_count,
)
import json  # For JSON serialization in streaming
import asyncio  # For async operations

# Django 流式响应
from django.http import StreamingHttpResponse

from mcp_tools.models import RemoteMCPConfig  # To load remote MCP server configs
from langchain_mcp_adapters.client import (
    MultiServerMCPClient,
)  # To connect to remote MCPs
from mcp_tools.persistent_client import mcp_session_manager  # 持久化MCP会话管理器

# 需求文档（docimg:// 占位符）
from requirements.models import RequirementDocument
# --- 新增导入结束 ---

logger = logging.getLogger(__name__)  # Initialize logger


# --- 辅助函数 ---
def create_llm_instance(active_config, temperature=0.7):
    """
    根据配置创建LLM实例
    支持多供应商：
    - openai_compatible: ChatOpenAI（OpenAI兼容协议）
    - qwen: ChatQwen（阿里云百炼通义千问）

    关键参数说明：
    - timeout: 请求超时时间（秒），防止无限期等待
    - max_retries: 最大重试次数，处理临时网络问题
    """
    model_identifier = active_config.name or "gpt-3.5-turbo"
    provider = (getattr(active_config, "provider", None) or "openai_compatible").strip()

    # 从配置获取超时设置，默认120秒（LLM响应可能较慢）
    request_timeout = getattr(active_config, "request_timeout", None) or 120
    # 重试次数，默认3次
    max_retries = getattr(active_config, "max_retries", None) or 3

    base_url = (active_config.api_url or "").strip() or None
    api_key = (active_config.api_key or "").strip()

    try:
        if provider == "qwen":
            try:
                from langchain_qwq import ChatQwen
            except ImportError as e:
                raise ImportError(
                    "Qwen provider requires langchain-qwq. Please install dependencies from requirements.txt."
                ) from e

            llm_kwargs = {
                "model": model_identifier,
                "temperature": temperature,
                "timeout": request_timeout,
                "max_retries": max_retries,
            }
            if api_key:
                llm_kwargs["api_key"] = api_key
            if base_url:
                llm_kwargs["base_url"] = base_url

            llm = ChatQwen(**llm_kwargs)
        else:
            if provider != "openai_compatible":
                logger.warning(
                    "Unknown provider '%s', fallback to openai_compatible", provider
                )
            llm_kwargs = {
                "model": model_identifier,
                "temperature": temperature,
                "api_key": api_key,
                "base_url": base_url,
                "timeout": request_timeout,  # 单次请求超时
                "max_retries": max_retries,  # 自动重试次数
            }
            llm = ChatOpenAI(**llm_kwargs)

        logger.info(
            "Initialized LLM: provider=%s, model=%s, base_url=%s, timeout=%ss, max_retries=%s",
            provider,
            model_identifier,
            base_url,
            request_timeout,
            max_retries,
        )
    except Exception as e:
        logger.error(
            "Failed to initialize LLM: provider=%s, model=%s, base_url=%s, error=%s: %s",
            provider,
            model_identifier,
            base_url,
            type(e).__name__,
            e,
            exc_info=True,
        )
        raise

    return llm


def create_sse_data(data_dict):
    """
    创建SSE格式的数据，确保中文字符正确编码
    """
    json_str = json.dumps(data_dict, ensure_ascii=False)
    return f"data: {json_str}\n\n"


_REQ_DOC_ID_RE = re.compile(r"需求文档ID[:：]\s*([0-9a-fA-F-]{36})")
_REQ_DOC_IMAGE_URL_RE = re.compile(
    r"/api/requirements/documents/(?P<doc_id>[0-9a-fA-F-]{36})/images/(?P<image_id>[^/]+)/"
)
_REQ_DOCIMG_MD_RE = re.compile(r"!\[[^\]]*?\]\(docimg://(?P<image_id>[^)]+)\)")
_REQ_DOCIMG_API_MD_RE = re.compile(
    r"!\[[^\]]*?\]\(/api/requirements/documents/(?P<doc_id>[0-9a-fA-F-]{36})/images/(?P<image_id>[^)/]+)/*\)"
)


def _detect_requirement_document_id(message: str) -> Optional[str]:
    if not message:
        return None
    url_match = _REQ_DOC_IMAGE_URL_RE.search(message)
    if url_match:
        return url_match.group("doc_id")
    text_match = _REQ_DOC_ID_RE.search(message)
    if text_match:
        return text_match.group(1)
    return None


def _replace_docimg_markdown_with_api_urls(message: str, document_id: str) -> str:
    if not message or not document_id or "docimg://" not in message:
        return message

    def _repl(match: re.Match) -> str:
        alt = match.group(1)
        image_id = match.group(2)
        return f"![{alt}](/api/requirements/documents/{document_id}/images/{image_id}/)"

    return re.sub(r"!\[(.*?)\]\(docimg://([^)]+)\)", _repl, message)


def _extract_requirement_image_ids_in_order(message: str) -> list[str]:
    if not message:
        return []

    ordered: list[str] = []
    seen: set[str] = set()

    # Markdown 中的 docimg://img_001
    for m in _REQ_DOCIMG_MD_RE.finditer(message):
        image_id = m.group("image_id")
        if image_id and image_id not in seen:
            seen.add(image_id)
            ordered.append(image_id)

    # Markdown 中的 /api/requirements/documents/{doc}/images/{img}/
    for m in _REQ_DOCIMG_API_MD_RE.finditer(message):
        image_id = m.group("image_id")
        if image_id and image_id not in seen:
            seen.add(image_id)
            ordered.append(image_id)

    return ordered


def _file_to_data_url(path: str, content_type: str) -> str:
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{content_type};base64,{encoded}"


async def _extract_requirement_doc_images_for_message(
    message: str,
    project: Project,
) -> tuple[str, list[str], Optional[str]]:
    """
    从消息中识别需求文档图片引用（docimg:// 或 /api/requirements/documents/.../images/...），
    并返回：
    - message_text: 将 docimg:// 占位符替换为可访问的 /api URL 后的文本（用于展示/存档）
    - image_data_urls: 需要送入多模态模型的 data:... URL 列表（按出现顺序、去重）
    - document_id: 解析到的需求文档ID（UUID字符串）
    """
    if not message:
        return message, [], None

    document_id = _detect_requirement_document_id(message)
    if not document_id:
        return message, [], None

    message_text = _replace_docimg_markdown_with_api_urls(message, document_id)
    image_ids = _extract_requirement_image_ids_in_order(message_text)
    if not image_ids:
        return message_text, [], document_id

    # 只允许读取当前项目下的文档图片，避免跨项目泄露
    document = await sync_to_async(
        lambda: RequirementDocument.objects.filter(
            id=document_id, project=project
        ).first()
    )()
    if not document:
        logger.warning(
            "Chat: RequirementDocument %s not found in project %s, skip image attachment",
            document_id,
            getattr(project, "id", None),
        )
        return message_text, [], document_id

    images = await sync_to_async(
        lambda: list(document.images.filter(image_id__in=image_ids))
    )()
    image_map = {img.image_id: img for img in images}

    data_urls: list[str] = []
    for image_id in image_ids:
        img = image_map.get(image_id)
        if not img:
            logger.warning(
                "Chat: Document image %s not found in document %s",
                image_id,
                document_id,
            )
            continue
        try:
            path = img.image_file.path
            data_url = await sync_to_async(_file_to_data_url)(path, img.content_type)
            data_urls.append(data_url)
        except Exception as e:
            logger.error(
                "Chat: Failed to load document image %s (%s): %s",
                image_id,
                document_id,
                e,
            )
            continue

    return message_text, data_urls, document_id


# --- AgentState 定义 ---
class AgentState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]


# --- AgentState 定义结束 ---

# --- 全局 Checkpointer 说明 ---
# 该配置会在项目 BASE_DIR 下创建/使用 SQLite 文件。
# 请确保 settings.py 中的 BASE_DIR 定义正确。
# settings.BASE_DIR 应为 Path 对象或字符串。
# --- 全局 Checkpointer 说明结束 ---
# 全局 checkpointer 'memory' 已移除，将在 post 方法内实例化。


class LLMConfigViewSet(BaseModelViewSet):
    """
    LLM配置管理接口
    提供完整的CRUD操作
    """

    queryset = LLMConfig.objects.all().order_by("-created_at")
    serializer_class = LLMConfigSerializer

    def perform_create(self, serializer):
        """执行创建操作"""
        if serializer.validated_data.get("is_active", False):
            LLMConfig.objects.filter(is_active=True).update(is_active=False)
        serializer.save()

    def perform_update(self, serializer):
        """执行更新操作"""
        if serializer.validated_data.get("is_active", False):
            LLMConfig.objects.filter(is_active=True).exclude(
                pk=serializer.instance.pk
            ).update(is_active=False)
        serializer.save()

    @action(detail=True, methods=["post"])
    def test_connection(self, request, pk=None):
        """测试LLM配置连接"""
        config = self.get_object()

        try:
            llm = create_llm_instance(config, temperature=0.1)
            response = llm.invoke("Hi")
            if getattr(response, "content", None):
                return Response({"status": "success", "message": "连接测试成功"})
            return Response(
                {"status": "warning", "message": "响应格式异常"},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            msg = str(e)
            return Response(
                {"status": "error", "message": f"连接失败: {msg}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["post"])
    def fetch_models(self, request):
        """
        从LLM API获取可用模型列表
        请求体:
        - 新建配置时: { "api_url": "...", "api_key": "..." }
        - 编辑配置时: { "config_id": 123 } 或 { "api_url": "...", "config_id": 123 }
          (api_key 优先从数据库获取)
        """
        import requests as http_requests

        api_url = request.data.get("api_url", "").rstrip("/")
        api_key = request.data.get("api_key", "")
        config_id = request.data.get("config_id")

        # 如果提供了 config_id，优先从数据库获取配置
        if config_id:
            try:
                config = LLMConfig.objects.get(pk=config_id)
                if not api_url:
                    api_url = config.api_url.rstrip("/")
                if not api_key:
                    api_key = config.api_key or ""
            except LLMConfig.DoesNotExist:
                return Response(
                    {"status": "error", "message": "配置不存在"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        if not api_url:
            return Response(
                {"status": "error", "message": "请提供 API URL"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            resp = http_requests.get(f"{api_url}/models", headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if data.get("data"):
                models = [model.get("id") for model in data["data"] if model.get("id")]
                return Response({"status": "success", "models": models})
            else:
                return Response(
                    {
                        "status": "warning",
                        "message": "API 返回格式不符合预期",
                        "models": [],
                    }
                )
        except http_requests.Timeout:
            return Response(
                {"status": "error", "message": "请求超时"},
                status=status.HTTP_408_REQUEST_TIMEOUT,
            )
        except http_requests.RequestException as e:
            msg = str(e)
            if hasattr(e, "response") and e.response is not None:
                try:
                    msg = e.response.json().get("error", {}).get("message", str(e))
                except Exception:
                    msg = e.response.text[:200] if e.response.text else str(e)
            return Response(
                {"status": "error", "message": f"获取模型列表失败: {msg}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


def get_effective_system_prompt(user, prompt_id=None):
    """
    获取有效的系统提示词（同步版本）
    优先级：用户指定的提示词 > 用户默认提示词 > 全局LLM配置的system_prompt

    Args:
        user: 当前用户
        prompt_id: 指定的提示词ID（可选）

    Returns:
        tuple: (prompt_content, prompt_source)
        prompt_content: 提示词内容
        prompt_source: 提示词来源 ('user_specified', 'user_default', 'global', 'none')
    """
    try:
        # 1. 如果指定了提示词ID，优先使用
        if prompt_id:
            try:
                user_prompt = UserPrompt.objects.get(
                    id=prompt_id, user=user, is_active=True
                )
                return user_prompt.content, "user_specified"
            except UserPrompt.DoesNotExist:
                logger.warning(
                    f"Specified prompt {prompt_id} not found for user {user.id}"
                )

        # 2. 尝试获取用户的默认提示词
        default_prompt = UserPrompt.get_user_default_prompt(user)
        if default_prompt:
            return default_prompt.content, "user_default"

        # 3. 使用全局LLM配置的system_prompt
        try:
            active_config = LLMConfig.objects.get(is_active=True)
            if active_config.system_prompt and active_config.system_prompt.strip():
                return active_config.system_prompt.strip(), "global"
        except LLMConfig.DoesNotExist:
            logger.warning("No active LLM configuration found")

        # 4. 没有任何提示词
        return None, "none"

    except Exception as e:
        logger.error(f"Error getting effective system prompt: {e}")
        # 降级到全局配置
        try:
            active_config = LLMConfig.objects.get(is_active=True)
            if active_config.system_prompt and active_config.system_prompt.strip():
                return active_config.system_prompt.strip(), "global"
        except:
            pass
        return None, "none"


async def _format_project_credentials(project):
    """
    格式化项目凭据信息为文本

    Args:
        project: 项目对象

    Returns:
        str: 格式化后的凭据信息文本
    """
    try:
        from projects.models import ProjectCredential

        # 获取项目的所有凭据
        credentials = await sync_to_async(list)(
            ProjectCredential.objects.filter(project=project).all()
        )

        if not credentials:
            return "当前项目未配置登录信息。\n"

        # 格式化凭据信息
        credentials_text = "**当前项目已配置以下登录信息**：\n"
        for cred in credentials:
            role = cred.user_role or "未指定角色"
            url = cred.system_url or "未指定URL"
            username = cred.username or "未指定用户名"
            password = cred.password or "未指定密码"
            credentials_text += f"- **{role}**：系统地址: {url} / 用户名: {username} / 密码: {password}\n"

        credentials_text += "\n"
        return credentials_text

    except Exception as e:
        logger.error(f"Format project credentials error: {e}")
        return ""


async def _format_project_skills(project):
    """
    格式化全局 Skills 信息为文本（渐进式加载）

    只注入 Skill 的名称和描述（元数据），完整的 SKILL.md 内容需要通过
    read_skill_content 工具按需获取。Skills 全局共享，不限制项目。

    Args:
        project: 项目对象（保留参数兼容性，但不用于过滤）

    Returns:
        str: 格式化后的 Skills 元数据文本
    """
    try:
        from skills.models import Skill

        # Skills 全局共享，不限制项目
        skills = await sync_to_async(list)(Skill.objects.filter(is_active=True).all())

        if not skills:
            return ""

        skills_text = "\n\n# Available Skills\n\n"
        skills_text += "以下是可用的 Skills 列表。需要使用某个 Skill 时，先调用 `read_skill_content` 工具获取完整的使用说明，再调用 `execute_skill_script` 执行命令。\n\n"
        for skill in skills:
            skills_text += f"- **{skill.name}**: {skill.description}\n"

        return skills_text

    except Exception as e:
        logger.error(f"Format project skills error: {e}")
        return ""


def _build_project_scope_hint(project) -> str:
    """
    构建项目作用域提示词。

    默认约束 LLM：如果用户未明确指定其他项目，所有操作均基于当前项目。
    """
    if not project:
        return ""

    project_name = getattr(project, "name", "") or "未命名项目"
    project_id = getattr(project, "id", None)
    project_label = (
        f"{project_name} (ID: {project_id})" if project_id is not None else project_name
    )

    return (
        "# 当前项目上下文\n"
        f"- 当前项目：{project_label}\n"
        "- 默认规则：如用户无特殊要求，所有操作均基于当前项目进行。\n"
        "- 若用户明确指定了其他项目，再按用户要求切换。"
    )


async def _inject_project_context(prompt_content: str, project) -> str:
    """
    注入项目上下文（项目作用域、凭据和 Skills）到提示词中

    Args:
        prompt_content: 原始提示词内容
        project: 项目对象

    Returns:
        str: 注入上下文后的提示词
    """
    if not project:
        return prompt_content

    prompt_content = prompt_content or ""

    # 注入项目作用域提示（可使用占位符 {project_scope_hint} 精确控制位置）
    project_scope_hint = _build_project_scope_hint(project)
    if "{project_scope_hint}" in prompt_content:
        prompt_content = prompt_content.replace(
            "{project_scope_hint}", project_scope_hint
        )
    elif (
        project_scope_hint
        and "默认规则：如用户无特殊要求，所有操作均基于当前项目进行。"
        not in prompt_content
    ):
        prompt_content = f"{project_scope_hint}\n\n{prompt_content}".strip()

    # 注入凭据信息
    if "{credentials_info}" in prompt_content:
        credentials_text = await _format_project_credentials(project)
        prompt_content = prompt_content.replace("{credentials_info}", credentials_text)

    # 注入 Skills 信息
    if "{skills_info}" in prompt_content:
        skills_text = await _format_project_skills(project)
        prompt_content = prompt_content.replace("{skills_info}", skills_text)
    else:
        # 即使没有占位符，也自动追加 Skills 到提示词末尾
        skills_text = await _format_project_skills(project)
        if skills_text:
            prompt_content = prompt_content + skills_text

    return prompt_content


async def get_effective_system_prompt_async(user, prompt_id=None, project=None):
    """
    获取有效的系统提示词（异步版本）
    优先级：用户指定的提示词 > 用户默认提示词 > 全局LLM配置的system_prompt
    支持占位符: {project_scope_hint} 注入项目作用域, {credentials_info} 注入项目凭据,
    {skills_info} 注入项目 Skills 元数据
    如果未使用 {skills_info} 占位符，活跃的 Skills 元数据将自动追加到提示词末尾
    （完整的 SKILL.md 内容通过 read_skill_content 工具按需获取）

    Args:
        user: 当前用户
        prompt_id: 指定的提示词ID（可选）
        project: 项目对象（可选），用于注入凭据和 Skills 信息

    Returns:
        tuple: (prompt_content, prompt_source)
        prompt_content: 提示词内容（已注入项目上下文）
        prompt_source: 提示词来源 ('user_specified', 'user_default', 'global', 'project_context', 'none')
    """
    try:
        # 1. 如果指定了提示词ID，优先使用
        if prompt_id:
            try:
                user_prompt = await sync_to_async(UserPrompt.objects.get)(
                    id=prompt_id, user=user, is_active=True
                )
                prompt_content = await _inject_project_context(
                    user_prompt.content, project
                )
                return prompt_content, "user_specified"
            except UserPrompt.DoesNotExist:
                logger.warning(
                    f"Specified prompt {prompt_id} not found for user {user.id}"
                )

        # 2. 尝试获取用户的默认提示词
        try:
            default_prompt = await sync_to_async(UserPrompt.objects.get)(
                user=user, is_default=True, is_active=True
            )
            if default_prompt:
                prompt_content = await _inject_project_context(
                    default_prompt.content, project
                )
                return prompt_content, "user_default"
        except UserPrompt.DoesNotExist:
            pass

        # 3. 使用全局LLM配置的system_prompt
        try:
            active_config = await sync_to_async(LLMConfig.objects.get)(is_active=True)
            if active_config.system_prompt and active_config.system_prompt.strip():
                prompt_content = await _inject_project_context(
                    active_config.system_prompt.strip(), project
                )
                return prompt_content, "global"
        except LLMConfig.DoesNotExist:
            logger.warning("No active LLM configuration found")

        # 4. 没有任何提示词时，至少注入项目作用域提示，确保默认按当前项目执行
        project_scope_hint = _build_project_scope_hint(project)
        if project_scope_hint:
            return project_scope_hint, "project_context"

        # 5. 仍无可用提示词
        return None, "none"

    except Exception as e:
        logger.error(f"Error getting effective system prompt: {e}")
        # 降级到全局配置
        try:
            active_config = await sync_to_async(LLMConfig.objects.get)(is_active=True)
            if active_config.system_prompt and active_config.system_prompt.strip():
                return active_config.system_prompt.strip(), "global"
        except:
            pass
        project_scope_hint = _build_project_scope_hint(project)
        if project_scope_hint:
            return project_scope_hint, "project_context"
        return None, "none"


class ChatAPIView(APIView):
    """
    使用 LangGraph 与当前激活的 LLM 处理聊天请求的 API 端点，
    支持按需集成远程 MCP 工具。
    支持项目隔离，聊天记录按项目分组。
    """

    permission_classes = [HasModelPermission]

    async def dispatch(self, request, *args, **kwargs):
        """
        处理入站请求，并确保当前视图按异步方式执行。
        """
        self.request = request
        self.args = args
        self.kwargs = kwargs
        # 确保 request 对象满足 DRF 的常规初始化预期。
        # 若同步代码过早访问 request.user，可能需要更复杂的初始化处理。
        # 当前先按可包装标准 DRF 请求流程处理。
        request = await sync_to_async(self.initialize_request)(request, *args, **kwargs)
        self.request = request
        self.headers = await sync_to_async(lambda: self.default_response_headers)()

        try:
            await sync_to_async(self.initial)(request, *args, **kwargs)

            if request.method.lower() in self.http_method_names:
                handler = getattr(
                    self, request.method.lower(), self.http_method_not_allowed
                )
            else:
                handler = self.http_method_not_allowed

            response = await handler(request, *args, **kwargs)

        except Exception as exc:
            response = await sync_to_async(self.handle_exception)(exc)

        self.response = await sync_to_async(self.finalize_response)(
            request, response, *args, **kwargs
        )
        return self.response

    async def post(self, request, *args, **kwargs):
        logger.info(f"ChatAPIView: Received POST request from user {request.user.id}")
        user_message_content = request.data.get("message")
        session_id = request.data.get("session_id")
        project_id = request.data.get("project_id")
        image_base64 = request.data.get("image")  # 图片base64编码（不含前缀）

        # 知识库相关参数
        knowledge_base_id = request.data.get("knowledge_base_id")
        use_knowledge_base = request.data.get(
            "use_knowledge_base", True
        )  # 默认启用知识库
        similarity_threshold = request.data.get("similarity_threshold", 0.5)
        top_k = request.data.get("top_k", 5)

        # 提示词相关参数
        prompt_id = request.data.get("prompt_id")  # 用户指定的提示词ID

        # 验证项目ID是否提供
        if not project_id:
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "project_id is required.",
                    "data": {},
                    "errors": {"project_id": ["This field is required."]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 检查项目权限
        project = await sync_to_async(check_project_permission)(
            request.user, project_id
        )
        if not project:
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_403_FORBIDDEN,
                    "message": "You don't have permission to access this project or project doesn't exist.",
                    "data": {},
                    "errors": {
                        "project_id": ["Permission denied or project not found."]
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        is_new_session = False
        if not session_id:
            session_id = uuid.uuid4().hex
            is_new_session = True
            logger.info(f"ChatAPIView: Generated new session_id: {session_id}")

        if not user_message_content:
            logger.warning("ChatAPIView: Message content is required but not provided.")
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "Message content is required.",
                    "data": {},
                    "errors": {"message": ["This field may not be blank."]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # 如果是新会话，立即创建ChatSession对象
            if is_new_session:
                try:
                    # 获取关联的提示词对象
                    prompt_obj = None
                    if prompt_id:
                        try:
                            prompt_obj = await sync_to_async(UserPrompt.objects.get)(
                                id=prompt_id, user=request.user, is_active=True
                            )
                        except UserPrompt.DoesNotExist:
                            logger.warning(
                                f"ChatAPIView: Prompt {prompt_id} not found or inactive"
                            )

                    await sync_to_async(ChatSession.objects.create)(
                        user=request.user,
                        session_id=session_id,
                        project=project,
                        prompt=prompt_obj,
                        title=f"新对话 - {user_message_content[:30]}",
                    )
                    logger.info(
                        f"ChatAPIView: Created new ChatSession entry for session_id: {session_id}, prompt_id: {prompt_id}"
                    )
                except Exception as e:
                    logger.error(
                        f"ChatAPIView: Failed to create ChatSession entry: {e}",
                        exc_info=True,
                    )

            active_config = await sync_to_async(LLMConfig.objects.get)(is_active=True)
            logger.info(f"ChatAPIView: Using active LLMConfig: {active_config.name}")
        except LLMConfig.DoesNotExist:
            logger.error("ChatAPIView: No active LLM configuration found.")
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_503_SERVICE_UNAVAILABLE,
                    "message": "No active LLM configuration found. Please configure and activate an LLM.",
                    "data": {},
                    "errors": {
                        "llm_config": ["No active LLM configuration available."]
                    },
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except LLMConfig.MultipleObjectsReturned:
            logger.error("ChatAPIView: Multiple active LLM configurations found.")
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "message": "Multiple active LLM configurations found. Ensure only one is active.",
                    "data": {},
                    "errors": {
                        "llm_config": ["Multiple active LLM configurations found."]
                    },
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # 验证图片输入是否支持
        if image_base64 and not active_config.supports_vision:
            logger.warning(
                f"ChatAPIView: Image input rejected - model {active_config.name} does not support vision"
            )
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": f"当前模型 {active_config.name} 不支持图片输入，请切换到支持多模态的模型（如 GPT-4V、Claude 3、Gemini Vision 或 Qwen-VL）",
                    "data": {},
                    "errors": {
                        "image": [
                            "Current model does not support image input. Please switch to a vision-capable model."
                        ]
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # 使用新的LLM工厂函数，支持多供应商
            llm = create_llm_instance(active_config, temperature=0.7)
            logger.info(f"ChatAPIView: Initialized LLM with provider auto-detection")

            async with get_async_checkpointer() as actual_memory_checkpointer:
                # 加载远程 MCP 工具
                logger.info("ChatAPIView: Attempting to load remote MCP tools.")
                mcp_tools_list = []
                try:
                    active_remote_mcp_configs_qs = RemoteMCPConfig.objects.filter(
                        is_active=True
                    )
                    active_remote_mcp_configs = await sync_to_async(list)(
                        active_remote_mcp_configs_qs
                    )

                    if active_remote_mcp_configs:
                        client_mcp_config = {}
                        for r_config in active_remote_mcp_configs:
                            config_key = r_config.name or f"remote_config_{r_config.id}"
                            client_mcp_config[config_key] = {
                                "url": r_config.url,
                                "transport": (
                                    r_config.transport or "streamable_http"
                                ).replace("-", "_"),
                            }
                            if (
                                r_config.headers
                                and isinstance(r_config.headers, dict)
                                and r_config.headers
                            ):
                                client_mcp_config[config_key]["headers"] = (
                                    r_config.headers
                                )

                        if client_mcp_config:
                            logger.info(
                                f"ChatAPIView: Initializing persistent MCP client with config: {client_mcp_config}"
                            )
                            # 使用持久化MCP会话管理器，传递用户、项目和会话信息以支持跨对话轮次的状态保持
                            mcp_tools_list = await mcp_session_manager.get_tools_for_config(
                                client_mcp_config,
                                user_id=str(request.user.id),
                                project_id=str(project_id),
                                session_id=session_id,  # 传递session_id以启用会话级别的工具缓存
                            )
                            logger.info(
                                f"ChatAPIView: Successfully loaded {len(mcp_tools_list)} persistent tools from remote MCP servers: {[tool.name for tool in mcp_tools_list if hasattr(tool, 'name')]}"
                            )
                        else:
                            logger.info(
                                "ChatAPIView: No active remote MCP configurations to build client config."
                            )
                    else:
                        logger.info("ChatAPIView: No active RemoteMCPConfig found.")
                except (
                    Exception
                ) as e:  # Catches errors from mcp_client.get_tools() like HTTP 429
                    logger.error(
                        f"ChatAPIView: Error loading remote MCP tools: {e}",
                        exc_info=True,
                    )
                # mcp_tools_list 为空时回退到基础聊天机器人

                # 准备 LangGraph 可执行对象
                runnable_to_invoke = None
                is_agent_with_tools = False

                # v2.0.1: 提前获取系统提示词（用于 create_agent 的 system_prompt 参数）
                # Determine thread_id first - 包含项目ID以实现项目隔离
                thread_id_parts = [str(request.user.id), str(project_id)]
                if session_id:
                    thread_id_parts.append(str(session_id))
                thread_id = "_".join(thread_id_parts)
                logger.info(
                    f"ChatAPIView: Using thread_id: {thread_id} for project: {project.name}"
                )

                # 获取有效的系统提示词（用户提示词优先，并注入项目凭据信息）
                (
                    effective_prompt,
                    prompt_source,
                ) = await get_effective_system_prompt_async(
                    request.user, prompt_id, project
                )
                logger.info(
                    f"ChatAPIView: Got effective prompt from {prompt_source}: {effective_prompt[:100] if effective_prompt else 'None'}..."
                )

                # 检查是否需要创建Agent（有MCP工具）
                if mcp_tools_list:
                    logger.info(
                        f"ChatAPIView: Attempting to create agent with {len(mcp_tools_list)} remote tools."
                    )
                    try:
                        # 如果同时有知识库和MCP工具，创建知识库增强的Agent
                        if knowledge_base_id and use_knowledge_base:
                            logger.info(
                                f"ChatAPIView: Creating knowledge-enhanced agent with {len(mcp_tools_list)} tools and knowledge base {knowledge_base_id}"
                            )

                            # 创建知识库工具
                            from knowledge.langgraph_integration import (
                                create_knowledge_tool,
                            )

                            knowledge_tool = create_knowledge_tool(
                                knowledge_base_id=knowledge_base_id,
                                user=request.user,
                                similarity_threshold=similarity_threshold,
                                top_k=top_k,
                            )

                            # 将知识库工具添加到MCP工具列表
                            enhanced_tools = mcp_tools_list + [knowledge_tool]
                            # 获取工具名列表用于 HITL
                            tool_names = [t.name for t in enhanced_tools]
                            # v2.0.1: 使用中间件创建 Agent，传入 system_prompt
                            agent_executor = create_agent(
                                llm,
                                enhanced_tools,
                                checkpointer=actual_memory_checkpointer,
                                middleware=get_middleware_from_config(
                                    active_config,
                                    llm,
                                    user=request.user,
                                    session_id=session_id,
                                    all_tool_names=tool_names,
                                ),
                                system_prompt=effective_prompt,
                            )
                            runnable_to_invoke = agent_executor
                            is_agent_with_tools = True
                            logger.info(
                                f"ChatAPIView: Knowledge-enhanced agent created with {len(enhanced_tools)} tools (including knowledge base)"
                            )
                        else:
                            # 只有MCP工具，创建普通Agent
                            # 获取工具名列表用于 HITL
                            tool_names = [t.name for t in mcp_tools_list]
                            # v2.0.1: 使用中间件创建 Agent，传入 system_prompt
                            agent_executor = create_agent(
                                llm,
                                mcp_tools_list,
                                checkpointer=actual_memory_checkpointer,
                                middleware=get_middleware_from_config(
                                    active_config,
                                    llm,
                                    user=request.user,
                                    session_id=session_id,
                                    all_tool_names=tool_names,
                                ),
                                system_prompt=effective_prompt,
                            )
                            runnable_to_invoke = agent_executor
                            is_agent_with_tools = True
                            logger.info(
                                "ChatAPIView: Agent with remote tools created with checkpointer."
                            )
                    except Exception as e:
                        logger.error(
                            f"ChatAPIView: Failed to create agent with remote tools: {e}. Falling back to knowledge-enhanced chatbot.",
                            exc_info=True,
                        )

                if not runnable_to_invoke:
                    logger.info(
                        "ChatAPIView: No remote tools or agent creation failed. Trying middleware-enabled agent fallback."
                    )

                    fallback_tools = []
                    if knowledge_base_id and use_knowledge_base:
                        try:
                            from knowledge.langgraph_integration import (
                                create_knowledge_tool,
                            )

                            knowledge_tool = create_knowledge_tool(
                                knowledge_base_id=knowledge_base_id,
                                user=request.user,
                                similarity_threshold=similarity_threshold,
                                top_k=top_k,
                            )
                            fallback_tools.append(knowledge_tool)
                            logger.info(
                                "ChatAPIView: Added knowledge tool in fallback path"
                            )
                        except Exception as e:
                            logger.warning(
                                f"ChatAPIView: Failed to create fallback knowledge tool: {e}",
                                exc_info=True,
                            )

                    try:
                        fallback_tool_names = (
                            [t.name for t in fallback_tools] if fallback_tools else None
                        )
                        agent_executor = create_agent(
                            llm,
                            fallback_tools,
                            checkpointer=actual_memory_checkpointer,
                            middleware=get_middleware_from_config(
                                active_config,
                                llm,
                                user=request.user,
                                session_id=session_id,
                                all_tool_names=fallback_tool_names,
                            ),
                            system_prompt=effective_prompt,
                        )
                        runnable_to_invoke = agent_executor
                        # 使用 create_agent 路径时 system_prompt 由参数注入，不再走手动 SystemMessage 注入逻辑
                        is_agent_with_tools = True
                        logger.info(
                            "ChatAPIView: Middleware-enabled fallback agent created with %d tools",
                            len(fallback_tools),
                        )
                    except Exception as e:
                        logger.error(
                            f"ChatAPIView: Failed to create fallback agent: {e}",
                            exc_info=True,
                        )

                # 兜底：极端情况下 create_agent 失败，回退到旧 StateGraph（无中间件）
                if not runnable_to_invoke:
                    logger.info(
                        "ChatAPIView: Falling back to legacy knowledge-enhanced chatbot graph (without middleware)."
                    )
                    is_agent_with_tools = (
                        False  # Ensure flag is false for basic chatbot
                    )

                    def knowledge_enhanced_chatbot_node(state: AgentState):
                        """知识库增强的聊天机器人节点"""
                        try:
                            # 获取最新的用户消息
                            user_messages = [
                                msg
                                for msg in state["messages"]
                                if isinstance(msg, HumanMessage)
                            ]

                            if not user_messages:
                                # 如果没有用户消息，直接调用LLM
                                invoked_response = llm.invoke(state["messages"])
                                return {"messages": [invoked_response]}

                            latest_user_message = user_messages[-1].content

                            # 检查是否需要使用知识库
                            should_use_kb = use_knowledge_base and knowledge_base_id

                            if should_use_kb:
                                logger.info(
                                    f"ChatAPIView: Using knowledge base {knowledge_base_id} for query"
                                )

                                # 使用知识库RAG服务
                                from knowledge.langgraph_integration import (
                                    ConversationalRAGService,
                                )

                                rag_service = ConversationalRAGService(llm)

                                # 执行RAG查询
                                rag_result = rag_service.query(
                                    question=latest_user_message,
                                    knowledge_base_id=knowledge_base_id,
                                    user=request.user,
                                    project_id=project_id,
                                    thread_id=thread_id,
                                    use_knowledge_base=True,
                                    similarity_threshold=similarity_threshold,
                                    top_k=top_k,
                                )

                                # 返回RAG结果中的消息
                                rag_messages = rag_result.get("messages", [])
                                if rag_messages:
                                    logger.info(
                                        f"ChatAPIView: RAG returned {len(rag_messages)} messages"
                                    )
                                    return {"messages": rag_messages}
                                else:
                                    logger.warning(
                                        "ChatAPIView: RAG returned no messages, falling back to basic chat"
                                    )

                            # 降级到基础对话
                            logger.info(
                                "ChatAPIView: Using basic chat without knowledge base"
                            )
                            invoked_response = llm.invoke(state["messages"])
                            return {"messages": [invoked_response]}

                        except Exception as e:
                            logger.error(
                                f"ChatAPIView: Error in knowledge-enhanced chatbot: {e}"
                            )
                            # 降级到基础对话
                            invoked_response = llm.invoke(state["messages"])
                            return {"messages": [invoked_response]}

                    graph_builder = StateGraph(AgentState)
                    graph_builder.add_node("chatbot", knowledge_enhanced_chatbot_node)
                    graph_builder.set_entry_point("chatbot")
                    graph_builder.add_edge("chatbot", END)
                    runnable_to_invoke = graph_builder.compile(
                        checkpointer=actual_memory_checkpointer
                    )  # Use actual checkpointer instance
                    logger.info(
                        "ChatAPIView: Knowledge-enhanced chatbot graph compiled."
                    )

                # v2.0.1: thread_id 和 effective_prompt 已在前面获取（用于 create_agent 的 system_prompt）

                # 构建消息列表，检查是否需要添加系统提示词（仅用于非 Agent 模式）
                messages_list = []

                # 检查当前会话是否已经有系统提示词（仅用于 StateGraph chatbot 模式）
                should_add_system_prompt = False
                if effective_prompt and not is_agent_with_tools:
                    try:
                        # 尝试获取当前会话的历史消息
                        with get_sync_checkpointer() as memory:
                            checkpoint_generator = memory.list(
                                config={"configurable": {"thread_id": thread_id}}
                            )
                            checkpoint_tuples_list = list(checkpoint_generator)

                            if checkpoint_tuples_list:
                                # 检查最新checkpoint中是否已有系统提示词
                                latest_checkpoint = checkpoint_tuples_list[0].checkpoint
                                if (
                                    latest_checkpoint
                                    and "channel_values" in latest_checkpoint
                                    and "messages"
                                    in latest_checkpoint["channel_values"]
                                ):
                                    existing_messages = latest_checkpoint[
                                        "channel_values"
                                    ]["messages"]
                                    # 检查第一条消息是否是系统消息
                                    if not existing_messages or not isinstance(
                                        existing_messages[0], SystemMessage
                                    ):
                                        should_add_system_prompt = True
                                else:
                                    should_add_system_prompt = True
                            else:
                                # 新会话，需要添加系统提示词
                                should_add_system_prompt = True
                    except Exception as e:
                        logger.warning(
                            f"ChatAPIView: Error checking existing messages: {e}"
                        )
                        should_add_system_prompt = True

                if should_add_system_prompt and effective_prompt:
                    messages_list.append(SystemMessage(content=effective_prompt))
                    logger.info(
                        f"ChatAPIView: Added {prompt_source} system prompt: {effective_prompt[:100]}..."
                    )

                clean_user_message = user_message_content.strip()
                (
                    clean_user_message,
                    req_image_data_urls,
                    req_doc_id,
                ) = await _extract_requirement_doc_images_for_message(
                    clean_user_message,
                    project,
                )

                if req_image_data_urls and not active_config.supports_vision:
                    logger.warning(
                        "ChatAPIView: Requirement document images detected but model %s does not support vision; sending text only",
                        active_config.name,
                    )

                # 构建用户消息（支持多模态：上传图片 + 需求文档图片）
                multimodal_parts = []
                if active_config.supports_vision and (
                    image_base64 or req_image_data_urls
                ):
                    multimodal_parts.append(
                        {"type": "text", "text": clean_user_message}
                    )

                    # 需求文档图片（按占位符出现顺序）
                    for data_url in req_image_data_urls:
                        multimodal_parts.append(
                            {"type": "image_url", "image_url": {"url": data_url}}
                        )

                    # 用户上传图片（最后追加）
                    if image_base64:
                        multimodal_parts.append(
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                },
                            }
                        )

                    additional_kwargs = {}
                    if req_doc_id:
                        additional_kwargs["requirement_document_id"] = req_doc_id
                        additional_kwargs["image_source"] = "requirement_document"

                    messages_list.append(
                        HumanMessage(
                            content=multimodal_parts,
                            additional_kwargs=additional_kwargs,
                        )
                    )
                    logger.info(
                        "ChatAPIView: Added multimodal message with %s doc images",
                        len(req_image_data_urls),
                    )
                else:
                    # 纯文本消息
                    messages_list.append(HumanMessage(content=clean_user_message))
                input_messages = {"messages": messages_list}

                invoke_config = {
                    "configurable": {"thread_id": thread_id},
                    "recursion_limit": 1000,  # 支持约500次工具调用
                }
                logger.info(
                    f"ChatAPIView: Set recursion_limit to 1000 for thread_id: {thread_id}"
                )
                # Agent 与基础聊天机器人都已完成 Checkpointer 配置

                final_state = await runnable_to_invoke.ainvoke(
                    input_messages, config=invoke_config
                )

                ai_response_content = "No valid AI response found."
                conversation_flow = []  # 存储完整的对话流程

                if final_state and final_state.get("messages"):
                    # 处理所有消息，提取对话流程
                    messages = final_state["messages"]
                    logger.info(
                        f"ChatAPIView: Processing {len(messages)} messages in final state"
                    )

                    # 找到本次对话的起始位置（用户刚发送的消息）
                    user_message_index = -1

                    def _human_message_text(content):
                        if isinstance(content, list):
                            text_parts = []
                            for item in content:
                                if (
                                    isinstance(item, dict)
                                    and item.get("type") == "text"
                                ):
                                    text_parts.append(item.get("text", ""))
                            return "".join(text_parts)
                        return content

                    for i, msg in enumerate(messages):
                        if isinstance(msg, HumanMessage):
                            msg_text = _human_message_text(getattr(msg, "content", ""))
                            if msg_text == clean_user_message:
                                user_message_index = i
                                break

                    # 如果找到了用户消息，提取从该消息开始的所有后续消息
                    if user_message_index >= 0:
                        current_conversation = messages[user_message_index:]

                        for i, msg in enumerate(current_conversation):
                            msg_type = "unknown"
                            content = ""

                            if isinstance(msg, SystemMessage):
                                msg_type = "system"
                                content = (
                                    msg.content if hasattr(msg, "content") else str(msg)
                                )
                            elif isinstance(msg, HumanMessage):
                                msg_type = "human"
                                raw_content = (
                                    msg.content if hasattr(msg, "content") else str(msg)
                                )
                                content = _human_message_text(raw_content)
                            elif isinstance(msg, AIMessage):
                                msg_type = "ai"
                                content = (
                                    msg.content if hasattr(msg, "content") else str(msg)
                                )

                                # 跳过空的AI消息（工具调用前的中间状态）
                                if not content or content.strip() == "":
                                    logger.debug(
                                        f"ChatAPIView: Skipping empty AI message at index {i}"
                                    )
                                    continue

                            elif isinstance(msg, ToolMessage):
                                msg_type = "tool"
                                content = (
                                    msg.content if hasattr(msg, "content") else str(msg)
                                )
                            else:
                                # 处理其他类型的消息，可能是工具调用结果
                                content = (
                                    msg.content if hasattr(msg, "content") else str(msg)
                                )
                                # 如果内容看起来像JSON，可能是工具返回
                                if content.strip().startswith(
                                    "["
                                ) or content.strip().startswith("{"):
                                    msg_type = "tool"
                                else:
                                    msg_type = "unknown"

                            # 只添加有内容的消息
                            if content and content.strip():
                                conversation_flow.append(
                                    {"type": msg_type, "content": content}
                                )

                                # 记录最后一条AI消息作为主要回复
                                if msg_type == "ai":
                                    ai_response_content = content

                    # 如果没有找到用户消息，使用最后一条消息作为回复
                    if user_message_index == -1 and messages:
                        last_message = messages[-1]
                        if hasattr(last_message, "content"):
                            ai_response_content = last_message.content

                logger.info(
                    f"ChatAPIView: Successfully processed message for thread_id: {thread_id}. AI response: {ai_response_content[:100]}..."
                )
                logger.info(
                    f"ChatAPIView: Conversation flow contains {len(conversation_flow)} messages"
                )

                return Response(
                    {
                        "status": "success",
                        "code": status.HTTP_200_OK,
                        "message": "Message processed successfully.",
                        "data": {
                            "user_message": user_message_content,
                            "llm_response": ai_response_content,
                            "conversation_flow": conversation_flow,  # 新增：完整的对话流程
                            "active_llm": active_config.name,
                            "thread_id": thread_id,
                            "session_id": session_id,
                            "project_id": project_id,
                            "project_name": project.name,
                            # 知识库相关信息
                            "knowledge_base_id": knowledge_base_id,
                            "use_knowledge_base": use_knowledge_base,
                            "knowledge_base_used": bool(
                                knowledge_base_id and use_knowledge_base
                            ),
                        },
                    },
                    status=status.HTTP_200_OK,
                )

        except Exception as e:  # This outer try-except catches errors from the 'with SqliteSaver' block or LLM init
            logger.error(
                f"ChatAPIView: Error interacting with LLM or LangGraph: {e}",
                exc_info=True,
            )
            friendly_error = get_user_friendly_llm_error(e)
            if friendly_error:
                return Response(
                    {
                        "status": "error",
                        "code": friendly_error["status_code"],
                        "message": friendly_error["message"],
                        "data": {},
                        "errors": friendly_error["errors"],
                    },
                    status=friendly_error["status_code"],
                )
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "message": f"Error interacting with LLM or LangGraph: {str(e)}",
                    "data": {},
                    "errors": {"llm_interaction": [str(e)]},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ChatHistoryAPIView(APIView):
    """
    根据 session_id 获取聊天历史的 API 端点。
    支持项目隔离，只能获取指定项目的聊天记录。
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        session_id = request.query_params.get("session_id")
        project_id = request.query_params.get("project_id")

        if not session_id:
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "session_id query parameter is required.",
                    "data": {},
                    "errors": {"session_id": ["This field is required."]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not project_id:
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "project_id query parameter is required.",
                    "data": {},
                    "errors": {"project_id": ["This field is required."]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 检查项目权限
        project = check_project_permission(request.user, project_id)
        if not project:
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_403_FORBIDDEN,
                    "message": "You don't have permission to access this project or project doesn't exist.",
                    "data": {},
                    "errors": {
                        "project_id": ["Permission denied or project not found."]
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # 获取会话信息（包括关联的提示词）
        prompt_id = None
        prompt_name = None
        try:
            chat_session = ChatSession.objects.select_related("prompt").get(
                session_id=session_id, user=request.user, project_id=project_id
            )
            if chat_session.prompt:
                prompt_id = chat_session.prompt.id
                prompt_name = chat_session.prompt.name
        except ChatSession.DoesNotExist:
            pass  # 会话可能还没创建到数据库

        thread_id_parts = [str(request.user.id), str(project_id), str(session_id)]
        thread_id = "_".join(thread_id_parts)

        history_messages = []

        try:
            # 使用统一的 Checkpointer 读取数据
            from wharttest_django.checkpointer import (
                get_database_type,
                get_db_connection_string,
            )

            db_type = get_database_type()
            conn_str = get_db_connection_string()
            logger.warning(
                f"ChatHistoryAPIView: DEBUG - database_type={db_type}, connection={conn_str}"
            )

            with get_sync_checkpointer() as memory:
                logger.warning(
                    f"ChatHistoryAPIView: DEBUG - Checkpointer type={type(memory).__name__}"
                )
                checkpoint_generator = memory.list(
                    config={"configurable": {"thread_id": thread_id}}
                )
                checkpoint_tuples_list = list(checkpoint_generator)

                logger.info(
                    f"ChatHistoryAPIView: Found {len(checkpoint_tuples_list)} checkpoints for thread_id: {thread_id}"
                )

                if checkpoint_tuples_list:  # Check if the list is not empty
                    # 构建消息到时间戳的映射
                    # 遍历所有checkpoints，为每条新消息分配对应checkpoint的时间戳
                    message_timestamps = {}
                    processed_message_count = 0

                    # 按时间顺序处理checkpoints（从旧到新）
                    for checkpoint_tuple in reversed(checkpoint_tuples_list):
                        if checkpoint_tuple and hasattr(checkpoint_tuple, "checkpoint"):
                            checkpoint_data = checkpoint_tuple.checkpoint
                            if (
                                checkpoint_data
                                and "channel_values" in checkpoint_data
                                and "messages" in checkpoint_data["channel_values"]
                            ):
                                messages = checkpoint_data["channel_values"]["messages"]
                                current_message_count = len(messages)

                                # 如果这个checkpoint有新消息，为新消息分配时间戳
                                if current_message_count > processed_message_count:
                                    checkpoint_timestamp = checkpoint_data.get("ts")
                                    if checkpoint_timestamp:
                                        # 为新增的消息分配时间戳
                                        for i in range(
                                            processed_message_count,
                                            current_message_count,
                                        ):
                                            message_timestamps[i] = checkpoint_timestamp
                                    processed_message_count = current_message_count

                    # 获取最新checkpoint的消息列表
                    latest_checkpoint_tuple = checkpoint_tuples_list[0]
                    logger.info(
                        f"ChatHistoryAPIView: latest_checkpoint_tuple type={type(latest_checkpoint_tuple).__name__}"
                    )
                    if latest_checkpoint_tuple and hasattr(
                        latest_checkpoint_tuple, "checkpoint"
                    ):
                        checkpoint_data = latest_checkpoint_tuple.checkpoint
                        logger.info(
                            f"ChatHistoryAPIView: checkpoint_data type={type(checkpoint_data).__name__}, keys={list(checkpoint_data.keys()) if isinstance(checkpoint_data, dict) else 'N/A'}"
                        )
                        if (
                            isinstance(checkpoint_data, dict)
                            and "channel_values" in checkpoint_data
                        ):
                            channel_values = checkpoint_data["channel_values"]
                            logger.info(
                                f"ChatHistoryAPIView: channel_values keys={list(channel_values.keys()) if isinstance(channel_values, dict) else 'N/A'}"
                            )

                        if (
                            checkpoint_data
                            and "channel_values" in checkpoint_data
                            and "messages" in checkpoint_data["channel_values"]
                        ):
                            messages = checkpoint_data["channel_values"]["messages"]
                            logger.info(
                                f"ChatHistoryAPIView: Found {len(messages)} messages in latest checkpoint"
                            )

                            for i, msg in enumerate(messages):
                                msg_type = "unknown"
                                content = ""

                                if isinstance(msg, SystemMessage):
                                    msg_type = "system"
                                    content = (
                                        msg.content
                                        if hasattr(msg, "content")
                                        else str(msg)
                                    )
                                elif isinstance(msg, HumanMessage):
                                    msg_type = "human"
                                    raw_content = (
                                        msg.content
                                        if hasattr(msg, "content")
                                        else str(msg)
                                    )
                                    # 处理多模态消息（包含图片的列表格式）
                                    image_data = None  # 用于存储图片数据（兼容旧单图字段）
                                    image_data_list = []  # 用于存储多图数据
                                    if isinstance(raw_content, list):
                                        # 提取文本部分 + 图片部分
                                        text_parts = []
                                        image_urls = []
                                        for item in raw_content:
                                            if isinstance(item, dict):
                                                if item.get("type") == "text":
                                                    text_parts.append(
                                                        item.get("text", "")
                                                    )
                                                elif item.get("type") == "image_url":
                                                    # 提取图片URL中的Base64数据
                                                    image_url = item.get(
                                                        "image_url", {}
                                                    )
                                                    if isinstance(image_url, dict):
                                                        url = image_url.get("url", "")
                                                        # url格式: data:image/jpeg;base64,xxx
                                                        if url and url.startswith(
                                                            "data:image/"
                                                        ):
                                                            image_urls.append(url)

                                        # 保留原文本格式（拼接而不是用空格连接），避免破坏Markdown/换行
                                        content = (
                                            "".join(text_parts)
                                            if text_parts
                                            else "[包含图片的消息]"
                                        )

                                        # 如果文本中已经包含需求文档图片占位符/URL，则不再通过 image 字段额外展示图片，避免重复
                                        has_requirement_doc_images = isinstance(
                                            content, str
                                        ) and (
                                            "docimg://" in content
                                            or "/api/requirements/documents/" in content
                                        )

                                        if image_urls and not has_requirement_doc_images:
                                            image_data_list = image_urls
                                            if len(image_urls) == 1:
                                                image_data = image_urls[0]
                                    else:
                                        content = raw_content
                                elif isinstance(msg, AIMessage):
                                    msg_type = "ai"
                                    raw_content = (
                                        msg.content
                                        if hasattr(msg, "content")
                                        else str(msg)
                                    )
                                    # AI消息通常不是多模态，但为了安全也检查一下
                                    if isinstance(raw_content, list):
                                        text_parts = [
                                            item.get("text", "")
                                            for item in raw_content
                                            if isinstance(item, dict)
                                            and item.get("type") == "text"
                                        ]
                                        content = (
                                            " ".join(text_parts) if text_parts else ""
                                        )
                                    else:
                                        content = raw_content

                                    # 跳过空的AI消息（工具调用前的中间状态）
                                    if not content or (
                                        isinstance(content, str)
                                        and content.strip() == ""
                                    ):
                                        logger.debug(
                                            f"ChatHistoryAPIView: Skipping empty AI message at index {i}"
                                        )
                                        continue

                                    # ⭐ 提取 additional_kwargs 中的 metadata（包含 Agent Loop 元数据）
                                    agent_info = None
                                    agent_type = None
                                    step = None
                                    max_steps = None
                                    sse_event_type = None

                                    if (
                                        hasattr(msg, "additional_kwargs")
                                        and msg.additional_kwargs
                                    ):
                                        # 兼容旧格式（直接存在 additional_kwargs）
                                        agent_info = msg.additional_kwargs.get("agent")
                                        agent_type = msg.additional_kwargs.get(
                                            "agent_type"
                                        )

                                        # ⭐ 从 metadata 子字段提取（新格式）
                                        metadata = msg.additional_kwargs.get(
                                            "metadata", {}
                                        )
                                        if metadata:
                                            agent_info = agent_info or metadata.get(
                                                "agent"
                                            )
                                            agent_type = agent_type or metadata.get(
                                                "agent_type"
                                            )
                                            step = metadata.get("step")
                                            max_steps = metadata.get("max_steps")
                                            sse_event_type = metadata.get(
                                                "sse_event_type"
                                            )

                                        logger.debug(
                                            f"ChatHistoryAPIView: AI message metadata - agent: {agent_info}, type: {agent_type}, step: {step}, sse_type: {sse_event_type}"
                                        )

                                elif isinstance(msg, ToolMessage):
                                    msg_type = "tool"
                                    content = (
                                        msg.content
                                        if hasattr(msg, "content")
                                        else str(msg)
                                    )

                                    # ⭐ 提取工具消息的元数据
                                    step = None
                                    sse_event_type = None
                                    if (
                                        hasattr(msg, "additional_kwargs")
                                        and msg.additional_kwargs
                                    ):
                                        metadata = msg.additional_kwargs.get(
                                            "metadata", {}
                                        )
                                        if metadata:
                                            step = metadata.get("step")
                                            sse_event_type = metadata.get(
                                                "sse_event_type"
                                            )
                                        logger.debug(
                                            f"ChatHistoryAPIView: Tool message metadata - step: {step}, sse_type: {sse_event_type}"
                                        )
                                else:
                                    # 处理其他类型的消息，可能是工具调用结果
                                    content = (
                                        msg.content
                                        if hasattr(msg, "content")
                                        else str(msg)
                                    )
                                    # 如果内容看起来像JSON，可能是工具返回
                                    if content.strip().startswith(
                                        "["
                                    ) or content.strip().startswith("{"):
                                        msg_type = "tool"
                                    else:
                                        msg_type = "unknown"

                                logger.debug(
                                    f"ChatHistoryAPIView: Message {i}: type={msg_type}, content={str(content)[:50]}..."
                                )

                                # 只添加有内容的消息
                                if content and (
                                    not isinstance(content, str) or content.strip()
                                ):
                                    message_data = {
                                        "type": msg_type,
                                        "content": content,
                                    }
                                    # 如果消息包含图片，添加图片数据
                                    if msg_type == "human":
                                        if image_data_list:
                                            message_data["images"] = image_data_list
                                        if image_data:
                                            message_data["image"] = image_data

                                    # ⭐ 如果 AI 消息包含 agent 信息（Agent Loop），添加完整元数据
                                    if msg_type == "ai":
                                        if "agent_info" in locals() and agent_info:
                                            message_data["agent"] = agent_info
                                        if "agent_type" in locals() and agent_type:
                                            message_data["agent_type"] = agent_type
                                        if "step" in locals() and step is not None:
                                            message_data["step"] = step  # ⭐ 步骤号
                                        if (
                                            "max_steps" in locals()
                                            and max_steps is not None
                                        ):
                                            message_data["max_steps"] = max_steps
                                        if (
                                            "sse_event_type" in locals()
                                            and sse_event_type
                                        ):
                                            message_data["sse_event_type"] = (
                                                sse_event_type  # ⭐ SSE 事件类型
                                            )

                                        # 检查是否是思考过程消息
                                        if (
                                            hasattr(msg, "additional_kwargs")
                                            and msg.additional_kwargs
                                        ):
                                            metadata = msg.additional_kwargs.get(
                                                "metadata", {}
                                            )
                                            if metadata.get("is_thinking_process"):
                                                message_data["is_thinking_process"] = (
                                                    True
                                                )

                                    # ⭐ 如果是工具消息，添加步骤号和事件类型
                                    elif msg_type == "tool":
                                        if "step" in locals() and step is not None:
                                            message_data["step"] = step
                                        if (
                                            "sse_event_type" in locals()
                                            and sse_event_type
                                        ):
                                            message_data["sse_event_type"] = (
                                                sse_event_type
                                            )

                                    # 添加对应的时间戳
                                    if i in message_timestamps:
                                        timestamp_str = message_timestamps[i]
                                        try:
                                            # 解析ISO时间戳并转换为本地时间
                                            from datetime import datetime

                                            dt = datetime.fromisoformat(
                                                timestamp_str.replace("Z", "+00:00")
                                            )
                                            # 转换为本地时间
                                            local_dt = dt.astimezone()
                                            # 格式化为本地时间字符串
                                            message_data["timestamp"] = (
                                                local_dt.strftime("%Y-%m-%d %H:%M:%S")
                                            )
                                        except Exception as e:
                                            # 如果解析失败，只返回原始字符串
                                            logger.warning(
                                                f"ChatHistoryAPIView: Failed to parse timestamp {timestamp_str}: {e}"
                                            )
                                            message_data["timestamp"] = timestamp_str

                                    history_messages.append(message_data)
                        else:
                            logger.warning(
                                f"ChatHistoryAPIView: No messages found in checkpoint data structure"
                            )
                    else:
                        logger.warning(
                            f"ChatHistoryAPIView: Invalid checkpoint tuple structure"
                        )
                else:
                    logger.info(
                        f"ChatHistoryAPIView: No checkpoints found for thread_id: {thread_id}"
                    )
            # 仅处理最新 checkpoint，可拿到最终消息状态并避免重复。

            # 获取当前上下文Token使用信息（取最后一条 AI 消息的 usage_metadata）
            context_token_count = 0
            context_limit = 128000
            try:
                active_config = LLMConfig.objects.get(is_active=True)
                context_limit = active_config.context_limit or 128000

                # 获取最后一次 LLM 调用的 token 使用量
                # 注意：每次 LLM 返回的 input_tokens 已包含完整上下文，不能累加
                if "messages" in locals() and messages:
                    for msg in reversed(messages):
                        if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                            input_tokens = msg.usage_metadata.get("input_tokens", 0)
                            output_tokens = msg.usage_metadata.get("output_tokens", 0)
                            context_token_count = input_tokens + output_tokens
                            break  # 只取最后一条有 usage_metadata 的消息
            except Exception as e:
                logger.warning(
                    f"ChatHistoryAPIView: Failed to calculate token count: {e}"
                )

            return Response(
                {
                    "status": "success",
                    "code": status.HTTP_200_OK,
                    "message": "Chat history retrieved successfully.",
                    "data": {
                        "thread_id": thread_id,
                        "session_id": session_id,
                        "project_id": project_id,
                        "project_name": project.name,
                        "prompt_id": prompt_id,
                        "prompt_name": prompt_name,
                        "history": history_messages,
                        "context_token_count": context_token_count,
                        "context_limit": context_limit,
                    },
                },
                status=status.HTTP_200_OK,
            )

        except FileNotFoundError:
            return Response(
                {
                    "status": "success",
                    "code": status.HTTP_200_OK,  # 如需区分“无历史文件”场景，也可按需返回 404
                    "message": "No chat history found for this session (history file does not exist).",
                    "data": {
                        "thread_id": thread_id,
                        "session_id": session_id,
                        "history": [],
                    },
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "message": f"Error retrieving chat history: {str(e)}",
                    "data": {},
                    "errors": {"history_retrieval": [str(e)]},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, *args, **kwargs):
        session_id = request.query_params.get("session_id")
        project_id = request.query_params.get("project_id")

        if not session_id:
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "session_id query parameter is required.",
                    "data": {},
                    "errors": {"session_id": ["This field is required."]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not project_id:
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "project_id query parameter is required.",
                    "data": {},
                    "errors": {"project_id": ["This field is required."]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 检查项目权限
        project = check_project_permission(request.user, project_id)
        if not project:
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_403_FORBIDDEN,
                    "message": "You don't have permission to access this project or project doesn't exist.",
                    "data": {},
                    "errors": {
                        "project_id": ["Permission denied or project not found."]
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        thread_id_parts = [str(request.user.id), str(project_id), str(session_id)]
        thread_id = "_".join(thread_id_parts)

        if not check_history_exists():
            return Response(
                {
                    "status": "success",
                    "code": status.HTTP_200_OK,
                    "message": "No chat history found to delete (history storage does not exist).",
                    "data": {
                        "thread_id": thread_id,
                        "session_id": session_id,
                        "deleted_count": 0,
                    },
                },
                status=status.HTTP_200_OK,
            )

        try:
            deleted_count = delete_checkpoints_by_thread_id(thread_id)

            # 同时删除 Django ChatSession 记录
            django_deleted_count = 0
            try:
                deleted_result = ChatSession.objects.filter(
                    session_id=session_id, user=request.user, project=project
                ).delete()
                django_deleted_count = deleted_result[0]
                logger.info(
                    f"ChatHistoryAPIView: Deleted {django_deleted_count} ChatSession records for session_id: {session_id}"
                )
            except Exception as e:
                logger.warning(
                    f"ChatHistoryAPIView: Failed to delete ChatSession for {session_id}: {e}"
                )

            if deleted_count > 0 or django_deleted_count > 0:
                message = f"Successfully deleted chat history for session_id: {session_id} (Thread ID: {thread_id}). {deleted_count} checkpoint records and {django_deleted_count} session records removed."
            else:
                message = f"No chat history found for session_id: {session_id} (Thread ID: {thread_id}) to delete."

            return Response(
                {
                    "status": "success",
                    "code": status.HTTP_200_OK,
                    "message": message,
                    "data": {
                        "thread_id": thread_id,
                        "session_id": session_id,
                        "deleted_count": deleted_count,
                        "session_deleted_count": django_deleted_count,
                    },
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "message": f"Database error while deleting chat history: {str(e)}",
                    "data": {},
                    "errors": {"database_error": [str(e)]},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def patch(self, request, *args, **kwargs):
        """
        回滚聊天历史到指定消息数量
        保留前 keep_count 条消息，删除之后的所有消息
        """
        session_id = request.query_params.get("session_id")
        project_id = request.query_params.get("project_id")
        keep_count = request.data.get("keep_count")

        if not session_id:
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "session_id query parameter is required.",
                    "data": {},
                    "errors": {"session_id": ["This field is required."]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not project_id:
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "project_id query parameter is required.",
                    "data": {},
                    "errors": {"project_id": ["This field is required."]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if keep_count is None or not isinstance(keep_count, int) or keep_count < 0:
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "keep_count must be a non-negative integer.",
                    "data": {},
                    "errors": {
                        "keep_count": ["This field must be a non-negative integer."]
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 检查项目权限
        project = check_project_permission(request.user, project_id)
        if not project:
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_403_FORBIDDEN,
                    "message": "You don't have permission to access this project or project doesn't exist.",
                    "data": {},
                    "errors": {
                        "project_id": ["Permission denied or project not found."]
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        thread_id_parts = [str(request.user.id), str(project_id), str(session_id)]
        thread_id = "_".join(thread_id_parts)

        if not check_history_exists():
            return Response(
                {
                    "status": "success",
                    "code": status.HTTP_200_OK,
                    "message": "No chat history found to rollback (history storage does not exist).",
                    "data": {
                        "thread_id": thread_id,
                        "session_id": session_id,
                        "deleted_count": 0,
                    },
                },
                status=status.HTTP_200_OK,
            )

        try:
            deleted_count = rollback_checkpoints_to_count(thread_id, keep_count)

            if deleted_count > 0:
                message = f"Successfully rolled back chat history for session_id: {session_id}. Kept {keep_count} checkpoints, removed {deleted_count} checkpoints."
            else:
                message = f"No checkpoints to remove for session_id: {session_id}. Current count is already at or below {keep_count}."

            logger.info(f"ChatHistoryAPIView PATCH: {message}")

            return Response(
                {
                    "status": "success",
                    "code": status.HTTP_200_OK,
                    "message": message,
                    "data": {
                        "thread_id": thread_id,
                        "session_id": session_id,
                        "deleted_count": deleted_count,
                        "kept_count": keep_count,
                    },
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"ChatHistoryAPIView PATCH error: {str(e)}")
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "message": f"Database error while rolling back chat history: {str(e)}",
                    "data": {},
                    "errors": {"database_error": [str(e)]},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ChatBatchDeleteAPIView(APIView):
    """
    批量删除聊天会话的 API 端点。
    批量删除聊天会话的API端点。
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """批量删除聊天会话"""
        session_ids = request.data.get("session_ids", [])
        project_id = request.data.get("project_id")

        if not session_ids or not isinstance(session_ids, list):
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "session_ids must be a non-empty list.",
                    "data": {},
                    "errors": {
                        "session_ids": ["This field is required and must be a list."]
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not project_id:
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "project_id is required.",
                    "data": {},
                    "errors": {"project_id": ["This field is required."]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 检查项目权限
        project = check_project_permission(request.user, project_id)
        if not project:
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_403_FORBIDDEN,
                    "message": "You don't have permission to access this project or project doesn't exist.",
                    "data": {},
                    "errors": {
                        "project_id": ["Permission denied or project not found."]
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if not check_history_exists():
            return Response(
                {
                    "status": "success",
                    "code": status.HTTP_200_OK,
                    "message": "No chat history found to delete (history storage does not exist).",
                    "data": {"deleted_count": 0, "failed_sessions": []},
                },
                status=status.HTTP_200_OK,
            )

        total_deleted = 0
        failed_sessions = []

        try:
            # 构建所有 thread_ids
            thread_ids = []
            for session_id in session_ids:
                thread_id_parts = [
                    str(request.user.id),
                    str(project_id),
                    str(session_id),
                ]
                thread_ids.append("_".join(thread_id_parts))

            # 批量删除 checkpoints
            total_deleted = delete_checkpoints_batch(thread_ids)

            # 删除 Django 中的 ChatSession 记录
            for session_id in session_ids:
                try:
                    ChatSession.objects.filter(
                        session_id=session_id, user=request.user, project=project
                    ).delete()
                except Exception as e:
                    logger.warning(
                        f"Failed to delete ChatSession for {session_id}: {e}"
                    )
                    failed_sessions.append({"session_id": session_id, "reason": str(e)})

            message = f"Successfully deleted {total_deleted} checkpoint records from {len(session_ids)} sessions."
            if failed_sessions:
                message += f" {len(failed_sessions)} sessions had issues with Django model deletion."

            return Response(
                {
                    "status": "success",
                    "code": status.HTTP_200_OK,
                    "message": message,
                    "data": {
                        "deleted_count": total_deleted,
                        "processed_sessions": len(session_ids),
                        "failed_sessions": failed_sessions,
                    },
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Error during batch delete: {e}", exc_info=True)
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "message": f"Database error while batch deleting chat history: {str(e)}",
                    "data": {},
                    "errors": {"database_error": [str(e)]},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserChatSessionsAPIView(APIView):
    """
    查询认证用户在指定项目下全部聊天会话的 API 端点。
    支持项目隔离，只返回指定项目的聊天会话。
    优先从Django ChatSession模型读取（带标题和时间），回退到sqlite查询session_id。
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user_id = str(request.user.id)
        project_id = request.query_params.get("project_id")

        if not project_id:
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "project_id query parameter is required.",
                    "data": {},
                    "errors": {"project_id": ["This field is required."]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 检查项目权限
        project = check_project_permission(request.user, project_id)
        if not project:
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_403_FORBIDDEN,
                    "message": "You don't have permission to access this project or project doesn't exist.",
                    "data": {},
                    "errors": {
                        "project_id": ["Permission denied or project not found."]
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # 优先从Django ChatSession模型读取会话列表（带标题和时间，无需查sqlite）
        django_sessions = (
            ChatSession.objects.filter(user=request.user, project_id=project_id)
            .order_by("-updated_at")
            .values("session_id", "title", "updated_at", "created_at")
        )

        sessions_list = []
        django_session_ids = set()

        for s in django_sessions:
            django_session_ids.add(s["session_id"])
            sessions_list.append(
                {
                    "id": s["session_id"],
                    "title": s["title"] or "新对话",
                    "updated_at": s["updated_at"].isoformat()
                    if s["updated_at"]
                    else None,
                    "created_at": s["created_at"].isoformat()
                    if s["created_at"]
                    else None,
                }
            )

        # 回退：检查checkpoints中是否有Django模型没记录的会话
        if check_history_exists():
            try:
                thread_id_prefix = f"{user_id}_{project_id}_"
                thread_ids = get_thread_ids_by_prefix(thread_id_prefix)

                for full_thread_id in thread_ids:
                    if full_thread_id.startswith(thread_id_prefix):
                        session_id_part = full_thread_id[len(thread_id_prefix) :]
                        if (
                            session_id_part
                            and session_id_part not in django_session_ids
                        ):
                            # checkpoints有但Django没有的会话，添加到列表
                            sessions_list.append(
                                {
                                    "id": session_id_part,
                                    "title": f"会话 {session_id_part[:8]}...",
                                    "updated_at": None,
                                    "created_at": None,
                                }
                            )
            except Exception as e:
                logger.warning(
                    f"UserChatSessionsAPIView: Failed to check checkpoints for additional sessions: {e}"
                )

        return Response(
            {
                "status": "success",
                "code": status.HTTP_200_OK,
                "message": "User chat sessions retrieved successfully.",
                "data": {
                    "user_id": user_id,
                    "project_id": project_id,
                    "project_name": project.name,
                    "sessions": [s["id"] for s in sessions_list],  # 保持向后兼容
                    "sessions_detail": sessions_list,  # 新增：带详情的会话列表
                },
            },
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class ChatResumeAPIView(View):
    """
    HITL Resume API - 处理用户对工具调用的审批决定

    当 AgentLoopStreamAPIView 返回 interrupt 事件后，前端调用此 API 恢复执行。
    使用 LangGraph 的 Command(resume=...) 模式。
    """

    async def authenticate_request(self, request):
        """手动进行JWT认证（异步版本）"""
        auth_header = request.META.get("HTTP_AUTHORIZATION")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise AuthenticationFailed("Authentication credentials were not provided.")

        token = auth_header.split(" ")[1]
        jwt_auth = JWTAuthentication()

        try:
            validated_token = await sync_to_async(jwt_auth.get_validated_token)(token)
            user = await sync_to_async(jwt_auth.get_user)(validated_token)
            return user
        except Exception as e:
            raise AuthenticationFailed(f"Invalid token: {str(e)}")

    async def _create_resume_generator(
        self, request, thread_id, decision_type, session_id, project_id
    ):
        """创建恢复执行的 SSE 生成器"""
        from langgraph.types import Command

        try:
            active_config = await sync_to_async(LLMConfig.objects.get)(is_active=True)
            logger.info(
                f"ChatResumeAPIView: Using active LLMConfig: {active_config.name}"
            )
        except LLMConfig.DoesNotExist:
            yield create_sse_data(
                {"type": "error", "message": "No active LLM configuration found"}
            )
            return

        try:
            llm = create_llm_instance(active_config, temperature=0.7)

            async with get_async_checkpointer() as actual_memory_checkpointer:
                # 加载 MCP 工具（与 AgentLoopStreamAPIView 相同逻辑）
                mcp_tools_list = []
                try:
                    active_remote_mcp_configs = await sync_to_async(list)(
                        RemoteMCPConfig.objects.filter(is_active=True)
                    )
                    if active_remote_mcp_configs:
                        client_mcp_config = {}
                        for r_config in active_remote_mcp_configs:
                            config_key = r_config.name or f"remote_config_{r_config.id}"
                            client_mcp_config[config_key] = {
                                "url": r_config.url,
                                "transport": (
                                    r_config.transport or "streamable_http"
                                ).replace("-", "_"),
                            }
                            if r_config.headers:
                                client_mcp_config[config_key]["headers"] = (
                                    r_config.headers
                                )

                        if client_mcp_config:
                            mcp_tools_list = (
                                await mcp_session_manager.get_tools_for_config(
                                    client_mcp_config,
                                    user_id=str(request.user.id),
                                    project_id=str(project_id),
                                    session_id=session_id,
                                )
                            )
                except Exception as e:
                    logger.warning(f"ChatResumeAPIView: Error loading MCP tools: {e}")

                if not mcp_tools_list:
                    yield create_sse_data(
                        {"type": "error", "message": "No tools available for resume"}
                    )
                    return

                # 获取工具名列表用于 HITL
                tool_names = [t.name for t in mcp_tools_list]
                # 重建 Agent（与原始聊天相同配置）
                agent_executor = create_agent(
                    llm,
                    mcp_tools_list,
                    checkpointer=actual_memory_checkpointer,
                    middleware=get_middleware_from_config(
                        active_config,
                        llm,
                        user=request.user,
                        session_id=session_id,
                        all_tool_names=tool_names,
                    ),
                )

                invoke_config = {
                    "configurable": {"thread_id": thread_id},
                    "recursion_limit": 1000,
                }

                # 构建 resume 命令
                if decision_type == "approve":
                    resume_command = Command(
                        resume={"decisions": [{"type": "approve"}]}
                    )
                else:
                    resume_command = Command(resume={"decisions": [{"type": "reject"}]})

                logger.info(
                    f"ChatResumeAPIView: Resuming with decision={decision_type}, thread_id={thread_id}"
                )

                yield create_sse_data(
                    {
                        "type": "resume_start",
                        "thread_id": thread_id,
                        "decision": decision_type,
                    }
                )

                stream_modes = ["updates", "messages"]

                # 用于跟踪是否检测到中断
                interrupt_detected = False

                try:
                    async for stream_mode, chunk in agent_executor.astream(
                        resume_command, config=invoke_config, stream_mode=stream_modes
                    ):
                        if stream_mode == "updates":
                            # 检查是否是中断事件 (HITL)
                            if isinstance(chunk, dict) and "__interrupt__" in chunk:
                                interrupt_info = chunk["__interrupt__"]
                                logger.info(
                                    f"ChatResumeAPIView: HITL interrupt detected in stream: {interrupt_info}"
                                )

                                # 解析中断信息
                                action_requests = []
                                interrupt_id = None

                                # interrupt_info 可能是列表或单个对象
                                interrupts_list = (
                                    interrupt_info
                                    if isinstance(interrupt_info, list)
                                    else [interrupt_info]
                                )

                                for intr in interrupts_list:
                                    # 获取 interrupt ID
                                    if hasattr(intr, "id"):
                                        interrupt_id = intr.id
                                    elif isinstance(intr, dict) and "id" in intr:
                                        interrupt_id = intr["id"]

                                    # 获取 action_requests
                                    intr_value = (
                                        getattr(intr, "value", intr)
                                        if hasattr(intr, "value")
                                        else intr
                                    )

                                    if isinstance(intr_value, dict):
                                        ars = intr_value.get("action_requests", [])
                                    elif hasattr(intr_value, "action_requests"):
                                        ars = intr_value.action_requests
                                    else:
                                        ars = []

                                    for ar in ars:
                                        if isinstance(ar, dict):
                                            action_requests.append(
                                                {
                                                    "name": ar.get(
                                                        "name",
                                                        ar.get(
                                                            "action_name", "unknown"
                                                        ),
                                                    ),
                                                    "args": ar.get(
                                                        "arguments", ar.get("args", {})
                                                    ),
                                                    "description": ar.get(
                                                        "description", ""
                                                    ),
                                                }
                                            )
                                        else:
                                            action_requests.append(
                                                {
                                                    "name": getattr(
                                                        ar, "name", "unknown"
                                                    ),
                                                    "args": getattr(
                                                        ar,
                                                        "arguments",
                                                        getattr(ar, "args", {}),
                                                    ),
                                                    "description": getattr(
                                                        ar, "description", ""
                                                    ),
                                                }
                                            )

                                if action_requests:
                                    interrupt_detected = True
                                    yield create_sse_data(
                                        {
                                            "type": "interrupt",
                                            "interrupt_id": interrupt_id
                                            or str(id(interrupt_info)),
                                            "action_requests": action_requests,
                                            "session_id": session_id,
                                            "thread_id": thread_id,
                                        }
                                    )
                                    logger.info(
                                        f"ChatResumeAPIView: Sent interrupt event with {len(action_requests)} action requests"
                                    )
                            # 跳过普通 updates，只用于检测 interrupt（节省 token 和带宽）
                            continue
                        elif stream_mode == "messages":
                            if hasattr(chunk, "content") and chunk.content:
                                yield create_sse_data(
                                    {"type": "message", "data": chunk.content}
                                )
                            else:
                                yield create_sse_data(
                                    {"type": "message", "data": str(chunk)}
                                )

                        await asyncio.sleep(0.01)

                except Exception as e:
                    logger.error(
                        f"ChatResumeAPIView: Error during resume streaming: {e}",
                        exc_info=True,
                    )
                    friendly_error = get_user_friendly_llm_error(e)
                    if friendly_error:
                        yield create_sse_data(
                            {
                                "type": "error",
                                "message": friendly_error["message"],
                                "code": friendly_error["status_code"],
                                "error_code": friendly_error["error_code"],
                                "errors": friendly_error["errors"],
                            }
                        )
                    else:
                        yield create_sse_data(
                            {
                                "type": "error",
                                "message": f"Resume streaming error: {str(e)}",
                            }
                        )

                # 如果已经在流中检测到中断，直接返回
                if interrupt_detected:
                    logger.info(
                        "ChatResumeAPIView: Interrupt was detected in stream, returning early"
                    )
                    yield "data: [DONE]\n\n"
                    return

                # 备用检查 - 通过 aget_state 检查是否有新的 interrupt
                try:
                    current_state = await agent_executor.aget_state(invoke_config)
                    if current_state and hasattr(current_state, "tasks"):
                        for task in current_state.tasks:
                            if hasattr(task, "interrupts") and task.interrupts:
                                for interrupt in task.interrupts:
                                    interrupt_value = (
                                        interrupt.value
                                        if hasattr(interrupt, "value")
                                        else interrupt
                                    )
                                    action_requests = []
                                    if isinstance(interrupt_value, dict):
                                        action_requests = interrupt_value.get(
                                            "action_requests", []
                                        )
                                    elif hasattr(interrupt_value, "action_requests"):
                                        action_requests = (
                                            interrupt_value.action_requests
                                        )

                                    if action_requests:
                                        interrupt_id = getattr(
                                            interrupt, "id", None
                                        ) or str(id(interrupt))
                                        yield create_sse_data(
                                            {
                                                "type": "interrupt",
                                                "interrupt_id": interrupt_id,
                                                "action_requests": [
                                                    {
                                                        "name": ar.get(
                                                            "name",
                                                            ar.get(
                                                                "action_name", "unknown"
                                                            ),
                                                        )
                                                        if isinstance(ar, dict)
                                                        else getattr(
                                                            ar, "name", "unknown"
                                                        ),
                                                        "args": ar.get(
                                                            "arguments",
                                                            ar.get("args", {}),
                                                        )
                                                        if isinstance(ar, dict)
                                                        else getattr(
                                                            ar, "arguments", {}
                                                        ),
                                                        "description": ar.get(
                                                            "description", ""
                                                        )
                                                        if isinstance(ar, dict)
                                                        else getattr(
                                                            ar, "description", ""
                                                        ),
                                                    }
                                                    for ar in action_requests
                                                ],
                                                "session_id": session_id,
                                                "thread_id": thread_id,
                                            }
                                        )
                                        yield "data: [DONE]\n\n"
                                        return
                except Exception as e:
                    logger.warning(
                        f"ChatResumeAPIView: Error checking interrupt state: {e}"
                    )

                yield create_sse_data({"type": "complete"})
                yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(
                f"ChatResumeAPIView: Error in resume generator: {e}", exc_info=True
            )
            friendly_error = get_user_friendly_llm_error(e)
            if friendly_error:
                yield create_sse_data(
                    {
                        "type": "error",
                        "message": friendly_error["message"],
                        "code": friendly_error["status_code"],
                        "error_code": friendly_error["error_code"],
                        "errors": friendly_error["errors"],
                    }
                )
            else:
                yield create_sse_data(
                    {"type": "error", "message": f"Resume error: {str(e)}"}
                )

    async def post(self, request, *args, **kwargs):
        """处理 HITL 恢复请求"""
        try:
            user = await self.authenticate_request(request)
            request.user = user
            logger.info(
                f"ChatResumeAPIView: Received resume request from user {user.id}"
            )
        except AuthenticationFailed as e:
            from django.http import JsonResponse

            return JsonResponse({"error": str(e), "code": 401}, status=401)

        try:
            import json as json_module

            body_data = json_module.loads(request.body.decode("utf-8"))
        except (json_module.JSONDecodeError, UnicodeDecodeError) as e:
            from django.http import JsonResponse

            return JsonResponse(
                {"error": f"Invalid JSON: {str(e)}", "code": 400}, status=400
            )

        session_id = body_data.get("session_id")
        project_id = body_data.get("project_id")
        decision_type = body_data.get("decision", "approve")  # 'approve' or 'reject'

        if not project_id:
            from django.http import JsonResponse

            return JsonResponse(
                {"error": "project_id is required", "code": 400}, status=400
            )

        if not session_id:
            from django.http import JsonResponse

            return JsonResponse(
                {"error": "session_id is required", "code": 400}, status=400
            )

        # 检查项目权限
        project = await sync_to_async(check_project_permission)(
            request.user, project_id
        )
        if not project:
            from django.http import JsonResponse

            return JsonResponse(
                {"error": "Project access denied", "code": 403}, status=403
            )

        # 构建 thread_id
        thread_id = f"{request.user.id}_{project_id}_{session_id}"

        async def async_generator():
            async for chunk in self._create_resume_generator(
                request, thread_id, decision_type, session_id, project_id
            ):
                yield chunk

        response = StreamingHttpResponse(
            async_generator(), content_type="text/event-stream; charset=utf-8"
        )
        response["Cache-Control"] = "no-cache"
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Headers"] = "Cache-Control"

        return response


class ProviderChoicesAPIView(APIView):
    """获取可用的LLM供应商选项"""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """返回所有可用的供应商选项"""
        choices = [
            {"value": choice[0], "label": choice[1]}
            for choice in LLMConfig.PROVIDER_CHOICES
        ]
        return Response(
            {
                "status": "success",
                "code": status.HTTP_200_OK,
                "message": "Provider choices retrieved successfully.",
                "data": {"choices": choices},
            }
        )


class KnowledgeRAGAPIView(APIView):
    """知识库RAG查询API视图"""

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """执行知识库RAG查询"""
        try:
            # 获取请求参数
            query = request.data.get("query")
            knowledge_base_id = request.data.get("knowledge_base_id")
            project_id = request.data.get("project_id")

            if not query:
                return Response(
                    {"error": "查询内容不能为空"}, status=status.HTTP_400_BAD_REQUEST
                )

            if not knowledge_base_id:
                return Response(
                    {"error": "知识库ID不能为空"}, status=status.HTTP_400_BAD_REQUEST
                )

            # 验证项目权限
            if project_id:
                try:
                    project = Project.objects.get(id=project_id)
                    if (
                        not project.members.filter(user=request.user).exists()
                        and not request.user.is_superuser
                    ):
                        return Response(
                            {"error": "您没有权限访问此项目"},
                            status=status.HTTP_403_FORBIDDEN,
                        )
                except Project.DoesNotExist:
                    return Response(
                        {"error": "项目不存在"}, status=status.HTTP_404_NOT_FOUND
                    )

            # 验证知识库权限
            try:
                knowledge_base = KnowledgeBase.objects.get(id=knowledge_base_id)
                if (
                    not knowledge_base.project.members.filter(
                        user=request.user
                    ).exists()
                    and not request.user.is_superuser
                ):
                    return Response(
                        {"error": "您没有权限访问此知识库"},
                        status=status.HTTP_403_FORBIDDEN,
                    )
            except KnowledgeBase.DoesNotExist:
                return Response(
                    {"error": "知识库不存在"}, status=status.HTTP_404_NOT_FOUND
                )

            # 获取LLM配置
            try:
                active_config = LLMConfig.objects.filter(is_active=True).first()
                if not active_config:
                    return Response(
                        {"error": "没有可用的LLM配置"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

                # 使用新的LLM工厂函数，支持多供应商
                llm = create_llm_instance(active_config, temperature=0.7)
            except Exception as e:
                logger.error(f"LLM配置错误: {e}")
                return Response(
                    {"error": "LLM配置错误"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # 执行RAG查询
            rag_service = KnowledgeRAGService(llm)
            result = rag_service.query(
                question=query, knowledge_base_id=knowledge_base_id, user=request.user
            )

            return Response(
                {
                    "query": result["question"],
                    "answer": result["answer"],
                    "sources": result["context"],
                    "retrieval_time": result["retrieval_time"],
                    "generation_time": result["generation_time"],
                    "total_time": result["total_time"],
                }
            )

        except Exception as e:
            logger.error(f"知识库RAG查询失败: {e}")
            return Response(
                {"error": f"查询失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ============== 用户工具审批偏好 API ==============

from .models import UserToolApproval
from .serializers import UserToolApprovalSerializer, UserToolApprovalBatchSerializer


class UserToolApprovalViewSet(viewsets.ModelViewSet):
    """
    用户工具审批偏好管理

    支持"记住审批选择"功能：
    - 用户在 HITL 审批时可选择"始终允许"或"始终拒绝"
    - 后续相同工具的调用将自动应用已保存的决策
    """

    serializer_class = UserToolApprovalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """只返回当前用户的审批偏好"""
        return UserToolApproval.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """创建时自动关联当前用户"""
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["get"])
    def available_tools(self, request):
        """
        获取可配置审批偏好的工具列表

        返回所有工具及其当前用户的偏好设置，按 MCP 分组
        数据来源：
        1. 内置工具（Skill 工具、Diagram 工具）
        2. MCPTool - 从数据库读取的 MCP 工具
        """
        from mcp_tools.models import MCPTool

        user = request.user
        session_id = request.query_params.get("session_id")

        # 获取用户当前的偏好
        user_approvals = {}
        approvals = UserToolApproval.objects.filter(user=user)
        if session_id:
            approvals = approvals.filter(
                Q(scope="permanent") | Q(scope="session", session_id=session_id)
            )
        else:
            approvals = approvals.filter(scope="permanent")

        for approval in approvals:
            user_approvals[approval.tool_name] = {
                "policy": approval.policy,
                "scope": approval.scope,
            }

        # 构建返回数据：分组展示
        tool_groups = []

        # 1. 内置工具组（按实际工具分类展示）
        # Skill 工具
        skill_builtin_tools = [
            {
                "tool_name": "read_skill_content",
                "description": "读取 Skill 的 SKILL.md 内容",
            },
            {
                "tool_name": "execute_skill_script",
                "description": "执行 Skill 脚本命令，支持单个或批量并发执行（需审批）",
            },
        ]

        # 组装 Skill 组
        skill_tools_for_display = []
        for t in skill_builtin_tools:
            skill_tools_for_display.append(
                {
                    "tool_name": t["tool_name"],
                    "description": t["description"],
                    "allowed_decisions": ["approve", "reject"],
                    "current_policy": user_approvals.get(t["tool_name"], {}).get(
                        "policy", "ask_every_time"
                    ),
                    "current_scope": user_approvals.get(t["tool_name"], {}).get(
                        "scope", "permanent"
                    ),
                }
            )
        tool_groups.append(
            {
                "group_name": "Skill 工具",
                "group_id": "builtin_skill",
                "tools": skill_tools_for_display,
            }
        )

        # 2. MCP 工具组（从数据库读取，按 MCP 分组）
        # 注意：Diagram 工具（display_diagram, edit_diagram）已移至 WHartTest-Tools MCP
        from mcp_tools.models import RemoteMCPConfig

        mcp_configs = RemoteMCPConfig.objects.filter(is_active=True).prefetch_related(
            "tools"
        )

        for mcp_config in mcp_configs:
            mcp_tools = []
            for tool in mcp_config.tools.all():
                mcp_tools.append(
                    {
                        "tool_name": tool.name,
                        "description": tool.description
                        or f"[{mcp_config.name}] {tool.name}",
                        "allowed_decisions": ["approve", "reject"],
                        "current_policy": user_approvals.get(tool.name, {}).get(
                            "policy", "ask_every_time"
                        ),
                        "current_scope": user_approvals.get(tool.name, {}).get(
                            "scope", "permanent"
                        ),
                        "require_hitl": tool.effective_require_hitl,
                    }
                )

            if mcp_tools:
                tool_groups.append(
                    {
                        "group_name": mcp_config.name,
                        "group_id": f"mcp_{mcp_config.id}",
                        "tools": mcp_tools,
                    }
                )

        # 兼容旧版：扁平化的工具列表
        all_tools = []
        for group in tool_groups:
            all_tools.extend(group["tools"])

        return Response(
            {
                "tools": all_tools,  # 兼容旧版前端
                "tool_groups": tool_groups,  # 新版分组数据
                "policy_choices": [
                    {"value": "always_allow", "label": "始终允许"},
                    {"value": "always_reject", "label": "始终拒绝"},
                    {"value": "ask_every_time", "label": "每次询问"},
                ],
                "scope_choices": [
                    {"value": "session", "label": "仅本次会话"},
                    {"value": "permanent", "label": "永久生效"},
                ],
            }
        )

    @action(detail=False, methods=["post"])
    def batch_update(self, request):
        """
        批量更新工具审批偏好

        请求体示例：
        {
            "approvals": [
                {"tool_name": "execute_script", "policy": "always_allow", "scope": "permanent"},
                {"tool_name": "run_playwright", "policy": "ask_every_time", "scope": "session", "session_id": "xxx"}
            ]
        }
        """
        user = request.user
        approvals_data = request.data.get("approvals", [])

        if not approvals_data:
            return Response(
                {"error": "请提供要更新的审批偏好"}, status=status.HTTP_400_BAD_REQUEST
            )

        updated = []
        errors = []

        for item in approvals_data:
            serializer = UserToolApprovalBatchSerializer(data=item)
            if not serializer.is_valid():
                errors.append(
                    {
                        "tool_name": item.get("tool_name", "unknown"),
                        "errors": serializer.errors,
                    }
                )
                continue

            data = serializer.validated_data
            tool_name = data["tool_name"]
            policy = data["policy"]
            scope = data.get("scope", "permanent")
            session_id = data.get("session_id")

            # 查找或创建偏好记录
            if scope == "permanent":
                approval, created = UserToolApproval.objects.update_or_create(
                    user=user,
                    tool_name=tool_name,
                    scope="permanent",
                    defaults={"policy": policy, "session_id": None},
                )
            else:
                approval, created = UserToolApproval.objects.update_or_create(
                    user=user,
                    tool_name=tool_name,
                    scope="session",
                    session_id=session_id,
                    defaults={"policy": policy},
                )

            updated.append(
                {
                    "tool_name": tool_name,
                    "policy": policy,
                    "scope": scope,
                    "created": created,
                }
            )

        return Response({"updated": updated, "errors": errors if errors else None})

    @action(detail=False, methods=["post"])
    def reset(self, request):
        """
        重置用户的工具审批偏好

        可选参数：
        - tool_name: 只重置指定工具的偏好
        - scope: 只重置指定范围的偏好 (session/permanent)
        - session_id: 只重置指定会话的偏好
        """
        user = request.user
        tool_name = request.data.get("tool_name")
        scope = request.data.get("scope")
        session_id = request.data.get("session_id")

        queryset = UserToolApproval.objects.filter(user=user)

        if tool_name:
            queryset = queryset.filter(tool_name=tool_name)
        if scope:
            queryset = queryset.filter(scope=scope)
        if session_id:
            queryset = queryset.filter(session_id=session_id)

        count = queryset.count()
        queryset.delete()

        return Response(
            {"message": f"已重置 {count} 条审批偏好", "deleted_count": count}
        )


class TokenUsageStatsAPIView(APIView):
    """
    Token 使用统计 API

    提供按用户和按时间维度的 Token 使用量统计。
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        获取 Token 使用统计

        查询参数：
        - start_date: 开始日期 (YYYY-MM-DD)
        - end_date: 结束日期 (YYYY-MM-DD)
        - group_by: 分组方式 (day/week/month)，默认 day
        - user_id: 指定用户ID（仅管理员可用）
        """
        from django.db.models import Sum, Count
        from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
        from datetime import datetime, timedelta

        user = request.user
        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")
        group_by = request.query_params.get("group_by", "day")
        target_user_id = request.query_params.get("user_id")

        # 权限检查：只有管理员可以查看其他用户的统计
        if target_user_id and not user.is_superuser:
            return Response(
                {"error": "无权查看其他用户的统计信息"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 解析日期
        try:
            # 使用本地时区的当前日期，避免 UTC 时区偏差
            from django.utils import timezone as tz

            local_now = tz.localtime(tz.now())
            today = local_now.date()

            if start_date_str:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            else:
                # 根据 group_by 自动计算起始日期
                if group_by == "day":
                    start_date = today
                elif group_by == "week":
                    # 本周一
                    start_date = today - timedelta(days=today.weekday())
                elif group_by == "month":
                    # 本月1号
                    start_date = today.replace(day=1)
                else:
                    start_date = (timezone.now() - timedelta(days=30)).date()

            if end_date_str:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            else:
                end_date = today
        except ValueError:
            return Response(
                {"error": "日期格式错误，请使用 YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 构建查询
        import logging

        logger = logging.getLogger("langgraph_integration")
        logger.info(
            f"[TokenUsageStats] 查询日期范围: {start_date} ~ {end_date}, group_by={group_by}"
        )

        queryset = ChatSession.objects.filter(
            created_at__date__gte=start_date, created_at__date__lte=end_date
        )

        logger.info(f"[TokenUsageStats] 查询到 {queryset.count()} 个会话")

        # 用于个人统计的查询（只看自己的数据）
        if target_user_id:
            personal_queryset = queryset.filter(user_id=target_user_id)
        else:
            personal_queryset = queryset.filter(user=user)

        # 用户排行榜使用全部数据（所有人都能看到排行榜）
        all_users_queryset = queryset

        # 用户维度统计（排行榜 - 使用全部数据）
        user_stats = (
            all_users_queryset.values("user__username", "user_id")
            .annotate(
                total_input=Sum("total_input_tokens"),
                total_output=Sum("total_output_tokens"),
                total_tokens=Sum("total_tokens"),
                total_requests=Sum("request_count"),
                session_count=Count("id"),
            )
            .order_by("-total_tokens")
        )

        # 时间维度统计（使用个人数据）
        trunc_func = {"day": TruncDate, "week": TruncWeek, "month": TruncMonth}.get(
            group_by, TruncDate
        )

        time_stats = (
            personal_queryset.annotate(period=trunc_func("created_at"))
            .values("period")
            .annotate(
                total_input=Sum("total_input_tokens"),
                total_output=Sum("total_output_tokens"),
                total_tokens=Sum("total_tokens"),
                total_requests=Sum("request_count"),
                session_count=Count("id"),
            )
            .order_by("period")
        )

        # 总计统计（使用个人数据）
        total_stats = personal_queryset.aggregate(
            total_input=Sum("total_input_tokens"),
            total_output=Sum("total_output_tokens"),
            total_tokens=Sum("total_tokens"),
            total_requests=Sum("request_count"),
            session_count=Count("id"),
        )

        return Response(
            {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "group_by": group_by,
                },
                "total": {
                    "input_tokens": total_stats["total_input"] or 0,
                    "output_tokens": total_stats["total_output"] or 0,
                    "total_tokens": total_stats["total_tokens"] or 0,
                    "request_count": total_stats["total_requests"] or 0,
                    "session_count": total_stats["session_count"] or 0,
                },
                "by_user": [
                    {
                        "user_id": item["user_id"],
                        "username": item["user__username"],
                        "input_tokens": item["total_input"] or 0,
                        "output_tokens": item["total_output"] or 0,
                        "total_tokens": item["total_tokens"] or 0,
                        "request_count": item["total_requests"] or 0,
                        "session_count": item["session_count"] or 0,
                    }
                    for item in user_stats
                ],
                "by_time": [
                    {
                        "period": item["period"].isoformat()
                        if item["period"]
                        else None,
                        "input_tokens": item["total_input"] or 0,
                        "output_tokens": item["total_output"] or 0,
                        "total_tokens": item["total_tokens"] or 0,
                        "request_count": item["total_requests"] or 0,
                        "session_count": item["session_count"] or 0,
                    }
                    for item in time_stats
                ],
            }
        )
