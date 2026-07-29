<script setup lang="ts">
import { computed, onMounted, provide, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import {
  IconCopy,
  IconDelete,
  IconEdit,
  IconFolder,
  IconList,
  IconPlus,
  IconSearch,
  IconSend
} from '@arco-design/web-vue/es/icon'
import { useProjectStore } from '@/store/projectStore'
import { useThemeStore } from '@/store/themeStore'
import { useAppI18n } from '@/composables/useAppI18n'
import { useEnvironmentStore } from '../../stores/environmentStore'
import { useApiTabsStore } from '../../stores/apiTabsStore'
import { moduleService } from '../../services/moduleService'
import { interfaceService } from '../../services/interfaceService'
import { interfaceCaseService } from '../../services/interfaceCaseService'
import type { ApiModule, ApiInterface } from '../../services/interfaceService'
import type { ApiInterfaceCase } from '../../types/interfaceCase'
import TestCaseSearch from '../testcases/TestCaseSearch.vue'
import TestCaseFilter from '../testcases/TestCaseFilter.vue'
import ModuleTree from '../interfaces/ModuleTree.vue'
import ModuleForm from '../interfaces/ModuleForm.vue'
import InterfaceCaseTable from './InterfaceCaseTable.vue'
import { showExtractPersistenceNotice } from '../../utils/extractPersistence'

interface QueryParams {
  name?: string
  description?: string
  priority?: string
  group?: number
  tags?: number[]
  interface_id?: number
  module_id?: number
  no_module?: boolean
  ordering?: string
  page?: number
  page_size?: number
}

const projectStore = useProjectStore()
const environmentStore = useEnvironmentStore()
const apiTabsStore = useApiTabsStore()
const themeStore = useThemeStore()
const router = useRouter()
const { isEnglish, tl } = useAppI18n()

const loading = ref(false)
const treeLoading = ref(false)
const formLoading = ref(false)
const modules = ref<ApiModule[]>([])
const interfaces = ref<ApiInterface[]>([])
const interfaceCases = ref<ApiInterfaceCase[]>([])
const expandedModuleIds = ref<number[]>([])
const selectedInterface = ref<ApiInterface | null>(null)
const selectedModule = ref<ApiModule | null>(null)
const selectedNoModuleScope = ref(false)
const searchKeyword = ref('')
const formVisible = ref(false)
const formType = ref<'create' | 'edit'>('create')
const formParentId = ref<number | undefined>()
const currentModule = ref<ApiModule | undefined>()
const isDarkTheme = computed(() => themeStore.isBlack)

const draggingModule = ref<ApiModule | null>(null)
const dragOverModule = ref<ApiModule | null>(null)
const dragOverPosition = ref<number | null>(null)
provide('draggingModule', draggingModule)
provide('dragOverModule', dragOverModule)
provide('dragOverPosition', dragOverPosition)

const queryParams = reactive<QueryParams>({
  name: '',
  description: '',
  priority: undefined,
  group: undefined,
  tags: undefined,
  interface_id: undefined,
  ordering: '-created_at',
  page: 1,
  page_size: 10
})

const pagination = reactive({
  current: 1,
  page_size: 10,
  total: 0
})

const noModuleInterfaces = computed(() =>
  interfaces.value
    .filter(api => !api.module)
    .sort((a, b) => a.name.localeCompare(b.name))
)
const hasNoModuleInterfaces = computed(() => noModuleInterfaces.value.length > 0)
const filteredModules = computed(() => {
  if (!searchKeyword.value) return modules.value
  const keyword = searchKeyword.value.toLowerCase()
  const filterModules = (items: ApiModule[]): ApiModule[] => items.reduce((result: ApiModule[], module) => {
    const children = module.children ? filterModules(module.children) : []
    if (module.name.toLowerCase().includes(keyword) || children.length > 0) {
      result.push({ ...module, children })
    }
    return result
  }, [])
  return filterModules(modules.value)
})

const currentScopeLabel = computed(() => {
  if (selectedInterface.value) return selectedInterface.value.name
  if (selectedModule.value) return selectedModule.value.name
  if (selectedNoModuleScope.value) return tl('未选择模块接口')
  return tl('全部接口用例')
})

const loadTreeData = async () => {
  if (!projectStore.currentProjectId) return
  try {
    treeLoading.value = true
    const [moduleRes, interfaceRes] = await Promise.all([
      moduleService.tree(projectStore.currentProjectId),
      interfaceService.list(projectStore.currentProjectId, { page_size: 1000 })
    ])
    modules.value = moduleRes.success && moduleRes.data
      ? (Array.isArray(moduleRes.data) ? moduleRes.data : (moduleRes.data as any).results || [])
      : []
    interfaces.value = interfaceRes.success && interfaceRes.data
      ? (Array.isArray(interfaceRes.data) ? interfaceRes.data : (interfaceRes.data as any).results || [])
      : []
    if (expandedModuleIds.value.length === 0) {
      expandedModuleIds.value = modules.value.map(item => item.id)
    }
  } catch (error) {
    console.error('加载接口树失败:', error)
    Message.error(tl('加载接口列表失败'))
  } finally {
    treeLoading.value = false
  }
}

const fetchInterfaceCases = async (page = 1) => {
  if (!projectStore.currentProjectId) return
  try {
    loading.value = true
    queryParams.page = page
    queryParams.page_size = pagination.page_size
    queryParams.interface_id = selectedInterface.value?.id
    queryParams.module_id = !selectedInterface.value && selectedModule.value ? selectedModule.value.id : undefined
    queryParams.no_module = !selectedInterface.value && selectedNoModuleScope.value ? true : undefined

    const res = await interfaceCaseService.list(projectStore.currentProjectId, queryParams)
    if (res.success && res.data) {
      interfaceCases.value = Array.isArray(res.data) ? res.data : (res.data as any).results || []
      pagination.total = (res.data as any).count || interfaceCases.value.length
      pagination.current = page
    } else {
      throw new Error(res.error || tl('获取接口用例列表失败'))
    }
  } catch (error) {
    console.error('获取接口用例列表失败:', error)
    Message.error(error instanceof Error ? error.message : tl('获取接口用例列表失败'))
    interfaceCases.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

const handleToggleExpand = async (moduleId: number) => {
  const index = expandedModuleIds.value.indexOf(moduleId)
  if (index === -1) {
    expandedModuleIds.value.push(moduleId)
  } else {
    expandedModuleIds.value.splice(index, 1)
  }
}

const handleSelectModule = (module: ApiModule) => {
  selectedModule.value = module
  selectedInterface.value = null
  selectedNoModuleScope.value = false
  if (!expandedModuleIds.value.includes(module.id)) {
    expandedModuleIds.value.push(module.id)
  }
  pagination.current = 1
  fetchInterfaceCases(1)
}

const handleSelectInterface = (api: ApiInterface) => {
  selectedInterface.value = api
  selectedModule.value = null
  selectedNoModuleScope.value = !api.module
  pagination.current = 1
  fetchInterfaceCases(1)
}

const handleSelectNoModuleScope = () => {
  selectedInterface.value = null
  selectedModule.value = null
  selectedNoModuleScope.value = true
  expandedModuleIds.value = []
  pagination.current = 1
  fetchInterfaceCases(1)
}

const handleShowAll = () => {
  selectedInterface.value = null
  selectedModule.value = null
  selectedNoModuleScope.value = false
  pagination.current = 1
  fetchInterfaceCases(1)
}

const handleSearch = () => {
  pagination.current = 1
  fetchInterfaceCases(1)
}

const handleReset = () => {
  Object.assign(queryParams, {
    name: '',
    description: '',
    priority: undefined,
    group: undefined,
    tags: undefined,
    ordering: '-created_at',
    page: 1,
    page_size: pagination.page_size
  })
  pagination.current = 1
  fetchInterfaceCases(1)
}

const handleSortChange = (dataIndex: string, direction: string) => {
  queryParams.ordering = direction === 'ascend' ? dataIndex : `-${dataIndex}`
  fetchInterfaceCases(1)
}

const updateSearchParams = (data: Pick<QueryParams, 'name' | 'description'>) => {
  Object.assign(queryParams, data)
}

const updateFilterParams = (data: Pick<QueryParams, 'priority' | 'group' | 'tags'>) => {
  Object.assign(queryParams, data)
}

const handleCreate = () => {
  router.push({
    name: 'ApiInterfaceCaseCreate',
    query: {
      tab: 'interface-cases',
      ...(selectedInterface.value ? { interface_id: String(selectedInterface.value.id) } : {})
    }
  })
}

const handleEdit = (record: ApiInterfaceCase) => {
  router.push({
    name: 'ApiInterfaceCaseEdit',
    params: { id: record.id },
    query: { tab: 'interface-cases' }
  })
}

const handleRun = async (record: ApiInterfaceCase) => {
  if (!environmentStore.currentEnvironmentId) {
    Message.warning(tl('请先选择环境'))
    return
  }
  if (!projectStore.currentProjectId) return
  try {
    loading.value = true
    const res = await interfaceCaseService.run(projectStore.currentProjectId, record.id, {
      environment_id: Number(environmentStore.currentEnvironmentId)
    })
    if (res.success) {
      showExtractPersistenceNotice((res.data as any)?.extract_persistence)
      Message.success(tl('接口用例运行成功'))
    } else {
      throw new Error(res.error || tl('运行接口用例失败'))
    }
  } catch (error) {
    console.error('运行接口用例失败:', error)
    Message.error(error instanceof Error ? error.message : tl('运行接口用例失败'))
  } finally {
    loading.value = false
  }
}

const handleReport = async (record: ApiInterfaceCase) => {
  if (!projectStore.currentProjectId) return
  const res = await interfaceCaseService.historyReports(projectStore.currentProjectId, record.id, {
    page: 1,
    page_size: 1
  })
  if (!res.success || !res.data) {
    Message.error(tl('获取报告失败'))
    return
  }
  const reports = Array.isArray(res.data) ? res.data : (res.data as any).results || []
  if (!reports.length) {
    Message.warning(tl('该接口用例暂无报告，请先运行测试'))
    return
  }
  router.push({
    name: 'ApiInterfaceCaseReportDetail',
    params: { id: reports[0].id },
    query: { tab: 'interface-cases', returnTo: 'interfaceCases' }
  })
}

const handleCopy = async (record: ApiInterfaceCase) => {
  if (!projectStore.currentProjectId) return
  try {
    loading.value = true
    const res = await interfaceCaseService.copy(projectStore.currentProjectId, record.id)
    if (res.success) {
      Message.success(tl('接口用例复制成功'))
      await fetchInterfaceCases(pagination.current)
    } else {
      throw new Error(res.error || tl('复制接口用例失败'))
    }
  } catch (error) {
    Message.error(error instanceof Error ? error.message : tl('复制接口用例失败'))
  } finally {
    loading.value = false
  }
}

const handleDelete = async (record: ApiInterfaceCase) => {
  if (!projectStore.currentProjectId) return
  Modal.confirm({
    title: tl('确认删除'),
    content: isEnglish.value
      ? `Delete interface case "${record.name}"? Preconditions and execution records will also be deleted. This cannot be undone.`
      : `确定要删除接口用例「${record.name}」吗？删除后将同时删除前置条件和执行记录，且无法恢复。`,
    okText: tl('确认删除'),
    cancelText: tl('取消'),
    okButtonProps: { status: 'danger' },
    async onOk() {
      if (!projectStore.currentProjectId) return
      await interfaceCaseService.delete(projectStore.currentProjectId, record.id)
      Message.success(tl('接口用例删除成功'))
      await fetchInterfaceCases(pagination.current)
    }
  })
}

const handleOpenCreateModuleForm = (parentId?: number) => {
  formType.value = 'create'
  formParentId.value = parentId
  currentModule.value = undefined
  formVisible.value = true
}

const handleOpenEditModuleForm = (module: ApiModule) => {
  formType.value = 'edit'
  formParentId.value = undefined
  currentModule.value = module
  formVisible.value = true
}

const handleModuleFormSubmit = async (formData: any) => {
  if (!projectStore.currentProjectId) {
    Message.warning(tl('请先选择项目'))
    return
  }
  try {
    formLoading.value = true
    if (formType.value === 'create') {
      await moduleService.create(projectStore.currentProjectId, {
        ...formData,
        project: projectStore.currentProjectId
      })
      Message.success(tl('创建模块成功'))
    } else if (currentModule.value) {
      await moduleService.update(projectStore.currentProjectId, currentModule.value.id, formData)
      Message.success(tl('更新模块成功'))
    }
    formVisible.value = false
    await loadTreeData()
  } catch (error) {
    Message.error(error instanceof Error ? error.message : tl('保存模块失败'))
  } finally {
    formLoading.value = false
  }
}

const handleDeleteModule = (module: ApiModule) => {
  if (!projectStore.currentProjectId) return
  Modal.confirm({
    title: tl('确认删除'),
    content: isEnglish.value
      ? `Delete module "${module.name}"? All interfaces in this module will also be deleted, and this action cannot be undone.`
      : `确定要删除模块"${module.name}"吗？删除后将同时删除该模块下的所有接口，且不可恢复。`,
    okText: tl('确定'),
    cancelText: tl('取消'),
    okButtonProps: { status: 'danger' },
    async onOk() {
      if (!projectStore.currentProjectId) return
      await moduleService.delete(projectStore.currentProjectId, module.id)
      Message.success(tl('删除模块成功'))
      if (selectedModule.value?.id === module.id) {
        selectedModule.value = null
        selectedInterface.value = null
        selectedNoModuleScope.value = false
      }
      await loadTreeData()
      await fetchInterfaceCases(1)
    }
  })
}

const handleModuleDrop = async (dragged: ApiModule, target: ApiModule, position: number) => {
  if (!projectStore.currentProjectId || dragged.id === target.id) return
  await moduleService.move(projectStore.currentProjectId, dragged.id, {
    target_id: target.id,
    drop_position: position
  })
  await loadTreeData()
}

provide('handleModuleDrop', handleModuleDrop)

const openInterfacesTab = (api?: ApiInterface) => {
  if (api) {
    apiTabsStore.openOrActivateInterface(api)
  } else {
    apiTabsStore.createTab()
  }
  router.push({ path: '/api-testing', query: { tab: 'interfaces' } })
}

const handleCreateInterface = () => {
  openInterfacesTab()
}

const handleEditInterface = (api: ApiInterface) => {
  openInterfacesTab(api)
}

const handleRunInterface = async (api: ApiInterface) => {
  if (!environmentStore.currentEnvironmentId) {
    Message.warning(tl('请先选择环境'))
    return
  }
  if (!projectStore.currentProjectId || !api.id) return
  const res = await interfaceService.run(projectStore.currentProjectId, api.id, {
    environment_id: Number(environmentStore.currentEnvironmentId)
  })
  if (res.success) {
    showExtractPersistenceNotice((res.data as any)?.extract_persistence)
    Message.success(tl('接口运行成功'))
  } else {
    Message.error(res.error || tl('接口运行失败'))
  }
}

const handleCopyInterface = async (api: ApiInterface) => {
  if (!projectStore.currentProjectId || !api.id) return
  const res = await interfaceService.duplicate(projectStore.currentProjectId, api.id)
  if (res.success) {
    Message.success(tl('接口复制成功'))
    await loadTreeData()
  } else {
    Message.error(res.error || tl('复制接口失败'))
  }
}

const handleDeleteInterface = (api: ApiInterface) => {
  if (!projectStore.currentProjectId || !api.id) return
  Modal.confirm({
    title: tl('确认删除'),
    content: isEnglish.value
      ? `Delete interface "${api.name}"? This action cannot be undone.`
      : `确定要删除接口"${api.name}"吗？删除后不可恢复。`,
    okText: tl('确定'),
    cancelText: tl('取消'),
    okButtonProps: { status: 'danger' },
    async onOk() {
      if (!projectStore.currentProjectId || !api.id) return
      await interfaceService.delete(projectStore.currentProjectId, api.id)
      Message.success(tl('删除接口成功'))
      if (selectedInterface.value?.id === api.id) {
        handleShowAll()
      }
      await loadTreeData()
    }
  })
}

const handlePageChange = (page: number) => {
  pagination.current = page
  fetchInterfaceCases(page)
}

const handlePageSizeChange = (size: number) => {
  pagination.page_size = size
  pagination.current = 1
  fetchInterfaceCases(1)
}

watch(() => projectStore.currentProjectId, async (projectId) => {
  if (!projectId) return
  selectedInterface.value = null
  await loadTreeData()
  await fetchInterfaceCases(1)
}, { immediate: true })

onMounted(() => {
  if (projectStore.currentProjectId) {
    loadTreeData()
  }
})
</script>

<template>
  <div class="api-management interface-cases-panel h-full flex p-2 gap-2" :class="isDarkTheme ? 'api-management--dark api-testcases--dark' : 'api-management--light api-testcases--light'">
    <div class="w-80 flex flex-col">
      <div class="flex-1 bg-gray-800 rounded-lg shadow-lg overflow-hidden flex flex-col">
        <div class="p-4 border-b border-gray-700/50 flex-shrink-0">
          <div class="flex justify-between items-center mb-4">
            <h2 class="text-lg font-medium text-gray-100">{{ tl('模块列表') }}</h2>
            <div class="flex items-center gap-2">
              <a-button type="text" size="small" @click="handleShowAll" :title="tl('显示全部接口用例')">
                <template #icon><icon-list /></template>
              </a-button>
              <a-button type="text" size="small" @click="handleOpenCreateModuleForm()">
                <template #icon><icon-plus /></template>
                {{ tl('模块') }}
              </a-button>
            </div>
          </div>
          <a-input-search
            v-model="searchKeyword"
            :placeholder="tl('搜索模块...')"
            allow-clear
          >
            <template #prefix>
              <icon-search />
            </template>
          </a-input-search>
        </div>

        <div class="flex-1 min-h-0 overflow-hidden">
          <a-spin :loading="treeLoading" dot class="!block h-full">
            <div class="h-full overflow-y-auto scrollbar-hide">
              <div class="py-2">
                <a-empty v-if="filteredModules.length === 0 && !hasNoModuleInterfaces" class="p-4">
                  {{ tl('暂无模块数据') }}
                </a-empty>
                <template v-else>
                  <div class="space-y-1.5 m-2">
                    <div v-if="hasNoModuleInterfaces" class="mb-3">
                      <div
                        class="flex items-center justify-between px-3 py-2 rounded-md cursor-pointer hover:bg-gray-700/30"
                        :class="{ 'bg-gray-700/50': selectedNoModuleScope }"
                        @click="handleSelectNoModuleScope"
                      >
                        <div class="flex items-center gap-2">
                          <icon-folder class="text-gray-400" />
                          <span class="text-gray-100 font-medium">{{ tl('未选择模块接口') }}</span>
                          <a-tag size="small" type="arcoblue">{{ noModuleInterfaces.length }}</a-tag>
                        </div>
                        <div class="flex items-center">
                          <a-button type="text" size="mini" @click.stop="handleCreateInterface">
                            <template #icon><icon-plus /></template>
                          </a-button>
                        </div>
                      </div>

                      <div v-if="selectedNoModuleScope" class="mt-1">
                        <a-spin :loading="treeLoading" dot>
                          <div class="flex flex-col px-4">
                            <div
                              v-for="api in noModuleInterfaces"
                              :key="api.id"
                              class="no-module-interface-item !w-full !px-6 !py-2 !text-sm !text-gray-400 hover:!text-gray-300 !rounded !bg-[rgb(70,84,102,0.2)] hover:!bg-[rgb(70,84,102,0.4)] !min-w-0 !cursor-pointer !mt-1"
                              :class="{ '!bg-[rgb(70,84,102,0.4)]': selectedInterface?.id === api.id }"
                              @click="handleSelectInterface(api)"
                            >
                              <div class="no-module-interface-main">
                                <div class="no-module-interface-info">
                                  <a-tag
                                    :color="api.method === 'GET' ? 'blue' : api.method === 'POST' ? 'green' : api.method === 'PUT' ? 'orange' : 'red'"
                                    class="!w-16 !flex !justify-center !flex-shrink-0"
                                  >
                                    {{ api.method || api.sql_method }}
                                  </a-tag>
                                  <span class="no-module-interface-name !truncate" :title="api.name">{{ api.name }}</span>
                                </div>
                                <div class="no-module-interface-actions">
                                  <a-button type="text" size="mini" class="!p-0 !text-[#6b7785] hover:!text-[#86909c]" @click.stop="handleRunInterface(api)" :title="tl('调试接口')">
                                    <template #icon><icon-send /></template>
                                  </a-button>
                                  <a-button type="text" size="mini" class="!p-0 !text-[#6b7785] hover:!text-[#86909c]" @click.stop="handleEditInterface(api)" :title="tl('编辑接口')">
                                    <template #icon><icon-edit /></template>
                                  </a-button>
                                  <a-button type="text" size="mini" class="!p-0 !text-[#6b7785] hover:!text-[#86909c]" @click.stop="handleCopyInterface(api)" :title="tl('复制接口')">
                                    <template #icon><icon-copy /></template>
                                  </a-button>
                                  <a-button type="text" size="mini" class="!p-0 !text-[#6b7785] hover:!text-[#86909c]" @click.stop="handleDeleteInterface(api)">
                                    <template #icon><icon-delete /></template>
                                  </a-button>
                                </div>
                              </div>
                            </div>
                          </div>
                        </a-spin>
                      </div>
                    </div>

                    <ModuleTree
                      v-for="module in filteredModules"
                      :key="module.id"
                      :module="module"
                      :expanded-ids="expandedModuleIds"
                      :selected-id="selectedModule?.id"
                      :selected-interface-id="selectedInterface?.id"
                      :form-loading="formLoading"
                      display-mode="detail"
                      interface-select-mode="direct"
                      @select="handleSelectModule"
                      @toggle-expand="handleToggleExpand"
                      @edit="handleOpenEditModuleForm"
                      @add-child="handleOpenCreateModuleForm"
                      @delete="handleDeleteModule"
                      @edit-interface="handleEditInterface"
                      @delete-interface="handleDeleteInterface"
                      @copy-interface="handleCopyInterface"
                      @run-interface="handleRunInterface"
                      @select-interface="handleSelectInterface"
                    />
                  </div>
                </template>
              </div>
            </div>
          </a-spin>
        </div>
      </div>
    </div>

    <section class="flex-1 min-w-0 flex flex-col gap-4">
      <div class="panel-shell rounded-lg px-6 py-5 space-y-4">
        <div class="scope-row">
          <div class="scope-title">{{ currentScopeLabel }}</div>
          <div class="scope-subtitle">{{ tl('点击左侧接口查看关联接口用例') }}</div>
        </div>
        <div class="flex items-center gap-4">
          <div class="flex-1">
            <TestCaseSearch
              :model-value="{ name: queryParams.name || '', description: queryParams.description || '' }"
              @update:model-value="updateSearchParams"
              @search="handleSearch"
              @reset="handleReset"
            />
          </div>
          <div class="flex-1">
            <TestCaseFilter
              :model-value="{ priority: queryParams.priority, group: queryParams.group, tags: queryParams.tags }"
              :project-id="projectStore.currentProjectId"
              @update:model-value="updateFilterParams"
              @search="handleSearch"
            />
          </div>
          <div class="flex items-center gap-2">
            <a-button class="custom-reset-button" @click="handleReset">
              {{ tl('重置') }}
            </a-button>
            <a-button type="primary" class="custom-add-button" @click="handleCreate">
              {{ tl('新增接口用例') }}
            </a-button>
          </div>
        </div>
      </div>

      <div class="panel-shell flex-1 min-w-0 overflow-hidden">
        <div class="p-6 min-w-0 h-full">
          <InterfaceCaseTable
            :data="interfaceCases"
            :loading="loading"
            @sort="handleSortChange"
            @run="handleRun"
            @report="handleReport"
            @edit="handleEdit"
            @copy="handleCopy"
            @delete="handleDelete"
          />
        </div>
      </div>

      <div class="panel-shell px-6 py-5">
        <a-pagination
          v-model:current="pagination.current"
          v-model:page-size="pagination.page_size"
          :total="pagination.total"
          show-total
          show-jumper
          show-page-size
          class="flex justify-end"
          @change="handlePageChange"
          @page-size-change="handlePageSizeChange"
        />
      </div>
    </section>

    <ModuleForm
      v-model:visible="formVisible"
      :type="formType"
      :loading="formLoading"
      :apis="modules"
      :current-module="currentModule"
      :parent-id="formParentId"
      @submit="handleModuleFormSubmit"
    />
  </div>
</template>

<style scoped>
.interface-cases-panel {
  --tc-panel-bg: color-mix(in srgb, var(--theme-card-bg) 92%, var(--theme-page-bg) 8%);
  --tc-panel-border: rgba(148, 163, 184, 0.16);
  --tc-panel-shadow: 0 14px 30px rgba(15, 23, 42, 0.08);
  --tc-input-bg: #ffffff;
  --tc-input-border: rgba(148, 163, 184, 0.18);
  --tc-input-bg-hover: color-mix(in srgb, var(--theme-card-bg) 88%, var(--theme-page-bg) 12%);
  --tc-table-header-bg: color-mix(in srgb, var(--theme-card-bg) 76%, var(--theme-page-bg) 24%);
  --tc-row-hover: rgba(15, 23, 42, 0.04);
  --tc-text: var(--theme-text);
  --tc-text-muted: var(--theme-text-secondary);
  --tc-text-subtle: var(--theme-text-tertiary);
  --tc-link: var(--theme-accent);
  --tc-link-hover: var(--theme-accent-hover);
  --tc-secondary-bg: rgba(148, 163, 184, 0.08);
  --tc-secondary-bg-hover: rgba(148, 163, 184, 0.14);
  --tc-secondary-border: rgba(148, 163, 184, 0.18);
  --tc-secondary-text: var(--theme-text-secondary);
  --tc-secondary-text-hover: var(--theme-text);
  --tc-more-bg: linear-gradient(to right, #e2e8f0, #cbd5e1);
  --tc-more-text: #334155;
}

.api-testcases--dark {
  --tc-panel-bg: rgba(31, 41, 55, 0.58);
  --tc-panel-border: rgba(148, 163, 184, 0.12);
  --tc-panel-shadow: 0 18px 32px rgba(2, 6, 23, 0.28);
  --tc-input-bg: rgba(30, 41, 59, 0.5);
  --tc-input-border: rgba(148, 163, 184, 0.1);
  --tc-input-bg-hover: rgba(30, 41, 59, 0.72);
  --tc-table-header-bg: rgba(30, 41, 59, 0.5);
  --tc-row-hover: rgba(30, 41, 59, 0.5);
  --tc-secondary-bg: rgba(148, 163, 184, 0.1);
  --tc-secondary-bg-hover: rgba(148, 163, 184, 0.2);
  --tc-secondary-border: rgba(148, 163, 184, 0.2);
  --tc-secondary-text: #94a3b8;
  --tc-secondary-text-hover: #e2e8f0;
  --tc-more-bg: linear-gradient(to right, rgb(71, 85, 105), rgb(51, 65, 85));
  --tc-more-text: rgb(226, 232, 240);
}

.panel-shell {
  background: var(--tc-panel-bg);
  border: 1px solid var(--tc-panel-border);
  box-shadow: var(--tc-panel-shadow);
  border-radius: 8px;
}

.scope-title {
  color: var(--tc-text);
  font-weight: 600;
}

.scope-row {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.scope-subtitle {
  color: var(--tc-text-subtle);
  font-size: 12px;
}

.custom-reset-button {
  background: var(--tc-secondary-bg) !important;
  border: 1px solid var(--tc-secondary-border) !important;
  color: var(--tc-secondary-text) !important;
  padding: 0 24px !important;
  height: 36px !important;
  border-radius: 8px !important;
}

.custom-reset-button:hover {
  background: var(--tc-secondary-bg-hover) !important;
  color: var(--tc-secondary-text-hover) !important;
}

.custom-add-button {
  background: linear-gradient(to right, #3b82f6, #1d4ed8) !important;
  border: none !important;
  padding: 0 24px !important;
  height: 36px !important;
  border-radius: 8px !important;
}

:deep(.arco-pagination-total) {
  color: var(--tc-text-subtle) !important;
}

:deep(.arco-switch) {
  background-color: rgb(55, 65, 81) !important;
  border: 1px solid rgb(75, 85, 99) !important;
}

:deep(.arco-switch.arco-switch-checked) {
  background-color: rgb(59, 130, 246) !important;
  border-color: rgb(59, 130, 246) !important;
}

:deep(.arco-switch .arco-switch-handle) {
  background-color: rgb(243, 244, 246) !important;
}

.api-management--dark {
  --interface-dark-surface: rgba(30, 41, 59, 0.96);
  --interface-dark-surface-soft: rgba(15, 23, 42, 0.78);
  --interface-dark-surface-muted: rgba(51, 65, 85, 0.72);
  --interface-dark-border: rgba(148, 163, 184, 0.14);
  --interface-dark-text-primary: #f8fafc;
  --interface-dark-text-secondary: #cbd5e1;
  --interface-dark-text-muted: #94a3b8;
  --interface-dark-hover: rgba(96, 165, 250, 0.12);
  --interface-dark-hover-strong: rgba(96, 165, 250, 0.18);
  --interface-module-surface: rgba(51, 65, 85, 0.54);
  --interface-module-hover: rgba(96, 165, 250, 0.16);
  --interface-module-active: rgba(96, 165, 250, 0.24);
  --interface-module-active-border: rgba(147, 197, 253, 0.22);
  --interface-dark-shadow: 0 20px 44px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(148, 163, 184, 0.05);
  background-color: rgba(0, 0, 0, 0.18);
}

.api-management--dark :deep([class~='bg-gray-800']),
.api-management--dark :deep([class~='bg-gray-800/50']),
.api-management--dark :deep([class~='bg-gray-800/85']) {
  background-color: var(--interface-dark-surface) !important;
}

.api-management--dark :deep([class~='bg-gray-700']),
.api-management--dark :deep([class~='bg-gray-700/30']),
.api-management--dark :deep([class~='bg-gray-700/50']) {
  background-color: var(--interface-dark-surface-muted) !important;
}

.api-management--dark :deep([class~='border-gray-700']),
.api-management--dark :deep([class~='border-gray-700/50']),
.api-management--dark :deep([class~='border-gray-600']),
.api-management--dark :deep([class~='border-gray-500']) {
  border-color: var(--interface-dark-border) !important;
}

.api-management--dark :deep([class~='text-gray-100']),
.api-management--dark :deep([class~='text-gray-200']) {
  color: var(--interface-dark-text-primary) !important;
}

.api-management--dark :deep([class~='text-gray-300']) {
  color: var(--interface-dark-text-secondary) !important;
}

.api-management--dark :deep([class~='text-gray-400']),
.api-management--dark :deep([class~='text-gray-500']) {
  color: var(--interface-dark-text-muted) !important;
}

.api-management--dark :deep([class~='shadow-lg']),
.api-management--dark :deep([class~='shadow-dark']) {
  box-shadow: var(--interface-dark-shadow) !important;
}

.api-management--dark :deep([class~='hover:bg-gray-700/30']:hover),
.api-management--dark :deep([class~='hover:bg-gray-700/50']:hover),
.api-management--dark :deep([class~='hover:bg-gray-800/50']:hover),
.api-management--dark :deep([class~='hover:bg-[rgb(70,84,102,0.4)]']:hover) {
  background-color: var(--interface-dark-hover) !important;
}

.api-management--dark :deep(.arco-input-wrapper),
.api-management--dark :deep(.arco-select-view) {
  background-color: var(--interface-dark-surface-soft) !important;
  border-color: var(--interface-dark-border) !important;
}

.api-management--light {
  --interface-surface: #fff;
  --interface-surface-soft: #f8fafc;
  --interface-surface-muted: #eef2f7;
  --interface-border: rgba(15, 23, 42, 0.12);
  --interface-text-primary: var(--color-text-1);
  --interface-text-secondary: var(--color-text-2);
  --interface-text-muted: var(--color-text-3);
  --interface-hover: rgba(var(--theme-accent-rgb), 0.06);
  --interface-hover-strong: rgba(var(--theme-accent-rgb), 0.12);
  --interface-module-surface: rgba(15, 23, 42, 0.05);
  --interface-module-hover: rgba(var(--theme-accent-rgb), 0.1);
  --interface-module-active: rgba(var(--theme-accent-rgb), 0.16);
  --interface-module-active-border: rgba(var(--theme-accent-rgb), 0.2);
  --interface-shadow: 0 18px 40px rgba(15, 23, 42, 0.12), 0 4px 12px rgba(15, 23, 42, 0.08);
  background-color: rgba(15, 23, 42, 0.04);
}

.api-management--light :deep([class~='bg-gray-800']),
.api-management--light :deep([class~='bg-gray-800/50']),
.api-management--light :deep([class~='bg-gray-800/85']) {
  background-color: var(--interface-surface) !important;
}

.api-management--light :deep([class~='bg-gray-700']),
.api-management--light :deep([class~='bg-gray-700/30']),
.api-management--light :deep([class~='bg-gray-700/50']) {
  background-color: var(--interface-surface-muted) !important;
}

.api-management--light :deep([class~='bg-[rgb(70,84,102,0.2)]']),
.api-management--light :deep([class~='!bg-[rgb(70,84,102,0.2)]']) {
  background-color: rgba(15, 23, 42, 0.05) !important;
}

.api-management--light :deep([class~='bg-[rgb(70,84,102,0.4)]']),
.api-management--light :deep([class~='!bg-[rgb(70,84,102,0.4)]']) {
  background-color: rgba(15, 23, 42, 0.09) !important;
}

.api-management--light :deep([class~='border-gray-700']),
.api-management--light :deep([class~='border-gray-700/50']),
.api-management--light :deep([class~='border-gray-600']),
.api-management--light :deep([class~='border-gray-500']) {
  border-color: var(--interface-border) !important;
}

.api-management--light :deep([class~='text-gray-100']),
.api-management--light :deep([class~='text-gray-200']) {
  color: var(--interface-text-primary) !important;
}

.api-management--light :deep([class~='text-gray-300']) {
  color: var(--interface-text-secondary) !important;
}

.api-management--light :deep([class~='text-gray-400']),
.api-management--light :deep([class~='text-gray-500']) {
  color: var(--interface-text-muted) !important;
}

.api-management--light :deep([class~='shadow-lg']),
.api-management--light :deep([class~='shadow-dark']) {
  box-shadow: var(--interface-shadow) !important;
}

.api-management--light :deep([class~='hover:bg-gray-700/30']:hover),
.api-management--light :deep([class~='hover:bg-gray-700/50']:hover),
.api-management--light :deep([class~='hover:bg-gray-800/50']:hover),
.api-management--light :deep([class~='hover:bg-[rgb(70,84,102,0.4)]']:hover) {
  background-color: var(--interface-hover) !important;
}

.api-management--light :deep([class~='hover:text-gray-300']:hover),
.api-management--light :deep([class~='hover:text-gray-200']:hover) {
  color: var(--interface-text-primary) !important;
}

.api-management--light :deep(.arco-input-wrapper),
.api-management--light :deep(.arco-select-view),
.api-management--light :deep(.arco-pagination-jumper .arco-input-wrapper) {
  background-color: var(--interface-surface) !important;
  border-color: var(--interface-border) !important;
  box-shadow: none !important;
}

.api-management--light :deep(.arco-input-wrapper input),
.api-management--light :deep(.arco-input),
.api-management--light :deep(.arco-select-view-value),
.api-management--light :deep(.arco-select-view-single .arco-select-view-value) {
  color: var(--interface-text-primary) !important;
}

.api-management--light :deep(.arco-input-wrapper input::placeholder),
.api-management--light :deep(.arco-select-view-placeholder) {
  color: var(--interface-text-muted) !important;
}

.api-management--light :deep(.arco-switch) {
  background-color: var(--color-neutral-3) !important;
  border-color: var(--interface-border) !important;
}

.api-management--light :deep(.arco-switch .arco-switch-handle) {
  background-color: #fff !important;
}

.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.scrollbar-hide::-webkit-scrollbar {
  display: none;
}

.no-module-interface-item {
  overflow: hidden;
}

.no-module-interface-main {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.75rem;
  min-width: 0;
  width: 100%;
}

.no-module-interface-info {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  column-gap: 0.5rem;
  min-width: 0;
  overflow: hidden;
}

.no-module-interface-name {
  display: block;
  flex: 1 1 auto;
  min-width: 0;
}

.no-module-interface-actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  margin-left: 1rem;
}
</style>
