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
      @batch-delete-sessions="batchDeleteSessions"
    />

    <!-- 右侧聊天区域 -->
    <div class="chat-container">
      <ChatHeader
        ref="chatHeaderRef"
        :session-id="sessionId"
        :has-messages="messages.length > 0"
        :project-id="projectStore.currentProjectId"
        :use-knowledge-base="useKnowledgeBase"
        :selected-knowledge-base-id="selectedKnowledgeBaseId"
        :similarity-threshold="similarityThreshold"
        :top-k="topK"
        :selected-prompt-id="selectedPromptId"
        @clear-chat="clearChat"
        @show-system-prompt="showSystemPromptModal"
        @show-tool-approval-settings="isToolApprovalSettingsVisible = true"
        @update:use-knowledge-base="useKnowledgeBase = $event"
        @update:selected-knowledge-base-id="selectedKnowledgeBaseId = $event"
        @update:similarity-threshold="similarityThreshold = $event"
        @update:top-k="topK = $event"
        @update:selected-prompt-id="selectedPromptId = $event"
      />

      <ChatMessages
        ref="chatMessagesRef"
        :messages="displayedMessages"
        :is-loading="isLoading && messages.length === 0"
        :floating-tool-image-src="floatingToolImageSrc"
        @toggle-expand="toggleExpand"
        @quote="handleQuote"
        @retry="handleRetry"
        @delete="handleDeleteMessage"
        @preview-diagram="handlePreviewDiagram"
        @preview-html="handlePreviewHtml"
        @tool-image-detected="handleToolImageDetected"
        @float-tool-image="handleFloatToolImage"
      />

      <!-- 工具图片悬浮面板（可拖动） -->
      <div
        v-if="floatingToolImageSrc"
        ref="floatingPanelRef"
        class="floating-tool-image-panel"
        :style="floatingPanelStyle"
      >
        <div class="floating-panel-header" @mousedown="startDrag">
          <span class="floating-panel-title">📷 工具截图</span>
          <button class="floating-panel-close" @click="closeFloatingImage">&times;</button>
        </div>
        <img :src="floatingToolImageSrc" alt="工具截图" class="floating-panel-img" />
      </div>

      <!-- ⭐ HITL 工具审批卡片（输入框上方） -->
      <ToolApprovalCard
        :visible="toolApprovalDialogVisible"
        :interrupt="currentInterrupt"
        :session-id="sessionId"
        @update:visible="toolApprovalDialogVisible = $event"
        @decision="handleToolDecision"
      />

      <ChatInput
        :is-loading="isLoading"
        :supports-vision="currentLlmConfig?.supports_vision || false"
        :context-token-count="contextTokenInfo.tokenCount"
        :context-limit="contextTokenInfo.limit"
        :quoted-message="quotedMessage"
        @send-message="handleSendMessage"
        @clear-quote="handleClearQuote"
        @stop-generation="handleStopGeneration"
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

    <!-- ⭐工具审批设置弹窗 -->
    <ToolApprovalSettingsModal
      v-model:visible="isToolApprovalSettingsVisible"
      :session-id="sessionId"
    />

    <!-- 图表预览弹窗 -->
    <a-modal
      v-model:visible="diagramPreviewVisible"
      title="图表预览"
      :width="'90%'"
      :footer="false"
      :mask-closable="true"
      :unmount-on-close="true"
    >
      <iframe
        v-if="diagramPreviewUrl"
        ref="diagramPreviewIframeRef"
        :src="diagramPreviewUrl"
        class="diagram-preview-iframe"
      ></iframe>
    </a-modal>

    <!-- HTML 预览弹窗 -->
    <a-modal
      v-model:visible="htmlPreviewVisible"
      title="HTML 预览"
      :width="'90%'"
      :footer="false"
      :mask-closable="true"
      :unmount-on-close="true"
    >
      <div v-if="htmlPreviewContent" ref="htmlPreviewContainerRef" class="html-preview-wrapper">
        <a-button
          class="html-preview-fullscreen-btn"
          type="secondary"
          shape="circle"
          size="small"
          @click="toggleHtmlPreviewFullscreen"
        >
          <template #icon>
            <IconFullscreenExit v-if="isHtmlPreviewFullscreen" />
            <IconFullscreen v-else />
          </template>
        </a-button>
        <iframe
          class="diagram-preview-iframe html-preview-iframe"
          :srcdoc="htmlPreviewContent"
          sandbox="allow-scripts allow-forms allow-modals allow-popups allow-popups-to-escape-sandbox allow-top-navigation-by-user-activation"
        ></iframe>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onActivated, watch, onUnmounted, computed, nextTick } from 'vue';
import { Message, Modal } from '@arco-design/web-vue';
import {
  sendChatMessageNonStream,
  sendChatMessageStream,
  getChatHistory,
  deleteChatHistory,
  rollbackChatHistory,
  batchDeleteChatHistory,
  getChatSessions,
  activeStreams,
  clearStreamState,
  latestContextUsage,
  stopAgentLoop,
  resumeAgentLoop
} from '@/features/langgraph/services/chatService';
import { listLlmConfigs, partialUpdateLlmConfig } from '@/features/langgraph/services/llmConfigService';
import { getUserPrompts } from '@/features/prompts/services/promptService';
import type { ChatRequest, ChatHistoryMessage } from '@/features/langgraph/types/chat';
import type { LlmConfig } from '@/features/langgraph/types/llmConfig';
import { useProjectStore } from '@/store/projectStore';
import { useLlmConfigRefresh } from '@/composables/useLlmConfigRefresh';
import { marked } from 'marked';
import { IconFullscreen, IconFullscreenExit } from '@arco-design/web-vue/es/icon';
import type { ToolFileAttachment } from '@/features/langgraph/utils/toolResultParser';
import { parseToolResultDisplayPayload } from '@/features/langgraph/utils/toolResultParser';

// 导入子组件
import ChatSidebar from '../components/ChatSidebar.vue';
import ChatHeader from '../components/ChatHeader.vue';
import ChatMessages from '../components/ChatMessages.vue';
import ChatInput from '../components/ChatInput.vue';
import SystemPromptModal from '../components/SystemPromptModal.vue';
import ToolApprovalCard from '../components/ToolApprovalCard.vue';
import ToolApprovalSettingsModal from '../components/ToolApprovalSettingsModal.vue';
import type { InterruptEvent } from '../components/ToolApprovalCard.vue';

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
  messageType?: 'human' | 'ai' | 'tool' | 'system' | 'agent_step' | 'step_separator';  // ⭐ 新增 step_separator 类型
  toolName?: string;
  isExpanded?: boolean;
  isStreaming?: boolean;
  imageBase64?: string;
  imageDataUrl?: string;
  fileAttachments?: ToolFileAttachment[];
  imageBase64List?: string[];
  imageDataUrls?: string[];
  isThinkingProcess?: boolean;
  isThinkingExpanded?: boolean;
  // Agent Step 专用字段
  stepNumber?: number;
  maxSteps?: number;
  stepStatus?: 'start' | 'complete' | 'error';
  // ⭐ Agent Loop 历史记录专用字段
  agent?: string;  // 'agent_loop'
  agentType?: string;  // 'intermediate' | 'final'
  step?: number;  // 步骤号
  isStepSeparator?: boolean;  // 是否是步骤分隔消息
}

interface ChatSession {
  id: string;
  title: string;
  lastTime: Date;
  messageCount: number;
}

interface DiagramPreviewPayload {
  xml: string;
  sourceMessage: ChatMessage;
}

