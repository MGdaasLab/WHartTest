<template>
  <a-modal
    :visible="visible"
    :title="text.title"
    :footer="false"
    :mask-closable="!recording && !starting"
    :closable="!starting"
    :width="phase === 'setup' ? 620 : 'min(1400px, calc(100vw - 24px))'"
    @cancel="handleCancel"
  >
    <!-- 阶段1：录制参数表单 -->
    <div v-if="phase === 'setup'" class="recorder-setup">
      <a-form :model="form" layout="vertical">
        <a-form-item :label="text.page" :required="true">
          <div class="recorder-select-with-add">
            <a-select
              v-model="form.page_id"
              :options="pageOptions"
              :placeholder="text.selectPage"
              allow-search
              allow-clear
              :loading="loadingPages"
              class="flex-1"
              @change="onPageChange"
            />
            <a-button type="outline" size="small" :disabled="starting" :title="text.addPage" @click="openAddPage">
              <template #icon><icon-plus /></template>
            </a-button>
          </div>
        </a-form-item>
        <a-form-item :label="text.pageStep" :required="true">
          <div class="recorder-select-with-add">
            <a-select
              v-model="form.page_step_id"
              :options="stepOptions"
              :placeholder="text.selectPageStep"
              allow-search
              allow-clear
              :loading="loadingSteps"
              class="flex-1"
            />
            <a-button type="outline" size="small" :disabled="starting" :title="text.addPageStep" @click="openAddStep">
              <template #icon><icon-plus /></template>
            </a-button>
          </div>
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
        <a-form-item :label="text.preStep">
          <a-select
            v-model="form.pre_page_step_id"
            :options="preStepOptions"
            :placeholder="text.preStepPlaceholder"
            allow-search
            allow-clear
            :loading="loadingPreSteps"
          />
          <div class="recorder-form-hint">{{ text.preStepHint }}</div>
        </a-form-item>
      </a-form>
      <div class="recorder-setup-actions">
        <a-button :disabled="starting" @click="handleCancel">{{ text.cancel }}</a-button>
        <a-button type="primary" :loading="starting" @click="handleStart">
          {{ text.startRecord }}
        </a-button>
      </div>
    </div>

    <!-- 快捷新增页面 -->
    <a-modal
      :visible="addPageVisible"
      :title="text.addPage"
      :footer="false"
      :mask-closable="!addPageSubmitting"
      :closable="!addPageSubmitting"
      width="480px"
      @cancel="addPageVisible = false"
    >
      <a-form :model="addPageForm" layout="vertical">
        <a-form-item :label="text.module" :required="true">
          <a-select
            v-model="addPageForm.module"
            :options="moduleFlatOptions"
            :placeholder="text.selectModule"
            allow-search
            allow-clear
          />
        </a-form-item>
        <a-form-item :label="text.pageName" :required="true">
          <a-input v-model="addPageForm.name" :placeholder="text.enterPageName" :max-length="64" allow-clear />
        </a-form-item>
        <a-form-item :label="text.pageUrl">
          <a-input v-model="addPageForm.url" :placeholder="text.enterPageUrl" allow-clear />
        </a-form-item>
      </a-form>
      <div class="recorder-setup-actions">
        <a-button :disabled="addPageSubmitting" @click="addPageVisible = false">{{ text.cancel }}</a-button>
        <a-button type="primary" :loading="addPageSubmitting" @click="submitAddPage">{{ text.create }}</a-button>
      </div>
    </a-modal>

    <!-- 快捷新增页面步骤 -->
    <a-modal
      :visible="addStepVisible"
      :title="text.addPageStep"
      :footer="false"
      :mask-closable="!addStepSubmitting"
      :closable="!addStepSubmitting"
      width="480px"
      @cancel="addStepVisible = false"
    >
      <a-form :model="addStepForm" layout="vertical">
        <a-form-item :label="text.stepName" :required="true">
          <a-input v-model="addStepForm.name" :placeholder="text.enterStepName" :max-length="64" allow-clear />
        </a-form-item>
        <a-form-item :label="text.description">
          <a-textarea v-model="addStepForm.description" :placeholder="text.enterDescription" :auto-size="{ minRows: 2 }" />
        </a-form-item>
      </a-form>
      <div class="recorder-setup-actions">
        <a-button :disabled="addStepSubmitting" @click="addStepVisible = false">{{ text.cancel }}</a-button>
        <a-button type="primary" :loading="addStepSubmitting" @click="submitAddStep">{{ text.create }}</a-button>
      </div>
    </a-modal>

    <!-- 阶段2：录制视图 -->
    <div v-if="phase !== 'setup'" class="recorder-live">
      <div class="recorder-canvas-wrap">
        <canvas
          ref="canvasRef"
          class="recorder-canvas"
          :style="{ aspectRatio: `${viewport.width} / ${viewport.height}` }"
          @pointerdown="onPointerDown"
          @pointerup="onPointerUp"
          @pointermove="onPointerMove"
          @wheel="onWheel"
        />
        <!-- 隐藏输入法载体：保持聚焦让中文输入法正常组合（compositionend 拿到最终文本） -->
        <input
          ref="imeInputRef"
          class="recorder-ime-input"
          @keydown.stop
          @keyup.stop
        />
        <div v-if="!firstFrame" class="recorder-loading-overlay">
          <a-spin :loading="true" />
          <span>{{ text.connecting }}</span>
        </div>
      </div>

      <div class="recorder-side">
        <div class="recorder-toolbar">
          <a-select
            v-model="assertMode"
            size="small"
            style="width: 140px"
            @change="onAssertModeChange"
          >
            <a-option-group :label="text.assertGroupState">
              <a-option v-for="o in assertStateOptions" :key="o.value" :value="o.value">{{ o.label }}</a-option>
            </a-option-group>
            <a-option-group :label="text.assertGroupContent">
              <a-option v-for="o in assertContentOptions" :key="o.value" :value="o.value">{{ o.label }}</a-option>
            </a-option-group>
            <a-option-group :label="text.assertGroupPage">
              <a-option v-for="o in assertPageOptions" :key="o.value" :value="o.value">{{ o.label }}</a-option>
            </a-option-group>
          </a-select>
          <a-input
            v-if="needAssertValue"
            v-model="assertValue"
            :placeholder="assertValuePlaceholder"
            size="small"
            style="width: 130px"
            allow-clear
          />
          <a-button
            type="primary"
            :status="assertActive ? 'warning' : undefined"
            size="small"
            :disabled="!recording"
            @click="handleAssert"
          >
            {{ assertActive ? text.assertPickElement : text.assert }}
          </a-button>
          <a-dropdown :disabled="!recording" @select="handleAddWait">
            <a-button size="small" :disabled="!recording">
              <template #icon><icon-clock-circle /></template>
              {{ text.wait }}
            </a-button>
            <template #content>
              <a-doption v-for="sec in waitOptions" :key="sec" :value="sec">{{ text.waitSeconds(sec) }}</a-doption>
            </template>
          </a-dropdown>
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
            <a-button
              type="text"
              size="mini"
              class="recorder-action-delete"
              :title="text.removeAction"
              @click="removeAction(a)"
            >
              <template #icon><icon-delete /></template>
            </a-button>
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
import { IconDelete, IconClockCircle } from '@arco-design/web-vue/es/icon'
import { useAppI18n } from '@/composables/useAppI18n'
import { useProjectStore } from '@/store/projectStore'
import { pageApi, pageStepsApi, envConfigApi, moduleApi, recorderApi } from '../api'
import type { RecorderSessionInfo, RecorderFinishResult } from '../api'
import type { UiPage, UiPageSteps, UiEnvironmentConfig, UiModule, UiPageForm, UiPageStepsForm } from '../types'
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
        preStep: 'Pre-step (optional)',
        preStepPlaceholder: 'Select a page step to auto-run before recording',
        preStepHint: 'Auto executes this step (e.g. login) before recording starts; its actions are not recorded.',
        cancel: 'Cancel',
        startRecord: 'Start Recording',
        connecting: 'Connecting to browser...',
        preparing: 'Preparing browser...',
        assert: 'Assert',
        assertPickElement: 'Click an element in the view…',
        assertGroupState: 'Element state',
        assertGroupContent: 'Content check',
        assertGroupPage: 'Page check',
        assertHidden: 'Hidden',
        assertDisabled: 'Disabled',
        assertChecked: 'Checked',
        assertText: 'Has text',
        assertValue: 'Has value',
        assertCount: 'Count equals',
        assertUrl: 'URL equals',
        assertTitle: 'Title equals',
        assertContentPlaceholder: 'Expected text/value',
        assertUrlPlaceholder: 'Expected URL (empty = current)',
        assertTitlePlaceholder: 'Expected title',
        assertCountPlaceholder: 'Expected count',
        assertTitleRequired: 'Enter the expected title',
        assertValueRequired: 'Enter the content to check',
        assertModeHint: 'Assert mode: click the target element in the browser view',
        preFailed: 'Pre-step failed, please check its definition',
        wait: 'Wait',
        waitSeconds: (sec: number) => `${sec}s`,
        addPage: 'New page',
        addPageStep: 'New page step',
        module: 'Module',
        selectModule: 'Select module',
        pageName: 'Page name',
        enterPageName: 'Enter page name',
        pageUrl: 'Page URL',
        enterPageUrl: 'Enter page URL (optional)',
        stepName: 'Step name',
        enterStepName: 'Enter step name',
        description: 'Description',
        enterDescription: 'Enter description (optional)',
        create: 'Create',
        createSuccess: 'Created successfully',
        createFailed: 'Creation failed',
        modulePageRequired: 'Select a module and enter a page name',
        selectPageFirst: 'Select a page first',
        finishRecord: 'Finish',
        recordHint: 'Operate in the browser view below. Hover an element then click Assert to record an assertion.',
        noActions: 'No actions yet. Operate in the browser view.',
        confirmCancel: 'Cancel recording? The unfinished recording will be discarded.',
        startFailed: 'Failed to start recording',
        finishFailed: 'Failed to finish recording',
        finishSuccess: 'Recording saved',
        stats: 'Actions: {actions}, elements: +{elements}, steps: +{steps}',
        assertRecorded: 'Assertion recorded',
        assertFailed: 'Assertion failed',
        assertVisible: 'Visible',
        assertContainText: 'Contains text',
        assertEnabled: 'Enabled',
        emptyPageSteps: 'This page has no page steps yet',
        selectedEnvNoUrl: 'The selected environment has no base URL. Pick one with an address, or set the base URL in environment config.',
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
        preStep: '前置步骤（可选）',
        preStepPlaceholder: '选择录制前自动执行的页面步骤',
        preStepHint: '开始录制前自动执行该步骤（如登录），执行过程不会进入录制动作。',
        cancel: '取消',
        startRecord: '开始录制',
        connecting: '正在连接浏览器…',
        preparing: '正在准备浏览器…',
        assert: '断言',
        assertPickElement: '请在画面中点击元素…',
        removeAction: '删除此操作',
        assertGroupState: '元素状态',
        assertGroupContent: '内容校验',
        assertGroupPage: '页面校验',
        assertHidden: '元素隐藏',
        assertDisabled: '元素不可用',
        assertChecked: '已勾选',
        assertText: '文本等于',
        assertValue: '值等于',
        assertCount: '数量等于',
        assertUrl: 'URL等于',
        assertTitle: '标题等于',
        assertContentPlaceholder: '期望的文本/值',
        assertUrlPlaceholder: '期望 URL（留空=当前）',
        assertTitlePlaceholder: '期望标题',
        assertCountPlaceholder: '期望数量',
        assertTitleRequired: '请输入要断言的页面标题',
        assertValueRequired: '请输入要校验的内容',
        assertModeHint: '断言模式：请在左侧画面中点击要断言的元素',
        preFailed: '前置步骤执行失败，请检查步骤定义',
        wait: '等待',
        waitSeconds: (sec: number) => `${sec} 秒`,
        addPage: '新增页面',
        addPageStep: '新增页面步骤',
        module: '所属模块',
        selectModule: '请选择模块',
        pageName: '页面名称',
        enterPageName: '请输入页面名称',
        pageUrl: '页面 URL',
        enterPageUrl: '请输入页面 URL（可选）',
        stepName: '步骤名称',
        enterStepName: '请输入步骤名称',
        description: '描述',
        enterDescription: '请输入描述（可选）',
        create: '创建',
        createSuccess: '创建成功',
        createFailed: '创建失败',
        modulePageRequired: '请选择模块并填写页面名称',
        selectPageFirst: '请先选择页面',
        finishRecord: '结束录制',
        recordHint: '在左侧浏览器画面中操作；悬停目标元素后点击「断言」可记录断言。',
        noActions: '暂无动作，请在浏览器画面中操作',
        confirmCancel: '确定取消录制？未完成的录制将被丢弃。',
        startFailed: '启动录制失败',
        finishFailed: '结束录制失败',
        finishSuccess: '录制已保存',
        stats: '动作 {actions} 个，新增元素 {elements} 个，新增步骤 {steps} 个',
        assertRecorded: '断言已记录',
        assertFailed: '断言失败',
        assertVisible: '元素可见',
        assertContainText: '包含文本',
        assertEnabled: '元素可用',
        emptyPageSteps: '该页面下还没有页面步骤',
        selectedEnvNoUrl: '所选环境未配置基础 URL，请选择带地址的环境，或在环境配置中填写 base_url',
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
  pre_page_step_id: undefined as number | undefined,
})

