<template>
  <div class="step-detail-list">
    <div class="step-header">
      <span class="step-title">{{ stepText.stepListTitle }}</span>
      <a-space>
        <a-select v-model="selectedEnvConfig" :placeholder="stepText.executionEnv" size="small" style="width: 120px" allow-clear>
          <a-option v-for="env in envConfigs" :key="env.id" :value="env.id">
            {{ env.name }}
            <a-tag v-if="env.is_default" size="small" color="arcoblue" style="margin-left: 4px">{{ stepText.default }}</a-tag>
          </a-option>
        </a-select>
        <a-select v-model="selectedActuator" :placeholder="stepText.selectActuator" size="small" style="width: 150px" allow-clear>
          <a-option v-for="act in actuators" :key="act.id" :value="act.id" :disabled="!act.is_open">
            {{ act.name || act.id }}
            <a-tag v-if="!act.is_open" size="small" color="gray" style="margin-left: 4px">{{ stepText.offline }}</a-tag>
          </a-option>
        </a-select>
        <a-button type="outline" status="success" size="small" :loading="executing" :disabled="!selectedActuator" @click="executePageStep">
          <template #icon><icon-play-arrow /></template>
          {{ stepText.debugRun }}
        </a-button>
        <a-button type="primary" size="small" @click="showAddModal">
          <template #icon><icon-plus /></template>
          {{ stepText.addAction }}
        </a-button>
      </a-space>
    </div>

    <a-spin :loading="loading">
      <div v-if="stepData.length === 0" class="empty-tips">
        <a-empty :description="stepText.emptyActions" />
      </div>
      <draggable
        v-else
        v-model="stepData"
        item-key="id"
        handle=".drag-handle"
        @end="onDragEnd"
      >
        <template #item="{ element, index }">
          <div class="step-card">
            <div class="step-left">
              <div class="drag-handle">
                <icon-drag-dot-vertical />
              </div>
              <div class="step-index">{{ index + 1 }}</div>
              <div class="step-type">
                <a-tag :color="stepTypeColors[element.step_type as StepType]" size="small">
                  {{ getStepTypeLabel(element.step_type as StepType) }}
                </a-tag>
              </div>
            </div>
            <div class="step-content">
              <span v-if="element.element_name" class="info-item">
                <a-tag v-if="element.module_name" size="small" color="arcoblue" style="margin-right: 4px;">
                  {{ element.module_name }}
                </a-tag>
                <a-tag v-if="element.page_name" size="small" color="cyan" style="margin-right: 4px;">
                  {{ element.page_name }}
                </a-tag>
                <span class="info-label">{{ stepText.elementLabel }}</span>
                <span class="element-name">{{ element.element_name }}</span>
              </span>
              <span v-if="element.ope_key" class="info-item">
                <span class="info-label">{{ stepText.actionLabel }}</span>
                <span class="ope-key">{{ getOpeKeyLabel(element.ope_key) }}</span>
              </span>
              <span v-if="element.ope_value && Object.keys(element.ope_value).length > 0" class="info-item">
                <span class="info-label">{{ stepText.paramsLabel }}</span>
                <span class="ope-value">{{ formatOpeValue(element.ope_value) }}</span>
              </span>
              <span v-if="element.sql_execute && Object.keys(element.sql_execute).length > 0" class="sql-info">{{ stepText.sqlAction }}</span>
              <span v-if="element.custom && Object.keys(element.custom).length > 0" class="custom-info">{{ stepText.customVariable }}</span>
              <span v-if="element.condition_value && Object.keys(element.condition_value).length > 0" class="condition-info">{{ stepText.conditionJudge }}</span>
              <span v-if="element.description" class="step-desc" :title="element.description">{{ element.description }}</span>
            </div>
            <div class="step-actions">
              <a-button type="text" size="mini" @click="editStep(element)">
                <template #icon><icon-edit /></template>
              </a-button>
              <a-popconfirm :content="stepText.deleteActionConfirm" @ok="deleteStep(element)">
                <a-button type="text" status="danger" size="mini">
                  <template #icon><icon-delete /></template>
                </a-button>
              </a-popconfirm>
            </div>
          </div>
        </template>
      </draggable>
    </a-spin>

    <!-- 添加/编辑操作弹窗 -->
    <a-modal
      v-model:visible="modalVisible"
      :title="isEdit ? stepText.editAction : stepText.addAction"
      :ok-loading="submitting"
      width="700px"
      @before-ok="handleSubmit"
      @cancel="handleCancel"
    >
      <a-form ref="formRef" :model="formData" :rules="rules" layout="vertical">
        <a-form-item field="step_type" :label="stepText.actionType" required>
          <a-select v-model="formData.step_type" @change="onStepTypeChange">
            <a-option v-for="(label, value) in stepTypeLabels" :key="value" :value="Number(value)">
              {{ label }}
            </a-option>
          </a-select>
        </a-form-item>

        <!-- 元素操作 -->
        <template v-if="formData.step_type === 0">
          <a-form-item :label="stepText.selectModule">
            <a-select
              v-model="selectedElementModule"
              :placeholder="stepText.pleaseSelectModule"
              allow-search
              allow-clear
              @popup-visible-change="onModuleDropdownVisibleChange"
              @change="onElementModuleChange"
            >
              <a-option
                v-for="module in flatModuleOptions"
                :key="module.id"
                :value="module.id"
                :label="getModuleOptionLabel(module)"
              >
                {{ getModuleOptionLabel(module) }}
              </a-option>
            </a-select>
          </a-form-item>
          <a-form-item :label="stepText.selectPage">
            <a-select
              v-model="selectedElementPage"
              :placeholder="stepText.pleaseSelectPage"
              allow-search
              allow-clear
              :disabled="!selectedElementModule"
              @change="onElementPageChange"
            >
              <a-option v-for="page in pageOptions" :key="page.id" :value="page.id">
                {{ page.name }}
              </a-option>
            </a-select>
          </a-form-item>
          <a-form-item field="element" :label="stepText.selectElement">
            <a-select
              v-model="formData.element"
              :placeholder="stepText.pleaseSelectElement"
              allow-search
              allow-clear
              :disabled="!selectedElementPage"
            >
              <a-option v-for="el in elementOptions" :key="el.id" :value="el.id">
                {{ el.name }}
              </a-option>
            </a-select>
          </a-form-item>
          <a-form-item field="ope_key" :label="stepText.actionMethod">
            <a-select v-model="formData.ope_key" allow-search @change="onOpeKeyChange">
              <a-optgroup :label="stepText.groupMouse">
                <a-option value="click">{{ stepText.clickOption }}</a-option>
                <a-option value="dblclick">{{ stepText.dblclickOption }}</a-option>
                <a-option value="hover">{{ stepText.hoverOption }}</a-option>
                <a-option value="focus">{{ stepText.focusOption }}</a-option>
              </a-optgroup>
              <a-optgroup :label="stepText.groupKeyboard">
                <a-option value="fill">{{ stepText.fillOption }}</a-option>
                <a-option value="type">{{ stepText.typeOption }}</a-option>
                <a-option value="clear">{{ stepText.clearOption }}</a-option>
                <a-option value="press">{{ stepText.pressOption }}</a-option>
              </a-optgroup>
              <a-optgroup :label="stepText.groupSelect">
                <a-option value="select_option">{{ stepText.selectOption }}</a-option>
                <a-option value="check">{{ stepText.checkOption }}</a-option>
                <a-option value="uncheck">{{ stepText.uncheckOption }}</a-option>
              </a-optgroup>
              <a-optgroup :label="stepText.groupFile">
                <a-option value="upload">{{ stepText.uploadOption }}</a-option>
              </a-optgroup>
              <a-optgroup :label="stepText.groupPage">
                <a-option value="goto">{{ stepText.gotoOption }}</a-option>
                <a-option value="reload">{{ stepText.reloadOption }}</a-option>
                <a-option value="go_back">{{ stepText.goBackOption }}</a-option>
                <a-option value="go_forward">{{ stepText.goForwardOption }}</a-option>
                <a-option value="switch_tab">{{ stepText.switchTabOption }}</a-option>
                <a-option value="wait">{{ stepText.waitOption }}</a-option>
                <a-option value="wait_load">{{ stepText.waitLoadOption }}</a-option>
                <a-option value="wait_network">{{ stepText.waitNetworkOption }}</a-option>
                <a-option value="screenshot">{{ stepText.screenshotOption }}</a-option>
              </a-optgroup>
            </a-select>
          </a-form-item>
          <!-- 根据操作类型动态渲染参数表单 -->
          <template v-if="currentOpeParams.length > 0">
            <a-form-item
              v-for="param in currentOpeParams"
              :key="param.field"
              :field="'opeParams.' + param.field"
              :label="getParamLabel(param)"
              :required="param.required"
            >
              <a-input
                v-if="param.type === 'input'"
                v-model="opeParams[param.field]"
                :placeholder="getParamPlaceholder(param)"
              />
              <a-input-number
                v-else-if="param.type === 'number'"
                v-model="opeParams[param.field]"
                :placeholder="getParamPlaceholder(param)"
                :min="param.min"
                :max="param.max"
              />
              <a-textarea
                v-else-if="param.type === 'textarea'"
                v-model="opeParams[param.field]"
                :placeholder="getParamPlaceholder(param)"
                :auto-size="{ minRows: 2, maxRows: 5 }"
              />
              <div v-else-if="param.type === 'file'" class="upload-param-row">
                <input id="ui-upload-file-input" type="file" class="hidden-file-input" @change="handleUploadFileChange" />
                <a-dropdown trigger="click">
                  <a-button type="outline" :loading="uploadingFile">
                    <template #icon><icon-upload /></template>
                    {{ opeParams.file_name || stepText.chooseUploadFile }}
                  </a-button>
                  <template #content>
                    <a-doption @click="openManagedFileChoose">{{ stepText.chooseFromFileManagement }}</a-doption>
                    <a-doption @click="openUploadFilePicker">{{ stepText.uploadLocalFile }}</a-doption>
                  </template>
                </a-dropdown>
                <a-button v-if="opeParams.file_id" type="text" status="danger" @click="clearUploadFile">{{ stepText.clearUploadFile }}</a-button>
              </div>
            </a-form-item>
          </template>
        </template>

        <!-- 断言操作 -->
        <template v-else-if="formData.step_type === 1">
          <a-form-item :label="stepText.selectModule">
            <a-select
              v-model="selectedElementModule"
              :placeholder="stepText.pleaseSelectModule"
              allow-search
              allow-clear
              @popup-visible-change="onModuleDropdownVisibleChange"
              @change="onElementModuleChange"
            >
              <a-option
                v-for="module in flatModuleOptions"
                :key="module.id"
                :value="module.id"
                :label="getModuleOptionLabel(module)"
              >
                {{ getModuleOptionLabel(module) }}
              </a-option>
            </a-select>
          </a-form-item>
          <a-form-item :label="stepText.selectPage">
            <a-select
              v-model="selectedElementPage"
              :placeholder="stepText.pleaseSelectPage"
              allow-search
              allow-clear
              :disabled="!selectedElementModule"
              @change="onElementPageChange"
            >
              <a-option v-for="page in pageOptions" :key="page.id" :value="page.id">
                {{ page.name }}
              </a-option>
            </a-select>
          </a-form-item>
          <a-form-item field="element" :label="stepText.assertElement">
            <a-select
              v-model="formData.element"
              :placeholder="stepText.pleaseSelectElement"
              allow-search
              allow-clear
              :disabled="!selectedElementPage"
            >
              <a-option v-for="el in elementOptions" :key="el.id" :value="el.id">
                {{ el.name }}
              </a-option>
            </a-select>
          </a-form-item>
          <a-form-item field="ope_key" :label="stepText.assertMethod">
            <a-select v-model="formData.ope_key" allow-search @change="onOpeKeyChange">
              <a-optgroup :label="stepText.groupAssertElement">
                <a-option value="assert_visible">{{ stepText.assertVisible }}</a-option>
                <a-option value="assert_hidden">{{ stepText.assertHidden }}</a-option>
                <a-option value="assert_enabled">{{ stepText.assertEnabled }}</a-option>
                <a-option value="assert_disabled">{{ stepText.assertDisabled }}</a-option>
                <a-option value="assert_checked">{{ stepText.assertChecked }}</a-option>
              </a-optgroup>
              <a-optgroup :label="stepText.groupAssertContent">
                <a-option value="assert_text">{{ stepText.assertText }}</a-option>
                <a-option value="assert_contain_text">{{ stepText.assertContainText }}</a-option>
                <a-option value="assert_value">{{ stepText.assertValue }}</a-option>
                <a-option value="assert_count">{{ stepText.assertCount }}</a-option>
              </a-optgroup>
              <a-optgroup :label="stepText.groupAssertPage">
                <a-option value="assert_url">{{ stepText.assertUrl }}</a-option>
                <a-option value="assert_title">{{ stepText.assertTitle }}</a-option>
              </a-optgroup>
            </a-select>
          </a-form-item>
          <!-- 根据断言类型动态渲染参数 -->
          <template v-if="currentOpeParams.length > 0">
            <a-form-item
              v-for="param in currentOpeParams"
              :key="param.field"
              :label="getParamLabel(param)"
              :required="param.required"
            >
              <a-input
                v-if="param.type === 'input'"
                v-model="opeParams[param.field]"
                :placeholder="getParamPlaceholder(param)"
              />
              <a-input-number
                v-else-if="param.type === 'number'"
                v-model="opeParams[param.field]"
                :placeholder="getParamPlaceholder(param)"
                :min="param.min"
                :max="param.max"
              />
            </a-form-item>
          </template>
        </template>

        <!-- SQL 操作 -->
        <template v-else-if="formData.step_type === 2">
          <a-form-item field="sql_execute" :label="stepText.sqlConfig">
            <a-textarea v-model="sqlExecuteStr" :placeholder="stepText.sqlConfigPlaceholder" :auto-size="{ minRows: 3 }" />
          </a-form-item>
        </template>

        <!-- 自定义变量 -->
        <template v-else-if="formData.step_type === 3">
          <a-form-item field="custom" :label="stepText.customVariable">
            <a-textarea v-model="customStr" :placeholder="stepText.customVariablePlaceholder" :auto-size="{ minRows: 3 }" />
          </a-form-item>
        </template>

        <!-- 条件判断 -->
        <template v-else-if="formData.step_type === 4">
          <a-form-item field="condition_value" :label="stepText.conditionConfig">
            <a-textarea v-model="conditionValueStr" :placeholder="stepText.conditionConfigPlaceholder" :auto-size="{ minRows: 3 }" />
          </a-form-item>
        </template>

        <a-form-item field="description" :label="stepText.description">
          <a-input v-model="formData.description" :placeholder="stepText.optionalDescription" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:visible="managedFileChooseVisible" :title="stepText.chooseFromFileManagement" :footer="false" width="720px">
      <a-input-search
        v-model="managedFileKeyword"
        :placeholder="stepText.searchFilePlaceholder"
        allow-clear
        class="managed-file-search"
        @search="loadManagedFilesForChoose"
        @clear="loadManagedFilesForChoose"
      />
      <a-table :loading="managedFileLoading" :data="managedFileOptions" row-key="id" :pagination="false" size="small">
        <template #columns>
          <a-table-column :title="stepText.fileNameColumn" data-index="name">
            <template #cell="{ record }">{{ record.name || record.original_name }}</template>
          </a-table-column>
          <a-table-column :title="stepText.fileTypeColumn" data-index="mime_type" :width="160" />
          <a-table-column :title="stepText.fileRefsColumn" data-index="reference_count" :width="80" />
          <a-table-column :title="stepText.actionColumn" :width="90">
            <template #cell="{ record }">
              <a-button size="mini" type="primary" @click="chooseManagedFile(record)">{{ stepText.selectFileAction }}</a-button>
            </template>
          </a-table-column>
        </template>
      </a-table>
    </a-modal>

  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed, onMounted, onUnmounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconPlus, IconEdit, IconDelete, IconDragDotVertical, IconPlayArrow, IconUpload } from '@arco-design/web-vue/es/icon'
