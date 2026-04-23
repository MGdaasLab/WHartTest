<template>
  <div class="testcase-list">
    <div class="page-header">
      <div class="search-box">
        <a-select
          v-model="filters.module"
          placeholder="选择模块"
          allow-clear
          style="width: 160px; margin-right: 12px"
          @change="onSearch"
        >
          <a-option v-for="mod in moduleOptions" :key="mod.id" :value="mod.id">
            {{ mod.name }}
          </a-option>
        </a-select>
        <a-select
          v-model="filters.level"
          placeholder="用例等级"
          allow-clear
          style="width: 100px; margin-right: 12px"
          @change="onSearch"
        >
          <a-option value="P0">P0</a-option>
          <a-option value="P1">P1</a-option>
          <a-option value="P2">P2</a-option>
          <a-option value="P3">P3</a-option>
        </a-select>
        <a-input-search
          v-model="filters.search"
          placeholder="搜索用例名称"
          allow-clear
          style="width: 200px"
          @search="onSearch"
          @clear="onSearch"
        />
      </div>
      <div class="action-buttons">
        <a-select
          v-model="selectedActuator"
          placeholder="选择执行器"
          allow-clear
          style="width: 150px; margin-right: 12px"
          @focus="fetchActuators"
        >
          <template #empty>
            <div style="padding: 8px; text-align: center; color: var(--color-text-3)">
              暂无在线执行器
            </div>
          </template>
          <a-option v-for="act in actuators" :key="act.id" :value="act.id" :disabled="!act.is_open">
            {{ act.name || act.id }}
            <a-tag v-if="act.is_open" color="green" size="small" style="margin-left: 4px">在线</a-tag>
            <a-tag v-else color="gray" size="small" style="margin-left: 4px">离线</a-tag>
          </a-option>
        </a-select>
        <a-select
          v-model="selectedEnvConfig"
          placeholder="执行环境"
          allow-clear
          style="width: 150px; margin-right: 12px"
        >
          <a-option v-for="env in envConfigs" :key="env.id" :value="env.id">
            {{ env.name }}{{ env.is_default ? ' (默认)' : '' }}
          </a-option>
        </a-select>
        <a-button
          type="primary"
          status="success"
          :disabled="selectedRowKeys.length === 0 || executingIds.length > 0"
          :loading="executingIds.length > 0"
          style="margin-right: 12px"
          @click="runBatchTestCases"
        >
          <template #icon><icon-thunderbolt /></template>
          批量执行{{ selectedRowKeys.length > 0 ? ` (${selectedRowKeys.length})` : '' }}
        </a-button>
        <a-popconfirm
          content="确定要删除选中的用例吗？此操作不可恢复。"
          @ok="batchDeleteTestCases"
        >
          <a-button
            type="primary"
            status="danger"
            :disabled="selectedRowKeys.length === 0"
            style="margin-right: 12px"
          >
            <template #icon><icon-delete /></template>
            批量删除{{ selectedRowKeys.length > 0 ? ` (${selectedRowKeys.length})` : '' }}
          </a-button>
        </a-popconfirm>
        <a-button type="primary" @click="showAddModal">
          <template #icon><icon-plus /></template>
          新增用例
        </a-button>
      </div>
    </div>

    <a-table
      :columns="columns"
      :data="testcaseData"
      :pagination="pagination"
      :loading="loading"
      :scroll="{ x: 1100 }"
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
          {{ STATUS_LABELS[record.status as ExecutionStatus] }}
        </a-tag>
      </template>
      <template #step_count="{ record }">
        <a-tag color="cyan">{{ record.step_count || 0 }} 步</a-tag>
      </template>
      <template #created_at="{ record }">
        {{ formatDate(record.created_at) }}
      </template>
      <template #operations="{ record }">
        <a-space :size="4">
          <a-button type="text" size="mini" @click="viewSteps(record)">
            <template #icon><icon-ordered-list /></template>
            步骤
          </a-button>
          <a-button
            type="text"
            size="mini"
            :loading="isExecuting(record.id)"
            :disabled="isExecuting(record.id)"
            @click="runTestCase(record)"
          >
            <template #icon><icon-play-arrow /></template>
            {{ isExecuting(record.id) ? '执行中' : '执行' }}
          </a-button>
          <a-button type="text" size="mini" @click="editTestCase(record)">
            <template #icon><icon-edit /></template>
            编辑
          </a-button>
          <a-popconfirm content="确定删除该用例？" @ok="deleteTestCase(record)">
            <a-button type="text" status="danger" size="mini">
              <template #icon><icon-delete /></template>
              删除
            </a-button>
          </a-popconfirm>
        </a-space>
      </template>
    </a-table>

    <!-- 新增/编辑弹窗 -->
    <a-modal
      v-model:visible="modalVisible"
      :title="isEdit ? '编辑用例' : '新增用例'"
      :ok-loading="submitting"
      width="600px"
      @before-ok="handleSubmit"
      @cancel="handleCancel"
    >
      <a-form ref="formRef" :model="formData" :rules="rules" layout="vertical">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="module" label="所属模块" required>
              <a-select v-model="formData.module" placeholder="请选择模块">
                <a-option v-for="mod in moduleOptions" :key="mod.id" :value="mod.id">
                  {{ mod.name }}
                </a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="level" label="用例等级" required>
              <a-select v-model="formData.level">
                <a-option value="P0">P0 - 冒烟</a-option>
                <a-option value="P1">P1 - 核心</a-option>
                <a-option value="P2">P2 - 重要</a-option>
                <a-option value="P3">P3 - 一般</a-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item field="name" label="用例名称" required>
          <a-input v-model="formData.name" placeholder="请输入用例名称" :max-length="255" />
        </a-form-item>
        <a-form-item field="description" label="用例描述">
          <a-textarea v-model="formData.description" placeholder="请输入用例描述" :auto-size="{ minRows: 2, maxRows: 4 }" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 步骤管理抽屉 -->
    <a-drawer
      v-model:visible="stepsDrawerVisible"
      :title="`用例步骤 - ${currentTestCase?.name || ''}`"
      :width="900"
      :footer="false"
    >
      <CaseStepList v-if="currentTestCase" :test-case="currentTestCase" />
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch, onUnmounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconPlus, IconEdit, IconDelete, IconOrderedList, IconPlayArrow, IconThunderbolt } from '@arco-design/web-vue/es/icon'
import { useProjectStore } from '@/store/projectStore'
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

