<template>
  <div class="config-info-shell rounded-lg border">
    <div class="config-info-header px-4 pt-2 border-b">
      <h3 class="config-info-title text-lg font-medium -mb-1">配置信息</h3>
    </div>
    <div class="px-4">
      <div class="space-y-3">
        <div class="config-item">
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center gap-2">
              <p class="config-meta-label text-sm">配置变量</p>
              <span v-if="configVarEntries.length" class="config-meta-count text-xs">
                ({{ configVarEntries.length }}个)
              </span>
            </div>
            <div class="flex items-center gap-2">
              <a-button 
                v-if="configVarEntries.length" 
                type="text" 
                size="mini" 
                @click="toggleDrawer('config_vars')"
              >
                <template #icon><icon-expand class="config-action-icon" /></template>
                查看全部
              </a-button>
              <a-tooltip position="left">
                <template #content>
                  <div class="text-sm">
                    <p>测试执行时的环境配置变量</p>
                  </div>
                </template>
                <icon-info-circle class="config-action-icon cursor-help" />
              </a-tooltip>
            </div>
          </div>
          <div v-if="configVarEntries.length" class="config-card rounded-lg p-3 border">
            <div class="space-y-2 max-h-[200px] overflow-y-auto">
              <div v-for="([key, value], index) in visibleConfigVarEntries" :key="key"
                   class="config-row flex items-center justify-between px-2 py-1 rounded">
                <span class="config-key text-sm">{{ key }}</span>
                <div class="flex items-center gap-2">
                  <span class="text-sm text-blue-400 font-mono" :title="toCopyText(value)">{{ formatPreviewValue(value) }}</span>
                  <a-button type="text" size="mini" @click="copyToClipboard(value)">
                    <template #icon><icon-copy class="config-action-icon hover:text-blue-400" /></template>
                  </a-button>
                </div>
              </div>
              <div v-if="configVarEntries.length > 3" class="config-meta-count text-center text-xs mt-2">
                显示前3项，共{{ configVarEntries.length }}项
              </div>
            </div>
          </div>
          <div v-else class="config-card rounded-lg p-3 border">
            <p class="config-empty text-sm text-center">无配置变量</p>
          </div>
        </div>
        <div class="config-item">
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center gap-2">
              <p class="config-meta-label text-sm">提取变量</p>
              <span v-if="exportVarEntries.length" class="config-meta-count text-xs">
                ({{ exportVarEntries.length }}个)
              </span>
            </div>
            <div class="flex items-center gap-2">
              <a-button 
                v-if="exportVarEntries.length" 
                type="text" 
                size="mini" 
                @click="toggleDrawer('export_vars')"
              >
                <template #icon><icon-expand class="config-action-icon" /></template>
                查看全部
              </a-button>
              <a-tooltip position="left">
                <template #content>
                  <div class="text-sm">
                    <p>测试执行过程中从响应中提取的变量</p>
                  </div>
                </template>
                <icon-info-circle class="config-action-icon cursor-help" />
              </a-tooltip>
            </div>
          </div>
          <div v-if="exportVarEntries.length" class="config-card rounded-lg p-3 border">
            <div class="space-y-2 max-h-[200px] overflow-y-auto">
              <div v-for="([key, value], index) in visibleExportVarEntries" :key="key"
                   class="config-row flex items-center justify-between px-2 py-1 rounded">
                <span class="config-key text-sm">{{ key }}</span>
                <div class="flex items-center gap-2">
                  <span class="text-sm text-green-400 font-mono" :title="toCopyText(value)">{{ formatPreviewValue(value) }}</span>
                  <a-button type="text" size="mini" @click="copyToClipboard(value)">
                    <template #icon><icon-copy class="config-action-icon hover:text-green-400" /></template>
                  </a-button>
                </div>
              </div>
              <div v-if="exportVarEntries.length > 3" class="config-meta-count text-center text-xs mt-2">
                显示前3项，共{{ exportVarEntries.length }}项
              </div>
            </div>
          </div>
          <div v-else class="config-card rounded-lg p-3 border">
            <p class="config-empty text-sm text-center">无提取变量</p>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 抽屉组件 - 用于显示完整的变量信息 -->
  <a-drawer
    :visible="drawerVisible"
    :width="800"
    @cancel="drawerVisible = false"
    :title="currentDrawerType === 'config_vars' ? '配置变量详情' : '提取变量详情'"
    :footer="false"
    class="config-info-drawer"
    :mask="true"
    :mask-style="{ backgroundColor: 'transparent' }"
    :mask-closable="true"
    @close="drawerVisible = false"
  >
    <div class="p-6">
      <div v-if="currentDrawerType === 'config_vars' && configVarEntries.length" class="space-y-3">
        <div v-for="([key, value]) in configVarEntries" :key="key" class="config-card rounded-lg p-3 border">
          <div class="flex items-start gap-3">
            <div class="flex-1">
              <div class="config-key text-sm">{{ key }}</div>
              <div class="config-inline-value mt-2 p-2 rounded border">
                <div class="text-sm text-blue-400 font-mono break-all">{{ value }}</div>
              </div>
            </div>
            <a-button type="text" size="mini" @click="copyToClipboard(value)">
              <template #icon><icon-copy class="config-action-icon hover:text-blue-400" /></template>
            </a-button>
          </div>
        </div>
      </div>
      <div v-else-if="currentDrawerType === 'export_vars' && exportVarEntries.length" class="space-y-3">
        <div v-for="([key, value]) in exportVarEntries" :key="key" class="config-card rounded-lg p-3 border">
          <div class="flex items-start gap-3">
            <div class="flex-1">
              <div class="config-key text-sm">{{ key }}</div>
              <div class="config-inline-value mt-2 p-2 rounded border">
                <div class="text-sm text-green-400 font-mono break-all">{{ value }}</div>
              </div>
            </div>
            <a-button type="text" size="mini" @click="copyToClipboard(value)">
              <template #icon><icon-copy class="config-action-icon hover:text-green-400" /></template>
            </a-button>
          </div>
        </div>
      </div>
      <div v-else class="config-empty text-center">
        无数据
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { 
  IconInfoCircle, 
  IconCopy, 
  IconExpand 
} from '@arco-design/web-vue/es/icon'
import { Message } from '@arco-design/web-vue'
import type { TestReportResponse } from './TestReportDetail.vue'

