<script setup lang="ts">
import { ref, watch, onMounted, computed } from 'vue'
import { Message, Modal, Spin } from '@arco-design/web-vue'
import { useAppI18n } from '@/composables/useAppI18n'
import { useProjectStore } from '@/store/projectStore'
import { useThemeStore } from '@/store/themeStore'
import { getFunctions, createFunction, updateFunction, deleteFunction, type Function, getFunctionDetail } from '../../services/functionService'
import { toArray } from '../../services/responseHelpers'
import FunctionList from './FunctionList.vue'
import FunctionDetail from './FunctionDetail.vue'
import FunctionForm from './FunctionForm.vue'

const projectStore = useProjectStore()
const themeStore = useThemeStore()
const { isEnglish } = useAppI18n()
const loading = ref(false)
const formLoading = ref(false)
const detailLoading = ref(false)
const functions = ref<Function[]>([])
const selectedFunction = ref<Function | null>(null)
const createVisible = ref(false)
const editVisible = ref(false)
const editingFunction = ref<Function | null>(null)
const globalLoading = ref(false)
const isDarkTheme = computed(() => themeStore.isBlack)
const pageText = computed(() => isEnglish.value
  ? {
      emptySelection: 'Please select a function on the left or create a new one',
    }
  : {
      emptySelection: '请选择左侧函数或新建函数',
    }
)

const toFunctionList = (results: unknown): Function[] => {
  return toArray<Function>(results)
}

// 获取函数列表
const fetchFunctions = async () => {
  if (!projectStore.currentProjectId) {
    functions.value = []
    return
  }

  try {
    loading.value = true
    const response = await getFunctions({
      project_id: Number(projectStore.currentProjectId),
      page_size: 100
    })
    functions.value = toFunctionList(response.data?.results ?? response.data)
  } catch (error) {
    console.error('获取函数列表失败:', error)
    Message.error('获取函数列表失败')
    functions.value = []
  } finally {
    loading.value = false
  }
}

// 监听项目变化
watch(
  () => projectStore.currentProjectId,
  (newId) => {
    if (newId) {
      fetchFunctions()
    } else {
      functions.value = []
    }
    selectedFunction.value = null
  }
)

// 获取函数详情
const fetchFunctionDetail = async (id: number) => {
  try {
    detailLoading.value = true
    const { data } = await getFunctionDetail(id)
    selectedFunction.value = {
      ...data,
      _loaded: true
    }
  } catch (error) {
    console.error('获取函数详情失败:', error)
    Message.error('获取函数详情失败')
  } finally {
    detailLoading.value = false
  }
}

// 处理函数选择
const handleFunctionSelect = async (func: Function) => {
  // 如果已经加载过详情，直接使用
  if (func._loaded) {
    selectedFunction.value = func
    return
  }
  
  // 否则请求详情
  try {
    globalLoading.value = true
    const { data } = await getFunctionDetail(func.id)
    selectedFunction.value = {
      ...data,
      _loaded: true
    }
  } catch (error) {
    console.error('获取函数详情失败:', error)
    Message.error('获取函数详情失败')
  } finally {
    globalLoading.value = false
  }
}

// 处理新建函数
const handleCreate = async (values: Partial<Function>) => {
  if (!projectStore.currentProjectId) {
    Message.warning('请先选择项目')
    return
  }

  try {
    formLoading.value = true
    const data = {
      ...values,
      project: Number(projectStore.currentProjectId)
    }

    const response = await createFunction(data)
    
    if (response.status === 'success') {
      Message.success('创建函数成功')
      createVisible.value = false
      fetchFunctions()
    } else if (response.errors) {
      const messages = []
      if (response.errors.name) messages.push(response.errors.name[0])
      if (response.errors.code) messages.push(response.errors.code[0])
      Message.error(messages.join('\n'))
    } else {
      Message.error(response.message || '创建函数失败')
    }
  } catch (error: any) {
    console.error('创建函数失败:', error)
    if (error.response?.data?.errors) {
      const errors = error.response.data.errors
      const messages = []
      if (errors.name) messages.push(errors.name[0])
      if (errors.code) messages.push(errors.code[0])
      Message.error(messages.join('\n'))
    } else {
      Message.error(error.response?.data?.message || '创建函数失败')
    }
  } finally {
    formLoading.value = false
  }
}

