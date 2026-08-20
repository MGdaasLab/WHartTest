<script setup lang="ts">
import { ref, onMounted, watch, nextTick, computed } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { useAppI18n } from '@/composables/useAppI18n'
import { useProjectStore } from '@/store/projectStore'
import { useThemeStore } from '@/store/themeStore'
import {
  getDatabaseConfigs,
  createDatabaseConfig,
  updateDatabaseConfig,
  deleteDatabaseConfig,
  testDatabaseConnection,
  testConnection,
  type DatabaseConfig,
  type CreateDatabaseConfigData,
  type UpdateDatabaseConfigData,
  type TestConnectionData
} from '../../services/databaseConfigService'
import {
  IconPlus,
  IconEdit,
  IconDelete,
  IconLink,
  IconInfoCircle,
  IconExclamationCircle,
  IconStorage
} from '@arco-design/web-vue/es/icon'

const projectStore = useProjectStore()
const themeStore = useThemeStore()
const { isEnglish, tl } = useAppI18n()
const isDarkTheme = computed(() => themeStore.isBlack)
const databaseConfigs = ref<DatabaseConfig[]>([])
const loading = ref(false)
const showCreateModal = ref(false)
const showEditModal = ref(false)
const formLoading = ref(false)
const testingConnection = ref(false)
const activeButtonType = ref<'edit' | 'delete' | 'test' | null>(null)
const activeConfigId = ref<number | null>(null)

const panelText = computed(() => isEnglish.value
  ? {
      infoLine1: 'Database configs store the database connections used in the project',
      infoLine2: 'Refer to these configs by database name in test cases',
      infoLine3: 'For security reasons, database passwords are not displayed in the list',
      databaseConfigs: 'Database Configs',
      addDatabaseConfig: 'Add Database Config',
      host: 'Host',
      database: 'Database',
      username: 'Username',
      disabled: 'Disabled',
      testConnection: 'Test Connection',
      edit: 'Edit',
      delete: 'Delete',
      description: 'Description',
      noDatabaseConfigs: 'No database configs yet',
      noDatabaseDescription: 'Add database configs for use in test cases',
      createModalTitle: 'Add Database Config',
      editModalTitle: 'Edit Database Config',
      create: 'Create',
      save: 'Save',
      cancel: 'Cancel',
      configNameLabel: 'Config Name',
      configNamePlaceholder: 'Enter config name, e.g. Development Database',
      databaseTypeLabel: 'Database Type',
      selectDatabaseType: 'Select a database type',
      hostLabel: 'Host',
      hostPlaceholder: 'e.g. localhost or 192.168.1.1',
      portLabel: 'Port',
      databaseNameLabel: 'Database Name',
      databaseNamePlaceholder: 'Enter database name',
      usernameLabel: 'Username',
      usernamePlaceholder: 'Enter database username',
      passwordLabel: 'Password',
      passwordPlaceholder: 'Enter database password',
      editPasswordLabel: 'Password (leave blank to keep the current password)',
      descriptionPlaceholder: 'Enter description',
      enableConfig: 'Enable this config',
      fetchDatabaseConfigsFailed: 'Failed to load database configs',
      createDatabaseConfigSuccess: 'Database config created successfully',
      createDatabaseConfigFailed: 'Failed to create database config',
      updateDatabaseConfigSuccess: 'Database config updated successfully',
      updateDatabaseConfigFailed: 'Failed to update database config',
      deleteDatabaseConfigSuccess: 'Database config deleted successfully',
      deleteDatabaseConfigFailed: 'Failed to delete database config',
      testConnectionSuccess: 'Database connection test succeeded',
      testConnectionFailed: 'Database connection test failed',
      connectionFailed: (detail: string) => `Database connection failed: ${detail}`,
      confirmDeleteTitle: 'Confirm deletion',
      confirmDeleteContent: (name: string) => `Delete database config "${name}"?`,
      confirmDeleteAction: 'Delete',
    }
  : {
      infoLine1: '数据库配置用于存储项目中使用的数据库连接信息',
      infoLine2: '您可以在测试用例中通过数据库名称引用这些配置',
      infoLine3: '出于安全考虑，数据库密码不会显示在列表中',
      databaseConfigs: '数据库配置列表',
      addDatabaseConfig: '添加数据库配置',
      host: '主机',
      database: '数据库',
      username: '用户名',
      disabled: '已禁用',
      testConnection: '测试连接',
      edit: '编辑',
      delete: '删除',
      description: '描述',
      noDatabaseConfigs: '暂无数据库配置',
      noDatabaseDescription: '您可以添加数据库配置，在测试用例中使用这些数据库连接',
      createModalTitle: '添加数据库配置',
      editModalTitle: '编辑数据库配置',
      create: '创建',
      save: '保存',
      cancel: '取消',
      configNameLabel: '配置名称',
      configNamePlaceholder: '请输入配置名称，如：开发环境数据库',
      databaseTypeLabel: '数据库类型',
      selectDatabaseType: '请选择数据库类型',
      hostLabel: '主机地址',
      hostPlaceholder: '如：localhost 或 192.168.1.1',
      portLabel: '端口',
      databaseNameLabel: '数据库名称',
      databaseNamePlaceholder: '请输入数据库名称',
      usernameLabel: '用户名',
      usernamePlaceholder: '请输入数据库用户名',
      passwordLabel: '密码',
      passwordPlaceholder: '请输入数据库密码',
      editPasswordLabel: '密码（不填则保持原密码）',
      descriptionPlaceholder: '请输入描述信息',
      enableConfig: '启用该配置',
      fetchDatabaseConfigsFailed: '获取数据库配置列表失败',
      createDatabaseConfigSuccess: '创建数据库配置成功',
      createDatabaseConfigFailed: '创建数据库配置失败',
      updateDatabaseConfigSuccess: '更新数据库配置成功',
      updateDatabaseConfigFailed: '更新数据库配置失败',
      deleteDatabaseConfigSuccess: '删除数据库配置成功',
      deleteDatabaseConfigFailed: '删除数据库配置失败',
      testConnectionSuccess: '数据库连接测试成功',
      testConnectionFailed: '数据库连接测试失败',
      connectionFailed: (detail: string) => `数据库连接失败: ${detail}`,
      confirmDeleteTitle: '确认删除',
      confirmDeleteContent: (name: string) => `确定要删除数据库配置 "${name}" 吗？`,
      confirmDeleteAction: '删除',
    }
)

