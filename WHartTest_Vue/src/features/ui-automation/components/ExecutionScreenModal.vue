<template>
  <a-modal
    :visible="visible"
    :title="title || text.title"
    :mask-closable="finished"
    width="min(1200px, calc(100vw - 24px))"
    @cancel="emit('update:visible', false)"
  >
    <!-- 执行画面（只读）：与录制器画布同构的帧展示，无输入转发 -->
    <div class="exec-screen-live">
      <div ref="canvasWrapRef" class="exec-screen-canvas-wrap">
        <canvas ref="canvasRef" class="exec-screen-canvas" :style="canvasStyle" />
        <div v-if="!hasFrame" class="exec-screen-overlay">
          <a-spin :loading="!finished" />
          <span>{{ finished ? text.done : text.waiting }}</span>
          <span v-if="noFrameHint" class="exec-screen-no-frame">{{ text.noFrameHint }}</span>
        </div>
        <div v-if="hasFrame" class="exec-screen-badge" :class="finished ? 'is-done' : 'is-running'">
          {{ finished ? text.done : text.running }}
        </div>
      </div>
    </div>
    <!-- 关闭按钮放 footer 插槽；状态由左上角角标展示 -->
    <template #footer>
      <div class="exec-screen-footer">
        <a-button @click="emit('update:visible', false)">{{ text.close }}</a-button>
      </div>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useAppI18n } from '@/composables/useAppI18n'
import { uiWebSocket, UiSocketEnum } from '../services/websocket'

const props = withDefaults(defineProps<{
  visible: boolean
  /** case=用例执行（按 case_id 收结果）；page-steps=页面步骤执行（按 page_step_id 收结果） */
  mode?: 'case' | 'page-steps'
  taskId?: number | null
  title?: string
}>(), { mode: 'case', taskId: null })

const emit = defineEmits<{ (e: 'update:visible', v: boolean): void }>()

const { isEnglish } = useAppI18n()
const text = computed(() => (
  isEnglish.value
    ? {
        title: 'Execution Screen',
        running: 'Executing…',
        done: 'Finished',
        waiting: 'Waiting for execution screen…',
        noFrameHint: 'No frames received. Make sure the actuator has been upgraded (frame_stream).',
        close: 'Close',
      }
    : {
        title: '执行画面',
        running: '执行中…',
        done: '执行完成',
        waiting: '等待执行画面…',
        noFrameHint: '未收到执行画面，请确认执行器已升级（含 frame_stream 帧采集）',
        close: '关闭',
      }
))

// ---------------------------------------------------------------
// 画布：帧绘制 + letterbox 自适应（与录制器 RecorderModal 同构）
// ---------------------------------------------------------------

const viewport = reactive({ width: 1400, height: 900 })
const canvasRef = ref<HTMLCanvasElement | null>(null)
const canvasWrapRef = ref<HTMLElement | null>(null)
const canvasSize = reactive({ width: 0, height: 0 })
const hasFrame = ref(false)
const finished = ref(false)
const noFrameHint = ref(false)
let noFrameTimer: ReturnType<typeof setTimeout> | null = null

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

// ---------------------------------------------------------------
// 订阅：执行画面帧 / 执行结束（按任务 id 过滤，避免与其它执行混淆）
// ---------------------------------------------------------------

function onExecFrame(data: any) {
  if (!props.visible) return
  const args = data?.data?.func_args || {}
  const frame = args.frame
  if (!frame?.data) return
  hasFrame.value = true
  noFrameHint.value = false
  if (noFrameTimer) {
    clearTimeout(noFrameTimer)
    noFrameTimer = null
  }
  if (viewport.width !== frame.w || viewport.height !== frame.h) {
    viewport.width = frame.w || viewport.width
    viewport.height = frame.h || viewport.height
  }
  // 每帧重算显示尺寸：弹窗开启动画期间计算出的瞬时小尺寸会在一帧内自愈，
  // 避免"第二次执行画面变小、四周黑边"（viewport 未变化时不触发重算的竞态）
  fitCanvas()
  drawFrame(`data:image/jpeg;base64,${frame.data}`)
}

function onResult(data: any) {
  if (!props.visible) return
  const args = data?.data?.func_args || {}
  const id = props.mode === 'case' ? args.case_id : args.page_step_id
  if (props.taskId && id === props.taskId) {
    finished.value = true
  }
}

watch(
  () => [props.visible, props.taskId],
  ([visible]) => {
    if (noFrameTimer) {
      clearTimeout(noFrameTimer)
      noFrameTimer = null
    }
    if (visible) {
      finished.value = false
      hasFrame.value = false
      noFrameHint.value = false
      // 15s 仍未收到任何帧：大概率执行器还没升级（旧执行器无帧采集）
      noFrameTimer = setTimeout(() => {
        if (!hasFrame.value) noFrameHint.value = true
      }, 15000)
      nextTick(fitCanvas)
    }
  },
)

let offFrame: (() => void) | null = null
let offCase: (() => void) | null = null
let offStep: (() => void) | null = null
let resizeObserver: ResizeObserver | null = null

onMounted(() => {
  offFrame = uiWebSocket.on(UiSocketEnum.EXEC_FRAME, onExecFrame as any)
  offCase = uiWebSocket.on(UiSocketEnum.CASE_RESULT, onResult as any)
  offStep = uiWebSocket.on(UiSocketEnum.PAGE_STEP_RESULT, onResult as any)
  resizeObserver = new ResizeObserver(() => fitCanvas())
  if (canvasWrapRef.value) resizeObserver.observe(canvasWrapRef.value)
  nextTick(fitCanvas)
})

onUnmounted(() => {
  offFrame?.()
  offCase?.()
  offStep?.()
  resizeObserver?.disconnect()
  resizeObserver = null
  if (noFrameTimer) {
    clearTimeout(noFrameTimer)
    noFrameTimer = null
  }
})
</script>

<style scoped>
.exec-screen-live {
  /* body 内只有画布区（状态栏在 footer 插槽）：高度 min(700px, 70vh-44px)
     保证 body 内容永不超全局 70vh 限高，不出现右侧滚动条；
     700px 与 1400:900 画布比例匹配（1200 弹窗宽度下画布恰好铺满，无左右深色留白） */
  height: min(700px, calc(70vh - 44px));
  min-height: 0;
  overflow: hidden;
  display: flex;
}

.exec-screen-canvas-wrap {
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
  /* 留白处与弹窗面板同色（深浅主题自适应），避免 letterbox 深色区块 */
  background: var(--color-bg-2);
}

.exec-screen-canvas {
  display: block;
  max-width: 100%;
  max-height: 100%;
}

.exec-screen-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--color-text-2);
}

.exec-screen-badge {
  position: absolute;
  top: 12px;
  left: 12px;
  padding: 2px 10px;
  border-radius: 10px;
  color: #fff;
  font-size: 12px;
}

.exec-screen-badge.is-running {
  background: rgba(22, 93, 255, 0.85);
}

.exec-screen-badge.is-done {
  background: rgba(18, 150, 70, 0.85);
}

.exec-screen-no-frame {
  font-size: 12px;
  color: var(--color-warning-6);
}

.exec-screen-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
}
</style>