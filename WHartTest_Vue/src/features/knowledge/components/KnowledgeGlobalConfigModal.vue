<template>
  <a-modal
    :visible="visible"
    title="知识库全局配置"
    :width="modalWidth"
    @ok="handleSubmit"
    @cancel="handleCancel"
    :confirm-loading="loading"
    :modal-style="{ maxWidth: '95vw' }"
  >
    <a-spin :loading="fetchLoading">
      <a-form
        ref="formRef"
        :model="formData"
        :rules="rules"
        layout="vertical"
      >
        <a-alert type="info">
          全局配置将应用于所有知识库向量生成，修改后新上传的文档将使用新配置。
        </a-alert>

        <a-divider>嵌入服务配置</a-divider>

        <a-row :gutter="16">
          <a-col :xs="24" :sm="12">
            <a-form-item label="嵌入服务" field="embedding_service">
              <a-select
                v-model="formData.embedding_service"
                placeholder="请选择嵌入服务"
                @change="handleEmbeddingServiceChange"
              >
                <a-option
                  v-for="service in embeddingServices"
                  :key="service.value"
                  :value="service.value"
                  :label="service.label"
                />
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :xs="24" :sm="12">
            <a-form-item label="模型名称" field="model_name">
              <a-input
                v-model="formData.model_name"
                placeholder="text-embedding-ada-002 / bge-m3"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item label="API基础URL" field="api_base_url">
          <a-input
            v-model="formData.api_base_url"
            placeholder="http://your-embedding-service.com/v1/embeddings"
          />
        </a-form-item>

        <a-row :gutter="16" align="end">
          <a-col :xs="24" :sm="16">
            <a-form-item label="API密钥" field="api_key">
              <a-input-password
                v-model="formData.api_key"
                :placeholder="apiKeyPlaceholder"
                @input="handleApiKeyInput"
              />
            </a-form-item>
          </a-col>
          <a-col :xs="24" :sm="8">
            <a-form-item>
              <a-button
                @click="testEmbeddingService"
                :loading="testingConnection"
                type="outline"
                long
              >
                <template #icon><icon-refresh /></template>
                测试连接
              </a-button>
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider>Reranker 精排服务（可选）</a-divider>

        <a-row :gutter="16">
          <a-col :xs="24" :sm="12">
            <a-form-item field="reranker_service">
              <template #label>
                Reranker 服务
                <a-tooltip content="Reranker用于对检索结果进行精排，可显著提升检索精度。可独立于嵌入服务配置。">
                  <icon-question-circle class="label-tip-icon" />
                </a-tooltip>
              </template>
              <a-select
                v-model="formData.reranker_service"
                placeholder="请选择Reranker服务"
                @change="handleRerankerServiceChange"
              >
                <a-option
                  v-for="service in rerankerServices"
                  :key="service.value"
                  :value="service.value"
                  :label="service.label"
                />
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :xs="24" :sm="12">
            <a-form-item label="Reranker 模型" field="reranker_model_name">
              <a-input
                v-model="formData.reranker_model_name"
                placeholder="bge-reranker-v2-m3"
                :disabled="formData.reranker_service === 'none'"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item
          v-if="formData.reranker_service !== 'none'"
          label="Reranker API地址"
          field="reranker_api_url"
        >
          <a-input
            v-model="formData.reranker_api_url"
            placeholder="http://xinference:9997（不填则使用嵌入服务地址）"
          />
        </a-form-item>

        <a-row v-if="formData.reranker_service !== 'none'" :gutter="16" align="end">
          <a-col :xs="24" :sm="16">
            <a-form-item label="Reranker API密钥" field="reranker_api_key">
              <a-input-password
                v-model="formData.reranker_api_key"
                :placeholder="rerankerApiKeyPlaceholder"
                @input="handleRerankerApiKeyInput"
              />
            </a-form-item>
          </a-col>
          <a-col :xs="24" :sm="8">
            <a-form-item>
              <a-button
                @click="testRerankerService"
                :loading="testingReranker"
                type="outline"
                long
              >
                <template #icon><icon-refresh /></template>
                测试
              </a-button>
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider>默认分块配置</a-divider>

        <a-row :gutter="16">
          <a-col :xs="24" :sm="12">
            <a-form-item field="chunk_size">
              <template #label>
                分块大小
                <a-tooltip content="每个文本块的最大字符数。建议值1000-2000，较小值提高检索精度，较大值保持上下文完整性。">
                  <icon-question-circle class="label-tip-icon" />
                </a-tooltip>
              </template>
              <a-input-number
                v-model="formData.chunk_size"
                placeholder="分块大小"
                :min="100"
                :max="4000"
                :step="100"
                style="width: 100%"
              />
            </a-form-item>
          </a-col>
          <a-col :xs="24" :sm="12">
            <a-form-item field="chunk_overlap">
              <template #label>
                分块重叠
                <a-tooltip content="相邻文本块之间的重叠字符数。建议为分块大小的10-20%，可避免跨块信息丢失。">
                  <icon-question-circle class="label-tip-icon" />
                </a-tooltip>
              </template>
              <a-input-number
                v-model="formData.chunk_overlap"
                placeholder="分块重叠"
                :min="0"
                :max="500"
                :step="50"
                style="width: 100%"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <div v-if="formData.updated_by_name" class="config-meta">
          <a-space>
            <span>最后更新：{{ formData.updated_by_name }}</span>
            <span>{{ formatDate(formData.updated_at) }}</span>
          </a-space>
        </div>
      </a-form>
    </a-spin>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue';
