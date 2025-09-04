<template>
  <div class="knowledge-base-detail">
    <div class="detail-header">
      <h3>{{ knowledgeBase.name }}</h3>
      <a-button type="text" @click="$emit('close')">
        <template #icon><icon-close /></template>
      </a-button>
    </div>

    <div class="detail-content">
      <!-- 基本信息和配置信息 - 两列布局 -->
      <div class="info-grid">
        <!-- 基本信息 -->
        <div class="info-section">
          <h4>基本信息</h4>
          <div class="info-item">
            <span class="label">描述:</span>
            <span class="value">{{ knowledgeBase.description || '暂无描述' }}</span>
          </div>
          <div class="info-item">
            <span class="label">所属项目:</span>
            <span class="value">{{ getProjectName(knowledgeBase.project) }}</span>
          </div>
          <div class="info-item">
            <span class="label">状态:</span>
            <a-tag :color="knowledgeBase.is_active ? 'green' : 'red'">
              {{ knowledgeBase.is_active ? '启用' : '禁用' }}
            </a-tag>
          </div>
          <div class="info-item">
            <span class="label">创建者:</span>
            <span class="value">{{ knowledgeBase.creator_name || '未知' }}</span>
          </div>
          <div class="info-item">
            <span class="label">创建时间:</span>
            <span class="value">{{ formatDate(knowledgeBase.created_at) }}</span>
          </div>
        </div>

        <!-- 配置信息 -->
        <div class="info-section">
          <h4>配置信息</h4>
          <div class="info-item">
            <span class="label">嵌入服务:</span>
            <span class="value">{{ getEmbeddingServiceDisplayName(knowledgeBase.embedding_service) }}</span>
          </div>
          <div class="info-item">
            <span class="label">模型名称:</span>
            <span class="value">{{ knowledgeBase.model_name }}</span>
          </div>
          <div class="info-item">
            <span class="label">分块大小:</span>
            <span class="value">{{ knowledgeBase.chunk_size }}</span>
          </div>
          <div class="info-item">
            <span class="label">分块重叠:</span>
            <span class="value">{{ knowledgeBase.chunk_overlap }}</span>
          </div>
          
          <!-- API配置信息（如果有的话） -->
          <template v-if="hasApiConfig">
            <div class="info-item" v-if="knowledgeBase.api_base_url">
              <span class="label">API基础URL:</span>
              <span class="value">{{ knowledgeBase.api_base_url }}</span>
            </div>
            <div class="info-item" v-if="knowledgeBase.api_key">
              <span class="label">API密钥:</span>
              <span class="value">{{ maskApiKey(knowledgeBase.api_key) }}</span>
            </div>
          </template>
        </div>
      </div>

      <!-- 统计信息 -->
      <div class="info-section">
        <h4>统计信息</h4>
        <div class="stats-grid">
          <div class="stat-item">
            <div class="stat-value">{{ knowledgeBase.document_count }}</div>
            <div class="stat-label">文档数量</div>
          </div>
          <div class="stat-item">
            <div class="stat-value">{{ knowledgeBase.chunk_count }}</div>
            <div class="stat-label">分块数量</div>
          </div>
        </div>
      </div>

      <!-- 文档管理 -->
      <div class="documents-section">
        <div class="section-header">
          <h4>文档管理</h4>
          <a-button type="primary" size="small" @click="showUploadModal">
            <template #icon><icon-upload /></template>
            上传文档
          </a-button>
        </div>

        <div class="documents-list">
          <a-table
            :columns="documentColumns"
            :data="documents"
            :loading="documentsLoading"
            :pagination="false"
            size="small"
          >
            <template #title="{ record }">
              <span
                class="document-title-link"
                @click="viewDocument(record.id)"
              >
                {{ record.title }}
              </span>
            </template>

            <template #status="{ record }">
              <div class="status-cell">
                <a-tag :color="getStatusColor(record.status)">
                  {{ getStatusText(record.status) }}
                </a-tag>
                <a-tooltip v-if="record.status === 'failed' && record.error_message" :content="record.error_message">
                  <icon-exclamation-circle style="color: #f53f3f; margin-left: 4px; cursor: help;" />
                </a-tooltip>
              </div>
            </template>

            <template #actions="{ record }">
              <a-space>
                <a-button
                  type="text"
                  size="mini"
                  @click="viewDocument(record.id)"
                >
                  查看
                </a-button>
                <a-button
                  v-if="record.status === 'failed'"
                  type="text"
                  size="mini"
                  @click="reprocessDocument(record.id)"
                >
                  重试
                </a-button>
                <a-popconfirm
                  content="确定要删除这个文档吗？"
                  @ok="deleteDocument(record.id)"
                >
                  <a-button type="text" size="mini" status="danger">
                    删除
                  </a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </a-table>
        </div>
      </div>

      <!-- 查询测试 -->
      <div class="query-section">
        <h4>查询测试</h4>
        <div class="query-form">
          <a-textarea
            v-model="queryText"
            placeholder="输入查询内容..."
            :rows="3"
            style="margin-bottom: 12px"
          />

          <!-- 查询参数设置 -->
          <div class="query-settings">
            <div class="setting-item">
              <label>相似度阈值:</label>
              <a-slider
                v-model="similarityThreshold"
                :min="0.1"
                :max="1.0"
                :step="0.1"
                :show-tooltip="true"
                style="width: 120px;"
              />
              <span class="value-display">{{ similarityThreshold }}</span>
            </div>

            <div class="setting-item">
              <label>检索数量:</label>
              <a-input-number
                v-model="topK"
                :min="1"
                :max="20"
                :step="1"
                size="small"
                style="width: 80px;"
              />
            </div>
          </div>

          <a-button
            type="primary"
            :loading="queryLoading"
            @click="testQuery"
            style="width: 100%"
          >
            测试查询
          </a-button>
        </div>

        <div v-if="queryResult" class="query-result">
          <h5>查询结果</h5>
          <div class="result-content">
            <div class="query-info">
              <strong>查询内容:</strong>
              <p>{{ queryResult.query }}</p>
            </div>
            <div class="answer" v-if="queryResult.answer">
              <strong>回答:</strong>
              <p>{{ queryResult.answer }}</p>
            </div>
            <div class="sources">
              <strong>相关内容 ({{ queryResult.sources.length }} 条结果):</strong>
              <div
                v-for="(source, index) in queryResult.sources"
                :key="index"
                class="source-item"
              >
                <div class="source-content">{{ source.content }}</div>
                <div class="source-meta">
                  <span>文档: {{ source.metadata.title }}</span> |
                  <span>相似度: {{ (source.similarity_score * 100).toFixed(1) }}%</span>
                  <span v-if="source.metadata.page"> | 页码: {{ source.metadata.page }}</span>
                </div>
              </div>
            </div>
            <div class="timing">
              <small>
                检索时间: {{ queryResult.retrieval_time.toFixed(2) }}s |
                生成时间: {{ queryResult.generation_time.toFixed(2) }}s |
                总时间: {{ queryResult.total_time.toFixed(2) }}s
              </small>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 上传文档弹窗 -->
    <DocumentUploadModal
      :visible="isUploadModalVisible"
      :knowledge-base-id="knowledgeBase.id"
      @submit="handleDocumentUploaded"
      @cancel="closeUploadModal"
    />

    <!-- 文档详情弹窗 -->
    <DocumentDetailModal
      :visible="isDocumentDetailVisible"
      :document-id="selectedDocumentId"
      @close="closeDocumentDetail"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { Message } from '@arco-design/web-vue';
