<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue'
import { useProjectStore } from '@/store/projectStore'
import { useThemeStore } from '@/store/themeStore'
import { Message } from '@arco-design/web-vue'
import { moduleService } from '../../services/moduleService'
import { interfaceService } from '../../services/interfaceService'
import { toArray } from '../../services/responseHelpers'
import type { ApiInterface } from '../../types/interface'
import type { ApiModule } from '../../types/module'
import ApiSelectDialogHeader from './ApiSelectDialogHeader.vue'
import ModuleList from './ModuleList.vue'
import InterfaceList from './InterfaceList.vue'
import InterfacePagination from './InterfacePagination.vue'

const props = defineProps<{
  visible: boolean
  testCaseId?: number
  testCase?: {
    name: string
    priority: string
    project: number
    description?: string
    group?: number
    tags?: number[]
    config?: {
      base_url: string
      variables: string | Record<string, any>
      parameters: string | Record<string, any>
      export: string | string[]
      verify?: boolean
    }
  }
}>()

const emit = defineEmits(['update:visible', 'select'])

const loading = ref(false)
const selectedModuleId = ref<number>()
const expandedModuleIds = ref<number[]>([])

const modules = ref<ApiModule[]>([])
const currentModule = ref<ApiModule | null>(null)
const interfaces = ref<ApiInterface[]>([])
const selectedKeys = ref<number[]>([])

const pagination = ref({
  current: 1,
  pageSize: 10,
  total: 0
})

const projectStore = useProjectStore()
const themeStore = useThemeStore()
const isDarkTheme = computed(() => themeStore.isBlack)

const loadModules = async () => {
  if (!projectStore.currentProjectId) {
    console.error('No project selected')
    return
  }

  loading.value = true
  modules.value = []

  try {
    const res = await moduleService.tree(projectStore.currentProjectId)
    if (res.success && res.data) {
      modules.value = toArray<ApiModule>((res.data as any)?.results ?? res.data)
    }
  } catch (error) {
    console.error('Failed to load modules:', error)
    Message.error('加载模块列表失败')
  } finally {
    loading.value = false
  }
}

const loadModuleInterfaces = async (moduleId: number, page = 1) => {
  if (!projectStore.currentProjectId) {
    Message.error('未选择项目')
    return
  }

  loading.value = true
  if (page === 1) {
    interfaces.value = []
    selectedKeys.value = []
  }

  try {
    const res = await interfaceService.list(projectStore.currentProjectId, {
      module_id: moduleId,
      page: page,
      page_size: pagination.value.pageSize
    })
    if (res.success && res.data) {
      interfaces.value = toArray<ApiInterface>((res.data as any)?.results ?? res.data)
      pagination.value.total = (res.data as any).count || interfaces.value.length
      pagination.value.current = page
    }
  } catch (error) {
    console.error('Failed to load interfaces:', error)
    Message.error('加载接口列表失败')
  } finally {
    loading.value = false
  }
}

const handlePageChange = (page: number) => {
  if (currentModule.value) {
    loadModuleInterfaces(currentModule.value.id, page)
  }
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.value.pageSize = pageSize
  if (currentModule.value) {
    loadModuleInterfaces(currentModule.value.id, 1)
  }
}

const handleToggleExpand = (moduleId: number) => {
  const index = expandedModuleIds.value.indexOf(moduleId)
  if (index === -1) {
    expandedModuleIds.value.push(moduleId)
  } else {
    expandedModuleIds.value.splice(index, 1)
  }
}

const handleModuleSelect = async (mod: ApiModule) => {
  try {
    loading.value = true
    selectedModuleId.value = mod.id
    currentModule.value = mod
    selectedKeys.value = []
    await loadModuleInterfaces(mod.id)
  } catch (error) {
    console.error('Failed to load module interfaces:', error)
    selectedModuleId.value = undefined
    currentModule.value = null
  } finally {
    loading.value = false
  }
}

const handleConfirm = () => {
  if (selectedKeys.value.length === 0) {
    Message.warning('请至少选择一个接口')
    return
  }

  const selectedInterfaces = interfaces.value.filter(api => selectedKeys.value.includes(api.id!))
  emit('select', selectedInterfaces)
  selectedKeys.value = []
  emit('update:visible', false)
}

const handleSelectionChange = (keys: number[]) => {
  selectedKeys.value = keys.map(k => Number(k))
}

