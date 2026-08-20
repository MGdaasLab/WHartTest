<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { getTestTaskExecution, type TestTaskExecution } from '../../services/testTaskService'
import { useThemeStore } from '@/store/themeStore'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const executionData = ref<TestTaskExecution | null>(null)
const themeStore = useThemeStore()
const isDarkTheme = computed(() => themeStore.isBlack)
const progressTrackColor = computed(() => isDarkTheme.value ? 'rgba(30, 41, 59, 0.5)' : 'rgba(148, 163, 184, 0.18)')

// 自动刷新相关
const refreshTimer = ref<number | null>(null)
const autoRefresh = ref(true)
const refreshInterval = ref(2000) // 2秒刷新一次

// 获取测试任务执行详情
const fetchExecutionDetail = async (isAutoRefresh = false) => {
  const id = route.params.id
  if (!id) {
    Message.warning('未指定执行记录ID')
    return
  }

  // 自动刷新时不显示loading
  if (!isAutoRefresh) {
    loading.value = true
  }
  
  try {
    const response = await getTestTaskExecution(Number(id))
    if (response.status === 'success' && response.data) {
      const oldStatus = executionData.value?.status
      executionData.value = response.data
      
      if (isAutoRefresh && oldStatus !== response.data.status) {
        if (['completed', 'canceled', 'failed', 'error'].includes(response.data.status)) {
          stopAutoRefresh()

          if (response.data.status === 'completed') {
            Message.success('任务执行完成，正在跳转到结果页面...')
            setTimeout(() => {
              router.push({
                name: 'ApiTestTaskExecutionCaseResults',
                params: { id: response.data.id }
              })
            }, 1000)
          } else if (response.data.status === 'canceled') {
            Message.warning('任务已取消')
          } else {
            Message.error('任务执行出错')
          }
        }
      }
    } else {
      throw new Error(response.message || '获取执行记录详情失败')
    }
  } catch (error) {
    console.error('获取执行记录详情失败', error)
    if (!isAutoRefresh) {
      Message.error(error instanceof Error ? error.message : '获取执行记录详情失败')
    }
  } finally {
    if (!isAutoRefresh) {
      loading.value = false
    }
  }
}

