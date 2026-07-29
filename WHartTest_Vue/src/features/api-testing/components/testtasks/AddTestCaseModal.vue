<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconSearch } from '@arco-design/web-vue/es/icon'
import type { TableRowSelection } from '@arco-design/web-vue'
import type { InterfaceCase, TestCase, TestTaskCaseType } from '../../services/testTaskService'
import { useThemeStore } from '@/store/themeStore'

type TaskCaseOption = (TestCase | InterfaceCase) & {
  case_type: TestTaskCaseType
  selectionKey: string
  interface_name?: string
}

const props = defineProps<{
  visible: boolean
  loading: boolean
  testCases: TaskCaseOption[]
  pagination: {
    current: number
    pageSize: number
    total: number
  }
  existingKeys?: string[]
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  'add': [selectedKeys: string[]]
  'pageChange': [current: number]
  'pageSizeChange': [pageSize: number]
}>()

const themeStore = useThemeStore()
const isDarkTheme = computed(() => themeStore.isBlack)

// 使用计算属性处理 visible 的双向绑定
const modalVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value)
})

// 选中的测试用例
const selectedTestCases = ref<string[]>([])
// 搜索关键词
const searchKeyword = ref('')
const caseTypeFilter = ref<TestTaskCaseType | undefined>(undefined)

// 处理分页变化
const handlePageChange = (current: number) => {
  emit('pageChange', current)
}

// 处理每页条数变化
const handlePageSizeChange = (pageSize: number) => {
  emit('pageSizeChange', pageSize)
}

// 添加测试用例
const handleAdd = async () => {
  if (selectedTestCases.value.length === 0) {
    Message.warning('请选择要添加的测试用例')
    return
  }
  emit('add', [...selectedTestCases.value])
  selectedTestCases.value = []
}

// 关闭弹窗
const handleClose = () => {
  modalVisible.value = false
  selectedTestCases.value = []
  searchKeyword.value = ''
  caseTypeFilter.value = undefined
}

// 优先级颜色映射
const testCasePriorityColorMap: Record<string, string> = {
  'P0': 'red',
  'P1': 'orange',
  'P2': 'blue',
  'P3': 'green'
}

// 过滤测试用例
const matchedTestCases = computed(() => {
  let cases = props.testCases

  if (caseTypeFilter.value) {
    cases = cases.filter(item => item.case_type === caseTypeFilter.value)
  }

  if (!searchKeyword.value) return cases
  
  const keyword = searchKeyword.value.toLowerCase()
  return cases.filter(item =>
    (item.name?.toLowerCase().includes(keyword) || 
    item.description?.toLowerCase().includes(keyword))
  )
})

const filteredTestCases = computed(() => {
  const start = (props.pagination.current - 1) * props.pagination.pageSize
  const end = start + props.pagination.pageSize
  return matchedTestCases.value.slice(start, end)
})

watch([searchKeyword, caseTypeFilter], () => {
  emit('pageChange', 1)
})
</script>

