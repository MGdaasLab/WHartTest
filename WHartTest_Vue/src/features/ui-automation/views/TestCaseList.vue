<template>
  <div class="testcase-list">
    <div class="page-header">
      <div class="search-box">
        <a-select
          v-model="filters.module"
          :placeholder="pageText.selectModule"
          allow-clear
          style="width: 160px"
          @change="onSearch"
        >
          <a-option v-for="mod in moduleOptions" :key="mod.id" :value="mod.id">
            {{ mod.name }}
          </a-option>
        </a-select>
        <a-select
          v-model="filters.level"
          :placeholder="pageText.caseLevel"
          allow-clear
          style="width: 120px"
          @change="onSearch"
        >
          <a-option v-for="option in levelOptions" :key="option.value" :value="option.value">
            {{ option.value }}
          </a-option>
        </a-select>
        <a-input-search
          v-model="filters.search"
          :placeholder="pageText.searchCaseName"
          allow-clear
          style="width: 200px"
          @search="onSearch"
          @clear="onSearch"
        />
      </div>
      <div class="action-buttons">
        <a-select
          v-model="selectedActuator"
          :placeholder="pageText.selectActuator"
          allow-clear
          style="width: 150px"
          @focus="fetchActuators"
        >
          <template #empty>
            <div style="padding: 8px; text-align: center; color: var(--color-text-3)">
              {{ pageText.noOnlineActuators }}
            </div>
          </template>
          <a-option v-for="act in actuators" :key="act.id" :value="act.id" :disabled="!act.is_open">
            {{ act.name || act.id }}
            <a-tag v-if="act.is_open" color="green" size="small" style="margin-left: 4px">{{ pageText.online }}</a-tag>
            <a-tag v-else color="gray" size="small" style="margin-left: 4px">{{ pageText.offline }}</a-tag>
          </a-option>
        </a-select>
        <a-select
          v-model="selectedEnvConfig"
          :placeholder="pageText.executionEnvironment"
          allow-clear
          style="width: 150px"
        >
          <a-option v-for="env in envConfigs" :key="env.id" :value="env.id">
            {{ formatEnvLabel(env) }}
          </a-option>
        </a-select>
        <a-button
          type="primary"
          status="success"
          :disabled="selectedRowKeys.length === 0 || executingIds.length > 0"
          :loading="executingIds.length > 0"
          @click="runBatchTestCases"
        >
          <template #icon><icon-thunderbolt /></template>
          {{ batchExecuteLabel }}
        </a-button>
        <a-popconfirm
          :content="pageText.batchDeleteConfirm"
          @ok="batchDeleteTestCases"
        >
          <a-button
            type="primary"
            status="danger"
            :disabled="selectedRowKeys.length === 0"
          >
            <template #icon><icon-delete /></template>
            {{ batchDeleteLabel }}
          </a-button>
        </a-popconfirm>
        <a-button type="primary" @click="showAddModal">
          <template #icon><icon-plus /></template>
          {{ pageText.addCase }}
        </a-button>
      </div>
    </div>

    <a-table
      :key="`testcase-table-${locale}`"
      :columns="columns"
      :data="testcaseData"
      :pagination="pagination"
      :loading="loading"
      :scroll="{ x: 1260 }"
      :row-selection="{ type: 'checkbox', showCheckedAll: true }"
      v-model:selectedKeys="selectedRowKeys"
      row-key="id"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
    >
      <template #level="{ record }">
        <a-tag :color="levelColors[record.level as CaseLevel]">{{ record.level }}</a-tag>
      </template>
      <template #status="{ record }">
        <a-tag :color="statusColors[record.status as ExecutionStatus]">
          {{ formatStatusLabel(record.status as ExecutionStatus) }}
        </a-tag>
      </template>
      <template #step_count="{ record }">
        <a-tag color="cyan">{{ formatStepCount(record.step_count) }}</a-tag>
      </template>
      <template #created_at="{ record }">
        {{ formatDate(record.created_at) }}
      </template>
      <template #operations="{ record }">
        <a-space :size="4">
          <a-button type="text" size="mini" @click="viewSteps(record)">
            <template #icon><icon-ordered-list /></template>
            {{ pageText.steps }}
          </a-button>
          <a-button
            type="text"
            size="mini"
            :loading="isExecuting(record.id)"
            :disabled="isExecuting(record.id)"
            @click="runTestCase(record)"
          >
            <template #icon><icon-play-arrow /></template>
            {{ isExecuting(record.id) ? pageText.running : pageText.run }}
          </a-button>
          <a-button type="text" size="mini" @click="editTestCase(record)">
            <template #icon><icon-edit /></template>
            {{ pageText.edit }}
          </a-button>
          <a-button type="text" size="mini" @click="copyTestCase(record)">
            <template #icon><icon-copy /></template>
            {{ pageText.copy }}
          </a-button>
          <a-popconfirm :content="pageText.deleteCaseConfirm" @ok="deleteTestCase(record)">
            <a-button type="text" status="danger" size="mini">
              <template #icon><icon-delete /></template>
              {{ pageText.delete }}
            </a-button>
          </a-popconfirm>
        </a-space>
      </template>
    </a-table>

    <!-- 新增/编辑弹窗 -->
    <a-modal
      v-model:visible="modalVisible"
      :title="testCaseModalTitle"
      :ok-loading="submitting"
      width="600px"
      @before-ok="handleSubmit"
      @cancel="handleCancel"
    >
      <a-form ref="formRef" :model="formData" :rules="rules" layout="vertical">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="module" :label="pageText.module" required>
              <a-select v-model="formData.module" :placeholder="pageText.selectModule">
                <a-option v-for="mod in moduleOptions" :key="mod.id" :value="mod.id">
                  {{ mod.name }}
                </a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="level" :label="pageText.caseLevel" required>
              <a-select v-model="formData.level">
                <a-option v-for="option in levelOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </a-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item field="name" :label="pageText.caseName" required>
          <a-input v-model="formData.name" :placeholder="pageText.enterCaseName" :max-length="255" />
        </a-form-item>
        <a-form-item field="description" :label="pageText.caseDescription">
          <a-textarea v-model="formData.description" :placeholder="pageText.enterCaseDescription" :auto-size="{ minRows: 2, maxRows: 4 }" />
        </a-form-item>
      
          <a-form-item label="附件">
            <FileAttachmentPicker
              v-model="formData.file_ids"
              :project-id="projectStore.currentProjectId || 0"
              button-text="上传附件"
            />
          </a-form-item>
