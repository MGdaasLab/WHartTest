<template>
  <div class="element-list">
    <div class="element-header">
      <a-input-search
        v-model="searchKey"
        placeholder="搜索元素名称"
        allow-clear
        style="width: 200px"
        @search="fetchElements"
        @clear="fetchElements"
      />
      <div class="element-header-right">
        <a-popconfirm
          content="确定删除选中的元素？被页面步骤引用的元素将被跳过。"
          :disabled="!selectedRowKeys.length"
          @ok="handleBatchDelete"
        >
          <a-button status="danger" :disabled="!selectedRowKeys.length">
            <template #icon><icon-delete /></template>
            批量删除{{ selectedRowKeys.length ? `（${selectedRowKeys.length}）` : '' }}
          </a-button>
        </a-popconfirm>
        <a-button type="primary" @click="showAddModal">
          <template #icon><icon-plus /></template>
          新增元素
        </a-button>
      </div>
    </div>

    <div ref="tableWrapRef" class="element-table-wrap">
      <a-table
        v-model:selectedKeys="selectedRowKeys"
        :columns="columns"
        :data="elementData"
        :loading="loading"
        :pagination="false"
        size="small"
        :scroll="{ y: tableScrollY }"
        :row-selection="rowSelection"
        row-key="id"
      >
        <template #locator_type="{ record }">
          <a-tag>{{ record.locator_type }}</a-tag>
        </template>
        <template #name="{ record }">
          <a-tooltip :content="record.name" position="top">
            <div class="name-ellipsis">{{ record.name }}</div>
          </a-tooltip>
        </template>
        <template #locator_value="{ record }">
          <a-tooltip :content="record.locator_value" position="top">
            <div class="ellipsis-text">{{ record.locator_value }}</div>
          </a-tooltip>
        </template>
        <template #is_iframe="{ record }">
          <a-tag :color="record.is_iframe ? 'orange' : 'gray'">
            {{ record.is_iframe ? '是' : '否' }}
          </a-tag>
        </template>
        <template #operations="{ record }">
          <a-space :size="4">
            <a-button type="text" size="mini" @click="editElement(record)">
              <template #icon><icon-edit /></template>
            </a-button>
            <a-popconfirm content="确定删除该元素？若被页面步骤引用则无法删除，请先删除相关步骤。" @ok="deleteElement(record)">
              <a-button type="text" status="danger" size="mini">
                <template #icon><icon-delete /></template>
              </a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </a-table>
    </div>

    <!-- 新增/编辑弹窗 -->
    <a-modal
      v-model:visible="modalVisible"
      :title="isEdit ? '编辑元素' : '新增元素'"
      :ok-loading="submitting"
      width="600px"
      @before-ok="handleSubmit"
      @cancel="handleCancel"
    >
      <a-form ref="formRef" :model="formData" :rules="rules" layout="vertical">
        <a-form-item field="name" label="元素名称" required>
          <a-input v-model="formData.name" placeholder="请输入元素名称" :max-length="64" />
        </a-form-item>

        <a-divider>主定位</a-divider>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item field="locator_type" label="定位类型" required>
              <a-select v-model="formData.locator_type">
                <a-option v-for="opt in locatorTypes" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="locator_value" label="定位表达式" required>
              <a-textarea v-model="formData.locator_value" placeholder="请输入定位表达式" :auto-size="{ minRows: 1, maxRows: 3 }" />
            </a-form-item>
          </a-col>
          <a-col :span="4">
            <a-form-item field="locator_index" label="下标">
              <a-input-number v-model="formData.locator_index" :min="0" placeholder="可选" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider>备用定位 1（可选）</a-divider>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item field="locator_type_2" label="定位类型">
              <a-select v-model="formData.locator_type_2" allow-clear>
                <a-option v-for="opt in locatorTypes" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="locator_value_2" label="定位表达式">
              <a-textarea v-model="formData.locator_value_2" placeholder="可选" :auto-size="{ minRows: 1, maxRows: 3 }" />
            </a-form-item>
          </a-col>
          <a-col :span="4">
            <a-form-item field="locator_index_2" label="下标">
              <a-input-number v-model="formData.locator_index_2" :min="0" placeholder="可选" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider>备用定位 2（可选）</a-divider>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item field="locator_type_3" label="定位类型">
              <a-select v-model="formData.locator_type_3" allow-clear>
                <a-option v-for="opt in locatorTypes" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="locator_value_3" label="定位表达式">
              <a-textarea v-model="formData.locator_value_3" placeholder="可选" :auto-size="{ minRows: 1, maxRows: 3 }" />
            </a-form-item>
          </a-col>
          <a-col :span="4">
            <a-form-item field="locator_index_3" label="下标">
              <a-input-number v-model="formData.locator_index_3" :min="0" placeholder="可选" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider>配置</a-divider>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item field="wait_time" label="等待时间（秒）">
              <a-input-number v-model="formData.wait_time" :min="1" :max="120" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item field="is_iframe" label="在 iframe 中">
              <a-switch v-model="formData.is_iframe" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item v-if="formData.is_iframe" field="iframe_locator" label="iframe 定位表达式">
          <a-textarea v-model="formData.iframe_locator" placeholder="请输入 iframe 定位表达式" :auto-size="{ minRows: 1, maxRows: 3 }" />
        </a-form-item>
        <a-form-item field="description" label="描述">
          <a-textarea v-model="formData.description" placeholder="可选描述" :auto-size="{ minRows: 2 }" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconPlus, IconEdit, IconDelete } from '@arco-design/web-vue/es/icon'
