<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { useThemeStore } from '@/store/themeStore'
import { useAppI18n } from '@/composables/useAppI18n'
import { getTestTaskExecutions, cancelTestTaskExecution, type TestTaskExecution } from '../../services/testTaskService'
import { toArray } from '../../services/responseHelpers'

const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()
const { isEnglish, tl } = useAppI18n()
const loading = ref(false)
const executions = ref<TestTaskExecution[]>([])
const taskSuiteId = ref<number | null>(null)
const taskSuiteName = ref('')
const isDarkTheme = computed(() => themeStore.isBlack)

// 定时器引用
const refreshTimer = ref<number | null>(null)
// 自动刷新开关
const autoRefresh = ref(true)
// 刷新间隔（毫秒）
const refreshInterval = ref(1000)

// 分页
const pagination = ref({
  current: 1,
  pageSize: 10,
  total: 0
})

// 搜索参数
const searchParams = ref({
  status: undefined as string | undefined,
  environment: undefined as number | undefined
})

// 状态选项
const statusOptions = [
  { label: '等待中', value: 'pending' },
  { label: '执行中', value: 'running' },
  { label: '已完成', value: 'completed' },
  { label: '已取消', value: 'canceled' },
  { label: '错误', value: 'error' }
]

const pageTitle = computed(() => {
  if (taskSuiteName.value) {
    return isEnglish.value
      ? `Execution History of "${taskSuiteName.value}"`
      : `"${taskSuiteName.value}" 的执行历史`
  }

  return isEnglish.value ? 'Test Task Execution History' : '测试任务执行历史'
})

const autoRefreshTooltip = computed(() => {
  return isEnglish.value
    ? (autoRefresh.value ? 'Click to turn off auto-refresh' : 'Click to turn on auto-refresh')
    : (autoRefresh.value ? '点击关闭自动刷新' : '点击开启自动刷新')
})

const autoRefreshButtonLabel = computed(() => {
  return isEnglish.value
    ? (autoRefresh.value ? 'Auto-refresh on' : 'Auto-refresh')
    : (autoRefresh.value ? '自动刷新中' : '自动刷新')
})

const totalCasesColumnTitle = computed(() => {
  return isEnglish.value ? 'Total Cases' : '用例总数'
})

// 获取测试任务执行历史记录（完整刷新）
const fetchExecutionHistory = async () => {
  if (!taskSuiteId.value) {
    Message.warning('未指定测试任务')
    return
  }

  loading.value = true
  try {
    const response = await getTestTaskExecutions({
      task_suite_id: taskSuiteId.value,
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
      status: searchParams.value.status,
      environment: searchParams.value.environment,
      ordering: '-created_at'
    })

    executions.value = toArray<TestTaskExecution>(response.data?.results ?? response.data)
    pagination.value.total = response.data.count || 0

    // 如果有执行记录，获取任务名称
    if (executions.value.length > 0) {
      taskSuiteName.value = executions.value[0].task_suite_name
    }
  } catch (error) {
    console.error('获取执行历史记录失败', error)
    Message.error('获取执行历史记录失败')
  } finally {
    loading.value = false
  }
}

// 仅更新状态和成功率等动态字段（轻量级刷新）
const updateExecutionStatus = async () => {
  if (!taskSuiteId.value || executions.value.length === 0) {
    return
  }

  try {
    const response = await getTestTaskExecutions({
      task_suite_id: taskSuiteId.value,
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
      status: searchParams.value.status,
      environment: searchParams.value.environment,
      ordering: '-created_at'
    })
    
    const newExecutions = toArray<TestTaskExecution>(response.data?.results ?? response.data)
    
    // 只更新现有记录的特定字段
    executions.value.forEach((execution, index) => {
      const newExecution = newExecutions.find(e => e.id === execution.id)
      if (newExecution) {
        // 只更新可能变化的字段
        execution.status = newExecution.status
        execution.success_rate = newExecution.success_rate
        execution.end_time = newExecution.end_time
        execution.duration = newExecution.duration
        execution.total_count = newExecution.total_count
      }
    })
    
    // 检查是否有新的执行记录（比如新任务开始执行）
    const existingIds = new Set(executions.value.map(e => e.id))
    const newRecords = newExecutions.filter(e => !existingIds.has(e.id))
    if (newRecords.length > 0) {
      // 如果有新记录，执行完整刷新
      executions.value = newExecutions
      pagination.value.total = response.data.count || 0
    }
  } catch (error) {
    // 静默处理错误，避免频繁提示
    console.error('更新执行状态失败', error)
  }
}

