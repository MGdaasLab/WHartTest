<script setup lang="ts">
import { ref, reactive, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { testcaseService } from '../../services/testcaseService'
import { toArray } from '../../services/responseHelpers'
import type { ApiTestCase } from '../../types/testcase'
import { useProjectStore } from '@/store/projectStore'
import { useThemeStore } from '@/store/themeStore'
import { useEnvironmentStore } from '../../stores/environmentStore'
import TestCaseSearch from './TestCaseSearch.vue'
import TestCaseFilter from './TestCaseFilter.vue'
import TestCaseTable from './TestCaseTable.vue'
import ReferencedInterfacesDialog from './ReferencedInterfacesDialog.vue'
import { showExtractPersistenceNotice } from '../../utils/extractPersistence'
import { useAppI18n } from '@/composables/useAppI18n'

const projectStore = useProjectStore()
const environmentStore = useEnvironmentStore()
const themeStore = useThemeStore()
const router = useRouter()
const { isEnglish, tl } = useAppI18n()
const loading = ref(false)
const testcases = ref<ApiTestCase[]>([])
const isDarkTheme = computed(() => themeStore.isBlack)

const emit = defineEmits(['run'])

const TEST_CASES_TAB_QUERY = { tab: 'testcases' } as const

interface QueryParams {
  name?: string
  description?: string
  priority?: string
  group?: number
  tags?: number[]
  ordering?: string
  page?: number
  page_size?: number
}

const queryParams = reactive<QueryParams>({
  name: '',
  description: '',
  priority: undefined,
  group: undefined,
  tags: undefined,
  ordering: '-created_at',
  page: 1,
  page_size: 10
})

const pagination = reactive({
  current: 1,
  page_size: 10,
  total: 0,
  showTotal: true,
  showJumper: true,
  showPageSize: true
})

const fetchTestCases = async (page: number = 1) => {
  if (!projectStore.currentProjectId) return
  try {
    loading.value = true
    queryParams.page = page
    queryParams.page_size = pagination.page_size

    const res = await testcaseService.list(projectStore.currentProjectId, queryParams)
    if (res.success && res.data) {
      testcases.value = toArray<ApiTestCase>((res.data as any)?.results ?? res.data)
      pagination.total = (res.data as any).count || testcases.value.length
      pagination.current = page
    } else {
      throw new Error(res.error || tl('获取测试用例列表失败'))
    }
  } catch (error) {
    console.error('Failed to fetch test cases:', error)
    Message.error(error instanceof Error ? error.message : tl('获取测试用例列表失败'))
    testcases.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

watch(() => projectStore.currentProjectId, (newProjectId) => {
  if (newProjectId) {
    pagination.current = 1
    fetchTestCases(1)
  }
})

const handleSortChange = (dataIndex: string, direction: string) => {
  queryParams.ordering = direction === 'ascend' ? dataIndex : `-${dataIndex}`
  fetchTestCases()
}

const handlePageChange = (current: number) => {
  pagination.current = current
  fetchTestCases(current)
}

const handleSearch = () => {
  pagination.current = 1
  fetchTestCases(1)
}

const handleReset = () => {
  Object.assign(queryParams, {
    name: '',
    description: '',
    priority: undefined,
    group: undefined,
    tags: undefined,
    ordering: '-created_at',
    page: 1,
    page_size: pagination.page_size
  })
  pagination.current = 1
  fetchTestCases(1)
}

const updateSearchParams = (data: Pick<QueryParams, 'name' | 'description'>) => {
  Object.assign(queryParams, data)
}

const updateFilterParams = (data: Pick<QueryParams, 'priority' | 'group' | 'tags'>) => {
  Object.assign(queryParams, data)
}

const handleCreate = () => {
  router.push({ name: 'ApiTestCaseCreate', query: TEST_CASES_TAB_QUERY })
}

const handleEdit = (testcase: ApiTestCase) => {
  router.push({
    name: 'ApiTestCaseEdit',
    params: { id: testcase.id },
    query: TEST_CASES_TAB_QUERY
  })
}

const handleRun = async (testcase: ApiTestCase) => {
  if (!environmentStore.currentEnvironmentId) {
    Message.warning(tl('请先选择环境'))
    return
  }

  if (!projectStore.currentProjectId) return

  try {
    loading.value = true
    const res = await testcaseService.run(projectStore.currentProjectId, testcase.id!, {
      environment_id: Number(environmentStore.currentEnvironmentId)
    })
    if (res.success) {
      showExtractPersistenceNotice((res.data as any)?.extract_persistence)
      Message.success(tl('用例运行成功'))
    } else {
      throw new Error(res.error || tl('运行用例失败'))
    }
  } catch (error) {
    console.error('运行用例失败:', error)
    Message.error(error instanceof Error ? error.message : tl('运行用例失败'))
  } finally {
    loading.value = false
  }
}

const handleReport = (testcase: ApiTestCase) => {
  router.push({
    name: 'ApiTestCaseReports',
    params: { id: testcase.id },
    query: TEST_CASES_TAB_QUERY
  })
}

const referencedInterfacesVisible = ref(false)
const currentTestcase = ref<ApiTestCase | null>(null)

const handleLink = (testcase: ApiTestCase) => {
  currentTestcase.value = testcase
  referencedInterfacesVisible.value = true
}

const handleReferencedInterfacesClose = () => {
  currentTestcase.value = null
}

const formatDeleteCaseContent = (caseName: string) => {
  return isEnglish.value
    ? `Are you sure you want to delete test case "${caseName}"? This will also delete all test steps and execution records and cannot be undone.`
    : `确定要删除测试用例「${caseName}」吗？删除后将同时删除所有测试步骤和执行记录，且无法恢复。`
}

const handleCopy = async (testcase: ApiTestCase) => {
  if (!projectStore.currentProjectId || !testcase.id) return

  try {
    loading.value = true
    const res = await testcaseService.copy(projectStore.currentProjectId, testcase.id)
    if (res.success) {
      Message.success(tl('测试用例复制成功'))
      await fetchTestCases(pagination.current)
    } else {
      throw new Error(res.error || tl('复制测试用例失败'))
    }
  } catch (error) {
    console.error('复制测试用例失败:', error)
    Message.error(error instanceof Error ? error.message : tl('复制测试用例失败'))
  } finally {
    loading.value = false
  }
}

const handleDelete = async (testcase: ApiTestCase) => {
  if (!projectStore.currentProjectId) return

  Modal.confirm({
    title: tl('确认删除'),
    content: formatDeleteCaseContent(testcase.name),
    okText: tl('确认删除'),
    cancelText: tl('取消'),
    okButtonProps: {
      status: 'danger'
    },
    async onOk() {
      try {
        loading.value = true
        await testcaseService.delete(projectStore.currentProjectId!, testcase.id!)
        Message.success(tl('测试用例删除成功'))
        await fetchTestCases(pagination.current)
      } catch (error: any) {
        console.error('删除测试用例失败:', error)
        Message.error(tl('删除测试用例失败'))
      } finally {
        loading.value = false
      }
    }
  })
}

const handlePageSizeChange = (size: number) => {
  pagination.page_size = size
  pagination.current = 1
  fetchTestCases(1)
}

// 初始加载
fetchTestCases()
</script>

<template>
  <div class="api-testcases-panel h-full flex flex-col gap-4 p-4" :class="isDarkTheme ? 'api-testcases--dark' : 'api-testcases--light'">
    <!-- 搜索区域 -->
    <div class="panel-shell rounded-lg px-6 py-5 space-y-4">
      <div class="flex items-center gap-4">
        <div class="flex-1">
          <TestCaseSearch
            :model-value="{ name: queryParams.name, description: queryParams.description }"
            @update:model-value="updateSearchParams"
            @search="handleSearch"
            @reset="handleReset"
          />
        </div>
        <div class="flex-1">
          <TestCaseFilter
            :model-value="{
              priority: queryParams.priority,
              group: queryParams.group,
              tags: queryParams.tags
            }"
            :project-id="projectStore.currentProjectId"
            @update:model-value="updateFilterParams"
            @search="handleSearch"
          />
        </div>
        <div class="flex items-center gap-2">
          <a-button class="custom-reset-button" @click="handleReset">
            {{ tl('重置') }}
          </a-button>
          <a-button type="primary" class="custom-add-button" @click="handleCreate">
            {{ tl('新增用例') }}
          </a-button>
        </div>
      </div>
    </div>

    <!-- 内容区域 -->
    <div class="panel-shell flex-1 overflow-hidden">
      <div class="p-6">
        <TestCaseTable
          :data="testcases"
          :loading="loading"
          @sort="handleSortChange"
          @run="handleRun"
          @link="handleLink"
          @report="handleReport"
          @edit="handleEdit"
          @copy="handleCopy"
          @delete="handleDelete"
        />
      </div>
    </div>

    <!-- 分页区域 -->
    <div class="panel-shell px-6 py-5">
      <a-pagination
        v-model:current="pagination.current"
        v-model:page-size="pagination.page_size"
        :total="pagination.total"
        show-total
        show-jumper
        show-page-size
        class="flex justify-end"
        @change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      />
    </div>

    <!-- 关联接口弹窗 -->
    <ReferencedInterfacesDialog
      v-model:visible="referencedInterfacesVisible"
      :testcase-id="currentTestcase?.id || 0"
      :testcase-name="currentTestcase?.name || ''"
      @close="handleReferencedInterfacesClose"
    />
  </div>
</template>

<style scoped>
.api-testcases-panel {
  min-height: 0;
  --tc-panel-bg: color-mix(in srgb, var(--theme-card-bg) 92%, var(--theme-page-bg) 8%);
  --tc-panel-border: rgba(148, 163, 184, 0.16);
  --tc-panel-shadow: 0 14px 30px rgba(15, 23, 42, 0.08);
  --tc-input-bg: #ffffff;
  --tc-input-border: rgba(148, 163, 184, 0.18);
  --tc-input-bg-hover: color-mix(in srgb, var(--theme-card-bg) 88%, var(--theme-page-bg) 12%);
  --tc-table-header-bg: color-mix(in srgb, var(--theme-card-bg) 76%, var(--theme-page-bg) 24%);
  --tc-row-hover: rgba(15, 23, 42, 0.04);
  --tc-text: var(--theme-text);
  --tc-text-muted: var(--theme-text-secondary);
  --tc-text-subtle: var(--theme-text-tertiary);
  --tc-link: var(--theme-accent);
  --tc-link-hover: var(--theme-accent-hover);
  --tc-secondary-bg: rgba(148, 163, 184, 0.08);
  --tc-secondary-bg-hover: rgba(148, 163, 184, 0.14);
  --tc-secondary-border: rgba(148, 163, 184, 0.18);
  --tc-secondary-text: var(--theme-text-secondary);
  --tc-secondary-text-hover: var(--theme-text);
  --tc-more-bg: linear-gradient(to right, #e2e8f0, #cbd5e1);
  --tc-more-bg-hover: linear-gradient(to right, #cbd5e1, #94a3b8);
  --tc-more-text: #334155;
}

.api-testcases--dark {
  --tc-panel-bg: rgba(31, 41, 55, 0.58);
  --tc-panel-border: rgba(148, 163, 184, 0.12);
  --tc-panel-shadow: 0 18px 32px rgba(2, 6, 23, 0.28);
  --tc-input-bg: rgba(30, 41, 59, 0.5);
  --tc-input-border: rgba(148, 163, 184, 0.1);
  --tc-input-bg-hover: rgba(30, 41, 59, 0.72);
  --tc-table-header-bg: rgba(30, 41, 59, 0.5);
  --tc-row-hover: rgba(30, 41, 59, 0.5);
  --tc-secondary-bg: rgba(148, 163, 184, 0.1);
  --tc-secondary-bg-hover: rgba(148, 163, 184, 0.2);
  --tc-secondary-border: rgba(148, 163, 184, 0.2);
  --tc-secondary-text: #94a3b8;
  --tc-secondary-text-hover: #e2e8f0;
  --tc-more-bg: linear-gradient(to right, rgb(71, 85, 105), rgb(51, 65, 85));
  --tc-more-bg-hover: linear-gradient(to right, rgb(100, 116, 139), rgb(71, 85, 105));
  --tc-more-text: rgb(226, 232, 240);
}

.panel-shell {
  background: var(--tc-panel-bg);
  border: 1px solid var(--tc-panel-border);
  box-shadow: var(--tc-panel-shadow);
}

/* 自定义滚动条 */
.custom-scrollbar {
  scrollbar-width: none !important;
  -ms-overflow-style: none !important;
  &::-webkit-scrollbar {
    display: none !important;
  }
}

/* 分页样式 */
:deep(.arco-pagination) {
  .arco-pagination-item {
    border-radius: 4px !important;
    color: var(--tc-text-subtle) !important;
    background-color: transparent !important;
    border: 1px solid transparent !important;

    &:hover {
      color: var(--tc-link-hover) !important;
      background-color: rgba(var(--theme-accent-rgb), 0.1) !important;
      border-color: rgba(var(--theme-accent-rgb), 0.22) !important;
    }

    &.arco-pagination-item-active {
      background-color: rgba(var(--theme-accent-rgb), 0.14) !important;
      color: var(--tc-link-hover) !important;
      border-color: rgba(var(--theme-accent-rgb), 0.28) !important;
    }
  }

  .arco-pagination-jumper {
    .arco-input {
      border-radius: 4px !important;
      background-color: var(--tc-input-bg) !important;
      border: 1px solid var(--tc-input-border) !important;
      color: var(--tc-text) !important;

      &:hover, &:focus {
        border-color: rgba(var(--theme-accent-rgb), 0.42) !important;
        background-color: var(--tc-input-bg-hover) !important;
      }
    }
  }

  .arco-pagination-total {
    color: var(--tc-text-subtle) !important;
  }

  .arco-select-view {
    background-color: var(--tc-input-bg) !important;
    border: 1px solid var(--tc-input-border) !important;
    border-radius: 4px !important;
    color: var(--tc-text) !important;

    &:hover {
      border-color: rgba(var(--theme-accent-rgb), 0.42) !important;
      background-color: var(--tc-input-bg-hover) !important;
    }
  }
}

.custom-reset-button {
  background: var(--tc-secondary-bg) !important;
  border: 1px solid var(--tc-secondary-border) !important;
  color: var(--tc-secondary-text) !important;
  padding: 0 24px !important;
  height: 36px !important;
  border-radius: 8px !important;
  font-weight: 500 !important;
  transition: all 0.3s ease !important;

  &:hover {
    background: var(--tc-secondary-bg-hover) !important;
    border-color: rgba(var(--theme-accent-rgb), 0.22) !important;
    color: var(--tc-secondary-text-hover) !important;
    transform: translateY(-1px) !important;
  }

  &:active {
    transform: translateY(1px) !important;
  }
}

.custom-add-button {
  background: linear-gradient(to right, #3b82f6, #1d4ed8) !important;
  border: none !important;
  padding: 0 24px !important;
  height: 36px !important;
  border-radius: 8px !important;
  font-weight: 500 !important;
  transition: all 0.3s ease !important;
  box-shadow: 0 2px 6px rgba(59, 130, 246, 0.3) !important;

  &:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4) !important;
    background: linear-gradient(to right, #2563eb, #60a5fa) !important;
  }

  &:active {
    transform: translateY(1px) !important;
    box-shadow: 0 1px 3px rgba(59, 130, 246, 0.3) !important;
  }
}

:global(.arco-modal) {
  background: #ffffff !important;
  border: 1px solid rgba(148, 163, 184, 0.18) !important;
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.16) !important;
}

:global(.arco-modal .arco-modal-header) {
  background: #ffffff !important;
  border-bottom: 1px solid rgba(148, 163, 184, 0.14) !important;
}

:global(.arco-modal .arco-modal-title) {
  color: #0f172a !important;
}

:global(.arco-modal .arco-modal-content),
:global(.arco-modal .arco-modal-body) {
  background: #ffffff !important;
  color: #475569 !important;
}

:global(.arco-modal .arco-modal-footer) {
  background: #ffffff !important;
  border-top: 1px solid rgba(148, 163, 184, 0.14) !important;
}

:global(body.api-testing-theme .arco-modal) {
  background: rgb(31, 41, 55) !important;
  border-color: rgba(75, 85, 99, 0.5) !important;
  box-shadow: 0 18px 40px rgba(2, 6, 23, 0.35) !important;
}

:global(body.api-testing-theme .arco-modal .arco-modal-header) {
  background: rgb(31, 41, 55) !important;
  border-bottom-color: rgba(75, 85, 99, 0.4) !important;
}

:global(body.api-testing-theme .arco-modal .arco-modal-title) {
  color: rgb(226, 232, 240) !important;
}

:global(body.api-testing-theme .arco-modal .arco-modal-content),
:global(body.api-testing-theme .arco-modal .arco-modal-body) {
  background: rgb(31, 41, 55) !important;
  color: rgb(148, 163, 184) !important;
}

:global(body.api-testing-theme .arco-modal .arco-modal-footer) {
  background: rgb(31, 41, 55) !important;
  border-top-color: rgba(75, 85, 99, 0.4) !important;
}
</style>
