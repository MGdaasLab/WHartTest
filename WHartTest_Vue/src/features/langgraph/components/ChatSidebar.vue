<template>
  <div class="chat-sidebar">
    <div class="sidebar-header">
      <h2 class="sidebar-title">历史对话</h2>
      <a-button type="text" @click="$emit('create-new-chat')">
        <template #icon>
          <icon-plus />
        </template>
        新对话
      </a-button>
    </div>

    <div class="chat-history-list">
      <div v-if="sessions.length === 0" class="empty-history">
        暂无历史对话
      </div>
      <div
        v-for="session in sessions"
        :key="session.id"
        :class="['chat-history-item', session.id === currentSessionId ? 'active' : '']"
        @click="$emit('switch-session', session.id)"
      >
        <div class="history-item-content">
          <icon-message class="history-item-icon" />
          <div class="history-item-info">
            <div class="history-item-title">{{ session.title || '未命名对话' }}</div>
            <div class="history-item-time">{{ formatTime(session.lastTime) }}</div>
          </div>
        </div>
        <div class="history-item-actions">
          <a-button type="text" size="mini" @click.stop="$emit('delete-session', session.id)">
            <template #icon>
              <icon-delete style="color: #f53f3f;" />
            </template>
          </a-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Button as AButton } from '@arco-design/web-vue';
import { IconPlus, IconDelete, IconMessage } from '@arco-design/web-vue/es/icon';

interface ChatSession {
  id: string;
  title: string;
  lastTime: Date;
  messageCount: number;
}

interface Props {
  sessions: ChatSession[];
  currentSessionId: string;
  isLoading: boolean;
}

defineProps<Props>();

defineEmits<{
  'create-new-chat': [];
  'switch-session': [id: string];
  'delete-session': [id: string];
}>();

// 格式化时间显示
const formatTime = (date: Date) => {
  // 确保传入的是有效的 Date 对象
  if (!date || !(date instanceof Date) || isNaN(date.getTime())) {
    return '时间未知';
  }

  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (date >= today) {
    return `今天 ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
  } else if (date >= yesterday) {
    return `昨天 ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
  } else {
    return `${date.getMonth() + 1}月${date.getDate()}日 ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
  }
};
</script>

<style scoped>
.chat-sidebar {
  width: 280px;
  background-color: #ffffff;
  border-right: 1px solid #e5e6eb;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #e5e6eb;
}

.sidebar-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.chat-history-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.empty-history {
  padding: 16px;
  color: #86909c;
  text-align: center;
}

.chat-history-item {
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: background-color 0.2s;
}

.chat-history-item:hover {
  background-color: #f2f3f5;
}

.chat-history-item.active {
  background-color: #e8f3ff;
}

.history-item-content {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
}

.history-item-icon {
  font-size: 16px;
  color: #4e5969;
  margin-right: 8px;
}

.history-item-info {
  flex: 1;
  min-width: 0;
}

.history-item-title {
  font-size: 14px;
  font-weight: 500;
  color: #1d2129;
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-item-time {
  font-size: 12px;
  color: #86909c;
}

.history-item-actions {
  opacity: 0;
  transition: opacity 0.2s;
}

.chat-history-item:hover .history-item-actions {
  opacity: 1;
}
</style>
