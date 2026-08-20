<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconTag, IconPlus, IconEdit, IconDelete } from '@arco-design/web-vue/es/icon'
import { testcaseTagService } from '../../services/testcaseTagService'
import { toArray } from '../../services/responseHelpers'
import type { ApiTestCaseTag } from '../../types/testcase'

interface Props {
  modelValue: number[]
  readonly?: boolean
  projectId: number
}

const props = defineProps<Props>()
const emit = defineEmits(['update:modelValue'])

const tagLoading = ref(false)
const tagList = ref<ApiTestCaseTag[]>([])
const tagStats = ref<any[]>([])
const tagSearchValue = ref('')
const createTagVisible = ref(false)
const createTagLoading = ref(false)
const isEditMode = ref(false)
const editingTagId = ref<number | null>(null)

const newTag = reactive({
  name: '',
  color: '#1890ff'
})

const resetTagForm = () => {
  newTag.name = ''
  newTag.color = '#1890ff'
  isEditMode.value = false
  editingTagId.value = null
}

const handleCreateTag = () => {
  resetTagForm()
  createTagVisible.value = true
}

const handleEditTag = (tag: ApiTestCaseTag, event: Event) => {
  event.stopPropagation()
  isEditMode.value = true
  editingTagId.value = tag.id
  newTag.name = tag.name
  newTag.color = tag.color
  createTagVisible.value = true
}

const handleDeleteTag = async (tagId: number, event: Event) => {
  event.stopPropagation()
  try {
    await testcaseTagService.delete(props.projectId, tagId)
    Message.success('删除成功')
    loadTags()
    loadTagStats()
  } catch (error) {
    console.error('Failed to delete tag:', error)
    Message.error('删除标签失败')
  }
}

const handleCreateTagConfirm = async () => {
  if (!newTag.name.trim()) {
    Message.error('请输入标签名称')
    return false
  }

  try {
    createTagLoading.value = true
    if (isEditMode.value && editingTagId.value) {
      await testcaseTagService.update(props.projectId, editingTagId.value, {
        name: newTag.name.trim(),
        color: newTag.color,
        project: props.projectId
      })
      Message.success('更新成功')
    } else {
      await testcaseTagService.create(props.projectId, {
        name: newTag.name.trim(),
        color: newTag.color,
        project: props.projectId
      })
      Message.success('创建成功')
    }
    createTagVisible.value = false
    resetTagForm()
    loadTags()
    loadTagStats()
    return true
  } catch (error) {
    console.error('Failed to handle tag:', error)
    Message.error(isEditMode.value ? '更新标签失败' : '创建标签失败')
    return false
  } finally {
    createTagLoading.value = false
  }
}

const loadTags = async (search?: string) => {
  try {
    tagLoading.value = true
    const params: Record<string, any> = { ordering: 'name' }
    if (search) params.search = search
    const res = await testcaseTagService.list(props.projectId, params)
    if (res.success && res.data) {
      tagList.value = toArray<ApiTestCaseTag>((res.data as any)?.results ?? res.data)
    }
  } catch (error) {
    console.error('Failed to load tags:', error)
    Message.error('加载标签列表失败')
  } finally {
    tagLoading.value = false
  }
}

const loadTagStats = async () => {
  try {
    const res = await testcaseTagService.statistics(props.projectId)
    if (res.success && res.data) {
      tagStats.value = toArray((res.data as any)?.results ?? res.data)
    }
  } catch (error) {
    console.error('Failed to load tag statistics:', error)
  }
}

const handleTagSearch = (value: string) => {
  tagSearchValue.value = value
  loadTags(value)
}

onMounted(() => {
  loadTags()
  loadTagStats()
})
</script>

