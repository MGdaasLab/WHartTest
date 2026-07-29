<script setup lang="ts">
import { ref, onMounted, watch, computed, nextTick, provide } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import { useProjectStore } from '@/store/projectStore'
import { IconPlus, IconSearch, IconFolder, IconEdit, IconDelete, IconList, IconApps, IconInfoCircle, IconSend, IconCopy } from '@arco-design/web-vue/es/icon'
import type { ApiModule, PaginatedData, ApiInterface } from '../../services/interfaceService'
import { getInterfaces, getInterfaceById, deleteInterface, duplicateInterface } from '../../services/interfaceService'
import { getModules, createModule, updateModule, deleteModule, moveModule } from '../../services/moduleService'
import { toArray } from '../../services/responseHelpers'
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
// 模块树显示模式: 'list' - 列表模式（不显示接口）, 'detail' - 详情模式（显示接口）
const treeDisplayMode = ref<'list' | 'detail'>('detail')
// 视图模式应该根据treeDisplayMode来决定默认值
const viewMode = ref<'list' | 'detail'>('detail')
// 分页相关状态
const pagination = ref({
  page: 1,
  pageSize: 20,
  total: 0
})
// 全部接口列表（用于列表模式）
const allInterfaces = ref<ApiInterface[]>([])
// 当前模块名称
const currentModuleName = computed(() => {
  if (!selectedApi.value) return '全部接口'
  return selectedApi.value.name
})

const toInterfaceList = (results: unknown): ApiInterface[] => {
  return toArray<ApiInterface>(results)
}

// 获取接口列表（支持分页）
const fetchInterfaceListForDisplay = async () => {
  if (!projectStore.currentProjectId) {
    allInterfaces.value = []
    return
  }

  try {
    loading.value = true
    const params = {
      project_id: Number(projectStore.currentProjectId),
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
      ...(selectedApi.value ? { module_id: selectedApi.value.id } : {})
    }

    const { data } = await getInterfaces(params)
    if (data) {
      const resultList = toInterfaceList(data.results ?? data)
      allInterfaces.value = resultList
      pagination.value.total = data.count || 0
      console.log(`获取到${resultList.length}个接口，总数：${data.count}`)
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
    const resultList = toInterfaceList(data?.results ?? data)
    if (resultList.length > 0) {
      interfaces.value = resultList
      console.log(`获取到${resultList.length}个接口`)
      // 如果有选中的接口，更新它的数据
      if (selectedInterface.value) {
        const updatedInterface = resultList.find(item => item.id === selectedInterface.value?.id)
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
    const resultList = toInterfaceList(data?.results ?? data)
    if (resultList.length > 0) {
      noModuleInterfaces.value = resultList
      hasNoModuleInterfaces.value = true
      console.log(`获取到${resultList.length}个无模块接口`)
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
    Message.error('移动后模块层级将超过5级限制')
    return
  }

  loading.value = true
  try {
    const response = await moveModule(dragged.id, {
      target_id: target.id,
      drop_position: position
    })

    if (response.status === 'success') {
      Message.success('模块排序/移动成功')
      await fetchApiModules()
    } else {
      Message.error(response.message || '移动模块失败')
    }
  } catch (error: any) {
    console.error('Failed to move module:', error)
    Message.error(error.message || '移动模块时发生错误')
  } finally {
    loading.value = false
    draggingModule.value = null
    dragOverModule.value = null
    dragOverPosition.value = null
  }
}
provide('handleModuleDrop', handleModuleDrop)

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

    apis.value = toArray<ApiModule>(response.data?.results ?? response.data)
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

// 切换展开状态
const handleToggleExpand = async (moduleId: number) => {
  const index = expandedIds.value.indexOf(moduleId)
  if (index === -1) {
    expandedIds.value.push(moduleId)
  } else {
    expandedIds.value.splice(index, 1)
  }
  // 同时获取该模块的接口列表
  await fetchInterfaces(moduleId)
}

// 选择模块
const handleSelectModule = async (module: ApiModule) => {
  selectedApi.value = module

  // 根据树显示模式决定右侧显示什么
  if (treeDisplayMode.value === 'list') {
    // 列表模式：点击模块显示接口列表
    viewMode.value = 'list'
    pagination.value.page = 1 // 重置页码

    try {
      loading.value = true
      const { data } = await getInterfaces({
        module_id: module.id,
        project_id: Number(projectStore.currentProjectId),
        page_size: 1000 // 设置较大的页面大小，确保能显示所有接口
      })
      const resultList = toInterfaceList(data?.results ?? data)
      if (resultList.length > 0) {
        console.log(`模块${module.name}获取到${resultList.length}个接口`)
      }
      interfaces.value = resultList
    } catch (error: any) {
      Message.error(error.message || '获取接口列表失败')
      interfaces.value = []
    } finally {
      loading.value = false
    }

    // 获取用于列表显示的接口数据
    await fetchInterfaceListForDisplay()
  } else {
    // 详情模式：保持原有逻辑，展开模块显示接口
    try {
      loading.value = true
      const { data } = await getInterfaces({
        module_id: module.id,
        project_id: Number(projectStore.currentProjectId),
        page_size: 1000
      })
      const resultList = toInterfaceList(data?.results ?? data)
      if (resultList.length > 0) {
        console.log(`模块${module.name}获取到${resultList.length}个接口`)
        // 如果有接口数据，就展开该模块
        if (!expandedIds.value.includes(module.id)) {
          expandedIds.value.push(module.id)
        }
      }
      interfaces.value = resultList
    } catch (error: any) {
      Message.error(error.message || '获取接口列表失败')
      interfaces.value = []
    } finally {
      loading.value = false
    }
  }
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
  () => {
    fetchApiModules()
    selectedApi.value = undefined
    selectedInterface.value = undefined
    interfaces.value = []
    noModuleInterfaces.value = []
    hasNoModuleInterfaces.value = false
    expandedIds.value = []
    viewMode.value = 'detail'
    pagination.value.page = 1
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
  tabsStore.loadFromLocalStorage()

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
  tabsStore.saveToLocalStorage()
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
            @interface-select="handleSelectInterface"
            @interface-edit="handleEditInterface"
            @interface-delete="handleDeleteInterface"
            @interface-copy="handleCopyInterface"
            @interface-run="handleInterfaceRun"
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
</style>
