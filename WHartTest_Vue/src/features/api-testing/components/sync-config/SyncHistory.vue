<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { IconRefresh } from '@arco-design/web-vue/es/icon'
import { syncApi, type SyncHistory } from '../../services/syncService'
import { normalizeListPayload } from '../../services/responseHelpers'
import type { TableColumnData } from '@arco-design/web-vue'
import { useAppI18n } from '@/composables/useAppI18n'
import { useProjectStore } from '@/store/projectStore'
import { useThemeStore } from '@/store/themeStore'
const projectStore = useProjectStore()
const themeStore = useThemeStore()
const { isEnglish } = useAppI18n()
const isDarkTheme = computed(() => themeStore.isBlack)
const loading = ref(false)
const histories = ref<SyncHistory[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const showDetailModal = ref(false)
const currentHistory = ref<SyncHistory | null>(null)
const diffFields = ref<Array<{ key: string; oldValue: any; newValue: any; changed: boolean }>>([])
const showUnchanged = ref(false)

const text = computed(() => isEnglish.value
  ? {
      index: 'No.',
      configName: 'Config Name',
      syncFields: 'Sync Fields',
      syncStatus: 'Sync Status',
      createdInfo: 'Created Info',
      actions: 'Actions',
      selectProjectFirst: 'Please select a project first',
      fetchSyncHistoryFailed: 'Failed to fetch sync history',
      fetchHistoryDetailFailed: 'Failed to fetch history details',
      confirmRollbackTitle: 'Confirm Rollback',
      historyRecord: 'this history record',
      confirmRollbackContent: (name: string) => `Are you sure you want to roll back to "${name}"? This action may affect the current configuration.`,
      confirmRollback: 'Confirm Rollback',
      cancel: 'Cancel',
      rollbackSuccess: 'Rollback successful',
      rollbackFailed: 'Rollback failed',
      notSet: 'Not set',
      refresh: 'Refresh',
      success: 'Succeeded',
      failed: 'Failed',
      operator: 'Operator:',
      time: 'Time:',
      details: 'Details',
      rollback: 'Roll Back',
      syncHistoryDetail: 'Sync History Details',
      operatorName: 'Operator',
      errorMessage: 'Error Message',
      totalFields: (count: number) => `${count} fields total`,
      noSyncFields: 'No sync fields',
      dataChangeDetails: 'Data Change Details',
      hideUnchangedFields: 'Hide unchanged fields',
      showUnchangedFields: 'Show unchanged fields',
      fieldName: 'Field Name',
      beforeChange: 'Before Change',
      afterChange: 'After Change',
    }
  : {
      index: '序号',
      configName: '配置名称',
      syncFields: '同步字段',
      syncStatus: '同步状态',
      createdInfo: '创建信息',
      actions: '操作',
      selectProjectFirst: '请先选择项目',
      fetchSyncHistoryFailed: '获取同步历史失败',
      fetchHistoryDetailFailed: '获取历史详情失败',
      confirmRollbackTitle: '确认回滚',
      historyRecord: '此历史记录',
      confirmRollbackContent: (name: string) => `确定要回滚到"${name}"吗？此操作可能影响当前配置。`,
      confirmRollback: '确认回滚',
      cancel: '取消',
      rollbackSuccess: '回滚成功',
      rollbackFailed: '回滚失败',
      notSet: '未设置',
      refresh: '刷新',
      success: '成功',
      failed: '失败',
      operator: '操作者：',
      time: '时间：',
      details: '详情',
      rollback: '回滚',
      syncHistoryDetail: '同步历史详情',
      operatorName: '操作人',
      errorMessage: '错误信息',
      totalFields: (count: number) => `共 ${count} 个字段`,
      noSyncFields: '暂无同步字段',
      dataChangeDetails: '数据变更详情',
      hideUnchangedFields: '收起未变更字段',
      showUnchangedFields: '显示未变更字段',
      fieldName: '字段名称',
      beforeChange: '变更前',
      afterChange: '变更后',
    }
)

const columns = computed<TableColumnData[]>(() => [
  {
    title: text.value.index,
    width: 80,
    align: 'center',
    slotName: 'index'
  },
  {
    title: text.value.configName,
    slotName: 'config_name'
  },
  {
    title: text.value.syncFields,
    slotName: 'sync_fields'
  },
  {
    title: text.value.syncStatus,
    width: isEnglish.value ? 120 : 100,
    slotName: 'status'
  },
  {
    title: text.value.createdInfo,
    slotName: 'created_info'
  },
  {
    title: text.value.actions,
    width: isEnglish.value ? 120 : 100,
    slotName: 'operations'
  }
])

const fieldDescriptions = computed<Record<string, string>>(() => isEnglish.value
  ? {
      name: 'Config Name',
      description: 'Config Description',
      status: 'Status',
      created_at: 'Created At',
      updated_at: 'Updated At',
      method: 'Request Method',
      url: 'Request URL',
      headers: 'Headers',
      params: 'Query Params',
      body: 'Request Body',
      setup_hooks: 'Setup Hooks',
      teardown_hooks: 'Teardown Hooks',
      variables: 'Variables',
      validators: 'Validators',
      extract: 'Extract Variables',
      request_type: 'Request Type',
      timeout: 'Timeout',
      verify: 'SSL Verification',
      allow_redirects: 'Allow Redirects',
      base_url: 'Base URL',
      json: 'JSON Data',
      data: 'Form Data',
      files: 'Files',
      auth: 'Auth Info',
      cookies: 'Cookies',
      proxies: 'Proxy Settings',
      env: 'Environment Variables',
      export: 'Export Variables',
      validate: 'Validation Rules',
      retry_times: 'Retry Count',
      retry_interval: 'Retry Interval',
      weight: 'Weight',
      priority: 'Priority',
      skip: 'Skip',
      times: 'Execution Count'
    }
  : {
      name: '配置名称',
      description: '配置描述',
      status: '状态',
      created_at: '创建时间',
      updated_at: '更新时间',
      method: '请求方法',
      url: '请求地址',
      headers: '请求头',
      params: '查询参数',
      body: '请求体',
      setup_hooks: '前置钩子',
      teardown_hooks: '后置钩子',
      variables: '变量定义',
      validators: '断言规则',
      extract: '提取变量',
      request_type: '请求类型',
      timeout: '超时时间',
      verify: 'SSL验证',
      allow_redirects: '允许重定向',
      base_url: '基础URL',
      json: 'JSON数据',
      data: '表单数据',
      files: '文件数据',
      auth: '认证信息',
      cookies: 'Cookie信息',
      proxies: '代理设置',
      env: '环境变量',
      export: '导出变量',
      validate: '验证规则',
      retry_times: '重试次数',
      retry_interval: '重试间隔',
      weight: '权重',
      priority: '优先级',
      skip: '是否跳过',
      times: '执行次数'
    }
)

const fetchHistories = async () => {
  if (!projectStore.currentProject?.id) {
    Message.error(text.value.selectProjectFirst)
    return
  }

  try {
    loading.value = true
    const response = await syncApi.getHistories({
      project_id: projectStore.currentProject.id,
      page: currentPage.value,
      page_size: pageSize.value
    })

    const responseData = response.data
    const normalized = normalizeListPayload<SyncHistory>(responseData)

    if (
      normalized.results.length > 0
      || (responseData && typeof responseData === 'object' && 'results' in (responseData as any))
    ) {
      histories.value = normalized.results
      total.value = normalized.count
    } else if (Array.isArray((responseData as any)?.histories)) {
      histories.value = (responseData as any).histories
      total.value = Number((responseData as any).total || histories.value.length)
    } else {
      histories.value = []
      total.value = 0
    }
  } catch (error) {
    Message.error(text.value.fetchSyncHistoryFailed)
    console.error(error)
    histories.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

const handlePageChange = (page: number) => {
  currentPage.value = page
  fetchHistories()
}

const handlePageSizeChange = (size: number) => {
  pageSize.value = size
  currentPage.value = 1
  fetchHistories()
}

const handleViewDetail = async (record: SyncHistory) => {
  try {
    loading.value = true
    const response = await syncApi.getHistoryDetail(record.id)
    currentHistory.value = response.data
    processDiffData() // 处理数据对比
    showDetailModal.value = true
  } catch (error) {
    Message.error(text.value.fetchHistoryDetailFailed)
    console.error(error)
  } finally {
    loading.value = false
  }
}

const handleRollback = async (record: SyncHistory) => {
  const configName = record.sync_config_info?.name || record.config?.name || text.value.historyRecord
  
  Modal.warning({
    title: text.value.confirmRollbackTitle,
    content: text.value.confirmRollbackContent(configName),
    okText: text.value.confirmRollback,
    cancelText: text.value.cancel,
    async onOk() {
      try {
        loading.value = true
        await syncApi.rollbackHistory(record.id)
        Message.success(text.value.rollbackSuccess)
        await fetchHistories()
      } catch (error) {
        Message.error(text.value.rollbackFailed)
        console.error(error)
      } finally {
        loading.value = false
      }
    }
  })
}

// 处理数据对比
const processDiffData = () => {
  if (!currentHistory.value) return
  
  const oldData = currentHistory.value.old_data || {}
  const newData = currentHistory.value.new_data || {}
  const allKeys = new Set([...Object.keys(oldData), ...Object.keys(newData)])
  
  diffFields.value = Array.from(allKeys).map(key => {
    const oldValue = oldData[key]
    const newValue = newData[key]
    return {
      key,
      oldValue,
      newValue,
      changed: JSON.stringify(oldValue) !== JSON.stringify(newValue)
    }
  }).sort((a, b) => {
    // 把变更的字段排在前面
    if (a.changed && !b.changed) return -1
    if (!a.changed && b.changed) return 1
    return a.key.localeCompare(b.key)
  })
}

// 格式化值的显示
const formatValue = (value: any): string => {
  if (value === undefined) return text.value.notSet
  if (value === null) return 'null'
  if (typeof value === 'object') {
    try {
      const formatted = JSON.stringify(value, null, 1)
        .split('\n')
        .map((line, index) => {
          const indentMatch = line.match(/^(\s*)/)
          const indent = indentMatch ? indentMatch[1].length : 0
          
          // 处理键值对行
          if (line.includes(':')) {
            const [key, ...rest] = line.split(':')
            const value = rest.join(':')
            return `${' '.repeat(indent)}<span class="text-blue-400">${key.replace(/[",]/g, '')}</span>:${value}`
          }
          
          // 处理数组项
          if (line.trim().startsWith('"')) {
            return `${' '.repeat(indent)}<span class="text-green-400">${line}</span>`
          }
          
          // 处理数字
          if (/^(\s*)-?\d+/.test(line)) {
            return `${' '.repeat(indent)}<span class="text-yellow-400">${line}</span>`
          }
          
          // 处理布尔值和 null
          if (/true|false|null/.test(line)) {
            return `${' '.repeat(indent)}<span class="text-purple-400">${line}</span>`
          }
          
          // 处理括号和逗号
          return line.replace(/[{}\[\],]/g, match => `<span class="text-gray-500">${match}</span>`)
        })
        .join('\n')
      return formatted
    } catch (e) {
      return String(value)
    }
  }
  return String(value)
}

// 获取字段说明
const getFieldDescription = (key: string): string => {
  return fieldDescriptions.value[key] || key
}

watch(() => projectStore.currentProject?.id, (newProjectId: number | undefined) => {
  if (newProjectId) {
    currentPage.value = 1
    fetchHistories()
  } else {
    histories.value = []
    total.value = 0
  }
})

onMounted(() => {
  if (projectStore.currentProject?.id) {
    fetchHistories()
  }
})
</script>

<template>
  <div class="sync-history" :class="isDarkTheme ? 'sync-history--dark' : 'sync-history--light'">
    <div class="flex justify-end mb-6">
      <a-button type="outline" :loading="loading" @click="fetchHistories">
        <template #icon>
          <icon-refresh />
        </template>
        {{ text.refresh }}
      </a-button>
    </div>

    <a-table
      :loading="loading"
      :data="histories"
      :columns="columns"
      :pagination="{
        total,
        current: currentPage,
        pageSize,
        showTotal: true,
        showJumper: true,
        showPageSize: true
      }"
      :bordered="true"
      :stripe="true"
      class="custom-table"
      @page-change="handlePageChange"
      @page-size-change="handlePageSizeChange"
    >
      <template #index="{ rowIndex }">
        {{ (currentPage - 1) * pageSize + rowIndex + 1 }}
      </template>

      <template #config_name="{ record }">
        <span>{{ record.sync_config_info?.name || record.config?.name || '-' }}</span>
      </template>

      <template #sync_fields="{ record }">
        <div class="flex flex-wrap gap-1">
          <a-tag
            v-for="field in record.sync_fields"
            :key="field"
            color="arcoblue"
            size="small"
          >
            {{ getFieldDescription(field) }}
          </a-tag>
        </div>
      </template>

      <template #status="{ record }">
        <a-tag 
          :color="record.sync_status === 'success' || record.status === 'success' ? 'green' : 'red'"
          size="medium"
          class="min-w-[60px] text-center"
        >
          {{ (record.sync_status === 'success' || record.status === 'success') ? text.success : text.failed }}
        </a-tag>
        <a-tooltip v-if="record.error_message">
          <template #content>
            {{ record.error_message }}
          </template>
          <icon-exclamation-circle class="text-red-500 ml-1" />
        </a-tooltip>
      </template>

      <template #created_info="{ record }">
        <div class="flex flex-col gap-1 text-sm">
          <span>{{ text.operator }}{{ record.operator_info?.username || record.created_by_info?.username || '-' }}</span>
          <span>{{ text.time }}{{ record.sync_time ? new Date(record.sync_time).toLocaleString() : (record.created_at ? new Date(record.created_at).toLocaleString() : '-') }}</span>
        </div>
      </template>

      <template #operations="{ record }">
        <div class="flex gap-2">
          <a-button
            type="text"
            size="mini"
            :loading="loading"
            @click="handleViewDetail(record)"
          >
            {{ text.details }}
          </a-button>
          <a-button
            v-if="record.sync_status === 'success' || record.status === 'success'"
            type="text"
            status="warning"
            size="mini"
            :loading="loading"
            @click="handleRollback(record)"
          >
            {{ text.rollback }}
          </a-button>
        </div>
      </template>
    </a-table>

    <!-- 详情弹窗 -->
    <a-modal
      v-model:visible="showDetailModal"
      :title="text.syncHistoryDetail"
      :width="900"
      :modal-class="isDarkTheme ? 'sync-history-modal sync-history-modal--dark' : 'sync-history-modal sync-history-modal--light'"
      @cancel="currentHistory = null"
    >
      <div class="history-overview p-3 rounded-lg">
        <div class="grid grid-cols-4 gap-3">
          <div class="detail-cell rounded">
            <div class="detail-cell-title py-2 px-3 font-medium border-b">
              {{ text.configName }}
            </div>
            <div class="detail-cell-body py-2 px-3">
              {{ currentHistory?.sync_config_info?.name || currentHistory?.config?.name || '-' }}
            </div>
          </div>

          <div class="detail-cell rounded">
            <div class="detail-cell-title py-2 px-3 font-medium border-b">
              {{ text.syncStatus }}
            </div>
            <div class="detail-cell-body py-2 px-3">
              <span 
                :class="[
                  'px-2 py-0.5 rounded text-white', 
                  (currentHistory?.sync_status === 'success' || currentHistory?.status === 'success') 
                    ? 'bg-green-500' 
                    : 'bg-red-500'
                ]"
              >
                {{ (currentHistory?.sync_status === 'success' || currentHistory?.status === 'success') ? text.success : text.failed }}
              </span>
            </div>
          </div>

          <div class="detail-cell rounded">
            <div class="detail-cell-title py-2 px-3 font-medium border-b">
              {{ text.operatorName }}
            </div>
            <div class="detail-cell-body py-2 px-3 text-xs">
              <div>{{ currentHistory?.operator_info?.username || currentHistory?.created_by_info?.username || '-' }}</div>
              <div class="detail-cell-meta mt-0.5">
                {{ currentHistory?.sync_time 
                  ? new Date(currentHistory.sync_time).toLocaleString() 
                  : (currentHistory?.created_at ? new Date(currentHistory.created_at).toLocaleString() : '-') }}
              </div>
            </div>
          </div>

          <div class="detail-cell rounded">
            <div class="detail-cell-title py-2 px-3 font-medium border-b">
              {{ text.errorMessage }}
            </div>
            <div class="detail-cell-body detail-cell-body--scroll py-2 px-3 text-xs overflow-auto max-h-[60px]">
              {{ currentHistory?.error_message || '-' }}
            </div>
          </div>

          <div class="detail-cell detail-cell--wide rounded col-span-4">
            <div class="detail-cell-title py-1.5 px-3 font-medium border-b flex items-center justify-between">
              <span>{{ text.syncFields }}</span>
              <span class="text-xs font-normal">{{ text.totalFields(currentHistory?.sync_fields?.length || 0) }}</span>
            </div>
            <div class="detail-cell-body p-2">
              <div v-if="currentHistory?.sync_fields?.length" class="flex flex-wrap gap-1.5">
                <a-tag
                  v-for="field in currentHistory.sync_fields"
                  :key="field"
                  color="arcoblue"
                  size="small"
                >
                  {{ getFieldDescription(field) }}
                </a-tag>
              </div>
              <div v-else class="detail-empty text-sm">{{ text.noSyncFields }}</div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="currentHistory?.old_data || currentHistory?.new_data" class="mt-3">
        <div class="mb-3">
          <div class="flex items-center justify-between">
            <h3 class="diff-title text-sm font-medium flex items-center">
              <span class="inline-block w-1.5 h-1.5 bg-blue-500 rounded-full mr-1.5"></span>
              {{ text.dataChangeDetails }}
            </h3>
            <a-button
              type="text"
              size="mini"
              class="diff-toggle-btn"
              @click="showUnchanged = !showUnchanged"
            >
              {{ showUnchanged ? text.hideUnchangedFields : text.showUnchangedFields }}
            </a-button>
          </div>
        </div>

        <div class="diff-shell rounded-lg border">
          <div class="diff-header grid grid-cols-12 gap-3 py-1.5 px-3 border-b">
            <div class="col-span-2 diff-header-text text-xs font-medium">{{ text.fieldName }}</div>
            <div class="col-span-5 diff-header-text text-xs font-medium flex items-center">
              <span class="inline-block w-1.5 h-1.5 bg-red-500/70 rounded-full mr-1.5"></span>
              {{ text.beforeChange }}
            </div>
            <div class="col-span-5 diff-header-text text-xs font-medium flex items-center">
              <span class="inline-block w-1.5 h-1.5 bg-green-500/70 rounded-full mr-1.5"></span>
              {{ text.afterChange }}
            </div>
          </div>

          <div class="diff-list">
            <div
              v-for="field in diffFields"
              :key="field.key"
              v-show="field.changed || showUnchanged"
              :class="[
                'grid grid-cols-12 gap-3 py-2 px-3 diff-row',
                field.changed ? 'diff-row--changed' : ''
              ]"
            >
              <div class="col-span-2 flex flex-col justify-center">
                <div class="diff-name text-sm font-medium">
                  {{ getFieldDescription(field.key) }}
                </div>
                <div class="diff-key text-xs mt-0.5">
                  {{ field.key }}
                </div>
              </div>

              <div class="col-span-5">
                <div 
                  :class="[
                    'rounded p-1 text-sm font-mono leading-5 diff-value-box',
                    field.changed ? 'diff-value-box--old' : 'diff-value-box--same'
                  ]"
                >
                  <pre class="whitespace-pre-wrap break-all text-left" v-html="formatValue(field.oldValue)"></pre>
                </div>
              </div>

              <div class="col-span-5">
                <div 
                  :class="[
                    'rounded p-1 text-sm font-mono leading-5 diff-value-box',
                    field.changed ? 'diff-value-box--new' : 'diff-value-box--same'
                  ]"
                >
                  <pre class="whitespace-pre-wrap break-all text-left" v-html="formatValue(field.newValue)"></pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<style scoped>
