<template>
  <a-modal
    :visible="props.visible"
    :title="isEditing ? text.editConfig : text.addConfig"
    @ok="handleSubmit"
    @cancel="handleCancel"
    :confirm-loading="formLoading"
    :mask-closable="false"
    width="700px"
  >
    <a-form
      ref="formRef"
      :model="formData"
      :rules="formRules"
      layout="vertical"
      @submit="handleSubmit"
    >
      <a-row :gutter="24">
        <a-col :span="24">
          <a-form-item field="config_name" :label="text.configName" required>
            <a-input
              v-model="formData.config_name"
              :placeholder="text.configNamePlaceholder"
            />
          </a-form-item>
        </a-col>

        <a-col :span="8">
          <a-form-item field="provider" :label="text.provider" required>
            <a-select
              v-model="formData.provider"
              :options="providerOptions"
              :placeholder="text.providerPlaceholder"
              allow-clear
              @change="handleProviderChange"
            />
          </a-form-item>
        </a-col>
        <a-col :span="16">
          <a-form-item field="name" :label="text.modelName" required>
            <div class="model-input-wrapper">
              <a-auto-complete
                v-model="formData.name"
                :data="modelOptions"
                :loading="loadingModels"
                :placeholder="text.modelNamePlaceholder"
                allow-clear
                :filter-option="filterModelOption"
                @focus="handleModelInputFocus"
                class="model-input"
              />
              <a-tooltip :content="text.refreshModelsTooltip">
                <a-button
                  type="secondary"
                  :loading="loadingModels"
                  @click="fetchAvailableModels"
                >
                  <template #icon><icon-refresh /></template>
                </a-button>
              </a-tooltip>
            </div>
          </a-form-item>
        </a-col>

        <a-col :span="12">
          <a-form-item field="api_url" label="API URL" required>
            <a-input v-model="formData.api_url" :placeholder="apiUrlPlaceholder" />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item field="api_key" label="API Key">
            <a-input-password
              v-model="formData.api_key"
              :placeholder="apiKeyPlaceholder"
            />
          </a-form-item>
        </a-col>

        <a-col :span="24" class="test-button-row">
          <span class="api-hint">{{ apiHintText }}</span>
          <a-button
            type="outline"
            status="success"
            size="small"
            :loading="testingModel"
            @click="testLlmModel"
          >
            <template #icon><icon-thunderbolt /></template>
            {{ text.testConnection }}
          </a-button>
        </a-col>

        <a-col :span="24">
          <a-form-item field="system_prompt" :label="text.systemPrompt">
            <a-textarea
              v-model="formData.system_prompt"
              :placeholder="text.systemPromptPlaceholder"
              :auto-size="{ minRows: 1, maxRows: 6 }"
              :max-length="2000"
              show-word-limit
            />
          </a-form-item>
        </a-col>

        <a-col :span="6">
          <a-form-item field="context_limit" :label="text.contextLimit">
            <a-input-number
              v-model="formData.context_limit"
              :min="1000"
              :max="2000000"
              :step="1000"
              placeholder="128000"
            />
          </a-form-item>
        </a-col>
        <a-col :span="6">
          <a-form-item field="supports_vision" :label="text.multimodal">
            <a-space>
              <a-switch v-model="formData.supports_vision" />
              <span class="switch-desc">{{ text.visionShort }}</span>
            </a-space>
          </a-form-item>
        </a-col>
        <a-col :span="6">
          <a-form-item field="enable_streaming" :label="text.streamingOutput">
            <a-space>
              <a-switch v-model="formData.enable_streaming" checked-color="#722ed1" />
              <span class="switch-desc">{{ text.streamingShort }}</span>
            </a-space>
          </a-form-item>
        </a-col>
        <a-col :span="6">
          <a-form-item field="is_active" :label="text.status">
            <a-space>
              <a-switch v-model="formData.is_active" checked-color="#00b42a" />
              <span class="switch-desc">{{ text.activeShort }}</span>
            </a-space>
          </a-form-item>
        </a-col>

        <a-col :span="8">
          <a-form-item field="enable_summarization" :label="text.contextSummary">
            <a-space>
              <a-switch v-model="formData.enable_summarization" checked-color="#165dff" />
              <span class="switch-desc">{{ text.autoCompressHistory }}</span>
            </a-space>
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item field="enable_hitl" :label="text.humanApproval">
            <a-space>
              <a-switch v-model="formData.enable_hitl" checked-color="#f77234" />
              <span class="switch-desc">{{ text.highRiskConfirm }}</span>
            </a-space>
          </a-form-item>
        </a-col>
      </a-row>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch, computed, nextTick } from 'vue';
import {
  Modal as AModal,
  Form as AForm,
  FormItem as AFormItem,
  Input as AInput,
  InputPassword as AInputPassword,
  InputNumber as AInputNumber,
  Textarea as ATextarea,
  Switch as ASwitch,
  AutoComplete as AAutoComplete,
  Select as ASelect,
  Button as AButton,
  Row as ARow,
  Col as ACol,
  Space as ASpace,
  Tooltip as ATooltip,
  Message,
  type FormInstance,
  type FieldRule,
} from '@arco-design/web-vue';
import { IconRefresh, IconThunderbolt } from '@arco-design/web-vue/es/icon';
import { useAppI18n } from '@/composables/useAppI18n';
import {
  createLlmConfig,
  partialUpdateLlmConfig,
  testLlmConnection,
  fetchModels,
  getProviders,
} from '@/features/langgraph/services/llmConfigService';
import type {
  LlmConfig,
  CreateLlmConfigRequest,
  PartialUpdateLlmConfigRequest,
} from '@/features/langgraph/types/llmConfig';

interface Props {
  visible: boolean;
  configData?: LlmConfig | null;
  formLoading?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  configData: null,
  formLoading: false,
});

const emit = defineEmits<{
  (e: 'submit', data: CreateLlmConfigRequest | PartialUpdateLlmConfigRequest, id?: number): void;
  (e: 'cancel'): void;
  (e: 'auto-saved', closeModal?: boolean): void;
}>();
const { isEnglish, tl } = useAppI18n();

const text = computed(() => (
  isEnglish.value
    ? {
        addConfig: 'New LLM Config',
        editConfig: 'Edit LLM Config',
        configName: 'Config Name',
        configNamePlaceholder: 'Example: GPT-4 production environment',
        provider: 'Provider',
        providerPlaceholder: 'Please select a provider',
        modelName: 'Model Name',
        modelNamePlaceholder: 'Type or select a model name, e.g. gpt-4-turbo',
        refreshModelsTooltip: 'Refresh model list from API',
        apiKeyKeepExisting: 'Leave blank to keep current value',
        apiKeyOptional: 'Enter API Key (optional)',
        qwenApiHint: 'Qwen is recommended with a DashScope-compatible endpoint (customizable)',
        openaiApiHint: 'For OpenAI-compatible providers, fill in a compatible API endpoint',
        testConnection: 'Test Connection',
        systemPrompt: 'System Prompt',
        systemPromptPlaceholder: 'Set the default system prompt for the model (optional)',
        contextLimit: 'Context Limit',
        multimodal: 'Multimodal',
        visionShort: 'Vision',
        streamingOutput: 'Streaming',
        streamingShort: 'Stream',
        status: 'Status',
        activeShort: 'Active',
        contextSummary: 'Context Summary',
        autoCompressHistory: 'Auto-compress long chat history',
        humanApproval: 'Human Approval',
        highRiskConfirm: 'Require confirmation for risky actions',
        configNameRequired: 'Config name is required',
        providerRequired: 'Provider is required',
        modelNameRequired: 'Model name is required',
        apiUrlRequired: 'API URL is required',
        apiUrlInvalid: 'Please enter a valid URL',
        checkForm: 'Please check the form input',
        fillApiUrlFirst: 'Please fill in the API URL first',
        fetchModelsSuccess: (count: number) => `Fetched ${count} model(s) successfully`,
        noAvailableModels: 'No available models found',
        fetchModelsFailed: 'Failed to fetch model list',
        completeRequiredFields: 'Please complete the required fields first',
        saveConfigFailed: 'Failed to save config',
        configAutoSaved: 'Config auto-saved',
        connectionTestSuccess: 'Connection test succeeded',
        connectionTestFailed: 'Connection test failed',
        testFailedWithReason: (reason: string) => `Test failed: ${reason}`,
        unknownError: 'Unknown error',
        providerOpenAICompatible: 'OpenAI Compatible',
        providerDeepSeek: 'DeepSeek',
        providerQwen: 'Qwen',
        deepseekApiHint: 'DeepSeek is recommended with the official /v1 endpoint and the dedicated DeepSeek provider',
      }
    : {
        addConfig: '新增 LLM 配置',
        editConfig: '编辑 LLM 配置',
        configName: '配置名称',
        configNamePlaceholder: '例如: GPT-4 生产环境',
        provider: '供应商',
        providerPlaceholder: '请选择供应商',
        modelName: '模型名称',
        modelNamePlaceholder: '输入或选择模型名称 (如: gpt-4-turbo)',
        refreshModelsTooltip: '从 API 刷新模型列表',
        apiKeyKeepExisting: '留空不修改',
        apiKeyOptional: '请输入 API Key（可选）',
        qwenApiHint: 'Qwen 建议使用 DashScope 兼容地址（可自定义）',
        openaiApiHint: 'OpenAI 兼容供应商请填写兼容 API 地址',
        testConnection: '测试连接',
        systemPrompt: '系统提示词',
        systemPromptPlaceholder: '设置模型的默认 System Prompt（可选）',
        contextLimit: '上下文限制',
        multimodal: '多模态',
        visionShort: 'Vision',
        streamingOutput: '流式输出',
        streamingShort: 'Stream',
        status: '状态',
        activeShort: '激活',
        contextSummary: '上下文摘要',
        autoCompressHistory: '超限时自动压缩对话历史',
        humanApproval: '人工审批',
        highRiskConfirm: '高风险操作需确认',
        configNameRequired: '配置名称不能为空',
        providerRequired: '供应商不能为空',
        modelNameRequired: '模型名称不能为空',
        apiUrlRequired: 'API URL 不能为空',
        apiUrlInvalid: '请输入有效的 URL',
        checkForm: '请检查表单输入',
        fillApiUrlFirst: '请先填写 API URL',
        fetchModelsSuccess: (count: number) => `成功获取 ${count} 个模型`,
        noAvailableModels: '未找到可用模型',
        fetchModelsFailed: '获取模型列表失败',
        completeRequiredFields: '请先完善表单必填项',
        saveConfigFailed: '保存配置失败',
        configAutoSaved: '配置已自动保存',
        connectionTestSuccess: '连接测试成功',
        connectionTestFailed: '连接测试失败',
        testFailedWithReason: (reason: string) => `测试失败: ${reason}`,
        unknownError: '未知错误',
        providerOpenAICompatible: 'OpenAI 兼容',
        providerDeepSeek: 'DeepSeek',
        providerQwen: 'Qwen/通义千问',
        deepseekApiHint: 'DeepSeek 建议使用官方 /v1 地址，并选择专用 DeepSeek 供应商',
      }
));

const localizeProviderLabel = (value: string, fallback?: string) => {
  if (value === 'openai_compatible') {
    return text.value.providerOpenAICompatible;
  }
  if (value === 'deepseek') {
    return text.value.providerDeepSeek;
  }
  if (value === 'qwen') {
    return text.value.providerQwen;
  }
  return fallback || value;
};

