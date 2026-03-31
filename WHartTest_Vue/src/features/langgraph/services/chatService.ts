import { ref } from 'vue';
import { request } from '@/utils/request';
import { useAuthStore } from '@/store/authStore';
import type { ApiResponse } from '@/features/langgraph/types/api';
import type {
  ChatRequest,
  ChatResponseData,
  ChatHistoryResponseData,
  ChatSessionsResponseData
} from '@/features/langgraph/types/chat';
import type { ToolFileAttachment } from '@/features/langgraph/utils/toolResultParser';
import { parseToolResultDisplayPayload } from '@/features/langgraph/utils/toolResultParser';

// --- 全局流式状态管理 ---
interface StreamMessage {
  content: string;
  type: 'human' | 'ai' | 'tool' | 'system' | 'agent_step';
  time: string;
  toolName?: string;
  imageDataUrl?: string;
  fileAttachments?: ToolFileAttachment[];
  isExpanded?: boolean;
  isThinkingProcess?: boolean;
  isThinkingExpanded?: boolean;
  // Agent Step 专用字段
  stepNumber?: number;
  maxSteps?: number;
  stepStatus?: 'start' | 'complete' | 'error';
}

interface StreamState {
  content: string;
  error?: string;
  isComplete: boolean;
  messages: StreamMessage[]; // 存储所有消息,包括工具消息
  contextTokenCount?: number; // 当前上下文Token数
  contextLimit?: number; // 上下文Token限制
  currentStep?: number;  // Agent Loop 当前步骤
  maxSteps?: number;     // Agent Loop 最大步骤数
  userMessage?: string;  // 用户发送的消息内容
  userMessageTime?: string;  // 用户消息时间（会话创建时间）
  taskId?: number;       // Agent Task ID
  // ⭐ 脚本生成信息
  scriptGeneration?: {
    available: boolean;
    playwrightSteps: number;
    message: string;
  };
  // ⭐ HITL 中断信息
  interrupt?: {
    id: string;
    interrupt_id?: string;
    action_requests: Array<{
      name: string;
      args: Record<string, unknown>;
      description?: string;
      auto_reject?: boolean;
    }>;
  };
  isWaitingForApproval?: boolean; // 是否正在等待用户审批
}

// Agent Loop SSE 事件类型定义（供文档和类型参考）
export interface AgentLoopSseEvent {
  type: string;
  session_id?: string;
  context_limit?: number;
  context_token_count?: number;
  max_steps?: number | string;
  step?: number | string;
  summary?: string | Record<string, unknown>;
  message?: string;
  data?: string | { content?: string } | Record<string, unknown> | null;
}

// 格式化时间辅助函数
const formatStreamTime = (): string => {
  const now = new Date();
  return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
};

// 格式化 ISO 时间字符串为显示格式
const formatIsoTime = (isoString: string | null | undefined): string => {
  if (!isoString) return formatStreamTime();
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return formatStreamTime();
    return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
  } catch {
    return formatStreamTime();
  }
};

// 数字字段归一化（处理字符串或数字类型）
const normalizeNumericField = (value: unknown): number | undefined => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return undefined;
};

