<template>
  <div class="testcase-form-container">
    <div class="form-header">
      <div class="form-title">
        <a-button type="text" size="small" @click="handleBackToList">
          <template #icon><icon-arrow-left /></template>
          {{ text.backToList }}
        </a-button>
        <h2>{{ isEditing ? text.editTitle : text.addTitle }}</h2>
      </div>
      <div class="form-actions">
        <a-space>
          <!-- 用例导航按钮（仅在编辑模式且有用例列表时显示） -->
          <template v-if="isEditing && totalTestCases > 0">
            <a-button-group>
              <a-button :disabled="!hasPrevTestCase" @click="goToPrevTestCase">
                <template #icon><icon-left /></template>
                {{ text.prevCase }}
              </a-button>
              <a-button disabled class="nav-indicator">
                {{ currentTestCaseIndex + 1 }} / {{ totalTestCases }}
              </a-button>
              <a-button :disabled="!hasNextTestCase" @click="goToNextTestCase">
                {{ text.nextCase }}
                <template #icon><icon-right /></template>
              </a-button>
            </a-button-group>
            <a-divider direction="vertical" />
          </template>
          <a-button @click="handleBackToList">{{ text.cancel }}</a-button>
          <a-button type="primary" :loading="formLoading" @click="handleSubmit">
            {{ text.save }}
          </a-button>
        </a-space>
      </div>
    </div>

    <a-form
      ref="testCaseFormRef"
      :model="formState"
      :rules="testCaseRules"
      layout="vertical"
      class="testcase-form"
    >
      <a-row :gutter="16">
        <a-col :span="10">
          <a-form-item field="name" :label="text.caseName">
            <a-input v-model="formState.name" :placeholder="text.caseNamePlaceholder" allow-clear />
          </a-form-item>
        </a-col>
        <a-col :span="3">
          <a-form-item field="level" :label="text.priority">
            <a-select v-model="formState.level" :placeholder="text.priorityPlaceholder">
              <a-option v-for="opt in priorityOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="3">
          <a-form-item field="test_type" :label="text.testType">
            <a-select v-model="formState.test_type" :placeholder="text.testTypePlaceholder">
              <a-option v-for="opt in localizedTestTypeOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="4">
          <a-form-item field="module_id" :label="text.module">
            <a-tree-select
              v-model="formState.module_id"
              :data="moduleTree"
              :placeholder="text.modulePlaceholder"
              allow-clear
              allow-search
              :dropdown-style="{ maxHeight: '300px', overflow: 'auto' }"
            />
          </a-form-item>
        </a-col>
        <a-col :span="4" v-if="isEditing">
          <a-form-item field="review_status" :label="text.reviewStatus">
            <a-select v-model="formState.review_status" :placeholder="text.reviewStatusPlaceholder">
              <a-option v-for="opt in localizedReviewStatusOptions" :key="opt.value" :value="opt.value">
                <a-tag :color="opt.color" size="small">{{ opt.label }}</a-tag>
              </a-option>
            </a-select>
          </a-form-item>
        </a-col>
      </a-row>
      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item field="ui_test_case" :label="tl('关联 UI 自动化用例')">
            <a-select
              v-model="formState.ui_test_case"
              :placeholder="tl('请选择关联的 UI 自动化用例（可选）')"
              allow-clear
              :loading="loadingUiTestCases"
            >
              <a-option
                v-for="item in availableUiCases"
                :key="item.id"
                :value="item.id"
                :label="`${item.name} (${item.level || 'P2'})`"
              />
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item field="execution_mode" :label="tl('默认执行模式')">
            <a-select v-model="formState.execution_mode" :placeholder="tl('请选择执行模式')">
              <a-option value="hybrid">{{ tl('智能双模（脚本优先 + 失败 AI 自愈介入）') }}</a-option>
              <a-option value="script_only">{{ tl('仅脚本执行') }}</a-option>
              <a-option value="ai_only">{{ tl('纯 AI 探索执行') }}</a-option>
            </a-select>
          </a-form-item>
        </a-col>
      </a-row>
      <a-form-item field="precondition" :label="text.precondition">
        <a-textarea
          v-model="formState.precondition"
          :placeholder="text.preconditionPlaceholder"
          allow-clear
          :auto-size="{ minRows: 1, maxRows: 4 }"
        />
      </a-form-item>

      <div class="steps-section">
        <div class="steps-header">
          <h3>{{ text.testSteps }}</h3>
          <a-space>
            <a-tag color="blue" size="small" style="margin-right: 8px;">
              <template #icon><icon-drag-dot-vertical /></template>
              {{ text.dragHint }}
            </a-tag>
            <a-button type="primary" size="small" @click="addStep">
              <template #icon><icon-plus /></template>
              {{ text.addStep }}
            </a-button>
          </a-space>
        </div>

        <div class="steps-table-container">
          <table class="custom-steps-table">
            <thead>
              <tr>
                <th style="width: 60px;">{{ text.dragColumn }}</th>
                <th style="width: 80px;">{{ text.stepColumn }}</th>
                <th>{{ text.stepDescriptionColumn }}</th>
                <th>{{ text.expectedResultColumn }}</th>
                <th style="width: 120px;">{{ text.actionColumn }}</th>
              </tr>
            </thead>
            <draggable
              v-model="formState.steps"
              tag="tbody"
              item-key="temp_id"
              handle=".drag-handle"
              @end="handleDragEnd"
              :animation="200"
              ghost-class="ghost-row"
              chosen-class="chosen-row"
            >
              <template #item="{ element: record, index: rowIndex }">
                <tr :key="record.temp_id" class="step-row">
                  <td class="drag-cell">
                    <div class="drag-handle">
                      <icon-drag-dot-vertical />
                    </div>
                  </td>
                  <td class="step-number-cell">{{ record.step_number }}</td>
                  <td class="step-content-cell">
                    <a-textarea
                      v-model="record.description"
                      :placeholder="text.stepDescriptionPlaceholder"
                      :auto-size="{ minRows: 1, maxRows: 4 }"
                      @blur="validateStepField(rowIndex, 'description')"
                    />
                    <div class="field-error" v-if="stepErrors[rowIndex]?.description">
                      {{ stepErrors[rowIndex].description }}
                    </div>
                  </td>
                  <td class="step-content-cell">
                    <a-textarea
                      v-model="record.expected_result"
                      :placeholder="text.expectedResultPlaceholder"
                      :auto-size="{ minRows: 1, maxRows: 4 }"
                      @blur="validateStepField(rowIndex, 'expected_result')"
                    />
                    <div class="field-error" v-if="stepErrors[rowIndex]?.expected_result">
                      {{ stepErrors[rowIndex].expected_result }}
                    </div>
                  </td>
                  <td class="action-cell">
                    <a-button
                      v-if="formState.steps.length > 1"
                      type="text"
                      status="danger"
                      size="small"
                      @click="removeStep(rowIndex)"
                    >
                      {{ text.delete }}
                    </a-button>
                  </td>
                </tr>
              </template>
            </draggable>
          </table>
        </div>
      </div>

      <a-form-item field="notes" :label="text.notes">
        <a-textarea
          v-model="formState.notes"
          :placeholder="text.notesPlaceholder"
          allow-clear
          :auto-size="{ minRows: 2, maxRows: 5 }"
        />
      </a-form-item>

      <!-- 截图管理区域 -->
      <div class="screenshots-section" v-if="isEditing">
        <div class="screenshots-header">
          <h3>{{ text.screenshot }}</h3>
          <a-button type="primary" size="small" @click="triggerFileInput">
            <template #icon><icon-plus /></template>
            {{ text.uploadScreenshot }}
          </a-button>
        </div>

        <input
          ref="fileInputRef"
          type="file"
          accept="image/*"
          style="display: none"
          @change="handleFileSelect"
        />

        <!-- 多截图展示（与详情页保持一致） -->
        <div v-if="existingScreenshots.length > 0" class="screenshots-grid">
          <div
            v-for="screenshot in existingScreenshots"
            :key="screenshot.id || screenshot.url"
            class="screenshot-item"
          >
            <div class="screenshot-preview" @click="previewExistingScreenshot(screenshot)">
              <img
                :src="getScreenshotUrl(screenshot)"
                :alt="getScreenshotDisplayName(screenshot)"
                class="screenshot-thumbnail"
                @error="handleImageError"
                @load="handleImageLoad"
              />
              <div class="preview-overlay">
                <icon-eye class="preview-icon" />
                <span>{{ text.clickPreview }}</span>
              </div>
            </div>
            <div class="screenshot-info-container">
              <div class="screenshot-info">
                <div class="screenshot-filename">{{ getScreenshotDisplayName(screenshot) }}</div>
                <div class="screenshot-description" v-if="screenshot.description">{{ screenshot.description }}</div>
                <div class="screenshot-meta">
                  <span v-if="screenshot.step_number" class="step-number">{{ text.stepLabel }} {{ screenshot.step_number }}</span>
                  <span class="screenshot-date">{{ formatDate(getScreenshotUploadTime(screenshot)) }}</span>
                </div>
              </div>
              <a-button
                type="text"
                status="danger"
                size="mini"
                class="delete-btn"
                @click="handleDeleteExistingScreenshot(screenshot)"
              >
                {{ text.delete }}
              </a-button>
            </div>
          </div>
        </div>

        <!-- 新上传的截图预览 -->
        <div v-if="newScreenshot" class="new-screenshot">
          <div class="section-title">{{ text.pendingScreenshots }}</div>
          <div class="screenshots-grid">
            <div class="screenshot-item">
              <div class="screenshot-preview" @click="previewNewScreenshot()">
                <img :src="getFilePreview(newScreenshot)" :alt="newScreenshot.name" class="screenshot-thumbnail" />
                <div class="preview-overlay">
                  <icon-eye class="preview-icon" />
                  <span>{{ text.clickPreview }}</span>
                </div>
              </div>
              <div class="screenshot-info-container">
                <div class="screenshot-info">
                  <div class="screenshot-filename">{{ newScreenshot.name }}</div>
                  <div class="screenshot-size">{{ formatFileSize(newScreenshot.size) }}</div>
                </div>
                <a-button
                  type="text"
                  status="danger"
                  size="mini"
                  class="delete-btn"
                  @click="removeNewScreenshot(0)"
                >
                  {{ text.delete }}
                </a-button>
              </div>
            </div>
          </div>
        </div>

        <div v-if="existingScreenshots.length === 0 && !newScreenshot" class="no-screenshots">
          <a-empty :description="text.noScreenshots" />
        </div>
      </div>
    </a-form>

    <!-- 截图预览模态框 -->
    <a-modal
      v-model:visible="showPreviewModal"
      :footer="false"
      :width="1200"
      :style="{ top: '50px' }"
      class="screenshot-preview-modal"
      :title="previewModalTitle"
      :mask-closable="true"
      :esc-to-close="true"
    >
      <div v-if="previewImageUrl" class="enhanced-preview-container">
        <!-- 左侧信息面板 -->
        <div class="preview-sidebar">
          <!-- 图片信息 -->
          <div class="preview-info" v-if="previewInfo">
            <h4>{{ text.imageInfo }}</h4>
            <div class="info-item" v-for="(value, key) in previewInfo" :key="key">
              <span class="label">{{ key }}:</span>
              <span class="value">{{ value }}</span>
            </div>
          </div>

          <!-- 缩略图导航 -->
          <div class="thumbnail-navigation" v-if="existingScreenshots.length > 1">
            <h4>{{ text.allImages }} ({{ existingScreenshots.length }})</h4>
            <div class="thumbnail-grid">
              <div
                v-for="(screenshot, index) in existingScreenshots"
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
          <div class="image-navigation" v-if="existingScreenshots.length > 1">
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
              :disabled="currentPreviewIndex === existingScreenshots.length - 1"
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
import { ref, reactive, watch, toRefs, onMounted, computed } from 'vue';
import { Message, Modal } from '@arco-design/web-vue';
import { IconArrowLeft, IconPlus, IconEye, IconLeft, IconRight, IconDragDotVertical } from '@arco-design/web-vue/es/icon';
import type { FormInstance, TreeNodeData } from '@arco-design/web-vue';
import draggable from 'vuedraggable';
import {
  createTestCase,
  updateTestCase,
  getTestCaseDetail,
  uploadTestCaseScreenshot,
  deleteTestCaseScreenshot,
  type TestCaseStep,
  type TestCaseScreenshot,
  type CreateTestCaseRequest,
  type UpdateTestCaseRequest,
} from '@/services/testcaseService';
import { formatDate, REVIEW_STATUS_OPTIONS, TEST_TYPE_OPTIONS } from '@/utils/formatters';
import type { ReviewStatus } from '@/services/testcaseService';
import { useAppI18n } from '@/composables/useAppI18n';
import { testCaseApi } from '@/features/ui-automation/api';
import type { UiTestCase } from '@/features/ui-automation/types';
import { extractPaginationData } from '@/features/ui-automation/types';

