<template>
  <a-modal
    :visible="visible"
    :title="text.title"
    :footer="false"
    :mask-closable="!recording && !starting"
    :closable="!starting"
    :width="phase === 'setup' ? 620 : 1060"
    @cancel="handleCancel"
  >
    <!-- 阶段1：录制参数表单 -->
    <div v-if="phase === 'setup'" class="recorder-setup">
      <a-form :model="form" layout="vertical">
        <a-form-item :label="text.page" :required="true">
          <a-select
            v-model="form.page_id"
            :options="pageOptions"
            :placeholder="text.selectPage"
            allow-search
            allow-clear
            :loading="loadingPages"
            @change="onPageChange"
          />
        </a-form-item>
        <a-form-item :label="text.pageStep" :required="true">
          <a-select
            v-model="form.page_step_id"
            :options="stepOptions"
            :placeholder="text.selectPageStep"
            allow-search
            allow-clear
            :loading="loadingSteps"
          />
        </a-form-item>
        <a-form-item :label="text.environment" :required="true">
          <a-select
            v-model="form.env_config_id"
            :options="envOptions"
            :placeholder="text.selectEnvironment"
            allow-search
            allow-clear
            :loading="loadingEnvs"
          />
          <div class="recorder-form-hint">{{ text.envHint }}</div>
        </a-form-item>
        <a-form-item :label="text.recordOptions" class="recorder-switches">
          <a-space direction="vertical" fill>
            <div class="recorder-switch-row">
              <span>{{ text.createElementsLabel }}</span>
              <a-switch v-model="form.create_elements" />
            </div>
            <div class="recorder-switch-row">
              <span>{{ text.createStepsLabel }}</span>
              <a-switch v-model="form.create_steps" />
            </div>
          </a-space>
        </a-form-item>
      </a-form>
      <div class="recorder-setup-actions">
        <a-button :disabled="starting" @click="handleCancel">{{ text.cancel }}</a-button>
        <a-button type="primary" :loading="starting" @click="handleStart">
          {{ text.startRecord }}
        </a-button>
      </div>
    </div>

    <!-- 阶段2：录制视图 -->
    <div v-else class="recorder-live">
      <div class="recorder-canvas-wrap">
        <canvas
          ref="canvasRef"
          class="recorder-canvas"
          :style="{ width: viewportCssWidth }"
          @pointerdown="onPointerDown"
          @pointerup="onPointerUp"
          @pointermove="onPointerMove"
          @wheel="onWheel"
        />
        <div v-if="!firstFrame" class="recorder-loading-overlay">
          <a-spin :loading="true" />
          <span>{{ text.connecting }}</span>
        </div>
        <div class="recorder-url-bar" :title="currentUrl || ''">
          <icon-link />
          <span class="truncate">{{ currentUrl || text.preparing }}</span>
        </div>
      </div>

      <div class="recorder-side">
        <div class="recorder-toolbar">
          <a-select
            v-model="assertMode"
            :options="assertOptions"
            size="small"
            style="width: 130px"
          />
          <a-button
            type="primary"
            size="small"
            :disabled="!recording"
            @click="handleAssert"
          >
            {{ text.assert }}
          </a-button>
          <a-button
            type="outline"
            status="danger"
            size="small"
            :loading="finishing"
            :disabled="!recording"
            @click="handleFinish"
          >
            {{ text.finishRecord }}
          </a-button>
        </div>
        <div class="recorder-hint">{{ text.recordHint }}</div>
        <div class="recorder-actions-list">
          <div v-for="a in actions" :key="a.seq" class="recorder-action-item">
            <a-tag size="small" :color="actionTagColor(a.type)">
              {{ actionLabel(a) }}
            </a-tag>
            <span class="recorder-action-desc">{{ actionDesc(a) }}</span>
          </div>
          <div v-if="recording && actions.length === 0" class="recorder-actions-empty">
            {{ text.noActions }}
          </div>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { IconLink } from '@arco-design/web-vue/es/icon'
import { useAppI18n } from '@/composables/useAppI18n'
import { useProjectStore } from '@/store/projectStore'
import { pageApi, pageStepsApi, envConfigApi, recorderApi } from '../api'
import type { RecorderSessionInfo, RecorderFinishResult } from '../api'
import type { UiPage, UiPageSteps, UiEnvironmentConfig } from '../types'
import { extractListData, extractResponseData } from '../types'
import { uiWebSocket, UiSocketEnum } from '../services/websocket'

