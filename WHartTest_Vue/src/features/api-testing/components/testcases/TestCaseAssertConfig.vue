<script setup lang="ts">
import { ref, watch, onMounted, inject } from 'vue'
import { IconDelete, IconPlus, IconCode } from '@arco-design/web-vue/es/icon'
import { Message } from '@arco-design/web-vue'
import ResponseJsonViewer from '../interfaces/ResponseJsonViewer.vue'

interface Props {
  validators?: Array<Record<string, any>>
}

const props = withDefaults(defineProps<Props>(), {
  validators: () => []
})

const apiResponse = inject('apiResponse', ref(null))
const drawerVisible = ref(false)
const currentEditingIndex = ref(-1)

interface AssertRule {
  type: string
  expression: string
  expected: string
  expectedValueType: ExpectedValueType
  description: string
  enabled: boolean
}

type ExpectedValueType = 'string' | 'number' | 'boolean' | 'null' | 'json'
const EXPECTED_VALUE_TYPE_META_KEY = '__expected_value_type'

const dataTypes = [
  { label: '整数', value: 'int' },
  { label: '浮点数', value: 'float' },
  { label: '字符串', value: 'str' },
  { label: '布尔值', value: 'bool' },
  { label: '列表', value: 'list' },
  { label: '字典', value: 'dict' },
  { label: '对象', value: 'object' },
  { label: '数组', value: 'array' },
  { label: '空值', value: 'None' }
]

const validatorTypes = [
  { label: '等于', value: 'eq', category: '基础比较' },
  { label: '不等于', value: 'ne', category: '基础比较' },
  { label: '大于', value: 'gt', category: '基础比较' },
  { label: '大于等于', value: 'ge', category: '基础比较' },
  { label: '小于', value: 'lt', category: '基础比较' },
  { label: '小于等于', value: 'le', category: '基础比较' },
  { label: '包含', value: 'contains', category: '字符串' },
  { label: '被包含', value: 'contained_by', category: '字符串' },
  { label: '以...开头', value: 'startswith', category: '字符串' },
  { label: '以...结尾', value: 'endswith', category: '字符串' },
  { label: '正则匹配', value: 'regex_match', category: '字符串' },
  { label: '字符串等于', value: 'str_eq', category: '字符串' },
  { label: '长度等于', value: 'length_equal', category: '长度' },
  { label: '长度大于', value: 'length_greater_than', category: '长度' },
  { label: '长度小于', value: 'length_less_than', category: '长度' },
  { label: '长度大于等于', value: 'length_greater_or_equals', category: '长度' },
  { label: '长度小于等于', value: 'length_less_or_equals', category: '长度' },
  { label: '类型匹配', value: 'type_match', category: '其他' }
] as const

const expectedValueTypes = [
  { label: '字符串', value: 'string' },
  { label: '数字', value: 'number' },
  { label: '布尔', value: 'boolean' },
  { label: '空值', value: 'null' },
  { label: 'JSON', value: 'json' }
] as const

const inferExpectedValueType = (value: any): ExpectedValueType => {
  if (value === null) return 'null'
  if (typeof value === 'number') return 'number'
  if (typeof value === 'boolean') return 'boolean'
  if (typeof value === 'object') return 'json'
  return 'string'
}

const isExpectedValueType = (value: unknown): value is ExpectedValueType => (
  value === 'string' ||
  value === 'number' ||
  value === 'boolean' ||
  value === 'null' ||
  value === 'json'
)

const extractValidatorRule = (validator: Record<string, any>) => {
  if ('check' in validator && 'expect' in validator) {
    return {
      type: validator.assert || validator.comparator || 'eq',
      expression: validator.check ?? '',
      expected: validator.expect,
      expectedValueType: isExpectedValueType(validator[EXPECTED_VALUE_TYPE_META_KEY])
        ? validator[EXPECTED_VALUE_TYPE_META_KEY]
        : undefined
    }
  }

  const entry = Object.entries(validator).find(([key, value]) =>
    key !== EXPECTED_VALUE_TYPE_META_KEY && Array.isArray(value)
  )
  if (!entry) return null
  const [type, values] = entry
  return {
    type,
    expression: values[0] ?? '',
    expected: values[1],
    expectedValueType: isExpectedValueType(validator[EXPECTED_VALUE_TYPE_META_KEY])
      ? validator[EXPECTED_VALUE_TYPE_META_KEY]
      : undefined
  }
}

const formatExpectedForInput = (value: any): string => {
  if (value === null || value === undefined) return ''
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value, null, 2)
    } catch {
      return String(value)
    }
  }
  return String(value)
}

