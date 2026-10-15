<template>
  <a-modal
    v-model:visible="visible"
    :title="text.title"
    :width="1000"
    :footer="false"
    :mask-closable="false"
    :unmount-on-close="false"
    :body-style="skillStoreModalBodyStyle"
    @cancel="handleCancel"
  >
    <div class="skill-store">
      <!-- 顶部工具栏 -->
      <div class="store-toolbar">
        <a-space wrap>
          <a-select
            v-model="activeSourceId"
            :style="{ width: '240px' }"
            :placeholder="text.selectSource"
            @change="onSourceChange"
          >
            <a-option
              v-for="source in allSources"
              :key="source.id"
              :value="source.id"
              :label="source.name"
            />
          </a-select>
          <a-button @click="showSourceManager = true">
            <template #icon><icon-settings /></template>
            {{ text.manageSources }}
          </a-button>
          <a-button @click="loadManifest(true)" :loading="loadingManifest">
            <template #icon><icon-refresh /></template>
            {{ text.refresh }}
          </a-button>
          <a-button
            type="outline"
            :href="skillHubWebUrl"
            target="_blank"
          >
            <template #icon><icon-link /></template>
            {{ text.visitSkillHub }}
          </a-button>
        </a-space>
        <a-input
          v-model="searchKeyword"
          :placeholder="text.searchPlaceholder"
          allow-clear
          :style="{ width: '220px' }"
        >
          <template #prefix><icon-search /></template>
        </a-input>
      </div>

      <!-- 分类筛选栏 -->
      <div class="category-nav-bar" v-if="categories.length > 1">
        <div class="category-pill-list">
          <button
            v-for="cat in categories"
            :key="cat.slug"
            type="button"
            class="category-pill-btn"
            :class="{ active: selectedCategory === cat.slug }"
            @click="onSelectCategory(cat.slug)"
          >
            <span class="pill-title">{{ categoryDisplayName(cat) }}</span>
            <span class="pill-count">{{ cat.skill_count }}</span>
          </button>
        </div>
      </div>

      <!-- 选择操作栏 -->
      <div class="select-bar" v-if="filteredStates.length > 0">
        <a-checkbox
          :model-value="allSelected"
          :indeterminate="someSelected && !allSelected"
          @change="toggleSelectAll"
        >
          {{ text.selectAll }}（{{ filteredStates.length }}）
        </a-checkbox>
        <span class="selected-count" v-if="selectedCount > 0">
          {{ text.selectedHint(selectedCount) }}
        </span>
      </div>

      <!-- 内容区 -->
      <a-spin class="store-content-spin" :loading="loadingManifest">
        <div v-if="manifestError" class="store-empty">
          <icon-exclamation-circle style="font-size: 40px; color: var(--color-danger-light-4)" />
          <p class="empty-text">{{ manifestError }}</p>
          <a-button @click="loadManifest(true)" type="primary" size="small">
            {{ text.retry }}
          </a-button>
        </div>

        <div v-else-if="!loadingManifest && filteredStates.length === 0" class="store-empty">
          <icon-empty style="font-size: 48px; color: #c0c4cc" />
          <p class="empty-text">
            {{ searchKeyword ? text.noSearchResult : text.emptyManifest }}
          </p>
        </div>

        <div v-else class="store-grid">
          <div
            v-for="(state, idx) in filteredStates"
            :key="state.item.id"
            class="store-card"
            :class="{
              installed: state.installed,
              selected: state.selected,
              busy: state.status === 'installing' || state.status === 'uninstalling',
              error: state.status === 'error',
            }"
            @click="toggleSelect(state)"
          >
            <!-- 卡片头部：复选框 + 标题 + 分类/安装状态徽标 -->
            <div class="card-header">
              <div class="card-title-box">
                <a-checkbox
                  :model-value="state.selected"
                  class="card-checkbox"
                  @click.stop
                  @change="onCheckboxChange(state, $event as boolean)"
                />
                <span class="card-title" :title="skillDisplayName(state.item)">
                  {{ skillDisplayName(state.item) }}
                </span>
              </div>
              <div class="card-badges">
                <span v-if="state.installed" class="installed-badge">
                  <icon-check-circle-fill class="installed-icon" />
                  {{ text.installedTag }}
                </span>
                <span v-else-if="skillCategoryLabel(state.item)" class="category-badge">
                  {{ skillCategoryLabel(state.item) }}
                </span>
              </div>
            </div>

            <!-- 卡片描述：2 行省略 -->
            <div class="card-body">
              <p class="card-desc" :title="skillDisplayDesc(state.item)">
                {{ skillDisplayDesc(state.item) || '暂无详细描述' }}
              </p>
            </div>

            <!-- 卡片底部：版本、作者、预览按钮、状态 -->
            <div class="card-footer">
              <div class="card-meta">
                <span v-if="state.item.version" class="version-tag">
                  v{{ state.item.version }}
                </span>
                <span v-if="state.item.author" class="author-tag" :title="state.item.author">
                  <icon-user /> {{ state.item.author }}
                </span>
              </div>

              <div class="card-actions">
                <a-button
                  v-if="state.item.readme_path"
                  type="text"
                  size="mini"
                  class="preview-btn"
                  @click.stop="openReadme(state.item)"
                >
                  <icon-eye /> {{ text.preview }}
                </a-button>
                <span class="status-indicator" v-if="state.status === 'installing'">
                  <icon-loading /> {{ text.installing }}
                </span>
                <span class="status-indicator" v-if="state.status === 'uninstalling'">
                  <icon-loading /> {{ text.uninstalling }}
                </span>
                <span class="status-indicator ok" v-if="state.status === 'ok'">
                  <icon-check-circle-fill /> {{ text.done }}
                </span>
                <span class="status-indicator err" v-if="state.status === 'error'" :title="state.error">
                  <icon-close-circle-fill /> {{ text.failed }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </a-spin>

      <!-- 底部操作 -->
      <div class="store-footer" v-if="manifestStates.length > 0">
        <div class="footer-left">
          <a-progress
            v-if="batchRunning || batchCompletedAt"
            :percent="batchProgressRatio"
            :status="batchProgressStatus"
            :show-text="true"
            :style="{ width: '260px' }"
          />
        </div>
        <div class="footer-right">
          <a-button :disabled="batchRunning" @click="handleCancel">{{ text.close }}</a-button>
          <a-button
            type="outline"
            status="danger"
            :disabled="batchRunning || selectedInstalledCount === 0"
            @click="handleBatchUninstall"
          >
            <template #icon><icon-delete /></template>
            {{ text.batchUninstall }}（{{ selectedInstalledCount }}）
          </a-button>
          <a-button
            type="primary"
            :disabled="batchRunning || selectedNotInstalledCount === 0"
            @click="handleBatchInstall"
          >
            <template #icon><icon-download /></template>
            {{ text.batchInstall }}（{{ selectedNotInstalledCount }}）
          </a-button>
        </div>
      </div>
    </div>

    <!-- README 预览 -->
    <a-modal
      v-model:visible="readmeVisible"
      :title="currentReadme?.name || text.preview"
      :width="700"
      :footer="false"
      :unmount-on-close="true"
    >
      <a-spin :loading="readmeLoading">
        <pre class="readme-content">{{ currentReadme?.content || '' }}</pre>
      </a-spin>
    </a-modal>

    <!-- 源管理子对话框 -->
    <SkillStoreSourceManager
      v-model:visible="showSourceManager"
      :default-source="defaultSourceInfo"
      :allow-custom-source="storeConfig?.allow_custom_source ?? true"
      @sources-updated="onSourcesUpdated"
    />
  </a-modal>

  <SkillApiKeyConfirmModal
    :visible="showApiKeyConfirm"
    :skill-names="pendingInternalSkillNames"
    @confirmed="onApiKeyConfirmedForInstall"
    @update:visible="onApiKeyModalVisible"
  />
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { SkillService } from '../services/skillService'
import { SkillStoreService, SKILL_STORE_DEFAULT_SOURCE_ID } from '../services/skillStoreService'
import SkillStoreSourceManager from './SkillStoreSourceManager.vue'
import SkillApiKeyConfirmModal from './SkillApiKeyConfirmModal.vue'
import type {
  SkillListItem,
  SkillStoreConfig,
  SkillStoreSource,
  SkillStoreManifest,
  SkillStoreCategory,
  ManifestSkill,
  StoreItemState,
} from '../types'
import { useAppI18n } from '@/composables/useAppI18n'
import { isInternalPlatformSkill } from '../utils/internalSkills'

const props = defineProps<{
  visible: boolean
  projectId: number
  installedSkills: SkillListItem[]
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'skills-changed'): void
}>()