</a-form>
    </a-modal>

    <!-- 步骤管理抽屉 -->
    <a-drawer
      v-model:visible="stepsDrawerVisible"
      :title="stepsDrawerTitle"
      :width="900"
      :footer="false"
    >
      <CaseStepList v-if="currentTestCase" :test-case="currentTestCase" />
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import FileAttachmentPicker from '@/features/file-management/components/FileAttachmentPicker.vue'
import { ref, reactive, computed, onMounted, watch, onUnmounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconPlus, IconEdit, IconDelete, IconOrderedList, IconPlayArrow, IconThunderbolt, IconCopy } from '@arco-design/web-vue/es/icon'
import { useProjectStore } from '@/store/projectStore'
import { useAppI18n } from '@/composables/useAppI18n'
import { testCaseApi, moduleApi, actuatorApi, envConfigApi, type ActuatorInfo } from '../api'
import type { UiTestCase, UiTestCaseForm, UiModule, CaseLevel, ExecutionStatus, UiEnvironmentConfig } from '../types'
import { STATUS_LABELS, extractListData, extractPaginationData, extractResponseData } from '../types'
import { uiWebSocket, UiSocketEnum, type CaseResultModel } from '../services/websocket'
import CaseStepList from './CaseStepList.vue'

const props = defineProps<{
  selectedModuleId?: number
}>()

const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)
const { locale, isEnglish, tl } = useAppI18n()

