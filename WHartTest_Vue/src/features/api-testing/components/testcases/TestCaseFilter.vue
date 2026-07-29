<script setup lang="ts">
import { ref, watch } from 'vue'
import { IconFire, IconFolder, IconRight, IconDown } from '@arco-design/web-vue/es/icon'
import { testcaseTagService } from '../../services/testcaseTagService'
import { testcaseGroupService } from '../../services/testcaseGroupService'
import { toArray } from '../../services/responseHelpers'
import type { ApiTestCaseTag, ApiTestCaseGroup } from '../../types/testcase'
import { Message } from '@arco-design/web-vue'
import { collapseTreeBranchIds } from '../../utils/treeExpansion'

interface FilterValue {
  priority?: string
  group?: number
  tags?: number[]
}

interface Props {
  modelValue: FilterValue
  projectId?: number
}

const props = defineProps<Props>()
const emit = defineEmits(['update:modelValue', 'search'])

const tagList = ref<ApiTestCaseTag[]>([])
const tagLoading = ref(false)
const groupList = ref<ApiTestCaseGroup[]>([])
const groupLoading = ref(false)
const expandedGroups = ref<number[]>([])

const toggleGroup = (groupId: number, event: Event) => {
  event.preventDefault()
  event.stopPropagation()
  const index = expandedGroups.value.indexOf(groupId)
  if (index === -1) {
    expandedGroups.value.push(groupId)
  } else {
    expandedGroups.value = collapseTreeBranchIds(groupList.value, expandedGroups.value, groupId)
  }
}

const loadTags = async () => {
  if (!props.projectId) {
    tagList.value = []
    return
  }

  try {
    tagLoading.value = true
    const res = await testcaseTagService.list(props.projectId)
    if (res.success && res.data) {
      tagList.value = toArray<ApiTestCaseTag>((res.data as any)?.results ?? res.data)
    }
  } catch (error) {
    console.error('Failed to load tags:', error)
    Message.error('加载标签列表失败')
    tagList.value = []
  } finally {
    tagLoading.value = false
  }
}

const loadGroupTree = async () => {
  if (!props.projectId) {
    groupList.value = []
    return
  }

  try {
    groupLoading.value = true
    const res = await testcaseGroupService.tree(props.projectId)
    if (res.success && res.data) {
      const groups = toArray<ApiTestCaseGroup>((res.data as any)?.results ?? res.data)
      const sortGroups = (items: ApiTestCaseGroup[]): ApiTestCaseGroup[] => {
        items.sort((a, b) => {
          const timeA = new Date(a.created_at).getTime()
          const timeB = new Date(b.created_at).getTime()
          return timeA - timeB
        })
        items.forEach(group => {
          if (group.children?.length) {
            sortGroups(group.children)
          }
        })
        return items
      }
      groupList.value = sortGroups(groups)
    }
  } catch (error) {
    console.error('Failed to load group tree:', error)
    Message.error('加载分组列表失败')
    groupList.value = []
  } finally {
    groupLoading.value = false
  }
}

watch(() => props.projectId, (newVal: number | undefined) => {
  if (newVal) {
    loadTags()
    loadGroupTree()
  } else {
    tagList.value = []
    groupList.value = []
  }
}, { immediate: true })

const updateValue = (key: keyof FilterValue, value: any) => {
  if (value === null) {
    value = undefined
  }
  if (key === 'tags' && value) {
    value = value.map((v: any) => Number(v))
  }
  emit('update:modelValue', { ...props.modelValue, [key]: value })
  emit('search')
}

const priorityColors = {
  'P0': 'red',
  'P1': 'orange',
  'P2': 'blue',
  'P3': 'green'
} as const
</script>

