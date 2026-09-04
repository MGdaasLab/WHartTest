<template>
  <a-modal
    :visible="visible"
    :title="text.title"
    :footer="false"
    :mask-closable="true"
    width="min(1200px, calc(100vw - 24px))"
    @cancel="handleClose"
  >
    <div class="auth-capture-live">
      <div ref="canvasWrapRef" class="auth-capture-canvas-wrap">
        <canvas
          ref="canvasRef"
          class="auth-capture-canvas"
          :style="canvasStyle"
          @pointerdown="onPointerDown"
          @pointerup="onPointerUp"
          @pointermove="onPointerMove"
          @wheel="onWheel"
        />
        <!-- 隐藏输入法载体：保持聚焦让中文输入法正常组合 -->
        <input
          ref="imeInputRef"
          class="auth-capture-ime-input"
          @keydown.stop
          @keyup.stop
        />
        <div v-if="!hasFrame" class="auth-capture-overlay">
          <a-spin :loading="!saving" />
          <span>{{ text.waiting }}</span>
        </div>
      </div>
      <div class="auth-capture-side">
        <div class="auth-capture-env">{{ env?.name || '' }}</div>
        <div class="auth-capture-hint">{{ text.hint }}</div>
        <a-button type="primary" :loading="saving" :disabled="!sessionId" @click="openNameDialog">
          <template #icon><icon-safe /></template>
          {{ text.saveLoginState }}
        </a-button>
        <a-button @click="handleClose">{{ text.close }}</a-button>
      </div>
    </div>

    <!-- 保存登录态：自定义名称 -->
    <a-modal v-model:visible="nameVisible" :title="text.saveLoginState" :footer="false" width="420px">
      <a-form layout="vertical">
        <a-form-item :label="text.nameLabel">
          <a-input
            v-model="authName"
            :placeholder="text.namePlaceholder"
            :max-length="64"
            allow-clear
            @press-enter="submitSave"
          />
        </a-form-item>
      </a-form>
      <div class="auth-capture-actions">
        <a-button @click="nameVisible = false">{{ text.cancel }}</a-button>
        <a-button type="primary" :loading="saving" @click="submitSave">{{ text.create }}</a-button>
      </div>
    </a-modal>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconSafe } from '@arco-design/web-vue/es/icon'
import { useAppI18n } from '@/composables/useAppI18n'
import { recorderApi } from '../api'
import type { UiEnvironmentConfig } from '../types'
import { extractResponseData } from '../types'
import { uiWebSocket, UiSocketEnum } from '../services/websocket'

const props = defineProps<{
  visible: boolean
  env?: UiEnvironmentConfig | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'saved'): void
}>()

const { isEnglish } = useAppI18n()
const text = computed(() => (
  isEnglish.value
    ? {
        title: 'Record Login State',
        hint: 'Log in to the system in the view. After logging in, click "Save Login State" to capture cookies/localStorage for this environment.',
        saveLoginState: 'Save Login State',
        waiting: 'Waiting for browser…',
        close: 'Close',
        cancel: 'Cancel',
        create: 'Create',
        nameLabel: 'Login state name',
        namePlaceholder: 'Enter a name (leave empty to auto-generate)',
        saveSuccess: 'Login state saved, and will be injected automatically on execution',
        saveFailed: 'Failed to save login state',
        startFailed: 'Failed to start recorder browser',
      }
    : {
        title: '录制登录态',
        hint: '在画面中完成目标系统登录，登录成功后点击「保存登录态」，捕获该环境的 cookies/localStorage 供执行时自动注入。',
        saveLoginState: '保存登录态',
        waiting: '等待浏览器…',
        close: '关闭',
        cancel: '取消',
        create: '创建',
        nameLabel: '登录态名称',
        namePlaceholder: '填写登录态名称（留空自动生成）',
        saveSuccess: '登录态已保存，执行任务时将自动注入',
        saveFailed: '保存登录态失败',
        startFailed: '录制浏览器启动失败',
      }
))