@reference "tailwindcss";
.sync-history {
  --sh-text: var(--color-text-1);
  --sh-muted: var(--color-text-2);
  --sh-subtle: var(--color-text-3);
  --sh-border: rgba(148, 163, 184, 0.18);
  --sh-table-header: rgba(248, 250, 252, 0.98);
  --sh-table-cell: rgba(255, 255, 255, 0.94);
  --sh-table-hover: rgba(59, 130, 246, 0.06);
}

.sync-history--dark {
  --sh-text: rgb(229, 231, 235);
  --sh-muted: rgb(203, 213, 225);
  --sh-subtle: rgb(156, 163, 175);
  --sh-border: rgba(71, 85, 105, 0.32);
  --sh-table-header: rgba(15, 23, 42, 0.88);
  --sh-table-cell: rgba(31, 41, 55, 0.9);
  --sh-table-hover: rgba(30, 41, 59, 0.62);
}

:deep(.arco-table) {
  @apply bg-transparent;
}

:deep(.arco-table-th) {
  background: var(--sh-table-header) !important;
  border-color: var(--sh-border) !important;
  color: var(--sh-text) !important;
}

:deep(.arco-table-td) {
  background: var(--sh-table-cell) !important;
  color: var(--sh-muted) !important;
  border-color: var(--sh-border) !important;
}