const translateErrorMessage = (message: unknown) => (
  typeof message === 'string' && message.trim() ? tl(message) : null
)

// 表单数据
const formData = ref<CreateDatabaseConfigData>({
  name: '',
  host: '',
  port: 3306,
  database: '',
  username: '',
  password: '',
  type: 'mysql',
  project: 0,
  is_active: true,
  verify_ssl: true
})

// 测试连接表单数据
const testConnectionForm = ref<any>({
  host: '',
  port: 3306,
  database: '',
  user: '',
  password: ''
})

// 当前编辑的数据库配置
const currentConfig = ref<DatabaseConfig | null>(null)

// 显示密码
const showPassword = ref(false)

// DOM元素引用
const containerRef = ref<HTMLElement | null>(null)
const configCardRef = ref<HTMLElement[]>([])
const iconContainerRef = ref<HTMLElement[]>([])
const valueContainerRef = ref<HTMLElement[]>([])
const buttonGroupRef = ref<HTMLElement[]>([])

// 计算尺寸信息
const getElementsSizes = (index: number) => {
  const containerEl = containerRef.value
  const cardEl = configCardRef.value[index]
  const iconEl = iconContainerRef.value[index]
  const valueEl = valueContainerRef.value[index]
  const buttonEl = buttonGroupRef.value[index]
  
  if (!containerEl || !cardEl || !iconEl || !valueEl || !buttonEl) {
    console.error('获取元素失败:', { containerEl, cardEl, iconEl, valueEl, buttonEl })
    return {
      containerWidth: 0,
      cardWidth: 0,
      innerWidth: 0,
      iconWidth: 0,
      buttonWidth: 0,
      valueWidth: 0,
      gap: 12,
      totalGap: 24,
      availableWidth: 0,
      expectedValueWidth: 0,
      difference: 0
    }
  }
  
  // 容器宽度计算
  const containerWidth = containerEl.clientWidth
  // 卡片的内边距 (p-3 = 3*4 = 12px 每边)
  const cardPadding = 24
  // 列表的右边距 (pr-1 = 1*4 = 4px)
  const listRightPadding = 4
  
  // 可用内容宽度 = 容器宽度 - 滚动条宽度和内边距
  const availableContainerWidth = containerWidth - listRightPadding
  
  // 元素宽度
  const iconWidth = iconEl.offsetWidth
  const buttonWidth = buttonEl.offsetWidth
  const valueWidth = valueEl.offsetWidth
  
  // 间距 (gap-3 = 3*4 = 12px)
  const gap = 12
  // 总间距 = 图标和键值对之间的间距 + 键值对和按钮组之间的间距
  const totalGap = gap * 2
  
  // 期望的键值对宽度 = 可用容器宽度 - 内边距 - 图标宽度 - 按钮组宽度 - 间距
  const expectedValueWidth = availableContainerWidth - cardPadding - iconWidth - buttonWidth - totalGap
  
  // 实际与期望的差异
  const difference = valueWidth - expectedValueWidth
  
  // 打印计算信息
  console.log(`==== 宽度计算 [${index}] ====`)
  console.log('容器宽度:', containerWidth)
  console.log('可用容器宽度:', availableContainerWidth)
  console.log('图标宽度:', iconWidth)
  console.log('键值对宽度(当前):', valueWidth)
  console.log('按钮组宽度:', buttonWidth)
  console.log('期望键值对宽度:', expectedValueWidth)
  console.log('差异:', difference)
  
  return {
    containerWidth,
    listRightPadding,
    availableContainerWidth,
    cardWidth: cardEl.offsetWidth,
    cardPadding,
    iconWidth,
    buttonWidth,
    valueWidth,
    gap,
    totalGap,
    expectedValueWidth,
    difference
  }
}

// 应用计算宽度到所有键值对容器
const applyCalculatedWidths = () => {
  if (!configCardRef.value.length || !containerRef.value) {
    console.warn('未找到DOM元素引用，无法应用宽度', {
      configCards: configCardRef.value.length,
      container: containerRef.value
    })
    return
  }
  
  // 使用requestAnimationFrame保证在下一帧渲染前更新
  requestAnimationFrame(() => {
    configCardRef.value.forEach((_, index) => {
      const sizes = getElementsSizes(index)
      const valueEl = valueContainerRef.value[index]
      
      if (valueEl && sizes.expectedValueWidth > 0) {
        console.log(`应用宽度 [${index}]: ${sizes.expectedValueWidth}px`)
        // 直接设置宽度，确保撑满空间
        valueEl.style.width = `${sizes.expectedValueWidth}px`
        valueEl.style.maxWidth = `${sizes.expectedValueWidth}px`
        valueEl.style.minWidth = `0px`
      }
      
      // 类型标签自适应：按标签内容实际宽度撑开类型列，保证完整包裹数据库类型文字
      const card = configCardRef.value[index]
      const tag = card?.querySelector('.type-tag')
      const typeCol = card?.querySelector('.col-type')
      if (tag && typeCol) {
        // offsetWidth 含 padding；scrollWidth 为内容宽度，取较大者保证完整包裹类型文字
        const tagWidth = Math.max(tag.offsetWidth, tag.scrollWidth + 12) // 12px = 标签左右 padding
        typeCol.style.minWidth = `${tagWidth + 8}px` // 8px = 列右侧间距
      }
    })
  })
}

// 主动触发宽度计算和应用的防抖函数
let recalculateDebounceTimer: number | null = null
const debouncedRecalculateWidths = () => {
  if (recalculateDebounceTimer) {
    clearTimeout(recalculateDebounceTimer)
  }
  
  recalculateDebounceTimer = window.setTimeout(() => {
    console.log('触发宽度重新计算')
    applyCalculatedWidths()
  }, 100)
}

