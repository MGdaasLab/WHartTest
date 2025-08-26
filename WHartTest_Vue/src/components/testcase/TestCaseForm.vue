<template>
  <div class="testcase-form-container">
    <div class="form-header">
      <div class="form-title">
        <a-button type="text" size="small" @click="handleBackToList">
          <template #icon><icon-arrow-left /></template>
          返回列表
        </a-button>
        <h2>{{ isEditing ? '编辑测试用例' : '添加测试用例' }}</h2>
      </div>
      <div class="form-actions">
        <a-space>
          <a-button @click="handleBackToList">取消</a-button>
          <a-button type="primary" :loading="formLoading" @click="handleSubmit">
            保存
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
        <a-col :span="12">
          <a-form-item field="name" label="用例名称">
            <a-input v-model="formState.name" placeholder="请输入用例名称" allow-clear />
          </a-form-item>
        </a-col>
        <a-col :span="6">
          <a-form-item field="level" label="优先级">
            <a-select v-model="formState.level" placeholder="请选择优先级">
              <a-option value="P0">P0 - 最高</a-option>
              <a-option value="P1">P1 - 高</a-option>
              <a-option value="P2">P2 - 中</a-option>
              <a-option value="P3">P3 - 低</a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="6">
          <a-form-item field="module_id" label="所属模块">
            <a-tree-select
              v-model="formState.module_id"
              :data="moduleTree"
              placeholder="请选择所属模块"
              allow-clear
              allow-search
              :dropdown-style="{ maxHeight: '300px', overflow: 'auto' }"
            />
          </a-form-item>
        </a-col>
      </a-row>      <a-form-item field="precondition" label="前置条件">
        <a-textarea
          v-model="formState.precondition"
          placeholder="请输入前置条件"
          allow-clear
          :auto-size="{ minRows: 1, maxRows: 4 }"
        />
      </a-form-item>

      <div class="steps-section">
        <div class="steps-header">
          <h3>测试步骤</h3>
          <a-button type="primary" size="small" @click="addStep">
            <template #icon><icon-plus /></template>
            添加步骤
          </a-button>
        </div>

        <a-table
          :data="formState.steps"
          :pagination="false"
          :bordered="{ cell: true }"
          class="steps-table"
          row-key="temp_id"
        >
          <template #columns>
            <a-table-column title="步骤" data-index="step_number" :width="80" />
            <a-table-column title="步骤描述" data-index="description">
              <template #cell="{ record, rowIndex }">
                <a-textarea
                  v-model="record.description"
                  placeholder="请输入步骤描述"
                  :auto-size="{ minRows: 1, maxRows: 4 }"
                  @blur="validateStepField(rowIndex, 'description')"
                />
                <div class="field-error" v-if="stepErrors[rowIndex]?.description">
                  {{ stepErrors[rowIndex].description }}
                </div>
              </template>
            </a-table-column>
            <a-table-column title="预期结果" data-index="expected_result">
              <template #cell="{ record, rowIndex }">
                <a-textarea
                  v-model="record.expected_result"
                  placeholder="请输入预期结果"
                  :auto-size="{ minRows: 1, maxRows: 4 }"
                  @blur="validateStepField(rowIndex, 'expected_result')"
                />
                <div class="field-error" v-if="stepErrors[rowIndex]?.expected_result">
                  {{ stepErrors[rowIndex].expected_result }}
                </div>
              </template>
            </a-table-column>
            <a-table-column title="操作" :width="80">
              <template #cell="{ rowIndex }">
                <a-button
                  v-if="formState.steps.length > 1"
                  type="text"
                  status="danger"
                  size="small"
                  @click="removeStep(rowIndex)"
                >
                  删除
                </a-button>
              </template>
            </a-table-column>
          </template>
        </a-table>
      </div>

      <a-form-item field="notes" label="备注">
        <a-textarea
          v-model="formState.notes"
          placeholder="请输入备注信息"
          allow-clear
          :auto-size="{ minRows: 2, maxRows: 5 }"
        />
      </a-form-item>

      <!-- 截图管理区域 -->
      <div class="screenshots-section" v-if="isEditing">
        <div class="screenshots-header">
          <h3>截图</h3>
          <a-button type="primary" size="small" @click="triggerFileInput">
            <template #icon><icon-plus /></template>
            上传截图
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
                <span>点击预览</span>
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
                @click="handleDeleteExistingScreenshot(screenshot)"
              >
                删除
              </a-button>
            </div>
          </div>
        </div>

        <!-- 新上传的截图预览 -->
        <div v-if="newScreenshot" class="new-screenshot">
          <div class="section-title">待上传的截图</div>
          <div class="screenshots-grid">
            <div class="screenshot-item">
              <div class="screenshot-preview" @click="previewNewScreenshot()">
                <img :src="getFilePreview(newScreenshot)" :alt="newScreenshot.name" class="screenshot-thumbnail" />
                <div class="preview-overlay">
                  <icon-eye class="preview-icon" />
                  <span>点击预览</span>
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
                  删除
                </a-button>
              </div>
            </div>
          </div>
        </div>

        <div v-if="existingScreenshots.length === 0 && !newScreenshot" class="no-screenshots">
          <a-empty description="暂无截图" />
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
      :title="`图片预览 (${currentPreviewIndex + 1}/${existingScreenshots.length})`"
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
          <div class="thumbnail-navigation" v-if="existingScreenshots.length > 1">
            <h4>所有图片 ({{ existingScreenshots.length }})</h4>
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
import { IconArrowLeft, IconPlus, IconEye, IconLeft, IconRight } from '@arco-design/web-vue/es/icon';
import type { FormInstance, TreeNodeData } from '@arco-design/web-vue';
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
import { formatDate } from '@/utils/formatters';

