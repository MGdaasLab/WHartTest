<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { TableColumnData } from '@arco-design/web-vue'
import type { ApiTestCase } from '../../types/testcase'
import { IconEdit, IconDelete, IconMore, IconCopy } from '@arco-design/web-vue/es/icon'

import { useAppI18n } from '@/composables/useAppI18n'

interface Props {
  data: ApiTestCase[]
  loading?: boolean
}

const props = defineProps<Props>()
const emit = defineEmits(['sort', 'run', 'link', 'report', 'edit', 'copy', 'delete', 'batch-delete'])
const { isEnglish, tl } = useAppI18n()

const priorityColors = {
  'P0': 'red',
  'P1': 'orange',
  'P2': 'blue',
  'P3': 'green'
} as const

const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const columns: TableColumnData[] = [
  {
    title: 'ID',
    dataIndex: 'id',
    width: 80,
    align: 'center'
  },
  {
    title: '名称',
    dataIndex: 'name',
    ellipsis: true,
    tooltip: true,
    width: 200,
    align: 'center',
    slotName: 'name'
  },
  {
    title: '描述',
    dataIndex: 'description',
    ellipsis: true,
    tooltip: true,
    width: 250,
    align: 'center'
  },
  {
    title: '优先级',
    dataIndex: 'priority',
    width: 80,
    align: 'center',
    slotName: 'priority'
  },
  {
    title: '分组',
    dataIndex: 'group_info.name',
    width: 150,
    ellipsis: true,
    tooltip: true,
    align: 'center'
  },
  {
    title: '标签',
    dataIndex: 'tags',
    slotName: 'tags',
    width: 150,
    align: 'center'
  },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    sortable: {
      sortDirections: ['ascend', 'descend'],
      defaultSortOrder: 'descend'
    },
    width: 140,
    slotName: 'created_at',
    align: 'center'
  },
  {
    title: '更新时间',
    dataIndex: 'updated_at',
    sortable: {
      sortDirections: ['ascend', 'descend']
    },
    width: 140,
    slotName: 'updated_at',
    align: 'center'
  },
  {
    title: '操作',
    align: 'center',
    width: 240,
    slotName: 'operations',
  }
]

const handleSortChange = (dataIndex: string, direction: string) => {
  emit('sort', dataIndex, direction)
}

const handleRun = (record: ApiTestCase) => {
  emit('run', record)
}

const handleReport = (record: ApiTestCase) => {
  emit('report', record)
}

const handleLink = (record: ApiTestCase) => {
  emit('link', record)
}

const handleEdit = (record: ApiTestCase) => {
  emit('edit', record)
}

const handleCopy = (record: ApiTestCase) => {
  emit('copy', record)
}

const handleDelete = (record: ApiTestCase) => {
  emit('delete', record)
}

// 批量选择
const selectedRowKeys = ref<(string | number)[]>([])

const selectedRecords = computed(() => {
  const keySet = new Set(selectedRowKeys.value.map(String))
  return props.data.filter(item => item.id !== null && item.id !== undefined && keySet.has(String(item.id)))
})

const selectedCount = computed(() => selectedRecords.value.length)

const rowSelection = {
  type: 'checkbox' as const,
  showCheckedAll: true,
  onlyCurrent: true,
  width: 42,
}

const clearSelection = () => {
  selectedRowKeys.value = []
}

const handleBatchDeleteClick = () => {
  if (selectedRecords.value.length === 0) return
  emit('batch-delete', [...selectedRecords.value])
}

// 列表数据变化时清理已不存在的勾选项
watch(
  () => props.data.map(item => item.id),
  (ids) => {
    const valid = new Set((ids || []).filter(id => id !== null && id !== undefined).map(String))
    selectedRowKeys.value = selectedRowKeys.value.filter(key => valid.has(String(key)))
  },
)

defineExpose({ clearSelection, selectedRowKeys })
</script>

