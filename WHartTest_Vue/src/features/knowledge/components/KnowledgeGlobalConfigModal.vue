<template>
  <a-modal
    :visible="visible"
    :title="text.modalTitle"
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
          {{ text.globalConfigTip }}
        </a-alert>

        <a-divider>{{ text.embeddingServiceConfig }}</a-divider>

        <a-row :gutter="16">
          <a-col :xs="24" :sm="12">
            <a-form-item :label="text.embeddingService" field="embedding_service">
              <a-select
                v-model="formData.embedding_service"
                :placeholder="text.selectEmbeddingService"
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
            <a-form-item :label="text.modelName" field="model_name">
              <!-- OrcaRouter embedding models come from the live catalog
                   filtered to the embedding capability, not free text. -->
              <OrcaRouterModelSelect
                v-if="formData.embedding_service === 'orcarouter'"
                v-model="formData.model_name"
                :options="orcaEmbeddingModelOptions"
                :loading="loadingOrcaEmbeddingModels"
                :placeholder="text.modelName"
                search-placeholder="Search models"
                loading-text="Loading…"
                empty-text="No embedding models"
                @open-change="handleOrcaEmbeddingDropdown"
              />
              <a-input
                v-else
                v-model="formData.model_name"
                placeholder="text-embedding-ada-002 / bge-m3"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item :label="text.apiBaseUrl" field="api_base_url">
          <a-input
            v-model="formData.api_base_url"
            placeholder="http://your-embedding-service.com/v1/embeddings"
          />
        </a-form-item>

        <a-row :gutter="16" align="end">
          <a-col :xs="24" :sm="16">
            <a-form-item :label="text.apiKey" field="api_key">
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
                {{ text.testConnection }}
              </a-button>
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider>{{ text.rerankerOptional }}</a-divider>

        <a-row :gutter="16">
          <a-col :xs="24" :sm="12">
            <a-form-item field="reranker_service">
              <template #label>
                {{ text.rerankerService }}
                <a-tooltip :content="text.rerankerServiceHint">
                  <icon-question-circle class="label-tip-icon" />
                </a-tooltip>
              </template>
              <a-select
                v-model="formData.reranker_service"
                :placeholder="text.selectRerankerService"
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
            <a-form-item :label="text.rerankerModel" field="reranker_model_name">
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
          :label="text.rerankerApiUrl"
          field="reranker_api_url"
        >
          <a-input
            v-model="formData.reranker_api_url"
            :placeholder="text.rerankerApiUrlPlaceholder"
          />
        </a-form-item>

        <a-row v-if="formData.reranker_service !== 'none'" :gutter="16" align="end">
          <a-col :xs="24" :sm="16">
            <a-form-item :label="text.rerankerApiKey" field="reranker_api_key">
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
                {{ text.test }}
              </a-button>
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider>{{ text.defaultChunkConfig }}</a-divider>

        <a-row :gutter="16">
          <a-col :xs="24" :sm="12">
            <a-form-item field="chunk_size">
              <template #label>
                {{ text.chunkSize }}
                <a-tooltip :content="text.chunkSizeHint">
                  <icon-question-circle class="label-tip-icon" />
                </a-tooltip>
              </template>
              <a-input-number
                v-model="formData.chunk_size"
                :placeholder="text.chunkSize"
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
                {{ text.chunkOverlap }}
                <a-tooltip :content="text.chunkOverlapHint">
                  <icon-question-circle class="label-tip-icon" />
                </a-tooltip>
              </template>
              <a-input-number
                v-model="formData.chunk_overlap"
                :placeholder="text.chunkOverlap"
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
            <span>{{ text.lastUpdatedBy }}{{ formData.updated_by_name }}</span>
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
import OrcaRouterModelSelect from '@/features/langgraph/components/OrcaRouterModelSelect.vue';
import { fetchOrcaRouterModels } from '@/features/langgraph/services/llmConfigService';
import { useAppI18n } from '@/composables/useAppI18n';
import { translateLegacyText, type AppLocale } from '@/i18n';

interface Props {
  visible: boolean;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  close: [];
  saved: [];
}>();
const { isEnglish } = useAppI18n();
const currentLocale = computed<AppLocale>(() => (isEnglish.value ? 'en-US' : 'zh-CN'));

const localizeBackendMessage = (message: unknown, fallback: string) => {
  if (typeof message !== 'string' || !message.trim()) {
    return fallback;
  }
  return translateLegacyText(message, currentLocale.value);
};

const text = computed(() => (
  isEnglish.value
    ? {
        modalTitle: 'Global knowledge config',
        globalConfigTip: 'Global config applies to all knowledge base vectors. New uploads use the updated config.',
        embeddingServiceConfig: 'Embedding service',
        embeddingService: 'Embedding service',
        selectEmbeddingService: 'Select embedding service',
        modelName: 'Model name',
        apiBaseUrl: 'API base URL',
        apiKey: 'API key',
        testConnection: 'Test connection',
        rerankerOptional: 'Reranker (optional)',
        rerankerService: 'Reranker service',
        rerankerServiceHint: 'Reranker re-ranks retrieval results to improve precision. It can be configured independently.',
        selectRerankerService: 'Select reranker service',
        rerankerModel: 'Reranker model',
        rerankerApiUrl: 'Reranker API URL',
        rerankerApiUrlPlaceholder: 'http://xinference:9997 (leave empty to reuse embedding URL)',
        rerankerApiKey: 'Reranker API key',
        test: 'Test',
        defaultChunkConfig: 'Default chunk settings',
        chunkSize: 'Chunk size',
        chunkSizeHint: 'Max characters per chunk. Recommended 1000-2000.',
        chunkOverlap: 'Chunk overlap',
        chunkOverlapHint: 'Overlapped chars between adjacent chunks. Recommended 10-20% of chunk size.',
        lastUpdatedBy: 'Last updated by: ',
        rerankerNone: 'Disabled',
        rerankerCustom: 'Custom API',
        validateEmbeddingService: 'Please select an embedding service',
        validateApiBaseUrl: 'Please enter API base URL',
        validateModelName: 'Please enter model name',
        validateChunkSizeRequired: 'Please enter chunk size',
        validateChunkSizeRange: 'Chunk size must be between 100 and 4000',
        validateChunkOverlapRequired: 'Please enter chunk overlap',
        validateChunkOverlapRange: 'Chunk overlap must be between 0 and 500',
        validateApiKeyRequired: 'Please enter API key',
        savedApiKeyHint: 'Saved. Re-enter to update',
        apiKeyHint: 'Required for OpenAI/Azure, optional for others',
        fetchConfigFailed: 'Failed to fetch config',
        embeddingConfigIncomplete: 'Please complete embedding configuration first',
        apiKeyRequiredForService: 'API key is required for this service',
        embeddingTestSuccess: 'Embedding test passed',
        testFailed: 'Test failed',
        connectFailed: 'Unable to connect to service',
        rerankerNotEnabled: 'Please enable reranker first',
        rerankerModelRequired: 'Please enter reranker model name',
        rerankerTestSuccess: 'Reranker test passed',
        rerankerTestFailed: 'Reranker test failed',
        rerankerConnectFailed: 'Unable to connect to reranker service',
        saveConfigSuccess: 'Configuration saved',
        saveConfigFailed: 'Failed to save configuration',
      }
    : {
        modalTitle: '知识库全局配置',
        globalConfigTip: '全局配置将应用于所有知识库向量生成，修改后新上传的文档将使用新配置。',
        embeddingServiceConfig: '嵌入服务配置',
        embeddingService: '嵌入服务',
        selectEmbeddingService: '请选择嵌入服务',
        modelName: '模型名称',
        apiBaseUrl: 'API基础URL',
        apiKey: 'API密钥',
        testConnection: '测试连接',
        rerankerOptional: 'Reranker 精排服务（可选）',
        rerankerService: 'Reranker 服务',
        rerankerServiceHint: 'Reranker用于对检索结果进行精排，可显著提升检索精度。可独立于嵌入服务配置。',
        selectRerankerService: '请选择Reranker服务',
        rerankerModel: 'Reranker 模型',
        rerankerApiUrl: 'Reranker API地址',
        rerankerApiUrlPlaceholder: 'http://xinference:9997（不填则使用嵌入服务地址）',
        rerankerApiKey: 'Reranker API密钥',
        test: '测试',
        defaultChunkConfig: '默认分块配置',
        chunkSize: '分块大小',
        chunkSizeHint: '每个文本块的最大字符数。建议值1000-2000，较小值提高检索精度，较大值保持上下文完整性。',
        chunkOverlap: '分块重叠',
        chunkOverlapHint: '相邻文本块之间的重叠字符数。建议为分块大小的10-20%，可避免跨块信息丢失。',
        lastUpdatedBy: '最后更新：',
        rerankerNone: '不启用',
        rerankerCustom: '自定义API',
        validateEmbeddingService: '请选择嵌入服务',
        validateApiBaseUrl: '请输入API基础URL',
        validateModelName: '请输入模型名称',
        validateChunkSizeRequired: '请输入分块大小',
        validateChunkSizeRange: '分块大小必须在100-4000之间',
        validateChunkOverlapRequired: '请输入分块重叠',
        validateChunkOverlapRange: '分块重叠必须在0-500之间',
        validateApiKeyRequired: '请输入API密钥',
        savedApiKeyHint: '已保存，如需修改请重新输入',
        apiKeyHint: 'OpenAI/Azure必填，其他服务可选',
        fetchConfigFailed: '获取配置失败',
        embeddingConfigIncomplete: '请先完成嵌入服务配置',
        apiKeyRequiredForService: '此服务需要API密钥',
        embeddingTestSuccess: '嵌入模型测试成功！服务运行正常',
        testFailed: '测试失败',
        connectFailed: '无法连接到服务',
        rerankerNotEnabled: '请先启用 Reranker 服务',
        rerankerModelRequired: '请输入 Reranker 模型名称',
        rerankerTestSuccess: 'Reranker 服务测试成功！',
        rerankerTestFailed: 'Reranker 测试失败',
        rerankerConnectFailed: '无法连接到 Reranker 服务',
        saveConfigSuccess: '配置保存成功',
        saveConfigFailed: '保存配置失败',
      }
));

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

