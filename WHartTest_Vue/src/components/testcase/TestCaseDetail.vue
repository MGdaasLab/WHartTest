<template>
  <div class="testcase-form-container"> <!-- 复用form的容器样式 -->
    <div class="form-header">
      <div class="form-title">
        <a-button type="text" size="small" @click="handleBackToList">
          <template #icon><icon-arrow-left /></template>
          返回列表
        </a-button>
        <h2>测试用例详情</h2>
      </div>
      <div class="form-actions" v-if="testCaseDetail">
        <a-space>
          <!-- 用例导航按钮（当有用例列表时显示） -->
          <template v-if="totalTestCases > 0">
            <a-button-group>
              <a-button :disabled="!hasPrevTestCase" @click="goToPrevTestCase">
                <template #icon><icon-left /></template>
                上一条
              </a-button>
              <a-button disabled class="nav-indicator">
                {{ currentTestCaseIndex + 1 }} / {{ totalTestCases }}
              </a-button>
              <a-button :disabled="!hasNextTestCase" @click="goToNextTestCase">
                下一条
                <template #icon><icon-right /></template>
              </a-button>
            </a-button-group>
            <a-divider direction="vertical" />
          </template>
          <a-button type="primary" @click="handleEdit">编辑</a-button>
          <a-button type="primary" status="danger" @click="handleDelete">删除</a-button>
        </a-space>
      </div>
    </div>

    <div v-if="loading" class="loading-container">
      <a-spin />
    </div>
    <div v-else-if="testCaseDetail" class="testcase-detail-content">
      <a-descriptions :column="2" bordered>
        <a-descriptions-item label="用例名称">{{ testCaseDetail.name }}</a-descriptions-item>
        <a-descriptions-item label="所属模块">
            {{ getModuleNameById(testCaseDetail.module_id) }}
        </a-descriptions-item>
        <a-descriptions-item label="优先级">
          <a-tag :color="getLevelColor(testCaseDetail.level)">{{ testCaseDetail.level }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="测试类型">
          <a-tag>{{ getTestTypeLabel(testCaseDetail.test_type) }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="审核状态">
          <a-select
            :model-value="testCaseDetail.review_status"
            size="small"
            style="width: 120px;"
            @change="(val: string | number | boolean | Record<string, unknown> | (string | number | boolean | Record<string, unknown>)[]) => handleReviewStatusChange(val as string)"
          >
            <a-option v-for="opt in REVIEW_STATUS_OPTIONS" :key="opt.value" :value="opt.value">
              <a-tag :color="opt.color" size="small">{{ opt.label }}</a-tag>
            </a-option>
          </a-select>
        </a-descriptions-item>
        <a-descriptions-item label="创建者">{{ testCaseDetail.creator_detail?.username || '-' }}</a-descriptions-item>
        <a-descriptions-item label="更新时间">{{ formatDate(testCaseDetail.updated_at) }}</a-descriptions-item>
        <a-descriptions-item label="UI自动化" :span="2">
          <div v-if="testCaseDetail.ui_test_case_detail" style="display: flex; align-items: center; gap: 8px;">
            <a-tag color="green" size="small">
              <template #icon><icon-check-circle-fill /></template>
              已绑定 UI 用例
            </a-tag>
            <span style="font-weight: 500;">{{ testCaseDetail.ui_test_case_detail.name }}</span>
            <a-tag v-if="testCaseDetail.ui_test_case_detail.module_name" color="blue" size="small">
              {{ testCaseDetail.ui_test_case_detail.module_name }}
            </a-tag>
            <a-tag v-if="testCaseDetail.ui_test_case_detail.step_count !== undefined" color="arcoblue" size="small">
              {{ testCaseDetail.ui_test_case_detail.step_count }} 步
            </a-tag>
            <a-tag color="arcoblue" size="small">
              模式: {{ getExecutionModeLabel(testCaseDetail.execution_mode) }}
            </a-tag>
          </div>
          <div v-else style="color: var(--color-text-3);">
            <a-tag color="gray" size="small">未绑定 UI 脚本</a-tag>
            <span style="margin-left: 6px; font-size: 12px;">（可在编辑用例或执行时快速关联）</span>
          </div>
        </a-descriptions-item>
      </a-descriptions>

      <div class="precondition-section">
        <h3>前置条件</h3>
        <div class="precondition-content" style="white-space: pre-wrap;">{{ testCaseDetail.precondition || '-' }}</div>
      </div>

      <div class="steps-section view-steps">
        <h3>测试步骤</h3>
        <a-table
          :columns="stepColumns"
          :data="testCaseDetail.steps"
          :pagination="false"
          :bordered="{ cell: true }"
          row-key="id"
        />
      </div>

      <div class="notes-section">
        <h3>备注</h3>
        <div class="notes-content" style="white-space: pre-wrap;">{{ testCaseDetail.notes || '-' }}</div>
      </div>

      <div class="screenshots-section">
        <div class="screenshots-header">
          <h3>截图</h3>
          <a-space>
            <a-button type="primary" size="small" @click="showUploadModal = true">
              <template #icon><icon-plus /></template>
              上传截图
            </a-button>
            <a-checkbox
              v-if="allScreenshots.length > 0"
              :model-value="isAllSelected"
              :indeterminate="isIndeterminate"
              @change="handleSelectAll"
            >
              全选
            </a-checkbox>
            <a-button
              v-if="selectedScreenshotIds.length > 0"
              type="primary"
              status="danger"
              size="small"
              @click="handleBatchDeleteScreenshots"
            >
              批量删除 ({{ selectedScreenshotIds.length }})
            </a-button>
          </a-space>
        </div>

        <!-- 多截图展示（新接口） -->
        <div v-if="allScreenshots.length > 0" class="screenshots-grid">
          <div
            v-for="screenshot in allScreenshots"
            :key="screenshot.id || screenshot.url"
            class="screenshot-item"
            :class="{ 'selected': selectedScreenshotIds.includes(screenshot.id) }"
          >
            <a-checkbox
              v-if="screenshot.id"
              class="screenshot-checkbox"
              :model-value="selectedScreenshotIds.includes(screenshot.id)"
              @change="toggleScreenshotSelection(screenshot.id)"
            />
            <div class="screenshot-preview" @click="previewScreenshot(screenshot)">
              <img
                :src="getScreenshotUrl(screenshot)"
                :alt="getScreenshotDisplayName(screenshot)"
                :data-screenshot-id="screenshot.id"
                class="screenshot-thumbnail"
                @error="handleImageError"
                @load="handleImageLoad"
              />
              <div class="preview-overlay">
                <icon-eye class="preview-icon" />
                <span>点击预览</span>
              </div>
              <!-- 图片加载失败时的占位符 -->
              <div v-if="imageLoadErrors[screenshot.id]" class="image-error-placeholder">
                <div class="error-icon"><icon-file-image /></div>
                <div class="error-text">图片加载失败</div>
                <div class="error-url">{{ getScreenshotUrl(screenshot) }}</div>
              </div>
            </div>
            <div class="screenshot-info-container">
              <div class="screenshot-info">
                <div class="screenshot-filename">{{ getScreenshotDisplayName(screenshot) }}</div>
                <div class="screenshot-description" v-if="screenshot.description">{{ screenshot.description }}</div>
                <div class="screenshot-meta">
                  <span v-if="screenshot.step_number" class="step-number">步骤 {{ screenshot.step_number }}</span>
                  <span class="screenshot-date">{{ formatDate(getScreenshotUploadTime(screenshot)) }}</span>
                </div>
              </div>
              <a-button
                type="text"
                status="danger"
                size="mini"
                class="delete-btn"
                @click="handleDeleteScreenshot(screenshot)"
              >
                删除
              </a-button>
            </div>
          </div>
        </div>

        <div v-else class="no-screenshots">
          <a-empty description="暂无截图" />
        </div>
      </div>
    </div>
    <a-empty v-else description="无法加载测试用例详情" />

    <!-- 截图上传模态框 -->
    <a-modal
      v-model:visible="showUploadModal"
      title="上传截图"
      :width="600"
      @ok="handleUploadScreenshot"
      @cancel="handleCancelUpload"
      :confirm-loading="uploadLoading"
    >
      <a-form layout="vertical" :model="uploadForm">
        <a-form-item label="标题（可选）">
          <a-input v-model="uploadForm.title" placeholder="为这批截图添加标题" />
        </a-form-item>

        <a-form-item label="描述（可选）">
          <a-textarea v-model="uploadForm.description" placeholder="描述截图内容" :auto-size="{ minRows: 2, maxRows: 4 }" />
        </a-form-item>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="步骤编号（可选）">
              <a-input-number v-model="uploadForm.step_number" placeholder="关联步骤" :min="1" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="页面URL（可选）">
              <a-input v-model="uploadForm.page_url" placeholder="截图页面地址" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>

      <div class="upload-area" @click="triggerFileInput" @dragover.prevent @drop.prevent="handleDrop">
        <input
          ref="fileInputRef"
          type="file"
          accept="image/*"
          multiple
          style="display: none"
          @change="handleFileSelect"
        />
        <div class="upload-content">
          <icon-upload />
          <div class="upload-text">
            <div>点击选择图片或拖拽到此处</div>
            <div class="upload-tip">支持 JPG、PNG、GIF 格式，最多上传10张，单个文件不超过 10MB</div>
          </div>
        </div>
      </div>

      <div v-if="selectedFiles.length > 0" class="selected-files">
        <div class="files-header">
          <span>已选择 {{ selectedFiles.length }} 个文件</span>
          <a-button type="text" size="mini" @click="clearAllFiles">清空</a-button>
        </div>
        <div v-for="(file, index) in selectedFiles" :key="index" class="file-item">
          <img :src="getFilePreview(file)" alt="预览" class="file-preview" />
          <div class="file-info">
            <div class="file-name">{{ file.name }}</div>
            <div class="file-size">{{ formatFileSize(file.size) }}</div>
          </div>
          <a-button type="text" size="mini" @click="removeFile(index)">删除</a-button>
        </div>
      </div>
    </a-modal>

    <!-- 截图预览模态框 -->
    <a-modal
      v-model:visible="showPreviewModal"
      :footer="false"
      :width="1200"
      :style="{ top: '50px' }"
      class="screenshot-preview-modal"
      :title="`图片预览 (${currentPreviewIndex + 1}/${allScreenshots.length})`"
      :mask-closable="true"
      :esc-to-close="true"
    >
      <div v-if="previewImageUrl" class="enhanced-preview-container">
        <!-- 左侧信息面板 -->
        <div class="preview-sidebar">
          <!-- 图片信息 -->
          <div class="preview-info" v-if="previewInfo">
            <h4>图片信息</h4>
            <div class="info-item" v-for="(value, key) in previewInfo" :key="key">
              <span class="label">{{ key }}：</span>
              <span class="value">{{ value }}</span>
            </div>
          </div>

          <!-- 缩略图导航 -->
          <div class="thumbnail-navigation" v-if="allScreenshots.length > 1">
            <h4>所有图片 ({{ allScreenshots.length }})</h4>
            <div class="thumbnail-grid">
              <div
                v-for="(screenshot, index) in allScreenshots"
                :key="screenshot.id || index"
                class="thumbnail-item"
                :class="{ active: index === currentPreviewIndex }"
                @click="jumpToImage(index)"
              >
                <img
                  :src="getScreenshotUrl(screenshot)"
                  :alt="getScreenshotDisplayName(screenshot)"
                  class="thumbnail-image"
                />
                <div class="thumbnail-overlay">{{ index + 1 }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 右侧图片显示区域 -->
        <div class="preview-main">
          <!-- 图片切换按钮 -->
          <div class="image-navigation" v-if="allScreenshots.length > 1">
            <a-button
              type="outline"
              shape="circle"
              class="nav-button prev-button"
              :disabled="currentPreviewIndex === 0"
              @click="prevImage"
            >
              <icon-left />
            </a-button>
            <a-button
              type="outline"
              shape="circle"
              class="nav-button next-button"
              :disabled="currentPreviewIndex === allScreenshots.length - 1"
              @click="nextImage"
            >
              <icon-right />
            </a-button>
          </div>

          <!-- 主图片显示 -->
          <div class="main-image-container">
            <img
              :src="previewImageUrl"
              :alt="previewTitle"
              class="preview-image"
              @load="handleImageLoad"
              @error="handleImageError"
            />
          </div>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, toRefs, computed } from 'vue';
import { Message, Modal } from '@arco-design/web-vue';
import { IconArrowLeft, IconPlus, IconUpload, IconEye, IconLeft, IconRight, IconCheckCircleFill, IconFileImage } from '@arco-design/web-vue/es/icon';
import {
  getTestCaseDetail,
  deleteTestCase as deleteTestCaseService,
  uploadTestCaseScreenshots,
  getTestCaseScreenshots,
  deleteTestCaseScreenshot,
  batchDeleteTestCaseScreenshots,
  updateTestCaseReviewStatus,
  type TestCase,
  type TestCaseScreenshot,
  type UploadScreenshotsRequest,
  type ReviewStatus,
} from '@/services/testcaseService';
import { type TestCaseModule } from '@/services/testcaseModuleService';
import { formatDate, getLevelColor, getTestTypeLabel, REVIEW_STATUS_OPTIONS } from '@/utils/formatters';

const getExecutionModeLabel = (mode?: string) => {
  switch (mode) {
    case 'hybrid':
      return '智能双模(脚本+AI自愈)';
    case 'script_only':
      return '仅脚本执行';
    case 'ai_only':
      return '纯AI探索执行';
    default:
      return '智能双模';
  }
};

const props = defineProps<{
  testCaseId: number | null;
  currentProjectId: number | null;
  modules: TestCaseModule[]; // 传入模块列表用于显示模块名称
  testCaseIds?: number[]; // 当前筛选后的用例ID列表（用于导航）
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'editTestCase', testCaseId: number): void;
  (e: 'testCaseDeleted'): void;
  (e: 'navigate', testCaseId: number): void;
  (e: 'reviewStatusChanged'): void; // 审核状态变更后通知父组件刷新
}>();

const { testCaseId, currentProjectId, modules, testCaseIds } = toRefs(props);

const loading = ref(false);
const testCaseDetail = ref<TestCase | null>(null);

// 截图相关状态
const showUploadModal = ref(false);
const showPreviewModal = ref(false);
const uploadLoading = ref(false);
const selectedFiles = ref<File[]>([]);
const fileInputRef = ref<HTMLInputElement>();

// 上传表单数据
const uploadForm = ref<Omit<UploadScreenshotsRequest, 'screenshots'>>({
  title: '',
  description: '',
  step_number: undefined,
  mcp_session_id: '',
  page_url: '',
});

// 预览相关状态
const previewImageUrl = ref<string>('');
const previewTitle = ref<string>('');
const previewInfo = ref<Record<string, string> | null>(null);
const currentPreviewIndex = ref<number>(0); // 当前预览图片索引

// 图片加载错误状态
const imageLoadErrors = ref<Record<number, boolean>>({});

// 批量删除截图相关状态
const selectedScreenshotIds = ref<number[]>([]);

const stepColumns = [
  { title: '步骤', dataIndex: 'step_number', width: 80 },
  { title: '描述', dataIndex: 'description' },
  { title: '预期结果', dataIndex: 'expected_result' },
];

// 工具函数：从URL获取文件名
const getScreenshotFilename = (url: string): string => {
  return url.split('/').pop() || '截图';
};

// 工具函数：获取截图URL
const getScreenshotUrl = (screenshot: TestCaseScreenshot): string => {
  return screenshot.url || screenshot.screenshot_url || screenshot.screenshot || '';
};

// 工具函数：获取截图显示名称
const getScreenshotDisplayName = (screenshot: TestCaseScreenshot): string => {
  return screenshot.title || screenshot.filename || getScreenshotFilename(getScreenshotUrl(screenshot));
};

// 工具函数：获取截图上传时间
const getScreenshotUploadTime = (screenshot: TestCaseScreenshot): string => {
  return screenshot.uploaded_at || screenshot.created_at || '';
};

// 计算属性：合并所有截图
const allScreenshots = computed(() => {
  const screenshots: TestCaseScreenshot[] = [];

  // 新的多截图数据
  if (testCaseDetail.value?.screenshots && testCaseDetail.value.screenshots.length > 0) {
    // 映射API数据到组件期望的格式
    const mappedScreenshots = testCaseDetail.value.screenshots.map(screenshot => {
      const screenshotUrl = screenshot.screenshot_url || screenshot.screenshot;
      return {
        ...screenshot,
        url: screenshotUrl, // 使用screenshot_url或screenshot作为url
        filename: getScreenshotFilename(screenshotUrl),
        uploaded_at: screenshot.created_at, // 使用created_at作为uploaded_at
      };
    });
    screenshots.push(...mappedScreenshots);
  }

  // 兼容旧的单截图数据
  if (testCaseDetail.value?.screenshot && (!testCaseDetail.value?.screenshots || testCaseDetail.value.screenshots.length === 0)) {
    screenshots.push({
      id: 0, // 临时ID
      test_case: testCaseDetail.value.id,
      screenshot: testCaseDetail.value.screenshot,
      screenshot_url: testCaseDetail.value.screenshot,
      created_at: testCaseDetail.value.updated_at,
      uploader: testCaseDetail.value.creator,
      uploader_detail: testCaseDetail.value.creator_detail,
      url: testCaseDetail.value.screenshot,
      filename: getScreenshotFilename(testCaseDetail.value.screenshot),
      uploaded_at: testCaseDetail.value.updated_at,
    });
  }

  return screenshots;
});

const fetchDetails = async (id: number) => {
  if (!currentProjectId.value) return;
  loading.value = true;
  try {
    const response = await getTestCaseDetail(currentProjectId.value, id);
    if (response.success && response.data) {
      testCaseDetail.value = response.data;
      // 同时获取最新的截图列表
      await fetchScreenshots(id);
    } else {
      Message.error(response.error || '获取测试用例详情失败');
      testCaseDetail.value = null;
    }
  } catch (error) {
    Message.error('获取测试用例详情时发生错误');
    testCaseDetail.value = null;
  } finally {
    loading.value = false;
  }
};

const fetchScreenshots = async (testCaseId: number) => {
  if (!currentProjectId.value) return;
  try {
    const response = await getTestCaseScreenshots(currentProjectId.value, testCaseId);
    if (response.success && response.data && testCaseDetail.value) {
      // 更新测试用例的截图数据
      testCaseDetail.value.screenshots = response.data;
    }
  } catch (error) {
    console.error('获取截图列表失败:', error);
  }
};

const getModuleNameById = (moduleId?: number | null) => {
    if (!moduleId) return '-';
    const module = modules.value.find(m => m.id === moduleId);
    return module ? module.name : '未知模块';
};

// 用例导航相关计算属性
const currentTestCaseIndex = computed(() => {
  if (!testCaseId?.value || !testCaseIds?.value?.length) return -1;
  return testCaseIds.value.indexOf(testCaseId.value);
});

const hasPrevTestCase = computed(() => {
  return currentTestCaseIndex.value > 0;
});

const hasNextTestCase = computed(() => {
  if (!testCaseIds?.value?.length) return false;
  return currentTestCaseIndex.value >= 0 && currentTestCaseIndex.value < testCaseIds.value.length - 1;
});

const totalTestCases = computed(() => {
  return testCaseIds?.value?.length || 0;
});

// 用例导航方法
const goToPrevTestCase = () => {
  if (hasPrevTestCase.value && testCaseIds?.value) {
    const prevId = testCaseIds.value[currentTestCaseIndex.value - 1];
    emit('navigate', prevId);
  }
};

const goToNextTestCase = () => {
  if (hasNextTestCase.value && testCaseIds?.value) {
    const nextId = testCaseIds.value[currentTestCaseIndex.value + 1];
    emit('navigate', nextId);
  }
};

onMounted(() => {
  if (testCaseId.value) {
    fetchDetails(testCaseId.value);
  }
  // 添加键盘事件监听
  document.addEventListener('keydown', handleKeydown);
});

onUnmounted(() => {
  // 移除键盘事件监听
  document.removeEventListener('keydown', handleKeydown);
});

watch(testCaseId, (newId) => {
  if (newId) {
    fetchDetails(newId);
  } else {
    testCaseDetail.value = null;
  }
});

const handleBackToList = () => {
  emit('close');
};

const handleEdit = () => {
  if (testCaseDetail.value) {
    emit('editTestCase', testCaseDetail.value.id);
  }
};

// 处理审核状态变更
const handleReviewStatusChange = async (newStatus: string) => {
  if (!testCaseDetail.value || !currentProjectId.value) return;

  try {
    const response = await updateTestCaseReviewStatus(
      currentProjectId.value,
      testCaseDetail.value.id,
      newStatus as ReviewStatus
    );
    if (response.success) {
      Message.success('状态更新成功');
      // 更新本地数据
      testCaseDetail.value.review_status = newStatus as ReviewStatus;
      // 通知父组件刷新列表和导航ID
      emit('reviewStatusChanged');
    } else {
      Message.error(response.error || '状态更新失败');
    }
  } catch (error) {
    Message.error('状态更新时发生错误');
  }
};

const handleDelete = () => {
  if (!testCaseDetail.value || !currentProjectId.value) return;
  const tc = testCaseDetail.value;
  Modal.warning({
    title: '确认删除',
    content: `确定要删除测试用例 "${tc.name}" 吗？此操作不可恢复。`,
    okText: '确认',
    cancelText: '取消',
    onOk: async () => {
      try {
        const response = await deleteTestCaseService(currentProjectId.value!, tc.id);
        if (response.success) {
          Message.success('测试用例删除成功');
          emit('testCaseDeleted');
          emit('close'); // 删除成功后关闭详情页
        } else {
          Message.error(response.error || '删除测试用例失败');
        }
      } catch (error) {
        Message.error('删除测试用例时发生错误');
      }
    },
  });
};

// 截图相关方法
const triggerFileInput = () => {
  fileInputRef.value?.click();
};

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement;
  if (target.files) {
    const files = Array.from(target.files);

    // 验证文件数量限制（最多10张）
    const totalFiles = selectedFiles.value.length + files.length;
    if (totalFiles > 10) {
      Message.warning(`最多只能上传10张图片，当前已选择${selectedFiles.value.length}张，本次最多还能选择${10 - selectedFiles.value.length}张`);
      return;
    }

    // 验证文件类型和大小
    const validFiles = files.filter(file => {
      if (!file.type.startsWith('image/')) {
        Message.warning(`${file.name} 不是有效的图片文件`);
        return false;
      }
      if (file.size > 10 * 1024 * 1024) { // 10MB
        Message.warning(`${file.name} 文件大小超过10MB`);
        return false;
      }
      return true;
    });

    selectedFiles.value = [...selectedFiles.value, ...validFiles];
  }
};

