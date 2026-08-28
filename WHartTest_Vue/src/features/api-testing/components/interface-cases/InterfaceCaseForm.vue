<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { IconCheck, IconClose, IconFire, IconHistory, IconPlayArrow, IconPlus, IconDelete, IconUp, IconDown } from '@arco-design/web-vue/es/icon'
import { useProjectStore } from '@/store/projectStore'
import { useThemeStore } from '@/store/themeStore'
import { useAppI18n } from '@/composables/useAppI18n'
import { useEnvironmentStore } from '../../stores/environmentStore'
import { moduleService } from '../../services/moduleService'
import { interfaceService } from '../../services/interfaceService'
import { interfaceCaseReportService, interfaceCaseService } from '../../services/interfaceCaseService'
import type { ApiModule } from '../../types/module'
import type { ApiInterface } from '../../types/interface'
import type { ApiInterfaceCaseStep } from '../../types/interfaceCase'
import type { TestCasePriority } from '../../types/testcase'
import TestCaseBasicInfo from '../testcases/TestCaseBasicInfo.vue'
import GroupManager from '../testcases/GroupManager.vue'
import TagManager from '../testcases/TagManager.vue'
import TestCaseConfigDialog from '../testcases/TestCaseConfigDialog.vue'
import TestCaseStepDetail from '../testcases/TestCaseStepDetail.vue'
import ApiSelectDialog from '../testcases/ApiSelectDialog.vue'
import ExecutionSteps from '../test-reports/ExecutionSteps.vue'
import { showExtractPersistenceNotice } from '../../utils/extractPersistence'

interface Props {
  mode?: 'create' | 'edit'
  interfaceCaseId?: number
}

const props = withDefaults(defineProps<Props>(), {
  mode: 'create'
})

const emit = defineEmits(['success'])
const router = useRouter()
const route = useRoute()
const projectStore = useProjectStore()
const themeStore = useThemeStore()
const environmentStore = useEnvironmentStore()
const { isEnglish, tl } = useAppI18n()

const isDarkTheme = computed(() => themeStore.isBlack)
const loading = ref(false)
const reportLoading = ref(false)
const modules = ref<ApiModule[]>([])
const interfaces = ref<ApiInterface[]>([])
const steps = ref<ApiInterfaceCaseStep[]>([])
const activeStep = ref<ApiInterfaceCaseStep | null>(null)
const activeStepDetailRef = ref<any>(null)
const showReport = ref(false)
const latestReport = ref<any>(null)
const addPreconditionVisible = ref(false)
const addPreconditionMenuVisible = ref(false)
const currentInterfaceCaseId = ref<number | undefined>(props.interfaceCaseId)

const formData = reactive({
  name: '',
  description: '',
  priority: 'P2' as TestCasePriority,
  group: undefined as number | undefined,
  tags: [] as number[],
  interface_id: undefined as number | undefined,
  config: {
    base_url: '',
    variables: '',
    parameters: '',
    export: [] as string[],
    verify: undefined as boolean | undefined
  }
})

const readonly = computed(() => false)
const mainStep = computed(() => steps.value.find(step => step.role === 'main') || null)
const preconditionSteps = computed(() => steps.value.filter(step => step.role === 'precondition'))
const preconditionCountText = computed(() => tl(`${preconditionSteps.value.length}个前置条件`))
const mainStepBadge = computed(() => isEnglish.value ? 'Main' : '主')
const activeStepRenderKey = computed(() => {
  if (!activeStep.value) return 'empty-interface-case-step'
  if (activeStep.value.client_key) return activeStep.value.client_key
  if (activeStep.value.id) return `step-${activeStep.value.id}`
  return `draft-${activeStep.value.role}-${activeStep.value.order}`
})

const stepsForConfig = computed(() => steps.value.map(step => ({
  id: step.id || 0,
  name: step.name,
  interface_data: {
    extract: step.interface_data?.extract || {}
  }
})))

const normalizeHookList = (hooks: any[]) => (hooks || []).map(hook =>
  typeof hook === 'string' ? hook : JSON.stringify(hook)
)

