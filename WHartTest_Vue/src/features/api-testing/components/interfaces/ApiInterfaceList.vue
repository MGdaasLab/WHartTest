<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onBeforeUnmount, watch } from 'vue'
import { IconSearch, IconSend, IconEdit, IconDelete, IconClockCircle, IconCopy } from '@arco-design/web-vue/es/icon'
import type { ApiInterface } from '../../services/interfaceService'
import { patchInterface } from '../../services/interfaceService'
import { Message } from '@arco-design/web-vue'
import {
  INTERFACE_STATUS_OPTIONS,
  getInterfaceStatusColor,
  getInterfaceStatusLabel,
  type InterfaceStatus,
} from '../../types/interface'
import { formatDateTime } from '@/utils/formatters'

/** 列表单行展示：YYYY-MM-DD HH:mm */
const formatListDateTime = (dateString?: string): string => {
  if (!dateString) return '-'
  const date = new Date(dateString)
  if (Number.isNaN(date.getTime())) return '-'
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  const hh = String(date.getHours()).padStart(2, '0')
  const mm = String(date.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${d} ${hh}:${mm}`
}

/** Tooltip 完整时间 */
const formatFullDateTime = formatDateTime

/** URL 左侧省略、保留末尾：123456789 -> ...6789 */
const measureCanvas = typeof document !== 'undefined' ? document.createElement('canvas') : null
const measureCtx = measureCanvas?.getContext('2d')

const measureTextWidth = (text: string, font: string) => {
  if (!measureCtx) return text.length * 7
  measureCtx.font = font
  return measureCtx.measureText(text).width
}

const truncateUrlKeepEnd = (url: string, maxWidth: number, font: string) => {
  if (!url) return '-'
  if (maxWidth <= 0) return url
  if (measureTextWidth(url, font) <= maxWidth) return url

  const ellipsis = '...'
  const ellipsisWidth = measureTextWidth(ellipsis, font)
  if (ellipsisWidth >= maxWidth) return ellipsis

  // 二分找到能放进剩余宽度的最长后缀
  let lo = 1
  let hi = url.length
  let best = ellipsis
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    const candidate = ellipsis + url.slice(url.length - mid)
    if (measureTextWidth(candidate, font) <= maxWidth) {
      best = candidate
      lo = mid + 1
    } else {
      hi = mid - 1
    }
  }
  return best
}

const formatUrlKeepEnd = (el: HTMLElement | null, url?: string) => {
  const value = url || '-'
  if (!el) return value
  const style = window.getComputedStyle(el)
  const font = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`
  // 预留 2px，避免亚像素抖动
  const maxWidth = Math.max(0, el.clientWidth - 2)
  return truncateUrlKeepEnd(value, maxWidth, font)
}

const urlDisplayMap = ref<Record<string, string>>({})
const urlCellRefs = new Map<string, HTMLElement>()

const urlKeyOf = (record: ApiInterface) => String(record.id ?? record.url ?? '')

const setUrlCellRef = (record: ApiInterface, el: unknown) => {
  const key = urlKeyOf(record)
  if (!key) return
  if (el instanceof HTMLElement) {
    urlCellRefs.set(key, el)
  } else {
    urlCellRefs.delete(key)
  }
}

const refreshUrlDisplays = () => {
  const next: Record<string, string> = {}
  let changed = false
  for (const item of filteredInterfaces.value) {
    const key = urlKeyOf(item)
    if (!key) continue
    const el = urlCellRefs.get(key) || null
    // 若 ref 尚未挂载，先用完整 URL，待下次再算
    const display = el ? formatUrlKeepEnd(el, item.url) : (item.url || '-')
    next[key] = display
    if (urlDisplayMap.value[key] !== display) changed = true
  }
  // 清理已不在列表中的 key
  for (const key of Object.keys(urlDisplayMap.value)) {
    if (!(key in next)) {
      changed = true
      break
    }
  }
  if (changed) {
    urlDisplayMap.value = next
  }
}

const getUrlDisplay = (record: ApiInterface) => {
  const key = urlKeyOf(record)
  return urlDisplayMap.value[key] || record.url || '-'
}


export interface InterfaceListModuleOption {
  id: number
  name: string
  level?: number
}

interface Props {
  interfaces: ApiInterface[]
  loading?: boolean
  selectedInterfaceId?: number
  currentModuleName?: string
  modules?: InterfaceListModuleOption[]
  filterModuleId?: number | null
  filterStatus?: InterfaceStatus | ''
  sortField?: 'created_at' | 'updated_at' | ''
  sortOrder?: 'ascend' | 'descend' | ''
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  interfaces: () => [],
  modules: () => [],
  filterModuleId: null,
  filterStatus: '',
  sortField: '',
  sortOrder: '',
})

