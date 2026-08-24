<script setup lang="ts">
import { ref, computed, watch, h } from 'vue'
import { IconCopy, IconClose, IconPlayArrow } from '@arco-design/web-vue/es/icon'
import { useClipboard } from '@vueuse/core'
import { Message } from '@arco-design/web-vue'
import jmespath from 'jmespath'
import { useAppI18n } from '@/composables/useAppI18n'

type ViewerDataSource = 'response' | 'request'

interface Props {
  visible: boolean
  responseData: any
  fieldType?: 'extract' | 'assert'
  dataSource?: ViewerDataSource
}

const props = defineProps<Props>()
const emit = defineEmits(['update:visible', 'update:dataSource', 'select-path'])
const { isEnglish } = useAppI18n()

const viewerModeLabel = computed(() => (
  props.fieldType === 'extract'
    ? (isEnglish.value ? 'Extractor' : '提取器')
    : (isEnglish.value ? 'Assertion' : '断言')
))

const pathActionLabel = computed(() => (
  props.fieldType === 'extract'
    ? (isEnglish.value ? 'Select' : '选择')
    : (isEnglish.value ? 'Assert' : '断言')
))

const guideExpressionLabel = computed(() => (
  props.fieldType === 'extract'
    ? (isEnglish.value ? 'extract' : '提取')
    : (isEnglish.value ? 'assert' : '断言')
))

const guideTargetLabel = computed(() => (
  props.fieldType === 'extract'
    ? (isEnglish.value ? 'extract rules' : '提取规则')
    : (isEnglish.value ? 'assert config' : '断言配置')
))

const dataSourceLabel = computed(() => (
  props.dataSource === 'request'
    ? (isEnglish.value ? 'Request Body' : '请求体')
    : (isEnglish.value ? 'Response Body' : '响应体')
))

const activeDataSource = computed<ViewerDataSource>(() => (
  props.dataSource === 'request' ? 'request' : 'response'
))

const dataSourceOptions = computed(() => [
  { label: isEnglish.value ? 'Response' : '响应体', value: 'response' },
  { label: isEnglish.value ? 'Request' : '请求体', value: 'request' },
])

const viewerTitle = computed(() => (
  `${dataSourceLabel.value} - ${viewerModeLabel.value}`
))

const guideTitle = computed(() => (
  isEnglish.value ? 'Guide' : '使用说明'
))

const guideLines = computed(() => ([
  isEnglish.value
    ? 'Click the arrow before an object or array to expand or collapse it'
    : '点击对象或数组前的箭头可以展开/折叠节点',
  isEnglish.value
    ? `Click the "${pathActionLabel.value}" button next to a value to test that path`
    : `点击值后面的"${pathActionLabel.value}"按钮可以选择该路径进行测试`,
  isEnglish.value
    ? `Use the test area to try ${guideExpressionLabel.value} expressions, then apply them to the ${guideTargetLabel.value}`
    : `使用测试区域可以调试${guideExpressionLabel.value}表达式，测试成功后可应用到${guideTargetLabel.value}中`,
  isEnglish.value
    ? 'Selected paths are automatically converted to JMESPath expressions'
    : '选择的路径会自动转换为JMESPath表达式',
  isEnglish.value ? 'Path format example:' : '路径格式示例:',
]))

// 复制功能
const { copy } = useClipboard()
const copyContent = async (content: string) => {
  await copy(content)
  Message.success('复制成功')
}

// 关闭抽屉
const closeDrawer = () => {
  emit('update:visible', false)
}

// 测试提取表达式相关
const testExpression = ref('')
const testResult = ref<{ success: boolean; value: any; error?: string } | null>(null)
const isTestAreaExpanded = ref(false)

const handleDataSourceChange = (source: string | number | boolean) => {
  emit('update:dataSource', source === 'request' ? 'request' : 'response')
  testResult.value = null
}

const parseJsonString = (value: string) => {
  let current = value

  for (let depth = 0; depth < 2; depth += 1) {
    const trimmed = current.trim()
    if (!trimmed) return current

    const looksLikeStructuredJson = trimmed.startsWith('{') || trimmed.startsWith('[')
    const looksLikeQuotedStructuredJson = trimmed.startsWith('"')

    if (!looksLikeStructuredJson && !looksLikeQuotedStructuredJson) {
      return current
    }

    try {
      const parsed = JSON.parse(trimmed)

      if (typeof parsed === 'string') {
        const parsedTrimmed = parsed.trim()
        if (parsedTrimmed.startsWith('{') || parsedTrimmed.startsWith('[')) {
          current = parsed
          continue
        }
        return value
      }

      return parsed
    } catch {
      return current
    }
  }

  return current
}

