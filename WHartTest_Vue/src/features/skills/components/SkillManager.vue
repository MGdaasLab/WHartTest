<template>
  <div class="skill-manager">
    <!-- 头部操作栏 -->
    <div class="header-bar">
      <h3>{{ text.title }}</h3>
      <a-space>
        <a-button type="primary" status="success" @click="showStoreModal = true">
          <template #icon><icon-storage /></template>
          {{ text.skillStore }}
        </a-button>
        <a-button @click="showGitImportModal = true">
          <template #icon><icon-github /></template>
          {{ text.importFromGit }}
        </a-button>
        <a-button type="primary" @click="showUploadModal = true">
          <template #icon><icon-upload /></template>
          {{ text.uploadSkill }}
        </a-button>
      </a-space>
    </div>

    <!-- Skills 列表 -->
    <a-spin :loading="loading">
      <div v-if="skills.length === 0" class="empty-state">
        <icon-apps style="font-size: 48px; color: #c0c4cc" />
        <p>{{ text.emptyState }}</p>
      </div>

      <div v-else class="skill-list">
        <div
          v-for="skill in skills"
          :key="skill.id"
          class="skill-card"
          :class="{ inactive: !skill.is_active }"
        >
          <div class="skill-header">
            <div class="skill-name">{{ skill.name }}</div>
            <a-switch
              v-model="skill.is_active"
              size="small"
              @change="(val) => handleToggle(skill, val as boolean)"
            />
          </div>
          <div class="skill-description">{{ skill.description }}</div>
          <div class="skill-footer">
            <span class="skill-meta">
              <icon-user /> {{ skill.creator_name }}
            </span>
            <span class="skill-meta">
              <icon-calendar /> {{ formatDate(skill.created_at) }}
            </span>
            <div class="skill-actions">
              <a-button type="text" size="mini" @click="handleViewContent(skill)">
                <icon-eye />
              </a-button>
              <a-popconfirm
                :content="text.deleteConfirm"
                @ok="handleDelete(skill)"
              >
                <a-button type="text" size="mini" status="danger">
                  <icon-delete />
                </a-button>
              </a-popconfirm>
            </div>
          </div>
        </div>
      </div>
    </a-spin>

    <!-- 上传弹窗 -->
    <a-modal
      v-model:visible="showUploadModal"
      :title="text.uploadSkill"
      :width="500"
      @ok="handleUpload"
      :ok-text="text.confirm"
      :cancel-text="text.cancel"
      :confirm-loading="uploading"
    >
      <div class="upload-container">
        <input
          ref="fileInputRef"
          type="file"
          accept=".zip"
          style="display: none"
          @change="handleFileChange"
        />
        <div class="upload-area" @click="triggerFileInput">
          <icon-upload style="font-size: 32px" />
          <div class="upload-text">
            <div>{{ text.selectZipFile }}</div>
            <div class="upload-tip">{{ text.uploadTip }}</div>
          </div>
        </div>
        <div v-if="selectedFile" class="selected-file">
          <icon-file />
          <span>{{ selectedFile.name }}</span>
          <a-button type="text" size="mini" @click="selectedFile = null">
            <icon-close />
          </a-button>
        </div>
      </div>
    </a-modal>

    <!-- 内容查看弹窗 -->
    <a-modal
      v-model:visible="showContentModal"
      :title="currentSkillContent?.name || text.skillContent"
      :width="700"
      :footer="false"
    >
      <div v-if="currentSkillContent" class="skill-content-view">
        <div class="content-description">{{ currentSkillContent.description }}</div>
        <a-divider />
        <pre class="content-body">{{ currentSkillContent.content }}</pre>
      </div>
    </a-modal>

    <!-- Git 导入弹窗 -->
    <a-modal
      v-model:visible="showGitImportModal"
      :title="text.importSkillFromGit"
      :width="500"
      @ok="handleGitImport"
      :ok-text="text.confirm"
      :cancel-text="text.cancel"
      :confirm-loading="importing"
    >
      <a-form :model="{ gitUrl, gitBranch }" layout="vertical">
        <a-form-item :label="text.gitRepoUrl" required>
          <a-input
            v-model="gitUrl"
            :placeholder="text.gitRepoUrlPlaceholder"
          />
          <template #extra>
            <span class="form-tip">{{ text.gitRepoTip }}</span>
          </template>
        </a-form-item>
        <a-form-item :label="text.branch">
          <a-input
            v-model="gitBranch"
            :placeholder="text.branchPlaceholder"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- Skill 商店弹窗 -->
    <SkillStoreModal
      v-model:visible="showStoreModal"
      :project-id="props.projectId"
      :installed-skills="skills"
      @skills-changed="fetchSkills"
    />

    <SkillApiKeyConfirmModal
      :visible="showApiKeyConfirm"
      :skill-names="pendingApiKeySkillNames"
      @confirmed="onApiKeyConfirmed"
      @update:visible="onApiKeyModalVisible"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { Message } from '@arco-design/web-vue'
