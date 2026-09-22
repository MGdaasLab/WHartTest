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
        <!-- 页面 + 页面步骤 一行两列；各行尾部统一 28px 槽位（按钮/占位/图标），
             保证所有选择框宽度一致（等于列宽 - 槽位 - 间距） -->
        <div class="recorder-form-row">
          <a-form-item :label="text.page" :required="true" class="recorder-form-col">
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
          <a-form-item :label="text.pageStep" :required="true" class="recorder-form-col">
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
            <!-- 问号提示放 label 行（template #label），不占控件行尾槽位，
                 保证该行选择框与页面行等宽 -->
            <template #label>
              {{ text.pageStep }}
              <a-tooltip :content="text.pageStepHint" position="top">
                <span class="recorder-hint-icon recorder-hint-icon-label"><icon-question-circle /></span>
              </a-tooltip>
            </template>
          </a-form-item>
        </div>
        <!-- 环境 + 登录态 一行两列 -->
        <div class="recorder-form-row">
          <a-form-item :label="text.environment" :required="true" class="recorder-form-col">
            <div class="recorder-select-with-add">
              <a-select
                v-model="form.env_config_id"
                :options="envOptions"
                :placeholder="text.selectEnvironment"
                allow-search
                allow-clear
                :loading="loadingEnvs"
                class="flex-1"
              />
              <span class="recorder-hint-slot">
                <a-tooltip :content="text.envHint" position="top">
                  <span class="recorder-hint-icon"><icon-question-circle /></span>
                </a-tooltip>
              </span>
            </div>
          </a-form-item>
          <a-form-item :label="text.authState" class="recorder-form-col">
            <div class="recorder-select-with-add">
              <a-select
                v-model="form.auth_state_id"
                :options="authStateOptions"
                :placeholder="text.authStatePlaceholder"
                allow-search
                allow-clear
                class="flex-1"
              />
              <span class="recorder-select-spacer" aria-hidden="true" />
            </div>
          </a-form-item>
        </div>
        <!-- 前置步骤：单列行按半列宽限制，控件宽度与其余行一致 -->
        <div class="recorder-form-row">
          <a-form-item :label="text.preStep" class="recorder-form-col">
            <div class="recorder-select-with-add">
              <a-select
                v-model="form.pre_page_step_id"
                :options="preStepOptions"
                :placeholder="text.preStepPlaceholder"
                allow-search
                allow-clear
                :loading="loadingPreSteps"
                class="flex-1"
              />
              <span class="recorder-hint-slot">
                <a-tooltip :content="text.preStepHint" position="top">
                  <span class="recorder-hint-icon"><icon-question-circle /></span>
                </a-tooltip>
              </span>
            </div>
          </a-form-item>
        </div>
      </a-form>
      <div class="recorder-setup-actions">
        <a-button :disabled="starting" @click="handleCancel">{{ text.cancel }}</a-button>
        <a-button type="primary" :loading="starting" @click="handleStart">
          {{ text.startRecord }}
        </a-button>
      </div>
    </div>

    <!-- 上传文件选择弹窗（本地 / 平台文件） -->
    <a-modal
      :visible="uploadDialogVisible"
      :title="text.upload"
      :footer="false"
      width="520px"
      @cancel="uploadDialogVisible = false"
    >
      <a-radio-group v-model="uploadSource" type="button" class="upload-source-tabs">
        <a-radio value="local">{{ text.uploadLocal }}</a-radio>
        <a-radio value="platform">{{ text.uploadPlatform }}</a-radio>
      </a-radio-group>
      <div v-if="uploadSource === 'local'" class="upload-local-box">
        <a-button type="outline" :loading="uploadingFile" @click="pickLocalFile">
          <template #icon><icon-upload /></template>
          {{ text.uploadPickLocal }}
        </a-button>
        <div class="upload-hint">{{ text.uploadLocalHint }}</div>
        <input ref="localFileInput" type="file" style="display: none" @change="onLocalFileChange" />
      </div>
      <div v-else class="upload-platform-box">
        <a-select
          v-model="selectedPlatformFileId"
          :options="platformFiles.map(f => ({ label: f.original_name || f.name, value: f.id }))"
          :placeholder="text.uploadSelectPlatform"
          allow-search
          style="width: 100%"
        />
        <div class="upload-hint">{{ text.uploadPlatformHint }}</div>
      </div>
      <div class="recorder-setup-actions">
        <a-button @click="uploadDialogVisible = false">{{ text.cancel }}</a-button>
        <a-button type="primary" :disabled="uploadSource === 'platform' && !selectedPlatformFileId" @click="confirmPlatformFile">
          {{ text.uploadConfirm }}
        </a-button>
      </div>
    </a-modal>

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
      <div ref="canvasWrapRef" class="recorder-canvas-wrap">
        <canvas
          ref="canvasRef"
          class="recorder-canvas"
          :style="canvasStyle"
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
          <!-- 第一行：断言（模式下拉 + 期望值输入 + 断言按钮） -->
          <div class="recorder-toolbar-row">
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
              class="recorder-assert-btn"
              type="primary"
              :status="assertActive ? 'warning' : undefined"
              size="small"
              :disabled="!recording"
              :title="assertActive ? text.assertPickElement : undefined"
              @click="handleAssert"
            >
              <!-- Arco 按钮文字是裸文本节点，必须自包 span 才能做省略号截断 -->
              <span class="recorder-btn-label">{{ assertActive ? text.assertPickElement : text.assert }}</span>
            </a-button>
          </div>
          <!-- 第二行：等待（独立） + 更多操作（上传文件/保存登录态收纳于此） -->
          <div class="recorder-toolbar-row">
            <a-dropdown :disabled="!recording" @select="handleAddWait">
              <a-button size="small" :disabled="!recording">
                <template #icon><icon-clock-circle /></template>
                {{ text.wait }}
              </a-button>
              <template #content>
                <a-doption v-for="sec in waitOptions" :key="sec" :value="sec">{{ text.waitSeconds(sec) }}</a-doption>
              </template>
            </a-dropdown>
            <a-dropdown :disabled="!recording" @select="onMoreActionSelect">
              <a-button size="small" :disabled="!recording">
                {{ text.moreActions }}
                <template #icon><icon-down /></template>
              </a-button>
              <template #content>
                <a-doption value="upload" :disabled="!recording">
                  <template #icon><icon-upload /></template>
                  {{ text.upload }}
                </a-doption>
                <a-doption value="saveLoginState" :disabled="!recording">
                  <template #icon><icon-safe /></template>
                  {{ text.saveLoginState }}
                </a-doption>
              </template>
            </a-dropdown>
          </div>
          <!-- 第三行：结束录制（与保存登录态按钮等宽） -->
          <div class="recorder-toolbar-row">
            <a-button
              class="recorder-finish-btn"
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
    <!-- 保存登录态：自定义名称 -->
    <a-modal v-model:visible="authNameVisible" :title="text.saveLoginState" :footer="false" width="420px">
      <a-form layout="vertical">
        <a-form-item :label="text.authNameLabel">
          <a-input
            v-model="authName"
            :placeholder="text.authNamePlaceholder"
            :max-length="64"
            allow-clear
            @press-enter="submitSaveLoginState"
          />
        </a-form-item>
      </a-form>
      <div class="recorder-setup-actions">
        <a-button @click="authNameVisible = false">{{ text.cancel }}</a-button>
        <a-button type="primary" :loading="savingAuth" @click="submitSaveLoginState">{{ text.create }}</a-button>
      </div>
    </a-modal>

  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { IconDelete, IconClockCircle, IconSafe, IconQuestionCircle, IconUpload, IconDown } from '@arco-design/web-vue/es/icon'
