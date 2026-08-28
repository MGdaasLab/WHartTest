<script setup lang="ts">
import { ref, onMounted, h, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message, Tag as ATag, Collapse as ACollapse, CollapseItem as ACollapseItem, 
         Progress as AProgress, Tooltip as ATooltip } from '@arco-design/web-vue'
import { useThemeStore } from '@/store/themeStore'
import { IconExclamationCircleFill } from '@arco-design/web-vue/es/icon'
import { getTestTaskExecutionCaseResults, getTestTaskExecution } from '../../services/testTaskService'
import ApiDetailCard from './ApiDetailCard.vue'

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

interface TestReport {
  id: number
  name: string
  status: string
  success_count: number
  fail_count: number
  error_count: number
  duration: number
  start_time: string
  summary: {
    success: boolean
    step_results: any[]
  }
  details: StepDetail[]
  success_rate: string
  environment_info: {
    name: string
    base_url: string
    project: {
      name: string
    }
  }
  executed_by_info: {
    username: string
  }
}

interface CaseResult {
  id: number
  case_type: 'scenario' | 'interface'
  case_id: number
  testcase: number | null
  interface_case?: number | null
  testcase_name: string
  status: string
  start_time: string
  end_time: string
  duration: number
  error_message: string
  report: TestReport
}

const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()
const loading = ref(false)
const caseResults = ref<CaseResult[]>([])
const expandedStepIds = ref<Record<number, number[]>>({})
const isDarkTheme = computed(() => themeStore.isBlack)

// 获取用例执行结果
const fetchCaseResults = async () => {
  const id = route.params.id
  if (!id) {
    Message.warning('未指定执行记录ID')
    return
  }

  loading.value = true
  try {
    const { data } = await getTestTaskExecutionCaseResults(Number(id))
    if (data) {
      caseResults.value = data as any
    }
  } catch (error) {
    console.error('获取用例执行结果失败', error)
    Message.error(error instanceof Error ? error.message : '获取用例执行结果失败')
  } finally {
    loading.value = false
  }
}

// 返回历史记录页面
const goBack = async () => {
  try {
    const executionId = Number(route.params.id);
    const response = await getTestTaskExecution(executionId);
    if (response?.status === 'success' && response.data?.task_suite) {
      router.push({ name: 'ApiTestTaskDetail', params: { id: response.data.task_suite } });
    } else {
      router.push({ path: '/api-testing', query: { tab: 'testtasks' } });
    }
  } catch {
    router.push({ path: '/api-testing', query: { tab: 'testtasks' } });
  }
}

