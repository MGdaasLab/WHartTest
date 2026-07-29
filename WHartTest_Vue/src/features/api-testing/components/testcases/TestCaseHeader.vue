<script setup lang="ts">
import { ref } from 'vue'
import { IconFire, IconClose, IconCheck, IconPlayArrow, IconHistory } from '@arco-design/web-vue/es/icon'
import TestCaseBasicInfoComp from './TestCaseBasicInfo.vue'
import GroupManager from './GroupManager.vue'
import TagManager from './TagManager.vue'
import TestCaseConfigDialog from './TestCaseConfigDialog.vue'
import { useEnvironmentStore } from '../../stores/environmentStore'
import { Message } from '@arco-design/web-vue'

interface BasicInfoData {
  name: string
  description: string
  priority: string
  group: number | null
  tags: number[]
  config: Record<string, any>
  [key: string]: any
}

interface Props {
  modelValue: BasicInfoData
  loading?: boolean
  readonly?: boolean
  projectId: number
  testCaseId?: number
  steps?: {
    id: number
    name: string
    interface_data: {
      extract?: Record<string, string>
    }
  }[]
}

const props = defineProps<Props>()
const emit = defineEmits(['update:modelValue', 'cancel', 'save', 'run', 'show-report'])

const environmentStore = useEnvironmentStore()
const isRunning = ref(false)

const updateValue = (key: string, value: any) => {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

const handleCancel = () => {
  emit('cancel')
}

const handleSave = () => {
  emit('save')
}

const handleRun = async () => {
  if (!props.testCaseId) {
    Message.warning('请先保存用例')
    return
  }

  if (!environmentStore.currentEnvironmentId) {
    Message.warning('请先选择环境')
    return
  }

  emit('run', {
    testCaseId: props.testCaseId,
    environmentId: Number(environmentStore.currentEnvironmentId)
  })
}

const handleShowReport = () => {
  if (!props.testCaseId) {
    Message.warning('请先保存用例')
    return
  }

  emit('show-report', props.testCaseId)
}
</script>

<template>
  <div class="testcase-header flex justify-between items-center">
    <div class="flex items-center gap-4 flex-wrap">
      <test-case-basic-info-comp
        :model-value="modelValue"
        @update:model-value="val => emit('update:modelValue', val)"
        :readonly="readonly"
      />

      <group-manager
        :model-value="modelValue.group"
        @update:model-value="val => updateValue('group', val)"
        :readonly="readonly"
        :project-id="projectId"
      />

      <tag-manager
        :model-value="modelValue.tags"
        @update:model-value="val => updateValue('tags', val)"
        :readonly="readonly"
        :project-id="projectId"
      />

      <a-select
        :model-value="modelValue.priority"
        @update:model-value="val => updateValue('priority', val)"
        placeholder="优先级"
        class="!w-24"
        :disabled="readonly"
      >
        <template #prefix>
          <icon-fire />
        </template>
        <a-option value="P0">P0</a-option>
        <a-option value="P1">P1</a-option>
        <a-option value="P2">P2</a-option>
        <a-option value="P3">P3</a-option>
      </a-select>

      <test-case-config-dialog
        :model-value="modelValue.config"
        @update:model-value="val => updateValue('config', val)"
        :readonly="readonly"
        :steps="props.steps"
      />
    </div>

    <div class="flex items-center gap-3">
      <a-button
        v-if="testCaseId"
        type="outline"
        size="small"
        status="normal"
        class="!flex !items-center !gap-1 !h-8 btn-run"
        :loading="isRunning"
        @click="handleRun"
      >
        <template #icon>
          <icon-play-arrow class="!text-[#10B981]" />
        </template>
        <span class="!text-[#10B981]">运行</span>
      </a-button>

      <a-button
        v-if="testCaseId"
        type="outline"
        size="small"
        status="normal"
        class="!flex !items-center !gap-1 !h-8 btn-report"
        @click="handleShowReport"
      >
        <template #icon>
          <icon-history class="!text-[#F97316]" />
        </template>
        <span class="!text-[#F97316]">报告</span>
      </a-button>

      <a-button
        type="outline"
        size="small"
        status="normal"
        class="!flex !items-center !gap-1 !h-8 btn-cancel"
        @click="handleCancel"
      >
        <template #icon>
          <icon-close class="cancel-icon" />
        </template>
        <span class="cancel-text">取消</span>
      </a-button>

      <a-button
        v-if="!readonly"
        type="outline"
        size="small"
        status="normal"
        class="!flex !items-center !gap-1 !h-8 btn-save"
        :loading="loading"
        @click="handleSave"
      >
        <template #icon>
          <icon-check class="!text-[#8B5CF6]" />
        </template>
        <span class="!text-[#8B5CF6]">保存</span>
      </a-button>
    </div>
  </div>
</template>

<style lang="postcss" scoped>
@reference "tailwindcss";
:global(.arco-modal-mask) {
  backdrop-filter: blur(4px) !important;
  background: rgba(15, 23, 42, 0.2) !important;
}

:global(.arco-modal) {
  background: #ffffff !important;
  border-radius: 12px !important;
  border: 1px solid rgba(148, 163, 184, 0.16) !important;
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.16) !important;
}