// 监听容器宽度变化
const observeContainerWidth = () => {
  if (!containerRef.value) {
    console.warn('容器未找到，无法监听宽度变化')
    return
  }
  
  const resizeObserver = new ResizeObserver(() => {
    // 当容器宽度变化时，重新应用计算宽度
    console.log('容器宽度变化，重新计算')
    debouncedRecalculateWidths()
  })
  
  resizeObserver.observe(containerRef.value)
  
  return resizeObserver
}

// 加载数据库配置列表
const fetchDatabaseConfigs = async () => {
  if (!projectStore.currentProjectId) {
    databaseConfigs.value = []
    return
  }

  try {
    loading.value = true
    const response = await getDatabaseConfigs(Number(projectStore.currentProjectId))
    console.log('数据库配置返回数据:', response)
    
    // 修复：正确处理分页格式的返回数据
    if (response.data && Array.isArray(response.data.results)) {
      // 常见的分页格式 { count, next, previous, results: [] }
      databaseConfigs.value = response.data.results
    } else if (response.data && Array.isArray(response.data.data)) {
      // 如果返回的是 { data: [] } 格式
      databaseConfigs.value = response.data.data
    } else if (Array.isArray(response.data)) {
      // 如果直接返回数组
      databaseConfigs.value = response.data
    } else {
      // 其他情况，确保是空数组
      console.warn('获取数据库配置返回格式异常:', response)
      databaseConfigs.value = []
    }
    
    console.log('处理后的数据库配置列表:', databaseConfigs.value)
  } catch (error) {
    console.error('获取数据库配置列表失败:', error)
    Message.error(
      translateErrorMessage((error as any)?.response?.data?.message)
      || translateErrorMessage((error as Error)?.message)
      || panelText.value.fetchDatabaseConfigsFailed
    )
    databaseConfigs.value = [] // 确保在出错时是空数组
  } finally {
    loading.value = false
  }
}

// 监听项目变化
watch(
  () => projectStore.currentProjectId,
  () => {
    fetchDatabaseConfigs()
  }
)

// 创建数据库配置
const handleCreate = () => {
  resetForm()
  formData.value.project = Number(projectStore.currentProjectId)
  showCreateModal.value = true
}

// 重置表单
const resetForm = () => {
  formData.value = {
    name: '',
    host: '',
    port: 3306,
    database: '',
    username: '',
    password: '',
    type: 'mysql',
    project: Number(projectStore.currentProjectId),
    is_active: true,
    verify_ssl: true
  }
  showPassword.value = false
}

// 提交创建表单
const submitCreate = async () => {
  try {
    formLoading.value = true
    const response = await createDatabaseConfig(formData.value)
    console.log('创建数据库配置返回:', response)
    Message.success(panelText.value.createDatabaseConfigSuccess)
    showCreateModal.value = false
    await fetchDatabaseConfigs()
  } catch (error: any) {
    console.error('创建数据库配置失败:', error)
    Message.error(
      translateErrorMessage(error.response?.data?.message)
      || translateErrorMessage(error.message)
      || panelText.value.createDatabaseConfigFailed
    )
  } finally {
    formLoading.value = false
  }
}

// 编辑数据库配置
const handleEdit = (config: DatabaseConfig) => {
  activeButtonType.value = 'edit'
  activeConfigId.value = config.id
  currentConfig.value = config
  formData.value = {
    name: config.name,
    host: config.host,
    port: config.port,
    database: config.database,
    username: config.username,
    password: '',  // 密码不会从后端返回
    type: config.type,
    connection_params: config.connection_params,
    psm: config.psm,
    verify_ssl: config.verify_ssl,
    project: config.project,
    description: config.description,
    is_active: config.is_active
  }
  showEditModal.value = true
}

// 提交编辑表单
const submitEdit = async () => {
  if (!currentConfig.value) return

  try {
    formLoading.value = true
    const updateData: UpdateDatabaseConfigData = {
      name: formData.value.name,
      host: formData.value.host,
      port: formData.value.port,
      database: formData.value.database,
      username: formData.value.username,
      type: formData.value.type,
      connection_params: formData.value.connection_params,
      psm: formData.value.psm,
      verify_ssl: formData.value.verify_ssl,
      description: formData.value.description,
      is_active: formData.value.is_active
    }
    
    // 只有当用户输入了密码时才更新密码
    if (formData.value.password) {
      updateData.password = formData.value.password
    }
    
    const response = await updateDatabaseConfig(currentConfig.value.id, updateData)
    console.log('更新数据库配置返回:', response)
    Message.success(panelText.value.updateDatabaseConfigSuccess)
    showEditModal.value = false
    await fetchDatabaseConfigs()
  } catch (error: any) {
    console.error('更新数据库配置失败:', error)
    Message.error(
      translateErrorMessage(error.response?.data?.message)
      || translateErrorMessage(error.message)
      || panelText.value.updateDatabaseConfigFailed
    )
  } finally {
    formLoading.value = false
  }
}

// 删除数据库配置
const handleDelete = (config: DatabaseConfig) => {
  activeButtonType.value = 'delete'
  activeConfigId.value = config.id
  Modal.warning({
    title: panelText.value.confirmDeleteTitle,
    content: panelText.value.confirmDeleteContent(config.name),
    okText: panelText.value.confirmDeleteAction,
    cancelText: panelText.value.cancel,
    onOk: async () => {
      try {
        loading.value = true
        const response = await deleteDatabaseConfig(config.id)
        console.log('删除数据库配置返回:', response)
        Message.success(panelText.value.deleteDatabaseConfigSuccess)
        await fetchDatabaseConfigs()
      } catch (error: any) {
        console.error('删除数据库配置失败:', error)
        Message.error(
          translateErrorMessage(error.response?.data?.message)
          || translateErrorMessage(error.message)
          || panelText.value.deleteDatabaseConfigFailed
        )
      } finally {
        loading.value = false
      }
    }
  })
}