import { Message } from '@arco-design/web-vue';
import { IconRefresh, IconQuestionCircle } from '@arco-design/web-vue/es/icon';
import { KnowledgeService } from '../services/knowledgeService';
import type {
  KnowledgeGlobalConfig,
  EmbeddingServiceType,
  EmbeddingServiceOption,
  RerankerServiceType,
  RerankerServiceOption
} from '../types/knowledge';
import { getRequiredFieldsForEmbeddingService } from '../types/knowledge';

interface Props {
  visible: boolean;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  close: [];
  saved: [];
}>();

const formRef = ref();
const loading = ref(false);
const fetchLoading = ref(false);
const testingConnection = ref(false);
const testingReranker = ref(false);
const hasSavedApiKey = ref(false);
const hasSavedRerankerApiKey = ref(false);
const apiKeyTouched = ref(false);
const rerankerApiKeyTouched = ref(false);

// 窗口宽度响应式
const windowWidth = ref(window.innerWidth);
const updateWindowWidth = () => { windowWidth.value = window.innerWidth; };
const modalWidth = computed(() => windowWidth.value < 600 ? '95%' : 580);

onMounted(() => window.addEventListener('resize', updateWindowWidth));
onUnmounted(() => window.removeEventListener('resize', updateWindowWidth));

// 表单数据
const formData = reactive<KnowledgeGlobalConfig>({
  embedding_service: 'custom',
  api_base_url: '',
  api_key: '',
  model_name: '',
  reranker_service: 'none',
  reranker_api_url: '',
  reranker_api_key: '',
  reranker_model_name: 'Qwen3-VL-Reranker-2B',
  chunk_size: 1000,
  chunk_overlap: 200,
  updated_at: '',
  updated_by_name: '',
});

// 嵌入服务选项
const embeddingServices = ref<EmbeddingServiceOption[]>([]);

// Reranker 服务选项
const rerankerServices = ref<RerankerServiceOption[]>([
  { value: 'none', label: '不启用' },
  { value: 'xinference', label: 'Xinference' },
  { value: 'custom', label: '自定义API' },
]);