import { useAppI18n } from '@/composables/useAppI18n'
import { useProjectStore } from '@/store/projectStore'
import { pageApi, pageStepsApi, envConfigApi, moduleApi, recorderApi, authStateApi } from '../api'
import type { RecorderSessionInfo, RecorderFinishResult, RecorderSaveLoginStateResult } from '../api'
import type { UiPage, UiPageSteps, UiEnvironmentConfig, UiModule, UiPageForm, UiPageStepsForm } from '../types'
import type { UiAuthState } from '../types'
import { extractListData, extractResponseData } from '../types'
import { fileService } from '@/features/file-management/services/fileService'
import type { FileAsset } from '@/features/file-management/types'
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
        pageStepHint: 'The page step to record into; its existing actions stay unchanged and new actions are appended.',
        selectPageStep: 'Select a page step',
        environment: 'Environment',
        selectEnvironment: 'Select an environment',
        envHint: 'Recording navigates to the environment base URL (falls back to the page URL).',
        authState: 'Login state',
        authStatePlaceholder: 'Select login state',
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
        moreActions: 'More Actions',
        upload: 'Upload',
        uploadPick: 'Click upload control…',
        uploadPickHint: 'Upload mode: click the upload control (file input / button) in the browser view',
        uploadLocateFailed: 'Please click an upload control on the page',
        uploadLocal: 'Local file',
        uploadPlatform: 'Platform files',
        uploadPickLocal: 'Choose local file',
        uploadLocalHint: 'The selected file will be uploaded to the platform and bound to this step.',
        uploadSelectPlatform: 'Select a file from the platform',
        uploadPlatformHint: 'Pick an existing file stored on the platform.',
        uploadConfirm: 'Confirm',
        uploadAdded: 'Upload step added',
        uploadFailed: 'Upload failed',
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
        saveLoginState: 'Save Login State',
        authNameLabel: 'Login state name',
        authNamePlaceholder: 'Enter a name (leave empty to auto-generate)',
                saveLoginStateSuccess: 'Login state saved (cookies={cookies}, localStorage={keys}), executions will auto-inject it',
        saveLoginStateFailed: 'Failed to save login state',
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
        pageStepHint: '录制目标页面步骤：已有动作保持不变，录制的新动作追加到该步骤下。',
        selectPageStep: '请选择页面步骤',
        environment: '环境',
        selectEnvironment: '请选择环境',
        envHint: '录制时先导航到环境的基础 URL（环境未配置时使用页面 URL）。',
        authState: '登录态',
        authStatePlaceholder: '请选择登录态',
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
        moreActions: '更多操作',
        upload: '上传文件',
        uploadPick: '请在画面中点击上传控件…',
        uploadPickHint: '上传模式：请在左侧画面中点击上传控件（文件输入框或上传按钮）',
        uploadLocateFailed: '请点击页面上传控件',
        uploadLocal: '本地文件',
        uploadPlatform: '平台文件',
        uploadPickLocal: '选择本地文件',
        uploadLocalHint: '所选文件将上传到平台并与该步骤绑定。',
        uploadSelectPlatform: '请选择平台文件',
        uploadPlatformHint: '从平台已存储的文件中选择。',
        uploadConfirm: '确定',
        uploadAdded: '上传步骤已添加',
        uploadFailed: '上传失败',
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
        saveLoginState: '保存登录态',
        authNameLabel: '登录态名称',
        authNamePlaceholder: '填写登录态名称（留空自动生成）',
                saveLoginStateSuccess: '登录态已保存（cookies={cookies}，localStorage={keys}），执行时会自动注入',
        saveLoginStateFailed: '保存登录态失败',
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
const savingAuth = ref(false)