// 测试数据库连接（已保存的配置）
const handleTestConnection = async (config: DatabaseConfig) => {
  activeButtonType.value = 'test'
  activeConfigId.value = config.id
  try {
    testingConnection.value = true
    const response = await testDatabaseConnection(config.id)
    Message.success(panelText.value.testConnectionSuccess)
    console.log('测试结果:', response.data.test_result)
  } catch (error: any) {
    console.error('数据库连接测试失败:', error)
    if (error.response?.data?.errors?.connection) {
      Message.error(panelText.value.connectionFailed(tl(error.response.data.errors.connection[0])))
      return
    }
    Message.error(
      translateErrorMessage(error.response?.data?.message)
      || translateErrorMessage(error.message)
      || panelText.value.testConnectionFailed
    )
  } finally {
    testingConnection.value = false
    setTimeout(() => {
      activeButtonType.value = null
      activeConfigId.value = null
    }, 500)
  }
}

// 测试数据库连接（未保存的配置）
const handleTestFormConnection = async () => {
  // 使用当前表单数据进行测试
  testConnectionForm.value = {
    db_type: formData.value.type || 'mysql',
    host: formData.value.host,
    port: formData.value.port || 3306,
    database: formData.value.database,
    username: formData.value.username,
    password: formData.value.password
  }
  
  try {
    testingConnection.value = true
    const response = await testConnection(testConnectionForm.value)
    Message.success(panelText.value.testConnectionSuccess)
    console.log('测试结果:', response.data.test_result)
  } catch (error: any) {
    console.error('数据库连接测试失败:', error)
    if (error.response?.data?.errors?.connection) {
      const connectionError = error.response.data.errors.connection[0]
      const mysqlErrorMatch = connectionError.match(/\((\d+),\s*"(.+)"\)/)
      if (mysqlErrorMatch) {
        Message.error(panelText.value.connectionFailed(tl(mysqlErrorMatch[2])))
      } else {
        Message.error(panelText.value.connectionFailed(tl(connectionError)))
      }
      return
    }
    if (error.response?.data?.message) {
      const message = error.response.data.message
      const statusCodeMatch = message.match(/^\d+,\s*(.+)$/)
      Message.error(translateErrorMessage(statusCodeMatch ? statusCodeMatch[1] : message) || panelText.value.testConnectionFailed)
      return
    }
    Message.error(translateErrorMessage(error.message) || panelText.value.testConnectionFailed)
  } finally {
    testingConnection.value = false
  }
}

// 根据数据库类型更新默认端口
const updateDefaultPort = () => {
  const portMap: Record<string, number> = {
    mysql: 3306,
    postgresql: 5432,
    oracle: 1521,
  }
  
  if (formData.value.type && portMap[formData.value.type]) {
    formData.value.port = portMap[formData.value.type]
  }
}

// 仅在用户主动切换数据库类型时更新默认端口（编辑加载记录时不触发，避免覆盖自定义端口）
const handleTypeChange = () => {
  updateDefaultPort()
}

onMounted(() => {
  fetchDatabaseConfigs().then(() => {
    // 等待DOM更新
    nextTick(() => {
      setTimeout(() => {
        // 首次应用宽度
        console.log('初始化宽度计算')
        applyCalculatedWidths()
        
        // 设置监听
        observeContainerWidth()
        
        // 监听窗口大小变化
        window.addEventListener('resize', () => {
          console.log('窗口大小变化')
          debouncedRecalculateWidths()
        })
      }, 300)
    })
  })
})

// 监听数据变化
watch(databaseConfigs, () => {
  // 在数据变化后应用宽度
  console.log('数据库配置列表变化，重新计算宽度')
  nextTick(() => {
    setTimeout(() => {
      applyCalculatedWidths()
    }, 300)
  })
}, { deep: true })

// 关闭编辑模态框时重置按钮状态
watch(showEditModal, (newVal) => {
  if (!newVal) {
    setTimeout(() => {
      activeButtonType.value = null
      activeConfigId.value = null
    }, 200)
  }
})

// 对外暴露方法
defineExpose({
  handleCreate
})
</script>