// 动态表单验证规则
const rules = computed(() => {
  const baseRules: any = {
    embedding_service: [
      { required: true, message: '请选择嵌入服务' },
    ],
    api_base_url: [
      { required: true, message: '请输入API基础URL' },
    ],
    model_name: [
      { required: true, message: '请输入模型名称' },
    ],
    chunk_size: [
      { required: true, message: '请输入分块大小' },
      { type: 'number', min: 100, max: 4000, message: '分块大小必须在100-4000之间' },
    ],
    chunk_overlap: [
      { required: true, message: '请输入分块重叠' },
      { type: 'number', min: 0, max: 500, message: '分块重叠必须在0-500之间' },
    ],
  };

  const requiredFields = getRequiredFieldsForEmbeddingService(formData.embedding_service || '');
  if (requiredFields.includes('api_key')) {
    baseRules.api_key = [{
      required: !hasSavedApiKey.value || apiKeyTouched.value,
      message: '请输入API密钥',
    }];
  }

  return baseRules;
});

const apiKeyPlaceholder = computed(() =>
  hasSavedApiKey.value ? '已保存，如需修改请重新输入' : 'OpenAI/Azure必填，其他服务可选'
);

const rerankerApiKeyPlaceholder = computed(() =>
  hasSavedRerankerApiKey.value ? '已保存，如需修改请重新输入' : 'OpenAI/Azure必填，其他服务可选'
);

// 监听弹窗显示状态
watch(() => props.visible, async (visible) => {
  if (visible) {
    await fetchData();
  }
});

// 获取数据
const fetchData = async () => {
  fetchLoading.value = true;
  try {
    // 获取嵌入服务选项
    const servicesResponse = await KnowledgeService.getEmbeddingServices();
    embeddingServices.value = servicesResponse.services;

    // 获取当前配置
    const config = await KnowledgeService.getGlobalConfig();
    hasSavedApiKey.value = !!config.api_key;
    hasSavedRerankerApiKey.value = !!config.reranker_api_key;
    apiKeyTouched.value = false;
    rerankerApiKeyTouched.value = false;
    Object.assign(formData, {
      ...config,
      api_key: '',
      reranker_api_key: '',
    });
  } catch (error) {
    console.error('获取配置失败:', error);
    Message.error('获取配置失败');
  } finally {
    fetchLoading.value = false;
  }
};

// 处理嵌入服务变化
const handleEmbeddingServiceChange = (value: EmbeddingServiceType) => {
  switch (value) {
    case 'openai':
      formData.api_base_url = 'https://api.openai.com/v1/embeddings';
      formData.model_name = 'text-embedding-ada-002';
      break;
    case 'azure_openai':
      formData.api_base_url = 'https://your-resource.openai.azure.com/';
      formData.model_name = 'text-embedding-ada-002';
      break;
    case 'ollama':
      formData.api_base_url = 'http://localhost:11434';
      formData.model_name = 'bge-m3';
      formData.api_key = '';
      hasSavedApiKey.value = false;
      apiKeyTouched.value = true;
      break;
    case 'xinference':
      formData.api_base_url = 'http://127.0.0.1:8917';
      formData.model_name = 'qwen3-vl-emb-2b';
      formData.api_key = '';
      hasSavedApiKey.value = false;
      apiKeyTouched.value = true;
      break;
    case 'custom':
      formData.api_base_url = 'http://your-embedding-service:8080/v1/embeddings';
      formData.model_name = 'bge-m3';
      break;
  }
};

const handleApiKeyInput = () => {
  apiKeyTouched.value = true;
};

const handleRerankerApiKeyInput = () => {
  rerankerApiKeyTouched.value = true;
};

// 处理 Reranker 服务变化
const handleRerankerServiceChange = (value: RerankerServiceType) => {
  switch (value) {
    case 'none':
      formData.reranker_api_url = '';
      // 保留默认模型名，不清空
      if (!formData.reranker_model_name) {
        formData.reranker_model_name = 'Qwen3-VL-Reranker-2B';
      }
      break;
    case 'xinference':
      formData.reranker_api_url = '';
      formData.reranker_model_name = 'Qwen3-VL-Reranker-2B';
      break;
    case 'custom':
      formData.reranker_api_url = 'http://your-reranker-service:8080/v1/rerank';
      formData.reranker_model_name = 'Qwen3-VL-Reranker-2B';
      break;
  }
};

