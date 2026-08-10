<script setup lang="ts">
import { ref, onMounted, watch, computed, nextTick, provide } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import { useProjectStore } from '@/store/projectStore'
import { IconPlus, IconSearch, IconFolder, IconEdit, IconDelete, IconList, IconSend, IconCopy, IconUpload, IconDownload, IconClose } from '@arco-design/web-vue/es/icon'
import type { ApiModule, PaginatedData, ApiInterface } from '../../services/interfaceService'
import type { InterfaceStatus } from '../../types/interface'
import { getInterfaces, getInterfaceById, deleteInterface, batchDeleteInterfaces, duplicateInterface, importApiDocument, importApiDocumentText, exportApiDocument } from '../../services/interfaceService'
import type { ApiDocumentExportFormat, ApiDocumentImportType } from '../../services/interfaceService'
import { getModules, createModule, updateModule, deleteModule, moveModule } from '../../services/moduleService'
import ApiDetail from './ApiDetail.vue'
import ApiTabs from './ApiTabs.vue'
import ModuleTree from './ModuleTree.vue'
import ModuleForm from './ModuleForm.vue'
import ApiInterfaceList from './ApiInterfaceList.vue'
import ApiInterfacePagination from './ApiInterfacePagination.vue'
import { useApiTabsStore } from '../../stores/apiTabsStore'
import { useThemeStore } from '@/store/themeStore'
import { useAppI18n } from '@/composables/useAppI18n'

const projectStore = useProjectStore()
const tabsStore = useApiTabsStore()
const themeStore = useThemeStore()
const { isEnglish, tl } = useAppI18n()
const loading = ref(false)
const formLoading = ref(false)
const apis = ref<ApiModule[]>([])
const interfaces = ref<ApiInterface[]>([])
const searchKeyword = ref('')
const selectedApi = ref<ApiModule | undefined>()
const selectedInterface = ref<ApiInterface | undefined>(undefined)
const expandedIds = ref<number[]>([])
const detailKey = ref(0)
const openApiFileInput = ref<HTMLInputElement | null>(null)
const importingOpenApi = ref(false)
const exportingOpenApi = ref(false)
const selectedImportType = ref<ApiDocumentImportType>('swagger')
const importTextDialogVisible = ref(false)
const importTextDialogType = ref<'swagger' | 'curl'>('swagger')
const importTextValue = ref('')
// 导入文件弹窗相关状态
const importFileDialogVisible = ref(false)
const importFileDialogType = ref<ApiDocumentImportType>('swagger')
const importFileSelected = ref<File | null>(null)
const stripBaseUrl = ref(true)
const createEnvironments = ref(false)
// 无模块接口相关状态
const noModuleInterfaces = ref<ApiInterface[]>([])
const hasNoModuleInterfaces = ref(false)
// 自动调试标志
const autoDebug = ref(false)
const isDarkTheme = computed(() => themeStore.isBlack)
const containsChinese = (value: string) => /[\u4e00-\u9fff]/.test(value)
const translateErrorMessage = (message: unknown) => {
  if (typeof message !== 'string' || !message.trim()) {
    return null
  }
  const translated = tl(message)
  if (isEnglish.value && translated === message && containsChinese(message)) {
    return null
  }
  return translated
}
const moduleText = computed(() => isEnglish.value
  ? {
      createSuccess: 'Module created successfully',
      updateSuccess: 'Module updated successfully',
      createFailed: 'Failed to create module',
      updateFailed: 'Failed to update module',
      deleteSuccess: 'Module deleted successfully',
      deleteFailed: 'Failed to delete module',
      deleteConfirmTitle: 'Confirm deletion',
      deleteConfirmContent: (name: string) => `Delete module "${name}"? All interfaces in this module will also be deleted, and this action cannot be undone.`,
      confirm: 'Confirm',
      cancel: 'Cancel',
      selectProjectFirst: 'Select a project first',
    }
  : {
      createSuccess: '创建模块成功',
      updateSuccess: '更新模块成功',
      createFailed: '创建模块失败',
      updateFailed: '更新模块失败',
      deleteSuccess: '删除模块成功',
      deleteFailed: '删除模块失败',
      deleteConfirmTitle: '确认删除',
      deleteConfirmContent: (name: string) => `确定要删除模块"${name}"吗？删除后将同时删除该模块下的所有接口，且不可恢复。`,
      confirm: '确定',
      cancel: '取消',
      selectProjectFirst: '请先选择项目',
    }
)

// 视图模式控制
const viewMode = ref<'list' | 'detail'>('detail')
// 分页相关状态
const pagination = ref({
  page: 1,
  pageSize: 20,
  total: 0
})

// 列表筛选 / 排序（服务端）
// undefined=跟随左侧树；null=列表显式“不限模块”；number=指定模块
const listFilterModuleId = ref<number | null | undefined>(undefined)
const listFilterStatus = ref<InterfaceStatus | ''>('')
const listSortField = ref<'created_at' | 'updated_at' | ''>('created_at')
const listSortOrder = ref<'ascend' | 'descend' | ''>('descend')
const listSearchKeyword = ref('')

// 全部接口列表（用于列表模式）
const allInterfaces = ref<ApiInterface[]>([])
// 当前模块名称
const findModuleNameById = (modules: ApiModule[], id: number): string | undefined => {
  for (const module of modules || []) {
    if (module.id === id) return module.name
    if (module.children?.length) {
      const child = findModuleNameById(module.children, id)
      if (child) return child
    }
  }
  return undefined
}

const currentModuleName = computed(() => {
  if (listFilterModuleId.value === null) return '全部接口'
  if (typeof listFilterModuleId.value === 'number') {
    return findModuleNameById(apis.value || [], listFilterModuleId.value) || '全部接口'
  }
  if (!selectedApi.value) return '全部接口'
  return selectedApi.value.name
})

const fileImportTypes: ApiDocumentImportType[] = [
  'swagger', 'postman', 'markdown', 'har', 'insomnia', 'apidoc',
  'apifox', 'apipost', 'yapi', 'apizza', 'eolink'
]

const refreshAfterImport = async () => {
  await Promise.all([
    fetchApiModules(),
    fetchInterfaceListForDisplay()
  ])

  if (selectedApi.value?.id) {
    await fetchInterfaces(selectedApi.value.id)
  }
}

const showImportResult = (result: any) => {
  const envCount = Array.isArray(result?.created_environments) ? result.created_environments.length : 0
  const envText = envCount > 0 ? `，创建环境 ${envCount} 个` : ''
  Message.success(
    `导入完成：新增 ${result?.created_count ?? 0} 个，更新 ${result?.updated_count ?? 0} 个，跳过 ${result?.skipped_count ?? 0} 个${envText}`
  )
}

// 导入格式下拉选项（与按钮下拉一致，用于弹窗内二次选择）
const importFormatOptions: Array<{ label: string; value: ApiDocumentImportType }> = [
  { label: 'Swagger 文件', value: 'swagger' },
  { label: 'Postman', value: 'postman' },
  { label: 'Markdown', value: 'markdown' },
  { label: 'HAR', value: 'har' },
  { label: 'Insomnia', value: 'insomnia' },
  { label: 'ApiDoc', value: 'apidoc' },
  { label: 'Apifox', value: 'apifox' },
  { label: 'Apipost', value: 'apipost' },
  { label: 'YApi', value: 'yapi' },
  { label: 'Apizza', value: 'apizza' },
  { label: 'Eolink', value: 'eolink' },
]

const handleImportTypeSelect = (value: unknown) => {
  if (!projectStore.currentProjectId) {
    Message.warning('请先选择项目')
    return
  }

  const importType = String(value) as ApiDocumentImportType | 'swagger-url'
  if (importType === 'swagger-url' || importType === 'curl') {
    importTextDialogType.value = importType === 'swagger-url' ? 'swagger' : 'curl'
    importTextValue.value = ''
    importTextDialogVisible.value = true
    return
  }
  if (!fileImportTypes.includes(importType as ApiDocumentImportType)) return
  // 文件类型：不再直接进入文件选择，改为打开导入弹窗（默认显示用户刚才选择的格式）
  selectedImportType.value = importType as ApiDocumentImportType
  importFileDialogType.value = importType as ApiDocumentImportType
  importFileSelected.value = null
  stripBaseUrl.value = true
  createEnvironments.value = false
  importFileDialogVisible.value = true
}

// 弹窗内点击文件区域，唤出 Windows 文件选择
const handlePickImportFile = () => {
  if (importingOpenApi.value) return
  if (openApiFileInput.value) {
    openApiFileInput.value.value = ''
    openApiFileInput.value.click()
  }
}

// 文件选择回调：仅记录已选文件，不立即导入
const handleOpenApiFileChange = (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) {
    importFileSelected.value = file
  }
  target.value = ''
}

const resetImportFileDialog = () => {
  importFileSelected.value = null
  stripBaseUrl.value = true
  createEnvironments.value = false
}

// 弹窗「开始导入」按钮
const handleImportFileConfirm = async () => {
  if (!importFileSelected.value) {
    Message.warning('请先选择要导入的文件')
    return
  }

  try {
    importingOpenApi.value = true
    const response = await importApiDocument(importFileSelected.value, importFileDialogType.value, {
      strip_base_url: stripBaseUrl.value,
      create_environments: createEnvironments.value,
    })
    showImportResult(response.data)
    await refreshAfterImport()
    importFileDialogVisible.value = false
    resetImportFileDialog()
  } catch (error: any) {
    Message.error(error.message || '导入接口文档失败')
  } finally {
    importingOpenApi.value = false
  }
}