const handleDrop = (event: DragEvent) => {
  event.preventDefault();
  if (event.dataTransfer?.files) {
    const files = Array.from(event.dataTransfer.files).filter(file => file.type.startsWith('image/'));

    // 验证文件数量限制
    const totalFiles = selectedFiles.value.length + files.length;
    if (totalFiles > 10) {
      Message.warning(`最多只能上传10张图片，当前已选择${selectedFiles.value.length}张，本次最多还能拖拽${10 - selectedFiles.value.length}张`);
      return;
    }

    // 验证文件大小
    const validFiles = files.filter(file => {
      if (file.size > 10 * 1024 * 1024) { // 10MB
        Message.warning(`${file.name} 文件大小超过10MB`);
        return false;
      }
      return true;
    });

    selectedFiles.value = [...selectedFiles.value, ...validFiles];
  }
};

const removeFile = (index: number) => {
  selectedFiles.value.splice(index, 1);
};

const getFilePreview = (file: File): string => {
  return URL.createObjectURL(file);
};

const handleUploadScreenshot = async () => {
  if (selectedFiles.value.length === 0) {
    Message.warning('请选择要上传的图片');
    return;
  }

  if (!testCaseDetail.value || !currentProjectId.value) {
    Message.error('测试用例信息不完整');
    return;
  }

  uploadLoading.value = true;
  try {
    const uploadData: UploadScreenshotsRequest = {
      screenshots: selectedFiles.value,
      title: uploadForm.value.title || undefined,
      description: uploadForm.value.description || undefined,
      step_number: uploadForm.value.step_number || undefined,
      page_url: uploadForm.value.page_url || undefined,
    };

    const response = await uploadTestCaseScreenshots(
      currentProjectId.value,
      testCaseDetail.value.id,
      uploadData
    );

    if (response.success) {
      Message.success(`成功上传 ${selectedFiles.value.length} 张截图`);
      showUploadModal.value = false;
      selectedFiles.value = [];
      resetUploadForm();

      // 重新获取截图列表
      if (testCaseDetail.value) {
        await fetchScreenshots(testCaseDetail.value.id);
      }
    } else {
      Message.error(`上传失败: ${response.error}`);
    }
  } catch (error) {
    Message.error('上传截图时发生错误');
  } finally {
    uploadLoading.value = false;
  }
};

