<template>
  <div class="chat-messages" ref="messagesContainer">
    <div v-if="messages.length === 0" class="empty-chat">
      <div class="empty-icon">
        <img :src="brandLogoUrl" alt="" class="empty-logo" />
      </div>
      <p>开始与 WHartTest 的对话吧</p>
    </div>

    <MessageItem
      v-for="(message, index) in messages"
      :key="index"
      :message="message"
      :floating-tool-image-src="floatingToolImageSrc"
      @toggle-expand="$emit('toggle-expand', $event)"
      @quote="$emit('quote', $event)"
      @retry="$emit('retry', $event)"
      @delete="$emit('delete', $event)"
      @preview-diagram="$emit('preview-diagram', $event)"
      @preview-html="$emit('preview-html', $event)"
      @tool-image-detected="$emit('tool-image-detected', $event)"
      @float-tool-image="$emit('float-tool-image', $event)"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue';
import MessageItem from './MessageItem.vue';
import { brandLogoUrl } from '@/utils/assetUrl';
import type { ToolFileAttachment } from '@/features/langgraph/utils/toolResultParser';

interface ChatMessage {
  content: string;
  isUser: boolean;
  time: string;
  isLoading?: boolean;
  messageType?: 'human' | 'ai' | 'tool' | 'system' | 'agent_step' | 'step_separator';
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
  // Step Separator 专用字段
  isStepSeparator?: boolean;
}

interface Props {
  messages: ChatMessage[];
  isLoading: boolean;
  floatingToolImageSrc?: string | null;
}

const props = withDefaults(defineProps<Props>(), {
  floatingToolImageSrc: null,
});

defineEmits<{
  'toggle-expand': [message: ChatMessage];
  'quote': [message: ChatMessage];
  'retry': [message: ChatMessage];
  'delete': [message: ChatMessage];
  'preview-diagram': [payload: { xml: string; sourceMessage: ChatMessage }];
  'preview-html': [payload: { html: string; sourceMessage: ChatMessage }];
  'tool-image-detected': [src: string];
  'float-tool-image': [src: string];
}>();

const messagesContainer = ref<HTMLElement | null>(null);
const userIsScrolling = ref(false); // 用户是否正在查看历史消息
let scrollTimeout: number | null = null;

// 检测用户是否在底部附近
const isNearBottom = (): boolean => {
  if (!messagesContainer.value) return true;
  const { scrollTop, scrollHeight, clientHeight } = messagesContainer.value;
  // 如果距离底部小于100px，认为用户在底部
  return scrollHeight - scrollTop - clientHeight < 100;
};

// 滚动到最新消息
const scrollToBottom = async () => {
  await nextTick();
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
};

// 处理滚动事件
const handleScroll = () => {
  // 检测用户是否在底部
  const nearBottom = isNearBottom();
  userIsScrolling.value = !nearBottom;
  
  // 清除之前的定时器
  if (scrollTimeout !== null) {
    clearTimeout(scrollTimeout);
  }
  
  // 如果用户滚动到底部附近，恢复自动滚动
  if (nearBottom) {
    scrollTimeout = window.setTimeout(() => {
      userIsScrolling.value = false;
    }, 150);
  }
};

// 监听消息数量变化，只在用户未主动滚动时自动滚动
watch(() => props.messages.length, () => {
  if (!userIsScrolling.value) {
    scrollToBottom();
  }
});

// 监听流式消息内容变化，只在用户未主动滚动时自动滚动
watch(() => {
  // 找到最后一条正在流式输出的消息
  const lastMessage = props.messages[props.messages.length - 1];
  if (lastMessage && lastMessage.isStreaming && lastMessage.messageType === 'ai') {
    return lastMessage.content;
  }
  return null;
}, (newContent) => {
  // 只有当内容确实发生变化且用户未主动滚动时才滚动
  if (newContent !== null && !userIsScrolling.value) {
    scrollToBottom();
  }
});

// 组件挂载时添加滚动监听
onMounted(() => {
  if (messagesContainer.value) {
    messagesContainer.value.addEventListener('scroll', handleScroll);
  }
});

// 组件卸载时移除滚动监听
onUnmounted(() => {
  if (messagesContainer.value) {
    messagesContainer.value.removeEventListener('scroll', handleScroll);
  }
  if (scrollTimeout !== null) {
    clearTimeout(scrollTimeout);
  }
});

// 暴露滚动方法给父组件
defineExpose({
  scrollToBottom
});
</script>

<style scoped>
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.empty-chat {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #86909c;
}

.empty-icon {
  width: 72px;
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.empty-logo {
  width: 72px;
  height: 72px;
  object-fit: contain;
  filter: drop-shadow(0 0 20px rgba(100, 180, 255, 0.18));
}
</style>
