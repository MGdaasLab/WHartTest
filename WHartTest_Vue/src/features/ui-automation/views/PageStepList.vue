<template>
  <div class="page-step-list">
    <div class="page-header">
      <div class="search-box">
        <a-select
          v-model="filters.page"
          :placeholder="pageText.selectPage"
          allow-clear
          allow-search
          style="width: 200px; margin-right: 12px"
          @change="onSearch"
        >
          <a-option v-for="p in pageOptions" :key="p.id" :value="p.id">
            {{ p.name }}
          </a-option>
        </a-select>
        <a-input-search
          v-model="filters.search"
          :placeholder="pageText.searchStepName"
          allow-clear
          style="width: 200px"
          @search="onSearch"
          @clear="onSearch"
        />
      </div>
      <div class="action-buttons">
        <a-button type="primary" @click="showAddModal">
          <template #icon><icon-plus /></template>
          {{ pageText.addStep }}
        </a-button>
      </div>
    </div>

    <a-table
      :key="`page-step-table-${locale}`"
      :columns="columns"
      :data="pageStepData"
      :pagination="pagination"
      :loading="loading"
      :scroll="{ x: 900 }"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
    >
      <template #page_name="{ record }">
        <a-tag color="arcoblue">{{ record.page_name }}</a-tag>
      </template>
      <template #status="{ record }">
        <a-tag :color="statusColors[record.status as ExecutionStatus]">
          {{ formatStatusLabel(record.status as ExecutionStatus) }}
        </a-tag>
      </template>
      <template #step_count="{ record }">
        <a-tag color="cyan">{{ record.step_count || 0 }}</a-tag>
      </template>
      <template #created_at="{ record }">
        {{ formatDate(record.created_at) }}
      </template>
      <template #operations="{ record }">
        <a-space :size="4">
          <a-button type="text" size="mini" @click="viewStepDetails(record)">
            <template #icon><icon-settings /></template>
            {{ pageText.manageStepDetails }}
          </a-button>
          <a-button type="text" size="mini" @click="editPageStep(record)">
            <template #icon><icon-edit /></template>
            {{ pageText.edit }}
          </a-button>
          <a-button type="text" size="mini" @click="copyPageStep(record)">
            <template #icon><icon-copy /></template>
            {{ pageText.copy }}
          </a-button>
          <a-popconfirm :content="pageText.deleteStepConfirm" @ok="deletePageStep(record)">
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
      :title="pageStepModalTitle"
      :ok-loading="submitting"
      @before-ok="handleSubmit"
      @cancel="handleCancel"
    >
      <a-form ref="formRef" :model="formData" :rules="rules" layout="vertical">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="module" :label="pageText.module" required>
              <a-select v-model="formData.module" :placeholder="pageText.selectModule" @change="onFormModuleChange">
                <a-option v-for="mod in moduleOptions" :key="mod.id" :value="mod.id">
                  {{ mod.name }}
                </a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="page" :label="pageText.page" required>
              <a-select v-model="formData.page" :placeholder="pageText.selectPage" :disabled="!formData.module">
                <a-option v-for="p in filteredPageOptions" :key="p.id" :value="p.id">
                  {{ p.name }}
                </a-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item field="name" :label="pageText.stepName" required>
          <a-input v-model="formData.name" :placeholder="pageText.enterStepName" :max-length="64" />
        </a-form-item>
        <a-form-item field="description" :label="pageText.description">
          <a-textarea v-model="formData.description" :placeholder="pageText.enterDescription" :auto-size="{ minRows: 2 }" />
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

    <!-- 步骤详情抽屉 -->
    <a-drawer
      v-model:visible="detailDrawerVisible"
      :title="pageStepDrawerTitle"
      width="50%"
      :footer="false"
    >
      <StepDetailList v-if="currentPageStep" :page-step="currentPageStep" />
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import FileAttachmentPicker from '@/features/file-management/components/FileAttachmentPicker.vue'
import { ref, reactive, computed, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconPlus, IconEdit, IconDelete, IconSettings, IconCopy } from '@arco-design/web-vue/es/icon'
import { useProjectStore } from '@/store/projectStore'
import { useAppI18n } from '@/composables/useAppI18n'
import { pageStepsApi, pageApi, moduleApi } from '../api'
import type { UiPageSteps, UiPageStepsForm, UiPage, UiModule, ExecutionStatus } from '../types'
import { STATUS_LABELS, extractListData, extractPaginationData, extractResponseData } from '../types'
import StepDetailList from './StepDetailList.vue'

const props = defineProps<{
  selectedModuleId?: number
}>()

const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)
const { locale, isEnglish, tl } = useAppI18n()

