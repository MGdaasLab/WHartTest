<template>
  <div class="chat-layout">
    <!-- 左侧历史对话列表 -->
    <ChatSidebar
      :sessions="chatSessions"
      :current-session-id="sessionId"
      :is-loading="isLoading"
      @create-new-chat="createNewChat"
      @switch-session="switchSession"
      @delete-session="deleteSession"
    />

    <!-- 右侧聊天区域 -->
    <div class="chat-container">
      <ChatHeader
        ref="chatHeaderRef"
        :session-id="sessionId"
        :is-stream-mode="isStreamMode"
        :has-messages="messages.length > 0"
        :project-id="projectStore.currentProjectId"
        :use-knowledge-base="useKnowledgeBase"
        :selected-knowledge-base-id="selectedKnowledgeBaseId"
        :similarity-threshold="similarityThreshold"
        :top-k="topK"
        :selected-prompt-id="selectedPromptId"
        @update:is-stream-mode="isStreamMode = $event"
        @clear-chat="clearChat"
        @show-system-prompt="showSystemPromptModal"
        @update:use-knowledge-base="useKnowledgeBase = $event"
        @update:selected-knowledge-base-id="selectedKnowledgeBaseId = $event"
        @update:similarity-threshold="similarityThreshold = $event"
        @update:top-k="topK = $event"
        @update:selected-prompt-id="selectedPromptId = $event"
      />

      <ChatMessages
        :messages="displayedMessages"
        :is-loading="isLoading && messages.length === 0"
        @toggle-expand="toggleExpand"
      />

      <ChatInput
        :is-loading="isLoading"
        :has-prompts="hasPrompts"
        @send-message="handleSendMessage"
      />
    </div>

    <!-- 系统提示词管理弹窗 -->
    <SystemPromptModal
      :visible="isSystemPromptModalVisible"
      :current-llm-config="currentLlmConfig"
      :loading="isSystemPromptLoading"
      @update-system-prompt="handleUpdateSystemPrompt"
      @cancel="closeSystemPromptModal"
      @prompts-updated="handlePromptsUpdated"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onActivated, watch, onUnmounted, computed } from 'vue';
import { Message, Modal } from '@arco-design/web-vue';
import {
  sendChatMessage,
  sendChatMessageStream,
  getChatHistory,
  deleteChatHistory,
  getChatSessions,
  activeStreams,
  clearStreamState
} from '@/features/langgraph/services/chatService';
import { listLlmConfigs, partialUpdateLlmConfig } from '@/features/langgraph/services/llmConfigService';
import { getUserPrompts } from '@/features/prompts/services/promptService';
import type { ChatRequest } from '@/features/langgraph/types/chat';
import type { LlmConfig } from '@/features/langgraph/types/llmConfig';
import { useProjectStore } from '@/store/projectStore';
import { marked } from 'marked';

// 导入子组件
import ChatSidebar from '../components/ChatSidebar.vue';
import ChatHeader from '../components/ChatHeader.vue';
import ChatMessages from '../components/ChatMessages.vue';
import ChatInput from '../components/ChatInput.vue';
import SystemPromptModal from '../components/SystemPromptModal.vue';

// 配置marked
marked.setOptions({
  breaks: true,
  gfm: true
});

interface ChatMessage {
  content: string;
  isUser: boolean;
  time: string;
  isLoading?: boolean;
  messageType?: 'human' | 'ai' | 'tool' | 'system'; // 🆕 消息类型，用于区分头像，添加 system 类型
  isExpanded?: boolean; // 工具消息是否展开
  isStreaming?: boolean; // 是否正在流式输出
}

interface ChatSession {
  id: string;
  title: string;
  lastTime: Date;
  messageCount: number;
}

const messages = ref<ChatMessage[]>([]);
const isLoading = ref(false);
const sessionId = ref<string>('');
const chatSessions = ref<ChatSession[]>([]);
const isStreamMode = ref(true); // 流式模式开关，默认开启

// 知识库相关
const useKnowledgeBase = ref(false); // 是否启用知识库功能
const selectedKnowledgeBaseId = ref<string | null>(null); // 选中的知识库ID
const similarityThreshold = ref(0.3); // 相似度阈值
const topK = ref(5); // 检索结果数量

// 提示词相关
const selectedPromptId = ref<number | null>(null); // 用户选择的提示词ID
const hasPrompts = ref(false); // 是否有可用的提示词