interface HtmlPreviewPayload {
  html: string;
  sourceMessage: ChatMessage;
}

const messages = ref<ChatMessage[]>([]);
const isLoading = ref(false);
const sessionId = ref<string>('');
const chatSessions = ref<ChatSession[]>([]);
const chatMessagesRef = ref<InstanceType<typeof ChatMessages> | null>(null);

// 流式模式：从 LLM 配置读取（computed）
const isStreamMode = computed(() => currentLlmConfig.value?.enable_streaming ?? true);

// 知识库相关
const useKnowledgeBase = ref(false); // 是否启用知识库功能
const selectedKnowledgeBaseId = ref<string | null>(null); // 选中的知识库ID
const similarityThreshold = ref(0.3); // 相似度阈值
const topK = ref(5); // 检索结果数量

// 消息操作相关
const quotedMessage = ref<ChatMessage | null>(null); // 引用的消息
const diagramPreviewVisible = ref(false);
const diagramPreviewXml = ref('');
const diagramPreviewIframeRef = ref<HTMLIFrameElement | null>(null);
const diagramPreviewReady = ref(false);
const htmlPreviewVisible = ref(false);
const htmlPreviewContent = ref('');
const htmlPreviewContainerRef = ref<HTMLElement | null>(null);
const isHtmlPreviewFullscreen = ref(false);

// 工具图片悬浮预览（可拖动）
const floatingToolImageSrc = ref<string | null>(null);
const floatingPanelRef = ref<HTMLElement | null>(null);
const panelPos = ref<{ x: number; y: number } | null>(null);
const dragState = ref<{ startX: number; startY: number; origX: number; origY: number } | null>(null);

const floatingPanelStyle = computed(() => {
  if (!panelPos.value) return {};
  return { top: `${panelPos.value.y}px`, right: 'auto', left: `${panelPos.value.x}px` };
});

const startDrag = (e: MouseEvent) => {
  // 防止在关闭按钮上触发拖动
  if ((e.target as HTMLElement).closest('.floating-panel-close')) return;
  e.preventDefault();
  const panel = floatingPanelRef.value;
  if (!panel) return;

  const rect = panel.getBoundingClientRect();
  const containerRect = panel.offsetParent?.getBoundingClientRect() || { left: 0, top: 0 };
  const currentX = panelPos.value?.x ?? rect.left - containerRect.left;
  const currentY = panelPos.value?.y ?? rect.top - containerRect.top;

  dragState.value = { startX: e.clientX, startY: e.clientY, origX: currentX, origY: currentY };
  if (!panelPos.value) panelPos.value = { x: currentX, y: currentY };

  const onMove = (ev: MouseEvent) => {
    if (!dragState.value) return;
    panelPos.value = {
      x: dragState.value.origX + (ev.clientX - dragState.value.startX),
      y: dragState.value.origY + (ev.clientY - dragState.value.startY),
    };
  };
  const onUp = () => {
    dragState.value = null;
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
  };
  document.addEventListener('mousemove', onMove);
  document.addEventListener('mouseup', onUp);
};

const handleToolImageDetected = (src: string) => {
  floatingToolImageSrc.value = src;
  // 保持用户已拖动的位置，不重置 panelPos
};
const handleFloatToolImage = (src: string) => {
  if (floatingToolImageSrc.value === src) {
    floatingToolImageSrc.value = null;
  } else {
    floatingToolImageSrc.value = src;
    panelPos.value = null;
  }
};
const closeFloatingImage = () => {
  floatingToolImageSrc.value = null;
};

// 切换会话时清除悬浮图片
watch(sessionId, () => {
  floatingToolImageSrc.value = null;
  panelPos.value = null;
});

// 提示词相关
const selectedPromptId = ref<number | null>(null); // 用户选择的提示词ID
const hasPrompts = ref(false); // 是否有可用的提示词

// ⭐从localStorage恢复选中的提示词
const PROMPT_STORAGE_KEY = 'wharttest_selected_prompt_id';
const loadSavedPromptId = () => {
  try {
    const saved = localStorage.getItem(PROMPT_STORAGE_KEY);
    if (saved) {
      selectedPromptId.value = parseInt(saved, 10);
    }
  } catch (error) {
    console.error('加载保存的提示词ID失败:', error);
  }
};

// ⭐监听selectedPromptId变化,保存到localStorage
watch(selectedPromptId, (newValue) => {
  try {
    if (newValue !== null) {
      localStorage.setItem(PROMPT_STORAGE_KEY, String(newValue));
    } else {
      localStorage.removeItem(PROMPT_STORAGE_KEY);
    }
  } catch (error) {
    console.error('保存提示词ID失败:', error);
  }
});


// 系统提示词相关
const isSystemPromptModalVisible = ref(false);
const isSystemPromptLoading = ref(false);
const currentLlmConfig = ref<LlmConfig | null>(null);

// ⭐工具审批设置弹窗
const isToolApprovalSettingsVisible = ref(false);

// 项目store
const projectStore = useProjectStore();
const { getRefreshTrigger } = useLlmConfigRefresh();

// 上下文Token使用信息（从流式状态中获取）
const contextTokenInfo = computed(() => {
  const defaultLimit = currentLlmConfig.value?.context_limit || 128000;
  const id = sessionId.value;
  if (!id) return { tokenCount: 0, limit: defaultLimit };

  // 检查普通聊天模式的流状态
  const chatStream = activeStreams.value[id];
  if (chatStream && chatStream.contextTokenCount !== undefined) {
    return {
      tokenCount: chatStream.contextTokenCount || 0,
      limit: chatStream.contextLimit || defaultLimit
    };
  }

  // Fallback: 使用普通聊天缓存
  const chatCache = latestContextUsage.value[id];
  if (chatCache) {
    return {
      tokenCount: chatCache.tokenCount,
      limit: chatCache.limit || defaultLimit
    };
  }

  return { tokenCount: 0, limit: defaultLimit };
});

// 规范化历史消息内容：
// 后端历史接口在 tool 消息中可能返回数组/对象（如 [{type:"text", text:"..."}]），
// 前端渲染链路按字符串处理，需要先统一为字符串。
const normalizeHistoryContent = (historyItem: ChatHistoryMessage): string => {
  const rawContent: unknown = (historyItem as any).content;

  if (typeof rawContent === 'string') {
    return rawContent;
  }

  if (historyItem.type === 'tool' && Array.isArray(rawContent)) {
    const hasNonTextItem = rawContent.some((item: any) =>
      item && typeof item === 'object' && item.type !== 'text'
    );
    if (!hasNonTextItem) {
      const textParts = rawContent
        .filter((item: any) => item && typeof item === 'object' && item.type === 'text' && typeof item.text === 'string')
        .map((item: any) => item.text);
      if (textParts.length > 0) {
        return textParts.join('\n');
      }
    }
  }

  try {
    return JSON.stringify(rawContent, null, 2);
  } catch {
    return String(rawContent ?? '');
  }
};

const getFullUrl = (url: string) => {
  return url.startsWith('/') ? `${window.location.origin}${url}` : url;
};

const drawioPreviewBaseUrl = getFullUrl(import.meta.env.VITE_DRAWIO_URL || 'https://embed.diagrams.net');
const drawioPreviewOrigin = computed(() => new URL(drawioPreviewBaseUrl).origin);

const diagramPreviewUrl = computed(() => {
  if (!diagramPreviewXml.value) return '';
  const params = new URLSearchParams({
    embed: '1',
    proto: 'json',
    spin: '1',
    ui: 'kennedy',
    splash: '0',
    noSaveBtn: '1',
    noExitBtn: '1',
    toolbar: '0',
    math: '0'
  });
  return `${drawioPreviewBaseUrl}/?${params.toString()}`;
});

