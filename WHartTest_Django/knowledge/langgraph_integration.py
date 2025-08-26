"""
LangGraph与知识库集成模块
提供RAG功能的LangGraph节点和状态管理
"""
import time
from typing import List, Dict, Any, TypedDict, Annotated
from langchain_core.documents import Document as LangChainDocument
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from .models import KnowledgeBase
from .services import KnowledgeBaseService
import logging

logger = logging.getLogger(__name__)


class RAGState(TypedDict):
    """RAG状态定义"""
    messages: Annotated[List, add_messages]
    question: str
    knowledge_base_id: str
    context: List[Dict[str, Any]]
    answer: str
    retrieval_time: float
    generation_time: float
    total_time: float
    # 新增字段
    project_id: str
    user_id: str
    thread_id: str
    use_knowledge_base: bool
    similarity_threshold: float
    top_k: int


class KnowledgeRAGService:
    """知识库RAG服务"""

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.graph = self._build_rag_graph()

    def _build_rag_graph(self) -> StateGraph:
        """构建RAG图"""
        graph_builder = StateGraph(RAGState)

        # 添加节点
        graph_builder.add_node("retrieve", self._retrieve_node)
        graph_builder.add_node("generate", self._generate_node)

        # 设置边
        graph_builder.add_edge(START, "retrieve")
        graph_builder.add_edge("retrieve", "generate")
        graph_builder.add_edge("generate", END)

        return graph_builder.compile()

    def _retrieve_node(self, state: RAGState) -> Dict[str, Any]:
        """检索节点"""
        start_time = time.time()

        try:
            # 检查是否需要使用知识库
            if not state.get("use_knowledge_base", True):
                logger.info("跳过知识库检索")
                return {
                    "context": [],
                    "retrieval_time": time.time() - start_time
                }

            # 获取知识库
            knowledge_base_id = state.get("knowledge_base_id")
            if not knowledge_base_id:
                logger.warning("未提供知识库ID")
                return {
                    "context": [],
                    "retrieval_time": time.time() - start_time
                }

            knowledge_base = KnowledgeBase.objects.get(id=knowledge_base_id)
            service = KnowledgeBaseService(knowledge_base)

            # 获取检索参数
            top_k = state.get("top_k", 5)
            similarity_threshold = state.get("similarity_threshold", 0.7)

            # 执行检索
            search_results = service.vector_manager.similarity_search(
                state["question"], k=top_k, score_threshold=similarity_threshold
            )

            retrieval_time = time.time() - start_time

            logger.info(f"检索完成: 找到 {len(search_results)} 个相关片段，耗时 {retrieval_time:.3f}s")

            return {
                "context": search_results,
                "retrieval_time": retrieval_time
            }

        except Exception as e:
            logger.error(f"检索失败: {e}")
            return {
                "context": [],
                "retrieval_time": time.time() - start_time
            }

    def _generate_node(self, state: RAGState) -> Dict[str, Any]:
        """生成节点"""
        start_time = time.time()

        try:
            # 构建上下文
            context_sources = state.get("context", [])
            context_text = ""

            if context_sources:
                # 构建详细的上下文信息
                context_parts = []
                for i, result in enumerate(context_sources[:3], 1):
                    content = result.get("content", "")
                    score = result.get("similarity_score", 0.0)
                    metadata = result.get("metadata", {})
                    source = metadata.get("source", "未知来源")

                    context_parts.append(f"[来源{i}: {source} (相似度: {score:.2f})]\n{content}")

                context_text = "\n\n".join(context_parts)

            # 构建提示
            if context_text:
                system_prompt = """你是一个智能助手，请基于提供的上下文信息回答用户的问题。

请遵循以下原则：
1. 优先使用上下文信息中的内容回答问题
2. 如果上下文信息不足以完整回答问题，请明确说明
3. 保持回答准确、简洁且有帮助
4. 可以适当引用来源信息
5. 如果问题与上下文完全无关，请说明并提供一般性建议

上下文信息：
{context}"""

                messages = [
                    SystemMessage(content=system_prompt.format(context=context_text)),
                    HumanMessage(content=state["question"])
                ]

                logger.info(f"使用知识库上下文生成回答，上下文长度: {len(context_text)}")
            else:
                system_prompt = """你是一个智能助手，请回答用户的问题。
由于没有找到相关的知识库信息，请基于你的一般知识回答，并明确说明这不是基于特定文档的回答。"""

                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=state["question"])
                ]

                logger.info("未找到相关上下文，使用一般知识回答")

            # 生成回答
            response = self.llm.invoke(messages)
            generation_time = time.time() - start_time

            logger.info(f"回答生成完成，耗时 {generation_time:.3f}s")

            return {
                "answer": response.content,
                "generation_time": generation_time,
                "messages": [AIMessage(content=response.content)]
            }

        except Exception as e:
            logger.error(f"生成回答失败: {e}")
            error_message = "抱歉，生成回答时出现错误。请稍后重试。"
            return {
                "answer": error_message,
                "generation_time": time.time() - start_time,
                "messages": [AIMessage(content=error_message)]
            }

    def query(self, question: str, knowledge_base_id: str = None, user=None,
              project_id: str = None, thread_id: str = None,
              use_knowledge_base: bool = True, similarity_threshold: float = 0.7,
              top_k: int = 5) -> Dict[str, Any]:
        """执行RAG查询"""
        start_time = time.time()

        initial_state = {
            "messages": [HumanMessage(content=question)],
            "question": question,
            "knowledge_base_id": knowledge_base_id or "",
            "context": [],
            "answer": "",
            "retrieval_time": 0.0,
            "generation_time": 0.0,
            "total_time": 0.0,
            # 新增参数
            "project_id": project_id or "",
            "user_id": str(user.id) if user else "",
            "thread_id": thread_id or "",
            "use_knowledge_base": use_knowledge_base,
            "similarity_threshold": similarity_threshold,
            "top_k": top_k
        }

        try:
            logger.info(f"开始RAG查询: {question[:50]}...")
            logger.info(f"知识库ID: {knowledge_base_id}, 使用知识库: {use_knowledge_base}")

            # 执行图
            final_state = self.graph.invoke(initial_state)

            # 计算总时间
            total_time = time.time() - start_time
            final_state["total_time"] = total_time

            logger.info(f"RAG查询完成，总耗时: {total_time:.3f}s")

            # 记录查询日志
            if user and knowledge_base_id:
                self._log_query(final_state, user)

            return final_state

        except Exception as e:
            logger.error(f"RAG查询失败: {e}")
            error_response = {
                "question": question,
                "answer": "抱歉，查询过程中出现错误。",
                "context": [],
                "retrieval_time": 0.0,
                "generation_time": 0.0,
                "total_time": time.time() - start_time
            }
            return error_response

    def _log_query(self, state: RAGState, user):
        """记录查询日志"""
        try:
            from .models import QueryLog

            knowledge_base = KnowledgeBase.objects.get(id=state["knowledge_base_id"])

            QueryLog.objects.create(
                knowledge_base=knowledge_base,
                user=user,
                query=state["question"],
                response=state["answer"],
                retrieved_chunks=[{
                    'content': result['content'][:200] + '...' if len(result['content']) > 200 else result['content'],
                    'metadata': result.get('metadata', {}),
                    'score': result.get('similarity_score', 0.0)
                } for result in state["context"]],
                similarity_scores=[result.get('similarity_score', 0.0) for result in state["context"]],
                retrieval_time=state["retrieval_time"],
                generation_time=state["generation_time"],
                total_time=state["total_time"]
            )
        except Exception as e:
            logger.error(f"记录查询日志失败: {e}")