interface StepWithError extends TestCaseStep {
  temp_id?: string; // 用于表格 row-key
}

interface FormState extends CreateTestCaseRequest {
  id?: number;
  steps: StepWithError[];
  notes?: string;
  module_id?: number;
  review_status?: ReviewStatus;
  test_type?: string;
  ui_test_case?: number | null;
  execution_mode?: 'hybrid' | 'script_only' | 'ai_only';
}


const props = defineProps<{
  isEditing: boolean;
  testCaseId?: number | null;
  currentProjectId: number | null;
  initialSelectedModuleId?: number | null; // 用于新建时默认选中模块
  moduleTree: TreeNodeData[]; // 模块树数据
  testCaseIds?: number[]; // 当前筛选后的用例ID列表（用于导航）
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'submitSuccess'): void;
  (e: 'navigate', testCaseId: number): void; // 导航到指定用例
  (e: 'reviewStatusChanged'): void; // 审核状态变更后通知父组件刷新
}>();

const { isEditing, testCaseId, currentProjectId, initialSelectedModuleId, moduleTree, testCaseIds } = toRefs(props);
const { isEnglish, tl } = useAppI18n();

const formLoading = ref(false);
const testCaseFormRef = ref<FormInstance>();
const availableUiCases = ref<UiTestCase[]>([]);
const loadingUiTestCases = ref(false);