const emit = defineEmits<{
  'interface-select': [api: ApiInterface]
  'interface-edit': [api: ApiInterface]
  'interface-delete': [api: ApiInterface]
  'interface-batch-delete': [apis: ApiInterface[]]
  'interface-copy': [api: ApiInterface]
  'interface-run': [api: ApiInterface]
  'interface-status-change': [payload: { api: ApiInterface; status: InterfaceStatus }]
  'filter-change': [payload: {
    moduleId: number | null
    status: InterfaceStatus | ''
    sortField: 'created_at' | 'updated_at' | ''
    sortOrder: 'ascend' | 'descend' | ''
    keyword: string
  }]
}>()

// 搜索 / 筛选：统一走服务端（filter-change）
const searchKeyword = ref('')
const localModuleId = ref<number | null>(props.filterModuleId ?? null)
const localStatus = ref<InterfaceStatus | ''>((props.filterStatus || '') as InterfaceStatus | '')

watch(
  () => props.filterModuleId,
  (value) => { localModuleId.value = value ?? null },
)
watch(
  () => props.filterStatus,
  (value) => { localStatus.value = (value || '') as InterfaceStatus | '' },
)

const statusFilterOptions = [
  { label: '全部状态', value: '' },
  ...INTERFACE_STATUS_OPTIONS.map(item => ({ label: item.label, value: item.value })),
]

const emitFilterChange = () => {
  emit('filter-change', {
    moduleId: localModuleId.value,
    status: localStatus.value,
    sortField: props.sortField || '',
    sortOrder: props.sortOrder || '',
    keyword: searchKeyword.value,
  })
}

const handleModuleFilterChange = (value: number | string | null | undefined) => {
  localModuleId.value = value == null || value === '' ? null : Number(value)
  emitFilterChange()
}

const handleStatusFilterChange = (value: string | null | undefined) => {
  localStatus.value = (value || '') as InterfaceStatus | ''
  emitFilterChange()
}

const handleSearchChange = () => {
  // 只走 filter-change，避免父组件重复请求
  emitFilterChange()
}

// 列表数据由服务端分页筛选，这里直接展示当前页
const filteredInterfaces = computed(() => props.interfaces)

const sorterMap = computed(() => {
  const field = props.sortField
  const order = props.sortOrder
  if (!field || !order) return {}
  return {
    [field]: order,
  } as Record<string, 'ascend' | 'descend'>
})

const handleSorterChange = (
  dataIndex: string,
  direction: 'ascend' | 'descend' | '',
) => {
  if (dataIndex !== 'created_at' && dataIndex !== 'updated_at') return
  const field = dataIndex as 'created_at' | 'updated_at'
  emit('filter-change', {
    moduleId: localModuleId.value,
    status: localStatus.value,
    sortField: direction ? field : '',
    sortOrder: direction || '',
    keyword: searchKeyword.value,
  })
}

// 批量选择
const selectedRowKeys = ref<(string | number)[]>([])

const selectedInterfaces = computed(() => {
  const keySet = new Set(selectedRowKeys.value.map(String))
  // 基于完整列表，避免搜索过滤导致「已选数量」与实际删除目标不一致
  return props.interfaces.filter(item => item.id != null && keySet.has(String(item.id)))
})

const selectedCount = computed(() => selectedInterfaces.value.length)

const rowSelection = {
  type: 'checkbox' as const,
  showCheckedAll: true,
  onlyCurrent: false,
  width: 42,
}

const clearSelection = () => {
  selectedRowKeys.value = []
}

const handleBatchDeleteClick = () => {
  if (selectedInterfaces.value.length === 0) return
  emit('interface-batch-delete', [...selectedInterfaces.value])
}

