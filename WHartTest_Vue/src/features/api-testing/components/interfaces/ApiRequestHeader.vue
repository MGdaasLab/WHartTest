<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { IconSend, IconSave, IconBug } from '@arco-design/web-vue/es/icon'
import { useEnvironmentStore } from '../../stores/environmentStore'
import type { ApiInterface } from '../../services/interfaceService'
import { quickDebugInterface, type QuickDebugInterfaceRequest } from '../../services/interfaceService'
import { useProjectStore } from '@/store/projectStore'
import { Message } from '@arco-design/web-vue'

// 扩展 ApiInterface 类型
interface ExtendedApiInterface extends ApiInterface {
  module_info?: ApiModule
}

interface Props {
  modules?: ApiModule[]
  interface?: ApiInterface
  selectedModule?: ApiModule
  savingLoading?: boolean
  sendingLoading?: boolean
  quickDebugLoading?: boolean
}

// 获取环境store
const environmentStore = useEnvironmentStore()

// 获取当前项目的store
const projectStore = useProjectStore()
const currentProjectId = computed(() => {
  if (projectStore.currentProject) {
    return projectStore.currentProject.id
  }
  return undefined
})

// 获取当前环境的base_url
const currentEnvironmentBaseUrl = computed(() => {
  const currentEnv = environmentStore.environments.find(
    env => env.id === Number(environmentStore.currentEnvironmentId)
  )
  return currentEnv?.base_url || ''
})

// 处理模块数据，添加level属性
const processModules = (modules: ApiModule[], level = 0): (ApiModule & { level: number })[] => {
  return modules.reduce((acc: (ApiModule & { level: number })[], module) => {
    acc.push({ ...module, level })
    if (module.children?.length) {
      acc.push(...processModules(module.children, level + 1))
    }
    return acc
  }, [])
}

interface ApiModule {
  id: number
  name: string
  project: number
  parent: number | null
  description: string | null
  create_time?: string
  update_time?: string
  children?: ApiModule[]
}

const props = withDefaults(defineProps<Props>(), {
  modules: () => [],
  interface: undefined,
  selectedModule: undefined,
  savingLoading: false,
  sendingLoading: false,
  quickDebugLoading: false
})

// 处理后的模块列表
const processedModules = computed(() => {
  return processModules(props.modules)
})

const normalizeModuleValue = (moduleValue: unknown) => {
  if (typeof moduleValue === 'object' && moduleValue !== null && 'value' in moduleValue) {
    return normalizeModuleValue((moduleValue as { value?: unknown }).value)
  }

  if (typeof moduleValue === 'boolean') {
    return undefined
  }

  if (moduleValue === null || moduleValue === undefined || moduleValue === '') {
    return undefined
  }

  const normalizedId = Number(moduleValue)
  return Number.isFinite(normalizedId) && normalizedId > 0 ? normalizedId : undefined
}

// 接口名称
const apiName = ref('')
// 选择的模块
const selectedModule = ref<number>()
const lastDefaultModuleId = ref<number>()
// 请求URL
const requestUrl = ref('')
// 当前选中的请求方法
const selectedMethod = ref('GET')

// 请求方法选项
const httpMethods = [
  { label: 'GET', value: 'GET', color: 'method-get' },
  { label: 'POST', value: 'POST', color: 'method-post' },
  { label: 'PUT', value: 'PUT', color: 'method-put' },
  { label: 'DELETE', value: 'DELETE', color: 'method-delete' },
  { label: 'PATCH', value: 'PATCH', color: 'method-patch' }
]

// 下拉框显示状态
const popupVisible = ref(false)

const emit = defineEmits(['send', 'save'])

// 发送请求
const handleSend = () => {
  console.log('发送请求，接口ID:', props.interface?.id)
  emit('send', {
    method: selectedMethod.value,
    url: requestUrl.value,
    id: props.interface?.id
  })
}

// 保存用例
const handleSave = () => {
  const normalizedModuleId = normalizeModuleValue(selectedModule.value)
  emit('save', {
    name: apiName.value,
    method: selectedMethod.value,
    url: requestUrl.value,
    module: normalizedModuleId,
    id: props.interface?.id
  })
}