import { elementApi } from '../api'
import type { UiElement, UiElementForm, UiPage, LocatorType } from '../types'
import { extractListData } from '../types'

const props = defineProps<{ page: UiPage }>()

const loading = ref(false)
const submitting = ref(false)
const elementData = ref<UiElement[]>([])
const modalVisible = ref(false)
const isEdit = ref(false)
const currentElement = ref<UiElement | null>(null)
const formRef = ref()
const searchKey = ref('')
const tableWrapRef = ref<HTMLDivElement | null>(null)
const tableScrollY = ref(400)
let resizeObserver: ResizeObserver | null = null

function measureTableHeight() {
  const el = tableWrapRef.value
  if (!el) return
  // 容器高度 - 表头(~40px)，最小 240
  tableScrollY.value = Math.max(240, el.clientHeight - 40)
}

onMounted(() => {
  nextTick(() => {
    measureTableHeight()
    if (typeof ResizeObserver !== 'undefined' && tableWrapRef.value) {
      resizeObserver = new ResizeObserver(() => measureTableHeight())
      resizeObserver.observe(tableWrapRef.value)
    }
  })
})

onUnmounted(() => {
  resizeObserver?.disconnect()
})
const selectedRowKeys = ref<(string | number)[]>([])
const rowSelection = { showCheckedAll: true }

const locatorTypes = [
  { value: 'xpath', label: 'XPath' },
  { value: 'css', label: 'CSS' },
  { value: 'text', label: '文本' },
  { value: 'role', label: 'Role' },
  { value: 'label', label: 'Label' },
  { value: 'placeholder', label: 'Placeholder' },
  { value: 'test_id', label: 'Test ID' },
  { value: 'id', label: 'ID' },
  { value: 'name', label: 'Name' },
]

const formData = reactive<UiElementForm>({
  page: 0,
  name: '',
  locator_type: 'xpath' as LocatorType,
  locator_value: '',
  locator_index: undefined,
  locator_type_2: undefined,
  locator_value_2: undefined,
  locator_index_2: undefined,
  locator_type_3: undefined,
  locator_value_3: undefined,
  locator_index_3: undefined,
  wait_time: 0,
  is_iframe: false,
  iframe_locator: undefined,
  description: undefined,
})

const rules = {
  name: [{ required: true, message: '请输入元素名称' }],
  locator_type: [{ required: true, message: '请选择定位类型' }],
  locator_value: [{ required: true, message: '请输入定位表达式' }],
}

const columns = [
  { title: '名称', dataIndex: 'name', width: 120, align: 'center' as const },
  { title: '定位类型', slotName: 'locator_type', width: 90, align: 'center' as const },
  { title: '定位表达式', slotName: 'locator_value', width: 200, align: 'center' as const },
  { title: '等待(秒)', dataIndex: 'wait_time', width: 80, align: 'center' as const },
  { title: 'iframe', slotName: 'is_iframe', width: 70, align: 'center' as const },
  { title: '操作', slotName: 'operations', width: 120, fixed: 'right' as const, align: 'center' as const },
]

