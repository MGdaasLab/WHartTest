<template>
  <a-modal
    :visible="props.visible"
    :title="isEditing ? '编辑 LLM 配置' : '新增 LLM 配置'"
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
        <!-- 第一行：配置名称 (全宽) -->
        <a-col :span="24">
          <a-form-item field="config_name" label="配置名称" required>
            <a-input v-model="formData.config_name" placeholder="例如: GPT-4 生产环境" />
          </a-form-item>
        </a-col>

        <!-- 第二行：供应商 + 模型名称 -->
        <a-col :span="8">
          <a-form-item field="provider" label="供应商" required>
            <a-select
              v-model="formData.provider"
              :options="providerOptions"
              placeholder="请选择供应商"
              allow-clear
              @change="handleProviderChange"
            />
          </a-form-item>
        </a-col>
        <a-col :span="16">
          <a-form-item field="name" label="模型名称" required>
            <div class="model-input-wrapper">
              <a-auto-complete
                v-model="formData.name"
                :data="modelOptions"
                :loading="loadingModels"
                placeholder="输入或选择模型名称 (如: gpt-4-turbo)"
                allow-clear
                :filter-option="filterModelOption"
                @focus="handleModelInputFocus"
                class="model-input"
              />
              <a-tooltip content="从 API 刷新模型列表">
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

        <!-- 第三行：API URL + API Key -->
        <a-col :span="12">
          <a-form-item field="api_url" label="API URL" required>
            <a-input v-model="formData.api_url" :placeholder="apiUrlPlaceholder" />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item field="api_key" label="API Key">
            <a-input-password
              v-model="formData.api_key"
              :placeholder="isEditing ? '留空不修改' : '请输入 API Key（可选）'"
            />
          </a-form-item>
        </a-col>

        <!-- 提示信息 + 测试按钮 -->
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
            测试连接
          </a-button>
        </a-col>

        <!-- 第四行：系统提示词 (全宽) -->
        <a-col :span="24">
          <a-form-item field="system_prompt" label="系统提示词">
            <a-textarea
              v-model="formData.system_prompt"
              placeholder="设置模型的默认 System Prompt（可选）"
              :auto-size="{ minRows: 1, maxRows: 6 }"
              :max-length="2000"
              show-word-limit
            />
          </a-form-item>
        </a-col>

        <!-- 第五行：上下文限制 + 基础开关 -->
        <a-col :span="6">
          <a-form-item field="context_limit" label="上下文限制">
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
          <a-form-item field="supports_vision" label="多模态">
            <a-space>
              <a-switch v-model="formData.supports_vision" />
              <span class="switch-desc">Vision</span>
            </a-space>
          </a-form-item>
        </a-col>
        <a-col :span="6">
          <a-form-item field="enable_streaming" label="流式输出">
            <a-space>
              <a-switch v-model="formData.enable_streaming" checked-color="#722ed1" />
              <span class="switch-desc">Stream</span>
            </a-space>
          </a-form-item>
        </a-col>
        <a-col :span="6">
          <a-form-item field="is_active" label="状态">
            <a-space>
              <a-switch v-model="formData.is_active" checked-color="#00b42a" />
              <span class="switch-desc">激活</span>
            </a-space>
          </a-form-item>
        </a-col>

        <!-- 第六行：中间件配置 -->
        <a-col :span="8">
          <a-form-item field="enable_summarization" label="上下文摘要">
            <a-space>
              <a-switch v-model="formData.enable_summarization" checked-color="#165dff" />
              <span class="switch-desc">超限时自动压缩对话历史</span>
            </a-space>
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item field="enable_hitl" label="人工审批">
            <a-space>
              <a-switch v-model="formData.enable_hitl" checked-color="#f77234" />
              <span class="switch-desc">高风险操作需确认</span>
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
import { createLlmConfig, partialUpdateLlmConfig, testLlmConnection, fetchModels, getProviders } from '@/features/langgraph/services/llmConfigService';
import type { LlmConfig, CreateLlmConfigRequest, PartialUpdateLlmConfigRequest } from '@/features/langgraph/types/llmConfig';