// 格式化日期
const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  try {
    const date = new Date(dateStr)
    // 检查日期是否有效
    if (isNaN(date.getTime())) {
      return '-'
    }
    return date.toLocaleString('zh-CN')
  } catch (error) {
    console.error('日期格式化错误:', error)
    return '-'
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

const getCaseTypeText = (caseType: string) => {
  return caseType === 'interface' ? '接口用例' : '场景用例'
}

const getCaseStatusText = (status: string) => {
  const statusMap: Record<string, string> = {
    success: '成功',
    fail: '失败',
    failure: '失败',
    error: '错误',
    skipped: '跳过',
    pending: '等待中',
    running: '执行中'
  }
  return statusMap[status] || '未知'
}

const getCaseStatusColor = (status: string) => {
  const colorMap: Record<string, string> = {
    success: 'green',
    fail: 'orange',
    failure: 'orange',
    error: 'red',
    skipped: 'gray',
    pending: 'blue',
    running: 'arcoblue'
  }
  return colorMap[status] || 'gray'
}

// 展开行渲染函数
const expandedRowRender = (record: any) => {
  // 如果 report 为 null，显示错误信息
  if (!record.report) {
    return h('div', { 
      class: 'task-case-expand-card rounded-lg p-4 mt-4' 
    }, [
      h('div', { class: 'flex items-center gap-2' }, [
        h('span', { class: 'task-case-expand-error-label' }, '错误信息：'),
        h('span', { class: 'task-case-expand-error-message' }, record.error_message || '未知错误')
      ])
    ])
  }

  try {
    // 确保该记录在 expandedStepIds 中有对应的数组
    if (!expandedStepIds.value[record.id]) {
      expandedStepIds.value[record.id] = []
    }

    return h('div', { 
      class: 'task-case-expand-card rounded-lg p-4 mt-4' 
    }, [
      // 添加基本信息
      h('div', { class: 'task-case-expand-grid mb-4 grid grid-cols-2 gap-4' }, [
        h('div', { class: 'flex items-center gap-2' }, [
          h('span', { class: 'task-case-expand-label' }, '报告名称：'),
          h('span', { class: 'task-case-expand-value' }, record.report.name || '-')
        ]),
        h('div', { class: 'flex items-center gap-2' }, [
          h('span', { class: 'task-case-expand-label' }, '项目名称：'),
          h('span', { class: 'task-case-expand-value' }, 
            record.report.environment_info?.project?.name || '-'
          )
        ])
      ]),
      // 步骤详情
      record.report.details && record.report.details.length > 0 ? 
        h(ACollapse, {
          class: 'custom-collapse',
          modelValue: expandedStepIds.value[record.id],
          'onUpdate:modelValue': (val: number[]) => {
            expandedStepIds.value[record.id] = val
          }
        }, () => record.report.details.map((detail: StepDetail) => 
          h(ACollapseItem, {
            key: detail.id,
            name: detail.id,
            header: detail.step_name,
          }, {
            default: () => [
              // 使用ApiDetailCard组件展示接口详情
              h(ApiDetailCard, {
                detail: detail
              })
            ],
            extra: () => h('div', { class: 'flex items-center gap-4' }, [
              h(ATag, {
                color: detail.success ? 'green' : 'red'
              }, () => detail.success ? '成功' : '失败'),
              h('span', { class: 'task-case-expand-extra-text' }, formatDuration(detail.elapsed || 0))
            ])
          })
        ))
        : h('div', { class: 'task-case-expand-empty text-center py-4' }, '暂无步骤详情')
    ])
  } catch (error) {
    console.error('展开行渲染函数发生错误:', error)
    return h('div', { 
      class: 'task-case-expand-card rounded-lg p-4 mt-4' 
    }, [
      h('div', { class: 'flex items-center gap-2' }, [
        h('span', { class: 'task-case-expand-error-label' }, '错误信息：'),
        h('span', { class: 'task-case-expand-error-message' }, record.error_message || '未知错误')
      ])
    ])
  }
}

onMounted(() => {
  fetchCaseResults()
})
</script>

<template>
  <div class="testtask-case-results-page h-full flex flex-col gap-4 p-4" :class="isDarkTheme ? 'testtask-case-results-page--dark' : 'testtask-case-results-page--light'">
    <!-- 标题区域 -->
    <div class="panel-shell rounded-lg px-6 py-5 flex justify-between items-center">
      <div class="flex items-center gap-2">
        <h2 class="page-title text-xl font-medium">
          测试任务执行结果
        </h2>
        <a-tag v-if="route.params.id" color="blue">ID: {{ route.params.id }}</a-tag>
      </div>
      <a-button type="outline" class="back-button" @click="goBack">返回</a-button>
    </div>

    <!-- 内容区域 -->
    <div class="panel-shell flex-1 rounded-lg overflow-hidden">
      <a-spin :loading="loading" class="!block h-full">
        <div class="h-full overflow-auto">
          <template v-if="caseResults.length > 0">
            <!-- 汇总信息卡片 -->
            <div class="summary-section p-6 border-b">
              <div class="summary-card rounded-lg p-6">
                <h3 class="section-title text-lg font-medium mb-4">执行概况</h3>
                <div class="grid grid-cols-4 gap-6">
                  <!-- 总用例数 -->
                  <div class="summary-stat-card summary-stat-card--neutral rounded-lg p-4">
                    <div class="flex flex-col items-center">
                      <span class="summary-stat-label text-sm">总用例数</span>
                      <span class="summary-stat-value text-2xl font-semibold mt-2">
                        {{ caseResults.length }}
                      </span>
                    </div>
                  </div>
                  <!-- 成功用例 -->
                  <div class="summary-stat-card summary-stat-card--success rounded-lg p-4">
                    <div class="flex flex-col items-center">
                      <span class="summary-stat-label summary-stat-label--success text-sm">成功用例</span>
                      <span class="summary-stat-value summary-stat-value--success text-2xl font-semibold mt-2">
                        {{ caseResults.filter(r => r.status === 'success').length }}
                      </span>
                    </div>
                  </div>
                  <!-- 失败用例 -->
                  <div class="summary-stat-card summary-stat-card--warning rounded-lg p-4">
                    <div class="flex flex-col items-center">
                      <span class="summary-stat-label summary-stat-label--warning text-sm">失败用例</span>
                      <span class="summary-stat-value summary-stat-value--warning text-2xl font-semibold mt-2">
                        {{ caseResults.filter(r => r.status === 'fail' || r.status === 'failure').length }}
                      </span>
                    </div>
                  </div>
                  <!-- 错误用例 -->
                  <div class="summary-stat-card summary-stat-card--danger rounded-lg p-4">
                    <div class="flex flex-col items-center">
                      <span class="summary-stat-label summary-stat-label--danger text-sm">错误用例</span>
                      <span class="summary-stat-value summary-stat-value--danger text-2xl font-semibold mt-2">
                        {{ caseResults.filter(r => r.status === 'error').length }}
                      </span>
                    </div>
                  </div>
                </div>
                <!-- 执行时间信息 -->
                <div class="mt-4 grid grid-cols-2 gap-4">
                  <div class="flex items-center gap-2">
                    <span class="summary-meta-label">开始时间：</span>
                    <span class="summary-meta-value">{{ formatDate(caseResults[0]?.start_time || '') }}</span>
                  </div>
                  <div class="flex items-center gap-2">
                    <span class="summary-meta-label">总执行时长：</span>
                    <span class="summary-meta-value">{{ formatDuration(caseResults.reduce((sum, r) => sum + (r.duration || 0), 0)) }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 用例列表 -->
            <div class="p-6">
              <h3 class="section-title text-lg font-medium mb-4">用例详情</h3>
              <a-table 
                :data="caseResults" 
                :pagination="false" 
                :bordered="false"
                row-key="id"
                :expandable="{
                  expandedRowRender
                }"
                class="custom-table"
              >
                <template #columns>
                  <a-table-column 
                    title="ID" 
                    data-index="id"
                    :width="80"
                    align="center"
                  />
                  <a-table-column
                    title="类型"
                    data-index="case_type"
                    :width="110"
                    align="center"
                  >
                    <template #cell="{ record }">
                      <a-tag :color="record.case_type === 'interface' ? 'arcoblue' : 'purple'">
                        {{ getCaseTypeText(record.case_type) }}
                      </a-tag>
                    </template>
                  </a-table-column>
                  <a-table-column 
                    title="用例名称" 
                    data-index="testcase_name"
                    :width="250"
                    :sortable="{
                      sortDirections: ['ascend', 'descend']
                    }"
                  >
                    <template #cell="{ record }">
                      <div class="flex items-center gap-2">
                        <span class="case-primary-text">{{ record.testcase_name }}</span>
                        <a-tooltip v-if="record.error_message" position="right">
                          <template #content>
                            <span class="text-red-300">{{ record.error_message }}</span>
                          </template>
                          <icon-exclamation-circle-fill class="text-red-500" />
                        </a-tooltip>
                      </div>
                    </template>
                  </a-table-column>
                  <a-table-column 
                    title="状态" 
                    align="center"
                    :width="100"
                    :sortable="{
                      sortDirections: ['ascend', 'descend']
                    }"
                    :sort-field="(record: any) => record.status"
                  >
                    <template #cell="{ record }">
                      <a-tag :color="getCaseStatusColor(record.status)">
                        {{ getCaseStatusText(record.status) }}
                      </a-tag>
                    </template>
                  </a-table-column>
                  <a-table-column 
                    title="执行环境" 
                    :width="120"
                  >
                    <template #cell="{ record }">
                      <span class="case-secondary-text text-sm">{{ record.report?.environment_info?.name || '-' }}</span>
                    </template>
                  </a-table-column>
                  <a-table-column 
                    title="执行人" 
                    :width="100"
                  >
                    <template #cell="{ record }">
                      <span class="case-secondary-text text-sm">{{ record.report?.executed_by_info?.username || '-' }}</span>
                    </template>
                  </a-table-column>
                  <a-table-column 
                    title="执行时间" 
                    align="center"
                    :sortable="{
                      sortDirections: ['ascend', 'descend']
                    }"
                    :width="180"
                    :sort-field="(record: any) => new Date(record.start_time).getTime()"
                  >
                    <template #cell="{ record }">
                        <span class="case-secondary-text text-sm">{{ formatDate(record.start_time) }}</span>
                    </template>
                  </a-table-column>
                  <a-table-column 
                    title="执行时长" 
                    align="center"
                    :sortable="{
                      sortDirections: ['ascend', 'descend']
                    }"
                    :width="100"
                    :sort-field="(record: any) => record.duration"
                  >
                    <template #cell="{ record }">
                        <span class="case-secondary-text text-sm">{{ formatDuration(record.duration) }}</span>
                    </template>
                  </a-table-column>
                  <a-table-column 
                    title="步骤统计" 
                    align="center"
                    :width="250"
                    :sortable="{
                      sortDirections: ['ascend', 'descend']
                    }"
                    :sort-field="(record: any) => record.report?.success_count || 0"
                  >
                    <template #cell="{ record }">
                      <div class="flex items-center gap-2 justify-center">
                        <a-space v-if="record.report">
                          <a-tag color="green">成功: {{ record.report.success_count }}</a-tag>
                          <a-tag color="orange">失败: {{ record.report.fail_count }}</a-tag>
                          <a-tag color="red">错误: {{ record.report.error_count }}</a-tag>
                        </a-space>
                        <a-tag v-else color="red">数据异常</a-tag>
                      </div>
                    </template>
                  </a-table-column>
                  <a-table-column 
                    title="成功率" 
                    align="center"
                    :width="100"
                    :sortable="{
                      sortDirections: ['ascend', 'descend']
                    }"
                    :sort-field="(record: any) => Number(record.report?.success_rate || 0)"
                  >
                    <template #cell="{ record }">
                      <template v-if="record.report">
                        <a-progress
                          :percent="Number(record.report.success_rate || 0)"
                          :stroke-color="Number(record.report.success_rate || 0) === 1 ? '#00b42a' : '#ff7d00'"
                          :size="'small'"
                        />
                      </template>
                      <span v-else class="case-secondary-text text-sm">-</span>
                    </template>
                  </a-table-column>
                </template>
              </a-table>
            </div>
          </template>
          <div v-else class="h-full flex items-center justify-center">
            <div class="page-empty text-lg">暂无执行结果数据</div>
          </div>
        </div>
      </a-spin>
    </div>
  </div>
