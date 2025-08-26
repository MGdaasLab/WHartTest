<template>
  <div class="chat-input-container">
    <div class="input-wrapper">
      <a-textarea
        v-model="inputMessage"
        placeholder="请输入你的消息... (Shift+Enter换行，Enter发送)"
        :disabled="isLoading"
        class="chat-input"
        :auto-size="{ minRows: 1, maxRows: 6 }"
        @keydown="handleKeyDown"
      />
      <a-button
        type="primary"
        :loading="isLoading"
        class="send-button"
        @click="handleSendMessage"
      >
        <i class="icon-send"></i>
        <span v-if="!isLoading">发送</span>
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { Textarea as ATextarea, Button as AButton, Message } from '@arco-design/web-vue';

interface Props {
  isLoading: boolean;
}

defineProps<Props>();

const emit = defineEmits<{
  'send-message': [message: string];
}>();

const inputMessage = ref('');

const handleSendMessage = () => {
  const message = inputMessage.value.trim();
  if (!message) {
    Message.warning('消息内容不能为空！');
    return;
  }

  emit('send-message', message);
  inputMessage.value = '';
};

// 处理键盘事件
const handleKeyDown = (event: KeyboardEvent) => {
  // Enter键发送消息，Shift+Enter换行
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault(); // 阻止默认的换行行为
    handleSendMessage();
  }
  // Shift+Enter允许换行，不做任何处理，让默认行为发生
};
</script>

<style scoped>
.chat-input-container {
  padding: 16px 20px;
  background-color: white;
  border-top: 1px solid #e5e6eb;
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  width: 100%;
  gap: 8px;
}

.chat-input {
  flex: 1;
  border-radius: 12px;
  background-color: #f2f3f5;
  transition: all 0.2s;
  resize: none;
}

.chat-input:hover, .chat-input:focus {
  background-color: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* 确保文本框内容样式正确 */
.chat-input :deep(.arco-textarea) {
  border-radius: 12px;
  padding: 8px 12px;
  line-height: 1.5;
}

.send-button {
  display: flex;
  align-items: center;
  border-radius: 20px;
  padding: 0 16px;
  height: 36px;
  flex-shrink: 0;
}

.icon-send {
  margin-right: 4px;
  font-size: 16px;
}
</style>