<template>
  <div class="database-config-panel h-full overflow-hidden flex flex-col" :class="isDarkTheme ? 'database-config--dark' : 'database-config--light'">
    <!-- 说明信息卡片 -->
    <div class="info-card p-4 text-sm space-y-2 mb-4 rounded-lg flex-shrink-0">
      <div class="flex items-start gap-2">
        <icon-info-circle class="text-blue-400 mt-0.5 flex-shrink-0" />
        <div>{{ panelText.infoLine1 }}</div>
      </div>
      <div class="flex items-start gap-2">
        <icon-link class="text-teal-400 mt-0.5 flex-shrink-0" />
        <div>{{ panelText.infoLine2 }}</div>
      </div>
      <div class="flex items-start gap-2">
        <icon-exclamation-circle class="text-amber-400 mt-0.5 flex-shrink-0" />
        <div>{{ panelText.infoLine3 }}</div>
      </div>
    </div>

    <!-- 数据库配置列表标题 -->
    <div class="flex items-center gap-2 mb-4 flex-shrink-0">
      <icon-storage class="panel-title-icon" />
      <span class="panel-title-text font-medium">{{ panelText.databaseConfigs }}</span>
      
      <a-button 
        size="mini" 
        type="text" 
        class="ml-auto panel-action-btn"
        @click="handleCreate"
      >
        <template #icon>
          <icon-plus class="panel-action-icon" />
        </template>
        {{ panelText.addDatabaseConfig }}
      </a-button>
    </div>

    <!-- 列表内容 -->
    <div class="flex-1 overflow-y-auto pr-1 custom-scrollbar flex flex-col" ref="containerRef">
      <a-spin :loading="loading" dot class="flex-1 flex flex-col justify-center">
        <div class="space-y-2 pb-4 h-full flex flex-col" :class="{ 'justify-center': !databaseConfigs?.length && !loading }">
          <!-- 数据库配置卡片 -->
          <div
            v-for="(config, index) in databaseConfigs || []" 
            :key="config.id"
            class="config-card p-3 rounded-lg border transition-all duration-300"
            :class="{ 'opacity-60': !config.is_active }"
            :data-index="index"
            ref="configCardRef"
          >
            <!-- 单行显示：图标 + 配置信息 + 按钮组 -->
            <div class="flex items-center gap-3 w-full">
              <!-- 图标 -->
              <div 
                class="config-icon-shell w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                :data-index="index"
                ref="iconContainerRef"
              >
                <icon-storage class="text-purple-500" />
              </div>
              
              <!-- 配置信息 -->
              <div 
                class="config-value-shell flex-1 min-w-0 px-4 py-2 rounded text-sm overflow-visible"
                :data-index="index"
                ref="valueContainerRef"
              >
                <!-- 五列不等宽网格布局 -->
                <div class="grid grid-cols-5 gap-0 w-full custom-grid">
                  <!-- 第一列：名称 -->
                  <div class="overflow-visible whitespace-nowrap col-name">
                    <span class="config-name font-semibold inline-block">{{ config.name }}</span>
                  </div>
                  
                  <!-- 第二列：类型 (减小宽度) -->
                  <div class="overflow-visible whitespace-nowrap col-type">
                    <span class="type-tag">{{ config.type }}</span>
                  </div>
                  
                  <!-- 第三列：主机 (增加宽度) -->
                  <div class="overflow-hidden whitespace-nowrap text-ellipsis col-host justify-center">
                    <span class="config-meta-label text-xs font-medium mr-1">{{ panelText.host }}: </span>
                    <span class="config-meta-value whitespace-nowrap font-medium">{{ config.host }}:{{ config.port }}</span>
                  </div>
                  
                  <!-- 第四列：数据库 -->
                  <div class="overflow-hidden whitespace-nowrap text-ellipsis justify-center">
                    <span class="config-meta-label text-xs font-medium mr-1">{{ panelText.database }}: </span>
                    <span class="config-meta-value whitespace-nowrap font-medium">{{ config.database }}</span>
                  </div>
                  
                  <!-- 第五列：用户名 + 状态 -->
                  <div class="flex items-center overflow-visible whitespace-nowrap justify-between">
                    <div class="overflow-visible">
                      <span class="config-meta-label text-xs font-medium mr-1">{{ panelText.username }}: </span>
                      <span class="config-meta-value font-medium">{{ config.username }}</span>
                    </div>
                    <span v-if="!config.is_active" class="config-disabled-tag text-xs px-1.5 py-0.5 rounded ml-1 flex-shrink-0">{{ panelText.disabled }}</span>
                  </div>
                </div>
              </div>
              
              <!-- 操作按钮组 -->
              <div 
                class="flex flex-shrink-0 flex-nowrap ml-auto gap-2 button-group"
                :data-index="index"
                ref="buttonGroupRef"  
              >
                <a-button 
                  type="text" 
                  size="mini"
                  @click.stop="handleTestConnection(config)"
                  :loading="testingConnection"
                  :class="{ 'active-button': activeButtonType === 'test' && activeConfigId === config.id, 'test-button': true }"
                >
                  {{ panelText.testConnection }}
                </a-button>
                <a-button 
                  type="text" 
                  size="mini"
                  @click.stop="handleEdit(config)"
                  :class="{ 'active-button': activeButtonType === 'edit' && activeConfigId === config.id, 'edit-button': true }"
                >
                  <template #icon>
                    <icon-edit />
                  </template>
                  {{ panelText.edit }}
                </a-button>
                <a-button 
                  type="text" 
                  size="mini" 
                  status="danger"
                  @click.stop="handleDelete(config)"
                  :class="{ 'active-button': activeButtonType === 'delete' && activeConfigId === config.id, 'delete-button': true }"
                >
                  <template #icon>
                    <icon-delete />
                  </template>
                  {{ panelText.delete }}
                </a-button>
              </div>
            </div>
            
            <!-- 详细信息 -->
            <div v-if="config.description" class="config-description mt-2 text-xs px-2 py-1 pl-3">
              <span class="config-meta-label">{{ panelText.description }}:</span>
              <span class="config-meta-value ml-2">{{ config.description }}</span>
            </div>
          </div>
          
          <!-- 无数据时的提示 -->
          <div
            v-if="!databaseConfigs?.length && !loading"
            class="text-center py-10 px-4 flex flex-col items-center justify-center h-full flex-1"
          >
            <div class="mb-4">
              <div class="empty-state-icon-shell w-16 h-16 rounded-full flex items-center justify-center mx-auto">
                <icon-storage class="text-purple-500 text-2xl" />
              </div>
            </div>
            <div class="empty-state-title text-base mb-2 text-center">{{ panelText.noDatabaseConfigs }}</div>
            <div class="empty-state-description text-sm mb-6 max-w-md mx-auto text-center">
              {{ panelText.noDatabaseDescription }}
            </div>
            <a-button type="outline" @click="handleCreate">
              <template #icon><icon-plus /></template>
              {{ panelText.addDatabaseConfig }}
            </a-button>
          </div>
        </div>
      </a-spin>
    </div>

    <!-- 创建数据库配置弹窗 -->
    <a-modal
      v-model:visible="showCreateModal"
      :title="panelText.createModalTitle"
      @cancel="showCreateModal = false"
      @ok="submitCreate"
      :ok-loading="formLoading"
      :ok-text="panelText.create"
      :cancel-text="panelText.cancel"
      :mask-closable="false"
      :unmount-on-close="false"
      modal-class="config-modal"
      :width="650"
    >
      <a-form :model="formData" layout="vertical">
        <a-form-item field="name" :label="panelText.configNameLabel" required>
          <a-input v-model="formData.name" :placeholder="panelText.configNamePlaceholder" allow-clear />
        </a-form-item>
        
        <a-form-item field="type" :label="panelText.databaseTypeLabel" required>
          <a-select v-model="formData.type" :placeholder="panelText.selectDatabaseType" @change="handleTypeChange">
            <a-option value="mysql">MySQL</a-option>
            <a-option value="postgresql">PostgreSQL</a-option>
            <a-option value="oracle">Oracle</a-option>
          </a-select>
        </a-form-item>
        
        <div class="grid grid-cols-2 gap-4">
          <a-form-item field="host" :label="panelText.hostLabel" required>
            <a-input v-model="formData.host" :placeholder="panelText.hostPlaceholder" allow-clear />
          </a-form-item>
          
          <a-form-item field="port" :label="panelText.portLabel">
            <a-input-number v-model="formData.port" :placeholder="panelText.portLabel" :min="1" :max="65535" />
          </a-form-item>
        </div>
        
        <a-form-item field="database" :label="panelText.databaseNameLabel" required>
          <a-input v-model="formData.database" :placeholder="panelText.databaseNamePlaceholder" allow-clear />
        </a-form-item>
        
        <div class="grid grid-cols-2 gap-4">
          <a-form-item field="username" :label="panelText.usernameLabel" required>
            <a-input v-model="formData.username" :placeholder="panelText.usernamePlaceholder" allow-clear />
          </a-form-item>
          
          <a-form-item field="password" :label="panelText.passwordLabel" required>
            <a-input-password
              v-model="formData.password"
              :placeholder="panelText.passwordPlaceholder"
              allow-clear
              :hide-footer="false"
            />
          </a-form-item>
        </div>
        
        <a-form-item field="description" :label="panelText.description">
          <a-textarea v-model="formData.description" :placeholder="panelText.descriptionPlaceholder" />
        </a-form-item>
        
        <a-form-item field="is_active">
          <a-space>
            <a-checkbox v-model="formData.is_active">{{ panelText.enableConfig }}</a-checkbox>
          </a-space>
        </a-form-item>
        
        <div class="text-right">
          <a-button type="text" @click="handleTestFormConnection" :loading="testingConnection">
            {{ panelText.testConnection }}
          </a-button>
        </div>
      </a-form>
    </a-modal>
    
    <!-- 编辑数据库配置弹窗 -->
    <a-modal
      v-model:visible="showEditModal"
      :title="panelText.editModalTitle"
      @cancel="showEditModal = false"
      @ok="submitEdit"
      :ok-loading="formLoading"
      :ok-text="panelText.save"
      :cancel-text="panelText.cancel"
      :mask-closable="false"
      :unmount-on-close="false"
      modal-class="config-modal"
      :width="650"
    >
      <a-form :model="formData" layout="vertical">
        <a-form-item field="name" :label="panelText.configNameLabel" required>
          <a-input v-model="formData.name" :placeholder="panelText.configNamePlaceholder" allow-clear />
        </a-form-item>
        
        <a-form-item field="type" :label="panelText.databaseTypeLabel" required>
          <a-select v-model="formData.type" :placeholder="panelText.selectDatabaseType" @change="handleTypeChange">
            <a-option value="mysql">MySQL</a-option>
            <a-option value="postgresql">PostgreSQL</a-option>
            <a-option value="oracle">Oracle</a-option>
          </a-select>
        </a-form-item>
        
        <div class="grid grid-cols-2 gap-4">
          <a-form-item field="host" :label="panelText.hostLabel" required>
            <a-input v-model="formData.host" :placeholder="panelText.hostPlaceholder" allow-clear />
          </a-form-item>
          
          <a-form-item field="port" :label="panelText.portLabel">
            <a-input-number v-model="formData.port" :placeholder="panelText.portLabel" :min="1" :max="65535" />
          </a-form-item>
        </div>
        
        <a-form-item field="database" :label="panelText.databaseNameLabel" required>
          <a-input v-model="formData.database" :placeholder="panelText.databaseNamePlaceholder" allow-clear />
        </a-form-item>
        
        <div class="grid grid-cols-2 gap-4">
          <a-form-item field="username" :label="panelText.usernameLabel" required>
            <a-input v-model="formData.username" :placeholder="panelText.usernamePlaceholder" allow-clear />
          </a-form-item>
          
          <a-form-item field="password" :label="panelText.editPasswordLabel">
            <a-input-password
              v-model="formData.password"
              :placeholder="panelText.passwordPlaceholder"
              allow-clear
              :hide-footer="false"
            />
          </a-form-item>
        </div>
        
        <a-form-item field="description" :label="panelText.description">
          <a-textarea v-model="formData.description" :placeholder="panelText.descriptionPlaceholder" />
        </a-form-item>
        
        <a-form-item field="is_active">
          <a-space>
            <a-checkbox v-model="formData.is_active">{{ panelText.enableConfig }}</a-checkbox>
          </a-space>
        </a-form-item>
        
        <div class="text-right">
          <a-button type="text" @click="handleTestFormConnection" :loading="testingConnection">
            {{ panelText.testConnection }}
          </a-button>
        </div>
      </a-form>
    </a-modal>
  </div>
