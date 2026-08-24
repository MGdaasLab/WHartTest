<script setup lang="ts">
import { ref, onMounted, h, watch } from 'vue'
import { Message, Tag as ATag, Button as AButton } from '@arco-design/web-vue'
import type { TableColumnData } from '@arco-design/web-vue'
import { testcaseService } from '../../services/testcaseService'
import { normalizeListPayload } from '../../services/responseHelpers'
import type { TestCaseHistoryReport } from '../../types/testcase'
import type { PaginatedResponse } from '../../types/common'
import { useProjectStore } from '@/store/projectStore'
import dayjs from 'dayjs'

type HistoryReportsPayload = TestCaseHistoryReport[] | PaginatedResponse<TestCaseHistoryReport>

const formatDuration = (ms: number): string => {
  const roundedMs = Math.round(ms * 100) / 100

  if (roundedMs < 1) {
    return `${roundedMs.toFixed(2)}ms`
  }

  if (roundedMs < 1000) {
    return `${Math.round(roundedMs)}ms`
  }

  const seconds = Math.floor(roundedMs / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)

  if (hours > 0) {
    const remainingMinutes = minutes % 60
    const remainingSeconds = seconds % 60
    return `${hours}h ${remainingMinutes}m ${remainingSeconds}s`
  }

  if (minutes > 0) {
    const remainingSeconds = seconds % 60
    return `${minutes}m ${remainingSeconds}s`
  }

  return `${seconds}s`
}

const props = defineProps<{
  testcaseId: number
  pagination: {
    current: number
    pageSize: number
    total: number
    showTotal: boolean
    showJumper: boolean
    showPageSize: boolean
  }
}>()

const emit = defineEmits(['update:pagination', 'view-report'])

const projectStore = useProjectStore()
const loading = ref(false)
const reports = ref<TestCaseHistoryReport[]>([])

const normalizeHistoryReports = (payload?: HistoryReportsPayload) => {
  const { results, count } = normalizeListPayload<TestCaseHistoryReport>(payload)
  return { results, total: count }
}

const columns: TableColumnData[] = [
  {
    title: '#',
    width: 80,
    align: 'center' as const,
    render: (data) => {
      const currentPage = props.pagination.current
      const pageSize = props.pagination.pageSize
      return ((currentPage - 1) * pageSize + data.rowIndex + 1)
    }
  },
  {
    title: '报告ID',
    dataIndex: 'id',
    width: 80,
    align: 'center' as const
  },
  {
    title: '报告名称',
    dataIndex: 'name',
    ellipsis: true,
    align: 'center' as const
  },
  {
    title: '执行状态',
    dataIndex: 'status',
    width: 100,
    align: 'center' as const,
    render: (data) => h(ATag, {
      color: (data.record as TestCaseHistoryReport).status === 'success' ? 'green' :
            (data.record as TestCaseHistoryReport).status === 'failure' ? 'red' : 'orange'
    }, () => (data.record as TestCaseHistoryReport).status === 'success' ? '成功' :
           (data.record as TestCaseHistoryReport).status === 'failure' ? '失败' : '错误')
  },
  {
    title: '成功率',
    dataIndex: 'success_rate',
    width: 100,
    align: 'center' as const,
    render: (data) => `${Number((data.record as TestCaseHistoryReport).success_rate) * 100}%`
  },
  {
    title: '步骤统计',
    dataIndex: 'steps',
    width: 200,
    align: 'center' as const,
    render: (data) => {
      const record = data.record as TestCaseHistoryReport
      return h('div', {
        class: 'flex items-center justify-center gap-2'
      }, [
        h(ATag, {
          color: 'green',
          class: record.success_count === 0 ? 'opacity-50' : ''
        }, () => `成功: ${record.success_count}`),
        h(ATag, {
          color: 'red',
          class: record.fail_count === 0 ? 'opacity-50' : ''
        }, () => `失败: ${record.fail_count}`),
        h(ATag, {
          color: 'orange',
          class: record.error_count === 0 ? 'opacity-50' : ''
        }, () => `错误: ${record.error_count}`)
      ])
    }
  },
  {
    title: '执行时长',
    dataIndex: 'duration',
    width: 100,
    align: 'center' as const,
    render: (data) => formatDuration((data.record as TestCaseHistoryReport).duration)
  },
  {
    title: '执行时间',
    dataIndex: 'start_time',
    width: 180,
    align: 'center' as const,
    render: (data) => dayjs((data.record as TestCaseHistoryReport).start_time).format('YYYY-MM-DD HH:mm:ss')
  },
  {
    title: '执行环境',
    dataIndex: 'environment_name',
    width: 120,
    align: 'center' as const,
    render: (data) => (data.record as TestCaseHistoryReport).environment_name || '-'
  },
  {
    title: '操作',
    width: 120,
    align: 'center' as const,
    render: (data) => h('div', {
      class: 'flex items-center justify-center gap-2'
    }, [
      h(AButton, {
        type: 'text',
        size: 'small',
        onClick: () => handleViewDetail(data.record as TestCaseHistoryReport)
      }, () => '查看详情')
    ])
  }
]