const formState = reactive<FormState>({
  id: undefined,
  name: '',
  precondition: '',
  level: 'P2',
  test_type: 'functional',
  module_id: undefined,
  ui_test_case: undefined,
  execution_mode: 'hybrid',
  steps: [{ step_number: 1, description: '', expected_result: '', temp_id: Date.now().toString() }],
  notes: '',
  review_status: 'pending_review',
});

const loadUiTestCases = async () => {
  if (!currentProjectId.value) return;
  loadingUiTestCases.value = true;
  try {
    const res = await testCaseApi.list({ project: currentProjectId.value });
    const { items } = extractPaginationData(res);
    availableUiCases.value = items || [];
  } catch (e) {
    console.error('加载 UI 用例失败', e);
  } finally {
    loadingUiTestCases.value = false;
  }
};

// 保存原始数据用于变更追踪
const originalFormData = ref<FormState | null>(null);

// 截图相关状态
const fileInputRef = ref<HTMLInputElement>();
const existingScreenshots = ref<TestCaseScreenshot[]>([]);
const newScreenshots = ref<File[]>([]);
const uploadingScreenshots = ref(false);

// 预览相关状态
const showPreviewModal = ref(false);
const previewImageUrl = ref<string>('');
const previewTitle = ref<string>('');
const previewInfo = ref<Record<string, string> | null>(null);
const currentPreviewIndex = ref(0);