const handleCancelUpload = () => {
  showUploadModal.value = false;
  selectedFiles.value = [];
  resetUploadForm();
  // 清理预览URL
  selectedFiles.value.forEach(file => {
    if (file instanceof File) {
      URL.revokeObjectURL(getFilePreview(file));
    }
  });
};

const resetUploadForm = () => {
  uploadForm.value = {
    title: '',
    description: '',
    step_number: undefined,
    mcp_session_id: '',
    page_url: '',
  };
};

const clearAllFiles = () => {
  selectedFiles.value.forEach(file => {
    URL.revokeObjectURL(getFilePreview(file));
  });
  selectedFiles.value = [];
};

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

const previewScreenshot = (screenshot: TestCaseScreenshot) => {
  // 找到当前截图在列表中的索引
  const index = allScreenshots.value.findIndex(s => s.id === screenshot.id);
  currentPreviewIndex.value = index >= 0 ? index : 0;

  updatePreviewContent();
  showPreviewModal.value = true;
};

// 更新预览内容
const updatePreviewContent = () => {
  const screenshot = allScreenshots.value[currentPreviewIndex.value];
  if (!screenshot) return;

  const screenshotUrl = getScreenshotUrl(screenshot);
  const displayName = getScreenshotDisplayName(screenshot);
  const uploadTime = getScreenshotUploadTime(screenshot);

  previewImageUrl.value = screenshotUrl;
  previewTitle.value = displayName;

  const info: Record<string, string> = {
    '文件名': getScreenshotFilename(screenshotUrl),
  };

  if (screenshot.title) info['标题'] = screenshot.title;
  if (screenshot.description) info['描述'] = screenshot.description;
  if (screenshot.step_number) info['关联步骤'] = `步骤 ${screenshot.step_number}`;
  if (screenshot.page_url) info['页面地址'] = screenshot.page_url;
  if (screenshot.mcp_session_id) info['会话ID'] = screenshot.mcp_session_id;
  if (screenshot.uploader_detail) info['上传者'] = screenshot.uploader_detail.username;

  info['上传时间'] = formatDate(uploadTime);

  previewInfo.value = info;
};

