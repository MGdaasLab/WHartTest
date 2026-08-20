<template>
  <a-modal
    v-model:visible="visible"
    title="导入用例"
    :width="600"
    :mask-closable="false"
    :modal-class="'import-modal'"
    :footer-style="{ display: 'flex', justifyContent: 'flex-end' }"
    @cancel="handleClose"
  >
    <template #footer>
      <a-space v-if="!importResult">
        <a-button @click="handleClose">取消</a-button>
        <a-button
          type="primary"
          :loading="importing"
          :disabled="!canImport"
          @click="handleImport"
        >
          <template #icon><icon-import /></template>
          {{ importing ? '导入中...' : '开始导入' }}
        </a-button>
      </a-space>
    </template>

    <a-spin :loading="loading">
      <!-- 导入结果展示 -->
      <div v-if="importResult" class="import-result">
        <a-result
          :status="importResult.error_count === 0 ? 'success' : 'warning'"
          :title="importResult.error_count === 0 ? '导入完成' : '导入完成（有警告）'"
        >
          <template #subtitle>
            <div class="result-stats">
              <div class="stat-item">
                <div class="stat-value">{{ importResult.total_rows }}</div>
                <div class="stat-label">总行数</div>
              </div>
              <div class="stat-item stat-success">
                <div class="stat-value">{{ importResult.imported_count }}</div>
                <div class="stat-label">成功导入</div>
              </div>
              <div class="stat-item stat-skip">
                <div class="stat-value">{{ importResult.skipped_count }}</div>
                <div class="stat-label">跳过</div>
              </div>
              <div class="stat-item stat-error">
                <div class="stat-value">{{ importResult.error_count }}</div>
                <div class="stat-label">错误</div>
              </div>
            </div>
          </template>
          <template #extra>
            <div v-if="importResult.duplicate_names.length > 0" class="result-detail">
              <a-collapse :default-active-key="[]" :bordered="false">
                <a-collapse-item key="duplicates">
                  <template #header>
                    <icon-exclamation-circle-fill class="warning-icon" />
                    发现 {{ importResult.duplicate_names.length }} 条同名用例
                  </template>
                  <ul class="detail-list">
                    <li v-for="dup in importResult.duplicate_names.slice(0, 10)" :key="dup.row">
                      第 {{ dup.row }} 行: "{{ dup.name }}" ({{ dup.module }})
                    </li>
                    <li v-if="importResult.duplicate_names.length > 10" class="more-items">
                      ... 还有 {{ importResult.duplicate_names.length - 10 }} 条
                    </li>
                  </ul>
                </a-collapse-item>
              </a-collapse>
            </div>
            <div v-if="importResult.errors.length > 0" class="result-detail">
              <a-collapse :default-active-key="['errors']" :bordered="false">
                <a-collapse-item key="errors">
                  <template #header>
                    <icon-close-circle-fill class="error-icon" />
                    {{ importResult.errors.length }} 条导入错误
                  </template>
                  <ul class="detail-list error-list">
                    <li v-for="err in importResult.errors.slice(0, 10)" :key="err.row">
                      第 {{ err.row }} 行: {{ err.error }}
                    </li>
                    <li v-if="importResult.errors.length > 10" class="more-items">
                      ... 还有 {{ importResult.errors.length - 10 }} 条
                    </li>
                  </ul>
                </a-collapse-item>
              </a-collapse>
            </div>
            <a-button type="outline" @click="resetImport" style="margin-top: 16px;">
              <template #icon><icon-refresh /></template>
              重新导入
            </a-button>
          </template>
        </a-result>
      </div>

      <!-- 导入表单 -->
      <div v-else class="import-form">
        <!-- 步骤指引 -->
        <div class="step-guide">
          <div class="step-item" :class="{ active: !form.templateId }">
            <span class="step-num">1</span>
            <span class="step-text">选择模版</span>
          </div>
          <div class="step-line"></div>
          <div class="step-item" :class="{ active: form.templateId && fileList.length === 0 }">
            <span class="step-num">2</span>
            <span class="step-text">上传文件</span>
          </div>
          <div class="step-line"></div>
          <div class="step-item" :class="{ active: canImport }">
            <span class="step-num">3</span>
            <span class="step-text">开始导入</span>
          </div>
        </div>

        <a-form :model="form" layout="vertical">
          <!-- 选择模版 -->
          <a-form-item required>
            <template #label>
              <span class="form-label">
                <icon-file-image class="label-icon" />
                选择导入模版
              </span>
            </template>
            <a-select
              v-model="form.templateId"
              placeholder="请选择导入模版"
              :loading="loadingTemplates"
              allow-clear
              size="large"
            >
              <a-option
                v-for="template in templates"
                :key="template.id"
                :value="template.id"
              >
                <div class="template-option">
                  <span class="template-name">{{ template.name }}</span>
                  <span class="template-desc" v-if="template.description">
                    {{ template.description }}
                  </span>
                </div>
              </a-option>
            </a-select>
            <template #extra>
              <a-link @click="goToTemplateManagement" class="manage-link">
                <icon-settings /> 管理模版
              </a-link>
            </template>
          </a-form-item>

          <!-- 模版配置预览 -->
          <transition name="fade">
            <div v-if="selectedTemplate" class="template-preview">
              <div class="preview-header">
                <icon-info-circle /> 模版配置
              </div>
              <div class="preview-content">
                <div class="preview-item">
                  <span class="preview-label">表头行</span>
                  <span class="preview-value">第 {{ selectedTemplate.header_row }} 行</span>
                </div>
                <div class="preview-item">
                  <span class="preview-label">数据起始行</span>
                  <span class="preview-value">第 {{ selectedTemplate.data_start_row }} 行</span>
                </div>
                <div class="preview-item">
                  <span class="preview-label">解析模式</span>
                  <span class="preview-value">{{ selectedTemplate.step_parsing_mode_display }}</span>
                </div>
                <div class="preview-item" v-if="selectedTemplate.sheet_name">
                  <span class="preview-label">工作表</span>
                  <span class="preview-value">{{ selectedTemplate.sheet_name }}</span>
                </div>
              </div>
            </div>
          </transition>

          <!-- 上传文件 -->
          <a-form-item required>
            <template #label>
              <span class="form-label">
                <icon-upload class="label-icon" />
                上传 Excel 文件
              </span>
            </template>
            <a-upload
              :file-list="fileList"
              :auto-upload="false"
              accept=".xlsx,.xls"
              :limit="1"
              draggable
              @change="handleFileChange"
            >
              <template #upload-button>
                <div class="upload-area">
                  <icon-upload class="upload-icon" />
                  <div class="upload-text">
                    <p class="upload-title">点击或拖拽文件到此处上传</p>
                    <p class="upload-hint">支持 .xlsx, .xls 格式</p>
                  </div>
                </div>
              </template>
            </a-upload>
          </a-form-item>
        </a-form>
      </div>
    </a-spin>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import { Message } from '@arco-design/web-vue';
