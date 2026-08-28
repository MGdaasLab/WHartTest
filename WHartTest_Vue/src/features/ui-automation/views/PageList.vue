<template>
  <div class="page-management">
    <div class="page-header">
      <div class="search-box">
        <a-select
          v-model="filters.module"
          placeholder="选择模块"
          allow-clear
          style="width: 180px; margin-right: 12px"
          @change="onSearch"
        >
          <a-option v-for="mod in moduleOptions" :key="mod.id" :value="mod.id">
            {{ mod.name }}
          </a-option>
        </a-select>
        <a-input-search
          v-model="filters.search"
          placeholder="搜索页面名称/URL"
          allow-clear
          style="width: 260px"
          @search="onSearch"
          @clear="onSearch"
        />
      </div>
      <div class="action-buttons">
        <a-button type="primary" @click="showAddModal">
          <template #icon><icon-plus /></template>
          新增页面
        </a-button>
      </div>
    </div>

    <a-table
      :columns="columns"
      :data="pageData"
      :pagination="pagination"
      :loading="loading"
      :scroll="{ x: 900 }"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
    >
      <template #module_name="{ record }">
        <a-tag color="arcoblue">{{ record.module_name }}</a-tag>
      </template>
      <template #url="{ record }">
        <a-tooltip v-if="record.url" :content="record.url" position="top">
          <div class="ellipsis-text url-text">{{ record.url }}</div>
        </a-tooltip>
        <span v-else class="empty-text">-</span>
      </template>
      <template #element_count="{ record }">
        <a-tag color="green">{{ record.element_count || 0 }}</a-tag>
      </template>
      <template #created_at="{ record }">
        {{ formatDate(record.created_at) }}
      </template>
      <template #operations="{ record }">
        <a-space :size="4">
          <a-button type="text" size="mini" @click="viewElements(record)">
            <template #icon><icon-eye /></template>
            元素
          </a-button>
          <a-button type="text" size="mini" @click="editPage(record)">
            <template #icon><icon-edit /></template>
            编辑
          </a-button>
          <a-button type="text" size="mini" @click="copyPage(record)">
            <template #icon><icon-copy /></template>
            复制
          </a-button>
          <a-popconfirm
            content="确定删除该页面？若页面下存在步骤或元素被步骤引用，将无法删除。"
            @ok="deletePage(record)"
          >
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
      :title="isEdit ? '编辑页面' : '新增页面'"
      :ok-loading="submitting"
      @before-ok="handleSubmit"
      @cancel="handleCancel"
    >
      <a-form ref="formRef" :model="formData" :rules="rules" layout="vertical">
        <a-form-item field="module" label="所属模块" required>
          <a-select v-model="formData.module" placeholder="请选择模块">
            <a-option v-for="mod in moduleOptions" :key="mod.id" :value="mod.id">
              {{ mod.name }}
            </a-option>
          </a-select>
        </a-form-item>
        <a-form-item field="name" label="页面名称" required>
          <a-input v-model="formData.name" placeholder="请输入页面名称" :max-length="64" />
        </a-form-item>
        <a-form-item field="url" label="页面 URL">
          <a-textarea v-model="formData.url" placeholder="请输入页面 URL" :auto-size="{ minRows: 2 }" />
        </a-form-item>
        <a-form-item field="description" label="描述">
          <a-textarea v-model="formData.description" placeholder="请输入描述" :auto-size="{ minRows: 2 }" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 元素管理抽屉 -->
    <a-drawer
      v-model:visible="elementDrawerVisible"
      :title="`元素管理 - ${currentPage?.name || ''}`"
      :width="800"
      :footer="false"
    >
      <ElementList v-if="currentPage" :page="currentPage" />
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconPlus, IconEdit, IconDelete, IconEye, IconCopy } from '@arco-design/web-vue/es/icon'
import { useProjectStore } from '@/store/projectStore'
import { pageApi, moduleApi } from '../api'
import type { UiPage, UiPageForm, UiModule } from '../types'
import { extractPaginationData, extractResponseData } from '../types'
import ElementList from './ElementList.vue'

const props = defineProps<{
  selectedModuleId?: number
}>()

const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)

const loading = ref(false)
const submitting = ref(false)
const pageData = ref<UiPage[]>([])
const moduleOptions = ref<UiModule[]>([])
const modalVisible = ref(false)
const elementDrawerVisible = ref(false)
const isEdit = ref(false)
const currentPage = ref<UiPage | null>(null)
const formRef = ref()

