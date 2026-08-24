<template>
  <div class="api-testreports-panel h-full flex flex-col gap-4 p-4" :class="isDarkTheme ? 'api-testreports--dark' : 'api-testreports--light'">
    <!-- 搜索区域 -->
    <div class="panel-shell rounded-lg px-6 py-5 flex justify-between items-center">
      <div class="flex items-center gap-4">
        <a-input-search
          v-model="searchQuery"
          placeholder="搜索报告名称、用例名称或接口名称"
          class="w-64"
          allow-clear
          @search="handleSearch"
          @press-enter="handleSearch"
          @clear="handleSearch"
        />
        <a-select
          v-model="filterReportType"
          placeholder="用例类型"
          allow-clear
          @change="handleFilterChange"
          class="w-32"
        >
          <a-option value="testcase">场景用例</a-option>
          <a-option value="interface_case">接口用例</a-option>
        </a-select>
        <a-select
          v-model="filterStatus"
          placeholder="执行状态"
          allow-clear
          @change="handleFilterChange"
          class="w-32"
        >
          <a-option value="success">成功</a-option>
          <a-option value="failure">失败</a-option>
          <a-option value="error">错误</a-option>
        </a-select>
      </div>
    </div>

    <!-- 表格区域 -->
    <div class="panel-shell flex-1 overflow-hidden flex items-center justify-center">
      <a-spin :loading="loading" dot class="h-full w-full">
        <!-- 未选择项目的空状态 -->
        <div v-if="!currentProjectId" class="h-full w-full flex flex-col items-center justify-center p-8 text-center">
          <div class="empty-icon text-6xl mb-6">
            <icon-apps class="opacity-50" />
          </div>
          <h2 class="empty-title text-2xl font-medium mb-2">请先选择项目</h2>
          <p class="empty-description mb-8 text-center max-w-md">
            测试报告需要基于项目查看，请先从项目管理中选择一个项目
          </p>
          <a-button type="primary" size="large" @click="router.push({ name: 'ProjectManagement' })">
            选择项目
          </a-button>
        </div>
        
        <!-- 数据为空的提示 -->
        <div v-else-if="reports.length === 0 && !loading" class="h-full w-full flex flex-col items-center justify-center p-8 text-center">
          <div class="empty-icon text-6xl mb-6">
            <icon-file class="opacity-50" />
          </div>
          <h2 class="empty-title text-2xl font-medium mb-2">暂无测试报告</h2>
          <p class="empty-description mb-8 text-center max-w-md">
            当前项目尚未生成任何测试报告，请先执行测试用例
          </p>
        </div>
        
        <div v-else class="h-full w-full">
          <div class="table-container">
          <a-table
            :data="reports"
            :loading="loading"
            :pagination="false"
            :scroll="{ y: '100%' }"
            class="custom-table"
          >
            <template #columns>
              <a-table-column title="报告名称" data-index="name" :width="300" align="center">
                <template #cell="{ record }">
                  <div class="flex items-center justify-center gap-2">
                    <icon-file class="text-blue-500 flex-shrink-0" />
                    <a-link @click="viewReport(record)" class="report-link truncate">{{ record.name }}</a-link>
                  </div>
                </template>
              </a-table-column>
              <a-table-column title="用例类型" data-index="report_type" :width="110" align="center">
                <template #cell="{ record }">
                  <a-tag :color="getReportTypeColor(record.report_type)" size="small">
                    {{ getReportTypeText(record.report_type) }}
                  </a-tag>
                </template>
              </a-table-column>
              <a-table-column title="用例名称" data-index="testcase_name" :width="250" align="center">
                <template #cell="{ record }">
                  <div class="report-case-cell flex items-center justify-center gap-2">
                    <icon-code class="report-row-icon" />
                    <div class="report-case-text">
                      <div class="report-muted-text truncate">{{ record.testcase_name }}</div>
                      <div v-if="record.interface_name" class="report-subtle-text truncate">{{ record.interface_name }}</div>
                    </div>
                  </div>
                </template>
              </a-table-column>
              <a-table-column title="状态" data-index="status" align="center">
                <template #cell="{ record }">
                  <a-tag :color="getStatusColor(record.status)">
                    {{ getStatusText(record.status) }}
                  </a-tag>
                </template>
              </a-table-column>
              <a-table-column title="执行结果" align="center" :width="200">
                <template #cell="{ record }">
                  <div class="execution-results-cell flex items-center justify-center">
                    <div class="execution-results-item text-center">
                      <div class="text-sm font-medium text-green-500">{{ record.success_count }}</div>
                      <div class="execution-results-label text-xs report-subtle-text">成功</div>
                    </div>
                    <div class="execution-results-item text-center">
                      <div class="text-sm font-medium text-red-500">{{ record.fail_count }}</div>
                      <div class="execution-results-label text-xs report-subtle-text">失败</div>
                    </div>
                    <div class="execution-results-item text-center">
                      <div class="text-sm font-medium text-orange-500">{{ record.error_count }}</div>
                      <div class="execution-results-label text-xs report-subtle-text">错误</div>
                    </div>
                  </div>
                </template>
              </a-table-column>
              <a-table-column title="成功率" data-index="success_rate" align="center">
                <template #cell="{ record }">
                  <a-progress
                    :percent="Number(record.success_rate || 0)"
                    size="small"
                    :stroke-width="4"
                    :color="getProgressColor(Number(record.success_rate || 0))"
                  />
                </template>
              </a-table-column>
              <a-table-column title="执行时间" data-index="start_time" :width="180" align="center">
                <template #cell="{ record }">
                  <span class="report-muted-text">{{ formatDateTime(record.start_time) }}</span>
                </template>
              </a-table-column>
              <a-table-column title="执行时长" data-index="duration" align="center">
                <template #cell="{ record }">
                  <span class="report-muted-text">{{ formatDuration(record.duration) }}</span>
                </template>
              </a-table-column>
              <a-table-column title="执行环境" data-index="environment_name" align="center">
                <template #cell="{ record }">
                  <a-tag v-if="record.environment_name" color="arcoblue" size="small">{{ record.environment_name }}</a-tag>
                  <span v-else class="report-subtle-text">-</span>
                </template>
              </a-table-column>
              <a-table-column title="执行人" data-index="executed_by_name" align="center">
                <template #cell="{ record }">
                  <div class="flex items-center justify-center gap-1">
                    <icon-user class="report-row-icon" />
                    <span class="report-muted-text">{{ record.executed_by_name }}</span>
                  </div>
                </template>
              </a-table-column>
            </template>
          </a-table>
          </div>
        </div>
      </a-spin>
    </div>

    <!-- 分页区域 -->
    <div class="panel-shell px-6 py-5">
      <a-pagination
        v-model:current="pagination.current"
        v-model:page_size="pagination.page_size"
        :total="pagination.total"
        show-total
        show-jumper
        show-page-size
        class="flex justify-end"
        @change="onPageChange"
        @page-size-change="onPageSizeChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { getTestReports } from '../../services/testReportService'