interface StepWithError extends TestCaseStep {
  temp_id?: string; // 用于表格 row-key
}

interface FormState extends CreateTestCaseRequest {
  id?: number;
  steps: StepWithError[];
  notes?: string;
  module_id?: number;
}


const props = defineProps<{
  isEditing: boolean;
  testCaseId?: number | null;
  currentProjectId: number | null;
  initialSelectedModuleId?: number | null; // 用于新建时默认选中模块
  moduleTree: TreeNodeData[]; // 模块树数据
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'submitSuccess'): void;
}>();

const { isEditing, testCaseId, currentProjectId, initialSelectedModuleId, moduleTree } = toRefs(props);

const formLoading = ref(false);
const testCaseFormRef = ref<FormInstance>();
const formState = reactive<FormState>({
  id: undefined,
  name: '',
  precondition: '',
  level: 'P2',
  module_id: undefined,
  steps: [{ step_number: 1, description: '', expected_result: '', temp_id: Date.now().toString() }],
  notes: '',
});

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

const testCaseRules = {
  name: [
    { required: true, message: '请输入用例名称' },
    { maxLength: 100, message: '用例名称长度不能超过100个字符' },
  ],
  precondition: [
    { maxLength: 500, message: '前置条件长度不能超过500个字符' },
  ],
  level: [{ required: true, message: '请选择优先级' }],
  notes: [ // 备注字段的校验规则 (可选)
    { maxLength: 1000, message: '备注长度不能超过1000个字符' },
  ],
};

const stepErrors = ref<Array<{ description?: string; expected_result?: string }>>([]);

// 计算属性
const newScreenshot = computed(() => {
  return newScreenshots.value.length > 0 ? newScreenshots.value[0] : null;
});

const resetForm = () => {
  formState.id = undefined;
  formState.name = '';
  formState.precondition = '';
  formState.level = 'P2';
  formState.module_id = initialSelectedModuleId?.value || undefined;
  formState.steps = [{ step_number: 1, description: '', expected_result: '', temp_id: Date.now().toString() }];
  formState.notes = '';
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
      formState.module_id = data.module_id;
      formState.notes = data.notes || ''; // 设置备注信息
      formState.steps = data.steps.map((step, index) => ({ ...step, temp_id: `${Date.now()}-${index}` }));
      stepErrors.value = Array(data.steps.length).fill({});
      
      // 设置现有截图，并确保每个截图都有url字段用于兼容性
      existingScreenshots.value = (data.screenshots || []).map((screenshot: TestCaseScreenshot) => ({
        ...screenshot,
        url: screenshot.url || screenshot.screenshot_url || screenshot.screenshot,
        filename: screenshot.filename || getScreenshotFilename(screenshot.url || screenshot.screenshot_url || screenshot.screenshot || ''),
        uploaded_at: screenshot.uploaded_at || screenshot.created_at
      }));
    } else {
      Message.error(response.error || '获取测试用例详情失败');
      emit('close');
    }
  } catch (error) {
    Message.error('获取测试用例详情时发生错误');
    emit('close');
  } finally {
    formLoading.value = false;
  }
};

