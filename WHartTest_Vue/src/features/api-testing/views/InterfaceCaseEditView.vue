<template>
  <div class="api-testing-container" :class="isDarkTheme ? 'api-testing-container--dark' : 'api-testing-container--light'">
    <InterfaceCaseForm
      v-if="projectId"
      mode="edit"
      :interface-case-id="Number(id)"
    />
    <div v-else class="flex items-center justify-center h-full text-gray-500">
      {{ tl('请先选择项目') }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useProjectStore } from '@/store/projectStore'
import { useThemeStore } from '@/store/themeStore'
import { useAppI18n } from '@/composables/useAppI18n'
import InterfaceCaseForm from '../components/interface-cases/InterfaceCaseForm.vue'

defineProps<{ id: string | number }>()

const projectStore = useProjectStore()
const themeStore = useThemeStore()
const { tl } = useAppI18n()
const projectId = computed(() => projectStore.currentProjectId)
const isDarkTheme = computed(() => themeStore.isBlack)
</script>

<style scoped>
.api-testing-container {
  height: 100%;
  background: var(--ic-page-bg);
  border: 1px solid var(--ic-page-border);
  border-radius: 8px;
  overflow: hidden;
}

.api-testing-container--light {
  --ic-page-bg: color-mix(in srgb, var(--theme-card-bg) 94%, var(--theme-page-bg) 6%);
  --ic-page-border: rgba(148, 163, 184, 0.16);
}

.api-testing-container--dark {
  --ic-page-bg: rgb(17, 24, 39);
  --ic-page-border: rgba(75, 85, 99, 0.35);
}
</style>