const rules = {
  module: [{ required: true, message: '请选择模块' }],
  name: [{ required: true, message: '请输入用例名称' }],
  level: [{ required: true, message: '请选择用例等级' }],
}

const levelColors: Record<CaseLevel, string> = { P0: 'red', P1: 'orange', P2: 'blue', P3: 'gray' }
const statusColors: Record<ExecutionStatus, string> = { 0: 'gray', 1: 'blue', 2: 'green', 3: 'red' }

const columns = [
  { title: 'ID', dataIndex: 'id', width: 70, align: 'center' as const },
  { title: '模块', dataIndex: 'module_name', width: 120, align: 'center' as const },
  { title: '用例名称', dataIndex: 'name', ellipsis: true, tooltip: true, width: 200, align: 'center' as const },
  { title: '等级', slotName: 'level', width: 80, align: 'center' as const },
  { title: '状态', slotName: 'status', width: 90, align: 'center' as const },
  { title: '步骤数', slotName: 'step_count', width: 90, align: 'center' as const },
  { title: '创建者', dataIndex: 'creator_name', width: 100, align: 'center' as const },
  { title: '创建时间', slotName: 'created_at', width: 160, align: 'center' as const },
  { title: '操作', slotName: 'operations', width: 290, fixed: 'right' as const, align: 'center' as const },
]

