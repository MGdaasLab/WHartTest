<template>
  <div class="card-tabs" :class="{ 'card-tabs--full': fullHeight }">
    <div class="card-tabs-nav">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="['card-tab-item', { 'card-tab-item--active': modelValue === tab.key }]"
        @click="emit('update:modelValue', tab.key)"
      >
        {{ tab.title }}
      </button>
    </div>
    <div class="card-tabs-content">
      <template v-if="destroyOnHide">
        <div v-if="activeTabItem" :key="activeTabItem.key" class="card-tab-pane">
          <slot :name="activeTabItem.key" />
        </div>
      </template>
      <template v-else>
        <div v-for="tab in tabs" :key="tab.key" v-show="modelValue === tab.key" class="card-tab-pane">
          <slot :name="tab.key" />
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

export interface TabItem {
  key: string
  title: string
}

const props = withDefaults(defineProps<{
  modelValue: string
  tabs: TabItem[]
  fullHeight?: boolean
  destroyOnHide?: boolean
}>(), {
  fullHeight: true,
  destroyOnHide: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const activeTabItem = computed(() => {
  return props.tabs.find(tab => tab.key === props.modelValue) ?? props.tabs[0]
})
</script>

<style scoped>
.card-tabs {
  display: flex;
  flex-direction: column;
}

.card-tabs--full {
  height: 100%;
}

.card-tabs-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px 10px;
  flex-shrink: 0;
  border-bottom: 1px solid var(--color-border-2, rgba(0, 0, 0, 0.08));
}

.card-tab-item {
  padding: 4px 12px;
  font-size: 12px;
  line-height: 20px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  color: var(--color-text-3, #86909c);
  background: var(--color-fill-2, #f2f3f5);
  transition: all 0.2s ease;
  white-space: nowrap;
}

.card-tab-item:hover {
  color: var(--color-text-2, #4e5969);
  background: var(--color-fill-3, #e5e6eb);
}

.card-tab-item--active {
  color: rgb(var(--primary-6, 64 128 255));
  background: rgba(var(--primary-6, 64 128 255), 0.1);
  font-weight: 500;
}

.card-tab-item--active:hover {
  color: rgb(var(--primary-6, 64 128 255));
  background: rgba(var(--primary-6, 64 128 255), 0.15);
}

.card-tabs-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  position: relative;
}

.card-tab-pane {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  overflow: hidden;
}
</style>
