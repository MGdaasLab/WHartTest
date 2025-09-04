<template>
  <div class="requirement-management">
    <!-- 搜索和筛选 -->
    <div class="filter-section">
      <div class="filter-row">
        <a-input-search
          v-model="searchKeyword"
          placeholder="搜索文档标题或描述"
          style="width: 300px"
          @search="handleSearch"
          @clear="handleSearch"
          allow-clear
        />
        <a-select
          v-model="statusFilter"
          placeholder="文档状态"
          style="width: 150px; margin-left: 12px"
          @change="handleSearch"
          allow-clear
        >
          <a-option value="">全部状态</a-option>
          <a-option value="uploaded">已上传</a-option>
          <a-option value="processing">处理中</a-option>
          <a-option value="module_split">模块拆分中</a-option>
          <a-option value="user_reviewing">用户调整中</a-option>
          <a-option value="ready_for_review">待评审</a-option>
          <a-option value="reviewing">评审中</a-option>
          <a-option value="review_completed">评审完成</a-option>
          <a-option value="failed">处理失败</a-option>
        </a-select>
        <a-select
          v-model="typeFilter"
          placeholder="文档类型"
          style="width: 120px; margin-left: 12px"
          @change="handleSearch"
          allow-clear
        >
          <a-option value="">全部类型</a-option>
          <a-option value="pdf">PDF</a-option>
          <a-option value="docx">Word</a-option>
          <a-option value="pptx">PPT</a-option>
          <a-option value="md">Markdown</a-option>
          <a-option value="txt">文本</a-option>
          <a-option value="html">HTML</a-option>
        </a-select>
        <a-button type="primary" @click="showUploadModal" style="margin-left: 12px">
          <template #icon><icon-plus /></template>
          上传需求文档
        </a-button>
      </div>
    </div>

    <!-- 文档列表 -->
    <div class="content-section">
      <a-table
        :columns="columns"
        :data="documentList"
        :loading="loading"
        :pagination="pagination"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
        row-key="id"
      >
        <!-- 状态列 -->
        <template #status="{ record }">
          <a-tag :color="getStatusColor(record.status)">
            {{ getStatusText(record.status) }}
          </a-tag>
        </template>

        <!-- 文档类型列 -->
        <template #document_type="{ record }">
          <a-tag color="blue">{{ getTypeText(record.document_type) }}</a-tag>
        </template>

        <!-- 统计信息列 -->
        <template #stats="{ record }">
          <div class="stats-info">
            <span class="stat-item">{{ record.word_count || 0 }} 字</span>
            <span class="stat-item">{{ record.page_count || 0 }} 页</span>
            <span class="stat-item">{{ record.modules_count || 0 }} 模块</span>
          </div>
        </template>

        <!-- 操作列 -->
        <template #actions="{ record }">
          <a-space>
            <a-button type="text" size="small" @click="viewDocument(record)">
              查看详情
            </a-button>
            <a-button
              v-if="record.status === 'uploaded'"
              type="text"
              size="small"
              @click="viewDocument(record)"
            >
              配置拆分
            </a-button>
            <a-button
              v-if="record.status === 'ready_for_review'"
              type="text"
              size="small"
              @click="startReview(record)"
            >
              开始评审
            </a-button>
            <a-button
              v-if="record.status === 'review_completed'"
              type="text"
              size="small"
              @click="viewReports(record)"
            >
              查看报告
            </a-button>
            <a-button
              v-if="record.status === 'review_completed'"
              type="text"
              size="small"
              @click="restartReview(record)"
            >
              重新评审
            </a-button>
            <a-button
              v-if="record.status === 'failed'"
              type="text"
              size="small"
              @click="retryReview(record)"
            >
              重试评审
            </a-button>
            <a-popconfirm
              content="确定要删除这个文档吗？"
              @ok="deleteDocument(record)"
            >
              <a-button type="text" size="small" status="danger">
                删除
              </a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </a-table>
    </div>

    <!-- 上传文档模态框 -->
    <a-modal
      v-model:visible="uploadModalVisible"
      title="上传需求文档"
      width="600px"
      @ok="handleUpload"
      @cancel="resetUploadForm"
      :confirm-loading="uploadLoading"
    >
      <a-form
        ref="uploadFormRef"
        :model="uploadForm"
        :rules="uploadRules"
        layout="vertical"
      >
        <a-form-item label="文档标题" field="title">
          <a-input v-model="uploadForm.title" placeholder="请输入文档标题" />
        </a-form-item>
        <a-form-item label="文档描述" field="description">
          <a-textarea
            v-model="uploadForm.description"
            placeholder="请输入文档描述（可选）"
            :rows="3"
          />
        </a-form-item>
        <a-form-item label="上传方式" field="uploadType">
          <a-radio-group v-model="uploadForm.uploadType" @change="handleUploadTypeChange">
            <a-radio value="file">上传文件</a-radio>
            <a-radio value="content">直接输入</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item
          v-if="uploadForm.uploadType === 'file'"
          label="选择文件"
          field="file"
        >
          <a-upload
            ref="uploadRef"
            :file-list="fileList"
            :auto-upload="false"
            :show-file-list="true"
            :limit="1"
            accept=".pdf,.doc,.docx,.ppt,.pptx,.txt,.md,.html"
            @change="handleFileChange"
          >
            <template #upload-button>
              <div class="upload-area">
                <icon-upload />
                <div>点击上传文件</div>
                <div class="upload-tip">支持 PDF、Word、PPT、文本、Markdown、HTML</div>
              </div>
            </template>
            <template #upload-item="{ fileItem, index }">
              <div class="upload-file-item">
                <div class="file-info">
                  <icon-file />
                  <span class="file-name">{{ fileItem.name }}</span>
                  <span class="file-size">({{ formatFileSize(fileItem.file?.size || fileItem.size) }})</span>
                </div>
                <a-button
                  type="text"
                  size="mini"
                  status="danger"
                  @click="removeFile(index)"
                >
                  <template #icon><icon-delete /></template>
                </a-button>
              </div>
            </template>
          </a-upload>
        </a-form-item>
        <a-form-item
          v-if="uploadForm.uploadType === 'content'"
          label="文档内容"
          field="content"
        >
          <a-textarea
            v-model="uploadForm.content"
            placeholder="请输入或粘贴文档内容"
            :rows="8"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { Message, Modal } from '@arco-design/web-vue';