const buildInterfaceInfo = (api: ApiInterface) => ({
  id: api.id,
  name: api.name,
  type: api.type,
  method: api.method || api.sql_method,
  url: api.url || api.sql,
  module: api.module_info || (api.module ? { id: Number(api.module), name: '' } : null),
  module_info: api.module_info || (api.module ? { id: Number(api.module), name: '' } : null),
  project: {
    id: projectStore.currentProjectId || 0,
    name: ''
  }
})

const buildInterfaceData = (api: ApiInterface) => ({
  name: api.name,
  type: api.type,
  method: api.method || api.sql_method,
  url: api.url,
  headers: api.headers || [],
  params: api.params || [],
  body: api.body || { type: 'none', content: null },
  sql_method: api.sql_method,
  sql: api.sql,
  sql_params: api.sql_params || {},
  sql_size: api.sql_size || 10,
  validators: api.validators || [],
  extract: api.extract || {},
  extract_meta: api.extract_meta || {},
  setup_hooks: normalizeHookList(api.setup_hooks || []),
  teardown_hooks: normalizeHookList(api.teardown_hooks || []),
  variables: api.variables || {},
  file_ids: api.file_ids || []
})

const defaultSyncFields = [
  'method',
  'url',
  'headers',
  'params',
  'body',
  'setup_hooks',
  'teardown_hooks',
  'variables',
  'validators',
  'extract'
]

