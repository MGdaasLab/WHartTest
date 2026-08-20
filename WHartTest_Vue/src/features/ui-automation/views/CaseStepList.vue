<template>
  <div class="case-step-list">
    <div class="step-header">
      <span class="step-title">{{ pageText.stepListTitle }}</span>
      <a-button type="primary" size="small" @click="showAddModal">
        <template #icon><icon-plus /></template>
        {{ pageText.addStep }}
      </a-button>
    </div>

    <a-spin :loading="loading">
      <div v-if="stepData.length === 0" class="empty-tips">
        <a-empty :description="pageText.emptyState" />
      </div>
      <draggable
        v-else
        v-model="stepData"
        item-key="id"
        handle=".drag-handle"
        @end="onDragEnd"
      >
        <template #item="{ element, index }">
          <div class="step-card">
            <div class="step-left">
              <div class="drag-handle">
                <icon-drag-dot-vertical />
              </div>
              <div class="step-index">{{ index + 1 }}</div>
            </div>
            <div class="step-content">
              <span class="info-item">
                <a-tag v-if="element.module_name" size="small" color="arcoblue" style="margin-right: 4px;">
                  {{ element.module_name }}
                </a-tag>
                <a-tag v-if="element.page_name" size="small" color="cyan" style="margin-right: 4px;">
                  {{ element.page_name }}
                </a-tag>
                <span class="info-label">{{ pageText.stepLabel }}</span>
                <span class="step-name">{{ element.page_step_name }}</span>
              </span>
              <a-tag v-if="element.switch_step_open_url" color="orange" size="small">{{ pageText.switchUrl }}</a-tag>
              <a-tag v-if="element.error_retry > 0" color="blue" size="small">{{ pageText.retryLabel(element.error_retry) }}</a-tag>
              <a-tag :color="statusColors[element.status as ExecutionStatus]" size="small">
                {{ formatStatusLabel(element.status as ExecutionStatus) }}
              </a-tag>
            </div>
            <div class="step-actions">
              <a-button type="text" size="mini" @click="editStep(element)">
                <template #icon><icon-edit /></template>
              </a-button>
              <a-popconfirm :content="pageText.deleteStepConfirm" @ok="deleteStep(element)">
                <a-button type="text" status="danger" size="mini">
                  <template #icon><icon-delete /></template>
                </a-button>
              </a-popconfirm>
            </div>
          </div>
        </template>
      </draggable>
    </a-spin>

    <!-- 添加/编辑步骤弹窗 -->
    <a-modal
      v-model:visible="modalVisible"
      :title="caseStepModalTitle"
      :ok-loading="submitting"
      @before-ok="handleSubmit"
      @cancel="handleCancel"
    >
      <a-form ref="formRef" :model="formData" :rules="rules" layout="vertical">
        <a-form-item :label="pageText.selectModule">
          <a-select
            v-model="selectedModule"
            :placeholder="pageText.pleaseSelectModule"
            allow-search
            allow-clear
            @change="onModuleChange"
          >
            <a-option
              v-for="module in flatModuleOptions"
              :key="module.id"
              :value="module.id"
              :label="getModuleOptionLabel(module)"
            >
              {{ getModuleOptionLabel(module) }}
            </a-option>
          </a-select>
        </a-form-item>
        <a-form-item field="page_step" :label="pageText.selectPageStep" required>
          <a-select
            v-model="formData.page_step"
            :placeholder="pageText.selectPageStepPlaceholder"
            allow-search
            :disabled="!filteredPageStepOptions.length && selectedModule !== undefined"
            @change="onPageStepChange"
          >
            <a-option
              v-for="step in filteredPageStepOptions"
              :key="step.id"
              :value="step.id"
            >
              {{ step.page_name }} - {{ step.name }}
            </a-option>
          </a-select>
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="switch_step_open_url" :label="pageText.switchPageUrl">
              <a-switch v-model="formData.switch_step_open_url" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="error_retry" :label="pageText.retryCount">
              <a-input-number v-model="formData.error_retry" :min="0" :max="5" />
            </a-form-item>
          </a-col>
        </a-row>

        <!-- 数据覆盖区域 -->
        <template v-if="overrideFields.length > 0">
          <div class="override-section" style="margin-top: 16px; border-top: 1px solid var(--color-border); padding-top: 16px;">
            <div style="font-weight: 500; margin-bottom: 12px; font-size: 14px;">{{ pageText.dataOverride }}</div>
            <div style="color: var(--color-text-3); font-size: 12px; margin-bottom: 16px;">
              {{ pageText.dataOverrideHelp }}
            </div>
            
            <a-form-item
              v-for="field in overrideFields"
              :key="field.id"
              :label="field.label"
            >
              <a-input-number
                v-if="field.type === 'number'"
                v-model="caseOverrides[field.id]"
                :placeholder="field.placeholder"
                allow-clear
              />
              <a-input
                v-else
                v-model="caseOverrides[field.id]"
                :placeholder="field.placeholder"
                allow-clear
              />
            </a-form-item>
          </div>
        </template>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconPlus, IconEdit, IconDelete, IconDragDotVertical } from '@arco-design/web-vue/es/icon'