const pageText = computed(() => (
  isEnglish.value
    ? {
        selectModule: 'Select module',
        caseLevel: 'Case level',
        searchCaseName: 'Search case name',
        selectActuator: 'Select actuator',
        noOnlineActuators: 'No online actuators',
        online: 'Online',
        offline: 'Offline',
        executionEnvironment: 'Execution environment',
        defaultSuffix: ' (Default)',
        batchExecute: 'Batch run',
        batchDelete: 'Batch delete',
        batchDeleteConfirm: 'Delete the selected cases? This action cannot be undone.',
        addCase: 'Create case',
        steps: 'Steps',
        run: 'Run',
        running: 'Running',
        edit: 'Edit',
        delete: 'Delete',
        copy: 'Copy',
        deleteCaseConfirm: 'Delete this case?',
        editCase: 'Edit case',
        module: 'Module',
        caseName: 'Case name',
        enterCaseName: 'Enter case name',
        caseDescription: 'Case description',
        enterCaseDescription: 'Enter case description',
        caseSteps: 'Case steps',
        selectModuleRequired: 'Select module',
        enterCaseNameRequired: 'Enter case name',
        selectCaseLevelRequired: 'Select a case level',
        tableModule: 'Module',
        tableCaseName: 'Case name',
        tableLevel: 'Level',
        tableStatus: 'Status',
        tableStepCount: 'Step count',
        tableCreatedBy: 'Created by',
        tableCreatedAt: 'Created at',
        tableActions: 'Actions',
        fetchModuleListFailed: 'Failed to fetch module list',
        fetchCaseListFailed: 'Failed to fetch case list',
        fillRequired: 'Fill in the required fields',
        updateSuccess: 'Updated successfully',
        createSuccess: 'Created successfully',
        updateFailed: 'Update failed',
        createFailed: 'Creation failed',
        deleteSuccess: 'Deleted successfully',
        deleteFailed: 'Delete failed',
        copySuccess: 'Copied successfully',
        copyFailed: 'Copy failed',
        noActuatorAvailable: 'No actuator is available. Start the actuator service first.',
        selectOnlineActuator: 'Select an online actuator',
        websocketConnectFailed: 'WebSocket connection failed',
        runCommandFailed: 'Failed to send execution command',
        batchRunCommandFailed: 'Failed to send batch execution command',
        selectCasesToRun: 'Select the cases to execute first',
        selectCasesToDelete: 'Select the cases to delete first',
        batchDeleteFailed: 'Batch delete failed',
        batchDeleteError: 'An error occurred while batch deleting cases',
        batchExecuteLabel: (count: number) => `Batch run${count > 0 ? ` (${count})` : ''}`,
        batchDeleteLabel: (count: number) => `Batch delete${count > 0 ? ` (${count})` : ''}`,
        stepCount: (count: number) => `${count} steps`,
        startedCase: (name: string) => `Started case: ${name}`,
        startedBatchRun: (count: number) => `Started batch run for ${count} cases`,
        batchDeleteSuccess: (count: number) => `Deleted ${count} cases successfully`,
        caseRunSuccess: (passed: number, total: number) => `Case execution succeeded: ${passed}/${total} steps passed`,
        caseRunFailed: (message: string) => `Case execution failed: ${message}`,
      }
    : {
        selectModule: '选择模块',
        caseLevel: '用例等级',
        searchCaseName: '搜索用例名称',
        selectActuator: '选择执行器',
        noOnlineActuators: '暂无在线执行器',
        online: '在线',
        offline: '离线',
        executionEnvironment: '执行环境',
        defaultSuffix: ' (默认)',
        batchExecute: '批量执行',
        batchDelete: '批量删除',
        batchDeleteConfirm: '确定要删除选中的用例吗？此操作不可恢复。',
        addCase: '新增用例',
        steps: '步骤',
        run: '执行',
        running: '执行中',
        edit: '编辑',
        delete: '删除',
        copy: '复制',
        deleteCaseConfirm: '确定删除该用例？',
        editCase: '编辑用例',
        module: '所属模块',
        caseName: '用例名称',
        enterCaseName: '请输入用例名称',
        caseDescription: '用例描述',
        enterCaseDescription: '请输入用例描述',
        caseSteps: '用例步骤',
        selectModuleRequired: '请选择模块',
        enterCaseNameRequired: '请输入用例名称',
        selectCaseLevelRequired: '请选择用例等级',
        tableModule: '模块',
        tableCaseName: '用例名称',
        tableLevel: '等级',
        tableStatus: '状态',
        tableStepCount: '步骤数',
        tableCreatedBy: '创建者',
        tableCreatedAt: '创建时间',
        tableActions: '操作',
        fetchModuleListFailed: '获取模块列表失败',
        fetchCaseListFailed: '获取用例列表失败',
        fillRequired: '请填写必填项',
        updateSuccess: '更新成功',
        createSuccess: '创建成功',
        updateFailed: '更新失败',
        createFailed: '创建失败',
        deleteSuccess: '删除成功',
        deleteFailed: '删除失败',
        copySuccess: '复制成功',
        copyFailed: '复制失败',
        noActuatorAvailable: '没有可用的执行器，请先启动执行器服务',
        selectOnlineActuator: '请选择一个在线的执行器',
        websocketConnectFailed: 'WebSocket 连接失败',
        runCommandFailed: '发送执行命令失败',
        batchRunCommandFailed: '发送批量执行命令失败',
        selectCasesToRun: '请先选择要执行的用例',
        selectCasesToDelete: '请先选择要删除的用例',
        batchDeleteFailed: '批量删除失败',
        batchDeleteError: '批量删除用例时发生错误',
        batchExecuteLabel: (count: number) => `批量执行${count > 0 ? ` (${count})` : ''}`,
        batchDeleteLabel: (count: number) => `批量删除${count > 0 ? ` (${count})` : ''}`,
        stepCount: (count: number) => `${count} 步`,
        startedCase: (name: string) => `开始执行用例: ${name}`,
        startedBatchRun: (count: number) => `开始批量执行 ${count} 个用例`,
        batchDeleteSuccess: (count: number) => `成功删除 ${count} 个用例`,
        caseRunSuccess: (passed: number, total: number) => `用例执行成功: ${passed}/${total} 步骤通过`,
        caseRunFailed: (message: string) => `用例执行失败: ${message}`,
      }
))

