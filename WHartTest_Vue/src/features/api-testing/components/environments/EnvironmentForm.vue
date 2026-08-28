<script setup lang="ts">
import { ref, onMounted, computed, watch, onBeforeMount } from 'vue'
import type { Environment, EnvironmentVariable, CreateEnvironmentVariableData, NewEnvironmentVariableData, VariableType } from '../../services/environmentService'
import { deleteEnvironmentVariable, createEnvironmentVariable, updateEnvironmentVariable, VARIABLE_TYPES } from '../../services/environmentService'
import { getDatabaseConfigs, type DatabaseConfig } from '../../services/databaseConfigService'
import { toArray } from '../../services/responseHelpers'
import { Message } from '@arco-design/web-vue'
import {
  IconPlus,
  IconEdit,
  IconSettings,
  IconInfoCircle,
  IconStorage,
  IconLink,
  IconCode,
  IconLock,
  IconRefresh
} from '@arco-design/web-vue/es/icon'
import EnvironmentVariableForm from './EnvironmentVariableForm.vue'
import EnvironmentVariableList from './EnvironmentVariableList.vue'
import type { FormInstance } from '@arco-design/web-vue'
import { useAppI18n } from '@/composables/useAppI18n'
import { useProjectStore } from '@/store/projectStore'

interface Props {
  mode: 'create' | 'edit'
  loading: boolean
  modelValue: {
    id?: number
    name: string
    base_url: string
    description: string
    project: number
    is_active: boolean
    variables: EnvironmentVariable[]
    database_config?: number | null
    verify_ssl?: boolean
  }
}

