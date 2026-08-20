<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { testcaseService } from '../../services/testcaseService'
import { testReportService } from '../../services/testReportService'
import { toArray } from '../../services/responseHelpers'
import type { CreateTestCaseData, TestCaseStep } from '../../services/testcaseService'
import type { ApiTestReportDetail } from '../../types/testcase'
import type { ApiModule } from '../../types/module'
import { moduleService } from '../../services/moduleService'
import { useProjectStore } from '@/store/projectStore'
import { useThemeStore } from '@/store/themeStore'
import TestCaseHeader from './TestCaseHeader.vue'
import TestCaseStepList from './TestCaseStepList.vue'
import TestCaseStepDetail from './TestCaseStepDetail.vue'
import ExecutionSteps from '../test-reports/ExecutionSteps.vue'
import { showExtractPersistenceNotice } from '../../utils/extractPersistence'
import { useAppI18n } from '@/composables/useAppI18n'

interface Props {
  projectId: number
  mode?: 'create' | 'edit' | 'view'
  testCaseId?: number
}

const props = withDefaults(defineProps<Props>(), {
  mode: 'create'
})
const emit = defineEmits(['cancel', 'success', 'update:testCaseId'])

const projectStore = useProjectStore()
const themeStore = useThemeStore()
const { tl } = useAppI18n()
const isDarkTheme = computed(() => themeStore.isBlack)

const currentTestCaseId = ref<number | undefined>(props.testCaseId)

const testCaseId = computed(() => {
  return currentTestCaseId.value || props.testCaseId
})

const loading = ref(false)
const activeStep = ref<TestCaseStep | null>(null)

// 模块列表
const modules = ref<ApiModule[]>([])

const fetchModules = async () => {
  if (!projectStore.currentProjectId) return
  try {
    const res = await moduleService.tree(projectStore.currentProjectId)
    if (res.success && res.data) {
      modules.value = toArray<ApiModule>((res.data as any)?.results ?? res.data)
    }
  } catch (error) {
    console.error('获取模块列表失败:', error)
  }
}

// 报告相关
const showReport = ref(false)
const reportLoading = ref(false)
const latestReport = ref<any>(null)

// 初始化表单数据
const formData = reactive<CreateTestCaseData>({
  name: '',
  description: '',
  project: props.projectId,
  priority: 'P3',
  config: {
    base_url: '',
    variables: '',
    parameters: '',
    export: '',
    verify: ''
  },
  steps_info: []
})

const readonly = computed(() => props.mode === 'view')

interface TestCaseStepForHeader {
  id: number
  name: string
  interface_data: {
    extract?: Record<string, string>
  }
}

const steps = ref<TestCaseStep[]>([])

const activeStepRenderKey = computed(() => {
  if (!activeStep.value) {
    return 'empty-step'
  }

  if (activeStep.value.id) {
    return `step-${activeStep.value.id}`
  }

  return `draft-step-${activeStep.value.order || 0}`
})

const stepsForHeader = computed<TestCaseStepForHeader[]>(() => {
  return steps.value.map(step => ({
    id: step.id || 0,
    name: step.name,
    interface_data: {
      extract: step.interface_data.extract as Record<string, string>
    }
  }))
})

const resolveConfigVerify = (value: unknown) => {
  return typeof value === 'boolean' ? value : undefined
}

const buildSubmitConfig = () => {
  const config = { ...(formData.config || {}) }
  if (typeof config.verify !== 'boolean') {
    delete config.verify
  }
  return config
}

const updateSteps = (newSteps: TestCaseStep[]) => {
  steps.value = newSteps.map(step => ({
    ...step,
    interface_info: {
      ...step.interface_info,
      module_info: step.interface_info.module_info || {
        id: step.interface_info.module?.id || 0,
        name: step.interface_info.module?.name || ''
      }
    }
  }))

  formData.steps_info = steps.value.map((step, index) => ({
    ...(step.id ? { id: step.id } : {}),
    name: step.name,
    interface_id: step.interface_info.id || 0,
    order: step.order || index + 1,
    interface_data: {
      ...step.interface_data,
      module: step.interface_info.module_info?.id || step.interface_data.module || 0
    },
    config: step.config,
    sync_fields: step.sync_fields
  }))
}

