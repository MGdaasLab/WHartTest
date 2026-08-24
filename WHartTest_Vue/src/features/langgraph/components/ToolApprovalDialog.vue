<template>
  <a-modal
    :visible="props.visible"
    :mask-closable="false"
    :closable="false"
    :footer="false"
    width="520px"
    modal-class="tool-approval-modal"
    @cancel="handleReject"
  >
    <div class="approval-container">
      <!-- 顶部警告区域 -->
      <div class="approval-header">
        <div class="warning-icon">
          <icon-exclamation-circle-fill />
        </div>
        <div class="header-content">
          <h3 class="title">{{ dialogText.title }}</h3>
          <p class="subtitle">{{ dialogText.subtitle }}</p>
        </div>
      </div>

      <!-- 工具信息卡片 -->
      <div class="tool-card">
        <div class="tool-header">
          <div class="tool-icon">
            <icon-code />
          </div>
          <div class="tool-meta">
            <span class="tool-name">{{ actionRequest?.name }}</span>
            <span class="tool-badge" v-if="actionRequest?.description">
              {{ actionRequest.description.replace('⚠️ ', '') }}
            </span>
          </div>
        </div>

        <div class="tool-args" v-if="actionRequest?.args && Object.keys(actionRequest.args).length">
          <div class="args-label">
            <icon-command /> {{ dialogText.executionArgs }}
          </div>
          <div class="args-content">
            <pre>{{ formatArgs(actionRequest.args) }}</pre>
          </div>
        </div>
      </div>

      <!-- 记住选择 -->
      <div class="remember-section">
        <a-checkbox v-model="rememberChoice">
          <span class="remember-text">{{ dialogText.rememberChoice }}</span>
        </a-checkbox>
        <a-select
          v-if="rememberChoice"
          v-model="rememberScope"
          size="small"
          :style="{ width: '120px', marginLeft: '12px' }"
          :options="scopeOptions"
        />
      </div>

      <!-- 操作按钮 -->
      <div class="action-buttons">
        <a-button
          size="large"
          class="btn-reject"
          @click="handleReject"
          :loading="loading"
        >
          <template #icon><icon-close /></template>
          {{ dialogText.rejectExecution }}
        </a-button>
        <a-button
          type="primary"
          size="large"
          class="btn-approve"
          @click="handleApprove"
          :loading="loading"
        >
          <template #icon><icon-check /></template>
          {{ dialogText.approveExecution }}
        </a-button>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { Message } from '@arco-design/web-vue';
import { saveToolApproval } from '@/features/langgraph/services/toolApprovalService';
import type { ApprovalScope } from '@/features/langgraph/types/toolApproval';
import { useAppI18n } from '@/composables/useAppI18n';

/** 工具调用请求 */
export interface ActionRequest {
  name: string;
  args: Record<string, unknown>;
  description?: string;
  auto_reject?: boolean;
}

/** Interrupt 事件 */
export interface InterruptEvent {
  id: string;
  interrupt_id?: string;
  action_requests: ActionRequest[];
}

const props = defineProps<{
  visible: boolean;
  interrupt?: InterruptEvent | null;
  sessionId?: string;
}>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'decision', decision: {
    interruptId: string;
    type: 'approve' | 'reject';
    rememberChoice?: boolean;
    rememberScope?: ApprovalScope;
    toolName?: string;
  }): void;
}>();

const { isEnglish } = useAppI18n();
const loading = ref(false);
const rememberChoice = ref(false);
const rememberScope = ref<ApprovalScope>('permanent');

const dialogText = computed(() => (
  isEnglish.value
    ? {
        title: 'Tool Execution Approval',
        subtitle: 'The following action requires your approval before execution',
        executionArgs: 'Execution Arguments',
        rememberChoice: 'Remember this choice',
        rejectExecution: 'Reject',
        approveExecution: 'Allow',
        scopeSession: 'This Session Only',
        scopePermanent: 'Always Apply',
        setAlwaysAllow: (name: string) => `${name} is now always allowed`,
        setAlwaysReject: (name: string) => `${name} is now always rejected`,
        operationFailed: (reason?: string) => `Operation failed: ${reason || 'Unknown error'}`,
      }
    : {
        title: '工具执行审批',
        subtitle: '以下操作需要您的确认后才能执行',
        executionArgs: '执行参数',
        rememberChoice: '记住此选择',
        rejectExecution: '拒绝执行',
        approveExecution: '允许执行',
        scopeSession: '仅本次会话',
        scopePermanent: '永久生效',
        setAlwaysAllow: (name: string) => `已设置 ${name} 为始终允许`,
        setAlwaysReject: (name: string) => `已设置 ${name} 为始终拒绝`,
        operationFailed: (reason?: string) => `操作失败: ${reason || '未知错误'}`,
      }
));

const scopeOptions = computed(() => ([
  { label: dialogText.value.scopeSession, value: 'session' },
  { label: dialogText.value.scopePermanent, value: 'permanent' },
]));