import { SkillService } from '../services/skillService'
import SkillStoreModal from './SkillStoreModal.vue'
import SkillApiKeyConfirmModal from './SkillApiKeyConfirmModal.vue'
import type { SkillListItem } from '../types'
import { useAppI18n } from '@/composables/useAppI18n'
import { zipNameSuggestsInternalSkill } from '../utils/internalSkills'

const props = defineProps<{
  projectId: number
}>()
const { isEnglish } = useAppI18n()
const text = computed(() => (
  isEnglish.value
    ? {
        title: 'Skills Management',
        skillStore: 'Skill Hub',
        importFromGit: 'Import from Git',
        uploadSkill: 'Upload Skill',
        emptyState: 'No Skills yet. Click the button above to upload',
        deleteConfirm: 'Delete this Skill?',
        confirm: 'Confirm',
        cancel: 'Cancel',
        selectZipFile: 'Click to select a zip file',
        uploadTip: 'The zip can contain one or more Skills',
        skillContent: 'Skill Content',
        importSkillFromGit: 'Import Skill from Git',
        gitRepoUrl: 'Git repository URL',
        gitRepoUrlPlaceholder: 'https://github.com/username/repo',
        gitRepoTip: 'Any publicly accessible Git repository is supported',
        branch: 'Branch',
        branchPlaceholder: 'main (default)',
        fetchSkillsFailed: 'Failed to fetch Skills',
        selectFile: 'Select a file',
        uploadSuccess: (count: number, names: string) => `Uploaded ${count} Skill(s) successfully: ${names}`,
        uploadFailed: 'Upload failed',
        enabled: 'Enabled',
        disabled: 'Disabled',
        operationFailed: 'Operation failed',
        deleteSuccess: 'Deleted successfully',
        deleteFailed: 'Delete failed',
        fetchContentFailed: 'Failed to fetch content',
        gitRepoRequired: 'Enter a Git repository URL',
        importSuccess: (count: number, names: string) => `Imported ${count} Skill(s) successfully: ${names}`,
        importFailed: 'Import failed',
      }
    : {
        title: 'Skills 管理',
        skillStore: 'Skill 中心',
        importFromGit: '从 Git 导入',
        uploadSkill: '上传 Skill',
        emptyState: '暂无 Skills，点击上方按钮上传',
        deleteConfirm: '确定删除此 Skill 吗？',
        confirm: '确认',
        cancel: '取消',
        selectZipFile: '点击选择 zip 文件',
        uploadTip: '支持 zip 内包含一个或多个 Skill',
        skillContent: 'Skill 内容',
        importSkillFromGit: '从 Git 导入 Skill',
        gitRepoUrl: 'Git 仓库地址',
        gitRepoUrlPlaceholder: 'https://github.com/username/repo',
        gitRepoTip: '支持任何可公开访问的 Git 仓库',
        branch: '分支',
        branchPlaceholder: 'main（默认）',
        fetchSkillsFailed: '获取 Skills 失败',
        selectFile: '请选择文件',
        uploadSuccess: (count: number, names: string) => `成功上传 ${count} 个 Skill: ${names}`,
        uploadFailed: '上传失败',
        enabled: '已启用',
        disabled: '已禁用',
        operationFailed: '操作失败',
        deleteSuccess: '删除成功',
        deleteFailed: '删除失败',
        fetchContentFailed: '获取内容失败',
        gitRepoRequired: '请输入 Git 仓库地址',
        importSuccess: (count: number, names: string) => `成功导入 ${count} 个 Skill: ${names}`,
        importFailed: '导入失败',
      }
))

