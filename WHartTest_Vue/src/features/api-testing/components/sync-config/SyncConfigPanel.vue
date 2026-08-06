<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { useAppI18n } from '@/composables/useAppI18n'
import { IconPlus, IconEmpty, IconStar, IconDelete } from '@arco-design/web-vue/es/icon'
import { syncApi, type SyncConfig } from '../../services/syncService'
import type { TableColumnData } from '@arco-design/web-vue'
import { useProjectStore } from '@/store/projectStore'
import { useThemeStore } from '@/store/themeStore'
import SyncHistory from './SyncHistory.vue'
import ApiConfig from './ApiConfig.vue'

const projectStore = useProjectStore()
const themeStore = useThemeStore()
const { isEnglish } = useAppI18n()
const loading = ref(false)
const configs = ref<SyncConfig[]>([])
const activeConfigId = ref<number | null>(null)
const showCreateModal = ref(false)
const isEditing = ref(false)
const editingConfigId = ref<number | null>(null)
const activeTab = ref('config')
const isDarkTheme = computed(() => themeStore.isBlack)
const pageText = computed(() => isEnglish.value
  ? {
      createdBy: 'Created by',
      createdAt: 'Created at',
    }
  : {
      createdBy: '创建者',
      createdAt: '创建时间',
    }
)

const formModel = ref({
  name: '',
  description: '',
  sync_fields: [] as string[],
  sync_enabled: true,
  sync_mode: 'manual' as 'manual' | 'auto',
  is_active: false
})

const fieldOptions = [
  { label: '请求方法', value: 'method' },
  { label: 'URL', value: 'url' },
  { label: '请求头', value: 'headers' },
  { label: '查询参数', value: 'params' },
  { label: '请求体', value: 'body' },
  { label: '前置钩子', value: 'setup_hooks' },
  { label: '后置钩子', value: 'teardown_hooks' },
  { label: '变量定义', value: 'variables' },
  { label: '断言规则', value: 'validators' },
  { label: '提取变量', value: 'extract' }
]

const panelTabs = [
  { key: 'config', title: '配置管理' },
  { key: 'api-config', title: '接口同步配置' },
  { key: 'history', title: '同步历史' }
] as const

const columns: TableColumnData[] = [
  {
    title: '序号',
    width: 80,
    align: 'center',
    slotName: 'index'
  },
  {
    title: '配置名称',
    dataIndex: 'name',
    slotName: 'name'
  },
  {
    title: '同步字段',
    dataIndex: 'sync_fields',
    slotName: 'sync_fields'
  },
  {
    title: '同步模式',
    dataIndex: 'sync_mode_display'
  },
  {
    title: '状态',
    slotName: 'status'
  },
  {
    title: '创建信息',
    slotName: 'created_info'
  },
  {
    title: '操作',
    width: 100,
    slotName: 'operations'
  }
]

