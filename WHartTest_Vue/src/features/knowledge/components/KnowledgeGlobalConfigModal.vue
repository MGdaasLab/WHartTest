<template>
  <a-modal
    :visible="visible"
    title="知识库全局配置"
    :width="modalWidth"
    :confirm-loading="loading"
    :modal-style="{ maxWidth: '95vw' }"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-spin :loading="fetchLoading">
      <a-form ref="formRef" :model="formData" :rules="rules" layout="vertical">
        <a-alert type="info">
          全局配置会应用到新上传并重新处理的知识库文档。修改切分策略后，历史文档需要重新处理才能生效。
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
              <a-input v-model="formData.model_name" placeholder="text-embedding-ada-002 / bge-m3" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item label="API 基础 URL" field="api_base_url">
          <a-input
            v-model="formData.api_base_url"
            placeholder="http://your-embedding-service.com/v1/embeddings"
          />
        </a-form-item>

        <a-row :gutter="16" align="end">
          <a-col :xs="24" :sm="16">
            <a-form-item label="API 密钥" field="api_key">
              <a-input-password
                v-model="formData.api_key"
                :placeholder="apiKeyPlaceholder"
                @input="handleApiKeyInput"
              />
            </a-form-item>
          </a-col>
          <a-col :xs="24" :sm="8">
            <a-form-item>
              <a-button type="outline" long :loading="testingConnection" @click="testEmbeddingService">
                <template #icon><icon-refresh /></template>
                测试连接
              </a-button>
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider>Reranker 精排服务</a-divider>

        <a-row :gutter="16">
          <a-col :xs="24" :sm="12">
            <a-form-item field="reranker_service">
              <template #label>
                Reranker 服务
                <a-tooltip content="Reranker 用于对检索结果做二次精排，能提升召回结果的排序质量。">
                  <icon-question-circle class="label-tip-icon" />
                </a-tooltip>
              </template>
              <a-select
                v-model="formData.reranker_service"
                placeholder="请选择 Reranker 服务"
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
          label="Reranker API 地址"
          field="reranker_api_url"
        >
          <a-input
            v-model="formData.reranker_api_url"
            placeholder="http://xinference:9997，不填则复用嵌入服务地址"
          />
        </a-form-item>

        <a-row v-if="formData.reranker_service !== 'none'" :gutter="16" align="end">
          <a-col :xs="24" :sm="16">
            <a-form-item label="Reranker API 密钥" field="reranker_api_key">
              <a-input-password
                v-model="formData.reranker_api_key"
                :placeholder="rerankerApiKeyPlaceholder"
                @input="handleRerankerApiKeyInput"
              />
            </a-form-item>
          </a-col>
          <a-col :xs="24" :sm="8">
            <a-form-item>
              <a-button type="outline" long :loading="testingReranker" @click="testRerankerService">
                <template #icon><icon-refresh /></template>
                测试
              </a-button>
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider>默认切分配置</a-divider>

        <a-row :gutter="16">
          <a-col :xs="24" :sm="12">
            <a-form-item field="chunk_strategy">
              <template #label>
                切分策略
                <a-tooltip content="固定长度按字符窗口切分；结构优先会优先按标题、段落和换行切分；Markdown 标题仅对 Markdown 文档按标题层级切分。">
                  <icon-question-circle class="label-tip-icon" />
                </a-tooltip>
              </template>
              <a-select v-model="formData.chunk_strategy" placeholder="请选择切分策略">
                <a-option value="recursive_character">固定长度</a-option>
                <a-option value="heading_aware">结构优先</a-option>
                <a-option value="markdown_header">Markdown 标题</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :xs="24" :sm="12">
            <a-form-item field="chunk_size">
              <template #label>
                分块大小
                <a-tooltip content="每个文本块的最大字符数。通常 1000-2000 比较稳，值越大越保留上下文，值越小越利于精准召回。">
                  <icon-question-circle class="label-tip-icon" />
                </a-tooltip>
              </template>
              <a-input-number
                v-model="formData.chunk_size"
                :min="100"
                :max="4000"
                :step="100"
                style="width: 100%"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :xs="24" :sm="12">
            <a-form-item field="chunk_overlap">
              <template #label>
                分块重叠
                <a-tooltip content="相邻分块间保留的重叠字符数。一般建议设置为分块大小的 10%-20%。">
                  <icon-question-circle class="label-tip-icon" />
                </a-tooltip>
              </template>
              <a-input-number
                v-model="formData.chunk_overlap"
                :min="0"
                :max="500"
                :step="50"
                style="width: 100%"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider>Parent-Child 双层切分</a-divider>

        <a-form-item field="parent_child_enabled">
          <template #label>
            启用 Parent-Child 模式
            <a-tooltip content="开启后，文档会切分为大块（parent，用于上下文）和小块（child，用于召回）。检索命中 child 后返回其 parent 内容，减少语义断裂。">
              <icon-question-circle class="label-tip-icon" />
            </a-tooltip>
          </template>
          <a-switch v-model="formData.parent_child_enabled" />
        </a-form-item>

        <template v-if="formData.parent_child_enabled">
          <a-row :gutter="16">
            <a-col :xs="24" :sm="12">
              <a-form-item field="parent_chunk_size">
                <template #label>
                  Parent 块大小
                  <a-tooltip content="父块的最大字符数，用于提供完整上下文。建议 2000-4000。">
                    <icon-question-circle class="label-tip-icon" />
                  </a-tooltip>
                </template>
                <a-input-number
                  v-model="formData.parent_chunk_size"
                  :min="1000"
                  :max="8000"
                  :step="500"
                  style="width: 100%"
                />
              </a-form-item>
            </a-col>
            <a-col :xs="24" :sm="12">
              <a-form-item field="parent_chunk_overlap">
                <template #label>
                  Parent 块重叠
                  <a-tooltip content="父块之间的重叠字符数。">
                    <icon-question-circle class="label-tip-icon" />
                  </a-tooltip>
                </template>
                <a-input-number
                  v-model="formData.parent_chunk_overlap"
                  :min="0"
                  :max="500"
                  :step="50"
                  style="width: 100%"
                />
              </a-form-item>
            </a-col>
          </a-row>

          <a-row :gutter="16">
            <a-col :xs="24" :sm="12">
              <a-form-item field="child_chunk_size">
                <template #label>
                  Child 块大小
                  <a-tooltip content="子块的最大字符数，用于向量化召回。建议与 embedding 模型最优输入长度对齐（通常 500-1000）。">
                    <icon-question-circle class="label-tip-icon" />
                  </a-tooltip>
                </template>
                <a-input-number
                  v-model="formData.child_chunk_size"
                  :min="200"
                  :max="2000"
                  :step="100"
                  style="width: 100%"
                />
              </a-form-item>
            </a-col>
            <a-col :xs="24" :sm="12">
              <a-form-item field="child_chunk_overlap">
                <template #label>
                  Child 块重叠
                  <a-tooltip content="子块之间的重叠字符数。">
                    <icon-question-circle class="label-tip-icon" />
                  </a-tooltip>
                </template>
                <a-input-number
                  v-model="formData.child_chunk_overlap"
                  :min="0"
                  :max="400"
                  :step="50"
                  style="width: 100%"
                />
              </a-form-item>
            </a-col>
          </a-row>
        </template>

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
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import { Message } from '@arco-design/web-vue';
import { IconQuestionCircle, IconRefresh } from '@arco-design/web-vue/es/icon';
import { KnowledgeService } from '../services/knowledgeService';
import type {
  EmbeddingServiceOption,
  EmbeddingServiceType,
  KnowledgeGlobalConfig,
  RerankerServiceOption,
  RerankerServiceType,
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

const windowWidth = ref(window.innerWidth);
const updateWindowWidth = () => {
  windowWidth.value = window.innerWidth;
};
const modalWidth = computed(() => (windowWidth.value < 600 ? '95%' : 580));

onMounted(() => window.addEventListener('resize', updateWindowWidth));
onUnmounted(() => window.removeEventListener('resize', updateWindowWidth));

const formData = reactive<KnowledgeGlobalConfig>({
  embedding_service: 'custom',
  api_base_url: '',
  api_key: '',
  model_name: '',
  reranker_service: 'none',
  reranker_api_url: '',
  reranker_api_key: '',
  reranker_model_name: 'Qwen3-VL-Reranker-2B',
  chunk_strategy: 'recursive_character',
  chunk_size: 1000,
  chunk_overlap: 200,
  parent_child_enabled: false,
  parent_chunk_size: 2000,
  parent_chunk_overlap: 200,
  child_chunk_size: 800,
  child_chunk_overlap: 200,
  updated_at: '',
  updated_by_name: '',
});

const embeddingServices = ref<EmbeddingServiceOption[]>([]);
const rerankerServices = ref<RerankerServiceOption[]>([
  { value: 'none', label: '不启用' },
  { value: 'xinference', label: 'Xinference' },
  { value: 'custom', label: '自定义 API' },
]);

const rules = computed(() => {
  const baseRules: any = {
    embedding_service: [{ required: true, message: '请选择嵌入服务' }],
    api_base_url: [{ required: true, message: '请输入 API 基础 URL' }],
    model_name: [{ required: true, message: '请输入模型名称' }],
    chunk_strategy: [{ required: true, message: '请选择切分策略' }],
    chunk_size: [
      { required: true, message: '请输入分块大小' },
      { type: 'number', min: 100, max: 4000, message: '分块大小必须在 100-4000 之间' },
    ],
    chunk_overlap: [
      { required: true, message: '请输入分块重叠' },
      { type: 'number', min: 0, max: 500, message: '分块重叠必须在 0-500 之间' },
    ],
    parent_chunk_size: [
      { type: 'number', min: 1000, max: 8000, message: 'Parent 块大小必须在 1000-8000 之间' },
    ],
    parent_chunk_overlap: [
      { type: 'number', min: 0, max: 500, message: 'Parent 块重叠必须在 0-500 之间' },
    ],
    child_chunk_size: [
      { type: 'number', min: 200, max: 2000, message: 'Child 块大小必须在 200-2000 之间' },
    ],
    child_chunk_overlap: [
      { type: 'number', min: 0, max: 400, message: 'Child 块重叠必须在 0-400 之间' },
    ],
  };

  const requiredFields = getRequiredFieldsForEmbeddingService(formData.embedding_service || '');
  if (requiredFields.includes('api_key')) {
    baseRules.api_key = [
      {
        required: !hasSavedApiKey.value || apiKeyTouched.value,
        message: '请输入 API 密钥',
      },
    ];
  }

  return baseRules;
});

const apiKeyPlaceholder = computed(() =>
  hasSavedApiKey.value ? '已保存，如需修改请重新输入' : 'OpenAI / Azure OpenAI 必填'
);

const rerankerApiKeyPlaceholder = computed(() =>
  hasSavedRerankerApiKey.value ? '已保存，如需修改请重新输入' : '需要时再填写'
);

watch(
  () => props.visible,
  async (visible) => {
    if (visible) {
      await fetchData();
    }
  }
);

const fetchData = async () => {
  fetchLoading.value = true;
  try {
    const servicesResponse = await KnowledgeService.getEmbeddingServices();
    embeddingServices.value = servicesResponse.services;

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

const handleRerankerServiceChange = (value: RerankerServiceType) => {
  switch (value) {
    case 'none':
      formData.reranker_api_url = '';
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

const handleApiKeyInput = () => {
  apiKeyTouched.value = true;
};

const handleRerankerApiKeyInput = () => {
  rerankerApiKeyTouched.value = true;
};

const testEmbeddingService = async () => {
  if (!formData.embedding_service || !formData.api_base_url || !formData.model_name) {
    Message.warning('请先完成嵌入服务配置');
    return;
  }

  const needsApiKey =
    formData.embedding_service === 'openai' || formData.embedding_service === 'azure_openai';
  const hasUsableApiKey = apiKeyTouched.value ? !!formData.api_key : hasSavedApiKey.value;
  if (needsApiKey && !hasUsableApiKey) {
    Message.warning('当前服务需要 API 密钥');
    return;
  }

  testingConnection.value = true;
  try {
    const payload: {
      embedding_service: string;
      api_base_url: string;
      api_key?: string;
      model_name: string;
    } = {
      embedding_service: formData.embedding_service,
      api_base_url: formData.api_base_url || '',
      model_name: formData.model_name,
    };
    if (apiKeyTouched.value) {
      payload.api_key = formData.api_key || '';
    }
    const result = await KnowledgeService.testEmbeddingConnection(payload);
    if (result.success) {
      Message.success(result.message || '嵌入服务测试成功');
    } else {
      Message.error(result.message || '测试失败');
    }
  } catch (error: any) {
    Message.error(error?.message || '无法连接到嵌入服务');
  } finally {
    testingConnection.value = false;
  }
};

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
      Message.success(result.message || 'Reranker 服务测试成功');
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
      chunk_strategy: formData.chunk_strategy,
      chunk_size: formData.chunk_size,
      chunk_overlap: formData.chunk_overlap,
      parent_child_enabled: formData.parent_child_enabled,
      parent_chunk_size: formData.parent_chunk_size,
      parent_chunk_overlap: formData.parent_chunk_overlap,
      child_chunk_size: formData.child_chunk_size,
      child_chunk_overlap: formData.child_chunk_overlap,
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
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border);
  color: var(--color-text-3);
  font-size: 12px;
  text-align: right;
}

.label-tip-icon {
  margin-left: 4px;
  color: var(--color-text-3);
  cursor: help;
}
</style>
