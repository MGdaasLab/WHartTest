<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { Message } from '@arco-design/web-vue'
import { testcaseService } from '../../services/testcaseService'
import { toArray } from '../../services/responseHelpers'
import { useProjectStore } from '@/store/projectStore'
import { useThemeStore } from '@/store/themeStore'

interface ReferencedInterface {
  interface: {
    id: number
    name: string
    method: string
    url: string
    module: { id: number; name: string } | null
    project: { id: number; name: string }
  }
  step: {
    id: number
    name: string
    order: number
  }
}

const props = defineProps<{
  visible: boolean
  testcaseId: number
  testcaseName: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', visible: boolean): void
  (e: 'close'): void
}>()

const projectStore = useProjectStore()
const themeStore = useThemeStore()
const loading = ref(false)
const interfaces = ref<ReferencedInterface[]>([])
const currentPage = ref(1)
const pageSize = ref(10)
const isDarkTheme = computed(() => themeStore.isBlack)

const currentPageData = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return interfaces.value?.slice(start, end) || []
})

const fetchReferencedInterfaces = async () => {
  if (!projectStore.currentProjectId) return
  try {
    loading.value = true
    const res = await testcaseService.referencedInterfaces(projectStore.currentProjectId, props.testcaseId)
    if (res.success && res.data) {
      interfaces.value = []
      const data = toArray<any>((res.data as any)?.results ?? res.data)
      data.forEach((item: any) => {
        if (item.steps && Array.isArray(item.steps)) {
          item.steps.forEach((step: {
            id: number
            name: string
            order: number
            sync_fields?: any[]
            last_sync_time?: string | null
          }) => {
            interfaces.value.push({
              interface: {
                id: item.id,
                name: item.name,
                method: item.method,
                url: item.url,
                module: typeof item.module === 'string'
                  ? { id: 0, name: item.module }
                  : (item.module || null),
                project: { id: props.testcaseId, name: props.testcaseName }
              },
              step: {
                id: step.id,
                name: step.name,
                order: step.order
              }
            })
          })
        }
      })
    } else {
      Message.error('获取关联接口失败')
    }
  } catch (error) {
    console.error('获取关联接口失败:', error)
    Message.error('获取关联接口失败')
  } finally {
    loading.value = false
  }
}

const getMethodColor = (method: string) => {
  const colorMap: Record<string, string> = {
    GET: 'blue',
    POST: 'green',
    PUT: 'orange',
    DELETE: 'red',
    PATCH: 'purple'
  }
  return colorMap[method] || 'gray'
}

const handleClose = () => {
  emit('update:visible', false)
  emit('close')
}

const handlePageChange = (page: number) => {
  currentPage.value = page
}

const handlePageSizeChange = (size: number) => {
  pageSize.value = size
  currentPage.value = 1
}

const resetPagination = () => {
  currentPage.value = 1
}

watch(
  () => props.visible,
  (newVal) => {
    if (newVal && props.testcaseId) {
      resetPagination()
      fetchReferencedInterfaces()
    } else {
      interfaces.value = []
    }
  }
)
</script>

