<script setup lang="ts">
import type { TestCaseStep } from '../../services/testcaseService'
import ApiHeadersConfig from '../interfaces/ApiHeadersConfig.vue'
import ApiParamsConfig from '../interfaces/ApiParamsConfig.vue'
import ApiPathParamsConfig from '../interfaces/ApiPathParamsConfig.vue'
import ApiBodyConfig from '../interfaces/ApiBodyConfig.vue'
import ApiSetupHooksConfig from '../interfaces/ApiSetupHooksConfig.vue'
import ApiTeardownHooksConfig from '../interfaces/ApiTeardownHooksConfig.vue'
import ApiExtractConfig from '../interfaces/ApiExtractConfig.vue'
import ApiAssertConfig from '../interfaces/ApiAssertConfig.vue'
import { ref } from 'vue'

interface Props {
  modelValue: TestCaseStep
  readonly?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  readonly: false
})

const emit = defineEmits(['update:modelValue'])

const headersRef = ref()
const paramsRef = ref()
const pathParamsRef = ref()
const bodyRef = ref()
const setupHooksRef = ref()
const teardownHooksRef = ref()
const extractRef = ref()
const assertRef = ref()

const activeTab = ref('headers')

const updateInterfaceData = (key: string, value: any) => {
  const updatedStep = {
    ...props.modelValue,
    interface_data: {
      ...props.modelValue.interface_data,
      [key]: value
    }
  }
  emit('update:modelValue', updatedStep)
}

const updateConfig = (key: string, value: any) => {
  const updatedStep = {
    ...props.modelValue,
    config: {
      ...props.modelValue.config,
      [key]: value
    }
  }
  emit('update:modelValue', updatedStep)
}

defineExpose({
  headersRef,
  paramsRef,
  pathParamsRef,
  bodyRef,
  setupHooksRef,
  teardownHooksRef,
  extractRef,
  assertRef
})
</script>

<template>
  <div class="step-config-container">
    <a-tabs v-model:active-key="activeTab" class="h-full">
      <a-tab-pane key="headers" title="Headers">
        <div class="p-4">
          <api-headers-config
            ref="headersRef"
            :model-value="modelValue.interface_data.headers"
            @update:model-value="val => updateInterfaceData('headers', val)"
            :readonly="readonly"
          />
        </div>
      </a-tab-pane>

      <a-tab-pane key="params" title="Params">
        <div class="p-4">
          <api-params-config
            ref="paramsRef"
            :model-value="modelValue.interface_data.params"
            @update:model-value="val => updateInterfaceData('params', val)"
            :readonly="readonly"
          />
        </div>
      </a-tab-pane>

      <a-tab-pane key="path_params" title="Path Params">
        <div class="p-4">
          <api-path-params-config
            ref="pathParamsRef"
            :path-params="modelValue.interface_data.path_params"
            :url="modelValue.interface_data.url"
            @update:path-params="val => updateInterfaceData('path_params', val)"
            :readonly="readonly"
          />
        </div>
      </a-tab-pane>

      <a-tab-pane key="body" title="Body">
        <div class="p-4">
          <api-body-config
            ref="bodyRef"
            :model-value="modelValue.interface_data.body"
            @update:model-value="val => updateInterfaceData('body', val)"
            :readonly="readonly"
          />
        </div>
      </a-tab-pane>

      <a-tab-pane key="setup_hooks" title="Setup Hooks">
        <div class="p-4">
          <api-setup-hooks-config
            ref="setupHooksRef"
            :model-value="modelValue.config.setup_hooks"
            @update:model-value="val => updateConfig('setup_hooks', val)"
            :readonly="readonly"
          />
        </div>
      </a-tab-pane>

      <a-tab-pane key="teardown_hooks" title="Teardown Hooks">
        <div class="p-4">
          <api-teardown-hooks-config
            ref="teardownHooksRef"
            :model-value="modelValue.config.teardown_hooks"
            @update:model-value="val => updateConfig('teardown_hooks', val)"
            :readonly="readonly"
          />
        </div>
      </a-tab-pane>

      <a-tab-pane key="extract" title="Extract">
        <div class="p-4">
          <api-extract-config
            ref="extractRef"
            :model-value="modelValue.config.extract"
            @update:model-value="val => updateConfig('extract', val)"
            :readonly="readonly"
          />
        </div>
      </a-tab-pane>

      <a-tab-pane key="assert" title="Assert">
        <div class="p-4">
          <api-assert-config
            ref="assertRef"
            :model-value="modelValue.config.validators"
            @update:model-value="val => updateConfig('validators', val)"
            :readonly="readonly"
          />
        </div>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<style lang="postcss" scoped>
@reference "tailwindcss";
:deep(.arco-tabs) {
  @apply h-full;
}

:deep(.arco-tabs-content) {
  @apply flex-1 min-h-0;
}

:deep(.arco-tabs-content-list) {
  @apply h-full;
}

:deep(.arco-tabs-pane) {
  @apply h-full overflow-y-auto;
}

:deep(.arco-tabs-nav) {
  background: var(--tcf-control-bg) !important;
  border-bottom: 1px solid var(--tcf-panel-border) !important;
}

:deep(.arco-tabs-nav-tab) {
  @apply border-0;
}

:deep(.arco-tabs-nav-tab-list) {
  @apply px-4;
}

:deep(.arco-tabs-tab) {
  color: var(--tcf-text-subtle) !important;
  border: 0 !important;

  &:hover {
    color: rgb(59, 130, 246) !important;
  }

  &.arco-tabs-tab-active {
    color: rgb(37, 99, 235) !important;
  }
}

:deep(.arco-tabs-nav-ink) {
  background: rgb(37, 99, 235) !important;
}
</style>
