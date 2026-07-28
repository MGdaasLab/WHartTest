<template>
  <div class="env-config-list">
    <div class="page-header">
      <div class="search-box">
        <a-select
          v-model="filters.browser"
          placeholder="浏览器"
          allow-clear
          style="width: 120px; margin-right: 12px"
          @change="onSearch"
        >
          <a-option value="chromium">Chromium</a-option>
          <a-option value="firefox">Firefox</a-option>
          <a-option value="webkit">WebKit</a-option>
        </a-select>
        <a-input-search
          v-model="filters.search"
          placeholder="搜索环境名称"
          allow-clear
          style="width: 200px"
          @search="onSearch"
          @clear="onSearch"
        />
      </div>
      <div class="action-buttons">
        <a-button type="primary" @click="showAddModal">
          <template #icon><icon-plus /></template>
          新增环境
        </a-button>
      </div>
    </div>

    <a-table
      :columns="columns"
      :data="envConfigData"
      :pagination="pagination"
      :loading="loading"
      :scroll="{ x: 900 }"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
    >
      <template #browser="{ record }">
        <a-tag :color="browserColors[record.browser as BrowserType]">{{ record.browser }}</a-tag>
      </template>
      <template #headless="{ record }">
        <a-tag :color="record.headless ? 'green' : 'orange'">{{ record.headless ? '无头' : '有头' }}</a-tag>
      </template>
      <template #is_default="{ record }">
        <a-tag v-if="record.is_default" color="arcoblue">默认</a-tag>
        <span v-else>-</span>
      </template>
      <template #operations="{ record }">
        <a-space :size="4">
          <a-button v-if="!record.is_default" type="text" size="mini" @click="setDefault(record)">
            <template #icon><icon-check /></template>
            设为默认
          </a-button>
          <a-button type="text" size="mini" @click="editConfig(record)">
            <template #icon><icon-edit /></template>
            编辑
          </a-button>
          <a-popconfirm content="确定删除？" @ok="deleteConfig(record)">
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
      :title="isEdit ? '编辑环境配置' : '新增环境配置'"
      :ok-loading="submitting"
      width="600px"
      @before-ok="handleSubmit"
      @cancel="handleCancel"
    >
      <a-form ref="formRef" :model="formData" :rules="rules" layout="vertical">
        <a-form-item field="name" label="环境名称" required>
          <a-input v-model="formData.name" placeholder="如：开发环境、测试环境" :max-length="64" />
        </a-form-item>
        <a-form-item field="base_url" label="基础 URL">
          <a-input v-model="formData.base_url" placeholder="如：http://localhost:3000" />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item field="browser" label="浏览器">
              <a-select v-model="formData.browser">
                <a-option value="chromium">Chromium</a-option>
                <a-option value="firefox">Firefox</a-option>
                <a-option value="webkit">WebKit</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item field="headless" label="无头模式">
              <a-switch v-model="formData.headless" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item field="is_default" label="设为默认">
              <a-switch v-model="formData.is_default" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item field="viewport_width" label="视口宽度">
              <a-input-number v-model="formData.viewport_width" :min="320" :max="3840" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item field="viewport_height" label="视口高度">
              <a-input-number v-model="formData.viewport_height" :min="240" :max="2160" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item field="timeout" label="超时(ms)">
              <a-input-number v-model="formData.timeout" :min="1000" :max="120000" :step="1000" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-divider>数据库配置</a-divider>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item field="db_c_status" label="启用新增">
              <a-switch v-model="formData.db_c_status" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item field="db_rud_status" label="启用查改删">
              <a-switch v-model="formData.db_rud_status" />
            </a-form-item>
          </a-col>
        </a-row>
        <div v-if="formData.db_c_status || formData.db_rud_status">
          <a-form-item field="db_type" label="数据库类型">
            <a-select v-model="formData.db_type" placeholder="请选择数据库类型">
              <a-option value="mysql">MySQL</a-option>
            </a-select>
          </a-form-item>

          <!-- MySQL 配置 -->
          <div v-if="formData.db_type === 'mysql'" class="mysql-config-form">
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="主机地址">
                  <a-input v-model="mysqlConfig.host" placeholder="localhost 或 127.0.0.1" />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="端口">
                  <a-input-number v-model="mysqlConfig.port" :min="1" :max="65535" placeholder="3306" style="width: 100%" />
                </a-form-item>
              </a-col>
            </a-row>
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="用户名">
                  <a-input v-model="mysqlConfig.user" placeholder="数据库用户名" />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="密码">
                  <a-input-password v-model="mysqlConfig.password" placeholder="数据库密码" />
                </a-form-item>
              </a-col>
            </a-row>
            <a-form-item label="数据库">
              <a-input v-model="mysqlConfig.database" placeholder="要连接的数据库名称" />
            </a-form-item>
          </div>
        </div>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconPlus, IconEdit, IconDelete, IconCheck } from '@arco-design/web-vue/es/icon'
import { useProjectStore } from '@/store/projectStore'
import { envConfigApi } from '../api'
import type { UiEnvironmentConfig, UiEnvironmentConfigForm, BrowserType } from '../types'
import { extractPaginationData } from '../types'

const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)

const loading = ref(false)
const submitting = ref(false)
const envConfigData = ref<UiEnvironmentConfig[]>([])
const modalVisible = ref(false)
const isEdit = ref(false)
const currentConfig = ref<UiEnvironmentConfig | null>(null)
const formRef = ref()

// MySQL 配置表单
const mysqlConfig = reactive({
  host: '',
  port: 3306,
  user: '',
  password: '',
  database: '',
})


const filters = reactive({ browser: undefined as string | undefined, search: '' })
const pagination = reactive({ current: 1, pageSize: 10, total: 0, showTotal: true, showPageSize: true })

