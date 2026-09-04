<template>
  <div class="env-config-list">
    <div class="page-header">
      <div class="search-box">
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
      <template #is_default="{ record }">
        <a-tag v-if="record.is_default" color="arcoblue">默认</a-tag>
        <span v-else>-</span>
      </template>
      <template #auth_state="{ record }">
        <a-tag v-if="record.auth_state_active" color="green">有登录态</a-tag>
        <a-tag v-else color="gray">未配置</a-tag>
      </template>
      <template #operations="{ record }">
        <a-space :size="4">
          <a-button v-if="!record.is_default" type="text" size="mini" @click="setDefault(record)">
            <template #icon><icon-check /></template>
            设为默认
          </a-button>
          <a-button type="text" size="mini" @click="openAuthModal(record)">
            <template #icon><icon-safe /></template>
            登录态
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

    <!-- 环境登录态管理弹窗 -->
    <a-modal
      v-model:visible="authModalVisible"
      title="环境登录态管理"
      width="680px"
      :footer="false"
      @cancel="authModalVisible = false"
    >
      <a-alert type="info" style="margin-bottom: 12px">
        执行任务时执行器会自动按环境注入此登录态（cookies + localStorage，兼容 Cookie/Session 与
        JWT 系统），无需登录页与验证码。点「录制登录态」在录制窗口中完成登录后保存即可捕获。
      </a-alert>
      <div class="auth-toolbar">
        <a-button type="primary" size="mini" @click="authCaptureVisible = true">
          <template #icon><icon-safe /></template>
          录制登录态
        </a-button>
        <span class="auth-tip">
          点击「录制登录态」，在录制窗口中登录目标系统并点「保存登录态」即可捕获。
          登录态仅在录制/编排时显式选择绑定后才会注入。
        </span>
      </div>
      <a-table
        :columns="authColumns"
        :data="authStates"
        :pagination="false"
        :loading="authLoading"
      >
        <template #credentials="{ record }">
          <span class="auth-cred-cell" :title="credentialSummary(record)">{{ credentialSummary(record) }}</span>
        </template>
        <template #auth_expiry="{ record }">
          <span :class="{ 'auth-expired': isAuthExpired(record) }">{{ authExpiryText(record) }}</span>
        </template>
        <template #updated_at="{ record }">
          <span>{{ formatAuthTime(record.updated_at) }}</span>
        </template>
        <template #auth_operations="{ record }">
          <div class="auth-ops-row">
            <a-button type="text" size="mini" @click="openEditAuth(record)">
              <template #icon><icon-edit /></template>
              编辑
            </a-button>
            <a-popconfirm content="确定删除该登录态？" @ok="deleteAuthState(record)">
              <a-button type="text" status="danger" size="mini">
                <template #icon><icon-delete /></template>
                删除
              </a-button>
            </a-popconfirm>
          </div>
        </template>
      </a-table>
    </a-modal>

    <!-- 编辑登录态名称 -->
    <a-modal v-model:visible="authEditVisible" title="编辑登录态名称" :footer="false" width="420px">
      <a-form layout="vertical">
        <a-form-item label="登录态名称">
          <a-input v-model="authEditName" :max-length="64" allow-clear @press-enter="submitEditAuth" />
        </a-form-item>
      </a-form>
      <div class="auth-edit-actions">
        <a-button @click="authEditVisible = false">取消</a-button>
        <a-button type="primary" :loading="authEditing" @click="submitEditAuth">保存</a-button>
      </div>
    </a-modal>

    <!-- 录制登录态（登录态采集录制窗口：仅保留保存登录态） -->
    <AuthCaptureModal
      v-model:visible="authCaptureVisible"
      :env="currentAuthEnv"
      @saved="onAuthRecorded"
    />

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
        <a-form-item field="is_default" label="设为默认">
          <a-switch v-model="formData.is_default" />
        </a-form-item>
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
import { IconPlus, IconEdit, IconDelete, IconCheck, IconSafe } from '@arco-design/web-vue/es/icon'
import { useProjectStore } from '@/store/projectStore'
import { envConfigApi, authStateApi } from '../api'
import AuthCaptureModal from '../components/AuthCaptureModal.vue'
import type { UiEnvironmentConfig, UiEnvironmentConfigForm, UiAuthState } from '../types'
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

const filters = reactive({ search: '' })
const pagination = reactive({ current: 1, pageSize: 10, total: 0, showTotal: true, showPageSize: true })

