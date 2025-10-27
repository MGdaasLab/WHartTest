from rest_framework import status, permissions, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django.db.models import Q
from django.utils import timezone
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

# --- New Imports ---
from typing import TypedDict, Annotated, List
from langchain_core.messages import AnyMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.chat_models.tongyi import ChatTongyi
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages # Correct import for add_messages
from langgraph.checkpoint.sqlite import SqliteSaver # For sync operations in ChatHistoryAPIView
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver # Use Async version for async views
from langgraph.prebuilt import create_react_agent # For agent with tools
# from langgraph.checkpoint.memory import InMemorySaver # Remove InMemorySaver import if no longer globally needed
import os
import uuid # Import uuid module
# Knowledge base integration
from knowledge.langgraph_integration import KnowledgeRAGService, ConversationalRAGService, LangGraphKnowledgeIntegration
from knowledge.models import KnowledgeBase
import sqlite3 # Import sqlite3 module
from django.conf import settings
import logging # Import logging
from asgiref.sync import sync_to_async # For async operations in sync context
import json # For JSON serialization in streaming
import asyncio # For async operations

# Django streaming response
from django.http import StreamingHttpResponse

from mcp_tools.models import RemoteMCPConfig # To load remote MCP server configs
from langchain_mcp_adapters.client import MultiServerMCPClient # To connect to remote MCPs
from mcp_tools.persistent_client import mcp_session_manager # 持久化MCP会话管理器
# --- End New Imports ---

logger = logging.getLogger(__name__) # Initialize logger

# --- Helper Functions ---
def create_llm_instance(active_config, temperature=0.7):
    """
    根据配置创建合适的LLM实例，支持多种供应商
    """
    model_identifier = active_config.name or "gpt-3.5-turbo"
    provider = active_config.provider
    
    if provider == 'anthropic':
        # Anthropic/Claude
        llm = ChatAnthropic(
            model=model_identifier,
            api_key=active_config.api_key,
            temperature=temperature
        )
        logger.info(f"Initialized ChatAnthropic with model: {model_identifier}")
    elif provider == 'openai':
        # OpenAI 官方
        llm = ChatOpenAI(
            model=model_identifier,
            temperature=temperature,
            api_key=active_config.api_key,
        )
        logger.info(f"Initialized ChatOpenAI with model: {model_identifier}")
    elif provider == 'ollama':
        # Ollama 本地部署
        llm = ChatOllama(
            model=model_identifier,
            base_url=active_config.api_url,
            temperature=temperature
        )
        logger.info(f"Initialized ChatOllama with model: {model_identifier}")
    elif provider == 'gemini':
        # Google Gemini
        llm = ChatGoogleGenerativeAI(
            model=model_identifier,
            google_api_key=active_config.api_key,
            temperature=temperature
        )
        logger.info(f"Initialized ChatGoogleGenerativeAI with model: {model_identifier}")
    elif provider == 'qwen':
        # Alibaba Qwen (Tongyi)
        llm = ChatTongyi(
            model=model_identifier,
            dashscope_api_key=active_config.api_key,
            temperature=temperature
        )
        logger.info(f"Initialized ChatTongyi with model: {model_identifier}")
    elif provider == 'openai_compatible':
        # OpenAI 兼容服务
        llm_kwargs = {
            "model": model_identifier,
            "temperature": temperature,
            "api_key": active_config.api_key,
            "base_url": active_config.api_url
        }
        
        llm = ChatOpenAI(**llm_kwargs)
        logger.info(f"Initialized OpenAI-compatible LLM with model: {model_identifier}")
    else:
        # 默认使用OpenAI
        llm = ChatOpenAI(
            model=model_identifier,
            temperature=temperature,
            api_key=active_config.api_key,
        )
        logger.info(f"Initialized default ChatOpenAI with model: {model_identifier}")
    
    return llm

def create_sse_data(data_dict):
    """
    创建SSE格式的数据，确保中文字符正确编码
    """
    json_str = json.dumps(data_dict, ensure_ascii=False)
    return f"data: {json_str}\n\n"

# --- AgentState Definition ---
class AgentState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]
# --- End AgentState Definition ---

# --- Global Checkpointer ---
# This creates/uses a SQLite file in the project's BASE_DIR
# Ensure BASE_DIR is correctly defined in your settings.py
# settings.BASE_DIR should be a Path object or string.
# --- End Global Checkpointer ---
# Global checkpointer 'memory' is removed. It will be instantiated within the post method.

class LLMConfigViewSet(BaseModelViewSet):
    """
    LLM配置管理接口
    提供完整的CRUD操作
    """
    queryset = LLMConfig.objects.all().order_by('-created_at')
    serializer_class = LLMConfigSerializer
    def perform_create(self, serializer):
        """执行创建操作"""
        if serializer.validated_data.get('is_active', False):
            LLMConfig.objects.filter(is_active=True).update(is_active=False)
        serializer.save()

    def perform_update(self, serializer):
        """执行更新操作"""
        if serializer.validated_data.get('is_active', False):
            LLMConfig.objects.filter(is_active=True).exclude(pk=serializer.instance.pk).update(is_active=False)
        serializer.save()


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
                    id=prompt_id,
                    user=user,
                    is_active=True
                )
                return user_prompt.content, 'user_specified'
            except UserPrompt.DoesNotExist:
                logger.warning(f"Specified prompt {prompt_id} not found for user {user.id}")

        # 2. 尝试获取用户的默认提示词
        default_prompt = UserPrompt.get_user_default_prompt(user)
        if default_prompt:
            return default_prompt.content, 'user_default'

        # 3. 使用全局LLM配置的system_prompt
        try:
            active_config = LLMConfig.objects.get(is_active=True)
            if active_config.system_prompt and active_config.system_prompt.strip():
                return active_config.system_prompt.strip(), 'global'
        except LLMConfig.DoesNotExist:
            logger.warning("No active LLM configuration found")

        # 4. 没有任何提示词
        return None, 'none'

    except Exception as e:
        logger.error(f"Error getting effective system prompt: {e}")
        # 降级到全局配置
        try:
            active_config = LLMConfig.objects.get(is_active=True)
            if active_config.system_prompt and active_config.system_prompt.strip():
                return active_config.system_prompt.strip(), 'global'
        except:
            pass
        return None, 'none'