// 解析消息内容 - 支持 Agent Loop 纯文本和旧 LangGraph 格式
const parseMessageContent = (data: unknown): string => {
  if (typeof data === 'string') {
    // 旧 LangGraph 格式: AIMessageChunk(content='xxx')
    if (data.includes('AIMessageChunk')) {
      const match = data.match(/content='((?:\\'|[^'])*)'/);
      if (match && match[1] !== undefined) {
        return match[1].replace(/\\'/g, "'");
      }
    }
    // Agent Loop 纯文本格式
    return data;
  }
  // 对象格式 { content: string }
  if (data && typeof data === 'object' && 'content' in data && typeof (data as Record<string, unknown>).content === 'string') {
    return (data as Record<string, unknown>).content as string;
  }
  return '';
};

// 上下文使用快照（独立缓存，不受clearStreamState影响）
interface ContextUsageSnapshot {
  tokenCount: number;
  limit: number;
}

export const activeStreams = ref<Record<string, StreamState>>({});
export const latestContextUsage = ref<Record<string, ContextUsageSnapshot>>({});

export const clearStreamState = (sessionId: string) => {
  if (activeStreams.value[sessionId]) {
    delete activeStreams.value[sessionId];
  }
  // 注意：不清除 latestContextUsage，保留最后的Token使用信息
};
// --- 全局流式状态管理结束 ---

const API_BASE_URL = '/lg/chat';
// Agent Loop API 端点 - 解决 Token 累积问题
const AGENT_LOOP_API_URL = '/orchestrator/agent-loop';
// Agent Loop 停止 API 端点
const AGENT_LOOP_STOP_API_URL = '/orchestrator/agent-loop/stop';

// 获取API基础URL
function getApiBaseUrl() {
  const envUrl = import.meta.env.VITE_API_BASE_URL;

  // 如果环境变量是完整URL（包含http/https），直接使用
  if (envUrl && (envUrl.startsWith('http://') || envUrl.startsWith('https://'))) {
    return envUrl;
  }

  // 否则使用相对路径，让浏览器自动解析到当前域名
  return '/api';
}

/**
 * 发送对话消息（旧版 API，已废弃）
 * @deprecated 请使用 sendChatMessageNonStream 调用统一的 Agent Loop 接口
 */
export async function sendChatMessage(
  data: ChatRequest
): Promise<ApiResponse<ChatResponseData>> {
  const response = await request<ChatResponseData>({
    url: `${API_BASE_URL}/`,
    method: 'POST',
    data
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || 'success',
      data: response.data!,
      errors: undefined
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to send chat message',
      data: {} as ChatResponseData,
      errors: { detail: [response.error || 'Unknown error'] }
    };
  }
}

/**
 * Agent Loop 非流式响应数据类型
 */
export interface AgentLoopNonStreamResponse {
  session_id: string;
  content: string;
  total_steps: number;
  tool_results: Array<{ summary: string; step: number; tool_output?: unknown; tool_name?: string }>;
  context_token_count: number;
  context_limit: number;
  interrupt?: {
    interrupt_id: string;
    action_requests: Array<{
      name: string;
      args: Record<string, unknown>;
      description?: string;
    }>;
  };
  script_generation?: {
    enabled: boolean;
    message: string;
  };
}

/**
 * 发送非流式对话消息（统一 Agent Loop 接口）
 *
 * 使用 Agent Loop API 的 stream=false 模式，获得与流式模式一致的功能：
 * - HITL（人工审批）支持
 * - 上下文摘要中间件
 * - MCP 工具调用
 */
export async function sendChatMessageNonStream(
  data: ChatRequest
): Promise<ApiResponse<AgentLoopNonStreamResponse>> {
  const authStore = useAuthStore();
  const token = authStore.getAccessToken;

  if (!token) {
    return {
      status: 'error',
      code: 401,
      message: '未登录或登录已过期',
      data: null as unknown as AgentLoopNonStreamResponse,
      errors: { detail: ['未登录'] }
    };
  }

  try {
    const requestData = {
      ...data,
      stream: false  // 关键：使用非流式模式
    };

    const response = await fetch(`${getApiBaseUrl()}${AGENT_LOOP_API_URL}/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(requestData)
    });

    if (response.status === 401) {
      // Token 过期，尝试刷新
      const newToken = await refreshAccessToken();
      if (!newToken) {
        return {
          status: 'error',
          code: 401,
          message: '登录已过期，请重新登录',
          data: null as unknown as AgentLoopNonStreamResponse,
          errors: { detail: ['Token 刷新失败'] }
        };
      }

      // 使用新 token 重试
      const retryResponse = await fetch(`${getApiBaseUrl()}${AGENT_LOOP_API_URL}/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${newToken}`
        },
        body: JSON.stringify(requestData)
      });

      const retryData = await retryResponse.json();
      if (retryData.status === 'success') {
        return {
          status: 'success',
          code: 200,
          message: retryData.message || 'success',
          data: retryData.data,
          errors: undefined
        };
      } else {
        return {
          status: 'error',
          code: retryData.code || 500,
          message: retryData.message || 'Request failed',
          data: null as unknown as AgentLoopNonStreamResponse,
          errors: retryData.errors || { detail: [retryData.message] }
        };
      }
    }

    const responseData = await response.json();

    if (responseData.status === 'success') {
      return {
        status: 'success',
        code: 200,
        message: responseData.message || 'success',
        data: responseData.data,
        errors: undefined
      };
    } else {
      return {
        status: 'error',
        code: responseData.code || 500,
        message: responseData.message || 'Request failed',
        data: null as unknown as AgentLoopNonStreamResponse,
        errors: responseData.errors || { detail: [responseData.message] }
      };
    }
  } catch (error: any) {
    console.error('[ChatService] Non-stream request error:', error);
    return {
      status: 'error',
      code: 500,
      message: error.message || '请求失败',
      data: null as unknown as AgentLoopNonStreamResponse,
      errors: { detail: [error.message || 'Unknown error'] }
    };
  }
}

/**
 * 刷新token
 */
async function refreshAccessToken(): Promise<string | null> {
  const authStore = useAuthStore();
  const refreshToken = authStore.getRefreshToken;

  if (!refreshToken) {
    authStore.logout();
    return null;
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/token/refresh/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        refresh: refreshToken
      }),
    });

    if (response.ok) {
      const data = await response.json();
      if (data.access) {
        // 更新token
        localStorage.setItem('auth-accessToken', data.access);
        return data.access;
      }
    }

    // 刷新失败，登出用户
    authStore.logout();
    return null;
  } catch (error) {
    console.error('Token refresh failed:', error);
    authStore.logout();
    return null;
  }
}

/**
 * 发送流式对话消息
 */
export async function sendChatMessageStream(
  data: ChatRequest,
  onStart: (sessionId: string) => void, // 简化回调，只保留 onStart
  signal?: AbortSignal
): Promise<void> {
  const authStore = useAuthStore();
  let token = authStore.getAccessToken;
  let streamSessionId: string | null = data.session_id || null;

  // 错误处理函数，用于更新全局状态
  const handleError = (error: any, sessionId: string | null) => {
    // 判断是否是用户主动中断（AbortError）
    const isAbortError = error?.name === 'AbortError' ||
                         error?.message?.includes('aborted') ||
                         error?.message?.includes('BodyStreamBuffer') ||
                         error?.message?.includes('The user aborted');

    if (isAbortError) {
      // 用户主动中断，静默处理，不显示错误
      console.log('[ChatService] Stream aborted by user');
      if (sessionId && activeStreams.value[sessionId]) {
        activeStreams.value[sessionId].isComplete = true;
        // 不设置 error，避免显示错误提示
      }
      return;
    }

    // 真正的错误
    console.error('Stream error:', error);
    if (sessionId && activeStreams.value[sessionId]) {
      activeStreams.value[sessionId].error = error.message || '流式请求失败';
      activeStreams.value[sessionId].isComplete = true;
    }
  };

  if (!token) {
    handleError(new Error('未登录或登录已过期'), streamSessionId);
    return;
  }

  try {
    let response = await fetch(`${getApiBaseUrl()}${AGENT_LOOP_API_URL}/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify(data),
      signal,
    });

    if (response.status === 401) {
      const newToken = await refreshAccessToken();
      if (newToken) {
        token = newToken;
        response = await fetch(`${getApiBaseUrl()}${AGENT_LOOP_API_URL}/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify(data),
          signal,
        });
      } else {
        handleError(new Error('登录已过期，请重新登录'), streamSessionId);
        return;
      }
    }

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) {
      throw new Error('Failed to get response reader');
    }

    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      
      if (done) {
        // 流结束时，处理buffer中剩余的数据
        if (buffer.trim()) {
          const remainingLines = buffer.split('\n');
          for (const line of remainingLines) {
            if (line.trim() === '' || !line.startsWith('data: ')) continue;
            
            const jsonData = line.slice(6);
            if (jsonData === '[DONE]') continue;
            
            try {
              const parsed = JSON.parse(jsonData);
              
              // 处理上下文Token更新事件
              if (parsed.type === 'context_update' && streamSessionId) {
                const tokenCount = parsed.context_token_count ?? 0;
                const limit = parsed.context_limit ?? 128000;
                latestContextUsage.value[streamSessionId] = { tokenCount, limit };
                
                if (activeStreams.value[streamSessionId]) {
                  activeStreams.value[streamSessionId].contextTokenCount = tokenCount;
                  activeStreams.value[streamSessionId].contextLimit = limit;
                }
              }
              
              if (parsed.type === 'complete' && streamSessionId && activeStreams.value[streamSessionId]) {
                activeStreams.value[streamSessionId].isComplete = true;
              }
            } catch (e) {
              console.warn('Failed to parse remaining SSE data:', line);
            }
          }
        }
        
        // ⚠️ 流结束但未收到 complete/[DONE] 事件 = 异常中断
        // 不自动设置 isComplete，让前端保持加载状态直到用户手动刷新
        // 这避免了网络波动导致停止按钮过早消失的问题
        // HITL: 如果正在等待审批，不设置错误状态
        if (streamSessionId && activeStreams.value[streamSessionId] && 
            !activeStreams.value[streamSessionId].isComplete &&
            !activeStreams.value[streamSessionId].isWaitingForApproval) {
            console.warn('[ChatService] Stream ended without complete event, possible network interruption');
            // 设置错误状态而非完成状态，让用户知道可能需要重试
            activeStreams.value[streamSessionId].error = '连接意外中断，请重试';
            activeStreams.value[streamSessionId].isComplete = true;
        }
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.trim() === '' || !line.startsWith('data: ')) continue;
        
        const jsonData = line.slice(6);
        if (jsonData === '[DONE]') {
            if (streamSessionId && activeStreams.value[streamSessionId]) {
                // HITL: 如果正在等待审批，不设置 isComplete，让 resumeAgentLoop 处理后续流程
                if (!activeStreams.value[streamSessionId].isWaitingForApproval) {
                    activeStreams.value[streamSessionId].isComplete = true;
                }
            }
            continue;
        }

        try {
          const parsed = JSON.parse(jsonData);

          if (parsed.type === 'error') {
            handleError(new Error(parsed.message || '流式请求失败'), streamSessionId);
            return;
          }

          if (parsed.type === 'start' && parsed.session_id) {
            streamSessionId = parsed.session_id;
            if (streamSessionId) {
              // 从缓存中获取上一次的token使用信息，避免闪烁
              const cachedUsage = latestContextUsage.value[streamSessionId];
              const prevTokenCount = cachedUsage?.tokenCount || 0;
              const contextLimit = parsed.context_limit || cachedUsage?.limit || 128000;
              const initialMaxSteps = normalizeNumericField(parsed.max_steps);

              // 初始化或重置此会话的流状态，保留之前的token信息
              activeStreams.value[streamSessionId] = {
                content: '',
                isComplete: false,
                messages: [],
                contextTokenCount: prevTokenCount,
                contextLimit: contextLimit,
                currentStep: 0,
                maxSteps: initialMaxSteps,
                userMessage: data.message, // 保存用户消息
                userMessageTime: formatIsoTime(parsed.created_at) // 使用会话创建时间
              };
              onStart(streamSessionId);
            }
          }

          // 处理上下文Token更新事件
          if (parsed.type === 'context_update' && streamSessionId) {
            const tokenCount = parsed.context_token_count ?? 0;
            const limit = parsed.context_limit ?? 128000;
            
            // 总是更新独立缓存（优先保证缓存被更新）
            latestContextUsage.value[streamSessionId] = { tokenCount, limit };
            
            // 如果活跃流还存在，也更新它
            if (activeStreams.value[streamSessionId]) {
              activeStreams.value[streamSessionId].contextTokenCount = tokenCount;
              activeStreams.value[streamSessionId].contextLimit = limit;
            }
          }

          // 处理警告事件（如上下文即将满）
          if (parsed.type === 'warning' && streamSessionId && activeStreams.value[streamSessionId]) {
            const warningMessage = parsed.message || '警告';
            console.warn('[Chat] Warning:', warningMessage);
            activeStreams.value[streamSessionId].messages.push({
              content: warningMessage,
              type: 'system',
              time: formatStreamTime()
            });
          }

          // 处理 Agent Loop 步骤开始事件
          if (parsed.type === 'step_start' && streamSessionId && activeStreams.value[streamSessionId]) {
            const stepNumber = normalizeNumericField(parsed.step);
            const maxSteps = normalizeNumericField(parsed.max_steps);
            console.log('[step_start] raw:', parsed.step, parsed.max_steps, '| normalized:', stepNumber, maxSteps);
            if (maxSteps !== undefined) {
              activeStreams.value[streamSessionId].maxSteps = maxSteps;
            }
            if (stepNumber !== undefined) {
              activeStreams.value[streamSessionId].currentStep = stepNumber;
            }
            activeStreams.value[streamSessionId].messages.push({
              content: '',
              type: 'agent_step',
              time: formatStreamTime(),
              stepNumber: stepNumber,
              maxSteps: maxSteps,
              stepStatus: 'start',
              isThinkingProcess: true
            });
            console.log('[step_start] pushed message with stepNumber:', stepNumber, 'maxSteps:', maxSteps);
          }

          // 处理 Agent Loop 步骤完成事件
          if (parsed.type === 'step_complete' && streamSessionId && activeStreams.value[streamSessionId]) {
            const stepNumber = normalizeNumericField(parsed.step);
            if (stepNumber !== undefined) {
              activeStreams.value[streamSessionId].currentStep = stepNumber;
            }
            // ✅ 移除step_complete的重复分隔符显示
            // step_start已经插入了分隔符,step_complete不需要再显示
          }

          // 处理 Agent Loop 工具结果事件
          if (parsed.type === 'tool_result' && streamSessionId && activeStreams.value[streamSessionId]) {
            // 优先使用 tool_output（完整内容），fallback 到 summary（截断摘要）
            const toolOutput = parsed.tool_output || parsed.content || parsed.summary;
            const toolPayload = parseToolResultDisplayPayload(toolOutput);
            if (toolPayload.content || toolPayload.imageDataUrl) {
              const time = formatStreamTime();
              // 如果当前有AI流式内容,先将其固化为独立消息
              if (activeStreams.value[streamSessionId].content && activeStreams.value[streamSessionId].content.trim()) {
                activeStreams.value[streamSessionId].messages.push({
                  content: activeStreams.value[streamSessionId].content,
                  type: 'ai',
                  time: time,
                  isExpanded: false
                });
                activeStreams.value[streamSessionId].content = '';
              }
              activeStreams.value[streamSessionId].messages.push({
                content: toolPayload.content || '[工具返回了图片]',
                type: 'tool',
                time: time,
                toolName: typeof parsed.tool_name === 'string' ? parsed.tool_name : undefined,
                imageDataUrl: toolPayload.imageDataUrl,
                fileAttachments: toolPayload.fileAttachments,
                isExpanded: false
              });
            }
          }

          // 处理工具消息(update事件) - 兼容旧 LangGraph 格式
          if (parsed.type === 'update' && streamSessionId && activeStreams.value[streamSessionId]) {
            const updateData = parsed.data;
            if (typeof updateData === 'string') {
              // 解析工具消息
              // 格式类似: "{'agent': {'messages': [ToolMessage(content='...', name='tool_name', ...)]}}"
              if (updateData.includes('ToolMessage')) {
                try {
                  // 提取工具消息内容
                  const contentMatch = updateData.match(/content='([^']*(?:\\'[^']*)*)'/);
                  
                  if (contentMatch) {
                    const toolContent = contentMatch[1].replace(/\\'/g, "'").replace(/\\n/g, '\n');
                    const time = formatStreamTime();
                    
                    // 如果当前有AI流式内容,先将其固化为独立消息
                    if (activeStreams.value[streamSessionId].content && activeStreams.value[streamSessionId].content.trim()) {
                      activeStreams.value[streamSessionId].messages.push({
                        content: activeStreams.value[streamSessionId].content,
                        type: 'ai',
                        time: time,
                        isExpanded: false
                      });
                      activeStreams.value[streamSessionId].content = '';
                    }
                    
                    // 添加工具消息作为新的独立消息
                    activeStreams.value[streamSessionId].messages.push({
                      content: toolContent,
                      type: 'tool',
                      time: time,
                      isExpanded: false
                    });
                  }
                } catch (e) {
                  console.warn('Failed to parse tool message:', updateData);
                }
              }
            }
          }

          // ⭐ 处理真正的流式输出 (type === 'stream') - Agent Loop 逐字流式
          if (parsed.type === 'stream' && streamSessionId && activeStreams.value[streamSessionId]) {
            const content = parsed.data;
            if (content) {
              activeStreams.value[streamSessionId].content += content;
            }
          }

          // ⭐ 流式结束事件
          if (parsed.type === 'stream_end' && streamSessionId && activeStreams.value[streamSessionId]) {
            // 流式结束，内容已通过 stream 事件累积
            // 不需要特殊处理，等待 complete 事件标记完成
          }

          // 处理AI消息(message事件) - 兼容旧格式（非流式模式）
          if (parsed.type === 'message' && streamSessionId && activeStreams.value[streamSessionId]) {
            const content = parseMessageContent(parsed.data);
            if (content) {
              activeStreams.value[streamSessionId].content += content;
            }
          }

          // ⭐ 处理 HITL 中断事件
          if (parsed.type === 'interrupt' && streamSessionId && activeStreams.value[streamSessionId]) {
            console.log('[ChatService] Interrupt event received:', parsed);
            activeStreams.value[streamSessionId].interrupt = {
              id: parsed.interrupt_id || parsed.id,
              interrupt_id: parsed.interrupt_id,
              action_requests: parsed.action_requests || [],
            };
            activeStreams.value[streamSessionId].isWaitingForApproval = true;
          }

          if (parsed.type === 'complete' && streamSessionId && activeStreams.value[streamSessionId]) {
            // ✅ 修复：标记完成，保持content不变（Vue组件会从content读取最终消息）
            // 不清空content，因为displayedMessages和watch都依赖stream.content来显示最终AI回复
            activeStreams.value[streamSessionId].isComplete = true;
            
            // ⭐ 保存任务 ID
            if (parsed.task_id) {
              activeStreams.value[streamSessionId].taskId = parsed.task_id;
            }
            
            // ⭐ 处理脚本生成信息
            if (parsed.script_generation && parsed.script_generation.available) {
              activeStreams.value[streamSessionId].scriptGeneration = {
                available: true,
                playwrightSteps: parsed.script_generation.playwright_steps || 0,
                message: parsed.script_generation.message || '可生成自动化用例'
              };
              console.log('[ChatService] Script generation available:', parsed.script_generation);
            }
          }
        } catch (e) {
          console.warn('Failed to parse SSE data:', jsonData);
        }
      }
    }
  } catch (error) {
    handleError(error, streamSessionId);
  }
}

/**
 * 获取聊天历史记录
 * @param sessionId 会话ID
 * @param projectId 项目ID
 */
export async function getChatHistory(
  sessionId: string,
  projectId: number | string
): Promise<ApiResponse<ChatHistoryResponseData>> {
  const response = await request<ChatHistoryResponseData>({
    url: `${API_BASE_URL}/history/`,
    method: 'GET',
    params: {
      session_id: sessionId,
      project_id: String(projectId) // 确保转换为string
    }
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || 'success',
      data: response.data!,
      errors: undefined
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to get chat history',
      data: {} as ChatHistoryResponseData,
      errors: { detail: [response.error || 'Unknown error'] }
    };
  }
}

/**
 * 删除聊天历史记录
 * @param sessionId 要删除历史记录的会话ID
 * @param projectId 项目ID
 */
export async function deleteChatHistory(
  sessionId: string,
  projectId: number | string
): Promise<ApiResponse<null>> {
  const response = await request<null>({
    url: `${API_BASE_URL}/history/`,
    method: 'DELETE',
    params: {
      session_id: sessionId,
      project_id: String(projectId) // 确保转换为string
    }
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || '聊天历史记录已成功删除',
      data: null,
      errors: undefined
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to delete chat history',
      data: null,
      errors: { detail: [response.error || 'Unknown error'] }
    };
  }
}

/**
 * 回滚聊天历史记录到指定消息数量
 * @param sessionId 会话ID
 * @param projectId 项目ID
 * @param keepCount 要保留的消息数量
 */
export async function rollbackChatHistory(
  sessionId: string,
  projectId: number | string,
  keepCount: number
): Promise<ApiResponse<{ deleted_count: number; kept_count: number }>> {
  const response = await request<{ deleted_count: number; kept_count: number }>({
    url: `${API_BASE_URL}/history/`,
    method: 'PATCH',
    params: {
      session_id: sessionId,
      project_id: String(projectId)
    },
    data: {
      keep_count: keepCount
    }
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || '聊天历史已回滚',
      data: response.data!,
      errors: undefined
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to rollback chat history',
      data: { deleted_count: 0, kept_count: 0 },
      errors: { detail: [response.error || 'Unknown error'] }
    };
  }
}

/**
 * 获取用户的所有会话列表
 * @param projectId 项目ID
 */
export async function getChatSessions(projectId: number): Promise<ApiResponse<ChatSessionsResponseData>> {
  const response = await request<ChatSessionsResponseData>({
    url: `${API_BASE_URL}/sessions/`,
    method: 'GET',
    params: {
      project_id: projectId
    }
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || 'success',
      data: response.data!,
      errors: undefined
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to get chat sessions',
      data: {} as ChatSessionsResponseData,
      errors: { detail: [response.error || 'Unknown error'] }
    };
  }
}

/**
 * 批量删除聊天历史记录
 * @param sessionIds 要删除的会话ID数组
 * @param projectId 项目ID
 */
export async function batchDeleteChatHistory(
  sessionIds: string[],
  projectId: number | string
): Promise<ApiResponse<{ deleted_count: number; processed_sessions: number; failed_sessions: any[] }>> {
  const response = await request<{ deleted_count: number; processed_sessions: number; failed_sessions: any[] }>({
    url: `${API_BASE_URL}/batch-delete/`,
    method: 'POST',
    data: {
      session_ids: sessionIds,
      project_id: String(projectId)
    }
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || '批量删除成功',
      data: response.data!,
      errors: undefined
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || '批量删除失败',
      data: { deleted_count: 0, processed_sessions: 0, failed_sessions: [] },
      errors: { detail: [response.error || 'Unknown error'] }
    };
  }
}

/**
 * 停止 Agent Loop 生成
 * @param sessionId 要停止的会话ID
 */
export async function stopAgentLoop(
  sessionId: string
): Promise<ApiResponse<{ success: boolean; session_id: string; message: string }>> {
  const authStore = useAuthStore();
  const token = authStore.getAccessToken;

  try {
    const response = await fetch(`${getApiBaseUrl()}${AGENT_LOOP_STOP_API_URL}/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ session_id: sessionId })
    });

    const data = await response.json();

    if (response.ok && data.status === 'success') {
      return {
        status: 'success',
        code: 200,
        message: data.message || '已停止生成',
        data: data.data,
        errors: undefined
      };
    } else {
      return {
        status: 'error',
        code: response.status,
        message: data.message || '停止失败',
        data: { success: false, session_id: sessionId, message: '' },
        errors: data.errors || { detail: ['Unknown error'] }
      };
    }
  } catch (error) {
    console.error('[ChatService] Stop agent loop error:', error);
    return {
      status: 'error',
      code: 500,
      message: error instanceof Error ? error.message : '停止请求失败',
      data: { success: false, session_id: sessionId, message: '' },
      errors: { detail: [error instanceof Error ? error.message : 'Unknown error'] }
    };
  }
}