</template>

<style lang="postcss" scoped>
.database-config-panel {
  --db-text: var(--color-text-1);
  --db-text-muted: var(--color-text-2);
  --db-text-subtle: var(--color-text-3);
  --db-card-bg: rgba(255, 255, 255, 0.88);
  --db-card-border: rgba(148, 163, 184, 0.18);
  --db-card-hover-border: rgba(147, 51, 234, 0.45);
  --db-info-bg: linear-gradient(135deg, rgba(250, 245, 255, 0.96), rgba(248, 250, 252, 0.96));
  --db-info-border: rgba(148, 163, 184, 0.18);
  --db-value-bg: rgba(248, 250, 252, 0.94);
  --db-value-border: rgba(148, 163, 184, 0.16);
  --db-value-hover-bg: rgba(241, 245, 249, 0.98);
  --db-name-text: rgb(147, 51, 234);
  --db-type-bg: rgba(237, 233, 254, 0.85);
  --db-type-text: rgba(109, 40, 217, 0.92);
  --db-description-border: rgba(148, 163, 184, 0.22);
  --db-button-hover-bg: rgba(124, 58, 237, 0.05);
  --db-empty-shadow: 0 0 15px rgba(147, 51, 234, 0.12);
  --db-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
  --db-shadow-hover: 0 12px 26px rgba(15, 23, 42, 0.1);
}