class LangGraphKnowledgeIntegration:
    """LangGraph对话系统的知识库集成"""

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.rag_service = ConversationalRAGService(llm)

    def create_knowledge_enhanced_agent(self, project_id: str, knowledge_base_id: str = None):
        """创建知识库增强的对话代理"""
        from langgraph.graph import StateGraph, END, START
        from typing import TypedDict, Annotated, List
        from langchain_core.messages import AnyMessage
        from langgraph.graph.message import add_messages

        class AgentState(TypedDict):
            messages: Annotated[List[AnyMessage], add_messages]
            project_id: str
            knowledge_base_id: str
            use_knowledge_base: bool

        def should_use_knowledge_base(state: AgentState) -> str:
            """判断是否需要使用知识库"""
            if not state.get("use_knowledge_base", True):
                return "chat_only"

            if not state.get("knowledge_base_id"):
                return "chat_only"

            # 获取最新的用户消息
            user_messages = [msg for msg in state["messages"]
                           if hasattr(msg, 'type') and msg.type == 'human']

            if not user_messages:
                return "chat_only"

            latest_message = user_messages[-1].content

            # 简单的关键词检测，判断是否需要知识库
            knowledge_keywords = [
                "什么是", "如何", "怎么", "为什么", "解释", "定义",
                "原理", "方法", "步骤", "流程", "文档", "资料"
            ]

            if any(keyword in latest_message for keyword in knowledge_keywords):
                return "rag_chat"
            else:
                return "chat_only"

        def rag_chat_node(state: AgentState) -> AgentState:
            """RAG增强的对话节点"""
            try:
                # 获取最新的用户消息
                user_messages = [msg for msg in state["messages"]
                               if hasattr(msg, 'type') and msg.type == 'human']

                if not user_messages:
                    return state

                latest_message = user_messages[-1].content

                # 执行RAG查询
                rag_result = self.rag_service.query(
                    question=latest_message,
                    knowledge_base_id=state.get("knowledge_base_id"),
                    use_knowledge_base=True,
                    similarity_threshold=0.6,
                    top_k=3
                )

                # 更新消息
                new_messages = rag_result.get("messages", [])
                return {
                    "messages": new_messages
                }

            except Exception as e:
                logger.error(f"RAG对话节点失败: {e}")
                # 降级到普通对话
                return chat_only_node(state)

        def chat_only_node(state: AgentState) -> AgentState:
            """纯对话节点"""
            try:
                response = self.llm.invoke(state["messages"])
                return {
                    "messages": [response]
                }
            except Exception as e:
                logger.error(f"对话节点失败: {e}")
                from langchain_core.messages import AIMessage
                error_msg = AIMessage(content="抱歉，我遇到了一些问题，请稍后重试。")
                return {
                    "messages": [error_msg]
                }

        # 构建图
        graph_builder = StateGraph(AgentState)

        # 添加节点
        graph_builder.add_node("rag_chat", rag_chat_node)
        graph_builder.add_node("chat_only", chat_only_node)

        # 设置条件边
        graph_builder.add_conditional_edges(
            START,
            should_use_knowledge_base,
            {
                "rag_chat": "rag_chat",
                "chat_only": "chat_only"
            }
        )

        # 设置结束边
        graph_builder.add_edge("rag_chat", END)
        graph_builder.add_edge("chat_only", END)

        return graph_builder.compile()

    def get_project_knowledge_bases(self, project_id: str) -> List[Dict[str, Any]]:
        """获取项目的知识库列表"""
        try:
            from projects.models import Project
            project = Project.objects.get(id=project_id)
            knowledge_bases = project.knowledge_bases.filter(is_active=True)

            return [{
                "id": str(kb.id),
                "name": kb.name,
                "description": kb.description,
                "document_count": kb.documents.filter(status='completed').count(),
                "created_at": kb.created_at.isoformat()
            } for kb in knowledge_bases]

        except Exception as e:
            logger.error(f"获取项目知识库失败: {e}")
            return []