const text = computed(() => (isEnglish.value ? {
  backToList: 'Back to List',
  editTitle: 'Edit Test Case',
  addTitle: 'Add Test Case',
  prevCase: 'Previous',
  nextCase: 'Next',
  cancel: 'Cancel',
  save: 'Save',
  delete: 'Delete',
  caseName: 'Case Name',
  caseNamePlaceholder: 'Please enter case name',
  priority: 'Priority',
  priorityPlaceholder: 'Please select priority',
  testType: 'Test Type',
  testTypePlaceholder: 'Please select test type',
  module: 'Module',
  modulePlaceholder: 'Please select module',
  reviewStatus: 'Review Status',
  reviewStatusPlaceholder: 'Please select review status',
  precondition: 'Precondition',
  preconditionPlaceholder: 'Please enter precondition',
  testSteps: 'Test Steps',
  dragHint: 'Drag steps to reorder',
  addStep: 'Add Step',
  dragColumn: 'Drag',
  stepColumn: 'Step',
  stepDescriptionColumn: 'Step Description',
  expectedResultColumn: 'Expected Result',
  actionColumn: 'Action',
  stepDescriptionPlaceholder: 'Please enter step description',
  expectedResultPlaceholder: 'Please enter expected result',
  notes: 'Notes',
  notesPlaceholder: 'Please enter notes',
  screenshot: 'Screenshots',
  uploadScreenshot: 'Upload Screenshot',
  clickPreview: 'Click to preview',
  stepLabel: 'Step',
  pendingScreenshots: 'Screenshots to Upload',
  noScreenshots: 'No screenshots',
  previewTitle: 'Image Preview',
  imageInfo: 'Image Info',
  allImages: 'All Images',
  fileName: 'File Name',
  fileSize: 'File Size',
  fileType: 'File Type',
  status: 'Status',
  pendingUpload: 'Pending Upload',
  description: 'Description',
  uploadTime: 'Upload Time',
  uploader: 'Uploaded By',
  projectIdMissing: 'Project ID is missing',
  fetchCaseDetailFailed: 'Failed to fetch test case details',
  fetchCaseDetailError: 'An error occurred while fetching test case details',
  noChangesDetected: 'No changes detected',
  updateSuccess: 'Test case updated successfully',
  createSuccess: 'Test case created successfully',
  updateFailed: 'Update failed',
  createFailed: 'Create failed',
  submitError: 'An error occurred while submitting test case',
  invalidImageFile: 'is not a valid image file',
  imageTooLarge: 'file size exceeds 10MB',
  confirmDelete: 'Confirm Delete',
  confirmDeleteScreenshot: 'Are you sure you want to delete screenshot "{name}"? This action cannot be undone.',
  confirm: 'Confirm',
  deleteFailedMissingInfo: 'Delete failed: missing required information',
  screenshotDeleteSuccess: 'Screenshot deleted successfully',
  screenshotDeleteFailed: 'Failed to delete screenshot',
  screenshotDeleteError: 'An error occurred while deleting screenshot',
  uploadFailed: 'Upload {name} failed: {error}',
  screenshotUploadError: 'An error occurred while uploading screenshot',
  imageLoadFailed: 'Image failed to load',
  nameRequired: 'Please enter case name',
  nameTooLong: 'Case name must be within 100 characters',
  preconditionTooLong: 'Precondition must be within 500 characters',
  priorityRequired: 'Please select priority',
  moduleRequired: 'Please select module',
  notesTooLong: 'Notes must be within 1000 characters',
  reviewStatusLabels: {
    pending_review: 'Pending Review',
    approved: 'Approved',
    needs_optimization: 'Needs Optimization',
    optimization_pending_review: 'Optimization Pending Review',
    unavailable: 'Unavailable',
  } as Record<string, string>,
  testTypeLabels: {
    smoke: 'Smoke Test',
    functional: 'Functional Test',
    boundary: 'Boundary Test',
    exception: 'Exception Test',
    permission: 'Permission Test',
    security: 'Security Test',
    compatibility: 'Compatibility Test',
  } as Record<string, string>,
  priorityLabels: {
    P0: 'P0 - Highest',
    P1: 'P1 - High',
    P2: 'P2 - Medium',
    P3: 'P3 - Low',
  } as Record<string, string>,
} : {
  backToList: '返回列表',
  editTitle: '编辑测试用例',
  addTitle: '添加测试用例',
  prevCase: '上一条',
  nextCase: '下一条',
  cancel: '取消',
  save: '保存',
  delete: '删除',
  caseName: '用例名称',
  caseNamePlaceholder: '请输入用例名称',
  priority: '优先级',
  priorityPlaceholder: '请选择优先级',
  testType: '测试类型',
  testTypePlaceholder: '请选择测试类型',
  module: '所属模块',
  modulePlaceholder: '请选择所属模块',
  reviewStatus: '审核状态',
  reviewStatusPlaceholder: '请选择审核状态',
  precondition: '前置条件',
  preconditionPlaceholder: '请输入前置条件',
  testSteps: '测试步骤',
  dragHint: '拖动步骤可调整顺序',
  addStep: '添加步骤',
  dragColumn: '拖动',
  stepColumn: '步骤',
  stepDescriptionColumn: '步骤描述',
  expectedResultColumn: '预期结果',
  actionColumn: '操作',
  stepDescriptionPlaceholder: '请输入步骤描述',
  expectedResultPlaceholder: '请输入预期结果',
  notes: '备注',
  notesPlaceholder: '请输入备注信息',
  screenshot: '截图',
  uploadScreenshot: '上传截图',
  clickPreview: '点击预览',
  stepLabel: '步骤',
  pendingScreenshots: '待上传的截图',
  noScreenshots: '暂无截图',
  previewTitle: '图片预览',
  imageInfo: '图片信息',
  allImages: '所有图片',
  fileName: '文件名',
  fileSize: '文件大小',
  fileType: '文件类型',
  status: '状态',
  pendingUpload: '待上传',
  description: '描述',
  uploadTime: '上传时间',
  uploader: '上传者',
  projectIdMissing: '项目ID不存在',
  fetchCaseDetailFailed: '获取测试用例详情失败',
  fetchCaseDetailError: '获取测试用例详情时发生错误',
  noChangesDetected: '没有检测到任何变更',
  updateSuccess: '测试用例更新成功',
  createSuccess: '测试用例创建成功',
  updateFailed: '更新失败',
  createFailed: '创建失败',
  submitError: '提交测试用例时发生错误',
  invalidImageFile: '不是有效的图片文件',
  imageTooLarge: '文件大小超过10MB',
  confirmDelete: '确认删除',
  confirmDeleteScreenshot: '确定要删除截图 "{name}" 吗？此操作不可恢复。',
  confirm: '确认',
  deleteFailedMissingInfo: '删除失败：缺少必要信息',
  screenshotDeleteSuccess: '截图删除成功',
  screenshotDeleteFailed: '删除截图失败',
  screenshotDeleteError: '删除截图时发生错误',
  uploadFailed: '上传 {name} 失败: {error}',
  screenshotUploadError: '上传截图时发生错误',
  imageLoadFailed: '图片加载失败',
  nameRequired: '请输入用例名称',
  nameTooLong: '用例名称长度不能超过100个字符',
  preconditionTooLong: '前置条件长度不能超过500个字符',
  priorityRequired: '请选择优先级',
  moduleRequired: '请选择所属模块',
  notesTooLong: '备注长度不能超过1000个字符',
  reviewStatusLabels: {
    pending_review: '待审核',
    approved: '通过',
    needs_optimization: '优化',
    optimization_pending_review: '优化待审核',
    unavailable: '不可用',
  } as Record<string, string>,
  testTypeLabels: {
    smoke: '冒烟测试',
    functional: '功能测试',
    boundary: '边界测试',
    exception: '异常测试',
    permission: '权限测试',
    security: '安全测试',
    compatibility: '兼容性测试',
  } as Record<string, string>,
  priorityLabels: {
    P0: 'P0 - 最高',
    P1: 'P1 - 高',
    P2: 'P2 - 中',
    P3: 'P3 - 低',
  } as Record<string, string>,
}));