const formRef = ref<FormInstance | null>(null);
const modelOptions = ref<string[]>([]);
const providerChoices = ref<Array<{ label: string; value: string }>>([
  { label: 'openai_compatible', value: 'openai_compatible' },
  { label: 'deepseek', value: 'deepseek' },
  { label: 'qwen', value: 'qwen' },
]);
const providerOptions = computed(() => providerChoices.value.map((item) => ({
  label: localizeProviderLabel(item.value, item.label),
  value: item.value,
})));
const loadingModels = ref(false);
const testingModel = ref(false);
const DEEPSEEK_DEFAULT_API_URL = 'https://api.deepseek.com/v1';
const QWEN_DEFAULT_API_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1';
const defaultFormData: CreateLlmConfigRequest = {
  config_name: '',
  provider: 'openai_compatible',
  name: '',
  api_url: '',
  api_key: '',
  system_prompt: '',
  supports_vision: false,
  context_limit: 128000,
  enable_summarization: true,
  enable_hitl: false,
  enable_streaming: true,
  is_active: false,
};
const formData = ref<CreateLlmConfigRequest>({ ...defaultFormData });
const currentConfigId = ref<number | null>(null);
const modalSessionId = ref(0);
const modelRequestId = ref(0);
const testRequestId = ref(0);

const isEditing = computed(() => !!(props.configData?.id || currentConfigId.value));
const effectiveConfigId = computed(() => props.configData?.id || currentConfigId.value);
const formRules = computed<Record<string, FieldRule[]>>(() => ({
  config_name: [{ required: true, message: text.value.configNameRequired }],
  provider: [{ required: true, message: text.value.providerRequired }],
  name: [{ required: true, message: text.value.modelNameRequired }],
  api_url: [
    { required: true, message: text.value.apiUrlRequired },
    { type: 'url', message: text.value.apiUrlInvalid },
  ],
}));

const apiUrlPlaceholder = computed(() => (
  formData.value.provider === 'deepseek'
    ? DEEPSEEK_DEFAULT_API_URL
    : formData.value.provider === 'qwen'
      ? QWEN_DEFAULT_API_URL
      : 'https://api.openai.com/v1'
));

const apiKeyPlaceholder = computed(() => (
  isEditing.value ? text.value.apiKeyKeepExisting : text.value.apiKeyOptional
));

const apiHintText = computed(() => (
  formData.value.provider === 'deepseek'
    ? text.value.deepseekApiHint
    : formData.value.provider === 'qwen'
      ? text.value.qwenApiHint
      : text.value.openaiApiHint
));

const invalidateAsyncState = () => {
  modalSessionId.value += 1;
  modelRequestId.value += 1;
  testRequestId.value += 1;
  loadingModels.value = false;
  testingModel.value = false;
};

const isActiveModelRequest = (sessionId: number, requestId: number) => (
  props.visible
  && modalSessionId.value === sessionId
  && modelRequestId.value === requestId
);

const isActiveTestRequest = (sessionId: number, requestId: number) => (
  props.visible
  && modalSessionId.value === sessionId
  && testRequestId.value === requestId
);

const loadProviderOptions = async () => {
  try {
    const response = await getProviders();
    if (response.status === 'success' && response.data?.choices?.length) {
      providerChoices.value = response.data.choices.map((item) => ({
        label: item.label,
        value: item.value,
      }));
    }
  } catch (error) {
    console.warn('Failed to load provider list, using defaults', error);
  }
};

const handleProviderChange = (provider?: string) => {
  if (provider === 'deepseek' && !formData.value.api_url) {
    formData.value.api_url = DEEPSEEK_DEFAULT_API_URL;
  }
  if (provider === 'qwen' && !formData.value.api_url) {
    formData.value.api_url = QWEN_DEFAULT_API_URL;
  }
};