// 查看执行详情
const viewExecutionDetail = (record: TestTaskExecution) => {
  if (['pending', 'running'].includes(record.status)) {
    router.push({
      name: 'ApiTestTaskExecutionDetail',
      params: { id: record.id }
    })
  } else {
    router.push({
      name: 'ApiTestTaskExecutionCaseResults',
      params: { id: record.id }
    })
  }
}

// 返回列表页
const goBack = () => {
  router.push({ path: '/api-testing', query: { tab: 'testtasks' } })
}

// 格式化日期
const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// 格式化持续时间
const formatDuration = (seconds: number) => {
  if (!seconds) return '-'
  
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  
  if (minutes > 0) {
    return `${minutes}分${remainingSeconds}秒`
  }
  return `${remainingSeconds}秒`
}

// 状态颜色映射
const statusColorMap: Record<string, string> = {
  'pending': 'blue',
  'running': 'orange',
  'completed': 'green',
  'canceled': 'gray',
  'error': 'red',
  'failure': 'red'
}

// 获取状态标签颜色
const getStatusColor = (status: string) => {
  return statusColorMap[status] || 'gray'
}

// 状态文本映射
const statusTextMap: Record<string, string> = {
  'pending': '等待中',
  'running': '执行中',
  'completed': '已完成',
  'canceled': '已取消',
  'error': '错误',
  'failure': '失败'
}

// 获取状态文本
const getStatusText = (status: string) => {
  return statusTextMap[status] || '未知'
}

// 页码变化
const handlePageChange = (page: number) => {
  pagination.value.current = page
  fetchExecutionHistory()
}

// 每页条数变化
const handlePageSizeChange = (pageSize: number) => {
  pagination.value.pageSize = pageSize
  pagination.value.current = 1
  fetchExecutionHistory()
}

// 处理搜索
const handleSearch = () => {
  pagination.value.current = 1
  fetchExecutionHistory()
}

// 重置搜索
const resetSearch = () => {
  searchParams.value = {
    status: undefined,
    environment: undefined
  }
  pagination.value.current = 1
  fetchExecutionHistory()
}

// 取消执行
const cancelExecution = async (id: number) => {
  try {
    await cancelTestTaskExecution(id)
    Message.success('已取消执行')
    fetchExecutionHistory()
  } catch (error) {
    console.error('取消执行失败', error)
    Message.error('取消执行失败')
  }
}

// 启动自动刷新
const startAutoRefresh = () => {
  stopAutoRefresh() // 先清除已有的定时器
  if (autoRefresh.value) {
    refreshTimer.value = setInterval(() => {
      // 只在不加载中的情况下刷新，避免重复请求
      if (!loading.value) {
        // 使用轻量级更新，只刷新状态和成功率
        updateExecutionStatus()
      }
    }, refreshInterval.value)
  }
}

// 停止自动刷新
const stopAutoRefresh = () => {
  if (refreshTimer.value) {
    clearInterval(refreshTimer.value)
    refreshTimer.value = null
  }
}

// 切换自动刷新状态
const toggleAutoRefresh = () => {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) {
    startAutoRefresh()
    Message.success('已开启自动刷新')
  } else {
    stopAutoRefresh()
    Message.info('已关闭自动刷新')
  }
}

// 监听路由参数变化
watch(() => route.params.id, (newId) => {
  if (newId) {
    taskSuiteId.value = Number(newId)
    fetchExecutionHistory()
    // 启动自动刷新
    if (autoRefresh.value) {
      startAutoRefresh()
    }
  }
}, { immediate: true })