async def get_effective_system_prompt_async(user, prompt_id=None):
    """
    获取有效的系统提示词（异步版本）
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
                user_prompt = await sync_to_async(UserPrompt.objects.get)(
                    id=prompt_id,
                    user=user,
                    is_active=True
                )
                return user_prompt.content, 'user_specified'
            except UserPrompt.DoesNotExist:
                logger.warning(f"Specified prompt {prompt_id} not found for user {user.id}")

        # 2. 尝试获取用户的默认提示词
        try:
            default_prompt = await sync_to_async(UserPrompt.objects.get)(
                user=user,
                is_default=True,
                is_active=True
            )
            if default_prompt:
                return default_prompt.content, 'user_default'
        except UserPrompt.DoesNotExist:
            pass

        # 3. 使用全局LLM配置的system_prompt
        try:
            active_config = await sync_to_async(LLMConfig.objects.get)(is_active=True)
            if active_config.system_prompt and active_config.system_prompt.strip():
                return active_config.system_prompt.strip(), 'global'
        except LLMConfig.DoesNotExist:
            logger.warning("No active LLM configuration found")

        # 4. 没有任何提示词
        return None, 'none'

    except Exception as e:
        logger.error(f"Error getting effective system prompt: {e}")
        # 降级到全局配置
        try:
            active_config = await sync_to_async(LLMConfig.objects.get)(is_active=True)
            if active_config.system_prompt and active_config.system_prompt.strip():
                return active_config.system_prompt.strip(), 'global'
        except:
            pass
        return None, 'none'


class ChatAPIView(APIView):
    """
    API endpoint for handling chat with the currently active LLM using LangGraph,
    with potential integration of remote MCP tools.
    支持项目隔离，聊天记录按项目分组。
    """
    permission_classes = [HasModelPermission]

    def _check_project_permission(self, user, project_id):
        """检查用户是否有访问指定项目的权限"""
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

    async def dispatch(self, request, *args, **kwargs):
        """
        Handles incoming requests and ensures that the view is treated as async.
        """
        self.request = request
        self.args = args
        self.kwargs = kwargs
        # Ensure request object is initialized for DRF's typical expectations
        # This might involve more complex handling if request.user is accessed early by sync code
        # For now, we assume standard DRF request processing can be wrapped.
        request = await sync_to_async(self.initialize_request)(request, *args, **kwargs)
        self.request = request
        self.headers = await sync_to_async(lambda: self.default_response_headers)()

        try:
            await sync_to_async(self.initial)(request, *args, **kwargs)

            if request.method.lower() in self.http_method_names:
                handler = getattr(self, request.method.lower(), self.http_method_not_allowed)
            else:
                handler = self.http_method_not_allowed

            response = await handler(request, *args, **kwargs)

        except Exception as exc:
            response = await sync_to_async(self.handle_exception)(exc)

        self.response = await sync_to_async(self.finalize_response)(request, response, *args, **kwargs)
        return self.response

    async def post(self, request, *args, **kwargs):
        logger.info(f"ChatAPIView: Received POST request from user {request.user.id}")
        user_message_content = request.data.get('message')
        session_id = request.data.get('session_id')
        project_id = request.data.get('project_id')

        # 知识库相关参数
        knowledge_base_id = request.data.get('knowledge_base_id')
        use_knowledge_base = request.data.get('use_knowledge_base', True)  # 默认启用知识库
        similarity_threshold = request.data.get('similarity_threshold', 0.7)
        top_k = request.data.get('top_k', 5)

        # 提示词相关参数
        prompt_id = request.data.get('prompt_id')  # 用户指定的提示词ID

        # 验证项目ID是否提供
        if not project_id:
            return Response({
                "status": "error", "code": status.HTTP_400_BAD_REQUEST,
                "message": "project_id is required.", "data": {},
                "errors": {"project_id": ["This field is required."]}
            }, status=status.HTTP_400_BAD_REQUEST)

        # 检查项目权限
        project = await sync_to_async(self._check_project_permission)(request.user, project_id)
        if not project:
            return Response({
                "status": "error", "code": status.HTTP_403_FORBIDDEN,
                "message": "You don't have permission to access this project or project doesn't exist.", "data": {},
                "errors": {"project_id": ["Permission denied or project not found."]}
            }, status=status.HTTP_403_FORBIDDEN)

        is_new_session = False
        if not session_id:
            session_id = uuid.uuid4().hex
            is_new_session = True
            logger.info(f"ChatAPIView: Generated new session_id: {session_id}")

        if not user_message_content:
            logger.warning("ChatAPIView: Message content is required but not provided.")
            return Response({
                "status": "error", "code": status.HTTP_400_BAD_REQUEST,
                "message": "Message content is required.", "data": {},
                "errors": {"message": ["This field may not be blank."]}
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 如果是新会话，立即创建ChatSession对象
            if is_new_session:
                try:
                    await sync_to_async(ChatSession.objects.create)(
                        user=request.user,
                        session_id=session_id,
                        project=project,
                        title=f"新对话 - {user_message_content[:30]}" # 使用消息内容作为临时标题
                    )
                    logger.info(f"ChatAPIView: Created new ChatSession entry for session_id: {session_id}")
                except Exception as e:
                    logger.error(f"ChatAPIView: Failed to create ChatSession entry: {e}", exc_info=True)

            active_config = await sync_to_async(LLMConfig.objects.get)(is_active=True)
            logger.info(f"ChatAPIView: Using active LLMConfig: {active_config.name}")
        except LLMConfig.DoesNotExist:
            logger.error("ChatAPIView: No active LLM configuration found.")
            return Response({
                "status": "error", "code": status.HTTP_503_SERVICE_UNAVAILABLE,
                "message": "No active LLM configuration found. Please configure and activate an LLM.", "data": {},
                "errors": {"llm_config": ["No active LLM configuration available."]}
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except LLMConfig.MultipleObjectsReturned:
            logger.error("ChatAPIView: Multiple active LLM configurations found.")
            return Response({
                "status": "error", "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Multiple active LLM configurations found. Ensure only one is active.", "data": {},
                "errors": {"llm_config": ["Multiple active LLM configurations found."]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            # 使用新的LLM工厂函数，支持多供应商
            llm = create_llm_instance(active_config, temperature=0.7)
            logger.info(f"ChatAPIView: Initialized LLM with provider auto-detection")

            db_path = os.path.join(str(settings.BASE_DIR), "chat_history.sqlite")
            async with AsyncSqliteSaver.from_conn_string(db_path) as actual_memory_checkpointer: # Use async with and AsyncSqliteSaver
                # Load remote MCP tools
                logger.info("ChatAPIView: Attempting to load remote MCP tools.")
                mcp_tools_list = []
                try:
                    active_remote_mcp_configs_qs = RemoteMCPConfig.objects.filter(is_active=True)
                    active_remote_mcp_configs = await sync_to_async(list)(active_remote_mcp_configs_qs)

                    if active_remote_mcp_configs:
                        client_mcp_config = {}
                        for r_config in active_remote_mcp_configs:
                            config_key = r_config.name or f"remote_config_{r_config.id}"
                            client_mcp_config[config_key] = {
                                "url": r_config.url,
                                "transport": (r_config.transport or "streamable_http").replace('-', '_'),
                            }
                            if r_config.headers and isinstance(r_config.headers, dict) and r_config.headers:
                                client_mcp_config[config_key]["headers"] = r_config.headers

                        if client_mcp_config:
                            logger.info(f"ChatAPIView: Initializing persistent MCP client with config: {client_mcp_config}")
                            # 使用持久化MCP会话管理器，传递用户、项目和会话信息以支持跨对话轮次的状态保持
                            mcp_tools_list = await mcp_session_manager.get_tools_for_config(
                                client_mcp_config,
                                user_id=str(request.user.id),
                                project_id=str(project_id),
                                session_id=session_id  # 传递session_id以启用会话级别的工具缓存
                            )
                            logger.info(f"ChatAPIView: Successfully loaded {len(mcp_tools_list)} persistent tools from remote MCP servers: {[tool.name for tool in mcp_tools_list if hasattr(tool, 'name')]}")
                        else:
                            logger.info("ChatAPIView: No active remote MCP configurations to build client config.")
                    else:
                        logger.info("ChatAPIView: No active RemoteMCPConfig found.")
                except Exception as e: # Catches errors from mcp_client.get_tools() like HTTP 429
                    logger.error(f"ChatAPIView: Error loading remote MCP tools: {e}", exc_info=True)
                    # mcp_tools_list remains empty, will fallback to basic chatbot

                # Prepare LangGraph runnable
                runnable_to_invoke = None
                is_agent_with_tools = False

                # 检查是否需要创建Agent（有MCP工具）
                if mcp_tools_list:
                    logger.info(f"ChatAPIView: Attempting to create agent with {len(mcp_tools_list)} remote tools.")
                    try:
                        # 如果同时有知识库和MCP工具，创建知识库增强的Agent
                        if knowledge_base_id and use_knowledge_base:
                            logger.info(f"ChatAPIView: Creating knowledge-enhanced agent with {len(mcp_tools_list)} tools and knowledge base {knowledge_base_id}")

                            # 创建知识库工具
                            from knowledge.langgraph_integration import create_knowledge_tool
                            knowledge_tool = create_knowledge_tool(
                                knowledge_base_id=knowledge_base_id,
                                user=request.user,
                                similarity_threshold=similarity_threshold,
                                top_k=top_k
                            )

                            # 将知识库工具添加到MCP工具列表
                            enhanced_tools = mcp_tools_list + [knowledge_tool]
                            agent_executor = create_react_agent(llm, enhanced_tools, checkpointer=actual_memory_checkpointer)
                            runnable_to_invoke = agent_executor
                            is_agent_with_tools = True
                            logger.info(f"ChatAPIView: Knowledge-enhanced agent created with {len(enhanced_tools)} tools (including knowledge base)")
                        else:
                            # 只有MCP工具，创建普通Agent
                            agent_executor = create_react_agent(llm, mcp_tools_list, checkpointer=actual_memory_checkpointer)
                            runnable_to_invoke = agent_executor
                            is_agent_with_tools = True
                            logger.info("ChatAPIView: Agent with remote tools created with checkpointer.")
                    except Exception as e:
                        logger.error(f"ChatAPIView: Failed to create agent with remote tools: {e}. Falling back to knowledge-enhanced chatbot.", exc_info=True)

                if not runnable_to_invoke:
                    logger.info("ChatAPIView: No remote tools or agent creation failed. Using knowledge-enhanced chatbot.")
                    is_agent_with_tools = False # Ensure flag is false for basic chatbot

                    def knowledge_enhanced_chatbot_node(state: AgentState):
                        """知识库增强的聊天机器人节点"""
                        try:
                            # 获取最新的用户消息
                            user_messages = [msg for msg in state['messages']
                                           if isinstance(msg, HumanMessage)]

                            if not user_messages:
                                # 如果没有用户消息，直接调用LLM
                                invoked_response = llm.invoke(state['messages'])
                                return {"messages": [invoked_response]}

                            latest_user_message = user_messages[-1].content

                            # 检查是否需要使用知识库
                            should_use_kb = use_knowledge_base and knowledge_base_id

                            if should_use_kb:
                                logger.info(f"ChatAPIView: Using knowledge base {knowledge_base_id} for query")

                                # 使用知识库RAG服务
                                from knowledge.langgraph_integration import ConversationalRAGService
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
                                    top_k=top_k
                                )

                                # 返回RAG结果中的消息
                                rag_messages = rag_result.get("messages", [])
                                if rag_messages:
                                    logger.info(f"ChatAPIView: RAG returned {len(rag_messages)} messages")
                                    return {"messages": rag_messages}
                                else:
                                    logger.warning("ChatAPIView: RAG returned no messages, falling back to basic chat")

                            # 降级到基础对话
                            logger.info("ChatAPIView: Using basic chat without knowledge base")
                            invoked_response = llm.invoke(state['messages'])
                            return {"messages": [invoked_response]}

                        except Exception as e:
                            logger.error(f"ChatAPIView: Error in knowledge-enhanced chatbot: {e}")
                            # 降级到基础对话
                            invoked_response = llm.invoke(state['messages'])
                            return {"messages": [invoked_response]}

                    graph_builder = StateGraph(AgentState)
                    graph_builder.add_node("chatbot", knowledge_enhanced_chatbot_node)
                    graph_builder.set_entry_point("chatbot")
                    graph_builder.add_edge("chatbot", END)
                    runnable_to_invoke = graph_builder.compile(checkpointer=actual_memory_checkpointer) # Use actual checkpointer instance
                    logger.info("ChatAPIView: Knowledge-enhanced chatbot graph compiled.")

                # Determine thread_id - 包含项目ID以实现项目隔离
                thread_id_parts = [str(request.user.id), str(project_id)]
                if session_id:
                    thread_id_parts.append(str(session_id))
                thread_id = "_".join(thread_id_parts)
                logger.info(f"ChatAPIView: Using thread_id: {thread_id} for project: {project.name}")

                # 构建消息列表，检查是否需要添加系统提示词
                messages_list = []

                # 获取有效的系统提示词（用户提示词优先）
                effective_prompt, prompt_source = get_effective_system_prompt(request.user, prompt_id)

                # 检查当前会话是否已经有系统提示词
                should_add_system_prompt = False
                if effective_prompt:
                    try:
                        # 尝试获取当前会话的历史消息
                        with SqliteSaver.from_conn_string(db_path) as memory:
                            checkpoint_generator = memory.list(config={"configurable": {"thread_id": thread_id}})
                            checkpoint_tuples_list = list(checkpoint_generator)

                            if checkpoint_tuples_list:
                                # 检查最新checkpoint中是否已有系统提示词
                                latest_checkpoint = checkpoint_tuples_list[0].checkpoint
                                if (latest_checkpoint and 'channel_values' in latest_checkpoint
                                    and 'messages' in latest_checkpoint['channel_values']):
                                    existing_messages = latest_checkpoint['channel_values']['messages']
                                    # 检查第一条消息是否是系统消息
                                    if not existing_messages or not isinstance(existing_messages[0], SystemMessage):
                                        should_add_system_prompt = True
                                else:
                                    should_add_system_prompt = True
                            else:
                                # 新会话，需要添加系统提示词
                                should_add_system_prompt = True
                    except Exception as e:
                        logger.warning(f"ChatAPIView: Error checking existing messages: {e}")
                        should_add_system_prompt = True

                if should_add_system_prompt and effective_prompt:
                    messages_list.append(SystemMessage(content=effective_prompt))
                    logger.info(f"ChatAPIView: Added {prompt_source} system prompt: {effective_prompt[:100]}...")

                messages_list.append(HumanMessage(content=user_message_content))
                input_messages = {"messages": messages_list}

                invoke_config = {
                    "configurable": {"thread_id": thread_id},
                    "recursion_limit": 100  # 增加递归限制，支持生成更多测试用例
                }
                logger.info(f"ChatAPIView: Set recursion_limit to 100 for thread_id: {thread_id}")
                # Checkpointer is already configured in both agent and basic chatbot

                final_state = await runnable_to_invoke.ainvoke(
                    input_messages,
                    config=invoke_config
                )

                ai_response_content = "No valid AI response found."
                conversation_flow = []  # 存储完整的对话流程

                if final_state and final_state.get('messages'):
                    # 处理所有消息，提取对话流程
                    messages = final_state['messages']
                    logger.info(f"ChatAPIView: Processing {len(messages)} messages in final state")

                    # 找到本次对话的起始位置（用户刚发送的消息）
                    user_message_index = -1
                    for i, msg in enumerate(messages):
                        if isinstance(msg, HumanMessage) and msg.content == user_message_content:
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
                                content = msg.content if hasattr(msg, 'content') else str(msg)
                            elif isinstance(msg, HumanMessage):
                                msg_type = "human"
                                content = msg.content if hasattr(msg, 'content') else str(msg)
                            elif isinstance(msg, AIMessage):
                                msg_type = "ai"
                                content = msg.content if hasattr(msg, 'content') else str(msg)

                                # 跳过空的AI消息（工具调用前的中间状态）
                                if not content or content.strip() == "":
                                    logger.debug(f"ChatAPIView: Skipping empty AI message at index {i}")
                                    continue

                            elif isinstance(msg, ToolMessage):
                                msg_type = "tool"
                                content = msg.content if hasattr(msg, 'content') else str(msg)
                            else:
                                # 处理其他类型的消息，可能是工具调用结果
                                content = msg.content if hasattr(msg, 'content') else str(msg)
                                # 如果内容看起来像JSON，可能是工具返回
                                if content.strip().startswith('[') or content.strip().startswith('{'):
                                    msg_type = "tool"
                                else:
                                    msg_type = "unknown"

                            # 只添加有内容的消息
                            if content and content.strip():
                                conversation_flow.append({
                                    "type": msg_type,
                                    "content": content
                                })

                                # 记录最后一条AI消息作为主要回复
                                if msg_type == "ai":
                                    ai_response_content = content

                    # 如果没有找到用户消息，使用最后一条消息作为回复
                    if user_message_index == -1 and messages:
                        last_message = messages[-1]
                        if hasattr(last_message, 'content'):
                            ai_response_content = last_message.content

                logger.info(f"ChatAPIView: Successfully processed message for thread_id: {thread_id}. AI response: {ai_response_content[:100]}...")
                logger.info(f"ChatAPIView: Conversation flow contains {len(conversation_flow)} messages")

                return Response({
                    "status": "success", "code": status.HTTP_200_OK,
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
                        "knowledge_base_used": bool(knowledge_base_id and use_knowledge_base)
                    }
                }, status=status.HTTP_200_OK)

        except Exception as e: # This outer try-except catches errors from the 'with SqliteSaver' block or LLM init
            logger.error(f"ChatAPIView: Error interacting with LLM or LangGraph: {e}", exc_info=True)
            return Response({
                "status": "error", "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error interacting with LLM or LangGraph: {str(e)}", "data": {},
                "errors": {"llm_interaction": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChatHistoryAPIView(APIView):
    """
    API endpoint for retrieving chat history for a given session_id.
    支持项目隔离，只能获取指定项目的聊天记录。
    """
    permission_classes = [permissions.IsAuthenticated]

    def _check_project_permission(self, user, project_id):
        """检查用户是否有访问指定项目的权限"""
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

    def get(self, request, *args, **kwargs):
        session_id = request.query_params.get('session_id')
        project_id = request.query_params.get('project_id')

        if not session_id:
            return Response({
                "status": "error", "code": status.HTTP_400_BAD_REQUEST,
                "message": "session_id query parameter is required.", "data": {},
                "errors": {"session_id": ["This field is required."]}
            }, status=status.HTTP_400_BAD_REQUEST)

        if not project_id:
            return Response({
                "status": "error", "code": status.HTTP_400_BAD_REQUEST,
                "message": "project_id query parameter is required.", "data": {},
                "errors": {"project_id": ["This field is required."]}
            }, status=status.HTTP_400_BAD_REQUEST)

        # 检查项目权限
        project = self._check_project_permission(request.user, project_id)
        if not project:
            return Response({
                "status": "error", "code": status.HTTP_403_FORBIDDEN,
                "message": "You don't have permission to access this project or project doesn't exist.", "data": {},
                "errors": {"project_id": ["Permission denied or project not found."]}
            }, status=status.HTTP_403_FORBIDDEN)

        thread_id_parts = [str(request.user.id), str(project_id), str(session_id)]
        thread_id = "_".join(thread_id_parts)

        db_path = os.path.join(str(settings.BASE_DIR), "chat_history.sqlite")
        history_messages = []

        try:
            # 首先尝试直接查询数据库以检查是否有数据
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # 检查是否有对应的thread_id记录
            cursor.execute("SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?", (thread_id,))
            checkpoint_count = cursor.fetchone()[0]
            logger.info(f"ChatHistoryAPIView: Found {checkpoint_count} checkpoints in database for thread_id: {thread_id}")

            if checkpoint_count == 0:
                # 如果没有找到记录，检查所有的thread_id
                cursor.execute("SELECT DISTINCT thread_id FROM checkpoints LIMIT 10")
                all_threads = cursor.fetchall()
                logger.info(f"ChatHistoryAPIView: Available thread_ids in database: {[t[0] for t in all_threads]}")

            conn.close()

            # 使用SqliteSaver读取数据
            with SqliteSaver.from_conn_string(db_path) as memory:
                # Fetch all checkpoints for the thread
                # The list method returns CheckpointTuple, we need the 'checkpoint' attribute
                checkpoint_generator = memory.list(config={"configurable": {"thread_id": thread_id}})
                checkpoint_tuples_list = list(checkpoint_generator) # Convert generator to list

                logger.info(f"ChatHistoryAPIView: SqliteSaver found {len(checkpoint_tuples_list)} checkpoints for thread_id: {thread_id}")

                if checkpoint_tuples_list: # Check if the list is not empty
                    # 构建消息到时间戳的映射
                    # 遍历所有checkpoints，为每条新消息分配对应checkpoint的时间戳
                    message_timestamps = {}
                    processed_message_count = 0

                    # 按时间顺序处理checkpoints（从旧到新）
                    for checkpoint_tuple in reversed(checkpoint_tuples_list):
                        if checkpoint_tuple and hasattr(checkpoint_tuple, 'checkpoint'):
                            checkpoint_data = checkpoint_tuple.checkpoint
                            if checkpoint_data and 'channel_values' in checkpoint_data and 'messages' in checkpoint_data['channel_values']:
                                messages = checkpoint_data['channel_values']['messages']
                                current_message_count = len(messages)

                                # 如果这个checkpoint有新消息，为新消息分配时间戳
                                if current_message_count > processed_message_count:
                                    checkpoint_timestamp = checkpoint_data.get('ts')
                                    if checkpoint_timestamp:
                                        # 为新增的消息分配时间戳
                                        for i in range(processed_message_count, current_message_count):
                                            message_timestamps[i] = checkpoint_timestamp
                                    processed_message_count = current_message_count

                    # 获取最新checkpoint的消息列表
                    latest_checkpoint_tuple = checkpoint_tuples_list[0]
                    if latest_checkpoint_tuple and hasattr(latest_checkpoint_tuple, 'checkpoint'):
                        checkpoint_data = latest_checkpoint_tuple.checkpoint
                        logger.info(f"ChatHistoryAPIView: Processing checkpoint with keys: {list(checkpoint_data.keys()) if checkpoint_data else 'None'}")

                        if checkpoint_data and 'channel_values' in checkpoint_data and 'messages' in checkpoint_data['channel_values']:
                            messages = checkpoint_data['channel_values']['messages']
                            logger.info(f"ChatHistoryAPIView: Found {len(messages)} messages in latest checkpoint")

                            for i, msg in enumerate(messages):
                                msg_type = "unknown"
                                content = ""

                                if isinstance(msg, SystemMessage):
                                    msg_type = "system"
                                    content = msg.content if hasattr(msg, 'content') else str(msg)
                                elif isinstance(msg, HumanMessage):
                                    msg_type = "human"
                                    content = msg.content if hasattr(msg, 'content') else str(msg)
                                elif isinstance(msg, AIMessage):
                                    msg_type = "ai"
                                    content = msg.content if hasattr(msg, 'content') else str(msg)

                                    # 跳过空的AI消息（工具调用前的中间状态）
                                    if not content or content.strip() == "":
                                        logger.debug(f"ChatHistoryAPIView: Skipping empty AI message at index {i}")
                                        continue

                                elif isinstance(msg, ToolMessage):
                                    msg_type = "tool"
                                    content = msg.content if hasattr(msg, 'content') else str(msg)
                                else:
                                    # 处理其他类型的消息，可能是工具调用结果
                                    content = msg.content if hasattr(msg, 'content') else str(msg)
                                    # 如果内容看起来像JSON，可能是工具返回
                                    if content.strip().startswith('[') or content.strip().startswith('{'):
                                        msg_type = "tool"
                                    else:
                                        msg_type = "unknown"

                                logger.debug(f"ChatHistoryAPIView: Message {i}: type={msg_type}, content={content[:50]}...")

                                # 只添加有内容的消息
                                if content and content.strip():
                                    message_data = {
                                        "type": msg_type,
                                        "content": content,
                                    }
                                    # 添加对应的时间戳
                                    if i in message_timestamps:
                                        timestamp_str = message_timestamps[i]
                                        try:
                                            # 解析ISO时间戳并转换为本地时间
                                            from datetime import datetime
                                            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                            # 转换为本地时间
                                            local_dt = dt.astimezone()
                                            # 格式化为本地时间字符串
                                            message_data["timestamp"] = local_dt.strftime("%Y-%m-%d %H:%M:%S")
                                        except Exception as e:
                                            # 如果解析失败，只返回原始字符串
                                            logger.warning(f"ChatHistoryAPIView: Failed to parse timestamp {timestamp_str}: {e}")
                                            message_data["timestamp"] = timestamp_str

                                    history_messages.append(message_data)
                        else:
                            logger.warning(f"ChatHistoryAPIView: No messages found in checkpoint data structure")
                    else:
                        logger.warning(f"ChatHistoryAPIView: Invalid checkpoint tuple structure")
                else:
                    logger.info(f"ChatHistoryAPIView: No checkpoints found for thread_id: {thread_id}")
            # By processing only the latest checkpoint, we get the final state of messages, avoiding duplicates.

            return Response({
                "status": "success", "code": status.HTTP_200_OK,
                "message": "Chat history retrieved successfully.",
                "data": {
                    "thread_id": thread_id,
                    "session_id": session_id,
                    "project_id": project_id,
                    "project_name": project.name,
                    "history": history_messages
                }
            }, status=status.HTTP_200_OK)

        except FileNotFoundError:
             return Response({
                "status": "success", "code": status.HTTP_200_OK, # Or 404 if preferred for no history file
                "message": "No chat history found for this session (history file does not exist).",
                "data": {
                    "thread_id": thread_id,
                    "session_id": session_id,
                    "history": []
                }
            }, status=status.HTTP_200_OK)
        except Exception as e:
            # import logging
            # logging.exception(f"Error retrieving chat history for thread_id {thread_id}")
            return Response({
                "status": "error", "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Error retrieving chat history: {str(e)}", "data": {},
                "errors": {"history_retrieval": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, *args, **kwargs):
        session_id = request.query_params.get('session_id')
        project_id = request.query_params.get('project_id')

        if not session_id:
            return Response({
                "status": "error", "code": status.HTTP_400_BAD_REQUEST,
                "message": "session_id query parameter is required.", "data": {},
                "errors": {"session_id": ["This field is required."]}
            }, status=status.HTTP_400_BAD_REQUEST)

        if not project_id:
            return Response({
                "status": "error", "code": status.HTTP_400_BAD_REQUEST,
                "message": "project_id query parameter is required.", "data": {},
                "errors": {"project_id": ["This field is required."]}
            }, status=status.HTTP_400_BAD_REQUEST)

        # 检查项目权限
        project = self._check_project_permission(request.user, project_id)
        if not project:
            return Response({
                "status": "error", "code": status.HTTP_403_FORBIDDEN,
                "message": "You don't have permission to access this project or project doesn't exist.", "data": {},
                "errors": {"project_id": ["Permission denied or project not found."]}
            }, status=status.HTTP_403_FORBIDDEN)

        thread_id_parts = [str(request.user.id), str(project_id), str(session_id)]
        thread_id = "_".join(thread_id_parts)

        db_path = os.path.join(str(settings.BASE_DIR), "chat_history.sqlite")

        if not os.path.exists(db_path):
            return Response({
                "status": "success", # Or "error" with 404 if preferred
                "code": status.HTTP_200_OK, # Or 404
                "message": "No chat history found to delete (history file does not exist).",
                "data": {"thread_id": thread_id, "session_id": session_id, "deleted_count": 0}
            }, status=status.HTTP_200_OK)

        conn = None
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # It's good practice to check how many rows were affected.
            cursor.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
            deleted_count = cursor.rowcount # Get the number of rows deleted

            conn.commit()

            if deleted_count > 0:
                message = f"Successfully deleted chat history for session_id: {session_id} (Thread ID: {thread_id}). {deleted_count} records removed."
            else:
                message = f"No chat history found for session_id: {session_id} (Thread ID: {thread_id}) to delete."

            return Response({
                "status": "success", "code": status.HTTP_200_OK,
                "message": message,
                "data": {"thread_id": thread_id, "session_id": session_id, "deleted_count": deleted_count}
            }, status=status.HTTP_200_OK)

        except sqlite3.Error as e:
            # import logging
            # logging.exception(f"SQLite error deleting chat history for thread_id {thread_id}: {e}")
            return Response({
                "status": "error", "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Database error while deleting chat history: {str(e)}", "data": {},
                "errors": {"database_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            # import logging
            # logging.exception(f"Unexpected error deleting chat history for thread_id {thread_id}: {e}")
            return Response({
                "status": "error", "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"An unexpected error occurred: {str(e)}", "data": {},
                "errors": {"unexpected_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            if conn:
                conn.close()


class UserChatSessionsAPIView(APIView):
    """
    API endpoint for listing all chat session IDs for the authenticated user in a specific project.
    支持项目隔离，只返回指定项目的聊天会话。
    """
    permission_classes = [permissions.IsAuthenticated]

    def _check_project_permission(self, user, project_id):
        """检查用户是否有访问指定项目的权限"""
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

    def get(self, request, *args, **kwargs):
        user_id = str(request.user.id)
        project_id = request.query_params.get('project_id')

        if not project_id:
            return Response({
                "status": "error", "code": status.HTTP_400_BAD_REQUEST,
                "message": "project_id query parameter is required.", "data": {},
                "errors": {"project_id": ["This field is required."]}
            }, status=status.HTTP_400_BAD_REQUEST)

        # 检查项目权限
        project = self._check_project_permission(request.user, project_id)
        if not project:
            return Response({
                "status": "error", "code": status.HTTP_403_FORBIDDEN,
                "message": "You don't have permission to access this project or project doesn't exist.", "data": {},
                "errors": {"project_id": ["Permission denied or project not found."]}
            }, status=status.HTTP_403_FORBIDDEN)

        db_path = os.path.join(str(settings.BASE_DIR), "chat_history.sqlite")
        session_ids = set() # Use a set to store unique session_ids

        if not os.path.exists(db_path):
            return Response({
                "status": "success",
                "code": status.HTTP_200_OK,
                "message": "No chat history found (history file does not exist).",
                "data": {"user_id": user_id, "sessions": []}
            }, status=status.HTTP_200_OK)

        conn = None
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Query for distinct thread_ids starting with the user_id and project_id prefix
            # The thread_id is stored as "USERID_PROJECTID_SESSIONID"
            thread_id_prefix = f"{user_id}_{project_id}_"
            cursor.execute("SELECT DISTINCT thread_id FROM checkpoints WHERE thread_id LIKE ?", (thread_id_prefix + '%',))

            rows = cursor.fetchall()

            for row in rows:
                full_thread_id = row[0]
                # Extract session_id part: everything after "USERID_PROJECTID_"
                if full_thread_id.startswith(thread_id_prefix):
                    session_id_part = full_thread_id[len(thread_id_prefix):]
                    if session_id_part: # Ensure there's something after the prefix
                        session_ids.add(session_id_part)

            return Response({
                "status": "success", "code": status.HTTP_200_OK,
                "message": "User chat sessions retrieved successfully.",
                "data": {
                    "user_id": user_id,
                    "project_id": project_id,
                    "project_name": project.name,
                    "sessions": sorted(list(session_ids))
                } # Return sorted list
            }, status=status.HTTP_200_OK)

        except sqlite3.Error as e:
            # import logging
            # logging.exception(f"SQLite error retrieving sessions for user {user_id}: {e}")
            return Response({
                "status": "error", "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"Database error while retrieving user sessions: {str(e)}", "data": {},
                "errors": {"database_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            # import logging
            # logging.exception(f"Unexpected error retrieving sessions for user {user_id}: {e}")
            return Response({
                "status": "error", "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": f"An unexpected error occurred: {str(e)}", "data": {},
                "errors": {"unexpected_error": [str(e)]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            if conn:
                conn.close()


from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed

@method_decorator(csrf_exempt, name='dispatch')
class ChatStreamAPIView(View):
    """
    API endpoint for streaming chat with the currently active LLM using LangGraph,
    with potential integration of remote MCP tools.
    支持项目隔离，聊天记录按项目分组。
    使用Server-Sent Events (SSE)实现流式响应。
    使用Django原生View绕过DRF的渲染器系统。
    """

    async def authenticate_request(self, request):
        """手动进行JWT认证（异步版本）"""
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if not auth_header or not auth_header.startswith('Bearer '):
            raise AuthenticationFailed('Authentication credentials were not provided.')

        token = auth_header.split(' ')[1]
        jwt_auth = JWTAuthentication()

        try:
            # 在异步上下文中使用sync_to_async包装同步方法
            validated_token = await sync_to_async(jwt_auth.get_validated_token)(token)
            user = await sync_to_async(jwt_auth.get_user)(validated_token)
            return user
        except Exception as e:
            raise AuthenticationFailed(f'Invalid token: {str(e)}')

    def _check_project_permission(self, user, project_id):
        """检查用户是否有访问指定项目的权限"""
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

    async def _create_sse_generator(self, request, user_message_content, session_id, project_id, project,
                                   knowledge_base_id=None, use_knowledge_base=True, similarity_threshold=0.7, top_k=5, prompt_id=None):
        """创建SSE数据生成器"""
        try:
            # 获取活跃的LLM配置
            active_config = await sync_to_async(LLMConfig.objects.get)(is_active=True)
            logger.info(f"ChatStreamAPIView: Using active LLMConfig: {active_config.name}")
        except LLMConfig.DoesNotExist:
            yield f"data: {json.dumps({'type': 'error', 'message': 'No active LLM configuration found'})}\n\n"
            return
        except LLMConfig.MultipleObjectsReturned:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Multiple active LLM configurations found'})}\n\n"
            return

        try:
            # 使用新的LLM工厂函数，支持多供应商
            llm = create_llm_instance(active_config, temperature=0.7)
            logger.info(f"ChatStreamAPIView: Initialized LLM with provider auto-detection")

            db_path = os.path.join(str(settings.BASE_DIR), "chat_history.sqlite")
            async with AsyncSqliteSaver.from_conn_string(db_path) as actual_memory_checkpointer:
                # 加载远程MCP工具
                logger.info("ChatStreamAPIView: Attempting to load remote MCP tools.")
                mcp_tools_list = []
                try:
                    active_remote_mcp_configs_qs = RemoteMCPConfig.objects.filter(is_active=True)
                    active_remote_mcp_configs = await sync_to_async(list)(active_remote_mcp_configs_qs)

                    if active_remote_mcp_configs:
                        client_mcp_config = {}
                        for r_config in active_remote_mcp_configs:
                            config_key = r_config.name or f"remote_config_{r_config.id}"
                            client_mcp_config[config_key] = {
                                "url": r_config.url,
                                "transport": (r_config.transport or "streamable_http").replace('-', '_'),
                            }
                            if r_config.headers and isinstance(r_config.headers, dict) and r_config.headers:
                                client_mcp_config[config_key]["headers"] = r_config.headers

                        if client_mcp_config:
                            logger.info(f"ChatStreamAPIView: Initializing persistent MCP client with config: {client_mcp_config}")
                            # 使用持久化MCP会话管理器，传递用户、项目和会话信息以支持跨对话轮次的状态保持
                            mcp_tools_list = await mcp_session_manager.get_tools_for_config(
                                client_mcp_config,
                                user_id=str(request.user.id),
                                project_id=str(project_id),
                                session_id=session_id  # 传递session_id以启用会话级别的工具缓存
                            )
                            logger.info(f"ChatStreamAPIView: Successfully loaded {len(mcp_tools_list)} persistent tools from remote MCP servers")
                        else:
                            logger.info("ChatStreamAPIView: No active remote MCP configurations to build client config.")
                    else:
                        logger.info("ChatStreamAPIView: No active RemoteMCPConfig found.")
                except Exception as e:
                    logger.error(f"ChatStreamAPIView: Error loading remote MCP tools: {e}", exc_info=True)
                    yield f"data: {json.dumps({'type': 'warning', 'message': f'Failed to load MCP tools: {str(e)}'})}\n\n"

                # 准备LangGraph runnable
                runnable_to_invoke = None

                # 检查是否需要创建Agent（有MCP工具）
                if mcp_tools_list:
                    logger.info(f"ChatStreamAPIView: Attempting to create agent with {len(mcp_tools_list)} remote tools.")
                    try:
                        # 如果同时有知识库和MCP工具，创建知识库增强的Agent
                        if knowledge_base_id and use_knowledge_base:
                            logger.info(f"ChatStreamAPIView: Creating knowledge-enhanced agent with {len(mcp_tools_list)} tools and knowledge base {knowledge_base_id}")

                            # 创建知识库工具
                            from knowledge.langgraph_integration import create_knowledge_tool
                            knowledge_tool = create_knowledge_tool(
                                knowledge_base_id=knowledge_base_id,
                                user=request.user,
                                similarity_threshold=similarity_threshold,
                                top_k=top_k
                            )

                            # 将知识库工具添加到MCP工具列表
                            enhanced_tools = mcp_tools_list + [knowledge_tool]
                            agent_executor = create_react_agent(llm, enhanced_tools, checkpointer=actual_memory_checkpointer)
                            runnable_to_invoke = agent_executor
                            logger.info(f"ChatStreamAPIView: Knowledge-enhanced agent created with {len(enhanced_tools)} tools (including knowledge base)")
                            yield create_sse_data({'type': 'info', 'message': f'Knowledge-enhanced agent initialized with {len(enhanced_tools)} tools'})
                        else:
                            # 只有MCP工具，创建普通Agent
                            agent_executor = create_react_agent(llm, mcp_tools_list, checkpointer=actual_memory_checkpointer)
                            runnable_to_invoke = agent_executor
                            logger.info("ChatStreamAPIView: Agent with remote tools created with checkpointer.")
                            yield create_sse_data({'type': 'info', 'message': f'Agent initialized with {len(mcp_tools_list)} tools'})
                    except Exception as e:
                        logger.error(f"ChatStreamAPIView: Failed to create agent with remote tools: {e}. Falling back to knowledge-enhanced chatbot.", exc_info=True)
                        yield create_sse_data({'type': 'warning', 'message': 'Failed to create agent with tools, using knowledge-enhanced chatbot'})

                if not runnable_to_invoke:
                    logger.info("ChatStreamAPIView: No remote tools or agent creation failed. Using knowledge-enhanced chatbot.")

                    def knowledge_enhanced_chatbot_node(state: AgentState):
                        """知识库增强的聊天机器人节点"""
                        messages = state['messages']
                        if not messages:
                            return {"messages": []}

                        # 获取最后一条用户消息
                        last_message = messages[-1]
                        if hasattr(last_message, 'content'):
                            user_query = last_message.content
                        else:
                            user_query = str(last_message)

                        # 检查是否需要使用知识库
                        if knowledge_base_id and use_knowledge_base:
                            try:
                                # 使用知识库增强回答
                                from knowledge.langgraph_integration import KnowledgeRAGService
                                rag_service = KnowledgeRAGService(llm)
                                rag_result = rag_service.query(
                                    question=user_query,
                                    knowledge_base_id=knowledge_base_id,
                                    user=request.user,
                                    similarity_threshold=similarity_threshold,
                                    top_k=top_k
                                )

                                # 使用RAG结果作为上下文
                                context_prompt = f"基于以下相关信息回答用户问题：\n\n{rag_result['context']}\n\n用户问题：{user_query}"
                                enhanced_messages = messages[:-1] + [HumanMessage(content=context_prompt)]
                                invoked_response = llm.invoke(enhanced_messages)
                                logger.info(f"ChatStreamAPIView: Used knowledge base {knowledge_base_id} for enhanced response")

                            except Exception as e:
                                logger.warning(f"ChatStreamAPIView: Knowledge base query failed: {e}, falling back to normal response")
                                invoked_response = llm.invoke(messages)
                        else:
                            # 普通聊天回复
                            invoked_response = llm.invoke(messages)

                        return {"messages": [invoked_response]}

                    graph_builder = StateGraph(AgentState)
                    graph_builder.add_node("chatbot", knowledge_enhanced_chatbot_node)
                    graph_builder.set_entry_point("chatbot")
                    graph_builder.add_edge("chatbot", END)
                    runnable_to_invoke = graph_builder.compile(checkpointer=actual_memory_checkpointer)

                    if knowledge_base_id and use_knowledge_base:
                        logger.info(f"ChatStreamAPIView: Knowledge-enhanced chatbot initialized with KB: {knowledge_base_id}")
                        yield create_sse_data({'type': 'info', 'message': f'Knowledge-enhanced chatbot initialized with knowledge base'})
                    else:
                        logger.info("ChatStreamAPIView: Basic chatbot initialized")
                        yield create_sse_data({'type': 'info', 'message': 'Basic chatbot initialized'})

                # 确定thread_id - 包含项目ID以实现项目隔离
                thread_id_parts = [str(request.user.id), str(project_id)]
                if session_id:
                    thread_id_parts.append(str(session_id))
                thread_id = "_".join(thread_id_parts)
                logger.info(f"ChatStreamAPIView: Using thread_id: {thread_id} for project: {project.name}")

                # 构建消息列表，检查是否需要添加系统提示词
                messages_list = []

                # 获取有效的系统提示词（用户提示词优先）
                effective_prompt, prompt_source = await get_effective_system_prompt_async(request.user, prompt_id)
                logger.info(f"ChatStreamAPIView: Using {prompt_source} prompt: {repr(effective_prompt[:100] if effective_prompt else None)}")

                # 检查当前会话是否已经有系统提示词
                should_add_system_prompt = False
                if effective_prompt:
                    try:
                        # 尝试获取当前会话的历史消息 - 使用异步接口
                        checkpoint_tuples_list = []
                        async for checkpoint_tuple in actual_memory_checkpointer.alist(config={"configurable": {"thread_id": thread_id}}):
                            checkpoint_tuples_list.append(checkpoint_tuple)

                        if checkpoint_tuples_list:
                            # 检查最新checkpoint中是否已有系统提示词
                            latest_checkpoint = checkpoint_tuples_list[0].checkpoint
                            if (latest_checkpoint and 'channel_values' in latest_checkpoint
                                and 'messages' in latest_checkpoint['channel_values']):
                                existing_messages = latest_checkpoint['channel_values']['messages']
                                # 检查第一条消息是否是系统消息
                                if not existing_messages or not isinstance(existing_messages[0], SystemMessage):
                                    should_add_system_prompt = True
                            else:
                                should_add_system_prompt = True
                        else:
                            # 新会话，需要添加系统提示词
                            should_add_system_prompt = True
                    except Exception as e:
                        logger.warning(f"ChatStreamAPIView: Error checking existing messages: {e}")
                        should_add_system_prompt = True

                    if should_add_system_prompt:
                        messages_list.append(SystemMessage(content=effective_prompt))
                        logger.info(f"ChatStreamAPIView: Added {prompt_source} system prompt: {effective_prompt[:100]}...")
                else:
                    logger.info("ChatStreamAPIView: No system prompt available")

                # 验证用户消息内容不为空
                if not user_message_content or not user_message_content.strip():
                    logger.error("ChatStreamAPIView: User message content is empty or whitespace only")
                    yield create_sse_data({'type': 'error', 'message': 'User message content cannot be empty'})
                    return

                # 确保用户消息内容格式正确
                clean_user_message = user_message_content.strip()
                if not clean_user_message:
                    logger.error("ChatStreamAPIView: User message is empty after stripping")
                    yield create_sse_data({'type': 'error', 'message': 'User message cannot be empty'})
                    return

                messages_list.append(HumanMessage(content=clean_user_message))
                logger.info(f"ChatStreamAPIView: Final messages list length: {len(messages_list)}")

                # 验证消息列表不为空且所有消息都有有效内容
                if not messages_list:
                    logger.error("ChatStreamAPIView: Messages list is empty")
                    yield create_sse_data({'type': 'error', 'message': 'No valid messages to process'})
                    return

                for i, msg in enumerate(messages_list):
                    if not hasattr(msg, 'content') or not msg.content or not str(msg.content).strip():
                        logger.error(f"ChatStreamAPIView: Message at index {i} has empty content: {msg}")
                        yield create_sse_data({'type': 'error', 'message': f'Message at index {i} has invalid content'})
                        return
                    logger.info(f"ChatStreamAPIView: Message {i}: {type(msg).__name__} with content length {len(str(msg.content))}")

                input_messages = {"messages": messages_list}
                invoke_config = {
                    "configurable": {"thread_id": thread_id},
                    "recursion_limit": 100  # 增加递归限制，支持生成更多测试用例
                }
                logger.info(f"ChatStreamAPIView: Set recursion_limit to 100 for thread_id: {thread_id}")
                logger.info(f"ChatStreamAPIView: Input messages structure: {input_messages}")

                # 详细记录每个消息的内容
                for i, msg in enumerate(messages_list):
                    logger.info(f"ChatStreamAPIView: Message {i}: type={type(msg).__name__}, content={repr(msg.content)}")

                # 发送开始信号
                yield create_sse_data({'type': 'start', 'thread_id': thread_id, 'session_id': session_id, 'project_id': project_id})

                # 使用astream进行流式处理，支持多种模式
                stream_modes = ["updates", "messages"]

                try:
                    async for stream_mode, chunk in runnable_to_invoke.astream(
                        input_messages,
                        config=invoke_config,
                        stream_mode=stream_modes
                    ):
                        if stream_mode == "updates":
                            # 代理进度更新 - 安全地序列化复杂对象
                            try:
                                # 尝试将chunk转换为可序列化的格式
                                if hasattr(chunk, '__dict__'):
                                    serializable_chunk = str(chunk)
                                else:
                                    serializable_chunk = chunk
                                yield create_sse_data({'type': 'update', 'data': serializable_chunk})
                            except (TypeError, ValueError) as e:
                                yield create_sse_data({'type': 'update', 'data': f'Update: {str(chunk)}'})
                        elif stream_mode == "messages":
                            # LLM令牌流式传输
                            if hasattr(chunk, 'content') and chunk.content:
                                yield create_sse_data({'type': 'message', 'data': chunk.content})
                            else:
                                yield create_sse_data({'type': 'message', 'data': str(chunk)})

                        # 添加小延迟以确保流式传输效果
                        await asyncio.sleep(0.01)

                except Exception as e:
                    logger.error(f"ChatStreamAPIView: Error during streaming: {e}", exc_info=True)
                    yield create_sse_data({'type': 'error', 'message': f'Streaming error: {str(e)}'})

                # 发送完成信号
                yield create_sse_data({'type': 'complete'})

                # 发送流结束标记
                yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"ChatStreamAPIView: Error in stream generator: {e}", exc_info=True)
            yield create_sse_data({'type': 'error', 'message': f'Generator error: {str(e)}'})

    async def post(self, request, *args, **kwargs):
        """处理流式聊天请求"""
        try:
            # 手动认证（异步）
            user = await self.authenticate_request(request)
            request.user = user
            logger.info(f"ChatStreamAPIView: Received POST request from user {user.id}")
        except AuthenticationFailed as e:
            error_data = create_sse_data({
                'type': 'error',
                'message': str(e),
                'code': 401
            })
            return StreamingHttpResponse(
                iter([error_data]),
                content_type='text/event-stream; charset=utf-8',
                status=401
            )

        # 解析JSON数据
        try:
            import json as json_module
            body_data = json_module.loads(request.body.decode('utf-8'))
        except (json_module.JSONDecodeError, UnicodeDecodeError) as e:
            error_data = create_sse_data({
                'type': 'error',
                'message': f'Invalid JSON data: {str(e)}',
                'code': 400
            })
            return StreamingHttpResponse(
                iter([error_data]),
                content_type='text/event-stream; charset=utf-8',
                status=400
            )

        user_message_content = body_data.get('message')
        session_id = body_data.get('session_id')
        project_id = body_data.get('project_id')

        # 知识库相关参数
        knowledge_base_id = body_data.get('knowledge_base_id')
        use_knowledge_base = body_data.get('use_knowledge_base', True)
        similarity_threshold = body_data.get('similarity_threshold', 0.7)
        top_k = body_data.get('top_k', 5)

        # 提示词相关参数
        prompt_id = body_data.get('prompt_id')  # 用户指定的提示词ID

        # 验证项目ID是否提供
        if not project_id:
            error_data = create_sse_data({
                'type': 'error',
                'message': 'project_id is required',
                'code': status.HTTP_400_BAD_REQUEST
            })
            return StreamingHttpResponse(
                iter([error_data]),
                content_type='text/event-stream; charset=utf-8',
                status=status.HTTP_400_BAD_REQUEST
            )

        # 检查项目权限
        project = await sync_to_async(self._check_project_permission)(request.user, project_id)
        if not project:
            error_data = create_sse_data({
                'type': 'error',
                'message': "You don't have permission to access this project or project doesn't exist",
                'code': status.HTTP_403_FORBIDDEN
            })
            return StreamingHttpResponse(
                iter([error_data]),
                content_type='text/event-stream; charset=utf-8',
                status=status.HTTP_403_FORBIDDEN
            )

        is_new_session = False
        if not session_id:
            session_id = uuid.uuid4().hex
            is_new_session = True
            logger.info(f"ChatStreamAPIView: Generated new session_id: {session_id}")

        # 如果是新会话，立即创建ChatSession对象
        if is_new_session:
            try:
                await sync_to_async(ChatSession.objects.create)(
                    user=request.user,
                    session_id=session_id,
                    project=project,
                    title=f"新对话 - {user_message_content[:30]}" # 使用消息内容作为临时标题
                )
                logger.info(f"ChatStreamAPIView: Created new ChatSession entry for session_id: {session_id}")
            except Exception as e:
                logger.error(f"ChatStreamAPIView: Failed to create ChatSession entry: {e}", exc_info=True)


        if not user_message_content:
            logger.warning("ChatStreamAPIView: Message content is required but not provided.")
            error_data = create_sse_data({
                'type': 'error',
                'message': 'Message content is required',
                'code': status.HTTP_400_BAD_REQUEST
            })
            return StreamingHttpResponse(
                iter([error_data]),
                content_type='text/event-stream; charset=utf-8',
                status=status.HTTP_400_BAD_REQUEST
            )

        # 创建异步生成器
        async def async_generator():
            async for chunk in self._create_sse_generator(
                request, user_message_content, session_id, project_id, project,
                knowledge_base_id, use_knowledge_base, similarity_threshold, top_k, prompt_id
            ):
                yield chunk

        response = StreamingHttpResponse(
            async_generator(),
            content_type='text/event-stream; charset=utf-8'
        )
        response['Cache-Control'] = 'no-cache'
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Headers'] = 'Cache-Control'

        return response


class ProviderChoicesAPIView(APIView):
    """获取可用的LLM供应商选项"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        """返回所有可用的供应商选项"""
        choices = [{'value': choice[0], 'label': choice[1]} for choice in LLMConfig.PROVIDER_CHOICES]
        return Response({
            'status': 'success',
            'code': status.HTTP_200_OK,
            'message': 'Provider choices retrieved successfully.',
            'data': {'choices': choices}
        })


class KnowledgeRAGAPIView(APIView):
    """知识库RAG查询API视图"""
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """执行知识库RAG查询"""
        try:
            # 获取请求参数
            query = request.data.get('query')
            knowledge_base_id = request.data.get('knowledge_base_id')
            project_id = request.data.get('project_id')

            if not query:
                return Response(
                    {'error': '查询内容不能为空'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not knowledge_base_id:
                return Response(
                    {'error': '知识库ID不能为空'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 验证项目权限
            if project_id:
                try:
                    project = Project.objects.get(id=project_id)
                    if not project.members.filter(user=request.user).exists() and not request.user.is_superuser:
                        return Response(
                            {'error': '您没有权限访问此项目'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                except Project.DoesNotExist:
                    return Response(
                        {'error': '项目不存在'},
                        status=status.HTTP_404_NOT_FOUND
                    )

            # 验证知识库权限
            try:
                knowledge_base = KnowledgeBase.objects.get(id=knowledge_base_id)
                if not knowledge_base.project.members.filter(user=request.user).exists() and not request.user.is_superuser:
                    return Response(
                        {'error': '您没有权限访问此知识库'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except KnowledgeBase.DoesNotExist:
                return Response(
                    {'error': '知识库不存在'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # 获取LLM配置
            try:
                active_config = LLMConfig.objects.filter(is_active=True).first()
                if not active_config:
                    return Response(
                        {'error': '没有可用的LLM配置'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

                # 使用新的LLM工厂函数，支持多供应商
                llm = create_llm_instance(active_config, temperature=0.7)
            except Exception as e:
                logger.error(f"LLM配置错误: {e}")
                return Response(
                    {'error': 'LLM配置错误'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # 执行RAG查询
            rag_service = KnowledgeRAGService(llm)
            result = rag_service.query(
                question=query,
                knowledge_base_id=knowledge_base_id,
                user=request.user
            )

            return Response({
                'query': result['question'],
                'answer': result['answer'],
                'sources': result['context'],
                'retrieval_time': result['retrieval_time'],
                'generation_time': result['generation_time'],
                'total_time': result['total_time']
            })

        except Exception as e:
            logger.error(f"知识库RAG查询失败: {e}")
            return Response(
                {'error': f'查询失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )