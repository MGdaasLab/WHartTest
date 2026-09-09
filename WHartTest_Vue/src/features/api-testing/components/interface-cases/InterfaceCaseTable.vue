<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { TableColumnData } from '@arco-design/web-vue'
import { IconCopy, IconDelete, IconEdit, IconMore } from '@arco-design/web-vue/es/icon'
import { useAppI18n } from '@/composables/useAppI18n'
import type { ApiInterfaceCase } from '../../types/interfaceCase'

interface Props {
  data: ApiInterfaceCase[]
  loading?: boolean
}

const props = defineProps<Props>()
const emit = defineEmits(['sort', 'run', 'report', 'edit', 'copy', 'delete', 'batch-delete'])
const { isEnglish, tl } = useAppI18n()

const priorityColors = {
  P0: 'red',
  P1: 'orange',
  P2: 'blue',
  P3: 'green'
} as const

const columns = computed<TableColumnData[]>(() => [
  { title: 'ID', dataIndex: 'id', width: 64, align: 'center' },
  { title: tl('名称'), dataIndex: 'name', ellipsis: true, tooltip: true, align: 'center', slotName: 'name' },
  { title: tl('主接口'), dataIndex: 'interface_info.name', ellipsis: true, tooltip: true, align: 'center', slotName: 'interface' },
  { title: tl('描述'), dataIndex: 'description', ellipsis: true, tooltip: true, align: 'center' },
  { title: tl('优先级'), dataIndex: 'priority', width: 76, align: 'center', slotName: 'priority' },
  { title: tl('前置条件'), dataIndex: 'precondition_count', width: 88, align: 'center', slotName: 'preconditions' },
  { title: tl('分组'), dataIndex: 'group_info.name', ellipsis: true, tooltip: true, align: 'center' },
  { title: tl('标签'), dataIndex: 'tags', slotName: 'tags', align: 'center' },
  { title: tl('更新时间'), dataIndex: 'updated_at', sortable: { sortDirections: ['ascend', 'descend'] }, width: 150, slotName: 'updated_at', align: 'center' },
  { title: tl('操作'), align: 'center', width: 160, slotName: 'operations' },
])