// 处理编辑函数
const handleEdit = async (values: Partial<Function>) => {
  if (!editingFunction.value) return

  try {
    formLoading.value = true
    const response = await updateFunction(editingFunction.value.id, values)
    
    if (response.status === 'success') {
      Message.success('更新函数成功')
      // 更新函数列表中的数据
      const updatedFunc = {
        ...response.data,
        _loaded: true
      }
      const index = functions.value.findIndex(f => f.id === updatedFunc.id)
      if (index !== -1) {
        functions.value[index] = updatedFunc
      }
      editVisible.value = false
    } else if (response.errors) {
      const messages = []
      if (response.errors.name) messages.push(response.errors.name[0])
      if (response.errors.code) messages.push(response.errors.code[0])
      Message.error(messages.join('\n'))
    } else {
      Message.error(response.message || '更新函数失败')
    }
  } catch (error: any) {
    console.error('更新函数失败:', error)
    if (error.response?.data?.errors) {
      const errors = error.response.data.errors
      const messages = []
      if (errors.name) messages.push(errors.name[0])
      if (errors.code) messages.push(errors.code[0])
      Message.error(messages.join('\n'))
    } else {
      Message.error(error.response?.data?.message || '更新函数失败')
    }
  } finally {
    formLoading.value = false
  }
}

// 处理删除函数
const handleDelete = async (func: Function) => {
  Modal.warning({
    title: '删除确认',
    content: `确定要删除函数"${func.name}"吗？`,
    okText: '确定',
    cancelText: '取消',
    onOk: async () => {
      try {
        const response = await deleteFunction(func.id)
        if (response.status === 'success') {
          Message.success('删除函数成功')
          // 如果当前选中的是被删除的函数，清空选中状态
          if (selectedFunction.value?.id === func.id) {
            selectedFunction.value = null
          }
          // 刷新列表
          fetchFunctions()
        } else {
          Message.error(response.message || '删除函数失败')
        }
      } catch (error) {
        console.error('删除函数失败:', error)
        Message.error('删除函数失败')
      }
    }
  })
}

// 处理编辑按钮点击
const handleEditClick = async (func: Function) => {
  // 先关闭当前编辑页面并显示加载状态
  editVisible.value = false
  editingFunction.value = null
  selectedFunction.value = null
  globalLoading.value = true

  try {
    // 如果已经加载过详情，直接进入编辑
    if (func._loaded) {
      editingFunction.value = func
      editVisible.value = true
      return
    }
    
    // 否则先加载详情
    formLoading.value = true
    const { data } = await getFunctionDetail(func.id)
    const loadedFunc = {
      ...data,
      _loaded: true
    }
    // 更新到函数列表中
    const index = functions.value.findIndex(f => f.id === func.id)
    if (index !== -1) {
      functions.value[index] = loadedFunc
    }
    editingFunction.value = loadedFunc
    editVisible.value = true
  } catch (error) {
    console.error('获取函数详情失败:', error)
    Message.error('获取函数详情失败')
  } finally {
    formLoading.value = false
    globalLoading.value = false
  }
}

// 处理新建按钮点击
const handleCreateClick = () => {
  selectedFunction.value = null
  editVisible.value = false
  editingFunction.value = null
  createVisible.value = true
}

onMounted(() => {
  if (projectStore.currentProjectId) {
    fetchFunctions()
  }
})
</script>

<template>
  <div class="functions-panel function-management h-full flex p-2 gap-2" :class="isDarkTheme ? 'functions-panel--dark' : 'functions-panel--light'">
    <!-- 左侧函数列表 -->
    <FunctionList
      :loading="loading"
      :functions="functions"
      :selected-function="selectedFunction"
      @select="handleFunctionSelect"
      @create="handleCreateClick"
      @edit="handleEditClick"
      @delete="handleDelete"
    />

    <!-- 右侧内容区域 -->
    <div class="flex-1 min-w-0">
      <a-spin :loading="globalLoading" dot class="!block h-full">
        <div class="function-main-shell rounded-lg h-full flex flex-col">
          <template v-if="selectedFunction">
            <FunctionDetail
              :loading="detailLoading"
              :function-data="selectedFunction"
              @close="selectedFunction = null"
              @edit="handleEditClick"
              @delete="handleDelete"
            />
          </template>
          <template v-else-if="createVisible">
            <FunctionForm
              mode="create"
              :loading="formLoading"
              @cancel="createVisible = false"
              @submit="handleCreate"
            />
          </template>
          <template v-else-if="editVisible && editingFunction">
            <FunctionForm
              mode="edit"
              :loading="formLoading"
              :initial-values="editingFunction"
              @cancel="editVisible = false"
              @submit="handleEdit"
            />
          </template>
          <template v-else>
            <!-- 欢迎页 -->
            <div class="h-full flex items-center justify-center">
              <a-empty :description="pageText.emptySelection" />
            </div>
          </template>
        </div>
      </a-spin>
    </div>
  </div>