const normalizeResponseContent = (responseData: any) => {
  const data = responseData?.value ?? responseData
  const content = data?.response?.content
    ?? data?.response?.body
    ?? data?.data?.response?.content
    ?? data?.data?.response?.body
    ?? data?.response_data?.content
    ?? data?.response_data?.body
    ?? data?.data?.response_data?.content
    ?? data?.data?.response_data?.body
    ?? data?.content
    ?? data?.body

  if (content === null || content === undefined || content === '') {
    return null
  }

  return typeof content === 'string' ? parseJsonString(content) : content
}

const normalizeRequestContent = (responseData: any) => {
  const data = responseData?.value ?? responseData
  const request = data?.request
    ?? data?.data?.request
    ?? data?.request_data
    ?? data?.data?.request_data
  const content = request?.body
    ?? request?.json
    ?? request?.data
    ?? data?.requestBody
    ?? data?.request_body
    ?? data?.data?.requestBody
    ?? data?.data?.request_body

  if (content === null || content === undefined || content === '') {
    return null
  }

  return typeof content === 'string' ? parseJsonString(content) : content
}

const normalizeViewerContent = (responseData: any) => {
  return props.dataSource === 'request'
    ? normalizeRequestContent(responseData)
    : normalizeResponseContent(responseData)
}

const stringifyForCopy = (data: any) => {
  if (typeof data === 'string') return data
  return JSON.stringify(data, null, 2)
}

// 格式化的JSON数据
const formattedData = computed(() => {
  try {
    if (!props.responseData) return null

    return normalizeViewerContent(props.responseData)
  } catch (error) {
    console.error('解析接口数据失败:', error)
    return null
  }
})

// 测试表达式
const runTest = () => {
  if (!testExpression.value) {
    Message.warning('请先输入提取表达式')
    return
  }
  
  if (!formattedData.value) {
    Message.warning(`暂无${dataSourceLabel.value}`)
    return
  }
  
  try {
    // 处理表达式
    let expression = testExpression.value
    let data = formattedData.value
    
    // 如果表达式以 body. 开头，则移除前缀
    if (expression.startsWith('body.')) {
      expression = expression.substring(5)
    }
    
    // 执行 JMESPath 查询
    const result = jmespath.search(data, expression)
    
    // 存储测试结果
    testResult.value = {
      success: true,
      value: result
    }
    
    // 根据不同模式显示不同的成功消息
    if (props.fieldType === 'extract') {
      Message.success('提取测试成功')
    } else if (props.fieldType === 'assert') {
      Message.success('断言表达式有效')
    }
  } catch (error: any) {
    testResult.value = {
      success: false,
      value: null,
      error: error.message || '表达式解析失败'
    }
    Message.error(`测试失败: ${error.message || '表达式解析失败'}`)
  }
}

// 格式化测试结果显示
const formatTestResult = (result: any) => {
  if (result === null) return 'null'
  if (result === undefined) return 'undefined'
  if (typeof result === 'string') return `"${result}"`
  if (typeof result === 'object') {
    try {
      return JSON.stringify(result, null, 2)
    } catch {
      return String(result)
    }
  }
  return String(result)
}

// 应用测试的表达式
const applyExpression = () => {
  if (testExpression.value && testResult.value?.success) {
    // 确保表达式包含 body. 前缀（如果需要）
    let expression = testExpression.value
    if (!expression.startsWith('body.')) {
      expression = `body.${expression}`
    }
    
    emit('select-path', expression, testResult.value.value)
    
    if (props.fieldType === 'extract') {
      Message.success('已应用提取表达式')
    } else if (props.fieldType === 'assert') {
      Message.success('已应用断言表达式和预期值')
    }
    
    // 清空测试区域
    testExpression.value = ''
    testResult.value = null
    isTestAreaExpanded.value = false
  }
}

// 展开的节点路径
const expandedPaths = ref<string[]>([])

// 判断指定路径是否展开
const isExpanded = (path: string) => {
  return expandedPaths.value.includes(path)
}

// 切换节点展开状态
const toggleExpand = (path: string) => {
  const index = expandedPaths.value.indexOf(path)
  if (index === -1) {
    expandedPaths.value.push(path)
  } else {
    expandedPaths.value.splice(index, 1)
  }
}