const sendDiagramPreviewXml = () => {
  if (!diagramPreviewIframeRef.value?.contentWindow || !diagramPreviewXml.value) return;
  diagramPreviewIframeRef.value.contentWindow.postMessage(
    JSON.stringify({
      action: 'load',
      xml: diagramPreviewXml.value
    }),
    drawioPreviewOrigin.value
  );
};

const handleDiagramPreviewMessage = (event: MessageEvent) => {
  if (event.origin !== drawioPreviewOrigin.value) return;

  try {
    const msg = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
    if (!msg || typeof msg !== 'object') return;

    if (msg.event === 'init') {
      diagramPreviewReady.value = true;
      sendDiagramPreviewXml();
    }
  } catch {
    // 忽略非 JSON 消息
  }
};

// ⭐ HITL 工具审批相关
const toolApprovalDialogVisible = ref(false);
const currentInterrupt = computed<InterruptEvent | null>(() => {
  const id = sessionId.value;
  if (!id) return null;
  const stream = activeStreams.value[id];
  console.log('[LangGraphChatView] currentInterrupt computed:', {
    sessionId: id,
    hasStream: !!stream,
    isWaitingForApproval: stream?.isWaitingForApproval,
    interrupt: stream?.interrupt
  });
  if (stream?.isWaitingForApproval && stream?.interrupt) {
    return stream.interrupt as InterruptEvent;
  }
  return null;
});

// 监听中断状态，自动弹出/关闭审批对话框
watch(currentInterrupt, async (interrupt) => {
  console.log('[LangGraphChatView] currentInterrupt watch triggered:', interrupt);
  if (interrupt) {
    // 检查是否所有工具都需要自动拒绝
    const actionRequests = interrupt.action_requests || [];
    const allAutoReject = actionRequests.length > 0 &&
      actionRequests.every((ar) => ar.auto_reject === true);

    if (allAutoReject) {
      // 所有工具都设为"始终拒绝"，自动发送拒绝响应
      console.log('[LangGraphChatView] All tools marked as auto_reject, sending auto-reject');
      const toolNames = actionRequests.map((ar) => ar.name || 'unknown').join(', ');
      Message.warning(`工具 ${toolNames} 已被设为始终拒绝，自动拒绝执行`);

      // 延迟自动拒绝，等待当前 SSE 流完全结束
      // 避免 clearStreamState 删除 activeStreams 后 resumeAgentLoop 无法正常工作
      setTimeout(async () => {
        await handleToolDecision({
          interruptId: interrupt.interrupt_id || interrupt.id || '',
          type: 'reject',
        });
      }, 100);
    } else {
      // 有需要用户审批的工具，显示对话框
      toolApprovalDialogVisible.value = true;
    }
  } else {
    // 当 interrupt 变为 null 时，自动关闭对话框
    toolApprovalDialogVisible.value = false;
  }
});

// 处理工具审批决策
const handleToolDecision = async (decision: {
  interruptId: string;
  type: 'approve' | 'reject';
  rememberChoice?: boolean;
  rememberScope?: string;
  toolName?: string;
}) => {
  console.log('[LangGraphChatView] handleToolDecision called:', decision);

  const projectId = projectStore.currentProjectId;
  if (!projectId || !sessionId.value) {
    console.error('[LangGraphChatView] Missing projectId or sessionId:', { projectId, sessionId: sessionId.value });
    Message.error('无法获取项目或会话信息');
    return;
  }

  console.log('[LangGraphChatView] Calling resumeAgentLoop with:', {
    sessionId: sessionId.value,
    interruptId: decision.interruptId,
    decision: decision.type,
    projectId,
    knowledgeBaseId: selectedKnowledgeBaseId.value,
    useKnowledgeBase: useKnowledgeBase.value
  });

  toolApprovalDialogVisible.value = false;

  // 显示操作提示
  Message.info(decision.type === 'approve' ? '正在执行工具...' : '已拒绝执行');

  // 获取工具调用数量
  const actionCount = currentInterrupt.value?.action_requests?.length || 1;

  try {
    // resumeAgentLoop 现在是 SSE 流式的，它会直接更新 activeStreams 状态
    // 不需要检查返回值，流会自动处理后续的工具执行和 LLM 响应
    await resumeAgentLoop(
      sessionId.value,
      decision.interruptId,
      decision.type,
      projectId,
      undefined, // signal
      selectedKnowledgeBaseId.value,
      useKnowledgeBase.value,
      actionCount
    );
    // SSE 流结束后，如果没有新的中断，会话会标记为完成
    // 如果有新的中断，interrupt 状态会被更新，触发新的审批对话框
  } catch (error) {
    console.error('Resume agent loop failed:', error);
    Message.error('操作失败，请重试');
  }
};

// 组件引用
const chatHeaderRef = ref<{ refreshPrompts: () => Promise<void> } | null>(null);

// 终止控制器
let abortController = new AbortController();

// 标记 onMounted 是否完成首次加载
let isMountedLoadComplete = false;

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


// 保存会话列表到本地存储
const saveSessionsToStorage = () => {
  localStorage.setItem('langgraph_sessions', JSON.stringify(chatSessions.value));
};

// ⭐ 安全停止加载状态：只有在没有正在进行的流时才设置 isLoading = false
const safeStopLoading = () => {
  const id = sessionId.value;
  // 检查普通聊天流
  const stream = id ? activeStreams.value[id] : null;
  const hasActiveStream = stream && !stream.isComplete;

  if (!hasActiveStream) {
    isLoading.value = false;
  }
};

// 从服务器加载会话列表
const loadSessionsFromServer = async () => {
  if (!projectStore.currentProjectId) {
    console.log('⏳ 等待项目加载完成，暂不加载会话列表');
    return;
  }

  try {
    isLoading.value = true;
    const response = await getChatSessions(projectStore.currentProjectId);

    if (response.status === 'success' && response.data) {
      // 优先使用 sessions_detail（包含标题和时间），避免 N+1 查询
      const sessionsDetail = response.data.sessions_detail;
      
      if (sessionsDetail && sessionsDetail.length > 0) {
        // 直接使用后端返回的会话详情
        const tempSessions: ChatSession[] = sessionsDetail.map(detail => {
          const timeStr = detail.updated_at || detail.created_at;
          let lastTime: Date | null = null;
          if (timeStr) {
            try {
              const parsed = new Date(timeStr.replace(' ', 'T'));
              if (!isNaN(parsed.getTime())) {
                lastTime = parsed;
              }
            } catch { /* 解析失败时 lastTime 保持 null */ }
          }
          return {
            id: detail.id,
            title: detail.title || '未命名对话',
            lastTime: lastTime ?? new Date(0),
            messageCount: 0
          };
        });

        // 按时间倒序排序
        tempSessions.sort((a, b) => b.lastTime.getTime() - a.lastTime.getTime());
        chatSessions.value = tempSessions;
        console.log(`✅ 从服务器快速加载了 ${tempSessions.length} 个会话`);
      } else {
        // 兼容旧版后端：无 sessions_detail 时清空列表
        chatSessions.value = [];
      }

      saveSessionsToStorage();
    } else {
      Message.error('获取会话列表失败');
    }
  } catch (error) {
    console.error('获取会话列表失败:', error);
    Message.error('获取会话列表失败，请稍后重试');
  } finally {
    safeStopLoading();
  }
};