const form = reactive({
  page_id: undefined as number | undefined,
  page_step_id: undefined as number | undefined,
  env_config_id: undefined as number | undefined,
  pre_page_step_id: undefined as number | undefined,
  // 选择绑定的登录态（录制的步骤/用例继承该绑定；留空随环境生效登录态）
  auth_state_id: undefined as number | undefined,
})


watch(() => form.env_config_id, (v) => { fetchAuthStateOptions(v) })
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
const canvasWrapRef = ref<HTMLElement | null>(null)
// 画布显示尺寸：录制视图高度固定（见 .recorder-live），画布按视口比例
// letterbox 自适应宽度并居中，避免 canvas 按宽度撑高溢出产生右侧纵向滚动条。
const canvasSize = reactive({ width: 0, height: 0 })
const canvasStyle = computed(() => ({
  aspectRatio: `${viewport.width} / ${viewport.height}`,
  width: canvasSize.width ? `${canvasSize.width}px` : '100%',
  height: canvasSize.height ? `${canvasSize.height}px` : 'auto',
}))
// 画布区高度约束：全局主题把 .arco-modal-body 限高 70vh 且 overflow-y:auto
// （arco-theme-override.css），画布区必须 ≤ 70vh - body 内边距(上下 20px×2)，
// 否则弹窗 body 出现右侧滚动条。70vh 上限同时保证弹窗整体不超出视口、垂直居中不受影响。
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
      auth_state_id: form.auth_state_id,
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
    fitCanvas()
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