<template>
  <a-modal
    v-model:visible="modalVisible"
    title="添加测试用例"
    :mask-closable="false"
    :footer="false"
    :align-center="false"
    :width="1200"
    :modal-class="isDarkTheme ? 'testtask-add-case-modal testtask-add-case-modal--dark' : 'testtask-add-case-modal testtask-add-case-modal--light'"
    @cancel="handleClose"
  >
    <a-spin :loading="loading">
      <div class="testtask-add-case flex flex-col gap-4">
        <div class="modal-section rounded p-3">
          <div class="flex items-center gap-3">
            <a-input-search
              v-model="searchKeyword"
              placeholder="搜索测试用例名称或描述"
              class="custom-search flex-1"
            >
              <template #prefix>
                <icon-search />
              </template>
            </a-input-search>
            <a-select
              v-model="caseTypeFilter"
              placeholder="全部类型"
              allow-clear
              class="case-type-filter"
            >
              <a-option value="scenario">场景用例</a-option>
              <a-option value="interface">接口用例</a-option>
            </a-select>
          </div>
        </div>

        <div class="modal-section rounded p-3 flex flex-col">
          <div class="section-title font-medium mb-3">测试用例列表</div>
          
          <div class="flex-1 overflow-x-auto overflow-y-auto hide-scrollbar" style="max-height: 400px">
            <a-table
              v-if="matchedTestCases.length > 0"
              :scroll="{ y: '100%' }"
              :data="filteredTestCases"
              :pagination="false"
              :bordered="false"
              :row-selection="{
                type: 'checkbox',
                showCheckedAll: true,
                selectedRowKeys: selectedTestCases
              } as TableRowSelection"
              :row-class="(record) => props.existingKeys?.includes(record.selectionKey) ? 'has-added' : ''"
              :row-key="'selectionKey'"
              @selection-change="selectedTestCases = $event"
              class="custom-table"
            >
              <template #columns>
                <a-table-column title="ID" data-index="id">
                  <template #cell="{ record }">
                    <div class="flex items-center gap-2">
                      <span>{{ record.id }}</span>
                      <a-tag v-if="props.existingKeys?.includes(record.selectionKey)" size="small" class="added-tag">
                        已添加
                      </a-tag>
                    </div>
                  </template>
                </a-table-column>
                <a-table-column title="类型" data-index="case_type" align="center">
                  <template #cell="{ record }">
                    <a-tag :color="record.case_type === 'interface' ? 'arcoblue' : 'purple'">
                      {{ record.case_type === 'interface' ? '接口用例' : '场景用例' }}
                    </a-tag>
                  </template>
                </a-table-column>
                <a-table-column title="用例名称" data-index="name" ellipsis tooltip />
                <a-table-column title="关联接口" data-index="interface_name" ellipsis tooltip>
                  <template #cell="{ record }">
                    {{ record.case_type === 'interface' ? (record.interface_name || '-') : '-' }}
                  </template>
                </a-table-column>
                <a-table-column title="描述" data-index="description" ellipsis tooltip />
                <a-table-column title="优先级" data-index="priority" align="center">
                  <template #cell="{ record }">
                    <a-tag :color="testCasePriorityColorMap[record.priority]">
                      {{ record.priority }}
                    </a-tag>
                  </template>
                </a-table-column>
              </template>
            </a-table>
            <div v-else class="empty-text text-center mt-20">
              没有找到匹配的测试用例
            </div>
          </div>

          <div class="pagination-shell flex justify-end mt-3 pt-3">
            <a-pagination
              :total="matchedTestCases.length"
              :current="pagination.current"
              :page-size="pagination.pageSize"
              :page-size-options="[10, 20, 30, 50]"
              @change="handlePageChange"
              @page-size-change="handlePageSizeChange"
              class="custom-pagination"
              size="small"
              show-total
              show-jumper
              show-page-size
            />
          </div>
        </div>
        
        <!-- 底部按钮 -->
        <div class="flex justify-end gap-2">
          <a-button @click="handleClose">取消</a-button>
          <a-button type="primary" @click="handleAdd" :disabled="selectedTestCases.length === 0">
            确定添加 ({{ selectedTestCases.length }})
          </a-button>
        </div>
      </div>
    </a-spin>
  </a-modal>
</template>

<style scoped>
.testtask-add-case {
  color: var(--tt-add-text);
}

:deep(.testtask-add-case-modal--light) {
  --tt-modal-bg: rgba(255, 255, 255, 0.98);
  --tt-modal-section-bg: rgba(248, 250, 252, 0.98);
  --tt-border: rgba(148, 163, 184, 0.18);
  --tt-text: var(--color-text-1);
  --tt-subtle: var(--color-text-3);
  --tt-input-bg: rgba(255, 255, 255, 0.98);
  --tt-input-bg-hover: rgba(248, 250, 252, 1);
  --tt-input-border: rgba(148, 163, 184, 0.2);
  --tt-table-header: rgba(248, 250, 252, 0.98);
  --tt-row-text: var(--color-text-2);
  --tt-row-hover: rgba(59, 130, 246, 0.06);
  --tt-row-checked: rgba(59, 130, 246, 0.08);
  --tt-added-row: rgba(226, 232, 240, 0.72);
  --tt-pagination: var(--color-text-2);
  --tt-pagination-border: rgba(148, 163, 184, 0.24);
  --tt-add-text: var(--color-text-1);
  --tt-tag-bg: rgba(226, 232, 240, 0.9);
  --tt-tag-text: rgb(51, 65, 85);
}

