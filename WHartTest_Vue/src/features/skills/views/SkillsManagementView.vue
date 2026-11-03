<template>
  <div class="skills-management-view">
    <div class="page-header">
      <h2>{{ pageText.pageTitle }}</h2>
      <p class="page-description">
        {{ pageText.pageDescription }}
      </p>
    </div>

    <div v-if="currentProjectId" class="skills-container">
      <SkillManager :project-id="currentProjectId" :key="currentProjectId" />
    </div>
    <div v-else class="empty-state">
      <icon-apps style="font-size: 64px; color: #c0c4cc" />
      <p>{{ pageText.selectProjectFirst }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { SkillManager } from '@/features/skills'
import { useProjectStore } from '@/store/projectStore'
import { useAppI18n } from '@/composables/useAppI18n'

const projectStore = useProjectStore()
const { isEnglish } = useAppI18n()
const currentProjectId = computed(() => projectStore.currentProjectId)
const pageText = computed(() => (
  isEnglish.value
    ? {
        pageTitle: 'Skills Management',
        pageDescription: 'Manage project Agent Skills. Skills are modular capability extensions containing instructions and executable scripts.',
        selectProjectFirst: 'Select a project from the navigation first',
      }
    : {
        pageTitle: 'Skills 管理',
        pageDescription: '管理项目的 Agent Skills。Skills 是模块化的能力扩展，包含指令和可执行脚本。',
        selectProjectFirst: '请先在导航栏选择一个项目',
      }
))
</script>

<style scoped>
/* MainLayout 的 .content 是固定高度 + overflow: hidden（子页面自行控制滚动），
   根节点吃满高度并自身滚动即可，内部保持原有文档式布局与卡片高度不变。 */
.skills-management-view {
  height: 100%;
  box-sizing: border-box;
  padding: 24px;
  overflow-y: auto;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h2 {
  margin: 0 0 8px 0;
}

.page-description {
  color: var(--color-text-2);
  margin: 0;
}

.skills-container {
  background: var(--color-bg-2);
  border-radius: 8px;
  min-height: 400px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 0;
  color: var(--color-text-3);
}
</style>