// --- OrcaRouter embedding catalog ----------------------------------------
const orcaEmbeddingModels = ref<Array<{ id: string; name: string }>>([]);
const loadingOrcaEmbeddingModels = ref(false);
const orcaEmbeddingRequestId = ref(0);

const orcaEmbeddingModelOptions = computed(() =>
  orcaEmbeddingModels.value.map((model) => ({
    label: model.name && model.name !== model.id ? `${model.name} (${model.id})` : model.id,
    value: model.id,
  }))
);

/**
 * Load the embedding-capability catalog from the backend. The API key stays
 * server-side or in this admin form; it is never read back by the browser.
 */
const loadOrcaEmbeddingModels = async () => {
  const requestId = orcaEmbeddingRequestId.value + 1;
  orcaEmbeddingRequestId.value = requestId;
  loadingOrcaEmbeddingModels.value = true;
  try {
    const response = await fetchOrcaRouterModels({
      capability: 'embedding',
      apiBase: formData.api_base_url || undefined,
      apiKey: formData.api_key || undefined,
    });
    if (requestId !== orcaEmbeddingRequestId.value) {
      return;
    }
    orcaEmbeddingModels.value = response.status === 'success' && response.data
      ? (response.data.models || [])
      : [];
    const ids = orcaEmbeddingModels.value.map((model) => model.id);
    if (formData.model_name && !ids.includes(formData.model_name)) {
      formData.model_name = '';
    }
  } catch (error) {
    if (requestId === orcaEmbeddingRequestId.value) {
      orcaEmbeddingModels.value = [];
    }
  } finally {
    if (requestId === orcaEmbeddingRequestId.value) {
      loadingOrcaEmbeddingModels.value = false;
    }
  }
};

const handleOrcaEmbeddingDropdown = (visible: boolean) => {
  if (visible && orcaEmbeddingModels.value.length === 0 && !loadingOrcaEmbeddingModels.value) {
    void loadOrcaEmbeddingModels();
  }
};