// ⭐ 纯函数: 为历史记录插入 Agent Loop 步骤分隔符
// 用于统一处理步骤分隔符逻辑,避免代码重复
const enrichMessagesWithSeparators = (rawHistory: ChatHistoryMessage[], formatHistoryTime: (timestamp: string) => string): ChatMessage[] => {
  const result: ChatMessage[] = [];
  let lastAgentLoopStep: number | null = null;  // ✅ 追踪上一条agent_loop消息的步骤号

  rawHistory.forEach(historyItem => {
    // 跳过系统消息
    if (historyItem.type === 'system') {
      return;
    }

    // ✅ 检测 Agent Loop 步骤变化: 只要有step字段就插入分隔符
    // 修复逻辑: 与上一条agent_loop消息的步骤比较,而非全局追踪
    // 这样可以支持多轮对话中步骤编号重复的情况(例如两次对话都从Step 1开始)
    if (historyItem.agent === 'agent_loop' && historyItem.step !== undefined) {
      const currentStep = historyItem.step;
      
      // 插入分隔符: 仅当步骤号与上一条不同,或者这是第一条agent_loop消息
      if (lastAgentLoopStep === null || currentStep !== lastAgentLoopStep) {
        result.push({
          content: `步骤 ${currentStep}/${historyItem.max_steps || 500}`,
          isUser: false,
          time: formatHistoryTime(historyItem.timestamp),
          messageType: 'step_separator'
        });
        
        lastAgentLoopStep = currentStep;
      }
    }
    
    // ✅ 如果遇到非agent_loop消息,重置步骤追踪
    // 这样下一次agent_loop调用会从新的步骤序列开始
    if (historyItem.agent !== 'agent_loop') {
      lastAgentLoopStep = null;
    }

    // 转换历史消息为 ChatMessage 格式
    const message: ChatMessage = {
      content: normalizeHistoryContent(historyItem),
      isUser: historyItem.type === 'human',
      time: formatHistoryTime(historyItem.timestamp),
      messageType: historyItem.type
    };

    // 工具消息默认折叠
    if (historyItem.type === 'tool') {
      message.isExpanded = false;
      const toolPayload = parseToolResultDisplayPayload(message.content);
      if (toolPayload.fileAttachments.length > 0) {
        message.fileAttachments = toolPayload.fileAttachments;
      }
    }

    // 思考过程消息折叠状态
    if (historyItem.is_thinking_process) {
      message.isThinkingProcess = true;
      message.isThinkingExpanded = false;
    }

    // 附加 Agent Loop 元数据
    if (historyItem.agent === 'agent_loop') {
      message.agent = historyItem.agent;
      message.agentType = historyItem.agent_type;
      message.step = historyItem.step;
    }

    // 图片数据
    if (historyItem.images && historyItem.images.length > 0) {
      message.imageDataUrls = historyItem.images;
      message.imageDataUrl = historyItem.images[0];
    } else if (historyItem.image) {
      message.imageDataUrls = [historyItem.image];
      message.imageDataUrl = historyItem.image;
    }

    result.push(message);
  });

  return result;
};

// 加载聊天历史记录
const loadChatHistory = async () => {
  const storedSessionId = getSessionIdFromStorage();
  
  // 🔧 修复：静默处理无会话ID的情况，不显示任何提示
  if (!storedSessionId) {
    console.log('💭 没有保存的会话ID，显示空白对话界面');
    return;
  }
  
  // 如果没有项目ID，也静默返回（watch会在项目加载完成后重新调用）
  if (!projectStore.currentProjectId) {
    console.log('⏳ 等待项目加载完成...');
    return;
  }

  try {
    isLoading.value = true;
    const response = await getChatHistory(storedSessionId, projectStore.currentProjectId);

    if (response.status === 'success' && response.data) {
      const data = response.data;
      sessionId.value = data.session_id;

      // 🆕 恢复该会话的Token使用信息
      if (data.context_token_count !== undefined) {
        const tokenCount = data.context_token_count || 0;
        const limit = data.context_limit || 128000;
        latestContextUsage.value[data.session_id] = { tokenCount, limit };
        console.log(`🔄 恢复会话Token使用: ${tokenCount}/${limit}`);
      }

      // 🆕 恢复该会话关联的提示词
      if (data.prompt_id !== null && data.prompt_id !== undefined) {
        selectedPromptId.value = data.prompt_id;
        localStorage.setItem(PROMPT_STORAGE_KEY, String(data.prompt_id));
        console.log(`🔄 恢复会话提示词: ${data.prompt_name} (ID: ${data.prompt_id})`);
      }

      // ✅ 使用纯函数处理历史记录,自动插入步骤分隔符
      const tempMessages = enrichMessagesWithSeparators(data.history, formatHistoryTime);
      
      // 🎨 合并连续的思考过程消息
      messages.value = mergeThinkingProcessMessages(tempMessages);
      
      console.log('🔍 [Debug] messages.value最终数量:', messages.value.length);
      console.log('🔍 [Debug] 最终step_separator数量:', messages.value.filter(m => m.messageType === 'step_separator').length);

      // 只有在会话列表中不存在该会话时才添加（避免重复）
      const existingSession = chatSessions.value.find(s => s.id === data.session_id);
      if (!existingSession) {
        const firstHumanMessage = data.history.find(msg => msg.type === 'human')?.content;
        updateSessionInList(data.session_id, firstHumanMessage, false);
      }
      
      console.log(`✅ 成功加载会话历史: ${sessionId.value}, ${messages.value.length} 条消息`);
    } else {
      // 🔧 修复：获取历史失败时静默处理，不显示错误提示
      // 可能是会话已被删除或过期，清除存储的会话ID即可
      console.warn('⚠️ 会话历史获取失败，可能已被删除');
      localStorage.removeItem('langgraph_session_id');
      sessionId.value = '';
    }
  } catch (error) {
    // 🔧 修复：网络错误等异常情况才显示错误提示
    console.error('❌ 加载聊天历史异常:', error);
    // 只在真正的错误情况下提示用户
    Message.error('加载聊天历史失败，将开始新的对话');
    localStorage.removeItem('langgraph_session_id');
    sessionId.value = '';
  } finally {
    safeStopLoading();
  }
};

// 获取当前时间
const getCurrentTime = () => {
  const now = new Date();
  return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
};

// 🔧 固化流式内容到messages.value（发送新消息前调用，避免内容丢失）
const solidifyStreamContent = () => {
  if (!sessionId.value) return;

  // 固化普通LLM聊天的流式内容
  const stream = activeStreams.value[sessionId.value];
  if (stream && stream.isComplete && stream.content && stream.content.trim()) {
    // ⭐ HITL：如果正在等待审批，不要清理流状态
    if (stream.isWaitingForApproval) {
      console.log('⏸️ 流正在等待 HITL 审批，跳过固化和清理');
      return;
    }

    // 检查是否已经固化过（避免重复）
    const lastMsg = messages.value[messages.value.length - 1];
    const alreadySolidified = lastMsg && !lastMsg.isUser && lastMsg.content === stream.content;

    if (!alreadySolidified) {
      // 先添加工具消息和中间消息
      if (stream.messages && stream.messages.length > 0) {
        stream.messages.forEach(msg => {
          const chatMsg: ChatMessage = {
            content: msg.content,
            isUser: false,
            time: msg.time,
            messageType: msg.type as ChatMessage['messageType'],
            toolName: msg.toolName,
            isExpanded: msg.isExpanded,
            imageDataUrl: msg.imageDataUrl,
            fileAttachments: msg.fileAttachments,
            isThinkingProcess: msg.isThinkingProcess,
            isThinkingExpanded: msg.isThinkingExpanded
          };
          // 保留 Agent Step 相关字段
          if (typeof msg.stepNumber === 'number') {
            chatMsg.stepNumber = msg.stepNumber;
          }
          if (typeof msg.maxSteps === 'number') {
            chatMsg.maxSteps = msg.maxSteps;
          }
          if (msg.stepStatus) {
            chatMsg.stepStatus = msg.stepStatus;
          }
          messages.value.push(chatMsg);
        });
      }
      // 添加AI回复内容
      messages.value.push({
        content: stream.content,
        isUser: false,
        time: getCurrentTime(),
        messageType: 'ai'
      });
      console.log('✅ 已固化LLM流式内容到messages.value');
    }
    clearStreamState(sessionId.value);
  }
};