const handleImportTextConfirm = async () => {
  const value = importTextValue.value.trim()
  if (!value) {
    Message.warning(importTextDialogType.value === 'swagger' ? '请输入 Swagger URL' : '请输入 cURL 命令')
    return false
  }

  try {
    importingOpenApi.value = true
    const response = await importApiDocumentText(importTextDialogType.value, value)
    showImportResult(response.data)
    await refreshAfterImport()
    importTextDialogVisible.value = false
    return true
  } catch (error: any) {
    Message.error(error.message || '导入接口文档失败')
    return false
  } finally {
    importingOpenApi.value = false
  }
}

const handleExportOpenApi = async (value: unknown) => {
  if (!projectStore.currentProjectId) {
    Message.warning('请先选择项目')
    return
  }

  const supportedFormats: ApiDocumentExportFormat[] = ['json', 'yaml', 'apifox', 'apipost', 'yapi']
  const format: ApiDocumentExportFormat = supportedFormats.includes(value as ApiDocumentExportFormat)
    ? value as ApiDocumentExportFormat
    : 'json'

  try {
    exportingOpenApi.value = true
    const { blob, filename } = await exportApiDocument(format)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
    Message.success('导出接口文档成功')
  } catch (error: any) {
    Message.error(error.message || '导出接口文档失败')
  } finally {
    exportingOpenApi.value = false
  }
}

// 获取接口列表（支持分页）
const fetchInterfaceListForDisplay = async () => {
  if (!projectStore.currentProjectId) {
    allInterfaces.value = []
    return
  }

  try {
    loading.value = true
    const ordering = listSortField.value
      ? `${listSortOrder.value === 'ascend' ? '' : '-'}${listSortField.value}`
      : '-created_at'

    // 列表模块筛选：undefined 跟随左侧树；null 表示不限模块；number 指定模块
    let moduleId: number | undefined
    if (listFilterModuleId.value === undefined) {
      moduleId = selectedApi.value?.id
    } else if (listFilterModuleId.value === null) {
      moduleId = undefined
    } else {
      moduleId = listFilterModuleId.value
    }

    const params: Record<string, any> = {
      project_id: Number(projectStore.currentProjectId),
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
      ordering,
    }
    if (moduleId != null) {
      params.module_id = moduleId
    }
    if (listFilterStatus.value) {
      params.status = listFilterStatus.value
    }
    if (listSearchKeyword.value.trim()) {
      params.search = listSearchKeyword.value.trim()
    }
    
    const { data } = await getInterfaces(params)
    if (data) {
      allInterfaces.value = data.results || []
      pagination.value.total = data.count || 0
    } else {
      allInterfaces.value = []
      pagination.value.total = 0
    }
  } catch (error: any) {
    Message.error(error.message || '获取接口列表失败')
    allInterfaces.value = []
    pagination.value.total = 0
  } finally {
    loading.value = false
  }
}

// 获取接口列表（用于树形结构）
const fetchInterfaces = async (moduleId?: number | null) => {
  if (!projectStore.currentProjectId) {
    interfaces.value = []
    return
  }

  try {
    loading.value = true
    const { data } = await getInterfaces({
      module_id: moduleId,
      project_id: Number(projectStore.currentProjectId),
      page_size: 1000 // 设置较大的页面大小，确保能显示所有接口
    })
    if (data?.results) {
      interfaces.value = data.results
      console.log(`获取到${data.results.length}个接口`)
      // 如果有选中的接口，更新它的数据
      if (selectedInterface.value) {
        const updatedInterface = data.results.find(item => item.id === selectedInterface.value?.id)
        if (updatedInterface) {
          selectedInterface.value = updatedInterface
        }
      }
    } else {
      interfaces.value = []
    }
  } catch (error: any) {
    Message.error(error.message || '获取接口列表失败')
    interfaces.value = []
  } finally {
    loading.value = false
  }
}

// 获取无模块接口列表
const fetchNoModuleInterfaces = async () => {
  if (!projectStore.currentProjectId) {
    noModuleInterfaces.value = []
    hasNoModuleInterfaces.value = false
    return
  }

  try {
    loading.value = true
    // 使用 getInterfaces 函数并传入 no_module: true 参数
    const { data } = await getInterfaces({
      project_id: Number(projectStore.currentProjectId),
      page_size: 1000,
      no_module: true
    })
    
    if (data?.results && data.results.length > 0) {
      noModuleInterfaces.value = data.results
      hasNoModuleInterfaces.value = true
      console.log(`获取到${data.results.length}个无模块接口`)
    } else {
      noModuleInterfaces.value = []
      hasNoModuleInterfaces.value = false
    }
  } catch (error: any) {
    console.error('获取无模块接口失败:', error)
    noModuleInterfaces.value = []
    hasNoModuleInterfaces.value = false
  } finally {
    loading.value = false
  }
}

// 表单相关状态
const formVisible = ref(false)
const formType = ref<'create' | 'edit'>('create')
const formParentId = ref<number | undefined>()
const currentModule = ref<ApiModule | undefined>()

// 模块拖拽排序状态
const draggingModule = ref<ApiModule | null>(null)
const dragOverModule = ref<ApiModule | null>(null)
const dragOverPosition = ref<number | null>(null) // -1: before, 0: inside, 1: after

provide('draggingModule', draggingModule)
provide('dragOverModule', dragOverModule)
provide('dragOverPosition', dragOverPosition)

const handleModuleDrop = async (dragged: ApiModule, target: ApiModule, position: number) => {
  if (!projectStore.currentProjectId || dragged.id === target.id) return
  
  // 检查移动后的深度是否超过5级限制
  let newLevel = target.level as number
  if (position === 0) {
    newLevel = (target.level as number) + 1
  }
  
  const getSubtreeDepth = (module: ApiModule): number => {
    if (!module.children || module.children.length === 0) return 1
    return 1 + Math.max(...module.children.map(child => getSubtreeDepth(child)))
  }
  
  const subtreeDepth = getSubtreeDepth(dragged)
  if (newLevel + subtreeDepth - 1 > 5) {
    Message.error(isEnglish.value ? 'Hierarchy exceeds the limit of 5 levels' : '移动后模块层级将超过5级限制')
    return
  }
  
  loading.value = true
  try {
    const response = await moveModule(dragged.id, {
      target_id: target.id,
      drop_position: position
    })
    
    if (response.status === 'success') {
      Message.success(isEnglish.value ? 'Module reordered successfully' : '模块排序/移动成功')
      await fetchApiModules()
    } else {
      Message.error(response.message || (isEnglish.value ? 'Failed to move module' : '移动模块失败'))
    }
  } catch (error: any) {
    console.error('Failed to move module:', error)
    Message.error(error.message || (isEnglish.value ? 'Error moving module' : '移动模块时发生错误'))
  } finally {
    loading.value = false
    draggingModule.value = null
    dragOverModule.value = null
    dragOverPosition.value = null
  }
}
provide('handleModuleDrop', handleModuleDrop)

// 递归收集所有模块ID
const collectAllModuleIds = (moduleList: ApiModule[]): number[] => {
  const ids: number[] = []
  const traverse = (modules: ApiModule[]) => {
    for (const module of modules) {
      ids.push(module.id)
      if (module.children && module.children.length > 0) {
        traverse(module.children)
      }
    }
  }
  traverse(moduleList)
  return ids
}

// 预加载所有模块的接口数据
const preloadAllModulesData = async (moduleList: ApiModule[]) => {
  const allModuleIds = collectAllModuleIds(moduleList)

  // 为每个模块预加载接口数据
  const preloadPromises = allModuleIds.map(moduleId =>
    getInterfaces({
      module_id: moduleId,
      project_id: Number(projectStore.currentProjectId),
      page_size: 1000
    }).catch(error => {
      console.error(`Failed to preload interfaces for module ${moduleId}:`, error)
    })
  )

  await Promise.all(preloadPromises)
}

// 获取API模块列表
const fetchApiModules = async () => {
  if (!projectStore.currentProjectId) {
    apis.value = []
    return
  }

  try {
    loading.value = true
    const response = await getModules({
      page: 1,
      page_size: 100,
      project_id: projectStore.currentProjectId
    })

    if (response.data?.results) {
      apis.value = response.data.results
      // 首次加载时预加载所有模块的接口数据
      await preloadAllModulesData(response.data.results)
    } else {
      apis.value = []
    }

    // 获取无模块接口
    await fetchNoModuleInterfaces()
  } catch (error: any) {
    Message.error(error.message || '获取模块列表失败')
    apis.value = []
  } finally {
    loading.value = false
  }
}

// 过滤后的模块列表
const getFilteredModules = computed(() => {
  if (!searchKeyword.value) return apis.value

  const keyword = searchKeyword.value.toLowerCase()
  
  const filterModules = (modules: ApiModule[]): ApiModule[] => {
    return modules.reduce((filtered: ApiModule[], module) => {
      const isMatch = module.name.toLowerCase().includes(keyword)
      const children = module.children ? filterModules(module.children) : []
      
      if (isMatch || children.length > 0) {
        filtered.push({
          ...module,
          children: children
        })
      }
      
      return filtered
    }, [])
  }

  return filterModules(apis.value)
})

