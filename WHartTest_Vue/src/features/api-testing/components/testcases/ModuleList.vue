<script setup lang="ts">
import { ref, computed } from 'vue'
import { IconSearch } from '@arco-design/web-vue/es/icon'
import type { ApiModule } from '../../types/module'
import ModuleTreeSelect from './ModuleTreeSelect.vue'

const props = defineProps<{
  modules: ApiModule[]
  expandedIds: number[]
  selectedId?: number
  loading: boolean
}>()

const emit = defineEmits(['select', 'toggle-expand'])

const searchKeyword = ref('')

const filteredModules = computed(() => {
  if (!searchKeyword.value) return props.modules

  const keyword = searchKeyword.value.toLowerCase()
  return props.modules.filter(item =>
    item.name.toLowerCase().includes(keyword)
  )
})
</script>

<template>
  <div class="module-list-panel w-[280px] rounded-lg border overflow-hidden flex flex-col min-h-0">
    <div class="module-list-header p-4 border-b">
      <div class="flex items-center justify-between mb-2">
        <span class="module-list-title">模块列表</span>
      </div>
      <div class="flex items-center gap-2">
        <a-input-search
          v-model="searchKeyword"
          placeholder="搜索模块"
          allow-clear
        >
          <template #prefix>
            <icon-search />
          </template>
        </a-input-search>
      </div>
    </div>
    <div class="module-list-body flex-1 min-h-0 overflow-y-auto hide-scrollbar">
      <div class="p-2 space-y-1">
        <ModuleTreeSelect
          v-for="module in filteredModules"
          :key="module.id"
          :module="module"
          :expanded-ids="expandedIds"
          :selected-id="selectedId"
          :loading="loading"
          @select="$emit('select', $event)"
          @toggle-expand="$emit('toggle-expand', $event)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.module-list-panel {
  background: var(--asd-panel-bg);
  border-color: var(--asd-panel-border);
}

.module-list-body {
  min-height: 0;
}

.module-list-header {
  border-color: var(--asd-panel-border);
  flex-shrink: 0;
}

.module-list-title {
  color: var(--asd-text);
}

:deep(.arco-input-wrapper) {
  background: var(--asd-control-bg) !important;
  border-color: var(--asd-control-border) !important;

  input {
    color: var(--asd-text) !important;
  }
}

:deep(.arco-input-wrapper input::placeholder),
:deep(.arco-input-prefix) {
  color: var(--asd-text-subtle) !important;
}

.hide-scrollbar {
  scrollbar-width: none;  /* Firefox */
  -ms-overflow-style: none;  /* IE and Edge */
}

.hide-scrollbar::-webkit-scrollbar {
  display: none;  /* Chrome, Safari and Opera */
}
</style>