const formData = reactive<UiEnvironmentConfigForm>({
  project: 0,
  name: '',
  base_url: '',
  browser: 'chromium',
  headless: true,
  viewport_width: 1280,
  viewport_height: 720,
  timeout: 30000,
  db_c_status: false,
  db_rud_status: false,
  db_type: 'mysql',
  mysql_config: {},
  extra_config: {},
  is_default: false,
})

const rules = {
  name: [{ required: true, message: '请输入环境名称' }],
}

const browserColors: Record<BrowserType, string> = { chromium: 'arcoblue', firefox: 'orange', webkit: 'purple' }

const columns = [
  { title: 'ID', dataIndex: 'id', width: 70, align: 'center' as const },
  { title: '环境名称', dataIndex: 'name', width: 150, align: 'center' as const },
  { title: '基础 URL', dataIndex: 'base_url', ellipsis: true, tooltip: true, width: 200, align: 'center' as const },
  { title: '浏览器', slotName: 'browser', width: 100, align: 'center' as const },
  { title: '模式', slotName: 'headless', width: 80, align: 'center' as const },
  { title: '默认', slotName: 'is_default', width: 70, align: 'center' as const },
  { title: '创建者', dataIndex: 'creator_name', width: 100, align: 'center' as const },
  { title: '操作', slotName: 'operations', width: 200, fixed: 'right' as const, align: 'center' as const },
]

const fetchData = async () => {
  if (!projectId.value) return
  loading.value = true
  try {
    const res = await envConfigApi.list({
      project: projectId.value,
      browser: filters.browser,
      search: filters.search || undefined,
    })
    const { items, count } = extractPaginationData(res)
    envConfigData.value = items
    pagination.total = count
  } catch {
    Message.error('获取环境配置失败')
  } finally {
    loading.value = false
  }
}

const onSearch = () => {
  pagination.current = 1
  fetchData()
}

const onPageChange = (page: number) => {
  pagination.current = page
  fetchData()
}

const onPageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
  fetchData()
}

const resetForm = () => {
  Object.assign(formData, {
    project: projectId.value || 0,
    name: '',
    base_url: '',
    browser: 'chromium',
    headless: true,
    viewport_width: 1280,
    viewport_height: 720,
    timeout: 30000,
    db_c_status: false,
    db_rud_status: false,
    db_type: 'mysql',
    mysql_config: {},
    extra_config: {},
    is_default: false,
  })
  Object.assign(mysqlConfig, { host: '', port: 3306, user: '', password: '', database: '' })
  formRef.value?.clearValidate()
}

const showAddModal = () => {
  isEdit.value = false
  resetForm()
  modalVisible.value = true
}

const editConfig = (record: UiEnvironmentConfig) => {
  isEdit.value = true
  currentConfig.value = record
  Object.assign(formData, {
    project: record.project,
    name: record.name,
    base_url: record.base_url || '',
    browser: record.browser,
    headless: record.headless,
    viewport_width: record.viewport_width,
    viewport_height: record.viewport_height,
    timeout: record.timeout,
    db_c_status: record.db_c_status,
    db_rud_status: record.db_rud_status,
    db_type: record.db_type || 'mysql',
    mysql_config: record.mysql_config || {},
    extra_config: record.extra_config || {},
    is_default: record.is_default,
  })
  const cfg = record.mysql_config || {}
  Object.assign(mysqlConfig, {
    host: cfg.host || '',
    port: cfg.port || 3306,
    user: cfg.user || '',
    password: cfg.password || '',
    database: cfg.database || '',
  })
  modalVisible.value = true
}

const buildMysqlConfig = () => {
  if (!formData.db_c_status && !formData.db_rud_status) return {}
  if (formData.db_type !== 'mysql') return {}
  const cfg: Record<string, unknown> = {}
  if (mysqlConfig.host) cfg.host = mysqlConfig.host
  if (mysqlConfig.port) cfg.port = mysqlConfig.port
  if (mysqlConfig.user) cfg.user = mysqlConfig.user
  if (mysqlConfig.password) cfg.password = mysqlConfig.password
  if (mysqlConfig.database) cfg.database = mysqlConfig.database
  return cfg
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
    const data = {
      ...formData,
      mysql_config: buildMysqlConfig(),
    }
    if (isEdit.value && currentConfig.value) {
      await envConfigApi.update(currentConfig.value.id, data)
      Message.success('更新成功')
    } else {
      await envConfigApi.create(data)
      Message.success('创建成功')
    }
    done(true)
    fetchData()
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

const deleteConfig = async (record: UiEnvironmentConfig) => {
  try {
    await envConfigApi.delete(record.id)
    Message.success('删除成功')
    fetchData()
  } catch {
    Message.error('删除失败')
  }
}

const setDefault = async (record: UiEnvironmentConfig) => {
  try {
    await envConfigApi.update(record.id, { is_default: true })
    Message.success('已设为默认')
    fetchData()
  } catch {
    Message.error('设置失败')
  }
}

const refresh = () => fetchData()

defineExpose({ refresh })

// 监听项目变化，重新加载数据
watch(projectId, () => {
  if (projectId.value) {
    pagination.current = 1
    fetchData()
  }
}, { immediate: true })
</script>

<style scoped>
.env-config-list {
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
.mysql-config-form {
  background: var(--color-fill-2);
  padding: 16px;
  border-radius: 6px;
  margin-top: 8px;
}
.mysql-config-form :deep(.arco-form-item) {
  margin-bottom: 16px;
}
.mysql-config-form :deep(.arco-form-item:last-child) {
  margin-bottom: 0;
}
.mysql-config-form :deep(.arco-form-item-label-col) {
  flex: 0 0 70px;
}
</style>