const loading = ref(false)
const submitting = ref(false)
const executingIds = ref<number[]>([]) // 正在执行的用例ID列表

/** 检查用例是否正在执行 */
const isExecuting = (caseId: number) => executingIds.value.includes(caseId)
const testcaseData = ref<UiTestCase[]>([])
const moduleOptions = ref<UiModule[]>([])
const envConfigs = ref<UiEnvironmentConfig[]>([]) // 环境配置列表
const actuators = ref<ActuatorInfo[]>([]) // 执行器列表
const selectedEnvConfig = ref<number | undefined>() // 选中的环境配置
const selectedActuator = ref<string | undefined>() // 选中的执行器
const selectedRowKeys = ref<number[]>([]) // 批量选中的用例ID
const modalVisible = ref(false)
const stepsDrawerVisible = ref(false)
const isEdit = ref(false)
const currentTestCase = ref<UiTestCase | null>(null)
const formRef = ref()

const filters = reactive({
  module: undefined as number | undefined,
  level: undefined as string | undefined,
  search: '',
})

const pagination = reactive({ current: 1, pageSize: 10, total: 0, showTotal: true, showPageSize: true })

const formData = reactive<UiTestCaseForm>({
  file_ids: [],
  project: 0,
  module: undefined as unknown as number,
  name: '',
  description: '',
  level: 'P2',
  front_custom: [],
  front_sql: [],
  posterior_sql: [],
  parametrize: [],
  case_flow: '',
})