const { isEnglish } = useAppI18n()

const text = computed(() => (
  isEnglish.value
    ? {
        title: 'Skill Hub',
        selectSource: 'Select source',
        manageSources: 'Manage sources',
        refresh: 'Refresh',
        searchPlaceholder: 'Search by name or description',
        selectAll: 'Select all',
        selectedHint: (n: number) => `${n} selected`,
        retry: 'Retry',
        emptyManifest: 'No Skills in this source',
        noSearchResult: 'No results match the keyword',
        installedTag: 'Installed',
        preview: 'Preview',
        installing: 'Installing',
        uninstalling: 'Uninstalling',
        done: 'Done',
        failed: 'Failed',
        close: 'Close',
        batchInstall: 'Batch install',
        batchUninstall: 'Batch uninstall',
        confirmUninstallTitle: 'Uninstall confirmation',
        confirmUninstallContent: (n: number) => `Uninstall ${n} installed skill(s)?`,
        ok: 'OK',
        cancel: 'Cancel',
        batchInstallDone: (ok: number, fail: number) =>
          `Installation complete: ${ok} succeeded, ${fail} failed`,
        batchUninstallDone: (ok: number, fail: number) =>
          `Uninstallation complete: ${ok} succeeded, ${fail} failed`,
        loadConfigFailed: 'Failed to load store config',
        visitSkillHub: 'Visit SkillHub Website',
      }
    : {
        title: 'Skill 中心',
        selectSource: '选择源',
        manageSources: '管理源',
        refresh: '刷新',
        searchPlaceholder: '按名称或描述搜索',
        selectAll: '全选',
        selectedHint: (n: number) => `已选 ${n} 个`,
        retry: '重试',
        emptyManifest: '该源下暂无 Skill',
        noSearchResult: '没有匹配的 Skill',
        installedTag: '已安装',
        preview: '预览',
        installing: '安装中',
        uninstalling: '卸载中',
        done: '完成',
        failed: '失败',
        close: '关闭',
        batchInstall: '批量安装',
        batchUninstall: '批量卸载',
        confirmUninstallTitle: '确认卸载',
        confirmUninstallContent: (n: number) => `确定要卸载已选中的 ${n} 个已安装 Skill 吗？`,
        ok: '确定',
        cancel: '取消',
        batchInstallDone: (ok: number, fail: number) =>
          `安装完成：成功 ${ok}，失败 ${fail}`,
        batchUninstallDone: (ok: number, fail: number) =>
          `卸载完成：成功 ${ok}，失败 ${fail}`,
        loadConfigFailed: '获取商店配置失败',
        visitSkillHub: '访问 Skill 网站',
      }
))