const fetchTestCaseDetail = async () => {
  if (props.mode !== 'create' && testCaseId.value && projectStore.currentProjectId) {
    try {
      loading.value = true
      const res = await testcaseService.get(projectStore.currentProjectId, testCaseId.value)

      if (!res.success || !res.data) {
        throw new Error(res.error || tl('获取用例详情失败'))
      }

      const testCase = res.data as any
      console.log('获取到的用例详情:', testCase)

      formData.name = testCase.name || ''
      formData.description = testCase.description || ''
      formData.priority = testCase.priority || 'P3'
      formData.group = testCase.group === null ? undefined : testCase.group
      formData.tags = testCase.tags || []
      formData.config = {
        base_url: testCase.config?.base_url || '',
        variables: testCase.config?.variables || '',
        parameters: testCase.config?.parameters || '',
        export: testCase.config?.export || '',
        verify: resolveConfigVerify(testCase.config?.verify)
      }

      updateSteps(testCase.steps || [])
    } catch (error) {
      console.error('获取用例详情失败:', error)
      Message.error(error instanceof Error ? error.message : tl('获取用例详情失败'))
    } finally {
      loading.value = false
    }
  }
}

onMounted(() => {
  fetchTestCaseDetail()
  fetchModules()
})

const handleAddStep = () => {
  if (readonly.value) return

  const newStep: TestCaseStep = {
    id: 0,
    name: `步骤${steps.value.length + 1}`,
    order: steps.value.length + 1,
    interface_info: {
      id: 0,
      name: '',
      method: 'GET',
      url: '',
      module: { id: 0, name: '' },
      project: { id: props.projectId, name: '' }
    },
    interface_data: {
      method: 'GET',
      url: '',
      headers: {},
      params: {},
      body: {},
      validators: [],
      extract: {},
      setup_hooks: [],
      teardown_hooks: [],
      variables: {}
    },
    config: {
      variables: {},
      validators: [],
      extract: {},
      setup_hooks: [],
      teardown_hooks: []
    },
    sync_fields: [
      'method', 'url', 'headers', 'params', 'body',
      'setup_hooks', 'teardown_hooks', 'variables', 'validators', 'extract'
    ],
    last_sync_time: null
  }

  const newSteps = [...steps.value, newStep]
  updateSteps(newSteps)
  handleStepSelect(newSteps[newSteps.length - 1])
}

const handleStepSelect = (step: TestCaseStep | null) => {
  if (step) {
    showReport.value = false
    activeStep.value = {
      ...step,
      interface_info: {
        ...step.interface_info,
        module: step.interface_info.module || { id: 0, name: '' },
        module_info: step.interface_info.module_info || step.interface_info.module || { id: 0, name: '' },
        project: step.interface_info.project || { id: props.projectId, name: '' }
      },
      interface_data: {
        ...step.interface_data,
        headers: step.interface_data.headers || {},
        params: step.interface_data.params || {},
        body: step.interface_data.body || {},
        validators: step.interface_data.validators || [],
        extract: step.interface_data.extract || {},
        setup_hooks: step.interface_data.setup_hooks || [],
        teardown_hooks: step.interface_data.teardown_hooks || [],
        variables: step.interface_data.variables || {}
      },
      config: {
        ...step.config,
        variables: step.config?.variables || {},
        validators: step.config?.validators || [],
        extract: step.config?.extract || {},
        setup_hooks: step.config?.setup_hooks || [],
        teardown_hooks: step.config?.teardown_hooks || []
      }
    }
  } else {
    activeStep.value = null
  }
}

