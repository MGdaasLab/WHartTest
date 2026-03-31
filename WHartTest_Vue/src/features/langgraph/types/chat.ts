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

  // 多模态相关参数
  image?: string; // 图片base64编码（不含前缀），可选
  images?: string[]; // 多张图片base64编码（不含前缀），可选
  
  // Playwright 脚本生成参数
  generate_playwright_script?: boolean; // 是否在任务完成后自动生成 Playwright 脚本
  test_case_id?: number; // 关联的测试用例ID，生成脚本时必需
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
  image?: string; // 🆕 图片Data URL(包含完整的data:image/xxx;base64,前缀)
  images?: string[]; // 🆕 多张图片Data URL
  is_thinking_process?: boolean; // 思考过程标记
  // ⭐ Agent Loop 历史记录专用字段
  agent?: string; // 'agent_loop' 表示来自Agent Loop
  agent_type?: string; // 'intermediate' | 'final' 表示中间/最终响应
  step?: number; // Agent Loop步骤号
  max_steps?: number; // Agent Loop最大步骤数
  sse_event_type?: string; // 'message' | 'tool_result' SSE事件类型
}

/**
 * 聊天历史记录响应数据
 */
export interface ChatHistoryResponseData {
  thread_id: string;
  session_id: string;
  project_id: string; // 🆕 新增项目ID字段
  project_name: string; // 🆕 新增项目名称字段
  prompt_id: number | null; // 🆕 新增提示词ID字段
  prompt_name: string | null; // 🆕 新增提示词名称字段
  history: ChatHistoryMessage[];
  context_token_count?: number; // 上下文Token使用量
  context_limit?: number; // 上下文Token限制
}

/**
 * 会话详情（轻量级，用于列表展示）
 */
export interface ChatSessionDetail {
  id: string;
  title: string;
  updated_at: string | null;
  created_at: string | null;
}

/**
 * 会话列表响应数据
 */
export interface ChatSessionsResponseData {
  user_id: string;
  sessions: string[]; // 该用户所有 session_id 列表（向后兼容）
  sessions_detail?: ChatSessionDetail[]; // 带详情的会话列表
}