const rules = computed(() => ({
  module: [{ required: true, message: pageText.value.selectModuleRequired }],
  name: [{ required: true, message: pageText.value.enterCaseNameRequired }],
  level: [{ required: true, message: pageText.value.selectCaseLevelRequired }],
}))

const levelColors: Record<CaseLevel, string> = { P0: 'red', P1: 'orange', P2: 'blue', P3: 'gray' }
const statusColors: Record<ExecutionStatus, string> = { 0: 'gray', 1: 'blue', 2: 'green', 3: 'red' }

const columns = computed(() => [
  { title: 'ID', dataIndex: 'id', width: isEnglish.value ? 90 : 70, align: 'center' as const },
  { title: pageText.value.tableModule, dataIndex: 'module_name', width: 120, align: 'center' as const },
  { title: pageText.value.tableCaseName, dataIndex: 'name', ellipsis: true, tooltip: true, width: 220, align: 'center' as const },
  { title: pageText.value.tableLevel, slotName: 'level', width: 90, align: 'center' as const },
  { title: pageText.value.tableStatus, slotName: 'status', width: 100, align: 'center' as const },
  { title: pageText.value.tableStepCount, slotName: 'step_count', width: 110, align: 'center' as const },
  { title: pageText.value.tableCreatedBy, dataIndex: 'creator_name', width: 110, align: 'center' as const },
  { title: pageText.value.tableCreatedAt, slotName: 'created_at', width: 180, align: 'center' as const },
  { title: pageText.value.tableActions, slotName: 'operations', width: isEnglish.value ? 440 : 360, fixed: 'right' as const, align: 'center' as const },
])

const levelOptions = computed(() => (
  isEnglish.value
    ? [
        { value: 'P0', label: 'P0 - Smoke' },
        { value: 'P1', label: 'P1 - Core' },
        { value: 'P2', label: 'P2 - Important' },
        { value: 'P3', label: 'P3 - General' },
      ]
    : [
        { value: 'P0', label: 'P0 - 冒烟' },
        { value: 'P1', label: 'P1 - 核心' },
        { value: 'P2', label: 'P2 - 重要' },
        { value: 'P3', label: 'P3 - 一般' },
      ]
))

const batchExecuteLabel = computed(() => pageText.value.batchExecuteLabel(selectedRowKeys.value.length))
const batchDeleteLabel = computed(() => pageText.value.batchDeleteLabel(selectedRowKeys.value.length))

const testCaseModalTitle = computed(() => (
  isEdit.value ? pageText.value.editCase : pageText.value.addCase
))

const stepsDrawerTitle = computed(() => (
  currentTestCase.value?.name
    ? `${pageText.value.caseSteps} - ${currentTestCase.value.name}`
    : pageText.value.caseSteps
))

const formatStatusLabel = (status: ExecutionStatus) => tl(STATUS_LABELS[status])

const formatDate = (dateStr: string) => dateStr ? new Date(dateStr).toLocaleString(isEnglish.value ? 'en-US' : 'zh-CN') : '-'

const formatStepCount = (count?: number) => pageText.value.stepCount(count || 0)

const formatEnvLabel = (env: UiEnvironmentConfig) => (
  `${env.name}${env.is_default ? pageText.value.defaultSuffix : ''}`
)

const flattenModules = (modules: UiModule[], level = 0, visited = new Set<number>()): UiModule[] => {
  const result: UiModule[] = []
  for (const mod of modules) {
    if (visited.has(mod.id)) continue
    visited.add(mod.id)
    result.push({ ...mod, name: '\u00A0\u00A0'.repeat(level) + mod.name })
    if (mod.children?.length) {
      result.push(...flattenModules(mod.children as UiModule[], level + 1, visited))
    }
  }
  return result
}

const fetchModules = async () => {
  if (!projectId.value) return
  try {
    const res = await moduleApi.tree(projectId.value)
    const modules = extractResponseData<UiModule[]>(res) || []
    moduleOptions.value = flattenModules(modules)
  } catch {
    Message.error(pageText.value.fetchModuleListFailed)
  }
}