import {
  IconUpload,
  IconImport,
  IconFileImage,
  IconSettings,
  IconInfoCircle,
  IconRefresh,
  IconExclamationCircleFill,
  IconCloseCircleFill,
} from '@arco-design/web-vue/es/icon';
import type { FileItem } from '@arco-design/web-vue/es/upload/interfaces';
import {
  getTemplateList,
  getTemplateDetail,
  importTestCases,
  type ImportExportTemplateListItem,
  type ImportExportTemplate,
  type ImportResult,
} from '../services/templateService';

const props = defineProps<{
  projectId: number;
}>();

const emit = defineEmits<{
  (e: 'success', result: ImportResult): void;
  (e: 'close'): void;
}>();

const router = useRouter();

const visible = ref(false);
const loading = ref(false);
const loadingTemplates = ref(false);
const importing = ref(false);

const templates = ref<ImportExportTemplateListItem[]>([]);
const selectedTemplate = ref<ImportExportTemplate | null>(null);
const fileList = ref<FileItem[]>([]);
const importResult = ref<ImportResult | null>(null);

const form = ref({
  templateId: null as number | null,
});

const canImport = computed(() => {
  return form.value.templateId && fileList.value.length > 0 && !importResult.value;
});

const loadTemplates = async () => {
  loadingTemplates.value = true;
  try {
    const result = await getTemplateList({ template_type: 'import', is_active: true });
    if (result.success && result.data) {
      templates.value = result.data;
      const bothResult = await getTemplateList({ template_type: 'both', is_active: true });
      if (bothResult.success && bothResult.data) {
        templates.value = [...templates.value, ...bothResult.data];
      }
    }
  } finally {
    loadingTemplates.value = false;
  }
};

