<template>
  <div class="requirement-management">
    <!-- 搜索和筛选 -->
    <div class="filter-section">
      <div class="filter-row">
        <a-input-search
          v-model="searchKeyword"
          :placeholder="pageText.searchPlaceholder"
          @search="handleSearch"
          @clear="handleSearch"
          allow-clear
        />
        <a-select
          v-model="statusFilter"
          :placeholder="pageText.documentStatus"
          @change="handleSearch"
          allow-clear
        >
          <a-option v-for="option in statusOptions" :key="option.value || 'all'" :value="option.value">
            {{ option.label }}
          </a-option>
        </a-select>
        <a-select
          v-model="typeFilter"
          :placeholder="pageText.documentType"
          @change="handleSearch"
          allow-clear
        >
          <a-option v-for="option in typeOptions" :key="option.value || 'all'" :value="option.value">
            {{ option.label }}
          </a-option>
        </a-select>
        <a-button type="primary" @click="showUploadModal">
          <template #icon><icon-plus /></template>
          {{ pageText.uploadRequirementDocument }}
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
        :scroll="{ x: 1000 }"
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
            <span class="stat-item">{{ formatWordCount(record.word_count || 0) }}</span>
            <span class="stat-item">{{ formatPageCount(record.page_count || 0) }}</span>
            <span class="stat-item">{{ formatModuleCount(record.modules_count || 0) }}</span>
          </div>
        </template>

        <!-- 操作列 -->
        <template #actions="{ record }">
          <div class="actions-wrapper">
            <a-button type="text" size="small" @click="viewDocument(record)">
              {{ pageText.details }}
            </a-button>
            <a-button
              v-if="record.status === 'uploaded'"
              type="text"
              size="small"
              @click="viewDocument(record)"
            >
              {{ pageText.split }}
            </a-button>
            <a-button
              v-if="record.status === 'ready_for_review'"
              type="text"
              size="small"
              @click="startReview(record)"
            >
              {{ pageText.review }}
            </a-button>
            <a-button
              v-if="record.status === 'reviewing'"
              type="text"
              size="small"
              status="warning"
              @click="viewDocument(record)"
            >
              {{ pageText.viewProgress }}
            </a-button>
            <a-button
              v-if="record.status === 'review_completed'"
              type="text"
              size="small"
              @click="viewReports(record)"
            >
              {{ pageText.report }}
            </a-button>
            <a-button
              v-if="record.status === 'review_completed'"
              type="text"
              size="small"
              @click="restartReview(record)"
            >
              {{ pageText.reReview }}
            </a-button>
            <a-button
              v-if="record.status === 'failed'"
              type="text"
              size="small"
              @click="retryReview(record)"
            >
              {{ pageText.retry }}
            </a-button>
            <a-popconfirm
              :content="pageText.deleteDocumentConfirm"
              @ok="deleteDocument(record)"
            >
              <a-button type="text" size="small" status="danger">
                {{ pageText.delete }}
              </a-button>
            </a-popconfirm>
          </div>
        </template>
      </a-table>
    </div>

    <!-- 上传文档模态框 -->
    <a-modal
      v-model:visible="uploadModalVisible"
      :title="pageText.uploadRequirementDocument"
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
        <a-form-item :label="pageText.documentTitle" field="title">
          <a-input v-model="uploadForm.title" :placeholder="pageText.enterDocumentTitle" />
        </a-form-item>
        <a-form-item :label="pageText.documentDescription" field="description">
          <a-textarea
            v-model="uploadForm.description"
            :placeholder="pageText.enterDocumentDescription"
            :rows="3"
          />
        </a-form-item>
        <a-form-item :label="pageText.uploadMethod" field="uploadType">
          <a-radio-group v-model="uploadForm.uploadType" @change="handleUploadTypeChange">
            <a-radio value="file">{{ pageText.uploadFile }}</a-radio>
            <a-radio value="content">{{ pageText.directInput }}</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item
          v-if="uploadForm.uploadType === 'file'"
          :label="pageText.selectFile"
          field="file"
        >
          <a-upload
            ref="uploadRef"
            :file-list="fileList"
            :auto-upload="false"
            :show-file-list="true"
            :limit="1"
            accept=".pdf,.doc,.docx,.txt,.md"
            @change="handleFileChange"
          >
            <template #upload-button>
              <div class="upload-area">
                <icon-upload />
                <div>{{ pageText.clickToUploadFile }}</div>
                <div class="upload-tip">{{ pageText.uploadFileTip }}</div>
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
          :label="pageText.documentContent"
          field="content"
        >
          <a-textarea
            v-model="uploadForm.content"
            :placeholder="pageText.enterOrPasteDocumentContent"
            :rows="8"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 评审配置模态框 -->
    <a-modal
      v-model:visible="reviewConfigVisible"
      :title="reviewAction === 'restart' ? pageText.restartReviewConfig : pageText.reviewConfigTitle"
      @ok="confirmReview"
      @cancel="reviewConfigVisible = false"
    >
      <a-alert v-if="reviewAction === 'restart'" type="warning" style="margin-bottom: 16px">
        {{ pageText.restartReviewHint }}
      </a-alert>
      
      <a-form :model="reviewConfig" layout="vertical">
        <a-form-item :label="pageText.concurrentAnalyses" field="max_workers">
          <a-select v-model="reviewConfig.max_workers" :placeholder="pageText.selectConcurrency">
            <a-option v-for="option in reviewWorkerOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </a-option>
          </a-select>
          <template #help>
            {{ pageText.reviewConcurrencyHelp }}
          </template>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { Message } from '@arco-design/web-vue';