interface Props {
  visible: boolean;
  configData?: LlmConfig | null; // 用于编辑时预填数据
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

const formRef = ref<FormInstance | null>(null);
const modelOptions = ref<string[]>([]);
const providerOptions = ref<Array<{ label: string; value: string }>>([
  { label: 'OpenAI 兼容', value: 'openai_compatible' },
  { label: 'Qwen/通义千问', value: 'qwen' },
]);
const loadingModels = ref(false);
const testingModel = ref(false);
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

// 编辑模式：考虑 props.configData 或自动保存后的 currentConfigId
const isEditing = computed(() => !!(props.configData?.id || currentConfigId.value));
// 获取当前配置ID（优先 props，其次是自动保存后的 currentConfigId）
const effectiveConfigId = computed(() => props.configData?.id || currentConfigId.value);

const formRules: Record<string, FieldRule[]> = {
  config_name: [{ required: true, message: '配置名称不能为空' }],
  provider: [{ required: true, message: '供应商不能为空' }],
  name: [{ required: true, message: '模型名称不能为空' }],
  api_url: [
    { required: true, message: 'API URL 不能为空' },
    { type: 'url', message: '请输入有效的 URL' },
  ],
};

const apiUrlPlaceholder = computed(() => (
  formData.value.provider === 'qwen'
    ? QWEN_DEFAULT_API_URL
    : 'https://api.openai.com/v1'
));

const apiHintText = computed(() => (
  formData.value.provider === 'qwen'
    ? 'Qwen 建议使用 DashScope 兼容地址（可自定义）'
    : 'OpenAI 兼容供应商请填写兼容 API 地址'
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
      providerOptions.value = response.data.choices.map((item) => ({
        label: item.label,
        value: item.value,
      }));
    }
  } catch (error) {
    console.warn('加载供应商列表失败，使用默认选项', error);
  }
};

const handleProviderChange = (provider?: string) => {
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
        // 编辑模式：填充表单，但不包括 API Key（除非用户想修改）
        formData.value = {
          config_name: props.configData.config_name,
          provider: props.configData.provider || 'openai_compatible',
          name: props.configData.name,
          api_url: props.configData.api_url,
          api_key: '', // 编辑时不显示旧 Key，留空表示不修改
          system_prompt: props.configData.system_prompt || '',
          supports_vision: props.configData.supports_vision || false,
          context_limit: props.configData.context_limit || 128000,
          enable_summarization: props.configData.enable_summarization ?? true,
          enable_hitl: props.configData.enable_hitl || false,
          enable_streaming: props.configData.enable_streaming ?? true,
          is_active: props.configData.is_active,
        };
      } else {
        // 新增模式：重置表单
        formData.value = { ...defaultFormData };
      }
      handleProviderChange(formData.value.provider);
      // 清除之前的校验状态
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
    // 校验失败
    Message.error('请检查表单输入！');
    return;
  }

  let submitData: CreateLlmConfigRequest | PartialUpdateLlmConfigRequest;

  if (isEditing.value && effectiveConfigId.value) {
    // 编辑模式（包括自动保存后的情况）
    const partialData: PartialUpdateLlmConfigRequest = {
      config_name: formData.value.config_name,
      provider: formData.value.provider,
      name: formData.value.name,
      api_url: formData.value.api_url,
      is_active: formData.value.is_active,
    };
    if (formData.value.api_key) { // 只有当用户输入了新的 API Key 时才包含它
      partialData.api_key = formData.value.api_key;
    }
    if (formData.value.system_prompt !== undefined) { // 包含系统提示词（可以为空字符串）
      partialData.system_prompt = formData.value.system_prompt;
    }
    if (formData.value.supports_vision !== undefined) { // 包含多模态支持
      partialData.supports_vision = formData.value.supports_vision;
    }
    if (formData.value.context_limit !== undefined) { // 包含上下文限制
      partialData.context_limit = formData.value.context_limit;
    }
    if (formData.value.enable_summarization !== undefined) { // 包含上下文摘要
      partialData.enable_summarization = formData.value.enable_summarization;
    }
    if (formData.value.enable_hitl !== undefined) { // 包含人工审批
      partialData.enable_hitl = formData.value.enable_hitl;
    }
    if (formData.value.enable_streaming !== undefined) { // 包含流式输出
      partialData.enable_streaming = formData.value.enable_streaming;
    }
    submitData = partialData;
    emit('submit', submitData, effectiveConfigId.value);
  } else {
    // 新增模式
    submitData = { ...formData.value };
    emit('submit', submitData);
  }
};