<template>
  <div class="flex items-center gap-4">
    <a-select
      :model-value="modelValue.priority"
      @update:model-value="val => updateValue('priority', val)"
      placeholder="优先级"
      class="flex-1"
      allow-clear
    >
      <template #value="{ value }">
        <div v-if="value" class="flex items-center gap-2 justify-center max-w-[160px]">
          <icon-fire :style="{ color: priorityColors[value as keyof typeof priorityColors] }" />
          <span class="truncate">{{ value }}</span>
        </div>
      </template>
      <a-option value="P0">
        <div class="priority-option">
          <icon-fire :style="{ color: priorityColors['P0'] }" />
          <span>P0</span>
        </div>
      </a-option>
      <a-option value="P1">
        <div class="priority-option">
          <icon-fire :style="{ color: priorityColors['P1'] }" />
          <span>P1</span>
        </div>
      </a-option>
      <a-option value="P2">
        <div class="priority-option">
          <icon-fire :style="{ color: priorityColors['P2'] }" />
          <span>P2</span>
        </div>
      </a-option>
      <a-option value="P3">
        <div class="priority-option">
          <icon-fire :style="{ color: priorityColors['P3'] }" />
          <span>P3</span>
        </div>
      </a-option>
    </a-select>
    <a-select
      :model-value="modelValue.group"
      @update:model-value="val => updateValue('group', val)"
      placeholder="选择分组"
      class="flex-1"
      allow-clear
      :loading="groupLoading"
      :fallback-option="false"
    >
      <template #prefix>
        <icon-folder />
      </template>
      <template #empty>
        <div v-if="groupLoading" class="flex items-center justify-center py-2">
          <a-spin />
        </div>
        <div v-else class="filter-empty-state text-center py-2">
          暂无分组
        </div>
      </template>
      <template v-for="group in groupList" :key="group.id">
        <a-option :value="group.id" :label="group.name">
          <div class="flex items-center gap-2">
            <div
              v-if="group.children?.length"
              class="w-4 h-4 flex items-center justify-center cursor-pointer"
              @click="toggleGroup(group.id, $event)"
            >
              <icon-right v-if="!expandedGroups.includes(group.id)" class="!w-3 !h-3 !text-[#6b7785]" />
              <icon-down v-else class="!w-3 !h-3 !text-[#6b7785]" />
            </div>
            <span v-else class="w-4"></span>
            <icon-folder class="text-blue-500 flex-shrink-0" />
            <span class="truncate">{{ group.name }}</span>
          </div>
        </a-option>
        <template v-if="group.children?.length && expandedGroups.includes(group.id)">
          <template v-for="child in group.children" :key="child.id">
            <a-option
              :value="child.id"
              :label="child.name"
            >
              <div class="flex items-center gap-2 pl-4">
                <div
                  v-if="child.children?.length"
                  class="w-4 h-4 flex items-center justify-center cursor-pointer"
                  @click="toggleGroup(child.id, $event)"
                >
                  <icon-right v-if="!expandedGroups.includes(child.id)" class="!w-3 !h-3 !text-[#6b7785]" />
                  <icon-down v-else class="!w-3 !h-3 !text-[#6b7785]" />
                </div>
                <span v-else class="w-4"></span>
                <icon-folder class="text-blue-400 flex-shrink-0" />
                <span class="truncate">{{ child.name }}</span>
              </div>
            </a-option>
            <template v-if="child.children?.length && expandedGroups.includes(child.id)">
              <a-option
                v-for="grandChild in child.children"
                :key="grandChild.id"
                :value="grandChild.id"
                :label="grandChild.name"
              >
                <div class="flex items-center gap-2 pl-8">
                  <span class="w-4"></span>
                  <icon-folder class="text-blue-300 flex-shrink-0" />
                  <span class="truncate">{{ grandChild.name }}</span>
                </div>
              </a-option>
            </template>
          </template>
        </template>
      </template>
    </a-select>
    <a-select
      :model-value="modelValue.tags"
      @update:model-value="val => updateValue('tags', val)"
      placeholder="选择标签"
      class="flex-1"
      allow-clear
      multiple
      :loading="tagLoading"
      :max-tag-width="30"
      :max-tag-count="3"
    >
      <template #empty>
        <div v-if="tagLoading" class="flex items-center justify-center py-2">
          <a-spin />
        </div>
        <div v-else class="filter-empty-state text-center py-2">
          暂无标签
        </div>
      </template>
      <a-option
        v-for="tag in tagList"
        :key="tag.id"
        :value="tag.id"
        :label="tag.name"
      >
        <div class="flex items-center gap-2 max-w-[160px]">
          <div
            class="w-2 h-2 rounded-full flex-shrink-0"
            :style="{ backgroundColor: tag.color }"
          />
          <span class="truncate flex-1 min-w-0">{{ tag.name }}</span>
        </div>
      </a-option>
    </a-select>
  </div>
