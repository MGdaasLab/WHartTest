<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { IconSend, IconSave, IconQuestionCircle } from '@arco-design/web-vue/es/icon'
import { Message } from '@arco-design/web-vue'
import { useEnvironmentStore } from '../../stores/environmentStore'
import type { ApiInterface } from '../../types/interface'
import type { ApiModule } from '../../types/module'

interface Props {
  modules?: ApiModule[]
  modelValue: {
    method: string
    url: string
    name: string
    module: number | string | null
    interface?: ApiInterface | null
  }
  savingLoading?: boolean
  sendingLoading?: boolean
  showSaveStep?: boolean
  saveStepRequiresModule?: boolean
  saveStepLabel?: string
  saveInterfaceLabel?: string
  sendTooltip?: string
}

const props = withDefaults(defineProps<Props>(), {
  modules: () => [],
  savingLoading: false,
  sendingLoading: false,
  showSaveStep: true,
  saveStepRequiresModule: true,
  saveStepLabel: '更新步骤',
  saveInterfaceLabel: '同步接口',
  sendTooltip: '运行前自动保存当前配置'
})

const emit = defineEmits([
  'update:modelValue',
  'send',
  'save',
  'save-step'
])

const environmentStore = useEnvironmentStore()

const currentEnvironmentBaseUrl = computed(() => {
  const currentEnv = (environmentStore as any).environments?.find(
    (env: any) => env.id === Number(environmentStore.currentEnvironmentId)
  )
  return currentEnv?.base_url || ''
})

const processModules = (modules: ApiModule[], level = 0): (ApiModule & { level: number })[] => {
  return modules.reduce((acc: (ApiModule & { level: number })[], mod) => {
    acc.push({ ...mod, level })
    if (mod.children?.length) {
      acc.push(...processModules(mod.children, level + 1))
    }
    return acc
  }, [])
}

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

const apiName = ref('')
const selectedModule = ref<number>()
const requestUrl = ref('')

const selectedMethod = ref('GET')

watch(
  () => props.modelValue,
  (newValue) => {
    if (apiName.value !== (newValue.name || '')) {
      apiName.value = newValue.name || ''
    }
    if (requestUrl.value !== (newValue.url || '')) {
      requestUrl.value = newValue.url || ''
    }
    if (selectedMethod.value !== (newValue.method || 'GET')) {
      selectedMethod.value = newValue.method || 'GET'
    }
  },
  { immediate: true, deep: true }
)

watch(
  () => props.modelValue.module,
  (newModule, oldModule) => {
    selectedModule.value = normalizeModuleValue(newModule)
  },
  { immediate: true }
)

watch(apiName, (newValue) => {
  if (newValue === (props.modelValue.name || '')) {
    return
  }

  emit('update:modelValue', {
    ...props.modelValue,
    name: newValue
  })
})

watch(requestUrl, (newValue) => {
  if (newValue === (props.modelValue.url || '')) {
    return
  }

  emit('update:modelValue', {
    ...props.modelValue,
    url: newValue
  })
})

watch(selectedModule, (newValue, oldValue) => {
  const normalizedValue = normalizeModuleValue(newValue) || null
  const currentModule = normalizeModuleValue(props.modelValue.module) || null
  if (normalizedValue === currentModule) {
    return
  }
  emit('update:modelValue', {
    ...props.modelValue,
    module: normalizedValue
  })
})

watch(selectedMethod, (newMethod) => {
  if (newMethod !== props.modelValue.method) {
    emit('update:modelValue', {
      ...props.modelValue,
      method: newMethod
    })
  }
})

const httpMethods = [
  { label: 'GET', value: 'GET', color: 'method-get' },
  { label: 'POST', value: 'POST', color: 'method-post' },
  { label: 'PUT', value: 'PUT', color: 'method-put' },
  { label: 'DELETE', value: 'DELETE', color: 'method-delete' },
  { label: 'PATCH', value: 'PATCH', color: 'method-patch' }
]

const popupVisible = ref(false)

const handleSend = () => {
  if (!requestUrl.value) {
    Message.warning('请输入请求路径')
    return
  }
  emit('send', {
    method: selectedMethod.value,
    url: requestUrl.value,
    name: apiName.value,
    module: selectedModule.value
  })
}

