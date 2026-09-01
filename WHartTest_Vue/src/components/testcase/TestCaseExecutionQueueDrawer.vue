<template>
  <a-drawer
    v-model:visible="visible"
    :title="tl('用例执行任务队列')"
    :width="540"
    :footer="false"
    class="execution-queue-drawer"
  >
    <template #header>
      <div class="drawer-header-custom">
        <div class="header-left">
          <span class="drawer-title">{{ tl('用例执行任务队列') }}</span>
          <a-badge :count="runningTasksCount" :dot="false" status="processing" v-if="runningTasksCount > 0" />
        </div>
        <div class="header-stats">
          <a-tag color="blue" size="small">{{ tl('进行中') }}: {{ runningTasksCount }}</a-tag>
          <a-tag color="green" size="small">{{ tl('成功') }}: {{ successTasksCount }}</a-tag>
          <a-tag color="red" size="small">{{ tl('失败') }}: {{ failedTasksCount }}</a-tag>
          <a-button
            type="text"
            size="mini"
            status="danger"
            @click="clearCompletedTasks"
            :disabled="tasks.length === 0 || runningTasksCount === tasks.length"
          >
            {{ tl('清空已完成') }}
          </a-button>
        </div>
      </div>
    </template>

    <div v-if="tasks.length === 0" class="empty-container">
      <a-empty :description="tl('当前暂无用例执行任务')">
        <template #image>
          <icon-schedule style="font-size: 48px; color: var(--color-text-4);" />
        </template>
      </a-empty>
    </div>

    <div v-else class="task-list">
      <div
        v-for="task in tasks"
        :key="task.id"
        class="task-card"
        :class="`task-card-${task.status}`"
      >
        <!-- 头部信息 -->
        <div class="task-card-header">
          <div class="task-title-wrap">
            <span class="task-case-name" :title="task.testCaseName">
              {{ task.testCaseName }}
            </span>
            <a-tag v-if="task.moduleName" size="small" color="arcoblue" class="module-tag">
              {{ task.moduleName }}
            </a-tag>
          </div>
          <div class="task-status-tag">
            <a-tag v-if="task.status === 'running'" color="arcoblue" size="small">
              <template #icon><icon-loading spin /></template>
              {{ tl('执行中') }}
            </a-tag>
            <a-tag v-else-if="task.status === 'diagnosing'" color="orange" size="small">
              <template #icon><icon-sync spin /></template>
              {{ tl('AI诊断中') }}
            </a-tag>
            <a-tag v-else-if="task.status === 'success'" color="green" size="small">
              <template #icon><icon-check-circle-fill /></template>
              {{ tl('执行通过') }}
            </a-tag>
            <a-tag v-else-if="task.status === 'failed'" color="red" size="small">
              <template #icon><icon-close-circle-fill /></template>
              {{ tl('执行失败') }}
            </a-tag>
            <a-tag v-else color="gray" size="small">{{ tl('排队中') }}</a-tag>
          </div>
        </div>

        <!-- 模式与时间 -->
        <div class="task-meta">
          <a-space size="small">
            <a-tag size="small" :color="getModeColor(task.executionMode)">
              {{ getModeLabel(task.executionMode) }}
            </a-tag>
            <span class="meta-time">
              {{ formatTime(task.startTime) }}
            </span>
            <span v-if="task.duration !== undefined" class="meta-duration">
              {{ tl('耗时') }}: {{ task.duration }}s
            </span>
          </a-space>
          <a-button
            type="text"
            size="mini"
            status="danger"
            @click="removeTask(task.id)"
            :disabled="task.status === 'running' || task.status === 'diagnosing'"
          >
            <template #icon><icon-delete /></template>
          </a-button>
        </div>

        <!-- 当前步骤与进度条 -->
        <div class="task-progress-section">
          <div class="progress-info">
            <span class="step-desc" :title="task.currentStepDesc">
              {{ task.currentStepDesc }}
            </span>
            <span class="step-ratio" v-if="task.totalSteps > 0">
              {{ (task.status === 'success' ? task.totalSteps : task.currentStepIndex) }}/{{ task.totalSteps }}
            </span>
          </div>
          <a-progress
            :percent="calcPercent(task)"
            :status="getProgressStatus(task.status)"
            :show-text="false"
            size="small"
          />
        </div>

        <!-- 错误信息提示 -->
        <div v-if="task.errorMessage" class="task-error-box">
          <icon-exclamation-circle-fill class="error-icon" />
          <span class="error-text">{{ task.errorMessage }}</span>
        </div>

        <!-- 日志与操作栏 -->
        <div class="task-card-footer">
          <a-button
            type="text"
            size="mini"
            @click="toggleLogs(task.id)"
          >
            <template #icon>
              <icon-down :style="{ transform: expandedLogs[task.id] ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }" />
            </template>
            {{ expandedLogs[task.id] ? tl('收起日志') : tl('查看执行日志') }} ({{ task.logs.length }})
          </a-button>

          <div class="footer-actions">
            <!-- 打开 AI 自愈对话按钮 -->
            <a-button
              v-if="task.status === 'failed' || task.status === 'diagnosing'"
              type="primary"
              size="mini"
              status="success"
              @click="handleOpenAiChat"
            >
              <template #icon><icon-message /></template>
              {{ tl('打开 AI 自愈对话') }}
            </a-button>

            <!-- AI 诊断查看按钮 -->
            <a-button
              v-if="task.status === 'failed'"
              type="outline"
              size="mini"
              status="warning"
              @click="handleViewAiDiagnosis(task)"
            >
              <template #icon><icon-robot /></template>
              {{ tl('查看诊断报告') }}
            </a-button>
          </div>
        </div>

        <!-- 折叠日志内容 -->
        <div v-if="expandedLogs[task.id]" class="task-logs-container">
          <div
            v-for="(log, idx) in task.logs"
            :key="idx"
            class="log-item"
            :class="`log-${log.type || 'info'}`"
          >
            <span class="log-time">[{{ log.time }}]</span>
            <span class="log-msg">{{ log.message }}</span>
          </div>
        </div>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useAppI18n } from '@/composables/useAppI18n';