:global(.arco-modal-header) {
  background: transparent !important;
  border-bottom: 1px solid rgba(148, 163, 184, 0.14) !important;
  padding-bottom: 1rem !important;
}

:global(.arco-modal-title) {
  color: #0f172a !important;
}

:global(.arco-modal-body) {
  background: transparent !important;
  padding-top: 1.5rem !important;
  padding-bottom: 1.5rem !important;
}

:global(.arco-modal-footer) {
  background: transparent !important;
  border-top: 1px solid rgba(148, 163, 184, 0.14) !important;
  padding-top: 1rem !important;
}

:global(body.api-testing-theme .arco-modal) {
  background: rgb(17, 24, 39) !important;
  border-color: rgba(75, 85, 99, 0.4) !important;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.08), 0 0 40px rgba(0, 0, 0, 0.55) !important;
}

:global(body.api-testing-theme .arco-modal-header) {
  border-bottom-color: rgba(75, 85, 99, 0.4) !important;
}

:global(body.api-testing-theme .arco-modal-title) {
  color: rgb(226, 232, 240) !important;
}

:global(body.api-testing-theme .arco-modal-footer) {
  border-top-color: rgba(75, 85, 99, 0.4) !important;
}

:deep(.arco-table) {
  @apply bg-transparent;
}

:deep(.arco-table-th) {
  background: var(--tcf-control-bg) !important;
  color: var(--tcf-text-subtle) !important;
  border-color: var(--tcf-panel-border) !important;
  &::before {
    background: var(--tcf-panel-border) !important;
  }
}

:deep(.arco-table-td) {
  background: transparent !important;
  color: var(--tcf-text-muted) !important;
  border-color: var(--tcf-panel-border) !important;
}

:deep(.arco-table-tr) {
  &:hover {
    .arco-table-td {
      background: var(--tcf-section-hover) !important;
    }
  }
}

:deep(.arco-input-wrapper) {
  background: var(--tcf-control-bg) !important;
  border-color: var(--tcf-control-border) !important;

  input {
    color: var(--tcf-text) !important;
    &::placeholder {
      color: var(--tcf-text-subtle) !important;
    }
  }
}

:deep(.arco-textarea-wrapper) {
  background: var(--tcf-control-bg) !important;
  border-color: var(--tcf-control-border) !important;

  textarea {
    color: var(--tcf-text) !important;
    &::placeholder {
      color: var(--tcf-text-subtle) !important;
    }
  }
}

:deep(.arco-btn-dashed) {
  border-color: var(--tcf-control-border) !important;
  color: var(--tcf-text-subtle) !important;

  &:hover {
    @apply border-blue-500 text-blue-500;
  }
}

:deep(.arco-btn-text) {
  color: var(--tcf-text-subtle) !important;

  &:hover {
    color: rgb(59, 130, 246) !important;
    background: rgba(59, 130, 246, 0.1) !important;

    &[status="danger"] {
      color: rgb(239, 68, 68) !important;
      background: rgba(239, 68, 68, 0.1) !important;
    }
  }
}

