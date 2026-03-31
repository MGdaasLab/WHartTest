<template>
  <div class="skill-manager">
    <!-- 头部操作栏 -->
    <div class="header-bar">
      <h3>Skills 管理</h3>
      <a-space>
        <a-button @click="showGitImportModal = true">
          <template #icon><icon-github /></template>
          从 Git 导入
        </a-button>
        <a-button type="primary" @click="showUploadModal = true">
          <template #icon><icon-upload /></template>
          上传 Skill
        </a-button>
      </a-space>
    </div>

    <!-- Skills 列表 -->
    <a-spin :loading="loading">
      <div v-if="skills.length === 0" class="empty-state">
        <icon-apps style="font-size: 48px; color: #c0c4cc" />
        <p>暂无 Skills，点击上方按钮上传</p>
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
                content="确定删除此 Skill 吗？"
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
      title="上传 Skill"
      :width="500"
      @ok="handleUpload"
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
            <div>点击选择 zip 文件</div>
            <div class="upload-tip">支持 zip 内包含一个或多个 Skill</div>
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
      :title="currentSkillContent?.name || 'Skill 内容'"
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
      title="从 Git 导入 Skill"
      :width="500"
      @ok="handleGitImport"
      :confirm-loading="importing"
    >
      <a-form :model="{ gitUrl, gitBranch }" layout="vertical">
        <a-form-item label="Git 仓库地址" required>
          <a-input
            v-model="gitUrl"
            placeholder="https://github.com/username/repo"
          />
          <template #extra>
            <span class="form-tip">支持任何可公开访问的 Git 仓库</span>
          </template>
        </a-form-item>
        <a-form-item label="分支">
          <a-input
            v-model="gitBranch"
            placeholder="main（默认）"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { SkillService } from '../services/skillService'
import type { SkillListItem } from '../types'

const props = defineProps<{
  projectId: number
}>()

const loading = ref(false)
const uploading = ref(false)
const skills = ref<SkillListItem[]>([])
const showUploadModal = ref(false)
const showContentModal = ref(false)
const selectedFile = ref<File | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const currentSkillContent = ref<{ name: string; description: string; content: string } | null>(null)
const showGitImportModal = ref(false)
const gitUrl = ref('')
const gitBranch = ref('')
const importing = ref(false)

const fetchSkills = async () => {
  loading.value = true
  try {
    skills.value = await SkillService.getSkills(props.projectId)
  } catch (e: any) {
    Message.error(e.message || '获取 Skills 失败')
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

const handleUpload = async () => {
  if (!selectedFile.value) {
    Message.warning('请选择文件')
    return
  }

  uploading.value = true
  try {
    const skills = await SkillService.uploadSkill(props.projectId, selectedFile.value)
    const count = skills.length
    const names = skills.map(s => s.name).join(', ')
    Message.success(`成功上传 ${count} 个 Skill: ${names}`)
    showUploadModal.value = false
    selectedFile.value = null
    await fetchSkills()
  } catch (e: any) {
    Message.error(e.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

const handleToggle = async (skill: SkillListItem, isActive: boolean) => {
  try {
    await SkillService.toggleSkill(props.projectId, skill.id, isActive)
    Message.success(isActive ? '已启用' : '已禁用')
  } catch (e: any) {
    skill.is_active = !isActive
    Message.error(e.message || '操作失败')
  }
}

const handleDelete = async (skill: SkillListItem) => {
  try {
    await SkillService.deleteSkill(props.projectId, skill.id)
    Message.success('删除成功')
    await fetchSkills()
  } catch (e: any) {
    Message.error(e.message || '删除失败')
  }
}

const handleViewContent = async (skill: SkillListItem) => {
  try {
    currentSkillContent.value = await SkillService.getSkillContent(props.projectId, skill.id)
    showContentModal.value = true
  } catch (e: any) {
    Message.error(e.message || '获取内容失败')
  }
}

const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

const handleGitImport = async () => {
  if (!gitUrl.value.trim()) {
    Message.warning('请输入 Git 仓库地址')
    return
  }

  importing.value = true
  try {
    const skills = await SkillService.importFromGit(
      props.projectId,
      gitUrl.value.trim(),
      gitBranch.value.trim() || undefined
    )
    const count = skills.length
    const names = skills.map(s => s.name).join(', ')
    Message.success(`成功导入 ${count} 个 Skill: ${names}`)
    showGitImportModal.value = false
    gitUrl.value = ''
    gitBranch.value = ''
    await fetchSkills()
  } catch (e: any) {
    Message.error(e.message || '导入失败')
  } finally {
    importing.value = false
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
