<template>
  <div class="actuator-list">
    <!-- 头部 -->
    <div class="header">
      <div class="title">
        <h3>{{ pageText.title }}</h3>
        <span class="count">{{ pageText.count(actuators.length) }}</span>
      </div>
      <div class="actions">
        <a-button @click="loadActuators" :loading="loading">
          <template #icon><icon-refresh /></template>
          {{ pageText.refresh }}
        </a-button>
      </div>
    </div>

    <!-- 状态提示 -->
    <a-alert
      v-if="!loading && actuators.length === 0"
      type="warning"
      class="mb-4"
    >
      <template #title>{{ pageText.emptyTitle }}</template>
      {{ pageText.startServiceHint }}
    </a-alert>

    <!-- 执行器表格 -->
    <a-table
      :key="`actuator-table-${locale}`"
      :data="actuators"
      :loading="loading"
      :pagination="false"
      stripe
    >
      <template #columns>
        <a-table-column :title="pageText.status" :width="70" align="center">
          <template #cell>
            <div class="online-dot"></div>
          </template>
        </a-table-column>
        <a-table-column :title="pageText.name" data-index="name" :width="160" />
        <a-table-column :title="pageText.ipAddress" data-index="ip" :width="150" />
        <a-table-column :title="pageText.type" :width="100">
          <template #cell="{ record }">
            <a-tag :color="getTypeTagColor(record.type)" size="small">
              {{ getTypeLabel(record.type) }}
            </a-tag>
          </template>
        </a-table-column>
        <a-table-column :title="pageText.browser" :width="160">
          <template #cell="{ record }">
            {{ (record.supported_browsers && record.supported_browsers.length) ? record.supported_browsers.join(', ') : (record.browser_type || '-') }}
          </template>
        </a-table-column>
        <a-table-column :title="pageText.slots || 'Slots'" :width="100">
          <template #cell="{ record }">
            {{ (record.busy_slots ?? 0) }}/{{ (record.max_slots ?? 1) }}
          </template>
        </a-table-column>
        <a-table-column :title="pageText.headlessMode" :width="90" align="center">
          <template #cell="{ record }">
            <a-tag :color="record.headless ? 'orangered' : 'green'" size="small">
              {{ record.headless ? pageText.yes : pageText.no }}
            </a-tag>
          </template>
        </a-table-column>
        <a-table-column title="OPEN" :width="80" align="center">
          <template #cell="{ record }">
            <a-switch v-model="record.is_open" size="small" disabled />
          </template>
        </a-table-column>
        <a-table-column title="DEBUG" :width="80" align="center">
          <template #cell="{ record }">
            <a-switch v-model="record.debug" size="small" disabled />
          </template>
        </a-table-column>
        <a-table-column :title="pageText.connectedAt" :width="170">
          <template #cell="{ record }">
            <span class="time-text">{{ formatTime(record.connected_at) }}</span>
          </template>
        </a-table-column>
        <a-table-column :title="pageText.operations" :width="90" fixed="right" align="center">
          <template #cell="{ record }">
            <a-button type="text" size="mini" @click="openEdit(record)">
              <template #icon><icon-edit /></template>
              {{ pageText.edit }}
            </a-button>
          </template>
        </a-table-column>
      </template>
    </a-table>

    <!-- 编辑执行器配置弹窗 -->
    <a-modal
      v-model:visible="editVisible"
      :title="pageText.editTitle"
      :ok-loading="submitting"
      @before-ok="handleSubmit"
      @cancel="handleCancel"
      width="560"
    >
      <a-form ref="formRef" :model="formData" :rules="formRules" layout="vertical" :validate-trigger="['blur', 'change']">
        <a-form-item field="name" :label="pageText.actuatorName">
          <a-input v-model="formData.name" :placeholder="pageText.actuatorNamePlaceholder" :max-length="50" />
        </a-form-item>
        <a-divider orientation="left" class="section-divider">{{ pageText.browserSettings }}</a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="browser_type" :label="pageText.browserType">
              <a-select v-model="formData.browser_type">
                <a-option v-for="b in browserOptions" :key="b" :value="b">{{ b }}</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="log_level" :label="pageText.logLevel">
              <a-select v-model="formData.log_level">
                <a-option v-for="l in logLevelOptions" :key="l" :value="l">{{ l }}</a-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="launch_timeout" :label="pageText.launchTimeout">
              <a-input-number v-model="formData.launch_timeout" :style="{ width: '100%' }" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="action_timeout" :label="pageText.actionTimeout">
              <a-input-number v-model="formData.action_timeout" :style="{ width: '100%' }" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="retry_count" :label="pageText.retryCount">
              <a-input-number v-model="formData.retry_count" :style="{ width: '100%' }" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="step_interval" :label="pageText.stepInterval">
              <a-input-number v-model="formData.step_interval" :style="{ width: '100%' }" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="headless" :label="pageText.headlessMode">
              <a-switch v-model="formData.headless" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="viewport_width" :label="pageText.viewportWidth">
              <a-input-number v-model="formData.viewport_width" :style="{ width: '100%' }" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="viewport_height" :label="pageText.viewportHeight">
              <a-input-number v-model="formData.viewport_height" :style="{ width: '100%' }" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left" class="section-divider">{{ pageText.clientCertSettings }}</a-divider>
        <a-alert type="info" class="client-cert-hint">{{ pageText.clientCertHint }}</a-alert>
        <a-form-item field="client_cert_enabled" :label="pageText.clientCertEnabled">
          <a-switch v-model="formData.client_cert_enabled" />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="24">
            <a-form-item field="client_cert_pfx_path" :label="pageText.clientCertPfxPath">
              <a-input
                v-model="formData.client_cert_pfx_path"
                :placeholder="pageText.clientCertPfxPlaceholder"
                :disabled="!formData.client_cert_enabled"
                allow-clear
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="client_cert_cert_path" :label="pageText.clientCertCertPath">
              <a-input
                v-model="formData.client_cert_cert_path"
                :disabled="!formData.client_cert_enabled"
                allow-clear
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="client_cert_key_path" :label="pageText.clientCertKeyPath">
              <a-input
                v-model="formData.client_cert_key_path"
                :disabled="!formData.client_cert_enabled"
                allow-clear
              />
            </a-form-item>
          </a-col>
          <a-col :span="24">
            <a-form-item field="client_cert_origins" :label="pageText.clientCertOrigins">
              <a-input
                v-model="formData.client_cert_origins"
                :placeholder="pageText.clientCertOriginsPlaceholder"
                :disabled="!formData.client_cert_enabled"
                allow-clear
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left" class="section-divider">{{ pageText.executionSettings }}</a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="max_concurrent" :label="pageText.maxConcurrent">
              <a-input-number v-model="formData.max_concurrent" :style="{ width: '100%' }" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="fail_fast" :label="pageText.failFast">
              <a-space>
                <a-switch v-model="formData.fail_fast" />
                <a-tooltip :content="pageText.failFastHint" position="top">
                  <span class="fail-fast-hint">?</span>
                </a-tooltip>
              </a-space>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="persistent" :label="pageText.persistent">
              <a-switch v-model="formData.persistent" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="trace_enabled" :label="pageText.trace">
              <a-switch v-model="formData.trace_enabled" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="trace_screenshots" :label="pageText.traceScreenshots">
              <a-switch v-model="formData.trace_screenshots" :disabled="!formData.trace_enabled" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="trace_snapshots" :label="pageText.traceSnapshots">
              <a-switch v-model="formData.trace_snapshots" :disabled="!formData.trace_enabled" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="trace_sources" :label="pageText.traceSources">
              <a-switch v-model="formData.trace_sources" :disabled="!formData.trace_enabled" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { IconRefresh, IconEdit } from '@arco-design/web-vue/es/icon'
