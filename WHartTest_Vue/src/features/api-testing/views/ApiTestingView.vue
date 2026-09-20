<template>
  <div class="api-testing-container">
    <div v-if="!projectId" style="padding: 60px 0;">
      <a-empty :description="tl('请先从顶部选择一个项目')" />
    </div>
    <template v-else>
      <CardTabs
        v-model="activeTab"
        :tabs="tabItems"
        :key="`api-testing-${locale}`"
      >
        <template #interfaces>
          <InterfacesPanel />
        </template>
        <template #interface-cases>
          <InterfaceCasesPanel />
        </template>
        <template #testcases>
          <TestCasesPanel />
        </template>
        <template #testtasks>
          <TestTasksPanel />
        </template>
        <template #reports>
          <TestReportsPanel />
        </template>
        <template #environments>
          <EnvironmentsPanel />
        </template>
        <template #functions>
          <FunctionsPanel />
        </template>
        <template #sync>
          <SyncConfigPanel />
        </template>
      </CardTabs>
      <div class="ai-generate-entry">
        <a-button type="primary" size="small" @click="showGenerateModal = true">
          <template #icon><icon-robot /></template>
          {{ tl('AI 生成用例') }}
        </a-button>
      </div>
      <GenerateApiCasesModal
        ref="modalRef"
        v-model:visible="showGenerateModal"
        @submit="handleGenerateSubmit"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { useAppI18n } from '@/composables/useAppI18n'
import { useProjectStore } from '@/store/projectStore'
import { useThemeStore } from '@/store/themeStore'
import '../styles/arco-overrides.css'

import InterfacesPanel from '../components/interfaces/InterfacesPanel.vue'
import InterfaceCasesPanel from '../components/interface-cases/InterfaceCasesPanel.vue'
import TestCasesPanel from '../components/testcases/TestCasesPanel.vue'
import TestTasksPanel from '../components/testtasks/TestTasksPanel.vue'
import TestReportsPanel from '../components/test-reports/TestReportsPanel.vue'
import EnvironmentsPanel from '../components/environments/EnvironmentsPanel.vue'
import FunctionsPanel from '../components/functions/FunctionsPanel.vue'
import SyncConfigPanel from '../components/sync-config/SyncConfigPanel.vue'
import CardTabs from '../components/shared/CardTabs.vue'
import GenerateApiCasesModal from '../components/generate/GenerateApiCasesModal.vue'
import { h } from 'vue'
import { Notification } from '@arco-design/web-vue'
import { useRouter } from 'vue-router'
import { sendChatMessageStream } from '@/features/langgraph/services/chatService'
import type { ChatRequest } from '@/features/langgraph/types/chat'
import { getInterfaces } from '../services/interfaceService'
import {
  extractConstraints,
  collectExistingInterfaceCaseNames,
  collectExistingScenarioCaseNames,
  buildGenerationMessage,
  type GenerationFormData,
  type ConstraintExtractResult,
  type GenerationInterfaceInfo,
} from '../services/apiCaseGeneration'
import type { ApiInterface } from '../types/interface'

const route = useRoute()
const router = useRouter()
const { locale, isEnglish, tl } = useAppI18n()
const projectStore = useProjectStore()
const themeStore = useThemeStore()
const projectId = computed(() => projectStore.currentProjectId)
const activeTab = ref('interfaces')
const API_TESTING_THEME_CLASS = 'api-testing-theme'
const isDarkTheme = computed(() => themeStore.isBlack)

const syncApiTestingThemeClass = () => {
  if (typeof document === 'undefined' || !document.body) {
    return
  }

  document.body.classList.toggle(API_TESTING_THEME_CLASS, isDarkTheme.value)
}

onMounted(() => {
  syncApiTestingThemeClass()
})

onBeforeUnmount(() => {
  if (typeof document !== 'undefined' && document.body) {
    document.body.classList.remove(API_TESTING_THEME_CLASS)
  }
})

watch(isDarkTheme, () => {
  syncApiTestingThemeClass()
}, { immediate: true })

// Support tab switching via query param (e.g. /api-testing?tab=testcases)
watch(() => route.query.tab, (newTab) => {
  if (newTab && typeof newTab === 'string') {
    activeTab.value = newTab
  }
}, { immediate: true })

const tabItems = computed(() => isEnglish.value ? [
  { key: 'interfaces', title: 'Interfaces' },
  { key: 'interface-cases', title: 'Interface Cases' },
  { key: 'testcases', title: 'Scenario Cases' },
  { key: 'testtasks', title: 'Test Tasks' },
  { key: 'reports', title: 'Reports' },
  { key: 'environments', title: 'Environments' },
  { key: 'functions', title: 'Functions' },
  { key: 'sync', title: 'Sync Config' },
] : [
  { key: 'interfaces', title: '接口管理' },
  { key: 'interface-cases', title: '接口用例' },
  { key: 'testcases', title: '场景用例' },
  { key: 'testtasks', title: '测试任务' },
  { key: 'reports', title: '测试报告' },
  { key: 'environments', title: '环境管理' },
  { key: 'functions', title: '自定义函数' },
  { key: 'sync', title: '同步配置' },
])