<template>
  <div class="h-full flex flex-col">
    <!-- 批量操作条 -->
    <div v-if="selectedCount > 0" class="batch-bar">
      <div class="batch-bar__info">
        <a-tag color="arcoblue" size="small">{{ tl('已选') }} {{ selectedCount }}</a-tag>
        <span class="batch-bar__hint">
          {{ isEnglish ? `Selected ${selectedCount} ${selectedCount === 1 ? 'test case' : 'test cases'}, ready for batch delete` : `已勾选 ${selectedCount} 个用例，可批量删除` }}
        </span>
      </div>
      <div class="batch-bar__actions">
        <a-button type="text" size="small" class="batch-bar__clear" @click="clearSelection">
          {{ tl('取消选择') }}
        </a-button>
        <a-button type="primary" status="danger" size="small" @click="handleBatchDeleteClick">
          <template #icon><icon-delete /></template>
          {{ tl('批量删除') }}
        </a-button>
      </div>
    </div>

    <a-table
      :data="data"
      :columns="columns"
      :pagination="false"
      :loading="loading"
      :scroll="{ y: 'calc(100vh - 340px)' }"
      :sticky-header="true"
      row-key="id"
      v-model:selected-keys="selectedRowKeys"
      :row-selection="rowSelection"
      class="custom-table"
      @sorter-change="handleSortChange"
    >
      <template #name="{ record }">
        <span class="name-link" @click="handleEdit(record)">{{ record.name }}</span>
      </template>

      <template #priority="{ record }">
        <a-tag :color="priorityColors[record.priority as keyof typeof priorityColors]">
          {{ record.priority }}
        </a-tag>
      </template>

      <template #tags="{ record }">
        <div class="flex flex-wrap gap-1 justify-center">
          <a-tag
            v-for="tag in (record as any).tags_info"
            :key="tag.id"
            :color="tag.color"
            size="small"
          >
            {{ tag.name }}
          </a-tag>
        </div>
      </template>

      <template #created_at="{ record }">
        {{ formatDate(record.created_at) }}
      </template>

      <template #updated_at="{ record }">
        {{ formatDate(record.updated_at) }}
      </template>

      <template #operations="{ record }">
        <div class="operations-wrapper flex items-center justify-center gap-1 px-2">
          <a-button-group class="btn-group">
            <a-button
              type="primary"
              size="mini"
              class="btn-run"
              @click="handleRun(record)"
            >
              运行
            </a-button>
            <a-button
              type="primary"
              size="mini"
              class="btn-report"
              @click="handleReport(record)"
            >
              报告
            </a-button>
            <a-button
              type="primary"
              size="mini"
              class="btn-link"
              @click="handleLink(record)"
            >
              关联
            </a-button>
          </a-button-group>
          <a-dropdown>
            <a-button type="secondary" size="mini" class="btn-more">
              <icon-more />
            </a-button>
            <template #content>
              <a-doption class="testcase-action-option flex items-center gap-2" @click="handleEdit(record)">
                <icon-edit />
                编辑
              </a-doption>
              <a-doption class="testcase-action-option flex items-center gap-2" @click="handleCopy(record)">
                <icon-copy />
                复制
              </a-doption>
              <a-doption class="testcase-action-option testcase-action-option--danger flex items-center gap-2" @click="handleDelete(record)">
                <icon-delete />
                删除
              </a-doption>
            </template>
          </a-dropdown>
        </div>
      </template>

      <template #empty>
        <div class="table-empty py-8 flex justify-center items-center">
          暂无数据
        </div>
      </template>
    </a-table>
  </div>
</template>

<style scoped>
@reference "tailwindcss";

/* 批量操作条 */
.batch-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 12px;
  margin-bottom: 8px;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.24);
  border-radius: 6px;
  background: rgba(var(--theme-accent-rgb), 0.06);
}

.batch-bar__info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.batch-bar__hint {
  color: var(--tc-text-muted);
  font-size: 12px;
}

.batch-bar__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.batch-bar__clear {
  color: var(--tc-text-muted) !important;
}

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
  background-color: var(--tc-table-header-bg) !important;
  border-bottom: 1px solid var(--tc-panel-border) !important;
  color: var(--tc-text) !important;
  font-weight: 500 !important;
  text-align: center !important;
}

.custom-table :deep(.arco-table-td) {
  background-color: transparent !important;
  border-bottom: 1px solid var(--tc-panel-border) !important;
  color: var(--tc-text-muted) !important;
}

.custom-table :deep(.arco-table-tr) {
  background-color: transparent !important;
}

.custom-table :deep(.arco-table-tr:hover) {
  background-color: var(--tc-row-hover) !important;
}

.custom-scrollbar {
  scrollbar-width: none !important;
  -ms-overflow-style: none !important;
  &::-webkit-scrollbar {
    display: none !important;
  }
}

/* 操作区域响应式样式 */
.operations-wrapper {
  @apply w-full;
  min-width: 0;
}

/* 操作按钮样式 */
.btn-group {
  @apply flex-shrink-0;

  .arco-btn {
    @apply px-2;
    min-width: 48px !important;
    height: 28px !important;
    margin: 0 !important;
    border-radius: 0 !important;
    font-size: 12px !important;
    white-space: nowrap !important;

    &:first-child {
      border-top-left-radius: 4px !important;
      border-bottom-left-radius: 4px !important;
    }

    &:last-child {
      border-top-right-radius: 4px !important;
      border-bottom-right-radius: 4px !important;
    }

    &:not(:first-child) {
      margin-left: 1px !important;
    }
  }
}