// 监听自动刷新开关变化
watch(autoRefresh, (newVal) => {
  if (newVal) {
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
})

// 组件挂载时启动自动刷新
onMounted(() => {
  if (autoRefresh.value && taskSuiteId.value) {
    startAutoRefresh()
  }
})

// 组件卸载时清除定时器
onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<template>
  <div class="testtask-history-page h-full flex flex-col gap-4 p-4" :class="isDarkTheme ? 'testtask-history-page--dark' : 'testtask-history-page--light'">
    <!-- 标题区域 -->
    <div class="panel-shell rounded-lg px-6 py-5 flex justify-between items-center">
      <div class="flex items-center gap-2">
        <h2 class="page-title text-xl font-medium">
          {{ pageTitle }}
        </h2>
        <a-tag v-if="taskSuiteId" color="blue">ID: {{ taskSuiteId }}</a-tag>
      </div>
      <div class="flex items-center gap-3">
        <a-tooltip :content="autoRefreshTooltip">
          <a-button
            :type="autoRefresh ? 'primary' : 'outline'"
            @click="toggleAutoRefresh"
            class="auto-refresh-button"
          >
            <template #icon>
              <icon-sync :spin="autoRefresh" />
            </template>
            {{ autoRefreshButtonLabel }}
          </a-button>
        </a-tooltip>
        <a-button type="outline" class="back-button" @click="goBack">{{ tl('返回列表') }}</a-button>
      </div>
    </div>

    <!-- 搜索区域 -->
    <div class="panel-shell rounded-lg px-6 py-5">
      <div class="flex items-center gap-4">
        <div class="flex-1 flex items-center gap-4">
          <a-select
            v-model="searchParams.status"
            placeholder="执行状态"
            allow-clear
            class="w-32"
          >
            <a-option 
              v-for="option in statusOptions" 
              :key="option.value" 
              :value="option.value"
            >
              {{ option.label }}
            </a-option>
          </a-select>
          
          <a-button type="outline" class="custom-reset-button" @click="resetSearch">
            重置
          </a-button>
          
          <a-button type="primary" class="custom-search-button" @click="handleSearch">
            搜索
          </a-button>
        </div>
      </div>
    </div>

    <!-- 内容区域 -->
    <div class="panel-shell flex-1 rounded-lg overflow-hidden">
      <div class="p-6">
        <a-table
          :loading="loading"
          :data="executions"
          :pagination="false"
          :bordered="false"
          :scroll="{ y: 'calc(100vh - 400px)' }"
          :sticky-header="true"
          class="custom-table"
        >
          <template #columns>
            <a-table-column title="ID" data-index="id" :width="80" align="center" />
            <a-table-column title="状态" data-index="status" :width="120" align="center">
              <template #cell="{ record }">
                <a-tag :color="getStatusColor(record.status)">
                  {{ getStatusText(record.status) }}
                </a-tag>
              </template>
            </a-table-column>
            <a-table-column title="环境" data-index="environment_name" :width="150" align="center">
              <template #cell="{ record }">
                <div class="cell-text">{{ record.environment_name || '-' }}</div>
              </template>
            </a-table-column>
            <a-table-column title="开始时间" data-index="start_time" :width="180" align="center">
              <template #cell="{ record }">
                <div class="cell-text">{{ formatDate(record.start_time) }}</div>
              </template>
            </a-table-column>
            <a-table-column title="结束时间" data-index="end_time" :width="180" align="center">
              <template #cell="{ record }">
                <div class="cell-text">{{ formatDate(record.end_time) }}</div>
              </template>
            </a-table-column>
            <a-table-column title="执行时长" data-index="duration" :width="120" align="center">
              <template #cell="{ record }">
                <div class="cell-text">{{ formatDuration(record.duration) }}</div>
              </template>
            </a-table-column>
            <a-table-column :title="totalCasesColumnTitle" data-index="total_count" :width="100" align="center">
              <template #cell="{ record }">
                <div class="cell-text">{{ record.total_count }}</div>
              </template>
            </a-table-column>
            <a-table-column title="成功率" data-index="success_rate" :width="100" align="center">
              <template #cell="{ record }">
                <a-progress
                  :percent="record.success_rate ? parseFloat(record.success_rate) : 0"
                  :color="record.success_rate && parseFloat(record.success_rate) >= 1 ? '#10b981' : '#f59e0b'"
                  :show-text="true"
                  size="small"
                />
              </template>
            </a-table-column>
            <a-table-column title="执行人" data-index="executed_by_name" :width="120" align="center">
              <template #cell="{ record }">
                <div class="cell-text">{{ record.executed_by_name || '-' }}</div>
              </template>
            </a-table-column>
            <a-table-column title="创建时间" data-index="created_at" :width="180" align="center">
              <template #cell="{ record }">
                <div class="cell-text cell-text--subtle">{{ formatDate(record.created_at) }}</div>
              </template>
            </a-table-column>
            <a-table-column title="操作" align="center" :width="200" fixed="right">
              <template #cell="{ record }">
                <div class="flex items-center gap-2 justify-center">
                  <a-button
                    type="primary"
                    size="mini"
                    class="btn-view"
                    @click="viewExecutionDetail(record)"
                  >
                    查看详情
                  </a-button>
                  <a-button
                    v-if="record.status === 'running'"
                    type="outline"
                    status="danger"
                    size="mini"
                    class="btn-cancel"
                    @click="cancelExecution(record.id)"
                  >
                    取消执行
                  </a-button>
                </div>
              </template>
            </a-table-column>
          </template>
          <template #empty>
            <div class="page-empty py-8 flex justify-center items-center">
              暂无执行记录
            </div>
          </template>
        </a-table>
      </div>
    </div>

    <!-- 分页区域 -->
    <div class="panel-shell rounded-lg px-6 py-5">
      <a-pagination
        v-model:current="pagination.current"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        show-total
        show-jumper
        show-page-size
        class="flex justify-end"
        @change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      />
    </div>
  </div>
</template>

<style scoped>
@reference "tailwindcss";
.testtask-history-page {
  min-height: 0;
  --tt-panel-bg: color-mix(in srgb, var(--theme-card-bg) 94%, var(--theme-page-bg) 6%);
  --tt-panel-border: rgba(148, 163, 184, 0.16);
  --tt-panel-shadow: 0 14px 30px rgba(15, 23, 42, 0.08);
  --tt-text: var(--theme-text);
  --tt-text-muted: var(--theme-text-secondary);
  --tt-text-subtle: var(--theme-text-tertiary);
  --tt-input-bg: #ffffff;
  --tt-input-border: rgba(148, 163, 184, 0.18);
  --tt-input-bg-hover: color-mix(in srgb, var(--theme-card-bg) 88%, var(--theme-page-bg) 12%);
  --tt-table-header-bg: color-mix(in srgb, var(--theme-card-bg) 76%, var(--theme-page-bg) 24%);
  --tt-table-row-alt: rgba(15, 23, 42, 0.02);
  --tt-table-row-hover: rgba(15, 23, 42, 0.04);
  --tt-secondary-bg: rgba(148, 163, 184, 0.08);
  --tt-secondary-bg-hover: rgba(148, 163, 184, 0.14);
  --tt-secondary-border: rgba(148, 163, 184, 0.18);
  --tt-secondary-text: var(--theme-text-secondary);
  --tt-secondary-text-hover: var(--theme-text);
  --tt-outline-border: rgba(148, 163, 184, 0.28);
  --tt-outline-text: var(--theme-text-secondary);
  --tt-outline-hover-bg: rgba(148, 163, 184, 0.1);
  --tt-outline-hover-border: rgba(148, 163, 184, 0.4);
  --tt-outline-hover-text: var(--theme-text);
  --tt-view-btn-bg: rgba(37, 99, 235, 0.12);
  --tt-view-btn-bg-hover: rgba(37, 99, 235, 0.18);
  --tt-view-btn-border: rgba(59, 130, 246, 0.24);
  --tt-view-btn-text: #2563eb;
  --tt-view-btn-text-hover: #1d4ed8;
  --tt-cancel-btn-bg: rgba(239, 68, 68, 0.12);
  --tt-cancel-btn-bg-hover: rgba(239, 68, 68, 0.18);
  --tt-cancel-btn-border: rgba(239, 68, 68, 0.24);
  --tt-cancel-btn-text: #dc2626;
  --tt-cancel-btn-text-hover: #b91c1c;
}

.testtask-history-page--dark {
  --tt-panel-bg: rgba(31, 41, 55, 0.85);
  --tt-panel-border: rgba(148, 163, 184, 0.12);
  --tt-panel-shadow: 0 18px 32px rgba(2, 6, 23, 0.28);
  --tt-text: rgb(241, 245, 249);
  --tt-text-muted: rgb(203, 213, 225);
  --tt-text-subtle: rgb(148, 163, 184);
  --tt-input-bg: rgba(51, 65, 85, 0.25);
  --tt-input-border: rgba(148, 163, 184, 0.15);
  --tt-input-bg-hover: rgba(51, 65, 85, 0.35);
  --tt-table-header-bg: rgba(30, 41, 59, 0.7);
  --tt-table-row-alt: rgba(30, 41, 59, 0.3);
  --tt-table-row-hover: rgba(30, 41, 59, 0.6);
  --tt-secondary-bg: rgba(148, 163, 184, 0.1);
  --tt-secondary-bg-hover: rgba(148, 163, 184, 0.18);
  --tt-secondary-border: rgba(148, 163, 184, 0.18);
  --tt-secondary-text: rgb(203, 213, 225);
  --tt-secondary-text-hover: rgb(241, 245, 249);
  --tt-outline-border: rgba(148, 163, 184, 0.3);
  --tt-outline-text: rgb(203, 213, 225);
  --tt-outline-hover-bg: rgba(148, 163, 184, 0.1);
  --tt-outline-hover-border: rgba(148, 163, 184, 0.45);
  --tt-outline-hover-text: rgb(241, 245, 249);
  --tt-view-btn-bg: rgba(15, 23, 42, 0.6);
  --tt-view-btn-bg-hover: rgba(15, 23, 42, 0.72);
  --tt-view-btn-border: rgba(59, 130, 246, 0.28);
  --tt-view-btn-text: #60a5fa;
  --tt-view-btn-text-hover: #93c5fd;
  --tt-cancel-btn-bg: rgba(15, 23, 42, 0.6);
  --tt-cancel-btn-bg-hover: rgba(15, 23, 42, 0.72);
  --tt-cancel-btn-border: rgba(239, 68, 68, 0.28);
  --tt-cancel-btn-text: #f87171;
  --tt-cancel-btn-text-hover: #fca5a5;
}

.panel-shell {
  background: var(--tt-panel-bg);
  border: 1px solid var(--tt-panel-border);
  box-shadow: var(--tt-panel-shadow);
}

.page-title {
  color: var(--tt-text);
}

.page-empty,
.cell-text {
  color: var(--tt-text-muted);
}

.cell-text--subtle {
  color: var(--tt-text-subtle);
}

/* 自定义滚动条 */
.custom-scrollbar {
  scrollbar-width: none !important;
  -ms-overflow-style: none !important;
  &::-webkit-scrollbar {
    display: none !important;
  }
}

/* 分页样式 */
:deep(.arco-pagination) {
  .arco-pagination-item {
    border-radius: 4px !important;
    color: var(--tt-text-subtle) !important;
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
      background-color: var(--tt-input-bg) !important;
      border: 1px solid var(--tt-input-border) !important;
      color: var(--tt-text) !important;

      &:hover, &:focus {
        border-color: rgba(59, 130, 246, 0.4) !important;
        background-color: var(--tt-input-bg-hover) !important;
      }
    }
  }

  .arco-pagination-total {
    color: var(--tt-text-subtle) !important;
  }

  .arco-select-view {
    background-color: var(--tt-input-bg) !important;
    border: 1px solid var(--tt-input-border) !important;
    border-radius: 4px !important;
    color: var(--tt-text) !important;

    &:hover {
      border-color: rgba(59, 130, 246, 0.4) !important;
      background-color: var(--tt-input-bg-hover) !important;
    }
  }
}