watch(
  () => props.visible,
  (newVal) => {
    invalidateAsyncState();
    modelOptions.value = [];

    if (newVal) {
      currentConfigId.value = null;
      void loadProviderOptions();
      if (props.configData && props.configData.id) {
        formData.value = {
          config_name: props.configData.config_name,
          provider: props.configData.provider || 'openai_compatible',
          name: props.configData.name,
          api_url: props.configData.api_url,
          api_key: '',
          system_prompt: props.configData.system_prompt || '',
          supports_vision: props.configData.supports_vision || false,
          context_limit: props.configData.context_limit || 128000,
          enable_summarization: props.configData.enable_summarization ?? true,
          enable_hitl: props.configData.enable_hitl || false,
          enable_streaming: props.configData.enable_streaming ?? true,
          is_active: props.configData.is_active,
        };
      } else {
        formData.value = { ...defaultFormData };
      }
      handleProviderChange(formData.value.provider);
      nextTick(() => {
        formRef.value?.clearValidate();
      });
    }
  }
);

const handleSubmit = async () => {
  if (!formRef.value) return;
  const validation = await formRef.value.validate();
  if (validation) {
    Message.error(text.value.checkForm);
    return;
  }

  let submitData: CreateLlmConfigRequest | PartialUpdateLlmConfigRequest;

  if (isEditing.value && effectiveConfigId.value) {
    const partialData: PartialUpdateLlmConfigRequest = {
      config_name: formData.value.config_name,
      provider: formData.value.provider,
      name: formData.value.name,
      api_url: formData.value.api_url,
      is_active: formData.value.is_active,
    };
    if (formData.value.api_key) {
      partialData.api_key = formData.value.api_key;
    }
    if (formData.value.system_prompt !== undefined) {
      partialData.system_prompt = formData.value.system_prompt;
    }
    if (formData.value.supports_vision !== undefined) {
      partialData.supports_vision = formData.value.supports_vision;
    }
    if (formData.value.context_limit !== undefined) {
      partialData.context_limit = formData.value.context_limit;
    }
    if (formData.value.enable_summarization !== undefined) {
      partialData.enable_summarization = formData.value.enable_summarization;
    }
    if (formData.value.enable_hitl !== undefined) {
      partialData.enable_hitl = formData.value.enable_hitl;
    }
    if (formData.value.enable_streaming !== undefined) {
      partialData.enable_streaming = formData.value.enable_streaming;
    }
    submitData = partialData;
    emit('submit', submitData, effectiveConfigId.value);
  } else {
    submitData = { ...formData.value };
    emit('submit', submitData);
  }
};

const handleCancel = () => {
  invalidateAsyncState();
  emit('cancel');
};

const normalizeModelOptionText = (option: unknown): string => {
  if (typeof option === 'string') {
    return option;
  }
  if (typeof option === 'number' || typeof option === 'boolean') {
    return String(option);
  }
  if (option && typeof option === 'object') {
    const record = option as { label?: unknown; value?: unknown };
    if (typeof record.label === 'string') {
      return record.label;
    }
    if (typeof record.value === 'string') {
      return record.value;
    }
    if (typeof record.value === 'number' || typeof record.value === 'boolean') {
      return String(record.value);
    }
  }
  return '';
};

const filterModelOption = (inputValue: string, option: unknown) => {
  if (!inputValue) {
    return true;
  }
  return normalizeModelOptionText(option).toLowerCase().includes(inputValue.toLowerCase());
};

const fetchAvailableModels = async () => {
  if (!formData.value.api_url) {
    Message.warning(text.value.fillApiUrlFirst);
    return;
  }

  const sessionId = modalSessionId.value;
  const requestId = ++modelRequestId.value;
  loadingModels.value = true;

  try {
    const configId = props.configData?.id;
    const response = await fetchModels(
      formData.value.api_url,
      formData.value.api_key || undefined,
      configId
    );

    if (!isActiveModelRequest(sessionId, requestId)) {
      return;
    }

    if (response.status === 'success' && response.data?.models) {
      modelOptions.value = response.data.models;
      if (response.data.models.length > 0) {
        Message.success(text.value.fetchModelsSuccess(response.data.models.length));
      } else {
        Message.warning(text.value.noAvailableModels);
      }
    } else {
      Message.error(response.message || text.value.fetchModelsFailed);
      modelOptions.value = [];
    }
  } catch (error) {
    if (!isActiveModelRequest(sessionId, requestId)) {
      return;
    }
    console.error('Failed to fetch model list:', error);
    Message.error(text.value.fetchModelsFailed);
    modelOptions.value = [];
  } finally {
    if (isActiveModelRequest(sessionId, requestId)) {
      loadingModels.value = false;
    }
  }
};