const handleRowClick = (record: ApiInterface) => {
  const id = record.id!
  const index = selectedKeys.value.indexOf(id)
  if (index === -1) {
    selectedKeys.value = [...selectedKeys.value, id]
  } else {
    selectedKeys.value = selectedKeys.value.filter(key => key !== id)
  }
}

const handleClose = () => {
  emit('update:visible', false)
}

const resetDialogState = () => {
  selectedKeys.value = []
  interfaces.value = []
  currentModule.value = null
  selectedModuleId.value = undefined
  expandedModuleIds.value = []
  pagination.value = {
    current: 1,
    pageSize: 10,
    total: 0
  }
}

watch(() => props.visible, async (newVal, oldVal) => {
  if (newVal && !oldVal) {
    resetDialogState()
    await nextTick()
    loadModules()
  } else if (!newVal && oldVal) {
    resetDialogState()
  }
}, { immediate: false })

const handleVisibleChange = (value: boolean) => {
  if (!value) {
    emit('update:visible', false)
  }
}
</script>

<template>
  <a-modal
    :visible="visible"
    width="min(1000px, calc(100vw - 64px))"
    :mask-closable="false"
    :footer="false"
    hide-title
    :closable="false"
    class="api-select-dialog-container"
    modal-class="api-select-dialog-modal"
    body-class="api-select-dialog-body"
    unmount-on-close
    @update:visible="handleVisibleChange"
    @cancel="handleClose"
  >
    <div class="api-select-dialog" :class="isDarkTheme ? 'api-select-dialog--dark' : 'api-select-dialog--light'">
      <div class="api-select-dialog-layout">
        <ApiSelectDialogHeader @close="handleClose" />

        <div class="api-select-dialog-content">
          <ModuleList
            :modules="modules"
            :expanded-ids="expandedModuleIds"
            :selected-id="selectedModuleId"
            :loading="loading"
            @select="handleModuleSelect"
            @toggle-expand="handleToggleExpand"
          />

          <div class="api-select-dialog-main">
            <InterfaceList
              :interfaces="interfaces"
              :selected-keys="selectedKeys"
              :loading="loading"
              :current-module-name="currentModule?.name"
              @selection-change="handleSelectionChange"
              @row-click="handleRowClick"
              @confirm="handleConfirm"
            />

            <InterfacePagination
              :current="pagination.current"
              :page-size="pagination.pageSize"
              :total="pagination.total"
              @change="handlePageChange"
              @page-size-change="handlePageSizeChange"
            />
          </div>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<style scoped>
@reference "tailwindcss";
.api-select-dialog {
  @apply bg-transparent p-6;
  box-sizing: border-box;
  height: min(640px, calc(100vh - 96px));
  color: var(--asd-text-muted);
  --asd-panel-bg: #ffffff;
  --asd-panel-border: rgba(148, 163, 184, 0.16);
  --asd-panel-hover: rgba(148, 163, 184, 0.08);
  --asd-control-bg: #ffffff;
  --asd-control-border: rgba(148, 163, 184, 0.28);
  --asd-control-hover: #f8fafc;
  --asd-text: var(--theme-text);
  --asd-text-muted: var(--theme-text-secondary);
  --asd-text-subtle: var(--theme-text-tertiary);
}

.api-select-dialog-layout {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  gap: 16px;
}

.api-select-dialog-content {
  display: flex;
  flex: 1;
  min-height: 0;
  gap: 16px;
}

.api-select-dialog-main {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: 16px;
}

.api-select-dialog--dark {
  --asd-panel-bg: rgb(31, 41, 55);
  --asd-panel-border: rgba(75, 85, 99, 0.4);
  --asd-panel-hover: rgba(51, 65, 85, 0.5);
  --asd-control-bg: rgba(15, 23, 42, 0.7);
  --asd-control-border: rgba(75, 85, 99, 0.45);
  --asd-control-hover: rgba(31, 41, 55, 0.92);
  --asd-text: rgb(241, 245, 249);
  --asd-text-muted: rgb(203, 213, 225);
  --asd-text-subtle: rgb(148, 163, 184);
}

:global(.api-select-dialog-modal.arco-modal) {
  background: transparent !important;
  border: 0 !important;
  box-shadow: none !important;
}

:global(.api-select-dialog-container .arco-modal-wrapper) {
  overflow: hidden !important;
}

:global(.api-select-dialog-body.arco-modal-body) {
  background: transparent !important;
  padding: 0 !important;
  overflow: visible !important;
}

:global(body.api-testing-theme .api-select-dialog-modal.arco-modal) {
  background: transparent !important;
  border: 0 !important;
  box-shadow: none !important;
}
</style>
