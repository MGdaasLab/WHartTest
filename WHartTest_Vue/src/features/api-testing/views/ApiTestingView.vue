<template>
  <div class="api-testing-container">
    <div v-if="!projectId" style="padding: 60px 0;">
      <a-empty :description="tl('请先从顶部选择一个项目')" />
    </div>
    <CardTabs
      v-else
      v-model="activeTab"
      :tabs="tabItems"
      :key="`api-testing-${locale}`"
      destroy-on-hide
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

const route = useRoute()
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
</script>

<style scoped>
.api-testing-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: var(--color-bg-2);
  border-radius: 8px;
}

.api-testing-container :deep(.card-tabs) {
  flex: 1;
  min-height: 0;
}

.api-testing-container :deep(.card-tab-pane) {
  overflow: hidden;
}
</style>
