<script setup lang="ts">
interface QueryParams {
  name: string
  description: string
}

interface Props {
  modelValue: QueryParams
}

const props = defineProps<Props>()
const emit = defineEmits(['update:modelValue', 'search', 'reset'])

const updateValue = (key: keyof QueryParams, value: string) => {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

const handleSearch = () => {
  emit('search')
}

const handleReset = () => {
  emit('reset')
}
</script>

<template>
  <div class="flex items-center gap-4">
    <a-input-search
      :model-value="modelValue.name"
      @update:model-value="(val: string) => updateValue('name', val)"
      placeholder="搜索用例名称"
      class="flex-1"
      allow-clear
      @search="handleSearch"
      @press-enter="handleSearch"
      @clear="handleReset"
    />
    <a-input
      :model-value="modelValue.description"
      @update:model-value="(val: string) => updateValue('description', val)"
      placeholder="搜索用例描述"
      class="flex-1"
      allow-clear
      @press-enter="handleSearch"
    />
  </div>
</template>

<style scoped>
:deep(.arco-input-wrapper) {
  background-color: var(--tc-input-bg) !important;
  border-color: var(--tc-input-border) !important;

  &:hover, &:focus-within {
    border-color: rgba(var(--theme-accent-rgb), 0.42) !important;
    background-color: var(--tc-input-bg-hover) !important;
  }

  .arco-input {
    color: var(--tc-text) !important;
  }

  .arco-input::placeholder {
    color: var(--tc-text-subtle) !important;
  }

  .arco-input-prefix, .arco-input-suffix {
    color: var(--tc-text-subtle) !important;
  }
}
</style>