const props = defineProps<{
  visible: boolean
  projectId?: number
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'refresh'): void
}>()

const { isEnglish } = useAppI18n()

const text = computed(() => (
  isEnglish.value
    ? {
        title: 'Record Steps',
        page: 'Page',
        selectPage: 'Select a page',
        pageStep: 'Page step',
        selectPageStep: 'Select a page step',
        environment: 'Environment',
        selectEnvironment: 'Select an environment',
        envHint: 'Recording navigates to the environment base URL (falls back to the page URL).',
        recordOptions: 'Recording options',
        createElementsLabel: 'Create page elements (saved under the selected page)',
        createStepsLabel: 'Create page steps (saved into the selected page step)',
        cancel: 'Cancel',
        startRecord: 'Start Recording',
        connecting: 'Connecting to browser...',
        preparing: 'Preparing browser...',
        assert: 'Assert',
        finishRecord: 'Finish',
        recordHint: 'Operate in the browser view below. Hover an element then click Assert to record an assertion.',
        noActions: 'No actions yet. Operate in the browser view.',
        confirmCancel: 'Cancel recording? The unfinished recording will be discarded.',
        startFailed: 'Failed to start recording',
        finishFailed: 'Failed to finish recording',
        finishSuccess: 'Recording saved',
        scriptSaved: 'Script:',
        stats: 'Actions: {actions}, elements: +{elements}, steps: +{steps}',
        assertRecorded: 'Assertion recorded',
        assertFailed: 'Assertion failed',
        assertVisible: 'Visible',
        assertContainText: 'Contains text',
        assertEnabled: 'Enabled',
        emptyPageSteps: 'This page has no page steps yet',
      }
    : {
        title: '录制步骤',
        page: '页面',
        selectPage: '请选择页面',
        pageStep: '页面步骤',
        selectPageStep: '请选择页面步骤',
        environment: '环境',
        selectEnvironment: '请选择环境',
        envHint: '录制时先导航到环境的基础 URL（环境未配置时使用页面 URL）。',
        recordOptions: '录制选项',
        createElementsLabel: '创建页面元素（保存到所选页面下）',
        createStepsLabel: '创建页面步骤（保存到所选页面步骤下）',
        cancel: '取消',
        startRecord: '开始录制',
        connecting: '正在连接浏览器…',
        preparing: '正在准备浏览器…',
        assert: '断言',
        finishRecord: '结束录制',
        recordHint: '在左侧浏览器画面中操作；悬停目标元素后点击「断言」可记录断言。',
        noActions: '暂无动作，请在浏览器画面中操作',
        confirmCancel: '确定取消录制？未完成的录制将被丢弃。',
        startFailed: '启动录制失败',
        finishFailed: '结束录制失败',
        finishSuccess: '录制已保存',
        scriptSaved: '脚本文件：',
        stats: '动作 {actions} 个，新增元素 {elements} 个，新增步骤 {steps} 个',
        assertRecorded: '断言已记录',
        assertFailed: '断言失败',
        assertVisible: '元素可见',
        assertContainText: '包含文本',
        assertEnabled: '元素可用',
        emptyPageSteps: '该页面下还没有页面步骤',
      }
))

type Phase = 'setup' | 'recording' | 'result'

const phase = ref<Phase>('setup')
const starting = ref(false)
const recording = ref(false)
const finishing = ref(false)

const form = reactive({
  page_id: undefined as number | undefined,
  page_step_id: undefined as number | undefined,
  env_config_id: undefined as number | undefined,
  create_elements: true,
  create_steps: true,
})

const projectId = computed(() => props.projectId ?? useProjectStore().currentProject?.id)

const loadingPages = ref(false)
const loadingSteps = ref(false)
const loadingEnvs = ref(false)
const pageOptions = ref<Array<{ label: string; value: number }>>([])
const stepOptions = ref<Array<{ label: string; value: number }>>([])
const envOptions = ref<Array<{ label: string; value: number }>>([])