import { Message } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import { useAppI18n } from '@/composables/useAppI18n'
import { actuatorApi, type ActuatorInfo, type ActuatorConfigPayload } from '../api'
import { extractResponseData } from '../types'

void IconRefresh
void IconEdit

const { locale, isEnglish } = useAppI18n()

const pageText = computed(() => (
  isEnglish.value
    ? {
        title: 'Online actuators',
        count: (count: number) => `${count} total`,
        refresh: 'Refresh',
        emptyTitle: 'No online actuators',
        startServiceHint: 'Start the actuator service first: cd WHartTest_Actuator && python main.py',
        status: 'Status',
        name: 'Name',
        ipAddress: 'IP address',
        type: 'Type',
        browser: 'Supported Browsers',
        slots: 'Slots',
        headlessMode: 'Headless',
        yes: 'Yes',
        no: 'No',
        connectedAt: 'Connected at',
        operations: 'Actions',
        edit: 'Edit',
        editTitle: 'Edit actuator config',
        saveSuccess: 'Actuator config saved and applied',
        saveFailed: 'Failed to save actuator config',
        browserSettings: 'Browser Settings',
        executionSettings: 'Execution Settings',
        browserType: 'Browser Type',
        logLevel: 'Log Level',
        launchTimeout: 'Launch Timeout (s)',
        actionTimeout: 'Action Timeout (s)',
        retryCount: 'Retry Count',
        stepInterval: 'Step Interval (ms)',
        maxConcurrent: 'Max Concurrent',
        failFast: 'Fail Fast',
        failFastHint: 'When an element cannot be located (all locators and action timeout exhausted), abort the case immediately and report the execution record instead of continuing with later steps',
        persistent: 'Persistent',
        trace: 'Trace',
        traceScreenshots: 'Screenshots',
        traceSnapshots: 'DOM',
        traceSources: 'Source',
        launchTimeoutRange: 'Launch timeout must be between 10 and 120 seconds',
        actionTimeoutRange: 'Action timeout must be between 5 and 60 seconds',
        retryCountRange: 'Retry count must be between 0 and 10',
        stepIntervalRange: 'Step interval must be between 0 and 60000 ms',
        maxConcurrentRange: 'Max concurrent must be between 1 and 20',
        actuatorName: 'Actuator Name',
        actuatorNamePlaceholder: 'Enter a custom actuator name',
        actuatorNameRequired: 'Actuator name is required',
        viewportWidth: 'Viewport Width',
        viewportHeight: 'Viewport Height',
        viewportWidthRange: 'Viewport width must be between 320 and 3840',
        viewportHeightRange: 'Viewport height must be between 240 and 2160',
        clientCertSettings: 'HTTPS Client Certificate',
        clientCertEnabled: 'Enable client certificate',
        clientCertPfxPath: 'PFX/P12 path',
        clientCertPfxPlaceholder: 'e.g. ./certs/client.pfx (relative to config.toml)',
        clientCertCertPath: 'PEM cert path',
        clientCertKeyPath: 'PEM key path',
        clientCertOrigins: 'Extra origins (comma separated)',
        clientCertOriginsPlaceholder: 'e.g. https://a.example.com,https://b.example.com:8443',
        clientCertHint: 'Used for HTTPS sites that require a client certificate. Origins are derived automatically from the case base_url / page URLs; fill extra origins only when one certificate covers multiple domains. The passphrase is NOT managed here — set WHARTTEST_ACTUATOR_CLIENT_CERT_PASSPHRASE on the actuator host.',
        clientCertMaterialRequired: 'Provide a PFX/P12 path, or both PEM cert and key paths',
      }
    : {
        title: '在线执行器',
        count: (count: number) => `共 ${count} 个`,
        refresh: '刷新',
        emptyTitle: '暂无在线执行器',
        startServiceHint: '请先启动执行器服务：cd WHartTest_Actuator && python main.py',
        status: '状态',
        name: '名称',
        ipAddress: 'IP地址',
        type: '类型',
        browser: '支持浏览器',
        slots: '槽位',
        headlessMode: '无头模式',
        yes: '是',
        no: '否',
        connectedAt: '连接时间',
        operations: '操作',
        edit: '编辑',
        editTitle: '编辑执行器配置',
        saveSuccess: '执行器配置已保存并生效',
        saveFailed: '执行器配置保存失败',
        browserSettings: '浏览器设置',
        executionSettings: '执行设置',
        browserType: '浏览器类型',
        logLevel: '日志级别',
        launchTimeout: '启动超时（秒）',
        actionTimeout: '操作超时（秒）',
        retryCount: '失败重试次数',
        stepInterval: '步骤间隔（毫秒）',
        maxConcurrent: '最大并发数',
        failFast: '失败中断执行',
        failFastHint: '元素定位失败（主/备用表达式与操作超时均等待结束仍未成功）时立即中断用例并上报执行记录，不再尝试定位后续步骤',
        maxConcurrent: '批量并发',
        persistent: '持久化',
        trace: 'Trace',
        traceScreenshots: '截图',
        traceSnapshots: 'DOM',
        traceSources: '源码',
        launchTimeoutRange: '启动超时必须为 10-120 之间的数',
        actionTimeoutRange: '操作超时必须为 5-60 之间的数',
        retryCountRange: '失败重试次数必须为 0-10 之间的数',
        stepIntervalRange: '步骤间隔必须为 0-60000 之间的数',
        maxConcurrentRange: '批量并发必须为 1-20 之间的数',
        actuatorName: '执行器名称',
        actuatorNamePlaceholder: '请输入自定义执行器名称',
        actuatorNameRequired: '执行器名称不能为空',
        viewportWidth: '视口宽度',
        viewportHeight: '视口高度',
        viewportWidthRange: '视口宽度必须为 320-3840 之间的数',
        viewportHeightRange: '视口高度必须为 240-2160 之间的数',
        clientCertSettings: 'HTTPS 客户端证书',
        clientCertEnabled: '启用客户端证书',
        clientCertPfxPath: 'PFX/P12 证书路径',
        clientCertPfxPlaceholder: '例如 ./certs/client.pfx（相对 config.toml 所在目录）',
        clientCertCertPath: 'PEM 证书路径',
        clientCertKeyPath: 'PEM 私钥路径',
        clientCertOrigins: '额外生效 origin（逗号分隔）',
        clientCertOriginsPlaceholder: '例如 https://a.example.com,https://b.example.com:8443',
        clientCertHint: '用于访问要求客户端证书的 HTTPS 站点。origin 会从用例的 base_url / 页面地址自动推导，仅当一张证书覆盖多个域名时才需要补充额外 origin。证书口令不在此处管理，请在执行器本机设置环境变量 WHARTTEST_ACTUATOR_CLIENT_CERT_PASSPHRASE。',
        clientCertMaterialRequired: '请填写 PFX/P12 路径，或同时填写 PEM 证书与私钥路径',
      }
))