const priorityOptions = computed(() => ([
  { value: 'P0', label: text.value.priorityLabels.P0 },
  { value: 'P1', label: text.value.priorityLabels.P1 },
  { value: 'P2', label: text.value.priorityLabels.P2 },
  { value: 'P3', label: text.value.priorityLabels.P3 },
]));

const localizedTestTypeOptions = computed(() => {
  return TEST_TYPE_OPTIONS.map(option => ({
    ...option,
    label: text.value.testTypeLabels[option.value] ?? option.label,
  }));
});

const localizedReviewStatusOptions = computed(() => {
  return REVIEW_STATUS_OPTIONS.map(option => ({
    ...option,
    label: text.value.reviewStatusLabels[option.value] ?? option.label,
  }));
});

const testCaseRules = computed(() => ({
  name: [
    { required: true, message: text.value.nameRequired },
    { maxLength: 100, message: text.value.nameTooLong },
  ],
  precondition: [
    { maxLength: 500, message: text.value.preconditionTooLong },
  ],
  level: [{ required: true, message: text.value.priorityRequired }],
  module_id: [{ required: true, message: text.value.moduleRequired }],
  notes: [
    { maxLength: 1000, message: text.value.notesTooLong },
  ],
}));

const stepErrors = ref<Array<{ description?: string; expected_result?: string }>>([]);

// 计算属性
const newScreenshot = computed(() => {
  return newScreenshots.value.length > 0 ? newScreenshots.value[0] : null;
});

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

const previewModalTitle = computed(() => {
  const total = existingScreenshots.value.length > 0 ? existingScreenshots.value.length : (newScreenshot.value ? 1 : 0);
  const current = total > 0 ? currentPreviewIndex.value + 1 : 0;
  return `${text.value.previewTitle} (${current}/${total})`;
});

const getPreviewInfoFromScreenshot = (screenshot: TestCaseScreenshot): Record<string, string> => {
  const displayName = getScreenshotDisplayName(screenshot);
  const uploadTime = getScreenshotUploadTime(screenshot);
  return {
    [text.value.fileName]: displayName,
    [text.value.description]: screenshot.description || '-',
    [text.value.stepLabel]: screenshot.step_number ? `${text.value.stepLabel} ${screenshot.step_number}` : '-',
    [text.value.uploadTime]: formatDate(uploadTime),
    [text.value.uploader]: screenshot.uploader_detail?.username || '-',
  };
};

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

const resetForm = () => {
  formState.id = undefined;
  formState.name = '';
  formState.precondition = '';
  formState.level = 'P2';
  formState.test_type = 'functional';
  formState.module_id = initialSelectedModuleId?.value || undefined;
  formState.ui_test_case = undefined;
  formState.execution_mode = 'hybrid';
  formState.steps = [{ step_number: 1, description: '', expected_result: '', temp_id: Date.now().toString() }];
  formState.notes = '';
  formState.review_status = 'pending_review';
  stepErrors.value = [];
  existingScreenshots.value = [];
  newScreenshots.value = [];
  testCaseFormRef.value?.clearValidate();
};

const fetchDetailsAndSetForm = async (id: number) => {
  if (!currentProjectId.value) return;
  formLoading.value = true;
  try {
    const response = await getTestCaseDetail(currentProjectId.value, id);
    if (response.success && response.data) {
      const data = response.data;
      formState.id = data.id;
      formState.name = data.name;
      formState.precondition = data.precondition;
      formState.level = data.level;
      formState.test_type = data.test_type || 'functional';
      formState.module_id = data.module_id;
      formState.ui_test_case = data.ui_test_case || undefined;
      formState.execution_mode = data.execution_mode || 'hybrid';
      formState.notes = data.notes || ''; // 设置备注信息
      formState.review_status = data.review_status || 'pending_review'; // 设置审核状态
      formState.steps = data.steps.map((step, index) => ({ ...step, temp_id: `${Date.now()}-${index}` }));
      stepErrors.value = Array(data.steps.length).fill({});

      // 保存原始数据的深拷贝，用于后续比较变更
      originalFormData.value = JSON.parse(JSON.stringify({
        id: data.id,
        name: data.name,
        precondition: data.precondition,
        level: data.level,
        module_id: data.module_id,
        ui_test_case: data.ui_test_case,
        execution_mode: data.execution_mode || 'hybrid',
        notes: data.notes || '',
        review_status: data.review_status || 'pending_review',
        steps: data.steps
      }));
      
      // 设置现有截图，并确保每个截图都有url字段用于兼容性
      existingScreenshots.value = (data.screenshots || []).map((screenshot: TestCaseScreenshot) => ({
        ...screenshot,
        url: screenshot.url || screenshot.screenshot_url || screenshot.screenshot,
        filename: screenshot.filename || getScreenshotFilename(screenshot.url || screenshot.screenshot_url || screenshot.screenshot || ''),
        uploaded_at: screenshot.uploaded_at || screenshot.created_at
      }));
    } else {
      Message.error(response.error || text.value.fetchCaseDetailFailed);
      emit('close');
    }
  } catch (error) {
    Message.error(text.value.fetchCaseDetailError);
    emit('close');
  } finally {
    formLoading.value = false;
  }
};

onMounted(() => {
  loadUiTestCases();
  if (isEditing.value && testCaseId?.value) {
    fetchDetailsAndSetForm(testCaseId.value);
  } else {
    resetForm();
  }
});

watch([isEditing, testCaseId], () => {
  if (isEditing.value && testCaseId?.value) {
    fetchDetailsAndSetForm(testCaseId.value);
  } else {
    resetForm();
  }
});


const validateStepField = (index: number, field: 'description' | 'expected_result') => {
  // 步骤字段不再是必填的，移除验证逻辑
  if (!stepErrors.value[index]) {
    stepErrors.value[index] = {};
  }
  // 清除可能存在的错误信息
  stepErrors.value[index][field] = undefined;
};