// 测试嵌入服务连接
const testEmbeddingService = async () => {
  if (!formData.embedding_service || !formData.api_base_url || !formData.model_name) {
    Message.warning('请先完成嵌入服务配置');
    return;
  }
  
  const needsApiKey = formData.embedding_service === 'openai' || formData.embedding_service === 'azure_openai';
  const hasUsableApiKey = apiKeyTouched.value ? !!formData.api_key : hasSavedApiKey.value;
  if (needsApiKey && !hasUsableApiKey) {
    Message.warning('此服务需要API密钥');
    return;
  }

  testingConnection.value = true;
  try {
    // 通过后端代理测试，避免跨域问题
    const payload: {
      embedding_service: string;
      api_base_url: string;
      api_key?: string;
      model_name: string;
    } = {
      embedding_service: formData.embedding_service,
      api_base_url: formData.api_base_url,
      model_name: formData.model_name,
    };
    if (apiKeyTouched.value) {
      payload.api_key = formData.api_key || '';
    }
    const result = await KnowledgeService.testEmbeddingConnection(payload);
    
    if (result.success) {
      Message.success(result.message || '嵌入模型测试成功！服务运行正常');
    } else {
      Message.error(result.message || '测试失败');
    }
  } catch (error: any) {
    Message.error(error?.message || '无法连接到服务');
  } finally {
    testingConnection.value = false;
  }
};

// 测试 Reranker 服务连接
const testRerankerService = async () => {
  if (formData.reranker_service === 'none') {
    Message.warning('请先启用 Reranker 服务');
    return;
  }

  if (!formData.reranker_model_name) {
    Message.warning('请输入 Reranker 模型名称');
    return;
  }

  testingReranker.value = true;
  try {
    const payload: {
      reranker_service: string;
      reranker_api_url: string;
      reranker_api_key?: string;
      reranker_model_name: string;
    } = {
      reranker_service: formData.reranker_service,
      reranker_api_url: formData.reranker_api_url || formData.api_base_url || '',
      reranker_model_name: formData.reranker_model_name,
    };
    if (rerankerApiKeyTouched.value) {
      payload.reranker_api_key = formData.reranker_api_key || '';
    }
    const result = await KnowledgeService.testRerankerConnection(payload);

    if (result.success) {
      Message.success(result.message || 'Reranker 服务测试成功！');
    } else {
      Message.error(result.message || 'Reranker 测试失败');
    }
  } catch (error: any) {
    Message.error(error?.message || '无法连接到 Reranker 服务');
  } finally {
    testingReranker.value = false;
  }
};

const formatDate = (dateStr?: string) => {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleString('zh-CN');
};

const handleSubmit = async () => {
  try {
    await formRef.value?.validate();
    loading.value = true;

    const payload: Partial<KnowledgeGlobalConfig> = {
      embedding_service: formData.embedding_service,
      api_base_url: formData.api_base_url,
      model_name: formData.model_name,
      reranker_service: formData.reranker_service,
      reranker_api_url: formData.reranker_api_url,
      reranker_model_name: formData.reranker_model_name,
      chunk_size: formData.chunk_size,
      chunk_overlap: formData.chunk_overlap,
    };
    if (apiKeyTouched.value) {
      payload.api_key = formData.api_key;
    }
    if (rerankerApiKeyTouched.value) {
      payload.reranker_api_key = formData.reranker_api_key;
    }

    await KnowledgeService.updateGlobalConfig(payload);

    Message.success('配置保存成功');
    emit('saved');
    emit('close');
  } catch (error: any) {
    console.error('保存配置失败:', error);
    Message.error(error?.message || '保存配置失败');
  } finally {
    loading.value = false;
  }
};

const handleCancel = () => {
  emit('close');
};
</script>

<style scoped>
:deep(.arco-form-item) {
  margin-bottom: 12px;
}

:deep(.arco-divider) {
  margin: 12px 0;
}

:deep(.arco-alert) {
  margin-bottom: 12px !important;
}

.config-meta {
  font-size: 12px;
  color: var(--color-text-3);
  text-align: right;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border);
}

.label-tip-icon {
  margin-left: 4px;
  color: var(--color-text-3);
  cursor: help;
}
</style>