import draggable from 'vuedraggable'
import { useAppI18n } from '@/composables/useAppI18n'
import { pageStepsDetailedApi, elementApi, actuatorApi, envConfigApi, moduleApi, pageApi, type ActuatorInfo } from '../api'
import type { UiPageStepsDetailed, UiPageSteps, UiElement, UiModule, UiPage, StepType, UiEnvironmentConfig } from '../types'
import { STEP_TYPE_LABELS, extractListData, extractResponseData } from '../types'
import { uiWebSocket, UiSocketEnum } from '../services/websocket'
import { fileService } from '@/features/file-management/services/fileService'

/** 操作参数定义 */
interface OpeParamDef {
  field: string
  label: string
  type: 'input' | 'number' | 'textarea' | 'file'
  placeholder: string
  required?: boolean
  min?: number
  max?: number
}

/** 操作方法与参数的映射 */
const OPE_PARAMS_MAP: Record<string, OpeParamDef[]> = {
  // 元素操作
  fill: [{ field: 'text', label: '输入内容', type: 'input', placeholder: '请输入要填充的文本', required: true }],
  type: [{ field: 'text', label: '输入内容', type: 'input', placeholder: '请输入要键入的文本', required: true }],
  wait: [{ field: 'timeout', label: '等待时间(毫秒)', type: 'number', placeholder: '默认1000', min: 0, max: 60000 }],
  screenshot: [{ field: 'name', label: '截图文件名', type: 'input', placeholder: '可选，留空自动生成' }],
  select_option: [{ field: 'value', label: '选项值', type: 'input', placeholder: '请输入要选择的选项值', required: true }],
  press: [{ field: 'key', label: '按键值', type: 'input', placeholder: '例如 Enter, Tab, Escape 等', required: true }],
  upload: [{ field: 'file_id', label: '上传文件', type: 'file', placeholder: '请选择要上传的文件', required: true }],
  goto: [{ field: 'url', label: '目标 URL', type: 'input', placeholder: '请输入完整的网页地址，例如 https://www.google.com', required: true }],
  switch_tab: [{ field: 'value', label: '页签索引或关键字', type: 'input', placeholder: '请输入页签索引(从0开始)或URL/标题关键字', required: true }],
  // 断言操作
  assert_text: [{ field: 'expected', label: '期望文本', type: 'input', placeholder: '请输入期望的文本内容', required: true }],
  assert_contain_text: [{ field: 'expected', label: '期望包含的文本', type: 'input', placeholder: '请输入期望被包含的文本', required: true }],
  assert_value: [{ field: 'expected', label: '期望值', type: 'input', placeholder: '请输入期望的值', required: true }],
  assert_count: [{ field: 'expected', label: '期望数量', type: 'number', placeholder: '请输入期望的元素数量', required: true, min: 0 }],
  assert_url: [{ field: 'expected', label: '期望 URL', type: 'input', placeholder: '例如 https://example.com/dashboard', required: true }],
  assert_title: [{ field: 'expected', label: '期望页面标题', type: 'input', placeholder: '例如 首页', required: true }],
}