watch(() => form.value.templateId, async (newId) => {
  if (newId) {
    loading.value = true;
    try {
      const result = await getTemplateDetail(newId);
      if (result.success && result.data) {
        selectedTemplate.value = result.data;
      }
    } finally {
      loading.value = false;
    }
  } else {
    selectedTemplate.value = null;
  }
});

const handleFileChange = (files: FileItem[]) => {
  fileList.value = files;
  importResult.value = null;
};

const handleImport = async () => {
  if (!form.value.templateId || fileList.value.length === 0) {
    Message.warning('请选择模版和上传文件');
    return;
  }

  const file = fileList.value[0].file;
  if (!file) {
    Message.error('文件无效');
    return;
  }

  importing.value = true;
  try {
    const result = await importTestCases(props.projectId, file, form.value.templateId);
    if (result.data) {
      importResult.value = result.data;
      if (result.data.imported_count > 0) {
        Message.success(`成功导入 ${result.data.imported_count} 条用例`);
        emit('success', result.data);
      }
    } else {
      Message.error(result.error || '导入失败');
    }
  } catch (error: any) {
    Message.error(error.message || '导入失败');
  } finally {
    importing.value = false;
  }
};

const resetImport = () => {
  importResult.value = null;
  fileList.value = [];
};

const handleClose = () => {
  visible.value = false;
  emit('close');
};

const goToTemplateManagement = () => {
  handleClose();
  router.push({ name: 'TemplateManagement' });
};

const open = () => {
  visible.value = true;
  importResult.value = null;
  fileList.value = [];
  form.value.templateId = null;
  selectedTemplate.value = null;
  loadTemplates();
};

defineExpose({ open });
</script>

<style scoped>
/* 导入表单容器 */
.import-form {
  width: 100%;
  box-sizing: border-box;
}

/* 隐藏上传列表中的开始按钮 */
:deep(.arco-upload-progress) {
  display: none !important;
}

/* 上传列表项样式 */
:deep(.arco-upload-list-item) {
  padding-right: 32px;
}

:deep(.arco-upload-list-item-operation) {
  right: 8px;
}

/* 步骤指引 */
.step-guide {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 28px;
  padding: 16px 0;
  background: linear-gradient(135deg, var(--color-fill-1) 0%, var(--color-fill-2) 100%);
  border-radius: 10px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 8px;
  opacity: 0.5;
  transition: all 0.3s;
}

.step-item.active {
  opacity: 1;
}

.step-num {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--color-border-2);
  color: var(--color-text-3);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  transition: all 0.3s;
}

.step-item.active .step-num {
  background: #00a0e9;
  color: #fff;
}

.step-text {
  font-size: 13px;
  color: var(--color-text-2);
}

.step-line {
  width: 40px;
  height: 2px;
  background: var(--color-border-2);
  margin: 0 12px;
}

/* 表单标签 */
.form-label {
  display: flex;
  align-items: center;
  gap: 6px;
}

.label-icon {
  color: var(--color-text-3);
}

/* 模版选项 */
.template-option {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.template-name {
  font-weight: 500;
}

.template-desc {
  font-size: 12px;
  color: var(--color-text-3);
}

.manage-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}