// 🎨 合并连续的思考过程消息（保持对象引用，避免丢失状态）
const mergeThinkingProcessMessages = (messages: ChatMessage[]): ChatMessage[] => {
  const result: ChatMessage[] = [];
  let thinkingBuffer: ChatMessage[] = [];

  for (let i = 0; i < messages.length; i++) {
    const msg = messages[i];
    
    if (msg.isThinkingProcess) {
      thinkingBuffer.push(msg);
    } else {
      // 遇到非思考过程消息，先处理缓冲区
      if (thinkingBuffer.length > 0) {
        if (thinkingBuffer.length === 1) {
          // 只有一个思考过程，直接添加
          result.push(thinkingBuffer[0]);
        } else {
          // 多个思考过程，合并内容到第一个对象（保持响应性）
          const merged = thinkingBuffer[0];
          merged.content = thinkingBuffer.map(m => m.content).join('\n\n---\n\n');
          result.push(merged);
        }
        thinkingBuffer = [];
      }
      // 添加当前非思考过程消息
      result.push(msg);
    }
  }

  // 处理末尾剩余的思考过程消息
  if (thinkingBuffer.length > 0) {
    if (thinkingBuffer.length === 1) {
      result.push(thinkingBuffer[0]);
    } else {
      const merged = thinkingBuffer[0];
      merged.content = thinkingBuffer.map(m => m.content).join('\n\n---\n\n');
      result.push(merged);
    }
  }

  return result;
};

// 获取Agent的中文名称


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

// 切换工具消息或思考过程的展开/收起状态
const toggleExpand = (message: ChatMessage) => {
  // 首先尝试在历史消息中查找并更新
  const index = messages.value.findIndex(m => 
    m.content === message.content && 
    m.time === message.time && 
    m.messageType === message.messageType
  );
  
  if (index !== -1) {
    // 使用响应式方式更新消息
    if (message.isThinkingProcess) {
      messages.value[index] = {
        ...messages.value[index],
        isThinkingExpanded: !messages.value[index].isThinkingExpanded
      };
    } else {
      messages.value[index] = {
        ...messages.value[index],
        isExpanded: !messages.value[index].isExpanded
      };
    }
    return;
  }

  // 如果在历史消息中找不到，检查当前活动流中的消息
  const stream = sessionId.value ? activeStreams.value[sessionId.value] : null;
  if (stream?.messages && stream.messages.length > 0) {
    const streamMsgIndex = stream.messages.findIndex(
      m => m.content === message.content && 
           m.time === message.time && 
           m.type === message.messageType
    );
    
    if (streamMsgIndex !== -1) {
      // 直接修改 activeStreams 中的消息对象
      if (message.isThinkingProcess) {
        stream.messages[streamMsgIndex].isThinkingExpanded = !stream.messages[streamMsgIndex].isThinkingExpanded;
      } else {
        stream.messages[streamMsgIndex].isExpanded = !stream.messages[streamMsgIndex].isExpanded;
      }
    }
  }
};

// 处理引用消息
const handleQuote = (message: ChatMessage) => {
  quotedMessage.value = message;
};

const handlePreviewDiagram = (payload: DiagramPreviewPayload) => {
  if (!payload.xml || !payload.xml.trim()) {
    Message.warning('未检测到可预览的图表XML');
    return;
  }
  if (!diagramPreviewVisible.value) {
    diagramPreviewReady.value = false;
  }
  diagramPreviewXml.value = payload.xml;
  diagramPreviewVisible.value = true;

  if (diagramPreviewReady.value) {
    sendDiagramPreviewXml();
  }
};

const handlePreviewHtml = (payload: HtmlPreviewPayload) => {
  if (!payload.html || !payload.html.trim()) {
    Message.warning('未检测到可预览的HTML内容');
    return;
  }
  htmlPreviewContent.value = payload.html;
  htmlPreviewVisible.value = true;
};

const syncHtmlPreviewFullscreenState = () => {
  isHtmlPreviewFullscreen.value = document.fullscreenElement === htmlPreviewContainerRef.value;
};

const toggleHtmlPreviewFullscreen = async () => {
  const container = htmlPreviewContainerRef.value;
  if (!container) return;

  try {
    if (document.fullscreenElement === container) {
      await document.exitFullscreen();
      return;
    }
    await container.requestFullscreen();
  } catch (error) {
    console.error('切换HTML预览全屏失败:', error);
    Message.warning('当前环境不支持全屏预览');
  }
};

// 清除引用
const handleClearQuote = () => {
  quotedMessage.value = null;
};

// 停止生成
const handleStopGeneration = async () => {
  // 1. 先中断前端 SSE 连接
  if (abortController) {
    abortController.abort();
  }

  // 2. 调用后端停止 API（真正停止 LLM 调用）
  if (sessionId.value) {
    try {
      const result = await stopAgentLoop(sessionId.value);
      if (result.status === 'success') {
        console.log('[LangGraphChatView] Backend stop signal sent:', result.data);
      } else {
        console.warn('[LangGraphChatView] Backend stop failed:', result.message);
      }
    } catch (error) {
      console.error('[LangGraphChatView] Stop API error:', error);
    }

    // ⭐ 强制清除流状态，避免重新加载历史时消息重复
    clearStreamState(sessionId.value);

    // ⭐ 延迟一小段时间后重新加载历史，确保后端已保存完整记录
    // 后端在收到停止信号后会保存包含 [用户中断] 的完整历史
    setTimeout(async () => {
      if (sessionId.value && projectStore.currentProjectId) {
        try {
          const response = await getChatHistory(sessionId.value, projectStore.currentProjectId);
          if (response.status === 'success' && response.data?.history) {
            const tempMessages = enrichMessagesWithSeparators(response.data.history, formatHistoryTime);
            messages.value = mergeThinkingProcessMessages(tempMessages);
            console.log('[LangGraphChatView] History reloaded after stop:', messages.value.length, 'messages');
          }
        } catch (error) {
          console.error('[LangGraphChatView] Failed to reload history after stop:', error);
        }
      }
    }, 500);  // 500ms 延迟，给后端足够时间保存历史
  }

  isLoading.value = false;
  Message.info('已停止生成');
};

