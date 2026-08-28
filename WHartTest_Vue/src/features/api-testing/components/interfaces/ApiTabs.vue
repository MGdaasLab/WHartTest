<script setup lang="ts">
import { computed } from 'vue'
import { IconClose, IconPlus } from '@arco-design/web-vue/es/icon'
import { useApiTabsStore } from '../../stores/apiTabsStore'
import type { ApiInterface } from '../../services/interfaceService'

const props = defineProps<{
  currentInterface?: ApiInterface
}>()

const emit = defineEmits<{
  'tab-change': [tabId: string]
  'new-interface': []
}>()

const tabsStore = useApiTabsStore()

// 计算属性
const tabs = computed(() => tabsStore.tabs)
const activeTabId = computed(() => tabsStore.activeTabId)

// 切换页签
const handleTabClick = (tabId: string) => {
  tabsStore.activateTab(tabId)
  emit('tab-change', tabId)
}

// 关闭页签
const handleCloseTab = (e: Event, tabId: string) => {
  e.stopPropagation()
  tabsStore.removeTab(tabId)
}

const handleCreateInterface = () => {
  emit('new-interface')
}


// 获取页签显示名称
const getTabLabel = (tab: any) => {
  const method = tab.method || 'GET'
  const name = tab.name || '新接口'
  return `${method} ${name}`
}

// 获取页签颜色
const getMethodColor = (method: string) => {
  switch (method?.toUpperCase()) {
    case 'GET': return 'text-blue-500'
    case 'POST': return 'text-green-500'
    case 'PUT': return 'text-orange-500'
    case 'DELETE': return 'text-red-500'
    case 'PATCH': return 'text-purple-500'
    default: return 'text-gray-400'
  }
}
</script>

<template>
  <!-- 独立的卡片样式容器 -->
  <div class="api-tabs-card mb-2 rounded-lg shadow-lg overflow-hidden">
    <div class="px-2 py-2">
      <div class="flex items-center gap-2 overflow-x-auto scrollbar-thin">
        <!-- 页签列表 -->
        <div
          v-for="tab in tabs"
          :key="tab.id"
          class="group flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer min-w-max transition-all border"
          :class="tab.id === activeTabId
            ? 'tab-chip tab-chip--active'
            : 'tab-chip tab-chip--inactive'"
          @click="handleTabClick(tab.id)"
        >
          <!-- 请求方法标签 -->
          <span
            class="text-xs font-bold"
            :class="tab.id === activeTabId ? 'opacity-100' : getMethodColor(tab.method)"
          >
            {{ tab.method }}
          </span>
          
          <!-- 接口名称 -->
          <span
            class="text-sm max-w-[180px] truncate"
            :class="tab.id === activeTabId ? 'font-medium' : ''"
            :title="tab.name"
          >
            {{ tab.name }}
          </span>
          
          <!-- 响应状态指示器 -->
          <div v-if="tab.response?.status" class="flex items-center">
            <div
              class="w-2 h-2 rounded-full animate-pulse"
              :class="{
                'bg-green-500': tab.response.status >= 200 && tab.response.status < 300,
                'bg-red-500': tab.response.status >= 400,
                'bg-yellow-500': tab.response.status >= 300 && tab.response.status < 400
              }"
            ></div>
          </div>
          
          <!-- 关闭按钮 - 只显示X -->
          <icon-close
            class="ml-1 w-3.5 h-3.5 cursor-pointer transition-all"
            :class="tab.id === activeTabId
              ? 'opacity-60 hover:opacity-100 hover:text-red-400'
              : 'opacity-0 group-hover:opacity-60 group-hover:hover:opacity-100 group-hover:hover:text-red-400'"
            @click="handleCloseTab($event, tab.id)"
            title="关闭页签"
          />
        </div>
        
        <div v-if="tabs.length === 0" class="tabs-empty-state py-1 px-3">
          <a-button type="primary" size="small" @click="handleCreateInterface">
            <template #icon><icon-plus /></template>
            新建接口
          </a-button>
          <span class="tabs-empty-hint text-sm">请从这里新建接口，或从左侧选择已有接口开始调试</span>
        </div>

        <a-button
          v-else
          class="tabs-create-button"
          size="small"
          @click="handleCreateInterface"
          title="新建接口"
        >
          <template #icon><icon-plus /></template>
        </a-button>
      </div>
    </div>
  </div>
</template>

<style lang="postcss" scoped>
.api-tabs-card {
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid rgba(148, 163, 184, 0.16);
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.08);
}

.tabs-empty-state {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.tab-chip--active {
  background: rgba(var(--primary-6), 0.12);
  border-color: rgba(var(--primary-6), 0.32);
  color: rgb(var(--primary-6));
}

.tab-chip--inactive {
  background: rgba(248, 250, 252, 0.96);
  border-color: rgba(148, 163, 184, 0.18);
  color: var(--color-text-2);
}

.tab-chip--inactive:hover {
  background: rgba(241, 245, 249, 1);
  border-color: rgba(148, 163, 184, 0.32);
}

.tabs-empty-hint {
  color: var(--color-text-3);
}

.tabs-create-button {
  flex-shrink: 0;
}

:global(body.api-testing-theme) .api-tabs-card {
  background: rgb(31, 41, 55);
  border-color: rgba(55, 65, 81, 0.92);
  box-shadow: 0 14px 28px rgba(2, 6, 23, 0.28);
}

:global(body.api-testing-theme) .tab-chip--inactive {
  background: rgba(55, 65, 81, 0.3);
  border-color: rgb(55, 65, 81);
  color: rgb(209, 213, 219);
}

:global(body.api-testing-theme) .tab-chip--inactive:hover {
  background: rgba(55, 65, 81, 0.5);
  border-color: rgb(75, 85, 99);
}

:global(body.api-testing-theme) .tabs-empty-hint {
  color: rgb(107, 114, 128);
}

/* 自定义滚动条样式 */
.scrollbar-thin {
  scrollbar-width: thin;
  scrollbar-color: rgba(156, 163, 175, 0.3) transparent;
}

.scrollbar-thin::-webkit-scrollbar {
  height: 6px;
}

.scrollbar-thin::-webkit-scrollbar-track {
  background: transparent;
}

.scrollbar-thin::-webkit-scrollbar-thumb {
  background-color: rgba(156, 163, 175, 0.3);
  border-radius: 3px;
}

.scrollbar-thin::-webkit-scrollbar-thumb:hover {
  background-color: rgba(156, 163, 175, 0.5);
}
</style>