const pageText = computed(() => (
  isEnglish.value
    ? {
        selectPage: 'Select page',
        searchStepName: 'Search step name',
        addStep: 'Add step',
        manageStepDetails: 'Add step',
        edit: 'Edit',
        delete: 'Delete',
        copy: 'Copy',
        deleteStepConfirm: 'Delete this step?',
        editPageStep: 'Edit page step',
        addPageStep: 'Create page step',
        module: 'Module',
        selectModule: 'Select module',
        page: 'Page',
        stepName: 'Step name',
        enterStepName: 'Enter step name',
        description: 'Description',
        enterDescription: 'Enter description',
        stepDetails: 'Step details',
        status: 'Status',
        actionCount: 'Action count',
        createdBy: 'Created by',
        createdAt: 'Created at',
        operations: 'Actions',
        selectPageRequired: 'Select page',
        selectModuleRequired: 'Select module',
        enterStepNameRequired: 'Enter step name',
        fetchPageListFailed: 'Failed to fetch page list',
        fetchModuleListFailed: 'Failed to fetch module list',
        fetchPageStepListFailed: 'Failed to fetch page step list',
        fillRequired: 'Fill in the required fields',
        updateSuccess: 'Updated successfully',
        createSuccess: 'Created successfully',
        updateFailed: 'Update failed',
        createFailed: 'Creation failed',
        deleteSuccess: 'Deleted successfully',
        deleteBlocked: 'Linked data prevents deletion. Remove the associations first',
        copySuccess: 'Copied successfully',
        copyFailed: 'Copy failed',
      }
    : {
        selectPage: '选择页面',
        searchStepName: '搜索步骤名称',
        addStep: '新增步骤',
        manageStepDetails: '添加步骤',
        edit: '编辑',
        delete: '删除',
        copy: '复制',
        deleteStepConfirm: '确定删除该步骤？',
        editPageStep: '编辑页面步骤',
        addPageStep: '新增页面步骤',
        module: '所属模块',
        selectModule: '请选择模块',
        page: '所属页面',
        stepName: '步骤名称',
        enterStepName: '请输入步骤名称',
        description: '描述',
        enterDescription: '请输入描述',
        stepDetails: '步骤详情',
        status: '状态',
        actionCount: '操作数',
        createdBy: '创建者',
        createdAt: '创建时间',
        operations: '操作',
        selectPageRequired: '请选择页面',
        selectModuleRequired: '请选择模块',
        enterStepNameRequired: '请输入步骤名称',
        fetchPageListFailed: '获取页面列表失败',
        fetchModuleListFailed: '获取模块列表失败',
        fetchPageStepListFailed: '获取页面步骤列表失败',
        fillRequired: '请填写必填项',
        updateSuccess: '更新成功',
        createSuccess: '创建成功',
        updateFailed: '更新失败',
        createFailed: '创建失败',
        deleteSuccess: '删除成功',
        deleteBlocked: '存在关联，无法删除。请先解除关联',
        copySuccess: '复制成功',
        copyFailed: '复制失败',
      }
))

const loading = ref(false)
const submitting = ref(false)
const pageStepData = ref<UiPageSteps[]>([])
const pageOptions = ref<UiPage[]>([])
const moduleOptions = ref<UiModule[]>([])
const modalVisible = ref(false)
const detailDrawerVisible = ref(false)
const isEdit = ref(false)
const currentPageStep = ref<UiPageSteps | null>(null)
const formRef = ref()

// 根据表单选择的模块过滤页面选项
const filteredPageOptions = computed(() => {
  if (!formData.module) return []
  return pageOptions.value.filter((p) => p.module === formData.module)
})

const filters = reactive({ page: undefined as number | undefined, module: undefined as number | undefined, search: '' })
const pagination = reactive({ current: 1, pageSize: 10, total: 0, showTotal: true, showPageSize: true })

const formData = reactive<UiPageStepsForm>({
  file_ids: [],
  project: 0,
  page: undefined as unknown as number,
  module: undefined as unknown as number,
  name: '',
  description: '',
  run_flow: '',
  flow_data: {},
})

const rules = computed(() => ({
  page: [{ required: true, message: pageText.value.selectPageRequired }],
  module: [{ required: true, message: pageText.value.selectModuleRequired }],
  name: [{ required: true, message: pageText.value.enterStepNameRequired }],
}))

const statusColors: Record<ExecutionStatus, string> = { 0: 'gray', 1: 'blue', 2: 'green', 3: 'red' }

const columns = computed(() => [
  { title: 'ID', dataIndex: 'id', width: isEnglish.value ? 90 : 70, align: 'center' as const },
  { title: pageText.value.page, slotName: 'page_name', width: 140, align: 'center' as const },
  { title: pageText.value.stepName, dataIndex: 'name', ellipsis: true, tooltip: true, width: 180, align: 'center' as const },
  { title: pageText.value.status, slotName: 'status', width: 100, align: 'center' as const },
  { title: pageText.value.actionCount, slotName: 'step_count', width: 100, align: 'center' as const },
  { title: pageText.value.createdBy, dataIndex: 'creator_name', width: 110, align: 'center' as const },
  { title: pageText.value.createdAt, slotName: 'created_at', width: 180, align: 'center' as const },
  { title: pageText.value.operations, slotName: 'operations', width: isEnglish.value ? 320 : 270, fixed: 'right' as const, align: 'center' as const },
])

