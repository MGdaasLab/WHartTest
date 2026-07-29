<script setup lang="ts">
import { ref, computed } from 'vue'
import { IconSettings, IconInfoCircle } from '@arco-design/web-vue/es/icon'

interface TestCaseConfigData {
  export?: string[]
  verify?: boolean | null
  base_url?: string
  variables?: string
  parameters?: string
  [key: string]: any
}

interface Props {
  modelValue: TestCaseConfigData
  readonly?: boolean
  steps?: {
    id: number
    name: string
    interface_data: {
      extract?: Record<string, string>
    }
  }[]
}

const props = defineProps<Props>()
const emit = defineEmits(['update:modelValue'])

const visible = ref(false)
const activeTab = ref('basic')

const config = ref<TestCaseConfigData>({
  export: [],
  base_url: '',
  variables: '{}',
  parameters: '{}'
})

const sslVerifyMode = computed(() => {
  if (config.value.verify === true) return 'on'
  if (config.value.verify === false) return 'off'
  return 'inherit'
})

const handleSslVerifyModeChange = (value: string | number | boolean) => {
  if (value === 'on') {
    config.value.verify = true
    return
  }
  if (value === 'off') {
    config.value.verify = false
    return
  }
  delete config.value.verify
}

const extractVariables = computed(() => {
  const variables: Array<{
    stepId: number
    stepName: string
    key: string
    extract: string
  }> = []

  props.steps?.forEach(step => {
    if (step.interface_data.extract) {
      Object.entries(step.interface_data.extract).forEach(([key, extract]) => {
        variables.push({
          stepId: step.id,
          stepName: step.name,
          key,
          extract
        })
      })
    }
  })

  return variables
})

const handleOpen = () => {
  visible.value = true
  config.value = {
    export: [],
    base_url: '',
    variables: '{}',
    parameters: '{}',
    ...props.modelValue
  }
  if (typeof config.value.verify !== 'boolean') {
    delete config.value.verify
  }
}

const handleSubmit = () => {
  const nextConfig = { ...config.value }
  if (typeof nextConfig.verify !== 'boolean') {
    delete nextConfig.verify
  }
  emit('update:modelValue', nextConfig)
  visible.value = false
}
</script>

<template>
  <div class="testcase-config-dialog">
    <a-button
      class="!flex !items-center !gap-1"
      type="outline"
      size="small"
      status="normal"
      @click="handleOpen"
      :disabled="readonly"
    >
      <template #icon>
        <icon-settings class="!text-[#165DFF]" />
      </template>
      <span class="!text-[#165DFF]">用例配置</span>
    </a-button>

    <a-modal
      v-model:visible="visible"
      :width="800"
      title="用例配置"
      @ok="handleSubmit"
    >
      <a-tabs v-model:active-key="activeTab">
        <a-tab-pane key="basic" title="基础配置">
          <div class="space-y-4">
            <div class="flex items-center gap-4">
              <span class="config-label w-24">Base URL</span>
              <a-input
                v-model="config.base_url"
                placeholder="请输入基础URL"
                class="flex-1"
                allow-clear
              />
            </div>

            <div class="flex items-center gap-4">
              <span class="config-label w-24">SSL验证</span>
              <a-radio-group
                type="button"
                :model-value="sslVerifyMode"
                @update:model-value="handleSslVerifyModeChange"
              >
                <a-radio value="inherit">继承环境</a-radio>
                <a-radio value="on">开启</a-radio>
                <a-radio value="off">关闭</a-radio>
              </a-radio-group>
            </div>

            <div class="flex items-start gap-4">
              <span class="config-label w-24 mt-2">变量定义</span>
              <a-textarea
                v-model="config.variables"
                placeholder="请输入JSON格式的变量定义"
                :auto-size="{ minRows: 3, maxRows: 8 }"
                class="flex-1 font-mono"
                allow-clear
              />
            </div>

            <div class="flex items-start gap-4">
              <span class="config-label w-24 mt-2">参数定义</span>
              <a-textarea
                v-model="config.parameters"
                placeholder="请输入JSON格式的参数定义"
                :auto-size="{ minRows: 3, maxRows: 8 }"
                class="flex-1 font-mono"
                allow-clear
              />
            </div>
          </div>
        </a-tab-pane>

        <a-tab-pane key="dependencies" title="步骤依赖">
          <div class="space-y-4">
            <div class="flex items-center gap-2 mb-4">
              <icon-info-circle class="config-tip-icon" />
              <span class="config-tip-text">展示步骤间的数据依赖关系，变量从步骤响应中提取后可在后续步骤中使用</span>
            </div>
            <a-table :data="extractVariables" :pagination="false" :bordered="false">
              <template #columns>
                <a-table-column title="步骤" data-index="step">
                  <template #cell="{ record }">
                    <span class="config-cell-text">{{ record.stepName }}</span>
                  </template>
                </a-table-column>
                <a-table-column title="变量名" data-index="key">
                  <template #cell="{ record }">
                    <div class="flex items-center gap-2">
                      <span class="font-mono text-[#165DFF]">${{ record.key }}</span>
                    </div>
                  </template>
                </a-table-column>
                <a-table-column title="提取规则" data-index="extract">
                  <template #cell="{ record }">
                    <span class="config-cell-rule font-mono">{{ record.extract }}</span>
                  </template>
                </a-table-column>
              </template>
            </a-table>
          </div>
        </a-tab-pane>
      </a-tabs>
    </a-modal>
  </div>