// 处理重试消息
const handleRetry = async (message: ChatMessage) => {
  const msgIndex = messages.value.findIndex(m =>
    m.content === message.content &&
    m.time === message.time &&
    m.messageType === message.messageType
  );

  if (msgIndex === -1) {
    Message.warning('未找到对应的消息');
    return;
  }

  let userMessage: ChatMessage;

  if (message.messageType === 'human') {
    // 用户消息重试：直接使用该消息
    userMessage = message;
  } else {
    // AI消息重试：向前查找最近的用户消息
    let foundUser: ChatMessage | null = null;
    for (let i = msgIndex - 1; i >= 0; i--) {
      if (messages.value[i].messageType === 'human') {
        foundUser = messages.value[i];
        break;
      }
    }

    if (!foundUser) {
      Message.warning('未找到对应的用户消息');
      return;
    }
    userMessage = foundUser;
  }

  // 不删除消息，直接重新发送用户消息（后端也不会删除历史，保持一致）
  await handleSendMessage({
    message: userMessage.content,
    image: userMessage.imageBase64,
    imageDataUrl: userMessage.imageDataUrl,
    images: userMessage.imageBase64List,
    imageDataUrls: userMessage.imageDataUrls
  });
};

// 处理删除消息
const handleDeleteMessage = async (message: ChatMessage) => {
  const index = messages.value.findIndex(m =>
    m.content === message.content &&
    m.time === message.time &&
    m.messageType === message.messageType
  );

  if (index === -1) {
    Message.warning('未找到该消息');
    return;
  }

  // 计算后端存储的消息索引
  // 前端过滤掉了 system 消息，但后端存储的 checkpoint 中包含 system 消息（通常是第1条）
  // 因此需要在前端索引基础上加1来对应后端的实际索引
  const backendMessageTypes = ['human', 'ai', 'tool'];
  const frontendMessagesBeforeIndex = messages.value
    .slice(0, index)
    .filter(m => backendMessageTypes.includes(m.messageType || '')).length;
  // 后端通常有1条 system 消息在最开始，前端不显示但后端存储
  const backendMessagesBeforeIndex = frontendMessagesBeforeIndex + 1;

  const messagesAfter = messages.value.length - index - 1;
  const confirmContent = messagesAfter > 0
    ? `删除此消息将同时清除该消息之后的 ${messagesAfter} 条对话记录。是否继续？`
    : '确定要删除这条消息吗？';

  Modal.confirm({
    title: '确认删除',
    content: confirmContent,
    okText: '确认删除',
    cancelText: '取消',
    okButtonProps: {
      status: 'danger',
    },
    onOk: async () => {
      try {
        isLoading.value = true;

        // 1. 回滚后端历史记录（使用后端消息索引）
        if (sessionId.value && projectStore.currentProjectId) {
          const response = await rollbackChatHistory(
            sessionId.value,
            projectStore.currentProjectId,
            backendMessagesBeforeIndex  // 使用后端消息的索引
          );

          if (response.status !== 'success') {
            Message.warning('服务器回滚可能未完成，但本地消息已删除');
          }
        }

        // 2. 截断前端消息数组（删除该消息及之后的所有消息）
        messages.value = messages.value.slice(0, index);

        // 3. 如果删除后没有消息了
        if (messages.value.length === 0) {
          // 删除整个会话
          if (sessionId.value && projectStore.currentProjectId) {
            await deleteChatHistory(sessionId.value, projectStore.currentProjectId);
          }
          const oldSessionId = sessionId.value;
          sessionId.value = '';
          localStorage.removeItem('langgraph_session_id');
          chatSessions.value = chatSessions.value.filter(s => s.id !== oldSessionId);
          saveSessionsToStorage();
          Message.success('对话历史已清空');
        } else {
          Message.success('消息已删除');
        }
      } catch (error) {
        console.error('删除消息失败:', error);
        Message.error('删除消息失败，请稍后重试');
      } finally {
        safeStopLoading();
      }
    }
  });
};

// 添加或更新会话到列表
const updateSessionInList = (id: string, firstMessage?: string, updateTime: boolean = true) => {
  if (!id) {
    console.warn('updateSessionInList: session_id is empty, skipping');
    return;
  }

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
    console.log(`updateSessionInList: Updated existing session ${id}`);
  } else {
    // 添加新会话前，再次检查是否已存在（防止并发问题）
    const doubleCheckIndex = chatSessions.value.findIndex(s => s.id === id);
    if (doubleCheckIndex >= 0) {
      console.warn(`updateSessionInList: Session ${id} already exists, skipping duplicate addition`);
      return;
    }
    
    // 添加新会话
    chatSessions.value.unshift({
      id,
      title,
      lastTime: new Date(),
      messageCount: messages.value.length || 1
    });
    console.log(`updateSessionInList: Added new session ${id}`);
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
  // 🔧 修复：静默处理没有项目的情况（项目加载完成后 watch 会自动重新加载）
  if (!projectStore.currentProjectId) {
    console.log('⏳ 等待项目加载完成，暂不加载会话历史');
    return;
  }

  try {
    isLoading.value = true;
    const response = await getChatHistory(id, projectStore.currentProjectId);

    if (response.status === 'success' && response.data) {
      // 🆕 恢复该会话的Token使用信息
      if (response.data.context_token_count !== undefined) {
        const tokenCount = response.data.context_token_count || 0;
        const limit = response.data.context_limit || 128000;
        latestContextUsage.value[id] = { tokenCount, limit };
        console.log(`🔄 切换会话时恢复Token使用: ${tokenCount}/${limit}`);
      }

      // 🆕 恢复该会话关联的提示词
      if (response.data.prompt_id !== null && response.data.prompt_id !== undefined) {
        selectedPromptId.value = response.data.prompt_id;
        localStorage.setItem(PROMPT_STORAGE_KEY, String(response.data.prompt_id));
        console.log(`🔄 切换会话时恢复提示词: ${response.data.prompt_name} (ID: ${response.data.prompt_id})`);
      }

      // ✅ 使用纯函数处理历史记录,自动插入步骤分隔符
      const tempMessages = enrichMessagesWithSeparators(response.data.history, formatHistoryTime);
      
      // 🎨 合并连续的思考过程消息
      messages.value = mergeThinkingProcessMessages(tempMessages);

      // 更新会话信息（不更新时间，因为这是加载历史记录）
      updateSessionInList(id, undefined, false);
    } else {
      Message.error('加载会话历史失败');
    }
  } catch (error) {
    console.error('加载会话历史失败:', error);
    Message.error('加载会话历史失败');
  } finally {
    safeStopLoading();
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
        safeStopLoading();
      }
    },
  });
};

// 批量删除会话
const batchDeleteSessions = async (sessionIds: string[]) => {
  try {
    if (!projectStore.currentProjectId) {
      Message.error('没有选择项目，无法删除会话');
      return;
    }

    isLoading.value = true;
    const response = await batchDeleteChatHistory(sessionIds, projectStore.currentProjectId);

    if (response.status === 'success' && response.data) {
      const { processed_sessions, failed_sessions } = response.data;
      
      // 从列表中移除已删除的会话
      chatSessions.value = chatSessions.value.filter(s => !sessionIds.includes(s.id));
      saveSessionsToStorage();

      // 如果删除的包含当前会话，清除当前状态
      if (sessionIds.includes(sessionId.value)) {
        sessionId.value = '';
        localStorage.removeItem('langgraph_session_id');
        messages.value = [];
      }

      // 重新加载会话列表
      await loadSessionsFromServer();

      // 显示结果消息
      if (failed_sessions.length === 0) {
        Message.success(`成功删除 ${processed_sessions} 个对话`);
      } else {
        Message.warning(`删除完成：成功 ${processed_sessions - failed_sessions.length} 个，失败 ${failed_sessions.length} 个`);
      }
    } else {
      Message.error('批量删除对话失败');
    }
  } catch (error) {
    console.error('批量删除对话失败:', error);
    Message.error('批量删除对话失败，请稍后重试');
  } finally {
    safeStopLoading();
  }
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
        safeStopLoading();
      }
    },
  });
};