// 扁平模块选项（列表筛选用，保留层级缩进）
const flattenModuleOptions = (modules: ApiModule[], level = 0): Array<{ id: number; name: string; level: number }> => {
  const result: Array<{ id: number; name: string; level: number }> = []
  for (const module of modules || []) {
    if (module?.id == null) continue
    result.push({ id: module.id, name: module.name, level })
    if (module.children?.length) {
      result.push(...flattenModuleOptions(module.children, level + 1))
    }
  }
  return result
}

const listModuleOptions = computed(() => flattenModuleOptions(apis.value || []))


// 切换展开状态
const handleToggleExpand = async (moduleId: number) => {
  const index = expandedIds.value.indexOf(moduleId)
  if (index === -1) {
    // 展开时，添加到展开列表
    expandedIds.value.push(moduleId)
    // 注意：不在这里调用 fetchInterfaces，因为子组件的 watch 会自动调用
  } else {
    // 收起时，从展开列表中移除
    expandedIds.value.splice(index, 1)
  }
}

// 选择模块
const handleSelectModule = async (module: ApiModule) => {
  selectedApi.value = module
  // 不再自动展开模块，由用户通过点击控制展开/收起
}

// 打开创建模块表单
const handleOpenCreateForm = (parentId?: number) => {
  formType.value = 'create'
  formParentId.value = parentId
  currentModule.value = undefined
  formVisible.value = true
}

// 打开编辑模块表单
const handleOpenEditForm = (module: ApiModule) => {
  formType.value = 'edit'
  currentModule.value = module
  formVisible.value = true
}

// 处理表单提交
const handleFormSubmit = async (formData: any) => {
  if (!projectStore.currentProjectId) {
    Message.warning(moduleText.value.selectProjectFirst)
    return
  }

  try {
    formLoading.value = true
    if (formType.value === 'create') {
      const data = {
        ...formData,
        project: Number(projectStore.currentProjectId)
      }
      await createModule(data)
      Message.success(moduleText.value.createSuccess)
    } else {
      await updateModule(currentModule.value!.id, formData)
      Message.success(moduleText.value.updateSuccess)
    }
    formVisible.value = false
    fetchApiModules()
  } catch (error: any) {
    Message.error(
      translateErrorMessage(error.message)
      || (formType.value === 'create' ? moduleText.value.createFailed : moduleText.value.updateFailed)
    )
  } finally {
    formLoading.value = false
  }
}

// 删除模块
const handleDelete = async (module: ApiModule) => {
  Modal.error({
    title: moduleText.value.deleteConfirmTitle,
    content: moduleText.value.deleteConfirmContent(module.name),
    hideCancel: false,
    okText: moduleText.value.confirm,
    cancelText: moduleText.value.cancel,
    okButtonProps: {
      status: 'danger'
    },
    onOk: async () => {
      try {
        formLoading.value = true
        const previousActiveTabId = tabsStore.activeTabId
        const response = await deleteModule(module.id)
        const deletedInterfaceIds = Array.isArray(response.data?.deleted_interface_ids)
          ? response.data.deleted_interface_ids.filter((id): id is number => Number.isInteger(id))
          : []
        Message.success(moduleText.value.deleteSuccess)

        removeInterfacesFromLocalLists(deletedInterfaceIds)

        const removedTabIds = deletedInterfaceIds.flatMap(interfaceId =>
          tabsStore.removeInterfaceTabs(interfaceId)
        )
        const deletedActiveTab = previousActiveTabId
          ? removedTabIds.includes(previousActiveTabId)
          : false
        const selectedInterfaceDeleted = !!selectedInterface.value?.id
          && deletedInterfaceIds.includes(selectedInterface.value.id)

        if (selectedInterfaceDeleted) {
          selectedInterface.value = undefined
        }

        expandedIds.value = expandedIds.value.filter(id => id !== module.id)

        if (selectedApi.value?.id === module.id) {
          selectedApi.value = undefined
          interfaces.value = []
        }

        if (deletedActiveTab) {
          if (tabsStore.activeTabId) {
            handleTabChange(tabsStore.activeTabId)
          } else {
            viewMode.value = 'list'
            detailKey.value++
          }
        } else if (!tabsStore.activeTabId && selectedInterfaceDeleted) {
          viewMode.value = 'list'
          detailKey.value++
        }

        await Promise.all([
          fetchApiModules(),
          fetchInterfaceListForDisplay()
        ])
      } catch (error: any) {
        Message.error(translateErrorMessage(error.message) || moduleText.value.deleteFailed)
      } finally {
        formLoading.value = false
      }
    }
  })
}

// 选择接口
const handleSelectInterface = (api: ApiInterface) => {
  console.log('父组件收到接口选择事件:', api)
  selectedInterface.value = api
  viewMode.value = 'detail' // 切换到详情模式
  
  // 创建或激活页签
  const tabId = tabsStore.openOrActivateInterface(api)
  
  // 如果是已存在的页签，强制触发状态恢复
  const existingTab = tabsStore.tabs.find(t => t.id === tabId)
  if (existingTab && existingTab.activeTab) {
    // 使用 nextTick 确保在下个渲染周期恢复状态
    nextTick(() => {
      // 通过更新 detailKey 来触发组件重新挂载，确保状态恢复
      detailKey.value++
    })
  }
  
  console.log('已更新选中的接口:', selectedInterface.value)
}


const applyInterfacePatchToLocalLists = (updated: ApiInterface) => {
  if (!updated?.id) return

  const patchList = (list: ApiInterface[]) => {
    const index = list.findIndex(item => item.id === updated.id)
    if (index !== -1) {
      list[index] = { ...list[index], ...updated }
    }
  }

  patchList(interfaces.value)
  patchList(noModuleInterfaces.value)
  patchList(allInterfaces.value)

  if (selectedInterface.value?.id === updated.id) {
    selectedInterface.value = { ...selectedInterface.value, ...updated }
  }
}

const handleInterfaceStatusChange = (payload: { api: ApiInterface; status: InterfaceStatus }) => {
  const { api } = payload
  if (!api?.id) return
  // list already patched server + optimistic row; sync other local caches / selection
  applyInterfacePatchToLocalLists(api)
}

// 更新接口
const handleUpdateInterface = (api: ApiInterface) => {
  console.log('更新接口信息:', api)
  // 不要严格检查接口完整性，使用存在的数据
  if (api) {
    console.log('接收到接口数据，设置为当前选中接口:', api)
    // 设置当前选中的接口
    selectedInterface.value = api
    
    // 如果接口有ID且在接口列表中存在，则更新列表中的数据
    if (api.id) {
      const index = interfaces.value.findIndex(item => item.id === api.id)
      if (index !== -1) {
        interfaces.value[index] = api
      } else {
        // 如果接口列表中不存在该接口，添加到接口列表中
        console.log('接口列表中未找到该接口，添加到列表中:', api)
        interfaces.value.push(api)
      }
    }
    
    // 确保在下一个tick渲染完成后，detailKey不会导致selectedInterface被清空
    nextTick(() => {
      console.log('确认选中接口状态:', selectedInterface.value)
    })
  }
}

const removeInterfaceFromLocalLists = (interfaceId: number) => {
  removeInterfacesFromLocalLists([interfaceId])
}

const removeInterfacesFromLocalLists = (interfaceIds: number[]) => {
  if (interfaceIds.length === 0) {
    return
  }

  const interfaceIdSet = new Set(interfaceIds)

  interfaces.value = interfaces.value.filter(item => !interfaceIdSet.has(item.id))
  noModuleInterfaces.value = noModuleInterfaces.value.filter(item => !interfaceIdSet.has(item.id))
  allInterfaces.value = allInterfaces.value.filter(item => !interfaceIdSet.has(item.id))
  hasNoModuleInterfaces.value = noModuleInterfaces.value.length > 0
}

// 删除接口

// 复制接口
const handleCopyInterface = async (api: ApiInterface) => {
  if (!api.id) return

  try {
    loading.value = true
    const response = await duplicateInterface(api.id)
    const copiedInterface = response.data
    Message.success('复制接口成功')

    // 复制后同步刷新模块树、当前模块接口列表、无模块分组数量和右侧分页列表
    await fetchApiModules()

    if (copiedInterface?.module) {
      if (!expandedIds.value.includes(copiedInterface.module)) {
        expandedIds.value.push(copiedInterface.module)
      }
      await fetchInterfaces(copiedInterface.module)

      // ModuleTree 子组件内部也有接口列表缓存，通过重置展开状态触发子组件重新拉取
      const expandedIndex = expandedIds.value.indexOf(copiedInterface.module)
      if (expandedIndex > -1) {
        expandedIds.value.splice(expandedIndex, 1)
        nextTick(() => {
          expandedIds.value.push(copiedInterface.module)
        })
      }
    } else {
      await fetchNoModuleInterfaces()
    }

    await fetchInterfaceListForDisplay()

    if (copiedInterface) {
      selectedInterface.value = copiedInterface
      tabsStore.openOrActivateInterface(copiedInterface)
      viewMode.value = 'detail'
    }
  } catch (error: any) {
    Message.error(error.message || '复制接口失败')
  } finally {
    loading.value = false
  }
}