const projectId = computed(() => props.projectId ?? useProjectStore().currentProject?.id)

// ---- 快捷新增页面/步骤 ----
const addPageVisible = ref(false)
const addStepVisible = ref(false)
const addPageSubmitting = ref(false)
const addStepSubmitting = ref(false)
const addPageForm = reactive<Partial<UiPageForm>>({
  project: 0,
  module: undefined,
  name: '',
  url: '',
})
const addStepForm = reactive<Partial<UiPageStepsForm>>({
  project: 0,
  page: undefined,
  name: '',
  description: '',
})

const moduleFlatOptions = computed(() => {
  const out: Array<{ label: string; value: number }> = []
  const walk = (modules: UiModule[], level: number) => {
    for (const m of modules) {
      out.push({ label: `${'　'.repeat(level)}${m.name}`, value: m.id })
      if (m.children?.length) walk(m.children, level + 1)
    }
  }
  walk(moduleOptions.value, 0)
  return out
})

async function fetchModules() {
  if (!projectId.value || moduleOptions.value.length) return
  loadingModules.value = true
  try {
    const res = await moduleApi.tree(projectId.value)
    moduleOptions.value = extractListData<UiModule>(res)
  } catch (_) {
    // 模块为可选项，拉取失败不阻塞
  } finally {
    loadingModules.value = false
  }
}