:deep(.testtask-add-case-modal--dark) {
  --tt-modal-bg: rgba(20, 27, 38, 0.98);
  --tt-modal-section-bg: rgba(29, 38, 51, 0.98);
  --tt-border: rgba(71, 85, 105, 0.35);
  --tt-text: rgb(226, 232, 240);
  --tt-subtle: rgb(148, 163, 184);
  --tt-input-bg: rgba(70, 84, 102, 0.4);
  --tt-input-bg-hover: rgba(70, 84, 102, 0.48);
  --tt-input-border: rgba(148, 163, 184, 0.18);
  --tt-table-header: rgba(30, 41, 59, 0.5);
  --tt-row-text: rgb(203, 213, 225);
  --tt-row-hover: rgba(30, 41, 59, 0.5);
  --tt-row-checked: rgba(22, 93, 255, 0.1);
  --tt-added-row: rgba(51, 65, 85, 0.35);
  --tt-pagination: rgb(148, 163, 184);
  --tt-pagination-border: rgba(148, 163, 184, 0.2);
  --tt-add-text: rgb(226, 232, 240);
  --tt-tag-bg: rgb(71, 85, 105);
  --tt-tag-text: rgb(241, 245, 249);
}

/* 隐藏滚动条但保持滚动功能 */
.hide-scrollbar {
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE and Edge */
}

.hide-scrollbar::-webkit-scrollbar {
  display: none; /* Chrome, Safari and Opera */
}

.modal-section {
  background: var(--tt-modal-section-bg);
  border: 1px solid var(--tt-border);
}

.case-type-filter {
  width: 140px;
  flex: 0 0 140px;
}

:deep(.testtask-add-case-modal .arco-modal) {
  background: var(--tt-modal-bg) !important;
  border: 1px solid var(--tt-border) !important;
}

:deep(.testtask-add-case-modal .arco-modal-header) {
  background: var(--tt-modal-bg) !important;
  border-bottom-color: var(--tt-border) !important;
}

:deep(.testtask-add-case-modal .arco-modal-title) {
  color: var(--tt-text) !important;
}

:deep(.testtask-add-case-modal .arco-modal-body) {
  padding: 20px !important;
  background-color: var(--tt-modal-bg) !important;
  width: 100% !important;
  box-sizing: border-box !important;
  overflow: hidden !important;
}

:deep(.testtask-add-case-modal .arco-modal-footer) {
  background: var(--tt-modal-bg) !important;
  border-top-color: var(--tt-border) !important;
}

.section-title,
.custom-table :deep(.arco-table-th),
.custom-table :deep(.arco-table-th .arco-table-th-item-title) {
  color: var(--tt-text) !important;
}

.empty-text,
.custom-pagination :deep(.arco-pagination-total) {
  color: var(--tt-subtle) !important;
}

.pagination-shell {
  border-top: 1px solid var(--tt-border);
}

.custom-search :deep(.arco-input-wrapper) {
  background-color: var(--tt-input-bg) !important;
  border-color: var(--tt-input-border) !important;
}

.custom-search :deep(.arco-input-wrapper:hover),
.custom-search :deep(.arco-input-wrapper.arco-input-focus) {
  background-color: var(--tt-input-bg-hover) !important;
  border-color: #3b82f6 !important;
}

.custom-search :deep(.arco-input) {
  color: var(--tt-text) !important;
}

.custom-search :deep(.arco-input-search-btn) {
  background-color: transparent !important;
  border-color: transparent !important;
  color: var(--tt-subtle) !important;
}