const handleSave = () => {
  if (!selectedModule.value) {
    Message.warning('请选择模块')
    return
  }
  if (!apiName.value) {
    Message.warning('请输入步骤名称')
    return
  }
  if (!requestUrl.value) {
    Message.warning('请输入请求路径')
    return
  }
  emit('save', {
    method: selectedMethod.value,
    url: requestUrl.value,
    name: apiName.value,
    module: selectedModule.value
  })
}

const handleSaveStep = () => {
  if (props.saveStepRequiresModule && !selectedModule.value) {
    Message.warning('请选择模块')
    return
  }
  if (!apiName.value) {
    Message.warning('请输入步骤名称')
    return
  }
  if (!requestUrl.value) {
    Message.warning('请输入请求路径')
    return
  }

  emit('save-step', {
    method: selectedMethod.value,
    url: requestUrl.value,
    name: apiName.value,
    module: selectedModule.value
  })
}

const selectMethod = (method: string) => {
  selectedMethod.value = method
  popupVisible.value = false
}

const getCurrentMethodColor = () => {
  return httpMethods.find(m => m.value === selectedMethod.value)?.color || 'method-default'
}
</script>

<template>
  <div class="testcase-request-header p-4 border-b">
    <div class="flex gap-2 mb-3">
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

      <a-input
        v-model="requestUrl"
        placeholder="请输入请求路径"
        size="large"
        allow-clear
        class="menu-item rounded-lg flex-1"
      >
        <template #prefix v-if="currentEnvironmentBaseUrl">
          <span class="base-url-text">{{ currentEnvironmentBaseUrl }}</span>
        </template>
      </a-input>

      <a-button-group>
        <a-button
          type="outline"
          size="large"
          :loading="props.sendingLoading"
          @click="handleSend"
          status="success"
          class="btn-debug"
        >
          <template #icon><icon-send /></template>
          运行调试
          <a-tooltip :content="props.sendTooltip">
            <icon-question-circle class="ml-1 text-xs opacity-70" />
          </a-tooltip>
        </a-button>
        <a-button
          v-if="props.showSaveStep"
          type="outline"
          size="large"
          :loading="props.savingLoading"
          @click="handleSaveStep"
          status="success"
        >
          <template #icon><icon-save /></template>
          {{ props.saveStepLabel }}
        </a-button>
        <a-button
          type="outline"
          size="large"
          :loading="props.savingLoading"
          @click="handleSave"
        >
          <template #icon><icon-save /></template>
          {{ props.saveInterfaceLabel }}
        </a-button>
      </a-button-group>
    </div>

    <div class="flex gap-2">
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

      <a-input
        v-model="apiName"
        placeholder="请输入步骤名称"
        size="large"
        allow-clear
        :style="{ width: '80%' }"
        class="rounded-lg"
      />
    </div>
  </div>
</template>

<style lang="postcss" scoped>
@reference "tailwindcss";
.testcase-request-header {
  border-color: var(--tcf-panel-border) !important;
}

/* 输入框menu-item样式 */
.menu-item {
  box-shadow: inset 0 1px 0 0 rgba(148, 163, 184, 0.2) !important;
  background-color: var(--tcf-control-bg) !important;
  border: 1px solid var(--tcf-control-border) !important;
}

/* 请求方法按钮样式 */
.method-button {
  @apply flex items-center justify-center rounded text-white font-medium text-sm cursor-pointer;
  width: 82px;
  height: 32px;
  font-size: 13px;
  letter-spacing: 0.5px;
  transition: all 0.2s ease-in-out;
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
  @apply flex flex-col items-center;
  min-width: 82px;
}

.method-dropdown .method-button {
  height: 28px;
  padding: 0;
  width: 65px !important;
  margin: 2px 1px 2px 0 !important;
}

/* 输入框样式 */
:deep(.arco-input-wrapper) {
  background: var(--tcf-control-bg) !important;
  border-color: var(--tcf-control-border) !important;

  input {
    color: var(--tcf-text) !important;
    &::placeholder {
      color: var(--tcf-text-subtle) !important;
    }
  }
}