import draggable from 'vuedraggable'
import { caseStepsApi, pageStepsApi, moduleApi } from '../api'
import type { UiCaseStepsDetailed, UiPageSteps, UiTestCase, ExecutionStatus, UiModule } from '../types'
import { STATUS_LABELS, extractListData, extractResponseData } from '../types'
import { useProjectStore } from '@/store/projectStore'
import { useAppI18n } from '@/composables/useAppI18n'

const props = defineProps<{ testCase: UiTestCase }>()

const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)
const { isEnglish, tl } = useAppI18n()

const pageText = computed(() => (
  isEnglish.value
    ? {
        stepListTitle: 'Step list (drag to reorder)',
        addStep: 'Add step',
        emptyState: 'No steps yet. Please add page steps',
        stepLabel: 'Step:',
        switchUrl: 'Switch URL',
        retryLabel: (count: number) => `Retry ${count} times`,
        deleteStepConfirm: 'Delete this step?',
        editStep: 'Edit step',
        selectModule: 'Select module',
        pleaseSelectModule: 'Please select a module',
        selectPageStep: 'Select page step',
        selectPageStepPlaceholder: 'Select page step',
        switchPageUrl: 'Switch page URL',
        retryCount: 'Retry count on failure',
        selectPageStepRequired: 'Select page step',
        fetchStepListFailed: 'Failed to fetch step list',
        fetchPageStepListFailed: 'Failed to fetch page step list',
        fillRequired: 'Fill in the required fields',
        updateSuccess: 'Updated successfully',
        addSuccess: 'Added successfully',
        updateFailed: 'Update failed',
        addFailed: 'Add failed',
        deleteSuccess: 'Deleted successfully',
        deleteFailed: 'Delete failed',
        sortSaved: 'Order saved',
        sortSaveFailed: 'Failed to save order',
        dataOverride: 'Step Data Override',
        dataOverrideHelp: 'If input value is specified below, it will override the step\'s default value. Leave empty to use the default.',
      }
    : {
        stepListTitle: '步骤列表（拖拽可排序）',
        addStep: '添加步骤',
        emptyState: '暂无步骤，请添加页面步骤',
        stepLabel: '步骤:',
        switchUrl: '切换URL',
        retryLabel: (count: number) => `重试${count}次`,
        deleteStepConfirm: '确定删除该步骤？',
        editStep: '编辑步骤',
        selectModule: '选择模块',
        pleaseSelectModule: '请选择模块',
        selectPageStep: '选择页面步骤',
        selectPageStepPlaceholder: '请选择页面步骤',
        switchPageUrl: '切换页面URL',
        retryCount: '失败重试次数',
        selectPageStepRequired: '请选择页面步骤',
        fetchStepListFailed: '获取步骤列表失败',
        fetchPageStepListFailed: '获取页面步骤列表失败',
        fillRequired: '请填写必填项',
        updateSuccess: '更新成功',
        addSuccess: '添加成功',
        updateFailed: '更新失败',
        addFailed: '添加失败',
        deleteSuccess: '删除成功',
        deleteFailed: '删除失败',
        sortSaved: '排序已保存',
        sortSaveFailed: '保存排序失败',
        dataOverride: '步骤数据覆盖',
        dataOverrideHelp: '如果在此处填写了输入值，执行时将覆盖页面步骤中的默认值。留空则使用默认值。',
      }
))