const parseExpectedValue = (rule: AssertRule): any => {
  if (rule.type === 'type_match') {
    return rule.expected
  }

  switch (rule.expectedValueType) {
    case 'number': {
      const numericValue = Number(rule.expected)
      return Number.isNaN(numericValue) ? rule.expected : numericValue
    }
    case 'boolean':
      return String(rule.expected).toLowerCase() === 'true'
    case 'null':
      return null
    case 'json':
      try {
        return JSON.parse(rule.expected)
      } catch {
        return rule.expected
      }
    default:
      return rule.expected
  }
}

const hasExpectedValue = (rule: AssertRule) => {
  if (rule.expectedValueType === 'null') {
    return true
  }
  return String(rule.expected ?? '').trim() !== ''
}

const buildAssertRule = (
  type = 'eq',
  expression = '',
  expected: any = '',
  expectedValueType?: ExpectedValueType
): AssertRule => ({
  type,
  expression,
  expected: formatExpectedForInput(expected),
  expectedValueType: type === 'type_match'
    ? 'string'
    : expectedValueType ?? inferExpectedValueType(expected),
  description: '',
  enabled: true
})

const assertRules = ref<AssertRule[]>([
  buildAssertRule()
])

const initAssertRules = () => {
  if (props.validators && props.validators.length > 0) {
    assertRules.value = props.validators
      .map(validator => {
        const rule = extractValidatorRule(validator)
        return rule
          ? buildAssertRule(rule.type, rule.expression, rule.expected, rule.expectedValueType)
          : null
      })
      .filter((rule): rule is AssertRule => Boolean(rule))
    if (assertRules.value.length === 0) {
      assertRules.value = [buildAssertRule()]
    }
  } else {
    assertRules.value = [buildAssertRule()]
  }
}

watch(() => props.validators, (newValidators) => {
  if (newValidators && newValidators.length > 0) {
    assertRules.value = newValidators
      .map(validator => {
        const rule = extractValidatorRule(validator)
        return rule
          ? buildAssertRule(rule.type, rule.expression, rule.expected, rule.expectedValueType)
          : null
      })
      .filter((rule): rule is AssertRule => Boolean(rule))
    if (assertRules.value.length === 0) {
      assertRules.value = [buildAssertRule()]
    }
  } else {
    assertRules.value = [buildAssertRule()]
  }
})

const addRow = () => {
  assertRules.value.push(buildAssertRule())
}

const removeRow = (index: number) => {
  assertRules.value.splice(index, 1)
  if (assertRules.value.length === 0) {
    assertRules.value.push(buildAssertRule())
  }
}

const handleExpectedTypeChange = (rule: AssertRule) => {
  if (rule.expectedValueType === 'null') {
    rule.expected = ''
  } else if (rule.expectedValueType === 'boolean' && !['true', 'false'].includes(String(rule.expected))) {
    rule.expected = 'true'
  }
}

const handleSelectPath = (path: string, value: any) => {
  if (currentEditingIndex.value >= 0 && currentEditingIndex.value < assertRules.value.length) {
    const currentRule = assertRules.value[currentEditingIndex.value]
    currentRule.expression = path
    if (!String(currentRule.expected ?? '').trim() && currentRule.expectedValueType !== 'null') {
      currentRule.expectedValueType = currentRule.type === 'type_match' ? 'string' : inferExpectedValueType(value)
      currentRule.expected = formatExpectedForInput(value)
    }
    Message.success('已设置断言表达式')
  }
}

const openResponseViewer = (index: number) => {
  currentEditingIndex.value = index
  drawerVisible.value = true
}

const getAssertRules = () => {
  return assertRules.value
    .filter(rule => rule.enabled && rule.expression && hasExpectedValue(rule))
    .map(rule => {
      const validator: Record<string, any> = {
        [rule.type]: [rule.expression, parseExpectedValue(rule)]
      }
      if (rule.type !== 'type_match') {
        validator[EXPECTED_VALUE_TYPE_META_KEY] = rule.expectedValueType
      }
      return validator
    })
}

onMounted(() => { initAssertRules() })
defineExpose({ getAssertRules })
</script>