// 系统提示词相关
const isSystemPromptModalVisible = ref(false);
const isSystemPromptLoading = ref(false);
const currentLlmConfig = ref<LlmConfig | null>(null);

// 项目store
const projectStore = useProjectStore();

// 组件引用
const chatHeaderRef = ref<{ refreshPrompts: () => Promise<void> } | null>(null);

// 终止控制器
let abortController = new AbortController();

// 在本地存储中保存会话ID
const saveSessionId = (id: string) => {
  localStorage.setItem('langgraph_session_id', id);
  sessionId.value = id;
};

// 从本地存储中获取会话ID
const getSessionIdFromStorage = (): string | null => {
  return localStorage.getItem('langgraph_session_id');
};

// 保存知识库设置到本地存储
const saveKnowledgeBaseSettings = () => {
  const settings = {
    useKnowledgeBase: useKnowledgeBase.value,
    selectedKnowledgeBaseId: selectedKnowledgeBaseId.value,
    similarityThreshold: similarityThreshold.value,
    topK: topK.value
  };
  localStorage.setItem('langgraph_knowledge_settings', JSON.stringify(settings));
};

// 从本地存储加载知识库设置
const loadKnowledgeBaseSettings = () => {
  const settingsJson = localStorage.getItem('langgraph_knowledge_settings');
  if (settingsJson) {
    try {
      const settings = JSON.parse(settingsJson);
      useKnowledgeBase.value = settings.useKnowledgeBase ?? false;
      selectedKnowledgeBaseId.value = settings.selectedKnowledgeBaseId ?? null;
      similarityThreshold.value = settings.similarityThreshold ?? 0.3;
      topK.value = settings.topK ?? 5;
      console.log('✅ 知识库设置加载完成:', settings);
    } catch (error) {
      console.error('❌ 加载知识库设置失败:', error);
    }
  }
};

// 从本地存储加载会话列表
const loadSessionsFromStorage = () => {
  const sessionsJson = localStorage.getItem('langgraph_sessions');
  if (sessionsJson) {
    try {
      const parsedSessions = JSON.parse(sessionsJson);
      // 确保日期对象正确恢复
      chatSessions.value = parsedSessions.map((session: any) => {
        let lastTime = new Date();
        try {
          // 尝试解析存储的时间
          lastTime = new Date(session.lastTime);
          // 检查日期是否有效
          if (isNaN(lastTime.getTime())) {
            lastTime = new Date();
          }
        } catch (error) {
          console.error('解析会话时间失败:', error);
          lastTime = new Date();
        }

        return {
          ...session,
          lastTime
        };
      });
    } catch (e) {
      console.error('解析会话列表失败:', e);
      chatSessions.value = [];
    }
  }
};

// 保存会话列表到本地存储
const saveSessionsToStorage = () => {
  localStorage.setItem('langgraph_sessions', JSON.stringify(chatSessions.value));
};