// 选择一个路径
const selectPath = (path: string, data: any) => {
  // 将路径格式转换为JMESPath格式 (例如 body.data.users[0].name)
  let jmesPath = path;
  
  // 如果需要添加前缀，可以在这里处理
  if (!path.startsWith('body')) {
    jmesPath = `body.${path}`;
  }
  
  // 准备值
  let value = data;
  if (typeof value === 'string') {
    // 对于字符串，去掉JSON.stringify添加的引号
    value = value;
  } else if (typeof value === 'object' && value !== null) {
    // 对于对象和数组，转换为JSON字符串
    value = JSON.stringify(value);
  } else {
    // 其他类型转为字符串
    value = String(value);
  }
  
  // 设置到测试表达式输入框
  testExpression.value = path
  isTestAreaExpanded.value = true
  
  // 自动运行测试
  runTest()
}

// 定义不同数据类型的样式
const getValueClass = (value: any) => {
  if (value === null) return 'text-gray-500'
  if (typeof value === 'number') return 'text-blue-400'
  if (typeof value === 'boolean') return 'text-purple-400'
  if (typeof value === 'string') return 'text-green-400'
  return 'text-gray-300'
}

// 格式化值，处理长字符串
const formatValue = (value: any) => {
  if (typeof value === 'string') {
    // 不再截断字符串，完整显示
    return JSON.stringify(value);
  }
  return JSON.stringify(value);
}

// 递归渲染JSON节点
const renderJsonNode = (data: any, path: string = '', isRoot: boolean = true): any => {
  if (data === null || data === undefined) {
    return h('div', { class: 'flex items-center' }, [
      h('span', { class: 'text-gray-500' }, 'null'),
      !isRoot && h('span', {
        class: 'ml-2 text-xs text-gray-500 hover:text-blue-400 cursor-pointer px-1 py-0.5 bg-blue-500/10 rounded',
        onClick: () => selectPath(path, data)
      }, props.fieldType === 'extract' ? '选择' : '断言')
    ])
  }
  
  if (typeof data !== 'object') {
    // 计算内容是否需要换行
    const content = formatValue(data);
    const needsWrapping = content.length > 40; // 大致估计一行的字符数

    return h('div', { class: 'flex items-center flex-wrap' }, [
      h('span', { 
        class: `${getValueClass(data)} break-all ${needsWrapping ? 'max-w-[calc(100%-70px)]' : ''}`,
      }, content),
      !isRoot && h('span', {
        class: 'ml-2 text-xs text-gray-500 hover:text-blue-400 cursor-pointer px-1 py-0.5 bg-blue-500/10 rounded whitespace-nowrap flex-shrink-0',
        onClick: () => selectPath(path, data)
      }, props.fieldType === 'extract' ? '选择' : '断言')
    ])
  }
  
  if (Array.isArray(data)) {
    if (data.length === 0) {
      return h('div', { class: 'flex items-center' }, [
        h('span', { class: 'text-gray-500 flex-shrink-0' }, '[]'),
        !isRoot && h('span', {
          class: 'ml-2 text-xs text-gray-500 hover:text-blue-400 cursor-pointer px-1 py-0.5 bg-blue-500/10 rounded flex-shrink-0',
          onClick: () => selectPath(path, data)
        }, props.fieldType === 'extract' ? '选择' : '断言')
      ])
    }
    
    const isNodeExpanded = isExpanded(path)
    
    // 计算数组标题是否需要预留空间
    const arrayTitle = `Array[${data.length}]`;
    const needsArrayTitleWrapping = arrayTitle.length > 20;
    
    return h('div', { class: 'flex flex-col max-w-full' }, [
      h('div', { 
        class: 'flex items-center cursor-pointer hover:text-blue-400 flex-wrap',
        onClick: () => toggleExpand(path)
      }, [
        h('span', { class: 'mr-1 flex-shrink-0' }, isNodeExpanded ? '▼' : '▶'),
        h('span', { 
          class: `text-gray-300 break-all ${needsArrayTitleWrapping ? 'max-w-[calc(100%-90px)]' : ''}`
        }, arrayTitle),
        !isRoot && h('span', {
          class: 'ml-2 text-xs text-gray-500 hover:text-blue-400 cursor-pointer px-1 py-0.5 bg-blue-500/10 rounded flex-shrink-0',
          onClick: (e: Event) => { e.stopPropagation(); selectPath(path, data) }
        }, props.fieldType === 'extract' ? '提取' : '选择断言')
      ]),
      
      isNodeExpanded && h('div', { class: 'pl-4 border-l border-gray-700 ml-2 max-w-full' }, 
        data.map((item: any, index: number) => h('div', { 
          key: index, 
          class: 'flex items-start py-1 max-w-full flex-wrap' 
        }, [
          h('span', { class: 'text-gray-400 mr-1 flex-shrink-0 whitespace-nowrap' }, `${index}:`),
          h('div', { 
            class: `flex-1 min-w-0 ${index > 999 ? 'max-w-[calc(100%-30px)]' : ''}`
          }, [
          renderJsonNode(item, `${path}[${index}]`, false)
          ])
        ]))
      )
    ])
  }
  
  // 处理对象
  const keys = Object.keys(data)
  if (keys.length === 0) {
    return h('div', { class: 'flex items-center' }, [
      h('span', { class: 'text-gray-500 flex-shrink-0' }, '{}'),
      !isRoot && h('span', {
        class: 'ml-2 text-xs text-gray-500 hover:text-blue-400 cursor-pointer px-1 py-0.5 bg-blue-500/10 rounded flex-shrink-0',
        onClick: () => selectPath(path, data)
      }, props.fieldType === 'extract' ? '提取' : '选择断言')
    ])
  }
  
  const isNodeExpanded = isExpanded(path)
  
  // 计算对象标题是否需要预留空间
  const objectTitle = `Object {${keys.length}}`;
  const needsObjectTitleWrapping = objectTitle.length > 20;
  
  return h('div', { class: 'flex flex-col max-w-full' }, [
    h('div', {
      class: 'flex items-center cursor-pointer hover:text-blue-400 flex-wrap',
      onClick: () => toggleExpand(path)
    }, [
      h('span', { class: 'mr-1 flex-shrink-0' }, isNodeExpanded ? '▼' : '▶'),
      h('span', { 
        class: `text-gray-300 break-all ${needsObjectTitleWrapping ? 'max-w-[calc(100%-90px)]' : ''}`
      }, objectTitle),
      !isRoot && h('span', {
        class: 'ml-2 text-xs text-gray-500 hover:text-blue-400 cursor-pointer px-1 py-0.5 bg-blue-500/10 rounded flex-shrink-0',
        onClick: (e: Event) => { e.stopPropagation(); selectPath(path, data) }
      }, props.fieldType === 'extract' ? '提取' : '选择断言')
    ]),
    
    isNodeExpanded && h('div', { class: 'pl-4 border-l border-gray-700 ml-2 max-w-full' },
      keys.map(key => h('div', { 
        key, 
        class: 'flex items-start py-1 max-w-full flex-wrap' 
      }, [
        h('div', { class: 'flex items-center mr-1 flex-shrink-0' }, [
          h('span', { class: 'text-gray-400 mr-1 whitespace-nowrap' }, `${key}:`)
        ]),
        h('div', { 
          class: `flex items-start flex-1 min-w-0 ${key.length > 15 ? 'max-w-[calc(100%-30px)]' : ''}`
        }, [
          renderJsonNode(data[key], path ? `${path}.${key}` : key, false)
        ])
      ]))
    )
  ])
}