const authNameVisible = ref(false)
const authName = ref('')

/** 保存登录态：先让用户填写自定义名称（留空则后端自动生成） */
async function handleSaveLoginState() {
  if (!sessionId.value) return
  authName.value = ''
  authNameVisible.value = true
}

async function submitSaveLoginState() {
  // 保存当前录制浏览器（已完成登录，含验证码）的登录态到所属环境
  if (!sessionId.value) return
  savingAuth.value = true
  const name = authName.value.trim() || undefined
  try {
    const result = extractResponseData<RecorderSaveLoginStateResult>(
      await recorderApi.saveLoginState(sessionId.value, name ? { name } : undefined),
    )
    if (!result) throw new Error(text.value.saveLoginStateFailed)
    authNameVisible.value = false
    Message.success(
      text.value.saveLoginStateSuccess
        .replace('{cookies}', String(result.cookies))
        .replace('{keys}', String(result.local_storage_keys)),
    )
    emit('refresh')
  } catch (e: any) {
    Message.error(e?.detail || e?.error || e?.message || text.value.saveLoginStateFailed)
  } finally {
    savingAuth.value = false
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

// 帧绘制去抖：动画页帧到达速率可能高于绘制速率，逐帧 new Image 解码重绘
// 会积压回调白耗性能。只保留最新一帧，绘制中到达的帧在完成后补画一次。
let pendingFrameSrc: string | null = null
let drawingFrame = false

function drawFrame(imageSrc: string) {
  if (drawingFrame) {
    pendingFrameSrc = imageSrc
    return
  }
  drawingFrame = true
  const canvas = canvasRef.value
  if (!canvas) {
    drawingFrame = false
    return
  }
  const img = new Image()
  img.onload = () => {
    try {
      const ctx = canvas.getContext('2d')
      if (ctx) {
        canvas.width = viewport.width
        canvas.height = viewport.height
        ctx.drawImage(img, 0, 0, viewport.width, viewport.height)
      }
    } finally {
      drawingFrame = false
      if (pendingFrameSrc) {
        const next = pendingFrameSrc
        pendingFrameSrc = null
        drawFrame(next)
      }
    }
  }
  img.src = imageSrc
}

// 画布布局：容器高度固定，宽度按 viewport 比例自适应（超高时收缩并居中）。
// canvas 元素尺寸即实际绘制区域，canvasPoint 的坐标换算不受影响。
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
  if (uploadActive.value) {
    // 上传定位模式：本次点击用于定位上传控件
    uploadActive.value = false
    uiWebSocket.recorderLocateUpload(x, y)
    return
  }
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

/** 「更多操作」下拉分发：upload 进入上传定位模式，saveLoginState 弹出保存登录态命名框 */
function onMoreActionSelect(value: string | number | Record<string, any> | undefined) {
  if (value === 'upload') {
    handleUploadLocate()
    return
  }
  if (value === 'saveLoginState') {
    handleSaveLoginState()
  }
}

// ---- 上传文件（方案A：定位上传控件 + 选择文件[本地/平台]插入 upload 动作）----
const uploadActive = ref(false)
const uploadDialogVisible = ref(false)
const pendingUploadSelector = ref<Record<string, any> | null>(null)
const uploadSource = ref<'local' | 'platform'>('local')
const uploadingFile = ref(false)
const platformFiles = ref<FileAsset[]>([])
const selectedPlatformFileId = ref<number | null>(null)
const localFileInput = ref<HTMLInputElement | null>(null)

function handleUploadLocate() {
  if (!recording.value) return
  if (uploadActive.value) {
    uploadActive.value = false
    return
  }
  uploadActive.value = true
  Message.info(text.value.uploadPickHint)
}

/** 定位后的文件选择弹窗 */
function openUploadDialog(selector: Record<string, any>) {
  pendingUploadSelector.value = selector
  uploadSource.value = 'local'
  selectedPlatformFileId.value = null
  fetchPlatformFiles()
  uploadDialogVisible.value = true
}

async function fetchPlatformFiles() {
  if (!projectId.value) return
  try {
    const res = await fileService.list(projectId.value || 0)
    platformFiles.value = extractListData<FileAsset>(res)
  } catch (_) {
    platformFiles.value = []
  }
}

function pickLocalFile() {
  localFileInput.value?.click()
}

async function onLocalFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || !pendingUploadSelector.value) return
  uploadingFile.value = true
  try {
    const res = await fileService.upload(projectId.value || 0, [file])
    const asset = extractResponseData<FileAsset | FileAsset[]>(res)
    const picked = Array.isArray(asset) ? asset[0] : asset
    const fileId = Number(picked?.id ?? picked?.file_id)
    if (!fileId) throw new Error('上传失败：未返回文件 ID')
    uiWebSocket.recorderAddUpload(pendingUploadSelector.value, fileId, file.name)
    Message.success(text.value.uploadAdded)
    uploadDialogVisible.value = false
  } catch (err: any) {
    Message.error(err?.error || err?.message || text.value.uploadFailed)
  } finally {
    uploadingFile.value = false
  }
}

