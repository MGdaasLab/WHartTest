<script setup lang="ts">
import { ref, onMounted, reactive, h, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Message, Modal, Select } from '@arco-design/web-vue'
import { Option } from '@arco-design/web-vue/es/select'
import { IconEdit, IconDelete, IconPlayArrow, IconPlus } from '@arco-design/web-vue/es/icon'
import { 
  getTestTaskSuite, 
  deleteTestTaskSuite, 
  createTestTaskExecution,
  removeCaseFromSuite,
  addCasesToSuite,
  getTestCases,
  getInterfaceCasesForTask,
  type InterfaceCase,
  type TestTaskCaseType,
  type TestTaskSuite,
  type TestCase 
} from '../../services/testTaskService'
import { toArray } from '../../services/responseHelpers'
import AddTestCaseModal from './AddTestCaseModal.vue'
import { useEnvironmentStore } from '../../stores/environmentStore'
import { useThemeStore } from '@/store/themeStore'

const router = useRouter()
const route = useRoute()
const loading = ref(false)
const testTaskSuite = ref<TestTaskSuite | null>(null)
const environmentStore = useEnvironmentStore()
const themeStore = useThemeStore()
const isDarkTheme = computed(() => themeStore.isBlack)

// 环境选择状态
const state = reactive({
  selectedEnvironmentId: 0,
  selectedEnvironment: null as any
})

// 添加用例相关
type TaskCaseOption = (TestCase | InterfaceCase) & {
  case_type: TestTaskCaseType
  selectionKey: string
  interface_name?: string
}

const addVisible = ref(false)
const addLoading = ref(false)
const allTestCases = ref<TaskCaseOption[]>([])
const pagination = ref({
  current: 1,
  pageSize: 10,
  total: 0
})

const makeCaseKey = (caseType: TestTaskCaseType, id: number) => `${caseType}:${id}`

const existingCaseKeys = computed(() => (
  testTaskSuite.value?.task_cases?.map(tc => {
    const caseType = (tc.case_type || 'scenario') as TestTaskCaseType
    const caseId = tc.case_id || tc.testcase_id || tc.interface_case_id
    return caseId ? makeCaseKey(caseType, Number(caseId)) : ''
  }).filter(Boolean) || []
))

const splitSelectedCases = (selectedKeys: string[]) => {
  const testcaseIds: number[] = []
  const interfaceCaseIds: number[] = []

  selectedKeys.forEach(key => {
    const [caseType, rawId] = String(key).split(':')
    const id = Number(rawId)
    if (!id) return
    if (caseType === 'interface') {
      interfaceCaseIds.push(id)
    } else {
      testcaseIds.push(id)
    }
  })

  return { testcaseIds, interfaceCaseIds }
}

// 从测试任务集中移除测试用例
const removeTestCase = async (record: any) => {
  try {
    const caseType = (record.case_type || 'scenario') as TestTaskCaseType
    const caseId = Number(record.case_id || record.testcase_id || record.interface_case_id)
    await removeCaseFromSuite(Number(route.params.id), caseType, caseId)
    Message.success('移除成功')
    // 重新加载测试任务集详情
    await fetchTestTaskSuite()
  } catch (error) {
    console.error('移除测试用例失败', error)
    Message.error('移除测试用例失败')
  }
}

// 获取测试任务集详情
const fetchTestTaskSuite = async () => {
  const id = Number(route.params.id)
  if (!id) {
    console.error('无效的任务ID')
    Message.error('无效的任务ID')
    return
  }

  loading.value = true
  try {
    const response = await getTestTaskSuite(id)

    if (response && response.status === 'success' && response.data) {
      testTaskSuite.value = response.data
    } else {
      throw new Error(response?.message || '获取测试任务集详情失败')
    }
  } catch (error) {
    console.error('获取测试任务集详情失败', error)
    if (error instanceof Error) {
      console.error('错误详情:', error.message)
      Message.error(error.message)
    } else {
      console.error('未知错误:', error)
      Message.error('获取测试任务集详情失败')
    }
  } finally {
    loading.value = false
  }
}