const addStep = () => {
  formState.steps.push({
    step_number: formState.steps.length + 1,
    description: '',
    expected_result: '',
    temp_id: `${Date.now()}-${formState.steps.length}`
  });
  stepErrors.value.push({});
};

const removeStep = (index: number) => {
  formState.steps.splice(index, 1);
  stepErrors.value.splice(index, 1);
  reorderSteps();
};

// 拖拽结束后重新编号
const handleDragEnd = () => {
  formState.steps.forEach((step, idx) => {
    step.step_number = idx + 1;
  });
};

// 删除步骤后重新编号
const reorderSteps = () => {
  formState.steps.forEach((step, idx) => {
    step.step_number = idx + 1;
  });
};

const handleBackToList = () => {
  emit('close');
};

const handleSubmit = async () => {
  if (!currentProjectId.value) {
    Message.error(text.value.projectIdMissing);
    return;
  }
  try {
    const formValidation = await testCaseFormRef.value?.validate();
    if (formValidation) {
      return; // 表单基础字段验证失败
    }

    formLoading.value = true;
    // 过滤掉描述和预期结果都为空的步骤
    const payloadSteps = formState.steps
      .filter(s => s.description.trim() !== '' || s.expected_result.trim() !== '')
      .map(s => ({
        step_number: s.step_number,
        description: s.description,
        expected_result: s.expected_result,
        id: s.id // 编辑时需要传id
      }));

    let response;
    let reviewStatusChanged = false; // 标记审核状态是否变更
    if (isEditing.value && formState.id) {
      // 编辑模式：只发送变更的字段（PATCH 语义）
      const updatePayload: Partial<UpdateTestCaseRequest> = {};
      
      if (originalFormData.value) {
        // 比较基础字段，只添加变更的字段
        if (formState.name !== originalFormData.value.name) {
          updatePayload.name = formState.name;
        }
        if (formState.precondition !== originalFormData.value.precondition) {
          updatePayload.precondition = formState.precondition;
        }
        if (formState.level !== originalFormData.value.level) {
          updatePayload.level = formState.level;
        }
        if (formState.module_id !== originalFormData.value.module_id) {
          updatePayload.module_id = formState.module_id;
        }
        if (formState.notes !== originalFormData.value.notes) {
          updatePayload.notes = formState.notes;
        }
        if (formState.review_status !== originalFormData.value.review_status) {
          updatePayload.review_status = formState.review_status;
          reviewStatusChanged = true; // 标记审核状态变更
        }
        if (formState.test_type !== originalFormData.value.test_type) {
          updatePayload.test_type = formState.test_type;
        }
        if (formState.ui_test_case !== originalFormData.value.ui_test_case) {
          updatePayload.ui_test_case = formState.ui_test_case || null;
        }
        if (formState.execution_mode !== originalFormData.value.execution_mode) {
          updatePayload.execution_mode = formState.execution_mode;
        }

        // 比较步骤：检查是否有变更
        // 将原始步骤数据标准化为与 payloadSteps 相同的格式后再比较
        const normalizedOriginalSteps = originalFormData.value.steps.map(s => ({
          id: s.id,
          step_number: s.step_number,
          description: s.description,
          expected_result: s.expected_result
        }));
        const stepsChanged = JSON.stringify(payloadSteps) !== JSON.stringify(normalizedOriginalSteps);
        if (stepsChanged) {
          updatePayload.steps = payloadSteps;
        }
      } else {
        // 如果没有原始数据（不应该发生），发送所有字段
        updatePayload.name = formState.name;
        updatePayload.precondition = formState.precondition;
        updatePayload.level = formState.level;
        updatePayload.test_type = formState.test_type;
        updatePayload.module_id = formState.module_id;
        updatePayload.ui_test_case = formState.ui_test_case || null;
        updatePayload.execution_mode = formState.execution_mode;
        updatePayload.steps = payloadSteps;
        updatePayload.notes = formState.notes;
      }
      
      // 检查是否有任何变更
      if (Object.keys(updatePayload).length === 0) {
        Message.info(text.value.noChangesDetected);
        formLoading.value = false;
        return;
      }
      
      // 开发环境下输出变更信息（便于调试）
      if (import.meta.env.DEV) {
        console.log('📝 PATCH 请求 - 只发送变更字段:', updatePayload);
        console.log('🔍 变更字段数量:', Object.keys(updatePayload).length);
      }
      
      response = await updateTestCase(currentProjectId.value, formState.id, updatePayload as UpdateTestCaseRequest);
    } else {
      const createPayload: CreateTestCaseRequest = {
        name: formState.name,
        precondition: formState.precondition,
        level: formState.level,
        test_type: formState.test_type,
        module_id: formState.module_id,
        ui_test_case: formState.ui_test_case || null,
        execution_mode: formState.execution_mode,
        steps: payloadSteps.map(({id, ...rest}) => rest), // 创建时不需要步骤id
        notes: formState.notes,
      };
      response = await createTestCase(currentProjectId.value, createPayload);
    }

    if (response.success) {
      // 如果有新截图需要上传，先上传截图
      if (newScreenshots.value.length > 0 && response.data?.id) {
        await uploadNewScreenshots(response.data.id);
      }

      Message.success(isEditing.value ? text.value.updateSuccess : text.value.createSuccess);

      // 无论是编辑还是新建，保存成功后都返回列表并刷新
      emit('submitSuccess');
    } else {
      Message.error(response.error || (isEditing.value ? text.value.updateFailed : text.value.createFailed));
    }
  } catch (error) {
    console.error('提交测试用例出错:', error);
    Message.error(text.value.submitError);
  } finally {
    formLoading.value = false;
  }
};

