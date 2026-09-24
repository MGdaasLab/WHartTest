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
      <div class="ai-generate-entry">
        <a-button type="primary" size="small" :loading="isSubmittingGeneration" @click="showGenerateModal = true">
          <template #icon><icon-robot /></template>
          {{ tl('AI 生成用例') }}
        </a-button>
      </div>
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
      <GenerateUiCasesModal
        v-model:visible="showGenerateModal"
        @submit="handleGenerateSubmit"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, h, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { IconFullscreen, IconFullscreenExit, IconRobot } from '@arco-design/web-vue/es/icon'
import { Notification } from '@arco-design/web-vue'
import { useRouter } from 'vue-router'
import { useAppI18n } from '@/composables/useAppI18n'
import { useProjectStore } from '@/store/projectStore'
import ModulePanel from '../components/ModulePanel.vue'
import PageList from './PageList.vue'
import PageStepList from './PageStepList.vue'
import TestCaseList from './TestCaseList.vue'
import ExecutionRecordList from './ExecutionRecordList.vue'
import BatchRecordList from './BatchRecordList.vue'
import PublicDataList from './PublicDataList.vue'
import EnvConfigList from './EnvConfigList.vue'
import ActuatorList from './ActuatorList.vue'
import GenerateUiCasesModal from '../components/generate/GenerateUiCasesModal.vue'
import { sendChatMessageStream } from '@/features/langgraph/services/chatService'
import type { ChatRequest } from '@/features/langgraph/types/chat'
import type { UiModule } from '../types'
import {
  buildUiGenerationMessage,
  collectExistingUiObjects,
  fetchEnvConfigs,
  fetchRequirementModules,
  type UiGenerationFormData,
} from '../services/uiCaseGeneration'

const { locale, tl } = useAppI18n()
const projectStore = useProjectStore()
const router = useRouter()
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

// ---------------------------------------------------------------------------
// AI 一键生成 UI 用例
// ---------------------------------------------------------------------------
const showGenerateModal = ref(false)
const isSubmittingGeneration = ref(false)

const handleGenerateSubmit = async (formData: UiGenerationFormData) => {
  const projectId = projectStore.currentProjectId
  if (!projectId) {
    Notification.warning({ title: tl('启动失败'), content: tl('请先选择项目'), duration: 4000 })
    return
  }
  isSubmittingGeneration.value = true
  try {
    // 并行收集上下文：需求模块正文、环境信息、已有对象（查重）
    const [requirementModules, envConfigs, existing] = await Promise.all([
      formData.requirementModuleId && formData.requirementDocumentId
        ? fetchRequirementModules(formData.requirementDocumentId).catch(() => [])
        : Promise.resolve([]),
      fetchEnvConfigs(projectId).catch(() => []),
      collectExistingUiObjects(projectId).catch(() => ({ pageNames: [], pageUrls: [], caseNames: [] })),
    ])
    const requirementModule = requirementModules.find((m) => m.id === formData.requirementModuleId) || null
    const envConfig = envConfigs.find((env) => env.id === formData.envConfigId) || null

    const message = buildUiGenerationMessage({ formData, projectId, requirementModule, envConfig, existing })

    const requestData: ChatRequest = {
      message,
      project_id: String(projectId),
      module_key: 'testcase_generation',
      use_knowledge_base: formData.useKnowledgeBase && !!formData.knowledgeBaseId,
      ui_generation: {
        env_config_id: formData.envConfigId ?? undefined,
        auth_state_id: formData.authMode === 'auth_state' ? (formData.authStateId ?? undefined) : undefined,
        username: formData.authMode === 'credentials' ? formData.username : undefined,
        password: formData.authMode === 'credentials' ? formData.password : undefined,
      },
    }
    if (formData.knowledgeBaseId) {
      requestData.knowledge_base_id = formData.knowledgeBaseId
    }

    sendChatMessageStream(
      requestData,
      (sessionId) => {
        localStorage.setItem('langgraph_session_id', sessionId)
        // 同步知识库设置：对话窗口 onActivated 时从该 localStorage 恢复开关状态
        localStorage.setItem('langgraph_knowledge_settings', JSON.stringify({
          useKnowledgeBase: requestData.use_knowledge_base || false,
          selectedKnowledgeBaseId: formData.knowledgeBaseId || null,
          similarityThreshold: 0.3,
          topK: 5,
        }))
        showStartNotification()
        // 生成完成后刷新测试用例页签数据
        setTimeout(() => {
          testCaseListRef.value?.refresh?.()
        }, 5000)
      },
    )
  } catch (error: any) {
    Notification.error({
      title: tl('启动失败'),
      content: error?.message || tl('生成任务启动失败，请重试'),
      duration: 5000,
    })
  } finally {
    isSubmittingGeneration.value = false
  }
}

// 提交成功通知：附「查看生成进度」按钮跳转到 AI 对话页（与接口自动化一致）
const showStartNotification = () => {
  const notificationReturn = Notification.info({
    title: tl('AI 生成任务已启动'),
    content: tl('用例将逐条生成并保存，完成后可在对话页查看总结'),
    footer: () =>
      h(
        'div',
        { style: 'text-align: right; margin-top: 12px;' },
        [
          h(
            'a',
            {
              href: 'javascript:;',
              onClick: () => {
                router.push({ name: 'LangGraphChat' })
                if (notificationReturn) notificationReturn.close()
              },
            },
            tl('查看生成进度')
          ),
        ]
      ),
    duration: 10000,
  })
}

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

/* AI 生成用例入口按钮（右上角，与全屏按钮错开） */
.ai-generate-entry {
  position: absolute;
  top: 20px;
  right: 60px;
  z-index: 10;
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