const formData = reactive<UiEnvironmentConfigForm>({
  project: 0,
  name: '',
  base_url: '',
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

const columns = [
  { title: 'ID', dataIndex: 'id', width: 70, align: 'center' as const },
  { title: '环境名称', dataIndex: 'name', width: 150, align: 'center' as const },
  { title: '基础 URL', dataIndex: 'base_url', ellipsis: true, tooltip: true, width: 200, align: 'center' as const },
  { title: '默认', slotName: 'is_default', width: 70, align: 'center' as const },
  { title: '登录态', slotName: 'auth_state', width: 90, align: 'center' as const },
  { title: '创建者', dataIndex: 'creator_name', width: 100, align: 'center' as const },
  { title: '操作', slotName: 'operations', width: 250, fixed: 'right' as const, align: 'center' as const },
]

// ---------------- 环境登录态管理 ----------------
const authModalVisible = ref(false)
const authLoading = ref(false)
const currentAuthEnv = ref<UiEnvironmentConfig | null>(null)
const authStates = ref<UiAuthState[]>([])
// 录制登录态（登录态采集录制窗口）
const authCaptureVisible = ref(false)

const onAuthRecorded = () => {
  authCaptureVisible.value = false
  fetchAuthStates()
  fetchData()
}

const authColumns = [
  { title: '名称', dataIndex: 'name', ellipsis: true, tooltip: true, width: 140, align: 'center' as const },
  { title: '凭据摘要', slotName: 'credentials', width: 130, align: 'center' as const },
  { title: '过期时间', slotName: 'auth_expiry', width: 140, align: 'center' as const },
  { title: '更新时间', slotName: 'updated_at', width: 140, align: 'center' as const },
  { title: '操作', slotName: 'auth_operations', width: 140, align: 'center' as const },
]

/** ISO 时间串 → 本地 'YYYY-MM-DD HH:mm:ss' */
const formatAuthTime = (value?: string | null): string => {
  if (!value) return '-'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

/** 登录态最短 cookie 过期时间：字符显示 + 过期判断（会话型 cookie 视为长期有效） */
const authExpiryText = (record: UiAuthState): string => {
  const state = record.state_json || {}
  const cookies = Array.isArray(state.cookies) ? state.cookies : []
  let min: number | null = null
  for (const c of cookies) {
    const e = Number(c?.expires)
    if (Number.isFinite(e) && e > 0 && (min === null || e < min)) min = e
  }
  if (min === null) return '会话型（长期）'
  const d = new Date(min * 1000)
  if (Number.isNaN(d.getTime())) return '-'
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const isAuthExpired = (record: UiAuthState): boolean => {
  const state = record.state_json || {}
  const cookies = Array.isArray(state.cookies) ? state.cookies : []
  for (const c of cookies) {
    const e = Number(c?.expires)
    if (Number.isFinite(e) && e > 0 && e * 1000 < Date.now()) return true
  }
  return false
}

const credentialSummary = (record: UiAuthState) => {
  const state = record.state_json || {}
  const cookies = Array.isArray(state.cookies) ? state.cookies.length : 0
  const origins = Array.isArray(state.origins) ? state.origins : []
  const lsKeys = origins.reduce(
    (sum: number, o: Record<string, unknown>) => sum + (Array.isArray(o.localStorage) ? o.localStorage.length : 0),
    0,
  )
  if (!cookies && !lsKeys) return '无凭据'
  return `cookies=${cookies}, localStorage=${lsKeys}`
}

const fetchAuthStates = async () => {
  if (!currentAuthEnv.value) return
  authLoading.value = true
  try {
    const res = await authStateApi.list({ env_config: currentAuthEnv.value.id })
    const { items } = extractPaginationData(res)
    authStates.value = items
  } catch {
    Message.error('获取登录态列表失败')
  } finally {
    authLoading.value = false
  }
}

const openAuthModal = (record: UiEnvironmentConfig) => {
  currentAuthEnv.value = record
  authModalVisible.value = true
  fetchAuthStates()
}

const authEditVisible = ref(false)
const authEditing = ref(false)
const authEditName = ref('')
const editingAuth = ref<UiAuthState | null>(null)

const openEditAuth = (record: UiAuthState) => {
  editingAuth.value = record
  authEditName.value = record.name || ''
  authEditVisible.value = true
}

const submitEditAuth = async () => {
  if (!editingAuth.value) return
  const name = authEditName.value.trim()
  if (!name) {
    Message.error('登录态名称不能为空')
    return
  }
  authEditing.value = true
  try {
    await authStateApi.update(editingAuth.value.id, { name })
    Message.success('名称已更新')
    authEditVisible.value = false
    fetchAuthStates()
  } catch (err) {
    const detail = (err as { detail?: string })?.detail
    Message.error(detail || '更新失败')
  } finally {
    authEditing.value = false
  }
}

const deleteAuthState = async (record: UiAuthState) => {
  try {
    await authStateApi.delete(record.id)
    Message.success('删除成功')
    if (authStates.value.length <= 1) fetchData()
    fetchAuthStates()
  } catch {
    Message.error('删除失败')
  }
}

const fetchData = async () => {
  if (!projectId.value) return
  loading.value = true
  try {
    const res = await envConfigApi.list({
      project: projectId.value,
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

/** 构建 MySQL 配置对象 */
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
      mysql_config: buildMysqlConfig()
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
.auth-edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.auth-ops-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  white-space: nowrap;
}

.auth-cred-cell {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
}

.auth-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.auth-tip {
  font-size: 12px;
  color: var(--color-text-3);
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
.auth-expired {
  color: var(--color-danger-6, #f53f3f);
  font-weight: 500;
}
</style>