// 截图相关方法
const triggerFileInput = () => {
  fileInputRef.value?.click();
};

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement;
  if (target.files) {
    const files = Array.from(target.files);
    // 验证文件类型和大小
    const validFiles = files.filter(file => {
      if (!file.type.startsWith('image/')) {
        Message.warning(`${file.name} ${text.value.invalidImageFile}`);
        return false;
      }
      if (file.size > 10 * 1024 * 1024) { // 10MB
        Message.warning(`${file.name} ${text.value.imageTooLarge}`);
        return false;
      }
      return true;
    });
    newScreenshots.value = [...newScreenshots.value, ...validFiles];
  }
  // 清空input值，允许重复选择同一文件
  if (target) target.value = '';
};

const removeNewScreenshot = (index: number) => {
  const file = newScreenshots.value[index];
  // 清理预览URL
  URL.revokeObjectURL(getFilePreview(file));
  newScreenshots.value.splice(index, 1);
};

// 处理删除现有截图（与详情页保持一致的交互）
const handleDeleteExistingScreenshot = (screenshot: TestCaseScreenshot) => {
  if (!screenshot.id) {
    // 如果没有ID，直接从列表中移除
    existingScreenshots.value = existingScreenshots.value.filter(s => s !== screenshot);
    return;
  }

  const displayName = getScreenshotDisplayName(screenshot);
  
  Modal.warning({
    title: text.value.confirmDelete,
    content: text.value.confirmDeleteScreenshot.replace('{name}', displayName),
    okText: text.value.confirm,
    cancelText: text.value.cancel,
    onOk: async () => {
      if (!testCaseId?.value || !currentProjectId.value || !screenshot.id) {
        Message.error(text.value.deleteFailedMissingInfo);
        return;
      }

      try {
        const response = await deleteTestCaseScreenshot(
          currentProjectId.value,
          testCaseId.value,
          screenshot.id
        );

        if (response.success) {
          Message.success(text.value.screenshotDeleteSuccess);
          // 从本地列表中移除
          existingScreenshots.value = existingScreenshots.value.filter(s => s.id !== screenshot.id);
        } else {
          Message.error(response.error || text.value.screenshotDeleteFailed);
        }
      } catch (error) {
        console.error('删除截图时发生错误:', error);
        Message.error(text.value.screenshotDeleteError);
      }
    }
  });
};

const getScreenshotFilename = (url: string): string => {
  try {
    const urlObj = new URL(url);
    const pathname = urlObj.pathname;
    return pathname.split('/').pop() || 'screenshot.png';
  } catch {
    return 'screenshot.png';
  }
};

// 获取截图URL（与详情页保持一致）
const getScreenshotUrl = (screenshot: TestCaseScreenshot): string => {
  return screenshot.url || screenshot.screenshot_url || screenshot.screenshot || '';
};

// 获取截图显示名称（与详情页保持一致）
const getScreenshotDisplayName = (screenshot: TestCaseScreenshot): string => {
  return screenshot.title || screenshot.filename || getScreenshotFilename(getScreenshotUrl(screenshot));
};

// 获取截图上传时间（与详情页保持一致）
const getScreenshotUploadTime = (screenshot: TestCaseScreenshot): string => {
  return screenshot.uploaded_at || screenshot.created_at || '';
};

const previewNewScreenshot = () => {
  if (newScreenshots.value.length > 0) {
    const file = newScreenshots.value[0];
    currentPreviewIndex.value = 0;
    previewImageUrl.value = getFilePreview(file);
    previewTitle.value = file.name;
    previewInfo.value = {
      [text.value.fileName]: file.name,
      [text.value.fileSize]: formatFileSize(file.size),
      [text.value.fileType]: file.type,
      [text.value.status]: text.value.pendingUpload,
    };
    showPreviewModal.value = true;
  }
};

const getFilePreview = (file: File): string => {
  return URL.createObjectURL(file);
};

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

const uploadNewScreenshots = async (testCaseId: number) => {
  if (!currentProjectId.value || newScreenshots.value.length === 0) return;

  uploadingScreenshots.value = true;
  try {
    for (const file of newScreenshots.value) {
      const response = await uploadTestCaseScreenshot(
        currentProjectId.value,
        testCaseId,
        file
      );

      if (!response.success) {
        Message.warning(text.value.uploadFailed.replace('{name}', file.name).replace('{error}', response.error || ''));
      }
    }

    // 清空新截图列表
    newScreenshots.value.forEach(file => {
      URL.revokeObjectURL(getFilePreview(file));
    });
    newScreenshots.value = [];

  } catch (error) {
    console.error('上传截图失败:', error);
    Message.error(text.value.screenshotUploadError);
  } finally {
    uploadingScreenshots.value = false;
  }
};

// 预览相关方法
const previewExistingScreenshot = (screenshot: TestCaseScreenshot) => {
  // 找到当前截图的索引
  const index = existingScreenshots.value.findIndex(s => s.id === screenshot.id);
  if (index >= 0) {
    currentPreviewIndex.value = index;
  }
  
  const screenshotUrl = getScreenshotUrl(screenshot);
  const displayName = getScreenshotDisplayName(screenshot);
  previewImageUrl.value = screenshotUrl;
  previewTitle.value = displayName;
  previewInfo.value = getPreviewInfoFromScreenshot(screenshot);
  showPreviewModal.value = true;
};

// 图片导航函数
const prevImage = () => {
  if (currentPreviewIndex.value > 0) {
    currentPreviewIndex.value--;
    updatePreviewFromIndex();
  }
};

const nextImage = () => {
  if (currentPreviewIndex.value < existingScreenshots.value.length - 1) {
    currentPreviewIndex.value++;
    updatePreviewFromIndex();
  }
};

const jumpToImage = (index: number) => {
  if (index >= 0 && index < existingScreenshots.value.length) {
    currentPreviewIndex.value = index;
    updatePreviewFromIndex();
  }
};

const updatePreviewFromIndex = () => {
  const screenshot = existingScreenshots.value[currentPreviewIndex.value];
  if (screenshot) {
    const screenshotUrl = getScreenshotUrl(screenshot);
    const displayName = getScreenshotDisplayName(screenshot);

    previewImageUrl.value = screenshotUrl;
    previewTitle.value = displayName;
    previewInfo.value = getPreviewInfoFromScreenshot(screenshot);
  }
};