function openAddPage() {
  addPageForm.project = projectId.value || 0
  addPageForm.module = undefined
  addPageForm.name = ''
  addPageForm.url = ''
  fetchModules()
  addPageVisible.value = true
}

async function submitAddPage() {
  if (!addPageForm.module || !addPageForm.name?.trim()) {
    Message.warning(text.value.modulePageRequired)
    return
  }
  addPageSubmitting.value = true
  try {
    const res = await pageApi.create(addPageForm as UiPageForm)
    const created = extractResponseData<UiPage>(res)
    if (!created) throw new Error(text.value.createFailed)
    addPageVisible.value = false
    // 刷新页面列表并自动选中新页面，联动加载其步骤
    const listRes = await pageApi.list({ project: projectId.value })
    pageOptions.value = extractListData<UiPage>(listRes).map((p) => ({
      label: p.name,
      value: p.id,
      module: p.module,
    }))
    form.page_id = created.id
    fetchSteps(created.id)
    Message.success(text.value.createSuccess)
  } catch (e: any) {
    Message.error(e?.error || e?.message || text.value.createFailed)
  } finally {
    addPageSubmitting.value = false
  }
}

function openAddStep() {
  if (!form.page_id) {
    Message.warning(text.value.selectPageFirst)
    return
  }
  const pickedPage = pageOptions.value.find((p) => p.value === form.page_id)
  addStepForm.project = projectId.value || 0
  addStepForm.page = form.page_id
  addStepForm.module = pickedPage?.module
  addStepForm.name = ''
  addStepForm.description = ''
  addStepVisible.value = true
}