// 列表数据变化时清理已不存在的勾选项
watch(
  () => props.interfaces.map(item => item.id),
  (ids) => {
    const valid = new Set((ids || []).filter(id => id != null).map(String))
    selectedRowKeys.value = selectedRowKeys.value.filter(key => valid.has(String(key)))
  },
)


// URL 显示宽度变化时重算“保留末尾”文本（避免 onUpdated 循环）
let urlRefreshTimer: number | undefined
const scheduleUrlRefresh = () => {
  window.clearTimeout(urlRefreshTimer)
  urlRefreshTimer = window.setTimeout(() => {
    nextTick(() => refreshUrlDisplays())
  }, 16)
}

watch(
  () => [props.interfaces, searchKeyword.value, filteredInterfaces.value.length] as const,
  () => scheduleUrlRefresh(),
  { deep: false },
)

onMounted(() => {
  scheduleUrlRefresh()
  // 等表格布局完成再量宽（双 rAF + 短延迟兜底）
  requestAnimationFrame(() => requestAnimationFrame(() => refreshUrlDisplays()))
  window.setTimeout(() => refreshUrlDisplays(), 120)
  window.addEventListener('resize', scheduleUrlRefresh)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', scheduleUrlRefresh)
  window.clearTimeout(urlRefreshTimer)
})


// 处理接口点击（点勾选框时不进入详情）
const handleRowClick = (record: any, ev?: Event) => {
  const target = ev?.target as HTMLElement | undefined
  if (target?.closest?.('.arco-checkbox, .arco-table-checkbox, .arco-table-td-operation, label')) {
    return
  }
  emit('interface-select', record as ApiInterface)
}

// 获取方法颜色
const getMethodColor = (method: string) => {
  const colors: Record<string, string> = {
    GET: 'green',
    POST: 'blue',
    PUT: 'orange',
    DELETE: 'red',
    PATCH: 'arcoblue',
    HEAD: 'purple',
    OPTIONS: 'cyan'
  }
  return colors[method] || 'gray'
}

const getStatusColor = getInterfaceStatusColor
const getStatusLabel = (record: ApiInterface) => getInterfaceStatusLabel(record.status, record.status_display)

const getModuleName = (record: ApiInterface) => {
  return record.module_info?.name || '-'
}

const getCreatorName = (record: ApiInterface) => {
  if (record.created_by_name) return record.created_by_name
  if (record.created_by && typeof record.created_by === 'object') {
    return record.created_by.username || '-'
  }
  return '-'
}

const statusUpdatingIds = ref<Set<number>>(new Set())
const statusMenuOpenId = ref<number | null>(null)
const statusMenuStyle = ref<Record<string, string>>({})
const statusMenuRecord = ref<ApiInterface | null>(null)

const isStatusUpdating = (id?: number) => {
  return !!id && statusUpdatingIds.value.has(id)
}

const setStatusUpdating = (id: number, updating: boolean) => {
  const next = new Set(statusUpdatingIds.value)
  if (updating) next.add(id)
  else next.delete(id)
  statusUpdatingIds.value = next
}

const closeStatusMenu = () => {
  statusMenuOpenId.value = null
  statusMenuRecord.value = null
  statusMenuStyle.value = {}
}

const placeStatusMenu = (anchor: HTMLElement) => {
  const rect = anchor.getBoundingClientRect()
  // 与列表 Tag 同宽（最短也保证三字状态能完整显示）
  const menuWidth = Math.max(Math.ceil(rect.width), 56)
  let left = rect.left + rect.width / 2 - menuWidth / 2
  left = Math.max(8, Math.min(left, window.innerWidth - menuWidth - 8))
  const top = rect.bottom + 4
  statusMenuStyle.value = {
    position: 'fixed',
    top: `${top}px`,
    left: `${left}px`,
    width: `${menuWidth}px`,
    zIndex: '3000',
  }
}