import { IconPlus, IconUpload, IconFile, IconDelete } from '@arco-design/web-vue/es/icon';
import { useAppI18n } from '@/composables/useAppI18n';
import { useProjectStore } from '@/store/projectStore';
import { RequirementDocumentService } from '../services/requirementService';
import { normalizeListPayload } from '@/features/api-testing/services/responseHelpers';
import type {
  RequirementDocument,
  DocumentStatus,
  DocumentType,
  CreateDocumentRequest,
  DocumentListParams
} from '../types';

// 状态仓库与路由
const projectStore = useProjectStore();
const router = useRouter();
const { isEnglish } = useAppI18n();

const pageText = computed(() => (
  isEnglish.value
    ? {
        searchPlaceholder: 'Search document title or description',
        documentStatus: 'Document status',
        documentType: 'Document type',
        uploadRequirementDocument: 'Upload requirement document',
        allStatuses: 'All statuses',
        allTypes: 'All types',
        textType: 'Text',
        words: 'words',
        pages: 'pages',
        modules: 'modules',
        details: 'Details',
        split: 'Split',
        review: 'Review',
        viewProgress: 'View progress',
        report: 'Report',
        reReview: 'Restart review',
        retry: 'Retry',
        delete: 'Delete',
        deleteDocumentConfirm: 'Delete this document?',
        documentTitle: 'Document title',
        enterDocumentTitle: 'Enter document title',
        documentDescription: 'Document description',
        enterDocumentDescription: 'Enter document description (optional)',
        uploadMethod: 'Upload method',
        uploadFile: 'Upload file',
        directInput: 'Direct input',
        selectFile: 'Select file',
        clickToUploadFile: 'Click to upload a file',
        uploadFileTip: 'Supports PDF, Word (.doc/.docx), TXT, and Markdown',
        documentContent: 'Document content',
        enterOrPasteDocumentContent: 'Enter or paste the document content',
        restartReviewConfig: 'Restart review configuration',
        reviewConfigTitle: 'Review configuration',
        restartReviewHint: 'Restarting the review creates a new report and keeps previous reports.',
        concurrentAnalyses: 'Concurrent analyses',
        selectConcurrency: 'Select concurrency',
        reviewConcurrencyHelp: 'This controls how many analysis tasks run at the same time. Lower it if you hit API rate limits.',
        titleRequired: 'Enter document title',
        titleMaxLength: 'Title cannot exceed 200 characters',
        descriptionMaxLength: 'Description cannot exceed 500 characters',
        fileRequired: 'Select a file',
        contentRequired: 'Enter document content',
        documentNameColumn: 'Document title',
        statusColumn: 'Status',
        typeColumn: 'Type',
        statsColumn: 'Stats',
        uploaderColumn: 'Uploaded by',
        uploadTimeColumn: 'Uploaded at',
        actionsColumn: 'Actions',
        selectProjectFirst: 'Select a project first',
        loadDocumentsFailed: 'Failed to load documents',
        uploadSuccess: 'Document uploaded successfully',
        uploadFailed: 'Failed to upload document',
        reviewStarted: (workers: number, isRestart: boolean) => `${isRestart ? 'Review restart' : 'Review'} started (concurrency: ${workers})`,
        reviewStartFailed: 'Failed to start review',
        noReportYet: 'No review report yet',
        deleteSuccess: 'Document deleted successfully',
        deleteFailed: 'Failed to delete document',
        unknownSize: 'Unknown size',
      }
    : {
        searchPlaceholder: '搜索文档标题或描述',
        documentStatus: '文档状态',
        documentType: '文档类型',
        uploadRequirementDocument: '上传需求文档',
        allStatuses: '全部状态',
        allTypes: '全部类型',
        textType: '文本',
        words: '字',
        pages: '页',
        modules: '模块',
        details: '详情',
        split: '拆分',
        review: '评审',
        viewProgress: '查看进度',
        report: '报告',
        reReview: '重审',
        retry: '重试',
        delete: '删除',
        deleteDocumentConfirm: '确定要删除这个文档吗？',
        documentTitle: '文档标题',
        enterDocumentTitle: '请输入文档标题',
        documentDescription: '文档描述',
        enterDocumentDescription: '请输入文档描述（可选）',
        uploadMethod: '上传方式',
        uploadFile: '上传文件',
        directInput: '直接输入',
        selectFile: '选择文件',
        clickToUploadFile: '点击上传文件',
        uploadFileTip: '支持 PDF、Word(.doc/.docx)、TXT、Markdown',
        documentContent: '文档内容',
        enterOrPasteDocumentContent: '请输入或粘贴文档内容',
        restartReviewConfig: '重新评审配置',
        reviewConfigTitle: '评审配置',
        restartReviewHint: '重新评审将创建新的评审报告，原有报告将保留。',
        concurrentAnalyses: '并发分析数量',
        selectConcurrency: '请选择并发数量',
        reviewConcurrencyHelp: '并发数量决定了同时进行的专项分析任务数。如果遇到API限流错误，请尝试降低并发数。',
        titleRequired: '请输入文档标题',
        titleMaxLength: '标题长度不能超过200个字符',
        descriptionMaxLength: '描述长度不能超过500个字符',
        fileRequired: '请选择文件',
        contentRequired: '请输入文档内容',
        documentNameColumn: '文档标题',
        statusColumn: '状态',
        typeColumn: '类型',
        statsColumn: '统计',
        uploaderColumn: '上传者',
        uploadTimeColumn: '上传时间',
        actionsColumn: '操作',
        selectProjectFirst: '请先选择项目',
        loadDocumentsFailed: '加载文档列表失败',
        uploadSuccess: '文档上传成功',
        uploadFailed: '文档上传失败',
        reviewStarted: (workers: number, isRestart: boolean) => `${isRestart ? '重新评审' : '需求评审'}已启动 (并发数: ${workers})`,
        reviewStartFailed: '评审启动失败',
        noReportYet: '暂无评审报告',
        deleteSuccess: '文档删除成功',
        deleteFailed: '文档删除失败',
        unknownSize: '未知大小',
      }
));