const handleDeleteInterface = (api: ApiInterface) => {
  const modalLoading = ref(false)
  
  Modal.error({
    title: '确认删除',
    content: `确定要删除接口"${api.name}"吗？删除后不可恢复。`,
    hideCancel: false,
    okText: '确定',
    cancelText: '取消',
    okButtonProps: {
      status: 'danger'
    },
    async onOk() {
      if (modalLoading.value) return
      modalLoading.value = true
      
      try {
        const previousActiveTabId = tabsStore.activeTabId
        const deletingCurrentInterface = selectedInterface.value?.id === api.id
        const previousActiveTab = previousActiveTabId
          ? tabsStore.tabs.find(tab => tab.id === previousActiveTabId)
          : undefined
        await deleteInterface(api.id!)
        Message.success('删除接口成功')

        removeInterfaceFromLocalLists(api.id!)

        const removedTabIds = tabsStore.removeInterfaceTabs(api.id!)

        if (
          removedTabIds.length === 0 &&
          deletingCurrentInterface &&
          previousActiveTab?.id &&
          !previousActiveTab.interfaceId
        ) {
          tabsStore.removeTab(previousActiveTab.id)
          removedTabIds.push(previousActiveTab.id)
        }

        const deletedActiveTab = previousActiveTabId
          ? removedTabIds.includes(previousActiveTabId)
          : false
        
        // 如果删除的是当前选中的接口，清空选中状态
        if (selectedInterface.value?.id === api.id) {
          selectedInterface.value = undefined
        }

        if (deletedActiveTab) {
          if (tabsStore.activeTabId) {
            handleTabChange(tabsStore.activeTabId)
          } else {
            viewMode.value = 'list'
            detailKey.value++
          }
        }
        
        // 如果接口有模块ID，刷新该模块的接口列表
        if (api.module) {
          // 确保模块是展开状态
          if (!expandedIds.value.includes(api.module)) {
            expandedIds.value.push(api.module)
          }
          
          // 先从expandedIds中移除，再添加回来，强制刷新
          const index = expandedIds.value.indexOf(api.module)
          if (index > -1) {
            expandedIds.value.splice(index, 1)
            // 使用nextTick确保DOM更新后再重新展开
            nextTick(() => {
              expandedIds.value.push(api.module)
              // 刷新模块的接口列表
              fetchInterfaces(api.module)
            })
          }
        } else {
          // 如果是无模块接口，刷新无模块接口列表
          await fetchNoModuleInterfaces()
        }
      } catch (error: any) {
        Message.error(error.message || '删除接口失败')
      } finally {
        modalLoading.value = false
      }
    }
  })
}

const handleBatchDeleteInterfaces = (apis: ApiInterface[]) => {
  const targets = (apis || []).filter(item => item?.id != null)
  if (targets.length === 0) {
    Message.warning('请先选择要删除的接口')
    return
  }

  const namesPreview = targets
    .slice(0, 3)
    .map(item => item.name)
    .join('、')
  const moreText = targets.length > 3 ? ` 等 ${targets.length} 个接口` : ''
  const modalLoading = ref(false)

  Modal.error({
    title: '确认批量删除',
    content: `确定删除「${namesPreview}${moreText}」吗？删除后不可恢复。`,
    hideCancel: false,
    okText: '删除',
    cancelText: '取消',
    okButtonProps: {
      status: 'danger'
    },
    async onOk() {
      if (modalLoading.value) return
      modalLoading.value = true

      try {
        const ids = targets.map(item => item.id!)
        const previousActiveTabId = tabsStore.activeTabId
        const deletingCurrentInterface = !!selectedInterface.value?.id && ids.includes(selectedInterface.value.id)
        const previousActiveTab = previousActiveTabId
          ? tabsStore.tabs.find(tab => tab.id === previousActiveTabId)
          : undefined

        const response = await batchDeleteInterfaces(ids)
        const deletedIds = Array.isArray(response.data?.deleted_ids)
          ? response.data.deleted_ids.filter((id: any): id is number => Number.isInteger(id))
          : ids

        Message.success(response.data?.message || `成功删除 ${deletedIds.length} 个接口`)

        removeInterfacesFromLocalLists(deletedIds)
        pagination.value.total = Math.max(0, (pagination.value.total || 0) - deletedIds.length)

        const removedTabIds = deletedIds.flatMap(interfaceId => tabsStore.removeInterfaceTabs(interfaceId))

        if (
          removedTabIds.length === 0 &&
          deletingCurrentInterface &&
          previousActiveTab?.id &&
          !previousActiveTab.interfaceId
        ) {
          tabsStore.removeTab(previousActiveTab.id)
          removedTabIds.push(previousActiveTab.id)
        }

        if (selectedInterface.value?.id && deletedIds.includes(selectedInterface.value.id)) {
          selectedInterface.value = undefined
        }

        const deletedActiveTab = previousActiveTabId
          ? removedTabIds.includes(previousActiveTabId)
          : false

        if (deletedActiveTab) {
          if (tabsStore.activeTabId) {
            handleTabChange(tabsStore.activeTabId)
          } else {
            viewMode.value = 'list'
            detailKey.value++
          }
        }

        // 仅刷新当前已展开模块，与单删一致：先收起再展开触发 ModuleTree 重拉
        const moduleIds = Array.from(new Set(
          targets
            .map(item => item.module)
            .filter((moduleId): moduleId is number => typeof moduleId === 'number')
        ))
        const expandedModuleIds = moduleIds.filter(moduleId => expandedIds.value.includes(moduleId))
        if (expandedModuleIds.length > 0) {
          for (const moduleId of expandedModuleIds) {
            const index = expandedIds.value.indexOf(moduleId)
            if (index > -1) {
              expandedIds.value.splice(index, 1)
            }
          }
          await nextTick()
          await Promise.all(expandedModuleIds.map(async (moduleId) => {
            if (!expandedIds.value.includes(moduleId)) {
              expandedIds.value.push(moduleId)
            }
            await fetchInterfaces(moduleId)
          }))
        }
        if (targets.some(item => !item.module) || hasNoModuleInterfaces.value) {
          await fetchNoModuleInterfaces()
        }
        await fetchInterfaceListForDisplay()
      } catch (error: any) {
        Message.error(error?.message || '批量删除接口失败')
        throw error
      } finally {
        modalLoading.value = false
      }
    }
  })
}

// 编辑接口 - 进入接口详情编辑页面
const handleEditInterface = (api: ApiInterface) => {
  console.log('编辑接口:', api)
  selectedInterface.value = api
  // 创建或激活页签
  const tabId = tabsStore.openOrActivateInterface(api)
  viewMode.value = 'detail' // 切换到详情模式进行编辑
  
  // 如果是已存在的页签，强制触发状态恢复
  const existingTab = tabsStore.tabs.find(t => t.id === tabId)
  if (existingTab && existingTab.activeTab) {
    nextTick(() => {
      detailKey.value++
    })
  }
}

// 选择无模块接口
const handleSelectNoModuleInterface = async (api: ApiInterface) => {
  try {
    loading.value = true
    const response = await getInterfaceById(api.id!)
    selectedInterface.value = response.data
    // 创建或激活页签
    const tabId = tabsStore.openOrActivateInterface(response.data)
    // 切换到详情视图
    viewMode.value = 'detail'
    
    // 如果是已存在的页签，强制触发状态恢复
    const existingTab = tabsStore.tabs.find(t => t.id === tabId)
    if (existingTab && existingTab.activeTab) {
      nextTick(() => {
        detailKey.value++
      })
    }
    
    // 刷新无模块接口列表
    await fetchNoModuleInterfaces()
  } catch (error: any) {
    console.error('获取接口详情失败:', error)
    Message.error('获取接口详情失败')
    selectedInterface.value = api
    // 创建或激活页签
    const tabId = tabsStore.openOrActivateInterface(api)
    
    // 如果是已存在的页签，强制触发状态恢复
    const existingTab = tabsStore.tabs.find(t => t.id === tabId)
    if (existingTab && existingTab.activeTab) {
      nextTick(() => {
        detailKey.value++
      })
    }
    
    // 即使出错也要切换到详情视图
    viewMode.value = 'detail'
  } finally {
    loading.value = false
  }
}