// 从服务器加载会话列表
const loadSessionsFromServer = async () => {
  // 检查是否有当前项目ID
  if (!projectStore.currentProjectId) {
    console.warn('没有选择项目，无法加载会话列表');
    return;
  }

  try {
    isLoading.value = true;
    const response = await getChatSessions(projectStore.currentProjectId);

    if (response.status === 'success') {
      // 获取到会话ID列表后，需要为每个会话获取历史记录以显示标题
      const sessionsData = response.data.sessions;

      // 先清空现有会话列表
      chatSessions.value = [];

      // 如果没有会话，直接返回
      if (sessionsData.length === 0) {
        isLoading.value = false;
        return;
      }

      // 为了避免一次发送太多请求，限制并发数量
      const BATCH_SIZE = 3; // 一次处理3个会话

      // 分批处理会话
      for (let i = 0; i < sessionsData.length; i += BATCH_SIZE) {
        const batch = sessionsData.slice(i, i + BATCH_SIZE);
        await Promise.all(batch.map(async (sessionId) => {
          try {
            // 为每个会话获取历史记录
            const historyResponse = await getChatHistory(sessionId, projectStore.currentProjectId!);
            if (historyResponse.status === 'success') {
              const history = historyResponse.data.history;
              // 使用第一条人类消息作为标题
              const firstHumanMessage = history.find(msg => msg.type === 'human')?.content || '';
              const title = firstHumanMessage
                ? (firstHumanMessage.length > 20 ? `${firstHumanMessage.substring(0, 20)}...` : firstHumanMessage)
                : '未命名对话';

              // 获取最后一条消息的时间戳作为会话时间
              const lastMessage = history[history.length - 1];
              let lastTime = new Date();
              if (lastMessage?.timestamp) {
                try {
                  // 处理时间戳格式，确保正确解析
                  const timestamp = lastMessage.timestamp;
                  // 如果时间戳格式是 "YYYY-MM-DD HH:MM:SS"，需要确保正确解析
                  lastTime = new Date(timestamp.replace(' ', 'T'));
                  // 检查日期是否有效
                  if (isNaN(lastTime.getTime())) {
                    lastTime = new Date();
                  }
                } catch (error) {
                  console.error('解析会话时间戳失败:', error);
                  lastTime = new Date();
                }
              }

              // 添加到会话列表
              chatSessions.value.push({
                id: sessionId,
                title,
                lastTime,
                messageCount: history.length
              });
            }
          } catch (error) {
            console.error(`获取会话 ${sessionId} 的历史记录失败:`, error);
          }
        }));
      }

      // 按时间倒序排序会话列表
      chatSessions.value.sort((a, b) => b.lastTime.getTime() - a.lastTime.getTime());

      // 保存到本地存储作为备份
      saveSessionsToStorage();
    } else {
      Message.error('获取会话列表失败');
      // 如果服务器获取失败，尝试从本地存储加载
      loadSessionsFromStorage();
    }
  } catch (error) {
    console.error('获取会话列表失败:', error);
    Message.error('获取会话列表失败，将使用本地缓存');
    // 如果服务器请求出错，尝试从本地存储加载
    loadSessionsFromStorage();
  } finally {
    isLoading.value = false;
  }
};

// 加载聊天历史记录
const loadChatHistory = async () => {
  const storedSessionId = getSessionIdFromStorage();
  if (!storedSessionId || !projectStore.currentProjectId) return;

  try {
    isLoading.value = true;
    const response = await getChatHistory(storedSessionId, projectStore.currentProjectId);

    if (response.status === 'success') {
      sessionId.value = response.data.session_id;

      // 清空当前消息列表
      messages.value = [];

      // 将历史记录转换为消息格式并添加到列表
      response.data.history.forEach(historyItem => {
        // 🆕 跳过系统消息，不在消息列表中显示
        if (historyItem.type === 'system') {
          return;
        }

        const message: ChatMessage = {
          content: historyItem.content,
          isUser: historyItem.type === 'human',
          time: formatHistoryTime(historyItem.timestamp),
          messageType: historyItem.type // 添加消息类型用于区分头像
        };

        // 如果是工具消息，设置默认折叠状态
        if (historyItem.type === 'tool') {
          message.isExpanded = false;
        }

        messages.value.push(message);
      });

      // 更新会话信息
      // 获取第一条human类型的消息作为标题
      const firstHumanMessage = response.data.history.find(msg => msg.type === 'human')?.content;
      updateSessionInList(response.data.session_id, firstHumanMessage);
    } else {
      // 如果获取历史失败，可能是会话过期，清除存储的会话ID
      localStorage.removeItem('langgraph_session_id');
      sessionId.value = '';
    }
  } catch (error) {
    console.error('加载聊天历史失败:', error);
    Message.error('加载聊天历史失败，将开始新的对话');
    localStorage.removeItem('langgraph_session_id');
    sessionId.value = '';
  } finally {
    isLoading.value = false;
  }
};

// 获取当前时间
const getCurrentTime = () => {
  const now = new Date();
  return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
};

// 格式化历史消息时间
const formatHistoryTime = (timestamp: string) => {
  if (!timestamp) return getCurrentTime();

  try {
    // 处理时间戳格式，确保正确解析
    // 如果时间戳格式是 "YYYY-MM-DD HH:MM:SS"，转换为 ISO 格式
    const isoTimestamp = timestamp.includes('T') ? timestamp : timestamp.replace(' ', 'T');
    const date = new Date(isoTimestamp);

    // 检查日期是否有效
    if (isNaN(date.getTime())) {
      return getCurrentTime();
    }

    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const messageDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());

    // 如果是今天的消息，只显示时间
    if (messageDate.getTime() === today.getTime()) {
      return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
    }

    // 如果是昨天的消息
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    if (messageDate.getTime() === yesterday.getTime()) {
      return `昨天 ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
    }

    // 如果是更早的消息，显示月日和时间
    return `${date.getMonth() + 1}月${date.getDate()}日 ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
  } catch (error) {
    console.error('格式化时间失败:', error);
    return getCurrentTime();
  }
};