const sessionId = ref('')
const viewport = reactive({ width: 1400, height: 900 })
const actions = ref<Array<Record<string, any>>>([])
const firstFrame = ref(false)
const currentUrl = ref('')
const canvasRef = ref<HTMLCanvasElement | null>(null)
const lastFrameData = ref('')

const assertMode = ref('visible')
const assertOptions = computed(() => [
  { label: text.value.assertVisible, value: 'visible' },
  { label: text.value.assertContainText, value: 'contain_text' },
  { label: text.value.assertEnabled, value: 'enabled' },
])

const viewportCssWidth = computed(() => {
  const ratio = viewport.width / Math.max(viewport.height, 1)
  return `${Math.min(960, Math.max(420, Math.round(ratio * 640)))}px`
})

// ------------------------------------------------------------------
// 表单数据
// ------------------------------------------------------------------

async function fetchPages() {
  if (!projectId.value) return
  loadingPages.value = true
  try {
    const res = await pageApi.list({ project: projectId.value })
    const list = extractListData<UiPage>(res)
    pageOptions.value = list.map((p) => ({ label: p.name, value: p.id }))
  } catch (e: any) {
    Message.error(e?.message || text.value.startFailed)
  } finally {
    loadingPages.value = false
  }
}

async function fetchSteps(pageId: number) {
  if (!projectId.value) return
  loadingSteps.value = true
  try {
    const res = await pageStepsApi.list({ project: projectId.value, page: pageId })
    const list = extractListData<UiPageSteps>(res)
    stepOptions.value = list.map((s) => ({ label: s.name, value: s.id }))
  } catch (e: any) {
    Message.error(e?.message || text.value.startFailed)
  } finally {
    loadingSteps.value = false
  }
}

async function fetchEnvs() {
  if (!projectId.value) return
  loadingEnvs.value = true
  try {
    const res = await envConfigApi.list({ project: projectId.value })
    const list = extractListData<UiEnvironmentConfig>(res)
    envOptions.value = list.map((e) => ({ label: e.name, value: e.id }))
    if (!form.env_config_id && list.length > 0) {
      const def = list.find((e) => e.is_default) || list[0]
      form.env_config_id = def.id
    }
  } catch (e: any) {
    Message.error(e?.message || text.value.startFailed)
  } finally {
    loadingEnvs.value = false
  }
}

function onPageChange(value: number | undefined) {
  form.page_step_id = undefined
  stepOptions.value = []
  if (value) fetchSteps(value)
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      resetState()
      fetchPages()
      fetchEnvs()
    }
  },
)

function resetState() {
  phase.value = 'setup'
  starting.value = false
  recording.value = false
  finishing.value = false
  form.page_id = undefined
  form.page_step_id = undefined
  form.env_config_id = undefined
  form.create_elements = true
  form.create_steps = true
  stepOptions.value = []
  sessionId.value = ''
  actions.value = []
  firstFrame.value = false
  currentUrl.value = ''
}

// ------------------------------------------------------------------
// 开始 / 结束 / 取消
// ------------------------------------------------------------------

async function ensureWs() {
  if (!uiWebSocket.connected.value) {
    await uiWebSocket.connect()
  }
}

async function handleStart() {
  if (!form.page_id || !form.page_step_id) {
    Message.warning(text.value.selectPageStep)
    return
  }
  if (!form.env_config_id) {
    Message.warning(text.value.selectEnvironment)
    return
  }
  starting.value = true
  try {
    const info = extractResponseData<RecorderSessionInfo>(await recorderApi.create({
      env_config_id: form.env_config_id,
      page_id: form.page_id,
      page_step_id: form.page_step_id,
      create_elements: form.create_elements,
      create_steps: form.create_steps,
    }))
    if (!info) throw new Error(text.value.startFailed)
    sessionId.value = info.session_id
    viewport.width = info.viewport?.width || 1400
    viewport.height = info.viewport?.height || 900
    currentUrl.value = info.base_url

    await ensureWs()
    uiWebSocket.recorderStart(sessionId.value)

    phase.value = 'recording'
    recording.value = true
    await nextTick()
    const canvas = canvasRef.value
    if (canvas) {
      canvas.width = viewport.width
      canvas.height = viewport.height
    }
    bindCanvasListeners()
  } catch (e: any) {
    Message.error(e?.message || text.value.startFailed)
  } finally {
    starting.value = false
  }
}

