<template>
  <div class="chat-input-container">
    <div v-if="quotedMessage" class="quote-preview-wrapper">
      <div class="quote-preview">
        <icon-reply class="quote-icon" />
        <span class="quote-text">{{ truncateQuote(quotedMessage.content) }}</span>
        <a-button type="text" size="mini" class="quote-close-btn" @click="$emit('clear-quote')">
          <template #icon><icon-close /></template>
        </a-button>
      </div>
    </div>

    <div v-if="imagePreviews.length > 0" class="image-preview-wrapper">
      <div class="image-preview-header">
        <span class="image-preview-count">已选择 {{ imagePreviews.length }} 张图片</span>
        <a-button type="text" size="mini" class="clear-images-btn" @click="clearImages">
          清空
        </a-button>
      </div>
      <div class="image-preview-list">
        <div
          v-for="(preview, index) in imagePreviews"
          :key="`${preview}-${index}`"
          class="image-preview"
        >
          <img :src="preview" :alt="`预览图片 ${index + 1}`" />
          <span class="image-order-badge">{{ index + 1 }}</span>
          <a-button
            class="remove-image-btn"
            type="text"
            size="small"
            @click="removeImage(index)"
          >
            <template #icon><icon-close /></template>
          </a-button>
        </div>
      </div>
    </div>

    <div
      class="input-wrapper"
      :class="{ 'drag-over': isDragOver }"
      @drop.prevent="handleDrop"
      @dragover.prevent="handleDragOver"
      @dragleave.prevent="handleDragLeave"
    >
      <div class="textarea-wrapper">
        <a-textarea
          v-model="inputMessage"
          :placeholder="supportsVision ? '输入消息、拖拽、粘贴或选择图片... (Shift+Enter换行，Enter发送)' : '请输入你的消息... (Shift+Enter换行，Enter发送)'"
          :disabled="isLoading"
          class="chat-input"
          :auto-size="{ minRows: 1, maxRows: 6 }"
          @keydown="handleKeyDown"
          @paste="handlePaste"
        />

        <div v-if="isDragOver && supportsVision" class="drag-overlay">
          <icon-image class="drag-icon" />
          <span>释放以上传图片</span>
        </div>
      </div>

      <TokenUsageIndicator
        v-if="contextTokenCount > 0 || contextLimit > 0"
        :current-tokens="contextTokenCount"
        :max-tokens="contextLimit"
      />

      <div class="input-actions">
        <input
          ref="fileInputRef"
          type="file"
          accept="image/jpeg,image/png,image/gif"
          multiple
          class="hidden-file-input"
          @change="handleFileInputChange"
        />

        <a-button
          v-if="supportsVision && !isLoading"
          type="secondary"
          class="upload-button"
          @click="openFilePicker"
        >
          <template #icon><icon-image /></template>
          <span>图片</span>
        </a-button>

        <a-button
          v-if="!isLoading"
          type="primary"
          class="send-button"
          @click="handleSendMessage"
        >
          <template #icon><icon-send /></template>
          <span>发送</span>
        </a-button>
        <a-button
          v-else
          type="primary"
          status="danger"
          class="stop-button"
          @click="handleStopGeneration"
        >
          <template #icon><icon-record-stop /></template>
          <span>停止</span>
        </a-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import {
  Textarea as ATextarea,
  Button as AButton,
  Message
} from '@arco-design/web-vue';
import { IconImage, IconClose, IconReply, IconSend, IconRecordStop } from '@arco-design/web-vue/es/icon';
import TokenUsageIndicator from './TokenUsageIndicator.vue';

interface ChatMessage {
  content: string;
  isUser: boolean;
  time: string;
  messageType?: 'human' | 'ai' | 'tool' | 'system' | 'agent_step' | 'step_separator';
  imageBase64?: string;
  imageDataUrl?: string;
  imageBase64List?: string[];
  imageDataUrls?: string[];
}

interface Props {
  isLoading: boolean;
  supportsVision?: boolean;
  contextTokenCount?: number;
  contextLimit?: number;
  quotedMessage?: ChatMessage | null;
}

const props = withDefaults(defineProps<Props>(), {
  supportsVision: false,
  contextTokenCount: 0,
  contextLimit: 128000,
  quotedMessage: null
});

const emit = defineEmits<{
  'send-message': [data: {
    message: string;
    image?: string;
    imageDataUrl?: string;
    images?: string[];
    imageDataUrls?: string[];
    quotedMessage?: ChatMessage | null;
  }];
  'clear-quote': [];
  'stop-generation': [];
}>();