// 展开所有节点
const expandAllNodes = (data: any, basePath: string = '') => {
  if (!data || typeof data !== 'object') return
  
  // 添加当前路径到展开列表
  if (basePath) {
    expandedPaths.value.push(basePath)
  }
  
  // 如果是数组，递归展开每个元素
  if (Array.isArray(data)) {
    data.forEach((item, index) => {
      const path = basePath ? `${basePath}[${index}]` : `[${index}]`
      expandAllNodes(item, path)
    })
  } 
  // 如果是对象，递归展开每个属性
  else if (data && typeof data === 'object') {
    Object.keys(data).forEach(key => {
      const path = basePath ? `${basePath}.${key}` : key
      expandAllNodes(data[key], path)
    })
  }
}

// 监听数据变化时自动展开所有节点
watch(() => [props.responseData, props.dataSource], ([newData]) => {
  // 重置展开状态
  expandedPaths.value = ['']
  
  // 如果有数据，展开所有节点
  const content = normalizeViewerContent(newData)
  if (content) {
    expandAllNodes(content, '')
  }
}, { immediate: true })

// 监听抽屉关闭时清空测试数据
watch(() => props.visible, (visible) => {
  if (!visible) {
    testExpression.value = ''
    testResult.value = null
    isTestAreaExpanded.value = false
  }
})
</script>