const loading = ref(false)
const submitting = ref(false)
const stepData = ref<UiCaseStepsDetailed[]>([])
const pageStepOptions = ref<UiPageSteps[]>([])
const moduleOptions = ref<UiModule[]>([])
const modulesLoading = ref(false)
const selectedModule = ref<number | undefined>(undefined)
const modalVisible = ref(false)
const isEdit = ref(false)
const currentStep = ref<UiCaseStepsDetailed | null>(null)
const formRef = ref()

const flatModuleOptions = computed(() => flattenModules(moduleOptions.value))

const flattenModules = (modules: UiModule[], level = 0): (UiModule & { __level?: number })[] => {
  const result: (UiModule & { __level?: number })[] = []
  modules.forEach(module => {
    result.push({ ...module, __level: level })
    if (module.children?.length) {
      result.push(...flattenModules(module.children, level + 1))
    }
  })
  return result
}

const getModuleOptionLabel = (module: UiModule & { __level?: number }) => `${'　'.repeat(module.__level || 0)}${module.name}`

const fetchModules = async (force = false) => {
  if (!projectId.value || modulesLoading.value) return
  if (!force && moduleOptions.value.length > 0) return
  modulesLoading.value = true
  try {
    const res = await moduleApi.tree(projectId.value)
    const data = extractResponseData<UiModule[]>(res)
    moduleOptions.value = Array.isArray(data) ? data : []
  } catch {
    Message.error('获取模块列表失败')
  } finally {
    modulesLoading.value = false
  }
}

const OPE_PARAM_KEYS: Record<string, string> = {
  fill: 'text',
  type: 'text',
  wait: 'timeout',
  screenshot: 'name',
  select_option: 'value',
  assert_text: 'expected',
  assert_value: 'expected',
  assert_count: 'expected',
}

const OPE_KEY_LABELS: Record<string, string> = {
  click: '点击',
  dblclick: '双击',
  hover: '悬停',
  fill: '填充',
  type: '输入',
  clear: '清空',
  wait: '等待',
  screenshot: '截图',
  select_option: '选择下拉',
  assert_visible: '元素可见',
  assert_hidden: '元素隐藏',
  assert_text: '文本断言',
  assert_value: '值断言',
  assert_count: '数量断言',
}

const caseOverrides = reactive<Record<number, any>>({})
const selectedPageStepDetails = ref<any[]>([])

const overrideFields = computed(() => {
  const fields: any[] = []
  selectedPageStepDetails.value.forEach((detail, index) => {
    if (detail.ope_key && OPE_PARAM_KEYS[detail.ope_key]) {
      const key = OPE_PARAM_KEYS[detail.ope_key]
      const label = `步骤 ${index + 1}: ${detail.element_name || '无元素'} (${OPE_KEY_LABELS[detail.ope_key] || detail.ope_key})`
      let defaultValue = ''
      if (detail.ope_value && typeof detail.ope_value === 'object') {
        defaultValue = detail.ope_value[key] !== undefined ? String(detail.ope_value[key]) : ''
      }
      
      const type = (detail.ope_key === 'wait' || detail.ope_key === 'assert_count') ? 'number' : 'input'
      
      fields.push({
        id: detail.id,
        label,
        type,
        placeholder: defaultValue ? `默认值: ${defaultValue}` : '默认无',
        paramKey: key,
      })
    }
  })
  return fields
})

