<script setup lang="ts">
defineProps<{
  current: number
  pageSize: number
  total: number
}>()

defineEmits(['change', 'page-size-change'])
</script>

<template>
  <div class="interface-pagination rounded-lg border px-4 py-3">
    <a-pagination
      :current="current"
      :page-size="pageSize"
      :total="total"
      @update:current="$emit('change', $event)"
      @update:page-size="$emit('page-size-change', $event)"
      show-total
      show-jumper
      show-page-size
      class="flex justify-end"
    />
  </div>
</template>

<style scoped>
.interface-pagination {
  background: var(--asd-panel-bg);
  border-color: var(--asd-panel-border);
  flex-shrink: 0;
}

:deep(.arco-pagination) {
  .arco-pagination-item {
    border-radius: 4px !important;
    color: var(--asd-text-subtle) !important;
    background-color: transparent !important;
    border: 1px solid transparent !important;

    &:hover {
      color: #60a5fa !important;
      background-color: rgba(59, 130, 246, 0.1) !important;
      border-color: rgba(59, 130, 246, 0.2) !important;
    }

    &.arco-pagination-item-active {
      background-color: rgba(59, 130, 246, 0.2) !important;
      color: #60a5fa !important;
      border-color: rgba(59, 130, 246, 0.3) !important;
    }
  }

  .arco-pagination-jumper {
    .arco-input {
      border-radius: 4px !important;
      background-color: var(--asd-control-bg) !important;
      border: 1px solid var(--asd-control-border) !important;
      color: var(--asd-text) !important;

      &:hover, &:focus {
        border-color: rgba(59, 130, 246, 0.5) !important;
        background-color: var(--asd-control-hover) !important;
      }
    }
  }

  .arco-pagination-total {
    color: var(--asd-text-subtle) !important;
  }

  .arco-select-view {
    background-color: var(--asd-control-bg) !important;
    border: 1px solid var(--asd-control-border) !important;
    border-radius: 4px !important;
    color: var(--asd-text) !important;

    &:hover {
      border-color: rgba(59, 130, 246, 0.5) !important;
      background-color: var(--asd-control-hover) !important;
    }
  }
}
</style>