onMounted(() => {
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

const validateAllSteps = (): boolean => {
  // 步骤不再必填，直接返回 true
  return true;
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
  formState.steps.forEach((step, idx) => {
    step.step_number = idx + 1;
  });
};

const handleBackToList = () => {
  emit('close');
};

const handleSubmit = async () => {
  if (!currentProjectId.value) {
    Message.error('项目ID不存在');
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
    if (isEditing.value && formState.id) {
      const updatePayload: UpdateTestCaseRequest = {
        name: formState.name,
        precondition: formState.precondition,
        level: formState.level,
        module_id: formState.module_id,
        steps: payloadSteps,
        notes: formState.notes,
      };
      response = await updateTestCase(currentProjectId.value, formState.id, updatePayload);
    } else {
      const createPayload: CreateTestCaseRequest = {
        name: formState.name,
        precondition: formState.precondition,
        level: formState.level,
        module_id: formState.module_id,
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

      Message.success(isEditing.value ? '测试用例更新成功' : '测试用例创建成功');
      emit('submitSuccess');
    } else {
      Message.error(response.error || (isEditing.value ? '更新失败' : '创建失败'));
    }
  } catch (error) {
    console.error('提交测试用例出错:', error);
    Message.error('提交测试用例时发生错误');
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
        Message.warning(`${file.name} 不是有效的图片文件`);
        return false;
      }
      if (file.size > 10 * 1024 * 1024) { // 10MB
        Message.warning(`${file.name} 文件大小超过10MB`);
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

const removeCurrentScreenshot = () => {
  if (existingScreenshots.value.length > 0) {
    existingScreenshots.value.splice(0, 1);
  }
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
    title: '确认删除',
    content: `确定要删除截图 "${displayName}" 吗？此操作不可恢复。`,
    okText: '确认',
    cancelText: '取消',
    onOk: async () => {
      if (!testCaseId?.value || !currentProjectId.value || !screenshot.id) {
        Message.error('删除失败：缺少必要信息');
        return;
      }

      try {
        const response = await deleteTestCaseScreenshot(
          currentProjectId.value,
          testCaseId.value,
          screenshot.id
        );

        if (response.success) {
          Message.success('截图删除成功');
          // 从本地列表中移除
          existingScreenshots.value = existingScreenshots.value.filter(s => s.id !== screenshot.id);
        } else {
          Message.error(response.error || '删除截图失败');
        }
      } catch (error) {
        console.error('删除截图时发生错误:', error);
        Message.error('删除截图时发生错误');
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
    previewImageUrl.value = getFilePreview(file);
    previewTitle.value = file.name;
    previewInfo.value = {
      '文件名': file.name,
      '文件大小': formatFileSize(file.size),
      '文件类型': file.type,
      '状态': '待上传',
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
        Message.warning(`上传 ${file.name} 失败: ${response.error}`);
      }
    }

    // 清空新截图列表
    newScreenshots.value.forEach(file => {
      URL.revokeObjectURL(getFilePreview(file));
    });
    newScreenshots.value = [];

  } catch (error) {
    console.error('上传截图失败:', error);
    Message.error('上传截图时发生错误');
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
  const uploadTime = getScreenshotUploadTime(screenshot);

  previewImageUrl.value = screenshotUrl;
  previewTitle.value = displayName;
  previewInfo.value = {
    '文件名': displayName,
    '描述': screenshot.description || '-',
    '步骤': screenshot.step_number ? `步骤 ${screenshot.step_number}` : '-',
    '上传时间': formatDate(uploadTime),
    '上传者': screenshot.uploader_detail?.username || '-',
  };
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
    const uploadTime = getScreenshotUploadTime(screenshot);

    previewImageUrl.value = screenshotUrl;
    previewTitle.value = displayName;
    previewInfo.value = {
      '文件名': displayName,
      '描述': screenshot.description || '-',
      '步骤': screenshot.step_number ? `步骤 ${screenshot.step_number}` : '-',
      '上传时间': formatDate(uploadTime),
      '上传者': screenshot.uploader_detail?.username || '-',
    };
  }
};

const handleImageLoad = (event: Event) => {
  const img = event.target as HTMLImageElement;
  console.log('图片加载成功:', img.naturalWidth, 'x', img.naturalHeight);
};

const handleImageError = (_event: Event) => {
  console.error('图片加载失败');
  Message.error('图片加载失败');
};
</script>

<style scoped>
.testcase-form-container {
  background-color: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 4px 0 10px rgba(0, 0, 0, 0.2), 0 4px 10px rgba(0, 0, 0, 0.2), 0 0 10px rgba(0, 0, 0, 0.15);
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

  .steps-table {
    margin-bottom: 16px;

    :deep(.arco-table-container) {
      border-radius: 4px;
    }

    :deep(.arco-textarea) {
      width: 100%;
      resize: none;
    }
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