:deep(.arco-select-view-value),
:deep(.arco-select-view-single .arco-select-view-input),
:deep(.arco-pagination-jumper-prepend),
:deep(.arco-pagination-jumper-append) {
  color: var(--tt-text) !important;
}

:deep(.arco-select-view-placeholder) {
  color: var(--tt-text-subtle) !important;
}

:deep(.arco-select-view-suffix),
:deep(.arco-pagination-item-ellipsis),
:deep(.arco-pagination-jumper-separator) {
  color: var(--tt-text-subtle) !important;
}

.custom-reset-button {
  background-color: var(--tt-secondary-bg) !important;
  border: 1px solid var(--tt-secondary-border) !important;
  color: var(--tt-secondary-text) !important;
  transition: all 0.3s ease !important;
  border-radius: 8px !important;

  &:hover {
    border-color: rgba(59, 130, 246, 0.24) !important;
    color: var(--tt-secondary-text-hover) !important;
    background-color: var(--tt-secondary-bg-hover) !important;
  }
}

.custom-search-button {
  @apply !bg-blue-500/20 !text-blue-400 !border-blue-500/30;
  transition: all 0.3s ease !important;
  box-shadow: 0 1px 3px rgba(59, 130, 246, 0.1) !important;
  border-radius: 8px !important;

  &:hover {
    @apply !bg-blue-500/30 !text-blue-300 !border-blue-500/40;
    transform: translateY(-1px) !important;
    box-shadow: 0 2px 5px rgba(59, 130, 246, 0.2) !important;
  }

  &:active {
    transform: translateY(1px) !important;
    box-shadow: 0 1px 2px rgba(59, 130, 246, 0.1) !important;
  }
}