:deep(.arco-input-prefix) {
  margin-right: 4px;
  padding-right: 8px;
  border-right: 1px solid var(--tcf-control-border);
}

/* 按钮样式 */
:deep(.arco-btn-outline) {
  border-color: var(--tcf-control-border) !important;
  color: var(--tcf-text-muted) !important;

  &:hover {
    border-color: rgba(59, 130, 246, 0.4) !important;
    color: rgb(59, 130, 246) !important;
  }
}

/* 运行调试按钮样式 */
:deep(.btn-debug) {
  @apply text-[#10B981] border-[#10B981]/30;
  background-color: rgba(16, 185, 129, 0.05) !important;

  &:hover {
    @apply text-[#10B981] border-[#10B981]/50;
    background-color: rgba(16, 185, 129, 0.1) !important;
  }
}

/* 下拉菜单样式 */
:global(.arco-dropdown),
:global(.arco-dropdown-list),
:global(.arco-dropdown-list-wrapper) {
  background: #ffffff !important;
  border-radius: 12px !important;
  border: 1px solid rgba(148, 163, 184, 0.16) !important;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.12) !important;
}

:global(body.api-testing-theme .arco-dropdown),
:global(body.api-testing-theme .arco-dropdown-list),
:global(body.api-testing-theme .arco-dropdown-list-wrapper) {
  background: rgb(31, 41, 55) !important;
  border-color: rgba(75, 85, 99, 0.4) !important;
}

/* 模块选择下拉框样式 */
:deep(.arco-select) {
  background: var(--tcf-control-bg) !important;

  .arco-select-view {
    box-shadow: inset 0 1px 0 0 rgba(148, 163, 184, 0.2) !important;
    background-color: var(--tcf-control-bg) !important;
    border: 1px solid var(--tcf-control-border) !important;
    @apply rounded-lg;

    &:hover {
      border-color: rgba(59, 130, 246, 0.28) !important;
      background: var(--tcf-control-hover) !important;
    }
  }

  .arco-select-view-value {
    color: var(--tcf-text) !important;
  }

  input {
    color: var(--tcf-text) !important;
    background: transparent !important;
    &::placeholder {
      color: var(--tcf-text-subtle) !important;
    }
  }
}

:global(.arco-select-dropdown) {
  background: #ffffff !important;
  border: 1px solid rgba(148, 163, 184, 0.16) !important;
  border-radius: 12px !important;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.12) !important;
  padding: 4px !important;
  margin: 4px 0 !important;
}

:global(body.api-testing-theme .arco-select-dropdown) {
  background: rgb(31, 41, 55) !important;
  border-color: rgba(75, 85, 99, 0.4) !important;
}

:global(.arco-select-dropdown .arco-select-option) {
  color: #334155 !important;
  border-radius: 8px !important;
  padding: 0.25rem 0.5rem !important;
  margin: 0.25rem 0 !important;

  &:hover {
    background: #f8fafc !important;
  }

  &.arco-select-option-active,
  &.arco-select-option-selected {
    background: rgba(59, 130, 246, 0.12) !important;
    color: #2563eb !important;
  }
}

:global(body.api-testing-theme .arco-select-dropdown .arco-select-option) {
  color: rgb(203, 213, 225) !important;

  &:hover {
    background: rgba(51, 65, 85, 0.9) !important;
  }
}

/* 模块树形结构样式 */
:global(.arco-select-dropdown .arco-select-option) {
  padding: 0 !important;
  background: transparent !important;
  margin: 2px 0 !important;
  border-radius: 4px !important;

  &:hover {
    background: rgba(59, 130, 246, 0.1) !important;
  }

  &.arco-select-option-active,
  &.arco-select-option-selected {
    background: rgba(59, 130, 246, 0.14) !important;
  }
}

:global(.arco-select-dropdown .arco-select-option .arco-btn) {
  background: transparent !important;
  border: none !important;

  &:hover {
    background: transparent !important;
  }

  .arco-icon {
    color: #6b7785 !important;

    &:hover {
      color: #86909c !important;
    }
  }
}

.base-url-text {
  color: var(--tcf-text-subtle) !important;
}

.module-select-shell {
  border: 1px solid var(--tcf-control-border);
  background: var(--tcf-control-bg);
}
</style>