const testLlmModel = async () => {
  if (!formRef.value) return;
  const validation = await formRef.value.validate();
  if (validation) {
    Message.error(text.value.completeRequiredFields);
    return;
  }

  const sessionId = modalSessionId.value;
  const requestId = ++testRequestId.value;
  testingModel.value = true;

  try {
    let configId = props.configData?.id || currentConfigId.value;

    if (!configId) {
      const createResp = await createLlmConfig(formData.value);
      if (!isActiveTestRequest(sessionId, requestId)) {
        return;
      }
      if (createResp.status !== 'success' || !createResp.data) {
        Message.error(createResp.message || text.value.saveConfigFailed);
        return;
      }
      configId = createResp.data.id;
      currentConfigId.value = configId;
      Message.success(text.value.configAutoSaved);
      emit('auto-saved', false);
    } else if (isEditing.value) {
      const partialData: PartialUpdateLlmConfigRequest = {
        config_name: formData.value.config_name,
        provider: formData.value.provider,
        name: formData.value.name,
        api_url: formData.value.api_url,
        is_active: formData.value.is_active,
      };
      if (formData.value.api_key) partialData.api_key = formData.value.api_key;
      if (formData.value.system_prompt !== undefined) partialData.system_prompt = formData.value.system_prompt;
      if (formData.value.supports_vision !== undefined) partialData.supports_vision = formData.value.supports_vision;
      if (formData.value.context_limit !== undefined) partialData.context_limit = formData.value.context_limit;
      if (formData.value.enable_summarization !== undefined) partialData.enable_summarization = formData.value.enable_summarization;
      if (formData.value.enable_hitl !== undefined) partialData.enable_hitl = formData.value.enable_hitl;
      if (formData.value.enable_streaming !== undefined) partialData.enable_streaming = formData.value.enable_streaming;

      const updateResp = await partialUpdateLlmConfig(configId, partialData);
      if (!isActiveTestRequest(sessionId, requestId)) {
        return;
      }
      if (updateResp.status !== 'success') {
        Message.error(updateResp.message || text.value.saveConfigFailed);
        return;
      }
    }

    const testResp = await testLlmConnection(configId);
    if (!isActiveTestRequest(sessionId, requestId)) {
      return;
    }
    if (testResp.status === 'success') {
      Message.success(testResp.data?.message || text.value.connectionTestSuccess);
    } else {
      Message.error(testResp.message || text.value.connectionTestFailed);
    }
  } catch (error: any) {
    if (!isActiveTestRequest(sessionId, requestId)) {
      return;
    }
    console.error('Test failed:', error);
    Message.error(text.value.testFailedWithReason(error.message || text.value.unknownError));
  } finally {
    if (isActiveTestRequest(sessionId, requestId)) {
      testingModel.value = false;
    }
  }
};

const handleModelInputFocus = () => {
  if (formData.value.api_url && modelOptions.value.length === 0) {
    void fetchAvailableModels();
  }
};
</script>

<style scoped>
.model-input-wrapper {
  display: flex;
  width: 100%;
  gap: 8px;
  align-items: center;
}

.model-input {
  flex: 1;
}

.test-button-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  margin-top: -8px;
}

.api-hint {
  font-size: 12px;
  color: var(--color-text-3);
}

.switch-desc {
  font-size: 13px;
  color: var(--color-text-3);
  cursor: pointer;
}
</style>