// 切换到上一张图片
const prevImage = () => {
  if (currentPreviewIndex.value > 0) {
    currentPreviewIndex.value--;
    updatePreviewContent();
  }
};

// 切换到下一张图片
const nextImage = () => {
  if (currentPreviewIndex.value < allScreenshots.value.length - 1) {
    currentPreviewIndex.value++;
    updatePreviewContent();
  }
};

// 跳转到指定图片
const jumpToImage = (index: number) => {
  if (index >= 0 && index < allScreenshots.value.length) {
    currentPreviewIndex.value = index;
    updatePreviewContent();
  }
};

// 键盘事件处理
const handleKeydown = (event: KeyboardEvent) => {
  if (!showPreviewModal.value) return;

  switch (event.key) {
    case 'ArrowLeft':
      event.preventDefault();
      prevImage();
      break;
    case 'ArrowRight':
      event.preventDefault();
      nextImage();
      break;
    case 'Escape':
      event.preventDefault();
      showPreviewModal.value = false;
      break;
  }
};



const handleDeleteScreenshot = (screenshot: TestCaseScreenshot) => {
  const displayName = getScreenshotDisplayName(screenshot);

  Modal.warning({
    title: '确认删除',
    content: `确定要删除截图 "${displayName}" 吗？此操作不可恢复。`,
    okText: '确认',
    cancelText: '取消',
    onOk: async () => {
      if (!testCaseDetail.value || !currentProjectId.value || !screenshot.id) {
        Message.error('删除失败：缺少必要信息');
        return;
      }

      try {
        const response = await deleteTestCaseScreenshot(
          currentProjectId.value,
          testCaseDetail.value.id,
          screenshot.id
        );

        if (response.success) {
          Message.success('截图删除成功');
          // 重新获取截图列表
          await fetchScreenshots(testCaseDetail.value.id);
        } else {
          Message.error(`删除失败: ${response.error}`);
        }
      } catch (error) {
        console.error('删除截图失败:', error);
        Message.error('删除截图时发生错误');
      }
    },
  });
};