const visible = computed({
  get: () => props.visible,
  set: (v: boolean) => emit('update:visible', v),
})

const skillStoreModalBodyStyle = {
  maxHeight: 'calc(100vh - 160px)',
  overflow: 'hidden',
}

const storeConfig = ref<SkillStoreConfig | null>(null)
const customSources = ref<SkillStoreSource[]>([])
const activeSourceId = ref<string>(SKILL_STORE_DEFAULT_SOURCE_ID)
const loadingManifest = ref(false)
const manifest = ref<SkillStoreManifest | null>(null)
const manifestError = ref('')
const searchKeyword = ref('')
const selectedCategory = ref<string>('all')
const manifestStates = ref<StoreItemState[]>([])
const showSourceManager = ref(false)

const categories = computed<SkillStoreCategory[]>(() => {
  if (manifest.value?.categories && manifest.value.categories.length > 0) {
    return manifest.value.categories
  }
  const map = new Map<string, { slug: string; name: string; name_en?: string; count: number }>()
  for (const s of manifestStates.value) {
    const slug = s.item.category || (s.item.id.includes('--') ? s.item.id.split('--')[0] : '')
    if (slug) {
      const name = s.item.category_name || slug
      const name_en = s.item.category_name_en || slug
      const cur = map.get(slug) || { slug, name, name_en, count: 0 }
      cur.count++
      map.set(slug, cur)
    }
  }
  if (map.size === 0) return []
  const list: SkillStoreCategory[] = [
    {
      slug: 'all',
      name: isEnglish.value ? 'All' : '全部',
      name_en: 'All',
      skill_count: manifestStates.value.length,
    }
  ]
  const sorted = Array.from(map.values()).sort((a, b) => b.count - a.count)
  for (const item of sorted) {
    list.push({
      slug: item.slug,
      name: item.name,
      name_en: item.name_en,
      skill_count: item.count,
    })
  }
  return list
})

