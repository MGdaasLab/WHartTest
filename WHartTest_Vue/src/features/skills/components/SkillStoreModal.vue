<template>
  <a-modal
    v-model:visible="visible"
    :title="text.title"
    :width="900"
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
            <div class="card-top">
              <a-checkbox
                :model-value="state.selected"
                @click.stop
                @change="onCheckboxChange(state, $event as boolean)"
              />
              <div class="card-title">
                {{ skillDisplayName(state.item) }}
              </div>
              <a-tag v-if="state.installed" color="green" size="small">{{ text.installedTag }}</a-tag>
            </div>
            <div class="card-desc">{{ skillDisplayDesc(state.item) }}</div>
            <div class="card-meta">
              <span v-if="state.item.version" class="meta-item">
                <icon-tag /> v{{ state.item.version }}
              </span>
              <span v-if="state.item.author" class="meta-item">
                <icon-user /> {{ state.item.author }}
              </span>
            </div>
            <div class="card-tags" v-if="state.item.tags && state.item.tags.length > 0">
              <a-tag
                v-for="t in state.item.tags"
                :key="t"
                size="small"
                color="arcoblue"
              >{{ t }}</a-tag>
            </div>
            <div class="card-footer">
              <a-button
                v-if="state.item.readme_path"
                type="text"
                size="mini"
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
const manifestStates = ref<StoreItemState[]>([])
const showSourceManager = ref(false)

const batchRunning = ref(false)
const batchProcessed = ref(0)
const batchTotal = ref(0)
const batchFailed = ref(0)
const batchCompletedAt = ref<number | null>(null)

const readmeVisible = ref(false)
const readmeLoading = ref(false)
const currentReadme = ref<{ name: string; content: string } | null>(null)

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
  if (!kw) return manifestStates.value
  return manifestStates.value.filter(s => {
    const name = skillDisplayName(s.item).toLowerCase()
    const desc = skillDisplayDesc(s.item).toLowerCase()
    return name.includes(kw) || desc.includes(kw)
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
  height: min(640px, calc(100vh - 200px));
  min-height: 320px;
}

@media (max-height: 520px) {
  .skill-store {
    height: calc(100vh - 160px);
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

.select-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border-2);
  margin-bottom: 12px;
}

.selected-count {
  color: var(--color-text-3);
  font-size: 13px;
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

.store-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(260px, 100%), 1fr));
  gap: 12px;
  height: 100%;
  overflow-y: auto;
  padding: 4px;
}

.store-card {
  background: var(--color-bg-2);
  border: 2px solid var(--color-border-2);
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.store-card:hover {
  border-color: var(--color-primary-light-2);
}

.store-card.selected {
  border-color: rgb(var(--primary-6));
  background: var(--color-fill-1);
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

.card-top {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.card-title {
  font-weight: 600;
  font-size: 14px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-desc {
  font-size: 12px;
  color: var(--color-text-2);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 32px;
}

.card-meta {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: var(--color-text-3);
  flex-wrap: wrap;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

.card-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 4px;
  font-size: 12px;
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