// 画布（与录制画布同构）
const viewport = reactive({ width: 1400, height: 900 })
const canvasRef = ref<HTMLCanvasElement | null>(null)
const canvasWrapRef = ref<HTMLElement | null>(null)
const imeInputRef = ref<HTMLInputElement | null>(null)
const canvasSize = reactive({ width: 0, height: 0 })
const hasFrame = ref(false)
const sessionId = ref('')
const saving = ref(false)
const nameVisible = ref(false)
const authName = ref('')

const canvasStyle = computed(() => ({
  aspectRatio: `${viewport.width} / ${viewport.height}`,
  width: canvasSize.width ? `${canvasSize.width}px` : '100%',
  height: canvasSize.height ? `${canvasSize.height}px` : 'auto',
}))

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

function fitCanvas() {
  const wrap = canvasWrapRef.value
  if (!wrap) return
  const rect = wrap.getBoundingClientRect()
  if (rect.width < 2 || rect.height < 2 || !viewport.width || !viewport.height) return
  const ratio = viewport.width / viewport.height
  let cw = rect.width
  let ch = cw / ratio
  if (ch > rect.height) {
    ch = rect.height
    cw = ch * ratio
  }
  canvasSize.width = Math.floor(cw)
  canvasSize.height = Math.floor(ch)
}

function onRecorderFrame(data: any) {
  if (!props.visible) return
  const args = data?.data?.func_args || {}
  const frame = args.frame
  if (!frame?.data) return
  hasFrame.value = true
  if (viewport.width !== frame.w || viewport.height !== frame.h) {
    viewport.width = frame.w || viewport.width
    viewport.height = frame.h || viewport.height
  }
  fitCanvas()
  drawFrame(`data:image/jpeg;base64,${frame.data}`)
}

// ------------------------------------------------------------------
// 输入转发（与录制画布同构：鼠标/滚轮/键盘/输入法回放进录制浏览器）
// ------------------------------------------------------------------

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
  if (!sessionId.value) return
  keepImeFocused()
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
  if (!sessionId.value) return
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
  if (!sessionId.value) return
  const now = Date.now()
  if (now - lastMoveSent < 30) return
  lastMoveSent = now
  const { x, y } = canvasPoint(e)
  uiWebSocket.recorderInput({ type: 'mouse', event: 'move', x, y })
}

function onWheel(e: WheelEvent) {
  if (!sessionId.value) return
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
  if (!sessionId.value) return
  // 输入法组合期间/Process 等组合键不转发（最终文本走 compositionend 通道）
  if (e.isComposing || e.key === 'Process' || e.key === 'Unidentified' || e.key === 'Dead') return
  uiWebSocket.recorderInput({ type: 'key', event: 'down', key: e.key, code: e.code })
  if (['Enter', 'Tab', ' '].includes(e.key)) e.preventDefault()
}

function onKeyUp(e: KeyboardEvent) {
  if (!sessionId.value) return
  uiWebSocket.recorderInput({ type: 'key', event: 'up', key: e.key, code: e.code })
}

function onCompositionEnd(e: CompositionEvent) {
  if (!sessionId.value) return
  const text = e.data || ''
  if (text) {
    uiWebSocket.recorderInput({ type: 'text', text })
  }
}

function keepImeFocused() {
  requestAnimationFrame(() => {
    if (imeInputRef.value) imeInputRef.value.focus({ preventScroll: true })
  })
}

function bindCanvasListeners() {
  window.addEventListener('keydown', onKeyDown, true)
  window.addEventListener('keyup', onKeyUp, true)
  window.addEventListener('compositionend', onCompositionEnd, true)
  keepImeFocused()
}

function unbindCanvasListeners() {
  window.removeEventListener('keydown', onKeyDown, true)
  window.removeEventListener('keyup', onKeyUp, true)
  window.removeEventListener('compositionend', onCompositionEnd, true)
}

