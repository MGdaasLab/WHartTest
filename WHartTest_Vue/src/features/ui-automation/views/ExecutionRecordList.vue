<template>
  <div class="execution-record-list">
    <div class="page-header">
      <div class="search-box">
        <a-select
          v-model="filters.status"
          :placeholder="pageText.statusPlaceholder"
          allow-clear
          style="width: 120px; margin-right: 12px"
          @change="onSearch"
        >
          <a-option v-for="(_label, key) in STATUS_LABELS" :key="key" :value="Number(key)">{{ getStatusLabel(Number(key)) }}</a-option>
        </a-select>
        <a-select
          v-model="filters.trigger_type"
          :placeholder="pageText.triggerPlaceholder"
          allow-clear
          style="width: 120px; margin-right: 12px"
          @change="onSearch"
        >
          <a-option value="manual">{{ triggerLabels.manual }}</a-option>
          <a-option value="scheduled">{{ triggerLabels.scheduled }}</a-option>
          <a-option value="api">{{ triggerLabels.api }}</a-option>
        </a-select>
        <a-button type="outline" @click="onSearch">
          <template #icon><icon-refresh /></template>
          {{ pageText.refresh }}
        </a-button>
      </div>
    </div>

    <a-table
      :columns="columns"
      :data="recordData"
      :pagination="pagination"
      :loading="loading"
      :scroll="{ x: 1100 }"
      row-key="id"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
    >
      <template #status="{ record }">
        <a-tag :color="statusColors[record.status as ExecutionStatus]">
          {{ getStatusLabel(record.status as ExecutionStatus) }}
        </a-tag>
      </template>
      <template #trigger_type="{ record }">
        <a-tag :color="triggerColors[record.trigger_type]">{{ triggerLabels[record.trigger_type] || record.trigger_type }}</a-tag>
      </template>
      <template #duration="{ record }">
        <span v-if="record.duration != null">{{ record.duration.toFixed(2) }}s</span>
        <span v-else>-</span>
      </template>
      <template #start_time="{ record }">
        <span v-if="record.start_time">{{ formatTime(record.start_time) }}</span>
        <span v-else>-</span>
      </template>
      <template #operations="{ record }">
        <a-space :size="4">
          <a-button type="text" size="mini" @click="viewDetail(record)">
            <template #icon><icon-eye /></template>
            {{ pageText.details }}
          </a-button>
          <a-popconfirm :content="pageText.deleteConfirm" @ok="handleDelete(record.id)">
            <a-button type="text" size="mini" status="danger">
              <template #icon><icon-delete /></template>
              {{ pageText.delete }}
            </a-button>
          </a-popconfirm>
        </a-space>
      </template>
    </a-table>

    <a-drawer
      v-model:visible="drawerVisible"
      :title="pageText.drawerTitle"
      width="700px"
      unmount-on-close
    >
      <template v-if="currentRecord">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item :label="pageText.caseName">{{ currentRecord.test_case_name ?? `ID: ${currentRecord.test_case}` }}</a-descriptions-item>
          <a-descriptions-item :label="pageText.executor">{{ currentRecord.executor_name ?? '-' }}</a-descriptions-item>
          <a-descriptions-item :label="pageText.executionStatus">
            <a-tag :color="statusColors[currentRecord.status as ExecutionStatus]">
              {{ getStatusLabel(currentRecord.status as ExecutionStatus) }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item :label="pageText.triggerType">
            <a-tag :color="triggerColors[currentRecord.trigger_type]">{{ triggerLabels[currentRecord.trigger_type] || currentRecord.trigger_type }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item :label="pageText.startTime">{{ currentRecord.start_time ? formatTime(currentRecord.start_time) : '-' }}</a-descriptions-item>
          <a-descriptions-item :label="pageText.endTime">{{ currentRecord.end_time ? formatTime(currentRecord.end_time) : '-' }}</a-descriptions-item>
          <a-descriptions-item :label="pageText.duration">{{ currentRecord.duration != null ? `${currentRecord.duration.toFixed(2)}s` : '-' }}</a-descriptions-item>
          <a-descriptions-item :label="pageText.executionTrace">
            <a-button v-if="currentRecord.trace_path" type="primary" size="small" @click="viewTrace(currentRecord.id)">
              <template #icon><icon-eye /></template>
              {{ pageText.viewTrace }}
            </a-button>
            <span v-else>-</span>
          </a-descriptions-item>
        </a-descriptions>

        <template v-if="currentRecord.error_message">
          <a-divider>{{ pageText.errorInfo }}</a-divider>
          <a-alert class="record-error-alert" type="error" :title="formatDynamicText(currentRecord.error_message)" />
        </template>

        <template v-if="currentRecord.log">
          <a-divider>{{ pageText.executionLogs }}</a-divider>
          <pre class="log-content">{{ formatExecutionLog(currentRecord.log) }}</pre>
        </template>

        <template v-if="currentRecord.step_results?.length">
          <a-divider>{{ pageText.stepExecutionResults }}</a-divider>
          <a-collapse :default-active-key="[]">
            <a-collapse-item v-for="(step, idx) in currentRecord.step_results" :key="idx">
              <template #header>
                <div class="step-header">
                  <span>{{ pageText.step(idx + 1) }}<template v-if="getStepDescription(step)">: {{ getStepDescription(step) }}</template></span>
                  <a-tag :color="getStepStatusColor(step)" size="small" style="margin-left: 8px">
                    {{ getStepStatusText(step) }}
                  </a-tag>
                  <span v-if="getStepDuration(step)" class="step-duration">{{ getStepDuration(step) }}s</span>
                </div>
              </template>
              <div class="step-detail">
                <div v-if="getStepMessage(step)" class="step-message">
                  <a-alert class="step-message-alert" :type="getStepStatus(step) === 'failed' ? 'error' : 'info'" :title="formatDynamicText(getStepMessage(step))" />
                </div>
                <div v-if="getStepScreenshot(step)" class="step-screenshot">
                  <a-image :src="formatScreenshotUrl(getStepScreenshot(step))" width="100%" fit="contain" />
                </div>
                <div class="step-raw">
                  <a-collapse>
                    <a-collapse-item :header="pageText.rawData">
                      <pre class="step-result">{{ JSON.stringify(step, null, 2) }}</pre>
                    </a-collapse-item>
                  </a-collapse>
                </div>
              </div>
            </a-collapse-item>
          </a-collapse>
        </template>

        <template v-if="currentRecord.screenshots?.length">
          <a-divider>{{ pageText.executionScreenshots }}</a-divider>
          <a-image-preview-group>
            <a-space wrap>
              <a-image
                v-for="(img, idx) in currentRecord.screenshots"
                :key="idx"
                :src="img"
                width="120"
                height="80"
                fit="cover"
              />
            </a-space>
          </a-image-preview-group>
        </template>

        <template v-if="currentRecord.video_path">
          <a-divider>{{ pageText.executionVideo }}</a-divider>
          <video :src="currentRecord.video_path" controls style="max-width: 100%; max-height: 300px;" />
        </template>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { IconRefresh, IconEye, IconDelete } from '@arco-design/web-vue/es/icon'
import { Message } from '@arco-design/web-vue'
import { useAppI18n } from '@/composables/useAppI18n'
import { executionRecordApi } from '../api'
import type { UiExecutionRecord, ExecutionStatus } from '../types'
import { STATUS_LABELS, extractPaginationData, extractResponseData } from '../types'
import { useProjectStore } from '@/store/projectStore'

const router = useRouter()
const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)
const { isEnglish, tl } = useAppI18n()

const loading = ref(false)
const recordData = ref<UiExecutionRecord[]>([])
const drawerVisible = ref(false)
const currentRecord = ref<UiExecutionRecord | null>(null)

const pageText = computed(() => (
  isEnglish.value
    ? {
        statusPlaceholder: 'Status',
        triggerPlaceholder: 'Trigger type',
        refresh: 'Refresh',
        unknown: 'Unknown',
        details: 'Details',
        delete: 'Delete',
        deleteConfirm: 'Delete this execution record? Related screenshots, videos, and trace files will also be deleted.',
        drawerTitle: 'Execution record details',
        caseName: 'Case Name',
        executor: 'Executor',
        executionStatus: 'Execution status',
        triggerType: 'Trigger type',
        startTime: 'Start time',
        endTime: 'End time',
        duration: 'Duration',
        executionTrace: 'Execution trace',
        viewTrace: 'View Trace',
        errorInfo: 'Error information',
        executionLogs: 'Execution Logs',
        stepExecutionResults: 'Step execution results',
        step: (index: number) => `Step ${index}`,
        rawData: 'Raw data',
        executionScreenshots: 'Execution screenshots',
        executionVideo: 'Execution video',
        manual: 'Manual',
        scheduled: 'Scheduled',
        api: 'API Trigger',
        caseNameColumn: 'Case Name',
        executorColumn: 'Executor',
        statusColumn: 'Status',
        durationColumn: 'Duration',
        startTimeColumn: 'Start time',
        actionsColumn: 'Actions',
        deleteSuccess: 'Deleted successfully',
        deleteFailed: 'Delete failed',
        passed: 'Passed',
        failed: 'Failed',
        skipped: 'Skipped',
        success: 'Succeeded',
      }
    : {
        statusPlaceholder: '执行状态',
        triggerPlaceholder: '触发类型',
        refresh: '刷新',
        unknown: '未知',
        details: '详情',
        delete: '删除',
        deleteConfirm: '确定删除此执行记录？关联的截图、视频、Trace文件将一并删除。',
        drawerTitle: '执行记录详情',
        caseName: '用例名称',
        executor: '执行人',
        executionStatus: '执行状态',
        triggerType: '触发类型',
        startTime: '开始时间',
        endTime: '结束时间',
        duration: '执行时长',
        executionTrace: '执行追踪',
        viewTrace: '查看 Trace',
        errorInfo: '错误信息',
        executionLogs: '执行日志',
        stepExecutionResults: '步骤执行结果',
        step: (index: number) => `步骤 ${index}`,
        rawData: '原始数据',
        executionScreenshots: '执行截图',
        executionVideo: '执行录像',
        manual: '手动执行',
        scheduled: '定时执行',
        api: 'API 触发',
        caseNameColumn: '用例名称',
        executorColumn: '执行人',
        statusColumn: '状态',
        durationColumn: '时长',
        startTimeColumn: '开始时间',
        actionsColumn: '操作',
        deleteSuccess: '删除成功',
        deleteFailed: '删除失败',
        passed: '通过',
        failed: '失败',
        skipped: '跳过',
        success: '成功',
      }
))

const filters = reactive({
  status: undefined as number | undefined,
  trigger_type: undefined as string | undefined,
})
const pagination = reactive({ current: 1, pageSize: 10, total: 0, showTotal: true, showPageSize: true })

const statusColors: Record<ExecutionStatus | 4, string> = {
  0: 'gray',
  1: 'arcoblue',
  2: 'green',
  3: 'red',
  4: 'orange',
}

const triggerLabels = computed<Record<string, string>>(() => ({
  manual: pageText.value.manual,
  scheduled: pageText.value.scheduled,
  api: pageText.value.api,
}))

const triggerColors: Record<string, string> = {
  manual: 'arcoblue',
  scheduled: 'purple',
  api: 'cyan',
}

const getStatusLabel = (status?: number) => {
  if (status == null) {
    return pageText.value.unknown
  }
  return tl(STATUS_LABELS[status as ExecutionStatus] ?? pageText.value.unknown)
}

const columns = computed(() => [
  { title: 'ID', dataIndex: 'id', width: 70, align: 'center' as const },
  { title: pageText.value.caseNameColumn, dataIndex: 'test_case_name', ellipsis: true, tooltip: true, width: 180, align: 'center' as const },
  { title: pageText.value.executorColumn, dataIndex: 'executor_name', width: 100, align: 'center' as const },
  { title: pageText.value.statusColumn, slotName: 'status', width: 90, align: 'center' as const },
  { title: pageText.value.triggerType, slotName: 'trigger_type', width: 100, align: 'center' as const },
  { title: pageText.value.durationColumn, slotName: 'duration', width: 90, align: 'center' as const },
  { title: pageText.value.startTimeColumn, slotName: 'start_time', width: 160, align: 'center' as const },
  { title: pageText.value.actionsColumn, slotName: 'operations', width: 130, fixed: 'right' as const, align: 'center' as const },
])

const formatTime = (time: string) => {
  const d = new Date(time)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

type StepResult = Record<string, unknown>

const getStepStatus = (step: unknown) => ((step as StepResult)?.status as string) ?? 'unknown'
const getStepDescription = (step: unknown) => ((step as StepResult)?.description as string) ?? ''
const getStepStatusText = (step: unknown) => {
  const status = getStepStatus(step)
  const map: Record<string, string> = {
    passed: pageText.value.passed,
    failed: pageText.value.failed,
    skipped: pageText.value.skipped,
    success: pageText.value.success,
    succeeded: pageText.value.success,
    error: pageText.value.failed,
  }
  return map[status] ?? status
}
const getStepStatusColor = (step: unknown) => {
  const status = getStepStatus(step)
  const map: Record<string, string> = {
    passed: 'green',
    failed: 'red',
    skipped: 'gray',
    success: 'green',
    succeeded: 'green',
    error: 'red',
  }
  return map[status] ?? 'gray'
}
const getStepMessage = (step: unknown) => ((step as StepResult)?.message as string) ?? ''
const getStepDuration = (step: unknown) => {
  const d = (step as StepResult)?.duration as number | undefined
  return d != null ? d.toFixed(2) : ''
}
const getStepScreenshot = (step: unknown) => ((step as StepResult)?.screenshot as string) ?? ''

const formatDynamicText = (text?: string | null) => {
  if (!text) return ''
  return tl(text)
}

const formatExecutionLog = (log?: string | null) => {
  if (!log) return ''
  return log
    .split('\n')
    .map((line) => {
      const trimmed = line.trim()
      if (!trimmed) {
        return line
      }
      return line.replace(trimmed, tl(trimmed))
    })
    .join('\n')
}

const formatScreenshotUrl = (path: string) => {
  if (!path) return ''
  if (path.startsWith('data:')) return path
  if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('/media/')) return path
  const filename = path.split('/').pop() || path
  return `/media/ui_screenshots/${filename}`
}

const fetchRecords = async () => {
  if (!projectId.value) return
  loading.value = true
  try {
    const res = await executionRecordApi.list({
      project: projectId.value,
      status: filters.status,
      trigger_type: filters.trigger_type,
    })
    const { items, count } = extractPaginationData(res)
    recordData.value = items
    pagination.total = count
  } finally {
    loading.value = false
  }
}

const onSearch = () => {
  pagination.current = 1
  fetchRecords()
}

const onPageChange = (page: number) => {
  pagination.current = page
  fetchRecords()
}

const onPageSizeChange = (size: number) => {
  pagination.pageSize = size
  pagination.current = 1
  fetchRecords()
}

const viewDetail = async (record: UiExecutionRecord) => {
  currentRecord.value = record
  drawerVisible.value = true
  try {
    const res = await executionRecordApi.get(record.id)
    const detail = extractResponseData<UiExecutionRecord>(res)
    if (detail) {
      currentRecord.value = detail
    }
  } catch {
    // 静默失败，使用列表数据
  }
}

const viewTrace = (recordId: number) => {
  router.push({ name: 'TraceDetail', params: { id: recordId } })
}

const handleDelete = async (id: number) => {
  try {
    await executionRecordApi.delete(id)
    Message.success(pageText.value.deleteSuccess)
    fetchRecords()
  } catch {
    Message.error(pageText.value.deleteFailed)
  }
}

const refresh = () => fetchRecords()

defineExpose({ refresh })

watch(projectId, () => {
  if (projectId.value) {
    pagination.current = 1
    fetchRecords()
  }
}, { immediate: true })
</script>

<style scoped>
.execution-record-list {
  padding: 16px;
  background: var(--color-bg-2);
  border-radius: 8px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.search-box {
  display: flex;
  align-items: center;
}

.log-content {
  background: var(--color-fill-2);
  padding: 12px;
  border-radius: 4px;
  overflow: auto;
  max-height: 200px;
  font-size: 12px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-all;
}

.step-result {
  background: var(--color-fill-2);
  padding: 8px;
  border-radius: 4px;
  font-size: 12px;
  overflow: auto;
  max-height: 200px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.step-header {
  display: flex;
  align-items: center;
  min-width: 0;
}
.step-header > span:first-child {
  min-width: 0;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.step-duration {
  margin-left: auto;
  font-size: 12px;
  color: var(--color-text-3);
  flex-shrink: 0;
}
.step-detail {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.step-message {
  margin-bottom: 8px;
}
.record-error-alert :deep(.arco-alert-body),
.step-message-alert :deep(.arco-alert-body) {
  min-width: 0;
}
.record-error-alert :deep(.arco-alert-title),
.record-error-alert :deep(.arco-alert-content),
.step-message-alert :deep(.arco-alert-title),
.step-message-alert :deep(.arco-alert-content) {
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.step-screenshot {
  max-width: 100%;
  border-radius: 4px;
  overflow: hidden;
}
.step-raw {
  margin-top: 8px;
}
</style>