const loadPageStepDetails = async (pageStepId: number) => {
  try {
    const res = await pageStepsApi.get(pageStepId)
    const detail = extractResponseData<any>(res)
    selectedPageStepDetails.value = detail?.step_details || []
  } catch {
    selectedPageStepDetails.value = []
  }
}

const onPageStepChange = async () => {
  Object.keys(caseOverrides).forEach(k => delete caseOverrides[Number(k)])
  if (formData.page_step) {
    await loadPageStepDetails(formData.page_step)
  } else {
    selectedPageStepDetails.value = []
  }
}

const filteredPageStepOptions = computed(() => {
  if (selectedModule.value === undefined || selectedModule.value === null) {
    return pageStepOptions.value
  }
  return pageStepOptions.value.filter(step => step.module === selectedModule.value)
})

const onModuleChange = () => {
  formData.page_step = undefined
  selectedPageStepDetails.value = []
  Object.keys(caseOverrides).forEach(k => delete caseOverrides[Number(k)])
}

const formData = reactive({
  page_step: undefined as number | undefined,
  switch_step_open_url: false,
  error_retry: 0,
})

const rules = computed(() => ({
  page_step: [{ required: true, message: pageText.value.selectPageStepRequired }],
}))

const statusColors: Record<ExecutionStatus, string> = { 0: 'gray', 1: 'blue', 2: 'green', 3: 'red' }
const caseStepModalTitle = computed(() => (isEdit.value ? pageText.value.editStep : pageText.value.addStep))
const formatStatusLabel = (status: ExecutionStatus) => tl(STATUS_LABELS[status])

const fetchSteps = async () => {
  loading.value = true
  try {
    const res = await caseStepsApi.list({ test_case: props.testCase.id })
    stepData.value = extractListData<UiCaseStepsDetailed>(res)
  } catch {
    Message.error(pageText.value.fetchStepListFailed)
  } finally {
    loading.value = false
  }
}

const fetchPageSteps = async () => {
  if (!projectId.value) return
  try {
    const res = await pageStepsApi.list({ project: projectId.value })
    pageStepOptions.value = extractListData<UiPageSteps>(res)
  } catch {
    Message.error(pageText.value.fetchPageStepListFailed)
  }
}

const resetForm = () => {
  Object.assign(formData, { page_step: undefined, switch_step_open_url: false, error_retry: 0 })
  formRef.value?.clearValidate()
}

const showAddModal = () => {
  isEdit.value = false
  resetForm()
  selectedModule.value = undefined
  selectedPageStepDetails.value = []
  Object.keys(caseOverrides).forEach(k => delete caseOverrides[Number(k)])
  modalVisible.value = true
}

