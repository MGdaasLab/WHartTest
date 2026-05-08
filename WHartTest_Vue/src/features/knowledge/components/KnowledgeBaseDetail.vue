<template>
  <div class="knowledge-base-detail">
    <div class="detail-header">
      <h3>{{ knowledgeBase.name }}</h3>
      <a-button type="text" @click="$emit('close')">
        <template #icon><icon-close /></template>
      </a-button>
    </div>

    <div class="detail-content">
      <div class="info-grid">
        <div class="info-section">
          <h4>基本信息</h4>
          <div class="info-item">
            <span class="label">描述</span>
            <span class="value">{{ knowledgeBase.description || '暂无描述' }}</span>
          </div>
          <div class="info-item">
            <span class="label">所属项目</span>
            <span class="value">{{ getProjectName(knowledgeBase.project) }}</span>
          </div>
          <div class="info-item">
            <span class="label">状态</span>
            <a-tag :color="knowledgeBase.is_active ? 'green' : 'red'">
              {{ knowledgeBase.is_active ? '启用' : '禁用' }}
            </a-tag>
          </div>
          <div class="info-item">
            <span class="label">创建者</span>
            <span class="value">{{ knowledgeBase.creator_name || '未知' }}</span>
          </div>
          <div class="info-item">
            <span class="label">创建时间</span>
            <span class="value">{{ formatDate(knowledgeBase.created_at) }}</span>
          </div>
        </div>

        <div class="info-section">
          <h4>配置</h4>
          <div class="info-item">
            <span class="label">分块大小</span>
            <span class="value">{{ knowledgeBase.chunk_size }}</span>
          </div>
          <div class="info-item">
            <span class="label">分块重叠</span>
            <span class="value">{{ knowledgeBase.chunk_overlap }}</span>
          </div>
        </div>
      </div>

      <div class="info-section">
        <h4>统计</h4>
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

      <div class="documents-section">
        <div class="section-header">
          <h4>文档管理</h4>
          <a-space>
            <a-button type="outline" size="small" @click="fetchDocuments" :loading="documentsLoading">
              <template #icon><icon-refresh /></template>
              刷新
            </a-button>
            <a-popconfirm
              content="确认重新处理当前知识库下的全部文档吗？这会重新生成分块和向量。"
              @ok="reprocessAllDocuments"
            >
              <a-button type="outline" size="small" :loading="documentsLoading">
                批量重处理
              </a-button>
            </a-popconfirm>
            <a-button type="primary" size="small" @click="showUploadModal">
              <template #icon><icon-upload /></template>
              上传文档
            </a-button>
          </a-space>
        </div>

        <div class="document-filter-grid">
          <a-input v-model="documentSearchText" placeholder="搜索标题、内容、标签" allow-clear />
          <a-select v-model="documentStatusFilter" placeholder="状态筛选" allow-clear>
            <a-option value="">全部状态</a-option>
            <a-option value="pending">待处理</a-option>
            <a-option value="processing">处理中</a-option>
            <a-option value="completed">已完成</a-option>
            <a-option value="failed">失败</a-option>
          </a-select>
          <a-input v-model="documentModuleFilter" placeholder="模块筛选" allow-clear />
          <a-input v-model="documentVersionFilter" placeholder="版本筛选" allow-clear />
          <a-input v-model="documentBusinessDomainFilter" placeholder="业务域筛选" allow-clear />
          <a-input v-model="documentStageFilter" placeholder="阶段筛选" allow-clear />
          <a-input v-model="documentTagsFilter" placeholder="标签筛选，逗号分隔" allow-clear />
        </div>

        <div class="documents-list">
          <a-table
            :columns="documentColumns"
            :data="filteredDocuments"
            :loading="documentsLoading"
            :pagination="false"
            size="small"
          >
            <template #title="{ record }">
              <span class="document-title-link" @click="viewDocument(record.id)">
                {{ record.title }}
              </span>
            </template>

            <template #status="{ record }">
              <div class="status-cell">
                <a-tag :color="getStatusColor(record.status)">
                  {{ getStatusText(record.status) }}
                </a-tag>
                <a-tooltip
                  v-if="record.status === 'failed' && record.error_message"
                  :content="record.error_message"
                >
                  <icon-exclamation-circle class="status-error-icon" />
                </a-tooltip>
              </div>
            </template>

            <template #tags="{ record }">
              <div v-if="record.tags?.length" class="tag-list">
                <a-tag v-for="tag in record.tags.slice(0, 3)" :key="tag" size="small">
                  {{ tag }}
                </a-tag>
                <span v-if="record.tags.length > 3" class="muted-text">+{{ record.tags.length - 3 }}</span>
              </div>
              <span v-else class="muted-text">-</span>
            </template>

            <template #metaSummary="{ record }">
              <div class="meta-summary">
                <div>{{ record.module || '-' }}</div>
                <div>{{ record.version || '-' }}</div>
                <div>{{ record.business_domain || '-' }}</div>
                <div>{{ record.document_stage || '-' }}</div>
              </div>
            </template>

            <template #actions="{ record }">
              <a-space>
                <a-button type="text" size="mini" @click="viewDocument(record.id)">
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
                <a-button
                  v-else
                  type="text"
                  size="mini"
                  @click="reprocessDocument(record.id)"
                >
                  重处理
                </a-button>
                <a-popconfirm content="确认删除这个文档吗？" @ok="deleteDocument(record.id)">
                  <a-button type="text" size="mini" status="danger">
                    删除
                  </a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </a-table>
        </div>
      </div>

      <div class="query-section">
        <h4>查询测试</h4>
        <div class="query-form">
          <a-textarea
            v-model="queryText"
            placeholder="输入查询内容..."
            :rows="3"
            style="margin-bottom: 12px"
          />

          <div class="query-settings">
            <div class="setting-item">
              <label>相似度阈值</label>
              <a-slider
                v-model="similarityThreshold"
                :min="0.1"
                :max="1"
                :step="0.1"
                :show-tooltip="true"
                style="width: 120px"
              />
              <span class="value-display">{{ similarityThreshold }}</span>
            </div>

            <div class="setting-item">
              <label>检索数量</label>
              <a-input-number
                v-model="topK"
                :min="1"
                :max="20"
                :step="1"
                size="small"
                style="width: 80px"
              />
            </div>
          </div>

          <div class="metadata-filter-grid">
            <a-input v-model="filterModule" placeholder="模块过滤" allow-clear />
            <a-input v-model="filterVersion" placeholder="版本过滤" allow-clear />
            <a-input v-model="filterBusinessDomain" placeholder="业务域过滤" allow-clear />
            <a-input v-model="filterDocumentStage" placeholder="阶段过滤" allow-clear />
            <a-input v-model="filterTagsText" placeholder="标签过滤，逗号分隔" allow-clear />
          </div>

          <a-textarea
            v-model="filterMetadataText"
            placeholder='自定义元数据过滤 JSON，例如：{"priority":"P0","owner":"QA"}'
            :rows="3"
            style="margin-bottom: 12px"
          />

          <a-button type="primary" :loading="queryLoading" @click="testQuery" style="width: 100%">
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
              <div class="answer-content" v-html="renderAnswer(queryResult)"></div>
            </div>
            <div class="sources">
              <strong>相关内容 ({{ queryResult.sources.length }} 条):</strong>
              <div
                v-for="(source, index) in queryResult.sources"
                :key="index"
                class="source-item"
              >
                <div class="source-content">{{ source.content }}</div>
                <div class="source-meta">
                  <span>文档: {{ source.metadata.title }}</span>
                  <span> | 相似度: {{ (source.similarity_score * 100).toFixed(1) }}%</span>
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

    <DocumentUploadModal
      :visible="isUploadModalVisible"
      :knowledge-base-id="knowledgeBase.id"
      @submit="handleDocumentUploaded"
      @cancel="closeUploadModal"
    />

    <DocumentDetailModal
      :visible="isDocumentDetailVisible"
      :document-id="selectedDocumentId"
      @close="closeDocumentDetail"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { Message } from '@arco-design/web-vue';