const toggleStatusMenu = async (record: ApiInterface, event?: Event) => {
  event?.stopPropagation()
  if (!record?.id || isStatusUpdating(record.id)) return

  if (statusMenuOpenId.value === record.id) {
    closeStatusMenu()
    return
  }

  const raw = (event?.currentTarget || event?.target) as HTMLElement | null
  const anchor = raw?.closest?.('.status-quick-wrap') as HTMLElement | null
    || raw?.closest?.('.arco-tag') as HTMLElement | null
    || raw
  statusMenuOpenId.value = record.id
  statusMenuRecord.value = record
  if (anchor) {
    placeStatusMenu(anchor)
  }
  await nextTick()
}

const onDocumentClickCloseStatusMenu = (event: MouseEvent) => {
  const target = event.target as HTMLElement | null
  if (!target) return
  if (target.closest('.status-quick-wrap') || target.closest('.status-quick-menu')) return
  closeStatusMenu()
}

const onWindowRepositionClose = () => {
  if (statusMenuOpenId.value != null) closeStatusMenu()
}

onMounted(() => {
  document.addEventListener('click', onDocumentClickCloseStatusMenu, true)
  window.addEventListener('scroll', onWindowRepositionClose, true)
  window.addEventListener('resize', onWindowRepositionClose)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClickCloseStatusMenu, true)
  window.removeEventListener('scroll', onWindowRepositionClose, true)
  window.removeEventListener('resize', onWindowRepositionClose)
})

const handleStatusChange = async (record: ApiInterface, status: InterfaceStatus) => {
  closeStatusMenu()
  if (!record?.id || record.status === status || isStatusUpdating(record.id)) {
    return
  }

  const previousStatus = record.status
  const previousDisplay = record.status_display
  const option = INTERFACE_STATUS_OPTIONS.find(item => item.value === status)

  // optimistic update on row object
  record.status = status
  record.status_display = option?.label || status

  setStatusUpdating(record.id, true)
  try {
    const response = await patchInterface(record.id, { status })
    const updated = response.data as ApiInterface | undefined
    if (updated) {
      record.status = updated.status || status
      record.status_display = updated.status_display || option?.label || status
      emit('interface-status-change', { api: { ...record, ...updated }, status: record.status as InterfaceStatus })
    } else {
      emit('interface-status-change', { api: record, status })
    }
    Message.success('状态已更新')
  } catch (error: any) {
    record.status = previousStatus
    record.status_display = previousDisplay
    Message.error(error?.message || '更新状态失败')
  } finally {
    setStatusUpdating(record.id, false)
  }
}

defineExpose({
  clearSelection,
  selectedRowKeys,
})

</script>

