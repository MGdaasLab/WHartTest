<template>
  <a-modal
    :visible="visible"
    title="上传文档"
    :width="600"
    @ok="handleSubmit"
    @cancel="handleCancel"
    :confirm-loading="loading"
  >
    <a-form
      ref="formRef"
      :model="formData"
      :rules="rules"
      layout="vertical"
    >
      <a-form-item label="上传方式" field="uploadType">
        <a-radio-group v-model="formData.uploadType" @change="handleUploadTypeChange">
          <a-radio value="file">文件上传</a-radio>
          <a-radio value="text">文本内容</a-radio>
          <a-radio value="url">网页链接</a-radio>
        </a-radio-group>
      </a-form-item>

      <a-form-item label="文档标题" field="title">
        <a-input
          v-model="formData.title"
          placeholder="请输入文档标题"
          :max-length="200"
        />
      </a-form-item>

      <!-- 文件上传 -->
      <template v-if="formData.uploadType === 'file'">
        <a-form-item label="选择文件" field="file">
          <div class="file-upload-container">
            <input
              ref="fileInputRef"
              type="file"
              accept=".pdf,.doc,.docx,.ppt,.pptx,.txt,.md,.html,.htm"
              style="display: none"
              @change="handleFileInputChange"
            />
            <div class="upload-area" @click="triggerFileInput">
              <icon-upload />
              <div class="upload-text">
                <div>点击选择文件</div>
                <div class="upload-tip">
                  支持 PDF、Word、PowerPoint、文本、Markdown、HTML 格式
                </div>
              </div>
            </div>
            <div v-if="formData.file" class="selected-file">
              <div class="file-info">
                <icon-file />
                <span class="file-name">{{ formData.file.name }}</span>
                <span class="file-size">({{ formatFileSize(formData.file.size) }})</span>
                <a-button type="text" size="mini" @click="removeFile">
                  <icon-close />
                </a-button>
              </div>
            </div>
          </div>
        </a-form-item>
      </template>

      <!-- 文本内容 -->
      <template v-if="formData.uploadType === 'text'">
        <a-form-item label="文本内容" field="content">
          <a-textarea
            v-model="formData.content"
            placeholder="请输入或粘贴文本内容..."
            :rows="10"
            :max-length="50000"
            show-word-limit
          />
        </a-form-item>
      </template>

      <!-- 网页链接 -->
      <template v-if="formData.uploadType === 'url'">
        <a-form-item label="网页链接" field="url">
          <a-input
            v-model="formData.url"
            placeholder="请输入网页链接，如：https://example.com"
          />
        </a-form-item>
      </template>
    </a-form>

    <div v-if="uploadProgress > 0 && uploadProgress < 100" class="upload-progress">
      <a-progress :percent="uploadProgress" />
      <div class="progress-text">正在上传文档...</div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue';
import { Message } from '@arco-design/web-vue';
import { IconUpload, IconFile, IconClose } from '@arco-design/web-vue/es/icon';
import { KnowledgeService } from '../services/knowledgeService';
import type { UploadDocumentRequest, DocumentType } from '../types/knowledge';

interface Props {
  visible: boolean;
  knowledgeBaseId: string;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  submit: [];
  cancel: [];
}>();

const formRef = ref();
const fileInputRef = ref<HTMLInputElement>();
const loading = ref(false);
const uploadProgress = ref(0);

// 表单数据
const formData = reactive({
  uploadType: 'file' as 'file' | 'text' | 'url',
  title: '',
  file: null as File | null,
  content: '',
  url: '',
});

// 表单验证规则
const rules = computed(() => {
  const baseRules = {
    title: [
      { required: true, message: '请输入文档标题' },
      { minLength: 1, message: '文档标题不能为空' },
      { maxLength: 200, message: '文档标题不能超过200个字符' },
    ],
  };

  if (formData.uploadType === 'file') {
    return {
      ...baseRules,
      file: [
        { required: true, message: '请选择要上传的文件' },
      ],
    };
  } else if (formData.uploadType === 'text') {
    return {
      ...baseRules,
      content: [
        { required: true, message: '请输入文本内容' },
        { minLength: 10, message: '文本内容至少10个字符' },
        { maxLength: 50000, message: '文本内容不能超过50000个字符' },
      ],
    };
  } else if (formData.uploadType === 'url') {
    return {
      ...baseRules,
      url: [
        { required: true, message: '请输入网页链接' },
        {
          type: 'url',
          message: '请输入有效的网页链接',
          validator: (value: string) => {
            try {
              new URL(value);
              return true;
            } catch {
              return false;
            }
          }
        },
      ],
    };
  }

  return baseRules;
});

// 监听弹窗显示状态
watch(() => props.visible, (visible) => {
  if (visible) {
    resetForm();
  }
});