const handleImageLoad = (event: Event) => {
  const img = event.target as HTMLImageElement;
  // 图片加载成功，清除错误状态
  const screenshotId = img.getAttribute('data-screenshot-id');
  if (screenshotId) {
    delete imageLoadErrors.value[parseInt(screenshotId)];
  }
};

const handleImageError = (event: Event) => {
  const img = event.target as HTMLImageElement;
  const screenshotId = img.getAttribute('data-screenshot-id');
  console.error('图片加载失败:', img.src);

  if (screenshotId) {
    imageLoadErrors.value[parseInt(screenshotId)] = true;
  }

  // 显示友好的错误提示
  Message.warning('部分截图无法加载，可能是网络问题或图片已被删除');
};

// 计算属性：是否全选
const isAllSelected = computed(() => {
  if (allScreenshots.value.length === 0) return false;
  const validScreenshots = allScreenshots.value.filter(s => s.id); // 过滤有效ID的截图
  return validScreenshots.length > 0 && selectedScreenshotIds.value.length === validScreenshots.length;
});

// 计算属性：是否为不确定状态(部分选中)
const isIndeterminate = computed(() => {
  const count = selectedScreenshotIds.value.length;
  const validScreenshots = allScreenshots.value.filter(s => s.id);
  return count > 0 && count < validScreenshots.length;
});