const statusLabelMap = computed<Record<DocumentStatus, string>>(() => (
  isEnglish.value
    ? {
        uploaded: 'Uploaded',
        processing: 'Processing',
        module_split: 'Splitting modules',
        user_reviewing: 'User reviewing',
        ready_for_review: 'Ready for review',
        reviewing: 'Reviewing',
        review_completed: 'Review completed',
        failed: 'Failed',
      }
    : {
        uploaded: '已上传',
        processing: '处理中',
        module_split: '模块拆分中',
        user_reviewing: '用户调整中',
        ready_for_review: '待评审',
        reviewing: '评审中',
        review_completed: '评审完成',
        failed: '处理失败',
      }
));

const typeLabelMap = computed<Record<DocumentType, string>>(() => (
  isEnglish.value
    ? {
        pdf: 'PDF',
        doc: 'Word document',
        docx: 'Word document',
        txt: 'Text file',
        md: 'Markdown',
      }
    : {
        pdf: 'PDF',
        doc: 'Word文档',
        docx: 'Word文档',
        txt: '文本文件',
        md: 'Markdown',
      }
));

const statusOptions = computed(() => [
  { value: '', label: pageText.value.allStatuses },
  { value: 'uploaded', label: statusLabelMap.value.uploaded },
  { value: 'processing', label: statusLabelMap.value.processing },
  { value: 'module_split', label: statusLabelMap.value.module_split },
  { value: 'user_reviewing', label: statusLabelMap.value.user_reviewing },
  { value: 'ready_for_review', label: statusLabelMap.value.ready_for_review },
  { value: 'reviewing', label: statusLabelMap.value.reviewing },
  { value: 'review_completed', label: statusLabelMap.value.review_completed },
  { value: 'failed', label: statusLabelMap.value.failed },
]);