// 编辑测试任务集
const handleEdit = () => {
  router.push({
    name: 'ApiTestTaskEdit',
    params: { id: route.params.id }
  })
}

// 删除测试任务集
const handleDelete = async () => {
  try {
    await deleteTestTaskSuite(Number(route.params.id))
    Message.success('删除成功')
    router.push({ path: '/api-testing', query: { tab: 'testtasks' } })
  } catch (error) {
    console.error('删除测试任务集失败', error)
    Message.error('删除测试任务集失败')
  }
}

// 执行测试任务集
const handleRun = async () => {
  if (!testTaskSuite.value) {
    Message.warning('测试任务集数据不存在')
    return
  }

  if (testTaskSuite.value.task_cases.length === 0) {
    Message.warning('当前任务集没有关联任何测试用例')
    return
  }

  try {
    loading.value = true
    
    // 确保环境列表已加载
    await environmentStore.fetchEnvironments(testTaskSuite.value.project)
    
    if (environmentStore.environments.length === 0) {
      Message.warning('当前项目没有可用的环境，请先创建环境')
      return
    }

    // 初始化选中的环境为第一个环境
    state.selectedEnvironmentId = environmentStore.environments[0].id
    state.selectedEnvironment = environmentStore.environments[0]

    // 打开弹窗
    Modal.open({
      title: '执行测试任务',
      titleAlign: 'start',
      width: 600,
      maskClosable: false,
      modalClass: isDarkTheme.value ? 'testtask-run-modal testtask-run-modal--dark' : 'testtask-run-modal testtask-run-modal--light',
      content: () => modalContent(testTaskSuite.value!),
      okText: '开始执行',
      cancelText: '取消',
      okButtonProps: {
        type: 'primary',
        status: 'success'
      },
      async onOk() {
        if (!state.selectedEnvironmentId) {
          Message.warning('请选择执行环境')
          return false
        }

        try {
          loading.value = true
          const response = await createTestTaskExecution({
            task_suite_id: testTaskSuite.value!.id,
            environment_id: state.selectedEnvironmentId
          })

          if (response.status === 'success') {
            Message.success('任务执行已启动')
            // 询问用户是否查看执行详情
            Modal.confirm({
              title: '执行已启动',
              content: '是否立即查看执行详情？',
              okText: '查看详情',
              cancelText: '留在当前页面',
              onOk: () => {
                router.push({
                  name: 'ApiTestTaskExecutionDetail',
                  params: { id: response.data.id }
                })
              }
            })
          } else {
            throw new Error(response.message || '启动任务执行失败')
          }
        } catch (error) {
          console.error('启动任务执行失败:', error)
          Message.error(error instanceof Error ? error.message : '启动任务执行失败')
        } finally {
          loading.value = false
        }
      }
    })
  } catch (error) {
    console.error('加载环境列表失败:', error)
    Message.error('加载环境列表失败')
  } finally {
    loading.value = false
  }
}

// 环境选择弹窗内容
const modalContent = (taskSuite: TestTaskSuite) => {
  return h('div', {
    class: 'task-run-modal-content space-y-4'
  }, [
    h('div', { class: 'task-run-section space-y-2' }, [
      h('div', { class: 'task-run-section-title' }, '任务信息'),
      h('div', { class: 'task-run-section-card p-4 rounded-lg space-y-2' }, [
        h('div', { class: 'flex items-center gap-2' }, [
          h('span', { class: 'task-run-inline-label' }, '任务名称：'),
          h('span', { class: 'task-run-inline-value' }, taskSuite.name)
        ]),
        h('div', { class: 'flex items-center gap-2' }, [
          h('span', { class: 'task-run-inline-label' }, '用例数量：'),
          h('span', { class: 'task-run-inline-value' }, `${taskSuite.task_cases.length} 个`)
        ])
      ])
    ]),

    h('div', { class: 'task-run-section space-y-2' }, [
      h('div', { class: 'task-run-section-title' }, '执行环境'),
      h(Select, {
        modelValue: state.selectedEnvironmentId,
        'onUpdate:modelValue': (value: number) => {
          state.selectedEnvironmentId = value
          state.selectedEnvironment = environmentStore.environments.find(env => env.id === value) || environmentStore.environments[0]
        },
        placeholder: '请选择执行环境',
        allowClear: false,
        class: 'w-full task-run-select'
      }, {
        default: () => environmentStore.environments.map(env => 
          h(Option, {
            key: env.id,
            value: env.id,
            label: env.name
          })
        )
      })
    ]),
  ])
}

