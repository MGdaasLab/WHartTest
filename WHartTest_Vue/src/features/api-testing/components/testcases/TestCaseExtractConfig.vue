<script setup lang="ts">
import { ref, watch, onMounted, inject } from 'vue'
import { IconDelete, IconPlus, IconCode } from '@arco-design/web-vue/es/icon'
import { Message } from '@arco-design/web-vue'
import type { ApiExtractMeta, ApiExtractPayload, ExtractSource, ExtractVariableType } from '../../types/interface'
import ResponseJsonViewer from '../interfaces/ResponseJsonViewer.vue'

interface Props {
  extract?: Record<string, string>
  extractMeta?: ApiExtractMeta
}

const props = withDefaults(defineProps<Props>(), {
  extract: () => ({}),
  extractMeta: () => ({})
})

const apiResponse = inject<any>('apiResponse', ref(null))

const drawerVisible = ref(false)
const currentEditingIndex = ref(-1)

interface ExtractRule {
  variable: string
  expression: string
  description: string
  enabled: boolean
  source: ExtractSource
  variableType: ExtractVariableType
}

const createEmptyRule = (): ExtractRule => ({
  variable: '',
  expression: '',
  description: '',
  enabled: true,
  source: 'response',
  variableType: 'temporary',
})

const extractRules = ref<ExtractRule[]>([createEmptyRule()])
const variableTypeOptions = [
  { label: '临时变量', value: 'temporary' },
  { label: '项目变量', value: 'project' },
]
const sourceOptions = [
  { label: '响应体', value: 'response' },
  { label: '请求体', value: 'request' },
]

const normalizeExtractSource = (source: unknown): ExtractSource => {
  return source === 'request' ? 'request' : 'response'
}

const initExtractRules = () => {
  if (props.extract && Object.keys(props.extract).length > 0) {
    extractRules.value = Object.entries(props.extract).map(([variable, expression]) => ({
      variable,
      expression,
      description: '',
      enabled: true,
      source: normalizeExtractSource(props.extractMeta?.[variable]?.source),
      variableType: props.extractMeta?.[variable]?.variable_type || 'temporary',
    }))
  } else {
    extractRules.value = [createEmptyRule()]
  }
}

watch(() => [props.extract, props.extractMeta], () => {
  initExtractRules()
}, { deep: true })

const addRow = () => {
  extractRules.value.push(createEmptyRule())
}

const removeRow = (index: number) => {
  extractRules.value.splice(index, 1)
  if (extractRules.value.length === 0) {
    extractRules.value.push(createEmptyRule())
  }
}

const handleSelectPath = (path: string) => {
  if (currentEditingIndex.value >= 0 && currentEditingIndex.value < extractRules.value.length) {
    extractRules.value[currentEditingIndex.value].expression = path
    if (!extractRules.value[currentEditingIndex.value].variable.trim()) {
      const pathParts = path.split('.')
      let varName = pathParts[pathParts.length - 1]
      varName = varName.replace(/\[(\d+)\]/g, '_$1')
      extractRules.value[currentEditingIndex.value].variable = varName
    }
    Message.success('已设置提取表达式')
  }
}

const handleDataSourceChange = (source: unknown) => {
  if (currentEditingIndex.value >= 0 && currentEditingIndex.value < extractRules.value.length) {
    extractRules.value[currentEditingIndex.value].source = normalizeExtractSource(source)
  }
}

const openResponseViewer = (index: number) => {
  currentEditingIndex.value = index
  drawerVisible.value = true
}

const getExtractRules = () => {
  const rules: Record<string, string> = {}
  const extractMeta: ApiExtractMeta = {}
  extractRules.value
    .filter(rule => rule.enabled && rule.variable && rule.expression)
    .forEach(rule => {
      rules[rule.variable] = rule.expression
      extractMeta[rule.variable] = {
        variable_type: rule.variableType,
        source: rule.source,
      }
    })
  const payload: ApiExtractPayload = {
    extract: rules,
    extractMeta,
  }
  return payload
}

