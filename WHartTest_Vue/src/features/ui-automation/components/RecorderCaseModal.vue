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
        <!-- 用例名称 + 页面 一行两列；各行尾部统一 28px 槽位（按钮/占位/图标），
             保证所有输入框、选择框宽度一致（等于列宽 - 槽位 - 间距） -->
        <div class="recorder-form-row">
          <a-form-item :label="text.caseName" :required="true" class="recorder-form-col">
            <div class="recorder-select-with-add">
              <a-input
                v-model="form.case_name"
                :placeholder="text.enterCaseName"
                :max-length="255"
                allow-clear
                class="flex-1"
              />
              <span class="recorder-select-spacer" aria-hidden="true" />
            </div>
          </a-form-item>
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
              />
              <a-button type="outline" size="small" :disabled="starting" :title="text.addPage" @click="openAddPage">
                <template #icon><icon-plus /></template>
              </a-button>
            </div>
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
          <!-- 第一行：断言（模式下拉 + 期望值输入 + 断言按钮） -->
          <div class="recorder-toolbar-row">
            <a-select
              v-model="assertMode"
              size="small"
              style="width: 132px"
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
          <!-- 第二行：等待 + 更多操作（上传文件/清空上下文收纳于此） -->
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
                <a-doption value="switchAccount" :disabled="!recording">
                  <template #icon><icon-user /></template>
                  {{ text.switchAccount }}
                </a-doption>
              </template>
            </a-dropdown>
          </div>
          <!-- 第三行：保存登录态 + 结束录制（两按钮等宽对齐） -->
          <div class="recorder-toolbar-row">
            <a-button
              type="outline"
              size="small"
              :loading="savingAuth"
              :disabled="!recording"
              @click="handleSaveLoginState"
            >
              <template #icon><icon-safe /></template>
              {{ text.saveLoginState }}
            </a-button>
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

        <!-- 步骤分组：添加步骤 + 当前活动步骤 + 分组切换 -->
        <div class="recorder-case-groups">
          <div class="recorder-case-groups-head">
            <a-button type="primary" size="small" :disabled="!recording" @click="openAddGroup">
              <template #icon><icon-plus /></template>
              {{ text.addStep }}
            </a-button>
            <a-tooltip :content="text.dragHint" position="top">
              <span class="recorder-hint-icon recorder-hint-icon-small"><icon-question-circle /></span>
            </a-tooltip>
          </div>
          <!-- 步骤分组列表：点击切换录制归属，拖动调整顺序（顺序即用例步骤顺序） -->
          <draggable
            v-model="recordGroups"
            item-key="uid"
            handle=".drag-handle"
            class="recorder-case-groups-list"
          >
            <template #item="{ element, index }">
              <div
                class="recorder-case-group-item"
                :class="{ active: element.uid === activeGroupId }"
                @click="selectGroup(element.uid)"
              >
                <icon-drag-dot-vertical class="drag-handle" />
                <span class="recorder-case-group-name">{{ element.name }}</span>
                <a-tag color="cyan">{{ element.seqs.length }}</a-tag>
                <a-popconfirm
                  :content="text.deleteGroupConfirm"
                  position="left"
                  @ok="deleteGroup(element.uid)"
                >
                  <a-button type="text" size="mini" class="recorder-case-group-del" @click.stop>
                    <template #icon><icon-delete /></template>
                  </a-button>
                </a-popconfirm>
              </div>
            </template>
          </draggable>
          <div v-if="recordGroups.length" class="recorder-case-active">
            {{ text.activeStep }}：
            <a-tag color="arcoblue" size="small">
              {{ activeGroupName || text.noStepYet }}
            </a-tag>
          </div>
        </div>

        <div class="recorder-actions-list">
          <div v-for="a in viewActions" :key="a.seq" class="recorder-action-item">
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
          <div v-if="recording && viewActions.length === 0" class="recorder-actions-empty">
            {{ text.noActions }}
          </div>
        </div>
      </div>
    </div>

    <!-- 添加步骤弹窗 -->
    <a-modal
      :visible="addGroupVisible"
      :title="text.addStep"
      :footer="false"
      width="420px"
      @cancel="addGroupVisible = false"
    >
      <a-input
        v-model="newGroupName"
        :placeholder="text.enterStepName"
        :max-length="64"
        allow-clear
        @press-enter="submitAddGroup"
      />
      <div class="recorder-setup-actions">
        <a-button @click="addGroupVisible = false">{{ text.cancel }}</a-button>
        <a-button type="primary" @click="submitAddGroup">{{ text.create }}</a-button>
      </div>
    </a-modal>

    <!-- 上传文件选择弹窗 -->
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
            :loading="loadingModules"
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
import { IconDelete, IconPlus, IconDragDotVertical, IconClockCircle, IconSafe, IconUser, IconQuestionCircle, IconDown } from '@arco-design/web-vue/es/icon'
import draggable from 'vuedraggable'
import { useAppI18n } from '@/composables/useAppI18n'
import { useProjectStore } from '@/store/projectStore'
import { pageApi, pageStepsApi, envConfigApi, moduleApi, recorderApi, authStateApi } from '../api'
import type { RecorderSessionInfo, RecorderCaseFinishResult, RecorderSaveLoginStateResult } from '../api'
import type { UiPage, UiPageSteps, UiEnvironmentConfig, UiModule, UiPageForm } from '../types'
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
        title: 'Record Test Case',
        caseName: 'Case name',
        enterCaseName: 'Enter case name',
        page: 'Page',
        selectPage: 'Select a page',
        environment: 'Environment',
        selectEnvironment: 'Select an environment',
        envHint: 'Recording navigates to the environment base URL (falls back to the page URL).',
        authState: 'Login state',
        authStatePlaceholder: 'Select login state',
        preStep: 'Pre-step (optional)',
        preStepPlaceholder: 'Select a page step to auto-run before recording',
        preStepHint: 'Auto executes this step (e.g. login) before recording; it will also be added to the case.',
        cancel: 'Cancel',
        startRecord: 'Start Recording',
        connecting: 'Connecting to browser...',
        preparing: 'Preparing browser...',
        assert: 'Assert',
        finishRecord: 'Finish',
        saveLoginState: 'Save Login State',
        switchAccount: 'Clear Context',
        switchAccountFailed: 'Switch account failed',
        switchAccountDone: 'Switched to a clean session. Please log in with the new account, then save its login state.',
        moreActions: 'More Actions',
        authNameLabel: 'Login state name',
        authNamePlaceholder: 'Enter a name (leave empty to auto-generate)',
                saveLoginStateSuccess: 'Login state saved (cookies={cookies}, localStorage={keys}), executions will auto-inject it',
        saveLoginStateFailed: 'Failed to save login state',
        wait: 'Wait',
        waitSeconds: (sec: number) => `${sec}s`,
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
        recordHint: 'Operate in the browser view. Use "Add step" to group later actions before recording.',
        noActions: 'No actions yet in this step.',
        addStep: 'Add step',
        enterStepName: 'Enter step name',
        create: 'Create',
        activeStep: 'Recording into',
        addPage: 'New page',
        module: 'Module',
        selectModule: 'Select module',
        pageName: 'Page name',
        enterPageName: 'Enter page name',
        pageUrl: 'Page URL',
        enterPageUrl: 'Enter page URL (optional)',
        createSuccess: 'Created successfully',
        createFailed: 'Creation failed',
        modulePageRequired: 'Select a module and enter a page name',
        noStepYet: 'No step yet — record actions will be unassigned until you add one',
        dragHint: 'Click a step to keep recording into it; drag to reorder (final case step order)',
        deleteGroupConfirm: 'Delete this step? Its recorded actions will not be saved.',
        selectPageFirst: 'Select a page first',
        startFailed: 'Failed to start recording',
        finishFailed: 'Failed to finish recording',
        finishSuccess: 'Case recorded',
        stats: 'Actions: {actions}, steps created: {steps}, case steps: {caseSteps}, elements: +{elements}',
        assertRecorded: 'Assertion recorded',
        assertFailed: 'Assertion failed',
        assertPickElement: 'Click an element in the view…',
        assertModeHint: 'Assert mode: click the target element in the browser view',
        removeAction: 'Remove this action',
        preFailed: 'Pre-step failed, please check its definition',
        needGroupFirst: 'Add at least one step before finishing if there are actions',
        needCreateStepFirst: 'Please add a step first, then record actions',
        selectStepToGroup: 'Please add a step first',
        confirmCancel: 'Cancel recording? The unfinished recording will be discarded.',
        assertGroupState: 'Element state',
        assertGroupContent: 'Content check',
        assertGroupPage: 'Page check',
        assertVisible: 'Visible',
        assertHidden: 'Hidden',
        assertEnabled: 'Enabled',
        assertDisabled: 'Disabled',
        assertChecked: 'Checked',
        assertText: 'Has text',
        assertContainText: 'Contains text',
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
      }
    : {
        title: '录制用例',
        caseName: '用例名称',
        enterCaseName: '请输入用例名称',
        page: '页面',
        selectPage: '请选择页面',
        environment: '环境',
        selectEnvironment: '请选择环境',
        envHint: '录制时先导航到环境的基础 URL（环境未配置时使用页面 URL）。',
        authState: '登录态',
        authStatePlaceholder: '请选择登录态',
        preStep: '前置步骤（可选）',
        preStepPlaceholder: '选择录制前自动执行的页面步骤',
        preStepHint: '开始录制前自动执行该步骤（如登录），执行过程不会进入录制动作；结束后该步骤也会加入用例。',
        cancel: '取消',
        startRecord: '开始录制',
        connecting: '正在连接浏览器…',
        preparing: '正在准备浏览器…',
        assert: '断言',
        finishRecord: '结束录制',
        saveLoginState: '保存登录态',
        switchAccount: '清空上下文',
        switchAccountFailed: '切换账号失败',
        switchAccountDone: '已切换到全新会话，请登录下一个账号后保存登录态。',
        moreActions: '更多操作',
        authNameLabel: '登录态名称',
        authNamePlaceholder: '填写登录态名称（留空自动生成）',
                saveLoginStateSuccess: '登录态已保存（cookies={cookies}，localStorage={keys}），执行时会自动注入',
        saveLoginStateFailed: '保存登录态失败',
        recordHint: '在左侧浏览器画面中操作；录制前请先点击「添加步骤」分组后续动作。',
        noActions: '该步骤下暂无动作',
        addStep: '添加步骤',
        enterStepName: '请输入步骤名称',
        create: '创建',
        activeStep: '当前录制到',
        addPage: '新增页面',
        module: '所属模块',
        selectModule: '请选择模块',
        pageName: '页面名称',
        enterPageName: '请输入页面名称',
        pageUrl: '页面 URL',
        enterPageUrl: '请输入页面 URL（可选）',
        createSuccess: '创建成功',
        createFailed: '创建失败',
        modulePageRequired: '请选择模块并填写页面名称',
        noStepYet: '尚未添加步骤',
        dragHint: '点击步骤切换录制归属；拖动可调整顺序（即用例步骤顺序）',
        deleteGroupConfirm: '删除该步骤？此步骤中录制的动作将不会保存。',
        selectPageFirst: '请先选择页面',
        startFailed: '启动录制失败',
        finishFailed: '结束录制失败',
        finishSuccess: '用例录制完成',
        stats: '动作 {actions} 个，新建步骤 {steps} 个，用例步骤 {caseSteps} 个，元素 +{elements}',
        assertRecorded: '断言已记录',
        assertFailed: '断言失败',
        assertPickElement: '请在画面中点击元素…',
        assertModeHint: '断言模式：请在左侧画面中点击要断言的元素',
        removeAction: '删除此操作',
        preFailed: '前置步骤执行失败，请检查步骤定义',
        wait: '等待',
        waitSeconds: (sec: number) => `${sec} 秒`,
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
        needGroupFirst: '存在未分组的动作，请先添加步骤',
        needCreateStepFirst: '请先创建步骤，再继续录制',
        selectStepToGroup: '请先添加步骤',
        confirmCancel: '确定取消录制？未完成的录制将被丢弃。',
        assertGroupState: '元素状态',
        assertGroupContent: '内容校验',
        assertGroupPage: '页面校验',
        assertVisible: '元素可见',
        assertHidden: '元素隐藏',
        assertEnabled: '元素可用',
        assertDisabled: '元素不可用',
        assertChecked: '已勾选',
        assertText: '文本等于',
        assertContainText: '包含文本',
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
      }
))