/** 操作方法标签映射 */
const OPE_KEY_LABELS: Record<string, string> = {
  click: '点击',
  dblclick: '双击',
  hover: '悬停',
  focus: '聚焦',
  fill: '填充',
  type: '输入',
  clear: '清空',
  press: '按键模拟',
  select_option: '选择下拉',
  check: '勾选',
  uncheck: '取消勾选',
  upload: '上传文件',
  goto: '访问网页',
  reload: '刷新页面',
  go_back: '页面后退',
  go_forward: '页面前进',
  switch_tab: '切换页签',
  wait: '等待',
  wait_load: '等待页面加载',
  wait_network: '等待网络空闲',
  screenshot: '截图',
  assert_visible: '元素可见',
  assert_hidden: '元素隐藏',
  assert_enabled: '元素已启用',
  assert_disabled: '元素被禁用',
  assert_checked: '单/复选框被选中',
  assert_text: '文本等于',
  assert_contain_text: '文本包含',
  assert_value: '值等于',
  assert_count: '数量等于',
  assert_url: '页面URL等于',
  assert_title: '页面标题等于',
}

/** 格式化操作值显示 */
const formatOpeValue = (opeValue: Record<string, any>) => {
  if (opeValue.file_name) return `file: ${opeValue.file_name}`
  const entries = Object.entries(opeValue).filter(([k, v]) => !['file_id', 'mime_type'].includes(k) && v !== null && v !== undefined && v !== '')
  if (entries.length === 0) return ''
  return entries.map(([k, v]) => `${k}: ${typeof v === 'string' && v.length > 30 ? v.slice(0, 30) + '...' : v}`).join(', ')
}