async function handleFinish() {
  if (!sessionId.value) return
  finishing.value = true
  try {
    uiWebSocket.recorderStop()
    const result = extractResponseData<RecorderFinishResult>(await recorderApi.finish(sessionId.value))
    if (!result) throw new Error(text.value.finishFailed)
    const stats = text.value.stats
      .replace('{actions}', String(result.actions_count))
      .replace('{elements}', String(result.elements_created))
      .replace('{steps}', String(result.steps_created))
    Message.success(`${text.value.finishSuccess}（${stats}）`)
    Message.info(`${text.value.scriptSaved} ${result.script_path}`)
    emit('refresh')
    closeModal()
  } catch (e: any) {
    Message.error(e?.message || text.value.finishFailed)
  } finally {
    finishing.value = false
  }
}

function handleCancel() {
  if (recording.value || starting.value) {
    Modal.confirm({
      title: text.value.confirmCancel,
      content: '',
      onOk: async () => {
        try {
          if (sessionId.value) {
            uiWebSocket.recorderStop()
            await recorderApi.cancel(sessionId.value)
          }
        } catch (_) {
          /* 忽略取消阶段的错误 */
        }
        closeModal()
      },
    })
    return
  }
  closeModal()
}

function closeModal() {
  unbindCanvasListeners()
  recording.value = false
  phase.value = 'setup'
  emit('update:visible', false)
}

// ------------------------------------------------------------------
// 画布：帧绘制 + 输入转发
// ------------------------------------------------------------------

function drawFrame(imageSrc: string) {
  const canvas = canvasRef.value
  if (!canvas) return
  const img = new Image()
  img.onload = () => {
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    canvas.width = viewport.width
    canvas.height = viewport.height
    ctx.drawImage(img, 0, 0, viewport.width, viewport.height)
  }
  img.src = imageSrc
}

function canvasPoint(e: PointerEvent | WheelEvent) {
  const canvas = canvasRef.value
  if (!canvas) return { x: 0, y: 0 }
  const rect = canvas.getBoundingClientRect()
  return {
    x: Math.round(((e.clientX - rect.left) / rect.width) * viewport.width),
    y: Math.round(((e.clientY - rect.top) / rect.height) * viewport.height),
  }
}

let lastMoveSent = 0

function onPointerDown(e: PointerEvent) {
  if (!recording.value) return
  const { x, y } = canvasPoint(e)
  uiWebSocket.recorderInput({
    type: 'mouse',
    event: 'down',
    x,
    y,
    button: e.button === 2 ? 'right' : 'left',
    clickCount: e.detail || 1,
  })
}

function onPointerUp(e: PointerEvent) {
  if (!recording.value) return
  const { x, y } = canvasPoint(e)
  uiWebSocket.recorderInput({
    type: 'mouse',
    event: 'up',
    x,
    y,
    button: e.button === 2 ? 'right' : 'left',
    clickCount: e.detail || 1,
  })
  e.preventDefault()
}

function onPointerMove(e: PointerEvent) {
  if (!recording.value) return
  const now = Date.now()
  if (now - lastMoveSent < 30) return
  lastMoveSent = now
  const { x, y } = canvasPoint(e)
  uiWebSocket.recorderInput({ type: 'mouse', event: 'move', x, y })
}

function onWheel(e: WheelEvent) {
  if (!recording.value) return
  const { x, y } = canvasPoint(e)
  uiWebSocket.recorderInput({
    type: 'wheel',
    x,
    y,
    deltaX: e.deltaX,
    deltaY: e.deltaY,
  })
  e.preventDefault()
}

function onKeyDown(e: KeyboardEvent) {
  if (!recording.value) return
  uiWebSocket.recorderInput({ type: 'key', event: 'down', key: e.key, code: e.code })
  if (['Enter', 'Tab', ' '].includes(e.key)) e.preventDefault()
}

function onKeyUp(e: KeyboardEvent) {
  if (!recording.value) return
  uiWebSocket.recorderInput({ type: 'key', event: 'up', key: e.key, code: e.code })
}

function bindCanvasListeners() {
  window.addEventListener('keydown', onKeyDown, true)
  window.addEventListener('keyup', onKeyUp, true)
}

function unbindCanvasListeners() {
  window.removeEventListener('keydown', onKeyDown, true)
  window.removeEventListener('keyup', onKeyUp, true)
}

