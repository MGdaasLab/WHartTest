<template>
  <div ref="layoutRef" class="ui-automation-layout">
    <ModulePanel ref="modulePanelRef" @select="onModuleSelect" @updated="onModuleUpdated" />
    <div class="layout-content">
      <a-tooltip :content="isFullscreen ? tl('退出全屏') : tl('全屏')">
        <button class="fullscreen-btn" type="button" @click="toggleFullscreen">
          <icon-fullscreen-exit v-if="isFullscreen" />
          <icon-fullscreen v-else />
        </button>
      </a-tooltip>
      <a-tabs
        :key="`ui-automation-tabs-${locale}`"
        v-model:active-key="activeTab"
        type="card-gutter"
        class="layout-tabs"
      >
        <a-tab-pane key="pages" :title="tl('页面管理')">
          <PageList ref="pageListRef" :selected-module-id="selectedModuleId" />
        </a-tab-pane>
        <a-tab-pane key="page-steps" :title="tl('页面步骤')">
          <PageStepList ref="pageStepListRef" :selected-module-id="selectedModuleId" />
        </a-tab-pane>
        <a-tab-pane key="testcases" :title="tl('测试用例')">
          <TestCaseList ref="testCaseListRef" :selected-module-id="selectedModuleId" />
        </a-tab-pane>
        <a-tab-pane key="execution-records" :title="tl('执行记录')">
          <ExecutionRecordList ref="executionRecordListRef" />
        </a-tab-pane>
        <a-tab-pane key="batch-records" :title="tl('批量执行')">
          <BatchRecordList ref="batchRecordListRef" />
        </a-tab-pane>
        <a-tab-pane key="public-data" :title="tl('公共数据')">
          <PublicDataList ref="publicDataListRef" />
        </a-tab-pane>
        <a-tab-pane key="env-config" :title="tl('环境配置')">
          <EnvConfigList ref="envConfigListRef" />
        </a-tab-pane>
        <a-tab-pane key="actuators" :title="tl('执行器')">
          <ActuatorList ref="actuatorListRef" />
        </a-tab-pane>
      </a-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { IconFullscreen, IconFullscreenExit } from '@arco-design/web-vue/es/icon'
import { useAppI18n } from '@/composables/useAppI18n'
import ModulePanel from '../components/ModulePanel.vue'
import PageList from './PageList.vue'
import PageStepList from './PageStepList.vue'
import TestCaseList from './TestCaseList.vue'
import ExecutionRecordList from './ExecutionRecordList.vue'
import BatchRecordList from './BatchRecordList.vue'
import PublicDataList from './PublicDataList.vue'
import EnvConfigList from './EnvConfigList.vue'
import ActuatorList from './ActuatorList.vue'
import type { UiModule } from '../types'

const { locale, tl } = useAppI18n()
const activeTab = ref('pages')
const modulePanelRef = ref()
const selectedModuleId = ref<number | undefined>(undefined)

const pageListRef = ref()
const pageStepListRef = ref()
const testCaseListRef = ref()
const executionRecordListRef = ref()
const batchRecordListRef = ref()
const publicDataListRef = ref()
const envConfigListRef = ref()
const actuatorListRef = ref()
void [modulePanelRef, pageListRef, pageStepListRef, testCaseListRef, executionRecordListRef, batchRecordListRef, publicDataListRef, envConfigListRef, actuatorListRef]

const layoutRef = ref<HTMLElement | null>(null)
const isFullscreen = ref(false)

const syncFullscreenState = () => {
  isFullscreen.value = document.fullscreenElement === layoutRef.value
}

const toggleFullscreen = async () => {
  const el = layoutRef.value
  if (!el) return

  try {
    if (document.fullscreenElement === el) {
      await document.exitFullscreen()
    } else {
      await el.requestFullscreen()
    }
    syncFullscreenState()
  } catch (error) {
    console.error('切换全屏失败:', error)
  }
}

onMounted(() => {
  document.addEventListener('fullscreenchange', syncFullscreenState)
})

onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', syncFullscreenState)
})

// 页签切换时刷新对应数据
watch(activeTab, (newTab) => {
  switch (newTab) {
    case 'pages':
      pageListRef.value?.refresh?.()
      break
    case 'page-steps':
      pageStepListRef.value?.refresh?.()
      break
    case 'testcases':
      testCaseListRef.value?.refresh?.()
      break
    case 'execution-records':
      executionRecordListRef.value?.refresh?.()
      break
    case 'batch-records':
      batchRecordListRef.value?.refresh?.()
      break
    case 'public-data':
      publicDataListRef.value?.refresh?.()
      break
    case 'env-config':
      envConfigListRef.value?.refresh?.()
      break
    case 'actuators':
      actuatorListRef.value?.refresh?.()
      break
  }
})

const onModuleSelect = (module: UiModule | null) => {
  selectedModuleId.value = module?.id
}

const onModuleUpdated = async () => {
  await nextTick()
  pageListRef.value?.refresh?.()
  pageStepListRef.value?.refresh?.()
  testCaseListRef.value?.refresh?.()
}
</script>

<style scoped>
.ui-automation-layout {
  display: flex;
  width: 100%;
  height: 100%;
  gap: 10px;
  overflow: hidden;
  background-color: var(--color-bg-1);
}

@media (max-width: 768px) {
  .ui-automation-layout {
    flex-direction: column;
  }
}

.layout-content {
  position: relative;
  flex: 1;
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 4px 0 10px rgba(0, 0, 0, 0.2), 0 4px 10px rgba(0, 0, 0, 0.2), 0 0 10px rgba(0, 0, 0, 0.15);
  padding: 20px;
}

/* 页签导航右侧预留全屏按钮宽度（28px 按钮 + 8px 间距），避免最右侧页签被按钮遮挡 */
.layout-tabs :deep(.arco-tabs-nav) {
  padding-right: 36px;
}

.fullscreen-btn {
  position: absolute;
  top: 20px;
  right: 20px;
  z-index: 10;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  color: var(--color-text-3, #86909c);
  background: var(--color-fill-2, #f2f3f5);
  font-size: 14px;
  transition: all 0.2s ease;
}

.fullscreen-btn:hover {
  color: var(--color-text-2, #4e5969);
  background: var(--color-fill-3, #e5e6eb);
}

/* 全屏态下铺满视口，保持内部布局不变 */
.ui-automation-layout:fullscreen {
  background-color: var(--color-bg-1);
  border-radius: 0;
}

:deep(.arco-tabs) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

:deep(.arco-tabs-content) {
  flex: 1;
  overflow: auto;
}

:deep(.arco-tabs-pane) {
  height: 100%;
}
</style>