const typeOptions = computed(() => [
  { value: '', label: pageText.value.allTypes },
  { value: 'pdf', label: 'PDF' },
  { value: 'docx', label: 'Word' },
  { value: 'pptx', label: 'PPT' },
  { value: 'md', label: 'Markdown' },
  { value: 'txt', label: pageText.value.textType },
  { value: 'html', label: 'HTML' },
]);

const reviewWorkerOptions = computed(() => (
  isEnglish.value
    ? [
        { value: 1, label: '1 (Serial - slowest but most stable)' },
        { value: 2, label: '2 (Low concurrency - suitable for low-resource environments)' },
        { value: 3, label: '3 (Recommended - balanced speed and stability)' },
        { value: 5, label: '5 (High concurrency - fastest)' },
      ]
    : [
        { value: 1, label: '1 (串行分析 - 最慢但最稳定)' },
        { value: 2, label: '2 (低并发 - 适合低配环境)' },
        { value: 3, label: '3 (推荐 - 平衡速度与稳定性)' },
        { value: 5, label: '5 (高并发 - 速度最快)' },
      ]
));

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

// 评审配置相关
const reviewConfigVisible = ref(false);
const reviewAction = ref<'start' | 'restart' | 'retry'>('start');
const currentDocument = ref<RequirementDocument | null>(null);
const reviewConfig = ref({
  max_workers: 3
});

// 表单验证规则
const uploadRules = computed(() => ({
  title: [
    { required: true, message: pageText.value.titleRequired },
    { maxLength: 200, message: pageText.value.titleMaxLength }
  ],
  description: [
    { maxLength: 500, message: pageText.value.descriptionMaxLength }
  ],
  file: [
    {
      required: true,
      message: pageText.value.fileRequired,
      validator: (_value: any, callback: Function) => {
        if (uploadForm.uploadType === 'file' && !uploadForm.file) {
          callback(pageText.value.fileRequired);
        } else {
          callback();
        }
      }
    }
  ],
  content: [
    {
      required: true,
      message: pageText.value.contentRequired,
      validator: (_value: any, callback: Function) => {
        if (uploadForm.uploadType === 'content' && !uploadForm.content) {
          callback(pageText.value.contentRequired);
        } else {
          callback();
        }
      }
    }
  ]
}));

// 表格列定义
const columns = computed(() => [
  {
    title: pageText.value.documentNameColumn,
    dataIndex: 'title',
    width: 200,
    ellipsis: true,
    tooltip: true
  },
  {
    title: pageText.value.statusColumn,
    dataIndex: 'status',
    slotName: 'status',
    width: 100
  },
  {
    title: pageText.value.typeColumn,
    dataIndex: 'document_type',
    slotName: 'document_type',
    width: 80
  },
  {
    title: pageText.value.statsColumn,
    slotName: 'stats',
    width: 180
  },
  {
    title: pageText.value.uploaderColumn,
    dataIndex: 'uploader_name',
    width: 80,
    ellipsis: true
  },
  {
    title: pageText.value.uploadTimeColumn,
    dataIndex: 'uploaded_at',
    width: 170,
    render: ({ record }: { record: RequirementDocument }) => {
      return new Date(record.uploaded_at).toLocaleString();
    }
  },
  {
    title: pageText.value.actionsColumn,
    slotName: 'actions',
    width: 260,
    fixed: 'right',
    align: 'center'
  }
]);

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
  return statusLabelMap.value[status] || status;
};

const getTypeText = (type: DocumentType) => {
  return typeLabelMap.value[type] || type;
};

const formatWordCount = (count: number) => (
  isEnglish.value ? `${count} ${pageText.value.words}` : `${count} ${pageText.value.words}`
);

const formatPageCount = (count: number) => (
  isEnglish.value ? `${count} ${count === 1 ? 'page' : pageText.value.pages}` : `${count} ${pageText.value.pages}`
);

const formatModuleCount = (count: number) => (
  isEnglish.value ? `${count} ${count === 1 ? 'module' : pageText.value.modules}` : `${count} ${pageText.value.modules}`
);

