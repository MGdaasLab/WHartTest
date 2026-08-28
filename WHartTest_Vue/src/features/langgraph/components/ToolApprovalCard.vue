<template>
  <Transition name="slide-up">
    <div v-if="visible && actionRequest" class="approval-card">
      <div class="card-content">
        <!-- 左侧：工具信息 -->
        <div class="tool-section">
          <div class="tool-icon">
            <icon-thunderbolt />
          </div>
          <div class="tool-info">
            <div class="tool-header">
              <span class="tool-name">{{ actionRequest.name }}</span>
              <span class="approval-badge">{{ text.needsApproval }}</span>
            </div>
          </div>
        </div>

        <!-- 右侧：操作按钮 -->
        <div class="action-section">
          <div class="remember-option">
            <a-select
              v-model="rememberPolicy"
              size="small"
              :style="{ width: '110px' }"
              :options="policyOptions"
            />
          </div>
          <div class="action-buttons">
            <a-button
              size="small"
              class="btn-reject"
              @click="handleReject"
              :loading="loading"
            >
              <template #icon><icon-close /></template>
              {{ text.reject }}
            </a-button>
            <a-button
              type="primary"
              size="small"
              class="btn-approve"
              @click="handleApprove"
              :loading="loading"
            >
              <template #icon><icon-check /></template>
              {{ text.allow }}
            </a-button>
          </div>
        </div>
      </div>

      <!-- 展开的参数详情 -->
      <Transition name="expand">
        <div v-if="showDetails && hasArgs" class="args-detail">
          <div class="args-list">
            <div
              v-for="(value, key) in actionRequest?.args"
              :key="key"
              class="arg-item"
            >
              <span class="arg-key">{{ key }}</span>
              <span class="arg-value" :class="getValueType(value)">
                {{ formatValue(value) }}
              </span>
            </div>
          </div>
        </div>
      </Transition>

      <!-- 展开/收起按钮 -->
      <button
        v-if="hasArgs"
        class="toggle-detail"
        @click="showDetails = !showDetails"
      >
        <icon-down v-if="!showDetails" />
        <icon-up v-else />
        {{ showDetails ? text.collapseArgs : text.viewArgs }}
      </button>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { Message } from '@arco-design/web-vue';
import { IconThunderbolt, IconDown, IconUp, IconCheck, IconClose } from '@arco-design/web-vue/es/icon';
import { saveToolApproval } from '@/features/langgraph/services/toolApprovalService';
import type { ApprovalScope } from '@/features/langgraph/types/toolApproval';
import { useAppI18n } from '@/composables/useAppI18n';

export interface ActionRequest {
  name: string;
  args: Record<string, unknown>;
  description?: string;
  auto_reject?: boolean;
}

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

const loading = ref(false);
const rememberPolicy = ref<'ask' | 'always_allow'>('ask');
const showDetails = ref(false);
const { isEnglish } = useAppI18n();

const text = computed(() => (
  isEnglish.value
    ? {
        needsApproval: 'Approval required',
        reject: 'Reject',
        allow: 'Allow',
        collapseArgs: 'Collapse args',
        viewArgs: 'View full args',
        policyAsk: 'Ask every time',
        policyAlwaysAllow: 'Always allow',
        setAlwaysAllowSuccess: (name: string) => `${name} is now always allowed`,
        operationFailed: (reason?: string) => `Action failed: ${reason || 'Unknown error'}`,
      }
    : {
        needsApproval: '需要审批',
        reject: '拒绝',
        allow: '允许',
        collapseArgs: '收起参数',
        viewArgs: '查看完整参数',
        policyAsk: '每次询问',
        policyAlwaysAllow: '始终允许',
        setAlwaysAllowSuccess: (name: string) => `已设置 ${name} 为始终允许`,
        operationFailed: (reason?: string) => `操作失败: ${reason || '未知错误'}`,
      }
));

const policyOptions = computed(() => [
  { label: text.value.policyAsk, value: 'ask' },
  { label: text.value.policyAlwaysAllow, value: 'always_allow' },
]);

const actionRequest = computed(() => {
  return props.interrupt?.action_requests?.[0] || null;
});

const hasArgs = computed(() => {
  return actionRequest.value?.args && Object.keys(actionRequest.value.args).length > 0;
});

const formatArgsInline = (args?: Record<string, unknown>) => {
  if (!args) return '';
  const str = JSON.stringify(args);
  return str.length > 60 ? str.substring(0, 60) + '...' : str;
};

const getValueType = (value: unknown): string => {
  if (value === null) return 'type-null';
  if (typeof value === 'string') return 'type-string';
  if (typeof value === 'number') return 'type-number';
  if (typeof value === 'boolean') return 'type-boolean';
  if (Array.isArray(value)) return 'type-array';
  if (typeof value === 'object') return 'type-object';
  return '';
};

const formatValue = (value: unknown): string => {
  if (value === null) return 'null';
  if (value === undefined) return 'undefined';
  if (typeof value === 'string') return `"${value}"`;
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (Array.isArray(value)) return JSON.stringify(value);
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
};

watch(() => props.visible, (val) => {
  if (val) {
    rememberPolicy.value = 'ask';
    showDetails.value = false;
    loading.value = false;
  }
});