import { toArray } from '../../services/responseHelpers'
import type { ReportListItem, ReportType } from '../../services/testReportService'
import { formatDateTime, formatDuration } from '@/utils/formatters'
import { useProjectStore } from '@/store/projectStore'
import { useThemeStore } from '@/store/themeStore'
import { 
  IconFile, 
  IconCode,
  IconUser,
  IconApps,
} from '@arco-design/web-vue/es/icon'

const router = useRouter()
const projectStore = useProjectStore()
const themeStore = useThemeStore()
const reports = ref<ReportListItem[]>([])
const loading = ref(false)
const searchQuery = ref('')
const filterReportType = ref<ReportType | ''>('')
const filterStatus = ref('')
const isDarkTheme = computed(() => themeStore.isBlack)
const REPORTS_TAB_QUERY = { tab: 'reports', returnTo: 'reports' } as const

// 获取当前项目ID
const currentProjectId = computed(() => {
  return projectStore.currentProject?.id || null
})

const toReportList = (results: unknown) => {
  return toArray(results)
}

const pagination = ref({
  total: 0,
  current: 1,
  page_size: 10,
  showTotal: true,
  showJumper: true,
  showPageSize: true,
})

const getStatusColor = (status: string) => {
  const statusMap: Record<string, string> = {
    success: 'green',
    failure: 'red',
    error: 'orange',
  }
  return statusMap[status] || 'gray'
}

const getStatusText = (status: string) => {
  const statusMap: Record<string, string> = {
    success: '成功',
    failure: '失败',
    error: '错误',
  }
  return statusMap[status] || '未知'
}

