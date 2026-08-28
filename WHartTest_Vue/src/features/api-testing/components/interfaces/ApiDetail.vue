<script setup lang="ts">
import { ref, computed, watch, provide, onMounted, onBeforeUnmount, shallowRef, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { useDraggable } from '@vueuse/core'
import ApiRequestHeader from './ApiRequestHeader.vue'
import ApiParamsConfig from './ApiParamsConfig.vue'
import ApiHeadersConfig from './ApiHeadersConfig.vue'
import ApiBodyConfig from './ApiBodyConfig.vue'
import ApiResponse from './ApiResponse.vue'
import ApiExtractConfig from './ApiExtractConfig.vue'
import ApiAssertConfig from './ApiAssertConfig.vue'
import ApiHooksConfigEnhanced from './ApiHooksConfigEnhanced.vue'
import { createInterface, updateInterface, debugInterface, quickDebugInterface, type ApiInterface, type DebugInterfaceRequest, type QuickDebugInterfaceRequest, type KeyValuePair } from '../../services/interfaceService'
import type { ApiExtractPayload } from '../../types/interface'
import { useProjectStore } from '@/store/projectStore'
import { useEnvironmentStore } from '../../stores/environmentStore'
import { useApiTabsStore } from '../../stores/apiTabsStore'

// Props定义
interface Props {
  interface?: ApiInterface
  modules?: ApiModule[]
  selectedModule?: ApiModule
  autoDebug?: boolean
}

// 接口类型定义
interface ApiModule {
  id: number
  name: string
  project: number
  parent: number | null
  description: string | null
  create_time?: string
  update_time?: string
  children?: ApiModule[]
}

const props = withDefaults(defineProps<Props>(), {
  interface: undefined,
  modules: () => [],
  selectedModule: undefined,
  autoDebug: false
})

const emit = defineEmits(['refresh', 'update:interface', 'debug-completed'])

// 页签管理
const tabsStore = useApiTabsStore()

// 当前选中的配置tab
const activeTab = ref('headers')

// 监听 activeTab 变化，保存到页签
watch(activeTab, (newTab) => {
  if (tabsStore.activeTabId) {
    tabsStore.updateTabUIState(tabsStore.activeTabId, { activeTab: newTab })
  }
})

// 响应数据
const response = ref<{
  status: number | null
  time: number | null
  size: number | null
  data: any
  request: any
  response: any
  validation_results: any
  extracted_variables: any
}>({
  status: null,
  time: null,
  size: null,
  data: null,
  request: null,
  response: null,
  validation_results: null,
  extracted_variables: null
})

// 提供响应数据给子组件
provide('apiResponse', response)

// 组件引用
const paramsRef = ref()
const headersRef = ref()
const bodyRef = ref()
const setupHooksRef = ref()
const teardownHooksRef = ref()
const extractRef = ref()
const assertRef = ref()
// ApiRequestHeader 组件引用
const requestHeaderRef = ref<any>()

const getCurrentExtractPayload = (): ApiExtractPayload => {
  const payload = extractRef.value?.getExtractRules()
  if (payload && typeof payload === 'object' && 'extract' in payload && 'extractMeta' in payload) {
    return payload as ApiExtractPayload
  }
  return {
    extract: payload ?? props.interface?.extract ?? {},
    extractMeta: (props.interface as any)?.extract_meta ?? {}
  }
}

// 响应卡片高度
const responseCardHeight = ref(44)
const resizeDragHandle = ref<HTMLElement | null>(null)

// 简单的拖动实现
let startY = 0
let startHeight = 0
let isDragging = false

const handleMouseDown = (e: MouseEvent) => {
  isDragging = true
  startY = e.clientY
  startHeight = responseCardHeight.value
  
  // 防止文本选中
  document.body.style.userSelect = 'none'
  
  // 添加全局监听器
  document.addEventListener('mousemove', handleMouseMove)
  document.addEventListener('mouseup', handleMouseUp)
}

const handleMouseMove = (e: MouseEvent) => {
  if (!isDragging) return
  
  // 计算鼠标移动的距离
  const deltaY = e.clientY - startY
  const containerHeight = window.innerHeight
  
  // 根据移动距离调整高度百分比（向上拖动增加高度，向下拖动减少高度）
  const deltaPercent = (deltaY / containerHeight) * 100
  const newHeightPercent = startHeight - deltaPercent
  
  // 限制在10%到90%之间
  responseCardHeight.value = Math.min(Math.max(newHeightPercent, 10), 90)
}

const handleMouseUp = () => {
  isDragging = false
  
  // 恢复文本选中
  document.body.style.userSelect = ''
  
  // 移除全局监听器
  document.removeEventListener('mousemove', handleMouseMove)
  document.removeEventListener('mouseup', handleMouseUp)
}

// 组件挂载时添加拖动监听器
onMounted(() => {
  if (resizeDragHandle.value) {
    resizeDragHandle.value.addEventListener('mousedown', handleMouseDown)
  }
  
  // ... 其他挂载逻辑
})

// 组件卸载时清理
onBeforeUnmount(() => {
  if (resizeDragHandle.value) {
    resizeDragHandle.value.removeEventListener('mousedown', handleMouseDown)
  }
  document.removeEventListener('mousemove', handleMouseMove)
  document.removeEventListener('mouseup', handleMouseUp)
})

// 处理发送请求
const handleSend = async (requestData: { method: string, url: string, id?: number, quickDebug?: boolean, quickDebugRequest?: QuickDebugInterfaceRequest }) => {
  console.log('接收到的请求数据:', requestData)
  console.log('当前接口:', props.interface)

  if (!requestData.quickDebug && !requestData.id) {
    Message.warning('请先保存接口后再调试')
    return
  }

  if (!currentEnvironmentId.value && !hasExplicitBaseUrl(requestData.url)) {
    Message.warning('请选择环境')
    return
  }

  try {
    // 根据是否是快速调试，设置对应的加载状态
    if (requestData.quickDebug) {
      quickDebugLoading.value = true
    } else {
      sendingLoading.value = true
    }
    const params = paramsRef.value?.getParams()
    const headers = headersRef.value?.getHeaders()
    const body = bodyRef.value?.getBody()
    const setupHooks = setupHooksRef.value?.getHooks()
    const teardownHooks = teardownHooksRef.value?.getHooks()
    const extractPayload = getCurrentExtractPayload()
    const assertRules = assertRef.value?.getAssertRules()

    // 如果是快速调试
    if (requestData.quickDebug && requestData.quickDebugRequest) {
      const quickDebugData = requestData.quickDebugRequest;

      // 添加headers
      if (headers) {
        headers.forEach(header => {
          if (header.enabled && header.key) {
            quickDebugData.headers![header.key] = header.value;
          }
        });
      }

      // 添加params
      if (params) {
        params.forEach(param => {
          if (param.enabled && param.key) {
            quickDebugData.params![param.key] = param.value;
          }
        });
      }

      // 添加body - 按原项目格式传递，runner 能识别 {type, content} 结构
      if (body) {
        if (body.type === 'none') {
          quickDebugData.body = null;
        } else if (['form-data', 'x-www-form-urlencoded'].includes(body.type)) {
          quickDebugData.body = {
            type: body.type,
            content: (body.content as KeyValuePair[]).filter(item => item.enabled && item.key)
          };
        } else if (body.type === 'raw') {
          quickDebugData.body = { type: 'raw', content: body.content };
        }
      }

      // 添加extract
      if (extractPayload.extract) {
        quickDebugData.extract = extractPayload.extract;
        quickDebugData.extract_meta = extractPayload.extractMeta;
      }

      // 添加validators（断言）
      if (assertRules) {
        quickDebugData.validators = assertRules;
      }

      // 添加前置钩子（setup_hooks）
      if (setupHooks) {
        quickDebugData.setup_hooks = setupHooks;
      }

      // 添加后置钩子（teardown_hooks）
      if (teardownHooks) {
        quickDebugData.teardown_hooks = teardownHooks;
      }

      console.log('发送快速调试请求:', quickDebugData);

      const { data } = await quickDebugInterface(quickDebugData);
      response.value = {
        status: data.status_code || null,
        time: data.elapsed || null,
        size: data.response?.content_size || null,
        data: data,
        request: data.request,
        response: data.response,
        validation_results: data.validation_results,
        extracted_variables: data.extracted_variables
      }
    } else {
      // 常规调试流程
      const debugData: DebugInterfaceRequest = {
        environment_id: environmentStore.currentEnvironmentId ? Number(environmentStore.currentEnvironmentId) : undefined,
        method: requestData.method,
        url: requestData.url,
        headers,
        params,
        body,
        setup_hooks: setupHooks,
        teardown_hooks: teardownHooks,
        extract: extractPayload.extract,
        extract_meta: extractPayload.extractMeta,
        validators: assertRules,
        file_ids: collectFileIdsFromBody(body)
      }

      console.log('发送调试请求:', debugData);

      const { data } = await debugInterface(requestData.id!, debugData)
      response.value = {
        status: data.status_code || null,
        time: data.elapsed || null,
        size: data.response?.content_size || null,
        data: data,
        request: data.request,
        response: data.response,
        validation_results: data.validation_results,
        extracted_variables: data.extracted_variables
      }
    }

    // 更新当前页签的响应数据
    if (tabsStore.activeTabId) {
      tabsStore.updateTabResponse(tabsStore.activeTabId, response.value)
    }
  } catch (error: any) {
    Message.error(error.message || '调试接口失败')
  } finally {
    // 重置所有加载状态
    sendingLoading.value = false
    quickDebugLoading.value = false
  }
}

const projectStore = useProjectStore()
const environmentStore = useEnvironmentStore()
const savingLoading = ref(false)
const sendingLoading = ref(false)
const quickDebugLoading = ref(false)

const hasExplicitBaseUrl = (requestUrl: string) => {
  return /^[a-zA-Z][a-zA-Z\d+.-]*:\/\//.test(requestUrl.trim())
}

const normalizeModuleValue = (moduleValue: unknown) => {
  if (typeof moduleValue === 'object' && moduleValue !== null && 'value' in moduleValue) {
    return normalizeModuleValue((moduleValue as { value?: unknown }).value)
  }

  if (typeof moduleValue === 'boolean') {
    return undefined
  }

  if (moduleValue === null || moduleValue === undefined || moduleValue === '') {
    return undefined
  }

  const normalizedId = Number(moduleValue)
  return Number.isFinite(normalizedId) && normalizedId > 0 ? normalizedId : undefined
}

// 获取当前环境ID
const currentEnvironmentId = computed(() => environmentStore.currentEnvironmentId)

const collectFileIdsFromBody = (body: any): number[] => {
  const ids = new Set<number>()
  const content = body?.content
  if (Array.isArray(content)) {
    content.forEach((item: any) => {
      const fileId = Number(item?.file_id || (typeof item?.value === 'string' && item.value.startsWith('file_id:') ? item.value.split(':')[1] : 0))
      if (Number.isFinite(fileId) && fileId > 0) ids.add(fileId)
    })
  }
  return Array.from(ids)
}

// 处理保存用例
const handleSave = async (requestData: { method: string, url: string, name: string, module?: number | string | null }) => {
  if (!projectStore.currentProjectId) {
    Message.warning('请先选择项目')
    return
  }

  const normalizedModuleId = normalizeModuleValue(requestData.module)

  if (!normalizedModuleId) {
    Message.warning('请选择模块')
    return
  }

  if (!requestData.name) {
    Message.warning('请输入接口名称')
    return
  }

  if (!requestData.url) {
    Message.warning('请输入请求路径')
    return
  }

  try {
    savingLoading.value = true
    const params = paramsRef.value?.getParams() ?? props.interface?.params ?? {}
    const headers = headersRef.value?.getHeaders() ?? props.interface?.headers ?? {}
    const body = bodyRef.value?.getBody() ?? props.interface?.body ?? { type: 'none', content: null }
    const setupHooks = setupHooksRef.value?.getHooks() ?? props.interface?.setup_hooks ?? []
    const teardownHooks = teardownHooksRef.value?.getHooks() ?? props.interface?.teardown_hooks ?? []
    const extractPayload = getCurrentExtractPayload()
    const assertRules = assertRef.value?.getAssertRules() ?? props.interface?.validators ?? []

    // 调试日志
    console.log('保存前置钩子:', setupHooks)
    console.log('保存后置钩子:', teardownHooks)

    // 处理钩子数据，确保SQL钩子采用新格式
    const processHooks = (hooks: any[]) => {
      return hooks.map(hook => {
        // 如果是字符串形式的JSON对象，尝试解析
        if (typeof hook === 'string' && hook.startsWith('{') && hook.endsWith('}')) {
          try {
            return JSON.parse(hook);
          } catch (e) {
            console.error('解析钩子JSON失败:', e);
            return hook;
          }
        }
        return hook;
      });
    };

    // 构建请求数据
    const data = {
      name: requestData.name,
      method: requestData.method,
      url: requestData.url,
      project: Number(projectStore.currentProjectId),
      module: normalizedModuleId,
      headers,
      params,
      body,
      setup_hooks: processHooks(setupHooks),
      teardown_hooks: processHooks(teardownHooks),
      variables: {}, // TODO: 待实现变量配置
      validators: assertRules,
      extract: extractPayload.extract,
      extract_meta: extractPayload.extractMeta,
      file_ids: collectFileIdsFromBody(body)
    }

    let savedInterface: ApiInterface | undefined
    if (props.interface?.id) {
      const response = await updateInterface(props.interface.id, data)
      console.log('更新接口响应:', response)
      Message.success('更新接口成功')
      savedInterface = response.data
      emit('update:interface', savedInterface)
      emit('refresh', savedInterface?.module || normalizedModuleId)
    } else {
      const response = await createInterface(data)
      console.log('创建接口响应:', response)
      Message.success('创建接口成功')
      savedInterface = response.data
      console.log('保存的接口数据:', savedInterface)

      // 不管接口数据是否完整，都尝试使用它
      // 即使数据不完整，缺失的字段可以使用默认值
      emit('update:interface', savedInterface)
      emit('refresh', normalizedModuleId)
    }

    if (tabsStore.activeTabId && savedInterface) {
      tabsStore.updateTabRequest(tabsStore.activeTabId, {
        interfaceId: savedInterface.id,
        method: savedInterface.method,
        url: savedInterface.url,
        name: savedInterface.name,
        module: savedInterface.module,
        params: savedInterface.params,
        headers: savedInterface.headers,
        body: savedInterface.body,
        setupHooks: savedInterface.setup_hooks,
        teardownHooks: savedInterface.teardown_hooks,
        extractRules: savedInterface.extract,
        extractMeta: (savedInterface as any).extract_meta,
        assertRules: savedInterface.validators
      })
    }

    // 确保更新后的接口数据包含ID
    console.log('最终的接口数据:', savedInterface)
  } catch (error: any) {
    Message.error(error.message || '保存接口失败')
  } finally {
    savingLoading.value = false
  }
}

// 当页签激活时，恢复响应数据和UI状态
watch(() => tabsStore.activeTabId, (newTabId, oldTabId) => {
  // 切换页签时恢复数据（包括初次激活）
  if (newTabId) {
    const tab = tabsStore.tabs.find(t => t.id === newTabId)
    if (tab) {
      // 恢复响应数据
      if (tab.response) {
        response.value = tab.response
      } else {
        // 清空响应
        response.value = {
          status: null,
          time: null,
          size: null,
          data: null,
          request: null,
          response: null,
          validation_results: null,
          extracted_variables: null
        }
      }
      
      // 恢复UI状态（使用 nextTick 确保在 DOM 更新后设置）
      nextTick(() => {
        if (tab.activeTab) {
          activeTab.value = tab.activeTab
          console.log('恢复页签UI状态:', tab.activeTab)
        } else {
          // 如果没有保存的状态，默认选中 headers
          activeTab.value = 'headers'
          tabsStore.updateTabUIState(newTabId, { activeTab: 'headers' })
        }
      })
    }
  }
}, { immediate: true })

// 监听接口数据变化，保存到页签
watch(() => [
  paramsRef.value?.getParams(),
  headersRef.value?.getHeaders(),
  bodyRef.value?.getBody(),
  setupHooksRef.value?.getHooks(),
  teardownHooksRef.value?.getHooks(),
  extractRef.value?.getExtractRules(),
  assertRef.value?.getAssertRules()
], () => {
  // 保存当前的请求配置到页签
  if (tabsStore.activeTabId && props.interface) {
    tabsStore.updateTabRequest(tabsStore.activeTabId, {
      method: props.interface.method,
      url: props.interface.url,
      name: props.interface.name,
      module: props.interface.module,
      params: paramsRef.value?.getParams(),
      headers: headersRef.value?.getHeaders(),
      body: bodyRef.value?.getBody(),
      setupHooks: setupHooksRef.value?.getHooks(),
      teardownHooks: teardownHooksRef.value?.getHooks(),
      extractRules: getCurrentExtractPayload().extract,
      extractMeta: getCurrentExtractPayload().extractMeta,
      assertRules: assertRef.value?.getAssertRules()
    })
  }
}, { deep: true })

// 监听接口信息变化
watch(() => props.interface, (newInterface, oldInterface) => {
  console.log('接口信息变化:', newInterface)

  // 当切换到不同接口时清空响应
  if (oldInterface?.id !== newInterface?.id) {
    // 检查是否是页签切换（如果新接口已经在页签中打开）
    const existingTab = newInterface?.id ? tabsStore.findTabByInterface(newInterface.id) : null
    
    if (existingTab) {
      // 如果是页签切换，恢复页签的响应数据
      if (existingTab.response) {
        response.value = existingTab.response
      } else {
        // 页签没有响应数据时清空
        response.value = {
          status: null,
          time: null,
          size: null,
          data: null,
          request: null,
          response: null,
          validation_results: null,
          extracted_variables: null
        }
      }
    } else {
      // 如果是新打开的接口，清空响应
      console.log('切换到新接口，清空响应内容')
      response.value = {
        status: null,
        time: null,
        size: null,
        data: null,
        request: null,
        response: null,
        validation_results: null,
        extracted_variables: null
      }
    }
  }

  // 只记录有无ID，不检查数据完整性
  const hasId = newInterface?.id ? true : false
  console.log('接口是否有ID:', hasId ? '是' : '否')

  // 调试钩子数据
  if (newInterface) {
    console.log('前置钩子数据:', newInterface.setup_hooks)
    console.log('后置钩子数据:', newInterface.teardown_hooks)
  }

  // 如果从无ID变为有ID，说明是从新建变为编辑模式
  if (oldInterface && !oldInterface.id && newInterface && newInterface.id) {
    console.log('从新建模式切换到编辑模式，接口ID为:', newInterface.id)
  }

  // 如果从有ID变为无ID，说明是从编辑变为新建模式
  if (oldInterface && oldInterface.id && (!newInterface || !newInterface.id)) {
    console.log('从编辑模式切换到新建模式')
  }
}, { deep: true })

// 监听自动调试标志
watch(() => props.autoDebug, async (newValue) => {
  if (newValue && props.interface) {
    console.log('触发自动调试，接口信息:', props.interface)
    // 等待下一个tick确保组件已渲染
    await nextTick()
    // 自动触发调试
    if (requestHeaderRef.value) {
      // 直接调用 handleSend
      handleSend({
        method: props.interface.method || 'GET',
        url: props.interface.url || '',
        id: props.interface.id
      })
      // 通知父组件调试已触发
      emit('debug-completed')
    }
  }
}, { immediate: true })

// 组件挂载时，恢复页签的UI状态（移到前面的onMounted中）
</script>

<template>
  <div class="api-detail h-full flex flex-col pt-0 pb-0 overflow-hidden">
    <!-- 顶部接口信息卡片 -->
    <div class="detail-shell detail-shell--header mb-2 flex-shrink-0 rounded-lg shadow-lg overflow-hidden">
      <div class="px-4 py-3">
        <ApiRequestHeader
          ref="requestHeaderRef"
          :modules="props.modules || []"
          :interface="props.interface"
          :selected-module="props.selectedModule"
          :saving-loading="savingLoading"
          :sending-loading="sendingLoading"
          :quick-debug-loading="quickDebugLoading"
          @send="handleSend"
          @save="handleSave"
        />
      </div>
    </div>

    <!-- 中间请求配置卡片 -->
    <div class="detail-shell detail-shell--config flex-1 min-h-0 rounded-lg shadow-lg overflow-hidden">
      <a-tabs v-model:active-key="activeTab" class="h-full" :lazy-load="false">
        <!-- Headers配置 -->
        <a-tab-pane key="headers" title="Headers">
          <ApiHeadersConfig ref="headersRef" :headers="(props.interface?.headers as any)" />
        </a-tab-pane>

        <!-- 参数配置 -->
        <a-tab-pane key="params" title="Params">
          <ApiParamsConfig ref="paramsRef" :params="(props.interface?.params as any)" />
        </a-tab-pane>

        <!-- Body配置 -->
        <a-tab-pane key="body" title="Body">
          <ApiBodyConfig ref="bodyRef" :body="(props.interface?.body as any)" />
        </a-tab-pane>

        <!-- Auth配置 -->
        <a-tab-pane key="auth" title="Auth">
          <div class="p-4">
            <a-empty description="暂未实现认证配置" />
          </div>
        </a-tab-pane>

        <!-- Setup Hooks配置 -->
        <a-tab-pane key="setup_hooks" title="Setup Hooks">
          <ApiHooksConfigEnhanced ref="setupHooksRef" :hooks="props.interface?.setup_hooks" type="setup" />
        </a-tab-pane>

        <!-- Teardown Hooks配置 -->
        <a-tab-pane key="teardown_hooks" title="Teardown Hooks">
          <ApiHooksConfigEnhanced ref="teardownHooksRef" :hooks="props.interface?.teardown_hooks" type="teardown" />
        </a-tab-pane>

        <!-- Extract配置 -->
        <a-tab-pane key="extract" title="Extract">
          <ApiExtractConfig
            ref="extractRef"
            :extract="props.interface?.extract"
            :extract-meta="(props.interface as any)?.extract_meta"
          />
        </a-tab-pane>

        <!-- Assert配置 -->
        <a-tab-pane key="assert" title="Assert">
          <ApiAssertConfig ref="assertRef" :validators="props.interface?.validators" />
        </a-tab-pane>
      </a-tabs>
    </div>

    <!-- 拖动条 -->
    <div
      ref="resizeDragHandle"
      class="resize-handle h-3 cursor-row-resize transition-colors flex items-center justify-center gap-1"
    >
      <div class="resize-line w-6 h-[2px] rounded-full"></div>
      <div class="resize-line w-6 h-[2px] rounded-full"></div>
      <div class="resize-line w-6 h-[2px] rounded-full"></div>
    </div>

    <!-- 底部响应卡片 -->
    <div
      class="detail-shell detail-shell--response rounded-lg shadow-lg overflow-hidden"
      :style="{ height: `${responseCardHeight}%` }"
    >
      <ApiResponse :response="response" />
    </div>
  </div>
</template>

<style lang="postcss" scoped>
@reference "tailwindcss";
.api-detail {
  --detail-shell-bg: rgba(255, 255, 255, 0.96);
  --detail-shell-border: rgba(148, 163, 184, 0.16);
  --detail-shell-shadow: 0 14px 28px rgba(15, 23, 42, 0.08);
  --detail-tab-border: rgba(148, 163, 184, 0.16);
  --detail-tab-text: var(--color-text-3);
  --detail-tab-active: rgb(var(--primary-6));
  --detail-resize-bg: rgba(148, 163, 184, 0.22);
  --detail-resize-bg-hover: rgba(59, 130, 246, 0.25);
  --detail-resize-line: rgba(100, 116, 139, 0.8);
}

.detail-shell {
  background: var(--detail-shell-bg);
  border: 1px solid var(--detail-shell-border);
  box-shadow: var(--detail-shell-shadow);
}

:global(body.api-testing-theme) .api-detail {
  --detail-shell-bg: rgb(31, 41, 55);
  --detail-shell-border: rgba(55, 65, 81, 0.92);
  --detail-shell-shadow: 0 16px 30px rgba(2, 6, 23, 0.28);
  --detail-tab-border: rgb(55, 65, 81);
  --detail-tab-text: rgb(156, 163, 175);
  --detail-tab-active: rgb(var(--primary-6));
  --detail-resize-bg: rgba(55, 65, 81, 0.52);
  --detail-resize-bg-hover: rgba(59, 130, 246, 0.35);
  --detail-resize-line: rgb(156, 163, 175);
}

:deep(.arco-tabs) {
  @apply h-full flex flex-col;

  .arco-tabs-content {
    @apply flex-1 min-h-0 overflow-auto;
  }

  .arco-tabs-nav {
    @apply flex-shrink-0;
  }

  .arco-tabs-header {
    border-bottom: 1px solid var(--detail-tab-border);
  }

  .arco-tabs-nav-tab {
    @apply border-b-0;
  }

  .arco-tabs-tab {
    color: var(--detail-tab-text);

    &.arco-tabs-tab-active {
      color: var(--detail-tab-active);
    }
  }
}

/* 拖动条样式 */
.resize-handle {
  @apply relative;
  background: var(--detail-resize-bg);

  &:hover {
    background: var(--detail-resize-bg-hover);
  }

  &:hover .resize-line {
    background: rgb(96, 165, 250);
  }
}

.resize-line {
  background: var(--detail-resize-line);
}

.cursor-row-resize {
  cursor: row-resize;
  user-select: none;
}

/* 只在拖动时禁用文本选择 */
.resize-handle {
  user-select: none;
}
</style>