// 处理接口刷新
const handleRefresh = async (moduleId?: number) => {
  try {
    loading.value = true
    console.log('刷新模块:', moduleId, '当前选中接口:', selectedInterface.value)
    
    // 如果有模块ID，确保模块是展开状态
    if (moduleId && !expandedIds.value.includes(moduleId)) {
      expandedIds.value.push(moduleId)
    }
    
    // 同时刷新模块列表和接口列表
    if (moduleId) {
      await Promise.all([
        fetchApiModules(),
        fetchInterfaces(moduleId)
      ])
    } else {
      // 如果是刷新无模块接口
      await Promise.all([
        fetchApiModules(),
        fetchNoModuleInterfaces() // 使用专门的无模块接口获取函数
      ])
    }

    // 如果有选中的接口且有ID，尝试在刷新后的接口列表中找到它
    if (selectedInterface.value && selectedInterface.value.id) {
      // 根据是否有模块ID决定在哪个列表中查找
      const list = moduleId ? interfaces.value : noModuleInterfaces.value
      const updatedInterface = list.find(item => item.id === selectedInterface.value?.id)
      if (updatedInterface) {
        console.log('更新选中接口:', updatedInterface)
        selectedInterface.value = updatedInterface
      }
    } else {
      // 如果没有选中的接口或选中的接口没有ID，查看是否有刚刚创建的新接口
      const list = moduleId ? interfaces.value : noModuleInterfaces.value
      if (list.length > 0) {
        // 获取最后一个接口作为新创建的接口
        const latestInterface = list[list.length - 1]
        console.log('选中最新创建的接口:', latestInterface)
        selectedInterface.value = latestInterface
      }
    }

    // 如果有模块ID，强制刷新模块展开状态
    if (moduleId) {
      const index = expandedIds.value.indexOf(moduleId)
      if (index > -1) {
        expandedIds.value.splice(index, 1)
        // 使用nextTick确保DOM更新后再重新展开
        nextTick(() => {
          expandedIds.value.push(moduleId)
        })
      }
    }
  } catch (error: any) {
    Message.error(error.message || '刷新接口列表失败')
  } finally {
    loading.value = false
  }
}

// 处理分页变化
const handleListFilterChange = (payload: {
  moduleId: number | null
  status: InterfaceStatus | ''
  sortField: 'created_at' | 'updated_at' | ''
  sortOrder: 'ascend' | 'descend' | ''
  keyword: string
}) => {
  // null=不限模块；number=指定模块（列表筛选显式生效，不再回退左侧树）
  listFilterModuleId.value = payload.moduleId
  listFilterStatus.value = payload.status
  listSortField.value = payload.sortField || 'created_at'
  listSortOrder.value = payload.sortOrder || 'descend'
  listSearchKeyword.value = payload.keyword || ''
  pagination.value.page = 1
  fetchInterfaceListForDisplay()
}

const handlePageChange = (page: number) => {
  pagination.value.page = page
  fetchInterfaceListForDisplay()
}

// 处理每页数量变化
const handlePageSizeChange = (pageSize: number) => {
  pagination.value.pageSize = pageSize
  pagination.value.page = 1 // 重置到第一页
  fetchInterfaceListForDisplay()
}

// 返回列表视图
const handleBackToList = () => {
  viewMode.value = 'list'
  selectedInterface.value = undefined
}

// 显示全部接口
const handleShowAllInterfaces = async () => {
  selectedApi.value = undefined
  viewMode.value = 'list'
  pagination.value.page = 1
  await fetchInterfaceListForDisplay()
}

// 处理列表中的接口操作 - 调试接口
const handleInterfaceRun = async (api: ApiInterface) => {
  console.log('调试接口:', api)
  // 先选中该接口
  selectedInterface.value = api
  // 创建或激活页签
  const tabId = tabsStore.openOrActivateInterface(api)
  // 设置自动调试标志
  autoDebug.value = true
  // 切换到详情模式
  viewMode.value = 'detail'
  
  // 如果是已存在的页签，强制触发状态恢复
  const existingTab = tabsStore.tabs.find(t => t.id === tabId)
  if (existingTab && existingTab.activeTab) {
    nextTick(() => {
      detailKey.value++
    })
  }
  // 在详情页面中会自动触发调试
}

// 处理模块树中的接口运行 - 调试接口
const handleRunInterface = async (api: ApiInterface) => {
  console.log('从模块树调试接口:', api)
  // 先选中该接口
  selectedInterface.value = api
  // 创建或激活页签
  const tabId = tabsStore.openOrActivateInterface(api)
  // 设置自动调试标志
  autoDebug.value = true
  // 切换到详情模式
  viewMode.value = 'detail'
  
  // 如果是已存在的页签，强制触发状态恢复
  const existingTab = tabsStore.tabs.find(t => t.id === tabId)
  if (existingTab && existingTab.activeTab) {
    nextTick(() => {
      detailKey.value++
    })
  }
  // 在详情页面中会自动触发调试
}

// 监听项目变化
watch(
  () => projectStore.currentProjectId,
  (newProjectId, oldProjectId) => {
    if (newProjectId !== oldProjectId) {
      tabsStore.clearInterfaceTabs()
      autoDebug.value = false
      detailKey.value++
    }

    selectedApi.value = undefined
    selectedInterface.value = undefined
    interfaces.value = []
    allInterfaces.value = []
    noModuleInterfaces.value = []
    hasNoModuleInterfaces.value = false
    expandedIds.value = []
    viewMode.value = 'detail'
    pagination.value.page = 1
    pagination.value.total = 0

    fetchApiModules()
    fetchInterfaceListForDisplay()
  }
)


// 新建接口
const handleCreateInterface = () => {
  // 清空选中的接口,但保留选中的模块
  console.log('准备创建新接口，清空当前选中接口')
  selectedInterface.value = undefined
  
  // 切换到详情视图模式
  viewMode.value = 'detail'
  
  // 创建新的空白页签
  tabsStore.createTab()
  
  // 强制重新渲染右侧组件，确保所有状态都被重置
  detailKey.value++
  
  // 使用nextTick确保在DOM更新后执行
  nextTick(() => {
    console.log('创建新接口模式已准备就绪')
  })
}

// 处理接口详情更新时，保存到当前页签
watch(() => selectedInterface.value, (newInterface) => {
  if (newInterface && tabsStore.activeTabId) {
    const activeTab = tabsStore.tabs.find(t => t.id === tabsStore.activeTabId)
    if (activeTab) {
      // 更新页签的接口信息
      tabsStore.updateTabRequest(tabsStore.activeTabId, {
        method: newInterface.method,
        url: newInterface.url,
        name: newInterface.name,
        module: newInterface.module,
        params: newInterface.params,
        headers: newInterface.headers,
        body: newInterface.body,
        setupHooks: newInterface.setup_hooks,
        teardownHooks: newInterface.teardown_hooks,
        extractRules: newInterface.extract,
        extractMeta: newInterface.extract_meta,
        assertRules: newInterface.validators
      })
    }
  }
}, { deep: true })

// 处理页签切换
const handleTabChange = (tabId: string) => {
  const tab = tabsStore.tabs.find(t => t.id === tabId)
  if (tab) {
    // 恢复页签的接口数据（不重新加载）
    if (tab.interfaceId) {
      // 尝试从各个列表中找到接口数据
      const foundInterface = [...interfaces.value, ...noModuleInterfaces.value, ...allInterfaces.value]
        .find(api => api.id === tab.interfaceId)
      
      if (foundInterface) {
        // 创建一个包含页签保存数据的接口对象
        selectedInterface.value = {
          ...foundInterface,
          // 恢复页签中保存的请求数据
          params: tab.params || foundInterface.params,
          headers: tab.headers || foundInterface.headers,
          body: tab.body || foundInterface.body,
          setup_hooks: tab.setupHooks || foundInterface.setup_hooks,
          teardown_hooks: tab.teardownHooks || foundInterface.teardown_hooks,
          extract: tab.extractRules || foundInterface.extract,
          extract_meta: tab.extractMeta || foundInterface.extract_meta,
          validators: tab.assertRules || foundInterface.validators
        }
      } else {
        selectedInterface.value = undefined
      }
    } else {
      // 新建接口页签
      selectedInterface.value = undefined
    }
    
    viewMode.value = 'detail'
    // 不再强制刷新，让 ApiDetail 组件自己处理状态恢复
    // detailKey.value++
  }
}

// 初始化时恢复页签
onMounted(async () => {
  // 恢复本地存储的页签
  tabsStore.loadFromLocalStorage(projectStore.currentProjectId)

  if (projectStore.currentProjectId) {
    await Promise.all([
      fetchApiModules(),
      fetchInterfaceListForDisplay()
    ])

    // 恢复当前激活页签对应的接口数据
    if (tabsStore.activeTabId) {
      const activeTab = tabsStore.tabs.find(t => t.id === tabsStore.activeTabId)
      if (activeTab?.interfaceId) {
        try {
          const { data } = await getInterfaces({
            project_id: Number(projectStore.currentProjectId),
            page_size: 1000
          })
          const restoredInterface = (data?.results || [])
            .find(api => api.id === activeTab.interfaceId)
          if (restoredInterface) {
            selectedInterface.value = {
              ...restoredInterface,
              params: activeTab.params || restoredInterface.params,
              headers: activeTab.headers || restoredInterface.headers,
              body: activeTab.body || restoredInterface.body,
              setup_hooks: activeTab.setupHooks || restoredInterface.setup_hooks,
              teardown_hooks: activeTab.teardownHooks || restoredInterface.teardown_hooks,
              extract: activeTab.extractRules || restoredInterface.extract,
              extract_meta: activeTab.extractMeta || restoredInterface.extract_meta,
              validators: activeTab.assertRules || restoredInterface.validators
            }
            viewMode.value = 'detail'
          } else {
            tabsStore.removeTab(activeTab.id)
            selectedInterface.value = undefined
            viewMode.value = 'list'
          }
        } catch {
          // 接口可能已删除，忽略
          tabsStore.removeTab(activeTab.id)
          selectedInterface.value = undefined
          viewMode.value = 'list'
        }
      }
    }
  }
})

// 保存页签到本地存储
watch(() => tabsStore.tabs, () => {
  tabsStore.saveToLocalStorage(projectStore.currentProjectId)
}, { deep: true })
</script>