const props = defineProps<{
  report: TestReportResponse | null
}>()

const configVarEntries = computed(() => Object.entries(props.report?.summary?.in_out?.config_vars || {}))
const exportVarEntries = computed(() => Object.entries(props.report?.summary?.in_out?.export_vars || {}))
const visibleConfigVarEntries = computed(() => configVarEntries.value.slice(0, 3))
const visibleExportVarEntries = computed(() => exportVarEntries.value.slice(0, 3))

// 抽屉组件状态控制
const drawerVisible = ref(false)
const currentDrawerType = ref<'config_vars' | 'export_vars' | null>(null)

/**
 * 切换抽屉的显示状态，并设置要显示的数据类型
 * @param type 数据类型（配置变量或提取变量）
 */
const toggleDrawer = (type: 'config_vars' | 'export_vars') => {
  currentDrawerType.value = type
  drawerVisible.value = true
}

const toCopyText = (value: unknown) => {
  if (value === null || value === undefined) {
    return ''
  }

  return typeof value === 'string' ? value : JSON.stringify(value)
}

const formatPreviewValue = (value: unknown) => {
  const text = toCopyText(value)
  return text.length > 20 ? `${text.substring(0, 20)}...` : text
}

/**
 * 将文本复制到剪贴板
 * @param text 要复制的文本
 */
const copyToClipboard = async (text: unknown) => {
  try {
    if (text === null || text === undefined) {
      Message.warning('复制内容为空')
      return
    }
    await navigator.clipboard.writeText(toCopyText(text))
    Message.success('复制成功')
  } catch (err) {
    Message.error('复制失败')
  }
}
</script>

<style scoped>
@reference "tailwindcss";
.config-info-shell {
  background: color-mix(in srgb, var(--api-report-card-bg) 88%, var(--theme-page-bg) 12%);
  border-color: var(--api-report-shell-border);
  backdrop-filter: blur(10px);
}

.config-info-header {
  border-color: var(--api-report-shell-border);
}

.config-info-title {
  color: var(--api-report-text);
}

.config-meta-label,
.config-key,
.config-action-icon,
.config-empty,
.config-meta-count {
  color: var(--api-report-text-subtle);
}

.config-card,
.config-row,
.config-inline-value {
  background: var(--api-report-inline-bg);
  border-color: var(--api-report-inline-border);
}

.config-card:hover .config-row {
  background: var(--api-report-card-hover);
}

pre {
  scrollbar-width: none;
  -ms-overflow-style: none;
  &::-webkit-scrollbar {
    display: none;
  }
}

.config-item {
  @apply transition-all duration-200;

  &:hover {
    .config-card {
      background: var(--api-report-card-hover);
      border-color: rgba(var(--theme-accent-rgb), 0.12);
    }
  }
}

/* 自定义滚动条样式 */
.overflow-y-auto {
  scrollbar-width: thin;
  scrollbar-color: rgba(107, 114, 128, 0.3) transparent;
  
  &::-webkit-scrollbar {
    width: 4px;
  }
  
  &::-webkit-scrollbar-track {
    background: transparent;
  }
  
  &::-webkit-scrollbar-thumb {
    background-color: rgba(107, 114, 128, 0.3);
    border-radius: 4px;
  }
}

/* 自定义抽屉组件样式 */
:deep(.config-info-drawer) {
  .arco-drawer-container {
    @apply !bg-transparent;
  }

  .arco-drawer-header {
    background: #f8fafc !important;
    border-bottom: 1px solid rgba(148, 163, 184, 0.18) !important;
  }

  .arco-drawer-body {
    background: #f8fafc !important;
  }

  .arco-drawer-content {
    background: #f8fafc !important;
  }

  .arco-drawer-wrapper {
    background: #f8fafc !important;
  }
}

/* 全局样式覆盖 - 确保抽屉组件样式具有最高优先级 */
:global(.arco-drawer-container) {
  background-color: transparent !important;
}

:global(.config-info-drawer .arco-drawer-header),
:global(.config-info-drawer .arco-drawer-body),
:global(.config-info-drawer .arco-drawer-content),
:global(.config-info-drawer .arco-drawer-wrapper) {
  background-color: #f8fafc !important;
}

:global(body.api-testing-theme .config-info-drawer .arco-drawer-header) {
  background-color: rgb(31, 41, 55) !important;
  border-bottom: 1px solid rgba(75, 85, 99, 0.4) !important;
}

:global(body.api-testing-theme .config-info-drawer .arco-drawer-body),
:global(body.api-testing-theme .config-info-drawer .arco-drawer-content),
:global(body.api-testing-theme .config-info-drawer .arco-drawer-wrapper) {
  background-color: rgb(31, 41, 55) !important;
}
</style> 