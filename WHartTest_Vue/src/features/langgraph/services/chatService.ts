import { request } from '@/utils/request';
import { useAuthStore } from '@/store/authStore';
import type { ApiResponse } from '@/features/langgraph/types/api';
import type {
  ChatRequest,
  ChatResponseData,
  ChatHistoryResponseData,
  ChatSessionsResponseData
} from '@/features/langgraph/types/chat';

const API_BASE_URL = '/lg/chat';

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
 * 发送对话消息
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
      errors: null
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to send chat message',
      data: null,
      errors: { detail: response.error }
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
  onMessage: (chunk: string) => void,
  onComplete: (response: ApiResponse<ChatResponseData>) => void,
  onError: (error: any) => void
): Promise<void> {
  const authStore = useAuthStore();
  let token = authStore.getAccessToken;

  // 如果没有token，直接返回错误
  if (!token) {
    onError(new Error('未登录或登录已过期'));
    return;
  }

  try {
    let response = await fetch(`${getApiBaseUrl()}${API_BASE_URL}/stream/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify(data),
    });

    // 如果是401错误，尝试刷新token
    if (response.status === 401) {
      const newToken = await refreshAccessToken();
      if (newToken) {
        // 使用新token重试请求
        response = await fetch(`${getApiBaseUrl()}${API_BASE_URL}/stream/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream',
            'Authorization': `Bearer ${newToken}`,
          },
          body: JSON.stringify(data),
        });
      } else {
        onError(new Error('登录已过期，请重新登录'));
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
    let finalResponse: ApiResponse<ChatResponseData> | null = null;

    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.trim() === '') continue;

        if (line.startsWith('data: ')) {
          const data = line.slice(6);

          if (data === '[DONE]') {
            if (finalResponse) {
              onComplete(finalResponse);
            }
            return;
          }

          try {
            const parsed = JSON.parse(data);

            // 处理错误消息
            if (parsed.type === 'error') {
              onError(new Error(parsed.message || '流式请求失败'));
              return;
            }

            // 处理开始消息，保存session信息
            if (parsed.type === 'start') {
              finalResponse = {
                status: 'success',
                code: 200,
                message: 'Message processed successfully.',
                data: {
                  user_message: '',
                  llm_response: '',
                  conversation_flow: [],
                  active_llm: 'gpt-4o-mini',
                  thread_id: parsed.thread_id,
                  session_id: parsed.session_id,
                  project_id: parsed.project_id,
                  project_name: ''
                },
                errors: undefined
              };
            }

            // 处理消息内容
            if (parsed.type === 'message') {
              // 解析消息数据，提取实际的文本内容
              const messageData = parsed.data;
              console.log('🔍 [流式数据] 接收到消息:', { type: parsed.type, data: messageData });
              if (typeof messageData === 'string') {
                // 检查是否是工具消息返回结果
                if (messageData.includes('ToolMessage(')) {
                  // 这是工具消息，提取工具消息内容
                  const toolMatch = messageData.match(/ToolMessage\(content='([^']*)'[^)]*\)/);
                  if (toolMatch && toolMatch[1]) {
                    // 解析工具消息内容，可能是JSON格式
                    let toolContent = toolMatch[1];
                    try {
                      // 尝试解析转义的JSON
                      toolContent = toolContent.replace(/\\n/g, '\n').replace(/\\"/g, '"');
                      const jsonData = JSON.parse(toolContent);
                      toolContent = JSON.stringify(jsonData, null, 2);
                    } catch (e) {
                      // 如果不是JSON，保持原样
                    }

                    // 发送工具消息，使用特殊标记
                    onMessage(`__TOOL_MESSAGE__${toolContent}`);
                  }
                } else if (messageData.includes('tool_calls') && messageData.includes('AIMessageChunk')) {
                  // 这是工具调用开始，提取工具名称
                  const toolCallMatch = messageData.match(/'name': '([^']*)'[^}]*'args': \{([^}]*)\}/);
                  if (toolCallMatch && toolCallMatch[1]) {
                    const toolName = toolCallMatch[1];
                    const toolArgs = toolCallMatch[2] || '';

                    // 发送工具调用信息
                    onMessage(`__TOOL_CALL__正在调用工具: ${toolName}${toolArgs ? ` (参数: ${toolArgs})` : ''}`);
                  }
                } else {
                  // 这是AI消息，提取文本内容
                  let content = '';

                  // 匹配 AIMessageChunk(content='...', ...)
                  let match = messageData.match(/AIMessageChunk\(content='([^']*)'[^)]*\)/);
                  if (match && match[1] !== undefined) {
                    content = match[1];
                  } else {
                    // 匹配 AIMessageChunk(content="...", ...)
                    match = messageData.match(/AIMessageChunk\(content="([^"]*)"[^)]*\)/);
                    if (match && match[1] !== undefined) {
                      content = match[1];
                    } else {
                      // 匹配没有引号的情况
                      match = messageData.match(/AIMessageChunk\(content=([^,)]*)[,)]/);
                      if (match && match[1] !== undefined) {
                        content = match[1].trim();
                      }
                    }
                  }

                  // 发送内容，包括空字符串（用于流式输出）
                  console.log('📤 [流式输出] 发送内容块:', { content, length: content.length });
                  onMessage(content);
                }
              }
            }

            // 处理完成消息
            if (parsed.type === 'complete') {
              // 流式完成，获取完整的conversation_flow
              if (finalResponse && finalResponse.data.session_id && finalResponse.data.project_id) {
                try {
                  // 获取完整的对话历史
                  const historyResponse = await getChatHistory(
                    finalResponse.data.session_id,
                    finalResponse.data.project_id
                  );
                  if (historyResponse.status === 'success' && historyResponse.data.history) {
                    finalResponse.data.conversation_flow = historyResponse.data.history;
                  }
                } catch (error) {
                  console.warn('Failed to get conversation history:', error);
                }
              }

              if (finalResponse) {
                onComplete(finalResponse);
              }
              return;
            }
          } catch (e) {
            console.warn('Failed to parse SSE data:', data);
          }
        }
      }
    }

    if (finalResponse) {
      onComplete(finalResponse);
    }
  } catch (error) {
    onError(error);
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
      errors: null
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to get chat history',
      data: null,
      errors: { detail: response.error }
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
      errors: null
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to delete chat history',
      data: null,
      errors: { detail: response.error }
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
      errors: null
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to get chat sessions',
      data: null,
      errors: { detail: response.error }
    };
  }
}