</template>

<style lang="postcss" scoped>
@reference "tailwindcss";
:global(.arco-modal-mask) {
  backdrop-filter: blur(4px) !important;
  background: rgba(15, 23, 42, 0.2) !important;
}

:global(.arco-modal) {
  background: #ffffff !important;
  border-radius: 12px !important;
  border: 1px solid rgba(148, 163, 184, 0.16) !important;
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.16) !important;
}

:global(.arco-modal-header) {
  background: transparent !important;
  border-bottom: 1px solid rgba(148, 163, 184, 0.14) !important;
  padding-bottom: 1rem !important;
}

:global(.arco-modal-title) {
  color: #0f172a !important;
}

:global(.arco-modal-body) {
  background: transparent !important;
  padding-top: 1.5rem !important;
  padding-bottom: 1.5rem !important;
}

:global(.arco-modal-footer) {
  background: transparent !important;
  border-top: 1px solid rgba(148, 163, 184, 0.14) !important;
  padding-top: 1rem !important;
}

:global(body.api-testing-theme .arco-modal) {
  background: rgb(17, 24, 39) !important;
  border-color: rgba(75, 85, 99, 0.4) !important;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.08), 0 0 40px rgba(0, 0, 0, 0.55) !important;
}

:global(body.api-testing-theme .arco-modal-header) {
  border-bottom-color: rgba(75, 85, 99, 0.4) !important;
}

:global(body.api-testing-theme .arco-modal-title) {
  color: rgb(226, 232, 240) !important;
}

:global(body.api-testing-theme .arco-modal-footer) {
  border-top-color: rgba(75, 85, 99, 0.4) !important;
}

:deep(.arco-tabs-nav) {
  border-color: var(--tcf-panel-border) !important;
}

:deep(.arco-tabs-tab) {
  color: var(--tcf-text-subtle) !important;

  &.arco-tabs-tab-active {
    @apply text-[#165DFF];
  }
}

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

:deep(.arco-textarea-wrapper) {
  background: var(--tcf-control-bg) !important;
  border-color: var(--tcf-control-border) !important;

  textarea {
    color: var(--tcf-text) !important;
    &::placeholder {
      color: var(--tcf-text-subtle) !important;
    }
  }
}

:deep(.arco-table) {
  @apply bg-transparent;
}

:deep(.arco-table-th) {
  background: var(--tcf-control-bg) !important;
  color: var(--tcf-text-subtle) !important;
  border-color: var(--tcf-panel-border) !important;
  &::before {
    background: var(--tcf-panel-border) !important;
  }
}

:deep(.arco-table-td) {
  background: transparent !important;
  color: var(--tcf-text-muted) !important;
  border-color: var(--tcf-panel-border) !important;
}

:deep(.arco-table-tr) {
  &:hover {
    .arco-table-td {
      background: var(--tcf-section-hover) !important;
    }
  }
}

.config-label,
.config-tip-icon,
.config-tip-text,
.config-cell-rule {
  color: var(--tcf-text-subtle) !important;
}

.config-cell-text {
  color: var(--tcf-text-muted) !important;
}
</style>