const handleCancel = () => {
  invalidateAsyncState();
  emit('cancel');
};

// 从后端 API 获取可用模型列表
const fetchAvailableModels = async () => {
  if (!formData.value.api_url) {
    Message.warning('请先填写 API URL');
    return;
  }

  const sessionId = modalSessionId.value;
  const requestId = ++modelRequestId.value;
  loadingModels.value = true;

  try {
    // 编辑模式时传递 configId，让后端从数据库获取 API Key
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
        Message.success(`成功获取 ${response.data.models.length} 个模型`);
      } else {
        Message.warning('未找到可用模型');
      }
    } else {
      Message.error(response.message || '获取模型列表失败');
      modelOptions.value = [];
    }
  } catch (error: any) {
    if (!isActiveModelRequest(sessionId, requestId)) {
      return;
    }
    console.error('获取模型列表失败:', error);
    Message.error('获取模型列表失败');
    modelOptions.value = [];
  } finally {
    if (isActiveModelRequest(sessionId, requestId)) {
      loadingModels.value = false;
    }
  }
};

// 测试 LLM 模型连接（后端发起测试）
const testLlmModel = async () => {
  if (!formRef.value) return;
  const validation = await formRef.value.validate();
  if (validation) {
    Message.error('请先完善表单必填项');
    return;
  }

  const sessionId = modalSessionId.value;
  const requestId = ++testRequestId.value;
  testingModel.value = true;
  try {
    let configId = props.configData?.id || currentConfigId.value;

    // 如果是新建且未保存，先保存
    if (!configId) {
      const createResp = await createLlmConfig(formData.value);
      if (!isActiveTestRequest(sessionId, requestId)) {
        return;
      }
      if (createResp.status !== 'success' || !createResp.data) {
        Message.error(createResp.message || '保存配置失败');
        return;
      }
      configId = createResp.data.id;
      currentConfigId.value = configId;
      Message.success('配置已自动保存');
      emit('auto-saved', false); // false 表示不关闭弹窗
    } else if (isEditing.value) {
      // 编辑模式：先保存更改
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
      const updateResp = await partialUpdateLlmConfig(configId, partialData);
      if (!isActiveTestRequest(sessionId, requestId)) {
        return;
      }
      if (updateResp.status !== 'success') {
        Message.error(updateResp.message || '保存配置失败');
        return;
      }
    }

    // 调用后端测试接口
    const testResp = await testLlmConnection(configId);
    if (!isActiveTestRequest(sessionId, requestId)) {
      return;
    }
    if (testResp.status === 'success') {
      Message.success(testResp.data?.message || '连接测试成功');
    } else {
      Message.error(testResp.message || '连接测试失败');
    }
  } catch (error: any) {
    if (!isActiveTestRequest(sessionId, requestId)) {
      return;
    }
    console.error('测试失败:', error);
    Message.error('测试失败: ' + (error.message || '未知错误'));
  } finally {
    if (isActiveTestRequest(sessionId, requestId)) {
      testingModel.value = false;
    }
  }
};

// 处理模型输入框聚焦
const handleModelInputFocus = () => {
  if (formData.value.api_url && modelOptions.value.length === 0) {
    fetchAvailableModels();
  }
};

// 自定义模型过滤，没输入时显示全部，输入时模糊匹配
const filterModelOption = (inputValue: string, option: { value: string }) => {
  if (!inputValue) {
    return true; // 没有输入时显示全部
  }
  return option.value.toLowerCase().includes(inputValue.toLowerCase());
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