const truncateQuote = (text: string): string => {
  const maxLen = 80;
  const singleLine = text.replace(/\n/g, ' ').trim();
  return singleLine.length > maxLen ? singleLine.slice(0, maxLen) + '...' : singleLine;
};

const inputMessage = ref('');
const imageFiles = ref<File[]>([]);
const imagePreviews = ref<string[]>([]);
const fileInputRef = ref<HTMLInputElement | null>(null);
const isDragOver = ref(false);

const handleStopGeneration = () => {
  emit('stop-generation');
};

const removeImage = (index: number) => {
  imageFiles.value = imageFiles.value.filter((_, fileIndex) => fileIndex !== index);
  imagePreviews.value = imagePreviews.value.filter((_, previewIndex) => previewIndex !== index);
};

const clearImages = () => {
  imageFiles.value = [];
  imagePreviews.value = [];
  if (fileInputRef.value) {
    fileInputRef.value.value = '';
  }
};

const handleSendMessage = async () => {
  const message = inputMessage.value.trim();

  if (!message && imageFiles.value.length === 0) {
    Message.warning('请输入消息或上传图片！');
    return;
  }

  if (imageFiles.value.length > 0 && !props.supportsVision) {
    Message.error({
      content: '❌ 当前AI模型不支持图片输入\n' +
               '请先移除图片或切换到支持多模态的模型\n' +
               '（推荐：GPT-4V、Claude 3、Gemini Vision、Qwen-VL）',
      duration: 5000
    });
    return;
  }

  let imageBase64List: string[] = [];
  let imageDataUrlList: string[] = [];

  if (imageFiles.value.length > 0) {
    try {
      const results = await Promise.all(imageFiles.value.map((file) => fileToBase64WithDataUrl(file)));
      imageBase64List = results.map((result) => result.base64);
      imageDataUrlList = results.map((result) => result.dataUrl);
    } catch {
      Message.error('图片处理失败，请重试');
      return;
    }
  }

  emit('send-message', {
    message: message || '请查看图片',
    image: imageBase64List[0],
    imageDataUrl: imageDataUrlList[0],
    images: imageBase64List,
    imageDataUrls: imageDataUrlList,
    quotedMessage: props.quotedMessage
  });

  inputMessage.value = '';
  clearImages();
};

const fileToBase64WithDataUrl = (file: File): Promise<{ base64: string; dataUrl: string }> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result as string;
      const base64 = dataUrl.split(',')[1];
      resolve({ base64, dataUrl });
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
};

const readFileAsDataUrl = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
};

const isDuplicateImageFile = (file: File) => {
  return imageFiles.value.some((existingFile) => (
    existingFile.name === file.name
    && existingFile.size === file.size
    && existingFile.lastModified === file.lastModified
  ));
};

const handleKeyDown = (event: KeyboardEvent) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    void handleSendMessage();
  }
};

const validateImageFile = (file: File) => {
  if (!file.type.startsWith('image/')) {
    Message.error('只能上传图片文件');
    return false;
  }

  const maxSize = 10 * 1024 * 1024;
  if (file.size > maxSize) {
    Message.error('图片大小不能超过10MB');
    return false;
  }

  const validTypes = ['image/jpeg', 'image/png', 'image/gif'];
  if (!validTypes.includes(file.type)) {
    Message.error('仅支持JPG、PNG、GIF格式的图片');
    return false;
  }

  if (isDuplicateImageFile(file)) {
    Message.warning(`${file.name} 已存在，无需重复上传`);
    return false;
  }

  return true;
};

const appendImageFiles = async (files: File[]) => {
  const validFiles = files.filter(validateImageFile);
  if (validFiles.length === 0) {
    return;
  }

  try {
    const previews = await Promise.all(validFiles.map((file) => readFileAsDataUrl(file)));
    imageFiles.value = [...imageFiles.value, ...validFiles];
    imagePreviews.value = [...imagePreviews.value, ...previews];
  } catch {
    Message.error('图片预览生成失败，请重试');
  }
};

const openFilePicker = () => {
  fileInputRef.value?.click();
};

const handleFileInputChange = async (event: Event) => {
  const input = event.target as HTMLInputElement;
  const files = input.files ? Array.from(input.files) : [];
  if (!files.length) {
    return;
  }

  await appendImageFiles(files);
  input.value = '';
};

const handleDragOver = (_e: DragEvent) => {
  if (!props.supportsVision || props.isLoading) return;
  isDragOver.value = true;
};

const handleDragLeave = (_e: DragEvent) => {
  isDragOver.value = false;
};

