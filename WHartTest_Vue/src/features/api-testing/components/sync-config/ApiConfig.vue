<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { IconPlus } from '@arco-design/web-vue/es/icon'
import { syncApi, type ApiSyncConfig } from '../../services/syncService'
import { toArray } from '../../services/responseHelpers'
import { useAppI18n } from '@/composables/useAppI18n'
import { useProjectStore } from '@/store/projectStore'
import { useThemeStore } from '@/store/themeStore'
import ApiConfigTable from './ApiConfigTable.vue'
import ApiConfigForm from './ApiConfigForm.vue'
import ApiConfigDetail from './ApiConfigDetail.vue'

const projectStore = useProjectStore()
const themeStore = useThemeStore()
const { isEnglish } = useAppI18n()
const loading = ref(false)
const configs = ref<ApiSyncConfig[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const showCreateModal = ref(false)
const showDetailModal = ref(false)
const isEditing = ref(false)
const editingConfigId = ref<number | null>(null)
const selectedRowKeys = ref<number[]>([])
const currentConfig = ref<ApiSyncConfig | null>(null)
const isDarkTheme = computed(() => themeStore.isBlack)

const text = computed(() => isEnglish.value
  ? {
      pageTitle: 'Interface Sync Config',
      batchDelete: 'Batch Delete',
      createConfig: 'Create Config',
      pageSubtitle: 'Manage sync relationships between interfaces, test cases, and test steps',
      selectProjectFirst: 'Please select a project first',
      fetchConfigListFailed: 'Failed to fetch interface sync configs',
      fetchConfigDetailFailed: 'Failed to fetch config details',
      updateSuccess: 'Sync config updated successfully',
      createSuccess: 'Sync config created successfully',
      updateFailed: 'Failed to update sync config',
      createFailed: 'Failed to create sync config',
      deleteConfirmTitle: 'Confirm Delete',
      deleteConfirmContent: (name: string) => `Are you sure you want to delete sync config "${name}"? This action cannot be undone.`,
      confirmDelete: 'Delete',
      cancel: 'Cancel',
      deleteSuccess: 'Deleted successfully',
      deleteFailed: 'Delete failed',
      batchDeleteWarning: 'Please select sync configs to delete first',
      batchDeleteTitle: 'Confirm Batch Delete',
      batchDeleteContent: (count: number) => `Are you sure you want to delete the selected ${count} sync configs? This action cannot be undone.`,
      batchDeleteSuccess: (count: number) => `Deleted ${count} sync configs`,
      batchDeletePartialFailed: (count: number) => `${count} sync configs failed to delete. Please try again.`,
      batchDeleteFailed: 'Batch delete failed',
      syncSuccess: 'Sync executed successfully',
      syncFailed: 'Sync execution failed',
      selectedCount: (count: number) => `(${count})`,
    }
  : {
      pageTitle: '接口同步配置',
      batchDelete: '批量删除',
      createConfig: '新建配置',
      pageSubtitle: '管理接口、用例和测试步骤之间的同步关系',
      selectProjectFirst: '请先选择项目',
      fetchConfigListFailed: '获取接口同步配置列表失败',
      fetchConfigDetailFailed: '获取配置详情失败',
      updateSuccess: '更新同步配置成功',
      createSuccess: '创建同步配置成功',
      updateFailed: '更新同步配置失败',
      createFailed: '创建同步配置失败',
      deleteConfirmTitle: '确认删除',
      deleteConfirmContent: (name: string) => `确定要删除同步配置"${name}"吗？此操作不可恢复。`,
      confirmDelete: '确认删除',
      cancel: '取消',
      deleteSuccess: '删除成功',
      deleteFailed: '删除失败',
      batchDeleteWarning: '请先选择要删除的同步配置',
      batchDeleteTitle: '确认批量删除',
      batchDeleteContent: (count: number) => `确定要删除选中的 ${count} 条同步配置吗？此操作不可恢复。`,
      batchDeleteSuccess: (count: number) => `已删除 ${count} 条同步配置`,
      batchDeletePartialFailed: (count: number) => `${count} 条同步配置删除失败，请重试`,
      batchDeleteFailed: '批量删除失败',
      syncSuccess: '同步执行成功',
      syncFailed: '同步执行失败',
      selectedCount: (count: number) => `（${count}）`,
    }
)

const fieldOptions = computed(() => isEnglish.value
  ? [
      { label: 'Request Method', value: 'method' },
      { label: 'URL', value: 'url' },
      { label: 'Headers', value: 'headers' },
      { label: 'Query Params', value: 'params' },
      { label: 'Request Body', value: 'body' },
      { label: 'Setup Hooks', value: 'setup_hooks' },
      { label: 'Teardown Hooks', value: 'teardown_hooks' },
      { label: 'Variables', value: 'variables' },
      { label: 'Validators', value: 'validators' },
      { label: 'Extract Variables', value: 'extract' },
    ]
  : [
      { label: '请求方法', value: 'method' },
      { label: 'URL', value: 'url' },
      { label: '请求头', value: 'headers' },
      { label: '查询参数', value: 'params' },
      { label: '请求体', value: 'body' },
      { label: '前置钩子', value: 'setup_hooks' },
      { label: '后置钩子', value: 'teardown_hooks' },
      { label: '变量定义', value: 'variables' },
      { label: '断言规则', value: 'validators' },
      { label: '提取变量', value: 'extract' },
    ]
)

const fetchConfigs = async () => {
  if (!projectStore.currentProject?.id) {
    Message.error(text.value.selectProjectFirst)
    return
  }

  try {
    loading.value = true
    const { data } = await syncApi.getApiConfigs(projectStore.currentProject.id)
    configs.value = toArray<ApiSyncConfig>(data?.results ?? data)
    total.value = data?.count ?? configs.value.length
  } catch (error) {
    Message.error(text.value.fetchConfigListFailed)
    console.error(error)
  } finally {
    loading.value = false
  }
}

const handleEdit = async (record: ApiSyncConfig) => {
  try {
    showCreateModal.value = false
    showDetailModal.value = false
    currentConfig.value = null
    isEditing.value = true
    editingConfigId.value = record.id

    loading.value = true
    console.log('获取配置详情，ID:', record.id)
    const response = await syncApi.getConfigDetail(record.id)
    const configData = response.data

    console.log('获取到的配置详情(原始):', configData)
    console.log('接口ID:', (configData as any).interface)
    console.log('用例ID:', (configData as any).testcase)
    console.log('步骤ID:', (configData as any).step)
    console.log('接口信息:', (configData as any).interface_info)
    console.log('用例信息:', (configData as any).testcase_info)
    console.log('步骤信息:', (configData as any).step_info)

    currentConfig.value = configData
    showCreateModal.value = true
  } catch (error) {
    Message.error(text.value.fetchConfigDetailFailed)
    console.error(error)
  } finally {
    loading.value = false
  }
}

const handleSubmit = async (formData: any) => {
  try {
    loading.value = true
    if (isEditing.value && editingConfigId.value) {
      await syncApi.updateApiConfig(editingConfigId.value, formData)
      Message.success(text.value.updateSuccess)
    } else {
      await syncApi.createApiConfig(formData)
      Message.success(text.value.createSuccess)
    }
    
    // 关闭弹窗并重置状态
    showCreateModal.value = false
    isEditing.value = false
    editingConfigId.value = null
    currentConfig.value = null
    
    // 重新获取配置列表
    await fetchConfigs()
  } catch (error: any) {
    if (error.errors) {
      const errorMessages = Object.values(error.errors).flat()
      Message.error(errorMessages.join(', '))
    } else {
      Message.error(isEditing.value ? text.value.updateFailed : text.value.createFailed)
    }
    console.error(error)
  } finally {
    loading.value = false
  }
}

const handleViewDetail = async (record: ApiSyncConfig) => {
  try {
    showCreateModal.value = false
    showDetailModal.value = false
    currentConfig.value = null

    loading.value = true
    const response = await syncApi.getConfigDetail(record.id)
    const configData = response.data
    console.log('查看详情，获取到的配置:', configData)

    currentConfig.value = configData
    showDetailModal.value = true
  } catch (error) {
    Message.error(text.value.fetchConfigDetailFailed)
    console.error(error)
  } finally {
    loading.value = false
  }
}

const handleDelete = async (record: ApiSyncConfig) => {
  Modal.warning({
    title: text.value.deleteConfirmTitle,
    content: text.value.deleteConfirmContent(record.name),
    okText: text.value.confirmDelete,
    cancelText: text.value.cancel,
    async onOk() {
      try {
        loading.value = true
        await syncApi.deleteApiConfig(record.id)
        Message.success(text.value.deleteSuccess)
        await fetchConfigs()
      } catch (error) {
        Message.error(text.value.deleteFailed)
        console.error(error)
      } finally {
        loading.value = false
      }
    }
  })
}

const handleBatchDelete = async () => {
  if (!selectedRowKeys.value.length) {
    Message.warning(text.value.batchDeleteWarning)
    return
  }

  const ids = [...selectedRowKeys.value]

  Modal.warning({
    title: text.value.batchDeleteTitle,
    content: text.value.batchDeleteContent(ids.length),
    okText: text.value.confirmDelete,
    cancelText: text.value.cancel,
    async onOk() {
      try {
        loading.value = true
        const results = await Promise.allSettled(ids.map(id => syncApi.deleteApiConfig(id)))
        const failedCount = results.filter(result => result.status === 'rejected').length
        const successCount = ids.length - failedCount

        if (successCount > 0) {
          Message.success(text.value.batchDeleteSuccess(successCount))
        }

        if (failedCount > 0) {
          Message.warning(text.value.batchDeletePartialFailed(failedCount))
        }

        selectedRowKeys.value = []
        await fetchConfigs()
      } catch (error) {
        Message.error(text.value.batchDeleteFailed)
        console.error(error)
      } finally {
        loading.value = false
      }
    }
  })
}

const handleSyncNow = async (record: ApiSyncConfig) => {
  try {
    loading.value = true
    await syncApi.syncNowConfig(record.id)
    Message.success(text.value.syncSuccess)
  } catch (error) {
    Message.error(text.value.syncFailed)
    console.error(error)
  } finally {
    loading.value = false
  }
}

const handlePageChange = (page: number) => {
  currentPage.value = page
  selectedRowKeys.value = []
  fetchConfigs()
}

const handlePageSizeChange = (size: number) => {
  pageSize.value = size
  currentPage.value = 1
  selectedRowKeys.value = []
  fetchConfigs()
}

// 处理新建配置
const handleCreate = () => {
  showCreateModal.value = false
  showDetailModal.value = false
  currentConfig.value = null
  isEditing.value = false
  editingConfigId.value = null
  showCreateModal.value = true
}

// 监听项目变化
watch(() => projectStore.currentProject?.id, (newProjectId) => {
  if (newProjectId) {
    selectedRowKeys.value = []
    fetchConfigs()
  } else {
    configs.value = []
    total.value = 0
    selectedRowKeys.value = []
  }
})

onMounted(() => {
  if (projectStore.currentProject?.id) {
    fetchConfigs()
  }
})
</script>

<template>
  <div class="api-config-page h-full flex flex-col" :class="isDarkTheme ? 'api-config-page--dark' : 'api-config-page--light'">
    <!-- 页面头部 -->
    <div class="api-config-header px-8 py-6 border-b">
      <div class="flex items-center justify-between">
        <h1 class="api-config-title text-xl font-semibold">{{ text.pageTitle }}</h1>
        <div class="flex items-center gap-2">
          <a-button
            type="outline"
            status="danger"
            :disabled="selectedRowKeys.length === 0"
            :loading="loading"
            @click="handleBatchDelete"
          >
            {{ text.batchDelete }}<span v-if="selectedRowKeys.length > 0">{{ text.selectedCount(selectedRowKeys.length) }}</span>
          </a-button>
          <a-button type="primary" :loading="loading" @click="handleCreate">
            <template #icon>
              <icon-plus />
            </template>
            {{ text.createConfig }}
          </a-button>
        </div>
      </div>
      <p class="api-config-subtitle mt-2 text-sm">{{ text.pageSubtitle }}</p>
    </div>

    <!-- 主要内容区域 -->
    <div class="flex-1 overflow-hidden p-2">
      <div class="h-full overflow-auto custom-scrollbar">
        <api-config-table
          :loading="loading"
          :configs="configs"
          v-model:selectedRowKeys="selectedRowKeys"
          :fieldOptions="fieldOptions"
          @sync="handleSyncNow"
          @edit="handleEdit"
          @view="handleViewDetail"
          @delete="handleDelete"
          @create="handleCreate"
        />
      </div>
    </div>

    <!-- 分页区域 -->
    <div class="api-config-footer px-8 py-4 border-t">
      <a-pagination
        :total="total"
        v-model:current="currentPage"
        v-model:pageSize="pageSize"
        show-total
        show-jumper
        show-page-size
        class="justify-end"
        @change="handlePageChange"
        @pageSizeChange="handlePageSizeChange"
      />
    </div>

    <!-- 创建/编辑弹窗 -->
    <api-config-form
      :visible="showCreateModal"
      :loading="loading"
      :isEditing="isEditing"
      :fieldOptions="fieldOptions"
      :currentConfig="currentConfig"
      @update:visible="showCreateModal = $event"
      @submit="handleSubmit"
    />

    <!-- 详情弹窗 -->
    <api-config-detail
      :visible="showDetailModal"
      :config="currentConfig"
      :fieldOptions="fieldOptions"
      @update:visible="showDetailModal = $event"
    />
  </div>
</template>

<style scoped>
@reference "tailwindcss";
.api-config-page {
  --api-config-bg: rgba(255, 255, 255, 0.9);
  --api-config-header-bg: rgba(248, 250, 252, 0.94);
  --api-config-footer-bg: rgba(248, 250, 252, 0.92);
  --api-config-border: rgba(148, 163, 184, 0.18);
  --api-config-title: var(--color-text-1);
  --api-config-subtitle: var(--color-text-3);
  --api-pagination-text: var(--color-text-2);
  --api-pagination-bg: #ffffff;
  --api-pagination-border: rgba(148, 163, 184, 0.22);
  --api-pagination-hover-border: rgb(var(--primary-6));
}

.api-config-page--dark {
  --api-config-bg: rgb(17, 24, 39);
  --api-config-header-bg: rgba(31, 41, 55, 0.5);
  --api-config-footer-bg: rgba(31, 41, 55, 0.5);
  --api-config-border: rgba(55, 65, 81, 1);
  --api-config-title: rgb(243, 244, 246);
  --api-config-subtitle: rgb(156, 163, 175);
  --api-pagination-text: rgb(156, 163, 175);
  --api-pagination-bg: rgba(55, 65, 81, 1);
  --api-pagination-border: rgba(75, 85, 99, 1);
  --api-pagination-hover-border: rgb(var(--primary-6));
}

.api-config-page {
  background: var(--api-config-bg);
}

.api-config-header {
  background: var(--api-config-header-bg);
  border-color: var(--api-config-border);
}

.api-config-footer {
  background: var(--api-config-footer-bg);
  border-color: var(--api-config-border);
}

.api-config-title {
  color: var(--api-config-title);
}

.api-config-subtitle {
  color: var(--api-config-subtitle);
}

/* 添加自定义滚动条样式 */
.custom-scrollbar {
  scrollbar-width: thin;
  scrollbar-color: rgba(107, 114, 128, 0.3) transparent;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: rgba(107, 114, 128, 0.3);
  border-radius: 3px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background-color: rgba(107, 114, 128, 0.5);
}

:deep(.arco-pagination) {
  @apply flex items-center;
}

:deep(.arco-pagination-total) {
  color: var(--api-pagination-text);
}

:deep(.arco-pagination-item) {
  background: var(--api-pagination-bg);
  border-color: var(--api-pagination-border);
  color: var(--api-pagination-text);
}

:deep(.arco-pagination-item:hover) {
  border-color: var(--api-pagination-hover-border);
}

:deep(.arco-pagination-item-active) {
  @apply bg-blue-500 border-blue-500 text-white;
}

:deep(.arco-pagination-jumper) {
  color: var(--api-pagination-text);
}

:deep(.arco-pagination-jumper .arco-input-wrapper) {
  background: var(--api-pagination-bg);
  border-color: var(--api-pagination-border);
}

:deep(.arco-pagination-jumper .arco-input) {
  color: var(--api-pagination-text);
}

:deep(.arco-select-view.arco-pagination-page-size-view) {
  background: var(--api-pagination-bg);
  border-color: var(--api-pagination-border);
  color: var(--api-pagination-text);
}
</style> 