import { IconPlus, IconUpload, IconFile, IconDelete } from '@arco-design/web-vue/es/icon';
import { useProjectStore } from '@/store/projectStore';
import { RequirementDocumentService } from '../services/requirementService';
import type {
  RequirementDocument,
  DocumentStatus,
  DocumentType,
  CreateDocumentRequest,
  DocumentListParams
} from '../types';
import {
  DocumentStatusDisplay,
  DocumentTypeDisplay
} from '../types';

// Store and Router
const projectStore = useProjectStore();
const router = useRouter();

// 响应式数据
const loading = ref(false);
const documentList = ref<RequirementDocument[]>([]);
const searchKeyword = ref('');
const statusFilter = ref<DocumentStatus | ''>('');
const typeFilter = ref<DocumentType | ''>('');

// 分页
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: true,
  showPageSize: true,
});

// 上传相关
const uploadModalVisible = ref(false);
const uploadLoading = ref(false);
const uploadFormRef = ref();
const uploadRef = ref();
const fileList = ref<any[]>([]);

const uploadForm = reactive<CreateDocumentRequest & { uploadType: 'file' | 'content' }>({
  title: '',
  description: '',
  document_type: 'pdf',
  project: '',
  uploadType: 'file',
  file: undefined,
  content: ''
});

// 表单验证规则
const uploadRules = {
  title: [
    { required: true, message: '请输入文档标题' },
    { maxLength: 200, message: '标题长度不能超过200个字符' }
  ],
  description: [
    { maxLength: 500, message: '描述长度不能超过500个字符' }
  ],
  file: [
    {
      required: true,
      message: '请选择文件',
      validator: (_value: any, callback: Function) => {
        if (uploadForm.uploadType === 'file' && !uploadForm.file) {
          callback('请选择文件');
        } else {
          callback();
        }
      }
    }
  ],
  content: [
    {
      required: true,
      message: '请输入文档内容',
      validator: (_value: any, callback: Function) => {
        if (uploadForm.uploadType === 'content' && !uploadForm.content) {
          callback('请输入文档内容');
        } else {
          callback();
        }
      }
    }
  ]
};

