<template>
  <a-modal
    :visible="visible"
    title="AI 生成测试用例"
    @cancel="handleCancel"
    @ok="handleOk"
    :width="600"
    :confirm-loading="isLoading"
  >
    <a-form :model="formState" :label-col-props="{ span: 6 }" :wrapper-col-props="{ span: 18 }">
      <a-form-item label="当前项目">
        <a-input v-model="currentProjectName" disabled />
      </a-form-item>
      <a-form-item
        label="选择需求文档"
        field="requirementDocumentId"
        :rules="[{ required: true, message: '请选择需求文档' }]"
      >
        <a-select
          v-model="formState.requirementDocumentId"
          placeholder="请选择"
          :loading="isDocLoading"
          @change="handleDocumentChange"
        >
          <a-option v-for="doc in requirementDocuments" :key="doc.id" :value="doc.id">
            {{ doc.title }}
          </a-option>
        </a-select>
      </a-form-item>
      <a-form-item
        label="需求文档模块"
        field="requirementModuleId"
        :rules="[{ required: true, message: '请选择需求文档模块' }]"
      >
        <a-select
          v-model="formState.requirementModuleId"
          placeholder="请先选择需求文档"
          :loading="isReqModuleLoading"
          :disabled="!formState.requirementDocumentId"
        >
          <a-option v-for="module in requirementModules" :key="module.id" :value="module.id">
            {{ module.title }}
          </a-option>
        </a-select>
      </a-form-item>
      <a-form-item
       label="选择提示词"
       field="promptId"
       :rules="[{ required: true, message: '请选择提示词' }]"
      >
       <a-select
         v-model="formState.promptId"
         placeholder="请选择"
         :loading="isPromptsLoading"
       >
         <a-option v-for="prompt in prompts" :key="prompt.id" :value="prompt.id">
           {{ prompt.name }}
         </a-option>
         <template #not-found>
           <div style="padding: 10px; text-align: center;">
             <a-empty description="没有可用的通用提示词，请先创建。" />
           </div>
         </template>
       </a-select>
      </a-form-item>
      <a-form-item label="启用知识库">
        <a-switch v-model="formState.useKnowledgeBase" @change="handleUseKbChange" />
      </a-form-item>
      <a-form-item
        label="关联知识库"
        field="knowledgeBaseId"
      >
        <a-select
          v-model="formState.knowledgeBaseId"
          placeholder="可选，用于提供额外业务知识"
          :loading="isKbLoading"
          :disabled="!formState.useKnowledgeBase"
          allow-clear
        >
          <a-option v-for="kb in knowledgeBases" :key="kb.id" :value="kb.id">
            {{ kb.name }}
          </a-option>
        </a-select>
      </a-form-item>
      <a-form-item
        label="用例保存模块"
        field="testCaseModuleId"
        :rules="[{ required: true, message: '请选择用例保存模块' }]"
      >
        <a-tree-select
          v-model="formState.testCaseModuleId"
          :data="testCaseModuleTree"
          placeholder="请选择"
          allow-clear
        >
        </a-tree-select>
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed } from 'vue';
import type { PropType } from 'vue';
import { useProjectStore } from '@/store/projectStore';
import type { TreeNodeData } from '@arco-design/web-vue';
import { Message } from '@arco-design/web-vue';
import { RequirementDocumentService } from '@/features/requirements/services/requirementService';
import type { RequirementDocument, DocumentModule } from '@/features/requirements/types';
import { getUserPrompts } from '@/features/prompts/services/promptService';
import type { UserPrompt, UserPromptListResponseData } from '@/features/prompts/types/prompt';
import { KnowledgeService } from '@/features/knowledge/services/knowledgeService';
import type { KnowledgeBase } from '@/features/knowledge/types/knowledge';

const props = defineProps({
  visible: {
    type: Boolean,
    required: true,
  },
  testCaseModuleTree: {
    type: Array as PropType<TreeNodeData[]>,
    default: () => [],
  },
});

const emit = defineEmits(['update:visible', 'submit']);

const projectStore = useProjectStore();
const isLoading = ref(false);
const isDocLoading = ref(false);
const isReqModuleLoading = ref(false);
const isPromptsLoading = ref(false);
const isKbLoading = ref(false);

const requirementDocuments = ref<RequirementDocument[]>([]);
const requirementModules = ref<DocumentModule[]>([]);
const prompts = ref<UserPrompt[]>([]);
const knowledgeBases = ref<KnowledgeBase[]>([]);