import { IconClose, IconUpload, IconExclamationCircle } from '@arco-design/web-vue/es/icon';
import { useProjectStore } from '@/store/projectStore';
import { KnowledgeService } from '../services/knowledgeService';
import type { KnowledgeBase, Document, QueryResponse } from '../types/knowledge';
import { SERVICES_REQUIRING_API_CONFIG } from '../types/knowledge';
import DocumentUploadModal from './DocumentUploadModal.vue';
import DocumentDetailModal from './DocumentDetailModal.vue';

interface Props {
  knowledgeBase: KnowledgeBase;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  refresh: [];
  close: [];
}>();

const projectStore = useProjectStore();

// 响应式数据
const documents = ref<Document[]>([]);
const documentsLoading = ref(false);
const queryText = ref('');
const queryLoading = ref(false);
const queryResult = ref<QueryResponse | null>(null);
const similarityThreshold = ref(0.3);
const topK = ref(3);
const isUploadModalVisible = ref(false);
const isDocumentDetailVisible = ref(false);
const selectedDocumentId = ref<string | null>(null);

// 文档表格列配置
const documentColumns = [
  {
    title: '文档名称',
    dataIndex: 'title',
    width: 120,
    slotName: 'title',
  },
  {
    title: '类型',
    dataIndex: 'document_type',
    width: 50,
  },
  {
    title: '状态',
    dataIndex: 'status',
    slotName: 'status',
    width: 70,
  },
  {
    title: '分块数',
    dataIndex: 'chunk_count',
    width: 60,
  },
  {
    title: '上传者',
    dataIndex: 'uploader_name',
    width: 80,
  },
  {
    title: '上传时间',
    dataIndex: 'uploaded_at',
    width: 100,
    render: ({ record }: { record: Document }) => {
      return new Date(record.uploaded_at).toLocaleDateString();
    },
  },
  {
    title: '操作',
    slotName: 'actions',
    width: 80,
  },
];