</template>

<style scoped lang="postcss">
@reference "tailwindcss";
.testtask-case-results-page {
  min-height: 0;
  --tt-panel-bg: color-mix(in srgb, var(--theme-card-bg) 94%, var(--theme-page-bg) 6%);
  --tt-panel-border: rgba(148, 163, 184, 0.16);
  --tt-panel-shadow: 0 14px 30px rgba(15, 23, 42, 0.08);
  --tt-text: var(--theme-text);
  --tt-text-muted: var(--theme-text-secondary);
  --tt-text-subtle: var(--theme-text-tertiary);
  --tt-summary-bg: rgba(15, 23, 42, 0.03);
  --tt-summary-border: rgba(148, 163, 184, 0.14);
  --tt-summary-card-bg: rgba(255, 255, 255, 0.82);
  --tt-summary-card-border: rgba(148, 163, 184, 0.12);
  --tt-row-hover: rgba(15, 23, 42, 0.04);
  --tt-code-bg: rgba(15, 23, 42, 0.04);
  --tt-code-border: rgba(148, 163, 184, 0.16);
  --tt-back-border: rgba(148, 163, 184, 0.28);
  --tt-back-text: var(--theme-text-secondary);
  --tt-back-hover-bg: rgba(148, 163, 184, 0.1);
  --tt-back-hover-border: rgba(148, 163, 184, 0.42);
  --tt-back-hover-text: var(--theme-text);
}