import {
  IconClose,
  IconExclamationCircle,
  IconRefresh,
  IconUpload,
} from '@arco-design/web-vue/es/icon';
import { useProjectStore } from '@/store/projectStore';
import { KnowledgeService } from '../services/knowledgeService';
import type { Document, KnowledgeBase, QueryResponse } from '../types/knowledge';
import DocumentDetailModal from './DocumentDetailModal.vue';
import DocumentUploadModal from './DocumentUploadModal.vue';

interface Props {
  knowledgeBase: KnowledgeBase;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  refresh: [];
  close: [];
}>();

const projectStore = useProjectStore();

const documents = ref<Document[]>([]);
const documentsLoading = ref(false);
const queryText = ref('');
const queryLoading = ref(false);
const queryResult = ref<QueryResponse | null>(null);
const similarityThreshold = ref(0.3);
const topK = ref(3);
const filterModule = ref('');
const filterVersion = ref('');
const filterBusinessDomain = ref('');
const filterDocumentStage = ref('');
const filterTagsText = ref('');
const filterMetadataText = ref('');
const documentSearchText = ref('');
const documentStatusFilter = ref('');
const documentModuleFilter = ref('');
const documentVersionFilter = ref('');
const documentBusinessDomainFilter = ref('');
const documentStageFilter = ref('');
const documentTagsFilter = ref('');
const isUploadModalVisible = ref(false);
const isDocumentDetailVisible = ref(false);
const selectedDocumentId = ref<string | null>(null);