// 表格列定义
const columns = [
  {
    title: '文档标题',
    dataIndex: 'title',
    width: 300,
    ellipsis: true,
    tooltip: true
  },
  {
    title: '描述',
    dataIndex: 'description',
    width: 80,
    ellipsis: true,
    tooltip: true,
    render: ({ record }: { record: RequirementDocument }) => {
      return record.description || '暂无描述';
    }
  },
  {
    title: '状态',
    dataIndex: 'status',
    slotName: 'status',
    width: 80
  },
  {
    title: '类型',
    dataIndex: 'document_type',
    slotName: 'document_type',
    width: 80
  },
  {
    title: '统计信息',
    slotName: 'stats',
    width: 150
  },
  {
    title: '上传者',
    dataIndex: 'uploader_name',
    width: 80
  },
  {
    title: '上传时间',
    dataIndex: 'uploaded_at',
    width: 150,
    render: ({ record }: { record: RequirementDocument }) => {
      return new Date(record.uploaded_at).toLocaleString();
    }
  },
  {
    title: '操作',
    slotName: 'actions',
    width: 280,
    fixed: 'right',
    align: 'center'
  }
];

// 计算属性
const currentProjectId = computed(() => projectStore.currentProjectId);

// 方法
const getStatusColor = (status: DocumentStatus) => {
  const colorMap = {
    uploaded: 'blue',
    processing: 'orange',
    module_split: 'orange',
    user_reviewing: 'purple',
    ready_for_review: 'cyan',
    reviewing: 'orange',
    review_completed: 'green',
    failed: 'red'
  };
  return colorMap[status] || 'gray';
};

const getStatusText = (status: DocumentStatus) => {
  return DocumentStatusDisplay[status] || status;
};

const getTypeText = (type: DocumentType) => {
  return DocumentTypeDisplay[type] || type;
};

// 加载文档列表
const loadDocuments = async () => {
  if (!currentProjectId.value) {
    Message.warning('请先选择项目');
    return;
  }

  loading.value = true;
  try {
    const params: DocumentListParams = {
      project: String(currentProjectId.value),
      page: pagination.current,
      page_size: pagination.pageSize
    };

    if (searchKeyword.value) {
      params.search = searchKeyword.value;
    }
    if (statusFilter.value) {
      params.status = statusFilter.value;
    }
    if (typeFilter.value) {
      params.document_type = typeFilter.value;
    }

    const response = await RequirementDocumentService.getDocumentList(params);

    console.log('API响应:', response); // 调试日志

    if (response.status === 'success') {
      // 适配后端返回的数据结构
      if (Array.isArray(response.data)) {
        // 如果直接返回数组
        documentList.value = response.data;
        pagination.total = response.data.length;
      } else if (response.data.results) {
        // 如果是分页格式
        documentList.value = response.data.results;
        pagination.total = response.data.count;
      } else {
        documentList.value = [];
        pagination.total = 0;
      }
    } else {
      Message.error(response.message || '加载文档列表失败');
    }
  } catch (error) {
    console.error('加载文档列表失败:', error);
    Message.error('加载文档列表失败');
  } finally {
    loading.value = false;
  }
};

// 搜索处理
const handleSearch = () => {
  pagination.current = 1;
  loadDocuments();
};

// 分页处理
const handlePageChange = (page: number) => {
  pagination.current = page;
  loadDocuments();
};

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize;
  pagination.current = 1;
  loadDocuments();
};

// 显示上传模态框
const showUploadModal = () => {
  if (!currentProjectId.value) {
    Message.warning('请先选择项目');
    return;
  }
  uploadForm.project = String(currentProjectId.value);
  console.log('打开上传模态框，项目ID:', uploadForm.project); // 调试日志
  uploadModalVisible.value = true;
};

