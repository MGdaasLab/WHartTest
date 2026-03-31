<template>
  <a-modal
    v-model:visible="visible"
    title="执行日志"
    :width="660"
    :footer="false"
    :mask-closable="true"
  >
    <a-spin :loading="loading">
      <div class="log-info" v-if="logData">
        <div class="log-meta">
          <a-descriptions :column="3" size="small" bordered>
            <a-descriptions-item label="执行ID">{{ logData.execution_id }}</a-descriptions-item>
            <a-descriptions-item label="状态">
              <a-tag :color="logData.status === 'success' ? 'green' : logData.status === 'failed' ? 'red' : 'blue'">
                {{ statusMap[logData.status] || logData.status }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="耗时">{{ logData.duration }}</a-descriptions-item>
          </a-descriptions>
        </div>
        <div class="log-content">
          <div class="log-section-title">执行日志</div>
          <pre class="log-text">{{ logData.log || '暂无日志' }}</pre>
        </div>
        <div v-if="logData.error_message" class="log-content error">
          <div class="log-section-title">错误信息</div>
          <pre class="log-text error-text">{{ logData.error_message }}</pre>
        </div>
      </div>
    </a-spin>
  </a-modal>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { Message } from '@arco-design/web-vue';
import { getExecutionLog } from '../services/taskService';

const props = defineProps<{
  projectId: number;
}>();

const visible = ref(false);
const loading = ref(false);
const logData = ref<{
  execution_id: string;
  log: string;
  error_message: string;
  status: string;
  duration: string;
} | null>(null);

const statusMap: Record<string, string> = {
  running: '执行中',
  success: '成功',
  failed: '失败',
};

const open = async (executionId: number) => {
  visible.value = true;
  loading.value = true;
  try {
    logData.value = await getExecutionLog(props.projectId, executionId);
  } catch {
    Message.error('加载日志失败');
  } finally {
    loading.value = false;
  }
};

defineExpose({ open });
</script>

<style scoped>
.log-info {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.log-meta {
  text-align: center;
  margin-bottom: 4px;
}

.log-meta :deep(.arco-descriptions) {
  display: inline-table;
  width: auto;
}

.log-section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-2);
  margin-bottom: 8px;
}

.log-text {
  background: var(--color-fill-2);
  border-radius: 6px;
  padding: 12px 16px;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 400px;
  overflow-y: auto;
  margin: 0;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
}

.error-text {
  color: var(--color-danger-6);
  background: var(--color-danger-1);
}
</style>