<template>
  <div class="api-interface-list h-full flex flex-col">
    <!-- 搜索 / 筛选区域 -->
    <div class="p-4 list-toolbar">
      <div class="list-toolbar__row">
        <div class="list-toolbar__left">
          <a-tooltip :content="currentModuleName || '全部接口'">
            <span class="list-module-name">{{ currentModuleName || '全部接口' }}</span>
          </a-tooltip>
          <a-tag size="small" class="flex-shrink-0">{{ filteredInterfaces.length }} 个接口</a-tag>
          <template v-if="selectedCount > 0">
            <a-tag color="arcoblue" size="small" class="flex-shrink-0">已选 {{ selectedCount }}</a-tag>
            <a-button
              type="primary"
              status="danger"
              size="small"
              @click="handleBatchDeleteClick"
            >
              <template #icon><icon-delete /></template>
              批量删除
            </a-button>
            <a-button type="text" size="small" @click="clearSelection">取消选择</a-button>
          </template>
        </div>
        <div class="list-filter-bar">
          <a-select
            :model-value="localModuleId ?? undefined"
            placeholder="模块"
            allow-clear
            allow-search
            class="list-filter-select"
            @change="handleModuleFilterChange"
            @clear="handleModuleFilterChange(null)"
          >
            <a-option
              v-for="item in modules"
              :key="item.id"
              :value="item.id"
              :label="item.name"
            >
              <span :style="{ paddingLeft: `${(item.level || 0) * 12}px` }">{{ item.name }}</span>
            </a-option>
          </a-select>
          <a-select
            :model-value="localStatus"
            placeholder="状态"
            allow-clear
            class="list-filter-select list-filter-select--status"
            @change="handleStatusFilterChange"
            @clear="handleStatusFilterChange('')"
          >
            <a-option
              v-for="item in statusFilterOptions"
              :key="item.value || 'all'"
              :value="item.value"
              :label="item.label"
            >
              {{ item.label }}
            </a-option>
          </a-select>
          <a-input-search
            v-model="searchKeyword"
            placeholder="搜索接口名称、URL或方法"
            class="list-filter-search"
            allow-clear
            @search="handleSearchChange"
            @clear="handleSearchChange"
            @press-enter="handleSearchChange"
          />
        </div>
      </div>
    </div>

    <!-- 表格区域 -->
    <div class="flex-1 overflow-hidden">
      <a-spin :loading="loading" dot class="h-full">
        <a-table
          :data="filteredInterfaces"
          :pagination="false"
          :scroll="{ y: 'calc(100vh - 360px)' }"
          class="custom-table"
          row-key="id"
          v-model:selected-keys="selectedRowKeys"
          :row-selection="rowSelection"
          :row-class="(record) => record.id === selectedInterfaceId ? 'selected-row' : ''"
          @row-click="handleRowClick"
          @sorter-change="handleSorterChange"
        >
          <template #columns>
            <a-table-column title="ID" data-index="id" :width="64" align="center" />
            <a-table-column title="请求方法" data-index="method" :width="92" align="center" class-name="col-method">
              <template #cell="{ record }">
                <a-tag
                  :color="getMethodColor(record.method)"
                  size="small"
                  class="list-method-tag !font-medium"
                >
                  {{ record.method }}
                </a-tag>
              </template>
            </a-table-column>
            <a-table-column title="接口名称" data-index="name" :width="160" align="left" ellipsis>
              <template #cell="{ record }">
                <a-tooltip :content="record.name">
                  <span class="list-cell-ellipsis list-name-link cursor-pointer">{{ record.name }}</span>
                </a-tooltip>
              </template>
            </a-table-column>
            <a-table-column title="状态" data-index="status" :width="104" align="center" class-name="col-status">
              <template #cell="{ record }">
                <div class="status-quick-wrap" @click.stop>
                  <a-tag
                    :color="getStatusColor(record.status)"
                    size="small"
                    class="status-tag-trigger"
                    :class="{ 'status-tag-trigger--loading': isStatusUpdating(record.id) }"
                    @click="toggleStatusMenu(record, $event)"
                  >
                    {{ getStatusLabel(record) }}
                  </a-tag>
                </div>
              </template>
            </a-table-column>
            <a-table-column title="模块" data-index="module" :width="120" align="center" class-name="col-module">
              <template #cell="{ record }">
                <a-tooltip :content="getModuleName(record)">
                  <span class="list-module-text list-module-name-cell">{{ getModuleName(record) }}</span>
                </a-tooltip>
              </template>
            </a-table-column>
            <a-table-column title="创建人" data-index="created_by" :width="120" align="center" class-name="col-creator">
              <template #cell="{ record }">
                <a-tooltip :content="getCreatorName(record)">
                  <span class="list-creator-text list-creator-name">{{ getCreatorName(record) }}</span>
                </a-tooltip>
              </template>
            </a-table-column>
            <a-table-column title="URL" data-index="url" class-name="col-url">
              <template #cell="{ record }">
                <a-tooltip :content="record.url || '-'">
                  <div
                    class="list-url-end list-url-text"
                    :ref="(el) => setUrlCellRef(record, el)"
                  >{{ getUrlDisplay(record) }}</div>
                </a-tooltip>
              </template>
            </a-table-column>
            <a-table-column
              title="创建时间"
              data-index="created_at"
              :width="148"
              align="center"
              :sortable="{
                sortDirections: ['ascend', 'descend'],
                sorter: true,
                sortOrder: sorterMap.created_at || '',
              }"
            >
              <template #cell="{ record }">
                <a-tooltip v-if="record.created_at" :content="formatFullDateTime(record.created_at)">
                  <div class="list-time-cell">
                    <icon-clock-circle class="list-time-icon" :size="12" />
                    <span class="list-time-text">{{ formatListDateTime(record.created_at) }}</span>
                  </div>
                </a-tooltip>
                <span v-else class="list-time-text">-</span>
              </template>
            </a-table-column>
            <a-table-column
              title="更新时间"
              data-index="updated_at"
              :width="148"
              align="center"
              :sortable="{
                sortDirections: ['ascend', 'descend'],
                sorter: true,
                sortOrder: sorterMap.updated_at || '',
              }"
            >
              <template #cell="{ record }">
                <a-tooltip v-if="record.updated_at" :content="formatFullDateTime(record.updated_at)">
                  <div class="list-time-cell">
                    <icon-clock-circle class="list-time-icon list-time-icon--updated" :size="12" />
                    <span class="list-time-text">{{ formatListDateTime(record.updated_at) }}</span>
                  </div>
                </a-tooltip>
                <span v-else class="list-time-text">-</span>
              </template>
            </a-table-column>
            <a-table-column title="操作" align="center" :width="148">
              <template #cell="{ record }">
                <div class="list-actions">
                  <a-button
                    type="text"
                    size="mini"
                    @click.stop="$emit('interface-run', record)"
                    title="调试接口"
                  >
                    <template #icon><icon-send /></template>
                  </a-button>
                  <a-button
                    type="text"
                    size="mini"
                    @click.stop="$emit('interface-edit', record)"
                    title="编辑接口"
                  >
                    <template #icon><icon-edit /></template>
                  </a-button>
                  <a-button
                    type="text"
                    size="mini"
                    @click.stop="$emit('interface-copy', record)"
                    title="复制接口"
                  >
                    <template #icon><icon-copy /></template>
                  </a-button>
                  <a-button
                    type="text"
                    size="mini"
                    status="danger"
                    @click.stop="$emit('interface-delete', record)"
                    title="删除接口"
                  >
                    <template #icon><icon-delete /></template>
                  </a-button>
                </div>
              </template>
            </a-table-column>
          </template>
        </a-table>
      </a-spin>
    </div>
  </div>
  <!-- 状态快捷菜单：Teleport 到 body，宽度贴合列表 Tag -->
  <Teleport to="body">
    <div
      v-if="statusMenuOpenId != null && statusMenuRecord"
      class="status-quick-menu"
      role="menu"
      :style="statusMenuStyle"
      @click.stop
    >
      <div
        v-for="item in INTERFACE_STATUS_OPTIONS"
        :key="item.value"
        class="status-quick-option"
        :class="{ 'status-quick-option--active': statusMenuRecord.status === item.value }"
        role="menuitem"
        @click="handleStatusChange(statusMenuRecord, item.value)"
      >
        <span
          class="status-quick-pill"
          :class="`status-quick-pill--${item.value}`"
        >{{ item.label }}</span>
      </div>
    </div>
  </Teleport>