// 切换工具消息的展开/收起状态
const toggleExpand = (message: ChatMessage) => {
  message.isExpanded = !message.isExpanded;
};

// 添加或更新会话到列表
const updateSessionInList = (id: string, firstMessage?: string, updateTime: boolean = true) => {
  const existingIndex = chatSessions.value.findIndex(s => s.id === id);
  const title = firstMessage ? (firstMessage.length > 20 ? `${firstMessage.substring(0, 20)}...` : firstMessage) : '新对话';

  if (existingIndex >= 0) {
    // 更新现有会话
    if (updateTime) {
      chatSessions.value[existingIndex].lastTime = new Date();
    }
    if (firstMessage && !chatSessions.value[existingIndex].title) {
      chatSessions.value[existingIndex].title = title;
    }
    if (chatSessions.value[existingIndex].messageCount !== undefined && updateTime) {
      chatSessions.value[existingIndex].messageCount += 1;
    }
    
    // 🆕 更新时间后，重新按时间倒序排序会话列表
    if (updateTime) {
      chatSessions.value.sort((a, b) => b.lastTime.getTime() - a.lastTime.getTime());
    }
  } else {
    // 添加新会话
    chatSessions.value.unshift({
      id,
      title,
      lastTime: new Date(),
      messageCount: messages.value.length || 1
    });
  }

  // 保存到本地存储
  saveSessionsToStorage();
};

// 切换到指定会话
const switchSession = async (id: string) => {
  if (id === sessionId.value) return;

  // 终止正在进行的流式请求
  // abortController.abort(); // 🔴 不再需要终止请求

  sessionId.value = id;
  saveSessionId(id);
  messages.value = [];

  // 加载选定会话的历史记录
  if (!projectStore.currentProjectId) {
    Message.error('没有选择项目，无法加载会话历史');
    return;
  }

  try {
    isLoading.value = true;
    const response = await getChatHistory(id, projectStore.currentProjectId);

    if (response.status === 'success') {
      response.data.history.forEach(historyItem => {
        // 🆕 跳过系统消息，不在消息列表中显示
        if (historyItem.type === 'system') {
          return;
        }

        const message: ChatMessage = {
          content: historyItem.content,
          isUser: historyItem.type === 'human',
          time: formatHistoryTime(historyItem.timestamp),
          messageType: historyItem.type // 添加消息类型用于区分头像
        };

        // 如果是工具消息，设置默认折叠状态
        if (historyItem.type === 'tool') {
          message.isExpanded = false;
        }

        messages.value.push(message);
      });

      // 更新会话信息（不更新时间，因为这是加载历史记录）
      updateSessionInList(id, undefined, false);
    } else {
      Message.error('加载会话历史失败');
    }
  } catch (error) {
    console.error('加载会话历史失败:', error);
    Message.error('加载会话历史失败');
  } finally {
    isLoading.value = false;
  }
};

// 创建新对话
const createNewChat = () => {
  // 终止正在进行的流式请求
  // abortController.abort(); // 🔴 不再需要终止请求

  // 清除当前会话ID和消息
  sessionId.value = '';
  localStorage.removeItem('langgraph_session_id');
  messages.value = [];
};

// 删除指定会话
const deleteSession = async (id: string) => {
  Modal.confirm({
    title: '确认删除',
    content: '确定要删除此对话吗？此操作不可恢复。',
    okText: '确认删除',
    cancelText: '取消',
    okButtonProps: {
      status: 'danger',
    },
    async onOk() {
      try {
        if (!projectStore.currentProjectId) {
          Message.error('没有选择项目，无法删除会话');
          return;
        }

        isLoading.value = true;
        const response = await deleteChatHistory(id, projectStore.currentProjectId);

        if (response.status === 'success') {
          // 从列表中移除
          chatSessions.value = chatSessions.value.filter(s => s.id !== id);
          saveSessionsToStorage();

          // 如果删除的是当前会话，清除当前状态
          if (id === sessionId.value) {
            sessionId.value = '';
            localStorage.removeItem('langgraph_session_id');
            messages.value = [];
          }

          // 重新加载会话列表
          await loadSessionsFromServer();

          Message.success('对话已删除');
        } else {
          Message.error('删除对话失败');
        }
      } catch (error) {
        console.error('删除对话失败:', error);
        Message.error('删除对话失败，请稍后重试');
      } finally {
        isLoading.value = false;
      }
    },
  });
};