/** 获取操作方法的显示标签 */
const { isEnglish } = useAppI18n()

const stepText = computed(() => isEnglish.value
  ? {
      stepListTitle: 'Action Steps (drag to reorder)',
      executionEnv: 'Environment',
      default: 'Default',
      selectActuator: 'Select actuator',
      offline: 'Offline',
      debugRun: 'Debug Run',
      addAction: 'Add action',
      emptyActions: 'No action steps',
      elementLabel: 'Element:',
      actionLabel: 'Action:',
      paramsLabel: 'Params:',
      sqlAction: 'SQL Action',
      customVariable: 'Custom variable',
      conditionJudge: 'Condition',
      deleteActionConfirm: 'Delete this action?',
      editAction: 'Edit action',
      actionType: 'Action Type',
      selectModule: 'Select module',
      pleaseSelectModule: 'Please select a module',
      selectPage: 'Select page',
      pleaseSelectPage: 'Please select a page',
      fetchModulesFailed: 'Failed to fetch module list',
      fetchPagesFailed: 'Failed to fetch page list',
      selectElement: 'Select element',
      pleaseSelectElement: 'Please select an element',
      actionMethod: 'Action Method',
      mouseActions: 'Mouse Actions',
      inputActions: 'Input Actions',
      otherActions: 'Other',
      groupMouse: 'Mouse Actions',
      groupKeyboard: 'Keyboard Actions',
      groupSelect: 'Select/Check',
      groupFile: 'File Actions',
      groupPage: 'Page Actions',
      clickOption: 'Click (click)',
      dblclickOption: 'Double click (dblclick)',
      hoverOption: 'Hover (hover)',
      focusOption: 'Focus (focus)',
      fillOption: 'Fill (fill)',
      typeOption: 'Type (type)',
      clearOption: 'Clear (clear)',
      pressOption: 'Press key (press)',
      selectOption: 'Select option (select_option)',
      checkOption: 'Check (check)',
      uncheckOption: 'Uncheck (uncheck)',
      uploadOption: 'Upload file (upload)',
      chooseUploadFile: 'Choose file',
      chooseFromFileManagement: 'Choose from file management',
      uploadLocalFile: 'Upload local file',
      searchFilePlaceholder: 'Search file name/type',
      loadFilesFailed: 'Failed to load files',
      fileNameColumn: 'File name',
      fileTypeColumn: 'Type',
      fileRefsColumn: 'Refs',
      actionColumn: 'Action',
      selectFileAction: 'Select',
      clearUploadFile: 'Clear',
      uploadSuccess: 'File uploaded',
      uploadFailed: 'File upload failed',
      selectProjectFirst: 'Please select a project first',
      gotoOption: 'Navigate to URL (goto)',
      reloadOption: 'Reload page (reload)',
      goBackOption: 'Go back (go_back)',
      goForwardOption: 'Go forward (go_forward)',
      switchTabOption: 'Switch tab (switch_tab)',
      waitOption: 'Wait (wait)',
      waitLoadOption: 'Wait for load (wait_load)',
      waitNetworkOption: 'Wait for network idle (wait_network)',
      screenshotOption: 'Screenshot (screenshot)',
      assertElement: 'Assertion Element',
      assertMethod: 'Assertion Method',
      assertVisible: 'Element visible (assert_visible)',
      assertHidden: 'Element hidden (assert_hidden)',
      assertEnabled: 'Element enabled (assert_enabled)',
      assertDisabled: 'Element disabled (assert_disabled)',
      assertChecked: 'Checkbox checked (assert_checked)',
      assertText: 'Text equals (assert_text)',
      assertContainText: 'Text contains (assert_contain_text)',
      assertValue: 'Value equals (assert_value)',
      assertCount: 'Count equals (assert_count)',
      assertUrl: 'URL equals (assert_url)',
      assertTitle: 'Title equals (assert_title)',
      groupAssertElement: 'Element State',
      groupAssertContent: 'Content Verification',
      groupAssertPage: 'Page Verification',
      sqlConfig: 'SQL Config',
      sqlConfigPlaceholder: 'SQL config in JSON format',
      customVariablePlaceholder: 'Variable definition in JSON format',
      conditionConfig: 'Condition Config',
      conditionConfigPlaceholder: 'Condition config in JSON format',
      description: 'Description',
      optionalDescription: 'Optional description',
      selectActionTypeRequired: 'Select an action type',
      fetchActionStepsFailed: 'Failed to fetch action steps',
      selectActuatorFirst: 'Please select an actuator first',
      noActionSteps: 'This page step has no actions',
      websocketFailed: 'WebSocket connection failed. Please refresh and try again',
      sendExecutionFailed: 'Failed to send execution command',
      executionSuccess: (passed: number, total: number) => `Execution succeeded: ${passed}/${total} steps passed`,
      executionFailed: (message: string) => `Execution failed: ${message}`,
      unknownError: 'Unknown error',
      fetchElementsFailed: 'Failed to fetch element list',
      fillRequired: 'Fill in the required fields',
      enterContent: 'Enter content',
      updateSuccess: 'Updated successfully',
      addSuccess: 'Added successfully',
      updateFailed: 'Update failed',
      addFailed: 'Add failed',
      deleteSuccess: 'Deleted successfully',
      deleteFailed: 'Delete failed',
      sortSaved: 'Order saved',
      saveSortFailed: 'Failed to save order',
    }
  : {
      stepListTitle: '操作步骤（拖拽可排序）',
      executionEnv: '执行环境',
      default: '默认',
      selectActuator: '选择执行器',
      offline: '离线',
      debugRun: '调试执行',
      addAction: '添加操作',
      emptyActions: '暂无操作步骤',
      elementLabel: '元素:',
      actionLabel: '操作:',
      paramsLabel: '参数:',
      sqlAction: 'SQL操作',
      customVariable: '自定义变量',
      conditionJudge: '条件判断',
      deleteActionConfirm: '确定删除该操作？',
      editAction: '编辑操作',
      actionType: '操作类型',
      selectModule: '选择模块',
      pleaseSelectModule: '请选择模块',
      selectPage: '选择页面',
      pleaseSelectPage: '请选择页面',
      fetchModulesFailed: '获取模块列表失败',
      fetchPagesFailed: '获取页面列表失败',
      selectElement: '选择元素',
      pleaseSelectElement: '请选择元素',
      actionMethod: '操作方法',
      mouseActions: '鼠标操作',
      inputActions: '输入操作',
      otherActions: '其他',
      groupMouse: '鼠标/点击',
      groupKeyboard: '键盘/输入',
      groupSelect: '选择/勾选',
      groupFile: '文件操作',
      groupPage: '页面操作',
      clickOption: '点击 (click)',
      dblclickOption: '双击 (dblclick)',
      hoverOption: '悬停 (hover)',
      focusOption: '聚焦 (focus)',
      fillOption: '填充 (fill)',
      typeOption: '输入 (type)',
      clearOption: '清空 (clear)',
      pressOption: '按键模拟 (press)',
      selectOption: '选择下拉 (select_option)',
      checkOption: '勾选 (check)',
      uncheckOption: '取消勾选 (uncheck)',
      uploadOption: '上传文件 (upload)',
      chooseUploadFile: '选择文件',
      chooseFromFileManagement: '文件管理选择',
      uploadLocalFile: '上传本地文件',
      searchFilePlaceholder: '搜索文件名/类型',
      loadFilesFailed: '加载文件失败',
      fileNameColumn: '文件名',
      fileTypeColumn: '类型',
      fileRefsColumn: '引用',
      actionColumn: '操作',
      selectFileAction: '选择',
      clearUploadFile: '清除',
      uploadSuccess: '文件已上传',
      uploadFailed: '文件上传失败',
      selectProjectFirst: '请先选择项目',
      gotoOption: '访问网页 (goto)',
      reloadOption: '刷新页面 (reload)',
      goBackOption: '页面后退 (go_back)',
      goForwardOption: '页面前进 (go_forward)',
      switchTabOption: '切换页签 (switch_tab)',
      waitOption: '等待 (wait)',
      waitLoadOption: '等待加载 (wait_load)',
      waitNetworkOption: '等待网络空闲 (wait_network)',
      screenshotOption: '截图 (screenshot)',
      assertElement: '断言元素',
      assertMethod: '断言方法',
      assertVisible: '元素可见 (assert_visible)',
      assertHidden: '元素隐藏 (assert_hidden)',
      assertEnabled: '元素已启用 (assert_enabled)',
      assertDisabled: '元素被禁用 (assert_disabled)',
      assertChecked: '单/复选框被选中 (assert_checked)',
      assertText: '文本等于 (assert_text)',
      assertContainText: '文本包含 (assert_contain_text)',
      assertValue: '值等于 (assert_value)',
      assertCount: '数量等于 (assert_count)',
      assertUrl: '页面URL等于 (assert_url)',
      assertTitle: '页面标题等于 (assert_title)',
      groupAssertElement: '元素状态',
      groupAssertContent: '内容校验',
      groupAssertPage: '页面校验',
      sqlConfig: 'SQL 配置',
      sqlConfigPlaceholder: 'JSON 格式 SQL 配置',
      customVariablePlaceholder: 'JSON 格式变量定义',
      conditionConfig: '条件配置',
      conditionConfigPlaceholder: 'JSON 格式条件配置',
      description: '描述',
      optionalDescription: '可选描述',
      selectActionTypeRequired: '请选择操作类型',
      fetchActionStepsFailed: '获取操作步骤失败',
      selectActuatorFirst: '请先选择执行器',
      noActionSteps: '该页面步骤没有操作',
      websocketFailed: 'WebSocket 连接失败，请刷新页面重试',
      sendExecutionFailed: '发送执行命令失败',
      executionSuccess: (passed: number, total: number) => `执行成功: ${passed}/${total} 步骤通过`,
      executionFailed: (message: string) => `执行失败: ${message}`,
      unknownError: '未知错误',
      fetchElementsFailed: '获取元素列表失败',
      fillRequired: '请填写必填项',
      enterContent: '请输入内容',
      updateSuccess: '更新成功',
      addSuccess: '添加成功',
      updateFailed: '更新失败',
      addFailed: '添加失败',
      deleteSuccess: '删除成功',
      deleteFailed: '删除失败',
      sortSaved: '排序已保存',
      saveSortFailed: '保存排序失败',
    }
)