</template>

<style lang="postcss" scoped>
@reference "tailwindcss";
.api-interface-list {
  --interface-list-text: var(--color-text-2);
  --interface-list-muted: var(--color-text-3);
  --interface-list-header-bg: rgba(248, 250, 252, 0.96);
  --interface-list-row-hover: rgba(59, 130, 246, 0.06);
  --interface-list-row-selected: rgba(59, 130, 246, 0.12);
  --interface-list-empty: rgba(100, 116, 139, 0.9);
}

.list-module-name,
.list-url-text,
.list-time-text,
.list-module-text,
.list-creator-text {
  color: var(--interface-list-muted);
}

.list-name-link {
  color: var(--interface-list-text);
}

.list-name-link:hover {
  color: rgb(96, 165, 250);
}

.list-time-icon {
  color: rgba(100, 116, 139, 0.9);
}

.list-time-icon--updated {
  color: rgb(96, 165, 250);
}

:global(body.api-testing-theme) .api-interface-list {
  --interface-list-text: rgb(229, 231, 235);
  --interface-list-muted: rgb(156, 163, 175);
  --interface-list-header-bg: rgba(30, 41, 59, 0.5);
  --interface-list-row-hover: rgba(59, 130, 246, 0.05);
  --interface-list-row-selected: rgba(59, 130, 246, 0.1);
  --interface-list-empty: rgb(107, 114, 128);
}

.custom-table {
  @apply h-full;
}

.custom-table :deep(.arco-table-checkbox),
.custom-table :deep(.arco-table-th.arco-table-operation),
.custom-table :deep(.arco-table-td.arco-table-operation) {
  white-space: nowrap !important;
  overflow: visible !important;
}