const fetchTestCases = async () => {
  if (!projectId.value) return
  loading.value = true
  try {
    const res = await testCaseApi.list({
      project: projectId.value,
      module: filters.module,
      level: filters.level,
      search: filters.search || undefined,
    })
    const { items, count } = extractPaginationData(res)
    testcaseData.value = items
    pagination.total = count
  } catch {
    Message.error(pageText.value.fetchCaseListFailed)
  } finally {
    loading.value = false
  }
}

const onSearch = () => {
  pagination.current = 1
  fetchTestCases()
}

const onPageChange = (page: number) => {
  pagination.current = page
  fetchTestCases()
}

const onPageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  fetchTestCases()
}

const resetForm = () => {
  Object.assign(formData, {
    project: projectId.value || 0,
    module: undefined,
    name: '',
    description: '',
    level: 'P2',
    front_custom: [],
    front_sql: [],
    posterior_sql: [],
    parametrize: [],
    case_flow: '',
  })
  formRef.value?.clearValidate()
}

const showAddModal = async () => {
  isEdit.value = false
  resetForm()
  if (props.selectedModuleId) {
    formData.module = props.selectedModuleId
  }
  if (!moduleOptions.value.length) await fetchModules()
  modalVisible.value = true
}

const editTestCase = async (record: UiTestCase) => {
  isEdit.value = true
  currentTestCase.value = record
  // 获取详情数据（包含完整字段）
  try {
    const res = await testCaseApi.get(record.id)
    const detail = extractResponseData<UiTestCase>(res)
    if (detail) {
      Object.assign(formData, {
        project: detail.project,
        module: detail.module,
        name: detail.name,
        description: detail.description || '',
        level: detail.level,
        front_custom: detail.front_custom,
        front_sql: detail.front_sql,
        posterior_sql: detail.posterior_sql,
        parametrize: detail.parametrize,
        case_flow: detail.case_flow || '',
      })
    }
  } catch {
    // 降级使用列表数据
    Object.assign(formData, {
      project: record.project,
      module: record.module,
      name: record.name,
      description: record.description || '',
      level: record.level,
      front_custom: record.front_custom,
      front_sql: record.front_sql,
      posterior_sql: record.posterior_sql,
      parametrize: record.parametrize,
      case_flow: record.case_flow || '',
    })
  }
  if (!moduleOptions.value.length) await fetchModules()
  modalVisible.value = true
}

const handleSubmit = async (done: (closed: boolean) => void) => {
  try {
    await formRef.value?.validate()
  } catch {
    Message.warning(pageText.value.fillRequired)
    done(false)
    return
  }
  submitting.value = true
  try {
    if (isEdit.value && currentTestCase.value) {
      await testCaseApi.update(currentTestCase.value.id, formData)
      Message.success(pageText.value.updateSuccess)
    } else {
      await testCaseApi.create(formData)
      Message.success(pageText.value.createSuccess)
    }
    done(true)
    fetchTestCases()
  } catch (error: unknown) {
    const err = error as { errors?: Record<string, string[]>; error?: string }
    const errors = err?.errors
    if (errors && typeof errors === 'object' && !('error' in errors) && !('message' in errors)) {
      const messages = Object.entries(errors)
        .map(([field, msgs]) => `${field}: ${Array.isArray(msgs) ? msgs.join(', ') : msgs}`)
        .join('\n')
      Message.error({ content: messages, duration: 5000 })
    } else {
      Message.error(err?.error || (isEdit.value ? pageText.value.updateFailed : pageText.value.createFailed))
    }
    done(false)
  } finally {
    submitting.value = false
  }
}

const handleCancel = () => {
  modalVisible.value = false
}

const copyTestCase = async (record: UiTestCase) => {
  try {
    loading.value = true
    await testCaseApi.copy(record.id)
    Message.success(pageText.value.copySuccess)
    fetchTestCases()
  } catch (error: unknown) {
    const err = error as { error?: string }
    Message.error(err?.error || pageText.value.copyFailed)
  } finally {
    loading.value = false
  }
}