// ---------------------------------------------------------------------------
// AI 生成接口测试用例
// ---------------------------------------------------------------------------

const showGenerateModal = ref(false)
const modalRef = ref<InstanceType<typeof GenerateApiCasesModal> | null>(null)

const fetchSelectedInterfaces = async (ids: number[]): Promise<GenerationInterfaceInfo[]> => {
  const idSet = new Set(ids)
  // getInterfaces 返回 { data: { results, count }, status } 形状（无 success 字段），与弹窗 fetchData 一致的读取方式
  const response: any = await getInterfaces({ page_size: 200 })
  const payload: any = response?.data
  const list: ApiInterface[] = Array.isArray(payload) ? payload : payload?.results || []
  return list.filter(item => idSet.has(item.id)) as GenerationInterfaceInfo[]
}

const showStartNotification = (done: number, total: number) => {
  const isBatch = total > 1
  const notificationReturn = Notification.info({
    title: tl('AI 生成任务已启动'),
    content: isBatch
      ? tl(`共 ${total} 个接口将逐接口串行生成并保存，每个接口独立试跑验证`)
      : tl('用例将逐条生成并保存，完成后可在对话页查看总结'),
    footer: () => h(
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

const handleGenerateSubmit = async (formData: GenerationFormData) => {
  if (!projectId.value) return
  try {
    // 0. 登录接口 ID（选中集合外的也要拉取定义）
    const allNeededIds = formData.loginInterfaceId
      ? Array.from(new Set([...formData.interfaceIds, formData.loginInterfaceId]))
      : formData.interfaceIds

    // 1. 获取接口定义（带完整 body/params/validators 的详情字段）
    const allInterfaces = await fetchSelectedInterfaces(allNeededIds)
    const interfaces = allInterfaces.filter(item => formData.interfaceIds.includes(item.id))
    const loginInterface = formData.loginInterfaceId
      ? allInterfaces.find(item => item.id === formData.loginInterfaceId) || null
      : null
    if (!interfaces.length) {
      Notification.warning({
        title: tl('获取接口定义失败'),
        content: tl('未能获取选中接口的完整定义，请重试'),
        duration: 5000,
      })
      return
    }

    // 2. 约束提取（有文档时）：弹窗关闭前直接从组件实例取用户上传的文件
    let constraints: ConstraintExtractResult | null = null
    let documentName = ''
    const file = modalRef.value?.getDocumentFile() || null
    if (file) {
      try {
        constraints = await extractConstraints(file, formData.interfaceIds)
        documentName = file.name
      } catch {
        Notification.warning({
          title: tl('约束提取失败'),
          content: tl('接口文档解析失败，将按无约束模式生成'),
          duration: 5000,
        })
      }
    }

    // 3. 已有用例名清单
    const existingNames = formData.caseType === 'scenario'
      ? await collectExistingScenarioCaseNames().catch(() => [])
      : await collectExistingInterfaceCaseNames(formData.interfaceIds).catch(() => [])

    // 4. 拼装指令并发送
    // 场景模式：一条 message 提交全部；单接口模式：逐接口串行提交（结构上消除工具漂移与总量收敛）
    const submitRequest = (message: string) => new Promise<void>((resolve, reject) => {
      const requestData: ChatRequest = {
        message,
        project_id: String(projectId.value),
        module_key: 'testcase_generation',
        use_knowledge_base: formData.useKnowledgeBase && !!formData.knowledgeBaseId,
      }
      if (formData.knowledgeBaseId) {
        requestData.knowledge_base_id = formData.knowledgeBaseId
      }
      try {
        sendChatMessageStream(
          requestData,
          (sessionId) => {
            localStorage.setItem('langgraph_session_id', sessionId)
            localStorage.setItem('langgraph_knowledge_settings', JSON.stringify({
              useKnowledgeBase: requestData.use_knowledge_base || false,
              selectedKnowledgeBaseId: formData.knowledgeBaseId || null,
              similarityThreshold: 0.3,
              topK: 5,
            }))
            // 流建立即视为该批次提交成功（后续生成在服务端异步进行）
            resolve()
          },
        )
      } catch (err) {
        reject(err)
      }
    })

    const message = buildGenerationMessage({
      formData,
      interfaces,
      projectId: projectId.value,
      existingNames,
      constraints,
      documentName,
      loginInterface,
    })
    showStartNotification(1, 1)
    await submitRequest(message)
  } catch (error: any) {
    Notification.error({
      title: tl('启动失败'),
      content: error?.message || tl('生成任务启动失败，请重试'),
      duration: 5000,
    })
  }
}

</script>

<style scoped>
.api-testing-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: var(--color-bg-2);
  border-radius: 8px;
  position: relative;
}

.ai-generate-entry {
  position: absolute;
  top: 12px;
  right: 16px;
  z-index: 10;
}

.api-testing-container :deep(.card-tabs) {
  flex: 1;
  min-height: 0;
}

.api-testing-container :deep(.card-tab-pane) {
  overflow: hidden;
}
</style>