:deep(.arco-select-view) {
  background: var(--tcf-control-bg) !important;
  border-color: var(--tcf-control-border) !important;

  &:hover {
    background: var(--tcf-control-hover) !important;
    border-color: rgba(59, 130, 246, 0.24) !important;
  }
}

:deep(.arco-select-view-input),
:deep(.arco-select-view-value),
:deep(.arco-select-view-single .arco-select-view-value) {
  color: var(--tcf-text) !important;
}

:global(.arco-select-dropdown) {
  background: #ffffff !important;
  border: 1px solid rgba(148, 163, 184, 0.16) !important;
  border-radius: 10px !important;
}

:global(.arco-select-dropdown .arco-select-option) {
  color: #334155 !important;

  &:hover {
    background: #f8fafc !important;
  }
}

:global(.arco-select-dropdown .arco-select-option.arco-select-option-active) {
  background: rgba(59, 130, 246, 0.12) !important;
  color: #2563eb !important;
}

:global(body.api-testing-theme .arco-select-dropdown) {
  background: rgb(31, 41, 55) !important;
  border-color: rgba(75, 85, 99, 0.4) !important;
}

:global(body.api-testing-theme .arco-select-dropdown .arco-select-option) {
  color: rgb(203, 213, 225) !important;

  &:hover {
    background: rgba(51, 65, 85, 0.9) !important;
  }
}

.cancel-icon,
.cancel-text {
  color: var(--tcf-text-subtle) !important;
}

:deep(.arco-tag) {
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  max-width: 60px !important;
  height: 22px !important;
  margin: 0 !important;
  padding: 0 4px !important;
  background: rgba(148, 163, 184, 0.1) !important;
  border: 1px solid rgba(148, 163, 184, 0.2) !important;
  border-radius: 2px !important;

  .arco-tag-content {
    flex: 1 !important;
    min-width: 0 !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
    font-size: 12px !important;
    line-height: 20px !important;
    text-align: center !important;
  }

  .arco-icon-hover {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
  }

  .arco-tag-close-btn {
    flex-shrink: 0 !important;
    margin-left: 4px !important;
    width: 12px !important;
    height: 12px !important;
    font-size: 12px !important;
    line-height: 12px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
  }
}

/* 运行按钮样式 */
.btn-run {
  border-color: rgba(16, 185, 129, 0.2) !important;
  background-color: rgba(16, 185, 129, 0.05) !important;
  line-height: 1 !important;
  padding: 4px 10px !important;

  &:hover {
    border-color: rgba(16, 185, 129, 0.4) !important;
    background-color: rgba(16, 185, 129, 0.1) !important;
  }
}

/* 报告按钮样式 */
.btn-report {
  border-color: rgba(249, 115, 22, 0.2) !important;
  background-color: rgba(249, 115, 22, 0.05) !important;
  line-height: 1 !important;
  padding: 4px 10px !important;

  &:hover {
    border-color: rgba(249, 115, 22, 0.4) !important;
    background-color: rgba(249, 115, 22, 0.1) !important;
  }
}

/* 取消按钮样式 */
.btn-cancel {
  border-color: rgba(148, 163, 184, 0.2) !important;
  background-color: rgba(148, 163, 184, 0.05) !important;
  line-height: 1 !important;
  padding: 4px 10px !important;

  &:hover {
    border-color: rgba(148, 163, 184, 0.4) !important;
    background-color: rgba(148, 163, 184, 0.1) !important;
  }
}

/* 保存按钮样式 */
.btn-save {
  border-color: rgba(139, 92, 246, 0.3) !important;
  background-color: rgba(139, 92, 246, 0.05) !important;
  line-height: 1 !important;
  padding: 4px 10px !important;

  &:hover {
    border-color: rgba(139, 92, 246, 0.5) !important;
    background-color: rgba(139, 92, 246, 0.1) !important;
  }
}
</style>
