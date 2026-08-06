<template>
  <div class="llm-config-management">
    <div class="page-header">
      <h1 class="page-title">{{ pageText.pageTitle }}</h1>
      <div class="header-actions">
        <a-button @click="showPromptManagement">
          <template #icon><icon-file /></template>
          {{ pageText.promptManagement }}
        </a-button>
        <a-button type="primary" @click="handleAddNewConfig">
          <template #icon><icon-plus /></template>
          {{ pageText.addConfig }}
        </a-button>
      </div>
    </div>

    <LlmConfigTable
      :configs="llmConfigs"
      :loading="isLoading"
      :pagination="pagination"
      @edit="handleEditConfig"
      @delete="handleDeleteConfig"
      @toggle-active="handleToggleActive"
      @page-change="handlePageChange"
      @page-size-change="handlePageSizeChange"
    />

    <LlmConfigFormModal
      :visible="isModalVisible"
      :config-data="currentConfig"
      :form-loading="isFormLoading"
      @submit="handleSubmitConfig"
      @cancel="handleCloseModal"
      @auto-saved="handleAutoSaved"
    />

    <SystemPromptModal
      :visible="isPromptModalVisible"
      :current-llm-config="currentLlmConfigForPrompt"
      :loading="false"
      @cancel="closePromptModal"
      @prompts-updated="handlePromptsUpdated"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, watch, computed } from 'vue';
import { Button as AButton, Message } from '@arco-design/web-vue';
import type { PaginationProps } from '@arco-design/web-vue';
import { IconPlus, IconFile } from '@arco-design/web-vue/es/icon';
import { useAppI18n } from '@/composables/useAppI18n';
import { useLlmConfigRefresh } from '@/composables/useLlmConfigRefresh';
import LlmConfigTable from '@/features/langgraph/components/LlmConfigTable.vue';
import LlmConfigFormModal from '@/features/langgraph/components/LlmConfigFormModal.vue';
import SystemPromptModal from '@/features/langgraph/components/SystemPromptModal.vue';
import {
  listLlmConfigs,
  createLlmConfig,
  partialUpdateLlmConfig,
  deleteLlmConfig,
  getLlmConfigDetails,
} from '@/features/langgraph/services/llmConfigService';
import type {
  LlmConfig,
  CreateLlmConfigRequest,
  PartialUpdateLlmConfigRequest,
} from '@/features/langgraph/types/llmConfig';
import { useProjectStore } from '@/store/projectStore';

const projectStore = useProjectStore();
const { triggerLlmConfigRefresh } = useLlmConfigRefresh();
const { isEnglish } = useAppI18n();

const pageText = computed(() => (
  isEnglish.value
    ? {
        pageTitle: 'LLM Configuration Management',
        promptManagement: 'Prompt Management',
        addConfig: 'New Config',
        promptsUpdated: 'Prompts updated',
        fetchListFailed: 'Failed to fetch the LLM config list',
        fetchListRetry: 'Failed to fetch the LLM config list, please check the network or contact an administrator',
        fetchDetailFailed: 'Failed to fetch config details',
        deleteSuccess: 'LLM config deleted successfully',
        deleteFailed: 'Delete failed',
        updateSuccess: 'LLM config updated successfully',
        createSuccess: 'LLM config created successfully',
        updateFailed: 'Update failed',
        createFailed: 'Create failed',
        activeSuccess: 'LLM config activated',
        inactiveSuccess: 'LLM config deactivated',
        toggleFailed: 'Failed to update status',
      }
    : {
        pageTitle: 'LLM 配置管理',
        promptManagement: '提示词管理',
        addConfig: '新增配置',
        promptsUpdated: '提示词已更新',
        fetchListFailed: '获取 LLM 配置列表失败',
        fetchListRetry: '获取 LLM 配置列表失败，请检查网络或联系管理员',
        fetchDetailFailed: '获取配置详情失败',
        deleteSuccess: 'LLM 配置删除成功',
        deleteFailed: '删除失败',
        updateSuccess: 'LLM 配置更新成功',
        createSuccess: 'LLM 配置创建成功',
        updateFailed: '更新失败',
        createFailed: '创建失败',
        activeSuccess: 'LLM 配置已激活',
        inactiveSuccess: 'LLM 配置已停用',
        toggleFailed: '更新状态失败',
      }
));

const llmConfigs = ref<LlmConfig[]>([]);
const isLoading = ref(false);
const isModalVisible = ref(false);
const currentConfig = ref<LlmConfig | null>(null);
const isFormLoading = ref(false);

const isPromptModalVisible = ref(false);
const currentLlmConfigForPrompt = ref<LlmConfig | null>(null);

const pagination = reactive<PaginationProps>({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: true,
  showPageSize: true,
});

const showPromptManagement = () => {
  const activeConfig = llmConfigs.value.find((config) => config.is_active);
  currentLlmConfigForPrompt.value = activeConfig || null;
  isPromptModalVisible.value = true;
};