const deleteTestCase = async (record: UiTestCase) => {
  try {
    await testCaseApi.delete(record.id)
    Message.success(pageText.value.deleteSuccess)
    fetchTestCases()
  } catch {
    Message.error(pageText.value.deleteFailed)
  }
}

const viewSteps = (record: UiTestCase) => {
  currentTestCase.value = record
  stepsDrawerVisible.value = true
}

const runTestCase = async (record: UiTestCase) => {
  // 先获取执行器列表
  await fetchActuators()

  // 检查是否有可用执行器
  if (actuators.value.length === 0 || !actuators.value.some(a => a.is_open)) {
    Message.warning(pageText.value.noActuatorAvailable)
    return
  }

  // 如果没有选择执行器，自动选择第一个可用的
  if (!selectedActuator.value) {
    const available = actuators.value.find(a => a.is_open)
    if (available) {
      selectedActuator.value = available.id
    } else {
      Message.warning(pageText.value.selectOnlineActuator)
      return
    }
  }

  // 如果没有选择环境配置，使用默认的
  if (!selectedEnvConfig.value && envConfigs.value.length > 0) {
    const defaultEnv = envConfigs.value.find(e => e.is_default)
    if (defaultEnv) {
      selectedEnvConfig.value = defaultEnv.id
    }
  }

  // 连接 WebSocket
  try {
    await uiWebSocket.connect()
  } catch {
    Message.error(pageText.value.websocketConnectFailed)
    return
  }

  // 发送执行命令（包含执行器ID）
  executingIds.value.push(record.id)
  const success = uiWebSocket.runTestCase(record.id, selectedEnvConfig.value, selectedActuator.value)
  if (success) {
    Message.info(pageText.value.startedCase(record.name))
    // 立即更新本地状态为"执行中"
    const idx = testcaseData.value.findIndex(tc => tc.id === record.id)
    if (idx !== -1) {
      testcaseData.value[idx].status = 1  // 执行中
    }
  } else {
    Message.error(pageText.value.runCommandFailed)
    executingIds.value = executingIds.value.filter(id => id !== record.id)
  }
}

/** 批量执行选中的用例 */
const runBatchTestCases = async () => {
  if (selectedRowKeys.value.length === 0) {
    Message.warning(pageText.value.selectCasesToRun)
    return
  }

  // 先获取执行器列表
  await fetchActuators()

  // 检查是否有可用执行器
  if (actuators.value.length === 0 || !actuators.value.some(a => a.is_open)) {
    Message.warning(pageText.value.noActuatorAvailable)
    return
  }

  // 如果没有选择执行器，自动选择第一个可用的
  if (!selectedActuator.value) {
    const available = actuators.value.find(a => a.is_open)
    if (available) {
      selectedActuator.value = available.id
    } else {
      Message.warning(pageText.value.selectOnlineActuator)
      return
    }
  }

  // 如果没有选择环境配置，使用默认的
  if (!selectedEnvConfig.value && envConfigs.value.length > 0) {
    const defaultEnv = envConfigs.value.find(e => e.is_default)
    if (defaultEnv) {
      selectedEnvConfig.value = defaultEnv.id
    }
  }

  // 连接 WebSocket
  try {
    await uiWebSocket.connect()
  } catch {
    Message.error(pageText.value.websocketConnectFailed)
    return
  }

  // 发送批量执行命令
  executingIds.value.push(...selectedRowKeys.value)
  const success = uiWebSocket.runTestCases(selectedRowKeys.value, selectedEnvConfig.value, selectedActuator.value)
  if (success) {
    Message.info(pageText.value.startedBatchRun(selectedRowKeys.value.length))
    // 更新选中用例状态为"执行中"
    for (const caseId of selectedRowKeys.value) {
      const idx = testcaseData.value.findIndex(tc => tc.id === caseId)
      if (idx !== -1) {
        testcaseData.value[idx].status = 1
      }
    }
    // 清空选择
    selectedRowKeys.value = []
  } else {
    Message.error(pageText.value.batchRunCommandFailed)
    executingIds.value = executingIds.value.filter(id => !selectedRowKeys.value.includes(id))
  }
}