// 选择请求方法
const selectMethod = (method: string) => {
  selectedMethod.value = method
  popupVisible.value = false
}

// 获取当前方法的颜色
const getCurrentMethodColor = () => {
  return httpMethods.find(m => m.value === selectedMethod.value)?.color || 'method-default'
}

const applyDefaultModule = (moduleId?: number) => {
  selectedModule.value = moduleId
  lastDefaultModuleId.value = moduleId
}

// 监听接口数据变化
watch(() => props.interface, (newInterface) => {
  if (newInterface) {
    // 更新表单数据
    apiName.value = newInterface.name || ''
    selectedMethod.value = newInterface.method || 'GET'
    requestUrl.value = newInterface.url || ''
    selectedModule.value = normalizeModuleValue(newInterface.module)
    lastDefaultModuleId.value = undefined
  } else {
    // 清空表单数据
    apiName.value = ''
    selectedMethod.value = 'GET'
    requestUrl.value = ''
    applyDefaultModule(normalizeModuleValue(props.selectedModule?.id))
  }
}, { immediate: true, deep: true })

watch(() => props.selectedModule?.id, (newModuleId, oldModuleId) => {
  if (props.interface) {
    return
  }

  const normalizedCurrent = normalizeModuleValue(selectedModule.value)
  const normalizedPreviousDefault = normalizeModuleValue(oldModuleId)
  const normalizedNextDefault = normalizeModuleValue(newModuleId)

  if (
    normalizedCurrent === undefined ||
    normalizedCurrent === lastDefaultModuleId.value ||
    normalizedCurrent === normalizedPreviousDefault
  ) {
    applyDefaultModule(normalizedNextDefault)
  }
})

const handleQuickDebug = async () => {
  if (!requestUrl.value) {
    Message.warning('请输入接口地址')
    return
  }

  if (!currentProjectId.value) {
    Message.warning('请先选择项目')
    return
  }

  // 准备请求数据
  const request: QuickDebugInterfaceRequest = {
    project_id: currentProjectId.value,
    method: selectedMethod.value,
    url: requestUrl.value,
    environment_id: environmentStore.currentEnvironmentId ? Number(environmentStore.currentEnvironmentId) : undefined,
    headers: {},
    params: {},
    body: null
  }

  // 通知父组件获取其他配置数据并发送请求
  emit('send', {
    method: selectedMethod.value,
    url: requestUrl.value,
    quickDebug: true,
    quickDebugRequest: request
  })
}
</script>

<template>
  <div class="api-request-header p-4 border-b">
    <!-- URL输入区域 -->
    <div class="flex gap-2 mb-3">
      <!-- 请求方法选择 -->
      <a-dropdown
        trigger="click"
        position="bl"
        v-model:popup-visible="popupVisible"
      >
        <div :class="['method-button', getCurrentMethodColor()]">
          {{ selectedMethod }}
        </div>
        <template #content>
          <div class="method-dropdown">
            <div
              v-for="method in httpMethods"
              :key="method.value"
              :class="['method-button', method.color]"
              @click="selectMethod(method.value)"
            >
              {{ method.value }}
            </div>
          </div>
        </template>
      </a-dropdown>

      <!-- URL输入框 -->
      <a-input
        v-model="requestUrl"
        placeholder="请输入请求路径"
        size="large"
        allow-clear
        class="menu-item request-url-input rounded-lg"
      >
        <template #prefix v-if="currentEnvironmentBaseUrl">
          <span class="request-base-url">{{ currentEnvironmentBaseUrl }}</span>
        </template>
      </a-input>

      <!-- 操作按钮 -->
      <div class="flex items-center gap-2">
        <a-tooltip content="无需保存接口即可直接测试">
          <a-button
            type="primary"
            status="success"
            size="large"
            :loading="props.quickDebugLoading"
            @click="handleQuickDebug"
            class="w-10"
          >
            <template #icon><icon-bug /></template>
          </a-button>
        </a-tooltip>
        
        <a-button-group>
          <a-button
            type="primary"
            size="large"
            :loading="props.sendingLoading"
            @click="handleSend"
          >
            <template #icon><icon-send /></template>
            调试
          </a-button>
          <a-button
            type="outline"
            size="large"
            :loading="props.savingLoading"
            @click="handleSave"
          >
            <template #icon><icon-save /></template>
            保存
          </a-button>
        </a-button-group>
      </div>
    </div>

    <!-- 接口信息区域 -->
    <div class="flex gap-2">
      <!-- 模块选择 -->
      <div class="module-select-shell rounded-lg" style="width: 20%">
        <a-select
          v-model="selectedModule"
          placeholder="请选择模块"
          size="large"
          allow-clear
          :style="{ width: '100%' }"
        >
          <a-option
            v-for="module in processedModules"
            :key="module.id"
            :value="module.id"
            :label="module.name"
          >
            <div class="flex items-center gap-2" :style="{ paddingLeft: `${module.level * 16}px` }">
              <span class="w-4"></span>
              {{ module.name }}
            </div>
          </a-option>
        </a-select>
      </div>

      <!-- 接口名称输入框 -->
      <a-input
        v-model="apiName"
        placeholder="请输入接口名称"
        size="large"
        allow-clear
        :style="{ width: '80%' }"
        class="menu-item api-name-input rounded-lg"
      />
    </div>
  </div>