// 启动自动刷新
const startAutoRefresh = () => {
  stopAutoRefresh()

  if (autoRefresh.value && executionData.value &&
      ['pending', 'running'].includes(executionData.value.status)) {
    refreshTimer.value = setInterval(() => {
      fetchExecutionDetail(true)
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

// 返回历史记录页面
const goBack = () => {
  if (executionData.value?.task_suite) {
    router.push({
      name: 'ApiTestTaskDetail',
      params: { id: executionData.value.task_suite }
    })
  } else {
    router.push({ path: '/api-testing', query: { tab: 'testtasks' } })
  }
}

// 查看执行结果
const viewCaseResults = () => {
  if (executionData.value?.id) {
    router.push({
      name: 'ApiTestTaskExecutionCaseResults',
      params: { id: executionData.value.id }
    })
  }
}

// 格式化日期
const formatDate = (dateStr: string | null) => {
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
const formatDuration = (seconds: number | null) => {
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
  'failed': 'red',
  'canceled': 'gray',
  'error': 'red'
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
  'failed': '失败',
  'canceled': '已取消',
  'error': '错误'
}

// 获取状态文本
const getStatusText = (status: string) => {
  return statusTextMap[status] || '未知'
}

// 监听执行数据变化，决定是否启动自动刷新
watch(executionData, (newData) => {
  if (newData && autoRefresh.value) {
    if (['pending', 'running'].includes(newData.status)) {
      startAutoRefresh()
    } else {
      stopAutoRefresh()
    }
  }
}, { immediate: false })

onMounted(async () => {
  await fetchExecutionDetail()
  // 初始加载后，如果任务在执行中，启动自动刷新
  if (executionData.value && ['pending', 'running'].includes(executionData.value.status)) {
    startAutoRefresh()
  }
})

// 组件卸载时清除定时器
onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<template>
  <div
    class="test-task-execution-detail h-full flex flex-col gap-4 p-4"
    :class="isDarkTheme ? 'test-task-execution-detail--dark' : 'test-task-execution-detail--light'"
  >
    <div class="execution-surface execution-surface--hero rounded-lg px-6 py-5 flex justify-between items-center">
      <div class="flex items-center gap-2">
        <h2 class="execution-title text-xl font-medium">
          测试任务执行详情
        </h2>
        <a-tag v-if="executionData" color="blue">ID: {{ executionData.id }}</a-tag>
      </div>
      <div class="flex items-center gap-3">
        <a-tooltip
          v-if="executionData && ['pending', 'running'].includes(executionData.status)"
          :content="autoRefresh ? '点击关闭自动刷新' : '点击开启自动刷新'"
        >
          <a-button
            :type="autoRefresh ? 'primary' : 'outline'"
            @click="toggleAutoRefresh"
            class="auto-refresh-button"
          >
            <template #icon>
              <icon-sync :spin="autoRefresh" />
            </template>
            {{ autoRefresh ? '自动刷新中' : '自动刷新' }}
          </a-button>
        </a-tooltip>
        <a-button
          v-if="executionData && ['running', 'completed'].includes(executionData.status)"
          :type="executionData.status === 'completed' ? 'primary' : 'outline'"
          :status="executionData.status === 'running' ? 'warning' : 'success'"
          class="view-results-button"
          @click="viewCaseResults"
        >
          <template #icon>
            <icon-eye />
          </template>
          查看执行结果
        </a-button>
        <a-button type="outline" @click="goBack">返回</a-button>
      </div>
    </div>

    <div class="execution-surface execution-surface--body flex-1 rounded-lg overflow-hidden">
      <a-spin :loading="loading" class="h-full">
        <div v-if="executionData" class="p-6">
          <div class="section-card rounded-lg p-6 mb-6">
            <h3 class="section-title text-lg font-medium mb-4">基本信息</h3>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div class="flex items-center gap-2">
                <span class="info-label w-24">任务名称：</span>
                <span class="info-value">{{ executionData.task_suite_name }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="info-label w-24">执行状态：</span>
                <a-tag :color="getStatusColor(executionData.status)">
                  {{ getStatusText(executionData.status) }}
                </a-tag>
              </div>
              <div class="flex items-center gap-2">
                <span class="info-label w-24">执行环境：</span>
                <span class="info-value">{{ executionData.environment_name || '-' }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="info-label w-24">执行人：</span>
                <span class="info-value">{{ executionData.executed_by_name || '-' }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="info-label w-24">开始时间：</span>
                <span class="info-value">{{ formatDate(executionData.start_time) }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="info-label w-24">结束时间：</span>
                <span class="info-value">{{ formatDate(executionData.end_time) }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="info-label w-24">执行时长：</span>
                <span class="info-value">{{ formatDuration(executionData.duration) }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="info-label w-24">创建时间：</span>
                <span class="info-value">{{ formatDate(executionData.created_at) }}</span>
              </div>
            </div>
          </div>

          <div class="section-card rounded-lg p-6">
            <h3 class="section-title text-lg font-medium mb-4">执行结果</h3>

            <div class="mb-6">
              <div class="flex justify-between items-center mb-2">
                <span class="info-label">成功率</span>
              </div>
              <a-progress
                :percent="executionData.success_rate ? Number(executionData.success_rate) : 0"
                :color="executionData.success_rate && Number(executionData.success_rate) >= 1 ? '#10b981' : '#f59e0b'"
                :track-color="progressTrackColor"
                :stroke-width="12"
              />
            </div>

            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div class="stat-card stat-card--neutral rounded-lg p-4 flex flex-col items-center justify-center">
                <span class="stat-label text-sm">总用例数</span>
                <span class="stat-value text-2xl font-semibold">{{ executionData.total_count }}</span>
              </div>
              <div class="stat-card stat-card--success rounded-lg p-4 flex flex-col items-center justify-center">
                <span class="text-green-400 text-sm">成功</span>
                <span class="text-green-300 text-2xl font-semibold">{{ executionData.success_count }}</span>
              </div>
              <div class="stat-card stat-card--warning rounded-lg p-4 flex flex-col items-center justify-center">
                <span class="text-amber-400 text-sm">失败</span>
                <span class="text-amber-300 text-2xl font-semibold">{{ executionData.fail_count }}</span>
              </div>
              <div class="stat-card stat-card--danger rounded-lg p-4 flex flex-col items-center justify-center">
                <span class="text-red-400 text-sm">错误</span>
                <span class="text-red-300 text-2xl font-semibold">{{ executionData.error_count }}</span>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="!loading" class="h-full flex items-center justify-center">
          <div class="empty-text text-lg">未找到执行记录数据</div>
        </div>
      </a-spin>
    </div>
  </div>
</template>

<style scoped>
@reference "tailwindcss";
.test-task-execution-detail {
  --tte-surface-bg: rgba(255, 255, 255, 0.94);
  --tte-surface-hero-bg: linear-gradient(135deg, rgba(248, 250, 252, 0.98), rgba(241, 245, 249, 0.96));
  --tte-section-bg: rgba(248, 250, 252, 0.94);
  --tte-border: rgba(148, 163, 184, 0.18);
  --tte-text: var(--color-text-1);
  --tte-muted: var(--color-text-2);
  --tte-subtle: var(--color-text-3);
  --tte-shadow: 0 12px 28px rgba(15, 23, 42, 0.06);
  --tte-neutral-card: rgba(241, 245, 249, 0.92);
}

.test-task-execution-detail--dark {
  --tte-surface-bg: rgba(31, 41, 55, 0.74);
  --tte-surface-hero-bg: rgba(31, 41, 55, 0.85);
  --tte-section-bg: rgba(17, 24, 39, 0.42);
  --tte-border: rgba(71, 85, 105, 0.32);
  --tte-text: rgb(241, 245, 249);
  --tte-muted: rgb(203, 213, 225);
  --tte-subtle: rgb(148, 163, 184);
  --tte-shadow: 0 10px 26px rgba(0, 0, 0, 0.18);
  --tte-neutral-card: rgba(30, 41, 59, 0.6);
}

.custom-scrollbar {
  scrollbar-width: none !important;
  -ms-overflow-style: none !important;
  &::-webkit-scrollbar {
    display: none !important;
  }
}

:deep(.arco-progress-text) {
  color: var(--tte-text) !important;
}

:deep(.arco-progress-text) {
  color: var(--tte-text) !important;
}

:deep(.arco-spin) {
  width: 100%;
  height: 100%;
}

:deep(.arco-spin-children) {
  height: 100%;
}

.execution-surface {
  background: var(--tte-surface-bg);
  border: 1px solid var(--tte-border);
  box-shadow: var(--tte-shadow);
}

.execution-surface--hero {
  background: var(--tte-surface-hero-bg);
}

.section-card {
  background: var(--tte-section-bg);
  border: 1px solid var(--tte-border);
}

.execution-title,
.section-title,
.info-value,
.stat-value {
  color: var(--tte-text);
}

.info-label,
.stat-label,
.empty-text {
  color: var(--tte-subtle);
}

.stat-card--neutral {
  background: var(--tte-neutral-card);
  border: 1px solid var(--tte-border);
}

.stat-card--success {
  background: rgba(16, 185, 129, 0.12);
  border: 1px solid rgba(16, 185, 129, 0.18);
}

.stat-card--warning {
  background: rgba(245, 158, 11, 0.12);
  border: 1px solid rgba(245, 158, 11, 0.18);
}

.stat-card--danger {
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.18);
}

.auto-refresh-button {
  transition: all 0.3s ease !important;
  
  &:deep(.arco-icon-sync) {
    transition: transform 0.3s ease !important;
  }
  
  &:hover:deep(.arco-icon-sync) {
    transform: rotate(180deg);
  }
}

.auto-refresh-button[type="primary"] {
  @apply !bg-green-500/20 !text-green-400 !border-green-500/30;
  box-shadow: 0 1px 3px rgba(34, 197, 94, 0.1) !important;
  
  &:hover {
    @apply !bg-green-500/30 !text-green-300 !border-green-500/40;
    box-shadow: 0 2px 5px rgba(34, 197, 94, 0.2) !important;
  }
}

.auto-refresh-button[type="outline"] {
  @apply !border-gray-500/30;
  color: var(--tte-subtle) !important;
  
  &:hover {
    @apply !border-gray-500/40 !bg-gray-700/30;
    color: var(--tte-muted) !important;
  }
}

.view-results-button {
  min-width: 156px;
  white-space: nowrap;
}
</style>