<template>
  <a-modal
    :visible="visible"
    :width="1000"
    :mask-closable="true"
    :footer="false"
    :modal-class="isDarkTheme ? 'referenced-interfaces-modal referenced-interfaces-modal--dark' : 'referenced-interfaces-modal referenced-interfaces-modal--light'"
    unmount-on-close
    @update:visible="val => emit('update:visible', val)"
    @cancel="handleClose"
  >
    <template #title>
      <span>测试用例「{{ testcaseName }}」关联接口</span>
    </template>

    <div class="flex flex-col" style="max-height: calc(85vh - 120px)">
      <a-spin :loading="loading" class="flex-1 min-h-0">
        <div class="h-full flex flex-col">
          <div class="flex-1 overflow-auto">
            <a-table
              :data="currentPageData"
              :pagination="false"
              :bordered="false"
              size="small"
              class="!w-full"
              :scroll="{ y: '100%' }"
              :scrollbar="false"
            >
              <template #columns>
                <a-table-column title="序号" align="center" :width="80">
                  <template #cell="{ record }">
                    <div class="flex justify-center items-center">
                      <a-tag>{{ record.step.order }}</a-tag>
                    </div>
                  </template>
                </a-table-column>
                <a-table-column title="步骤名称" align="center" :width="200">
                  <template #cell="{ record }">
                    <a-typography-paragraph :ellipsis="{ rows: 1 }" class="!text-center !mb-0">
                      {{ record.step.name }}
                    </a-typography-paragraph>
                  </template>
                </a-table-column>
                <a-table-column title="接口名称" align="center" :width="200">
                  <template #cell="{ record }">
                    <a-typography-paragraph :ellipsis="{ rows: 1 }" class="!text-center !mb-0">
                      {{ record.interface.name }}
                    </a-typography-paragraph>
                  </template>
                </a-table-column>
                <a-table-column title="请求方法" align="center" :width="100">
                  <template #cell="{ record }">
                    <div class="flex justify-center items-center">
                      <a-tag :color="getMethodColor(record.interface.method)">
                        {{ record.interface.method }}
                      </a-tag>
                    </div>
                  </template>
                </a-table-column>
                <a-table-column title="接口地址" align="center" :width="200">
                  <template #cell="{ record }">
                    <a-typography-paragraph :ellipsis="{ rows: 1 }" class="!text-center !mb-0">
                      {{ record.interface.url }}
                    </a-typography-paragraph>
                  </template>
                </a-table-column>
                <a-table-column title="所属模块" align="center">
                  <template #cell="{ record }">
                    <span class="block text-center">{{ record.interface.module?.name || '-' }}</span>
                  </template>
                </a-table-column>
              </template>
            </a-table>
          </div>
          <div v-if="interfaces?.length > 0" class="pagination-shell flex justify-end pt-4 mt-auto border-t">
            <a-pagination
              v-model:current="currentPage"
              :total="interfaces?.length || 0"
              :page-size="pageSize"
              show-total
              show-page-size
              :page-size-options="[10, 20, 50, interfaces?.length || 0]"
              size="small"
              @change="handlePageChange"
              @page-size-change="handlePageSizeChange"
            />
          </div>
        </div>
      </a-spin>
    </div>
  </a-modal>
</template>

<style scoped>
@reference "tailwindcss";
:deep(.referenced-interfaces-modal--light) {
  --rid-modal-bg: rgba(255, 255, 255, 0.99);
  --rid-modal-border: rgba(148, 163, 184, 0.18);
  --rid-header-bg: rgba(248, 250, 252, 0.96);
  --rid-row-bg: rgba(255, 255, 255, 0.96);
  --rid-row-hover: rgba(59, 130, 246, 0.06);
  --rid-text: var(--color-text-1);
  --rid-text-muted: var(--color-text-2);
  --rid-text-subtle: var(--color-text-3);
  --rid-tag-bg: rgba(226, 232, 240, 0.92);
  --rid-tag-text: rgb(71, 85, 105);
}

:deep(.referenced-interfaces-modal--dark) {
  --rid-modal-bg: rgba(17, 24, 39, 0.98);
  --rid-modal-border: rgba(71, 85, 105, 0.32);
  --rid-header-bg: rgba(31, 41, 55, 0.9);
  --rid-row-bg: rgba(31, 41, 55, 0.78);
  --rid-row-hover: rgba(51, 65, 85, 0.78);
  --rid-text: rgb(226, 232, 240);
  --rid-text-muted: rgb(203, 213, 225);
  --rid-text-subtle: rgb(148, 163, 184);
  --rid-tag-bg: rgba(51, 65, 85, 0.88);
  --rid-tag-text: rgb(226, 232, 240);
}

:deep(.referenced-interfaces-modal .arco-modal) {
  background: var(--rid-modal-bg) !important;
  border: 1px solid var(--rid-modal-border) !important;
  border-radius: 12px !important;
}

:deep(.referenced-interfaces-modal .arco-modal-header),
:deep(.referenced-interfaces-modal .arco-modal-footer) {
  background: var(--rid-modal-bg) !important;
  border-color: var(--rid-modal-border) !important;
}

:deep(.referenced-interfaces-modal .arco-modal-title) {
  color: var(--rid-text) !important;
}

:deep(.referenced-interfaces-modal .arco-modal-body) {
  background: var(--rid-modal-bg) !important;
}

:deep(.referenced-interfaces-modal .arco-table) {
  background: transparent !important;
}

:deep(.referenced-interfaces-modal .arco-table-container) {
  @apply !h-full;
  border: none !important;
  background: transparent !important;
}

:deep(.referenced-interfaces-modal .arco-table-body) {
  @apply !h-full !overflow-auto;
}

:deep(.referenced-interfaces-modal .arco-table-header) {
  @apply !sticky !top-0 !z-10;
  border: none !important;
  background: var(--rid-header-bg) !important;
  backdrop-filter: blur(8px) !important;
}