async function confirmPlatformFile() {
  if (!selectedPlatformFileId.value || !pendingUploadSelector.value) {
    Message.warning(text.value.uploadSelectPlatform)
    return
  }
  const asset = platformFiles.value.find((f) => f.id === selectedPlatformFileId.value)
  uiWebSocket.recorderAddUpload(pendingUploadSelector.value, selectedPlatformFileId.value, asset?.original_name || asset?.name || '')
  Message.success(text.value.uploadAdded)
  uploadDialogVisible.value = false
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
  if (a.type === 'upload') return a.file_name || `file_id:${a.file_id || ''}`
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
  // 每帧重算显示尺寸：弹窗开启动画等瞬时小 rect 一帧自愈（与执行画布同规则）
  fitCanvas()
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
  } else if (status === 'upload_located') {
    if (args.selector) {
      openUploadDialog(args.selector)
    } else {
      Message.error(text.value.uploadLocateFailed)
    }
  }
}

let offFrame: (() => void) | null = null
let offAction: (() => void) | null = null
let offStatus: (() => void) | null = null
let resizeObserver: ResizeObserver | null = null

const authStateOptions = ref<Array<{ label: string; value: number }>>([])
const fetchAuthStateOptions = async (envId: number | undefined) => {
  authStateOptions.value = []
  if (!envId) return
  try {
    const res = await authStateApi.list({ env_config: envId })
    const items = extractListData<UiAuthState>(res)
    authStateOptions.value = items.map((i) => ({ label: i.name, value: i.id }))
  } catch {
    authStateOptions.value = []
  }
}

onMounted(() => {
  fetchAuthStateOptions(form.env_config_id)

  offFrame = uiWebSocket.on(UiSocketEnum.RECORDER_FRAME, onRecorderFrame as any)
  offAction = uiWebSocket.on(UiSocketEnum.RECORDER_ACTION, onRecorderAction as any)
  offStatus = uiWebSocket.on(UiSocketEnum.RECORDER_STATUS, onRecorderStatus as any)
  resizeObserver = new ResizeObserver(() => fitCanvas())
  if (canvasWrapRef.value) resizeObserver.observe(canvasWrapRef.value)
  nextTick(fitCanvas)
})

onUnmounted(() => {
  offFrame?.()
  offAction?.()
  offStatus?.()
  resizeObserver?.disconnect()
  resizeObserver = null
  unbindCanvasListeners()
})
</script>

<style lang="postcss" scoped>
.upload-source-tabs {
  margin-bottom: 12px;
}

.upload-hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--color-text-3);
}

.recorder-setup-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}

.recorder-inject-login {
  margin-top: 4px;
}

.recorder-form-hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-3);
}

/* 表单提示问号图标：圆形边框内一个问号，悬停弹出气泡说明 */
.recorder-hint-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 1px solid var(--color-border-2);
  color: var(--color-text-3);
  font-size: 12px;
  cursor: help;
  flex: 0 0 auto;
  transition: color 0.2s, border-color 0.2s;
}