const closePromptModal = () => {
  isPromptModalVisible.value = false;
};

const handlePromptsUpdated = () => {
  Message.success(pageText.value.promptsUpdated);
};

const fetchLlmConfigs = async () => {
  isLoading.value = true;
  try {
    const response = await listLlmConfigs();
    if (response.status === 'success') {
      llmConfigs.value = response.data;
      pagination.total = response.data.length;
    } else {
      Message.error(response.message || pageText.value.fetchListFailed);
    }
  } catch (error) {
    console.error('Error fetching LLM configs:', error);
    Message.error(pageText.value.fetchListRetry);
  } finally {
    isLoading.value = false;
  }
};

const handlePageChange = (page: number) => {
  pagination.current = page;
};

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize;
  pagination.current = 1;
};

const handleAddNewConfig = () => {
  currentConfig.value = null;
  isModalVisible.value = true;
};

const handleEditConfig = async (config: LlmConfig) => {
  isLoading.value = true;
  try {
    const response = await getLlmConfigDetails(config.id);
    if (response.status === 'success') {
      currentConfig.value = response.data;
      isModalVisible.value = true;
    } else {
      Message.error(response.message || pageText.value.fetchDetailFailed);
    }
  } catch (error) {
    Message.error(pageText.value.fetchDetailFailed);
  } finally {
    isLoading.value = false;
  }
};

const handleDeleteConfig = async (configId: number) => {
  try {
    isLoading.value = true;
    const response = await deleteLlmConfig(configId);
    if (response.status === 'success') {
      Message.success(pageText.value.deleteSuccess);
      await fetchLlmConfigs();
      triggerLlmConfigRefresh();
      if (pagination.total > 0 && pagination.current > Math.ceil(pagination.total / pagination.pageSize)) {
        pagination.current = Math.ceil(pagination.total / pagination.pageSize);
      } else if (pagination.total === 0) {
        pagination.current = 1;
      }
    } else {
      Message.error(response.message || pageText.value.deleteFailed);
    }
  } catch (error) {
    console.error('Error deleting LLM config:', error);
    Message.error(pageText.value.deleteFailed);
  } finally {
    isLoading.value = false;
  }
};

const handleSubmitConfig = async (
  data: CreateLlmConfigRequest | PartialUpdateLlmConfigRequest,
  id?: number
) => {
  isFormLoading.value = true;
  try {
    const response = id
      ? await partialUpdateLlmConfig(id, data as PartialUpdateLlmConfigRequest)
      : await createLlmConfig(data as CreateLlmConfigRequest);

    if (response.status === 'success') {
      Message.success(id ? pageText.value.updateSuccess : pageText.value.createSuccess);
      isModalVisible.value = false;
      currentConfig.value = null;
      await fetchLlmConfigs();
      triggerLlmConfigRefresh();
    } else {
      const errorMessages = response.errors ? Object.values(response.errors).flat().join('; ') : '';
      Message.error(`${response.message}${errorMessages ? ` (${errorMessages})` : ''}` || (id ? pageText.value.updateFailed : pageText.value.createFailed));
    }
  } catch (error: any) {
    console.error('Error submitting LLM config:', error);
    const errorDetail = error.response?.data?.message || error.message || (id ? pageText.value.updateFailed : pageText.value.createFailed);
    Message.error(errorDetail);
  } finally {
    isFormLoading.value = false;
  }
};

const handleToggleActive = async (configId: number, isActive: boolean) => {
  try {
    const response = await partialUpdateLlmConfig(configId, { is_active: isActive });
    if (response.status === 'success') {
      Message.success(isActive ? pageText.value.activeSuccess : pageText.value.inactiveSuccess);
      await fetchLlmConfigs();
      triggerLlmConfigRefresh();
    } else {
      Message.error(response.message || pageText.value.toggleFailed);
      await fetchLlmConfigs();
    }
  } catch (error: any) {
    console.error('Error toggling LLM config active state:', error);
    const errorDetail = error.response?.data?.message || error.message || pageText.value.toggleFailed;
    Message.error(errorDetail);
    await fetchLlmConfigs();
  }
};

const handleCloseModal = () => {
  isModalVisible.value = false;
  currentConfig.value = null;
};

const handleAutoSaved = async (closeModal = false) => {
  if (closeModal) {
    isModalVisible.value = false;
    currentConfig.value = null;
  }
  await fetchLlmConfigs();
  triggerLlmConfigRefresh();
};

watch(() => projectStore.currentProjectId, (newProjectId, oldProjectId) => {
  if (newProjectId !== oldProjectId) {
    pagination.current = 1;
    void fetchLlmConfigs();
  }
}, { immediate: false });

onMounted(() => {
  void fetchLlmConfigs();
});
</script>

<style scoped>
.llm-config-management {
  padding: 20px 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.page-title {
  font-size: 1.5rem;
  font-weight: 600;
  margin-bottom: 0;
}

.header-actions {
  display: flex;
  gap: 12px;
}
</style>