function onSelectCategory(catSlug: string) {
  selectedCategory.value = catSlug
}

function categoryDisplayName(cat: SkillStoreCategory) {
  if (isEnglish.value && cat.name_en) {
    return cat.name_en
  }
  return cat.name || cat.slug
}

function skillCategoryLabel(item: ManifestSkill) {
  if (isEnglish.value && item.category_name_en) {
    return item.category_name_en
  }
  return item.category_name || item.category || ''
}

const batchRunning = ref(false)
const batchProcessed = ref(0)
const batchTotal = ref(0)
const batchFailed = ref(0)
const batchCompletedAt = ref<number | null>(null)

const readmeVisible = ref(false)
const readmeLoading = ref(false)
const currentReadme = ref<{ name: string; content: string } | null>(null)

const skillHubWebUrl = computed(() => {
  const url = activeSource.value?.baseUrl || storeConfig.value?.default_source || 'https://skillhub.mgdaas.com/'
  if (url.includes('skillhub')) {
    return 'https://skillhub.mgdaas.com/'
  }
  return url
})

const defaultSourceInfo = computed<SkillStoreSource | null>(() => {
  if (!storeConfig.value?.default_source) return null
  return {
    id: SKILL_STORE_DEFAULT_SOURCE_ID,
    name: storeConfig.value.default_source_name || '默认源',
    baseUrl: storeConfig.value.default_source,
    isDefault: true,
  }
})

const allSources = computed<SkillStoreSource[]>(() => {
  const list: SkillStoreSource[] = []
  if (defaultSourceInfo.value) list.push(defaultSourceInfo.value)
  list.push(...customSources.value)
  return list
})

const activeSource = computed<SkillStoreSource | null>(() => {
  return allSources.value.find(s => s.id === activeSourceId.value) || defaultSourceInfo.value
})

const filteredStates = computed(() => {
  const kw = searchKeyword.value.trim().toLowerCase()
  const cat = selectedCategory.value

  return manifestStates.value.filter(s => {
    // 分类过滤
    if (cat !== 'all') {
      const itemCat = s.item.category || (s.item.id.includes('--') ? s.item.id.split('--')[0] : '')
      if (itemCat !== cat) {
        return false
      }
    }
    // 关键字过滤
    if (kw) {
      const name = skillDisplayName(s.item).toLowerCase()
      const desc = skillDisplayDesc(s.item).toLowerCase()
      const catName = (s.item.category_name || '').toLowerCase()
      const tags = (s.item.tags || []).join(' ').toLowerCase()
      if (!name.includes(kw) && !desc.includes(kw) && !catName.includes(kw) && !tags.includes(kw)) {
        return false
      }
    }
    return true
  })
})

const selectedCount = computed(() => filteredStates.value.filter(s => s.selected).length)
const selectedInstalledCount = computed(() => filteredStates.value.filter(s => s.selected && s.installed).length)
const selectedNotInstalledCount = computed(() => filteredStates.value.filter(s => s.selected && !s.installed).length)
const allSelected = computed(() => filteredStates.value.length > 0 && filteredStates.value.every(s => s.selected))
const someSelected = computed(() => filteredStates.value.some(s => s.selected))

const batchProgressRatio = computed(() => {
  if (batchTotal.value === 0) return 0
  const roundedPercent = Math.round((batchProcessed.value / batchTotal.value) * 100)
  return Math.min(Math.max(roundedPercent / 100, 0), 1)
})

const batchProgressStatus = computed(() => {
  if (batchRunning.value) return 'normal'
  if (batchFailed.value > 0) return 'warning'
  return 'success'
})

function skillDisplayName(item: ManifestSkill): string {
  return isEnglish.value && item.name_en ? item.name_en : item.name
}

function skillDisplayDesc(item: ManifestSkill): string {
  return isEnglish.value && item.description_en ? item.description_en : item.description
}

async function loadStoreConfig() {
  try {
    storeConfig.value = await SkillService.getStoreConfig(props.projectId)
  } catch (e: any) {
    Message.error(e?.message || text.value.loadConfigFailed)
  }
}