const stepTypeLabels = computed<Record<StepType, string>>(() => isEnglish.value
  ? {
      0: 'Element Action',
      1: 'Assertion',
      2: 'SQL Action',
      3: 'Custom Variable',
      4: 'Condition',
    }
  : STEP_TYPE_LABELS
)

const opeKeyLabelsEn: Record<string, string> = {
  click: 'Click',
  dblclick: 'Double click',
  hover: 'Hover',
  focus: 'Focus',
  fill: 'Fill',
  type: 'Type',
  clear: 'Clear',
  press: 'Press key',
  select_option: 'Select option',
  check: 'Check',
  uncheck: 'Uncheck',
  upload: 'Upload file',
  goto: 'Navigate to URL',
  reload: 'Reload page',
  go_back: 'Go back',
  go_forward: 'Go forward',
  switch_tab: 'Switch tab',
  wait: 'Wait',
  wait_load: 'Wait for load',
  wait_network: 'Wait for network idle',
  screenshot: 'Screenshot',
  assert_visible: 'Element visible',
  assert_hidden: 'Element hidden',
  assert_enabled: 'Element enabled',
  assert_disabled: 'Element disabled',
  assert_checked: 'Checkbox checked',
  assert_text: 'Text equals',
  assert_contain_text: 'Text contains',
  assert_value: 'Value equals',
  assert_count: 'Count equals',
  assert_url: 'URL equals',
  assert_title: 'Title equals',
}

const paramLabelMap: Record<string, string> = {
  '输入内容': 'Input text',
  '等待时间(毫秒)': 'Wait time (ms)',
  '截图文件名': 'Screenshot filename',
  '选项值': 'Option value',
  '按键值': 'Key value',
  '文件路径': 'File path',
  '上传文件': 'Upload file',
  '目标 URL': 'Target URL',
  '页签索引或关键字': 'Tab index or keyword',
  '期望文本': 'Expected text',
  '期望包含的文本': 'Expected contained text',
  '期望值': 'Expected value',
  '期望数量': 'Expected count',
  '期望 URL': 'Expected URL',
  '期望页面标题': 'Expected title',
}

const paramPlaceholderMap: Record<string, string> = {
  '请输入要填充的文本': 'Enter the text to fill',
  '请输入要键入的文本': 'Enter the text to type',
  '默认1000': 'Default 1000',
  '可选，留空自动生成': 'Optional. Leave blank to auto-generate',
  '请输入要选择的选项值': 'Enter the option value to select',
  '例如 Enter, Tab, Escape 等': 'e.g. Enter, Tab, Escape etc.',
  '请输入要上传的文件绝对路径': 'Enter the absolute path to upload',
  '请选择要上传的文件': 'Choose a file to upload',
  '请输入完整的网页地址，例如 https://www.google.com': 'Enter full URL, e.g. https://www.google.com',
  '请输入页签索引(从0开始)或URL/标题关键字': 'Enter tab index (0-based) or URL/title keyword',
  '请输入期望的文本内容': 'Enter the expected text',
  '请输入期望被包含的文本': 'Enter the expected contained text',
  '请输入期望的值': 'Enter the expected value',
  '请输入期望的元素数量': 'Enter the expected element count',
  '例如 https://example.com/dashboard': 'e.g. https://example.com/dashboard',
  '例如 首页': 'e.g. Home',
}