onMounted(() => { initExtractRules() })

defineExpose({ getExtractRules })
</script>

<template>
  <div class="h-full flex flex-col p-4 space-y-2">
    <div class="flex-1 min-h-0 overflow-y-auto pr-2">
      <div class="space-y-2">
        <div
          v-for="(rule, index) in extractRules"
          :key="index"
          class="flex items-center gap-2 w-full"
        >
          <a-checkbox v-model="rule.enabled" class="flex-shrink-0" />
          <div class="flex flex-1 gap-2">
            <div class="flex relative w-3/5">
              <a-input
                v-model="rule.expression"
                placeholder="提取表达式 (例如: body.data.id)"
                allow-clear
                class="w-full"
              />
              <a-button
                type="text"
                class="extract-code-trigger absolute right-0 top-0 bottom-0 hover:text-blue-500"
                @click="openResponseViewer(index)"
                :disabled="!apiResponse"
              >
                <template #icon><icon-code /></template>
              </a-button>
            </div>
            <a-input v-model="rule.variable" placeholder="变量名" allow-clear class="flex-1" />
            <a-select
              v-model="rule.source"
              :options="sourceOptions"
              class="extract-source-select flex-shrink-0"
            />
            <a-select
              v-model="rule.variableType"
              :options="variableTypeOptions"
              class="extract-type-select flex-shrink-0"
            />
          </div>
          <a-button type="text" status="danger" @click="removeRow(index)" class="flex-shrink-0">
            <template #icon><icon-delete /></template>
          </a-button>
        </div>
      </div>
    </div>
    <div>
      <a-button type="outline" @click="addRow">
        <template #icon><icon-plus /></template>
        添加提取规则
      </a-button>
    </div>

    <!-- 响应JSON查看器 -->
    <ResponseJsonViewer
      v-model:visible="drawerVisible"
      :response-data="apiResponse"
      :data-source="currentEditingIndex >= 0 ? extractRules[currentEditingIndex]?.source : 'response'"
      field-type="extract"
      @update:data-source="handleDataSourceChange"
      @select-path="handleSelectPath"
    />
  </div>
</template>

<style lang="postcss" scoped>
@reference "tailwindcss";
.extract-code-trigger {
  color: var(--tcf-text-subtle);
}

:deep(.arco-input-wrapper) {
  background: var(--tcf-control-bg) !important;
  border-color: var(--tcf-control-border) !important;

  input {
    color: var(--tcf-text) !important;
    background: transparent !important;
    &::placeholder {
      color: var(--tcf-text-subtle) !important;
    }
  }
}

:deep(.arco-checkbox) {
  color: var(--tcf-text-subtle) !important;
}

:deep(.extract-type-select .arco-select-view) {
  background: var(--tcf-control-bg) !important;
  border-color: var(--tcf-control-border) !important;
  color: var(--tcf-text) !important;
}

:deep(.extract-source-select .arco-select-view) {
  background: var(--tcf-control-bg) !important;
  border-color: var(--tcf-control-border) !important;
  color: var(--tcf-text) !important;
}

:deep(.extract-type-select) {
  width: 108px !important;
  min-width: 108px;
}

:deep(.extract-source-select) {
  width: 96px !important;
  min-width: 96px;
}

:deep(.arco-btn-outline) {
  border-color: var(--tcf-control-border) !important;
  color: var(--tcf-text-muted) !important;

  &:hover {
    border-color: rgba(59, 130, 246, 0.4) !important;
    color: rgb(59, 130, 246) !important;
  }
}

:deep(.arco-btn-text) {
  color: var(--tcf-text-subtle) !important;

  &:hover {
    color: rgb(59, 130, 246) !important;
    background: rgba(59, 130, 246, 0.1) !important;
  }

  &.arco-btn-status-danger {
    &:hover {
      color: rgb(239, 68, 68) !important;
      background: rgba(239, 68, 68, 0.1) !important;
    }
  }
}
</style>
