<template>
  <a-modal
    :visible="visible"
    title="系统状态检查"
    :width="800"
    @cancel="handleClose"
    :footer="false"
  >
    <div v-if="loading" class="loading-container">
      <a-spin size="large" />
      <p>正在检查系统状态...</p>
    </div>

    <div v-else-if="error" class="error-container">
      <a-result status="error" :title="error" />
      <div class="retry-container">
        <a-button type="primary" @click="fetchSystemStatus">
          重新检查
        </a-button>
      </div>
    </div>

    <div v-else-if="systemStatus" class="status-container">
      <!-- 总体状态 -->
      <div class="status-header">
        <a-tag
          :color="systemStatus.overall_status === 'healthy' ? 'green' : 'red'"
          size="large"
        >
          {{ systemStatus.overall_status === 'healthy' ? '系统正常' : '系统异常' }}
        </a-tag>
        <span class="timestamp">
          检查时间: {{ formatTimestamp(systemStatus.timestamp) }}
        </span>
      </div>

      <!-- 嵌入模型状态 -->
      <div class="status-section">
        <h3>嵌入模型状态</h3>
        <div class="model-info">
          <div class="info-item">
            <span class="label">模型名称:</span>
            <span class="value">{{ systemStatus.embedding_model.model_name }}</span>
          </div>
          <div class="info-item">
            <span class="label">状态:</span>
            <a-tag :color="systemStatus.embedding_model.status === 'working' ? 'green' : 'red'">
              {{ systemStatus.embedding_model.status === 'working' ? '正常' : '异常' }}
            </a-tag>
          </div>
          <div class="info-item">
            <span class="label">模型存在:</span>
            <a-tag :color="systemStatus.embedding_model.model_exists ? 'green' : 'red'">
              {{ systemStatus.embedding_model.model_exists ? '是' : '否' }}
            </a-tag>
          </div>
          <div class="info-item">
            <span class="label">加载测试:</span>
            <a-tag :color="systemStatus.embedding_model.load_test ? 'green' : 'red'">
              {{ systemStatus.embedding_model.load_test ? '通过' : '失败' }}
            </a-tag>
          </div>
          <div class="info-item">
            <span class="label">向量维度:</span>
            <span class="value">{{ systemStatus.embedding_model.dimension }}</span>
          </div>
          <div class="info-item">
            <span class="label">缓存路径:</span>
            <span class="value small">{{ systemStatus.embedding_model.cache_path }}</span>
          </div>
        </div>
      </div>

      <!-- 依赖状态 -->
      <div class="status-section">
        <h3>依赖库状态</h3>
        <div class="dependencies-grid">
          <div
            v-for="(status, name) in systemStatus.dependencies"
            :key="name"
            class="dependency-item"
          >
            <span class="dep-name">{{ name }}</span>
            <a-tag :color="status ? 'green' : 'red'">
              {{ status ? '正常' : '异常' }}
            </a-tag>
          </div>
        </div>
      </div>

      <!-- 向量存储状态 -->
      <div class="status-section">
        <h3>向量存储状态</h3>
        <div class="vector-info">
          <div class="info-item">
            <span class="label">总知识库数:</span>
            <span class="value">{{ systemStatus.vector_stores.total_knowledge_bases }}</span>
          </div>
          <div class="info-item">
            <span class="label">活跃知识库数:</span>
            <span class="value">{{ systemStatus.vector_stores.active_knowledge_bases }}</span>
          </div>
          <div class="info-item">
            <span class="label">缓存状态:</span>
            <span class="value">{{ systemStatus.vector_stores.cache_status }}</span>
          </div>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="actions">
        <a-button @click="fetchSystemStatus" :loading="loading">
          刷新状态
        </a-button>
        <a-button type="primary" @click="handleClose">
          关闭
        </a-button>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import { Message } from '@arco-design/web-vue';
import { KnowledgeService } from '../services/knowledgeService';
import type { SystemStatusResponse } from '../types/knowledge';

interface Props {
  visible: boolean;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  close: [];
}>();

// 响应式数据
const loading = ref(false);
const error = ref<string | null>(null);
const systemStatus = ref<SystemStatusResponse | null>(null);

// 方法
const fetchSystemStatus = async () => {
  loading.value = true;
  error.value = null;
  
  try {
    const status = await KnowledgeService.getSystemStatus();
    systemStatus.value = status;
  } catch (err) {
    console.error('获取系统状态失败:', err);
    error.value = '获取系统状态失败，请稍后重试';
    Message.error('获取系统状态失败');
  } finally {
    loading.value = false;
  }
};

const formatTimestamp = (timestamp: number) => {
  return new Date(timestamp * 1000).toLocaleString();
};

const handleClose = () => {
  emit('close');
};

// 监听弹窗显示状态
watch(() => props.visible, (visible) => {
  if (visible) {
    fetchSystemStatus();
  } else {
    // 重置状态
    systemStatus.value = null;
    error.value = null;
  }
});
</script>

<style scoped>
.loading-container {
  text-align: center;
  padding: 40px;
}

.loading-container p {
  margin-top: 16px;
  color: #666;
}

.error-container {
  text-align: center;
}

.retry-container {
  margin-top: 16px;
}

.status-container {
  max-height: 600px;
  overflow-y: auto;
}

.status-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e5e6eb;
}

.timestamp {
  font-size: 12px;
  color: #666;
}

.status-section {
  margin-bottom: 24px;
}

.status-section h3 {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: bold;
  color: #333;
}

.model-info,
.vector-info {
  background: #f7f8fa;
  padding: 16px;
  border-radius: 6px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.info-item:last-child {
  margin-bottom: 0;
}

.label {
  font-weight: 500;
  color: #333;
  min-width: 100px;
}

.value {
  color: #666;
  text-align: right;
}

.value.small {
  font-size: 12px;
  word-break: break-all;
}

.dependencies-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}

.dependency-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #f7f8fa;
  border-radius: 4px;
}

.dep-name {
  font-weight: 500;
  color: #333;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #e5e6eb;
}
</style>