type Phase = 'setup' | 'recording'

const phase = ref<Phase>('setup')
const starting = ref(false)
const recording = ref(false)
const finishing = ref(false)
const savingAuth = ref(false)

// 环境下拉与页面下拉同用 flex-1 弹性布局（.recorder-form-col 锁宽），
// 宽度天然一致且不随选项内容变化，无需 JS 实测同步

const form = reactive({
  case_name: '',
  page_id: undefined as number | undefined,
  env_config_id: undefined as number | undefined,
  pre_page_step_id: undefined as number | undefined,
  // 选择绑定的登录态（录制的步骤/用例继承该绑定；留空随环境生效登录态）
  auth_state_id: undefined as number | undefined,
})


watch(() => form.env_config_id, (v) => { fetchAuthStateOptions(v) })
const projectId = computed(() => props.projectId ?? useProjectStore().currentProject?.id)

const loadingPages = ref(false)
const loadingEnvs = ref(false)
const loadingPreSteps = ref(false)
const pageOptions = ref<Array<{ label: string; value: number; module?: number }>>([])
const envOptions = ref<Array<{ label: string; value: number; base_url?: string | null }>>([])
const preStepOptions = ref<Array<{ label: string; value: number }>>([])
// 所选环境的基础 URL（切换账号时导航用）
const selectedEnvBaseUrl = computed(() => envOptions.value.find((e) => e.value === form.env_config_id)?.base_url || '')