// 方法
const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleString();
};

const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    pending: 'orange',
    processing: 'blue',
    completed: 'green',
    failed: 'red',
  };
  return colors[status] || 'gray';
};

const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    pending: '待处理',
    processing: '处理中',
    completed: '已完成',
    failed: '失败',
  };
  return texts[status] || status;
};

const fetchDocuments = async () => {
  documentsLoading.value = true;
  try {
    console.log('开始获取文档列表，知识库ID:', props.knowledgeBase.id);
    const response = await KnowledgeService.getDocuments({
      knowledge_base: props.knowledgeBase.id,
    });
    console.log('获取到的文档数据:', response);
    console.log('文档数组长度:', response?.length);
    documents.value = response;
    console.log('设置后的documents.value:', documents.value);
  } catch (error: any) {
    console.error('获取文档列表失败:', error);
    // 显示具体的错误消息
    const errorMessage = error?.message || '获取文档列表失败';
    Message.error(errorMessage);
  } finally {
    documentsLoading.value = false;
  }
};

const reprocessDocument = async (documentId: string) => {
  try {
    await KnowledgeService.reprocessDocument(documentId);
    Message.success('文档重新处理已开始');
    await fetchDocuments();
  } catch (error) {
    console.error('重新处理文档失败:', error);
    Message.error('重新处理文档失败');
  }
};

const deleteDocument = async (documentId: string) => {
  try {
    await KnowledgeService.deleteDocument(documentId);
    Message.success('文档删除成功');
    await fetchDocuments();
    emit('refresh');
  } catch (error) {
    console.error('删除文档失败:', error);
    Message.error('删除文档失败');
  }
};

const testQuery = async () => {
  if (!queryText.value.trim()) {
    Message.warning('请输入查询内容');
    return;
  }

  queryLoading.value = true;
  try {
    const result = await KnowledgeService.queryKnowledgeBase(props.knowledgeBase.id, {
      query: queryText.value,
      knowledge_base_id: props.knowledgeBase.id,
      top_k: topK.value,
      similarity_threshold: similarityThreshold.value,
      include_metadata: true,
    });
    queryResult.value = result;
  } catch (error: any) {
    console.error('查询失败:', error);
    // 显示具体的错误消息
    const errorMessage = error?.message || '查询失败';
    Message.error(errorMessage);
  } finally {
    queryLoading.value = false;
  }
};

const showUploadModal = () => {
  isUploadModalVisible.value = true;
};

const closeUploadModal = () => {
  isUploadModalVisible.value = false;
};

const handleDocumentUploaded = () => {
  closeUploadModal();
  fetchDocuments();
  emit('refresh');
  Message.success('文档上传成功');
};

const viewDocument = (documentId: string) => {
  selectedDocumentId.value = documentId;
  isDocumentDetailVisible.value = true;
};

const closeDocumentDetail = () => {
  isDocumentDetailVisible.value = false;
  selectedDocumentId.value = null;
};

const getProjectName = (projectId: number) => {
  // 首先尝试从知识库数据中获取项目名称
  if (props.knowledgeBase.project_name) {
    return props.knowledgeBase.project_name;
  }

  // 如果没有，从项目store中获取
  const project = projectStore.projectOptions.find(p => p.value === projectId);
  return project ? project.label : String(projectId);
};