const handleStepDelete = (step: TestCaseStep) => {
  if (readonly.value) return
  const index = steps.value.findIndex(s => s === step)
  if (index !== -1) {
    const newSteps = [...steps.value]
    newSteps.splice(index, 1)
    newSteps.forEach((s, i) => { s.order = i + 1 })
    updateSteps(newSteps)
    if (activeStep.value === step) {
      activeStep.value = null
    }
  }
}

const handleTestCaseRefresh = (testCase: { steps?: TestCaseStep[] }) => {
  const refreshedSteps = testCase.steps || []
  updateSteps(refreshedSteps)

  if (!activeStep.value) {
    return
  }

  const matchedStep = refreshedSteps.find((step) => {
    if (activeStep.value?.id) {
      return step.id === activeStep.value.id
    }

    return step.order === activeStep.value?.order
  })

  if (matchedStep) {
    handleStepSelect(matchedStep)
  }
}

const validateForm = () => {
  if (!formData.name) {
    Message.error(tl('请输入用例名称'))
    return false
  }
  if (!formData.priority) {
    Message.error(tl('请选择优先级'))
    return false
  }
  return true
}

const handleSubmit = async (continueAction?: () => void) => {
  if (readonly.value) return false
  if (!validateForm()) return false
  if (!projectStore.currentProjectId) return false

  try {
    loading.value = true
    const submitData: CreateTestCaseData & { update_mode?: 'update' } = {
      ...formData,
      config: buildSubmitConfig(),
      ...(props.mode === 'edit' ? { update_mode: 'update' } : {}),
      steps_info: steps.value.map((step, index) => ({
        ...(step.id ? { id: step.id } : {}),
        name: step.name,
        interface_id: step.interface_info.id || 0,
        interface_data: step.interface_data,
        config: step.config,
        sync_fields: step.sync_fields,
        order: index + 1
      }))
    }

    if (props.mode === 'edit' && testCaseId.value) {
      const res = await testcaseService.update(projectStore.currentProjectId, testCaseId.value, submitData as any)
      if (res.success) {
        Message.success(tl('更新成功'))
        await fetchTestCaseDetail()
      } else {
        throw new Error(res.error || tl('更新失败'))
      }
    } else {
      const res = await testcaseService.create(projectStore.currentProjectId, submitData as any)
      if (res.success && res.data) {
        Message.success(tl('创建成功，现在您可以添加测试步骤了'))
        const newId = (res.data as any).id
        if (newId) {
          currentTestCaseId.value = newId
          emit('update:testCaseId', newId)
          emit('success', { id: newId, mode: 'created' })
        }
      } else {
        throw new Error(res.error || tl('创建失败'))
      }
    }

    if (continueAction) {
      setTimeout(() => { continueAction() }, 500)
    }

    return true
  } catch (error) {
    Message.error(tl(props.mode === 'edit' ? '更新失败' : '创建失败'))
    return false
  } finally {
    loading.value = false
  }
}

const handleCancel = () => {
  emit('cancel')
}

const updateHeaderData = (data: Pick<CreateTestCaseData, 'name' | 'description' | 'priority' | 'group' | 'tags'>) => {
  Object.assign(formData, data)
}

const updateStepData = (step: TestCaseStep) => {
  const index = steps.value.findIndex(s => {
    if (activeStep.value) {
      if (!s.id) return s.order === activeStep.value.order
      return s.id === activeStep.value.id
    }
    return false
  })

  if (index !== -1) {
    const newSteps = [...steps.value]
    if (!steps.value[index].id) { step.id = 0 }
    newSteps[index] = step
    updateSteps(newSteps)
    activeStep.value = step
  }
}

// 运行用例
const runResultLoading = ref(false)

