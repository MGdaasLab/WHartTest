<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { functionService } from '../../services/functionService'
import { toArray } from '../../services/responseHelpers'
import { useProjectStore } from '@/store/projectStore'
import type { ApiCustomFunction } from '../../types/function'

interface Props {
  hooks?: string[]
}

const props = withDefaults(defineProps<Props>(), {
  hooks: () => []
})

const emit = defineEmits(['update:hooks'])
const projectStore = useProjectStore()

const state = ref({
  selectedFunctions: [] as number[],
  functions: [] as ApiCustomFunction[],
  loading: false
})

const loadFunctions = async () => {
  if (!projectStore.currentProjectId) return
  state.value.loading = true
  try {
    const res = await functionService.list(projectStore.currentProjectId)
    if (res.success && res.data) {
      state.value.functions = toArray<ApiCustomFunction>((res.data as any)?.results ?? res.data)
    }
    if (props.hooks && props.hooks.length > 0) {
      state.value.selectedFunctions = props.hooks.map(hook => {
        const fid = typeof hook === 'string' ? parseInt(hook) : -1
        return isNaN(fid) ? -1 : fid
      }).filter(id => id !== -1)
    }
  } catch (error) {
    console.error('Failed to load functions:', error)
  } finally {
    state.value.loading = false
  }
}

watch(() => props.hooks, (newHooks) => {
  if (newHooks && newHooks.length > 0) {
    state.value.selectedFunctions = newHooks.map(hook => {
      const fid = typeof hook === 'string' ? parseInt(hook) : -1
      return isNaN(fid) ? -1 : fid
    }).filter(id => id !== -1)
  } else {
    state.value.selectedFunctions = []
  }
}, { immediate: true, deep: true })

watch(() => projectStore.currentProjectId, () => { loadFunctions() })

const getHooks = () => {
  if (state.value.selectedFunctions.length > 0) {
    return state.value.selectedFunctions.map(id => {
      const func = state.value.functions.find(f => f.id === id)
      return func ? String(func.id) : ''
    }).filter(Boolean)
  }
  return []
}

onMounted(() => { loadFunctions() })
defineExpose({ getHooks })
</script>

<template>
  <div class="h-full flex flex-col p-4 gap-4">
    <a-select
      v-model="state.selectedFunctions"
      :loading="state.loading"
      placeholder="选择前置函数"
      allow-clear
      multiple
    >
      <a-option v-for="func in state.functions" :key="func.id" :value="func.id">
        {{ func.name }}
      </a-option>
    </a-select>
    <div v-if="state.selectedFunctions.length > 0" class="flex flex-col gap-2">
      <div class="selected-label">已选择的函数：</div>
      <div class="flex flex-wrap gap-2">
        <a-tag
          v-for="id in state.selectedFunctions"
          :key="id"
          closable
          @close="state.selectedFunctions = state.selectedFunctions.filter(fid => fid !== id)"
        >
          {{ state.functions.find(f => f.id === id)?.name || `函数${id}` }}
        </a-tag>
      </div>
    </div>
  </div>
</template>

<style lang="postcss" scoped>
@reference "tailwindcss";
:deep(.arco-select-view) {
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

:global(.arco-select-dropdown) {
  background: #ffffff !important;
  border: 1px solid rgba(148, 163, 184, 0.16) !important;
  border-radius: 10px !important;

  .arco-select-option {
    color: #334155 !important;

    &:hover {
      background: #f8fafc !important;
    }

    &.arco-select-option-active,
    &.arco-select-option-selected {
      background: rgba(59, 130, 246, 0.12) !important;
      color: #2563eb !important;
    }
  }
}

:global(body.api-testing-theme .arco-select-dropdown) {
  background: rgb(31, 41, 55) !important;
  border-color: rgba(75, 85, 99, 0.4) !important;
}

:global(body.api-testing-theme .arco-select-dropdown .arco-select-option) {
  color: rgb(203, 213, 225) !important;

  &:hover {
    background: rgba(51, 65, 85, 0.9) !important;
  }
}

:deep(.arco-tag) {
  background: rgba(59, 130, 246, 0.12) !important;
  border-color: rgba(59, 130, 246, 0.28) !important;
  color: #2563eb !important;
}

.selected-label {
  color: var(--tcf-text-subtle);
}
</style>