// Reranker 服务选项
const rerankerServices = ref<RerankerServiceOption[]>([
  { value: 'none', label: text.value.rerankerNone },
  { value: 'xinference', label: 'Xinference' },
  { value: 'custom', label: text.value.rerankerCustom },
]);

watch(isEnglish, () => {
  rerankerServices.value = [
    { value: 'none', label: text.value.rerankerNone },
    { value: 'xinference', label: 'Xinference' },
    { value: 'custom', label: text.value.rerankerCustom },
  ];
});

// 动态表单验证规则
const rules = computed(() => {
  const baseRules: any = {
    embedding_service: [
      { required: true, message: text.value.validateEmbeddingService },
    ],
    api_base_url: [
      { required: true, message: text.value.validateApiBaseUrl },
    ],
    model_name: [
      { required: true, message: text.value.validateModelName },
    ],
    chunk_size: [
      { required: true, message: text.value.validateChunkSizeRequired },
      { type: 'number', min: 100, max: 4000, message: text.value.validateChunkSizeRange },
    ],
    chunk_overlap: [
      { required: true, message: text.value.validateChunkOverlapRequired },
      { type: 'number', min: 0, max: 500, message: text.value.validateChunkOverlapRange },
    ],
  };

  const requiredFields = getRequiredFieldsForEmbeddingService(formData.embedding_service || '');
  if (requiredFields.includes('api_key')) {
    baseRules.api_key = [{
      required: !hasSavedApiKey.value || apiKeyTouched.value,
      message: text.value.validateApiKeyRequired,
    }];
  }

  return baseRules;
});

const apiKeyPlaceholder = computed(() =>
  hasSavedApiKey.value ? text.value.savedApiKeyHint : text.value.apiKeyHint
);

const rerankerApiKeyPlaceholder = computed(() =>
  hasSavedRerankerApiKey.value ? text.value.savedApiKeyHint : text.value.apiKeyHint
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
    Message.error(text.value.fetchConfigFailed);
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
    case 'orcarouter':
      // CustomAPIEmbeddings posts to the stored URL, so the full endpoint is
      // kept here; the model list is then loaded from the live catalog.
      formData.api_base_url = 'https://api.orcarouter.ai/v1/embeddings';
      formData.model_name = '';
      void loadOrcaEmbeddingModels();
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
    Message.warning(text.value.embeddingConfigIncomplete);
    return;
  }
  
  const needsApiKey = formData.embedding_service === 'openai' || formData.embedding_service === 'azure_openai';
  const hasUsableApiKey = apiKeyTouched.value ? !!formData.api_key : hasSavedApiKey.value;
  if (needsApiKey && !hasUsableApiKey) {
    Message.warning(text.value.apiKeyRequiredForService);
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
      Message.success(localizeBackendMessage(result.message, text.value.embeddingTestSuccess));
    } else {
      Message.error(localizeBackendMessage(result.message, text.value.testFailed));
    }
  } catch (error: any) {
    Message.error(error?.message || text.value.connectFailed);
  } finally {
    testingConnection.value = false;
  }
};

// 测试 Reranker 服务连接
const testRerankerService = async () => {
  if (formData.reranker_service === 'none') {
    Message.warning(text.value.rerankerNotEnabled);
    return;
  }

  if (!formData.reranker_model_name) {
    Message.warning(text.value.rerankerModelRequired);
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
      Message.success(localizeBackendMessage(result.message, text.value.rerankerTestSuccess));
    } else {
      Message.error(localizeBackendMessage(result.message, text.value.rerankerTestFailed));
    }
  } catch (error: any) {
    Message.error(localizeBackendMessage(error?.message, text.value.rerankerConnectFailed));
  } finally {
    testingReranker.value = false;
  }
};

const formatDate = (dateStr?: string) => {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleString(isEnglish.value ? 'en-US' : 'zh-CN');
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

    Message.success(text.value.saveConfigSuccess);
    emit('saved');
    emit('close');
  } catch (error: any) {
    console.error('保存配置失败:', error);
    Message.error(error?.message || text.value.saveConfigFailed);
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