// 全选/取消全选
const handleSelectAll = (checked: boolean) => {
  if (checked) {
    // 全选：选择所有有效ID的截图
    selectedScreenshotIds.value = allScreenshots.value
      .filter(s => s.id)
      .map(s => s.id);
  } else {
    // 取消全选
    selectedScreenshotIds.value = [];
  }
};

// 切换截图选择状态
const toggleScreenshotSelection = (screenshotId: number) => {
  const index = selectedScreenshotIds.value.indexOf(screenshotId);
  if (index > -1) {
    selectedScreenshotIds.value.splice(index, 1);
  } else {
    selectedScreenshotIds.value.push(screenshotId);
  }
};

// 批量删除截图
const handleBatchDeleteScreenshots = () => {
  if (!testCaseDetail.value || !currentProjectId.value || selectedScreenshotIds.value.length === 0) {
    Message.warning('请选择要删除的截图');
    return;
  }

  // 获取选中的截图信息用于显示
  const selectedScreenshots = allScreenshots.value.filter(screenshot =>
    selectedScreenshotIds.value.includes(screenshot.id)
  );

  const screenshotNames = selectedScreenshots.map(s => getScreenshotDisplayName(s)).join('、');
  const displayNames = screenshotNames.length > 100 ?
    screenshotNames.substring(0, 100) + '...' : screenshotNames;

  Modal.warning({
    title: '确认批量删除',
    content: `确定要删除以下 ${selectedScreenshotIds.value.length} 张截图吗？此操作不可恢复。\n\n${displayNames}`,
    okText: '确认删除',
    cancelText: '取消',
    width: 500,
    onOk: async () => {
      try {
        const response = await batchDeleteTestCaseScreenshots(
          currentProjectId.value!,
          testCaseDetail.value!.id,
          selectedScreenshotIds.value
        );

        if (response.success && response.data) {
          // 显示详细的删除结果
          const { deleted_count, deleted_screenshots } = response.data;

          let detailMessage = `成功删除 ${deleted_count} 张截图`;
          if (deleted_screenshots && deleted_screenshots.length > 0) {
            const details = deleted_screenshots
              .map(s => s.title || '无标题')
              .slice(0, 5)
              .join(', ');
            detailMessage += `\n删除的截图: ${details}${deleted_screenshots.length > 5 ? '...' : ''}`;
          }

          Message.success(detailMessage);

          // 清空选中状态并重新加载截图列表
          selectedScreenshotIds.value = [];
          if (testCaseDetail.value) {
            await fetchScreenshots(testCaseDetail.value.id);
          }
        } else {
          Message.error(response.error || '批量删除截图失败');
        }
      } catch (error) {
        console.error('批量删除截图出错:', error);
        Message.error('批量删除截图时发生错误');
      }
    },
  });
};