const fetchHistoryReports = async () => {
  if (!projectStore.currentProjectId) return
  try {
    loading.value = true
    const res = await testcaseService.historyReports(projectStore.currentProjectId, props.testcaseId, {
      page: props.pagination.current,
      page_size: props.pagination.pageSize
    })

    if (res.success) {
      const { results, total } = normalizeHistoryReports(res.data as HistoryReportsPayload | undefined)

      reports.value = results
      emit('update:pagination', {
        ...props.pagination,
        total: res.total ?? total
      })
    }
  } catch (error) {
    console.error('获取历史报告列表失败:', error)
    Message.error('获取历史报告列表失败')
    reports.value = []
  } finally {
    loading.value = false
  }
}

const handleViewDetail = (report: TestCaseHistoryReport) => {
  emit('view-report', report)
}

watch(() => props.pagination.current, () => {
  fetchHistoryReports()
})

watch(() => props.pagination.pageSize, () => {
  fetchHistoryReports()
})

onMounted(() => {
  fetchHistoryReports()
})
</script>

<template>
  <div class="history-reports-panel h-full">
    <a-table
      :data="reports"
      :columns="columns"
      :loading="loading"
      :pagination="false"
      :bordered="false"
      :stripe="true"
    >
      <template #empty>
        <div class="empty-text text-center py-8">
          暂无历史报告
        </div>
      </template>
    </a-table>
  </div>
</template>

<style scoped>
@reference "tailwindcss";
:deep(.arco-table) {
  @apply !bg-transparent;

  .arco-table-th {
    background: var(--api-report-table-header-bg) !important;
    color: var(--api-report-text) !important;
    border-color: var(--api-report-shell-border) !important;
  }

  .arco-table-td {
    background: transparent !important;
    color: var(--api-report-text-muted) !important;
    border-color: var(--api-report-shell-border) !important;
  }

  .arco-table-tr:hover .arco-table-td {
    background: var(--api-report-table-row-hover) !important;
  }
}

:deep(.arco-btn-text) {
  color: var(--theme-accent) !important;
}

:deep(.arco-btn-text:hover) {
  color: var(--theme-accent-hover) !important;
  background: rgba(var(--theme-accent-rgb), 0.08) !important;
}

.empty-text {
  color: var(--api-report-text-subtle);
}

/* 分页样式 */
:deep(.arco-pagination) {
  .arco-pagination-item {
    border-radius: 4px !important;
    color: var(--api-report-text-subtle) !important;
    background-color: transparent !important;
    border: 1px solid transparent !important;

    &:hover {
      color: var(--theme-accent-hover) !important;
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
      background-color: var(--api-report-inline-bg) !important;
      border: 1px solid var(--api-report-inline-border) !important;
      color: var(--api-report-text) !important;

      &:hover, &:focus {
        border-color: rgba(59, 130, 246, 0.5) !important;
        background-color: var(--api-report-card-hover) !important;
      }
    }
  }
}
</style>