async function submitAddStep() {
  if (!addStepForm.name?.trim()) {
    Message.warning(text.value.enterStepName)
    return
  }
  addStepSubmitting.value = true
  try {
    const res = await pageStepsApi.create(addStepForm as UiPageStepsForm)
    const created = extractResponseData<UiPageSteps>(res)
    if (!created) throw new Error(text.value.createFailed)
    addStepVisible.value = false
    // 刷新步骤列表并自动选中新步骤
    fetchSteps(form.page_id!)
    form.page_step_id = created.id
    Message.success(text.value.createSuccess)
  } catch (e: any) {
    Message.error(e?.error || e?.message || text.value.createFailed)
  } finally {
    addStepSubmitting.value = false
  }
}

const loadingPages = ref(false)
const loadingSteps = ref(false)
const loadingEnvs = ref(false)
const loadingPreSteps = ref(false)
const loadingModules = ref(false)
const pageOptions = ref<Array<{ label: string; value: number; module?: number }>>([])
const preStepOptions = ref<Array<{ label: string; value: number }>>([])
const moduleOptions = ref<UiModule[]>([])
const stepOptions = ref<Array<{ label: string; value: number }>>([])
const envOptions = ref<Array<{ label: string; value: number; base_url?: string | null }>>([])

const sessionId = ref('')
const viewport = reactive({ width: 1400, height: 900 })
const actions = ref<Array<Record<string, any>>>([])
const firstFrame = ref(false)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const imeInputRef = ref<HTMLInputElement | null>(null)
const lastFrameData = ref('')