const pageStepModalTitle = computed(() => (
  isEdit.value ? pageText.value.editPageStep : pageText.value.addPageStep
))

const pageStepDrawerTitle = computed(() => (
  currentPageStep.value?.name
    ? `${pageText.value.stepDetails} - ${currentPageStep.value.name}`
    : pageText.value.stepDetails
))

const formatStatusLabel = (status: ExecutionStatus) => tl(STATUS_LABELS[status])

const formatDate = (dateStr: string) => dateStr ? new Date(dateStr).toLocaleString(isEnglish.value ? 'en-US' : 'zh-CN') : '-'

const fetchPages = async () => {
  if (!projectId.value) return
  try {
    const res = await pageApi.list({ project: projectId.value })
    pageOptions.value = extractListData<UiPage>(res)
  } catch {
    Message.error(pageText.value.fetchPageListFailed)
  }
}

// 表单中模块选择变化时，清空页面选择
const onFormModuleChange = () => {
  formData.page = undefined as unknown as number
}

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

const fetchPageSteps = async () => {
  if (!projectId.value) return
  loading.value = true
  try {
    const res = await pageStepsApi.list({
      project: projectId.value,
      page: filters.page,
      module: filters.module,
      search: filters.search || undefined,
    })
    const { items, count } = extractPaginationData(res)
    pageStepData.value = items
    pagination.total = count
  } catch {
    Message.error(pageText.value.fetchPageStepListFailed)
  } finally {
    loading.value = false
  }
}

const onSearch = () => {
  pagination.current = 1
  fetchPageSteps()
}

const onPageChange = (page: number) => {
  pagination.current = page
  fetchPageSteps()
}

const onPageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  fetchPageSteps()
}

const resetForm = () => {
  Object.assign(formData, { project: projectId.value || 0, page: undefined, module: undefined, name: '', description: '', run_flow: '', flow_data: {}, file_ids: [] })
  formRef.value?.clearValidate()
}

const showAddModal = async () => {
  isEdit.value = false
  resetForm()
  if (props.selectedModuleId) {
    formData.module = props.selectedModuleId
  }
  if (!moduleOptions.value.length) await fetchModules()
  if (!pageOptions.value.length) await fetchPages()
  modalVisible.value = true
}

const editPageStep = async (record: UiPageSteps) => {
  isEdit.value = true
  currentPageStep.value = record
  // 获取详情数据（包含完整字段）
  try {
    const res = await pageStepsApi.get(record.id)
    const detail = extractResponseData<UiPageSteps>(res)
    if (detail) {
      Object.assign(formData, {
        project: detail.project,
        page: detail.page,
        module: detail.module,
        name: detail.name,
        description: detail.description || '',
        run_flow: detail.run_flow || '',
        flow_data: detail.flow_data || {},
      })
    }
  } catch {
    // 降级使用列表数据
    Object.assign(formData, {
      project: record.project,
      page: record.page,
      module: record.module,
      name: record.name,
      description: record.description || '',
      run_flow: record.run_flow || '',
      flow_data: record.flow_data || {},
    })
  }
  if (!moduleOptions.value.length) await fetchModules()
  if (!pageOptions.value.length) await fetchPages()
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
    if (isEdit.value && currentPageStep.value) {
      await pageStepsApi.update(currentPageStep.value.id, formData)
      Message.success(pageText.value.updateSuccess)
    } else {
      await pageStepsApi.create(formData)
      Message.success(pageText.value.createSuccess)
    }
    done(true)
    fetchPageSteps()
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

const copyPageStep = async (record: UiPageSteps) => {
  try {
    loading.value = true
    await pageStepsApi.copy(record.id)
    Message.success(pageText.value.copySuccess)
    fetchPageSteps()
  } catch (error: unknown) {
    const err = error as { error?: string }
    Message.error(err?.error || pageText.value.copyFailed)
  } finally {
    loading.value = false
  }
}

const deletePageStep = async (record: UiPageSteps) => {
  try {
    await pageStepsApi.delete(record.id)
    Message.success(pageText.value.deleteSuccess)
    fetchPageSteps()
  } catch (error: unknown) {
    const err = error as { error?: string }
    Message.error(err?.error || pageText.value.deleteBlocked)
  }
}

const viewStepDetails = (record: UiPageSteps) => {
  currentPageStep.value = record
  detailDrawerVisible.value = true
}

watch(() => props.selectedModuleId, (newVal) => {
  filters.module = newVal
  pagination.current = 1
  fetchPageSteps()
})

// 监听项目变化，重新加载数据
watch(projectId, () => {
  if (projectId.value) {
    pagination.current = 1
    fetchPages()
    fetchModules()
    fetchPageSteps()
  }
}, { immediate: true })

const refresh = () => {
  fetchPages()
  fetchModules()
  fetchPageSteps()
}

defineExpose({ refresh })
</script>

<style scoped>
.page-step-list {
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
  flex-wrap: wrap;
  gap: 12px;
}

.action-buttons {
  display: flex;
  align-items: center;
  gap: 12px;
}
</style>
