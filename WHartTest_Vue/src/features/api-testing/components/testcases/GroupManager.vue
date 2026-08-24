<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { IconFolder, IconPlus, IconEdit, IconDelete, IconRight, IconDown } from '@arco-design/web-vue/es/icon'
import { testcaseGroupService } from '../../services/testcaseGroupService'
import { toArray } from '../../services/responseHelpers'
import type { ApiTestCaseGroup } from '../../types/testcase'
import { collapseTreeBranchIds } from '../../utils/treeExpansion'

interface Props {
  modelValue: number | null
  readonly?: boolean
  projectId: number
}

const props = defineProps<Props>()
const emit = defineEmits(['update:modelValue'])

const groupList = ref<ApiTestCaseGroup[]>([])
const groupLoading = ref(false)
const createGroupVisible = ref(false)
const createGroupLoading = ref(false)
const isEditGroupMode = ref(false)
const editingGroupId = ref<number | null>(null)
const expandedGroups = ref<number[]>([])

const newGroup = reactive({
  name: '',
  parent: null as number | null,
  project: props.projectId
})

const loadGroupTree = async () => {
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

const handleCreateGroup = () => {
  newGroup.name = ''
  newGroup.parent = null
  newGroup.project = props.projectId
  createGroupVisible.value = true
}

const handleEditGroup = (group: ApiTestCaseGroup, event: Event) => {
  event.stopPropagation()
  isEditGroupMode.value = true
  editingGroupId.value = group.id
  newGroup.name = group.name
  newGroup.parent = group.parent
  newGroup.project = props.projectId
  createGroupVisible.value = true
}

const handleDeleteGroup = async (groupId: number, event: Event) => {
  event.stopPropagation()
  try {
    await testcaseGroupService.delete(props.projectId, groupId)
    Message.success('删除成功')
    loadGroupTree()
  } catch (error) {
    console.error('Failed to delete group:', error)
    Message.error('删除分组失败')
  }
}

const handleCreateGroupConfirm = async () => {
  if (!newGroup.name.trim()) {
    Message.error('请输入分组名称')
    return false
  }

  try {
    createGroupLoading.value = true
    if (isEditGroupMode.value && editingGroupId.value) {
      await testcaseGroupService.update(props.projectId, editingGroupId.value, {
        name: newGroup.name.trim(),
        parent: newGroup.parent,
        project: props.projectId
      })
      Message.success('更新成功')
    } else {
      await testcaseGroupService.create(props.projectId, {
        name: newGroup.name.trim(),
        parent: newGroup.parent,
        project: props.projectId
      })
      Message.success('创建成功')
    }
    createGroupVisible.value = false
    resetGroupForm()
    loadGroupTree()
    return true
  } catch (error) {
    console.error('Failed to handle group:', error)
    Message.error(isEditGroupMode.value ? '更新分组失败' : '创建分组失败')
    return false
  } finally {
    createGroupLoading.value = false
  }
}

const resetGroupForm = () => {
  newGroup.name = ''
  newGroup.parent = null
  newGroup.project = props.projectId
  isEditGroupMode.value = false
  editingGroupId.value = null
}

onMounted(() => {
  loadGroupTree()
})
</script>

<template>
  <div class="flex items-center">
    <a-select
      :model-value="modelValue"
      @update:model-value="val => emit('update:modelValue', val)"
      placeholder="选择分组"
      class="group-manager-select"
      :disabled="readonly"
      :loading="groupLoading"
      :fallback-option="false"
      allow-clear
    >
      <template #prefix>
        <icon-folder />
      </template>
      <template #empty>
        <div class="flex flex-col min-h-[80px]">
          <div class="flex items-center justify-center py-2">
            <div v-if="groupLoading">
              <a-spin />
            </div>
            <div v-else class="empty-text">
              暂无分组
            </div>
          </div>
          <div class="footer-bar">
            <a-button type="primary" size="mini" @click="handleCreateGroup" :disabled="readonly">
              <template #icon>
                <icon-plus />
              </template>
              新建分组
            </a-button>
          </div>
        </div>
      </template>
      <template v-for="group in groupList" :key="group.id">
        <a-option :value="group.id" :label="group.name">
          <div class="grid grid-cols-[1fr_48px] items-center w-full">
            <div class="flex items-center gap-2 min-w-0">
              <div
                v-if="group.children?.length"
                class="w-4 h-4 flex items-center justify-center cursor-pointer"
                @click="toggleGroup(group.id, $event)"
              >
                <icon-right v-if="!expandedGroups.includes(group.id)" class="!w-3 !h-3 expand-icon" />
                <icon-down v-else class="!w-3 !h-3 expand-icon" />
              </div>
              <span v-else class="w-4"></span>
              <icon-folder class="folder-icon flex-shrink-0" />
              <span class="truncate">{{ group.name }}</span>
            </div>
            <div class="flex items-center justify-end ml-2">
              <icon-edit
                class="action-icon mr-2"
                @click="handleEditGroup(group, $event)"
              />
              <icon-delete
                class="action-icon-danger"
                @click="handleDeleteGroup(group.id, $event)"
              />
            </div>
          </div>
        </a-option>
        <template v-if="group.children?.length && expandedGroups.includes(group.id)">
          <template v-for="child in group.children" :key="child.id">
            <a-option
              :value="child.id"
              :label="child.name"
            >
              <div class="grid grid-cols-[1fr_48px] items-center w-full">
                <div class="flex items-center gap-2 pl-4 min-w-0">
                  <div
                    v-if="child.children?.length"
                    class="w-4 h-4 flex items-center justify-center cursor-pointer"
                    @click="toggleGroup(child.id, $event)"
                  >
                    <icon-right v-if="!expandedGroups.includes(child.id)" class="!w-3 !h-3 expand-icon" />
                    <icon-down v-else class="!w-3 !h-3 expand-icon" />
                  </div>
                  <span v-else class="w-4"></span>
                  <icon-folder class="folder-icon flex-shrink-0" />
                  <span class="truncate">{{ child.name }}</span>
                </div>
                <div class="flex items-center justify-end ml-2">
                  <icon-edit
                    class="action-icon mr-2"
                    @click="handleEditGroup(child, $event)"
                  />
                  <icon-delete
                    class="action-icon-danger"
                    @click="handleDeleteGroup(child.id, $event)"
                  />
                </div>
              </div>
            </a-option>
            <template v-if="child.children?.length && expandedGroups.includes(child.id)">
              <a-option
                v-for="grandChild in child.children"
                :key="grandChild.id"
                :value="grandChild.id"
                :label="grandChild.name"
              >
                <div class="grid grid-cols-[1fr_48px] items-center w-full">
                  <div class="flex items-center gap-2 pl-8 min-w-0">
                    <span class="w-4"></span>
                    <icon-folder class="folder-icon flex-shrink-0" />
                    <span class="truncate">{{ grandChild.name }}</span>
                  </div>
                  <div class="flex items-center justify-end ml-2">
                    <icon-edit
                      class="action-icon mr-2"
                      @click="handleEditGroup(grandChild, $event)"
                    />
                    <icon-delete
                      class="action-icon-danger"
                      @click="handleDeleteGroup(grandChild.id, $event)"
                    />
                  </div>
                </div>
              </a-option>
            </template>
          </template>
        </template>
      </template>
      <template #footer>
        <div class="footer-bar">
          <a-button type="primary" size="mini" @click="handleCreateGroup" :disabled="readonly">
            <template #icon>
              <icon-plus />
            </template>
            新建分组
          </a-button>
        </div>
      </template>
    </a-select>

    <a-modal
      v-model:visible="createGroupVisible"
      :title="isEditGroupMode ? '编辑分组' : '创建分组'"
      @cancel="() => { createGroupVisible = false; resetGroupForm() }"
      @before-ok="handleCreateGroupConfirm"
      :ok-loading="createGroupLoading"
    >
      <div class="space-y-4">
        <div class="flex items-center gap-4">
          <span class="w-20 text-right">分组名称：</span>
          <a-input
            v-model="newGroup.name"
            placeholder="请输入分组名称"
            class="!flex-1"
            allow-clear
          />
        </div>
        <div class="flex items-center gap-4">
          <span class="w-20 text-right">父分组：</span>
          <a-select
            v-model="newGroup.parent"
            placeholder="请选择父分组"
            class="!flex-1"
            allow-clear
            :loading="groupLoading"
            :fallback-option="false"
          >
            <template #empty>
              <div v-if="groupLoading" class="flex items-center justify-center py-2">
                <a-spin />
              </div>
              <div v-else class="empty-text text-center py-2">
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
                    <icon-right v-if="!expandedGroups.includes(group.id)" class="!w-3 !h-3 expand-icon" />
                    <icon-down v-else class="!w-3 !h-3 expand-icon" />
                  </div>
                  <span v-else class="w-4"></span>
                  <icon-folder class="folder-icon flex-shrink-0" />
                  <span class="truncate">{{ group.name }}</span>
                </div>
              </a-option>
              <template v-if="group.children?.length && expandedGroups.includes(group.id)">
                <template v-for="child in group.children" :key="'child-' + child.id">
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
                        <icon-right v-if="!expandedGroups.includes(child.id)" class="!w-3 !h-3 expand-icon" />
                        <icon-down v-else class="!w-3 !h-3 expand-icon" />
                      </div>
                      <span v-else class="w-4"></span>
                      <icon-folder class="folder-icon flex-shrink-0" />
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
                        <icon-folder class="folder-icon flex-shrink-0" />
                        <span class="truncate">{{ grandChild.name }}</span>
                      </div>
                    </a-option>
                  </template>
                </template>
              </template>
            </template>
          </a-select>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<style scoped>
.empty-text {
  color: var(--color-text-3);
}
.group-manager-select {
  width: var(--testcase-group-select-width, 240px);
}
.expand-icon {
  color: var(--color-text-3) !important;
}
.folder-icon {
  color: rgb(var(--primary-6));
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