.custom-table :deep(.arco-table) {
  background-color: transparent !important;
  table-layout: fixed !important;
}

.custom-table :deep(.arco-table-container) {
  background-color: transparent !important;
  border: none !important;
}

.custom-table :deep(.arco-table-body) {
  background-color: transparent !important;
}

/* 隐藏所有滚动条但保留滚动功能 */
.custom-table :deep(*::-webkit-scrollbar) {
  width: 0 !important;
  height: 0 !important;
  display: none !important;
}

/* Firefox */
.custom-table :deep(*) {
  scrollbar-width: none !important;
}

/* IE 和 Edge */
.custom-table :deep(*) {
  -ms-overflow-style: none !important;
}

.custom-table :deep(.arco-table-header) {
  background-color: var(--interface-list-header-bg) !important;
  position: sticky;
  top: 0;
  z-index: 2;
}

.custom-table :deep(.arco-table-th) {
  color: var(--interface-list-text) !important;
}

.custom-table :deep(.arco-table-td) {
  color: var(--interface-list-text) !important;
}

.custom-table :deep(.arco-table-content) {
  background-color: transparent !important;
}

.custom-table :deep(.arco-spin) {
  @apply h-full flex flex-col;
}

.custom-table :deep(.arco-spin-children) {
  @apply h-full flex flex-col;
}

/* 选中行样式 */
.custom-table :deep(.selected-row) {
  background-color: var(--interface-list-row-selected) !important;
}

.custom-table :deep(.arco-table-tr:hover) {
  background-color: var(--interface-list-row-hover) !important;
  cursor: pointer;
}

/* 空状态样式 */
:deep(.arco-empty) {
  color: var(--interface-list-empty);
}

:deep(.arco-input-wrapper),
:deep(.arco-input-wrapper input) {
  color: var(--interface-list-text) !important;
}

:deep(.arco-input-wrapper input::placeholder),
:deep(.arco-input-search-prefix),
:deep(.arco-input-search-suffix) {
  color: var(--interface-list-muted) !important;
}

/* 工具栏强制单行 + 固定宽度，避免切换模块时左右抖动 */
.list-toolbar {
  padding: 12px 16px;
}

.list-toolbar__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: nowrap;
  min-width: 0;
  width: 100%;
}

.list-toolbar__left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1 1 auto;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
}

.list-module-name {
  display: inline-block;
  width: 120px;
  max-width: 120px;
  min-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
  flex: 0 0 120px;
}

.list-filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;
  flex-wrap: nowrap;
  justify-content: flex-end;
  white-space: nowrap;
  width: 440px;
  min-width: 440px;
  max-width: 440px;
}

.list-filter-select {
  width: 120px !important;
  min-width: 120px !important;
  max-width: 120px !important;
  flex: 0 0 120px !important;
}

.list-filter-select--status {
  width: 104px !important;
  min-width: 104px !important;
  max-width: 104px !important;
  flex: 0 0 104px !important;
}

.list-filter-search {
  width: 200px !important;
  min-width: 200px !important;
  max-width: 200px !important;
  flex: 0 0 200px !important;
}

.list-filter-bar :deep(.arco-select),
.list-filter-bar :deep(.arco-select-view),
.list-filter-bar :deep(.arco-select-view-single),
.list-filter-bar :deep(.arco-input-wrapper),
.list-filter-bar :deep(.arco-input-search) {
  width: 100% !important;
  min-width: 0 !important;
  max-width: 100% !important;
}

.list-filter-bar :deep(.arco-select-view-value),
.list-filter-bar :deep(.arco-select-view-value-mirror) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 整表单行：不换行，超出省略 */
.custom-table :deep(.arco-table-th),
.custom-table :deep(.arco-table-td) {
  white-space: nowrap !important;
  vertical-align: middle !important;
}

.custom-table :deep(.arco-table-th) {
  padding: 8px 10px !important;
}

.custom-table :deep(.arco-table-td) {
  padding: 6px 10px !important;
  height: 40px !important;
  line-height: 1.2 !important;
}

.custom-table :deep(.arco-table-cell) {
  white-space: nowrap !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
}

/* URL 单元格：文本由 JS 做左侧省略（...end） */
.custom-table :deep(th.col-url),
.custom-table :deep(td.col-url) {
  max-width: 0;
}