// 清除聊天历史
const clearChat = async () => {
  if (messages.value.length === 0) return;

  // 显示确认对话框
  Modal.confirm({
    title: '确认删除',
    content: '确定要删除此对话的所有历史记录吗？此操作不可恢复。',
    okText: '确认删除',
    cancelText: '取消',
    okButtonProps: {
      status: 'danger',
    },
    async onOk() {
      try {
        // 如果有会话ID，调用API删除服务器端历史记录
        if (sessionId.value && projectStore.currentProjectId) {
          isLoading.value = true;
          const response = await deleteChatHistory(sessionId.value, projectStore.currentProjectId);

          if (response.status === 'success') {
            // 从会话列表中移除
            chatSessions.value = chatSessions.value.filter(s => s.id !== sessionId.value);
            saveSessionsToStorage();

            Message.success('对话历史已从服务器删除');
          } else {
            // 即使服务器删除失败，我们仍然会清除本地状态
            Message.warning('服务器删除可能未完成，但本地对话已清除');
          }
        }

        // 无论服务器操作结果如何，都清除本地状态
        messages.value = [];
        localStorage.removeItem('langgraph_session_id');
        sessionId.value = '';
      } catch (error) {
        console.error('删除聊天历史失败:', error);
        Message.error('删除聊天历史失败，请稍后重试');
      } finally {
        isLoading.value = false;
      }
    },
  });
};

// 发送消息
const handleSendMessage = async (message: string) => {
  if (!message.trim()) {
    Message.warning('消息内容不能为空！');
    return;
  }

  if (!projectStore.currentProjectId) {
    Message.error('请先选择一个项目');
    return;
  }

  // 添加用户消息
  messages.value.push({
    content: message,
    isUser: true,
    time: getCurrentTime(),
    messageType: 'human'
  });

  isLoading.value = true;

  const requestData: ChatRequest = {
    message: message,
    session_id: sessionId.value || undefined,
    project_id: String(projectStore.currentProjectId), // 转换为string类型
  };

  // 添加提示词参数
  if (selectedPromptId.value) {
    requestData.prompt_id = selectedPromptId.value;
  }

  // 添加知识库参数
  if (useKnowledgeBase.value && selectedKnowledgeBaseId.value) {
    requestData.knowledge_base_id = selectedKnowledgeBaseId.value;
    requestData.use_knowledge_base = true;
    requestData.similarity_threshold = similarityThreshold.value;
    requestData.top_k = topK.value;
  } else if (useKnowledgeBase.value && !selectedKnowledgeBaseId.value) {
    // 如果开启了知识库但没有选择知识库，提示用户
    Message.warning('请先选择一个知识库');
    isLoading.value = false;
    return;
  }

  if (isStreamMode.value) {
    // 流式模式
    await handleStreamMessage(requestData, message);
  } else {
    // 非流式模式
    await handleNormalMessage(requestData, message);
  }
};

// 计算用于显示的最终消息列表
const displayedMessages = computed(() => {
  const combined = [...messages.value];
  // 从共享状态中获取当前会话的流
  const stream = sessionId.value ? activeStreams.value[sessionId.value] : null;

  // 如果当前会话有正在进行的流，则添加一个临时的流式消息用于显示
  if (stream && !stream.isComplete) {
    // 如果有错误，显示错误消息
    if (stream.error) {
      combined.push({
        content: stream.error,
        isUser: false,
        time: getCurrentTime(),
        messageType: 'ai',
        isStreaming: false,
      });
    }
    // 如果流式内容为空或只有空白字符，显示加载中状态
    else if (!stream.content || stream.content.trim() === '') {
      combined.push({
        content: '',
        isUser: false,
        time: getCurrentTime(),
        messageType: 'ai',
        isLoading: true,
      });
    }
    // 有实际内容时，显示流式内容
    else {
      combined.push({
        content: stream.content,
        isUser: false,
        time: getCurrentTime(),
        messageType: 'ai',
        isStreaming: true,
      });
    }
  }
  return combined;
});

