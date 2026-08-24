<template>
  <!-- 执行步骤主容器 - 包含所有测试步骤的垂直列表 -->
  <div class="execution-steps-shell rounded-lg border">
    <!-- 标题栏 -->
    <div class="steps-header px-4 py-3 border-b">
      <span class="steps-title text-base font-medium">执行步骤</span>
    </div>
    <!-- 步骤列表容器 -->
    <div class="p-4">
      <!-- Arco Design垂直步骤组件 - 显示所有测试步骤 -->
      <a-steps :current="report?.details?.length" direction="vertical">
        <!-- 单个测试步骤容器 - 循环渲染每个测试步骤 -->
        <a-step
          v-for="(step, index) in report?.details"
          :key="step.id"
          :title="step.step_name"
          :status="getStepStatus(step.success)"
          class="step-item"
        >
          <!-- 步骤描述插槽 - 包含步骤的详细信息 -->
          <template #description>
            <!-- 步骤状态概览行 - 显示成功/失败状态、请求方法、状态码等 -->
            <div class="flex items-start justify-between mt-2" :class="{'last-step-status': index === (report?.details?.length ?? 0) - 1}">
              <!-- 左侧信息组 - 状态标签、请求方法、状态码、响应时间 -->
              <div class="flex items-center gap-4">
                <!-- 状态标签 -->
                <a-tag size="small" :color="step.success ? 'green' : 'red'">
                  {{ step.success ? '成功' : '失败' }}
                </a-tag>

                <!-- 请求方法和状态码 -->
                <div v-if="step.request && step.response" class="flex items-center gap-2">
                  <span class="text-blue-400 text-sm">{{ step.request.method }}</span>
                  <a-tag :color="getResponseStatusColor(step.response.status_code)" size="small">
                    {{ step.response.status_code }}
                  </a-tag>
                </div>

                <!-- 响应时间 -->
                <div v-if="step.response" class="flex items-center gap-2">
                  <icon-clock-circle class="text-gray-400" />
                  <span class="text-gray-400 text-sm">{{ step.response.response_time_ms }}ms</span>
                </div>
              </div>

              <!-- 右侧验证器统计 - 显示通过的验证器数量 -->
              <div v-if="step.validators?.validate_extractor?.length" class="flex items-center gap-2 min-w-[60px] mr-2 pr-8 justify-end">
                <icon-check-circle class="text-yellow-400 flex-shrink-0" />
                <span class="text-gray-400 text-sm whitespace-nowrap">
                  {{ getValidatorStats(step.validators.validate_extractor).pass }}/{{ step.validators.validate_extractor.length }}
                </span>
              </div>
            </div>

            <!-- 详细信息网格 - 包含请求、响应、断言和变量等四个卡片，使用4列网格布局 -->
            <div class="mt-4 grid grid-cols-4 gap-4 w-[calc(100%-72px)]">
              <!-- 请求信息卡片 (网格第1列) - 显示HTTP请求详情 -->
              <div v-if="step.request" class="step-info-card">
                <!-- 卡片标题栏 -->
                <div class="bg-blue-500/5 px-3 py-1.5 border-b border-gray-700/30">
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                      <span class="text-blue-400 text-sm">请求信息</span>
                      <a-tag size="small">{{ step.request.method }}</a-tag>
                    </div>
                    <div class="flex items-center gap-2">
                      <a-button type="text" size="mini" @click="copyToClipboard(JSON.stringify(step.request, null, 2))">
                        <template #icon><icon-copy class="text-gray-400 hover:text-blue-400" /></template>
                      </a-button>
                      <a-button type="text" size="mini" @click="toggleDrawer(step.id, 'request')">
                        <template #icon><icon-expand class="text-gray-400 hover:text-blue-400" /></template>
                      </a-button>
                    </div>
                  </div>
                </div>
                <div class="p-2">
                  <!-- 请求信息容器 - 用于显示请求的JSON数据 -->
                  <pre class="code-pre p-2 rounded text-xs font-mono overflow-x-auto max-h-[120px] whitespace-pre-wrap break-all card-content">{{ JSON.stringify(step.request, null, 2) }}</pre>
                </div>
              </div>

              <!-- 响应信息卡片 (网格第2列) - 显示HTTP响应详情 -->
              <div v-if="step.response" class="step-info-card">
                <!-- 卡片标题栏 -->
                <div class="bg-purple-500/5 px-3 py-1.5 border-b border-gray-700/30">
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                      <span class="text-purple-400 text-sm">响应信息</span>
                      <a-tag size="small" :color="getResponseStatusColor(step.response.status_code)">
                        {{ step.response.status_code }}
                      </a-tag>
                    </div>
                    <div class="flex items-center gap-2">
                      <a-button type="text" size="mini" @click="copyToClipboard(JSON.stringify(step.response, null, 2))">
                        <template #icon><icon-copy class="text-gray-400 hover:text-purple-400" /></template>
                      </a-button>
                      <a-button type="text" size="mini" @click="toggleDrawer(step.id, 'response')">
                        <template #icon><icon-expand class="text-gray-400 hover:text-purple-400" /></template>
                      </a-button>
                    </div>
                  </div>
                </div>
                <div class="p-2">
                  <!-- 响应信息容器 - 用于显示响应的JSON数据 -->
                  <pre class="code-pre p-2 rounded text-xs font-mono overflow-x-auto max-h-[120px] whitespace-pre-wrap break-all card-content">{{ JSON.stringify(step.response, null, 2) }}</pre>
                </div>
              </div>

              <!-- 断言结果卡片 (网格第3列) - 显示验证结果 -->
              <div v-if="step.validators?.validate_extractor?.length" class="step-info-card">
                <!-- 卡片标题栏 -->
                <div class="bg-yellow-500/5 px-3 py-1.5 border-b border-gray-700/30">
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                      <span class="text-yellow-400 text-sm">断言结果</span>
                    </div>
                    <div class="flex items-center gap-2">
                      <a-button type="text" size="mini" @click="copyToClipboard(JSON.stringify(step.validators.validate_extractor, null, 2))">
                        <template #icon><icon-copy class="text-gray-400 hover:text-yellow-400" /></template>
                      </a-button>
                      <a-button type="text" size="mini" @click="toggleDrawer(step.id, 'validators')">
                        <template #icon><icon-expand class="text-gray-400 hover:text-yellow-400" /></template>
                      </a-button>
                    </div>
                  </div>
                </div>
                <div class="p-2 max-h-[120px] overflow-y-auto card-content">
                  <!-- 断言结果容器 - 用于显示验证器的结果列表 -->
                  <div class="space-y-2">
                    <div 
                      v-for="(validator, vIndex) in step.validators.validate_extractor" 
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
              <div v-if="step.extracted_variables && Object.keys(step.extracted_variables).length" class="step-info-card">
                <!-- 卡片标题栏 -->
                <div class="bg-green-500/5 px-3 py-1.5 border-b border-gray-700/30">
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                      <span class="text-green-400 text-sm">提取变量</span>
                      <a-tag size="small" color="green">{{ Object.keys(step.extracted_variables).length }}个</a-tag>
                    </div>
                    <div class="flex items-center gap-2">
                      <a-button type="text" size="mini" @click="copyToClipboard(JSON.stringify(step.extracted_variables, null, 2))">
                        <template #icon><icon-copy class="text-gray-400 hover:text-green-400" /></template>
                      </a-button>
                      <a-button type="text" size="mini" @click="toggleDrawer(step.id, 'variables')">
                        <template #icon><icon-expand class="text-gray-400 hover:text-green-400" /></template>
                      </a-button>
                    </div>
                  </div>
                </div>
                <div class="p-2">
                  <!-- 提取变量容器 - 用于显示从响应中提取的变量 -->
                  <div class="space-y-2 max-h-[120px] overflow-y-auto card-content">
                    <div v-for="(value, key) in step.extracted_variables" :key="key" class="variable-item rounded p-2 transition-all duration-200">
                      <div class="flex items-center justify-between">
                        <span class="text-gray-300 text-xs">{{ key }}</span>
                        <a-button type="text" size="mini" @click="copyToClipboard(value)">
                          <template #icon><icon-copy class="text-gray-400 hover:text-green-400" /></template>
                        </a-button>
                      </div>
                      <div class="variable-inline-value mt-1 rounded px-2 py-1">
                        <span class="text-green-400 text-xs font-mono break-all">{{ value }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </a-step>
      </a-steps>
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
          <div v-for="(value, key) in currentDrawerData" :key="key" class="variable-item rounded-lg p-3 transition-all duration-200">
            <div class="flex items-start justify-between">
              <div class="flex items-center gap-2">
                <icon-code class="text-green-400" />
                <span class="text-gray-300 font-medium">{{ key }}</span>
              </div>
              <a-button type="text" size="mini" @click="copyToClipboard(value)">
                <template #icon><icon-copy class="text-gray-400 hover:text-green-400" /></template>
              </a-button>
            </div>
            <div class="drawer-inline-value mt-2 rounded-lg p-3">
              <div class="text-green-400 font-mono break-all">{{ value }}</div>
            </div>
          </div>
        </div>
      </template>
      <template v-else>
        <pre class="drawer-pre rounded-lg p-4 text-sm font-mono whitespace-pre-wrap break-all">{{ JSON.stringify(currentDrawerData, null, 2) }}</pre>
      </template>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import { 
  IconCheckCircleFill, 
  IconCloseCircleFill, 
  IconUp, 
  IconDown,
  IconClockCircle,
  IconCheckCircle,
  IconCopy,
  IconExpand,
  IconCode
} from '@arco-design/web-vue/es/icon'
import { formatDuration } from '@/utils/formatters'
import type { TestReportResponse } from './TestReportDetail.vue'

// 组件属性定义 - 接收测试报告数据
const props = defineProps<{
  report: TestReportResponse | null
}>()

// 跟踪展开的步骤ID列表
const expandedSteps = ref<number[]>([])

/**
 * 切换步骤的展开/折叠状态
 * @param index 步骤索引
 */
const toggleStep = (index: number) => {
  const idx = expandedSteps.value.indexOf(index)
  if (idx > -1) {
    expandedSteps.value.splice(idx, 1)
  } else {
    expandedSteps.value.push(index)
  }
}

/**
 * 根据步骤成功状态获取Arco Design步骤组件的状态
 * @param success 步骤是否成功
 * @returns Arco Design步骤状态
 */
const getStepStatus = (success: boolean) => {
  return success ? 'finish' : 'error'
}

/**
 * 根据HTTP状态码获取对应的颜色
 * @param status HTTP状态码
 * @returns 颜色名称
 */
const getResponseStatusColor = (status: number) => {
  if (status >= 500) return 'red'
  if (status >= 400) return 'orange'
  if (status >= 300) return 'blue'
  return 'green'
}

/**
 * 计算验证器的统计信息
 * @param validators 验证器数组
 * @returns 包含通过数量的对象
 */
const getValidatorStats = (validators: Array<{ check_result: 'pass' | 'fail' }>) => {
  const pass = validators.filter(v => v.check_result === 'pass').length
  return { pass }
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

// 抽屉组件状态控制
const drawerVisible = ref(false)
const currentDrawerData = ref<any>(null)
const currentDrawerType = ref<'request' | 'response' | 'validators' | 'variables' | null>(null)

/**
 * 切换抽屉的显示状态，并设置要显示的数据
 * @param stepId 步骤ID
 * @param type 数据类型（请求、响应、验证器或变量）
 */
const toggleDrawer = (stepId: number, type: 'request' | 'response' | 'validators' | 'variables') => {
  const step = props.report?.details?.find((s: { id: number }) => s.id === stepId)
  if (step) {
    if (type === 'request') {
      currentDrawerData.value = step.request
    } else if (type === 'response') {
      currentDrawerData.value = step.response
    } else if (type === 'validators') {
      currentDrawerData.value = step.validators?.validate_extractor || []
    } else if (type === 'variables') {
      currentDrawerData.value = step.extracted_variables || {}
    }
    currentDrawerType.value = type
    drawerVisible.value = true
  }
}
</script>

<style scoped>
@reference "tailwindcss";
.execution-steps-shell {
  background: color-mix(in srgb, var(--api-report-card-bg) 88%, var(--theme-page-bg) 12%);
  border-color: var(--api-report-shell-border);
  backdrop-filter: blur(10px);
}

.steps-header {
  border-color: var(--api-report-shell-border);
}

.steps-title {
  color: var(--api-report-text);
}

.execution-steps-shell .text-gray-300 {
  color: var(--api-report-text-muted);
}

.execution-steps-shell .text-gray-400,
.execution-steps-shell .text-gray-500 {
  color: var(--api-report-text-subtle);
}

.code-pre,
.drawer-pre {
  background: var(--api-report-inline-bg);
  border: 1px solid var(--api-report-inline-border);
  color: var(--api-report-text-muted);
}

/* 覆盖Arco Design步骤组件的默认样式 */
:deep(.arco-steps) {
  .arco-step-content {
    @apply !min-h-0;
  }

  .arco-step-title {
    color: var(--api-report-text) !important;
    @apply !text-base !font-medium;
  }

  .arco-step-description {
    color: var(--api-report-text-subtle) !important;
    @apply !mt-2;
  }
}

/* 覆盖Arco Design折叠面板的默认样式 */
:deep(.arco-collapse) {
  @apply !bg-transparent !border-none;

  .arco-collapse-item {
    @apply !border-none;

    .arco-collapse-item-header {
      @apply !bg-transparent !text-gray-400 !border-none !p-0;

      &:hover {
        @apply !text-gray-300;
      }
    }

    .arco-collapse-item-content {
      @apply !bg-transparent !text-gray-300 !p-0 !mt-2;
    }
  }
}

/* 卡片内容区域的滚动样式 - 隐藏滚动条但保留滚动功能 */
.card-content {
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE and Edge */
  &::-webkit-scrollbar {
    display: none; /* Chrome, Safari, Opera */
  }
}

/* 步骤状态栏样式 - 显示步骤的基本状态信息 */
.step-status-bar {
  @apply flex items-center justify-between bg-gray-800/30 rounded-lg px-3 py-2 border border-gray-700/30 transition-all duration-200;

  &:hover {
    @apply bg-gray-800/50 border-gray-600/50;
  }
}

/* 步骤信息卡片样式 - 用于请求、响应、断言和变量等四个卡片 */
.step-info-card {
  @apply rounded-lg overflow-hidden transition-all duration-200;
  background: var(--api-report-inline-bg);
  border: 1px solid var(--api-report-inline-border);

  &:hover {
    background: var(--api-report-card-hover);
    border-color: rgba(var(--theme-accent-rgb), 0.12);
  }
}

/* 验证器项目样式 - 断言结果中的每个验证项 */
.validator-item {
  @apply rounded-lg p-3 transition-all duration-200;
  background: var(--api-report-inline-bg);
  border: 1px solid var(--api-report-inline-border);

  &:hover {
    background: var(--api-report-card-hover);
    border-color: rgba(var(--theme-accent-rgb), 0.12);
  }
}

/* 验证器值样式 - 显示期望值和实际值的容器 */
.validator-value {
  @apply flex items-center gap-2 rounded px-2 py-1;
  background: var(--api-report-inline-bg);
  border: 1px solid var(--api-report-inline-border);
}

.variable-item {
  background: var(--api-report-inline-bg);
  border: 1px solid var(--api-report-inline-border);
}

.variable-item:hover {
  background: var(--api-report-card-hover);
  border-color: rgba(var(--theme-accent-rgb), 0.12);
}

.variable-inline-value,
.drawer-inline-value {
  background: color-mix(in srgb, var(--api-report-inline-bg) 82%, var(--theme-page-bg) 18%);
  border: 1px solid var(--api-report-inline-border);
}

/* 最后一个步骤的状态概览行样式 */
.last-step-status {
  /* 使用负边距抵消Arco Design步骤组件对最后一个步骤的特殊处理 */
  @apply pr-8;
}

/* 自定义抽屉组件样式 - 用于显示完整的请求或响应详情 */
:deep(.custom-drawer) {
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

:global(.arco-drawer-header),
:global(.arco-drawer-body),
:global(.arco-drawer-content),
:global(.arco-drawer-wrapper) {
  background-color: #f8fafc !important;
}

:global(body.api-testing-theme .custom-drawer .arco-drawer-header),
:global(body.api-testing-theme .arco-drawer-header) {
  background-color: rgb(31, 41, 55) !important;
  border-bottom: 1px solid rgba(75, 85, 99, 0.4) !important;
}

:global(body.api-testing-theme .custom-drawer .arco-drawer-body),
:global(body.api-testing-theme .custom-drawer .arco-drawer-content),
:global(body.api-testing-theme .custom-drawer .arco-drawer-wrapper),
:global(body.api-testing-theme .arco-drawer-body),
:global(body.api-testing-theme .arco-drawer-content),
:global(body.api-testing-theme .arco-drawer-wrapper) {
  background-color: rgb(31, 41, 55) !important;
}
</style> 