// 返回列表页
const goBack = () => {
  router.push({ path: '/api-testing', query: { tab: 'testtasks' } })
}

// 格式化日期
const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 优先级文本映射
const priorityTextMap: Record<string, string> = {
  'P0': '最高',
  'P1': '较高',
  'P2': '普通',
  'P3': '较低'
}

// 优先级颜色映射
const priorityColorMap: Record<string, string> = {
  'P0': 'red',
  'P1': 'orange',
  'P2': 'blue',
  'P3': 'green'
}

// 测试用例优先级颜色映射
const testCasePriorityColorMap: Record<string, string> = {
  'P0': 'red',
  'P1': 'orange',
  'P2': 'blue',
  'P3': 'green'
}

// 获取可添加的测试用例列表
const fetchTestCases = async () => {
  if (!testTaskSuite.value?.project) return
  
  addLoading.value = true
  try {
    const response = await getTestCases({
      project: testTaskSuite.value.project,
      page: 1,
      page_size: 1000,
      ordering: '-created_at'
    })
    const interfaceCaseResponse = await getInterfaceCasesForTask({
      project: testTaskSuite.value.project,
      page: 1,
      page_size: 1000,
      ordering: '-created_at'
    })

    const scenarioCases: TaskCaseOption[] = toArray<TestCase>(response.data?.results ?? response.data).map((item: TestCase) => ({
      ...item,
      case_type: 'scenario',
      selectionKey: makeCaseKey('scenario', item.id)
    }))
    const interfaceCases: TaskCaseOption[] = toArray<InterfaceCase>(interfaceCaseResponse.data?.results ?? interfaceCaseResponse.data).map((item: InterfaceCase) => ({
      ...item,
      case_type: 'interface',
      selectionKey: makeCaseKey('interface', item.id),
      interface_name: item.interface_info?.name || ''
    }))

    allTestCases.value = [...scenarioCases, ...interfaceCases]
    pagination.value.total = allTestCases.value.length
  } catch (error) {
    console.error('获取测试用例列表失败', error)
    Message.error('获取测试用例列表失败')
  } finally {
    addLoading.value = false
  }
}

// 打开添加用例弹窗
const openAddDialog = async () => {
  pagination.value.current = 1
  addVisible.value = true
  await fetchTestCases()
}

// 处理分页变化
const handlePageChange = (current: number) => {
  pagination.value.current = current
}

// 处理每页条数变化
const handlePageSizeChange = (pageSize: number) => {
  pagination.value.pageSize = pageSize
  pagination.value.current = 1
}

// 处理添加测试用例
const handleAdd = async (selectedKeys: string[]) => {
  try {
    const { testcaseIds, interfaceCaseIds } = splitSelectedCases(selectedKeys)
    await addCasesToSuite(Number(route.params.id), testcaseIds, interfaceCaseIds)
    Message.success('添加成功')
    addVisible.value = false
    // 重新加载测试任务集详情
    await fetchTestTaskSuite()
  } catch (error) {
    console.error('添加测试用例失败', error)
    Message.error('添加测试用例失败')
  }
}

onMounted(() => {
  fetchTestTaskSuite()
})
</script>

