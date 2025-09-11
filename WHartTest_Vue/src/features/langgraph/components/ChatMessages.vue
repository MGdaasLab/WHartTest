<template>
  <div class="chat-messages" ref="messagesContainer">
    <div v-if="messages.length === 0" class="empty-chat">
      <div class="empty-icon">
        <icon-message />
      </div>
      <p>开始与 WHartTest 的对话吧</p>
    </div>

    <MessageItem
      v-for="(message, index) in messages"
      :key="index"
      :message="message"
      @toggle-expand="$emit('toggle-expand', $event)"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';
import { IconMessage } from '@arco-design/web-vue/es/icon';
import MessageItem from './MessageItem.vue';

interface ChatMessage {
  content: string;
  isUser: boolean;
  time: string;
  isLoading?: boolean;
  messageType?: 'human' | 'ai' | 'tool' | 'system'; // 🆕 添加 system 类型
  isExpanded?: boolean;
  isStreaming?: boolean;
}

interface Props {
  messages: ChatMessage[];
  isLoading: boolean;
}

const props = defineProps<Props>();

defineEmits<{
  'toggle-expand': [message: ChatMessage];
}>();

const messagesContainer = ref<HTMLElement | null>(null);

// 滚动到最新消息
const scrollToBottom = async () => {
  await nextTick();
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
};

// 监听消息数量变化，自动滚动（只在添加新消息时滚动，不在消息属性变化时滚动）
watch(() => props.messages.length, () => {
  scrollToBottom();
});

// 监听流式消息内容变化，自动滚动
watch(() => {
  // 找到最后一条正在流式输出的消息
  const lastMessage = props.messages[props.messages.length - 1];
  if (lastMessage && lastMessage.isStreaming && lastMessage.messageType === 'ai') {
    return lastMessage.content;
  }
  return null;
}, (newContent) => {
  // 只有当内容确实发生变化时才滚动
  if (newContent !== null) {
    scrollToBottom();
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
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background-color: #f2f3f5;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.empty-icon .arco-icon {
  font-size: 32px;
  color: #c9cdd4;
}
</style>