// 处理流式消息
const handleStreamMessage = async (requestData: ChatRequest) => {
  abortController = new AbortController();
  const isNewSession = !sessionId.value;

  isLoading.value = true;

  // onStart 回调，在收到 session_id 后立即处理
  const handleStart = async (newSessionId: string) => {
    if (isNewSession) {
      sessionId.value = newSessionId;
      saveSessionId(newSessionId);
      // 创建新会话后，立即刷新左侧列表
      await loadSessionsFromServer();
    }
  };

  await sendChatMessageStream(
    requestData,
    handleStart,
    abortController.signal
  );

  // sendChatMessageStream 现在是异步的，但我们不在这里等待它完成
  // 使用 watch 监视 isComplete 状态
};

// 处理非流式消息
const handleNormalMessage = async (requestData: ChatRequest, originalMessage: string) => {
  const isNewSession = !sessionId.value; // 检查是否是新会话
  // 添加loading占位消息
  const loadingMessageIndex = messages.value.length;
  messages.value.push({
    content: '',
    isUser: false,
    time: getCurrentTime(),
    messageType: 'ai',
    isLoading: true
  });

  try {
    const response = await sendChatMessage(requestData);

    // 移除loading消息
    messages.value.splice(loadingMessageIndex, 1);

    if (response.status === 'success') {
      // 保存会话ID
      if (response.data.session_id) {
        saveSessionId(response.data.session_id);
        // 如果是新会话，则从服务器刷新列表，否则只在本地更新
        if (isNewSession) {
          await loadSessionsFromServer();
        } else {
          updateSessionInList(response.data.session_id, undefined);
        }
      }

      // 处理conversation_flow中的新消息
      if (response.data.conversation_flow && response.data.conversation_flow.length > 0) {
        handleConversationFlow(response.data.conversation_flow, originalMessage);
      } else {
        // 如果没有conversation_flow，使用原来的方式添加AI回复
        messages.value.push({
          content: response.data.llm_response,
          isUser: false,
          time: getCurrentTime(),
          messageType: 'ai'
        });
      }
    } else {
      const errorMessages = response.errors ? Object.values(response.errors).flat().join('; ') : '';
      const errorMessage = `${response.message}${errorMessages ? ` (${errorMessages})` : ''}` || '发送消息失败';
      Message.error(errorMessage);
      messages.value.push({
        content: `错误: ${response.message || '发送失败'}`,
        isUser: false,
        time: getCurrentTime(),
        messageType: 'ai'
      });
    }
  } catch (error: any) {
    // 移除loading消息
    messages.value.splice(loadingMessageIndex, 1);

    console.error('Error sending chat message:', error);
    const errorDetail = error.response?.data?.message || error.message || '发送消息失败';
    Message.error(errorDetail);
    messages.value.push({
      content: `错误: ${errorDetail}`,
      isUser: false,
      time: getCurrentTime(),
      messageType: 'ai'
    });
  } finally {
    isLoading.value = false;
  }
};

// 处理conversation_flow
const handleConversationFlow = (conversationFlow: any[], originalMessage: string, skipAiIndex?: number) => {
  // 找到当前用户消息在conversation_flow中的位置
  let userMessageIndex = -1;

  // 从后往前找，找到最后一个匹配的用户消息
  for (let i = conversationFlow.length - 1; i >= 0; i--) {
    if (conversationFlow[i].type === 'human' &&
        conversationFlow[i].content === originalMessage) {
      userMessageIndex = i;
      break;
    }
  }

  // 如果找到了用户消息，添加该消息之后的所有新消息
  if (userMessageIndex >= 0) {
    const newMessages = conversationFlow.slice(userMessageIndex + 1);

    // 添加新消息到界面
    newMessages.forEach((flowItem, index) => {
      // 如果是流式模式，跳过已经在流式处理中添加的消息
      if (skipAiIndex !== undefined) {
        // 跳过最后一个AI消息（已经在流式处理中添加了）
        if (flowItem.type === 'ai' && index === newMessages.length - 1) {
          return;
        }
        // 跳过工具消息（已经在流式处理中添加了）
        if (flowItem.type === 'tool') {
          return;
        }
      }

      const message: ChatMessage = {
        content: flowItem.content,
        isUser: flowItem.type === 'human',
        time: getCurrentTime(),
        messageType: flowItem.type
      };

      // 如果是工具消息，设置默认折叠状态
      if (flowItem.type === 'tool') {
        message.isExpanded = false;
      }

      messages.value.push(message);
    });
  }
};