/* 表格样式 */
.custom-table :deep(.arco-table) {
  background-color: transparent !important;
}

.custom-table :deep(.arco-table-container) {
  background-color: transparent !important;
  border: none !important;
}

.custom-table :deep(.arco-table-header) {
  background-color: transparent !important;
}

.custom-table :deep(.arco-table-body) {
  background-color: transparent !important;
}

.custom-table :deep(.arco-table-th) {
  background-color: var(--tt-table-header-bg) !important;
  border-bottom: 1px solid var(--tt-panel-border) !important;
  color: var(--tt-text) !important;
  font-weight: 500 !important;
  text-align: center !important;
}

.custom-table :deep(.arco-table-td) {
  background-color: transparent !important;
  border-bottom: 1px solid var(--tt-panel-border) !important;
  color: var(--tt-text-muted) !important;
}

.custom-table :deep(.arco-table-tr) {
  background-color: transparent !important;
}

.custom-table :deep(.arco-table-tr:hover) {
  background-color: var(--tt-table-row-hover) !important;
}

/* 表格行样式调整 */
.custom-table :deep(.arco-table-tr:nth-child(even)) {
  background-color: var(--tt-table-row-alt) !important;
}

.custom-table :deep(.arco-table-tr:nth-child(odd)) {
  background-color: transparent !important;
}