const normalizeText = (value?: string | null) => (value || '').trim().toLowerCase();

const parseTagFilter = (value: string) =>
  value
    .split(',')
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);

const filteredDocuments = computed(() => {
  const searchText = normalizeText(documentSearchText.value);
  const tagFilters = parseTagFilter(documentTagsFilter.value);

  return documents.value.filter((document) => {
    if (documentStatusFilter.value && document.status !== documentStatusFilter.value) {
      return false;
    }

    if (
      documentModuleFilter.value &&
      !normalizeText(document.module).includes(normalizeText(documentModuleFilter.value))
    ) {
      return false;
    }

    if (
      documentVersionFilter.value &&
      !normalizeText(document.version).includes(normalizeText(documentVersionFilter.value))
    ) {
      return false;
    }

    if (
      documentBusinessDomainFilter.value &&
      !normalizeText(document.business_domain).includes(normalizeText(documentBusinessDomainFilter.value))
    ) {
      return false;
    }

    if (
      documentStageFilter.value &&
      !normalizeText(document.document_stage).includes(normalizeText(documentStageFilter.value))
    ) {
      return false;
    }

    if (tagFilters.length) {
      const documentTags = (document.tags || []).map((tag) => tag.toLowerCase());
      if (!tagFilters.every((tag) => documentTags.some((item) => item.includes(tag)))) {
        return false;
      }
    }

    if (!searchText) {
      return true;
    }

    const haystack = [
      document.title,
      document.module,
      document.version,
      document.business_domain,
      document.document_stage,
      document.error_message,
      ...(document.tags || []),
      ...Object.entries(document.metadata || {}).map(([key, value]) => `${key}:${String(value)}`),
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();

    return haystack.includes(searchText);
  });
});

const renderAnswer = (result: QueryResponse): string => escapeHtml(result.answer);

const escapeHtml = (text: string): string => {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
};

const documentColumns = [
  {
    title: '文档名称',
    dataIndex: 'title',
    width: 180,
    slotName: 'title',
  },
  {
    title: '类型',
    dataIndex: 'document_type',
    width: 70,
  },
  {
    title: '状态',
    dataIndex: 'status',
    slotName: 'status',
    width: 90,
  },
  {
    title: '标签',
    slotName: 'tags',
    width: 180,
  },
  {
    title: '元数据摘要',
    slotName: 'metaSummary',
    width: 220,
  },
  {
    title: '分块数',
    dataIndex: 'chunk_count',
    width: 80,
  },
  {
    title: '上传者',
    dataIndex: 'uploader_name',
    width: 100,
  },
  {
    title: '上传时间',
    dataIndex: 'uploaded_at',
    width: 120,
    render: ({ record }: { record: Document }) => new Date(record.uploaded_at).toLocaleDateString(),
  },
  {
    title: '操作',
    slotName: 'actions',
    width: 160,
  },
];

const formatDate = (dateString: string) => new Date(dateString).toLocaleString();

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
    const response = await KnowledgeService.getDocuments({
      knowledge_base: props.knowledgeBase.id,
    });
    documents.value = response;
  } catch (error: any) {
    Message.error(error?.message || '获取文档列表失败');
  } finally {
    documentsLoading.value = false;
  }
};

const reprocessDocument = async (documentId: string) => {
  try {
    await KnowledgeService.reprocessDocument(documentId);
    Message.success('文档已提交重新处理');
    await fetchDocuments();
  } catch (error) {
    console.error('重新处理文档失败:', error);
    Message.error('重新处理文档失败');
  }
};