const makeStepKey = () => `interface-case-step-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

const preconditionAddTypes = [
  { label: '引用接口', value: 'reference' },
  { label: '自定义接口', value: 'custom_api' }
] as const

const getStepKey = (step?: ApiInterfaceCaseStep | null) => {
  if (!step) return ''
  return step.client_key || (step.id ? `saved-${step.id}` : '')
}

const ensureStepIdentity = (step: ApiInterfaceCaseStep) => {
  if (!step.client_key) {
    step.client_key = step.id ? `saved-${step.id}` : makeStepKey()
  }
  return step
}

const isSameStep = (left?: ApiInterfaceCaseStep | null, right?: ApiInterfaceCaseStep | null) => {
  if (!left || !right) return false
  const leftKey = getStepKey(left)
  const rightKey = getStepKey(right)
  if (leftKey && rightKey) return leftKey === rightKey
  if (left.id && right.id) return left.id === right.id
  return left === right || (left.role === right.role && left.order === right.order)
}

const findMatchingStep = (list: ApiInterfaceCaseStep[], target?: ApiInterfaceCaseStep | null) =>
  list.find(step => isSameStep(step, target)) || null

const buildStepFromInterface = (api: ApiInterface, role: 'precondition' | 'main', order: number): ApiInterfaceCaseStep => ({
  id: 0,
  client_key: makeStepKey(),
  name: api.name,
  role,
  order,
  interface_info: buildInterfaceInfo(api),
  interface_data: buildInterfaceData(api),
  config: {
    variables: {},
    validators: [],
    extract: {},
    extract_meta: {},
    setup_hooks: [],
    teardown_hooks: []
  },
  file_ids: api.file_ids || [],
  sync_fields: [...defaultSyncFields],
  last_sync_time: null
})

const buildCustomStep = (role: 'precondition' | 'main', order: number): ApiInterfaceCaseStep => {
  const name = tl('自定义接口')
  return {
    id: 0,
    client_key: makeStepKey(),
    name,
    role,
    order,
    interface_info: {
      id: 0,
      name,
      type: 'http',
      method: 'GET',
      url: '',
      module: { id: 0, name: '' },
      module_info: { id: 0, name: '' },
      project: {
        id: projectStore.currentProjectId || 0,
        name: ''
      }
    },
    interface_data: {
      name,
      type: 'http',
      method: 'GET',
      url: '',
      headers: [],
      params: [],
      body: { type: 'none', content: null },
      validators: [],
      extract: {},
      extract_meta: {},
      setup_hooks: [],
      teardown_hooks: [],
      variables: {},
      file_ids: []
    },
    config: {
      variables: {},
      validators: [],
      extract: {},
      extract_meta: {},
      setup_hooks: [],
      teardown_hooks: []
    },
    file_ids: [],
    sync_fields: [...defaultSyncFields],
    last_sync_time: null
  }
}

const normalizeSteps = (nextSteps: ApiInterfaceCaseStep[]) => {
  const previousActiveStep = activeStep.value ? ensureStepIdentity(activeStep.value) : null
  const preconditions = nextSteps
    .filter(step => step.role === 'precondition')
    .map(step => ensureStepIdentity(step))
  const main = nextSteps.find(step => step.role === 'main')
  if (main) ensureStepIdentity(main)
  const normalized = [
    ...preconditions.map((step, index) => ({ ...step, order: index + 1 })),
    ...(main ? [{ ...main, order: preconditions.length + 1 }] : [])
  ]
  steps.value = normalized
  if (previousActiveStep) {
    activeStep.value = findMatchingStep(normalized, previousActiveStep)
  }
}

const loadModules = async () => {
  if (!projectStore.currentProjectId) return
  const res = await moduleService.tree(projectStore.currentProjectId)
  modules.value = res.success && res.data
    ? (Array.isArray(res.data) ? res.data : (res.data as any).results || [])
    : []
}

const loadInterfaces = async () => {
  if (!projectStore.currentProjectId) return
  const res = await interfaceService.list(projectStore.currentProjectId, { page_size: 1000 })
  interfaces.value = res.success && res.data
    ? (Array.isArray(res.data) ? res.data : (res.data as any).results || [])
    : []
}

const normalizeFetchedStep = (step: ApiInterfaceCaseStep): ApiInterfaceCaseStep => ({
  ...step,
  client_key: step.client_key || (step.id ? `saved-${step.id}` : makeStepKey()),
  interface_info: step.interface_info ? {
    ...step.interface_info,
    module_info: step.interface_info.module_info || step.interface_info.module || null
  } : null,
  interface_data: {
    ...(step.interface_data || {}),
    headers: step.interface_data?.headers || [],
    params: step.interface_data?.params || [],
    body: step.interface_data?.body || { type: 'none', content: null },
    validators: step.interface_data?.validators || [],
    extract: step.interface_data?.extract || {},
    extract_meta: step.interface_data?.extract_meta || {},
    setup_hooks: step.interface_data?.setup_hooks || [],
    teardown_hooks: step.interface_data?.teardown_hooks || [],
    variables: step.interface_data?.variables || {}
  },
  config: step.config || {},
  file_ids: step.file_ids || [],
  sync_fields: step.sync_fields || [...defaultSyncFields],
  last_sync_time: step.last_sync_time || null
})

const setMainInterface = (interfaceId?: number) => {
  formData.interface_id = interfaceId
  if (!interfaceId) {
    normalizeSteps(steps.value.filter(step => step.role !== 'main'))
    activeStep.value = null
    return
  }
  const api = interfaces.value.find(item => item.id === interfaceId)
  if (!api) return
  const main = buildStepFromInterface(api, 'main', preconditionSteps.value.length + 1)
  normalizeSteps([...preconditionSteps.value, main])
  activeStep.value = main
}

const fetchDetail = async () => {
  if (props.mode !== 'edit' || !currentInterfaceCaseId.value || !projectStore.currentProjectId) return
  try {
    loading.value = true
    const res = await interfaceCaseService.get(projectStore.currentProjectId, currentInterfaceCaseId.value)
    if (!res.success || !res.data) {
      throw new Error(res.error || tl('获取接口用例详情失败'))
    }
    const data = res.data as any
    formData.name = data.name || ''
    formData.description = data.description || ''
    formData.priority = data.priority || 'P2'
    formData.group = data.group === null ? undefined : data.group
    formData.tags = data.tags || []
    formData.interface_id = data.interface
    formData.config = {
      base_url: data.config?.base_url || '',
      variables: data.config?.variables || '',
      parameters: data.config?.parameters || '',
      export: Array.isArray(data.config?.export) ? data.config.export : [],
      verify: typeof data.config?.verify === 'boolean' ? data.config.verify : undefined
    }
    normalizeSteps((data.steps || []).map(normalizeFetchedStep))
    activeStep.value = mainStep.value || steps.value[0] || null
  } catch (error) {
    console.error('获取接口用例详情失败:', error)
    Message.error(error instanceof Error ? error.message : tl('获取接口用例详情失败'))
  } finally {
    loading.value = false
  }
}

const handleAddPreconditionType = (type: typeof preconditionAddTypes[number]['value']) => {
  addPreconditionMenuVisible.value = false
  if (type === 'reference') {
    addPreconditionVisible.value = true
    return
  }

  const newStep = buildCustomStep('precondition', preconditionSteps.value.length + 1)
  normalizeSteps([...preconditionSteps.value, newStep, ...(mainStep.value ? [mainStep.value] : [])])
  activeStep.value = newStep
  showReport.value = false
}

const handlePreconditionInterfaceSelect = (selectedInterfaces: ApiInterface[]) => {
  const newSteps = selectedInterfaces.map((api, index) =>
    buildStepFromInterface(api, 'precondition', preconditionSteps.value.length + index + 1)
  )
  normalizeSteps([...preconditionSteps.value, ...newSteps, ...(mainStep.value ? [mainStep.value] : [])])
  activeStep.value = newSteps[newSteps.length - 1] || activeStep.value
  showReport.value = false
}

const handleDeletePrecondition = (step: ApiInterfaceCaseStep) => {
  const wasActive = isSameStep(activeStep.value, step)
  normalizeSteps(steps.value.filter(item => !isSameStep(item, step)))
  if (wasActive) {
    activeStep.value = mainStep.value || steps.value[0] || null
  }
}

const movePrecondition = (step: ApiInterfaceCaseStep, offset: number) => {
  const list = [...preconditionSteps.value]
  const index = list.findIndex(item => isSameStep(item, step))
  const target = index + offset
  if (index < 0 || target < 0 || target >= list.length) return
  const [item] = list.splice(index, 1)
  list.splice(target, 0, item)
  normalizeSteps([...list, ...(mainStep.value ? [mainStep.value] : [])])
}

const updateHeaderData = (data: any) => {
  formData.name = data.name
  formData.description = data.description
}

const updateStepData = (step: any) => {
  const index = steps.value.findIndex(item => isSameStep(item, step))
  if (index === -1) return
  const nextSteps = [...steps.value]
  nextSteps[index] = {
    ...normalizeFetchedStep(step),
    client_key: getStepKey(steps.value[index]) || getStepKey(step) || makeStepKey()
  }
  normalizeSteps(nextSteps)
  activeStep.value = findMatchingStep(steps.value, nextSteps[index]) || steps.value[index] || null
}

const flushActiveStepDetail = () => {
  if (!activeStep.value || showReport.value) return
  activeStepDetailRef.value?.flushCurrentStepSnapshot?.()
}

const buildSubmitConfig = () => {
  const config = { ...(formData.config || {}) }
  if (typeof config.verify !== 'boolean') {
    delete config.verify
  }
  return config
}

const validateForm = () => {
  if (!formData.name.trim()) {
    Message.error(tl('请输入用例名称'))
    return false
  }
  if (!formData.interface_id) {
    Message.error(tl('请选择主接口'))
    return false
  }
  if (!mainStep.value) {
    Message.error(tl('主接口步骤不存在'))
    return false
  }
  return true
}

interface SubmitOptions {
  silent?: boolean
  refresh?: boolean
  skipFlush?: boolean
}

const handleSubmit = async (options: SubmitOptions = {}) => {
  if (!options.skipFlush) {
    flushActiveStepDetail()
  }
  if (!projectStore.currentProjectId || !validateForm()) return false
  try {
    loading.value = true
    const payload = {
      name: formData.name,
      description: formData.description,
      priority: formData.priority,
      group: formData.group,
      tags: formData.tags || [],
      interface_id: formData.interface_id,
      config: buildSubmitConfig(),
      steps_info: steps.value.map((step, index) => ({
        ...(step.id ? { id: step.id } : {}),
        name: step.name,
        role: step.role,
        order: index + 1,
        interface_id: step.interface_info?.id || undefined,
        interface_data: step.interface_data,
        config: step.config || {},
        file_ids: step.file_ids || [],
        sync_fields: step.sync_fields || []
      }))
    }

    if (props.mode === 'edit' && currentInterfaceCaseId.value) {
      const res = await interfaceCaseService.update(projectStore.currentProjectId, currentInterfaceCaseId.value, payload)
      if (!res.success) throw new Error(res.error || tl('更新失败'))
      if (!options.silent) {
        Message.success(tl('更新成功'))
      }
      if (options.refresh !== false) {
        await fetchDetail()
      }
    } else {
      const res = await interfaceCaseService.create(projectStore.currentProjectId, payload)
      if (!res.success || !res.data) throw new Error(res.error || tl('创建失败'))
      if (!options.silent) {
        Message.success(tl('创建成功'))
      }
      currentInterfaceCaseId.value = res.data.id
      emit('success', { id: res.data.id })
      router.replace({ name: 'ApiInterfaceCaseEdit', params: { id: res.data.id }, query: { tab: 'interface-cases' } })
    }
    return true
  } catch (error) {
    console.error('保存接口用例失败:', error)
    Message.error(error instanceof Error ? error.message : tl('保存失败'))
    return false
  } finally {
    loading.value = false
  }
}

const handleSaveStepToInterfaceCase = async (step: any, done?: (success: boolean) => void) => {
  updateStepData(step)
  const success = await handleSubmit({ silent: true, refresh: false, skipFlush: true })
  done?.(success)
}

const handleCancel = () => {
  router.push({ path: '/api-testing', query: { tab: 'interface-cases' } })
}

const handleRun = async () => {
  if (!currentInterfaceCaseId.value) {
    Message.warning(tl('请先保存接口用例'))
    return
  }
  if (!environmentStore.currentEnvironmentId) {
    Message.warning(tl('请先选择环境'))
    return
  }
  if (!projectStore.currentProjectId) return
  try {
    loading.value = true
    const res = await interfaceCaseService.run(projectStore.currentProjectId, currentInterfaceCaseId.value, {
      environment_id: Number(environmentStore.currentEnvironmentId)
    })
    if (!res.success || !res.data) throw new Error(res.error || tl('运行接口用例失败'))
    showExtractPersistenceNotice((res.data as any).extract_persistence)
    Message.success(tl('接口用例运行成功'))
    if ((res.data as any).report_id) {
      await fetchReportDetail((res.data as any).report_id)
    }
  } catch (error) {
    Message.error(error instanceof Error ? error.message : tl('运行接口用例失败'))
  } finally {
    loading.value = false
  }
}

const fetchReportDetail = async (reportId: number) => {
  if (!projectStore.currentProjectId) return
  reportLoading.value = true
  try {
    const res = await interfaceCaseReportService.get(projectStore.currentProjectId, reportId)
    if (!res.success || !res.data) throw new Error(res.error || tl('获取报告详情失败'))
    latestReport.value = res.data
    showReport.value = true
    activeStep.value = null
  } finally {
    reportLoading.value = false
  }
}

const handleShowReport = async () => {
  if (!currentInterfaceCaseId.value || !projectStore.currentProjectId) {
    Message.warning(tl('请先保存接口用例'))
    return
  }
  const res = await interfaceCaseService.historyReports(projectStore.currentProjectId, currentInterfaceCaseId.value, {
    page: 1,
    page_size: 1
  })
  const reports = res.success && res.data
    ? (Array.isArray(res.data) ? res.data : (res.data as any).results || [])
    : []
  if (!reports.length) {
    Message.warning(tl('该接口用例暂无报告，请先运行测试'))
    return
  }
  await fetchReportDetail(reports[0].id)
}

onMounted(async () => {
  if (!projectStore.currentProjectId) return
  await Promise.all([loadModules(), loadInterfaces()])
  if (props.mode === 'edit') {
    await fetchDetail()
  } else {
    const routeInterfaceId = Number(route.query.interface_id)
    if (Number.isInteger(routeInterfaceId) && routeInterfaceId > 0) {
      setMainInterface(routeInterfaceId)
    }
  }
})
</script>

<template>
  <div class="interface-case-form h-full flex flex-col gap-4 p-4 overflow-hidden" :class="isDarkTheme ? 'interface-case-form--dark' : 'interface-case-form--light'">
    <div class="form-card p-4 flex-shrink-0">
      <div class="form-header">
        <div class="form-header-main">
          <TestCaseBasicInfo
            class="basic-info-inline"
            :model-value="{ name: formData.name, description: formData.description }"
            :readonly="readonly"
            @update:model-value="updateHeaderData"
          />

          <a-select
            :model-value="formData.interface_id"
            :placeholder="tl('主接口')"
            class="main-interface-select"
            allow-search
            :fallback-option="false"
            @update:model-value="(value: number) => setMainInterface(value)"
          >
            <a-option v-for="api in interfaces" :key="api.id" :value="api.id" :label="api.name">
              <div class="interface-option">
                <a-tag size="small" color="arcoblue">{{ api.method || api.sql_method }}</a-tag>
                <span>{{ api.name }}</span>
              </div>
            </a-option>
          </a-select>

          <GroupManager
            class="group-select-inline"
            :model-value="formData.group"
            :project-id="projectStore.currentProjectId"
            @update:model-value="val => formData.group = val ?? undefined"
          />

          <TagManager
            class="tag-select-inline"
            :model-value="formData.tags"
            :project-id="projectStore.currentProjectId"
            @update:model-value="val => formData.tags = val || []"
          />

          <a-select v-model="formData.priority" :placeholder="tl('优先级')" class="!w-24">
            <template #prefix><icon-fire /></template>
            <a-option value="P0">P0</a-option>
            <a-option value="P1">P1</a-option>
            <a-option value="P2">P2</a-option>
            <a-option value="P3">P3</a-option>
          </a-select>

          <TestCaseConfigDialog
            :model-value="formData.config"
            :steps="stepsForConfig"
            @update:model-value="val => formData.config = val"
          />
        </div>

        <div class="form-header-actions">
          <a-button v-if="currentInterfaceCaseId" type="outline" size="small" class="btn-run" @click="handleRun">
            <template #icon><icon-play-arrow /></template>
            {{ tl('运行') }}
          </a-button>
          <a-button v-if="currentInterfaceCaseId" type="outline" size="small" class="btn-report" @click="handleShowReport">
            <template #icon><icon-history /></template>
            {{ tl('报告') }}
          </a-button>
          <a-button type="outline" size="small" class="btn-cancel" @click="handleCancel">
            <template #icon><icon-close /></template>
            {{ tl('取消') }}
          </a-button>
          <a-button type="outline" size="small" class="btn-save" :loading="loading" @click="() => handleSubmit()">
            <template #icon><icon-check /></template>
            {{ tl('保存') }}
          </a-button>
        </div>
      </div>
    </div>

    <div class="flex-1 flex gap-4 min-h-0">
      <div class="w-[23%] form-card p-4 overflow-hidden">
        <div class="step-list-header">
          <a-tag>{{ preconditionCountText }}</a-tag>
          <a-trigger
            trigger="click"
            position="bottom"
            :popup-visible="addPreconditionMenuVisible"
            :popup-translate="[0, 8]"
            @popup-visible-change="visible => addPreconditionMenuVisible = visible"
          >
            <a-button size="mini" type="primary">
              <template #icon><icon-plus /></template>
              {{ tl('添加') }}
            </a-button>
            <template #content>
              <a-menu class="precondition-add-menu">
                <a-menu-item
                  v-for="type in preconditionAddTypes"
                  :key="type.value"
                  class="precondition-add-menu-item"
                  @click="handleAddPreconditionType(type.value)"
                >
                  <span class="precondition-add-menu-label">{{ tl(type.label) }}</span>
                </a-menu-item>
              </a-menu>
            </template>
          </a-trigger>
        </div>

        <div class="step-list-scroll">
          <div
            v-for="(step, index) in preconditionSteps"
            :key="getStepKey(step) || `${step.role}-${step.order}-${index}`"
            class="step-card"
            :class="{ 'step-card--active': isSameStep(activeStep, step) }"
            @click="activeStep = step; showReport = false"
          >
            <div class="step-card-index">{{ index + 1 }}</div>
            <div class="step-card-body">
              <div class="step-card-title">{{ step.name }}</div>
              <div class="step-card-meta">
                <span>{{ step.interface_info?.method || 'METHOD' }}</span>
                <span class="truncate">{{ step.interface_info?.url || step.interface_data?.url || step.interface_data?.sql || '-' }}</span>
              </div>
            </div>
            <div class="step-card-actions">
              <a-button size="mini" type="text" :disabled="index === 0" @click.stop="movePrecondition(step, -1)">
                <icon-up />
              </a-button>
              <a-button size="mini" type="text" :disabled="index === preconditionSteps.length - 1" @click.stop="movePrecondition(step, 1)">
                <icon-down />
              </a-button>
              <a-button size="mini" type="text" status="danger" @click.stop="handleDeletePrecondition(step)">
                <icon-delete />
              </a-button>
            </div>
          </div>

          <div
            v-if="mainStep"
            class="step-card step-card--main"
            :class="{ 'step-card--active': isSameStep(activeStep, mainStep) }"
            @click="activeStep = mainStep; showReport = false"
          >
            <div class="step-card-index">{{ mainStepBadge }}</div>
            <div class="step-card-body">
              <div class="step-card-title">{{ mainStep.name }}</div>
              <div class="step-card-meta">
                <span>{{ mainStep.interface_info?.method || 'METHOD' }}</span>
                <span class="truncate">{{ mainStep.interface_info?.url || mainStep.interface_data?.url || mainStep.interface_data?.sql || '-' }}</span>
              </div>
            </div>
          </div>

          <div v-else class="empty-step-state">
            {{ tl('请选择主接口') }}
          </div>
        </div>
      </div>

      <div class="flex-1 min-w-0 form-card overflow-hidden">
        <TestCaseStepDetail
          v-if="activeStep && !showReport"
          ref="activeStepDetailRef"
          :key="activeStepRenderKey"
          :model-value="activeStep as any"
          :modules="modules"
          :readonly="readonly"
          interface-case-mode
          @update:model-value="updateStepData"
          @save-interface-case-step="handleSaveStepToInterfaceCase"
        />

        <a-spin :loading="reportLoading" dot class="h-full" v-else-if="showReport && latestReport">
          <div class="h-full overflow-auto p-4">
            <ExecutionSteps :report="latestReport" />
          </div>
        </a-spin>

        <div v-else class="empty-text">
          {{ showReport ? tl('暂无报告数据') : tl('请选择前置条件或主接口') }}
        </div>
      </div>
    </div>

    <ApiSelectDialog
      v-model:visible="addPreconditionVisible"
      @select="handlePreconditionInterfaceSelect"
    />
  </div>
</template>

<style scoped>
.interface-case-form {
  min-height: 0;
  --tcf-card-bg: #ffffff;
  --tcf-card-border: rgba(203, 213, 225, 0.9);
  --tcf-card-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
  --tcf-section-bg: #f8fafc;
  --tcf-section-hover: #f1f5f9;
  --tcf-control-bg: #ffffff;
  --tcf-control-border: rgba(148, 163, 184, 0.36);
  --tcf-text: #0f172a;
  --tcf-text-muted: #475569;
  --tcf-text-subtle: #64748b;
  --tcf-panel-border: rgba(203, 213, 225, 0.96);
}

.interface-case-form--dark {
  --tcf-card-bg: rgba(31, 41, 55, 0.5);
  --tcf-card-border: rgba(148, 163, 184, 0.12);
  --tcf-card-shadow: 0 18px 32px rgba(2, 6, 23, 0.28);
  --tcf-section-bg: rgba(31, 41, 55, 0.74);
  --tcf-section-hover: rgba(51, 65, 85, 0.5);
  --tcf-control-bg: rgba(15, 23, 42, 0.6);
  --tcf-control-border: rgba(75, 85, 99, 0.45);
  --tcf-text: rgb(241, 245, 249);
  --tcf-text-muted: rgb(203, 213, 225);
  --tcf-text-subtle: rgb(148, 163, 184);
  --tcf-panel-border: rgba(75, 85, 99, 0.4);
}

.form-card {
  background: var(--tcf-card-bg);
  border: 1px solid var(--tcf-card-border);
  border-radius: 8px;
  box-shadow: var(--tcf-card-shadow);
}

.form-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-width: 0;
  flex-wrap: nowrap;
}

.form-header-main,
.form-header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: nowrap;
}

.form-header-main {
  flex: 1 1 auto;
  min-width: 0;
  overflow-x: auto;
  scrollbar-width: thin;
}

.form-header-actions {
  flex: 0 0 auto;
}

.basic-info-inline {
  flex: 0 0 auto;
}

.main-interface-select {
  flex: 0 0 220px;
  width: 220px;
}

.group-select-inline,
.tag-select-inline {
  flex: 0 0 auto;
}

.group-select-inline {
  --testcase-group-select-width: 150px;
}

.tag-select-inline {
  --testcase-tag-select-width: 160px;
}

.interface-option {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
}

.step-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.step-list-scroll {
  height: calc(100vh - 270px);
  overflow: auto;
  scrollbar-width: none;
}

.step-list-scroll::-webkit-scrollbar {
  display: none;
}

.precondition-add-menu {
  min-width: 128px;
}

.precondition-add-menu-label {
  display: block;
  width: 100%;
  text-align: center;
}

:deep(.precondition-add-menu-item) {
  padding: 0 12px !important;
}

:deep(.precondition-add-menu-item .arco-menu-item-inner) {
  width: 100%;
  justify-content: center;
}

.step-card {
  display: flex;
  align-items: center;
  gap: 10px;
  box-sizing: border-box;
  height: 76px;
  min-height: 76px;
  padding: 12px;
  margin-bottom: 10px;
  border-radius: 8px;
  cursor: pointer;
  background: var(--tcf-section-bg);
  border: 1px solid var(--tcf-panel-border);
}

.step-card:hover {
  background: var(--tcf-section-hover);
}

.step-card--active {
  background: rgba(59, 130, 246, 0.12);
  border-color: rgba(59, 130, 246, 0.32);
}

.step-card--main {
  border-color: rgba(16, 185, 129, 0.35);
}

.step-card-index {
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: 8px;
  color: #fff;
  background: #3b82f6;
  font-size: 13px;
  font-weight: 600;
}

.step-card--main .step-card-index {
  background: #10b981;
}

.step-card-body {
  min-width: 0;
  flex: 1;
}

.step-card-title {
  color: var(--tcf-text);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.step-card-meta {
  display: flex;
  gap: 8px;
  margin-top: 6px;
  color: var(--tcf-text-subtle);
  font-size: 12px;
}

.step-card-actions {
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  justify-content: center;
  height: 52px;
}

.step-card-actions :deep(.arco-btn) {
  width: 20px;
  min-width: 20px;
  height: 16px;
  padding: 0;
  line-height: 16px;
}

.step-card-actions :deep(.arco-icon) {
  font-size: 12px;
}

.empty-step-state,
.empty-text {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--tcf-text-subtle);
}

.btn-run,
.btn-report,
.btn-cancel,
.btn-save {
  height: 32px !important;
}

.btn-run {
  color: #10b981 !important;
  border-color: rgba(16, 185, 129, 0.25) !important;
}

.btn-report {
  color: #f97316 !important;
  border-color: rgba(249, 115, 22, 0.25) !important;
}

.btn-save {
  color: #8b5cf6 !important;
  border-color: rgba(139, 92, 246, 0.3) !important;
}

:deep(.arco-select-view),
:deep(.arco-input-wrapper),
:deep(.arco-textarea-wrapper) {
  background: var(--tcf-control-bg) !important;
  border-color: var(--tcf-control-border) !important;
  color: var(--tcf-text) !important;
}
</style>