</template>

<style scoped>
.api-request-header {
  border-color: rgba(148, 163, 184, 0.16);
}

.request-base-url {
  color: var(--color-text-3);
}

.module-select-shell {
  border: 1px solid rgba(148, 163, 184, 0.18);
}

:global(body.api-testing-theme) .api-request-header {
  border-color: rgb(55, 65, 81);
}

:global(body.api-testing-theme) .request-base-url {
  color: rgb(107, 114, 128);
}

:global(body.api-testing-theme) .module-select-shell {
  border-color: rgb(75, 85, 99);
}

/* 输入框menu-item样式 */
a-input.menu-item {
  box-shadow: inset 0 1px 0 0 rgba(148, 163, 184, 0.12) !important;
  background-color: rgba(255, 255, 255, 0.96) !important;
  border: 1px solid rgba(148, 163, 184, 0.22) !important;
}

:global(body.api-testing-theme) a-input.menu-item {
  box-shadow: inset 0 1px 0 0 rgba(148, 163, 184, 0.2) !important;
  background-color: rgba(17, 24, 39, 0.8) !important;
  border: 1px solid rgba(75, 85, 99, 0.4) !important;
}

/* 请求方法按钮样式 */
.method-button {
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.25rem;
  color: #fff;
  font-weight: 500;
  cursor: pointer;
  width: 108px;
  height: 32px;
  font-size: 13px;
  letter-spacing: 0.5px;
  transition: all 0.2s ease-in-out;
  flex-shrink: 0;
}

/* 请求方法颜色 */
.method-get { background-color: rgba(59, 130, 246, 0.8); }
.method-post { background-color: rgba(34, 197, 94, 0.8); }
.method-put { background-color: rgba(249, 115, 22, 0.8); }
.method-delete { background-color: rgba(239, 68, 68, 0.8); }
.method-patch { background-color: rgba(239, 68, 68, 0.8); }
.method-default { background-color: rgba(75, 85, 99, 1); }

.method-button:hover {
  transform: translateY(-1px);
  opacity: 1;
}

.method-dropdown {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  width: 100%;
}

.method-dropdown .method-button {
  height: 28px;
  padding: 0;
  width: unset !important;
  margin: 2px 4px !important;
  border-radius: 4px;
  text-align: center;
}

/* 输入框样式 */
:deep(.arco-input-wrapper) {
  background-color: rgba(255, 255, 255, 0.96);
  border-color: rgba(148, 163, 184, 0.22);
}

:deep(.arco-input-wrapper input) {
  color: var(--color-text-1);
}

:deep(.arco-input-wrapper input::placeholder) {
  color: var(--color-text-3);
}

:global(body.api-testing-theme) .api-request-header :deep(.arco-input-wrapper) {
  background-color: rgb(17 24 39 / 0.6);
  border-color: rgb(55 65 81);
}