const getStepTypeLabel = (stepType: StepType) => stepTypeLabels.value[stepType] || String(stepType)
const getOpeKeyLabel = (opeKey: string) => (isEnglish.value ? opeKeyLabelsEn[opeKey] : OPE_KEY_LABELS[opeKey]) || opeKey
const getParamLabel = (param: OpeParamDef) => isEnglish.value ? (paramLabelMap[param.label] || param.label) : param.label
const getParamPlaceholder = (param: OpeParamDef) => isEnglish.value ? (paramPlaceholderMap[param.placeholder] || param.placeholder) : param.placeholder

const props = defineProps<{ pageStep: UiPageSteps }>()

const loading = ref(false)
const submitting = ref(false)
const stepData = ref<UiPageStepsDetailed[]>([])
const moduleOptions = ref<UiModule[]>([])
const modulesLoading = ref(false)
const flatModuleOptions = computed(() => flattenModules(moduleOptions.value))
const pageOptions = ref<UiPage[]>([])
const elementOptions = ref<UiElement[]>([])
const selectedElementModule = ref<number | undefined>(undefined)
const selectedElementPage = ref<number | undefined>(undefined)
const modalVisible = ref(false)
const isEdit = ref(false)
const currentStep = ref<UiPageStepsDetailed | null>(null)
const formRef = ref()

// 执行器相关
const actuators = ref<ActuatorInfo[]>([])
const selectedActuator = ref<string>('')
const executing = ref(false)

// 执行环境相关
const envConfigs = ref<UiEnvironmentConfig[]>([])
const selectedEnvConfig = ref<number | undefined>(undefined)

const formData = reactive<Partial<UiPageStepsDetailed>>({
  step_type: 0,
  element: null,
  ope_key: '',
  ope_value: {},
  sql_execute: {},
  custom: {},
  condition_value: {},
  func: '',
  description: '',
})

const opeParams = reactive<Record<string, any>>({})
const uploadingFile = ref(false)
const managedFileChooseVisible = ref(false)
const managedFileLoading = ref(false)
const managedFileKeyword = ref('')
const managedFileOptions = ref<any[]>([])
const sqlExecuteStr = ref('{}')
const customStr = ref('{}')
const conditionValueStr = ref('{}')

/** 当前操作方法的参数定义 */
const currentOpeParams = computed(() => {
  return OPE_PARAMS_MAP[formData.ope_key || ''] || []
})

/** 操作方法变更时重置参数 */
const onOpeKeyChange = () => {
  Object.keys(opeParams).forEach(k => delete opeParams[k])
  uploadingFile.value = false
}

const rules = {
  step_type: [{ required: true, message: stepText.value.selectActionTypeRequired }],
  // 动态验证规则将在提交时检查
}

const stepTypeColors: Record<StepType, string> = {
  0: 'arcoblue',
  1: 'orange',
  2: 'purple',
  3: 'green',
  4: 'magenta',
}

const flattenModules = (modules: UiModule[], level = 0): (UiModule & { __level?: number })[] => {
  const result: (UiModule & { __level?: number })[] = []
  modules.forEach(module => {
    result.push({ ...module, __level: level })
    if (module.children?.length) {
      result.push(...flattenModules(module.children, level + 1))
    }
  })
  return result
}

const getModuleOptionLabel = (module: UiModule & { __level?: number }) => `${'　'.repeat(module.__level || 0)}${module.name}`

const fetchModules = async (force = false) => {
  if (!props.pageStep.project || modulesLoading.value) return
  if (!force && moduleOptions.value.length > 0) return
  modulesLoading.value = true
  try {
    const res = await moduleApi.tree(props.pageStep.project)
    const data = extractResponseData<UiModule[]>(res)
    moduleOptions.value = Array.isArray(data) ? data : []
  } catch {
    Message.error(stepText.value.fetchModulesFailed)
  } finally {
    modulesLoading.value = false
  }
}

const onModuleDropdownVisibleChange = async (visible: boolean) => {
  if (visible) {
    await fetchModules()
  }
}

const fetchPages = async (moduleId?: number | null) => {
  if (!moduleId) {
    pageOptions.value = []
    return
  }
  try {
    const res = await pageApi.list({ project: props.pageStep.project, module: moduleId })
    pageOptions.value = extractListData<UiPage>(res)
  } catch {
    Message.error(stepText.value.fetchPagesFailed)
  }
}

const fetchElementsByPage = async (pageId?: number | null) => {
  if (!pageId) {
    elementOptions.value = []
    return
  }
  try {
    const res = await elementApi.list({ page: pageId })
    elementOptions.value = extractListData<UiElement>(res)
  } catch {
    Message.error(stepText.value.fetchElementsFailed)
  }
}

const initElementSelector = async (moduleId?: number | null, pageId?: number | null, elementId?: number | null) => {
  selectedElementModule.value = moduleId || undefined
  selectedElementPage.value = pageId || undefined
  formData.element = elementId || null
  await fetchModules()
  await fetchPages(selectedElementModule.value)
  await fetchElementsByPage(selectedElementPage.value)
}

const initElementSelectorFromElement = async (elementId?: number | null) => {
  if (!elementId) {
    await initElementSelector(props.pageStep.module, props.pageStep.page, null)
    return
  }
  try {
    const elementRes = await elementApi.get(elementId)
    const element = extractResponseData<UiElement>(elementRes)
    if (!element?.page) {
      await initElementSelector(props.pageStep.module, props.pageStep.page, elementId)
      return
    }
    const pageRes = await pageApi.get(element.page)
    const page = extractResponseData<UiPage>(pageRes)
    await initElementSelector(page?.module || props.pageStep.module, element.page, elementId)
  } catch {
    await initElementSelector(props.pageStep.module, props.pageStep.page, elementId)
  }
}

const onElementModuleChange = async () => {
  selectedElementPage.value = undefined
  formData.element = null
  elementOptions.value = []
  await fetchPages(selectedElementModule.value)
}

const onElementPageChange = async () => {
  formData.element = null
  await fetchElementsByPage(selectedElementPage.value)
}

const fetchSteps = async () => {
  loading.value = true
  try {
    const res = await pageStepsDetailedApi.list({ page_step: props.pageStep.id })
    stepData.value = extractListData<UiPageStepsDetailed>(res)
  } catch {
    Message.error(stepText.value.fetchActionStepsFailed)
  } finally {
    loading.value = false
  }
}

