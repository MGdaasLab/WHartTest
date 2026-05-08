<template>
  <a-modal
    :visible="visible"
    :title="`文档详情 - ${documentContent?.title || ''}`"
    :width="1000"
    :footer="false"
    @cancel="handleClose"
  >
    <div v-if="loading" class="loading-container">
      <a-spin size="large" />
      <div class="loading-text">正在加载文档内容...</div>
    </div>

    <div v-else-if="documentContent" class="document-detail">
      <div class="info-section">
        <h4>基本信息</h4>
        <a-descriptions :column="2" bordered>
          <a-descriptions-item label="文档标题">{{ documentContent.title }}</a-descriptions-item>
          <a-descriptions-item label="文档类型">{{ getDocumentTypeText(documentContent.document_type) }}</a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-tag :color="getStatusColor(documentContent.status)">
              {{ getStatusText(documentContent.status) }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="分块数量">{{ getChunkCount() }}</a-descriptions-item>
          <a-descriptions-item label="上传者">{{ documentContent.uploader_name }}</a-descriptions-item>
          <a-descriptions-item label="上传时间">{{ formatDate(documentContent.uploaded_at) }}</a-descriptions-item>
          <a-descriptions-item v-if="documentContent.processed_at" label="处理时间">
            {{ formatDate(documentContent.processed_at) }}
          </a-descriptions-item>
          <a-descriptions-item v-if="documentContent.file_size" label="文件大小">
            {{ formatFileSize(documentContent.file_size) }}
          </a-descriptions-item>
          <a-descriptions-item v-if="documentContent.page_count" label="页数">
            {{ documentContent.page_count }}
          </a-descriptions-item>
          <a-descriptions-item v-if="documentContent.word_count" label="字数">
            {{ documentContent.word_count }}
          </a-descriptions-item>
          <a-descriptions-item label="所属知识库">{{ documentContent.knowledge_base.name }}</a-descriptions-item>
          <a-descriptions-item v-if="documentContent.file_name" label="文件名">
            {{ documentContent.file_name }}
          </a-descriptions-item>
          <a-descriptions-item v-if="documentContent.url" label="原始 URL" :span="2">
            <a :href="documentContent.url" target="_blank" rel="noopener noreferrer" class="url-link">
              {{ documentContent.url }}
            </a>
          </a-descriptions-item>
        </a-descriptions>
      </div>

      <div class="info-section">
        <h4>业务元数据</h4>
        <a-descriptions :column="2" bordered>
          <a-descriptions-item label="模块">{{ documentContent.module || '-' }}</a-descriptions-item>
          <a-descriptions-item label="版本">{{ documentContent.version || '-' }}</a-descriptions-item>
          <a-descriptions-item label="业务域">{{ documentContent.business_domain || '-' }}</a-descriptions-item>
          <a-descriptions-item label="文档阶段">{{ documentContent.document_stage || '-' }}</a-descriptions-item>
          <a-descriptions-item label="标签" :span="2">
            <div v-if="documentContent.tags?.length" class="tag-list">
              <a-tag v-for="tag in documentContent.tags" :key="tag">{{ tag }}</a-tag>
            </div>
            <span v-else>-</span>
          </a-descriptions-item>
          <a-descriptions-item label="自定义元数据" :span="2">
            <pre class="metadata-block">{{ formatMetadata(documentContent.metadata) }}</pre>
          </a-descriptions-item>
        </a-descriptions>
      </div>

      <div class="chunks-section">
        <div class="section-header">
          <h4>文档内容</h4>
          <div class="content-actions">
            <a-switch
              v-if="showChunks"
              v-model="includeChunks"
              checked-text="分块视图"
              unchecked-text="原始内容"
              @change="handleChunksToggle"
            />
            <a-button v-if="documentContent.file_url" type="outline" size="small" @click="downloadFile">
              下载原文件
            </a-button>
            <a-button v-if="documentContent.url" type="primary" size="small" @click="openOriginalUrl">
              查看原网页
            </a-button>
          </div>
        </div>

        <div v-if="includeChunks && documentContent.chunks" class="chunks-content">
          <div class="chunks-info">
            共 {{ documentContent.chunks.total_count }} 个分块，当前第 {{ chunkPagination.current }} 页
          </div>

          <div class="chunks-pagination">
            <a-pagination
              :current="chunkPagination.current"
              :page-size="chunkPagination.pageSize"
              :total="documentContent.chunks.total_count"
              :show-total="true"
              :show-jumper="true"
              :show-page-size="true"
              :page-size-options="['5', '10', '20', '50']"
              @change="handleChunkPageChange"
              @page-size-change="handleChunkPageSizeChange"
            />
          </div>

          <div class="chunks-list">
            <div v-for="chunk in documentContent.chunks.items" :key="chunk.id" class="chunk-item">
              <div class="chunk-header">
                <span class="chunk-index">分块 #{{ chunk.chunk_index + 1 }}</span>
                <span class="chunk-length">{{ chunk.content.length }} 字符</span>
                <span v-if="chunk.start_index !== null && chunk.end_index !== null" class="chunk-range">
                  位置: {{ chunk.start_index }} - {{ chunk.end_index }}
                </span>
                <span v-if="chunk.page_number" class="chunk-page">页码: {{ chunk.page_number }}</span>
              </div>
              <div class="chunk-content">
                <pre>{{ chunk.content }}</pre>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="content-display">
          <div class="content-preview">
            <pre class="content-text">{{ documentContent.content }}</pre>
          </div>
        </div>
      </div>
    </div>

    <a-empty v-else description="无法加载文档内容" />
  </a-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { Message } from '@arco-design/web-vue';
import { KnowledgeService } from '../services/knowledgeService';
import type { DocumentContentResponse } from '../types/knowledge';

interface Props {
  visible: boolean;
  documentId: string | null;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  close: [];
}>();

const loading = ref(false);
const documentContent = ref<DocumentContentResponse | null>(null);
const includeChunks = ref(false);
const chunkPagination = ref({
  current: 1,
  pageSize: 10,
});

const showChunks = computed(() => {
  if (!documentContent.value) return false;
  const chunkCount = documentContent.value.chunks?.total_count ?? documentContent.value.chunk_count ?? 0;
  return chunkCount > 0;
});

const formatDate = (dateString: string) => new Date(dateString).toLocaleString();

const formatFileSize = (bytes: number) => {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const index = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${parseFloat((bytes / 1024 ** index).toFixed(2))} ${units[index]}`;
};

const formatMetadata = (metadata?: Record<string, any>) => {
  if (!metadata || Object.keys(metadata).length === 0) {
    return '-';
  }
  return JSON.stringify(metadata, null, 2);
};

const getStatusColor = (status: string) => {
  const colorMap: Record<string, string> = {
    pending: 'orange',
    processing: 'blue',
    completed: 'green',
    failed: 'red',
  };
  return colorMap[status] || 'gray';
};

const getStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    pending: '待处理',
    processing: '处理中',
    completed: '已完成',
    failed: '处理失败',
  };
  return textMap[status] || status;
};

const getDocumentTypeText = (type: string) => {
  const typeMap: Record<string, string> = {
    pdf: 'PDF',
    docx: 'Word',
    doc: 'Word',
    pptx: 'PowerPoint',
    txt: '文本',
    md: 'Markdown',
    html: 'HTML',
    url: '网页链接',
  };
  return typeMap[type] || type.toUpperCase();
};

const getChunkCount = () => {
  if (!documentContent.value) return 0;
  return documentContent.value.chunks?.total_count ?? documentContent.value.chunk_count ?? 0;
};

const fetchDocumentContent = async (documentId: string) => {
  loading.value = true;
  try {
    const response = await KnowledgeService.getDocumentContent(documentId, {
      include_chunks: includeChunks.value,
      chunk_page: chunkPagination.value.current,
      chunk_page_size: chunkPagination.value.pageSize,
    });
    documentContent.value = response;
  } catch (error) {
    console.error('获取文档内容失败:', error);
    Message.error('获取文档内容失败');
    documentContent.value = null;
  } finally {
    loading.value = false;
  }
};

const handleChunksToggle = () => {
  if (props.documentId) {
    chunkPagination.value.current = 1;
    fetchDocumentContent(props.documentId);
  }
};

const handleChunkPageChange = (page: number) => {
  chunkPagination.value.current = page;
  if (props.documentId) {
    fetchDocumentContent(props.documentId);
  }
};

const handleChunkPageSizeChange = (pageSize: number) => {
  chunkPagination.value.pageSize = pageSize;
  chunkPagination.value.current = 1;
  if (props.documentId) {
    fetchDocumentContent(props.documentId);
  }
};

const downloadFile = () => {
  if (documentContent.value?.file_url) {
    window.open(documentContent.value.file_url, '_blank');
  }
};

const openOriginalUrl = () => {
  if (documentContent.value?.url) {
    window.open(documentContent.value.url, '_blank', 'noopener,noreferrer');
  }
};

const handleClose = () => {
  emit('close');
};

watch(
  () => props.visible,
  (visible) => {
    if (visible && props.documentId) {
      fetchDocumentContent(props.documentId);
    } else if (!visible) {
      documentContent.value = null;
      includeChunks.value = false;
      chunkPagination.value = { current: 1, pageSize: 10 };
    }
  }
);

watch(
  () => props.documentId,
  (documentId) => {
    if (props.visible && documentId) {
      fetchDocumentContent(documentId);
    }
  }
);
</script>

<style scoped>
.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.loading-text {
  margin-top: 12px;
  color: #86909c;
}

.document-detail {
  max-height: 70vh;
  overflow-y: auto;
}

.info-section,
.chunks-section {
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
  font-size: 16px;
  font-weight: 600;
}

.content-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.url-link {
  color: #165dff;
  text-decoration: none;
  word-break: break-all;
}

.url-link:hover {
  text-decoration: underline;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.metadata-block,
.content-text,
.chunk-content pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: break-word;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
}

.metadata-block {
  padding: 8px 12px;
  border-radius: 6px;
  background: color-mix(in srgb, var(--theme-surface-soft) 72%, white 28%);
}

.content-display {
  border: 1px solid var(--theme-border);
  border-radius: 6px;
  overflow: hidden;
}

.content-preview {
  max-height: 400px;
  overflow-y: auto;
  padding: 16px;
  background-color: var(--theme-surface-soft);
}

.chunks-info {
  margin-bottom: 12px;
  padding: 8px 12px;
  border-left: 3px solid #165dff;
  border-radius: 4px;
  background-color: color-mix(in srgb, var(--theme-surface-soft) 72%, white 28%);
}

.chunks-pagination {
  margin-bottom: 12px;
}

.chunks-list {
  display: grid;
  gap: 12px;
}

.chunk-item {
  border: 1px solid var(--theme-border);
  border-radius: 6px;
  overflow: hidden;
}

.chunk-header {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 10px 12px;
  background: color-mix(in srgb, var(--theme-surface-soft) 72%, white 28%);
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.chunk-index {
  font-weight: 600;
  color: var(--theme-text);
}

.chunk-content {
  padding: 12px;
}
</style>