:global(body.api-testing-theme) .api-request-header :deep(.arco-input-wrapper input) {
  color: rgb(229 231 235);
}

:global(body.api-testing-theme) .api-request-header :deep(.arco-input-wrapper input::placeholder) {
  color: rgb(107 114 128);
}

/* 按钮样式 */
:deep(.arco-btn-outline) {
  border-color: rgba(148, 163, 184, 0.28);
  color: var(--color-text-2);
}

:deep(.arco-btn-outline:hover) {
  border-color: rgb(59 130 246);
  color: rgb(59 130 246);
}

:global(body.api-testing-theme) .api-request-header :deep(.arco-btn-outline) {
  border-color: rgb(75 85 99);
  color: rgb(209 213 219);
}

/* 下拉菜单样式 */
:global(body.api-testing-theme .arco-dropdown) {
  width: 108px !important;
  box-sizing: border-box !important;
  padding: 4px 0 !important;
}

:global(body.api-testing-theme .arco-dropdown .arco-dropdown-list.arco-dropdown-list) {
  background-color: rgb(31 41 55);
  border-radius: 0;
  padding: 0 !important;
  box-shadow: none !important;
  border: none !important;
}

/* 模块选择下拉框样式 */
:deep(.arco-select-view) {
  box-shadow: inset 0 1px 0 0 rgba(148, 163, 184, 0.12) !important;
  background-color: rgba(255, 255, 255, 0.96) !important;
  border: 1px solid rgba(148, 163, 184, 0.22) !important;
  border-radius: 0.5rem;
}

:deep(.arco-select-view:hover) {
  background-color: rgba(255, 255, 255, 0.98) !important;
  border-color: rgba(59, 130, 246, 0.36) !important;
}

:deep(.arco-select-view-value) {
  color: var(--color-text-1);
}

:deep(.arco-select-view-value::placeholder) {
  color: var(--color-text-3);
}

:global(body.api-testing-theme) .api-request-header :deep(.arco-select-view) {
  box-shadow: inset 0 1px 0 0 rgba(148, 163, 184, 0.2) !important;
  background-color: rgba(17, 24, 39, 0.8) !important;
  border: 1px solid rgba(75, 85, 99, 0.4) !important;
}

:global(body.api-testing-theme) .api-request-header :deep(.arco-select-view:hover) {
  background-color: rgba(17, 24, 39, 0.8) !important;
  border-color: rgba(75, 85, 99, 0.6) !important;
}

:global(body.api-testing-theme) .api-request-header :deep(.arco-select-view-value) {
  color: rgb(229 231 235);
}

:global(body.api-testing-theme) .api-request-header :deep(.arco-select-view-value::placeholder) {
  color: rgb(107 114 128);
}

:global(body.api-testing-theme .arco-select-dropdown) {
  background-color: rgb(31 41 55) !important;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1) !important;
  border: none !important;
  padding: 4px !important;
  margin: 4px 0 !important;
}

:global(body.api-testing-theme .arco-select-dropdown .arco-select-option) {
  padding: 0 !important;
  background: rgb(70 84 102 / 0.4) !important;
  margin: 2px 0 !important;
  border-radius: 4px !important;
}

:global(body.api-testing-theme .arco-select-dropdown .arco-select-option:hover) {
  background: rgb(47 66 114 / 0.4) !important;
}

:global(body.api-testing-theme .arco-select-dropdown .arco-select-option-active),
:global(body.api-testing-theme .arco-select-dropdown .arco-select-option-selected) {
  background: rgb(47 66 114 / 0.4) !important;
}

:global(body.api-testing-theme .arco-select-dropdown .arco-select-option .arco-btn) {
  background-color: transparent !important;
  border: none !important;
}

:global(body.api-testing-theme .arco-select-dropdown .arco-select-option .arco-btn:hover) {
  background-color: transparent !important;
}

:global(body.api-testing-theme .arco-select-dropdown .arco-select-option .arco-btn .arco-icon) {
  color: #6b7785 !important;
}

:global(body.api-testing-theme .arco-select-dropdown .arco-select-option .arco-btn:hover .arco-icon) {
  color: #86909c !important;
}
</style>