const handleRun = async (data: { testCaseId: number, environmentId: number }) => {
  if (!projectStore.currentProjectId) return
  try {
    runResultLoading.value = true
    const res = await testcaseService.run(projectStore.currentProjectId, data.testCaseId, {
      environment_id: data.environmentId
    })

    if (res.success && res.data) {
      showExtractPersistenceNotice((res.data as any).extract_persistence)
      Message.success(tl('用例运行成功'))
      const reportId = (res.data as any).report_id
      if (reportId) {
        await fetchReportDetail(Number(reportId))
        return
      }
      // Fallback: get latest report
      const historyRes = await testcaseService.historyReports(projectStore.currentProjectId!, data.testCaseId, {
        page: 1,
        page_size: 1
      })
      if (historyRes.success && historyRes.data) {
        const reports = toArray<any>((historyRes.data as any)?.results ?? historyRes.data)
        if (reports.length > 0) {
          await fetchReportDetail(reports[0].id)
        } else {
          Message.warning(tl('获取运行结果失败，请前往报告列表查看'))
        }
      }
    } else {
      throw new Error(res.error || tl('运行用例失败'))
    }
  } catch (error) {
    console.error('运行用例失败:', error)
    Message.error(error instanceof Error ? error.message : tl('运行用例失败'))
  } finally {
    runResultLoading.value = false
  }
}

const fetchReportDetail = async (reportId: number) => {
  if (!projectStore.currentProjectId) return
  try {
    reportLoading.value = true
    const res = await testReportService.get(projectStore.currentProjectId, reportId)
    if (res.success && res.data) {
      latestReport.value = res.data
      showReport.value = true
      activeStep.value = null
    } else {
      Message.error(tl('获取报告详情失败'))
    }
  } catch (error) {
    console.error('获取报告详情失败:', error)
    Message.error(tl('获取报告详情失败，请稍后重试'))
  } finally {
    reportLoading.value = false
  }
}

const handleShowReport = async (tcId: number) => {
  if (!projectStore.currentProjectId) return
  try {
    reportLoading.value = true
    const res = await testcaseService.historyReports(projectStore.currentProjectId, tcId, {
      page: 1,
      page_size: 1
    })
    if (res.success && res.data) {
      const reports = toArray<any>((res.data as any)?.results ?? res.data)
      if (reports.length > 0) {
        await fetchReportDetail(reports[0].id)
      } else {
        Message.warning(tl('该测试用例暂无报告，请先运行测试'))
        showReport.value = false
      }
    }
  } catch (error) {
    console.error('获取报告列表失败:', error)
    Message.error(tl('获取报告列表失败，请稍后重试'))
  } finally {
    reportLoading.value = false
  }
}
</script>