// 发送消息
const handleSendMessage = async (data: {
  message: string;
  image?: string;
  imageDataUrl?: string;
  images?: string[];
  imageDataUrls?: string[];
  quotedMessage?: ChatMessage | null;
}) => {
  const imageBase64List = data.images && data.images.length > 0
    ? data.images
    : (data.image ? [data.image] : []);
  const imageDataUrlList = data.imageDataUrls && data.imageDataUrls.length > 0
    ? data.imageDataUrls
    : (data.imageDataUrl ? [data.imageDataUrl] : []);
  const image = imageBase64List[0];
  const imageDataUrl = imageDataUrlList[0];
  const { message } = data;

  if (!message.trim() && imageBase64List.length === 0) {
    Message.warning('消息内容不能为空！');
    return;
  }

  if (!projectStore.currentProjectId) {
    Message.error('请先选择一个项目');
    return;
  }

  // 🔧 发送新消息前，先固化上一轮的流式内容（避免内容丢失）
  solidifyStreamContent();

  // 处理引用消息：将引用内容作为消息前缀
  let finalMessage = message;
  if (quotedMessage.value) {
    const quoteContent = quotedMessage.value.content.length > 200
      ? quotedMessage.value.content.slice(0, 200) + '...'
      : quotedMessage.value.content;
    finalMessage = `> ${quoteContent.replace(/\n/g, '\n> ')}\n\n${message}`;
    // 清除引用
    quotedMessage.value = null;
  }

  // 添加用户消息（保存图片数据以便显示）
  messages.value.push({
    content: finalMessage,
    isUser: true,
    time: getCurrentTime(),
    messageType: 'human',
    imageBase64: image, // 保存图片Base64数据（用于发送到后端）
    imageDataUrl: imageDataUrl, // 保存完整Data URL（用于前端显示）
    imageBase64List: imageBase64List,
    imageDataUrls: imageDataUrlList
  });

  isLoading.value = true;

  const requestData: ChatRequest = {
    message: finalMessage,
    session_id: sessionId.value || undefined,
    project_id: String(projectStore.currentProjectId), // 转换为string类型
  };
  
  // 如果有图片，添加到请求中
  if (imageBase64List.length > 0) {
    requestData.images = imageBase64List;
    if (imageBase64List.length === 1) {
      requestData.image = imageBase64List[0];
    }
  }

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
    // 流式模式（传递用户消息用于立即创建会话标题）
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

  // 如果当前会话有流（无论是否完成）
  if (stream) {
    // 🆕 检查是否需要补充用户消息（针对从其他页面跳转过来的情况）
    if (stream.userMessage && combined.length === 0) {
      combined.push({
        content: stream.userMessage,
        isUser: true,
        time: stream.userMessageTime || getCurrentTime(), // 使用会话创建时间
        messageType: 'human'
      });
    }

    // 检查最后一条消息是否已经包含了流式内容
    // 如果流已完成且内容已固化到 messages.value，则不需要再添加
    const lastMsg = combined[combined.length - 1];
    const contentAlreadyInMessages = lastMsg &&
      !lastMsg.isUser &&
      lastMsg.content === stream.content &&
      !lastMsg.isLoading;

    // 只有在内容尚未固化时才添加流式内容
    if (!contentAlreadyInMessages) {
      // 首先添加工具消息和 Agent Step 消息(如果有)
      if (stream.messages && stream.messages.length > 0) {
        stream.messages.forEach(msg => {
          const chatMsg: ChatMessage = {
            content: msg.content,
            isUser: false,
            time: msg.time,
            messageType: msg.type as ChatMessage['messageType'],
            toolName: msg.toolName,
            isExpanded: msg.isExpanded,
            imageDataUrl: msg.imageDataUrl,
            fileAttachments: msg.fileAttachments,
            isThinkingProcess: msg.isThinkingProcess,
            isThinkingExpanded: msg.isThinkingExpanded
          };

          // Agent Step 专用字段
          if (typeof msg.stepNumber === 'number') {
            chatMsg.stepNumber = msg.stepNumber;
          }
          if (typeof msg.maxSteps === 'number') {
            chatMsg.maxSteps = msg.maxSteps;
          }
          if (msg.stepStatus) {
            chatMsg.stepStatus = msg.stepStatus;
          }

          combined.push(chatMsg);
        });
      }

      // 然后处理AI消息
      if (stream.error) {
        // 如果有错误，显示错误消息
        combined.push({
          content: stream.error,
          isUser: false,
          time: getCurrentTime(),
          messageType: 'ai',
          isStreaming: false,
        });
      }
      else if (!stream.content || stream.content.trim() === '') {
        // 如果流式内容为空或只有空白字符，且流还未完成，显示加载中状态
        if (!stream.isComplete) {
          combined.push({
            content: '',
            isUser: false,
            time: getCurrentTime(),
            messageType: 'ai',
            isLoading: true,
          });
        }
      }
      else {
        // 有实际内容时，显示流式内容
        combined.push({
          content: stream.content,
          isUser: false,
          time: getCurrentTime(),
          messageType: 'ai',
          isStreaming: !stream.isComplete,
        });
      }
    }
  }
  return combined;
});