</script>

<style scoped>
.testcase-form-container { /* 复用 TestCaseForm.vue 的样式 */
  background-color: var(--theme-card-bg);
  color: var(--theme-page-text);
  border: 1px solid var(--theme-card-border);
  border-radius: 8px;
  padding: 20px;
  box-shadow: var(--theme-card-shadow);
  height: 100%;
  max-height: 100vh; /* 确保不超过视口高度 */
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  overflow: auto; /* 允许内部内容滚动 */
}

.form-header { /* 复用 TestCaseForm.vue 的样式 */
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  flex-shrink: 0;
}

.form-header .form-title { /* 复用 TestCaseForm.vue 的样式 */
  display: flex;
  align-items: center;
}

.form-header .form-title h2 { /* 复用 TestCaseForm.vue 的样式 */
  margin: 0 0 0 12px;
  font-size: 18px;
  font-weight: 500;
}

.form-header .form-actions { /* 复用 TestCaseForm.vue 的样式 */
  display: flex;
  align-items: center;
}

.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
  flex-grow: 1;
}

.testcase-detail-content {
  flex-grow: 1;
  overflow-y: auto;
  padding-right: 8px; /* 为滚动条留出空间 */
  margin-right: -8px; /* 抵消padding，保持对齐 */
  scroll-behavior: smooth; /* 平滑滚动 */
}

/* 自定义滚动条样式 */
.testcase-detail-content::-webkit-scrollbar {
  width: 6px;
}

.testcase-detail-content::-webkit-scrollbar-track {
  background: var(--theme-surface-soft);
  border-radius: 3px;
}

.testcase-detail-content::-webkit-scrollbar-thumb {
  background: color-mix(in srgb, var(--theme-text-tertiary) 72%, transparent);
  border-radius: 3px;
  transition: background 0.3s ease;
}

.testcase-detail-content::-webkit-scrollbar-thumb:hover {
  background: color-mix(in srgb, var(--theme-text-secondary) 78%, transparent);
}

.precondition-section {
  margin-top: 24px;
}

.precondition-section h3 {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: bold;
  text-align: left;
}

.precondition-content {
  padding: 16px;
  background-color: #f9fafb;
  border: 1px solid #e5e6eb;
  border-radius: 4px;
  min-height: 60px;
}

.steps-section {
  margin-top: 24px;
}

.steps-section h3 {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: bold;
  text-align: left;
}

.notes-section {
  margin-top: 24px;
}

.notes-section h3 {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: bold;
  text-align: left;
}

.notes-content {
  padding: 16px;
  background-color: #f9fafb;
  border: 1px solid #e5e6eb;
  border-radius: 4px;
  min-height: 60px;
}

.screenshots-section {
  margin-top: 24px;
  margin-bottom: 40px; /* 底部留出更多空间 */
}

.screenshots-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.screenshots-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: bold;
  text-align: left;
}

.screenshots-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.screenshot-item {
  display: flex;
  flex-direction: column;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  background-color: #fff;
  transition: all 0.3s ease;
  overflow: hidden;
  position: relative;
}

.screenshot-item:hover {
  border-color: #165dff;
  box-shadow: 0 2px 8px rgba(22, 93, 255, 0.15);
}

.screenshot-item.selected {
  border-color: #165dff;
  box-shadow: 0 0 0 2px rgba(22, 93, 255, 0.2);
}

.screenshot-checkbox {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 10;
  background-color: color-mix(in srgb, var(--theme-card-bg) 90%, transparent);
  border-radius: 4px;
  padding: 2px;
}

.screenshot-item {
  display: flex;
  flex-direction: column;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  background-color: #fff;
  transition: all 0.3s ease;
  overflow: hidden;
}

.screenshot-item:hover {
  border-color: #165dff;
  box-shadow: 0 2px 8px rgba(22, 93, 255, 0.15);
}

.screenshot-preview {
  position: relative;
  cursor: pointer;
  overflow: hidden;
}

.screenshot-preview:hover .preview-overlay {
  opacity: 1;
}

.screenshot-thumbnail {
  width: 100%;
  height: 200px;
  object-fit: cover;
  display: block;
  transition: transform 0.3s ease;
}

.screenshot-preview:hover .screenshot-thumbnail {
  transform: scale(1.05);
}

.preview-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: white;
  opacity: 0;
  transition: opacity 0.3s ease;
  gap: 8px;
}

.preview-icon {
  font-size: 24px;
}

.preview-overlay span {
  font-size: 14px;
}

.image-error-placeholder {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: color-mix(in srgb, var(--theme-surface-soft) 72%, white 28%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--theme-text-tertiary);
  font-size: 12px;
  text-align: center;
  padding: 10px;
}