// ------------------------------------------------------------------
// 断言 & 动作展示
// ------------------------------------------------------------------

function handleAssert() {
  if (!recording.value) return
  uiWebSocket.recorderAssert(assertMode.value)
}

function actionLabel(a: Record<string, any>): string {
  const map: Record<string, string> = {
    click: isEnglish.value ? 'Click' : '点击',
    fill: isEnglish.value ? 'Input' : '输入',
    check: 'Check',
    uncheck: 'Uncheck',
    press: isEnglish.value ? 'Press' : '按键',
    goto: isEnglish.value ? 'Navigate' : '跳转',
    assert: isEnglish.value ? 'Assert' : '断言',
  }
  return map[a.type] || a.type
}

function actionTagColor(type: string): string {
  if (type === 'assert') return 'gold'
  if (type === 'goto') return 'purple'
  return 'arcoblue'
}

function actionDesc(a: Record<string, any>): string {
  const sel = a.selector
  if (a.type === 'goto') return String(a.url || '')
  if (a.type === 'fill') return `${sel?.name || sel?.locator_value || ''} = ${a.value || ''}`
  if (a.type === 'press') return `${sel?.name || sel?.locator_value || ''} [${a.key || 'Enter'}]`
  if (a.type === 'assert') {
    if (a.mode === 'url') return String(a.value || '')
    const how = a.mode === 'contain_text' ? `: ${a.value || ''}` : ''
    return `${sel?.name || sel?.locator_value || ''}${how}`
  }
  return sel?.name || sel?.locator_value || ''
}

// ------------------------------------------------------------------
// WS 消息
// ------------------------------------------------------------------

function onRecorderFrame(data: any) {
  const args = data?.data?.func_args || {}
  const frame = args.frame
  if (!frame?.data) return
  lastFrameData.value = frame.data
  firstFrame.value = true
  if (viewport.width !== frame.w || viewport.height !== frame.h) {
    viewport.width = frame.w || viewport.width
    viewport.height = frame.h || viewport.height
  }
  drawFrame(`data:image/jpeg;base64,${frame.data}`)
}

function onRecorderAction(data: any) {
  const args = data?.data?.func_args || {}
  if (args.action) actions.value.push(args.action)
}

function onRecorderStatus(data: any) {
  const args = data?.data?.func_args || {}
  const status = args.status
  if (status === 'error') {
    Message.error(args.message || text.value.assertFailed)
  } else if (status === 'asserted') {
    Message.success(text.value.assertRecorded)
  }
}

let offFrame: (() => void) | null = null
let offAction: (() => void) | null = null
let offStatus: (() => void) | null = null

onMounted(() => {
  offFrame = uiWebSocket.on(UiSocketEnum.RECORDER_FRAME, onRecorderFrame as any)
  offAction = uiWebSocket.on(UiSocketEnum.RECORDER_ACTION, onRecorderAction as any)
  offStatus = uiWebSocket.on(UiSocketEnum.RECORDER_STATUS, onRecorderStatus as any)
})

onUnmounted(() => {
  offFrame?.()
  offAction?.()
  offStatus?.()
  unbindCanvasListeners()
})
</script>

<style lang="postcss" scoped>
.recorder-setup-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}

.recorder-form-hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-3);
}

.recorder-switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 2px;
}

.recorder-live {
  display: flex;
  gap: 12px;
  min-height: 560px;
}

.recorder-canvas-wrap {
  position: relative;
  flex: none;
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
  overflow: hidden;
  background: #111;
}

.recorder-canvas {
  display: block;
  cursor: crosshair;
}

.recorder-loading-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--color-text-2);
}

.recorder-url-bar {
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background: rgba(0, 0, 0, 0.55);
  color: #ddd;
  font-size: 12px;
}

.recorder-side {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.recorder-toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
}

.recorder-hint {
  font-size: 12px;
  color: var(--color-text-3);
  line-height: 1.5;
}

.recorder-actions-list {
  flex: 1;
  overflow-y: auto;
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 480px;
}

.recorder-action-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.recorder-action-desc {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recorder-actions-empty {
  color: var(--color-text-3);
  font-size: 13px;
  text-align: center;
  padding: 24px 0;
}
</style>