class ConversationalRAGService(KnowledgeRAGService):
    """对话式RAG服务，支持多轮对话"""

    def _build_rag_graph(self) -> StateGraph:
        """构建对话式RAG图"""
        graph_builder = StateGraph(RAGState)

        # 添加节点
        graph_builder.add_node("analyze_query", self._analyze_query_node)
        graph_builder.add_node("retrieve", self._retrieve_node)
        graph_builder.add_node("generate", self._conversational_generate_node)

        # 设置边
        graph_builder.add_edge(START, "analyze_query")
        graph_builder.add_edge("analyze_query", "retrieve")
        graph_builder.add_edge("retrieve", "generate")
        graph_builder.add_edge("generate", END)

        return graph_builder.compile()

    def _analyze_query_node(self, state: RAGState) -> Dict[str, Any]:
        """查询分析节点，处理对话历史"""
        try:
            # 获取最新的用户消息
            user_messages = [msg for msg in state["messages"] if isinstance(msg, HumanMessage)]
            if user_messages:
                latest_question = user_messages[-1].content
                return {"question": latest_question}
            else:
                return {"question": state.get("question", "")}
        except Exception as e:
            logger.error(f"查询分析失败: {e}")
            return {"question": state.get("question", "")}

    def _conversational_generate_node(self, state: RAGState) -> Dict[str, Any]:
        """对话式生成节点，考虑对话历史"""
        start_time = time.time()

        try:
            # 构建上下文
            context_text = "\n\n".join([
                result["content"] for result in state["context"][:3]
            ])

            # 构建对话历史
            conversation_history = []
            for msg in state["messages"][:-1]:  # 排除最新的用户消息
                if isinstance(msg, (HumanMessage, AIMessage)):
                    conversation_history.append(msg)

            # 构建提示
            if context_text:
                system_prompt = """你是一个智能助手，请基于提供的上下文信息和对话历史回答用户的问题。
请保持回答准确、简洁且有帮助。如果上下文中没有相关信息，请明确说明。

上下文信息：
{context}"""

                messages = [SystemMessage(content=system_prompt.format(context=context_text))]
                messages.extend(conversation_history)
                messages.append(HumanMessage(content=state["question"]))
            else:
                system_prompt = "你是一个智能助手，请基于对话历史回答用户的问题。如果没有足够的信息，请说明。"
                messages = [SystemMessage(content=system_prompt)]
                messages.extend(conversation_history)
                messages.append(HumanMessage(content=state["question"]))

            # 生成回答
            response = self.llm.invoke(messages)
            generation_time = time.time() - start_time

            return {
                "answer": response.content,
                "generation_time": generation_time,
                "messages": state["messages"] + [AIMessage(content=response.content)]
            }

        except Exception as e:
            logger.error(f"对话式生成回答失败: {e}")
            error_message = "抱歉，生成回答时出现错误。"
            return {
                "answer": error_message,
                "generation_time": time.time() - start_time,
                "messages": state["messages"] + [AIMessage(content=error_message)]
            }