<template>
  <div class="h-full flex flex-col p-4 space-y-2">
    <div class="flex-1 min-h-0 overflow-y-auto pr-2">
      <div class="space-y-2">
        <div
          v-for="(rule, index) in assertRules"
          :key="index"
          class="flex items-center gap-2 w-full"
        >
          <a-checkbox v-model="rule.enabled" class="flex-shrink-0" />
          <div class="flex flex-1 gap-2">
            <div class="flex relative w-3/5">
              <a-input v-model="rule.expression" placeholder="断言表达式 (例如: body.data.code)" allow-clear class="w-full" />
              <a-button type="text" class="assert-code-trigger absolute right-0 top-0 bottom-0 hover:text-blue-500" @click="openResponseViewer(index)" :disabled="!apiResponse">
                <template #icon><icon-code /></template>
              </a-button>
            </div>
            <div class="flex gap-2 w-2/5">
              <a-select v-model="rule.type" class="w-[30%]" placeholder="断言类型">
                <a-optgroup v-for="category in ['基础比较', '字符串', '长度', '其他']" :key="category" :label="category">
                  <a-option v-for="vtype in validatorTypes.filter(t => t.category === category)" :key="vtype.value" :value="vtype.value">
                    {{ vtype.label }}
                  </a-option>
                </a-optgroup>
              </a-select>
              <a-select
                v-if="rule.type !== 'type_match'"
                v-model="rule.expectedValueType"
                placeholder="值类型"
                class="w-[24%]"
                @change="handleExpectedTypeChange(rule)"
              >
                <a-option v-for="dtype in expectedValueTypes" :key="dtype.value" :value="dtype.value">{{ dtype.label }}</a-option>
              </a-select>
              <a-select v-if="rule.type === 'type_match'" v-model="rule.expected" placeholder="选择类型" allow-clear class="w-[70%]">
                <a-option v-for="dtype in dataTypes" :key="dtype.value" :value="dtype.value">{{ dtype.label }}</a-option>
              </a-select>
              <a-select v-else-if="rule.expectedValueType === 'boolean'" v-model="rule.expected" placeholder="布尔值" class="w-[46%]">
                <a-option value="true">true</a-option>
                <a-option value="false">false</a-option>
              </a-select>
              <a-input v-else-if="rule.expectedValueType === 'null'" :model-value="'null'" disabled class="w-[46%]" />
              <a-textarea
                v-else-if="rule.expectedValueType === 'json'"
                v-model="rule.expected"
                placeholder='JSON，例如 {"code": 0}'
                allow-clear
                auto-size
                class="w-[46%]"
              />
              <a-input
                v-else
                v-model="rule.expected"
                :placeholder="rule.expectedValueType === 'number' ? '预期数字' : '预期结果'"
                allow-clear
                class="w-[46%]"
              />
            </div>
          </div>
          <a-button type="text" status="danger" @click="removeRow(index)" class="flex-shrink-0">
            <template #icon><icon-delete /></template>
          </a-button>
        </div>
      </div>
    </div>
    <div>
      <a-button type="outline" @click="addRow">
        <template #icon><icon-plus /></template>
        添加断言规则
      </a-button>
    </div>

    <!-- 响应JSON查看器 -->
    <ResponseJsonViewer
      v-model:visible="drawerVisible"
      :response-data="apiResponse"
      field-type="assert"
      @select-path="handleSelectPath"
    />
  </div>
</template>

<style lang="postcss" scoped>
@reference "tailwindcss";
.assert-code-trigger {
  color: var(--tcf-text-subtle);
}

:deep(.arco-input-wrapper) {
  background: var(--tcf-control-bg) !important;
  border-color: var(--tcf-control-border) !important;

  input {
    color: var(--tcf-text) !important;
    background: transparent !important;
    &::placeholder {
      color: var(--tcf-text-subtle) !important;
    }
  }
}

:deep(.arco-select-view) {
  background: var(--tcf-control-bg) !important;
  border-color: var(--tcf-control-border) !important;
}

:deep(.arco-select-view-value) {
  color: var(--tcf-text) !important;
}

:deep(.arco-checkbox) {
  color: var(--tcf-text-subtle) !important;
}

:deep(.arco-btn-outline) {
  border-color: var(--tcf-control-border) !important;
  color: var(--tcf-text-muted) !important;

  &:hover {
    border-color: rgba(59, 130, 246, 0.4) !important;
    color: rgb(59, 130, 246) !important;
  }
}

:global(.arco-select-dropdown) {
  background: var(--color-bg-popup, var(--color-bg-2)) !important;
  border: 1px solid var(--color-border-2) !important;
  border-radius: 10px !important;

  .arco-select-option {
    color: var(--color-text-1) !important;

    &:hover {
      background: var(--color-fill-2) !important;
    }

    &.arco-select-option-active,
    &.arco-select-option-selected {
      background: rgba(59, 130, 246, 0.12) !important;
      color: #2563eb !important;
    }
  }
}

:global(body.api-testing-theme .arco-select-dropdown .arco-select-option) {
  color: rgb(203, 213, 225) !important;

  &:hover {
    background: rgba(51, 65, 85, 0.9) !important;
  }
}

:deep(.arco-btn-text) {
  color: var(--tcf-text-subtle) !important;

  &:hover {
    color: rgb(59, 130, 246) !important;
    background: rgba(59, 130, 246, 0.1) !important;
  }

  &.arco-btn-status-danger {
    &:hover {
      color: rgb(239, 68, 68) !important;
      background: rgba(239, 68, 68, 0.1) !important;
    }
  }
}
</style>
