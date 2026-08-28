<template>
  <div class="batch-record-list">
    <div class="page-header">
      <div class="search-box">
        <a-select
          v-model="filters.status"
          placeholder="执行状态"
          allow-clear
          style="width: 120px; margin-right: 12px"
          @change="onSearch"
        >
          <a-option v-for="(label, key) in BATCH_STATUS_LABELS" :key="key" :value="Number(key)">{{ label }}</a-option>
        </a-select>
        <a-button type="outline" @click="onSearch">
          <template #icon><icon-refresh /></template>
          刷新
        </a-button>
      </div>
    </div>

    <a-table
      :columns="columns"
      :data="recordData"
      :pagination="pagination"
      :loading="loading"
      :scroll="{ x: 1000 }"
      row-key="id"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
    >
      <template #status="{ record }">
        <a-tag :color="statusColors[record.status as BatchExecutionStatus]">
          {{ BATCH_STATUS_LABELS[record.status as BatchExecutionStatus] ?? '未知' }}
        </a-tag>
      </template>
      <template #progress="{ record }">
        <a-progress
          :percent="record.total_cases > 0 ? (record.passed_cases + record.failed_cases) / record.total_cases : 0"
          :status="getProgressStatus(record)"
          :show-text="false"
          size="small"
        />
        <span class="progress-text">{{ record.passed_cases + record.failed_cases }}/{{ record.total_cases }}</span>
      </template>
      <template #success_rate="{ record }">
        <span :style="{ color: record.success_rate >= 80 ? 'green' : record.success_rate >= 50 ? 'orange' : 'red' }">
          {{ record.success_rate?.toFixed(1) ?? 0 }}%
        </span>
      </template>
      <template #duration="{ record }">
        <span v-if="record.duration != null">{{ record.duration.toFixed(2) }}s</span>
        <span v-else>-</span>
      </template>
      <template #created_at="{ record }">
        <span v-if="record.created_at">{{ formatTime(record.created_at) }}</span>
        <span v-else>-</span>
      </template>
      <template #operations="{ record }">
        <a-space :size="4">
          <a-button type="text" size="mini" @click="viewDetail(record)">
            <template #icon><icon-eye /></template>
            详情
          </a-button>
          <a-popconfirm content="确定删除此批量执行记录？关联的执行记录将一并删除。" @ok="handleDelete(record.id)">
            <a-button type="text" size="mini" status="danger">
              <template #icon><icon-delete /></template>
              删除
            </a-button>
          </a-popconfirm>
        </a-space>
      </template>
    </a-table>

    <!-- 详情抽屉 -->
    <a-drawer
      v-model:visible="drawerVisible"
      title="批量执行详情"
      width="900px"
      unmount-on-close
    >
      <template v-if="currentRecord">
        <a-descriptions :column="2" bordered size="small">
          <a-descriptions-item label="批次名称">{{ currentRecord.name }}</a-descriptions-item>
          <a-descriptions-item label="执行人">{{ currentRecord.executor_name ?? '-' }}</a-descriptions-item>
          <a-descriptions-item label="执行状态">
            <a-tag :color="statusColors[currentRecord.status as BatchExecutionStatus]">
              {{ BATCH_STATUS_LABELS[currentRecord.status as BatchExecutionStatus] ?? '未知' }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="成功率">
            <span :style="{ color: (currentRecord.success_rate ?? 0) >= 80 ? 'green' : (currentRecord.success_rate ?? 0) >= 50 ? 'orange' : 'red' }">
              {{ currentRecord.success_rate?.toFixed(1) ?? 0 }}%
            </span>
          </a-descriptions-item>
          <a-descriptions-item label="用例统计">
            成功: {{ currentRecord.passed_cases }} / 失败: {{ currentRecord.failed_cases }} / 总计: {{ currentRecord.total_cases }}
          </a-descriptions-item>
          <a-descriptions-item label="执行时长">{{ currentRecord.duration?.toFixed(2) ?? '-' }}s</a-descriptions-item>
          <a-descriptions-item label="开始时间">{{ currentRecord.start_time ? formatTime(currentRecord.start_time) : '-' }}</a-descriptions-item>
          <a-descriptions-item label="结束时间">{{ currentRecord.end_time ? formatTime(currentRecord.end_time) : '-' }}</a-descriptions-item>
        </a-descriptions>

        <!-- 关联的执行记录列表 -->
        <a-divider>用例执行结果</a-divider>
        <a-table
          :columns="detailColumns"
          :data="currentRecord.execution_records ?? []"
          :pagination="false"
          :expandable="{ width: 30 }"
          size="small"
          row-key="id"
        >
          <template #status="{ record: r }">
            <a-tag :color="execStatusColors[r.status]">{{ STATUS_LABELS[r.status] ?? '未知' }}</a-tag>
          </template>
          <template #duration="{ record: r }">
            {{ r.duration?.toFixed(2) ?? '-' }}s
          </template>
          <template #error_message="{ record: r }">
            <span v-if="r.error_message" class="error-text">{{ r.error_message }}</span>
            <span v-else>-</span>
          </template>
          <template #expand-row="{ record: r }">
            <div class="expand-content">
              <!-- 步骤结果 -->
              <div v-if="r.step_results?.length" class="step-results">
                <div class="section-title">步骤执行详情</div>
                <a-table
                  :columns="stepColumns"
                  :data="r.step_results"
                  :pagination="false"
                  size="mini"
                  class="step-table"
                >
                  <template #step_no="{ rowIndex }">{{ rowIndex + 1 }}</template>
                  <template #step_status="{ record: step }">
                    <a-tag :color="step.status === 'success' ? 'green' : step.status === 'failed' ? 'red' : 'orange'" size="small">
                      {{ step.status === 'success' ? '成功' : step.status === 'failed' ? '失败' : '跳过' }}
                    </a-tag>
                  </template>
                  <template #step_duration="{ record: step }">
                    {{ step.duration?.toFixed(2) ?? '-' }}s
                  </template>
                  <template #step_screenshot="{ record: step }">
                    <a-image
                      v-if="step.screenshot"
                      :src="step.screenshot"
                      width="60"
                      height="40"
                      fit="cover"
                      :preview="true"
                    />
                    <span v-else>-</span>
                  </template>
                </a-table>
              </div>
              <div v-else class="no-steps">暂无步骤详情</div>

              <!-- 错误信息 -->
              <div v-if="r.error_message" class="error-section">
                <div class="section-title">错误信息</div>
                <div class="error-content">{{ r.error_message }}</div>
              </div>
            </div>
          </template>
        </a-table>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { IconRefresh, IconEye, IconDelete } from '@arco-design/web-vue/es/icon'
import { Message } from '@arco-design/web-vue'
import { batchRecordApi } from '../api'
import type { UiBatchExecutionRecord, BatchExecutionStatus, ExecutionStatus } from '../types'
import { BATCH_STATUS_LABELS, STATUS_LABELS, extractPaginationData, extractResponseData } from '../types'
import { useProjectStore } from '@/store/projectStore'

const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)