.custom-table :deep(.arco-table-tr:hover) {
  background-color: var(--tt-table-row-hover) !important;
}

/* 查看详情按钮样式 */
.btn-view {
  border: 1px solid var(--tt-view-btn-border) !important;
  color: var(--tt-view-btn-text) !important;
  background-color: var(--tt-view-btn-bg) !important;
  box-shadow: 0 1px 3px rgba(37, 99, 235, 0.12) !important;
  @apply !px-3;
  @apply !h-8 !font-medium !rounded-md;
  transition: all 0.2s ease;
  position: relative;
  z-index: 1;
  
  &:hover {
    @apply !shadow-md !transform !scale-105;
    box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2) !important;
    background-color: var(--tt-view-btn-bg-hover) !important;
    color: var(--tt-view-btn-text-hover) !important;
  }
}

/* 取消执行按钮样式 */
.btn-cancel {
  border: 1px solid var(--tt-cancel-btn-border) !important;
  color: var(--tt-cancel-btn-text) !important;
  background-color: var(--tt-cancel-btn-bg) !important;
  box-shadow: 0 1px 3px rgba(239, 68, 68, 0.12) !important;
  @apply !px-3;
  @apply !h-8 !font-medium !rounded-md;
  transition: all 0.2s ease;
  position: relative;
  z-index: 1;
  
  &:hover {
    @apply !shadow-md !transform !scale-105;
    box-shadow: 0 2px 4px rgba(239, 68, 68, 0.2) !important;
    background-color: var(--tt-cancel-btn-bg-hover) !important;
    color: var(--tt-cancel-btn-text-hover) !important;
  }
}

/* 自动刷新按钮样式 */
.auto-refresh-button {
  transition: all 0.3s ease !important;
  
  &:deep(.arco-icon-sync) {
    transition: transform 0.3s ease !important;
  }
  
  &:hover:deep(.arco-icon-sync) {
    transform: rotate(180deg);
  }
}

/* 自动刷新激活状态 */
.auto-refresh-button[type="primary"] {
  @apply !bg-green-500/20 !text-green-400 !border-green-500/30;
  box-shadow: 0 1px 3px rgba(34, 197, 94, 0.1) !important;
  
  &:hover {
    @apply !bg-green-500/30 !text-green-300 !border-green-500/40;
    box-shadow: 0 2px 5px rgba(34, 197, 94, 0.2) !important;
  }
}

/* 自动刷新非激活状态 */
.auto-refresh-button[type="outline"] {
  color: var(--tt-outline-text) !important;
  border-color: var(--tt-outline-border) !important;
  
  &:hover {
    color: var(--tt-outline-hover-text) !important;
    border-color: var(--tt-outline-hover-border) !important;
    background: var(--tt-outline-hover-bg) !important;
  }
}

.back-button {
  color: var(--tt-outline-text) !important;
  border-color: var(--tt-outline-border) !important;
  background: transparent !important;

  &:hover {
    color: var(--tt-outline-hover-text) !important;
    border-color: var(--tt-outline-hover-border) !important;
    background: var(--tt-outline-hover-bg) !important;
  }
}
</style>