// 方法
const resetForm = () => {
  Object.assign(formData, {
    uploadType: 'file',
    title: '',
    file: null,
    content: '',
    url: '',
  });
  uploadProgress.value = 0;
  if (fileInputRef.value) {
    fileInputRef.value.value = '';
  }
  formRef.value?.clearValidate();
};

const handleUploadTypeChange = () => {
  // 切换上传方式时清空相关字段
  formData.file = null;
  formData.content = '';
  formData.url = '';
  if (fileInputRef.value) {
    fileInputRef.value.value = '';
  }
  formRef.value?.clearValidate();
};

const triggerFileInput = () => {
  fileInputRef.value?.click();
};

const handleFileInputChange = (event: Event) => {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];

  if (file) {
    formData.file = file;

    // 如果没有设置标题，使用文件名作为默认标题
    if (!formData.title) {
      const fileName = file.name;
      const nameWithoutExt = fileName.substring(0, fileName.lastIndexOf('.')) || fileName;
      formData.title = nameWithoutExt;
    }
  }
};

const removeFile = () => {
  formData.file = null;
  if (fileInputRef.value) {
    fileInputRef.value.value = '';
  }
};

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

const getDocumentType = (uploadType: string, file?: File): DocumentType => {
  if (uploadType === 'text') return 'txt';
  if (uploadType === 'url') return 'url';

  if (file) {
    const ext = file.name.split('.').pop()?.toLowerCase();
    const typeMap: Record<string, DocumentType> = {
      'pdf': 'pdf',
      'doc': 'docx',
      'docx': 'docx',
      'ppt': 'pptx',
      'pptx': 'pptx',
      'txt': 'txt',
      'md': 'md',
      'html': 'html',
      'htm': 'html',
    };
    return typeMap[ext || ''] || 'txt';
  }

  return 'txt';
};

const handleSubmit = async () => {
  try {
    // Arco Design 的 validate 方法：成功时返回 undefined，失败时抛出错误
    await formRef.value?.validate();

    // 验证文件上传模式下是否选择了文件
    if (formData.uploadType === 'file' && !formData.file) {
      Message.error('请选择要上传的文件');
      return;
    }

    loading.value = true;
    uploadProgress.value = 0;

    const uploadData: UploadDocumentRequest = {
      knowledge_base: props.knowledgeBaseId,
      title: formData.title,
      document_type: getDocumentType(formData.uploadType, formData.file || undefined),
    };

    if (formData.uploadType === 'file' && formData.file) {
      uploadData.file = formData.file;
    } else if (formData.uploadType === 'text') {
      uploadData.content = formData.content;
    } else if (formData.uploadType === 'url') {
      uploadData.url = formData.url;
    }

    // 模拟上传进度
    const progressInterval = setInterval(() => {
      if (uploadProgress.value < 90) {
        uploadProgress.value += Math.random() * 20;
      }
    }, 200);

    const result = await KnowledgeService.uploadDocument(uploadData);

    clearInterval(progressInterval);
    uploadProgress.value = 100;

    setTimeout(() => {
      emit('submit');
    }, 500);

  } catch (error: any) {
    console.error('上传文档失败:', error);
    // 检查是否是表单验证错误
    if (error && typeof error === 'object' && 'errorFields' in error) {
      Message.error('请检查表单填写是否正确');
    } else {
      // 显示具体的错误消息
      const errorMessage = error?.message || '上传文档失败';
      Message.error(errorMessage);
    }
    uploadProgress.value = 0;
  } finally {
    loading.value = false;
  }
};

const handleCancel = () => {
  emit('cancel');
};
</script>

<style scoped>
.upload-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  border: 2px dashed #d9d9d9;
  border-radius: 6px;
  background-color: #fafafa;
  cursor: pointer;
  transition: border-color 0.3s;
}

.upload-area:hover {
  border-color: #00a0e9;
}

.upload-text {
  margin-top: 12px;
  text-align: center;
}

.upload-text > div:first-child {
  font-size: 14px;
  color: #333;
  margin-bottom: 4px;
}

.upload-tip {
  font-size: 12px;
  color: #999;
}

.upload-progress {
  margin-top: 16px;
  padding: 16px;
  background-color: #f7f8fa;
  border-radius: 6px;
}

.progress-text {
  text-align: center;
  margin-top: 8px;
  font-size: 12px;
  color: #666;
}

.file-upload-container {
  width: 100%;
}

.selected-file {
  margin-top: 12px;
  padding: 8px 12px;
  background: #f7f8fa;
  border-radius: 6px;
  border: 1px solid #e5e6eb;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-name {
  flex: 1;
  font-size: 14px;
  color: #333;
}

.file-size {
  font-size: 12px;
  color: #666;
}

:deep(.arco-form-item-label) {
  font-weight: 500;
}
</style>