const assertMode = ref('visible')
const assertValue = ref('')
const assertActive = ref(false)   // 断言模式：激活后下一次画布点击用于定位断言目标

// 断言方法三分类（与执行器 assert_* 词汇表对齐）
const assertStateOptions = computed(() => [
  { label: text.value.assertVisible, value: 'visible' },
  { label: text.value.assertHidden, value: 'hidden' },
  { label: text.value.assertEnabled, value: 'enabled' },
  { label: text.value.assertDisabled, value: 'disabled' },
  { label: text.value.assertChecked, value: 'checked' },
])
const assertContentOptions = computed(() => [
  { label: text.value.assertText, value: 'text' },
  { label: text.value.assertContainText, value: 'contain_text' },
  { label: text.value.assertValue, value: 'value' },
  { label: text.value.assertCount, value: 'count' },
])
const assertPageOptions = computed(() => [
  { label: text.value.assertUrl, value: 'url' },
  { label: text.value.assertTitle, value: 'title' },
])

// 内容校验与页面校验需要输入期望值
const ASSERT_NEEDS_VALUE = ['text', 'contain_text', 'value', 'count', 'url', 'title']
const needAssertValue = computed(() => ASSERT_NEEDS_VALUE.includes(assertMode.value))
const assertValuePlaceholder = computed(() => {
  if (assertMode.value === 'url') return text.value.assertUrlPlaceholder
  if (assertMode.value === 'title') return text.value.assertTitlePlaceholder
  if (assertMode.value === 'count') return text.value.assertCountPlaceholder
  return text.value.assertContentPlaceholder
})

function onAssertModeChange() {
  assertActive.value = false
  assertValue.value = ''
}

// ------------------------------------------------------------------
// 表单数据
// ------------------------------------------------------------------