<template>
  <div class="api-management h-full flex p-2 gap-2" :class="isDarkTheme ? 'api-management--dark' : 'api-management--light'">
    <!-- 左侧模块列表 -->
    <div class="w-80 flex flex-col">
      <div class="flex-1 bg-gray-800 rounded-lg shadow-lg overflow-hidden flex flex-col">
        <!-- 顶部标题和搜索栏 -->
        <div class="p-4 border-b border-gray-700/50 flex-shrink-0">
          <div class="flex justify-between items-center mb-4">
            <h2 class="text-lg font-medium text-gray-100">模块列表</h2>
            <div class="flex items-center gap-2">
              <input
                ref="openApiFileInput"
                type="file"
                accept=".json,.yaml,.yml,.har,.md,.markdown,.js,application/json,application/yaml,text/yaml,text/x-yaml,text/markdown"
                style="display: none"
                @change="handleOpenApiFileChange"
              />
              <a-dropdown trigger="click" @select="handleImportTypeSelect">
                <a-button
                  type="text"
                  size="small"
                  :loading="importingOpenApi"
                  :disabled="importingOpenApi || exportingOpenApi"
                  title="导入接口文档"
                >
                  <template #icon><icon-upload /></template>
                </a-button>
                <template #content>
                  <a-doption value="swagger">Swagger 文件</a-doption>
                  <a-doption value="swagger-url">Swagger URL</a-doption>
                  <a-doption value="postman">Postman</a-doption>
                  <a-doption value="curl">cURL</a-doption>
                  <a-doption value="markdown">Markdown</a-doption>
                  <a-doption value="har">HAR</a-doption>
                  <a-doption value="insomnia">Insomnia</a-doption>
                  <a-doption value="apidoc">ApiDoc</a-doption>
                  <a-doption value="apifox">Apifox</a-doption>
                  <a-doption value="apipost">Apipost</a-doption>
                  <a-doption value="yapi">YApi</a-doption>
                  <a-doption value="apizza">Apizza</a-doption>
                  <a-doption value="eolink">Eolink</a-doption>
                </template>
              </a-dropdown>
              <a-dropdown trigger="click" @select="handleExportOpenApi">
                <a-button
                  type="text"
                  size="small"
                  :loading="exportingOpenApi"
                  :disabled="importingOpenApi || exportingOpenApi"
                  title="导出接口文档"
                >
                  <template #icon><icon-download /></template>
                </a-button>
                <template #content>
                  <a-doption value="json">OpenAPI JSON</a-doption>
                  <a-doption value="yaml">OpenAPI YAML</a-doption>
                  <a-doption value="apifox">Apifox JSON</a-doption>
                  <a-doption value="apipost">Apipost JSON</a-doption>
                  <a-doption value="yapi">YApi JSON</a-doption>
                </template>
              </a-dropdown>
              <a-button type="text" size="small" @click="handleShowAllInterfaces" title="显示全部接口列表">
                <template #icon><icon-list /></template>
              </a-button>
              <a-button type="text" size="small" @click="handleOpenCreateForm()">
                <template #icon><icon-plus /></template>
                模块
              </a-button>
            </div>
          </div>
          <a-input-search
            v-model="searchKeyword"
            placeholder="搜索模块..."
            allow-clear
          >
            <template #prefix>
              <icon-search />
            </template>
          </a-input-search>
        </div>

        <!-- 模块列表内容 -->
        <div class="flex-1 min-h-0 overflow-hidden">
          <a-spin :loading="loading" dot class="!block h-full">
            <div class="h-full overflow-y-auto scrollbar-hide">
              <div class="py-2">
                <a-empty v-if="apis.length === 0" class="p-4">
                  暂无模块数据
                </a-empty>
                <template v-else>
                  <div class="space-y-1.5 m-2">
                    <!-- 未选择模块接口 -->
                    <div v-if="hasNoModuleInterfaces" class="mb-3">
                      <div
                        class="flex items-center justify-between px-3 py-2 rounded-md cursor-pointer hover:bg-gray-700/30"
                        :class="{ 'bg-gray-700/50': selectedApi === undefined && noModuleInterfaces.length > 0 }"
                        @click="selectedApi = undefined; interfaces = []; expandedIds = []"
                      >
                        <div class="flex items-center gap-2">
                          <icon-folder class="text-gray-400" />
                          <span class="text-gray-100 font-medium">未选择模块接口</span>
                          <a-tag size="small" type="arcoblue">{{ noModuleInterfaces.length }}</a-tag>
                        </div>
                        <div class="flex items-center">
                          <a-button type="text" size="mini" @click.stop="handleCreateInterface">
                            <template #icon><icon-plus /></template>
                          </a-button>
                        </div>
                      </div>

                      <!-- 无模块接口列表 -->
                      <div v-if="selectedApi === undefined" class="mt-1">
                        <a-spin :loading="loading" dot>
                          <div class="flex flex-col px-4">
                            <div
                              v-for="api in noModuleInterfaces"
                              :key="api.id"
                              class="no-module-interface-item !w-full !px-6 !py-2 !text-sm !text-gray-400 hover:!text-gray-300 !rounded !bg-[rgb(70,84,102,0.2)] hover:!bg-[rgb(70,84,102,0.4)] !min-w-0 !cursor-pointer !mt-1"
                              :class="{ '!bg-[rgb(70,84,102,0.4)]': selectedInterface?.id === api.id }"
                              @click="handleSelectNoModuleInterface(api)"
                            >
                              <div class="no-module-interface-main">
                                <div class="no-module-interface-info">
                                  <a-tag
                                    :color="api.method === 'GET' ? 'blue' : api.method === 'POST' ? 'green' : api.method === 'PUT' ? 'orange' : 'red'"
                                    class="!w-16 !flex !justify-center !flex-shrink-0"
                                  >
                                    {{ api.method }}
                                  </a-tag>
                                  <span class="no-module-interface-name !truncate" :title="api.name">{{ api.name }}</span>
                                </div>
                                <div class="no-module-interface-actions">
                                  <a-button
                                    type="text"
                                    size="mini"
                                    class="!p-0 !text-[#6b7785] hover:!text-[#86909c]"
                                    @click.stop="handleRunInterface(api)"
                                    title="调试接口"
                                  >
                                    <template #icon><icon-send /></template>
                                  </a-button>
                                  <a-button
                                    type="text"
                                    size="mini"
                                    class="!p-0 !text-[#6b7785] hover:!text-[#86909c]"
                                    @click.stop="handleEditInterface(api)"
                                    title="编辑接口"
                                  >
                                    <template #icon><icon-edit /></template>
                                  </a-button>
                                  <a-button
                                    type="text"
                                    size="mini"
                                    class="!p-0 !text-[#6b7785] hover:!text-[#86909c]"
                                    @click.stop="handleCopyInterface(api)"
                                    title="复制接口"
                                  >
                                    <template #icon><icon-copy /></template>
                                  </a-button>
                                  <a-button
                                    type="text"
                                    size="mini"
                                    class="!p-0 !text-[#6b7785] hover:!text-[#86909c]"
                                    @click.stop="handleDeleteInterface(api)"
                                  >
                                    <template #icon><icon-delete /></template>
                                  </a-button>
                                </div>
                              </div>
                            </div>
                          </div>
                        </a-spin>
                      </div>
                    </div>

                    <!-- 常规模块列表 -->
                    <ModuleTree
                      v-for="module in getFilteredModules"
                      :key="module.id"
                      :module="module"
                      :expanded-ids="expandedIds"
                      :selected-id="selectedApi?.id"
                      :form-loading="formLoading"
                      display-mode="detail"
                      @select="handleSelectModule"
                      @toggle-expand="handleToggleExpand"
                      @edit="handleOpenEditForm"
                      @add-child="handleOpenCreateForm"
                      @delete="handleDelete"
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

    <!-- 右侧内容区域 -->
    <div class="flex-1 min-w-0 overflow-hidden flex flex-col">
      <!-- 列表视图 -->
      <div v-if="viewMode === 'list'" class="h-full flex flex-col bg-gray-800 rounded-lg shadow-lg overflow-hidden">
        <!-- 顶部工具栏 -->
        <div v-if="selectedInterface" class="p-3 border-b border-gray-700 flex items-center justify-between">
          <div class="text-sm text-gray-400">
            已选择接口: <span class="text-gray-200">{{ selectedInterface.name }}</span>
          </div>
          <a-button size="small" type="primary" @click="viewMode = 'detail'">
            查看详情
          </a-button>
        </div>

        <!-- 接口列表 -->
        <div class="flex-1 overflow-hidden">
          <ApiInterfaceList
            :interfaces="allInterfaces"
            :loading="loading"
            :selected-interface-id="selectedInterface?.id"
            :current-module-name="currentModuleName"
            :modules="listModuleOptions"
            :filter-module-id="listFilterModuleId ?? null"
            :filter-status="listFilterStatus"
            :sort-field="listSortField"
            :sort-order="listSortOrder"
            @interface-select="handleSelectInterface"
            @interface-edit="handleEditInterface"
            @interface-delete="handleDeleteInterface"
            @interface-batch-delete="handleBatchDeleteInterfaces"
            @interface-copy="handleCopyInterface"
            @interface-run="handleInterfaceRun"
            @interface-status-change="handleInterfaceStatusChange"
            @filter-change="handleListFilterChange"
          />
        </div>

        <!-- 分页区域 -->
        <div v-if="pagination.total > 0" class="bg-gray-800/50 rounded-lg shadow-dark p-6">
          <ApiInterfacePagination
            :total="pagination.total"
            :page-size="pagination.pageSize"
            :current-page="pagination.page"
            @page-change="handlePageChange"
            @page-size-change="handlePageSizeChange"
          />
        </div>
      </div>

      <!-- 详情视图 -->
      <div v-else class="detail-view-shell h-full flex flex-col rounded-lg overflow-hidden">
        <!-- 页签栏 -->
        <ApiTabs
          :current-interface="selectedInterface"
          @tab-change="handleTabChange"
          @new-interface="handleCreateInterface"
        />

        <!-- 接口详情 -->
        <ApiDetail
          :key="detailKey"
          :modules="getFilteredModules"
          :selected-module="selectedApi"
          :interface="selectedInterface"
          :auto-debug="autoDebug"
          @refresh="handleRefresh"
          @update:interface="handleUpdateInterface"
          @debug-completed="autoDebug = false"
          class="flex-1"
        />
      </div>
    </div>

    <a-modal
      v-model:visible="importTextDialogVisible"
      :title="importTextDialogType === 'swagger' ? '通过 Swagger URL 导入' : '通过 cURL 导入'"
      :footer="false"
      :mask-closable="!importingOpenApi"
      :closable="!importingOpenApi"
      width="640px"
    >
      <a-input
        v-if="importTextDialogType === 'swagger'"
        v-model="importTextValue"
        placeholder="https://example.com/openapi.json"
        allow-clear
        @press-enter="handleImportTextConfirm"
      />
      <a-textarea
        v-else
        v-model="importTextValue"
        placeholder="curl -X POST https://example.com/api/..."
        :auto-size="{ minRows: 8, maxRows: 16 }"
      />
      <div class="mt-5 flex justify-end gap-2">
        <a-button :disabled="importingOpenApi" @click="importTextDialogVisible = false">取消</a-button>
        <a-button type="primary" :loading="importingOpenApi" @click="handleImportTextConfirm">导入</a-button>
      </div>
    </a-modal>

    <!-- 导入文件弹窗：选择格式 / 选择文件 / 去除域名开关 / 创建环境开关 -->
    <a-modal
      v-model:visible="importFileDialogVisible"
      title="导入接口文档"
      :footer="false"
      :mask-closable="!importingOpenApi"
      :closable="!importingOpenApi"
      width="560px"
      @cancel="resetImportFileDialog"
    >
      <div class="flex flex-col gap-4 import-file-dialog-body">
        <!-- 导入格式 -->
        <div class="flex items-center gap-3">
          <span class="w-20 flex-shrink-0 import-dialog-label">导入格式</span>
          <a-select
            v-model="importFileDialogType"
            :options="importFormatOptions"
            :disabled="importingOpenApi"
            placeholder="请选择导入格式"
            class="flex-1"
          />
        </div>

        <!-- 导入文件区域 -->
        <div>
          <div class="mb-1.5 import-dialog-label">导入文件</div>
          <div
            class="import-file-dropzone flex items-center justify-center gap-2 rounded-md border border-dashed border-gray-600 px-4 py-6 cursor-pointer hover:border-blue-500 transition-colors"
            :class="{ 'import-file-dropzone--active': importFileSelected }"
            @click="handlePickImportFile"
          >
            <template v-if="importFileSelected">
              <icon-upload class="import-dialog-icon" />
              <span class="import-dialog-filename truncate" :title="importFileSelected.name">
                {{ importFileSelected.name }}
              </span>
              <a-button
                type="text"
                size="mini"
                class="!p-0 import-dialog-clear-btn"
                :disabled="importingOpenApi"
                title="取消选择"
                @click.stop="importFileSelected = null"
              >
                <template #icon><icon-close /></template>
              </a-button>
            </template>
            <template v-else>
              <icon-upload class="import-dialog-icon" />
              <span class="import-dialog-hint">点击选择要导入的文件</span>
            </template>
          </div>
        </div>

        <!-- 开关1：去除 URL 里的域名 -->
        <div class="flex items-center justify-between rounded-md border border-gray-600/60 px-4 py-3 import-dialog-switch-row">
          <div class="pr-3">
            <div class="import-dialog-label">去除 URL 里的 http://...com</div>
            <div class="mt-0.5 text-xs import-dialog-hint">开启后接口默认去掉域名只保留 URL；关闭则导入完整 URL</div>
          </div>
          <a-switch v-model="stripBaseUrl" :disabled="importingOpenApi" />
        </div>

        <!-- 开关2：创建环境 -->
        <div class="flex items-center justify-between rounded-md border border-gray-600/60 px-4 py-3 import-dialog-switch-row">
          <div class="pr-3">
            <div class="import-dialog-label">创建环境</div>
            <div class="mt-0.5 text-xs import-dialog-hint">开启后识别接口 URL 前缀，在环境管理创建对应环境（同一域名仅创建一次）</div>
          </div>
          <a-switch v-model="createEnvironments" :disabled="importingOpenApi" />
        </div>
      </div>

      <!-- 右下角操作按钮 -->
      <div class="mt-5 flex justify-end gap-2">
        <a-button :disabled="importingOpenApi" @click="importFileDialogVisible = false">取消</a-button>
        <a-button type="primary" :loading="importingOpenApi" @click="handleImportFileConfirm">开始导入</a-button>
      </div>
    </a-modal>

    <!-- 模块表单弹窗 -->
    <ModuleForm
      v-model:visible="formVisible"
      :type="formType"
      :loading="formLoading"
      :apis="apis"
      :current-module="currentModule"
      :parent-id="formParentId"
      @submit="handleFormSubmit"
    />
  </div>