.error-icon {
  font-size: 24px;
  margin-bottom: 8px;
}

.error-text {
  margin-bottom: 4px;
  font-weight: 500;
}

.error-url {
  font-size: 10px;
  color: var(--theme-text-tertiary);
  word-break: break-all;
  line-height: 1.2;
}

.screenshot-info-container {
  padding: 12px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.screenshot-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.screenshot-filename {
  font-size: 14px;
  font-weight: 500;
  color: #1d2129;
  word-break: break-all;
  line-height: 1.4;
}

.screenshot-description {
  font-size: 12px;
  color: #4e5969;
  line-height: 1.4;
}

.screenshot-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #86909c;
}

.step-number {
  background-color: #f2f3f5;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
}

.screenshot-date {
  font-size: 12px;
  color: #86909c;
}

.delete-btn {
  flex-shrink: 0;
  margin-top: 4px;
}

.no-screenshots {
  text-align: center;
  padding: 40px 0;
}

/* 上传模态框样式 */
.upload-area {
  border: 2px dashed #d9d9d9;
  border-radius: 8px;
  padding: 40px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.3s ease;
}

.upload-area:hover {
  border-color: #165dff;
}

.upload-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.upload-text {
  color: #86909c;
}

.upload-tip {
  font-size: 12px;
  color: #c9cdd4;
}

.selected-files {
  margin-top: 16px;
  max-height: 300px;
  overflow-y: auto;
}

.files-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e5e6eb;
  font-size: 14px;
  font-weight: 500;
  color: #1d2129;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  margin-bottom: 8px;
  background-color: #fafbfc;
}

.file-preview {
  width: 50px;
  height: 50px;
  object-fit: cover;
  border-radius: 6px;
  flex-shrink: 0;
}

.file-info {
  flex: 1;
  min-width: 0;
}

.file-name {
  font-size: 14px;
  color: #1d2129;
  word-break: break-all;
  margin-bottom: 4px;
}

.file-size {
  font-size: 12px;
  color: #86909c;
}

/* 预览模态框样式 */
.screenshot-preview-modal :deep(.arco-modal-body) {
  padding: 0;
  height: 80vh;
  overflow: hidden;
}

.screenshot-preview-modal :deep(.arco-modal-header) {
  border-bottom: 1px solid #e5e6eb;
  padding: 16px 24px;
}

.enhanced-preview-container {
  display: flex;
  height: 100%;
  background-color: var(--theme-page-bg);
}

/* 左侧信息面板 */
.preview-sidebar {
  width: 320px;
  background-color: #fff;
  border-right: 1px solid #e5e6eb;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.preview-info {
  padding: 20px;
  border-bottom: 1px solid #e5e6eb;
}

.preview-info h4 {
  margin: 0 0 16px 0;
  font-size: 14px;
  font-weight: 600;
  color: #1d2129;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 8px 0;
  border-bottom: 1px solid #f2f3f5;
}

.info-item:last-child {
  border-bottom: none;
}

.label {
  font-weight: 500;
  color: #4e5969;
  min-width: 80px;
  flex-shrink: 0;
}

.value {
  color: #1d2129;
  word-break: break-all;
  text-align: right;
}

/* 缩略图导航 */
.thumbnail-navigation {
  padding: 20px;
  flex: 1;
}

.thumbnail-navigation h4 {
  margin: 0 0 16px 0;
  font-size: 14px;
  font-weight: 600;
  color: #1d2129;
}

.thumbnail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(60px, 1fr));
  gap: 8px;
}

.thumbnail-item {
  position: relative;
  cursor: pointer;
  border-radius: 4px;
  overflow: hidden;
  border: 2px solid transparent;
  transition: all 0.2s ease;
}

.thumbnail-item:hover {
  border-color: #165dff;
  transform: scale(1.05);
}

.thumbnail-item.active {
  border-color: #165dff;
  box-shadow: 0 2px 8px rgba(22, 93, 255, 0.3);
}

.thumbnail-image {
  width: 100%;
  height: 60px;
  object-fit: cover;
  display: block;
}

.thumbnail-overlay {
  position: absolute;
  bottom: 0;
  right: 0;
  background: rgba(0, 0, 0, 0.7);
  color: white;
  font-size: 10px;
  padding: 2px 4px;
  border-radius: 2px 0 0 0;
}

/* 右侧主图片区域 */
.preview-main {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--theme-page-bg);
}

.main-image-container {
  max-width: 100%;
  max-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.preview-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  background-color: var(--theme-card-bg);
}

/* 图片切换按钮 */
.image-navigation {
  position: absolute;
  top: 50%;
  left: 0;
  right: 0;
  transform: translateY(-50%);
  pointer-events: none;
  z-index: 10;
}

.nav-button {
  position: absolute;
  pointer-events: auto;
  background-color: color-mix(in srgb, var(--theme-card-bg) 90%, transparent);
  border: 1px solid var(--theme-border);
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.nav-button:hover:not(:disabled) {
  background-color: var(--theme-card-bg);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  transform: scale(1.1);
}

.prev-button {
  left: 20px;
}

.next-button {
  right: 20px;
}

.value {
  color: #4e5969;
  word-break: break-all;
}

/* 导航指示器样式 */
.nav-indicator {
  cursor: default !important;
  background-color: var(--theme-surface-soft) !important;
  color: var(--theme-text) !important;
  font-weight: 500;
  min-width: 70px;
}
</style>