// 监听项目变化，重新加载数据
watch(() => projectStore.currentProjectId, async (newProjectId, oldProjectId) => {
  if (newProjectId && newProjectId !== oldProjectId) {
    // 项目切换时清空当前状态
    messages.value = [];
    chatSessions.value = [];
    sessionId.value = '';
    localStorage.removeItem('langgraph_session_id');

    // 重新加载会话列表
    await loadSessionsFromServer();
  }
}, { immediate: false });

// 获取当前激活的LLM配置
const loadCurrentLlmConfig = async () => {
  try {
    const response = await listLlmConfigs();
    if (response.status === 'success') {
      // 找到激活的配置
      const activeConfig = response.data.find(config => config.is_active);
      if (activeConfig) {
        currentLlmConfig.value = activeConfig;
      } else {
        Message.warning('未找到激活的LLM配置');
      }
    }
  } catch (error) {
    console.error('获取LLM配置失败:', error);
    Message.error('获取LLM配置失败');
  }
};

// 显示系统提示词弹窗
const showSystemPromptModal = async () => {
  await loadCurrentLlmConfig();
  isSystemPromptModalVisible.value = true;
};

// 关闭系统提示词弹窗
const closeSystemPromptModal = async () => {
  isSystemPromptModalVisible.value = false;
  
  // 检查关闭弹窗后是否还没有提示词
  await checkPromptStatusAfterClose();
};

// 关闭弹窗后检查提示词状态
const checkPromptStatusAfterClose = async () => {
  try {
    const response = await getUserPrompts({
      is_active: true,
      page_size: 1
    });

    if (response.status === 'success') {
      const prompts = Array.isArray(response.data) ? response.data : response.data.results || [];
      hasPrompts.value = prompts.length > 0;
      
      // 如果还是没有提示词，提示用户
      if (!hasPrompts.value) {
        Message.warning('请添加或初始化提示词后才能开始对话');
      }
    }
  } catch (error) {
    console.error('❌ 关闭弹窗后检查提示词状态失败:', error);
  }
};

// 更新系统提示词
const handleUpdateSystemPrompt = async (configId: number, systemPrompt: string) => {
  isSystemPromptLoading.value = true;
  try {
    const response = await partialUpdateLlmConfig(configId, {
      system_prompt: systemPrompt
    });

    if (response.status === 'success') {
      Message.success('系统提示词更新成功');
      // 更新本地配置
      if (currentLlmConfig.value) {
        currentLlmConfig.value.system_prompt = systemPrompt;
      }
      closeSystemPromptModal();
    } else {
      Message.error(response.message || '更新系统提示词失败');
    }
  } catch (error) {
    console.error('更新系统提示词失败:', error);
    Message.error('更新系统提示词失败');
  } finally {
    isSystemPromptLoading.value = false;
  }
};

// 检查提示词状态
const checkPromptStatus = async () => {
  try {
    const response = await getUserPrompts({
      is_active: true,
      page_size: 1 // 只需要知道是否有提示词，不需要全部数据
    });

    if (response.status === 'success') {
      const prompts = Array.isArray(response.data) ? response.data : response.data.results || [];
      hasPrompts.value = prompts.length > 0;
      console.log('📝 提示词状态检查完成:', { hasPrompts: hasPrompts.value, count: prompts.length });
      
      // 如果没有提示词，自动弹出管理弹窗
      if (!hasPrompts.value) {
        console.log('⚠️ 没有提示词，自动弹出管理弹窗');
        isSystemPromptModalVisible.value = true;
      }
    } else {
      hasPrompts.value = false;
      console.warn('⚠️ 获取提示词状态失败:', response.message);
    }
  } catch (error) {
    hasPrompts.value = false;
    console.error('❌ 检查提示词状态失败:', error);
  }
};