const reprocessAllDocuments = async () => {
  try {
    const result = await KnowledgeService.reprocessKnowledgeBaseDocuments(props.knowledgeBase.id);
    Message.success(result.message || '已提交批量重处理任务');
    await fetchDocuments();
  } catch (error: any) {
    console.error('批量重新处理文档失败:', error);
    Message.error(error?.message || '批量重新处理文档失败');
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

  let metadataFilter: Record<string, any> | undefined;
  if (filterMetadataText.value.trim()) {
    try {
      const parsed = JSON.parse(filterMetadataText.value);
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        metadataFilter = parsed;
      } else {
        Message.warning('自定义元数据过滤必须是 JSON 对象');
        return;
      }
    } catch {
      Message.warning('自定义元数据过滤 JSON 格式不合法');
      return;
    }
  }

  queryLoading.value = true;
  try {
    const result = await KnowledgeService.queryKnowledgeBase(props.knowledgeBase.id, {
      query: queryText.value,
      knowledge_base_id: props.knowledgeBase.id,
      top_k: topK.value,
      similarity_threshold: similarityThreshold.value,
      include_metadata: true,
      module: filterModule.value.trim() || undefined,
      version: filterVersion.value.trim() || undefined,
      business_domain: filterBusinessDomain.value.trim() || undefined,
      document_stage: filterDocumentStage.value.trim() || undefined,
      tags: parseTagFilter(filterTagsText.value),
      metadata_filter: metadataFilter,
    });
    queryResult.value = result;
  } catch (error: any) {
    console.error('查询失败:', error);
    Message.error(error?.message || '查询失败');
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

const getProjectName = (projectId: number | string) => {
  if (props.knowledgeBase.project_name) {
    return props.knowledgeBase.project_name;
  }

  const numericId = typeof projectId === 'string' ? parseInt(projectId, 10) : projectId;
  const project = projectStore.projectOptions.find((item) => item.value === numericId);
  return project ? project.label : String(projectId);
};

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
  border-bottom: 1px solid var(--theme-border);
  margin-bottom: 20px;
}

.detail-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
}

.detail-content {
  flex: 1;
  overflow-y: auto;
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  margin-bottom: 24px;
}

.info-section {
  margin-bottom: 24px;
  padding: 20px;
  background: color-mix(in srgb, var(--theme-surface-soft) 72%, white 28%);
  border-radius: 8px;
  border: 1px solid var(--theme-border);
}

.info-section h4,
.query-section h4,
.section-header h4 {
  margin: 0 0 16px;
  font-size: 15px;
  font-weight: 700;
  color: var(--theme-text);
}

.info-item {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.label {
  width: 88px;
  flex-shrink: 0;
  color: var(--theme-text-secondary);
  font-size: 13px;
  font-weight: 500;
}

.value {
  flex: 1;
  color: var(--theme-text);
  font-size: 13px;
}

.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.stat-item {
  padding: 12px;
  border-radius: 6px;
  text-align: center;
  background: color-mix(in srgb, var(--theme-surface-soft) 72%, white 28%);
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #00a0e9;
}

.stat-label {
  margin-top: 4px;
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.documents-section,
.query-section {
  margin-bottom: 24px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.document-filter-grid,
.metadata-filter-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}

.documents-list {
  max-height: 320px;
  overflow-y: auto;
}

.status-cell {
  display: flex;
  align-items: center;
}

.status-error-icon {
  margin-left: 4px;
  color: #f53f3f;
  cursor: help;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.meta-summary {
  display: grid;
  gap: 2px;
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.muted-text {
  color: var(--theme-text-tertiary);
  font-size: 12px;
}

.query-settings {
  display: flex;
  gap: 24px;
  margin-bottom: 12px;
  padding: 12px;
  background: color-mix(in srgb, var(--theme-surface-soft) 72%, white 28%);
  border-radius: 6px;
  border: 1px solid var(--theme-border);
}

.setting-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.setting-item label {
  min-width: 80px;
  white-space: nowrap;
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.value-display {
  min-width: 30px;
  font-size: 12px;
  font-weight: 500;
}

.query-result {
  margin-top: 16px;
  padding: 12px;
  background: color-mix(in srgb, var(--theme-surface-soft) 72%, white 28%);
  border-radius: 6px;
}

.query-result h5 {
  margin: 0 0 12px;
  font-size: 13px;
  font-weight: 700;
}

.query-info,
.answer,
.sources {
  margin-bottom: 12px;
}

.query-info p,
.answer-content,
.source-content {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.5;
}

.source-item {
  margin: 8px 0;
  padding: 8px;
  background: var(--theme-surface);
  border-left: 3px solid #00a0e9;
  border-radius: 4px;
}

.source-meta,
.timing {
  font-size: 10px;
  color: var(--theme-text-secondary);
}

.document-title-link {
  color: #00a0e9;
  cursor: pointer;
  transition: color 0.2s;
}

.document-title-link:hover {
  color: #0e42d2;
  text-decoration: underline;
}
</style>
