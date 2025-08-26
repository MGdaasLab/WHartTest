<template>
  <a-modal
    :visible="visible"
    :title="isEdit ? '编辑知识库' : '新建知识库'"
    :width="700"
    @ok="handleSubmit"
    @cancel="handleCancel"
    :confirm-loading="loading"
  >
    <a-tabs v-model:active-key="activeTab" type="line" :lazy-load="false">
      <!-- 基础信息页签 -->
      <a-tab-pane key="basic" title="基础信息">
        <a-form
          ref="formRef"
          :model="formData"
          :rules="rules"
          layout="vertical"
        >
          <a-form-item label="知识库名称" field="name">
            <a-input
              v-model="formData.name"
              placeholder="请输入知识库名称"
              :max-length="100"
            />
          </a-form-item>

          <a-form-item label="描述" field="description">
            <a-textarea
              v-model="formData.description"
              placeholder="请输入知识库描述（可选）"
              :rows="3"
              :max-length="500"
            />
          </a-form-item>

          <a-form-item label="所属项目" field="project">
            <a-select
              v-model="formData.project"
              placeholder="请选择所属项目"
              :loading="projectStore.loading"
              :disabled="isEdit"
            >
              <a-option
                v-for="project in projects"
                :key="project.value"
                :value="project.value"
                :label="project.label"
              />
            </a-select>
          </a-form-item>

          <a-form-item v-if="!isEdit" label="状态" field="is_active">
            <a-switch
              v-model="formData.is_active"
              checked-text="启用"
              unchecked-text="禁用"
            />
          </a-form-item>
        </a-form>
      </a-tab-pane>

      <!-- 高级配置页签 -->
      <a-tab-pane key="advanced" title="高级配置">
        <a-form
          ref="advancedFormRef"
          :model="formData"
          :rules="rules"
          layout="vertical"
        >
          <a-divider>嵌入服务配置</a-divider>

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

          <a-form-item label="API基础URL" field="api_base_url">
            <a-input
              v-model="formData.api_base_url"
              placeholder="请输入API基础URL"
            />
          </a-form-item>

          <a-form-item label="API密钥" field="api_key">
            <a-input-password
              v-model="formData.api_key"
              placeholder="请输入API密钥（可选）"
            />
            <div class="form-item-tip">
              OpenAI和Azure OpenAI必填，Ollama和自定义可选
            </div>
          </a-form-item>

          <a-form-item label="模型名称" field="model_name">
            <a-input
              v-model="formData.model_name"
              placeholder="请输入模型名称"
            />
            <div class="form-item-tip">
              示例: OpenAI: text-embedding-ada-002 | Ollama: nomic-embed-text | 自定义: bge-m3
            </div>
          </a-form-item>

          <a-form-item>
            <a-button 
              @click="testEmbeddingService"
              :loading="testingConnection"
              type="outline"
            >
              <template #icon><icon-refresh /></template>
              测试连接
            </a-button>
          </a-form-item>

          <a-divider>分块配置</a-divider>
          
          <a-row :gutter="16">
            <a-col :span="12">
              <a-form-item label="分块大小" field="chunk_size">
                <a-input-number
                  v-model="formData.chunk_size"
                  placeholder="分块大小"
                  :min="100"
                  :max="4000"
                  :step="100"
                  style="width: 100%"
                />
                <div class="form-item-tip">建议值：1000-2000，影响检索精度</div>
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="分块重叠" field="chunk_overlap">
                <a-input-number
                  v-model="formData.chunk_overlap"
                  placeholder="分块重叠"
                  :min="0"
                  :max="500"
                  :step="50"
                  style="width: 100%"
                />
                <div class="form-item-tip">建议值：100-200，避免信息丢失</div>
              </a-form-item>
            </a-col>
          </a-row>
        </a-form>
      </a-tab-pane>
    </a-tabs>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue';
import { Message } from '@arco-design/web-vue';
import { IconRefresh } from '@arco-design/web-vue/es/icon';
import { useProjectStore } from '@/store/projectStore';
import { KnowledgeService } from '../services/knowledgeService';
import type {
  KnowledgeBase,
  CreateKnowledgeBaseRequest,
  UpdateKnowledgeBaseRequest,
  EmbeddingServiceType,
  EmbeddingServiceOption
} from '../types/knowledge';
import {
  getRequiredFieldsForEmbeddingService
} from '../types/knowledge';

interface Props {
  visible: boolean;
  knowledgeBase?: KnowledgeBase | null;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  submit: [];
  cancel: [];
}>();

const projectStore = useProjectStore();
const formRef = ref();
const advancedFormRef = ref();
const loading = ref(false);
const activeTab = ref('basic');

// 计算属性
const isEdit = computed(() => !!props.knowledgeBase);

// 表单数据
const formData = reactive<CreateKnowledgeBaseRequest>({
  name: '',
  description: '',
  project: 0,
  embedding_service: 'openai',
  api_base_url: 'https://api.openai.com/v1',
  api_key: '',
  model_name: 'text-embedding-ada-002',
  chunk_size: 1000,
  chunk_overlap: 200,
  is_active: true,
});