:deep(.referenced-interfaces-modal .arco-table-size-small .arco-table-th) {
  padding: 8px 4px !important;
  white-space: nowrap !important;
  background: transparent !important;
  border-bottom: 1px solid var(--rid-modal-border) !important;
  color: var(--rid-text-subtle) !important;
  font-weight: 500 !important;
  height: 36px !important;
  line-height: 20px !important;
}

:deep(.referenced-interfaces-modal .arco-table-size-small .arco-table-td) {
  padding: 8px 4px !important;
  border-bottom: 1px solid var(--rid-modal-border) !important;
  color: var(--rid-text-muted) !important;
  background: var(--rid-row-bg) !important;
  height: 36px !important;
  line-height: 20px !important;
}

:deep(.referenced-interfaces-modal .arco-table-tr:hover .arco-table-td) {
  background: var(--rid-row-hover) !important;
}

:deep(.referenced-interfaces-modal .arco-table-td),
:deep(.referenced-interfaces-modal .arco-table-th) {
  @apply !align-middle;
}

:deep(.referenced-interfaces-modal .arco-typography) {
  color: var(--rid-text-muted) !important;
  margin-bottom: 0 !important;
}

:deep(.referenced-interfaces-modal .arco-tag) {
  border: none !important;
  font-weight: 500 !important;
  padding: 2px 8px !important;
  border-radius: 4px !important;
  font-size: 12px !important;
  line-height: 18px !important;
  transition: all 0.2s ease-in-out !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  min-width: 60px !important;
}

:deep(.referenced-interfaces-modal .arco-tag:not(.arco-tag-blue):not(.arco-tag-green):not(.arco-tag-orange):not(.arco-tag-red):not(.arco-tag-purple)) {
  color: var(--rid-tag-text) !important;
  background: var(--rid-tag-bg) !important;
}

:deep(.referenced-interfaces-modal .arco-tag) {
  &.arco-tag-blue {
    color: #60a5fa !important;
    background-color: rgba(59, 130, 246, 0.1) !important;
  }

  &.arco-tag-green {
    color: #4ade80 !important;
    background-color: rgba(74, 222, 128, 0.1) !important;
  }

  &.arco-tag-orange {
    color: #fb923c !important;
    background-color: rgba(251, 146, 60, 0.1) !important;
  }

  &.arco-tag-red {
    color: #f87171 !important;
    background-color: rgba(248, 113, 113, 0.1) !important;
  }

  &.arco-tag-purple {
    color: #c084fc !important;
    background-color: rgba(192, 132, 252, 0.1) !important;
  }
}

:deep(.referenced-interfaces-modal .arco-spin) {
  .arco-spin-dot-list {
    .arco-spin-dot-item {
      background-color: #60a5fa !important;
    }
  }
}

:deep(.referenced-interfaces-modal .custom-table) {
  .arco-table-body,
  .arco-scrollbar,
  .arco-scrollbar-container,
  .arco-table-body-wrapper,
  .arco-scrollbar__wrap,
  .arco-virtual-list,
  .arco-virtual-list-holder {
    &::-webkit-scrollbar {
      width: 0 !important;
      height: 0 !important;
      display: none !important;
    }
    scrollbar-width: none !important;
    -ms-overflow-style: none !important;
  }
}

.pagination-shell {
  border-top-color: var(--rid-modal-border) !important;
}

:deep(.referenced-interfaces-modal .arco-pagination) {
  .arco-pagination-item {
    background: transparent !important;
    border-color: var(--rid-modal-border) !important;
    color: var(--rid-text-subtle) !important;

    &:hover {
      border-color: #2563eb !important;
      color: #2563eb !important;
      background: rgba(59, 130, 246, 0.1) !important;
    }

    &.arco-pagination-item-active {
      border-color: #2563eb !important;
      color: #2563eb !important;
      background: rgba(59, 130, 246, 0.1) !important;
    }
  }

  .arco-pagination-total {
    color: var(--rid-text-subtle) !important;
  }

  .arco-select-view {
    background: transparent !important;
    border-color: var(--rid-modal-border) !important;
    color: var(--rid-text-subtle) !important;

    &:hover {
      border-color: #2563eb !important;
    }
  }

  .arco-pagination-jumper {
    .arco-input {
      background: transparent !important;
      border-color: var(--rid-modal-border) !important;
      color: var(--rid-text-subtle) !important;

      &:hover {
        border-color: #2563eb !important;
      }

      &:focus {
        border-color: #2563eb !important;
        box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.2) !important;
      }
    }
  }
}
</style>