import {
  useTestCaseExecutionQueue,
  type ExecutionTask,
} from '@/composables/useTestCaseExecutionQueue';
import {
  IconLoading,
  IconSync,
  IconCheckCircleFill,
  IconCloseCircleFill,
  IconExclamationCircleFill,
  IconDown,
  IconDelete,
  IconRobot,
  IconSchedule,
  IconMessage,
} from '@arco-design/web-vue/es/icon';
import { useRouter } from 'vue-router';

const props = defineProps<{
  modelValue: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void;
  (e: 'viewDiagnosis', task: ExecutionTask): void;
}>();

const router = useRouter();
const { isEnglish, tl } = useAppI18n();
const {
  tasks,
  runningTasksCount,
  successTasksCount,
  failedTasksCount,
  removeTask,
  clearCompletedTasks,
} = useTestCaseExecutionQueue();

const handleOpenAiChat = () => {
  router.push({ name: 'LangGraphChat' });
};

const visible = computed({
  get: () => props.modelValue,
  set: (val: boolean) => emit('update:modelValue', val),
});

const expandedLogs = ref<Record<string, boolean>>({});

const toggleLogs = (taskId: string) => {
  expandedLogs.value[taskId] = !expandedLogs.value[taskId];
};

const getModeLabel = (mode: ExecutionTask['executionMode']) => {
  switch (mode) {
    case 'hybrid':
      return '智能双模';
    case 'script_only':
      return '原生脚本';
    case 'ai_only':
      return '纯AI探索';
    default:
      return '智能执行';
  }
};

const getModeColor = (mode: ExecutionTask['executionMode']) => {
  switch (mode) {
    case 'hybrid':
      return 'cyan';
    case 'script_only':
      return 'blue';
    case 'ai_only':
      return 'orangered';
    default:
      return 'gray';
  }
};

const getProgressStatus = (status: ExecutionTask['status']) => {
  switch (status) {
    case 'success':
      return 'success';
    case 'failed':
      return 'danger';
    case 'running':
    case 'diagnosing':
      return 'normal';
    default:
      return 'normal';
  }
};

const calcPercent = (task: ExecutionTask) => {
  if (task.status === 'success') return 1;
  if (task.status === 'failed') return Math.min(Math.max((task.currentStepIndex || 0) / (task.totalSteps || 1), 0.05), 1);
  if (!task.totalSteps || task.totalSteps === 0) return 0.3;
  return Math.min(Math.max(task.currentStepIndex / task.totalSteps, 0.05), 0.95);
};

const formatTime = (timestamp: number) => {
  const date = new Date(timestamp);
  return date.toLocaleTimeString();
};

const handleViewAiDiagnosis = (task: ExecutionTask) => {
  emit('viewDiagnosis', task);
};
</script>

<style scoped>
.drawer-header-custom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.drawer-title {
  font-size: 16px;
  font-weight: 600;
}

.header-stats {
  display: flex;
  align-items: center;
  gap: 6px;
}

.clear-btn {
  color: var(--color-text-3);
  font-size: 13px;
}

.clear-btn:hover {
  color: var(--color-danger-light-4);
}

.empty-wrap {
  padding: 40px 0;
  text-align: center;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 20px;
}

.task-card {
  border: 1px solid var(--color-border-2);
  border-radius: 8px;
  padding: 12px 14px;
  background: var(--color-bg-2);
  transition: all 0.2s ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.task-card-running {
  border-color: var(--color-primary-light-3);
  background: var(--color-primary-light-1);
}

.task-card-diagnosing {
  border-color: var(--color-warning-light-3);
  background: var(--color-warning-light-1);
}

.task-card-success {
  border-color: var(--color-success-light-3);
}

.task-card-failed {
  border-color: var(--color-danger-light-3);
}

.task-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.task-title-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  max-width: 75%;
}

.task-case-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.module-tag {
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.meta-time,
.meta-duration {
  font-size: 12px;
  color: var(--color-text-3);
}

.task-progress-section {
  margin-bottom: 8px;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
  font-size: 12px;
}

.step-desc {
  color: var(--color-text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 80%;
}

.step-ratio {
  color: var(--color-text-3);
  font-weight: 500;
}

.task-error-box {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: var(--color-danger-light-1);
  border: 1px solid var(--color-danger-light-2);
  border-radius: 4px;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--color-danger-text);
}

.error-icon {
  flex-shrink: 0;
  color: rgb(var(--danger-6));
}

.error-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 4px;
}

.footer-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.task-logs-container {
  margin-top: 8px;
  padding: 8px 10px;
  background: var(--color-fill-2);
  border-radius: 4px;
  font-size: 11px;
  font-family: monospace;
  max-height: 140px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.log-item {
  display: flex;
  gap: 6px;
  line-height: 1.4;
}

.log-time {
  color: var(--color-text-4);
  flex-shrink: 0;
}

.log-msg {
  color: var(--color-text-2);
  word-break: break-all;
}

.log-error .log-msg {
  color: rgb(var(--danger-6));
}

.log-success .log-msg {
  color: rgb(var(--success-6));
}

.log-warning .log-msg {
  color: rgb(var(--warning-6));
}
</style>