function refreshCustomSources() {
  customSources.value = SkillStoreService.getCustomSources()
}

function ensureActiveSourceExists() {
  const exists = allSources.value.find(s => s.id === activeSourceId.value)
  if (!exists) {
    activeSourceId.value = SKILL_STORE_DEFAULT_SOURCE_ID
    SkillStoreService.setActiveSourceId(activeSourceId.value)
  }
}

async function loadManifest(showError = false) {
  if (!activeSource.value) {
    manifestError.value = showError ? text.value.loadConfigFailed : ''
    return
  }
  loadingManifest.value = true
  manifestError.value = ''
  selectedCategory.value = 'all'
  try {
    const m = await SkillStoreService.fetchManifest(props.projectId, activeSource.value.baseUrl)
    manifest.value = m
    rebuildStates()
  } catch (e: any) {
    manifest.value = null
    manifestStates.value = []
    manifestError.value = e?.message || '加载 manifest 失败'
  } finally {
    loadingManifest.value = false
  }
}

function rebuildStates() {
  const m = manifest.value
  if (!m) {
    manifestStates.value = []
    return
  }
  const installedMap = new Map(props.installedSkills.map(s => [s.name, s.id]))
  manifestStates.value = m.skills.map(item => ({
    item,
    installed: installedMap.has(item.name),
    installedId: installedMap.get(item.name) ?? null,
    selected: false,
    status: 'idle' as const,
    error: '',
  }))
  batchCompletedAt.value = null
  batchFailed.value = 0
  batchProcessed.value = 0
  batchTotal.value = 0
}

function onSourceChange(id: string | number | undefined) {
  const sid = String(id ?? SKILL_STORE_DEFAULT_SOURCE_ID)
  activeSourceId.value = sid
  SkillStoreService.setActiveSourceId(sid)
  loadManifest()
}

function onSourcesUpdated() {
  refreshCustomSources()
  ensureActiveSourceExists()
}

function toggleSelect(state: StoreItemState) {
  if (batchRunning.value) return
  if (state.status === 'installing' || state.status === 'uninstalling') return
  state.selected = !state.selected
}

function onCheckboxChange(state: StoreItemState, v: boolean) {
  if (batchRunning.value) return
  state.selected = v
}

function toggleSelectAll(v: boolean | (string | number | boolean)[]) {
  if (batchRunning.value) return
  const flag = typeof v === 'boolean' ? v : false
  filteredStates.value.forEach(s => {
    if (s.status === 'installing' || s.status === 'uninstalling') return
    s.selected = flag
  })
}

async function openReadme(item: ManifestSkill) {
  if (!item.readme_path || !activeSource.value) return
  readmeVisible.value = true
  readmeLoading.value = true
  currentReadme.value = { name: skillDisplayName(item), content: '' }
  try {
    const content = await SkillStoreService.fetchReadme(props.projectId, activeSource.value.baseUrl, item.readme_path)
    currentReadme.value = { name: skillDisplayName(item), content }
  } catch (e: any) {
    currentReadme.value = { name: skillDisplayName(item), content: `加载失败：${e?.message || e}` }
  } finally {
    readmeLoading.value = false
  }
}

const showApiKeyConfirm = ref(false)
const pendingInternalSkillNames = ref<string[]>([])
const pendingInstallTargets = ref<StoreItemState[]>([])

async function runBatchInstall(targets: StoreItemState[], apiKey?: string) {
  batchRunning.value = true
  batchTotal.value = targets.length
  batchProcessed.value = 0
  batchFailed.value = 0
  batchCompletedAt.value = null

  for (const state of targets) {
    state.status = 'installing'
    state.error = ''
    try {
      const baseUrl = activeSource.value!.baseUrl
      const zipUrl = SkillStoreService.resolveZipUrl(baseUrl, state.item.zip_path)
      const needKey = isInternalPlatformSkill(state.item.name)
      const skills = await SkillService.importFromZipUrl(
        props.projectId,
        zipUrl,
        state.item.sha256,
        needKey ? apiKey : undefined
      )
      state.status = 'ok'
      state.installed = true
      state.installedId = skills[0]?.id ?? null
    } catch (e: any) {
      state.status = 'error'
      state.error = e?.message || '安装失败'
      batchFailed.value += 1
    }
    batchProcessed.value += 1
  }

  batchRunning.value = false
  batchCompletedAt.value = Date.now()
  const okCount = batchTotal.value - batchFailed.value
  Message.info(text.value.batchInstallDone(okCount, batchFailed.value))
  emit('skills-changed')
}