// 处理流式消息
const handleStreamMessage = async (requestData: ChatRequest, userMessage: string) => {
  abortController = new AbortController();
  const isNewSession = !sessionId.value;

  isLoading.value = true;

  // onStart 回调，在收到 session_id 后立即处理
  const handleStart = async (newSessionId: string) => {
    if (isNewSession) {
      sessionId.value = newSessionId;
      saveSessionId(newSessionId);
      console.log(`handleStart: New session created with id ${newSessionId}`);
      // 🔧 修复：立即创建会话并设置标题，不等流完成
      updateSessionInList(newSessionId, userMessage, true);
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

// 处理非流式消息（使用统一的 Agent Loop 接口）
const handleNormalMessage = async (requestData: ChatRequest, originalMessage: string) => {
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
    const response = await sendChatMessageNonStream(requestData);

    // 移除loading消息
    messages.value.splice(loadingMessageIndex, 1);

    if (response.status === 'success' && response.data) {
      const data = response.data;

      // 保存会话ID
      if (data.session_id) {
        saveSessionId(data.session_id);
        updateSessionInList(data.session_id, originalMessage, true);
      }

      // 更新 Token 使用信息
      if (data.context_token_count !== undefined && data.session_id) {
        latestContextUsage.value[data.session_id] = {
          tokenCount: data.context_token_count,
          limit: data.context_limit || 128000
        };
      }

      // 添加工具结果消息（如果有）
      if (data.tool_results && data.tool_results.length > 0) {
        for (const toolResult of data.tool_results) {
          const toolPayload = parseToolResultDisplayPayload(toolResult.tool_output || toolResult.summary);
          messages.value.push({
            content: toolPayload.content || toolResult.summary,
            isUser: false,
            time: getCurrentTime(),
            messageType: 'tool',
            toolName: toolResult.tool_name,
            imageDataUrl: toolPayload.imageDataUrl,
            fileAttachments: toolPayload.fileAttachments,
            isExpanded: false
          });
        }
      }

      // 添加 AI 回复
      if (data.content) {
        messages.value.push({
          content: data.content,
          isUser: false,
          time: getCurrentTime(),
          messageType: 'ai'
        });
      }

      // 处理 HITL 中断（如果有）
      if (data.interrupt) {
        // 初始化 activeStreams 以支持 HITL
        if (!activeStreams.value[data.session_id]) {
          activeStreams.value[data.session_id] = {
            content: data.content || '',
            isComplete: false,
            messages: [],
            isWaitingForApproval: true,
            interrupt: {
              id: data.interrupt.interrupt_id,
              interrupt_id: data.interrupt.interrupt_id,
              action_requests: data.interrupt.action_requests
            }
          };
        } else {
          activeStreams.value[data.session_id].isWaitingForApproval = true;
          activeStreams.value[data.session_id].interrupt = {
            id: data.interrupt.interrupt_id,
            interrupt_id: data.interrupt.interrupt_id,
            action_requests: data.interrupt.action_requests
          };
        }
        console.log('[LangGraphChatView] HITL interrupt received in non-stream mode:', data.interrupt);
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
    if (response.status === 'success' && response.data) {
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
  async (stream) => {
    if (stream && stream.isComplete) {
      // ⭐ HITL：如果正在等待审批，不触发流完成逻辑
      if (stream.isWaitingForApproval) {
        console.log(`⏸️ 会话 ${sessionId.value} 等待 HITL 审批，暂不处理流完成`);
        return;
      }

      console.log(`会话 ${sessionId.value} 的流已完成。`);

      const currentSessionId = sessionId.value;

      // 🔧 流完成后立即固化内容到messages.value，避免清理后内容丢失
      solidifyStreamContent();

      // 更新会话列表
      if (currentSessionId) {
        const existingSession = chatSessions.value.find(s => s.id === currentSessionId);
        if (!existingSession) {
          // 获取用户第一条消息作为标题
          const firstUserMsg = messages.value.find(m => m.isUser);
          if (firstUserMsg) {
            updateSessionInList(currentSessionId, firstUserMsg.content, true);
          }
        }
      }

      // 如果是通过本页面发送的消息，则需要在这里设置 isLoading = false
      if (isLoading.value) {
        isLoading.value = false;
      }
    }
  },
  { deep: true }
);

// 🔧 修复：监听项目ID变化，当项目加载完成后自动加载会话数据
watch(() => projectStore.currentProjectId, async (newProjectId, oldProjectId) => {
  console.log(`📊 项目ID变化: ${oldProjectId} -> ${newProjectId}`);
  
  if (newProjectId && newProjectId !== oldProjectId) {
    // 项目切换或首次加载完成
    console.log('🔄 项目已切换，重新加载会话数据...');
    
    // 只有在onMounted完成后才通过watch加载（避免重复）
    // 或者如果onMounted时没有项目，现在项目加载完成了，也需要加载
    if (isMountedLoadComplete || !oldProjectId) {
      await loadSessionsFromServer();
      await loadChatHistory();
    }
  } else if (!newProjectId && oldProjectId) {
    // 项目被清除
    console.log('⚠️ 项目已清除');
    messages.value = [];
    chatSessions.value = [];
    sessionId.value = '';
  }
});

watch([useKnowledgeBase, selectedKnowledgeBaseId, similarityThreshold, topK], () => {
  saveKnowledgeBaseSettings();
}, { deep: true });

watch(diagramPreviewVisible, (visible) => {
  if (!visible) {
    diagramPreviewReady.value = false;
  }
});

watch(htmlPreviewVisible, async (visible) => {
  if (!visible && document.fullscreenElement === htmlPreviewContainerRef.value) {
    try {
      await document.exitFullscreen();
    } catch (error) {
      console.error('退出HTML预览全屏失败:', error);
    }
  }
});

onMounted(async () => {
  window.addEventListener('message', handleDiagramPreviewMessage);
  document.addEventListener('fullscreenchange', syncHtmlPreviewFullscreenState);

  // ⭐加载保存的提示词ID
  loadSavedPromptId();
  
  // 加载知识库设置
  loadKnowledgeBaseSettings();
  
  // 🔧 修复：确保项目已选择
  // 如果没有当前项目，等待项目store加载完成
  if (!projectStore.currentProjectId) {
    console.log('⏳ 等待项目初始化...');
    // 尝试从projectStore加载项目列表
    if (projectStore.projectList.length === 0) {
      try {
        await projectStore.fetchProjects();
      } catch (error) {
        console.error('❌ 加载项目列表失败:', error);
      }
    }
    
    // 如果还是没有项目，提示用户
    // 注意：不直接return，因为watch会在项目加载后自动加载会话数据
    if (!projectStore.currentProjectId) {
      console.warn('⚠️ 没有选择项目，等待项目选择...');
      // 不显示提示，因为MainLayout会处理项目选择
    }
  }
  
  // 只有在有项目时才加载会话数据（避免watch中重复加载）
  if (projectStore.currentProjectId) {
    // 🔧 修复：先加载会话列表，再加载当前会话历史
    // 这样可以避免 loadChatHistory 中的 updateSessionInList 导致重复
    await loadSessionsFromServer();

    // 尝试加载当前会话的历史记录（只加载消息，不更新会话列表）
    await loadChatHistory();
  }

  // 加载当前LLM配置（不依赖项目）
  await loadCurrentLlmConfig();
  
  // 检查提示词状态（如果没有会自动弹出管理弹窗）
  await checkPromptStatus();
  
  // 标记onMounted完成
  isMountedLoadComplete = true;
});

// 监听 LLM 配置变化
watch(getRefreshTrigger(), async () => {
  console.log('🔄 检测到 LLM 配置变化,重新加载配置...');
  await loadCurrentLlmConfig();
}, { immediate: false });

onActivated(async () => {
  // 每次组件被激活时（从其他页面切回来）
  console.log('✅ Chat component activated.');

  // 0. 加载保存的提示词ID（从其他页面跳转时可能已更新）
  loadSavedPromptId();

  // 0.1 加载保存的知识库设置（从其他页面跳转时可能已更新）
  loadKnowledgeBaseSettings();

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

  // 5. 页面激活后滚动到最新消息
  await nextTick();
  chatMessagesRef.value?.scrollToBottom();
});

onUnmounted(() => {
  window.removeEventListener('message', handleDiagramPreviewMessage);
  document.removeEventListener('fullscreenchange', syncHtmlPreviewFullscreenState);
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
  min-height: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: #f7f8fa;
  overflow: hidden;
  position: relative;
}

.diagram-preview-iframe {
  width: 100%;
  height: 72vh;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  background: #fff;
}

.html-preview-wrapper {
  position: relative;
}

.html-preview-iframe {
  display: block;
}

.html-preview-fullscreen-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 2;
  border: 1px solid #d9dce3 !important;
  background-color: rgba(255, 255, 255, 0.95) !important;
}

/* 工具图片悬浮面板 */
.floating-tool-image-panel {
  position: absolute;
  top: 60px;
  right: 16px;
  z-index: 100;
  width: 320px;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  overflow: hidden;
  animation: float-in 0.25s ease;
}
@keyframes float-in {
  from { opacity: 0; transform: translateY(-12px) scale(0.95); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}
.floating-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background: #f2f3f5;
  border-bottom: 1px solid #e5e6eb;
  cursor: grab;
  user-select: none;
}
.floating-panel-header:active {
  cursor: grabbing;
}
.floating-panel-title {
  font-size: 12px;
  color: #4e5969;
  font-weight: 500;
}
.floating-panel-close {
  background: none;
  border: none;
  font-size: 18px;
  line-height: 1;
  color: #86909c;
  cursor: pointer;
  padding: 0 4px;
}
.floating-panel-close:hover {
  color: #1d2129;
}
.floating-panel-img {
  display: block;
  width: 100%;
  height: auto;
  max-height: 60vh;
  object-fit: contain;
  cursor: pointer;
}
</style>
