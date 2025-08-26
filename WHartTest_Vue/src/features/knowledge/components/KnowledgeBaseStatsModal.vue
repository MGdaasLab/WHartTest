<template>
  <a-modal
    :visible="visible"
    title="知识库统计信息"
    :width="800"
    :footer="false"
    @cancel="$emit('close')"
  >
    <div v-if="loading" class="loading-container">
      <a-spin size="large" />
      <div class="loading-text">正在加载统计信息...</div>
    </div>

    <div v-else-if="statistics" class="stats-container">
      <!-- 概览统计 -->
      <div class="stats-overview">
        <h3>概览统计</h3>
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-icon document-icon">
              <icon-file />
            </div>
            <div class="stat-content">
              <div class="stat-value">{{ statistics.document_count }}</div>
              <div class="stat-label">文档总数</div>
            </div>
          </div>

          <div class="stat-card">
            <div class="stat-icon chunk-icon">
              <icon-layers />
            </div>
            <div class="stat-content">
              <div class="stat-value">{{ statistics.chunk_count }}</div>
              <div class="stat-label">分块总数</div>
            </div>
          </div>

          <div class="stat-card">
            <div class="stat-icon query-icon">
              <icon-search />
            </div>
            <div class="stat-content">
              <div class="stat-value">{{ statistics.query_count }}</div>
              <div class="stat-label">查询次数</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 文档状态分布 -->
      <div class="status-distribution">
        <h3>文档状态分布</h3>
        <div class="status-grid">
          <div class="status-item completed">
            <div class="status-count">{{ statistics.document_status_distribution.completed }}</div>
            <div class="status-label">已完成</div>
          </div>
          <div class="status-item processing">
            <div class="status-count">{{ statistics.document_status_distribution.processing }}</div>
            <div class="status-label">处理中</div>
          </div>
          <div class="status-item failed">
            <div class="status-count">{{ statistics.document_status_distribution.failed }}</div>
            <div class="status-label">失败</div>
          </div>
        </div>
      </div>

      <!-- 最近查询 -->
      <div class="recent-queries">
        <h3>最近查询</h3>
        <div v-if="statistics.recent_queries.length === 0" class="empty-queries">
          暂无查询记录
        </div>
        <div v-else class="queries-list">
          <div
            v-for="(query, index) in statistics.recent_queries"
            :key="index"
            class="query-item"
          >
            <div class="query-content">
              <div class="query-text">{{ query.query }}</div>
              <div class="query-meta">
                <span class="query-time">{{ formatDate(query.created_at) }}</span>
                <span class="query-duration">耗时: {{ query.total_time.toFixed(3) }}s</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 性能指标 -->
      <div class="performance-metrics">
        <h3>性能指标</h3>
        <div class="metrics-grid">
          <div class="metric-item">
            <div class="metric-label">平均查询时间</div>
            <div class="metric-value">
              {{ getAverageQueryTime() }}s
            </div>
          </div>
          <div class="metric-item">
            <div class="metric-label">平均文档大小</div>
            <div class="metric-value">
              {{ getAverageChunksPerDocument() }} 分块/文档
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="error-container">
      <a-result status="error" title="加载失败">
        <template #subtitle>
          无法加载统计信息，请稍后重试
        </template>
        <template #extra>
          <a-button type="primary" @click="loadStatistics">
            重新加载
          </a-button>
        </template>
      </a-result>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import { Message } from '@arco-design/web-vue';
import { IconFile, IconLayers, IconSearch } from '@arco-design/web-vue/es/icon';
import { KnowledgeService } from '../services/knowledgeService';
import type { KnowledgeBaseStatistics } from '../types/knowledge';

interface Props {
  visible: boolean;
  knowledgeBaseId: string;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  close: [];
}>();

const loading = ref(false);
const statistics = ref<KnowledgeBaseStatistics | null>(null);

// 监听弹窗显示状态
watch(() => props.visible, (visible) => {
  if (visible && props.knowledgeBaseId) {
    loadStatistics();
  }
});

