<template>
  <a-modal
    :visible="props.visible"
    :title="isEditing ? '编辑 LLM 配置' : '新增 LLM 配置'"
    @ok="handleSubmit"
    @cancel="handleCancel"
    :confirm-loading="formLoading"
    :mask-closable="false"
    width="600px"
  >
    <a-form
      ref="formRef"
      :model="formData"
      :rules="formRules"
      layout="vertical"
      @submit="handleSubmit"
    >
      <a-form-item field="config_name" label="配置名称" required>
        <a-input v-model="formData.config_name" placeholder="请输入配置名称" />
      </a-form-item>
      <a-form-item field="provider" label="供应商" required>
        <a-select 
          v-model="formData.provider" 
          placeholder="请选择供应商"
          :loading="loadingProviders"
        >
          <a-option 
            v-for="option in providerOptions" 
            :key="option.value" 
            :value="option.value"
          >
            {{ option.label }}
          </a-option>
        </a-select>
      </a-form-item>
      <a-form-item field="name" label="模型名称" required>
        <a-input v-model="formData.name" placeholder="请输入模型名称" />
      </a-form-item>
      <a-form-item field="api_url" label="API URL" required>
        <a-input v-model="formData.api_url" placeholder="请输入 API URL" />
      </a-form-item>
      <a-form-item field="api_key" label="API Key" :required="!isEditing">
        <a-input-password
          v-model="formData.api_key"
          :placeholder="isEditing ? '如需修改请输入新的 API Key' : '请输入 API Key'"
        />
        <template #extra v-if="isEditing">
          <div class="text-xs text-gray-500">留空表示不修改 API Key。</div>
        </template>
      </a-form-item>
      <a-form-item field="system_prompt" label="系统提示词">
        <a-textarea
          v-model="formData.system_prompt"
          placeholder="请输入系统提示词（可选）"
          :rows="4"
          :max-length="2000"
          show-word-limit
        />
        <template #extra>
          <div class="text-xs text-gray-500">用于指导AI助手的行为和回答风格。</div>
        </template>
      </a-form-item>
      <a-form-item field="is_active" label="激活状态">
        <a-switch v-model="formData.is_active" />
        <template #extra>
          <div class="text-xs text-gray-500">如果设为 true，其他已激活的配置会自动设为 false。</div>
        </template>
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch, computed, nextTick, onMounted } from 'vue';
import {
  Modal as AModal,
  Form as AForm,
  FormItem as AFormItem,
  Input as AInput,
  InputPassword as AInputPassword,
  Textarea as ATextarea,
  Switch as ASwitch,
  Select as ASelect,
  Option as AOption,
  Message,
  type FormInstance,
  type FieldRule,
} from '@arco-design/web-vue';
import type { LlmConfig, CreateLlmConfigRequest, PartialUpdateLlmConfigRequest } from '@/features/langgraph/types/llmConfig';
import { getProviders, type ProviderOption } from '@/features/langgraph/services/llmConfigService';

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
}>();

const formRef = ref<FormInstance | null>(null);
const providerOptions = ref<ProviderOption[]>([]);
const loadingProviders = ref(false);
const defaultFormData: CreateLlmConfigRequest = {
  config_name: '',
  provider: '',
  name: '',
  api_url: '',
  api_key: '',
  system_prompt: '',
  is_active: false,
};
const formData = ref<CreateLlmConfigRequest>({ ...defaultFormData });

const isEditing = computed(() => !!props.configData?.id);

const formRules: Record<string, FieldRule[]> = {
  config_name: [{ required: true, message: '配置名称不能为空' }],
  provider: [{ required: true, message: '供应商不能为空' }],
  name: [{ required: true, message: '模型名称不能为空' }],
  api_url: [
    { required: true, message: 'API URL 不能为空' },
    { type: 'url', message: '请输入有效的 URL' },
  ],
  api_key: [
    // API Key 在创建时必填，编辑时可选
    {
      required: !isEditing.value,
      message: 'API Key 不能为空',
      validator: (value, cb) => {
        if (!isEditing.value && !value) {
          return cb('API Key 不能为空');
        }
        if (value && value.length < 10 && !isEditing.value) {
            // 仅在创建时或编辑时输入了新值才校验长度
            return cb('API key 必须至少 10 个字符长。');
        }
        if (isEditing.value && value && value.length > 0 && value.length < 10) {
             return cb('API key 必须至少 10 个字符长。');
        }
        return cb();
      }
    },
  ],
};


watch(
  () => props.visible,
  (newVal) => {
    if (newVal) {
      if (props.configData && props.configData.id) {
        // 编辑模式：填充表单，但不包括 API Key（除非用户想修改）
        formData.value = {
          config_name: props.configData.config_name,
          provider: props.configData.provider,
          name: props.configData.name,
          api_url: props.configData.api_url,
          api_key: '', // 编辑时不显示旧 Key，留空表示不修改
          system_prompt: props.configData.system_prompt || '', // 填充系统提示词
          is_active: props.configData.is_active,
        };
      } else {
        // 新增模式：重置表单
        formData.value = { ...defaultFormData };
      }
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

  if (isEditing.value && props.configData?.id) {
    // 编辑模式
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
    submitData = partialData;
    emit('submit', submitData, props.configData.id);
  } else {
    // 新增模式
    submitData = { ...formData.value };
     if (!submitData.api_key) { // 防御性检查，理论上表单校验会阻止
        Message.error('API Key 不能为空');
        return;
    }
    emit('submit', submitData);
  }
};

const handleCancel = () => {
  emit('cancel');
};

const loadProviders = async () => {
  loadingProviders.value = true;
  try {
    const response = await getProviders();
    if (response.status === 'success' && response.data) {
      providerOptions.value = response.data.choices;
    }
  } catch (error) {
    console.error('Failed to load providers:', error);
  } finally {
    loadingProviders.value = false;
  }
};

onMounted(() => {
  loadProviders();
});
</script>

<style scoped>
/* 可以在这里添加特定于此组件的样式 */
</style>