const handleImageLoad = (event: Event) => {
  const img = event.target as HTMLImageElement;
  console.log('图片加载成功:', img.naturalWidth, 'x', img.naturalHeight);
};

const handleImageError = (_event: Event) => {
  console.error('图片加载失败');
  Message.error(text.value.imageLoadFailed);
};
</script>

<style scoped>
.testcase-form-container {
  background-color: var(--theme-card-bg);
  color: var(--theme-page-text);
  border: 1px solid var(--theme-card-border);
  border-radius: 8px;
  padding: 20px;
  box-shadow: var(--theme-card-shadow);
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  overflow-y: auto; /* 允许表单内容滚动 */
  
  /* 隐藏滚动条但保留滚动功能 */
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE and Edge */
}

.testcase-form-container::-webkit-scrollbar {
  display: none; /* Chrome, Safari and Opera */
}

.form-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  flex-shrink: 0;

  .form-title {
    display: flex;
    align-items: center;

    h2 {
      margin: 0 0 0 12px;
      font-size: 18px;
      font-weight: 500;
    }
  }

  .form-actions {
    display: flex;
    align-items: center;
  }
}

/* 导航指示器样式 */
.nav-indicator {
  cursor: default !important;
  background-color: var(--theme-surface-soft) !important;
  color: var(--theme-text) !important;
  font-weight: 500;
  min-width: 70px;
  text-align: center;
}

.testcase-form {
  flex-grow: 1;
  .steps-section {
    margin-top: 20px;
    margin-bottom: 20px;
    border: 1px solid #e5e6eb;
    border-radius: 4px;
    padding: 16px;
    background-color: #f9fafb;
  }

  .steps-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;

    h3 {
      margin: 0;
      font-size: 16px;
      font-weight: 500;
    }
  }

  /* 自定义步骤表格样式 */
  .steps-table-container {
    overflow-x: auto;
  }

  .custom-steps-table {
    width: 100%;
    border-collapse: collapse;
    background-color: #fff;
    border-radius: 4px;
    overflow: hidden;
  }

  .custom-steps-table thead {
    background-color: #f7f8fa;
  }

  .custom-steps-table th {
    padding: 12px;
    text-align: left;
    font-weight: 500;
    color: #1d2129;
    border-bottom: 1px solid #e5e6eb;
    font-size: 14px;
  }

  .custom-steps-table td {
    padding: 12px;
    border-bottom: 1px solid #e5e6eb;
    vertical-align: top;
  }

  .step-row {
    background-color: #fff;
    transition: background-color 0.2s ease;
  }

  .step-row:hover {
    background-color: #f7f8fa;
  }

  /* 拖拽手柄样式 */
  .drag-cell {
    text-align: center;
    cursor: move;
  }

  .drag-handle {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border-radius: 4px;
    color: #86909c;
    cursor: move;
    transition: all 0.2s ease;
  }

  .drag-handle:hover {
    background-color: #e5e6eb;
    color: #165dff;
  }

  .drag-handle:active {
    background-color: #d4d5d9;
  }

  /* 步骤编号样式 */
  .step-number-cell {
    text-align: center;
    font-weight: 500;
    color: #1d2129;
    font-size: 14px;
  }

  /* 步骤内容单元格 */
  .step-content-cell {
    min-width: 200px;
  }

  .step-content-cell :deep(.arco-textarea) {
    width: 100%;
    resize: none;
  }

  /* 操作列样式 */
  .action-cell {
    text-align: center;
    white-space: nowrap;
  }

  /* 拖拽时的幽灵行样式 */
  .ghost-row {
    opacity: 0.5;
    background-color: #e8f3ff;
  }

  /* 选中时的行样式 */
  .chosen-row {
    background-color: #f0f7ff;
    box-shadow: 0 2px 8px rgba(22, 93, 255, 0.2);
  }

  .field-error {
    color: #f53f3f;
    font-size: 12px;
    margin-top: 4px;
  }

  .screenshots-section {
    margin-top: 20px;
    margin-bottom: 20px;
    border: 1px solid #e5e6eb;
    border-radius: 4px;
    padding: 16px;
    background-color: #f9fafb;
  }

  .screenshots-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;

    h3 {
      margin: 0;
      font-size: 16px;
      font-weight: 500;
    }
  }

  .existing-screenshots,
  .new-screenshots {
    margin-bottom: 16px;
  }

  .section-title {
    font-size: 14px;
    font-weight: 500;
    color: #1d2129;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid #e5e6eb;
  }

  /* 截图网格样式（与详情页保持一致） */
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
    font-size: 18px;
  }

  .screenshot-info {
    flex: 1;
    min-width: 0;
  }

  .screenshot-filename {
    font-size: 14px;
    font-weight: 500;
    color: #1d2129;
    margin-bottom: 4px;
    word-break: break-all;
  }

  .screenshot-date,
  .screenshot-size {
    font-size: 12px;
    color: #86909c;
  }

  .delete-btn {
    flex-shrink: 0;
  }

  .no-screenshots {
    text-align: center;
    padding: 20px 0;
  }

/* 预览模态框样式（与详情页保持一致） */
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
  background-color: #f7f8fa;
}

/* 左侧信息面板 */
.preview-sidebar {
  width: 320px;
  background-color: #fff;
  border-right: 1px solid #e5e6eb;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  
  /* 隐藏滚动条但保留滚动功能 */
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE and Edge */
}

.preview-sidebar::-webkit-scrollbar {
  display: none; /* Chrome, Safari and Opera */
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
  background-color: #f7f8fa;
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
  background-color: #fff;
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
  background-color: rgba(255, 255, 255, 0.9);
  border: 1px solid #e5e6eb;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.nav-button:hover:not(:disabled) {
  background-color: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  transform: scale(1.1);
}

.prev-button {
  left: 20px;
}

.next-button {
  right: 20px;
}
</style>