// 嵌入服务选项
const embeddingServices = ref<EmbeddingServiceOption[]>([]);
const embeddingServicesLoading = ref(false);
const testingConnection = ref(false);

// 项目列表
const projects = computed(() => projectStore.projectOptions);

// 获取嵌入服务选项
const fetchEmbeddingServices = async () => {
  embeddingServicesLoading.value = true;
  try {
    const response = await KnowledgeService.getEmbeddingServices();
    embeddingServices.value = response.services;
    
    // 如果当前选择的服务不在新的服务列表中，设置为第一个可用的服务
    if (embeddingServices.value.length > 0 &&
        !embeddingServices.value.some(s => s.value === formData.embedding_service)) {
      formData.embedding_service = embeddingServices.value[0].value as EmbeddingServiceType;
    }
  } catch (error) {
    console.error('获取嵌入服务选项失败:', error);
    Message.error('获取嵌入服务选项失败');
  } finally {
    embeddingServicesLoading.value = false;
  }
};

// 动态表单验证规则
const rules = computed(() => {
  const baseRules: any = {
    name: [
      { required: true, message: '请输入知识库名称' },
      { minLength: 2, message: '知识库名称至少2个字符' },
      { maxLength: 200, message: '知识库名称不能超过200个字符' },
    ],
    project: [
      { required: true, message: '请选择所属项目' },
    ],
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

  // 根据选择的嵌入服务动态添加验证规则
  const requiredFields = getRequiredFieldsForEmbeddingService(formData.embedding_service || '');
  
  if (requiredFields.includes('api_key')) {
    baseRules.api_key = [
      { required: true, message: '请输入API密钥' },
    ];
  }

  return baseRules;
});

// 监听弹窗显示状态
watch(() => props.visible, async (visible) => {
  if (visible) {
    resetForm();

    // 确保项目列表已加载
    if (projects.value.length === 0) {
      await projectStore.fetchProjects();
    }

    // 获取嵌入服务选项
    await fetchEmbeddingServices();

    if (props.knowledgeBase) {
      // 编辑模式，填充表单数据
      Object.assign(formData, {
        name: props.knowledgeBase.name,
        description: props.knowledgeBase.description || '',
        project: typeof props.knowledgeBase.project === 'string' 
          ? Number(props.knowledgeBase.project) 
          : props.knowledgeBase.project,
        embedding_service: props.knowledgeBase.embedding_service,
        api_base_url: props.knowledgeBase.api_base_url || '',
        api_key: props.knowledgeBase.api_key || '',
        model_name: props.knowledgeBase.model_name,
        chunk_size: props.knowledgeBase.chunk_size,
        chunk_overlap: props.knowledgeBase.chunk_overlap,
      });
      
      // 确保项目ID被正确设置（可能需要等待项目列表加载）
      if (projects.value.length > 0) {
        const projectId = typeof props.knowledgeBase.project === 'string' 
          ? Number(props.knowledgeBase.project) 
          : props.knowledgeBase.project;
        const projectExists = projects.value.some(p => p.value === projectId);
        if (!projectExists) {
          console.warn('知识库所属项目不在当前项目列表中:', projectId);
        }
      }
    } else {
      // 新建模式，设置默认项目
      if (projectStore.currentProjectId) {
        formData.project = Number(projectStore.currentProjectId);
      }
    }
  }
});

// 监听项目列表变化，确保编辑模式下的项目回显
watch(
  () => projects.value,
  (newProjects) => {
    if (props.visible && props.knowledgeBase && newProjects.length > 0) {
      const correctProjectId = typeof props.knowledgeBase.project === 'string' 
        ? Number(props.knowledgeBase.project) 
        : props.knowledgeBase.project;
      
      // 如果当前formData中的project还是0（初始值），或与应该设置的值不同，重新设置
      if (formData.project === 0 || formData.project !== correctProjectId) {
        formData.project = correctProjectId;
      }
    }
  },
  { immediate: true }
);

// 方法
const resetForm = () => {
  Object.assign(formData, {
    name: '',
    description: '',
    project: 0,
    embedding_service: 'openai',
    api_base_url: 'https://api.openai.com/v1',
    api_key: '',
    model_name: 'text-embedding-ada-002',
    chunk_size: 1000,
    chunk_overlap: 200,
    is_active: true,
  });
  activeTab.value = 'basic'; // 重置到基础信息页签
  formRef.value?.clearValidate();
  advancedFormRef.value?.clearValidate();
};

// 处理嵌入服务变化
const handleEmbeddingServiceChange = (value: EmbeddingServiceType) => {
  // 根据服务类型设置默认配置
  switch (value) {
    case 'openai':
      formData.api_base_url = 'https://api.openai.com/v1';
      formData.model_name = 'text-embedding-ada-002';
      break;
    case 'azure_openai':
      formData.api_base_url = 'https://your-resource.openai.azure.com/';
      formData.model_name = 'text-embedding-ada-002';
      break;
    case 'ollama':
      formData.api_base_url = 'http://localhost:11434';
      formData.model_name = 'nomic-embed-text';
      formData.api_key = '';
      break;
    case 'custom':
      formData.api_base_url = 'http://your-embedding-service:8080';
      formData.model_name = 'bge-m3';
      break;
  }
};

// 测试嵌入服务连接
const testEmbeddingService = async () => {
  // 验证必要字段
  if (!formData.embedding_service) {
    Message.warning('请先选择嵌入服务');
    return;
  }
  if (!formData.api_base_url) {
    Message.warning('请先输入API基础URL');
    return;
  }
  if (!formData.model_name) {
    Message.warning('请先输入模型名称');
    return;
  }
  
  // 检查是否需要API密钥
  const needsApiKey = formData.embedding_service === 'openai' || formData.embedding_service === 'azure_openai';
  if (needsApiKey && !formData.api_key) {
    Message.warning(`${formData.embedding_service === 'openai' ? 'OpenAI' : 'Azure OpenAI'} 服务需要API密钥`);
    return;
  }

  testingConnection.value = true;
  try {
    // 前端直接测试连接
    let testUrl = '';
    let headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    switch (formData.embedding_service) {
      case 'openai':
        testUrl = `${formData.api_base_url.replace(/\/+$/, '')}/models`;
        headers['Authorization'] = `Bearer ${formData.api_key}`;
        break;
      case 'azure_openai':
        testUrl = `${formData.api_base_url.replace(/\/+$/, '')}/openai/models?api-version=2023-05-15`;
        headers['api-key'] = formData.api_key!;
        break;
      case 'ollama':
        testUrl = `${formData.api_base_url.replace(/\/+$/, '')}/api/tags`;
        break;
      case 'custom':
        testUrl = `${formData.api_base_url.replace(/\/+$/, '')}/health`;
        if (formData.api_key) {
          headers['Authorization'] = `Bearer ${formData.api_key}`;
        }
        break;
    }

    const response = await fetch(testUrl, {
      method: 'GET',
      headers,
      signal: AbortSignal.timeout(10000) // 10秒超时
    });

    if (response.ok) {
      Message.success('连接测试成功！服务可正常访问');
    } else {
      Message.error(`连接测试失败: HTTP ${response.status} - ${response.statusText}`);
    }
  } catch (error: any) {
    console.error('嵌入服务连接测试失败:', error);
    let errorMessage = '连接测试失败';
    
    if (error.name === 'TimeoutError') {
      errorMessage = '连接超时，请检查URL是否正确';
    } else if (error.name === 'TypeError' && error.message.includes('fetch')) {
      errorMessage = '无法连接到服务，请检查URL和网络';
    } else {
      errorMessage = error.message || '连接测试失败';
    }
    
    Message.error(errorMessage);
  } finally {
    testingConnection.value = false;
  }
};

const handleSubmit = async () => {
  try {
    // 验证基础信息表单
    await formRef.value?.validate();
    
    // 验证高级配置表单
    if (advancedFormRef.value) {
      await advancedFormRef.value.validate();
    }

    loading.value = true;

    if (isEdit.value && props.knowledgeBase) {
      // 编辑模式
      const updateData: UpdateKnowledgeBaseRequest = {
        name: formData.name,
        description: formData.description,
        project: formData.project,
        embedding_service: formData.embedding_service,
        api_base_url: formData.api_base_url,
        api_key: formData.api_key,
        model_name: formData.model_name,
        chunk_size: formData.chunk_size,
        chunk_overlap: formData.chunk_overlap,
      };
      await KnowledgeService.updateKnowledgeBase(props.knowledgeBase.id, updateData);
    } else {
      // 新建模式
      const createData: CreateKnowledgeBaseRequest = {
        name: formData.name,
        description: formData.description,
        project: formData.project,
        embedding_service: formData.embedding_service,
        api_base_url: formData.api_base_url,
        api_key: formData.api_key,
        model_name: formData.model_name,
        chunk_size: formData.chunk_size,
        chunk_overlap: formData.chunk_overlap,
        is_active: formData.is_active,
      };
      await KnowledgeService.createKnowledgeBase(createData);
    }

    emit('submit');
  } catch (error: any) {
    console.error('保存知识库失败:', error);
    // 检查是否是表单验证错误
    if (error && typeof error === 'object' && 'errorFields' in error) {
      Message.error('请检查表单填写是否正确');
    } else {
      // 显示具体的错误消息
      const errorMessage = error?.message || '保存知识库失败';
      Message.error(errorMessage);
    }
  } finally {
    loading.value = false;
  }
};

const handleCancel = () => {
  emit('cancel');
};
</script>

<style scoped>
:deep(.arco-form-item-label) {
  font-weight: 500;
}

:deep(.arco-input-number) {
  width: 100%;
}

.form-item-tip {
  font-size: 12px;
  color: var(--color-text-3);
  margin-top: 4px;
}
</style>