// 获取嵌入服务显示名称
const getEmbeddingServiceDisplayName = (serviceValue: string) => {
  const serviceNames: Record<string, string> = {
    'openai': 'OpenAI',
    'azure_openai': 'Azure OpenAI',
    'ollama': 'Ollama',
    'custom': '自定义API'
  };
  return serviceNames[serviceValue] || serviceValue;
};

// 是否有API配置
const hasApiConfig = computed(() => {
  return SERVICES_REQUIRING_API_CONFIG.includes(props.knowledgeBase.embedding_service as any);
});

// 掩码API密钥
const maskApiKey = (apiKey: string) => {
  if (!apiKey || apiKey.length <= 8) return apiKey;
  return apiKey.substring(0, 4) + '****' + apiKey.substring(apiKey.length - 4);
};

// 生命周期
onMounted(() => {
  fetchDocuments();
});
</script>

<style scoped>
.knowledge-base-detail {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 16px;
  border-bottom: 1px solid #e5e6eb;
  margin-bottom: 20px;
}

.detail-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: bold;
}

.detail-content {
  flex: 1;
  overflow-y: auto;
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 32px;
  margin-bottom: 24px;
}

.info-section {
  margin-bottom: 24px;
  padding: 20px;
  background: #f7f8fa;
  border-radius: 8px;
  border: 1px solid #e5e6eb;
}

.info-section h4 {
  margin: 0 0 16px 0;
  font-size: 15px;
  font-weight: bold;
  color: #333;
  padding-bottom: 8px;
  border-bottom: 1px solid #e5e6eb;
}

.info-item {
  display: flex;
  margin-bottom: 12px;
  align-items: center;
}

.label {
  width: 90px;
  color: #666;
  font-size: 13px;
  font-weight: 500;
  flex-shrink: 0;
  text-align: left;
}

.value {
  flex: 1;
  font-size: 13px;
  color: #333;
  text-align: left;
}

.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.stat-item {
  text-align: center;
  padding: 12px;
  background: #f7f8fa;
  border-radius: 6px;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #00a0e9;
}

.stat-label {
  font-size: 12px;
  color: #666;
  margin-top: 4px;
}

.documents-section {
  margin-bottom: 24px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-header h4 {
  margin: 0;
  font-size: 14px;
  font-weight: bold;
  color: #333;
}

.documents-list {
  max-height: 200px;
  overflow-y: auto;
}

.status-cell {
  display: flex;
  align-items: center;
}

.query-section {
  margin-bottom: 24px;
}

.query-section h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: bold;
  color: #333;
}

.query-settings {
  display: flex;
  gap: 24px;
  margin-bottom: 12px;
  padding: 12px;
  background: #f7f8fa;
  border-radius: 6px;
  border: 1px solid #e5e6eb;
}

.setting-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.setting-item label {
  font-size: 12px;
  color: #666;
  white-space: nowrap;
  min-width: 80px;
}

.value-display {
  font-size: 12px;
  color: #333;
  font-weight: 500;
  min-width: 30px;
}

.query-result {
  margin-top: 16px;
  padding: 12px;
  background: #f7f8fa;
  border-radius: 6px;
}

.query-result h5 {
  margin: 0 0 12px 0;
  font-size: 12px;
  font-weight: bold;
}

.query-info {
  margin-bottom: 12px;
}

.query-info p {
  margin: 4px 0 0 0;
  font-size: 12px;
  line-height: 1.5;
}

.answer {
  margin-bottom: 12px;
}

.answer p {
  margin: 4px 0 0 0;
  font-size: 12px;
  line-height: 1.5;
}

.sources {
  margin-bottom: 12px;
}

.source-item {
  margin: 8px 0;
  padding: 8px;
  background: white;
  border-radius: 4px;
  border-left: 3px solid #00a0e9;
}

.source-content {
  font-size: 12px;
  line-height: 1.4;
  margin-bottom: 4px;
}

.source-meta {
  font-size: 10px;
  color: #666;
}

.timing {
  font-size: 10px;
  color: #999;
  margin-top: 8px;
}

.document-title-link {
  color: #00a0e9;
  cursor: pointer;
  text-decoration: none;
  transition: color 0.2s;
}

.document-title-link:hover {
  color: #0e42d2;
  text-decoration: underline;
}
</style>