<template>
  <div
    class="test-task-detail h-full flex flex-col gap-4 p-4"
    :class="isDarkTheme ? 'test-task-detail--dark' : 'test-task-detail--light'"
  >
    <a-spin :loading="loading" class="flex-1">
      <div class="surface-panel surface-panel--hero rounded-lg px-6 py-4 mb-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-4">
            <h2 class="panel-title text-xl font-medium">
              {{ testTaskSuite?.name }}
            </h2>
            <a-tag :color="priorityColorMap[testTaskSuite?.priority || 'P2']">
              {{ priorityTextMap[testTaskSuite?.priority || 'P2'] }}
            </a-tag>
          </div>
          <div class="flex gap-3">
            <a-button type="outline" @click="goBack">返回</a-button>
            <a-button type="primary" status="success" class="transparent-btn" @click="handleRun">
              <template #icon><icon-play-arrow /></template>
              执行
            </a-button>
            <a-button type="primary" class="transparent-btn" @click="handleEdit">
              <template #icon><icon-edit /></template>
              编辑
            </a-button>
            <a-popconfirm
              content="确定要删除这个测试任务集吗？"
              @ok="handleDelete"
            >
              <a-button type="primary" status="danger" class="transparent-btn">
                <template #icon><icon-delete /></template>
                删除
              </a-button>
            </a-popconfirm>
          </div>
        </div>
      </div>

      <div class="surface-panel surface-panel--section rounded-lg px-6 py-5 mb-4">
        <h3 class="section-title text-lg font-medium mb-4">基本信息</h3>
        <div class="grid grid-cols-2 gap-6">
          <div class="flex flex-col gap-2">
            <div class="panel-label">描述</div>
            <div class="panel-value">{{ testTaskSuite?.description || '-' }}</div>
          </div>
          <div class="flex flex-col gap-2">
            <div class="panel-label">快速失败</div>
            <div class="panel-value">
              {{ testTaskSuite?.fail_fast ? '是' : '否' }}
            </div>
          </div>
          <div class="flex flex-col gap-2">
            <div class="panel-label">所属项目</div>
            <div class="panel-value">{{ testTaskSuite?.project_name }}</div>
          </div>
          <div class="flex flex-col gap-2">
            <div class="panel-label">创建人</div>
            <div class="panel-value">{{ testTaskSuite?.created_by_name }}</div>
          </div>
          <div class="flex flex-col gap-2">
            <div class="panel-label">创建时间</div>
            <div class="panel-value">{{ formatDate(testTaskSuite?.created_at || '') }}</div>
          </div>
          <div class="flex flex-col gap-2">
            <div class="panel-label">更新时间</div>
            <div class="panel-value">{{ formatDate(testTaskSuite?.updated_at || '') }}</div>
          </div>
        </div>
      </div>

      <div class="surface-panel surface-panel--section rounded-lg px-6 py-5">
        <div class="flex justify-between items-center mb-4">
          <div class="flex items-center gap-4">
            <h3 class="section-title text-lg font-medium">测试用例列表</h3>
            <div class="panel-label">
              共 {{ testTaskSuite?.task_cases?.length || 0 }} 个用例
            </div>
          </div>
          <div>
            <a-button
              type="outline"
              size="small"
              @click="openAddDialog"
            >
              <template #icon><icon-plus /></template>
              添加用例
            </a-button>
          </div>
        </div>
        
        <a-table
          :data="testTaskSuite?.task_cases || []"
          :pagination="false"
          :bordered="false"
          :scroll="{ y: 'calc(100vh - 600px)' }"
          :sticky-header="true"
          class="custom-table"
          stripe
        >
          <template #columns>
            <a-table-column title="序号" data-index="order" :width="80" align="center" />
            <a-table-column title="类型" data-index="case_type" :width="110" align="center">
              <template #cell="{ record }">
                <a-tag :color="record.case_type === 'interface' ? 'arcoblue' : 'purple'">
                  {{ record.case_type === 'interface' ? '接口用例' : '场景用例' }}
                </a-tag>
              </template>
            </a-table-column>
            <a-table-column title="用例名称" data-index="testcase_name" :width="200" align="center">
              <template #cell="{ record }">
                <span class="table-link cursor-pointer">
                  {{ record.testcase_name }}
                </span>
              </template>
            </a-table-column>
            <a-table-column title="关联接口" data-index="interface_name" :width="180" align="center">
              <template #cell="{ record }">
                <div class="table-muted-text">
                  {{ record.case_type === 'interface' ? (record.interface_name || '-') : '-' }}
                </div>
              </template>
            </a-table-column>
            <a-table-column title="描述" data-index="description" align="center">
              <template #cell="{ record }">
                <div class="table-muted-text">{{ record.description || '-' }}</div>
              </template>
            </a-table-column>
            <a-table-column title="优先级" data-index="priority" :width="100" align="center">
              <template #cell="{ record }">
                <a-tag :color="testCasePriorityColorMap[record.priority]">
                  {{ record.priority }}
                </a-tag>
              </template>
            </a-table-column>
            <a-table-column title="操作" :width="100" align="center">
              <template #cell="{ record }">
                <a-popconfirm
                  content="确定要移除这个测试用例吗？"
                  @ok="() => removeTestCase(record)"
                  position="left"
                  popup-container="body"
                  class="custom-popconfirm"
                >
                  <a-button
                    type="text"
                    status="danger"
                    size="mini"
                  >
                    <template #icon><icon-delete /></template>
                  </a-button>
                </a-popconfirm>
              </template>
            </a-table-column>
          </template>
        </a-table>
      </div>
    </a-spin>

    <!-- 添加用例弹窗组件 -->
    <AddTestCaseModal
      v-model:visible="addVisible"
      :loading="addLoading"
      :test-cases="allTestCases"
      :pagination="{
        current: pagination.current,
        pageSize: pagination.pageSize,
        total: pagination.total
      }"
      :existing-keys="existingCaseKeys"
      @page-change="handlePageChange"
      @page-size-change="handlePageSizeChange"
      @add="handleAdd"
    />
  </div>