.testtask-case-results-page--dark {
  --tt-panel-bg: rgba(31, 41, 55, 0.85);
  --tt-panel-border: rgba(148, 163, 184, 0.12);
  --tt-panel-shadow: 0 18px 32px rgba(2, 6, 23, 0.28);
  --tt-text: rgb(241, 245, 249);
  --tt-text-muted: rgb(203, 213, 225);
  --tt-text-subtle: rgb(148, 163, 184);
  --tt-summary-bg: rgba(15, 23, 42, 0.26);
  --tt-summary-border: rgba(75, 85, 99, 0.4);
  --tt-summary-card-bg: rgba(30, 41, 59, 0.38);
  --tt-summary-card-border: rgba(75, 85, 99, 0.35);
  --tt-row-hover: rgba(30, 41, 59, 0.45);
  --tt-code-bg: rgba(15, 23, 42, 0.5);
  --tt-code-border: rgba(75, 85, 99, 0.4);
  --tt-back-border: rgba(148, 163, 184, 0.3);
  --tt-back-text: rgb(203, 213, 225);
  --tt-back-hover-bg: rgba(148, 163, 184, 0.1);
  --tt-back-hover-border: rgba(148, 163, 184, 0.45);
  --tt-back-hover-text: rgb(241, 245, 249);
}