// 方法
const loadStatistics = async () => {
  if (!props.knowledgeBaseId) return;

  loading.value = true;
  try {
    const data = await KnowledgeService.getKnowledgeBaseStatistics(props.knowledgeBaseId);
    statistics.value = data;
  } catch (error: any) {
    console.error('加载统计信息失败:', error);
    // 显示具体的错误消息
    const errorMessage = error?.message || '加载统计信息失败';
    Message.error(errorMessage);
    statistics.value = null;
  } finally {
    loading.value = false;
  }
};

const formatDate = (dateString: string) => {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffMins < 1) return '刚刚';
  if (diffMins < 60) return `${diffMins}分钟前`;
  if (diffHours < 24) return `${diffHours}小时前`;
  if (diffDays < 7) return `${diffDays}天前`;
  
  return date.toLocaleDateString();
};

const getAverageQueryTime = () => {
  if (!statistics.value || statistics.value.recent_queries.length === 0) {
    return '0.000';
  }
  
  const totalTime = statistics.value.recent_queries.reduce(
    (sum, query) => sum + query.total_time, 
    0
  );
  const average = totalTime / statistics.value.recent_queries.length;
  return average.toFixed(3);
};

const getAverageChunksPerDocument = () => {
  if (!statistics.value || statistics.value.document_count === 0) {
    return '0';
  }
  
  const average = statistics.value.chunk_count / statistics.value.document_count;
  return average.toFixed(1);
};
</script>

<style scoped>
.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
}

.loading-text {
  margin-top: 16px;
  color: #666;
  font-size: 14px;
}

.stats-container {
  padding: 20px 0;
}

.stats-container h3 {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: bold;
  color: #333;
  border-bottom: 1px solid #e5e6eb;
  padding-bottom: 8px;
}

.stats-overview {
  margin-bottom: 32px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.stat-card {
  display: flex;
  align-items: center;
  padding: 20px;
  background: #f7f8fa;
  border-radius: 8px;
  border-left: 4px solid #3370ff;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 16px;
  font-size: 20px;
  color: white;
}

.document-icon {
  background: #3370ff;
}

.chunk-icon {
  background: #00b42a;
}

.query-icon {
  background: #ff7d00;
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #333;
  line-height: 1;
}

.stat-label {
  font-size: 12px;
  color: #666;
  margin-top: 4px;
}

.status-distribution {
  margin-bottom: 32px;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.status-item {
  text-align: center;
  padding: 16px;
  border-radius: 8px;
  border: 2px solid;
}

.status-item.completed {
  border-color: #00b42a;
  background: rgba(0, 180, 42, 0.1);
}

.status-item.processing {
  border-color: #3370ff;
  background: rgba(51, 112, 255, 0.1);
}

.status-item.failed {
  border-color: #f53f3f;
  background: rgba(245, 63, 63, 0.1);
}

.status-count {
  font-size: 20px;
  font-weight: bold;
  margin-bottom: 4px;
}

.status-label {
  font-size: 12px;
  color: #666;
}

.recent-queries {
  margin-bottom: 32px;
}

.empty-queries {
  text-align: center;
  color: #999;
  padding: 40px 20px;
  background: #f7f8fa;
  border-radius: 8px;
}

.queries-list {
  max-height: 200px;
  overflow-y: auto;
}

.query-item {
  padding: 12px 16px;
  border: 1px solid #e5e6eb;
  border-radius: 6px;
  margin-bottom: 8px;
  background: white;
}

.query-item:last-child {
  margin-bottom: 0;
}

.query-text {
  font-size: 14px;
  color: #333;
  margin-bottom: 4px;
  line-height: 1.4;
}

.query-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #666;
}

.performance-metrics h3 {
  margin-bottom: 16px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.metric-item {
  padding: 16px;
  background: #f7f8fa;
  border-radius: 8px;
  text-align: center;
}

.metric-label {
  font-size: 12px;
  color: #666;
  margin-bottom: 8px;
}

.metric-value {
  font-size: 18px;
  font-weight: bold;
  color: #3370ff;
}

.error-container {
  padding: 20px 0;
}
</style>
