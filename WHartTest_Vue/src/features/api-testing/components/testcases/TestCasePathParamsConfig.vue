<script setup lang="ts">
import { ref, watch } from "vue"
import { IconDelete, IconPlus, IconRefresh } from "@arco-design/web-vue/es/icon"

interface KeyValuePair {
  key: string
  value: string
  description: string
  enabled: boolean
}

interface Props {
  pathParams?: Record<string, any> | KeyValuePair[]
  url?: string
  readonly?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  pathParams: () => [],
  url: "",
  readonly: false
})

const emit = defineEmits(["update:pathParams", "update:path-params"])

const pathParamsList = ref<KeyValuePair[]>([{ key: "", value: "", description: "", enabled: true }])

// 从 URL 中提取路径参数名（支持 {param} 和 :param 两种语法）
const extractPathKeysFromUrl = (urlStr?: string): string[] => {
  if (!urlStr) return []
  const keys: string[] = []
  const seen = new Set<string>()

  // 匹配 {param} 格式
  const braceMatches = urlStr.matchAll(/\{\s*([a-zA-Z_][a-zA-Z0-9_-]*)\s*\}/g)
  for (const match of braceMatches) {
    const key = match[1]
    if (key && !seen.has(key)) {
      seen.add(key)
      keys.push(key)
    }
  }

  // 匹配 :param 格式
  const colonMatches = urlStr.matchAll(/:([a-zA-Z_][a-zA-Z0-9_-]*)(?=(?:[/\\?#]|$))/g)
  for (const match of colonMatches) {
    const key = match[1]
    if (key && !seen.has(key)) {
      seen.add(key)
      keys.push(key)
    }
  }

  return keys
}

// 初始化参数列表
const initPathParamsList = () => {
  if (Array.isArray(props.pathParams)) {
    pathParamsList.value = props.pathParams.map(item => ({
      key: item.key ?? "",
      value: String(item.value ?? ""),
      description: item.description ?? "",
      enabled: item.enabled !== false
    }))
  } else if (props.pathParams && typeof props.pathParams === "object") {
    pathParamsList.value = Object.entries(props.pathParams).map(([key, value]) => ({
      key,
      value: String(value ?? ""),
      description: "",
      enabled: true
    }))
  } else {
    pathParamsList.value = []
  }

  if (pathParamsList.value.length === 0) {
    pathParamsList.value.push({ key: "", value: "", description: "", enabled: true })
  }
}

// 智能同步 URL 中的变量到表格中
const syncWithUrlKeys = (forceOverride = false) => {
  const urlKeys = extractPathKeysFromUrl(props.url)
  if (!urlKeys.length && !forceOverride) return

  const existingMap = new Map<string, KeyValuePair>()
  for (const item of pathParamsList.value) {
    if (item.key) {
      existingMap.set(item.key, item)
    }
  }

  if (
    pathParamsList.value.length === 1 &&
    !pathParamsList.value[0].key &&
    !pathParamsList.value[0].value
  ) {
    pathParamsList.value = urlKeys.map(k => ({
      key: k,
      value: "",
      description: "",
      enabled: true
    }))
    emitUpdates()
    return
  }

  let changed = false
  for (const k of urlKeys) {
    if (!existingMap.has(k)) {
      pathParamsList.value.push({
        key: k,
        value: "",
        description: "",
        enabled: true
      })
      changed = true
    }
  }

  if (changed) {
    emitUpdates()
  }
}

watch(
  () => props.pathParams,
  () => {
    initPathParamsList()
  },
  { immediate: true, deep: true }
)

watch(
  () => props.url,
  () => {
    syncWithUrlKeys(false)
  }
)

const emitUpdates = () => {
  const result = pathParamsList.value.map(p => ({ ...p }))
  emit("update:pathParams", result)
  emit("update:path-params", result)
}

const addParam = () => {
  pathParamsList.value.push({ key: "", value: "", description: "", enabled: true })
  emitUpdates()
}

const deleteParam = (index: number) => {
  pathParamsList.value.splice(index, 1)
  if (pathParamsList.value.length === 0) {
    pathParamsList.value.push({ key: "", value: "", description: "", enabled: true })
  }
  emitUpdates()
}

const onRowChange = () => {
  emitUpdates()
}

const handleExtractFromUrl = () => {
  syncWithUrlKeys(true)
}

const getPathParams = (): KeyValuePair[] => {
  return pathParamsList.value.filter(param => param.enabled !== false && (param.key.trim() || param.value.trim()))
}

const getParams = (): KeyValuePair[] => {
  return getPathParams()
}

defineExpose({
  getPathParams,
  getParams
})
</script>

<template>
  <div class="h-full flex flex-col p-4 space-y-2">
    <div class="flex-1 min-h-0 overflow-y-auto pr-2">
      <div class="space-y-2">
        <div
          v-for="(param, index) in pathParamsList"
          :key="index"
          class="flex items-center gap-2"
        >
          <a-checkbox
            v-model="param.enabled"
            :disabled="readonly"
            @change="onRowChange"
          />
          <a-input
            v-model="param.key"
            placeholder="参数名 (如: id 或 userId)"
            allow-clear
            :disabled="readonly"
            @input="onRowChange"
          />
          <a-input
            v-model="param.value"
            placeholder="参数值 (支持 $变量名)"
            allow-clear
            :disabled="readonly"
            @input="onRowChange"
          />
          <a-input
            v-model="param.description"
            placeholder="参数说明"
            allow-clear
            :disabled="readonly"
            @input="onRowChange"
          />
          <a-button
            type="text"
            status="danger"
            :disabled="readonly"
            @click="deleteParam(index)"
          >
            <template #icon><icon-delete /></template>
          </a-button>
        </div>
      </div>
    </div>
    <div class="flex items-center justify-center gap-2 pt-2 border-t border-[color:var(--color-border-2)]">
      <a-button type="outline" :disabled="readonly" @click="addParam">
        <template #icon><icon-plus /></template>
        添加路径参数
      </a-button>
      <a-button type="secondary" :disabled="readonly" @click="handleExtractFromUrl">
        <template #icon><icon-refresh /></template>
        从 URL 提取
      </a-button>
    </div>
  </div>
</template>

<style lang="postcss" scoped>
@reference "tailwindcss";
:deep(.arco-input-wrapper) {
  @apply bg-white border-[color:var(--color-border-2)];

  input {
    @apply text-[color:var(--color-text-1)] bg-transparent;
    &::placeholder {
      @apply text-[color:var(--color-text-3)];
    }
  }
}

:deep(.arco-checkbox) {
  @apply mr-0;
}
</style>