async function handleBatchInstall() {
  if (batchRunning.value) return
  const targets = manifestStates.value.filter(s => s.selected && !s.installed)
  if (targets.length === 0) return

  const internal = targets.filter(s => isInternalPlatformSkill(s.item.name))
  if (internal.length > 0) {
    pendingInstallTargets.value = targets
    pendingInternalSkillNames.value = internal.map(s => s.item.name)
    showApiKeyConfirm.value = true
    return
  }

  await runBatchInstall(targets)
}

async function onApiKeyConfirmedForInstall(payload: { apiKey: string; keyId: number; keyName: string }) {
  const targets = pendingInstallTargets.value
  pendingInstallTargets.value = []
  pendingInternalSkillNames.value = []
  if (targets.length === 0) return
  await runBatchInstall(targets, payload.apiKey)
}

function onApiKeyModalVisible(v: boolean) {
  showApiKeyConfirm.value = v
  if (!v && !batchRunning.value) {
    // 用户取消确认时清理挂起安装目标，避免残留状态
    pendingInstallTargets.value = []
    pendingInternalSkillNames.value = []
  }
}

async function handleBatchUninstall() {
  if (batchRunning.value) return
  const targets = manifestStates.value.filter(s => s.selected && s.installed && s.installedId != null)
  if (targets.length === 0) return

  Modal.warning({
    title: text.value.confirmUninstallTitle,
    content: text.value.confirmUninstallContent(targets.length),
    hideCancel: false,
    okText: text.value.ok,
    cancelText: text.value.cancel,
    onOk: async () => {
      batchRunning.value = true
      batchTotal.value = targets.length
      batchProcessed.value = 0
      batchFailed.value = 0
      batchCompletedAt.value = null

      for (const state of targets) {
        state.status = 'uninstalling'
        state.error = ''
        try {
          await SkillService.deleteSkill(props.projectId, state.installedId!)
          state.status = 'ok'
          state.installed = false
          state.installedId = null
        } catch (e: any) {
          state.status = 'error'
          state.error = e?.message || '卸载失败'
          batchFailed.value += 1
        }
        batchProcessed.value += 1
      }

      batchRunning.value = false
      batchCompletedAt.value = Date.now()
      const okCount = batchTotal.value - batchFailed.value
      Message.info(text.value.batchUninstallDone(okCount, batchFailed.value))
      emit('skills-changed')
    },
  })
}

function handleCancel() {
  if (batchRunning.value) return
  visible.value = false
}

watch(
  () => props.visible,
  async (v) => {
    if (!v) return
    refreshCustomSources()
    activeSourceId.value = SkillStoreService.getActiveSourceId()
    if (!storeConfig.value) {
      await loadStoreConfig()
    }
    ensureActiveSourceExists()
    if (activeSource.value) {
      await loadManifest()
    }
  },
  { immediate: false }
)

watch(
  () => props.installedSkills,
  () => {
    if (manifest.value) rebuildStates()
  },
  { deep: true }
)
</script>

<style scoped>
.skill-store {
  display: flex;
  flex-direction: column;
  height: min(650px, calc(100vh - 180px));
  min-height: 420px;
}

@media (max-height: 520px) {
  .skill-store {
    height: calc(100vh - 150px);
  }
}

.store-content-spin {
  display: block;
  flex: 1;
  height: 100%;
  min-height: 0;
}

.store-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

/* 分类胶囊标签栏 */
.category-nav-bar {
  margin-bottom: 12px;
  overflow-x: auto;
  padding-bottom: 4px;
  scrollbar-width: thin;
}

.category-nav-bar::-webkit-scrollbar {
  height: 4px;
}

.category-nav-bar::-webkit-scrollbar-thumb {
  background: var(--color-fill-4);
  border-radius: 4px;
}

.category-pill-list {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: nowrap;
  white-space: nowrap;
}

.category-pill-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 18px;
  background: var(--color-fill-2);
  color: var(--color-text-2);
  font-size: 13px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.34, 0.69, 0.1, 1);
  user-select: none;
  outline: none;
  flex-shrink: 0;
}

.category-pill-btn:hover {
  background: var(--color-fill-3);
  color: var(--color-text-1);
}