const fetchActuators = async () => {
  try {
    const res = await actuatorApi.list()
    const data = extractResponseData<{ count: number; items: ActuatorInfo[] }>(res)
    actuators.value = data?.items ?? []
    // 自动选择第一个在线的执行器
    if (!selectedActuator.value && actuators.value.length > 0) {
      const available = actuators.value.find((a: ActuatorInfo) => a.is_open)
      if (available) selectedActuator.value = available.id
    }
  } catch {
    // 静默失败
  }
}

/** 获取执行环境列表 */
const fetchEnvConfigs = async () => {
  try {
    // 从页面步骤获取关联的项目ID
    const res = await envConfigApi.list({ project: props.pageStep.project })
    envConfigs.value = extractListData<UiEnvironmentConfig>(res)
    // 优先选择默认环境，如果没有默认环境则选择第一个环境配置
    if (!selectedEnvConfig.value && envConfigs.value.length > 0) {
      const defaultEnv = envConfigs.value.find(e => e.is_default)
      if (defaultEnv) {
        selectedEnvConfig.value = defaultEnv.id
      } else {
        // 如果没有默认环境，选择第一个环境配置
        selectedEnvConfig.value = envConfigs.value[0].id
      }
    }
  } catch {
    // 静默失败
  }
}

/** 执行页面步骤 */
const executePageStep = async () => {
  // 防止重复执行
  if (executing.value) {
    return
  }
  if (!selectedActuator.value) {
    Message.warning(stepText.value.selectActuatorFirst)
    return
  }
  if (stepData.value.length === 0) {
    Message.warning(stepText.value.noActionSteps)
    return
  }
  
  executing.value = true
  
  // 确保 WebSocket 已连接
  if (!uiWebSocket.connected.value) {
    try {
      await uiWebSocket.connect()
    } catch {
      Message.error(stepText.value.websocketFailed)
      executing.value = false
      return
    }
  }
  
  const sent = uiWebSocket.send(UiSocketEnum.PAGE_STEPS, {
    page_step_id: props.pageStep.id,
    env_config_id: selectedEnvConfig.value,
    actuator_id: selectedActuator.value,
  })
  
  if (!sent) {
    Message.error(stepText.value.sendExecutionFailed)
    executing.value = false
  }
}

/** 处理页面步骤执行结果 */
const handleStepResult = (data: any) => {
  executing.value = false
  const result = data.data?.func_args
  if (!result) return
  
  if (result.status === 'success') {
    Message.success(stepText.value.executionSuccess(result.passed_steps || 0, result.total_steps || 0))
  } else {
    Message.error(stepText.value.executionFailed(result.message || stepText.value.unknownError))
  }
}

const fetchElements = async () => {
  await initElementSelector(props.pageStep.module, props.pageStep.page, formData.element || null)
}

const resetForm = () => {
  Object.assign(formData, {
    step_type: 0,
    element: null,
    ope_key: '',
    ope_value: {},
    sql_execute: {},
    custom: {},
    condition_value: {},
    func: '',
    description: '',
  })
  selectedElementModule.value = props.pageStep.module
  selectedElementPage.value = props.pageStep.page
  Object.keys(opeParams).forEach(k => delete opeParams[k])
  sqlExecuteStr.value = '{}'
  customStr.value = '{}'
  conditionValueStr.value = '{}'
  formRef.value?.clearValidate()
}

const onStepTypeChange = async () => {
  formData.ope_key = ''
  formData.element = null
  if (formData.step_type === 0 || formData.step_type === 1) {
    await initElementSelector(props.pageStep.module, props.pageStep.page, null)
  }
}

const showAddModal = async () => {
  isEdit.value = false
  resetForm()
  modalVisible.value = true
  await initElementSelector(props.pageStep.module, props.pageStep.page, null)
}

const editStep = async (step: UiPageStepsDetailed) => {
  isEdit.value = true
  currentStep.value = step
  Object.assign(formData, {
    step_type: step.step_type,
    element: step.element,
    ope_key: step.ope_key || '',
    ope_value: step.ope_value || {},
    sql_execute: step.sql_execute || {},
    custom: step.custom || {},
    condition_value: step.condition_value || {},
    func: step.func || '',
    description: step.description || '',
  })
  if (step.step_type === 0 || step.step_type === 1) {
    await initElementSelectorFromElement(step.element)
  }
  // 从 ope_value 还原参数到 opeParams
  Object.keys(opeParams).forEach(k => delete opeParams[k])
  if (step.ope_value && typeof step.ope_value === 'object') {
    Object.assign(opeParams, step.ope_value)
    
    // 兼容性处理：如果 ope_value 使用 'value' 字段而不是 'text' 字段，进行转换
    if (step.ope_key === 'fill' && step.ope_value.value !== undefined && step.ope_value.text === undefined) {
      // 将 value 字段的内容复制到 text 字段，以兼容前端表单
      opeParams.text = step.ope_value.value
    }
  }
  sqlExecuteStr.value = JSON.stringify(step.sql_execute || {}, null, 2)
  customStr.value = JSON.stringify(step.custom || {}, null, 2)
  conditionValueStr.value = JSON.stringify(step.condition_value || {}, null, 2)
  modalVisible.value = true
}

const parseJson = (str: string, defaultVal: Record<string, unknown> = {}) => {
  try {
    return JSON.parse(str)
  } catch {
    return defaultVal
  }
}


const loadManagedFilesForChoose = async () => {
  if (!props.pageStep.project) return
  managedFileLoading.value = true
  try {
    const res: any = await fileService.list(props.pageStep.project, {
      page: 1,
      page_size: 50,
      search: managedFileKeyword.value || undefined,
      ordering: '-created_at',
    })
    const payload = res?.data?.data || res?.data || res
    managedFileOptions.value = Array.isArray(payload) ? payload : (payload.results || payload.data || [])
  } catch (error: any) {
    Message.error(error?.message || stepText.value.loadFilesFailed)
  } finally {
    managedFileLoading.value = false
  }
}

const openManagedFileChoose = async () => {
  if (!props.pageStep.project) {
    Message.warning(stepText.value.selectProjectFirst)
    return
  }
  managedFileChooseVisible.value = true
  await loadManagedFilesForChoose()
}

const chooseManagedFile = (file: any) => {
  const fileId = file.file_id || file.id
  opeParams.file_id = fileId
  opeParams.file_name = file.name || file.original_name
  opeParams.mime_type = file.mime_type || ''
  opeParams.value = `file_id:${fileId}`
  managedFileChooseVisible.value = false
}

const openUploadFilePicker = () => {
  const input = globalThis.document?.getElementById('ui-upload-file-input') as HTMLInputElement | null
  input?.click()
}