const loading = ref(false)
const uploading = ref(false)
const skills = ref<SkillListItem[]>([])
const showUploadModal = ref(false)
const showContentModal = ref(false)
const selectedFile = ref<File | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const currentSkillContent = ref<{ name: string; description: string; content: string } | null>(null)
const showGitImportModal = ref(false)
const showStoreModal = ref(false)
const gitUrl = ref('')
const gitBranch = ref('')
const importing = ref(false)
const showApiKeyConfirm = ref(false)
const pendingApiKeySkillNames = ref<string[]>([])
const pendingApiKeyAction = ref<'upload' | 'git' | null>(null)

const fetchSkills = async () => {
  loading.value = true
  try {
    skills.value = await SkillService.getSkills(props.projectId)
  } catch (e: any) {
    Message.error(e.message || text.value.fetchSkillsFailed)
  } finally {
    loading.value = false
  }
}

const triggerFileInput = () => {
  fileInputRef.value?.click()
}

const handleFileChange = (e: Event) => {
  const target = e.target as HTMLInputElement
  if (target.files && target.files[0]) {
    selectedFile.value = target.files[0]
  }
}

const doUpload = async (apiKey?: string) => {
  if (!selectedFile.value) {
    Message.warning(text.value.selectFile)
    return
  }

  uploading.value = true
  try {
    const skills = await SkillService.uploadSkill(props.projectId, selectedFile.value, apiKey)
    const count = skills.length
    const names = skills.map(s => s.name).join(', ')
    Message.success(text.value.uploadSuccess(count, names))
    showUploadModal.value = false
    selectedFile.value = null
    await fetchSkills()
  } catch (e: any) {
    Message.error(e.message || text.value.uploadFailed)
  } finally {
    uploading.value = false
  }
}

const handleUpload = async () => {
  if (!selectedFile.value) {
    Message.warning(text.value.selectFile)
    return
  }
  // 内部 Skill 包（文件名粗判）安装前必须确认 API Key；后端会按 SKILL.md name 再校验
  if (zipNameSuggestsInternalSkill(selectedFile.value.name)) {
    pendingApiKeyAction.value = 'upload'
    pendingApiKeySkillNames.value = [selectedFile.value.name]
    showApiKeyConfirm.value = true
    return
  }
  await doUpload()
}

const handleToggle = async (skill: SkillListItem, isActive: boolean) => {
  try {
    await SkillService.toggleSkill(props.projectId, skill.id, isActive)
    Message.success(isActive ? text.value.enabled : text.value.disabled)
  } catch (e: any) {
    skill.is_active = !isActive
    Message.error(e.message || text.value.operationFailed)
  }
}

const handleDelete = async (skill: SkillListItem) => {
  try {
    await SkillService.deleteSkill(props.projectId, skill.id)
    Message.success(text.value.deleteSuccess)
    await fetchSkills()
  } catch (e: any) {
    Message.error(e.message || text.value.deleteFailed)
  }
}

const handleViewContent = async (skill: SkillListItem) => {
  try {
    currentSkillContent.value = await SkillService.getSkillContent(props.projectId, skill.id)
    showContentModal.value = true
  } catch (e: any) {
    Message.error(e.message || text.value.fetchContentFailed)
  }
}

const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleDateString(isEnglish.value ? 'en-US' : 'zh-CN')
}