.database-config--dark {
  --db-text: rgba(229, 231, 235, 0.94);
  --db-text-muted: rgba(209, 213, 219, 0.92);
  --db-text-subtle: rgba(156, 163, 175, 0.96);
  --db-card-bg: rgba(17, 24, 39, 0.6);
  --db-card-border: rgba(55, 65, 81, 1);
  --db-card-hover-border: rgba(147, 51, 234, 0.6);
  --db-info-bg: linear-gradient(to right, rgba(30, 41, 59, 0.7), rgba(30, 41, 59, 0.5));
  --db-info-border: rgba(55, 65, 81, 1);
  --db-value-bg: rgba(31, 41, 55, 0.5);
  --db-value-border: rgba(75, 85, 99, 0.3);
  --db-value-hover-bg: rgba(31, 41, 55, 0.82);
  --db-name-text: rgb(192, 132, 252);
  --db-type-bg: rgba(55, 65, 81, 0.8);
  --db-type-text: rgb(156, 163, 175);
  --db-description-border: rgba(55, 65, 81, 1);
  --db-button-hover-bg: rgba(124, 58, 237, 0.08);
  --db-empty-shadow: 0 0 15px rgba(147, 51, 234, 0.2);
  --db-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  --db-shadow-hover: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.info-card {
  font-size: 0.875rem;
  background: var(--db-info-bg);
  border: 1px solid var(--db-info-border);
  color: var(--db-text-muted);
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08);
}

.panel-title-icon,
.panel-action-icon,
.config-meta-label,
.empty-state-description,
.config-description {
  color: var(--db-text-subtle);
}

.panel-title-text,
.empty-state-title,
.config-meta-value {
  color: var(--db-text);
}

.config-name {
  color: var(--db-name-text);
}

.config-icon-shell,
.empty-state-icon-shell {
  background: rgba(147, 51, 234, 0.1);
}

.config-description {
  border-left: 2px solid var(--db-description-border);
}

.config-card {
  background: var(--db-card-bg);
  border-color: var(--db-card-border);
  box-shadow: var(--db-shadow);
  transition: all 0.2s;
  
  &:hover {
    border-color: var(--db-card-hover-border);
    transform: translateY(-2px);
    box-shadow: var(--db-shadow-hover);
  }
  
  /* 调整列宽度比例和间距 */
  .custom-grid {
    /* 名称/类型列 auto 自适应（类型列宽度由 JS 按标签内容动态撑开） */
    grid-template-columns: auto auto minmax(140px, 1fr) minmax(0, 1fr) minmax(0, 1fr) !important;
    column-gap: 0 !important;
  }
  
  /* 数据库/用户名列允许收缩（配合省略号截断），避免挤压名称与类型列 */
  .custom-grid > div:nth-child(4),
  .custom-grid > div:nth-child(5) {
    min-width: 0 !important;
  }
  
  .col-name {
    min-width: 0 !important;
    max-width: none !important;
    padding-right: 0 !important;
    margin-right: 0 !important;
    /* 名称过长时截断为省略号，避免溢出覆盖类型标签 */
    overflow: hidden !important;
  }
  
  .col-name .config-name {
    display: inline-block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    /* 不设置 max-width: 100%（会干扰 grid 轨道 max-content 计算） */
  }
  
  .col-type {
    width: auto !important;
    max-width: none !important;
    padding-left: 0 !important;
    padding-right: 8px !important;
    margin-left: 0 !important;
  }
  
  .col-host {
    min-width: 140px !important;
    padding-left: 8px !important;
  }
  
  /* 卡片布局结构 */
  .flex.items-center.gap-3.w-full {
    display: flex;
    align-items: center;
    width: 100%;
    
    /* 图标容器固定宽度（用精确类名，避免误匹配其他 first-child 元素） */
    .config-icon-shell {
      flex: 0 0 auto;
      width: 32px; /* 确保图标容器有固定宽度 */
    }
    
    /* 配置信息容器可伸缩 */
    > .config-value-shell {
      flex: 1 1 auto;
      min-width: 0;
      transition: all 0.2s ease;
      padding: 8px 12px;
      border-radius: 4px;
      background-color: var(--db-value-bg);
      border: 1px solid var(--db-value-border);
      color: var(--db-text-muted);
      position: relative;
      overflow: visible;
      box-sizing: border-box;
      
      /* 五列不等宽网格布局 */
      .grid.grid-cols-5 {
        display: grid;
        grid-template-columns: auto auto minmax(140px, 1fr) minmax(0, 1fr) minmax(0, 1fr);
        gap: 0.5rem;
        width: 100%;
        
        /* 创建不同的列间距 */
        > div:nth-child(1) {
          padding-right: 0;
        }
        
        > div:nth-child(2) {
          padding-left: 0;
        }
        
        /* 每列通用样式 */
        > div {
          overflow: visible;
          white-space: nowrap;
          
          /* 确保所有内容垂直居中 */
          display: flex;
          align-items: center;
          min-height: 24px;
          justify-content: flex-start;
          
          /* 第三、四、五列特殊处理 */
          &:nth-child(3),
          &:nth-child(4),
          &:nth-child(5) {
            justify-content: center;
          }
          
          /* 第五列特殊处理 */
          &:last-child {
            justify-content: space-between;
          }
        }
        
        /* 名称列样式 */
        .config-name {
          font-weight: 600;
          white-space: nowrap;
          overflow: visible;
        }
        
        /* 标签文本样式 */
        .config-meta-label {
          margin-right: 0.75rem;
          white-space: nowrap;
        }
        
        /* 值文本样式 */
        .config-meta-value {
          font-weight: 500;
        }
      }
      
      &:hover {
        background-color: var(--db-value-hover-bg);
      }
    }
    
    /* 按钮组固定宽度（用精确类名，避免误匹配其他 last-child 元素） */
    .button-group {
      flex: 0 0 auto;
      white-space: nowrap;
    }
  }
}