/**
 * 恢复被 HITL 中断的 Agent Loop 执行 (SSE 流式版本)
 *
 * 后端现在返回 SSE 流式响应，与主流格式一致。
 * 这样 resume 后的工具执行结果、LLM 响应都能实时流式展示。
 *
 * @param sessionId 会话ID
 * @param interruptId 中断事件ID
 * @param decision 用户决策 ('approve' | 'reject')
 * @param projectId 项目ID
 * @param signal 可选的 AbortSignal 用于中断请求
 */
export async function resumeAgentLoop(
  sessionId: string,
  interruptId: string,
  decision: 'approve' | 'reject',
  projectId: number,
  signal?: AbortSignal,
  knowledgeBaseId?: string | null,
  useKnowledgeBase?: boolean,
  actionCount?: number
): Promise<void> {
  const authStore = useAuthStore();
  let token = authStore.getAccessToken;

  // 确保 activeStreams 存在，如果不存在则初始化
  if (!activeStreams.value[sessionId]) {
    activeStreams.value[sessionId] = {
      content: '',
      isComplete: false,
      messages: [],
      isWaitingForApproval: false,
    };
    console.log('[ChatService] Resume: Initialized activeStreams for session', sessionId);
  } else {
    // 在开始新的 resume 之前，将当前累积的 content 固化到 messages
    // 这样拒绝后的新回复会显示为独立的消息框
    if (activeStreams.value[sessionId].content?.trim()) {
      activeStreams.value[sessionId].messages.push({
        content: activeStreams.value[sessionId].content,
        type: 'ai',
        time: formatStreamTime(),
        isExpanded: false
      });
      activeStreams.value[sessionId].content = '';
    }
    // 清除中断状态，准备接收新的流
    activeStreams.value[sessionId].interrupt = undefined;
    activeStreams.value[sessionId].isWaitingForApproval = false;
    activeStreams.value[sessionId].isComplete = false;
  }

  // 错误处理函数
  const handleError = (error: any) => {
    const isAbortError = error?.name === 'AbortError' ||
                         error?.message?.includes('aborted') ||
                         error?.message?.includes('The user aborted');

    if (isAbortError) {
      console.log('[ChatService] Resume stream aborted by user');
      if (activeStreams.value[sessionId]) {
        activeStreams.value[sessionId].isComplete = true;
      }
      return;
    }

    console.error('[ChatService] Resume stream error:', error);
    if (activeStreams.value[sessionId]) {
      activeStreams.value[sessionId].error = error.message || '恢复执行失败';
      activeStreams.value[sessionId].isComplete = true;
    }
  };

  if (!token) {
    handleError(new Error('未登录或登录已过期'));
    return;
  }

  try {
    // 构建 resume 数据（LangChain Command 格式）
    const resumeData: Record<string, any> = {
      session_id: sessionId,
      project_id: projectId,
      resume: {
        [interruptId]: {
          decisions: [{ type: decision }],
          action_count: actionCount || 1  // 传递工具调用数量
        }
      }
    };

    // 添加知识库参数
    if (knowledgeBaseId && useKnowledgeBase) {
      resumeData.knowledge_base_id = knowledgeBaseId;
      resumeData.use_knowledge_base = useKnowledgeBase;
    }

    let response = await fetch(`${getApiBaseUrl()}${AGENT_LOOP_API_URL}/resume/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(resumeData),
      signal
    });

    // Token 过期重试
    if (response.status === 401) {
      const newToken = await refreshAccessToken();
      if (newToken) {
        token = newToken;
        response = await fetch(`${getApiBaseUrl()}${AGENT_LOOP_API_URL}/resume/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify(resumeData),
          signal
        });
      } else {
        handleError(new Error('登录已过期，请重新登录'));
        return;
      }
    }

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) {
      throw new Error('Failed to get response reader');
    }

    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        // 流结束，处理剩余数据
        if (buffer.trim()) {
          const remainingLines = buffer.split('\n');
          for (const line of remainingLines) {
            if (line.trim() === '' || !line.startsWith('data: ')) continue;
            const jsonData = line.slice(6);
            if (jsonData === '[DONE]') continue;

            try {
              const parsed = JSON.parse(jsonData);
              if (parsed.type === 'complete' && activeStreams.value[sessionId]) {
                activeStreams.value[sessionId].isComplete = true;
              }
            } catch {
              // 忽略解析异常
            }
          }
        }

        if (activeStreams.value[sessionId] && !activeStreams.value[sessionId].isComplete) {
          console.warn('[ChatService] Resume stream ended without complete event');
          activeStreams.value[sessionId].isComplete = true;
        }
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.trim() === '' || !line.startsWith('data: ')) continue;

        const jsonData = line.slice(6);
        if (jsonData === '[DONE]') {
          if (activeStreams.value[sessionId]) {
            activeStreams.value[sessionId].isComplete = true;
          }
          continue;
        }

        try {
          const parsed = JSON.parse(jsonData);

          if (parsed.type === 'error') {
            handleError(new Error(parsed.message || '恢复执行失败'));
            return;
          }

          // resume_start 事件 - resume 开始
          if (parsed.type === 'resume_start' && activeStreams.value[sessionId]) {
            console.log('[ChatService] Resume started:', parsed.decision);
          }

          // 处理上下文 Token 更新
          if (parsed.type === 'context_update' && activeStreams.value[sessionId]) {
            const tokenCount = parsed.context_token_count ?? 0;
            const limit = parsed.context_limit ?? 128000;
            latestContextUsage.value[sessionId] = { tokenCount, limit };
            activeStreams.value[sessionId].contextTokenCount = tokenCount;
            activeStreams.value[sessionId].contextLimit = limit;
          }

          // 处理步骤开始事件
          if (parsed.type === 'step_start' && activeStreams.value[sessionId]) {
            const stepNumber = normalizeNumericField(parsed.step);
            const maxSteps = normalizeNumericField(parsed.max_steps);
            if (maxSteps !== undefined) {
              activeStreams.value[sessionId].maxSteps = maxSteps;
            }
            if (stepNumber !== undefined) {
              activeStreams.value[sessionId].currentStep = stepNumber;
            }
            activeStreams.value[sessionId].messages.push({
              content: '',
              type: 'agent_step',
              time: formatStreamTime(),
              stepNumber: stepNumber,
              maxSteps: maxSteps,
              stepStatus: 'start',
              isThinkingProcess: true
            });
          }

          // 处理步骤完成事件
          if (parsed.type === 'step_complete' && activeStreams.value[sessionId]) {
            const stepNumber = normalizeNumericField(parsed.step);
            if (stepNumber !== undefined) {
              activeStreams.value[sessionId].currentStep = stepNumber;
            }
          }

          // 处理工具结果事件
          if (parsed.type === 'tool_result' && activeStreams.value[sessionId]) {
            // 优先使用 tool_output（完整内容），fallback 到 summary（截断摘要）
            const toolOutput = parsed.tool_output || parsed.content || parsed.summary;
            const toolPayload = parseToolResultDisplayPayload(toolOutput);
            if (toolPayload.content || toolPayload.imageDataUrl) {
              const time = formatStreamTime();
              // 先固化当前 AI 内容
              if (activeStreams.value[sessionId].content?.trim()) {
                activeStreams.value[sessionId].messages.push({
                  content: activeStreams.value[sessionId].content,
                  type: 'ai',
                  time: time,
                  isExpanded: false
                });
                activeStreams.value[sessionId].content = '';
              }
              activeStreams.value[sessionId].messages.push({
                content: toolPayload.content || '[工具返回了图片]',
                type: 'tool',
                time: time,
                toolName: typeof parsed.tool_name === 'string' ? parsed.tool_name : undefined,
                imageDataUrl: toolPayload.imageDataUrl,
                fileAttachments: toolPayload.fileAttachments,
                isExpanded: false
              });
            }
          }

          // 处理 LLM 流式输出
          if (parsed.type === 'stream' && activeStreams.value[sessionId]) {
            const content = parsed.data;
            if (content) {
              activeStreams.value[sessionId].content += content;
            }
          }

          // 处理新的 HITL 中断（resume 后可能又触发新中断）
          if (parsed.type === 'interrupt' && activeStreams.value[sessionId]) {
            console.log('[ChatService] New interrupt after resume:', parsed);
            activeStreams.value[sessionId].interrupt = {
              id: parsed.interrupt_id || parsed.id,
              interrupt_id: parsed.interrupt_id,
              action_requests: parsed.action_requests || []
            };
            activeStreams.value[sessionId].isWaitingForApproval = true;
          }

          // 处理完成事件
          if (parsed.type === 'complete' && activeStreams.value[sessionId]) {
            activeStreams.value[sessionId].isComplete = true;
          }
        } catch (e) {
          console.warn('[ChatService] Failed to parse resume SSE data:', jsonData);
        }
      }
    }
  } catch (error) {
    handleError(error);
  }
}