const handleDrop = (e: DragEvent) => {
  isDragOver.value = false;

  if (!props.supportsVision) {
    Message.warning({
      content: '💡 当前AI模型不支持图片输入\n请在模型管理中选择支持多模态的模型（如GPT-4V、Claude 3、Qwen-VL等）',
      duration: 4000
    });
    return;
  }

  if (props.isLoading) return;

  const files = e.dataTransfer?.files ? Array.from(e.dataTransfer.files) : [];
  if (!files.length) return;

  void appendImageFiles(files);
};

const handlePaste = (e: ClipboardEvent) => {
  if (props.isLoading) return;

  const items = e.clipboardData?.items;
  if (!items) return;

  const imageFilesFromClipboard: File[] = [];

  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    if (!item.type.startsWith('image/')) {
      continue;
    }
    const file = item.getAsFile();
    if (file) {
      imageFilesFromClipboard.push(file);
    }
  }

  if (!imageFilesFromClipboard.length) {
    return;
  }

  e.preventDefault();

  if (!props.supportsVision) {
    Message.warning({
      content: '💡 当前AI模型不支持图片输入\n请在模型管理中选择支持多模态的模型\n（推荐：GPT-4V、Claude 3、Gemini Vision、Qwen-VL）',
      duration: 4000
    });
    return;
  }

  void appendImageFiles(imageFilesFromClipboard);
  Message.success(imageFilesFromClipboard.length === 1 ? '图片已粘贴' : `已粘贴 ${imageFilesFromClipboard.length} 张图片`);
};
</script>

<style scoped>
.hidden-file-input {
  display: none;
}

.chat-input-container {
  padding: 16px 20px;
  background-color: white;
  border-top: 1px solid #e5e6eb;
}

.quote-preview-wrapper {
  margin-bottom: 12px;
}

.quote-preview {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: linear-gradient(135deg, #f0f5ff 0%, #e8f3ff 100%);
  border-left: 3px solid #165dff;
  border-radius: 0 8px 8px 0;
}

.quote-icon {
  color: #165dff;
  font-size: 14px;
  flex-shrink: 0;
}

.quote-text {
  flex: 1;
  font-size: 13px;
  color: #4e5969;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.quote-close-btn {
  flex-shrink: 0;
  color: #86909c !important;
}

.quote-close-btn:hover {
  color: #f53f3f !important;
}

.image-preview-wrapper {
  margin-bottom: 12px;
}

.image-preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.image-preview-count {
  font-size: 12px;
  color: #4e5969;
  font-weight: 500;
}

.clear-images-btn {
  color: #86909c !important;
}

.image-preview-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.image-preview {
  position: relative;
  width: 108px;
  height: 108px;
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  background: #f7f8fa;
}

.image-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.image-order-badge {
  position: absolute;
  left: 6px;
  bottom: 6px;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.65);
  color: white;
  font-size: 11px;
  line-height: 20px;
  text-align: center;
}

.remove-image-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  background-color: rgba(0, 0, 0, 0.6);
  color: white;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.remove-image-btn:hover {
  background-color: rgba(0, 0, 0, 0.8);
}

.input-wrapper {
  display: flex;
  align-items: center;
  width: 100%;
  gap: 8px;
  position: relative;
  transition: all 0.3s;
}

.input-wrapper.drag-over {
  transform: scale(1.02);
}

.textarea-wrapper {
  position: relative;
  flex: 1;
}

.chat-input {
  width: 100%;
  border-radius: 12px;
  background-color: #f2f3f5;
  transition: all 0.2s;
  resize: none;
  min-height: 36px;
}

.chat-input:hover, .chat-input:focus {
  background-color: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.chat-input :deep(.arco-textarea) {
  border-radius: 12px;
  padding: 8px 12px;
  line-height: 20px;
  min-height: 36px;
}

.drag-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, rgba(22, 93, 255, 0.1), rgba(22, 93, 255, 0.05));
  border: 2px dashed #165dff;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  pointer-events: none;
  z-index: 10;
  animation: pulse 1.5s ease-in-out infinite;
}

.drag-icon {
  font-size: 32px;
  color: #165dff;
}

.drag-overlay span {
  font-size: 14px;
  color: #165dff;
  font-weight: 500;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.8;
    transform: scale(1.02);
  }
}

.input-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.upload-button,
.send-button,
.stop-button {
  display: flex;
  align-items: center;
  gap: 4px;
  border-radius: 20px;
  padding: 0 16px;
  height: 36px;
  flex-shrink: 0;
}

.stop-button {
  animation: pulse-stop 1.5s ease-in-out infinite;
}

@keyframes pulse-stop {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.icon-send {
  margin-right: 4px;
  font-size: 16px;
}
</style>
