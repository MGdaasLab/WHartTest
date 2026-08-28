<script setup lang="ts">
import { ref, computed } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconPlus, IconSearch, IconCode, IconEdit, IconDelete } from '@arco-design/web-vue/es/icon'
import type { Function } from '../../services/functionService'

interface Props {
  loading?: boolean
  functions: Function[]
  selectedFunction: Function | null
}

interface Emits {
  (e: 'select', func: Function): void
  (e: 'create'): void
  (e: 'edit', func: Function): void
  (e: 'delete', func: Function): void
}

const props = withDefaults(defineProps<Props>(), {
  loading: false
})

const emit = defineEmits<Emits>()

const searchKeyword = ref('')

// 过滤后的函数列表
const filteredFunctions = computed(() => {
  if (!searchKeyword.value) return props.functions

  const keyword = searchKeyword.value.toLowerCase()
  return props.functions.filter(func => 
    func.name.toLowerCase().includes(keyword) || 
    func.description?.toLowerCase().includes(keyword)
  )
})

// 处理编辑按钮点击
const handleEditClick = (func: Function, event: Event) => {
  event.stopPropagation()
  emit('edit', func)
}

// 处理删除按钮点击
const handleDeleteClick = (func: Function, event: Event) => {
  event.stopPropagation()
  emit('delete', func)
}
</script>

<template>
  <div class="w-56 flex flex-col function-list-panel">
    <div class="flex-1 function-list-shell rounded-lg overflow-hidden">
      <!-- 顶部标题和搜索栏 -->
      <div class="p-4 function-list-header">
        <div class="flex justify-between items-center mb-4">
          <div class="flex items-center gap-2">
            <h2 class="text-lg font-medium function-list-title">函数列表</h2>
          </div>
          <a-button type="text" size="small" @click="emit('create')">
            <template #icon><icon-plus /></template>
            新建
          </a-button>
        </div>
        <a-input-search
          v-model="searchKeyword"
          placeholder="搜索函数..."
          allow-clear
        >
          <template #prefix>
            <icon-search />
          </template>
        </a-input-search>
      </div>

      <!-- 函数列表内容 -->
      <div class="flex-1 overflow-hidden">
        <a-spin :loading="loading" dot class="!block h-full">
          <div class="h-full overflow-y-auto">
            <div class="py-2">
              <a-empty v-if="filteredFunctions.length === 0" class="p-4">
                暂无函数数据
              </a-empty>
              <template v-else>
                <div class="space-y-1.5 m-2">
                  <div
                    v-for="func in filteredFunctions"
                    :key="func.id"
                    class="function-list-item px-4 py-2 cursor-pointer transition-colors rounded-lg"
                    :class="{ 
                      'is-selected': selectedFunction?.id === func.id
                    }"
                    @click="emit('select', func)"
                  >
                    <div class="flex items-center justify-between">
                      <div class="flex items-center gap-2">
                        <IconCode class="text-blue-500 w-4 h-4" />
                        <span class="function-list-item-title truncate">{{ func.name }}</span>
                      </div>
                      <div class="flex items-center">
                        <a-button
                          type="text"
                          size="mini"
                          class="item-action !p-0"
                          @click="(e) => handleEditClick(func, e)"
                        >
                          <template #icon><icon-edit /></template>
                        </a-button>
                        <a-button
                          type="text"
                          size="mini"
                          class="item-action !p-0"
                          @click="(e) => handleDeleteClick(func, e)"
                        >
                          <template #icon><icon-delete /></template>
                        </a-button>
                      </div>
                    </div>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </a-spin>
      </div>
    </div>
  </div>
</template> 

<style lang="postcss" scoped>
.function-list-shell {
  background: var(--func-shell-bg);
  border: 1px solid var(--func-shell-border);
  box-shadow: var(--func-shell-shadow);
}

.function-list-header {
  border-bottom: 1px solid var(--func-shell-border);
}

.function-list-title,
.function-list-item-title {
  color: var(--func-text);
}

.function-list-shell :deep(.arco-input-wrapper) {
  background: var(--func-input-bg) !important;
  border-color: var(--func-input-border) !important;

  &:hover,
  &:focus-within {
    border-color: rgba(var(--theme-accent-rgb), 0.42) !important;
    background: var(--func-input-hover-bg) !important;
  }
}

.function-list-shell :deep(.arco-input),
.function-list-shell :deep(.arco-input::placeholder),
.function-list-shell :deep(.arco-input-prefix),
.function-list-shell :deep(.arco-empty-description) {
  color: var(--func-text-subtle) !important;
}

.function-list-shell :deep(.arco-input) {
  color: var(--func-text) !important;
}

.function-list-item {
  background: color-mix(in srgb, var(--func-card-bg) 88%, var(--theme-page-bg) 12%);
  border: 1px solid transparent;
}

.function-list-item:hover,
.function-list-item.is-selected {
  background: rgba(var(--theme-accent-rgb), 0.1);
  border-color: rgba(var(--theme-accent-rgb), 0.22);
}

.item-action {
  color: var(--func-text-subtle) !important;
}

.item-action:hover {
  color: var(--func-text-muted) !important;
}
</style>