// ---- 快捷新增页面 ----
const addPageVisible = ref(false)
const addPageSubmitting = ref(false)
const loadingModules = ref(false)
const moduleOptions = ref<UiModule[]>([])
const addPageForm = reactive<Partial<UiPageForm>>({
  project: 0,
  module: undefined,
  name: '',
  url: '',
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
  if (!projectId.value) return
  // 模块列表按项目拉取：每次打开弹窗都重新请求（切换项目后旧项目的模块必须刷新），
  // moduleOptions 无需跨弹窗缓存——模块树接口很轻，缓存反而导致串显上一项目数据
  loadingModules.value = true
  try {
    const res = await moduleApi.tree(projectId.value)
    moduleOptions.value = extractListData<UiModule>(res)
  } catch (_) {
    // 模块为可选项
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
    const listRes = await pageApi.list({ project: projectId.value })
    pageOptions.value = extractListData<UiPage>(listRes).map((p) => ({
      label: p.name,
      value: p.id,
      module: p.module,
    }))
    form.page_id = created.id
    Message.success(text.value.createSuccess)
  } catch (e: any) {
    Message.error(e?.error || e?.message || text.value.createFailed)
  } finally {
    addPageSubmitting.value = false
  }
}

const sessionId = ref('')
const viewport = reactive({ width: 1400, height: 900 })
const firstFrame = ref(false)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const imeInputRef = ref<HTMLInputElement | null>(null)

// ---- 录制动作与步骤分组 ----
const allActions = ref<Array<Record<string, any>>>([])
const recordGroups = ref<Array<{ uid: number; name: string; seqs: number[] }>>([])
const activeGroupId = ref<number | null>(null)   // 当前录制归属（切换分组即切换归属）
const addGroupVisible = ref(false)
const newGroupName = ref('')
let groupUidSeed = 1
let lastGroupHintTs = 0   // 未创建步骤时提示节流

const activeGroup = computed(() => {
  return activeGroupId.value === null
    ? null
    : recordGroups.value.find((g) => g.uid === activeGroupId.value) || null
})

const activeGroupName = computed(() => (activeGroup.value ? activeGroup.value.name : ''))

const viewActions = computed(() => {
  const g = activeGroup.value
  if (!g) return []
  const seqs = new Set(g.seqs)
  return allActions.value.filter((a) => seqs.has(a.seq))
})

function selectGroup(uid: number) {
  activeGroupId.value = uid
}

function deleteGroup(uid: number) {
  const idx = recordGroups.value.findIndex((g) => g.uid === uid)
  if (idx < 0) return
  recordGroups.value.splice(idx, 1)
  // 删除的是当前录制归属组时，切到第一个剩余分组
  if (activeGroupId.value === uid) {
    activeGroupId.value = recordGroups.value.length ? recordGroups.value[0].uid : null
  }
}

// ---- 断言 ----
const assertMode = ref('visible')
const assertValue = ref('')
const assertActive = ref(false)
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
    pageOptions.value = extractListData<UiPage>(res).map((p) => ({ label: p.name, value: p.id }))
  } catch (e: any) {
    Message.error(e?.error || e?.message || text.value.startFailed)
  } finally {
    loadingPages.value = false
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
    preStepOptions.value = extractListData<UiPageSteps>(res).map((s) => ({
      label: s.page_name ? `${s.name}（${s.page_name}）` : s.name,
      value: s.id,
    }))
  } catch (_) {
    // 前置步骤为可选项
  } finally {
    loadingPreSteps.value = false
  }
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      resetState()
      // 模块列表按项目维度：切换项目后必须重拉，否则快捷新增页面的
      // 模块下拉会串显上一个项目的模块
      moduleOptions.value = []
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
  form.case_name = ''
  form.page_id = undefined
  form.env_config_id = undefined
  form.pre_page_step_id = undefined
  sessionId.value = ''
  firstFrame.value = false
  allActions.value = []
  recordGroups.value = []
  activeGroupId.value = null
  assertActive.value = false
  assertValue.value = ''
  authMarks.value = []
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
  if (!form.case_name.trim()) {
    Message.warning(text.value.enterCaseName)
    return
  }
  if (!form.page_id) {
    Message.warning(text.value.selectPageFirst)
    return
  }
  if (!form.env_config_id) {
    Message.warning(text.value.selectEnvironment)
    return
  }
  starting.value = true
  try {
    const info = extractResponseData<RecorderSessionInfo>(await recorderApi.caseCreate({
      case_name: form.case_name.trim(),
      page_id: form.page_id,
      env_config_id: form.env_config_id,
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
  if (allActions.value.length > 0 && recordGroups.value.length === 0) {
    Message.warning(text.value.needGroupFirst)
    return
  }
  finishing.value = true
  try {
    uiWebSocket.recorderStop()
    const result = extractResponseData<RecorderCaseFinishResult>(await recorderApi.finish(
      sessionId.value,
      {
        groups: recordGroups.value.map((g) => ({ name: g.name, seqs: g.seqs.slice() })),
        auth_marks: authMarks.value.map((m) => ({ group_index: m.groupIndex, auth_state_id: m.authStateId })),
      },
    ))
    if (!result) throw new Error(text.value.finishFailed)
    const stats = text.value.stats
      .replace('{actions}', String(result.actions_count))
      .replace('{steps}', String(result.page_steps_created))
      .replace('{caseSteps}', String(result.case_steps_created))
      .replace('{elements}', String(result.elements_created))
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

// 录制过程中"重新保存登录态"的归属：保存成功时记录当时的活动步骤组序号
// （按结束时的组顺序），该组及其后的组绑定新登录态，之前的组保持原绑定
const authMarks = ref<Array<{ groupIndex: number; authStateId: number }>>([])

const switchingAccount = ref(false)

/** 切换账号：无痕重建上下文（不点目标系统"退出登录"，已保存的登录态保持有效） */
async function handleSwitchAccount() {
  if (!recording.value || !sessionId.value) return
  switchingAccount.value = true
  try {
    const url = selectedEnvBaseUrl.value || undefined
    if (!uiWebSocket.recorderSwitchAccount(url)) throw new Error(text.value.switchAccountFailed)
  } catch (e: any) {
    Message.error(e?.message || text.value.switchAccountFailed)
  } finally {
    switchingAccount.value = false
  }
}

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
    // 归属组序号 = 保存时刻的活动步骤组在结束分组列表中的位置。语义：登录流程
    // 动作隶属于保存时刻正在录制的组（如"进入登录页+输入账密"组），该组及其后
    // 的组都绑定新登录态；更早的组（如 A 登录后录完的步骤 1、2）保持原绑定。
    // 按 uid 找索引而非直接存 index：录制中可能拖动/删除分组，结束时以最终顺序为准。
    const activeIdx = recordGroups.value.findIndex((g) => g.uid === activeGroupId.value)
    if (activeIdx >= 0) {
      authMarks.value.push({ groupIndex: activeIdx, authStateId: result.auth_state_id })
    }
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
// 步骤分组
// ------------------------------------------------------------------

function openAddGroup() {
  if (!recording.value) return
  newGroupName.value = ''
  addGroupVisible.value = true
}

function submitAddGroup() {
  const name = newGroupName.value.trim()
  if (!name) {
    Message.warning(text.value.enterStepName)
    return
  }
  const uid = groupUidSeed++
  recordGroups.value.push({ uid, name, seqs: [] })
  activeGroupId.value = uid
  addGroupVisible.value = false
}

// ------------------------------------------------------------------
// 画布：帧绘制 + 输入转发（与录制步骤一致）
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
    uploadActive.value = false
    uiWebSocket.recorderLocateUpload(x, y)
    return
  }
  if (assertActive.value) {
    assertActive.value = false
    uiWebSocket.recorderAssert(assertMode.value, x, y, assertValue.value.trim() || undefined)
    return
  }
  uiWebSocket.recorderInput({
    type: 'mouse', event: 'down', x, y,
    button: e.button === 2 ? 'right' : 'left',
    clickCount: e.detail || 1,
  })
}

function onPointerUp(e: PointerEvent) {
  if (!recording.value) return
  const { x, y } = canvasPoint(e)
  uiWebSocket.recorderInput({
    type: 'mouse', event: 'up', x, y,
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
  uiWebSocket.recorderInput({ type: 'wheel', x, y, deltaX: e.deltaX, deltaY: e.deltaY })
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
// 断言按钮
// ------------------------------------------------------------------

const waitOptions = [2, 3, 5, 10]

function handleAddWait(seconds: number) {
  if (!recording.value) return
  if (!uiWebSocket.recorderAddWait(seconds)) {
    Message.error(text.value.finishFailed)
  }
}

/** 「更多操作」下拉分发：upload 进入上传定位模式，switchAccount 清空上下文 */
function onMoreActionSelect(value: string | number | Record<string, any> | undefined) {
  if (value === 'upload') {
    handleUploadLocate()
    return
  }
  if (value === 'switchAccount') {
    handleSwitchAccount()
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
  if (assertMode.value === 'url' || assertMode.value === 'title') {
    if (assertMode.value === 'title' && !assertValue.value.trim()) {
      Message.warning(text.value.assertTitleRequired)
      return
    }
    uiWebSocket.recorderAssert(assertMode.value, undefined, undefined, assertValue.value.trim())
    return
  }
  if (needAssertValue.value && !assertValue.value.trim()) {
    Message.warning(text.value.assertValueRequired)
    return
  }
  assertActive.value = true
  Message.info(text.value.assertModeHint)
}

// ------------------------------------------------------------------
// 动作展示
// ------------------------------------------------------------------

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

function removeAction(a: Record<string, any>) {
  allActions.value = allActions.value.filter((x) => x.seq !== a.seq)
  for (const g of recordGroups.value) {
    g.seqs = g.seqs.filter((s) => s !== a.seq)
  }
  uiWebSocket.recorderRemoveAction(a.seq)
}

// ------------------------------------------------------------------
// WS 消息
// ------------------------------------------------------------------

function onRecorderFrame(data: any) {
  if (!props.visible) return
  const frame = data?.data?.func_args?.frame
  if (!frame?.data) return
  firstFrame.value = true
  if (viewport.width !== frame.w || viewport.height !== frame.h) {
    viewport.width = frame.w || viewport.width
    viewport.height = frame.h || viewport.height
  }
  drawFrame(`data:image/jpeg;base64,${frame.data}`)
}

function onRecorderAction(data: any) {
  // 只处理本弹窗打开时的动作广播：tab 常驻渲染，隐藏的用例录制弹窗
  // 不能响应其它录制会话（如页面步骤录制）的动作，否则会误弹"请先创建步骤"
  if (!props.visible) return
  const action = data?.data?.func_args?.action
  if (!action) return
  // 未创建步骤时拦截：撤销该动作并提示先添加步骤（提示节流 3 秒一次）
  if (!activeGroup.value) {
    const now = Date.now()
    if (now - lastGroupHintTs > 3000) {
      lastGroupHintTs = now
      Message.warning(text.value.needCreateStepFirst)
    }
    uiWebSocket.recorderRemoveAction(action.seq)
    return
  }
  // 同 seq 更新（连续输入合并场景）
  const idx = allActions.value.findIndex((a) => a.seq === action.seq)
  if (idx >= 0) {
    allActions.value[idx] = action
  } else {
    allActions.value.push(action)
  }
  // 新动作挂到当前活动步骤
  if (activeGroup.value) {
    if (!activeGroup.value.seqs.includes(action.seq)) activeGroup.value.seqs.push(action.seq)
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
  } else if (status === 'context_reset') {
    Message.success(text.value.switchAccountDone)
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
})

onUnmounted(() => {
  offFrame?.()
  offAction?.()
  offStatus?.()
  unbindCanvasListeners()
})
</script>

<style lang="postcss" scoped>
/* 表单一行两列（用例名称+页面 / 环境+登录态），与录制步骤表单布局一致 */
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

.recorder-select-with-add {
  display: flex;
  gap: 8px;
  align-items: center;
  /* 行容器是 form-item-content（flex）的子项：min-width 默认 auto 会被超长
     选项文本撑开（内部固定宽随之失效），归零后行宽锁定列宽；flex:1 保证
     短内容/空值时行也撑满列宽，宽度不随选中内容变化 */
  flex: 1;
  min-width: 0;
  max-width: 100%;
}

/* 行尾槽位（占位/问号图标）与 small 图标按钮（28px）等宽：
   无按钮的行用它补齐，保证所有输入框/选择框宽度一致 */
.recorder-select-spacer,
.recorder-hint-slot {
  width: 28px;
  flex: 0 0 auto;
}

.recorder-hint-slot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

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
  flex: 0 1 320px;
  min-width: 240px;
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

/* 结束录制按钮与保存登录态按钮同行等宽：flex:1 平分剩余空间，两按钮等宽对齐 */
.recorder-finish-btn {
  flex: 1 1 0;
  min-width: 0;
}

.recorder-hint {
  font-size: 12px;
  color: var(--color-text-3);
  line-height: 1.5;
}

.recorder-case-groups {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.recorder-case-groups-head {
  display: flex;
  gap: 8px;
  align-items: center;
}

.recorder-case-active {
  font-size: 12px;
  color: var(--color-text-3);
  display: flex;
  align-items: center;
  gap: 4px;
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


.recorder-type-hint {
  font-size: 12px;
  color: var(--color-text-3);
  flex: 1;
  min-width: 0;
}

/* 小号问号提示图标（添加步骤旁）：与录制表单问号同款样式，尺寸略小适配按钮行 */
.recorder-hint-icon-small {
  width: 16px;
  height: 16px;
  font-size: 10px;
}

.recorder-case-groups-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 180px;
  overflow-y: auto;
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
  padding: 6px;
}

.recorder-case-group-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  border: 1px solid transparent;
}

.recorder-case-group-item:hover {
  background: var(--color-fill-2);
}

.recorder-case-group-item.active {
  background: var(--color-primary-light-1);
  border-color: var(--color-primary-4);
}

.recorder-case-group-item .drag-handle {
  cursor: move;
  color: var(--color-text-3);
  flex: none;
}

.recorder-case-group-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recorder-case-group-del {
  flex: none;
  color: var(--color-text-3);
}


.recorder-actions-empty {
  color: var(--color-text-3);
  font-size: 13px;
  text-align: center;
  padding: 24px 0;
}
</style>