<template>
  <div class="flex items-center">
    <a-select
      :model-value="modelValue"
      @update:model-value="val => emit('update:modelValue', val)"
      placeholder="选择标签"
      class="tag-manager-select"
      :disabled="readonly"
      :loading="tagLoading"
      multiple
      allow-search
      allow-clear
      @search="handleTagSearch"
      :popup-max-height="false"
    >
      <template #prefix>
        <icon-tag />
      </template>
      <template #empty>
        <div class="flex flex-col min-h-[80px]">
          <div class="flex items-center justify-center py-2">
            <div v-if="tagLoading">
              <a-spin />
            </div>
            <div v-else class="empty-text">
              {{ tagSearchValue ? '未找到相关标签' : '暂无标签' }}
            </div>
          </div>
          <div class="footer-bar">
            <a-button type="primary" size="mini" @click="handleCreateTag" :disabled="readonly">
              <template #icon>
                <icon-plus />
              </template>
              新建标签
            </a-button>
          </div>
        </div>
      </template>
      <a-option
        v-for="tag in tagList"
        :key="tag.id"
        :value="tag.id"
        :label="tag.name"
        class="!bg-transparent hover:!bg-[var(--color-fill-2)]"
      >
        <div class="grid grid-cols-[1fr_48px] items-center w-full">
          <div class="flex items-center min-w-0">
            <div
              class="w-3 h-3 rounded-full flex-shrink-0 mr-2"
              :style="{ backgroundColor: tag.color }"
            />
            <span class="truncate">{{ tag.name }}</span>
            <span v-if="tagStats.find((s: any) => s.id === tag.id)" class="stat-count">
              ({{ tagStats.find((s: any) => s.id === tag.id)?.usage_count || 0 }})
            </span>
          </div>
          <div class="flex items-center justify-end ml-2">
            <icon-edit
              class="action-icon mr-2"
              @click="handleEditTag(tag, $event)"
            />
            <icon-delete
              class="action-icon-danger"
              @click="handleDeleteTag(tag.id, $event)"
            />
          </div>
        </div>
      </a-option>
      <template #footer>
        <div class="footer-bar">
          <a-button type="primary" size="mini" @click="handleCreateTag" :disabled="readonly">
            <template #icon>
              <icon-plus />
            </template>
            新建标签
          </a-button>
        </div>
      </template>
    </a-select>

    <a-modal
      v-model:visible="createTagVisible"
      :title="isEditMode ? '编辑标签' : '创建标签'"
      @cancel="() => { createTagVisible = false; resetTagForm() }"
      @before-ok="handleCreateTagConfirm"
      :ok-loading="createTagLoading"
    >
      <div class="space-y-4">
        <div class="flex items-center gap-4">
          <span class="w-20 text-right">标签名称：</span>
          <a-input
            v-model="newTag.name"
            placeholder="请输入标签名称"
            class="!flex-1"
            allow-clear
          />
        </div>
        <div class="flex items-center gap-4">
          <span class="w-20 text-right">标签颜色：</span>
          <a-color-picker
            v-model="newTag.color"
            :default-value="newTag.color"
            class="!flex-1"
          />
        </div>
      </div>
    </a-modal>
  </div>
</template>

<style scoped>
.empty-text {
  color: var(--color-text-3);
}
.tag-manager-select {
  width: var(--testcase-tag-select-width, 240px);
}
.stat-count {
  color: var(--color-text-3);
  font-size: 12px;
  flex-shrink: 0;
  margin-left: 4px;
}
.action-icon {
  font-size: 12px;
  color: var(--color-text-3);
  cursor: pointer;
}
.action-icon:hover {
  color: var(--color-text-1);
}
.action-icon-danger {
  font-size: 12px;
  color: var(--color-text-3);
  cursor: pointer;
}
.action-icon-danger:hover {
  color: rgb(var(--red-6));
}
.footer-bar {
  position: sticky;
  bottom: 0;
  background: var(--color-bg-popup);
  border-top: 1px solid var(--color-border-2);
  padding: 8px 12px;
  display: flex;
  justify-content: center;
}
</style>