<template>
  <div class="testcase-form-page h-full flex flex-col gap-4 p-4 overflow-hidden" :class="isDarkTheme ? 'testcase-form-page--dark' : 'testcase-form-page--light'">
    <!-- 顶部：基础信息 -->
    <div class="flex-shrink-0 form-card p-4">
      <test-case-header
        :model-value="{
          name: formData.name || '',
          description: formData.description || '',
          priority: formData.priority,
          group: formData.group !== undefined ? formData.group : null,
          tags: formData.tags || [],
          config: {
            base_url: formData.config?.base_url || '',
            variables: typeof formData.config?.variables === 'string' ? formData.config.variables : JSON.stringify(formData.config?.variables || {}),
            parameters: typeof formData.config?.parameters === 'string' ? formData.config.parameters : JSON.stringify(formData.config?.parameters || {}),
            export: Array.isArray(formData.config?.export) ? formData.config.export : [],
            verify: resolveConfigVerify(formData.config?.verify)
          }
        }"
        :loading="loading"
        :readonly="readonly"
        :project-id="projectId"
        :test-case-id="testCaseId"
        :steps="stepsForHeader"
        @update:model-value="updateHeaderData"
        @cancel="handleCancel"
        @save="handleSubmit"
        @run="handleRun"
        @show-report="handleShowReport"
      />
    </div>

    <!-- 主体内容：左侧步骤列表 + 右侧步骤详情 -->
    <div class="flex-1 flex gap-4 min-h-0">
      <!-- 左侧：步骤列表 -->
      <div class="w-[20%] form-card p-4 overflow-hidden">
        <test-case-step-list
          :steps="steps"
          :active-step="activeStep"
          :readonly="readonly"
          :test-case-id="testCaseId"
          :test-case="{
            name: formData.name || '',
            priority: formData.priority as 'P0' | 'P1' | 'P2' | 'P3',
            project: formData.project,
            description: formData.description,
            group: formData.group,
            tags: formData.tags || [],
            config: {
              base_url: formData.config?.base_url || '',
              variables: typeof formData.config?.variables === 'string' ? {} : (formData.config?.variables || {}),
              parameters: typeof formData.config?.parameters === 'string' ? {} : (formData.config?.parameters || {}),
              export: Array.isArray(formData.config?.export) ? formData.config.export : [],
              verify: resolveConfigVerify(formData.config?.verify)
            }
          }"
          @add="handleAddStep"
          @select="handleStepSelect"
          @delete="handleStepDelete"
          @update:steps="updateSteps"
          @save-test-case="(callback) => handleSubmit(callback)"
        />
      </div>

      <!-- 右侧：步骤详情或报告详情 -->
      <div class="flex-1 min-w-0 form-card overflow-hidden">
        <!-- 步骤详情 -->
        <test-case-step-detail
          v-if="activeStep && !showReport"
          :key="activeStepRenderKey"
          :model-value="activeStep"
          :modules="modules"
          :readonly="readonly"
          :test-case-id="testCaseId"
          @update:model-value="updateStepData"
          @refresh-test-case="handleTestCaseRefresh"
        />

        <!-- 报告详情 -->
        <a-spin :loading="reportLoading" dot class="h-full" v-else-if="showReport && latestReport">
          <div class="h-full overflow-auto p-4">
            <execution-steps :report="latestReport" />
          </div>
        </a-spin>

        <!-- 空状态 -->
        <div v-else class="flex items-center justify-center h-full empty-text">
          {{ showReport ? tl('暂无报告数据') : (readonly ? tl('请选择步骤查看详情') : tl('请选择或添加步骤')) }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.testcase-form-page {
  min-height: 0;
  --tcf-card-bg: #ffffff;
  --tcf-card-border: rgba(203, 213, 225, 0.9);
  --tcf-card-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
  --tcf-section-bg: #f8fafc;
  --tcf-section-hover: #f1f5f9;
  --tcf-control-bg: #ffffff;
  --tcf-control-border: rgba(148, 163, 184, 0.36);
  --tcf-control-hover: #f8fafc;
  --tcf-text: #0f172a;
  --tcf-text-muted: #475569;
  --tcf-text-subtle: #64748b;
  --tcf-panel-border: rgba(203, 213, 225, 0.96);
  --tcf-resize-bg: rgba(148, 163, 184, 0.24);
  --tcf-resize-hover: rgba(59, 130, 246, 0.28);
}

.testcase-form-page--dark {
  --tcf-card-bg: rgba(31, 41, 55, 0.5);
  --tcf-card-border: rgba(148, 163, 184, 0.12);
  --tcf-card-shadow: 0 18px 32px rgba(2, 6, 23, 0.28);
  --tcf-section-bg: rgba(31, 41, 55, 0.74);
  --tcf-section-hover: rgba(51, 65, 85, 0.5);
  --tcf-control-bg: rgba(15, 23, 42, 0.6);
  --tcf-control-border: rgba(75, 85, 99, 0.45);
  --tcf-control-hover: rgba(31, 41, 55, 0.88);
  --tcf-text: rgb(241, 245, 249);
  --tcf-text-muted: rgb(203, 213, 225);
  --tcf-text-subtle: rgb(148, 163, 184);
  --tcf-panel-border: rgba(75, 85, 99, 0.4);
  --tcf-resize-bg: rgba(75, 85, 99, 0.5);
  --tcf-resize-hover: rgba(59, 130, 246, 0.4);
}

.form-card {
  background: var(--tcf-card-bg);
  border: 1px solid var(--tcf-card-border);
  border-radius: 0.5rem;
  box-shadow: var(--tcf-card-shadow);
}

.empty-text {
  color: var(--tcf-text-subtle);
}
</style>