const getReportTypeText = (type?: ReportType) => {
  const typeMap: Record<ReportType, string> = {
    testcase: '场景用例',
    interface_case: '接口用例',
  }
  return type ? typeMap[type] : '未知'
}

const getReportTypeColor = (type?: ReportType) => {
  const typeMap: Record<ReportType, string> = {
    testcase: 'purple',
    interface_case: 'arcoblue',
  }
  return type ? typeMap[type] : 'gray'
}

const getProgressColor = (rate: number) => {
  if (rate >= 0.9) return '#00B42A'
  if (rate >= 0.7) return '#FF7D00'
  return '#F53F3F'
}

const fetchReports = async () => {
  // 如果当前没有选择项目，则返回空列表
  if (!currentProjectId.value) {
    reports.value = []
    pagination.value.total = 0
    return
  }
  
  try {
    loading.value = true
    const response = await getTestReports({
      page: pagination.value.current,
      page_size: pagination.value.page_size,
      search: searchQuery.value,
      report_type: filterReportType.value || undefined,
      status: filterStatus.value || undefined,
      project: currentProjectId.value, // 添加项目ID过滤
    })
    reports.value = toReportList(response.data?.results ?? response.data)
    pagination.value.total = response.data?.count || 0
  } catch (error) {
    Message.error('获取测试报告列表失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.value.current = 1
  fetchReports()
}

const handleFilterChange = () => {
  pagination.value.current = 1
  fetchReports()
}

const onPageChange = (current: number) => {
  pagination.value.current = current
  fetchReports()
}

const onPageSizeChange = (size: number) => {
  pagination.value.page_size = size
  pagination.value.current = 1
  fetchReports()
}

const viewReport = (report: ReportListItem) => {
  if (report.report_type === 'interface_case') {
    router.push({
      name: 'ApiInterfaceCaseReportDetail',
      params: { id: report.id },
      query: REPORTS_TAB_QUERY
    })
    return
  }

  router.push({
    name: 'ApiTestReportDetail',
    params: { id: report.id },
    query: REPORTS_TAB_QUERY
  })
}

// 监听当前项目ID的变化，在变化时重新获取测试报告列表
watch(currentProjectId, (newProjectId, oldProjectId) => {
  if (newProjectId !== oldProjectId) {
    // 重置过滤条件
    searchQuery.value = ''
    filterReportType.value = ''
    filterStatus.value = ''
    
    // 重置分页
    pagination.value.current = 1
    pagination.value.page_size = 10
    
    // 重新获取测试报告
    fetchReports()
  }
}, { immediate: false })

onMounted(() => {
  fetchReports()
})

// 组件卸载时清理资源
onUnmounted(() => {
  // 如果有需要清理的资源，可以在这里添加
})
</script>

<style lang="postcss" scoped>
@reference "tailwindcss";
.api-testreports-panel {
  min-height: 0;
  --tr-panel-bg: color-mix(in srgb, var(--theme-card-bg) 92%, var(--theme-page-bg) 8%);
  --tr-panel-border: rgba(148, 163, 184, 0.16);
  --tr-panel-shadow: 0 14px 30px rgba(15, 23, 42, 0.08);
  --tr-input-bg: #ffffff;
  --tr-input-border: rgba(148, 163, 184, 0.18);
  --tr-input-bg-hover: color-mix(in srgb, var(--theme-card-bg) 88%, var(--theme-page-bg) 12%);
  --tr-table-header-bg: color-mix(in srgb, var(--theme-card-bg) 76%, var(--theme-page-bg) 24%);
  --tr-row-hover-bg: rgba(15, 23, 42, 0.05);
  --tr-text: var(--theme-text);
  --tr-text-muted: var(--theme-text-secondary);
  --tr-text-subtle: var(--theme-text-tertiary);
  --tr-link: var(--theme-accent);
  --tr-link-hover: var(--theme-accent-hover);
}

.api-testreports--dark {
  --tr-panel-bg: rgba(31, 41, 55, 0.58);
  --tr-panel-border: rgba(148, 163, 184, 0.12);
  --tr-panel-shadow: 0 18px 32px rgba(2, 6, 23, 0.28);
  --tr-input-bg: rgba(30, 41, 59, 0.5);
  --tr-input-border: rgba(148, 163, 184, 0.1);
  --tr-input-bg-hover: rgba(30, 41, 59, 0.72);
  --tr-table-header-bg: rgba(30, 41, 59, 0.5);
  --tr-row-hover-bg: rgba(30, 41, 59, 0.5);
}

.panel-shell {
  background: var(--tr-panel-bg);
  border: 1px solid var(--tr-panel-border);
  box-shadow: var(--tr-panel-shadow);
}

.table-container {
  @apply h-full w-full flex flex-col min-h-0;
}

.custom-table {
  @apply h-full;
}

.custom-table :deep(.arco-table-container) {
  @apply h-full;
}

.custom-table :deep(.arco-table-content) {
  @apply h-full;
}

.custom-table :deep(.arco-table-body) {
  @apply h-full;
}

.custom-table :deep(.arco-table-header) {
  position: sticky;
  top: 0;
  z-index: 2;
}

.custom-table :deep(.arco-spin) {
  @apply h-full flex flex-col;
}

.custom-table :deep(.arco-spin-children) {
  @apply h-full flex flex-col;
}

.custom-table :deep(.arco-table-td) {
  background-color: transparent !important;
  border-bottom: 1px solid var(--tr-panel-border) !important;
  color: var(--tr-text-muted) !important;
  text-align: center !important;
}

.custom-table :deep(.arco-table-tr) {
  background-color: transparent !important;
}

.custom-table :deep(.arco-table-tr:hover) {
  background-color: var(--tr-row-hover-bg) !important;
}

/* 分页样式 */
:deep(.arco-pagination) {
  .arco-pagination-item {
    border-radius: 6px !important;
    color: var(--tr-text-subtle) !important;
    background-color: transparent !important;
    
    &:hover {
      color: var(--tr-link-hover) !important;
      background-color: rgba(var(--theme-accent-rgb), 0.1) !important;
    }
    
    &.arco-pagination-item-active {
      background-color: rgba(var(--theme-accent-rgb), 0.14) !important;
      color: var(--tr-link-hover) !important;
    }
  }

  .arco-pagination-jumper {
    .arco-input {
      border-radius: 6px !important;
      background-color: var(--tr-input-bg) !important;
      border-color: var(--tr-input-border) !important;
      color: var(--tr-text) !important;

      &:hover, &:focus {
        border-color: rgba(var(--theme-accent-rgb), 0.42) !important;
        background-color: var(--tr-input-bg-hover) !important;
      }
    }
  }

  .arco-pagination-total {
    color: var(--tr-text-subtle) !important;
  }
}

/* 搜索框样式 */
:deep(.arco-input-wrapper),
:deep(.arco-select-view) {
  background-color: var(--tr-input-bg) !important;
  border-color: var(--tr-input-border) !important;
  color: var(--tr-text) !important;

  &:hover, &:focus-within {
    border-color: rgba(var(--theme-accent-rgb), 0.42) !important;
    background-color: var(--tr-input-bg-hover) !important;
  }

  .arco-input {
    color: var(--tr-text) !important;
  }

  .arco-input::placeholder {
    color: var(--tr-text-subtle) !important;
  }

  .arco-input-prefix,
  .arco-input-suffix,
  .arco-select-view-placeholder,
  .arco-select-view-suffix {
    color: var(--tr-text-subtle) !important;
  }
}

/* 表格样式 */
.custom-table :deep(.arco-table-th) {
  background-color: var(--tr-table-header-bg) !important;
  border-bottom: 1px solid var(--tr-panel-border) !important;
  color: var(--tr-text) !important;
  font-weight: 500 !important;
  text-align: center !important;
}

.report-link {
  color: var(--tr-link) !important;
}

.report-link:hover {
  color: var(--tr-link-hover) !important;
}

.report-row-icon,
.report-subtle-text,
.empty-icon,
.empty-description {
  color: var(--tr-text-subtle);
}

.report-muted-text {
  color: var(--tr-text-muted);
}

.execution-results-cell {
  gap: 12px;
  flex-wrap: nowrap;
  min-width: 176px;
}

.execution-results-item {
  min-width: 44px;
}

.execution-results-label {
  white-space: nowrap;
  line-height: 1.2;
}

.report-case-cell {
  min-width: 0;
}

.report-case-text {
  min-width: 0;
  max-width: 190px;
}

.empty-title {
  color: var(--tr-text);
}
</style> 