const fetchConfigs = async () => {
  if (!projectStore.currentProject?.id) {
    Message.error('请先选择项目')
    return
  }

  try {
    loading.value = true
    const { data } = await syncApi.getConfigs(projectStore.currentProject.id)
    configs.value = data.configs
    activeConfigId.value = data.active_config_id
  } catch (error) {
    Message.error('获取配置列表失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// 监听项目变化时重新获取配置列表
watch(() => projectStore.currentProject?.id, (newProjectId: number | undefined) => {
  if (newProjectId) {
    fetchConfigs()
  } else {
    configs.value = []
    activeConfigId.value = null
  }
})

const handleEdit = (record: SyncConfig) => {
  isEditing.value = true
  editingConfigId.value = record.id
  formModel.value = {
    name: record.name,
    description: record.description || '',
    sync_fields: record.sync_fields,
    sync_enabled: record.sync_enabled,
    sync_mode: record.sync_mode,
    is_active: record.is_active
  }
  showCreateModal.value = true
}

const handleSubmit = async () => {
  if (!projectStore.currentProject?.id) {
    Message.error('请先选择项目')
    return
  }

  try {
    loading.value = true
    const data = {
      project: projectStore.currentProject.id,
      name: formModel.value.name,
      description: formModel.value.description,
      sync_fields: formModel.value.sync_fields,
      sync_enabled: formModel.value.sync_enabled,
      sync_mode: formModel.value.sync_mode,
      is_active: formModel.value.is_active
    }

    if (isEditing.value && editingConfigId.value) {
      await syncApi.updateConfig(editingConfigId.value, data)
      Message.success('更新配置成功')
    } else {
      await syncApi.createConfig(data)
      Message.success('创建配置成功')
    }
    
    showCreateModal.value = false
    Object.assign(formModel, {
      name: '',
      description: '',
      sync_fields: [],
      sync_enabled: true,
      sync_mode: 'manual',
      is_active: false
    })
    isEditing.value = false
    editingConfigId.value = null
    await fetchConfigs()
  } catch (error: any) {
    if (error.errors) {
      const errorMessages = Object.values(error.errors).flat()
      Message.error(errorMessages.join(', '))
    } else {
      Message.error(isEditing.value ? '更新配置失败' : '创建配置失败')
    }
    console.error(error)
  } finally {
    loading.value = false
  }
}

const handleActivateConfig = async (configId: number) => {
  try {
    loading.value = true
    await syncApi.setActiveConfig(configId)
    Message.success('切换配置成功')
    await fetchConfigs()
  } catch (error) {
    Message.error('切换配置失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

const handleDelete = async (record: SyncConfig) => {
  Modal.warning({
    title: '确认删除',
    content: `确定要删除配置"${record.name}"吗？此操作不可恢复。`,
    okText: '确认删除',
    cancelText: '取消',
    async onOk() {
      try {
        loading.value = true
        await syncApi.deleteConfig(record.id)
        Message.success('删除配置成功')
        await fetchConfigs()
      } catch (error) {
        Message.error('删除配置失败')
        console.error(error)
      } finally {
        loading.value = false
      }
    }
  })
}

onMounted(() => {
  if (projectStore.currentProject?.id) {
    fetchConfigs()
  }
})
</script>

<template>
  <div class="sync-config-panel p-6 main-container" :class="isDarkTheme ? 'sync-config--dark' : 'sync-config--light'">
    <div class="custom-card p-6">
      <div class="flex items-center justify-between mb-6">
        <div class="flex items-center">
          <h1 class="text-2xl font-semibold panel-title">同步配置</h1>
          <div class="sync-tab-nav ml-8" role="tablist" aria-label="同步配置面板切换">
            <button
              v-for="tab in panelTabs"
              :key="tab.key"
              type="button"
              class="sync-tab-nav__item"
              :class="{ 'sync-tab-nav__item--active': activeTab === tab.key }"
              @click="activeTab = tab.key"
            >
              {{ tab.title }}
            </button>
          </div>
        </div>
        <div v-if="activeTab === 'config'" class="flex gap-2">
          <a-button 
            type="outline" 
            :loading="loading" 
            @click="showCreateModal = true"
          >
            <template #icon>
              <icon-plus />
            </template>
            新建配置
          </a-button>
        </div>
      </div>

      <div class="mt-4">
        <template v-if="activeTab === 'config'">
          <a-table
            :loading="loading"
            :data="configs"
            :columns="columns"
            :pagination="false"
            :bordered="true"
            :stripe="true"
            class="custom-table"
          >
            <template #empty>
              <div class="flex flex-col items-center justify-center py-8">
                <IconEmpty class="empty-icon w-12 h-12 mb-4" />
                <div class="empty-text mb-6">暂无同步配置</div>
                <a-button type="outline" @click="showCreateModal = true">
                  <template #icon>
                    <icon-plus />
                  </template>
                  新建配置
                </a-button>
              </div>
            </template>

            <template #name="{ record }">
              <div 
                class="config-name-card flex flex-col cursor-pointer p-1 rounded transition-all duration-200" 
                @click="handleEdit(record)"
              >
                <span class="font-medium config-name-link">{{ record.name }}</span>
                <span v-if="record.description" class="config-subtle-text text-sm">{{ record.description }}</span>
              </div>
            </template>

            <template #sync_fields="{ record }">
              <div class="flex flex-wrap gap-1">
                <a-tag 
                  v-for="field in record.sync_fields" 
                  :key="field"
                  color="arcoblue"
                  size="small"
                >
                  {{ fieldOptions.find(opt => opt.value === field)?.label }}
                </a-tag>
              </div>
            </template>

            <template #status="{ record }">
              <div class="flex gap-1">
                <a-tag v-if="record.is_current" color="arcoblue">当前配置</a-tag>
                <a-tag v-if="!record.sync_enabled" color="red">已禁用</a-tag>
              </div>
            </template>

            <template #created_info="{ record }">
              <div class="created-info flex flex-col gap-1 text-sm">
                <span>{{ pageText.createdBy }}：{{ record.created_by_info?.username || '-' }}</span>
                <span>{{ pageText.createdAt }}：{{ record.created_at ? new Date(record.created_at).toLocaleString() : '-' }}</span>
              </div>
            </template>

            <template #operations="{ record }">
              <div class="flex gap-2">
                <a-button
                  v-if="!record.is_current"
                  type="outline"
                  size="mini"
                  :loading="loading"
                  @click="handleActivateConfig(record.id)"
                >
                  设为当前配置
                </a-button>
                <a-button
                  v-if="!record.is_current"
                  type="outline"
                  status="danger"
                  size="mini"
                  :loading="loading"
                  @click="handleDelete(record)"
                >
                  <template #icon>
                    <icon-delete />
                  </template>
                </a-button>
              </div>
            </template>

            <template #index="{ rowIndex }">
              {{ rowIndex + 1 }}
            </template>
          </a-table>
        </template>
        <template v-else-if="activeTab === 'api-config'">
          <api-config />
        </template>
        <template v-else>
          <sync-history />
        </template>
      </div>

      <!-- 创建配置弹窗 -->
      <a-modal
        v-model:visible="showCreateModal"
        :title="isEditing ? '编辑配置' : '新建配置'"
        class="custom-card"
        @ok="handleSubmit"
        @cancel="() => {
          showCreateModal = false
          isEditing = false
          editingConfigId = null
          Object.assign(formModel, {
            name: '',
            description: '',
            sync_fields: [],
            sync_enabled: true,
            sync_mode: 'manual',
            is_active: false
          })
        }"
      >
        <a-form :model="formModel" layout="vertical">
          <a-form-item field="name" label="配置名称" required>
            <a-input
              v-model="formModel.name"
              placeholder="请输入配置名称"
              allow-clear
            />
          </a-form-item>

          <a-form-item field="description" label="配置描述">
            <a-textarea
              v-model="formModel.description"
              placeholder="请输入配置描述"
              allow-clear
            />
          </a-form-item>

          <a-form-item field="sync_fields" label="同步字段" required>
            <a-select
              v-model="formModel.sync_fields"
              placeholder="请选择同步字段"
              multiple
            >
              <a-option
                v-for="option in fieldOptions"
                :key="option.value"
                :value="option.value"
                :label="option.label"
              />
            </a-select>
          </a-form-item>

          <a-form-item field="sync_mode" label="同步模式" required>
            <a-radio-group v-model="formModel.sync_mode">
              <a-radio value="manual">手动同步</a-radio>
              <a-radio value="auto">自动同步</a-radio>
            </a-radio-group>
          </a-form-item>

          <div class="flex justify-between items-center mt-4 pt-4 border-t border-gray-700">
            <a-checkbox v-model="formModel.sync_enabled">
              <template #default>
                <span class="modal-text">启用同步</span>
              </template>
            </a-checkbox>
            <a-checkbox v-model="formModel.is_active">
              <template #default>
                <span class="modal-text">设为当前配置</span>
              </template>
            </a-checkbox>
          </div>
        </a-form>
      </a-modal>
    </div>
  </div>
</template>

<style scoped>
@reference "tailwindcss";
.sync-config-panel {
  --sync-shell-bg: color-mix(in srgb, var(--theme-card-bg) 92%, var(--theme-page-bg) 8%);
  --sync-shell-border: rgba(148, 163, 184, 0.16);
  --sync-shell-shadow: 0 14px 30px rgba(15, 23, 42, 0.08);
  --sync-table-header-bg: color-mix(in srgb, var(--theme-card-bg) 76%, var(--theme-page-bg) 24%);
  --sync-table-row-bg: color-mix(in srgb, var(--theme-card-bg) 90%, var(--theme-page-bg) 10%);
  --sync-table-row-hover: rgba(15, 23, 42, 0.05);
  --sync-input-bg: #ffffff;
  --sync-input-border: rgba(148, 163, 184, 0.18);
  --sync-input-hover-bg: color-mix(in srgb, var(--theme-card-bg) 88%, var(--theme-page-bg) 12%);
  --sync-text: var(--theme-text);
  --sync-text-muted: var(--theme-text-secondary);
  --sync-text-subtle: var(--theme-text-tertiary);
}

.sync-config--dark {
  --sync-shell-bg: rgba(31, 41, 55, 0.92);
  --sync-shell-border: rgba(55, 65, 81, 0.72);
  --sync-shell-shadow: 0 18px 34px rgba(2, 6, 23, 0.28);
  --sync-table-header-bg: rgba(3, 7, 18, 0.8);
  --sync-table-row-bg: rgba(31, 41, 55, 1);
  --sync-table-row-hover: rgba(55, 65, 81, 0.72);
  --sync-input-bg: rgba(55, 65, 81, 1);
  --sync-input-border: rgba(75, 85, 99, 1);
  --sync-input-hover-bg: rgba(55, 65, 81, 0.92);
}

.main-container {
  height: 100%;
  overflow-y: auto;
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE and Edge */
}

.main-container::-webkit-scrollbar {
  display: none; /* Chrome, Safari, Opera */
}

:deep(.arco-form-item-label-col),
:deep(.arco-form-item-label-col > label),
:deep(.arco-form-item-label) {
  color: var(--sync-text) !important;
}

:deep(.arco-form-item-label-col) {
  color: var(--sync-text) !important;
}

:deep(.arco-radio) {
  color: var(--sync-text) !important;
}

:deep(.arco-checkbox) {
  color: var(--sync-text) !important;
}

:deep(.arco-input-wrapper),
:deep(.arco-textarea-wrapper),
:deep(.arco-select-view) {
  background: var(--sync-input-bg) !important;
  border-color: var(--sync-input-border) !important;
}

:deep(.arco-input-wrapper:hover),
:deep(.arco-textarea-wrapper:hover),
:deep(.arco-select-view:hover),
:deep(.arco-input-wrapper:focus-within),
:deep(.arco-textarea-wrapper:focus-within),
:deep(.arco-select-view:focus-within) {
  border-color: rgba(var(--theme-accent-rgb), 0.42) !important;
  background: var(--sync-input-hover-bg) !important;
}

:deep(.arco-input) {
  color: var(--sync-text) !important;
}

:deep(.arco-textarea),
:deep(.arco-select-view-value),
:deep(.arco-input::placeholder),
:deep(.arco-textarea::placeholder),
:deep(.arco-select-view-placeholder) {
  color: var(--sync-text-subtle) !important;
}

:deep(.arco-textarea),
:deep(.arco-select-view-value) {
  color: var(--sync-text) !important;
}

:deep(.arco-modal) {
  background: var(--sync-shell-bg);
}

:deep(.arco-modal-header) {
  background: var(--sync-shell-bg);
  border-color: var(--sync-shell-border);
}

:deep(.arco-modal-title) {
  color: var(--sync-text);
}

:deep(.arco-modal-footer) {
  background: var(--sync-shell-bg);
  border-color: var(--sync-shell-border);
}

:deep(.custom-table) {
  background: transparent;
  border-radius: 0.5rem;
  overflow: hidden;
  border: 1px solid var(--sync-shell-border);
}

:deep(.custom-table .arco-table-container) {
  border-color: var(--sync-shell-border);
}

:deep(.custom-table .arco-table-th) {
  background: var(--sync-table-header-bg);
  color: var(--sync-text);
  border-color: var(--sync-shell-border);
  font-weight: 500;
  font-size: 0.875rem;
}

:deep(.custom-table .arco-table-th .arco-table-th-cell) {
  @apply py-4;
}

:deep(.custom-table .arco-table-th:first-child) {
  @apply rounded-tl-lg;
}

:deep(.custom-table .arco-table-th:last-child) {
  @apply rounded-tr-lg;
}

:deep(.custom-table .arco-table-tr:last-child .arco-table-td:first-child) {
  @apply rounded-bl-lg;
}

:deep(.custom-table .arco-table-tr:last-child .arco-table-td:last-child) {
  @apply rounded-br-lg;
}

:deep(.custom-table .arco-table-td) {
  background: var(--sync-table-row-bg);
  color: var(--sync-text-muted);
  border-color: var(--sync-shell-border);
}

:deep(.custom-table .arco-table-tr:hover .arco-table-td) {
  background: var(--sync-table-row-hover);
}

:deep(.custom-table .arco-table-border-cell .arco-table-td) {
  border-color: var(--sync-shell-border);
}

/* 隐藏默认滚动条 */
:deep(.arco-table-body) {
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE and Edge */
  &::-webkit-scrollbar {
    display: none; /* Chrome, Safari, Opera */
  }
}

:deep(.arco-table-header) {
  scrollbar-width: none;
  -ms-overflow-style: none;
  &::-webkit-scrollbar {
    display: none;
  }
}

:deep(.arco-modal-body) {
  scrollbar-width: none;
  -ms-overflow-style: none;
  &::-webkit-scrollbar {
    display: none;
  }
}

.custom-card {
  background: var(--sync-shell-bg);
  border-radius: 0.5rem;
  box-shadow: var(--sync-shell-shadow);
  border: 1px solid var(--sync-shell-border);
}

.panel-title,
.modal-text {
  color: var(--sync-text);
}

.empty-icon,
.empty-text,
.config-subtle-text,
.created-info {
  color: var(--sync-text-subtle);
}

.config-name-card:hover {
  background: rgba(var(--theme-accent-rgb), 0.08);
}

.config-name-link {
  color: var(--theme-accent);
}

.config-name-link:hover {
  color: var(--theme-accent-hover);
}

.sync-tab-nav {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.sync-tab-nav__item {
  border: none;
  background: transparent;
  color: var(--sync-text-subtle);
  padding: 0 0.75rem;
  min-height: 28px;
  line-height: 1;
  cursor: pointer;
  border-radius: 999px;
  transition: color 0.2s ease, background-color 0.2s ease;
}

.sync-tab-nav__item:hover {
  color: var(--sync-text);
  background: rgba(var(--theme-accent-rgb), 0.08);
}

.sync-tab-nav__item--active {
  color: var(--theme-accent);
  background: rgba(var(--theme-accent-rgb), 0.12);
  font-weight: 500;
}
</style> 