.recorder-hint-icon:hover {
  color: rgb(var(--primary-6));
  border-color: rgb(var(--primary-6));
}

/* 表单一行两列（页面+页面步骤 / 环境+登录态） */
.recorder-form-row {
  display: flex;
  gap: 12px;
}

.recorder-form-col {
  flex: 1 1 0;
  min-width: 0;
}

/* 单列行（前置步骤独占一行）的列同样限制为半行宽：
   flex:1 会占满整行，封顶后控件宽度与其余行的两列布局对齐 */
.recorder-form-row > .recorder-form-col:only-child {
  max-width: calc(50% - 6px);
}

/* 列内选择框锁定列宽：flex 子项默认 min-width:auto 会被超长选项撑开，
   归零后宽度恒等于列宽，超长内容以省略号截断 */
.recorder-form-col :deep(.arco-select) {
  min-width: 0;
  max-width: 100%;
}

/* 选择框行容器本身是 form-item-content（flex）的子项：min-width 默认 auto
   会被超长选项文本撑开（选择框的 max-width:100% 随之失效），归零后行宽锁定列宽；
   flex:1 保证短内容/空值时行也撑满列宽，宽度不随选中内容变化 */
.recorder-form-col :deep(.recorder-select-with-add) {
  flex: 1;
  min-width: 0;
  max-width: 100%;
}

.recorder-form-col :deep(.arco-select-view-value) {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}


.recorder-select-spacer {
  /* 与行尾 small 图标按钮（28px）等宽的占位：无按钮的行用它补齐槽位，
     保证所有选择框宽度一致 */
  width: 28px;
  flex: 0 0 auto;
}

/* 行尾问号图标槽位：外层占位与按钮等宽，内部图标居中，宽度对齐其余行 */
.recorder-hint-slot {
  width: 28px;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

/* label 行内的问号图标：跟随标题文字，不占控件行尾槽位 */
.recorder-hint-icon-label {
  margin-left: 4px;
  width: 16px;
  height: 16px;
  font-size: 10px;
  vertical-align: middle;
}

.recorder-env-item :deep(.arco-form-item-label-col) {
  /* 环境标题与选择框间距收紧（纵向表单默认 8px）：
     !important 压过组件默认规则，与"页面/页面步骤"表单项视觉一致 */
  margin-bottom: 2px !important;
}

.recorder-env-select-row .env-select {
  /* 固定宽度：不随选项内容变化，超长以省略号截断 */
  width: 205px;
  flex: none;
  min-width: 0;
}

.recorder-env-select-row :deep(.arco-select-view-value) {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
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
  /* 高固定 700px：受全局 .arco-modal-body 限高（70vh，arco-theme-override.css）
     约束自动收缩——400 屏上画布区 ≤ 70vh-44px，弹窗 body 永不出现右侧滚动条；
     画布由 fitCanvas 自适应 letterbox */
  height: min(700px, calc(70vh - 44px));
  min-height: 0;
  overflow: hidden;
}

.recorder-canvas-wrap {
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
  /* 留白处与弹窗面板同色（深浅主题自适应），避免 letterbox 黑条 */
  background: var(--color-bg-2);
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
  max-width: 100%;
  max-height: 100%;
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
  flex-direction: column;
  gap: 8px;
}

/* 工具栏行：断言行 / 保存登录态+更多操作行 / 结束录制行 */
.recorder-toolbar-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

/* 断言按钮固定宽度：激活后提示文案较长，不固定会被撑宽引起同行控件跳动 */
.recorder-assert-btn {
  width: 88px;
  flex: 0 0 auto;
}

/* 按钮内动态文字截断：Arco 按钮文字是裸文本节点（无内容包裹元素），
   截断样式只能作用于模板里自包的 .recorder-btn-label span */
.recorder-btn-label {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: bottom;
}

/* 结束录制按钮与保存登录态按钮等宽：断言行/更多操作行都是
   多控件 flex 行，等宽基准取第二行主按钮（保存登录态）的宽度 */
.recorder-finish-btn {
  flex: 0 0 auto;
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