<template>
  <a-drawer
    :visible="visible"
    :width="700"
    :footer="false"
    @cancel="closeDrawer"
    unmountOnClose
    placement="right"
    :mask-closable="true"
  >
    <template #title>
      <div class="flex justify-between items-center">
        <div class="flex flex-1 items-center gap-3 min-w-0">
          <span class="viewer-title-text">{{ viewerTitle }}</span>
          <a-radio-group
            v-if="fieldType === 'extract'"
            :model-value="activeDataSource"
            :options="dataSourceOptions"
            type="button"
            size="small"
            class="flex-shrink-0"
            @change="handleDataSourceChange"
          />
        </div>
        <a-button type="text" @click="closeDrawer" class="flex-shrink-0">
          <template #icon><icon-close /></template>
        </a-button>
      </div>
    </template>
    
    <div class="viewer-shell p-4 h-full overflow-auto">
      <!-- 测试区域 (用于提取和断言) -->
      <div class="mb-4">
        <div v-if="isTestAreaExpanded" class="mt-3 space-y-3">
          <div class="flex gap-2">
            <a-input
              v-model="testExpression"
              :placeholder="fieldType === 'extract' ? '输入提取表达式进行测试 (例如: data.results[0].id)' : '输入断言表达式进行测试 (例如: body.data.code)'"
              allow-clear
              class="flex-1"
              @press-enter="runTest"
            />
            <a-button type="primary" @click="runTest">
              <template #icon><icon-play-arrow /></template>
              测试
            </a-button>
          </div>
          
          <!-- 测试结果展示 -->
          <div v-if="testResult">
            <div v-if="testResult.success" class="viewer-test-result viewer-test-result--success rounded-md p-3">
              <div class="flex items-center justify-between mb-2">
                <span class="text-green-400 text-sm">✓ {{ fieldType === 'extract' ? '提取成功' : '表达式有效' }}</span>
                <a-button
                  size="mini"
                  type="primary"
                  status="success"
                  @click="applyExpression"
                >
                  {{ fieldType === 'extract' ? '应用此表达式' : '应用到断言' }}
                </a-button>
              </div>
              <div class="viewer-test-code rounded p-2 max-h-32 overflow-auto">
                <pre class="viewer-test-code-text text-xs font-mono whitespace-pre-wrap">{{ formatTestResult(testResult.value) }}</pre>
              </div>
            </div>
            <div v-else class="viewer-test-result viewer-test-result--error rounded-md p-3">
              <div class="text-red-400 text-sm mb-1">✗ {{ fieldType === 'extract' ? '提取失败' : '表达式无效' }}</div>
              <div class="text-red-300 text-xs">{{ testResult.error }}</div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 数据展示 -->
      <div v-if="formattedData" class="viewer-json-shell rounded-lg shadow-inner p-4 relative overflow-auto">
        <div
          class="absolute right-2 top-2 cursor-pointer viewer-copy-button"
          @click="copyContent(stringifyForCopy(formattedData))"
          title="复制"
        >
          <icon-copy />
        </div>
        
        <div class="font-mono text-sm break-all">
          <div class="mt-4">
            <div v-if="formattedData" class="overflow-x-auto content-container">
              <component :is="renderJsonNode(formattedData, '')" />
            </div>
            <div v-else class="text-gray-500">
              无数据
            </div>
          </div>
        </div>
      </div>
      <a-empty v-else :description="`暂无${dataSourceLabel}`" />
      
      <div class="viewer-guide mt-4 rounded-lg p-4">
        <h3 class="viewer-guide-title font-medium mb-2">{{ guideTitle }}</h3>
        <ul class="viewer-guide-list text-sm list-disc pl-4">
          <li class="mb-1">{{ guideLines[0] }}</li>
          <li class="mb-1">{{ guideLines[1] }}</li>
          <li class="mb-1">{{ guideLines[2] }}</li>
          <li class="mb-1">{{ guideLines[3] }}</li>
          <li>{{ guideLines[4] }} <code class="viewer-guide-code px-1 py-0.5 rounded">body.data.users[0].name</code></li>
        </ul>
      </div>
    </div>
  </a-drawer>
</template>

<style lang="postcss" scoped>
@reference "tailwindcss";
:root {
  --viewer-shell-text: var(--color-text-2);
}

.viewer-shell {
  --viewer-panel-bg: rgba(248, 250, 252, 0.98);
  --viewer-guide-bg: rgba(248, 250, 252, 0.92);
  --viewer-guide-title: var(--color-text-2);
  --viewer-guide-text: var(--color-text-3);
  --viewer-guide-code-bg: rgba(226, 232, 240, 0.96);
  --viewer-copy-text: var(--color-text-3);
  --viewer-test-code-bg: rgba(241, 245, 249, 0.96);
  color: var(--viewer-shell-text);
}