// ------------------------------------------------------------------
// 会话生命周期
// ------------------------------------------------------------------

async function startCapture() {
  if (!props.env) return
  sessionId.value = ''
  hasFrame.value = false
  try {
    await uiWebSocket.connect()
    const info = extractResponseData<{ session_id: string; viewport?: { width: number; height: number } } | null>(
      await recorderApi.authCapture(props.env.id),
    )
    if (!info) throw new Error(text.value.startFailed)
    sessionId.value = info.session_id
    if (info.viewport?.width && info.viewport?.height) {
      viewport.width = info.viewport.width
      viewport.height = info.viewport.height
    }
    uiWebSocket.recorderStart(info.session_id)
    bindCanvasListeners()
    nextTick(fitCanvas)
  } catch (e: any) {
    Message.error(e?.detail || e?.error || e?.message || text.value.startFailed)
    emit('update:visible', false)
  }
}

async function handleClose() {
  if (sessionId.value) {
    unbindCanvasListeners()
    try {
      uiWebSocket.recorderStop()
      await recorderApi.cancel(sessionId.value)
    } catch {
      // 忽略关闭失败（会话可能已结束）
    }
    sessionId.value = ''
  }
  emit('update:visible', false)
}

function openNameDialog() {
  authName.value = ''
  nameVisible.value = true
}

async function submitSave() {
  if (!sessionId.value) return
  saving.value = true
  const name = authName.value.trim() || undefined
  try {
    await recorderApi.saveLoginState(sessionId.value, name ? { name } : undefined)
    Message.success(text.value.saveSuccess)
    nameVisible.value = false
    // 保存成功：关闭会话并自动关闭录制画布
    unbindCanvasListeners()
    try {
      uiWebSocket.recorderStop()
      await recorderApi.cancel(sessionId.value)
    } catch {
      // 会话关闭失败不阻塞流程
    }
    sessionId.value = ''
    emit('saved')
    emit('update:visible', false)
  } catch (e: any) {
    Message.error(e?.detail || e?.error || e?.message || text.value.saveFailed)
  } finally {
    saving.value = false
  }
}

watch(() => props.visible, (v) => {
  if (v) {
    nextTick(startCapture)
  } else if (sessionId.value) {
    handleClose()
  }
})

let offFrame: (() => void) | null = null
let resizeObserver: ResizeObserver | null = null

onMounted(() => {
  offFrame = uiWebSocket.on(UiSocketEnum.RECORDER_FRAME, onRecorderFrame as any)
  resizeObserver = new ResizeObserver(() => fitCanvas())
  if (canvasWrapRef.value) resizeObserver.observe(canvasWrapRef.value)
})

onUnmounted(() => {
  offFrame?.()
  resizeObserver?.disconnect()
  resizeObserver = null
  unbindCanvasListeners()
})
</script>

<style scoped>
.auth-capture-live {
  display: flex;
  gap: 12px;
  height: min(560px, calc(70vh - 44px));
  min-height: 0;
  overflow: hidden;
}

.auth-capture-canvas-wrap {
  position: relative;
  flex: 1 1 auto;
  min-width: 0;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
  overflow: hidden;
  background: var(--color-bg-2);
}

.auth-capture-canvas {
  display: block;
  max-width: 100%;
  max-height: 100%;
  cursor: crosshair;
}

.auth-capture-ime-input {
  position: absolute;
  left: 0;
  top: 0;
  width: 1px;
  height: 1px;
  padding: 0;
  border: 0;
  outline: none;
  opacity: 0;
  pointer-events: none;
}

.auth-capture-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--color-text-2);
}

.auth-capture-side {
  flex: 0 0 220px;
  min-width: 180px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 4px 0;
}

.auth-capture-env {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.auth-capture-hint {
  font-size: 12px;
  color: var(--color-text-3);
  line-height: 1.6;
}

.auth-capture-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>