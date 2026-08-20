<script setup lang="ts">
import { ref, computed } from 'vue'
import { Message, Drawer } from '@arco-design/web-vue'
import { useThemeStore } from '@/store/themeStore'
import { IconCopy, IconExpand, IconCheckCircleFill, IconCloseCircleFill } from '@arco-design/web-vue/es/icon'

interface ValidateExtractor {
  check: string
  expect: string
  message: string
  comparator: string
  check_value: string
  check_result: string
  expect_value: string
}

interface StepDetail {
  id: number
  step_name: string
  success: boolean
  elapsed: number
  request: {
    url: string
    method: string
    headers: Record<string, string>
    body?: any
  }
  response: {
    status_code: number
    headers: Record<string, string>
    body: any
    response_time_ms: number
  }
  validators: {
    success: boolean
    validate_extractor: ValidateExtractor[]
  }
  extracted_variables: Record<string, any>
  attachment: string
}

const props = defineProps<{
  detail: StepDetail
}>()
const themeStore = useThemeStore()
const isDarkTheme = computed(() => themeStore.isBlack)

// 格式化 JSON
const formatJson = (json: any) => {
  try {
    return JSON.stringify(json, null, 2)
  } catch (error) {
    return json
  }
}

// 格式化持续时间
const formatDuration = (seconds: number) => {
  if (seconds === undefined || seconds === null || isNaN(seconds)) return '-'
  try {
    return `${Number(seconds).toFixed(2)}秒`
  } catch (error) {
    console.error('持续时间格式化错误:', error)
    return '-'
  }
}

// 根据HTTP状态码获取对应的颜色
const getResponseStatusColor = (status: number) => {
  if (status >= 500) return 'red'
  if (status >= 400) return 'orange'
  if (status >= 300) return 'blue'
  return 'green'
}

// 抽屉组件状态控制
const drawerVisible = ref(false)
const currentDrawerData = ref<any>(null)
const currentDrawerType = ref<'request' | 'response' | 'validators' | 'variables' | null>(null)

/**
 * 切换抽屉的显示状态，并设置要显示的数据
 * @param type 数据类型（请求、响应、验证器或变量）
 */
const toggleDrawer = (type: 'request' | 'response' | 'validators' | 'variables') => {
  if (type === 'request') {
    currentDrawerData.value = props.detail.request
  } else if (type === 'response') {
    currentDrawerData.value = props.detail.response
  } else if (type === 'validators') {
    currentDrawerData.value = props.detail.validators?.validate_extractor || []
  } else if (type === 'variables') {
    currentDrawerData.value = props.detail.extracted_variables || {}
  }
  currentDrawerType.value = type
  drawerVisible.value = true
}

/**
 * 将文本复制到剪贴板
 * @param text 要复制的文本
 */
const copyToClipboard = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text)
    Message.success('复制成功')
  } catch (err) {
    Message.error('复制失败')
  }
}

// 计算验证器的统计信息
const getValidatorStats = (validators: Array<{ check_result: string }>) => {
  const pass = validators.filter(v => v.check_result === 'pass').length
  return { pass, total: validators.length }
}
</script>

