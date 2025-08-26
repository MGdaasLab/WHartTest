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
      <!-- 基本信息 -->
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
          <a-descriptions-item v-if="documentContent.url" label="原始URL" :span="2">
            <a :href="documentContent.url" target="_blank" rel="noopener noreferrer" class="url-link">
              {{ documentContent.url }}
            </a>
          </a-descriptions-item>
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
        </a-descriptions>
      </div>

      <!-- 文档分块内容 -->
      <div v-if="showChunks" class="chunks-section">
        <div class="section-header">
          <h4>文档内容（分块显示）</h4>
          <div class="content-actions">
            <a-switch
              v-model="includeChunks"
              checked-text="显示分块"
              unchecked-text="隐藏分块"
              @change="handleChunksToggle"
            />
            <a-button
              v-if="documentContent.file_url"
              type="outline"
              size="small"
              @click="downloadFile"
            >
              下载原文件
            </a-button>
            <a-button
              v-if="documentContent.url"
              type="primary"
              size="small"
              @click="openOriginalUrl"
            >
              查看原网页
            </a-button>
          </div>
        </div>

        <div v-if="includeChunks && documentContent.chunks" class="chunks-content">
          <div class="chunks-info">
            <span class="chunks-summary">
              共 {{ documentContent.chunks.total_count }} 个分块，当前显示第 {{ chunkPagination.current }} 页
            </span>
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
            <div
              v-for="chunk in documentContent.chunks.items"
              :key="chunk.id"
              class="chunk-item"
            >
              <div class="chunk-header">
                <span class="chunk-index">分块 #{{ chunk.chunk_index + 1 }}</span>
                <span class="chunk-length">{{ chunk.content.length }} 字符</span>
                <span v-if="chunk.start_index !== null && chunk.end_index !== null" class="chunk-range">
                  位置: {{ chunk.start_index }} - {{ chunk.end_index }}
                </span>
                <span v-if="chunk.page_number" class="chunk-page">
                  第 {{ chunk.page_number }} 页
                </span>
              </div>
              <div class="chunk-content">
                <pre>{{ chunk.content }}</pre>
              </div>
            </div>
          </div>
        </div>

        <!-- 当分块隐藏时显示原始内容预览 -->
        <div v-else class="original-content-preview">
          <div class="preview-notice">
            <p>分块显示已关闭，以下是原始文档内容预览：</p>
          </div>
          <div class="content-display">
            <div class="content-preview">
              <pre class="content-text">{{ documentContent.content }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>

    <a-empty v-else description="无法加载文档内容" />
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue';
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

// 响应式数据
const loading = ref(false);
const documentContent = ref<DocumentContentResponse | null>(null);
const includeChunks = ref(true);
const chunkPagination = ref({
  current: 1,
  pageSize: 10,
});

// 计算属性
const showChunks = computed(() => {
  if (!documentContent.value) return false;
  const chunkCount = documentContent.value.chunks?.total_count ?? documentContent.value.chunk_count ?? 0;
  return chunkCount > 0;
});

// 方法
const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleString();
};

const formatFileSize = (bytes: number) => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
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
    pdf: 'PDF文档',
    docx: 'Word文档',
    pptx: 'PowerPoint文档',
    txt: '文本文件',
    md: 'Markdown文档',
    html: 'HTML文档',
    url: '网页链接',
  };
  return typeMap[type] || type.toUpperCase();
};

const getChunkCount = () => {
  if (!documentContent.value) return 0;
  // 优先使用 chunks.total_count，如果没有则使用 chunk_count
  return documentContent.value.chunks?.total_count ?? documentContent.value.chunk_count ?? 0;
};

const fetchDocumentContent = async (documentId: string) => {
  loading.value = true;
  try {
    const params = {
      include_chunks: includeChunks.value,
      chunk_page: chunkPagination.value.current,
      chunk_page_size: chunkPagination.value.pageSize,
    };

    const response = await KnowledgeService.getDocumentContent(documentId, params);
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
    chunkPagination.value.current = 1; // 重置分页
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
  chunkPagination.value.current = 1; // 重置到第一页
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

// 监听器
watch(
  () => props.visible,
  (newVisible) => {
    if (newVisible && props.documentId) {
      fetchDocumentContent(props.documentId);
    } else if (!newVisible) {
      // 关闭时重置数据
      documentContent.value = null;
      includeChunks.value = true;
      chunkPagination.value = { current: 1, pageSize: 10 };
    }
  }
);

watch(
  () => props.documentId,
  (newDocumentId) => {
    if (props.visible && newDocumentId) {
      fetchDocumentContent(newDocumentId);
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
.content-section,
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

.content-display {
  border: 1px solid #e5e6eb;
  border-radius: 6px;
  overflow: hidden;
}

.content-preview {
  max-height: 400px;
  overflow-y: auto;
  padding: 16px;
  background-color: #fafbfc;
}

.content-text {
  margin: 0;
  padding: 0;
  background: none;
  border: none;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: break-word;
  color: #1d2129;
}

.original-content-preview {
  margin-top: 16px;
}

.preview-notice {
  margin-bottom: 12px;
  padding: 8px 12px;
  background-color: #fff7e6;
  border: 1px solid #ffd591;
  border-radius: 4px;
  color: #d46b08;
}

.preview-notice p {
  margin: 0;
  font-size: 14px;
}

.chunks-info {
  margin-bottom: 12px;
  padding: 8px 12px;
  background-color: #f7f8fa;
  border-radius: 4px;
  border-left: 3px solid #165dff;
}

.chunks-summary {
  font-size: 14px;
  color: #4e5969;
  font-weight: 500;
}

.chunks-pagination {
  margin-bottom: 16px;
  text-align: right;
}

.chunks-list {
  space-y: 12px;
}

.chunk-item {
  border: 1px solid #e5e6eb;
  border-radius: 6px;
  padding: 16px;
  margin-bottom: 12px;
  background-color: #fff;
  transition: box-shadow 0.2s ease;
}

.chunk-item:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.chunk-header {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
  font-size: 12px;
  color: #86909c;
  flex-wrap: wrap;
}

.chunk-index {
  font-weight: 600;
  color: #1d2129;
  background-color: #f2f3f5;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
}

.chunk-length {
  color: #165dff;
  font-weight: 500;
}

.chunk-content {
  line-height: 1.6;
}

.chunk-content pre {
  margin: 0;
  padding: 0;
  background: none;
  border: none;
  font-family: inherit;
  font-size: inherit;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: break-word;
}
</style>