const editStep = async (step: UiCaseStepsDetailed) => {
  isEdit.value = true
  currentStep.value = step
  Object.assign(formData, {
    page_step: step.page_step,
    switch_step_open_url: step.switch_step_open_url,
    error_retry: step.error_retry,
  })
  
  Object.keys(caseOverrides).forEach(k => delete caseOverrides[Number(k)])
  
  if (step.page_step) {
    await loadPageStepDetails(step.page_step)
  }
  
  if (step.case_data && typeof step.case_data === 'object') {
    Object.entries(step.case_data).forEach(([detailId, val]) => {
      const id = Number(detailId)
      const detail = selectedPageStepDetails.value.find(d => d.id === id)
      if (detail && detail.ope_key && OPE_PARAM_KEYS[detail.ope_key]) {
        const paramKey = OPE_PARAM_KEYS[detail.ope_key]
        if (val && typeof val === 'object') {
          caseOverrides[id] = (val as any)[paramKey]
        } else {
          caseOverrides[id] = val
        }
      }
    })
  }
  
  const matchedStep = pageStepOptions.value.find(s => s.id === step.page_step)
  if (matchedStep) {
    selectedModule.value = matchedStep.module
  } else {
    selectedModule.value = undefined
  }
  
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
  
  const case_data: Record<number, any> = {}
  Object.entries(caseOverrides).forEach(([detailId, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      const id = Number(detailId)
      const detail = selectedPageStepDetails.value.find(d => d.id === id)
      if (detail && detail.ope_key && OPE_PARAM_KEYS[detail.ope_key]) {
        const paramKey = OPE_PARAM_KEYS[detail.ope_key]
        
        let finalValue: any = value
        if (detail.ope_key === 'wait' || detail.ope_key === 'assert_count') {
          finalValue = Number(value)
        }
        
        case_data[id] = { [paramKey]: finalValue }
      }
    }
  })
  
  submitting.value = true
  try {
    const payload = {
      ...formData,
      case_data: Object.keys(case_data).length > 0 ? case_data : null
    }
    
    if (isEdit.value && currentStep.value?.id) {
      await caseStepsApi.update(currentStep.value.id, payload)
      Message.success(pageText.value.updateSuccess)
    } else {
      await caseStepsApi.create({
        test_case: props.testCase.id,
        page_step: formData.page_step,
        case_sort: stepData.value.length,
        switch_step_open_url: formData.switch_step_open_url,
        error_retry: formData.error_retry,
        case_data: Object.keys(case_data).length > 0 ? case_data : null
      })
      Message.success(pageText.value.addSuccess)
    }
    done(true)
    fetchSteps()
  } catch (error: unknown) {
    const err = error as { errors?: Record<string, string[]>; error?: string }
    const errors = err?.errors
    if (errors && typeof errors === 'object' && !('error' in errors) && !('message' in errors)) {
      const messages = Object.entries(errors)
        .map(([field, msgs]) => `${field}: ${Array.isArray(msgs) ? msgs.join(', ') : msgs}`)
        .join('\n')
      Message.error({ content: messages, duration: 5000 })
    } else {
      Message.error(err?.error || (isEdit.value ? pageText.value.updateFailed : pageText.value.addFailed))
    }
    done(false)
  } finally {
    submitting.value = false
  }
}

const handleCancel = () => {
  modalVisible.value = false
}

const deleteStep = async (step: UiCaseStepsDetailed) => {
  if (!step.id) return
  try {
    await caseStepsApi.delete(step.id)
    Message.success(pageText.value.deleteSuccess)
    fetchSteps()
  } catch {
    Message.error(pageText.value.deleteFailed)
  }
}

const onDragEnd = async () => {
  try {
    const steps = stepData.value.map((s, idx) => ({
      page_step: s.page_step,
      case_sort: idx,
      switch_step_open_url: s.switch_step_open_url,
      error_retry: s.error_retry,
    }))
    await caseStepsApi.batchUpdate(props.testCase.id, steps)
    Message.success(pageText.value.sortSaved)
  } catch {
    Message.error(pageText.value.sortSaveFailed)
    fetchSteps()
  }
}

watch(() => props.testCase, () => {
  fetchSteps()
  fetchPageSteps()
  fetchModules(true)
}, { immediate: true })
</script>

<style scoped>
.case-step-list {
  padding: 8px 0;
  overflow-x: hidden;
}
.case-step-list :deep(.arco-spin) {
  width: 100%;
}
.step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.step-title {
  font-weight: 500;
}
.empty-tips {
  padding: 40px 0;
}
.step-card {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  margin-bottom: 8px;
  background: var(--color-bg-2);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  box-sizing: border-box;
  min-height: 48px;
  font-size: 13px;
  gap: 12px;
}
.step-left {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}
.drag-handle {
  cursor: move;
  color: var(--color-text-3);
  width: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 8px;
}
.step-index {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgb(var(--primary-6));
  color: #fff;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 500;
}
.step-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}
.info-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.info-label {
  color: var(--color-text-3);
  font-size: 12px;
  flex-shrink: 0;
}
.step-name {
  font-weight: 500;
  color: rgb(var(--primary-6));
}
.step-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
</style>