const doGitImport = async (apiKey?: string) => {
  if (!gitUrl.value.trim()) {
    Message.warning(text.value.gitRepoRequired)
    return
  }

  importing.value = true
  try {
    const skills = await SkillService.importFromGit(
      props.projectId,
      gitUrl.value.trim(),
      gitBranch.value.trim() || undefined,
      apiKey
    )
    const count = skills.length
    const names = skills.map(s => s.name).join(', ')
    Message.success(text.value.importSuccess(count, names))
    showGitImportModal.value = false
    gitUrl.value = ''
    gitBranch.value = ''
    await fetchSkills()
  } catch (e: any) {
    Message.error(e.message || text.value.importFailed)
  } finally {
    importing.value = false
  }
}

const handleGitImport = async () => {
  if (!gitUrl.value.trim()) {
    Message.warning(text.value.gitRepoRequired)
    return
  }
  // Git 导入可能包含内部 Skill：统一先确认 Key，后端对非内部包忽略该字段
  pendingApiKeyAction.value = 'git'
  pendingApiKeySkillNames.value = isEnglish.value
    ? ['Git import (may include internal Skills)']
    : ['Git 导入（可能含内部 Skill）']
  showApiKeyConfirm.value = true
}

const onApiKeyConfirmed = async (payload: { apiKey: string; keyId: number; keyName: string }) => {
  const action = pendingApiKeyAction.value
  // 先开始执行再清 pending，避免取消清理与确认竞态
  if (action === 'upload') {
    pendingApiKeyAction.value = null
    pendingApiKeySkillNames.value = []
    await doUpload(payload.apiKey)
  } else if (action === 'git') {
    pendingApiKeyAction.value = null
    pendingApiKeySkillNames.value = []
    await doGitImport(payload.apiKey)
  } else {
    pendingApiKeyAction.value = null
    pendingApiKeySkillNames.value = []
  }
}

const onApiKeyModalVisible = (v: boolean) => {
  showApiKeyConfirm.value = v
  // 仅在用户取消/关闭且当前没有进行中的上传/导入时清理挂起状态
  if (!v && !uploading.value && !importing.value) {
    pendingApiKeyAction.value = null
    pendingApiKeySkillNames.value = []
  }
}

onMounted(() => {
  fetchSkills()
})
</script>

<style scoped>
.skill-manager {
  padding: 16px;
  overflow-x: hidden;
}

.header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
}

.header-bar h3 {
  margin: 0;
  flex-shrink: 0;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60px 0;
  color: #909399;
}

.skill-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(300px, 100%), 1fr));
  gap: 16px;
}

.skill-card {
  background: var(--color-bg-2);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 16px;
  transition: all 0.2s;
  overflow: hidden;
  min-width: 0;
}

.skill-card:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.skill-card.inactive {
  opacity: 0.6;
}

.skill-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  gap: 8px;
}

.skill-name {
  font-weight: 600;
  font-size: 16px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.skill-description {
  color: var(--color-text-2);
  font-size: 13px;
  margin-bottom: 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.skill-footer {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 12px;
  font-size: 12px;
  color: var(--color-text-3);
}

.skill-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}

.skill-actions {
  margin-left: auto;
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.upload-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.upload-area {
  border: 2px dashed var(--color-border);
  border-radius: 8px;
  padding: 32px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
}

.upload-area:hover {
  border-color: var(--color-primary);
  background: var(--color-fill-1);
}

.upload-text {
  margin-top: 8px;
}

.upload-tip {
  color: var(--color-text-3);
  font-size: 12px;
  margin-top: 4px;
}

.selected-file {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--color-fill-2);
  border-radius: 4px;
}

.skill-content-view {
  max-height: 500px;
  overflow-y: auto;
}

.content-description {
  color: var(--color-text-2);
  font-size: 14px;
}

.content-body {
  background: var(--color-fill-2);
  padding: 16px;
  border-radius: 4px;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-word;
}
.form-tip {
  color: var(--color-text-3);
  font-size: 12px;
}
</style>