</template>

<style scoped>
@reference "tailwindcss";
.test-task-detail {
  --tt-panel-bg: rgba(255, 255, 255, 0.94);
  --tt-panel-hero-bg: linear-gradient(135deg, rgba(248, 250, 252, 0.98), rgba(241, 245, 249, 0.96));
  --tt-border: rgba(148, 163, 184, 0.18);
  --tt-text: var(--color-text-1);
  --tt-text-muted: var(--color-text-2);
  --tt-text-subtle: var(--color-text-3);
  --tt-table-header: rgba(248, 250, 252, 0.98);
  --tt-table-row: rgba(255, 255, 255, 0.02);
  --tt-table-row-hover: rgba(59, 130, 246, 0.06);
  --tt-btn-border: rgba(148, 163, 184, 0.24);
  --tt-btn-text: rgb(71, 85, 105);
  --tt-btn-hover-bg: rgba(59, 130, 246, 0.08);
  --tt-btn-hover-border: rgba(59, 130, 246, 0.35);
  --tt-shadow: 0 12px 28px rgba(15, 23, 42, 0.06);
}

.test-task-detail--dark {
  --tt-panel-bg: rgba(30, 41, 59, 0.58);
  --tt-panel-hero-bg: rgba(31, 41, 55, 0.74);
  --tt-border: rgba(71, 85, 105, 0.32);
  --tt-text: rgb(241, 245, 249);
  --tt-text-muted: rgb(203, 213, 225);
  --tt-text-subtle: rgb(148, 163, 184);
  --tt-table-header: rgba(30, 41, 59, 0.5);
  --tt-table-row: rgba(255, 255, 255, 0.01);
  --tt-table-row-hover: rgba(30, 41, 59, 0.5);
  --tt-btn-border: rgba(148, 163, 184, 0.2);
  --tt-btn-text: rgb(148, 163, 184);
  --tt-btn-hover-bg: rgba(59, 130, 246, 0.1);
  --tt-btn-hover-border: rgba(96, 165, 250, 0.45);
  --tt-shadow: 0 10px 26px rgba(0, 0, 0, 0.18);
}

.surface-panel {
  background: var(--tt-panel-bg);
  border: 1px solid var(--tt-border);
  box-shadow: var(--tt-shadow);
}

.surface-panel--hero {
  background: var(--tt-panel-hero-bg);
}

.panel-title,
.section-title,
.panel-value {
  color: var(--tt-text);
}

.panel-label,
.table-muted-text {
  color: var(--tt-text-subtle);
}

.table-link {
  color: #2563eb;
}