// 加载文档列表
const loadDocuments = async () => {
  if (!currentProjectId.value) {
    Message.warning(pageText.value.selectProjectFirst);
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
      const { results, count } = normalizeListPayload<RequirementDocument>(response.data);
      documentList.value = results;
      pagination.total = count;
    } else {
      Message.error(response.message || pageText.value.loadDocumentsFailed);
    }
  } catch (error) {
    console.error('加载文档列表失败:', error);
    Message.error(pageText.value.loadDocumentsFailed);
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
    Message.warning(pageText.value.selectProjectFirst);
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
    if (extension && ['pdf', 'doc', 'docx', 'txt', 'md'].includes(extension)) {
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
      Message.error(pageText.value.titleRequired);
      return;
    }

    if (uploadForm.uploadType === 'file' && !uploadForm.file) {
      Message.error(pageText.value.fileRequired);
      return;
    }

    if (uploadForm.uploadType === 'content' && (!uploadForm.content || !uploadForm.content.trim())) {
      Message.error(pageText.value.contentRequired);
      return;
    }

    if (!uploadForm.project) {
      Message.error(pageText.value.selectProjectFirst);
      return;
    }

    uploadLoading.value = true;

    console.log('上传数据:', uploadForm); // 调试日志

    const response = await RequirementDocumentService.uploadDocument(uploadForm);

    console.log('上传响应:', response); // 调试日志

    if (response.status === 'success') {
      Message.success(pageText.value.uploadSuccess);
      uploadModalVisible.value = false;
      resetUploadForm();
      loadDocuments();
    } else {
      Message.error(response.message || pageText.value.uploadFailed);
    }
  } catch (error) {
    console.error('文档上传失败:', error);
    Message.error(pageText.value.uploadFailed);
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
  if (!size || isNaN(size)) return pageText.value.unknownSize;
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

// 开始评审 - 打开配置对话框
const startReview = (document: RequirementDocument) => {
  currentDocument.value = document;
  reviewAction.value = 'start';
  reviewConfigVisible.value = true;
};

// 重新评审 - 打开配置对话框
const restartReview = (document: RequirementDocument) => {
  currentDocument.value = document;
  reviewAction.value = 'restart';
  reviewConfigVisible.value = true;
};

// 失败后重试评审 - 打开配置对话框
const retryReview = (document: RequirementDocument) => {
  currentDocument.value = document;
  reviewAction.value = 'retry';
  reviewConfigVisible.value = true;
};

// 确认评审
const confirmReview = async () => {
  if (!currentDocument.value) return;
  
  reviewConfigVisible.value = false;
  loading.value = true;
  
  const options = {
    analysis_type: 'comprehensive' as const,
    parallel_processing: true,
    max_workers: reviewConfig.value.max_workers
  };

  try {
    let response;
    const documentId = currentDocument.value.id;
    
    if (reviewAction.value === 'restart') {
      response = await RequirementDocumentService.restartReview(documentId, options);
    } else {
      // start 和 retry 都调用 startReview
      response = await RequirementDocumentService.startReview(documentId, options);
    }

    if (response.status === 'success') {
      Message.success(pageText.value.reviewStarted(reviewConfig.value.max_workers, reviewAction.value === 'restart'));
      loadDocuments();
    } else {
      Message.error(response.message || pageText.value.reviewStartFailed);
    }
  } catch (error) {
    console.error('评审启动失败:', error);
    Message.error(pageText.value.reviewStartFailed);
  } finally {
    loading.value = false;
    currentDocument.value = null;
  }
};

const viewReports = (document: RequirementDocument) => {
  // 跳转到专门的报告页面
  if (document.id) {
    router.push(`/requirements/${document.id}/report`);
  } else {
    Message.warning(pageText.value.noReportYet);
  }
};

const deleteDocument = async (document: RequirementDocument) => {
  try {
    loading.value = true;
    const response = await RequirementDocumentService.deleteDocument(document.id);

    if (response.status === 'success') {
      Message.success(pageText.value.deleteSuccess);
      loadDocuments();
    } else {
      Message.error(response.message || pageText.value.deleteFailed);
    }
  } catch (error) {
    console.error('文档删除失败:', error);
    Message.error(pageText.value.deleteFailed);
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

.filter-row .arco-input-search {
  width: 300px;
  flex-shrink: 0;
}

.filter-row .arco-select {
  width: 120px;
  flex-shrink: 0;
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

.actions-wrapper {
  display: flex;
  justify-content: center;
  gap: 4px;
}
</style>