// 当前操作请求（取第一个）
const actionRequest = computed(() => {
  return props.interrupt?.action_requests?.[0] || null;
});

// 格式化参数显示
const formatArgs = (args: Record<string, unknown>) => {
  try {
    return JSON.stringify(args, null, 2);
  } catch {
    return String(args);
  }
};

// 重置状态
watch(() => props.visible, (val) => {
  if (val) {
    rememberChoice.value = false;
    rememberScope.value = 'permanent';
    loading.value = false;
  }
});

// 处理允许
const handleApprove = async () => {
  if (!props.interrupt || !actionRequest.value) return;

  loading.value = true;

  try {
    // 如果选择了"记住此选择"，保存偏好
    if (rememberChoice.value && actionRequest.value.name) {
      await saveToolApproval(
        actionRequest.value.name,
        'always_allow',
        rememberScope.value,
        props.sessionId
      );
      Message.success(dialogText.value.setAlwaysAllow(actionRequest.value.name));
    }

    emit('decision', {
      interruptId: props.interrupt.id,
      type: 'approve',
      rememberChoice: rememberChoice.value,
      rememberScope: rememberScope.value,
      toolName: actionRequest.value.name,
    });
    emit('update:visible', false);
  } catch (error: any) {
    Message.error(dialogText.value.operationFailed(error.message));
  } finally {
    loading.value = false;
  }
};

// 处理拒绝
const handleReject = async () => {
  if (!props.interrupt || !actionRequest.value) {
    emit('update:visible', false);
    return;
  }

  loading.value = true;

  try {
    // 如果选择了"记住此选择"，保存偏好
    if (rememberChoice.value && actionRequest.value.name) {
      await saveToolApproval(
        actionRequest.value.name,
        'always_reject',
        rememberScope.value,
        props.sessionId
      );
      Message.info(dialogText.value.setAlwaysReject(actionRequest.value.name));
    }

    emit('decision', {
      interruptId: props.interrupt.id,
      type: 'reject',
      rememberChoice: rememberChoice.value,
      rememberScope: rememberScope.value,
      toolName: actionRequest.value.name,
    });
    emit('update:visible', false);
  } catch (error: any) {
    Message.error(dialogText.value.operationFailed(error.message));
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.approval-container {
  padding: 4px;
}

/* 顶部警告区域 */
.approval-header {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
}

.warning-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(135deg, color-mix(in srgb, var(--theme-surface) 84%, rgba(var(--theme-accent-rgb), 0.14)) 0%, color-mix(in srgb, var(--theme-shell-soft) 82%, rgba(var(--theme-accent-rgb), 0.2)) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.warning-icon :deep(svg) {
  font-size: 28px;
  color: var(--theme-accent);
}

.header-content {
  flex: 1;
}

.title {
  margin: 0 0 4px 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-1);
}

.subtitle {
  margin: 0;
  font-size: 14px;
  color: var(--color-text-3);
}

/* 工具信息卡片 */
.tool-card {
  background: linear-gradient(135deg, #f7f8fa 0%, #f2f3f5 100%);
  border: 1px solid var(--color-border-2);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
}

.tool-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.tool-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: linear-gradient(135deg, #165dff 0%, #0e42d2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.tool-icon :deep(svg) {
  font-size: 18px;
  color: #fff;
}

.tool-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tool-name {
  font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-1);
}

.tool-badge {
  font-size: 12px;
  color: var(--color-text-3);
}

/* 参数区域 */
.tool-args {
  background: var(--color-bg-2);
  border-radius: 8px;
  overflow: hidden;
}

.args-label {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-2);
  background: var(--color-fill-2);
  border-bottom: 1px solid var(--color-border-2);
}

.args-label :deep(svg) {
  font-size: 14px;
}

.args-content {
  padding: 12px;
  max-height: 180px;
  overflow-y: auto;
}

.args-content pre {
  margin: 0;
  font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-text-2);
  white-space: pre-wrap;
  word-break: break-word;
}

/* 记住选择 */
.remember-section {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  background: var(--color-fill-1);
  border-radius: 8px;
  margin-bottom: 20px;
}

.remember-text {
  font-size: 14px;
  color: var(--color-text-2);
}

/* 操作按钮 */
.action-buttons {
  display: flex;
  gap: 12px;
}

.btn-reject {
  flex: 1;
  border-color: var(--color-border-3);
  color: var(--color-text-2);
}

.btn-reject:hover {
  border-color: #f53f3f;
  color: #f53f3f;
  background: #fff1f0;
}

.btn-approve {
  flex: 1;
  background: linear-gradient(135deg, #00b42a 0%, #009a29 100%);
  border: none;
}

.btn-approve:hover {
  background: linear-gradient(135deg, #23c343 0%, #00b42a 100%);
}
</style>

<style>
/* 全局样式覆盖 Modal */
.tool-approval-modal .arco-modal-header {
  display: none;
}

.tool-approval-modal .arco-modal-body {
  padding: 24px;
}
</style>