// 文件选择处理
const handleFileChange = (fileListParam: any[], file: any) => {
  console.log('文件选择变化:', fileListParam, file); // 调试日志

  // 更新文件列表
  fileList.value = fileListParam;

  if (file && file.file) {
    uploadForm.file = file.file;
    console.log('设置文件到表单:', file.file); // 调试日志

    // 自动设置文档类型
    const fileName = file.file.name;
    const extension = fileName.split('.').pop()?.toLowerCase();
    if (extension && ['pdf', 'docx', 'pptx', 'txt', 'md', 'html'].includes(extension)) {
      uploadForm.document_type = extension as DocumentType;
    }
    // 如果没有标题，使用文件名
    if (!uploadForm.title) {
      uploadForm.title = fileName.substring(0, fileName.lastIndexOf('.')) || fileName;
    }
  } else if (fileListParam.length === 0) {
    // 文件被移除
    uploadForm.file = undefined;
    console.log('文件被移除'); // 调试日志
  }
};

// 处理上传类型变化
const handleUploadTypeChange = () => {
  if (uploadForm.uploadType === 'content') {
    // 切换到直接输入时，设置文档类型为txt
    uploadForm.document_type = 'txt';
    // 清空文件相关数据
    uploadForm.file = undefined;
    fileList.value = [];
  } else if (uploadForm.uploadType === 'file') {
    // 切换到文件上传时，重置文档类型为pdf
    uploadForm.document_type = 'pdf';
    // 清空内容
    uploadForm.content = '';
  }
};

// 上传处理
const handleUpload = async () => {
  try {
    // 手动验证必填字段
    if (!uploadForm.title.trim()) {
      Message.error('请输入文档标题');
      return;
    }

    if (uploadForm.uploadType === 'file' && !uploadForm.file) {
      Message.error('请选择文件');
      return;
    }

    if (uploadForm.uploadType === 'content' && (!uploadForm.content || !uploadForm.content.trim())) {
      Message.error('请输入文档内容');
      return;
    }

    if (!uploadForm.project) {
      Message.error('请先选择项目');
      return;
    }

    uploadLoading.value = true;

    console.log('上传数据:', uploadForm); // 调试日志

    const response = await RequirementDocumentService.uploadDocument(uploadForm);

    console.log('上传响应:', response); // 调试日志

    if (response.status === 'success') {
      Message.success('文档上传成功');
      uploadModalVisible.value = false;
      resetUploadForm();
      loadDocuments();
    } else {
      Message.error(response.message || '文档上传失败');
    }
  } catch (error) {
    console.error('文档上传失败:', error);
    Message.error('文档上传失败');
  } finally {
    uploadLoading.value = false;
  }
};

// 重置上传表单
const resetUploadForm = () => {
  uploadFormRef.value?.resetFields();
  fileList.value = [];
  Object.assign(uploadForm, {
    title: '',
    description: '',
    document_type: 'pdf',
    project: String(currentProjectId.value || ''),
    uploadType: 'file',
    file: undefined,
    content: ''
  });
};

// 格式化文件大小
const formatFileSize = (size: number | undefined): string => {
  if (!size || isNaN(size)) return '未知大小';
  if (size < 1024) return size + ' B';
  if (size < 1024 * 1024) return (size / 1024).toFixed(1) + ' KB';
  return (size / (1024 * 1024)).toFixed(1) + ' MB';
};

// 移除文件
const removeFile = (index: number) => {
  fileList.value.splice(index, 1);
  uploadForm.file = undefined;
};

// 文档操作
const viewDocument = (document: RequirementDocument) => {
  router.push(`/requirements/${document.id}`);
};

// 移除了startModuleSplit方法，现在统一在详情页面进行拆分配置

const startReview = async (document: RequirementDocument) => {
  try {
    loading.value = true;

    const response = await RequirementDocumentService.startReview(document.id, {
      analysis_type: 'comprehensive',
      parallel_processing: true
    });

    if (response.status === 'success') {
      Message.success('需求评审已开始');
      loadDocuments();
    } else {
      Message.error(response.message || '需求评审启动失败');
    }
  } catch (error) {
    console.error('需求评审启动失败:', error);
    Message.error('需求评审启动失败');
  } finally {
    loading.value = false;
  }
};