interface Emits {
  (e: 'update:modelValue', value: Props['modelValue']): void
  (e: 'cancel'): void
  (e: 'submit'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()
const projectStore = useProjectStore()
const { isEnglish } = useAppI18n()

const formText = computed(() => isEnglish.value
  ? {
      loadingDatabaseConfigs: 'Loading database configs...',
      noDatabaseConfigs: 'No database configs',
      noLinkedDatabase: 'No linked database',
      enableEnvironment: 'Enable environment',
      disableEnvironment: 'Disable environment',
      guide: 'Guide',
      guideLine1: 'Variable names must be unique and valid identifiers',
      guideLine2: 'Both variable name and value are required',
      guideLine3: 'Link a database config to access it in test cases',
      databaseConfigId: 'Database Config ID',
    }
  : {
      loadingDatabaseConfigs: '正在加载数据库配置...',
      noDatabaseConfigs: '无数据库配置',
      noLinkedDatabase: '不关联数据库',
      enableEnvironment: '启用环境',
      disableEnvironment: '禁用环境',
      guide: '使用说明',
      guideLine1: '变量名不能重复，且必须是有效的标识符',
      guideLine2: '变量名和变量值都是必填项',
      guideLine3: '关联数据库配置后，您可以在测试用例中访问该数据库',
      databaseConfigId: '数据库配置 ID',
    }
)

// 检查并保证database_config值的一致性
if (props.modelValue.database_config !== null && 
    props.modelValue.database_config !== undefined && 
    (props.modelValue.database_config as any) !== "null" &&
    typeof props.modelValue.database_config !== 'string') {
  console.log('初始化modelValue的database_config值:', props.modelValue.database_config, '类型:', typeof props.modelValue.database_config)
} else {
  if (props.modelValue.database_config === null || props.modelValue.database_config === undefined) {
    console.log('将null/undefined的database_config值设为"null"')
    
    // 注意：这种方式会触发一次更新，但这是必要的，确保初始值正确
    setTimeout(() => {
      emit('update:modelValue', {
        ...props.modelValue,
        database_config: "null" as any
      })
    }, 0)
  }
}

// 添加一个计算属性，用于监视和调试环境数据中是否包含database_config_info
const hasDatabaseConfigInfo = computed(() => {
  const env = props.modelValue as any
  return !!(env && env.database_config_info)
})

// 当环境对象中有database_config_info信息时，使用其ID作为database_config的值
watch(() => hasDatabaseConfigInfo.value, (hasInfo) => {
  if (hasInfo) {
    const env = props.modelValue as any
    if (env.database_config_info && env.database_config_info.id) {
      console.log('检测到database_config_info，使用其ID更新database_config值:', env.database_config_info.id)
      emit('update:modelValue', {
        ...props.modelValue,
        database_config: env.database_config_info.id
      })
      
      // 如果数据库配置列表为空，则添加从环境详情中获取的数据库配置
      if (databaseConfigs.value.length === 0 && env.database_config_info) {
        const dbInfo = env.database_config_info;
        databaseConfigs.value = [{
          id: dbInfo.id,
          name: dbInfo.name,
          host: dbInfo.host || '',
          db_type: dbInfo.db_type || dbInfo.type || 'mysql',
          is_active: true
        } as DatabaseConfig];
        console.log('从环境详情中添加了数据库配置到下拉列表:', databaseConfigs.value);
      }
    }
  }
}, { immediate: true })

const formRef = ref<FormInstance>()
const editVariableVisible = ref(false)
const editingVariableIndex = ref(-1)
const databaseConfigs = ref<DatabaseConfig[]>([])
const loadingDatabaseConfigs = ref(false)
const forceRefresh = ref(false)

// 获取数据库配置列表
const fetchDatabaseConfigs = async () => {
  // 优先使用表单中的项目ID，如果不存在则使用当前选中的项目ID
  const projectId = props.modelValue.project || Number(projectStore.currentProjectId)
  
  if (!projectId) {
    console.error('缺少项目ID，无法获取数据库配置列表')
    return
  }
  
  try {
    console.log('开始获取数据库配置列表，项目ID:', projectId, '模式:', props.mode)
    loadingDatabaseConfigs.value = true
    const response = await getDatabaseConfigs(projectId)
    console.log('数据库配置原始响应:', JSON.stringify(response))
    
    databaseConfigs.value = toArray<any>(response.data?.results ?? response.data).map((item: any) => ({
      id: item.id,
      name: item.name,
      host: item.host || '',
      db_type: item.db_type || item.type,
      is_active: item.is_active !== false
    } as DatabaseConfig));
    console.log('获取数据库配置列表数量:', databaseConfigs.value.length);
    
    // 如果当前环境有database_config_info但不在列表中，添加到列表
    const env = props.modelValue as any;
    if (env.database_config_info && !databaseConfigs.value.some(item => item.id === env.database_config_info.id)) {
      databaseConfigs.value.push({
        id: env.database_config_info.id,
        name: env.database_config_info.name,
        host: env.database_config_info.host || '',
        db_type: env.database_config_info.db_type,
        is_active: true
      } as DatabaseConfig);
      console.log('已将当前环境的数据库配置添加到列表中');
    }

    // 强制更新视图
    setTimeout(() => {
      console.log('数据库配置下拉框选项:', databaseConfigs.value.map(c => ({ id: c.id, name: c.name })))
      forceRefresh.value = !forceRefresh.value;
    }, 0);
    
  } catch (error) {
    console.error('获取数据库配置列表失败', error)
    Message.error('获取数据库配置列表失败')
    databaseConfigs.value = []
  } finally {
    loadingDatabaseConfigs.value = false
  }
}

// 格式化数据库选择器显示内容
const formatDatabaseSelection = (value: number | null | string) => {
  if (!value || value === "null") return formText.value.noLinkedDatabase;
  
  console.log('格式化数据库选择器显示内容，当前值:', value, '类型:', typeof value);
  
  // 如果value是字符串但表示数字，将其转换为数字进行比较
  const numericValue = typeof value === 'string' && !isNaN(Number(value)) ? Number(value) : value;
  
  // 尝试从databaseConfigs中找到匹配的配置
  const config = databaseConfigs.value.find(item => item.id === numericValue);
  if (config) {
    console.log('通过数据库配置列表匹配到了配置:', config.name);
    return config.name;
  }
  
  // 如果在列表中找不到，尝试从环境的database_config_info中获取
  const env = props.modelValue as any;
  if (env.database_config_info && env.database_config_info.id === numericValue) {
    // 如果找到匹配的配置信息但不在列表中，添加到列表
    if (!databaseConfigs.value.some(item => item.id === env.database_config_info.id)) {
      databaseConfigs.value.push({
        id: env.database_config_info.id,
        name: env.database_config_info.name,
        host: env.database_config_info.host || '',
        db_type: env.database_config_info.db_type,
        is_active: true
      } as DatabaseConfig);
      console.log('从database_config_info添加配置到列表中');
      forceRefresh.value = !forceRefresh.value;
    }
    return env.database_config_info.name;
  }
  
  return `${formText.value.databaseConfigId}: ${value}`;
}

// 添加创建时的日志
onBeforeMount(() => {
  console.log('[onBeforeMount] 组件即将挂载，准备注册事件处理函数')
})

// 处理下拉框显示状态变化 - 使用更明确的函数名称
const onDropdownVisibleChange = async (visible: boolean) => {
  // 获取可靠的项目ID
  const projectId = props.modelValue.project || Number(projectStore.currentProjectId)
  
  console.log('====> 下拉框状态变化事件被触发:', visible, '项目ID:', projectId, '当前数据库配置数量:', databaseConfigs.value.length)
  console.log('当前数据库配置值:', props.modelValue.database_config, '类型:', typeof props.modelValue.database_config)
  
  // 只在打开下拉框时加载最新数据库配置列表
  if (visible && projectId) {
    console.log('====> 下拉框打开，准备加载最新的数据库配置列表')
    try {
      await fetchDatabaseConfigs()
      
      // 如果当前有选中的数据库配置，确保它在列表中
      if (props.modelValue.database_config && (props.modelValue.database_config as any) !== "null") {
        const env = props.modelValue as any;
        if (env.database_config_info && !databaseConfigs.value.some(item => item.id === env.database_config_info.id)) {
          // 如果database_config_info存在但不在列表中，添加到列表
          databaseConfigs.value.push({
            id: env.database_config_info.id,
            name: env.database_config_info.name,
            host: env.database_config_info.host || '',
            db_type: env.database_config_info.db_type || env.database_config_info.type || 'mysql',
            is_active: true
          } as DatabaseConfig);
          console.log('已将当前选中的数据库配置添加到列表中');
          // 强制刷新视图
          forceRefresh.value = !forceRefresh.value;
        }
      }
    } catch (error) {
      console.error('加载数据库配置列表失败:', error);
    }
  }
}

// 将原函数指向新函数，保持兼容性
const handleDropdownVisibleChange = onDropdownVisibleChange

// 在组件创建时，只在编辑模式下加载数据库配置用于回显
onMounted(async () => {
  // 获取可靠的项目ID
  const projectId = props.modelValue.project || Number(projectStore.currentProjectId)
  
  console.log('[onMounted] 组件挂载，模式:', props.mode, '项目ID:', projectId, '数据库配置:', props.modelValue.database_config)
  
  // 只在编辑模式下预加载数据库配置，用于初始回显
  if (projectId && props.mode === 'edit') {
    console.log('[onMounted] 编辑模式下预加载数据库配置列表用于回显')
    try {
      await fetchDatabaseConfigs()
      
      // 如果有database_config_info，确保它在列表中
      const env = props.modelValue as any;
      if (env.database_config_info && !databaseConfigs.value.some(item => item.id === env.database_config_info.id)) {
        databaseConfigs.value.push({
          id: env.database_config_info.id,
          name: env.database_config_info.name,
          host: env.database_config_info.host || '',
          db_type: env.database_config_info.db_type,
          is_active: true
        } as DatabaseConfig);
        console.log('已将当前环境的数据库配置添加到列表中');
        forceRefresh.value = !forceRefresh.value;
      }
    } catch (error) {
      console.error('预加载数据库配置失败:', error);
    }
  }
})

// 监听modelValue变化，确保database_config_info被正确处理
watch(() => props.modelValue, (newVal) => {
  const env = newVal as any;
  if (env.database_config_info && !databaseConfigs.value.some(item => item.id === env.database_config_info.id)) {
    databaseConfigs.value.push({
      id: env.database_config_info.id,
      name: env.database_config_info.name,
      host: env.database_config_info.host || '',
      db_type: env.database_config_info.db_type,
      is_active: true
    } as DatabaseConfig);
    console.log('modelValue变化：已将数据库配置添加到列表中');
    forceRefresh.value = !forceRefresh.value;
  }
}, { deep: true })

// 只监听进入编辑模式，确保编辑模式下有数据用于回显
watch(() => props.mode, (newMode, oldMode) => {
  console.log('模式变化:', oldMode, '->', newMode)
  // 只在进入编辑模式时加载一次
  if (newMode === 'edit' && oldMode !== 'edit') {
    const projectId = props.modelValue.project || Number(projectStore.currentProjectId)
    if (projectId) {
      console.log('进入编辑模式，加载数据库配置列表用于回显')
      fetchDatabaseConfigs()
    }
  }
})

// 监听database_config变化，输出日志信息
watch(() => props.modelValue.database_config, (newValue) => {
  console.log('数据库配置值变化:', newValue)
}, { immediate: true })

// 处理清除数据库配置
const handleClearDatabaseConfig = () => {
  const updatedModel = { ...props.modelValue };
  updatedModel.database_config = "null" as any;
  emit('update:modelValue', updatedModel);
}

const editingVariable = ref<EnvironmentVariable>({
  id: 0,
  name: '',
  value: '',
  type: 'string',
  description: '',
  is_sensitive: false
} as EnvironmentVariable)

const newVariable = ref<NewEnvironmentVariableData>({
  name: '',
  value: '',
  type: 'string',
  description: '',
  is_sensitive: false
})

// 表单校验规则
const rules = {
  name: [
    { required: true, message: '请输入环境名称' }
  ],
  base_url: [
    { required: true, message: '请输入基础URL' },
    { 
      match: /^https?:\/\/.+/,
      message: '请输入有效的URL地址'
    }
  ]
}

const handleAddVariable = async () => {
  console.log('添加变量:', {
    mode: props.mode,
    environmentId: props.modelValue.id,
    newVariable: newVariable.value
  })

  if (!newVariable.value.name || !newVariable.value.value) {
    return
  }

  // 在编辑模式下，直接调用 API 添加变量
  if (props.mode === 'edit' && props.modelValue.id) {
    try {
      const variableData: CreateEnvironmentVariableData = {
        environment: props.modelValue.id,
        name: newVariable.value.name,
        value: newVariable.value.value,
        type: newVariable.value.type,
        description: newVariable.value.description,
        is_sensitive: newVariable.value.is_sensitive
      }

      console.log('准备调用 API 添加变量:', variableData)
      const response = await createEnvironmentVariable(variableData)
      if (response.data) {
        Message.success('添加变量成功')
        emit('update:modelValue', {
          ...props.modelValue,
          variables: [...props.modelValue.variables, response.data]
        })
        // 重置表单
        newVariable.value = {
          name: '',
          value: '',
          type: 'string',
          description: '',
          is_sensitive: false
        }
        // 触发提交事件，通知父组件刷新
        emit('submit')
      }
    } catch (error: any) {
      console.error('添加变量失败:', error)
      // 获取具体的错误信息
      let errorMessage = '添加变量失败'
      if (error.response?.data?.errors) {
        const errors = error.response.data.errors
        // 获取所有错误信息并合并
        const errorMessages = Object.values(errors).flat()
        if (errorMessages.length > 0) {
          errorMessage = errorMessages.join('; ')
        }
      }
      Message.error(errorMessage)
    }
  } else {
    console.log('在创建模式下添加变量到本地列表')
    // 在创建模式下，只添加到本地列表
    const tempVariable: EnvironmentVariable = {
      id: 0,
      ...newVariable.value
    } as EnvironmentVariable
    emit('update:modelValue', {
      ...props.modelValue,
      variables: [...props.modelValue.variables, tempVariable]
    })
    // 重置表单
    newVariable.value = {
      name: '',
      value: '',
      type: 'string',
      description: '',
      is_sensitive: false
    }
  }
}

const handleRemoveVariable = async (index: number) => {
  const variable = props.modelValue.variables[index]
  if (variable.id) {
    try {
      await deleteEnvironmentVariable(variable.id)
      Message.success('删除变量成功')
      const variables = [...props.modelValue.variables]
      variables.splice(index, 1)
      emit('update:modelValue', {
        ...props.modelValue,
        variables
      })
      // 触发提交事件，通知父组件刷新
      emit('submit')
    } catch (error) {
      console.error('删除变量失败:', error)
      Message.error('删除变量失败')
    }
  } else {
    // 如果是新添加的变量（还没有 id），直接从列表中移除
    const variables = [...props.modelValue.variables]
    variables.splice(index, 1)
    emit('update:modelValue', {
      ...props.modelValue,
      variables
    })
  }
}

const handleEditVariable = (index: number) => {
  editingVariableIndex.value = index
  const variable = props.modelValue.variables[index]
  editingVariable.value = { ...variable }
  editVariableVisible.value = true
}

const cancelEditVariable = () => {
  editVariableVisible.value = false
  editingVariableIndex.value = -1
  editingVariable.value = {
    id: 0,
    name: '',
    value: '',
    type: 'string',
    description: '',
    is_sensitive: false
  } as EnvironmentVariable
}

const confirmEditVariable = async () => {
  if (editingVariableIndex.value > -1) {
    if (!editingVariable.value.name || !editingVariable.value.value) {
      return
    }

    // 只在编辑模式下调用 API
    if (props.mode === 'edit' && editingVariable.value.id) {
      try {
        const variableData: CreateEnvironmentVariableData = {
          environment: props.modelValue.id || 0,
          name: editingVariable.value.name,
          value: editingVariable.value.value,
          type: editingVariable.value.type,
          description: editingVariable.value.description || '',
          is_sensitive: editingVariable.value.is_sensitive
        }

        const response = await updateEnvironmentVariable(editingVariable.value.id, variableData)

        if (response.data) {
          Message.success('更新变量成功')
          const variables = [...props.modelValue.variables]
          variables[editingVariableIndex.value] = response.data
          emit('update:modelValue', {
            ...props.modelValue,
            variables
          })
          // 触发提交事件，通知父组件刷新
          emit('submit')
          // 关闭编辑对话框
          editVariableVisible.value = false
          editingVariableIndex.value = -1
        }
      } catch (error: any) {
        console.error('更新变量失败:', error)
        // 获取具体的错误信息
        let errorMessage = '更新变量失败'
        if (error.response?.data?.errors) {
          const errors = error.response.data.errors
          // 获取所有错误信息并合并
          const errorMessages = Object.values(errors).flat()
          if (errorMessages.length > 0) {
            errorMessage = errorMessages.join('; ')
          }
        }
        Message.error(errorMessage)
        return
      }
    } else {
      // 在创建模式下，只更新本地列表
      const variables = [...props.modelValue.variables]
      variables[editingVariableIndex.value] = { ...editingVariable.value }
      emit('update:modelValue', {
        ...props.modelValue,
        variables
      })
    editVariableVisible.value = false
    editingVariableIndex.value = -1
    }
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
    emit('submit')
  } catch (error) {
    // 表单验证失败
  }
}
</script>

<template>
  <div class="env-form-panel h-full flex flex-col">
    <!-- 移除顶部按钮区域，直接从表单内容开始 -->
    <div class="form-scroll-area flex-1 overflow-y-auto px-8 py-6">
      <a-spin :loading="loading" dot>
        <a-form
          ref="formRef"
          :model="modelValue"
          :rules="rules"
          class="grid grid-cols-2 gap-6"
        >
          <!-- 左侧：基本信息卡片 -->
          <div class="space-y-6">
            <div class="form-section-card rounded-xl">
              <div class="form-section-header px-6 py-4 border-b">
                <div class="flex items-center gap-3">
                  <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500/20 to-indigo-500/10 flex items-center justify-center">
                    <icon-settings class="text-indigo-400" />
                  </div>
                  <span class="text-base font-medium form-section-title">基本信息</span>
                </div>
              </div>
              
              <div class="p-6 space-y-6">
                <!-- 环境名称 -->
                <a-form-item field="name" label="环境名称" validate-trigger="blur" class="!mb-0">
                  <a-input
                    v-model="modelValue.name"
                    placeholder="请输入环境名称，例如：开发环境、测试环境"
                    allow-clear
                    class="field-control"
                  >
                    <template #prefix>
                      <icon-storage class="text-indigo-400" />
                    </template>
                  </a-input>
                </a-form-item>

                <!-- 基础URL -->
                <a-form-item field="base_url" label="基础 URL" validate-trigger="blur" class="!mb-0">
                  <a-input
                    v-model="modelValue.base_url"
                    placeholder="请输入基础URL，例如：https://api.example.com"
                    allow-clear
                    class="field-control"
                  >
                    <template #prefix>
                      <icon-link class="text-indigo-400" />
                    </template>
                  </a-input>
                </a-form-item>

                <!-- 验证SSL选项 -->
                <a-form-item>
                  <div class="flex items-center gap-3">
                    <a-switch
                      v-model="props.modelValue.verify_ssl"
                      :default-checked="props.modelValue.verify_ssl === true"
                    />
                    <span class="form-text-muted">验证SSL证书</span>
                    <a-tooltip content="启用时会验证HTTPS请求的SSL证书，禁用可以跳过SSL验证（不安全但在开发环境可能需要）">
                      <icon-info-circle class="form-text-subtle" />
                    </a-tooltip>
                  </div>
                </a-form-item>

                <!-- 数据库配置选择器 - 新增 -->
                <a-form-item field="database_config" label="关联数据库" class="!mb-0">
                  <a-select
                    v-model="modelValue.database_config"
                    placeholder="请选择关联的数据库配置"
                    allow-clear
                    :loading="loadingDatabaseConfigs"
                    class="field-control"
                    @clear="handleClearDatabaseConfig"
                    :format-selected="formatDatabaseSelection"
                    @dropdown-visible-change="onDropdownVisibleChange"
                    allow-search
                    :key="forceRefresh"
                  >
                    <template #prefix>
                      <icon-storage class="text-indigo-400" />
                    </template>
                    <template #empty>
                      <div class="text-center p-2 form-text-subtle">
                        {{ loadingDatabaseConfigs ? formText.loadingDatabaseConfigs : formText.noDatabaseConfigs }}
                      </div>
                    </template>
                    <a-option value="null" :label="formText.noLinkedDatabase">{{ formText.noLinkedDatabase }}</a-option>
                    
                    <template v-if="databaseConfigs.length > 0">
                      <a-option
                        v-for="config in databaseConfigs"
                        :key="config.id"
                        :value="config.id"
                        :label="config.name"
                        :disabled="!config.is_active"
                      >
                        {{ config.name }} 
                        <span v-if="!config.is_active" class="text-xs text-red-400">(已禁用)</span>
                      </a-option>
                    </template>
                  </a-select>
                </a-form-item>

                <!-- 描述 -->
                <a-form-item field="description" label="描述" class="!mb-0">
                  <a-textarea
                    v-model="modelValue.description"
                    placeholder="请输入环境描述信息（选填）"
                    allow-clear
                    :auto-size="{ minRows: 3, maxRows: 5 }"
                    class="field-control"
                  />
                </a-form-item>

                <!-- 是否启用 -->
                <a-form-item field="is_active" class="!mb-0">
                  <div class="toggle-card flex items-center gap-3 p-3 rounded-lg">
                    <a-switch v-model="modelValue.is_active" class="!scale-110" />
                    <span class="form-text-muted">{{ modelValue.is_active ? formText.enableEnvironment : formText.disableEnvironment }}</span>
                  </div>
                </a-form-item>
              </div>
            </div>

            <!-- 帮助提示 -->
            <div class="help-card p-4 rounded-xl">
              <div class="flex items-center gap-2 mb-2">
                <icon-info-circle class="form-text-subtle" />
                <span class="text-sm font-medium form-text-muted">{{ formText.guide }}</span>
              </div>
              <ul class="text-xs form-text-subtle space-y-1.5">
                <li class="flex items-center gap-2">
                  <div class="helper-dot w-1 h-1 rounded-full"></div>
                  <span>{{ formText.guideLine1 }}</span>
                </li>
                <li class="flex items-center gap-2">
                  <div class="helper-dot w-1 h-1 rounded-full"></div>
                  <span>{{ formText.guideLine2 }}</span>
                </li>
                <li class="flex items-center gap-2">
                  <div class="helper-dot w-1 h-1 rounded-full"></div>
                  <span>{{ formText.guideLine3 }}</span>
                </li>
              </ul>
            </div>
          </div>

          <!-- 右侧：环境变量卡片 -->
          <div class="form-section-card rounded-xl">
            <div class="form-section-header px-6 py-4 border-b">
              <div class="flex items-center gap-3">
                <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500/20 to-purple-500/10 flex items-center justify-center">
                  <icon-apps class="text-purple-400" />
                </div>
                <span class="text-base font-medium form-section-title">环境变量</span>
              </div>
            </div>
            
            <div class="p-6 space-y-4">
              <!-- 添加变量表单 -->
              <environment-variable-form
                v-model="newVariable"
                @submit="handleAddVariable"
              />

              <!-- 变量列表 -->
              <environment-variable-list
                :variables="modelValue.variables"
                @edit="handleEditVariable"
                @delete="handleRemoveVariable"
              />

              <!-- 编辑变量弹窗 -->
              <a-modal
                v-model:visible="editVariableVisible"
                :title="'编辑变量 #' + (editingVariableIndex + 1)"
                @cancel="cancelEditVariable"
                @ok="confirmEditVariable"
                :ok-text="'保存'"
                :cancel-text="'取消'"
              >
                <div class="space-y-4">
                  <a-input
                    v-model="editingVariable.name"
                    placeholder="变量名"
                    allow-clear
                    class="field-control"
                  >
                    <template #prefix>
                      <icon-code class="text-purple-400" />
                    </template>
                  </a-input>
                  <a-input
                    v-model="editingVariable.value"
                    placeholder="变量值"
                    allow-clear
                    class="field-control"
                  >
                    <template #prefix>
                      <icon-edit class="text-purple-400" />
                    </template>
                  </a-input>
                  <!-- 变量类型选择 -->
                  <a-select
                    v-model="editingVariable.type"
                    placeholder="选择变量类型"
                    class="field-control"
                  >
                    <a-option
                      v-for="item in VARIABLE_TYPES"
                      :key="item.value"
                      :value="item.value"
                    >
                      {{ item.label }}
                    </a-option>
                  </a-select>
                  <a-input
                    v-model="editingVariable.description"
                    placeholder="变量描述（选填）"
                    allow-clear
                    class="field-control"
                  >
                    <template #prefix>
                      <icon-info-circle class="text-purple-400" />
                    </template>
                  </a-input>
                  <!-- 敏感变量开关 -->
                  <div class="toggle-card flex items-center gap-3 p-3 rounded-lg">
                    <a-switch
                      v-model="editingVariable.is_sensitive"
                      class="!scale-110"
                    />
                    <div class="flex items-center gap-2">
                      <icon-lock class="text-purple-400" />
                      <span class="form-text-muted">敏感变量</span>
                    </div>
                  </div>
                </div>
              </a-modal>
            </div>
          </div>
        </a-form>
      </a-spin>
    </div>
  </div>
</template> 

<style lang="postcss" scoped>
.env-form-panel {
  background: transparent;
}

.form-scroll-area {
  scrollbar-width: none;
  -ms-overflow-style: none;

  &::-webkit-scrollbar {
    display: none;
  }
}

.form-section-card,
.help-card {
  background: var(--env-shell-bg);
  border: 1px solid var(--env-shell-border);
  box-shadow: var(--env-shell-shadow);
}

.form-section-header {
  border-bottom-color: var(--env-header-border);
}

.form-section-title,
.form-text-muted {
  color: var(--env-text);
}

.form-text-subtle {
  color: var(--env-text-subtle);
}

.toggle-card {
  background: color-mix(in srgb, var(--env-block-bg) 86%, var(--theme-page-bg) 14%);
  border: 1px solid var(--env-block-border);
}

.helper-dot {
  background: var(--env-text-subtle);
}

:deep(.arco-form-item-label-col > label),
:deep(.arco-form-item-label) {
  color: var(--env-text) !important;
}

:deep(.field-control .arco-input-wrapper),
:deep(.field-control .arco-textarea-wrapper),
:deep(.field-control .arco-select-view) {
  background: var(--env-input-bg) !important;
  border-color: var(--env-input-border) !important;

  &:hover,
  &:focus-within {
    border-color: rgba(var(--theme-accent-rgb), 0.42) !important;
    background: var(--env-input-hover-bg) !important;
  }
}

:deep(.field-control .arco-input),
:deep(.field-control .arco-textarea),
:deep(.field-control .arco-select-view-value) {
  color: var(--env-text) !important;
}

:deep(.field-control .arco-input::placeholder),
:deep(.field-control .arco-textarea::placeholder),
:deep(.field-control .arco-select-view-placeholder),
:deep(.field-control .arco-input-prefix),
:deep(.field-control .arco-input-suffix),
:deep(.field-control .arco-select-view-suffix) {
  color: var(--env-text-subtle) !important;
}
</style>