const handleApprove = async () => {
  console.log('[ToolApprovalCard] handleApprove called');
  console.log('[ToolApprovalCard] props.interrupt:', props.interrupt);
  console.log('[ToolApprovalCard] actionRequest.value:', actionRequest.value);

  if (!props.interrupt || !actionRequest.value) {
    console.warn('[ToolApprovalCard] Early return - missing data:', {
      hasInterrupt: !!props.interrupt,
      hasActionRequest: !!actionRequest.value
    });
    return;
  }
  loading.value = true;

  try {
    // 如果选择了"始终允许"，保存偏好
    if (rememberPolicy.value === 'always_allow' && actionRequest.value.name) {
      await saveToolApproval(
        actionRequest.value.name,
        'always_allow',
        'permanent',
        props.sessionId
      );
      Message.success(text.value.setAlwaysAllowSuccess(actionRequest.value.name));
    }

    emit('decision', {
      interruptId: props.interrupt.id,
      type: 'approve',
      rememberChoice: rememberPolicy.value === 'always_allow',
      rememberScope: 'permanent',
      toolName: actionRequest.value.name,
    });
    emit('update:visible', false);
  } catch (error: any) {
    Message.error(text.value.operationFailed(error.message));
  } finally {
    loading.value = false;
  }
};

const handleReject = async () => {
  if (!props.interrupt || !actionRequest.value) {
    emit('update:visible', false);
    return;
  }

  loading.value = true;

  try {
    emit('decision', {
      interruptId: props.interrupt.id,
      type: 'reject',
      rememberChoice: false,
      rememberScope: 'permanent',
      toolName: actionRequest.value.name,
    });
    emit('update:visible', false);
  } catch (error: any) {
    Message.error(text.value.operationFailed(error.message));
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.approval-card {
  background: linear-gradient(135deg, color-mix(in srgb, var(--theme-surface) 92%, rgba(var(--theme-accent-rgb), 0.08)) 0%, color-mix(in srgb, var(--theme-shell-soft) 88%, rgba(var(--theme-accent-rgb), 0.12)) 100%);
  border: 1px solid rgba(var(--theme-accent-rgb), 0.18);
  border-radius: 12px;
  margin: 0 16px 12px 16px;
  overflow: hidden;
  box-shadow: 0 10px 24px rgba(2, 6, 23, 0.14);
}

.card-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  gap: 16px;
}

/* 左侧工具信息 */
.tool-section {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.tool-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: linear-gradient(135deg, #fa8c16 0%, #d46b08 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.tool-icon :deep(svg) {
  font-size: 18px;
  color: #fff;
}

.tool-info {
  flex: 1;
  min-width: 0;
}

.tool-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.tool-name {
  font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
  font-size: 14px;
  font-weight: 600;
  color: #874d00;
}

.approval-badge {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  background: #fff1b8;
  color: #ad6800;
  font-weight: 500;
}

.tool-args {
  overflow: hidden;
}

.tool-args code {
  font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
  font-size: 12px;
  color: #8c6e3a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
}

/* 右侧操作区 */
.action-section {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.remember-option {
  display: flex;
  align-items: center;
}

.remember-option :deep(.arco-select-view-single) {
  background: rgba(255, 255, 255, 0.8);
  border-color: rgba(var(--theme-accent-rgb), 0.18);
}

.remember-option :deep(.arco-select-view-single:hover) {
  border-color: rgba(var(--theme-accent-rgb), 0.28);
}

.action-buttons {
  display: flex;
  gap: 8px;
}

.btn-reject {
  border-color: #d9d9d9;
  color: #595959;
  background: #fff;
}

.btn-reject:hover {
  border-color: #ff4d4f;
  color: #ff4d4f;
}

.btn-approve {
  background: linear-gradient(135deg, #52c41a 0%, #389e0d 100%);
  border: none;
}

.btn-approve:hover {
  background: linear-gradient(135deg, #73d13d 0%, #52c41a 100%);
}

/* 参数详情 */
.args-detail {
  background: color-mix(in srgb, var(--theme-surface) 88%, transparent);
  border-top: 1px solid rgba(var(--theme-accent-rgb), 0.18);
  padding: 12px 16px;
  max-height: 200px;
  overflow-y: auto;
}

.args-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.arg-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 8px 12px;
  background: linear-gradient(135deg, color-mix(in srgb, var(--theme-surface-soft) 78%, white 22%) 0%, color-mix(in srgb, var(--theme-surface) 84%, white 16%) 100%);
  border-radius: 6px;
  border: 1px solid var(--theme-border);
}

.arg-key {
  font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
  font-size: 13px;
  font-weight: 600;
  color: #722ed1;
  min-width: 100px;
  flex-shrink: 0;
}

.arg-key::after {
  content: ':';
  color: #8c8c8c;
  margin-left: 2px;
}

.arg-value {
  font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
  font-size: 13px;
  line-height: 1.5;
  word-break: break-word;
  flex: 1;
}

.arg-value.type-string {
  color: #389e0d;
}

.arg-value.type-number {
  color: #1890ff;
}

.arg-value.type-boolean {
  color: #eb2f96;
  font-weight: 600;
}

.arg-value.type-null {
  color: #8c8c8c;
  font-style: italic;
}

.arg-value.type-array,
.arg-value.type-object {
  color: #d46b08;
}

/* 展开/收起按钮 */
.toggle-detail {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 100%;
  padding: 6px;
  border: none;
  background: rgba(250, 173, 20, 0.1);
  color: #ad6800;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.2s;
}

.toggle-detail:hover {
  background: rgba(250, 173, 20, 0.2);
}

.toggle-detail :deep(svg) {
  font-size: 12px;
}

/* 动画 */
.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.3s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
  transform: translateY(20px);
}

.expand-enter-active,
.expand-leave-active {
  transition: all 0.2s ease;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}
</style>