.panel-shell {
  background: var(--tt-panel-bg);
  border: 1px solid var(--tt-panel-border);
  box-shadow: var(--tt-panel-shadow);
}

.page-title,
.section-title,
.case-primary-text,
.summary-meta-value,
.summary-stat-value {
  color: var(--tt-text);
}

.summary-stat-value--success {
  color: #16a34a;
}

.summary-stat-value--warning {
  color: #d97706;
}

.summary-stat-value--danger {
  color: #dc2626;
}

.summary-stat-label,
.summary-meta-label,
.case-secondary-text,
.page-empty {
  color: var(--tt-text-subtle);
}

.summary-stat-label--success {
  color: #16a34a;
}

.summary-stat-label--warning {
  color: #d97706;
}

.summary-stat-label--danger {
  color: #dc2626;
}

.summary-section {
  border-color: var(--tt-summary-border);
}

.summary-card {
  background: var(--tt-summary-bg);
  border: 1px solid var(--tt-summary-border);
}

.summary-stat-card {
  background: var(--tt-summary-card-bg);
  border: 1px solid var(--tt-summary-card-border);
}

.summary-stat-card--success {
  background: rgba(34, 197, 94, 0.12);
  border-color: rgba(34, 197, 94, 0.18);
}

.summary-stat-card--warning {
  background: rgba(245, 158, 11, 0.12);
  border-color: rgba(245, 158, 11, 0.18);
}

.summary-stat-card--danger {
  background: rgba(239, 68, 68, 0.12);
  border-color: rgba(239, 68, 68, 0.18);
}

.back-button {
  color: var(--tt-back-text) !important;
  border-color: var(--tt-back-border) !important;
  background: transparent !important;

  &:hover {
    color: var(--tt-back-hover-text) !important;
    border-color: var(--tt-back-hover-border) !important;
    background: var(--tt-back-hover-bg) !important;
  }
}