/**
 * 恢复被 HITL 中断的 LangGraph Chat 执行（SSE 流式响应）
 * @param sessionId 会话ID
 * @param decision 用户决策 ('approve' | 'reject')
 * @param projectId 项目ID
 * @param onMessage 消息回调
 * @param onComplete 完成回调
 * @param onError 错误回调
 */
export async function resumeChatStream(
  sessionId: string,
  decision: 'approve' | 'reject',
  projectId: number,
  onMessage?: (content: string) => void,
  onComplete?: () => void,
  onError?: (error: string) => void,
  onInterrupt?: (interrupt: { id: string; action_requests: Array<{ name: string; args: Record<string, unknown>; description?: string }> }) => void
): Promise<void> {
  const authStore = useAuthStore();
  const token = authStore.getAccessToken;

  const resumeData = {
    session_id: sessionId,
    project_id: projectId,
    decision: decision
  };

  try {
    const response = await fetch(`${getApiBaseUrl()}/lg/chat/resume/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(resumeData)
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      onError?.(errorData.error || `Resume failed: ${response.status}`);
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      onError?.('No response body');
      return;
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const dataStr = line.slice(6).trim();
          if (dataStr === '[DONE]') {
            onComplete?.();
            return;
          }

          try {
            const parsed = JSON.parse(dataStr);

            if (parsed.type === 'message' && parsed.data) {
              onMessage?.(parsed.data);
            } else if (parsed.type === 'interrupt') {
              onInterrupt?.({
                id: parsed.interrupt_id,
                action_requests: parsed.action_requests || []
              });
            } else if (parsed.type === 'error') {
              onError?.(parsed.message || 'Unknown error');
            } else if (parsed.type === 'complete') {
              onComplete?.();
            }
          } catch {
            // 忽略解析错误
          }
        }
      }
    }

    // 清除中断状态
    clearInterruptState(sessionId);
    onComplete?.();
  } catch (error) {
    console.error('[ChatService] Resume chat stream error:', error);
    onError?.(error instanceof Error ? error.message : 'Resume failed');
  }
}

/**
 * 清除会话的中断状态
 * @param sessionId 会话ID
 */
export function clearInterruptState(sessionId: string): void {
  if (activeStreams.value[sessionId]) {
    activeStreams.value[sessionId].interrupt = undefined;
    activeStreams.value[sessionId].isWaitingForApproval = false;
  }
}