.config-disabled-tag {
  color: #ef4444;
  background-color: rgba(239, 68, 68, 0.1);
}

/* 自定义滚动条样式 */
.custom-scrollbar {
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE and Edge */
  
  &::-webkit-scrollbar {
    display: none; /* Chrome, Safari, Opera*/
  }
}

/* 响应式调整 */
@media (max-width: 1024px) {
  .config-card {
    .grid.grid-cols-5 {
      gap: 0.5rem;
    }
  }
}

/* 平板和较小屏幕适配 */
@media (max-width: 768px) {
  .config-card {
    /* 在平板上减少为四列 */
    .grid.grid-cols-5 {
      grid-template-columns: repeat(4, minmax(0, 1fr));
      
      /* 隐藏数据库列 */
      > div:nth-child(4) {
        display: none;
      }
    }
    
    .flex.flex-shrink-0.flex-nowrap {
      .arco-btn span {
        display: none;
      }
    }
  }
}

/* 极小屏幕适配 */
@media (max-width: 500px) {
  .config-card {
    .flex.items-center.gap-3.w-full {
      gap: 0.5rem;
    }
    
    .flex-1.min-w-0 {
      padding: 8px;
    }
    
    /* 在手机上减少为三列 */
    .grid.grid-cols-5 {
      grid-template-columns: repeat(3, minmax(0, 1fr));
      
      /* 隐藏类型列 */
      > div:nth-child(2) {
        display: none;
      }
    }
    
    .flex.flex-shrink-0.flex-nowrap {
      .arco-btn {
        padding: 0 4px;
      }
    }
  }
}

/* 补充按钮组样式，增加间距 */
.button-group {
  gap: 8px !important; /* 增加按钮之间的间距 */
  margin-left: 12px; /* 增加与前面元素的间距 */
}

.button-group > .arco-btn + .arco-btn {
  margin-left: 0 !important; /* 覆盖可能的默认边距 */
}

/* 确保测试连接按钮与其他按钮大小一致 */
:deep(.test-button) {
  min-width: 64px;
}

/* 编辑和删除按钮的宽度统一 */
:deep(.edit-button), 
:deep(.delete-button) {
  min-width: 52px;
}

/* 按钮基础样式调整 - 减小内边距使内容更紧凑 */
:deep(.arco-btn-text) {
  padding: 0 4px !important;
  height: 24px !important;
  line-height: 24px !important;
  font-size: 12px !important;
}

/* 编辑和删除按钮特殊内边距 */
:deep(.edit-button) {
  padding-left: 2px !important;
  padding-right: 4px !important;
}

:deep(.delete-button) {
  padding-left: 2px !important;
  padding-right: 8px !important;
}

/* 编辑和删除按钮选中状态的特殊内边距 */
:deep(.edit-button.active-button) {
  padding-left: 2px !important;
  padding-right: 4px !important;
}

:deep(.delete-button.active-button) {
  padding-left: 2px !important;
  padding-right: 8px !important;
}

/* 按钮悬停效果 */
:deep(.arco-btn-text:not([status="danger"]):hover) {
  background-color: var(--db-button-hover-bg);
  color: #a855f7;
}

:deep(.arco-btn[status="danger"]:hover) {
  background-color: rgba(239, 68, 68, 0.05);
}

/* 按钮点击效果 - 比悬停效果更强烈 */
:deep(.arco-btn-text:not([status="danger"]):active) {
  background-color: rgba(124, 58, 237, 0.2) !important;
  transform: translateY(0);
}

:deep(.arco-btn[status="danger"]:active) {
  background-color: rgba(239, 68, 68, 0.2) !important;
  transform: translateY(0);
}

/* 确保所有按钮都有平滑过渡 */
:deep(.arco-btn) {
  transition: all 0.2s ease;
}

/* 数据库类型标签样式调整 */
:deep(.type-tag) {
  font-size: 11px;
  text-transform: uppercase;
  color: var(--db-type-text);
  background-color: var(--db-type-bg);
  padding: 3px 6px;
  line-height: 1;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  letter-spacing: 0.05em;
  height: 18px;
  /* 强制标签按内容宽度展开，完整包裹数据库类型文字 */
  width: max-content;
  flex-shrink: 0;
}

/* 图标大小和对齐方式调整 */
:deep(.arco-btn-icon) {
  font-size: 14px !important;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 !important;
  margin: 0 !important;
  width: 14px !important;
  height: 14px !important;
}

/* 按钮内的图标和文字间距调整 - 全局设置 */
:deep(.arco-btn-icon + span) {
  margin-left: 0;
}

/* 特别针对编辑和删除按钮的图标间距调整 */
:deep(.edit-button .arco-btn-icon + span),
:deep(.delete-button .arco-btn-icon + span) {
  margin-left: -3px;
}

/* 添加选中按钮的样式 */
:deep(.active-button) {
  background-color: rgba(124, 58, 237, 0.15) !important;
  border-color: rgba(124, 58, 237, 0.5) !important;
  color: #a855f7 !important;
  transform: translateY(-1px);
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
  transition: all 0.2s ease;
  padding: 0 4px !important;
}

/* 删除按钮的选中样式特殊处理 */
:deep(.arco-btn[status="danger"].active-button) {
  background-color: rgba(239, 68, 68, 0.15) !important;
  border-color: rgba(239, 68, 68, 0.5) !important;
  color: #ef4444 !important;
  padding: 0 4px !important;
}

/* 编辑和删除按钮选中状态的特殊内边距 */
:deep(.edit-button.active-button) {
  padding-left: 2px !important;
  padding-right: 4px !important;
}

:deep(.delete-button.active-button) {
  padding-left: 2px !important;
  padding-right: 8px !important;
}
</style> 