/* 模版预览 */
.template-preview {
  background: var(--color-fill-1);
  border-radius: 8px;
  margin-bottom: 20px;
  overflow: hidden;
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  background: var(--color-fill-2);
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-2);
}

.preview-content {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1px;
  background: var(--color-border-1);
}

.preview-item {
  display: flex;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--color-bg-1);
  font-size: 13px;
}

.preview-label {
  color: var(--color-text-3);
}

.preview-value {
  color: var(--color-text-1);
  font-weight: 500;
}

/* 上传区域 */
.upload-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 20px;
  border: 2px dashed var(--color-border-2);
  border-radius: 8px;
  background: var(--color-fill-1);
  cursor: pointer;
  transition: all 0.2s;
}

.upload-area:hover {
  border-color: #00a0e9;
  background: rgba(0, 160, 233, 0.04);
}

.upload-icon {
  font-size: 36px;
  color: var(--color-text-4);
  margin-bottom: 12px;
}

.upload-text {
  text-align: center;
}

.upload-title {
  margin: 0 0 4px 0;
  font-size: 14px;
  color: var(--color-text-2);
}

.upload-hint {
  margin: 0;
  font-size: 12px;
  color: var(--color-text-4);
}

/* 导入结果 */
.import-result {
  padding: 8px 0;
}

.result-stats {
  display: flex;
  justify-content: center;
  gap: 24px;
  margin: 16px 0;
}

.stat-item {
  text-align: center;
  padding: 12px 20px;
  background: var(--color-fill-1);
  border-radius: 8px;
  min-width: 80px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-text-1);
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: var(--color-text-3);
  margin-top: 4px;
}

.stat-success .stat-value {
  color: rgb(var(--green-6));
}

.stat-skip .stat-value {
  color: rgb(var(--orange-6));
}

.stat-error .stat-value {
  color: rgb(var(--red-6));
}

/* 结果详情 */
.result-detail {
  margin-top: 12px;
}

.result-detail :deep(.arco-collapse) {
  background: transparent;
}

.result-detail :deep(.arco-collapse-item-header) {
  padding: 10px 12px;
  background: var(--color-fill-1);
  border-radius: 6px;
}

.result-detail :deep(.arco-collapse-item-content) {
  padding: 0;
}

.warning-icon {
  color: rgb(var(--orange-6));
  margin-right: 6px;
}

.error-icon {
  color: rgb(var(--red-6));
  margin-right: 6px;
}

.detail-list {
  margin: 12px 0 0 0;
  padding: 12px 16px 12px 32px;
  background: var(--color-fill-1);
  border-radius: 6px;
  max-height: 120px;
  overflow-y: auto;
  list-style: disc;
}

.detail-list li {
  font-size: 12px;
  color: var(--color-text-2);
  line-height: 1.6;
  margin-bottom: 4px;
}

.error-list li {
  color: rgb(var(--red-6));
}

.more-items {
  color: var(--color-text-3) !important;
  font-style: italic;
}

/* 过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* 表单样式 */
:deep(.arco-form-item) {
  margin-bottom: 20px;
}

:deep(.arco-form-item-label) {
  font-weight: 500;
}

:deep(.arco-upload-list-item) {
  border-radius: 6px;
  background: var(--color-fill-1);
}

:deep(.arco-upload-drag) {
  padding: 0;
  background: transparent;
  border: none;
}

/* 响应式 */
@media (max-width: 576px) {
  .step-guide {
    padding: 12px 8px;
    margin-bottom: 20px;
  }

  .step-text {
    display: none;
  }

  .step-line {
    width: 24px;
    margin: 0 8px;
  }

  .result-stats {
    gap: 12px;
  }

  .stat-item {
    padding: 10px 14px;
    min-width: 60px;
  }

  .stat-value {
    font-size: 22px;
  }

  .preview-content {
    grid-template-columns: 1fr;
  }

  .upload-area {
    padding: 24px 16px;
  }
}
</style>
