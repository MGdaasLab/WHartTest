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
              <a-switch v-model="formData.headless" @change="handleHeadlessChange" />
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

        <a-divider orientation="left" class="section-divider">{{ pageText.executionSettings }}</a-divider>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="max_concurrent" :label="pageText.maxConcurrent">
              <a-input-number v-model="formData.max_concurrent" :style="{ width: '100%' }" />
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
        dockerHeadlessWarn: 'The current actuator is deployed in a Docker environment and cannot enable headed mode',
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
        dockerHeadlessWarn: '当前执行器使用docker环境部署无法启用有头模式',
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
  persistent: true,
  trace_enabled: true,
  trace_screenshots: true,
  trace_snapshots: true,
  trace_sources: false,
  headless: true, // 无头模式默认开启
  viewport_width: 1280,
  viewport_height: 720,
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

const formRules = {
  name: [{ required: true, message: pageText.value.actuatorNameRequired }],
  launch_timeout: [rangeValidator(10, 120, pageText.value.launchTimeoutRange)],
  action_timeout: [rangeValidator(5, 60, pageText.value.actionTimeoutRange)],
  retry_count: [rangeValidator(0, 10, pageText.value.retryCountRange)],
  step_interval: [rangeValidator(0, 60000, pageText.value.stepIntervalRange)],
  max_concurrent: [rangeValidator(1, 20, pageText.value.maxConcurrentRange)],
  viewport_width: [rangeValidator(320, 3840, pageText.value.viewportWidthRange)],
  viewport_height: [rangeValidator(240, 2160, pageText.value.viewportHeightRange)],
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
    persistent: record.persistent ?? true,
    trace_enabled: record.trace_enabled ?? true,
    trace_screenshots: record.trace_screenshots ?? true,
    trace_snapshots: record.trace_snapshots ?? true,
    trace_sources: record.trace_sources ?? false,
    headless: record.headless ?? true,
    viewport_width: record.viewport_width ?? 1280,
    viewport_height: record.viewport_height ?? 720,
  })
  formRef.value?.clearValidate()
  editVisible.value = true
}

const handleCancel = () => {
  editVisible.value = false
}

/** 无头模式开关：docker 部署的执行器禁止关闭无头模式（无法启用有头） */
const handleHeadlessChange = (value: boolean | string | number) => {
  if (value === false && editingRecord.value?.in_container) {
    Message.warning(pageText.value.dockerHeadlessWarn)
    formData.headless = true // 回弹为开启
  }
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
</style>
