<template>
  <div class="llm-config-management">
    <div class="page-header">
      <h1 class="text-2xl font-semibold mb-4">LLM 配置管理</h1>
      <a-button type="primary" @click="handleAddNewConfig">
        <template #icon><icon-plus /></template>
        新增配置
      </a-button>
    </div>

    <LlmConfigTable
      :configs="llmConfigs"
      :loading="isLoading"
      :pagination="pagination"
      @edit="handleEditConfig"
      @delete="handleDeleteConfig"
      @page-change="handlePageChange"
      @page-size-change="handlePageSizeChange"
    />

    <LlmConfigFormModal
      :visible="isModalVisible"
      :config-data="currentConfig"
      :form-loading="isFormLoading"
      @submit="handleSubmitConfig"
      @cancel="handleCloseModal"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, watch } from 'vue';
import { Button as AButton, Message, Modal as AModal } from '@arco-design/web-vue';
import { IconPlus } from '@arco-design/web-vue/es/icon';
import LlmConfigTable from '@/features/langgraph/components/LlmConfigTable.vue';
import LlmConfigFormModal from '@/features/langgraph/components/LlmConfigFormModal.vue';
import type { LlmConfig, CreateLlmConfigRequest, PartialUpdateLlmConfigRequest } from '@/features/langgraph/types/llmConfig';
import {
  listLlmConfigs,
  createLlmConfig,
  updateLlmConfig,
  partialUpdateLlmConfig,
  deleteLlmConfig,
  getLlmConfigDetails
} from '@/features/langgraph/services/llmConfigService';
import type { PaginationProps } from '@arco-design/web-vue';
import { useProjectStore } from '@/store/projectStore';

const projectStore = useProjectStore();

const llmConfigs = ref<LlmConfig[]>([]);
const isLoading = ref(false);
const isModalVisible = ref(false);
const currentConfig = ref<LlmConfig | null>(null);
const isFormLoading = ref(false);

const pagination = reactive<PaginationProps>({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: true,
  showPageSize: true,
});

const fetchLlmConfigs = async () => {
  isLoading.value = true;
  try {
    // 注意：实际的 listLlmConfigs API 可能需要支持分页参数
    // 这里暂时获取所有数据，实际项目中应根据后端分页能力调整
    const response = await listLlmConfigs();
    if (response.status === 'success') {
      llmConfigs.value = response.data;
      // 假设 API 返回的数据本身就是分页好的，或者前端进行简单分页
      // 如果 API 支持分页，应该用 API 返回的 total
      pagination.total = response.data.length; // 简单示例，实际应从 API 获取 total
    } else {
      Message.error(response.message || '获取 LLM 配置列表失败');
    }
  } catch (error) {
    console.error('Error fetching LLM configs:', error);
    Message.error('获取 LLM 配置列表失败，请检查网络或联系管理员');
  } finally {
    isLoading.value = false;
  }
};

const handlePageChange = (page: number) => {
  pagination.current = page;
  // fetchLlmConfigs(); // 如果后端支持分页，则重新获取数据
};

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize;
  pagination.current = 1; // 通常页码大小改变后回到第一页
  // fetchLlmConfigs(); // 如果后端支持分页，则重新获取数据
};

const handleAddNewConfig = () => {
  currentConfig.value = null;
  isModalVisible.value = true;
};

const handleEditConfig = async (config: LlmConfig) => {
  // 为了获取最新的、可能包含 API Key（如果后端允许）的完整信息，或者只是为了确认数据最新
  // 可以选择在编辑前重新请求一次详细信息，但这取决于业务需求和API设计
  // 如果列表数据已足够，则不需要下面这步
  isLoading.value = true; // 可以用一个不同的 loading 状态，比如 isDetailLoading
  try {
    const response = await getLlmConfigDetails(config.id);
    if (response.status === 'success') {
      currentConfig.value = response.data;
      isModalVisible.value = true;
    } else {
      Message.error(response.message || '获取配置详情失败');
    }
  } catch (error) {
    Message.error('获取配置详情失败');
  } finally {
    isLoading.value = false;
  }
};

const handleDeleteConfig = async (configId: number) => {
  try {
    isLoading.value = true; // 或者用一个特定的删除 loading
    const response = await deleteLlmConfig(configId);
    // API 文档中 204 响应也带了 body，但通常 204 无 body
    // deleteLlmConfig service 内部已处理了 204 的情况
    if (response.status === 'success') {
      Message.success('LLM 配置删除成功');
      await fetchLlmConfigs(); // 刷新列表
      // 检查当前页码是否仍然有效，如果当前页码超出了新的总页数，则调整到最后一页或第一页
      if (pagination.total > 0 && pagination.current > Math.ceil(pagination.total / pagination.pageSize)) {
        pagination.current = Math.ceil(pagination.total / pagination.pageSize);
      } else if (pagination.total === 0) {
        pagination.current = 1;
      }
    } else {
      Message.error(response.message || '删除失败');
    }
  } catch (error) {
    console.error('Error deleting LLM config:', error);
    Message.error('删除失败，请稍后再试');
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
    let response;
    if (id) {
      // 编辑模式 - API 文档中 PUT 和 PATCH 都有，这里用 PATCH 作为示例，因为它更灵活
      // 如果后端严格区分 PUT (全量) 和 PATCH (部分)，需要根据 LlmConfigFormModal 的实现来决定调用哪个
      // LlmConfigFormModal 实现的是：如果 api_key 为空字符串，则不提交该字段，适合 PATCH
      response = await partialUpdateLlmConfig(id, data as PartialUpdateLlmConfigRequest);
      // 如果需要严格的 PUT，则 LlmConfigFormModal 需要确保所有字段都提交
      // response = await updateLlmConfig(id, data as CreateLlmConfigRequest);
    } else {
      // 新增模式
      response = await createLlmConfig(data as CreateLlmConfigRequest);
    }

    if (response.status === 'success') {
      Message.success(id ? 'LLM 配置更新成功' : 'LLM 配置创建成功');
      isModalVisible.value = false;
      await fetchLlmConfigs(); // 刷新列表
    } else {
      // API 返回的 errors 对象可以用于在表单中显示具体字段错误，此处简化处理
      const errorMessages = response.errors ? Object.values(response.errors).flat().join('; ') : '';
      Message.error(`${response.message}${errorMessages ? ` (${errorMessages})` : ''}` || (id ? '更新失败' : '创建失败'));
    }
  } catch (error: any) {
    console.error('Error submitting LLM config:', error);
    const errorDetail = error.response?.data?.message || error.message || (id ? '更新失败' : '创建失败');
    Message.error(errorDetail);
  } finally {
    isFormLoading.value = false;
  }
};

const handleCloseModal = () => {
  isModalVisible.value = false;
  currentConfig.value = null; // 清除当前编辑项
};

// 监听项目变化，重新加载数据
watch(() => projectStore.currentProjectId, (newProjectId, oldProjectId) => {
  if (newProjectId !== oldProjectId) {
    // 项目切换时重置状态
    pagination.current = 1;

    // 重新获取LLM配置列表
    fetchLlmConfigs();
  }
}, { immediate: false });

onMounted(() => {
  fetchLlmConfigs();
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

.page-header h1 {
  font-size: 1.5rem;
  font-weight: 600;
  margin-bottom: 0;
}
</style>