:deep(.arco-table-tr:hover .arco-table-td) {
  background: var(--sh-table-hover) !important;
}

:deep(.sync-history-modal--light) {
  --shm-bg: rgba(255, 255, 255, 0.99);
  --shm-card: rgba(248, 250, 252, 0.98);
  --shm-card-alt: rgba(255, 255, 255, 0.98);
  --shm-border: rgba(148, 163, 184, 0.18);
  --shm-text: var(--color-text-1);
  --shm-subtle: var(--color-text-3);
  --shm-key: rgba(100, 116, 139, 0.92);
  --shm-diff-header: rgba(241, 245, 249, 0.96);
  --shm-diff-row-hover: rgba(148, 163, 184, 0.08);
  --shm-diff-row-changed: rgba(59, 130, 246, 0.05);
  --shm-diff-old: rgba(239, 68, 68, 0.08);
  --shm-diff-new: rgba(16, 185, 129, 0.08);
  --shm-diff-same: rgba(248, 250, 252, 0.98);
}

:deep(.sync-history-modal--dark) {
  --shm-bg: rgba(31, 41, 55, 0.98);
  --shm-card: rgba(17, 24, 39, 0.42);
  --shm-card-alt: rgba(31, 41, 55, 0.72);
  --shm-border: rgba(71, 85, 105, 0.32);
  --shm-text: rgb(229, 231, 235);
  --shm-subtle: rgb(156, 163, 175);
  --shm-key: rgba(107, 114, 128, 0.92);
  --shm-diff-header: rgba(17, 24, 39, 0.5);
  --shm-diff-row-hover: rgba(31, 41, 55, 0.62);
  --shm-diff-row-changed: rgba(59, 130, 246, 0.08);
  --shm-diff-old: rgba(239, 68, 68, 0.1);
  --shm-diff-new: rgba(16, 185, 129, 0.12);
  --shm-diff-same: rgba(31, 41, 55, 0.45);
}

