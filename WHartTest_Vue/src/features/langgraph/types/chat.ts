/**
 * 对话请求体
 */
export interface ChatRequest {
  message: string; // 用户发送的消息
  session_id?: string; // 可选, 字符串, 用于区分同一用户的不同对话会话/窗口
  project_id: string; // 项目ID，必需 (更新为string类型)

  // 提示词相关参数
  prompt_id?: number; // 可选，指定使用的提示词ID

  // 知识库相关参数
  knowledge_base_id?: string; // 知识库ID，可选
  use_knowledge_base?: boolean; // 是否启用知识库功能，默认true
  similarity_threshold?: number; // 相似度阈值，范围0.0-1.0，默认0.3
  top_k?: number; // 检索结果数量，范围1-20，默认5
}

/**
 * 对话响应数据
 */
export interface ChatResponseData {
  user_message: string;
  llm_response: string;
  active_llm: string; // 当前激活的LLM配置名称
  thread_id: string; // 后端生成的对话线程ID
  session_id: string; // 会话ID，前端需要获取并持久化此ID
  conversation_flow: ChatHistoryMessage[]; // 完整对话流程
  project_id: number; // 项目ID
  project_name: string; // 项目名称

  // 知识库相关响应字段
  knowledge_base_id?: string; // 使用的知识库ID
  use_knowledge_base?: boolean; // 是否启用了知识库功能
  knowledge_base_used?: boolean; // 是否实际使用了知识库
}

/**
 * 聊天历史记录中的消息
 */
export interface ChatHistoryMessage {
  type: 'human' | 'ai' | 'tool' | 'system'; // 🆕 添加 system 类型
  content: string;
  timestamp: string; // 消息时间戳
}

/**
 * 聊天历史记录响应数据
 */
export interface ChatHistoryResponseData {
  thread_id: string;
  session_id: string;
  project_id: string; // 🆕 新增项目ID字段
  project_name: string; // 🆕 新增项目名称字段
  history: ChatHistoryMessage[];
}

/**
 * 会话列表响应数据
 */
export interface ChatSessionsResponseData {
  user_id: string;
  sessions: string[]; // 该用户所有 session_id 列表
}