// 处理提示词数据更新
const handlePromptsUpdated = async () => {
  console.log('🔄 收到提示词更新事件，开始刷新ChatHeader数据...');

  // 重新检查提示词状态（不会自动弹窗，因为用户刚刚在管理页面操作过）
  try {
    const response = await getUserPrompts({
      is_active: true,
      page_size: 1
    });

    if (response.status === 'success') {
      const prompts = Array.isArray(response.data) ? response.data : response.data.results || [];
      hasPrompts.value = prompts.length > 0;
      console.log('📝 提示词状态更新完成:', { hasPrompts: hasPrompts.value, count: prompts.length });
    }
  } catch (error) {
    console.error('❌ 更新提示词状态失败:', error);
  }

  // 先检查当前选中的提示词是否还存在
  if (selectedPromptId.value !== null) {
    try {
      const response = await getUserPrompts({
        is_active: true,
        page_size: 100
      });

      if (response.status === 'success') {
        const allPrompts = Array.isArray(response.data) ? response.data : response.data.results || [];
        const currentPromptExists = allPrompts.some(prompt => prompt.id === selectedPromptId.value);

        if (!currentPromptExists) {
          console.log('⚠️ 当前选中的提示词已被删除，重置为默认选择');
          selectedPromptId.value = null;
        }
      }
    } catch (error) {
      console.error('检查提示词存在性失败:', error);
    }
  }

  // 刷新ChatHeader中的提示词列表
  if (chatHeaderRef.value) {
    await chatHeaderRef.value.refreshPrompts();
    console.log('✅ ChatHeader提示词数据刷新完成');
  } else {
    console.warn('⚠️ chatHeaderRef为空，无法刷新提示词数据');
  }
};

// 监听知识库设置变化，自动保存到本地存储
// 监视当前会话的流是否完成
watch(
  () => (sessionId.value ? activeStreams.value[sessionId.value] : null),
  (stream) => {
    if (stream && stream.isComplete) {
      console.log(`会话 ${sessionId.value} 的流已完成。`);
      // 流结束后，刷新历史记录以持久化最终消息
      loadChatHistory();
      
      // 清理已完成的流状态，避免不必要的内存占用
      clearStreamState(sessionId.value!);

      // 如果是通过本页面发送的消息，则需要在这里设置 isLoading = false
      if (isLoading.value) {
        isLoading.value = false;
      }
    }
  },
  { deep: true }
);

watch([useKnowledgeBase, selectedKnowledgeBaseId, similarityThreshold, topK], () => {
  saveKnowledgeBaseSettings();
}, { deep: true });

onMounted(async () => {
  // 加载知识库设置
  loadKnowledgeBaseSettings();
  
  // 从服务器加载会话列表 - 仅在首次挂载时加载
  await loadSessionsFromServer();

  // 尝试加载当前会话的历史记录
  await loadChatHistory();

  // 加载当前LLM配置
  await loadCurrentLlmConfig();
  
  // 检查提示词状态（如果没有会自动弹出管理弹窗）
  await checkPromptStatus();
});

onActivated(async () => {
  // 每次组件被激活时（从其他页面切回来）
  console.log('✅ Chat component activated.');

  // 1. 刷新左侧的会话列表
  await loadSessionsFromServer();

  // 2. 检查localStorage，看是否有指定的会话需要加载
  const storedSessionId = getSessionIdFromStorage();

  // 3. 如果存储的ID和当前组件活跃的ID不一致，则强制切换到新会话
  if (storedSessionId && storedSessionId !== sessionId.value) {
    console.log(`Detected session change from localStorage: ${storedSessionId}. Switching...`);
    await switchSession(storedSessionId);
  }
  // 4. 如果是同一个会话，检查是否有正在进行的流需要恢复显示
  else if (storedSessionId && activeStreams.value[storedSessionId]) {
    console.log(`Resuming stream display for current session ${storedSessionId}.`);
    // 如果流在后台已经完成，但UI没有及时更新，这里重新加载历史记录
    if (activeStreams.value[storedSessionId].isComplete) {
      await loadChatHistory();
      clearStreamState(storedSessionId);
    }
  }
});

onUnmounted(() => {
  // 组件卸载时，终止任何正在进行的流式请求
  abortController.abort();
});
</script>

<script lang="ts">
export default {
  name: 'LangGraphChat'
}
</script>

<style scoped>
.chat-layout {
  display: flex;
  height: 100%;
  background-color: #f7f8fa;
  border-radius: 8px;
  overflow: hidden;
}

.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: #f7f8fa;
  overflow: hidden;
}
</style>