</template>

<style lang="postcss" scoped>
@reference "tailwindcss";
/* Switch 开关样式增强 */
:deep(.arco-switch) {
  @apply bg-gray-700 border border-gray-600;

  &.arco-switch-checked {
    @apply bg-blue-500 border-blue-500;
  }

  .arco-switch-handle {
    @apply bg-gray-100;
  }
}

/* 继承全局样式 */
:deep(.arco-empty) {
  @apply text-gray-500;
}

:deep(.arco-btn-primary) {
  @apply bg-blue-500 hover:bg-blue-600 border-blue-500 hover:border-blue-600;
}

:deep(.arco-tag-arcoblue) {
  @apply bg-blue-500/20 text-blue-500 border-blue-500/20;
}

/* 加载遮罩样式 */
:deep(.arco-spin) {
  .arco-spin-mask {
    @apply bg-transparent;
  }
  .arco-spin-dot {
    @apply border-blue-500;
  }
}

/* 隐藏滚动条但保留滚动功能 */
.scrollbar-hide {
  -ms-overflow-style: none;  /* IE and Edge */
  scrollbar-width: none;  /* Firefox */
}

.scrollbar-hide::-webkit-scrollbar {
  display: none;  /* Chrome, Safari and Opera */
}

/* 树形控件样式 */
:deep(.arco-tree) {
  @apply bg-transparent;

  .arco-tree-node {
    @apply bg-transparent hover:bg-gray-700/30;

    &.arco-tree-node-selected {
      @apply bg-gray-700/50;
    }
  }

  .arco-tree-node-title {
    @apply flex-1;
  }

  .arco-tree-node-switcher {
    @apply text-gray-400;
  }
}

/* 弹窗样式 */
:global(body.api-testing-theme .arco-modal-container) {
  .arco-modal-error {
    .arco-modal-title {
      @apply text-gray-100;
    }
    .arco-modal-body {
      @apply text-center;
    }
  }
}

:global(body.api-testing-theme .arco-modal-wrapper) {
  .arco-modal {
    @apply bg-gray-800 border border-gray-700;

    .arco-modal-header {
      @apply bg-gray-800 border-b border-gray-700;
      .arco-modal-title {
        @apply text-gray-100;
      }
    }

    .arco-modal-body {
      @apply bg-gray-800 text-center;
    }

    .arco-modal-content {
      @apply bg-gray-800 text-gray-300;
    }

    .arco-modal-footer {
      @apply bg-gray-800 border-t border-gray-700;
    }

    .arco-form-item-label {
      @apply text-gray-300;
    }

    .arco-input-wrapper {
      @apply bg-gray-900/60 border-gray-700;
      input {
        @apply text-gray-200;
        &::placeholder {
          @apply text-gray-500;
        }
      }
    }

    .arco-select-view {
      @apply bg-gray-900/60 border-gray-700;
      .arco-select-view-value {
        @apply text-gray-200;
      }
    }

    .arco-btn-secondary {
      @apply bg-gray-700 border-gray-600 text-gray-300;

      &:hover {
        @apply bg-gray-600 border-gray-500;
      }
    }

    .arco-btn-primary {
      @apply bg-blue-500 border-blue-500 text-white;

      &:hover {
        @apply bg-blue-600 border-blue-600;
      }
    }

    .arco-btn-danger {
      @apply bg-red-500 border-red-500 text-white;

      &:hover {
        @apply bg-red-600 border-red-600;
      }
    }
  }
}