const filters = reactive({ module: undefined as number | undefined, search: '' })
const pagination = reactive({ current: 1, pageSize: 10, total: 0, showTotal: true, showPageSize: true })

const formData = reactive<UiPageForm>({
  project: 0,
  module: undefined as unknown as number,
  name: '',
  url: '',
  description: '',
})

const rules = {
  module: [{ required: true, message: '请选择模块' }],
  name: [{ required: true, message: '请输入页面名称' }],
}

const columns = [
  { title: 'ID', dataIndex: 'id', width: 70, align: 'center' as const },
  { title: '模块', slotName: 'module_name', width: 120, align: 'center' as const },
  { title: '页面名称', dataIndex: 'name', ellipsis: true, tooltip: true, width: 150, align: 'center' as const },
  { title: 'URL', slotName: 'url', width: 200, align: 'center' as const },
  { title: '元素数', slotName: 'element_count', width: 80, align: 'center' as const },
  { title: '创建者', dataIndex: 'creator_name', width: 100, align: 'center' as const },
  { title: '创建时间', slotName: 'created_at', width: 160, align: 'center' as const },
  { title: '操作', slotName: 'operations', width: 270, fixed: 'right' as const, align: 'center' as const },
]

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
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
  } catch (e) {
    console.error('获取模块列表失败:', e)
    Message.error('获取模块列表失败')
  }
}

const fetchPages = async () => {
  if (!projectId.value) return
  loading.value = true
  try {
    const res = await pageApi.list({
      project: projectId.value,
      module: filters.module,
      search: filters.search || undefined,
    })
    const { items, count } = extractPaginationData(res)
    pageData.value = items
    pagination.total = count
  } catch {
    Message.error('获取页面列表失败')
  } finally {
    loading.value = false
  }
}

const onSearch = () => {
  pagination.current = 1
  fetchPages()
}

const onPageChange = (page: number) => {
  pagination.current = page
  fetchPages()
}

const onPageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  fetchPages()
}

const resetForm = () => {
  Object.assign(formData, { project: projectId.value || 0, module: undefined, name: '', url: '', description: '' })
  formRef.value?.clearValidate()
}

const showAddModal = async () => {
  isEdit.value = false
  resetForm()
  // 如果左侧选择了模块，自动带入
  if (props.selectedModuleId) {
    formData.module = props.selectedModuleId
  }
  if (!moduleOptions.value.length) {
    await fetchModules()
  }
  modalVisible.value = true
}

const editPage = async (record: UiPage) => {
  isEdit.value = true
  Object.assign(formData, {
    project: record.project,
    module: record.module,
    name: record.name,
    url: record.url || '',
    description: record.description || '',
  })
  currentPage.value = record
  if (!moduleOptions.value.length) {
    await fetchModules()
  }
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
    if (isEdit.value && currentPage.value) {
      await pageApi.update(currentPage.value.id, formData)
      Message.success('更新成功')
    } else {
      await pageApi.create(formData)
      Message.success('创建成功')
    }
    done(true)
    fetchPages()
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

const copyPage = async (record: UiPage) => {
  try {
    loading.value = true
    await pageApi.copy(record.id)
    Message.success('复制成功')
    fetchPages()
  } catch (error: unknown) {
    const err = error as { error?: string }
    Message.error(err?.error || '复制失败')
  } finally {
    loading.value = false
  }
}

const deletePage = async (record: UiPage) => {
  try {
    await pageApi.delete(record.id)
    Message.success('删除成功')
    fetchPages()
  } catch (error: unknown) {
    const err = error as { error?: string }
    Message.error(err?.error || '存在关联，无法删除。请先解除关联')
  }
}

const viewElements = (record: UiPage) => {
  currentPage.value = record
  elementDrawerVisible.value = true
}

watch(() => props.selectedModuleId, (newVal) => {
  filters.module = newVal
  pagination.current = 1
  fetchPages()
})

// 监听项目变化，重新加载数据
watch(projectId, () => {
  if (projectId.value) {
    pagination.current = 1
    fetchModules()
    fetchPages()
  }
}, { immediate: true })

const refresh = () => {
  fetchModules()
  fetchPages()
}

defineExpose({ refresh })
</script>

<style scoped>
.page-management {
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
.ellipsis-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.url-text {
  max-width: 180px;
  color: #1890ff;
}
.empty-text {
  color: #c0c4cc;
}
</style>