const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString(isEnglish.value ? 'en-US' : 'zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
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
  <div class="h-full min-w-0 overflow-hidden flex flex-col">
    <!-- 批量操作条 -->
    <div v-if="selectedCount > 0" class="batch-bar">
      <div class="batch-bar__info">
        <a-tag color="arcoblue" size="small">{{ tl('已选') }} {{ selectedCount }}</a-tag>
        <span class="batch-bar__hint">
          {{ isEnglish ? `Selected ${selectedCount} ${selectedCount === 1 ? 'interface case' : 'interface cases'}, ready for batch delete` : `已勾选 ${selectedCount} 个接口用例，可批量删除` }}
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
      :scroll="{ y: 'calc(100vh - 360px)' }"
      :sticky-header="true"
      row-key="id"
      v-model:selected-keys="selectedRowKeys"
      :row-selection="rowSelection"
      class="custom-table"
      @sorter-change="(dataIndex: string, direction: string) => emit('sort', dataIndex, direction)"
    >
      <template #name="{ record }">
        <span class="name-link" @click="emit('edit', record)">{{ record.name }}</span>
      </template>

      <template #interface="{ record }">
        <div class="interface-cell">
          <a-tag size="small" color="arcoblue">{{ record.interface_info?.method || '-' }}</a-tag>
          <span class="truncate">{{ record.interface_info?.name || '-' }}</span>
        </div>
      </template>

      <template #priority="{ record }">
        <a-tag :color="priorityColors[record.priority as keyof typeof priorityColors]">
          {{ record.priority }}
        </a-tag>
      </template>

      <template #preconditions="{ record }">
        <a-tag :color="record.precondition_count ? 'arcoblue' : 'gray'">
          {{ record.precondition_count || 0 }}
        </a-tag>
      </template>

      <template #tags="{ record }">
        <div class="flex flex-wrap gap-1 justify-center">
          <a-tag
            v-for="tag in record.tags_info || []"
            :key="tag.id"
            :color="tag.color"
            size="small"
          >
            {{ tag.name }}
          </a-tag>
        </div>
      </template>

      <template #updated_at="{ record }">
        {{ formatDate(record.updated_at) }}
      </template>

      <template #operations="{ record }">
        <div class="operations-wrapper flex items-center justify-center gap-1">
          <a-button-group class="btn-group">
            <a-button type="primary" size="mini" class="btn-run" @click="emit('run', record)">
              {{ tl('运行') }}
            </a-button>
            <a-button type="primary" size="mini" class="btn-report" @click="emit('report', record)">
              {{ tl('报告') }}
            </a-button>
          </a-button-group>
          <a-dropdown>
            <a-button type="secondary" size="mini" class="btn-more">
              <icon-more />
            </a-button>
            <template #content>
              <a-doption class="interface-case-action-option flex items-center gap-2" @click="emit('edit', record)">
                <icon-edit />
                {{ tl('编辑') }}
              </a-doption>
              <a-doption class="interface-case-action-option flex items-center gap-2" @click="emit('copy', record)">
                <icon-copy />
                {{ tl('复制') }}
              </a-doption>
              <a-doption class="interface-case-action-option interface-case-action-option--danger flex items-center gap-2" @click="emit('delete', record)">
                <icon-delete />
                {{ tl('删除') }}
              </a-doption>
            </template>
          </a-dropdown>
        </div>
      </template>

      <template #empty>
        <div class="table-empty py-8 flex justify-center items-center">
          {{ tl('暂无数据') }}
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

.custom-table :deep(.arco-table),
.custom-table :deep(.arco-table-container),
.custom-table :deep(.arco-table-header),
.custom-table :deep(.arco-table-body) {
  background-color: transparent !important;
  border: none !important;
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

.custom-table :deep(.arco-table-tr:hover) {
  background-color: var(--tc-row-hover) !important;
}

.interface-cell {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.name-link {
  color: var(--tc-link) !important;
  cursor: pointer !important;
}

.name-link:hover {
  color: var(--tc-link-hover) !important;
  text-decoration: underline !important;
}

.btn-group .arco-btn {
  min-width: 48px !important;
  height: 28px !important;
  margin: 0 !important;
  border-radius: 0 !important;
  font-size: 12px !important;
  white-space: nowrap !important;
}

.btn-group .arco-btn:first-child {
  border-top-left-radius: 4px !important;
  border-bottom-left-radius: 4px !important;
}

.btn-group .arco-btn:last-child {
  border-top-right-radius: 4px !important;
  border-bottom-right-radius: 4px !important;
}

.btn-run {
  background: linear-gradient(to right, rgb(16, 185, 129), rgb(5, 150, 105)) !important;
  border: none !important;
}

.btn-report {
  background: linear-gradient(to right, rgb(249, 115, 22), rgb(234, 88, 12)) !important;
  border: none !important;
}

.btn-more {
  min-width: 32px !important;
  height: 28px !important;
  margin-left: 4px !important;
  color: var(--tc-more-text) !important;
  background: var(--tc-more-bg) !important;
  border: none !important;
}

.table-empty {
  color: var(--tc-text-subtle);
}

:global(.interface-case-action-option) {
  @apply py-2 px-4;
  background-color: #ffffff !important;
  color: #334155 !important;
}

:global(.interface-case-action-option:hover) {
  background: #f8fafc !important;
  color: #0f172a !important;
}

:global(.interface-case-action-option--danger) {
  color: #ef4444 !important;
}

:global(body.api-testing-theme .interface-case-action-option) {
  background-color: rgb(30, 41, 59) !important;
  color: rgb(226, 232, 240) !important;
}

:global(body.api-testing-theme .interface-case-action-option:hover) {
  background: rgba(71, 85, 105, 0.8) !important;
}
</style>