</template>

<style scoped>
:deep(.arco-select-view) {
  background-color: var(--tc-input-bg) !important;
  border-color: var(--tc-input-border) !important;
  color: var(--tc-text) !important;
  height: 32px !important;
  padding: 0 8px !important;
  display: flex !important;
  align-items: center !important;

  &:hover {
    border-color: rgba(var(--theme-accent-rgb), 0.42) !important;
    background-color: var(--tc-input-bg-hover) !important;
  }
}

:deep(.arco-select-view-value),
:deep(.arco-select-view-single),
:deep(.arco-select-view-multiple),
:deep(.arco-select-view-placeholder),
:deep(.arco-select-view-suffix),
:deep(.arco-select-view-prefix) {
  color: var(--tc-text) !important;
}

:deep(.arco-select-view-placeholder),
:deep(.arco-select-view-suffix),
:deep(.arco-select-view-prefix) {
  color: var(--tc-text-subtle) !important;
}

:deep(.arco-select-view-inner) {
  height: 100% !important;
  display: flex !important;
  align-items: center !important;
  gap: 4px !important;
}

:deep(.arco-select-view-value) {
  display: flex !important;
  align-items: center !important;
  gap: 4px !important;
  height: 100% !important;
  min-width: 0 !important;
}

:deep(.arco-tag) {
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  max-width: 60px !important;
  height: 22px !important;
  margin: 0 !important;
  padding: 0 4px !important;
  background: rgba(var(--theme-accent-rgb), 0.08) !important;
  border: 1px solid rgba(var(--theme-accent-rgb), 0.18) !important;
  border-radius: 2px !important;

  .arco-tag-content {
    flex: 1 !important;
    min-width: 0 !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
    font-size: 12px !important;
    line-height: 20px !important;
    text-align: center !important;
  }

  .arco-icon-hover {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
  }

  .arco-tag-close-btn {
    flex-shrink: 0 !important;
    margin-left: 4px !important;
    width: 12px !important;
    height: 12px !important;
    font-size: 12px !important;
    line-height: 12px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
  }
}

:global(body.api-testing-theme .arco-select-dropdown),
:global(body.api-testing-theme .arco-select-dropdown .arco-select-dropdown-list) {
  background-color: rgb(31, 41, 55) !important;
  border: 1px solid rgba(148, 163, 184, 0.1) !important;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1) !important;
  max-height: none !important;
  height: auto !important;
  overflow: visible !important;
  box-sizing: border-box !important;
  padding: 4px 0 !important;
}

:global(body.api-testing-theme .arco-select-dropdown-list) {
  padding: 4px !important;
  max-height: none !important;
  height: auto !important;
  overflow: visible !important;
}

:global(body.api-testing-theme .arco-select-option) {
  color: #e2e8f0 !important;
  text-align: left !important;
  padding: 8px 12px !important;
  display: flex !important;
  justify-content: flex-start !important;
  min-width: 120px !important;
  max-width: 200px !important;

  .arco-select-option-content {
    display: flex !important;
    align-items: center !important;
    gap: 8px !important;
    width: 100% !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
  }

  &:hover {
    background-color: rgba(59, 130, 246, 0.1) !important;
  }

  &.arco-select-option-active {
    background-color: rgba(59, 130, 246, 0.2) !important;
    color: #60a5fa !important;
  }
}

:global(body.api-testing-theme .arco-select-popup-inner) {
  display: flex !important;
  justify-content: flex-start !important;
}

.priority-option {
  display: flex !important;
  align-items: center !important;
  gap: 8px !important;
  margin-left: 12px !important;
}

.filter-empty-state {
  color: var(--tc-text-subtle);
}
</style>