</template>

<style lang="postcss" scoped>
.functions-panel {
  --func-shell-bg: color-mix(in srgb, var(--theme-card-bg) 92%, var(--theme-page-bg) 8%);
  --func-shell-border: rgba(148, 163, 184, 0.16);
  --func-shell-shadow: 0 14px 30px rgba(15, 23, 42, 0.08);
  --func-card-bg: rgba(255, 255, 255, 0.76);
  --func-card-border: rgba(148, 163, 184, 0.14);
  --func-input-bg: #ffffff;
  --func-input-border: rgba(148, 163, 184, 0.18);
  --func-input-hover-bg: color-mix(in srgb, var(--theme-card-bg) 88%, var(--theme-page-bg) 12%);
  --func-editor-bg: #ffffff;
  --func-editor-border: rgba(148, 163, 184, 0.18);
  --func-editor-scrollbar: rgba(148, 163, 184, 0.28);
  --func-text: var(--theme-text);
  --func-text-muted: var(--theme-text-secondary);
  --func-text-subtle: var(--theme-text-tertiary);
}

.functions-panel--dark {
  --func-shell-bg: rgba(31, 41, 55, 0.92);
  --func-shell-border: rgba(55, 65, 81, 0.72);
  --func-shell-shadow: 0 18px 34px rgba(2, 6, 23, 0.28);
  --func-card-bg: rgba(17, 24, 39, 0.55);
  --func-card-border: rgba(75, 85, 99, 0.32);
  --func-input-bg: rgba(17, 24, 39, 0.6);
  --func-input-border: rgba(55, 65, 81, 1);
  --func-input-hover-bg: rgba(17, 24, 39, 0.82);
  --func-editor-bg: rgba(17, 24, 39, 0.9);
  --func-editor-border: rgba(75, 85, 99, 0.5);
  --func-editor-scrollbar: rgba(75, 85, 99, 0.9);
}

.function-main-shell {
  background: var(--func-shell-bg);
  border: 1px solid var(--func-shell-border);
  box-shadow: var(--func-shell-shadow);
}

:deep(.arco-empty) {
  color: var(--func-text-subtle);
}

:deep(.arco-btn-primary) {
  background-color: rgb(59, 130, 246);
  border-color: rgb(59, 130, 246);
  
  &:hover {
    background-color: rgb(37, 99, 235);
    border-color: rgb(37, 99, 235);
  }
}

:deep(.arco-spin) {
  .arco-spin-mask {
    background-color: transparent;
  }
  .arco-spin-dot {
    border-color: rgb(59, 130, 246);
  }
}

:deep(.arco-form-item-label) {
  color: var(--func-text);
}

:deep(.arco-input-wrapper),
:deep(.arco-textarea-wrapper),
:deep(.arco-select-view) {
  background-color: var(--func-input-bg);
  border-color: var(--func-input-border);

  &:hover,
  &:focus-within {
    border-color: rgba(var(--theme-accent-rgb), 0.42) !important;
    background-color: var(--func-input-hover-bg);
  }
  
  input,
  textarea {
    color: var(--func-text);
    background-color: transparent;
    &::placeholder {
      color: var(--func-text-subtle);
    }
  }
}

:deep(.monaco-editor) {
  .margin,
  .monaco-editor-background {
    background-color: var(--func-editor-bg);
  }
}

:deep(.monaco-editor),
:deep(.monaco-editor .overflow-guard) {
  height: 100%;
  width: 100%;
}

:deep(.monaco-editor .monaco-scrollable-element) {
  height: 100%;
  width: 100%;
}

:deep(.monaco-editor .monaco-scrollable-element .monaco-editor-background) {
  background-color: var(--func-editor-bg);
}

:deep(.monaco-editor .monaco-scrollable-element .scrollbar) {
  background-color: transparent;
  
  .slider {
    background-color: var(--func-editor-scrollbar);
  }
}

:deep(.arco-form-item-content-wrapper) {
  flex: 1;
  min-height: 0;
  width: 100%;
}

:deep(.arco-form-item-content) {
  height: 100%;
  width: 100%;
}

.function-management {
  :deep(.flex-1) {
    padding-bottom: 1.5rem;
  }
}
</style> 