:deep(.sync-history-modal .arco-modal) {
  background: var(--shm-bg) !important;
  border: 1px solid var(--shm-border) !important;
}

:deep(.sync-history-modal .arco-modal-header),
:deep(.sync-history-modal .arco-modal-footer) {
  background: var(--shm-bg) !important;
  border-color: var(--shm-border) !important;
}

:deep(.sync-history-modal .arco-modal-title) {
  color: var(--shm-text) !important;
}

:deep(.sync-history-modal .arco-modal-body) {
  background: var(--shm-bg) !important;
  @apply p-4;
}

.history-overview,
.diff-shell {
  background: var(--shm-card);
  border: 1px solid var(--shm-border);
}

.detail-cell {
  background: var(--shm-card-alt);
  border: 1px solid var(--shm-border);
}

.detail-cell-title,
.detail-cell-body,
.diff-title,
.diff-name,
.diff-header-text {
  color: var(--shm-text);
}

.detail-cell-title {
  border-bottom-color: var(--shm-border);
}

.detail-cell-meta,
.detail-empty,
.diff-key,
.diff-toggle-btn {
  color: var(--shm-subtle) !important;
}

.diff-header {
  background: var(--shm-diff-header);
  border-bottom-color: var(--shm-border);
}

.diff-list {
  border-top: 0;
}

.diff-row {
  border-top: 1px solid var(--shm-border);
}

.diff-row:hover {
  background: var(--shm-diff-row-hover);
}

.diff-row--changed {
  background: var(--shm-diff-row-changed);
}

.diff-value-box {
  color: var(--shm-text);
}

.diff-value-box--old {
  background: var(--shm-diff-old);
}

.diff-value-box--new {
  background: var(--shm-diff-new);
}

.diff-value-box--same {
  background: var(--shm-diff-same);
  color: var(--shm-subtle);
}

.diff-panel {
  @apply flex flex-col;
}

.diff-content {
  @apply h-[350px] overflow-auto p-3;
}
</style>