// 重新评审
const restartReview = async (document: RequirementDocument) => {
  try {
    // 确认重新评审
    const confirmed = await new Promise((resolve) => {
      Modal.confirm({
        title: '确认重新评审',
        content: `重新评审文档"${document.title}"将创建新的评审报告，原有报告将保留。是否继续？`,
        okText: '确认',
        cancelText: '取消',
        onOk: () => resolve(true),
        onCancel: () => resolve(false),
      });
    });

    if (!confirmed) return;

    loading.value = true;

    const response = await RequirementDocumentService.restartReview(document.id, {
      analysis_type: 'comprehensive',
      parallel_processing: true
    });

    if (response.status === 'success') {
      Message.success('重新评审已开始');
      loadDocuments();
    } else {
      Message.error(response.message || '重新评审启动失败');
    }
  } catch (error) {
    console.error('重新评审启动失败:', error);
    Message.error('重新评审启动失败');
  } finally {
    loading.value = false;
  }
};

// 失败后重试评审
const retryReview = async (document: RequirementDocument) => {
  try {
    // 确认重试
    const confirmed = await new Promise((resolve) => {
      Modal.confirm({
        title: '确认重试评审',
        content: `系统将重新尝试对文档"${document.title}"进行评审处理。是否继续？`,
        okText: '确认',
        cancelText: '取消',
        onOk: () => resolve(true),
        onCancel: () => resolve(false),
      });
    });

    if (!confirmed) return;

    loading.value = true;

    // 对于失败的文档，直接尝试重新开始评审流程
    // 如果文档没有模块信息，后端会自动处理模块拆分
    const response = await RequirementDocumentService.startReview(document.id, {
      analysis_type: 'comprehensive',
      parallel_processing: true
    });

    if (response.status === 'success') {
      Message.success('重试评审已开始');
      loadDocuments();
    } else {
      Message.error(response.message || '重试评审启动失败');
    }
  } catch (error) {
    console.error('重试评审启动失败:', error);
    Message.error('重试评审启动失败');
  } finally {
    loading.value = false;
  }
};

const viewReports = (document: RequirementDocument) => {
  // 跳转到专门的报告页面
  if (document.id) {
    router.push(`/requirements/${document.id}/report`);
  } else {
    Message.warning('暂无评审报告');
  }
};

const deleteDocument = async (document: RequirementDocument) => {
  try {
    loading.value = true;
    const response = await RequirementDocumentService.deleteDocument(document.id);

    if (response.status === 'success') {
      Message.success('文档删除成功');
      loadDocuments();
    } else {
      Message.error(response.message || '文档删除失败');
    }
  } catch (error) {
    console.error('文档删除失败:', error);
    Message.error('文档删除失败');
  } finally {
    loading.value = false;
  }
};

// 生命周期
onMounted(() => {
  if (currentProjectId.value) {
    loadDocuments();
  }
});

// 监听项目变化
projectStore.$subscribe((_mutation, state) => {
  const projectId = state.currentProject?.id;
  if (projectId && String(projectId) !== uploadForm.project) {
    uploadForm.project = String(projectId);
    loadDocuments();
  }
});
</script>

<style scoped>
.requirement-management {
  padding: 24px;
  background: transparent; /* 使用主布局的背景 */
  min-height: 100%; /* 适应父容器 */
}

.filter-section {
  margin-bottom: 16px;
  padding: 16px 24px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.content-section {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.stats-info {
  display: flex;
  flex-direction: row; /* 改为水平排列 */
  gap: 8px; /* 增加间距 */
  flex-wrap: wrap; /* 允许换行 */
}

.stat-item {
  font-size: 12px;
  color: #86909c;
  white-space: nowrap; /* 防止单个统计项换行 */
}

.upload-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  border: 2px dashed #d9d9d9;
  border-radius: 6px;
  background: #fafafa;
  cursor: pointer;
  transition: all 0.3s;
}

.upload-area:hover {
  border-color: #00a0e9;
  background: #f0f8ff;
}

.upload-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #86909c;
}

.upload-file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  margin-top: 8px;
  background: #f7f8fa;
  border-radius: 4px;
  border: 1px solid #e5e6eb;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.file-name {
  font-size: 14px;
  color: #1d2129;
  font-weight: 500;
}

.file-size {
  font-size: 12px;
  color: #86909c;
}
</style>