.custom-table :deep(td.col-url .arco-table-cell) {
  overflow: hidden !important;
  text-overflow: clip !important;
}

.custom-table :deep(td.col-url .arco-table-cell > *),
.custom-table :deep(td.col-url .arco-tooltip-open) {
  display: block !important;
  width: 100% !important;
  min-width: 0 !important;
  max-width: 100% !important;
}

.list-url-end {
  display: block;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: clip;
  line-height: 1.2;
  box-sizing: border-box;
  font-variant-numeric: tabular-nums;
}

.list-cell-ellipsis {
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.2;
}

.list-time-cell {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  max-width: 100%;
  white-space: nowrap;
  line-height: 1;
  vertical-align: middle;
}

.list-time-text {
  display: inline-block;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
}

.list-time-icon {
  flex-shrink: 0;
}

.list-method-tag {
  white-space: nowrap;
}

.list-actions {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
  white-space: nowrap;
  flex-wrap: nowrap;
}

.list-actions :deep(.arco-btn) {
  flex-shrink: 0;
}

/* 模块列：至少完整显示 4 个汉字 */
.custom-table :deep(.col-module),
.custom-table :deep(.col-module .arco-table-cell) {
  overflow: visible !important;
  text-overflow: clip !important;
}

.list-module-name-cell {
  display: inline-block;
  min-width: 4em;
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.2;
  vertical-align: middle;
}

/* 创建人列：加宽并完整显示常见用户名 */
.custom-table :deep(.col-creator),
.custom-table :deep(.col-creator .arco-table-cell) {
  overflow: visible !important;
  text-overflow: clip !important;
}

.list-creator-name {
  display: inline-block;
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.2;
  vertical-align: middle;
}

/* 状态/方法列：禁止裁切标签文字 */
.custom-table :deep(.col-status),
.custom-table :deep(.col-method) {
  overflow: visible !important;
}

.custom-table :deep(.col-status .arco-table-cell),
.custom-table :deep(.col-method .arco-table-cell) {
  overflow: visible !important;
  text-overflow: clip !important;
}

/* 列表状态快捷菜单：贴合列表 Tag（Teleport 固定定位） */
.status-quick-wrap {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  max-width: 100%;
  vertical-align: middle;
}

.status-tag-trigger {
  cursor: pointer;
  user-select: none;
  flex-shrink: 0;
  max-width: none;
  overflow: visible;
  white-space: nowrap;
}

.status-tag-trigger :deep(.arco-tag-content),
.status-tag-trigger :deep(span) {
  overflow: visible !important;
  text-overflow: clip !important;
  white-space: nowrap !important;
}

.status-tag-trigger:hover {
  opacity: 0.9;
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.35);
}

.status-tag-trigger--loading {
  opacity: 0.6;
  pointer-events: none;
}
</style>

<style>
/* Teleport 到 body，不受 scoped / 表格裁剪影响 */
.status-quick-menu {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  box-sizing: border-box;
  padding: 4px;
  background: var(--color-bg-popup, #fff);
  border: 1px solid var(--color-fill-3, rgba(148, 163, 184, 0.28));
  border-radius: 4px;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
}

.status-quick-option {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  margin: 0;
  padding: 0;
  background: transparent;
  line-height: 1;
  cursor: pointer;
}

.status-quick-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-width: 0;
  height: 20px;
  padding: 0 6px;
  border-radius: 2px;
  box-sizing: border-box;
  color: #fff;
  font-size: 12px;
  font-weight: 500;
  line-height: 20px;
  letter-spacing: 0;
  text-align: center;
  white-space: nowrap;
}

.status-quick-pill--self_testing { background-color: rgb(255, 125, 0); }
.status-quick-pill--integrating { background-color: rgb(22, 93, 255); }
.status-quick-pill--completed { background-color: rgb(0, 180, 42); }
.status-quick-pill--deprecated { background-color: rgb(134, 144, 156); }

.status-quick-option--active .status-quick-pill {
  box-shadow: 0 0 0 1px rgba(22, 93, 255, 0.55);
}

.status-quick-option:hover .status-quick-pill {
  filter: brightness(1.05);
}
</style>