const formState = reactive({
  requirementDocumentId: null as string | null,
  requirementModuleId: null as string | null,
  promptId: null as number | null,
  useKnowledgeBase: false,
  knowledgeBaseId: null as string | null,
  testCaseModuleId: null,
});

const currentProjectName = computed(() => projectStore.currentProject?.name || '未命名项目');

const handleCancel = () => {
  emit('update:visible', false);
};

const handleOk = () => {
  if (!formState.requirementDocumentId || !formState.requirementModuleId || !formState.testCaseModuleId || !formState.promptId) {
    Message.error('请填写所有必填项');
    return;
  }
  
  const selectedModule = requirementModules.value.find(m => m.id === formState.requirementModuleId);

  emit('submit', { ...formState, selectedModule });
};

const fetchRequirementDocuments = async () => {
  if (!projectStore.currentProjectId) return;
  isDocLoading.value = true;
  try {
    const response = await RequirementDocumentService.getDocumentList({ project: String(projectStore.currentProjectId) });
    if (response.status === 'success' && Array.isArray(response.data)) {
      requirementDocuments.value = response.data;
    } else if (response.status === 'success' && 'results' in response.data) {
       requirementDocuments.value = response.data.results;
    } else {
      Message.error('加载需求文档列表失败');
      requirementDocuments.value = [];
    }
  } catch (error) {
    Message.error('加载需求文档列表时发生错误');
    requirementDocuments.value = [];
  } finally {
    isDocLoading.value = false;
  }
};

const fetchRequirementModules = async (documentId: string) => {
  isReqModuleLoading.value = true;
  requirementModules.value = [];
  formState.requirementModuleId = null;
  try {
    const response = await RequirementDocumentService.getDocumentDetail(documentId);
    if (response.status === 'success' && response.data?.modules) {
      requirementModules.value = response.data.modules;
    } else {
      Message.error('加载需求模块失败');
    }
  } catch (error) {
    Message.error('加载需求模块时发生错误');
  } finally {
    isReqModuleLoading.value = false;
  }
};

const handleDocumentChange = (value: any) => {
  if (value) {
    fetchRequirementModules(value);
  } else {
    requirementModules.value = [];
    formState.requirementModuleId = null;
  }
};

const fetchPrompts = async () => {
  isPromptsLoading.value = true;
  try {
    // 获取 "general" 类型的提示词
    const response = await getUserPrompts({ prompt_type: 'general' });
    if (response.status === 'success') {
       // 根据您提供的实际返回，data可能直接是数组
       if (Array.isArray(response.data)) {
           prompts.value = response.data;
       }
       // 兼容旧的或分页的格式
       else if ((response.data as UserPromptListResponseData)?.results) {
           prompts.value = (response.data as UserPromptListResponseData).results;
       }
       else {
           // 接口成功但数据格式不符或为空
           prompts.value = [];
       }
    } else {
      Message.error(response.message || '加载提示词列表失败');
      prompts.value = [];
    }
  } catch (error) {
    Message.error('加载提示词列表时发生错误');
    prompts.value = [];
  } finally {
    isPromptsLoading.value = false;
  }
};

const fetchKnowledgeBases = async () => {
  if (!projectStore.currentProjectId) return;
  isKbLoading.value = true;
  try {
    const response = await KnowledgeService.getKnowledgeBases({ project: projectStore.currentProjectId });
    if (Array.isArray(response)) {
       knowledgeBases.value = response;
    } else {
       knowledgeBases.value = response.results;
    }
  } catch (error) {
    Message.error('加载知识库列表失败');
    knowledgeBases.value = [];
  } finally {
    isKbLoading.value = false;
  }
};

const handleUseKbChange = (value: string | number | boolean) => {
  if (!value) {
    formState.knowledgeBaseId = null;
  }
};

watch(() => props.visible, (newVal) => {
  if (newVal) {
    // 每次打开弹窗时重置表单
    formState.requirementDocumentId = null;
    formState.requirementModuleId = null;
    formState.promptId = null;
    formState.useKnowledgeBase = false;
    formState.knowledgeBaseId = null;
    formState.testCaseModuleId = null;
    requirementDocuments.value = [];
    requirementModules.value = [];
    prompts.value = [];
    knowledgeBases.value = [];
    fetchRequirementDocuments();
    fetchPrompts();
    fetchKnowledgeBases();
  }
});

</script>

<style scoped>
/* 你可以在这里添加一些样式 */
</style>