const handleUploadFileChange = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (!props.pageStep.project) {
    Message.warning(stepText.value.selectProjectFirst)
    input.value = ''
    return
  }
  uploadingFile.value = true
  try {
    const res: any = await fileService.upload(props.pageStep.project, [file])
    const payload = res?.data?.data || res?.data || res
    const uploaded = Array.isArray(payload) ? payload[0] : payload
    const fileId = uploaded.file_id || uploaded.id
    opeParams.file_id = fileId
    opeParams.file_name = uploaded.name || uploaded.original_name || file.name
    opeParams.mime_type = uploaded.mime_type || file.type
    opeParams.value = `file_id:${fileId}`
    Message.success(stepText.value.uploadSuccess)
  } catch (error: any) {
    Message.error(error?.message || stepText.value.uploadFailed)
  } finally {
    uploadingFile.value = false
    input.value = ''
  }
}

const clearUploadFile = () => {
  delete opeParams.file_id
  delete opeParams.file_name
  delete opeParams.mime_type
  delete opeParams.value
}

/** 构建 ope_value：从 opeParams 中过滤空值 */
const buildOpeValue = () => {
  const result: Record<string, any> = {}
  for (const [k, v] of Object.entries(opeParams)) {
    if (v !== '' && v !== undefined && v !== null) {
      result[k] = v
    }
  }
  
  // 兼容性处理：对于 fill 操作，如果存在 text 字段，也同步到 value 字段
  // 这样后端执行器可以正确识别两种格式
  if (formData.ope_key === 'fill' && result.text !== undefined) {
    result.value = result.text
  }
  
  return Object.keys(result).length > 0 ? result : undefined
}

const handleSubmit = async (done: (closed: boolean) => void) => {
  try {
    await formRef.value?.validate()
  } catch {
    Message.warning(stepText.value.fillRequired)
    done(false)
    return
  }
  
  // 额外的业务逻辑校验：对于 fill 操作，必须填写输入内容
  if (formData.ope_key === 'fill') {
    const textValue = opeParams.text
    if (!textValue || textValue.trim() === '') {
      Message.warning(stepText.value.enterContent)
      done(false)
      return
    }
  }
  if (formData.ope_key === 'upload' && !opeParams.file_id) {
    Message.warning(stepText.value.chooseUploadFile)
    done(false)
    return
  }
  submitting.value = true
  try {
    const data: Omit<UiPageStepsDetailed, 'id' | 'created_at' | 'updated_at'> = {
      page_step: props.pageStep.id,
      step_type: formData.step_type as StepType,
      element: formData.element || null,
      step_sort: isEdit.value && currentStep.value ? currentStep.value.step_sort : stepData.value.length,
      ope_key: formData.ope_key || undefined,
      ope_value: buildOpeValue(),
      sql_execute: parseJson(sqlExecuteStr.value),
      custom: parseJson(customStr.value),
      condition_value: parseJson(conditionValueStr.value),
      func: formData.func || undefined,
      description: formData.description || undefined,
    }

    if (isEdit.value && currentStep.value?.id) {
      await pageStepsDetailedApi.update(currentStep.value.id, data)
      Message.success(stepText.value.updateSuccess)
    } else {
      await pageStepsDetailedApi.create(data)
      Message.success(stepText.value.addSuccess)
    }
    done(true)
    fetchSteps()
  } catch (error: unknown) {
    const err = error as { errors?: Record<string, string[]>; error?: string }
    const errors = err?.errors
    if (errors && typeof errors === 'object' && !('error' in errors) && !('message' in errors)) {
      const messages = Object.entries(errors)
        .map(([field, msgs]) => `${field}: ${Array.isArray(msgs) ? msgs.join(', ') : msgs}`)
        .join('\n')
      Message.error({ content: messages, duration: 5000 })
    } else {
      Message.error(err?.error || (isEdit.value ? stepText.value.updateFailed : stepText.value.addFailed))
    }
    done(false)
  } finally {
    submitting.value = false
  }
}

const handleCancel = () => {
  modalVisible.value = false
}

const deleteStep = async (step: UiPageStepsDetailed) => {
  if (!step.id) return
  try {
    await pageStepsDetailedApi.delete(step.id)
    Message.success(stepText.value.deleteSuccess)
    fetchSteps()
  } catch {
    Message.error(stepText.value.deleteFailed)
  }
}

const onDragEnd = async () => {
  try {
    const steps = stepData.value.map((s, idx) => ({
      step_type: s.step_type,
      element: s.element,
      step_sort: idx,
      ope_key: s.ope_key,
      ope_value: s.ope_value,
      sql_execute: s.sql_execute,
      custom: s.custom,
      condition_value: s.condition_value,
      func: s.func,
      description: s.description,
    }))
    await pageStepsDetailedApi.batchUpdate(props.pageStep.id, steps)
    Message.success(stepText.value.sortSaved)
  } catch {
    Message.error(stepText.value.saveSortFailed)
    fetchSteps()
  }
}

// WebSocket 事件监听
let offStepResult: (() => void) | null = null

watch(() => props.pageStep, async () => {
  fetchSteps()
  moduleOptions.value = []
  // 页面和元素按当前页面步骤默认值初始化；同时加载模块树确保初次渲染不会回显ID，支持跨模块/页面
  await Promise.all([
    fetchModules(true),
    fetchElements(),
    fetchActuators(),
    fetchEnvConfigs()
  ])
}, { immediate: true })

onMounted(() => {
  fetchActuators()
  fetchEnvConfigs()
  // 监听页面步骤执行结果
  offStepResult = uiWebSocket.on(UiSocketEnum.PAGE_STEP_RESULT, handleStepResult)
})

onUnmounted(() => {
  offStepResult?.()
})
</script>

<style scoped>
.step-detail-list {
  padding: 8px 0;
  overflow-x: hidden;
}
.step-detail-list :deep(.arco-spin) {
  width: 100%;
}
.step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.step-title {
  font-weight: 500;
}
.empty-tips {
  padding: 40px 0;
}
.step-card {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  margin-bottom: 8px;
  background: var(--color-bg-2);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  box-sizing: border-box;
  min-height: 48px;
  font-size: 13px;
  gap: 12px;
}
.step-left {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}
.drag-handle {
  cursor: move;
  color: var(--color-text-3);
  width: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 8px;
}
.step-index {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-fill-3);
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  margin-right: 10px;
}
.step-type {
  flex-shrink: 0;
}
.step-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}
.info-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.info-label {
  color: var(--color-text-3);
  font-size: 12px;
  flex-shrink: 0;
}
.element-name {
  color: rgb(var(--primary-6));
  font-weight: 500;
}
.ope-key {
  background: var(--color-fill-2);
  padding: 2px 6px;
  border-radius: 3px;
}
.ope-value {
  color: var(--color-text-2);
  background: var(--color-fill-1);
  padding: 2px 6px;
  border-radius: 3px;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sql-info,
.custom-info,
.condition-info {
  background: rgb(var(--orange-2));
  color: rgb(var(--orange-6));
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 12px;
}
.step-desc {
  color: var(--color-text-3);
  font-style: italic;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.step-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.hidden-file-input { display: none; }
.upload-param-row { display: flex; align-items: center; gap: 8px; }
.managed-file-search { margin-bottom: 12px; }
</style>