.table-link:hover {
  color: #1d4ed8;
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
  background-color: var(--tt-table-header) !important;
  border-bottom: 1px solid var(--tt-border) !important;
  color: var(--tt-text) !important;
  font-weight: 500 !important;
  text-align: center !important;
}

.custom-table :deep(.arco-table-td) {
  background-color: var(--tt-table-row) !important;
  border-bottom: 1px solid var(--tt-border) !important;
  color: var(--tt-text-muted) !important;
}

.custom-table :deep(.arco-table-tr) {
  background-color: transparent !important;
}

.custom-table :deep(.arco-table-tr:hover) {
  background-color: var(--tt-table-row-hover) !important;
}

:deep(.arco-btn-outline) {
  border: 1px solid var(--tt-btn-border) !important;
  color: var(--tt-btn-text) !important;
  
  &:hover {
    border-color: var(--tt-btn-hover-border) !important;
    color: #2563eb !important;
    background-color: var(--tt-btn-hover-bg) !important;
  }
}

:deep(.transparent-btn) {
  opacity: 0.85 !important;
  backdrop-filter: blur(2px) !important;
}

:deep(.transparent-btn:hover) {
  opacity: 1 !important;
}

.task-run-section-title,
.task-run-inline-value {
  color: var(--tt-text);
}

.task-run-inline-label {
  color: var(--tt-text-subtle);
}

.task-run-section-card {
  background: rgba(148, 163, 184, 0.08);
  border: 1px solid var(--tt-border);
}

:deep(.custom-popconfirm .arco-trigger-popup) {
  @apply text-sm;
  max-width: 200px;
}

:deep(.custom-popconfirm .arco-popconfirm-message) {
  @apply text-sm mb-2;
}

:deep(.custom-popconfirm .arco-btn) {
  @apply text-sm h-7 px-3;
}

:deep(.testtask-run-modal--light) {
  --tt-run-bg: rgba(255, 255, 255, 0.99);
  --tt-run-border: rgba(148, 163, 184, 0.2);
  --tt-run-section-bg: rgba(248, 250, 252, 0.96);
  --tt-run-text: var(--color-text-1);
  --tt-run-subtle: var(--color-text-3);
}

:deep(.testtask-run-modal--dark) {
  --tt-run-bg: rgba(31, 41, 55, 0.98);
  --tt-run-border: rgba(71, 85, 105, 0.32);
  --tt-run-section-bg: rgba(17, 24, 39, 0.42);
  --tt-run-text: rgb(241, 245, 249);
  --tt-run-subtle: rgb(148, 163, 184);
}

:deep(.testtask-run-modal .arco-modal) {
  background: var(--tt-run-bg) !important;
  border: 1px solid var(--tt-run-border) !important;
}

:deep(.testtask-run-modal .arco-modal-header),
:deep(.testtask-run-modal .arco-modal-content),
:deep(.testtask-run-modal .arco-modal-footer) {
  background: var(--tt-run-bg) !important;
  border-color: var(--tt-run-border) !important;
}

:deep(.testtask-run-modal .arco-modal-title) {
  color: var(--tt-run-text) !important;
}

:deep(.testtask-run-modal .arco-select-view) {
  background: var(--tt-run-section-bg) !important;
  border-color: var(--tt-run-border) !important;
  color: var(--tt-run-text) !important;
}

:deep(.testtask-run-modal .arco-select-view-placeholder),
:deep(.testtask-run-modal .arco-select-view-suffix) {
  color: var(--tt-run-subtle) !important;
}

:global(body.api-testing-theme .arco-select-dropdown) {
  @apply !bg-gray-600/90;
  @apply !border-gray-500/50;
  backdrop-filter: blur(8px) !important;
}

:global(body.api-testing-theme .arco-select-dropdown .arco-select-option) {
  @apply !text-gray-100;
}

:global(body.api-testing-theme .arco-select-dropdown .arco-select-option:hover) {
  @apply !bg-gray-500/80;
}

:global(body.api-testing-theme .arco-select-dropdown .arco-select-option.arco-select-option-selected) {
  @apply !bg-blue-500/30 !text-blue-300;
}
</style>