:global(body.api-testing-theme .arco-select-dropdown) {
  @apply bg-gray-800 border border-gray-700;

  .arco-select-option {
    @apply text-gray-200;

    &:hover {
      @apply bg-gray-700/50;
    }

    &.arco-select-option-active {
      @apply bg-gray-700;
    }
  }
}

/* 亮色主题兜底：覆盖接口管理页主链路中写死的深色 utility class */
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

.api-management--dark :deep(.api-tabs-card) {
  background: var(--interface-dark-surface) !important;
  border-color: var(--interface-dark-border) !important;
  box-shadow: var(--interface-dark-shadow) !important;
}

.api-management--dark :deep(.tab-chip--active) {
  background: rgba(59, 130, 246, 0.18) !important;
  border-color: rgba(96, 165, 250, 0.38) !important;
  color: rgb(191, 219, 254) !important;
  box-shadow: 0 10px 18px rgba(15, 23, 42, 0.22) !important;
}

.api-management--dark :deep(.tab-chip--inactive) {
  background: var(--interface-dark-surface-muted) !important;
  border-color: var(--interface-dark-border) !important;
  color: var(--interface-dark-text-secondary) !important;
}

.api-management--dark :deep(.tab-chip--inactive:hover) {
  background: var(--interface-dark-hover) !important;
  border-color: rgba(96, 165, 250, 0.24) !important;
}

.api-management--dark :deep(.tabs-empty-hint) {
  color: var(--interface-dark-text-muted) !important;
}

.api-management--dark :deep(.api-detail) {
  --detail-shell-bg: var(--interface-dark-surface);
  --detail-shell-border: var(--interface-dark-border);
  --detail-shell-shadow: var(--interface-dark-shadow);
  --detail-tab-border: var(--interface-dark-border);
  --detail-tab-text: var(--interface-dark-text-muted);
  --detail-tab-active: rgb(var(--primary-6));
  --detail-resize-bg: var(--interface-dark-surface-muted);
  --detail-resize-bg-hover: rgba(59, 130, 246, 0.24);
  --detail-resize-line: var(--interface-dark-text-muted);
}

.api-management--dark :deep(.api-response) {
  --response-summary-border: var(--interface-dark-border);
  --response-summary-text: var(--interface-dark-text-muted);
  --response-shell-bg: var(--interface-dark-surface-soft);
  --response-shell-text: var(--interface-dark-text-secondary);
  --response-tab-border: var(--interface-dark-border);
  --response-tab-text: var(--interface-dark-text-muted);
  --response-tab-active: rgb(var(--primary-6));
  --response-copy-bg: rgba(30, 41, 59, 0.9);
  --response-copy-hover-bg: rgba(51, 65, 85, 0.96);
  --response-copy-icon: var(--interface-dark-text-secondary);
  --response-extracted-bg: rgba(30, 41, 59, 0.56);
  --response-extracted-hover-bg: rgba(51, 65, 85, 0.76);
}

.api-management--dark :deep(.api-request-header) {
  border-color: var(--interface-dark-border) !important;
}

.api-management--dark :deep(.module-select-shell) {
  border-color: var(--interface-dark-border) !important;
}

.api-management--dark :deep([class~='bg-gray-800']),
.api-management--dark :deep([class~='bg-gray-800/50']),
.api-management--dark :deep([class~='bg-gray-800/85']) {
  background-color: var(--interface-dark-surface) !important;
}

.api-management--dark :deep([class~='bg-gray-900/50']),
.api-management--dark :deep([class~='bg-gray-900/60']),
.api-management--dark :deep([class~='bg-gray-950']) {
  background-color: var(--interface-dark-surface-soft) !important;
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
.api-management--dark :deep(.arco-textarea-wrapper),
.api-management--dark :deep(.arco-select-view),
.api-management--dark :deep(.arco-pagination-jumper .arco-input-wrapper) {
  border-color: var(--interface-dark-border) !important;
  box-shadow: 0 0 0 1px rgba(148, 163, 184, 0.03) !important;
}

.api-management--dark :deep(.arco-tree .arco-tree-node:hover) {
  background-color: var(--interface-dark-hover) !important;
}

.api-management--dark :deep(.arco-tree .arco-tree-node.arco-tree-node-selected) {
  background-color: var(--interface-dark-hover-strong) !important;
}

.api-management--dark :deep(.arco-tabs-nav::before),
.api-management--dark :deep(.arco-tabs-tab),
.api-management--dark :deep(.arco-table-th),
.api-management--dark :deep(.arco-table-td),
.api-management--dark :deep(.arco-table-header) {
  border-color: var(--interface-dark-border) !important;
}

.api-management--dark .detail-view-shell {
  border: 1px solid rgba(148, 163, 184, 0.08);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.02);
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

.api-management--light :deep([class~='bg-gray-900/50']),
.api-management--light :deep([class~='bg-gray-900/60']),
.api-management--light :deep([class~='bg-gray-950']) {
  background-color: var(--interface-surface-soft) !important;
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

.api-management--light :deep([class~='hover:border-gray-600']:hover),
.api-management--light :deep([class~='hover:border-gray-500']:hover) {
  border-color: var(--interface-border) !important;
}

.api-management--light :deep(.arco-input-wrapper),
.api-management--light :deep(.arco-textarea-wrapper),
.api-management--light :deep(.arco-select-view),
.api-management--light :deep(.arco-pagination-jumper .arco-input-wrapper) {
  background-color: var(--interface-surface) !important;
  border-color: var(--interface-border) !important;
  box-shadow: none !important;
}

.api-management--light :deep(.arco-input-wrapper:hover),
.api-management--light :deep(.arco-textarea-wrapper:hover),
.api-management--light :deep(.arco-select-view:hover) {
  border-color: rgba(var(--theme-accent-rgb), 0.24) !important;
}

.api-management--light :deep(.arco-input-wrapper input),
.api-management--light :deep(.arco-input),
.api-management--light :deep(.arco-textarea),
.api-management--light :deep(.arco-select-view-value),
.api-management--light :deep(.arco-select-view-single .arco-select-view-value) {
  color: var(--interface-text-primary) !important;
}

.api-management--light :deep(.arco-input-wrapper input::placeholder),
.api-management--light :deep(.arco-textarea::placeholder),
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

.api-management--light :deep(.arco-tree .arco-tree-node:hover) {
  background-color: var(--interface-hover) !important;
}

.api-management--light :deep(.arco-tree .arco-tree-node.arco-tree-node-selected) {
  background-color: var(--interface-hover-strong) !important;
}

.api-management--light :deep(.arco-tree .arco-tree-node-switcher) {
  color: var(--interface-text-muted) !important;
}

.api-management--light :deep(.arco-tabs-nav::before),
.api-management--light :deep(.arco-tabs-tab) {
  border-color: var(--interface-border) !important;
}

.api-management--light :deep(.arco-tabs-tab),
.api-management--light :deep(.arco-tabs-tab-title),
.api-management--light :deep(.arco-tabs-tab-icon) {
  color: var(--interface-text-muted) !important;
}

.api-management--light :deep(.arco-tabs-tab:hover),
.api-management--light :deep(.arco-tabs-tab-active) {
  color: var(--interface-text-primary) !important;
}

.api-management--light :deep(.arco-table-header),
.api-management--light :deep(.arco-table-th),
.api-management--light :deep(.arco-table-thead > tr > .arco-table-th) {
  background-color: var(--interface-surface-soft) !important;
  color: var(--interface-text-primary) !important;
  border-color: var(--interface-border) !important;
}

.api-management--light :deep(.arco-table-td) {
  background-color: var(--interface-surface) !important;
  color: var(--interface-text-secondary) !important;
  border-color: var(--interface-border) !important;
}

.api-management--light .detail-view-shell {
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.72);
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

/* 导入文件弹窗：文件选择区域 */
.import-file-dropzone {
  transition: border-color 0.2s, background-color 0.2s;
}

.import-file-dropzone--active {
  border-style: solid;
}

/* 导入文件弹窗：文本/图标颜色（弹窗 teleport 到 body，需按主题区分） */
/* 浅色主题（body 无 api-testing-theme）：文本黑色 */
:global(body:not(.api-testing-theme) .import-file-dialog-body) {
  .import-dialog-label {
    color: #1d2129;
  }
  .import-dialog-hint {
    color: #4e5969;
  }
  .import-dialog-icon {
    color: #4e5969;
  }
  .import-dialog-filename {
    color: #1d2129;
  }
  .import-dialog-clear-btn {
    color: #86909c;
    &:hover {
      color: #1d2129;
    }
  }
  .import-dialog-switch-row {
    border-color: rgba(15, 23, 42, 0.12) !important;
  }
  .import-file-dropzone {
    border-color: rgba(15, 23, 42, 0.2) !important;
  }
}

/* 深色主题（body 含 api-testing-theme）：文本浅色 */
:global(body.api-testing-theme .import-file-dialog-body) {
  .import-dialog-label {
    color: #cbd5e1;
  }
  .import-dialog-hint {
    color: #94a3b8;
  }
  .import-dialog-icon {
    color: #94a3b8;
  }
  .import-dialog-filename {
    color: #f8fafc;
  }
  .import-dialog-clear-btn {
    color: #86909c;
    &:hover {
      color: #f8fafc;
    }
  }
}
</style>