/* 自定义滚动条 */
.custom-scrollbar {
  scrollbar-width: none !important;
  -ms-overflow-style: none !important;
  &::-webkit-scrollbar {
    display: none !important;
  }
}

:deep(.arco-collapse) {
  @apply !bg-transparent !border-none;
}

:deep(.arco-collapse-item) {
  background: var(--tt-summary-bg) !important;
  border: 1px solid var(--tt-summary-border) !important;
  @apply !rounded-lg !mb-4;
}

:deep(.arco-collapse-item-header) {
  @apply !bg-transparent !border-b;
  border-color: var(--tt-summary-border) !important;
}

:deep(.arco-collapse-item-content) {
  background: transparent !important;
  color: var(--tt-text-muted) !important;
}

:deep(.arco-tabs) {
  color: var(--tt-text-muted) !important;
}

:deep(.arco-tabs-nav) {
  border-color: var(--tt-summary-border) !important;
}

:deep(.arco-tabs-nav-tab) {
  @apply !border-none;
}

:deep(.arco-tabs-nav-tab-list) {
  @apply !border-none;
}

:deep(.arco-tabs-tab) {
  color: var(--tt-text-subtle) !important;
}

:deep(.arco-tabs-tab-active) {
  @apply !text-blue-400;
}

:deep(.arco-tabs-content) {
  @apply !border-none;
}

pre {
  background: var(--tt-code-bg) !important;
  border: 1px solid var(--tt-code-border) !important;
  color: var(--tt-text-muted) !important;
  @apply !rounded !p-2 !overflow-auto;
  max-height: 300px;
}

/* 优化表格样式 */
:deep(.custom-table) {
  @apply !bg-transparent;
}

:deep(.custom-table .arco-table-th) {
  background: var(--tt-summary-bg) !important;
  color: var(--tt-text-muted) !important;
  border-color: var(--tt-summary-border) !important;
  @apply !font-medium;
}

:deep(.custom-table .arco-table-td) {
  background: transparent !important;
  color: var(--tt-text-muted) !important;
  border-color: var(--tt-summary-border) !important;
}

:deep(.custom-table .arco-table-tr:hover .arco-table-td) {
  background: var(--tt-row-hover) !important;
}

:deep(.custom-table .arco-table-tr-expand) {
  @apply !bg-transparent;
}

:deep(.custom-table .arco-table-expand-content) {
  @apply !bg-transparent !border-none;
}

:deep(.custom-table .arco-table-expand-icon) {
  color: var(--tt-text-subtle) !important;
}

:deep(.custom-table .arco-table-th-item-title) {
  color: var(--tt-text-muted) !important;
}

:deep(.custom-table .arco-table-sorter) {
  color: var(--tt-text-subtle) !important;
}

:deep(.custom-table .arco-table-sorter-icon) {
  color: var(--tt-text-subtle) !important;
}

:deep(.custom-table .arco-table-sorter-icon.active) {
  @apply !text-blue-400;
}

/* 进度条样式 */
:deep(.arco-progress-line-text) {
  color: var(--tt-text-muted) !important;
}

:deep(.arco-progress-line-trail) {
  background: var(--tt-summary-border) !important;
}

/* spin组件样式 */
:deep(.arco-spin) {
  @apply !h-full;
}

:deep(.arco-spin-children) {
  @apply !h-full;
}

:deep(.arco-spin-loading) {
  background: rgba(15, 23, 42, 0.18) !important;
}

:global(.task-case-expand-card) {
  background: var(--tt-summary-bg) !important;
  border: 1px solid var(--tt-summary-border) !important;
}

:global(.task-case-expand-label),
:global(.task-case-expand-extra-text),
:global(.task-case-expand-empty) {
  color: var(--tt-text-subtle) !important;
}

:global(.task-case-expand-value) {
  color: var(--tt-text) !important;
}

:global(.task-case-expand-error-label) {
  color: #ef4444 !important;
}

:global(.task-case-expand-error-message) {
  color: #dc2626 !important;
}
</style>