const formatDate = (dateStr: string) => dateStr ? new Date(dateStr).toLocaleString('zh-CN') : '-'

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
    Message.error('获取模块列表失败')
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
    Message.error('获取用例列表失败')
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
    Message.warning('请填写必填项')
    done(false)
    return
  }
  submitting.value = true
  try {
    if (isEdit.value && currentTestCase.value) {
      await testCaseApi.update(currentTestCase.value.id, formData)
      Message.success('更新成功')
    } else {
      await testCaseApi.create(formData)
      Message.success('创建成功')
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
      Message.error(err?.error || (isEdit.value ? '更新失败' : '创建失败'))
    }
    done(false)
  } finally {
    submitting.value = false
  }
}

const handleCancel = () => {
  modalVisible.value = false
}

const deleteTestCase = async (record: UiTestCase) => {
  try {
    await testCaseApi.delete(record.id)
    Message.success('删除成功')
    fetchTestCases()
  } catch {
    Message.error('删除失败')
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
    Message.warning('没有可用的执行器，请先启动执行器')
    return
  }

  // 如果没有选择执行器，自动选择第一个可用的
  if (!selectedActuator.value) {
    const available = actuators.value.find(a => a.is_open)
    if (available) {
      selectedActuator.value = available.id
    } else {
      Message.warning('请选择一个在线的执行器')
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
    Message.error('WebSocket 连接失败')
    return
  }

  // 发送执行命令（包含执行器ID）
  executingIds.value.push(record.id)
  const success = uiWebSocket.runTestCase(record.id, selectedEnvConfig.value, selectedActuator.value)
  if (success) {
    Message.info(`开始执行用例: ${record.name}`)
    // 立即更新本地状态为"执行中"
    const idx = testcaseData.value.findIndex(tc => tc.id === record.id)
    if (idx !== -1) {
      testcaseData.value[idx].status = 1  // 执行中
    }
  } else {
    Message.error('发送执行命令失败')
    executingIds.value = executingIds.value.filter(id => id !== record.id)
  }
}

/** 批量执行选中的用例 */
const runBatchTestCases = async () => {
  if (selectedRowKeys.value.length === 0) {
    Message.warning('请先选择要执行的用例')
    return
  }

  // 先获取执行器列表
  await fetchActuators()

  // 检查是否有可用执行器
  if (actuators.value.length === 0 || !actuators.value.some(a => a.is_open)) {
    Message.warning('没有可用的执行器，请先启动执行器')
    return
  }

  // 如果没有选择执行器，自动选择第一个可用的
  if (!selectedActuator.value) {
    const available = actuators.value.find(a => a.is_open)
    if (available) {
      selectedActuator.value = available.id
    } else {
      Message.warning('请选择一个在线的执行器')
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
    Message.error('WebSocket 连接失败')
    return
  }

  // 发送批量执行命令
  executingIds.value.push(...selectedRowKeys.value)
  const success = uiWebSocket.runTestCases(selectedRowKeys.value, selectedEnvConfig.value, selectedActuator.value)
  if (success) {
    Message.info(`开始批量执行 ${selectedRowKeys.value.length} 个用例`)
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
    Message.error('发送批量执行命令失败')
    executingIds.value = executingIds.value.filter(id => !selectedRowKeys.value.includes(id))
  }
}

/** 批量删除选中的用例 */
const batchDeleteTestCases = async () => {
  if (selectedRowKeys.value.length === 0) {
    Message.warning('请先选择要删除的用例')
    return
  }

  try {
    const res = await testCaseApi.batchDelete(selectedRowKeys.value)
    const result = extractResponseData<{ message?: string }>(res)
    
    if (result) {
      Message.success(result.message || `成功删除 ${selectedRowKeys.value.length} 个用例`)
      // 清空选择
      selectedRowKeys.value = []
      // 刷新列表
      fetchTestCases()
    } else {
      Message.error('批量删除失败')
    }
  } catch (error) {
    console.error('批量删除用例出错:', error)
    Message.error('批量删除用例时发生错误')
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
    Message.success(`用例执行成功: ${result.passed_steps}/${result.total_steps} 步骤通过`)
  } else {
    Message.error(`用例执行失败: ${result.message}`)
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
}
.search-box {
  display: flex;
  align-items: center;
}
</style>