.category-pill-btn.active {
  background: rgb(var(--primary-6));
  color: #fff;
  font-weight: 500;
  box-shadow: 0 2px 8px rgba(var(--primary-6), 0.25);
}

.pill-title {
  font-size: 13px;
}

.pill-count {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.06);
  line-height: 14px;
}

.category-pill-btn.active .pill-count {
  background: rgba(255, 255, 255, 0.25);
  color: #fff;
}

/* 选择与统计条 */
.select-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 8px 12px;
  background: var(--color-fill-1);
  border-radius: 6px;
  margin-bottom: 12px;
  border: 1px solid var(--color-border-1);
}

.selected-count {
  color: rgb(var(--primary-6));
  font-size: 12px;
  font-weight: 500;
}

.store-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
  gap: 12px;
  color: var(--color-text-3);
}

.empty-text {
  margin: 0;
  font-size: 14px;
}

/* 卡片网格：明确设置行高和顶部对齐，绝不纵向拉伸 */
.store-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
  grid-auto-rows: 154px;
  align-content: start;
  gap: 14px;
  height: 100%;
  overflow-y: auto;
  padding: 4px 6px 12px 4px;
}

/* 单个卡片 */
.store-card {
  height: 154px;
  box-sizing: border-box;
  background: var(--color-bg-2);
  border: 1px solid var(--color-border-2);
  border-radius: 8px;
  padding: 14px 16px 12px 16px;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.25, 0.8, 0.25, 1);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.store-card:hover {
  border-color: rgb(var(--primary-4));
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.store-card.selected {
  border-color: rgb(var(--primary-6));
  background: rgba(var(--primary-6), 0.02);
  box-shadow: 0 0 0 1px rgb(var(--primary-6)), 0 4px 12px rgba(var(--primary-6), 0.12);
}

.store-card.installed {
  background: var(--color-fill-1);
}

.store-card.busy {
  opacity: 0.7;
  pointer-events: none;
}

.store-card.error {
  border-color: rgb(var(--danger-6));
}

/* 卡片头部 */
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}

.card-title-box {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.card-checkbox {
  flex-shrink: 0;
  margin: 0;
}

.card-title {
  font-weight: 600;
  font-size: 14px;
  color: var(--color-text-1);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-badges {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.installed-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  font-weight: 500;
  padding: 2px 7px;
  border-radius: 4px;
  background: rgba(var(--success-6), 0.1);
  color: rgb(var(--success-6));
  border: 1px solid rgba(var(--success-6), 0.2);
}

.installed-icon {
  font-size: 12px;
}

.category-badge {
  font-size: 11px;
  font-weight: 500;
  padding: 2px 7px;
  border-radius: 4px;
  background: var(--color-fill-2);
  color: var(--color-text-3);
  border: 1px solid var(--color-border-1);
  white-space: nowrap;
}

/* 卡片描述 */
.card-body {
  flex: 1;
  min-height: 0;
  margin-top: 6px;
}

.card-desc {
  font-size: 12px;
  color: var(--color-text-3);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.5;
  margin: 0;
  word-break: break-word;
}

/* 卡片底部 */
.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-top: auto;
  padding-top: 8px;
  border-top: 1px dashed var(--color-border-2);
  font-size: 12px;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--color-text-3);
  min-width: 0;
  flex: 1;
}

.version-tag {
  font-family: var(--font-family-mono, monospace);
  font-size: 11px;
  color: var(--color-text-3);
  background: var(--color-fill-2);
  padding: 1px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}

.author-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.preview-btn {
  font-size: 12px;
  color: var(--color-text-2);
  padding: 0 6px;
  height: 24px;
  border-radius: 4px;
}

.preview-btn:hover {
  color: rgb(var(--primary-6));
  background: var(--color-fill-2);
}

.status-indicator {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--color-text-3);
}

.status-indicator.ok {
  color: rgb(var(--success-6));
}

.status-indicator.err {
  color: rgb(var(--danger-6));
}

/* 底部操作区 */
.store-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding-top: 12px;
  margin-top: 12px;
  border-top: 1px solid var(--color-border-2);
  flex-wrap: wrap;
}

.footer-right {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.readme-content {
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--color-fill-2);
  padding: 16px;
  border-radius: 4px;
  font-size: 13px;
  max-height: 500px;
  overflow-y: auto;
  margin: 0;
}
</style>
