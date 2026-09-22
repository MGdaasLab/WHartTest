<template>
  <div ref="rootRef" class="card-tabs" :class="{ 'card-tabs--full': fullHeight }">
    <div class="card-tabs-nav">
      <div class="card-tabs-list">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          :class="['card-tab-item', { 'card-tab-item--active': modelValue === tab.key }]"
          @click="emit('update:modelValue', tab.key)"
        >
          {{ tab.title }}
        </button>
      </div>
      <a-tooltip :content="isFullscreen ? tl('退出全屏') : tl('全屏')">
        <button class="card-tabs-fullscreen-btn" type="button" @click="toggleFullscreen">
          <icon-fullscreen-exit v-if="isFullscreen" />
          <icon-fullscreen v-else />
        </button>
      </a-tooltip>
    </div>
    <div class="card-tabs-content">
      <template v-for="tab in tabs" :key="tab.key">
        <div
          v-if="destroyOnHide ? modelValue === tab.key : activatedKeys.includes(tab.key)"
          v-show="modelValue === tab.key"
          class="card-tab-pane"
        >
          <slot :name="tab.key" />
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { IconFullscreen, IconFullscreenExit } from '@arco-design/web-vue/es/icon'
import { useAppI18n } from '@/composables/useAppI18n'

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

const { tl } = useAppI18n()

const rootRef = ref<HTMLElement | null>(null)
const isFullscreen = ref(false)

// 非销毁模式下，记录已被激活过的页签：首次激活才挂载，之后保活，避免来回切换丢状态
const activatedKeys = ref<string[]>([])

watch(
  () => props.modelValue,
  (key) => {
    if (!activatedKeys.value.includes(key)) {
      activatedKeys.value.push(key)
    }
  },
  { immediate: true }
)

// tabs 动态增删时同步清理，避免残留 key 在同名页签重新加入时复用旧状态
watch(
  () => props.tabs,
  (tabs) => {
    const validKeys = new Set(tabs.map(tab => tab.key))
    if (activatedKeys.value.some(key => !validKeys.has(key))) {
      activatedKeys.value = activatedKeys.value.filter(key => validKeys.has(key))
    }
  },
  { deep: true }
)

const syncFullscreenState = () => {
  isFullscreen.value = document.fullscreenElement === rootRef.value
}

const toggleFullscreen = async () => {
  const el = rootRef.value
  if (!el) return

  try {
    if (document.fullscreenElement === el) {
      await document.exitFullscreen()
    } else {
      await el.requestFullscreen()
    }
  } catch (error) {
    console.error('切换全屏失败:', error)
  }
}

onMounted(() => {
  document.addEventListener('fullscreenchange', syncFullscreenState)
})

onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', syncFullscreenState)
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
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  flex-shrink: 0;
  border-bottom: 1px solid var(--color-border-2, rgba(0, 0, 0, 0.08));
}

.card-tabs-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  flex: 1;
  min-width: 0;
}

.card-tabs-fullscreen-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  flex-shrink: 0;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  color: var(--color-text-3, #86909c);
  background: var(--color-fill-2, #f2f3f5);
  font-size: 14px;
  transition: all 0.2s ease;
}

.card-tabs-fullscreen-btn:hover {
  color: var(--color-text-2, #4e5969);
  background: var(--color-fill-3, #e5e6eb);
}

/* 全屏态下铺满视口，保持内部布局不变 */
.card-tabs:fullscreen {
  background-color: var(--color-bg-1, #fff);
  border-radius: 0;
  overflow: auto;
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