/* 小屏幕优化 */
@media (max-width: 1280px) {
  .btn-group .arco-btn {
    min-width: 44px !important;
    @apply px-1;
    font-size: 11px !important;
  }

  .btn-more {
    min-width: 28px !important;
  }
}

.btn-run {
  background: linear-gradient(to right, rgb(16, 185, 129), rgb(5, 150, 105)) !important;
  border: none !important;
  box-shadow: 0 2px 4px rgba(16, 185, 129, 0.2) !important;

  &:hover {
    background: linear-gradient(to right, rgb(20, 210, 150), rgb(16, 185, 129)) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 8px rgba(16, 185, 129, 0.3) !important;
  }

  &:active {
    transform: translateY(0) !important;
  }
}

.btn-report {
  background: linear-gradient(to right, rgb(249, 115, 22), rgb(234, 88, 12)) !important;
  border: none !important;
  box-shadow: 0 2px 4px rgba(249, 115, 22, 0.2) !important;

  &:hover {
    background: linear-gradient(to right, rgb(255, 135, 40), rgb(249, 115, 22)) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 8px rgba(249, 115, 22, 0.3) !important;
  }

  &:active {
    transform: translateY(0) !important;
  }
}

.btn-link {
  background: linear-gradient(to right, rgb(139, 92, 246), rgb(124, 58, 237)) !important;
  border: none !important;
  box-shadow: 0 2px 4px rgba(139, 92, 246, 0.2) !important;

  &:hover {
    background: linear-gradient(to right, rgb(160, 110, 255), rgb(139, 92, 246)) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 8px rgba(139, 92, 246, 0.3) !important;
  }

  &:active {
    transform: translateY(0) !important;
  }
}

.btn-more {
  min-width: 32px !important;
  @apply flex-shrink-0;
  height: 28px !important;
  background: var(--tc-more-bg) !important;
  border: none !important;
  color: var(--tc-more-text) !important;
  border-radius: 4px !important;
  margin-left: 4px !important;
  box-shadow: 0 2px 4px rgba(51, 65, 85, 0.2) !important;

  &:hover {
    background: var(--tc-more-bg-hover) !important;
    color: var(--tc-more-text) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 8px rgba(51, 65, 85, 0.3) !important;
  }

  &:active {
    transform: translateY(0) !important;
  }
}

:global(body.api-testing-theme .arco-dropdown-option) {
  @apply py-2 px-4;
  background-color: rgb(30, 41, 59) !important;
  color: rgb(226, 232, 240) !important;

  &:hover {
    background: linear-gradient(to right, rgba(71, 85, 105, 0.8), rgba(51, 65, 85, 0.8)) !important;
    color: rgb(241, 245, 249) !important;
  }

  .arco-icon {
    color: rgb(148, 163, 184) !important;
  }
}

:global(body.api-testing-theme .arco-dropdown) {
  background-color: rgb(30, 41, 59) !important;
  border: 1px solid rgba(148, 163, 184, 0.1) !important;
  border-radius: 6px !important;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2) !important;

  .arco-dropdown-option-content {
    color: inherit !important;
  }
}

:global(body.api-testing-theme .arco-dropdown .arco-dropdown-list),
:global(body.api-testing-theme .arco-dropdown .arco-dropdown-list-wrapper),
:global(body.api-testing-theme .arco-dropdown .arco-dropdown-menu) {
  background-color: rgb(30, 41, 59) !important;
  border-radius: 8px !important;
}

:global(.arco-dropdown) {
  background-color: #ffffff !important;
  border: 1px solid rgba(148, 163, 184, 0.18) !important;
  border-radius: 8px !important;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.12) !important;
  overflow: hidden !important;
}

:global(.arco-dropdown .arco-dropdown-list),
:global(.arco-dropdown .arco-dropdown-list-wrapper),
:global(.arco-dropdown .arco-dropdown-menu) {
  background-color: #ffffff !important;
  border-radius: 8px !important;
  box-shadow: none !important;
}

:global(.testcase-action-option) {
  @apply py-2 px-4;
  background-color: #ffffff !important;
  color: #334155 !important;

  &:hover {
    background: #f8fafc !important;
    color: #0f172a !important;
  }

  .arco-icon {
    color: #64748b !important;
  }

  .arco-dropdown-option-content {
    color: inherit !important;
  }
}

:global(.testcase-action-option--danger) {
  color: #ef4444 !important;

  .arco-icon {
    color: #ef4444 !important;
  }

  &:hover {
    background: rgba(239, 68, 68, 0.08) !important;
    color: #dc2626 !important;
  }
}

.name-link {
  color: var(--tc-link) !important;
  cursor: pointer !important;
  transition: all 0.2s ease !important;

  &:hover {
    color: var(--tc-link-hover) !important;
    text-decoration: underline !important;
  }
}

.table-empty {
  color: var(--tc-text-subtle);
}
</style>