async function fetchPages() {
  if (!projectId.value) return
  loadingPages.value = true
  try {
    const res = await pageApi.list({ project: projectId.value })
    const list = extractListData<UiPage>(res)
    pageOptions.value = list.map((p) => ({ label: p.name, value: p.id, module: p.module }))
  } catch (e: any) {
    Message.error(e?.error || e?.message || text.value.startFailed)
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
    Message.error(e?.error || e?.message || text.value.startFailed)
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
    envOptions.value = list.map((e) => ({
      label: e.base_url ? `${e.name}（${e.base_url}）` : e.name,
      value: e.id,
      base_url: e.base_url,
    }))
    if (!form.env_config_id && list.length > 0) {
      // 优先选择带基础 URL 的环境（录制需要导航地址）
      const withUrl = list.filter((e) => e.base_url)
      const def = withUrl.find((e) => e.is_default) || withUrl[0] || list[0]
      form.env_config_id = def.id
    }
  } catch (e: any) {
    Message.error(e?.error || e?.message || text.value.startFailed)
  } finally {
    loadingEnvs.value = false
  }
}

async function fetchPreSteps() {
  if (!projectId.value) return
  loadingPreSteps.value = true
  try {
    const res = await pageStepsApi.list({ project: projectId.value })
    const list = extractListData<UiPageSteps>(res)
    preStepOptions.value = list.map((s) => ({
      label: s.page_name ? `${s.name}（${s.page_name}）` : s.name,
      value: s.id,
    }))
  } catch (e: any) {
    // 前置步骤为可选项，拉取失败不阻塞录制
  } finally {
    loadingPreSteps.value = false
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
      fetchPreSteps()
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
  form.pre_page_step_id = undefined
  stepOptions.value = []
  sessionId.value = ''
  actions.value = []
  firstFrame.value = false
  assertActive.value = false
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
  const pickedEnv = envOptions.value.find((e) => e.value === form.env_config_id)
  if (pickedEnv && !pickedEnv.base_url) {
    Message.warning(text.value.selectedEnvNoUrl)
    return
  }
  starting.value = true
  try {
    const info = extractResponseData<RecorderSessionInfo>(await recorderApi.create({
      env_config_id: form.env_config_id,
      page_id: form.page_id,
      page_step_id: form.page_step_id,
      pre_page_step_id: form.pre_page_step_id,
    }))
    if (!info) throw new Error(text.value.startFailed)
    if (info.pre_failed) Message.error(text.value.preFailed)
    sessionId.value = info.session_id
    viewport.width = info.viewport?.width || 1400
    viewport.height = info.viewport?.height || 900

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
    keepImeFocused()
  } catch (e: any) {
    Message.error(e?.error || e?.message || text.value.startFailed)
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
    emit('refresh')
    closeModal()
  } catch (e: any) {
    Message.error(e?.error || e?.message || text.value.finishFailed)
  } finally {
    finishing.value = false
  }
}

function handleCancel() {
  if (recording.value || starting.value) {
    Modal.confirm({
      title: text.value.confirmCancel,
      content: '',
      modalClass: 'recorder-confirm-modal',
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
  keepImeFocused()
  const { x, y } = canvasPoint(e)
  if (assertActive.value) {
    // 断言模式：本次点击只用于定位断言目标，不记录普通点击
    assertActive.value = false
    uiWebSocket.recorderAssert(assertMode.value, x, y, assertValue.value.trim() || undefined)
    return
  }
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
  // 输入法组合期间/Process 等组合键不转发（最终文本走 compositionend 通道）
  if (e.isComposing || e.key === 'Process' || e.key === 'Unidentified' || e.key === 'Dead') return
  uiWebSocket.recorderInput({ type: 'key', event: 'down', key: e.key, code: e.code })
  if (['Enter', 'Tab', ' '].includes(e.key)) e.preventDefault()
}

function onCompositionEnd(e: CompositionEvent) {
  if (!recording.value) return
  const text = e.data || ''
  if (text) {
    uiWebSocket.recorderInput({ type: 'text', text })
  }
}

function onKeyUp(e: KeyboardEvent) {
  if (!recording.value) return
  uiWebSocket.recorderInput({ type: 'key', event: 'up', key: e.key, code: e.code })
}

function keepImeFocused() {
  // 保持隐藏输入框聚焦：浏览器输入法需要真实输入框才会进入组合模式
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
// 断言 & 动作展示
// ------------------------------------------------------------------

const waitOptions = [2, 3, 5, 10]

function handleAddWait(seconds: number) {
  if (!recording.value) return
  if (!uiWebSocket.recorderAddWait(seconds)) {
    Message.error(text.value.finishFailed)
  }
}

function handleAssert() {
  if (!recording.value) return
  // 页面校验（URL/标题）：不需要选元素，直接记录断言
  if (assertMode.value === 'url' || assertMode.value === 'title') {
    if (assertMode.value === 'title' && !assertValue.value.trim()) {
      Message.warning(text.value.assertTitleRequired)
      return
    }
    uiWebSocket.recorderAssert(assertMode.value, undefined, undefined, assertValue.value.trim())
    return
  }
  // 内容校验需输入期望值
  if (needAssertValue.value && !assertValue.value.trim()) {
    Message.warning(text.value.assertValueRequired)
    return
  }
  // 进入断言模式：下一次画布点击定位要断言的元素
  assertActive.value = true
  Message.info(text.value.assertModeHint)
}

function removeAction(a: Record<string, any>) {
  // 本地即时移除 + 通知录制进程同步删除（保证落盘脚本一致）
  actions.value = actions.value.filter((x) => x.seq !== a.seq)
  uiWebSocket.recorderRemoveAction(a.seq)
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
  if (a.type === 'assert') {
    const modeMap: Record<string, string> = isEnglish.value
      ? {
          visible: 'Visible', hidden: 'Hidden', enabled: 'Enabled', disabled: 'Disabled', checked: 'Checked',
          text: 'Has text', contain_text: 'Contains text', value: 'Has value', count: 'Count equals',
          url: 'URL equals', title: 'Title equals',
        }
      : {
          visible: '元素可见', hidden: '元素隐藏', enabled: '元素可用', disabled: '元素不可用', checked: '已勾选',
          text: '文本等于', contain_text: '包含文本', value: '值等于', count: '数量等于',
          url: 'URL等于', title: '标题等于',
        }
    return modeMap[a.mode] || '断言'
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
  if (a.type === 'wait') return `${a.seconds || 1} ${isEnglish.value ? 's' : '秒'}`
  if (a.type === 'goto') return String(a.url || '')
  if (a.type === 'fill') return `${sel?.name || sel?.locator_value || ''} = ${a.value || ''}`
  if (a.type === 'press') return `${sel?.name || sel?.locator_value || ''} [${a.key || 'Enter'}]`
  if (a.type === 'assert') {
    if (a.mode === 'url' || a.mode === 'title') return String(a.value || '')
    const how = ['text', 'contain_text', 'value', 'count'].includes(a.mode) && a.value ? `: ${a.value}` : ''
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
  if (!props.visible) return
  const action = data?.data?.func_args?.action
  if (!action) return
  // 连续输入合并时同一 seq 会推送更新版本，按 seq 原地替换
  const idx = actions.value.findIndex((a) => a.seq === action.seq)
  if (idx >= 0) {
    actions.value[idx] = action
  } else {
    actions.value.push(action)
  }
}

function onRecorderStatus(data: any) {
  if (!props.visible) return
  const args = data?.data?.func_args || {}
  const status = args.status
  if (status === 'error') {
    assertActive.value = false
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


.recorder-select-with-add {
  display: flex;
  gap: 8px;
  align-items: center;
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
  min-height: 640px;
  max-height: 86vh;
}

.recorder-canvas-wrap {
  position: relative;
  flex: 1 1 auto;
  min-width: 0;
  align-self: flex-start;
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
  overflow: hidden;
  background: #111;
}

.recorder-ime-input {
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

.recorder-canvas {
  display: block;
  width: 100%;
  height: auto;
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

.recorder-side {
  flex: 0 1 300px;
  min-width: 220px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.recorder-toolbar {
  display: flex;
  flex-wrap: wrap;
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
  max-height: 560px;
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