.custom-table :deep(.arco-table) {
  background-color: transparent !important;
}

.custom-table :deep(.arco-table-container) {
  background-color: transparent !important;
  border: none !important;
  width: 100% !important;
  min-width: fit-content !important;
}

.custom-table :deep(.arco-table) {
  width: 100% !important;
  min-width: fit-content !important;
}

.custom-table :deep(.arco-table-header) {
  background-color: transparent !important;
  table-layout: fixed !important;
}

.custom-table :deep(.arco-table-body) {
  background-color: transparent !important;
  table-layout: fixed !important;
}

.custom-table :deep(.arco-table-td) {
  padding: 8px 16px !important;
  height: 40px !important;
  line-height: 24px !important;
  color: var(--tt-row-text) !important;
}

.custom-table :deep(.arco-table-th) {
  background-color: var(--tt-table-header) !important;
  border-bottom: 1px solid var(--tt-border) !important;
  font-weight: 500 !important;
  text-align: center !important;
  padding: 12px !important;
}

.custom-table :deep(.arco-table-tr) {
  background-color: transparent !important;
}

.custom-table :deep(.arco-table-tr:has([class*="added-tag"])) {
  background-color: var(--tt-added-row) !important;
  
  td {
    color: var(--tt-subtle) !important;
  }
  
  &:hover {
    background-color: var(--tt-added-row) !important;
  }
}

.custom-table :deep(.arco-table-tr:hover) {
  background-color: var(--tt-row-hover) !important;
}

.custom-table :deep(.arco-table-tr-checked) {
  background-color: var(--tt-row-checked) !important;
}

.custom-table :deep(.has-added) {
  background-color: var(--tt-added-row) !important;
  
  td {
    color: var(--tt-subtle) !important;
  }
  
  &:hover {
    background-color: var(--tt-added-row) !important;
  }
  
  .arco-checkbox {
    cursor: not-allowed;
  }
}

.custom-table :deep(.added-tag) {
  background-color: var(--tt-tag-bg) !important;
  border: none !important;
  color: var(--tt-tag-text) !important;
  font-size: 12px !important;
  padding: 0 8px !important;
  height: 20px !important;
  line-height: 20px !important;
  font-weight: 500 !important;
}

.custom-table :deep(.disabled-row) {
  opacity: 0.5 !important;
  cursor: not-allowed !important;
  background-color: var(--tt-added-row) !important;
}

.custom-table :deep(.disabled-row:hover) {
  background-color: var(--tt-added-row) !important;
}

.custom-table :deep(.disabled-row .arco-checkbox) {
  cursor: not-allowed !important;
}

.custom-pagination :deep(.arco-pagination-item) {
  background-color: transparent !important;
  border-color: var(--tt-pagination-border) !important;
  color: var(--tt-pagination) !important;
  min-width: 28px !important;
  height: 28px !important;
  line-height: 28px !important;
}

.custom-pagination :deep(.arco-pagination-item:hover),
.custom-pagination :deep(.arco-pagination-item-active) {
  border-color: #3b82f6 !important;
  color: #3b82f6 !important;
}

.custom-pagination :deep(.arco-select-view) {
  background-color: transparent !important;
  border-color: var(--tt-pagination-border) !important;
  color: var(--tt-pagination) !important;
  height: 28px !important;
  line-height: 28px !important;
}

.custom-pagination :deep(.arco-select-view:hover) {
  border-color: #3b82f6 !important;
}

.custom-pagination :deep(.arco-pagination-jumper) {
  height: 28px !important;
  line-height: 28px !important;
}

.custom-pagination :deep(.arco-pagination-jumper input) {
  background-color: transparent !important;
  border-color: var(--tt-pagination-border) !important;
  color: var(--tt-pagination) !important;
  height: 28px !important;
}

.custom-pagination :deep(.arco-pagination-jumper input:hover),
.custom-pagination :deep(.arco-pagination-jumper input:focus) {
  border-color: #3b82f6 !important;
}
</style>