def create_knowledge_tool(knowledge_base_id: str, user, similarity_threshold: float = 0.7, top_k: int = 5):
    """创建知识库工具，用于Agent调用"""
    from langchain_core.tools import tool

    @tool
    def knowledge_search(query: str) -> str:
        """
        搜索知识库获取相关信息

        Args:
            query: 搜索查询字符串

        Returns:
            str: 搜索结果，包含相关文档内容
        """
        try:
            logger.info(f"知识库工具被调用: {query[:50]}...")

            # 获取知识库
            knowledge_base = KnowledgeBase.objects.get(id=knowledge_base_id)
            service = KnowledgeBaseService(knowledge_base)

            # 执行检索
            search_results = service.vector_manager.similarity_search(
                query, k=top_k, score_threshold=similarity_threshold
            )

            if not search_results:
                return "未找到相关信息。"

            # 格式化结果
            formatted_results = []
            for i, result in enumerate(search_results[:3], 1):
                content = result.get("content", "")
                score = result.get("similarity_score", 0.0)
                metadata = result.get("metadata", {})
                source = metadata.get("source", "未知来源")

                # 将相似度转换为百分比显示
                similarity_percentage = score * 100
                formatted_results.append(
                    f"[结果{i}] (相似度: {similarity_percentage:.1f}%, 来源: {source})\n{content}"
                )

            result_text = "\n\n".join(formatted_results)
            logger.info(f"知识库工具返回 {len(search_results)} 个结果")

            return result_text

        except Exception as e:
            logger.error(f"知识库工具调用失败: {e}")
            return f"知识库搜索失败: {str(e)}"

    # 设置工具的名称和描述
    knowledge_search.name = "knowledge_search"
    knowledge_search.description = f"搜索知识库 {knowledge_base_id} 获取相关信息。当用户询问特定知识、文档内容或需要查找资料时使用此工具。"

    return knowledge_search