<template>
  <div class="api-detail-card-shell mt-4" :class="isDarkTheme ? 'api-detail-card-shell--dark' : 'api-detail-card-shell--light'">
    <!-- 详细信息网格 - 包含请求、响应、断言和变量等四个卡片，使用4列网格布局 -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <!-- 请求信息卡片 (网格第1列) - 显示HTTP请求详情 -->
      <div v-if="detail.request" class="step-info-card">
        <!-- 卡片标题栏 -->
        <div class="section-header section-header--request px-3 py-1.5 border-b">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="text-blue-400 text-sm">请求信息</span>
              <a-tag size="small">{{ detail.request.method }}</a-tag>
            </div>
            <div class="flex items-center gap-2">
              <a-button type="text" size="mini" @click="copyToClipboard(JSON.stringify(detail.request, null, 2))">
                <template #icon><icon-copy class="text-gray-400 hover:text-blue-400" /></template>
              </a-button>
              <a-button type="text" size="mini" @click="toggleDrawer('request')">
                <template #icon><icon-expand class="text-gray-400 hover:text-blue-400" /></template>
              </a-button>
            </div>
          </div>
        </div>
        <div class="p-2">
          <!-- 请求信息容器 - 用于显示请求的JSON数据 -->
          <pre class="data-preview p-2 rounded text-xs font-mono overflow-x-auto max-h-[120px] whitespace-pre-wrap break-all card-content">{{ formatJson(detail.request) }}</pre>
        </div>
      </div>

      <!-- 响应信息卡片 (网格第2列) - 显示HTTP响应详情 -->
      <div v-if="detail.response" class="step-info-card">
        <!-- 卡片标题栏 -->
        <div class="section-header section-header--response px-3 py-1.5 border-b">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="text-purple-400 text-sm">响应信息</span>
              <a-tag size="small" :color="getResponseStatusColor(detail.response.status_code)">
                {{ detail.response.status_code }}
              </a-tag>
            </div>
            <div class="flex items-center gap-2">
              <a-button type="text" size="mini" @click="copyToClipboard(JSON.stringify(detail.response, null, 2))">
                <template #icon><icon-copy class="text-gray-400 hover:text-purple-400" /></template>
              </a-button>
              <a-button type="text" size="mini" @click="toggleDrawer('response')">
                <template #icon><icon-expand class="text-gray-400 hover:text-purple-400" /></template>
              </a-button>
            </div>
          </div>
        </div>
        <div class="p-2">
          <!-- 响应信息容器 - 用于显示响应的JSON数据 -->
          <pre class="data-preview p-2 rounded text-xs font-mono overflow-x-auto max-h-[120px] whitespace-pre-wrap break-all card-content">{{ formatJson(detail.response) }}</pre>
        </div>
      </div>

      <!-- 断言结果卡片 (网格第3列) - 显示验证结果 -->
      <div v-if="detail.validators?.validate_extractor?.length" class="step-info-card">
        <!-- 卡片标题栏 -->
        <div class="section-header section-header--validators px-3 py-1.5 border-b">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="text-yellow-400 text-sm">断言结果</span>
              <a-tag size="small" :color="getValidatorStats(detail.validators.validate_extractor).pass === getValidatorStats(detail.validators.validate_extractor).total ? 'green' : 'red'">
                {{ getValidatorStats(detail.validators.validate_extractor).pass }}/{{ getValidatorStats(detail.validators.validate_extractor).total }}
              </a-tag>
            </div>
            <div class="flex items-center gap-2">
              <a-button type="text" size="mini" @click="copyToClipboard(JSON.stringify(detail.validators.validate_extractor, null, 2))">
                <template #icon><icon-copy class="text-gray-400 hover:text-yellow-400" /></template>
              </a-button>
              <a-button type="text" size="mini" @click="toggleDrawer('validators')">
                <template #icon><icon-expand class="text-gray-400 hover:text-yellow-400" /></template>
              </a-button>
            </div>
          </div>
        </div>
        <div class="p-2 max-h-[120px] overflow-y-auto card-content">
          <!-- 断言结果容器 - 用于显示验证器的结果列表 -->
          <div class="space-y-2">
            <div 
              v-for="(validator, vIndex) in detail.validators.validate_extractor" 
              :key="vIndex"
              class="validator-item p-2"
            >
              <div class="flex items-start gap-1.5">
                <icon-check-circle-fill 
                  v-if="validator.check_result === 'pass'"
                  class="text-green-500 mt-0.5 text-sm"
                />
                <icon-close-circle-fill
                  v-else
                  class="text-red-500 mt-0.5 text-sm"
                />
                <div class="flex-1">
                  <div class="flex items-center gap-1">
                    <span class="text-gray-300 text-xs">{{ validator.check }}</span>
                    <span class="text-gray-500 text-xs">({{ validator.comparator }})</span>
                  </div>
                  <div class="mt-1 space-y-1">
                    <div class="validator-value">
                      <span class="text-gray-400 text-xs">期望值:</span>
                      <span class="text-blue-400 text-xs font-mono">{{ validator.expect_value }}</span>
                    </div>
                    <div class="validator-value">
                      <span class="text-gray-400 text-xs">实际值:</span>
                      <span class="text-purple-400 text-xs font-mono">{{ validator.check_value }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 提取变量卡片 (网格第4列) - 显示从响应中提取的变量 -->
      <div v-if="detail.extracted_variables && Object.keys(detail.extracted_variables).length" class="step-info-card">
        <!-- 卡片标题栏 -->
        <div class="section-header section-header--variables px-3 py-1.5 border-b">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="text-green-400 text-sm">提取变量</span>
              <a-tag size="small" color="green">{{ Object.keys(detail.extracted_variables).length }}个</a-tag>
            </div>
            <div class="flex items-center gap-2">
              <a-button type="text" size="mini" @click="copyToClipboard(JSON.stringify(detail.extracted_variables, null, 2))">
                <template #icon><icon-copy class="text-gray-400 hover:text-green-400" /></template>
              </a-button>
              <a-button type="text" size="mini" @click="toggleDrawer('variables')">
                <template #icon><icon-expand class="text-gray-400 hover:text-green-400" /></template>
              </a-button>
            </div>
          </div>
        </div>
        <div class="p-2">
          <!-- 提取变量容器 - 用于显示从响应中提取的变量 -->
          <div class="space-y-2 max-h-[120px] overflow-y-auto card-content">
            <div v-for="(value, key) in detail.extracted_variables" :key="key" class="variable-item rounded p-2 transition-all duration-200">
              <div class="flex items-center justify-between">
                <span class="text-gray-300 text-xs">{{ key }}</span>
                <a-button type="text" size="mini" @click="copyToClipboard(value)">
                  <template #icon><icon-copy class="text-gray-400 hover:text-green-400" /></template>
                </a-button>
              </div>
              <div class="variable-value mt-1 rounded px-2 py-1">
                <span class="text-green-400 text-xs font-mono break-all">{{ value }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 抽屉组件 - 用于显示完整的请求或响应详情 -->
    <a-drawer
      :visible="drawerVisible"
      :width="800"
      @cancel="drawerVisible = false"
      :title="currentDrawerType === 'request' ? '请求详情' : currentDrawerType === 'response' ? '响应详情' : currentDrawerType === 'validators' ? '验证器详情' : '变量详情'"
      :footer="false"
      class="custom-drawer"
      :mask="true"
      :mask-style="{ backgroundColor: 'transparent' }"
      :mask-closable="true"
      @close="drawerVisible = false"
    >
      <div class="p-6">
        <!-- 根据不同的抽屉类型显示不同的内容 -->
        <template v-if="currentDrawerType === 'validators'">
          <div class="space-y-3">
            <div 
              v-for="(validator, vIndex) in currentDrawerData" 
              :key="vIndex"
              class="validator-item p-3"
            >
              <div class="flex items-start gap-2">
                <icon-check-circle-fill 
                  v-if="validator.check_result === 'pass'"
                  class="text-green-500 mt-0.5"
                />
                <icon-close-circle-fill
                  v-else
                  class="text-red-500 mt-0.5"
                />
                <div class="flex-1">
                  <div class="flex items-center gap-1">
                    <span class="text-gray-300">{{ validator.check }}</span>
                    <span class="text-gray-500">({{ validator.comparator }})</span>
                  </div>
                  <div class="mt-2 space-y-2">
                    <div class="validator-value">
                      <span class="text-gray-400">期望值:</span>
                      <span class="text-blue-400 font-mono">{{ validator.expect_value }}</span>
                    </div>
                    <div class="validator-value">
                      <span class="text-gray-400">实际值:</span>
                      <span class="text-purple-400 font-mono">{{ validator.check_value }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>
        <template v-else-if="currentDrawerType === 'variables'">
          <div class="space-y-3">
            <div v-for="(value, key) in currentDrawerData" :key="key" class="drawer-variable-item rounded-lg p-3 transition-all duration-200">
              <div class="flex items-start justify-between">
                <div class="flex items-center gap-2">
                  <span class="text-gray-300 font-medium">{{ key }}</span>
                </div>
                <a-button type="text" size="mini" @click="copyToClipboard(value)">
                  <template #icon><icon-copy class="text-gray-400 hover:text-green-400" /></template>
                </a-button>
              </div>
              <div class="drawer-variable-value mt-2 rounded-lg p-3">
                <div class="text-green-400 font-mono break-all">{{ value }}</div>
              </div>
            </div>
          </div>
        </template>
        <template v-else>
          <pre class="drawer-json-preview rounded-lg p-4 text-sm font-mono whitespace-pre-wrap break-all">{{ JSON.stringify(currentDrawerData, null, 2) }}</pre>
        </template>
      </div>
    </a-drawer>
  </div>
</template>

<style scoped>
@reference "tailwindcss";
.api-detail-card-shell {
  --ad-card-bg: rgba(255, 255, 255, 0.82);
  --ad-card-border: rgba(148, 163, 184, 0.16);
  --ad-card-hover: rgba(148, 163, 184, 0.08);
  --ad-code-bg: rgba(15, 23, 42, 0.04);
  --ad-code-border: rgba(148, 163, 184, 0.16);
  --ad-scroll-track: rgba(226, 232, 240, 0.8);
  --ad-scroll-thumb: rgba(148, 163, 184, 0.5);
  --ad-scroll-thumb-hover: rgba(100, 116, 139, 0.55);
  --ad-divider: rgba(148, 163, 184, 0.14);
}

.api-detail-card-shell--dark {
  --ad-card-bg: rgba(15, 23, 42, 0.34);
  --ad-card-border: rgba(75, 85, 99, 0.35);
  --ad-card-hover: rgba(30, 41, 59, 0.5);
  --ad-code-bg: rgba(15, 23, 42, 0.5);
  --ad-code-border: rgba(75, 85, 99, 0.4);
  --ad-scroll-track: rgba(31, 41, 55, 0.5);
  --ad-scroll-thumb: rgba(75, 85, 99, 0.5);
  --ad-scroll-thumb-hover: rgba(107, 114, 128, 0.55);
  --ad-divider: rgba(75, 85, 99, 0.4);
}

.step-info-card {
  background: var(--ad-card-bg);
  border: 1px solid var(--ad-card-border);
  @apply rounded-lg overflow-hidden;
}

.validator-item {
  background: var(--ad-card-bg);
  border: 1px solid var(--ad-card-border);
  @apply rounded transition-all duration-200;

  &:hover {
    background: var(--ad-card-hover);
  }
}

.validator-value {
  @apply flex items-center gap-2;
}

.section-header {
  border-color: var(--ad-divider) !important;
}

.section-header--request {
  background: rgba(59, 130, 246, 0.08);
}

.section-header--response {
  background: rgba(168, 85, 247, 0.08);
}

.section-header--validators {
  background: rgba(245, 158, 11, 0.08);
}

.section-header--variables {
  background: rgba(34, 197, 94, 0.08);
}

.data-preview,
.variable-value,
.drawer-variable-value,
.drawer-json-preview {
  background: var(--ad-code-bg);
  border: 1px solid var(--ad-code-border);
}

.variable-item,
.drawer-variable-item {
  background: var(--ad-card-bg);
  border: 1px solid var(--ad-card-border);

  &:hover {
    background: var(--ad-card-hover);
  }
}

.card-content {
  scrollbar-width: thin;
  scrollbar-color: var(--ad-scroll-thumb) var(--ad-scroll-track);
}

.card-content::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.card-content::-webkit-scrollbar-track {
  background: var(--ad-scroll-track);
  @apply rounded;
}

.card-content::-webkit-scrollbar-thumb {
  background: var(--ad-scroll-thumb);
  @apply rounded;
}

.card-content::-webkit-scrollbar-thumb:hover {
  background: var(--ad-scroll-thumb-hover);
}

:deep(.text-gray-200) {
  color: var(--theme-text) !important;
}

:deep(.text-gray-300) {
  color: var(--theme-text-secondary) !important;
}

:deep(.text-gray-400) {
  color: var(--theme-text-tertiary) !important;
}

:deep(.text-gray-500) {
  color: color-mix(in srgb, var(--theme-text-tertiary) 88%, transparent 12%) !important;
}

:global(.custom-drawer .arco-drawer-header) {
  background: #ffffff !important;
  border-bottom: 1px solid rgba(148, 163, 184, 0.16) !important;
}

:global(.custom-drawer .arco-drawer-title) {
  color: #0f172a !important;
}

:global(.custom-drawer .arco-drawer-body) {
  background: #ffffff !important;
  padding: 0 !important;
}

:global(.custom-drawer .arco-drawer-mask) {
  background: rgba(15, 23, 42, 0.2) !important;
  backdrop-filter: blur(4px);
}

:global(body.api-testing-theme .custom-drawer .arco-drawer-header) {
  background: rgb(31, 41, 55) !important;
  border-bottom-color: rgba(75, 85, 99, 0.4) !important;
}

:global(body.api-testing-theme .custom-drawer .arco-drawer-title) {
  color: rgb(226, 232, 240) !important;
}

:global(body.api-testing-theme .custom-drawer .arco-drawer-body) {
  background: rgb(31, 41, 55) !important;
}

:global(body.api-testing-theme .custom-drawer .arco-drawer-mask) {
  background: rgba(15, 23, 42, 0.45) !important;
}
</style> 