const actuators = ref<ActuatorInfo[]>([])
const loading = ref(false)
let refreshTimer: ReturnType<typeof setInterval> | null = null

const loadActuators = async () => {
  loading.value = true
  try {
    const res = await actuatorApi.list()
    const data = extractResponseData<{ count: number; items: ActuatorInfo[] }>(res)
    actuators.value = data?.items || []
  } catch (e) {
    console.error('Load actuators error:', e)
    actuators.value = []
  } finally {
    loading.value = false
  }
}

const getTypeLabel = (type: string) => {
  const typeMap: Record<string, string> = {
    web_ui: 'Web UI',
    android_ui: 'Android UI',
    pytest: 'Pytest',
    pytest_web: 'Pytest Web',
  }
  return typeMap[type] || type
}

const getTypeTagColor = (type: string) => {
  const typeMap: Record<string, string> = {
    web_ui: 'arcoblue',
    android_ui: 'green',
    pytest: 'orangered',
    pytest_web: 'purple',
  }
  return typeMap[type] || 'gray'
}

const formatTime = (isoString: string) => {
  if (!isoString) return '-'
  const date = new Date(isoString)
  return date.toLocaleString(isEnglish.value ? 'en-US' : 'zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const refresh = () => loadActuators()

defineExpose({ refresh })

// ==================== 编辑执行器配置 ====================
const editVisible = ref(false)
const editingRecord = ref<ActuatorInfo | null>(null)
const submitting = ref(false)
const formRef = ref<FormInstance>()

const logLevelOptions = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
const browserOptions = computed(() => {
  const supported = editingRecord.value?.supported_browsers
  return supported && supported.length ? supported : ['chromium', 'firefox', 'webkit']
})

const formData = reactive<ActuatorConfigPayload>({
  name: '',
  browser_type: 'chromium',
  log_level: 'INFO',
  launch_timeout: 30,
  action_timeout: 30,
  retry_count: 3,
  step_interval: 500,
  max_concurrent: 3,
  fail_fast: false,
  persistent: true,
  trace_enabled: true,
  trace_screenshots: true,
  trace_snapshots: true,
  trace_sources: false,
  headless: true, // 无头模式默认开启
  viewport_width: 1280,
  viewport_height: 720,
  // HTTPS 客户端证书（口令不在平台侧）
  client_cert_enabled: false,
  client_cert_pfx_path: '',
  client_cert_cert_path: '',
  client_cert_key_path: '',
  client_cert_origins: '',
})

/** 生成数值范围校验规则：不纠正输入，校验失败时在输入框下方红字提示 */
const rangeValidator = (min: number, max: number, message: string) => ({
  validator: (value: any, callback: (error?: string) => void) => {
    if (value === undefined || value === null || value === '') {
      callback(message)
      return
    }
    const v = Number(value)
    if (Number.isNaN(v) || v < min || v > max) {
      callback(message)
      return
    }
    callback()
  },
})

/** 客户端证书材料校验：启用时必须给出 pfx，或同时给出 PEM cert 与 key */
const clientCertMaterialValidator = {
  validator: (_value: any, callback: (error?: string) => void) => {
    if (!formData.client_cert_enabled) {
      callback()
      return
    }
    const pfx = (formData.client_cert_pfx_path || '').trim()
    const cert = (formData.client_cert_cert_path || '').trim()
    const key = (formData.client_cert_key_path || '').trim()
    callback(pfx || (cert && key) ? undefined : pageText.value.clientCertMaterialRequired)
  },
}

const formRules = {
  name: [{ required: true, message: pageText.value.actuatorNameRequired }],
  launch_timeout: [rangeValidator(10, 120, pageText.value.launchTimeoutRange)],
  action_timeout: [rangeValidator(5, 60, pageText.value.actionTimeoutRange)],
  retry_count: [rangeValidator(0, 10, pageText.value.retryCountRange)],
  step_interval: [rangeValidator(0, 60000, pageText.value.stepIntervalRange)],
  max_concurrent: [rangeValidator(1, 20, pageText.value.maxConcurrentRange)],
  viewport_width: [rangeValidator(320, 3840, pageText.value.viewportWidthRange)],
  viewport_height: [rangeValidator(240, 2160, pageText.value.viewportHeightRange)],
  client_cert_pfx_path: [clientCertMaterialValidator],
  client_cert_cert_path: [clientCertMaterialValidator],
  client_cert_key_path: [clientCertMaterialValidator],
}

const openEdit = (record: ActuatorInfo) => {
  editingRecord.value = record
  Object.assign(formData, {
    name: record.name || record.id,
    browser_type: record.browser_type || 'chromium',
    log_level: record.log_level || 'INFO',
    launch_timeout: record.launch_timeout ?? 30,
    action_timeout: record.action_timeout ?? 30,
    retry_count: record.retry_count ?? 3,
    step_interval: record.step_interval ?? 500,
    max_concurrent: record.max_slots ?? 3,
    fail_fast: record.fail_fast ?? false,
    persistent: record.persistent ?? true,
    trace_enabled: record.trace_enabled ?? true,
    trace_screenshots: record.trace_screenshots ?? true,
    trace_snapshots: record.trace_snapshots ?? true,
    trace_sources: record.trace_sources ?? false,
    headless: record.headless ?? true,
    viewport_width: record.viewport_width ?? 1280,
    viewport_height: record.viewport_height ?? 720,
    client_cert_enabled: record.client_cert_enabled ?? false,
    // 用 || '' 而非 ?? ''：后端可能返回 null，统一成空串，避免上一台的残留值串到下一条
    client_cert_pfx_path: record.client_cert_pfx_path || '',
    client_cert_cert_path: record.client_cert_cert_path || '',
    client_cert_key_path: record.client_cert_key_path || '',
    client_cert_origins: record.client_cert_origins || '',
  })
  formRef.value?.clearValidate()
  editVisible.value = true
}

const handleCancel = () => {
  editVisible.value = false
}

const handleSubmit = async (done: (closed: boolean) => void) => {
  if (!editingRecord.value) {
    done(false)
    return
  }
  try {
    await formRef.value?.validate()
  } catch {
    done(false) // 校验失败：错误红字显示在输入框下方，不关闭弹窗
    return
  }
  submitting.value = true
  try {
    const payload: ActuatorConfigPayload = { ...formData }
    await actuatorApi.updateConfig(editingRecord.value.id, payload)
    Message.success(pageText.value.saveSuccess)
    done(true)
    loadActuators() // 立即刷新列表
  } catch (err: any) {
    console.error('Update actuator config error:', err)
    Message.error(err?.error || pageText.value.saveFailed)
    done(false)
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  loadActuators()
  // 每30秒刷新一次
  refreshTimer = setInterval(loadActuators, 30000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>

<style scoped lang="scss">
.actuator-list {
  padding: 16px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;

  .title {
    display: flex;
    align-items: center;
    gap: 12px;

    h3 {
      margin: 0;
      font-size: 18px;
      font-weight: 600;
    }

    .count {
      color: var(--color-text-3);
      font-size: 14px;
    }
  }
}

.mb-4 {
  margin-bottom: 16px;
}

/* 失败中断提示问号：圆形边框，悬停展示说明气泡 */
.fail-fast-hint {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 1px solid var(--color-border-2);
  color: var(--color-text-3);
  font-size: 10px;
  cursor: help;
}

.online-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #00b42a;
  box-shadow: 0 0 8px rgba(0, 180, 42, 0.5);
  display: inline-block;
}

.time-text {
  font-size: 12px;
  color: var(--color-text-3);
}

.section-divider {
  margin-top: 4px;
  margin-bottom: 12px;
}

.client-cert-hint {
  margin-bottom: 12px;
  font-size: 12px;
  line-height: 1.6;
}
</style>