.viewer-title-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.viewer-test-result--success {
  background: rgba(34, 197, 94, 0.08);
  border: 1px solid rgba(34, 197, 94, 0.22);
}

.viewer-test-result--error {
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.22);
}

.viewer-test-code,
.viewer-json-shell {
  background: var(--viewer-panel-bg);
}

.viewer-test-code-text {
  color: var(--color-text-2);
}

.viewer-copy-button {
  color: var(--viewer-copy-text);
}

.viewer-copy-button:hover {
  color: rgb(96, 165, 250);
}

.viewer-guide {
  background: var(--viewer-guide-bg);
}

.viewer-guide-title {
  color: var(--viewer-guide-title);
}

.viewer-guide-list {
  color: var(--viewer-guide-text);
}

.viewer-guide-code {
  background: var(--viewer-guide-code-bg);
}

:global(body.api-testing-theme) .viewer-shell {
  --viewer-panel-bg: rgba(17, 24, 39, 0.5);
  --viewer-guide-bg: rgba(17, 24, 39, 0.3);
  --viewer-guide-title: rgb(209, 213, 219);
  --viewer-guide-text: rgb(156, 163, 175);
  --viewer-guide-code-bg: rgb(31, 41, 55);
  --viewer-copy-text: rgb(156, 163, 175);
  --viewer-test-code-bg: rgba(17, 24, 39, 0.5);
}

:deep(.arco-drawer) {
  background: rgba(255, 255, 255, 0.98);
}

:deep(.arco-drawer-header) {
  border-color: rgba(148, 163, 184, 0.16);
  background: rgba(255, 255, 255, 0.98);
  color: var(--color-text-2);
}

:deep(.arco-drawer-body) {
  background: rgba(255, 255, 255, 0.98);
  color: var(--color-text-2);
}

:deep(.arco-empty-description) {
  color: var(--color-text-3);
}

:deep(.arco-input-wrapper) {
  @apply bg-white border-[color:var(--color-border-2)];
  
  input {
    @apply text-[color:var(--color-text-1)] bg-transparent;
    &::placeholder {
      @apply text-[color:var(--color-text-3)];
    }
  }
}

:global(body.api-testing-theme) :deep(.arco-drawer) {
  @apply bg-gray-800;
}

:global(body.api-testing-theme) :deep(.arco-drawer-header) {
  @apply border-gray-700 bg-gray-800 text-gray-300;
}

:global(body.api-testing-theme) :deep(.arco-drawer-body) {
  @apply bg-gray-800 text-gray-300;
}

:global(body.api-testing-theme) :deep(.arco-empty-description) {
  @apply text-gray-500;
}

:global(body.api-testing-theme) :deep(.arco-input-wrapper) {
  @apply bg-gray-900/60 border-gray-700;

  input {
    @apply text-gray-200 bg-transparent;
    &::placeholder {
      @apply text-gray-500;
    }
  }
}

:deep(.arco-btn-primary) {
  @apply bg-blue-600 border-blue-600;
  
  &:hover {
    @apply bg-blue-700 border-blue-700;
  }
}

:deep(.arco-btn-primary.arco-btn-status-success) {
  @apply bg-green-600 border-green-600;
  
  &:hover {
    @apply bg-green-700 border-green-700;
  }
}

.font-mono {
  word-break: break-all;
  white-space: pre-wrap;
  word-wrap: break-word;
  overflow-wrap: break-word;
}

/* 优化内容容器样式 */
.overflow-x-auto {
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.2) transparent;
  overflow-x: auto;
  max-width: 100%;
  display: block;
  padding-right: 8px; /* 为滚动条预留空间 */
}

/* 添加内容容器样式 */
.content-container {
  max-height: 500px;
  overflow-y: auto;
}

.overflow-x-auto::-webkit-scrollbar {
  height: 6px;
  width: 6px;
}

.overflow-x-auto::-webkit-scrollbar-track {
  background: transparent;
}

.overflow-x-auto::-webkit-scrollbar-thumb {
  background-color: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
}

.overflow-x-auto::-webkit-scrollbar-thumb:hover {
  background-color: rgba(255, 255, 255, 0.3);
}

code {
  font-family: monospace;
}

pre {
  margin: 0;
  font-family: 'Monaco', 'Courier New', monospace;
}
</style>