const fetchElements = async () => {
  loading.value = true
  try {
    const res = await elementApi.list({ page: props.page.id, search: searchKey.value || undefined })
    elementData.value = extractListData<UiElement>(res)
  } catch {
    Message.error('获取元素列表失败')
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  Object.assign(formData, {
    page: props.page.id,
    name: '',
    locator_type: 'xpath',
    locator_value: '',
    locator_index: undefined,
    locator_type_2: undefined,
    locator_value_2: undefined,
    locator_index_2: undefined,
    locator_type_3: undefined,
    locator_value_3: undefined,
    locator_index_3: undefined,
    wait_time: 0,
    is_iframe: false,
    iframe_locator: undefined,
    description: undefined,
  })
  formRef.value?.clearValidate()
}

const showAddModal = () => {
  isEdit.value = false
  resetForm()
  modalVisible.value = true
}

const editElement = (record: UiElement) => {
  isEdit.value = true
  currentElement.value = record
  Object.assign(formData, {
    page: record.page,
    name: record.name,
    locator_type: record.locator_type,
    locator_value: record.locator_value,
    locator_index: record.locator_index,
    locator_type_2: record.locator_type_2,
    locator_value_2: record.locator_value_2,
    locator_index_2: record.locator_index_2,
    locator_type_3: record.locator_type_3,
    locator_value_3: record.locator_value_3,
    locator_index_3: record.locator_index_3,
    wait_time: record.wait_time,
    is_iframe: record.is_iframe,
    iframe_locator: record.iframe_locator,
    description: record.description,
  })
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
    if (isEdit.value && currentElement.value) {
      await elementApi.update(currentElement.value.id, formData)
      Message.success('更新成功')
    } else {
      await elementApi.create(formData)
      Message.success('创建成功')
    }
    done(true)
    fetchElements()
  } catch (error: unknown) {
    // 解析后端返回的验证错误
    const err = error as { errors?: Record<string, string[]>; error?: string }
    const errors = err?.errors
    if (errors && typeof errors === 'object' && !('error' in errors) && !('message' in errors)) {
      // 字段验证错误格式: { name: ['xxx'], locator_value: ['xxx'] }
      // 字段名到中文名称的映射
      const fieldNameMap: Record<string, string> = {
        name: '元素名称',
        locator_value: '元素表达式',
        locator_type: '定位类型',
        locator_value_2: '备用定位表达式1',
        locator_value_3: '备用定位表达式2',
        wait_time: '等待时间',
        is_iframe: 'iframe设置',
        iframe_locator: 'iframe定位表达式',
        description: '描述'
      }
      
      const messages = Object.entries(errors)
        .map(([field, msgs]) => {
          const chineseFieldName = fieldNameMap[field] || field
          return `${chineseFieldName}: ${Array.isArray(msgs) ? msgs.join(', ') : msgs}`
        })
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

const handleBatchDelete = async () => {
  if (!selectedRowKeys.value.length) return
  try {
    const res = await elementApi.batchDelete(selectedRowKeys.value.map(Number))
    const data = (res as any)?.data
    const deleted = data?.deleted ?? selectedRowKeys.value.length
    Message.success(`删除成功（${deleted} 个）`)
    selectedRowKeys.value = []
    fetchElements()
  } catch (error: unknown) {
    const err = error as { error?: string }
    Message.error(err?.error || '批量删除失败')
  }
}

const deleteElement = async (record: UiElement) => {
  try {
    await elementApi.delete(record.id)
    Message.success('删除成功')
    fetchElements()
  } catch (error: unknown) {
    const err = error as { error?: string }
    Message.error(err?.error || '删除失败')
  }
}

watch(() => props.page, fetchElements, { immediate: true })
</script>

<style scoped>
.element-list {
  padding: 8px 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.element-table-wrap {
  flex: 1;
  min-height: 280px;
  overflow: hidden;
}
.element-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.element-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ellipsis-text {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.name-ellipsis {
  max-width: 116px;
  margin: 0 auto;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