/** 批量删除选中的用例 */
const batchDeleteTestCases = async () => {
  if (selectedRowKeys.value.length === 0) {
    Message.warning(pageText.value.selectCasesToDelete)
    return
  }

  try {
    const res = await testCaseApi.batchDelete(selectedRowKeys.value)
    const result = extractResponseData<{ message?: string }>(res)
    
    if (result) {
      Message.success(result.message || pageText.value.batchDeleteSuccess(selectedRowKeys.value.length))
      // 清空选择
      selectedRowKeys.value = []
      // 刷新列表
      fetchTestCases()
    } else {
      Message.error(pageText.value.batchDeleteFailed)
    }
  } catch (error) {
    console.error('批量删除用例出错:', error)
    Message.error(pageText.value.batchDeleteError)
  }
}

/** 处理用例执行结果 */
const handleCaseResult = (data: any) => {
  const result = data.data?.func_args as CaseResultModel
  if (!result) return

  // 从执行中列表移除该用例
  if (result.case_id) {
    executingIds.value = executingIds.value.filter(id => id !== result.case_id)
  }

  if (result.status === 'success') {
    Message.success(pageText.value.caseRunSuccess(result.passed_steps, result.total_steps))
  } else {
    Message.error(pageText.value.caseRunFailed(result.message))
  }
  fetchTestCases()
}

/** 获取环境配置 */
const fetchEnvConfigs = async () => {
  if (!projectId.value) return
  try {
    const res = await envConfigApi.list({ project: projectId.value })
    envConfigs.value = extractListData<UiEnvironmentConfig>(res)
    // 优先选择默认环境，如果没有默认环境则选择第一个环境配置
    if (!selectedEnvConfig.value && envConfigs.value.length > 0) {
      const defaultEnv = envConfigs.value.find(e => e.is_default)
      if (defaultEnv) {
        selectedEnvConfig.value = defaultEnv.id
      } else {
        // 如果没有默认环境，选择第一个环境配置
        selectedEnvConfig.value = envConfigs.value[0].id
      }
    }
  } catch {
    // 静默失败
  }
}

/** 获取执行器列表 */
const fetchActuators = async () => {
  try {
    const res = await actuatorApi.list()
    const data = extractResponseData<{ count: number; items: ActuatorInfo[] }>(res)
    actuators.value = data?.items ?? []
    // 自动选择第一个可用的执行器
    if (!selectedActuator.value && actuators.value.length > 0) {
      const available = actuators.value.find(a => a.is_open)
      if (available) selectedActuator.value = available.id
    }
  } catch {
    // 静默失败
  }
}

/** WebSocket 事件监听 */
let offCaseResult: (() => void) | null = null

watch(() => props.selectedModuleId, (newVal) => {
  filters.module = newVal
  pagination.current = 1
  fetchTestCases()
})

/** 监听项目变化，重新加载数据 */
watch(projectId, async (newVal) => {
  if (newVal) {
    pagination.current = 1
    fetchModules()
    fetchTestCases()
    // 同时获取环境配置和执行器列表，并自动选择默认值
    await Promise.all([
      fetchEnvConfigs(),
      fetchActuators()
    ])
  }
}, { immediate: true })

const refresh = () => {
  fetchModules()
  fetchTestCases()
  fetchEnvConfigs()
}

defineExpose({ refresh })

onMounted(() => {
  // 监听用例执行结果
  offCaseResult = uiWebSocket.on(UiSocketEnum.CASE_RESULT, handleCaseResult)
})

onUnmounted(() => {
  // 清理事件监听
  offCaseResult?.()
})
</script>

<style scoped>
.testcase-list {
  padding: 16px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
}
.search-box {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.action-buttons {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 12px;
}
</style>