const loading = ref(false)
const recordData = ref<UiBatchExecutionRecord[]>([])
const drawerVisible = ref(false)
const currentRecord = ref<UiBatchExecutionRecord | null>(null)

const filters = reactive({
  status: undefined as number | undefined,
})
const pagination = reactive({ current: 1, pageSize: 10, total: 0, showTotal: true, showPageSize: true })

const statusColors: Record<BatchExecutionStatus, string> = {
  0: 'gray',
  1: 'arcoblue',
  2: 'green',
  3: 'orange',
  4: 'red',
}

const execStatusColors: Record<ExecutionStatus | 4, string> = {
  0: 'gray',
  1: 'arcoblue',
  2: 'green',
  3: 'red',
  4: 'orange',
}

const columns = [
  { title: 'ID', dataIndex: 'id', width: 70, align: 'center' as const },
  { title: '批次名称', dataIndex: 'name', ellipsis: true, tooltip: true, width: 200 },
  { title: '状态', slotName: 'status', width: 100, align: 'center' as const },
  { title: '执行进度', slotName: 'progress', width: 150, align: 'center' as const },
  { title: '成功率', slotName: 'success_rate', width: 80, align: 'center' as const },
  { title: '时长', slotName: 'duration', width: 90, align: 'center' as const },
  { title: '创建时间', slotName: 'created_at', width: 170, align: 'center' as const },
  { title: '操作', slotName: 'operations', width: 160, fixed: 'right' as const, align: 'center' as const },
]

const detailColumns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '用例名称', dataIndex: 'test_case_name', ellipsis: true },
  { title: '状态', slotName: 'status', width: 80 },
  { title: '时长', slotName: 'duration', width: 80 },
  { title: '错误信息', slotName: 'error_message', ellipsis: true, width: 200 },
]

const stepColumns = [
  { title: '步骤', slotName: 'step_no', width: 60, align: 'center' as const },
  { title: '描述', dataIndex: 'description', ellipsis: true },
  { title: '状态', slotName: 'step_status', width: 70 },
  { title: '时长', slotName: 'step_duration', width: 70 },
  { title: '截图', slotName: 'step_screenshot', width: 80 },
  { title: '消息', dataIndex: 'message', ellipsis: true },
]

const formatTime = (time: string) => {
  const d = new Date(time)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

const getProgressStatus = (record: UiBatchExecutionRecord) => {
  if (record.status === 1) return 'normal'
  if (record.status === 2) return 'success'
  if (record.status === 4) return 'danger'
  return 'warning'
}

const fetchRecords = async () => {
  if (!projectId.value) return
  loading.value = true
  try {
    const res = await batchRecordApi.list({ project: projectId.value, status: filters.status })
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

const viewDetail = async (record: UiBatchExecutionRecord) => {
  currentRecord.value = record
  drawerVisible.value = true
  try {
    const res = await batchRecordApi.get(record.id)
    const data = extractResponseData<UiBatchExecutionRecord>(res)
    if (data) {
      currentRecord.value = data
    }
  } catch {
    // 静默失败
  }
}

const handleDelete = async (id: number) => {
  try {
    await batchRecordApi.delete(id)
    Message.success('删除成功')
    fetchRecords()
  } catch {
    Message.error('删除失败')
  }
}

const refresh = () => fetchRecords()

defineExpose({ refresh })

// 监听项目变化，重新加载数据
watch(projectId, () => {
  if (projectId.value) {
    pagination.current = 1
    fetchRecords()
  }
}, { immediate: true })
</script>

<style scoped>
.batch-record-list {
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

.progress-text {
  margin-left: 8px;
  font-size: 12px;
  color: var(--color-text-3);
}

.error-text {
  color: rgb(var(--red-6));
  font-size: 12px;
}

.expand-content {
  padding: 12px 16px;
  background: var(--color-fill-1);
  border-radius: 4px;
}

.section-title {
  font-weight: 500;
  margin-bottom: 8px;
  color: var(--color-text-2);
}

.step-table {
  background: #fff;
  border-radius: 4px;
}

.no-steps {
  color: var(--color-text-3);
  font-size: 13px;
}

.error-section {
  margin-top: 12px;
}

.error-content {
  background: rgb(var(--red-1));
  color: rgb(var(--red-6));
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
