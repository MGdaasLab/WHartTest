<template>
  <div class="module-tree">
    <div class="tree-header">
      <span class="tree-title">模块管理</span>
      <a-button type="text" size="small" @click="showAddModal(null)">
        <template #icon><icon-plus /></template>
      </a-button>
    </div>

    <a-spin :loading="loading" class="tree-content">
      <a-tree
        v-if="mappedTreeData.length"
        :data="mappedTreeData"
        :selected-keys="selectedKeys"
        show-line
        block-node
        :draggable="true"
        @drop="onDrop"
        @select="onSelect"
      >
        <template #title="node">
          <div class="tree-node">
            <span class="node-title">{{ node.name }}</span>
            <a-dropdown trigger="hover" :popup-max-height="false">
              <a-button type="text" size="mini" class="node-action" @click.stop>
                <template #icon><icon-more /></template>
              </a-button>
              <template #content>
                <a-doption @click="showAddModal(node)">
                  <template #icon><icon-plus /></template>
                  添加子模块
                </a-doption>
                <a-doption @click="editModule(node)">
                  <template #icon><icon-edit /></template>
                  编辑
                </a-doption>
                <a-doption class="danger-option" @click="deleteModule(node)">
                  <template #icon><icon-delete /></template>
                  删除
                </a-doption>
              </template>
            </a-dropdown>
          </div>
        </template>
      </a-tree>
      <a-empty v-else description="暂无模块" />
    </a-spin>

    <!-- 新增/编辑弹窗 -->
    <a-modal
      v-model:visible="modalVisible"
      :title="isEdit ? '编辑模块' : '新增模块'"
      :ok-loading="submitting"
      @before-ok="handleSubmit"
      @cancel="handleCancel"
    >
      <a-form ref="formRef" :model="formData" :rules="rules" layout="vertical">
        <a-form-item v-if="parentModule" label="父模块">
          <a-input :model-value="parentModule.name" disabled />
        </a-form-item>
        <a-form-item field="name" label="模块名称" required>
          <a-input v-model="formData.name" placeholder="请输入模块名称" :max-length="100" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import type { TreeNodeData } from '@arco-design/web-vue'
import { IconPlus, IconEdit, IconDelete, IconMore } from '@arco-design/web-vue/es/icon'
import { moduleApi } from '../api'
import type { UiModule, UiModuleForm } from '../types'
import { useProjectStore } from '@/store/projectStore'

const emit = defineEmits<{
  (e: 'select', module: UiModule | null): void
}>()

const projectStore = useProjectStore()
const projectId = computed(() => projectStore.currentProject?.id)

const loading = ref(false)
const submitting = ref(false)
const treeData = ref<UiModule[]>([])
const mapTreeData = (modules: UiModule[]): any[] => {
  return modules.map(module => ({
    ...module,
    key: module.id,
    title: module.name,
    children: module.children ? mapTreeData(module.children) : []
  }))
}
const mappedTreeData = computed(() => {
  return mapTreeData(treeData.value)
})
const selectedKeys = ref<number[]>([])
const modalVisible = ref(false)
const isEdit = ref(false)
const parentModule = ref<UiModule | null>(null)
const currentModule = ref<UiModule | null>(null)
const formRef = ref()

const formData = reactive<UiModuleForm>({
  project: 0,
  name: '',
  parent: null,
})

const rules = {
  name: [{ required: true, message: '请输入模块名称' }],
}

const fetchModules = async () => {
  if (!projectId.value) return
  loading.value = true
  try {
    const res = await moduleApi.tree(projectId.value)
    treeData.value = res.data
  } catch {
    Message.error('获取模块树失败')
  } finally {
    loading.value = false
  }
}

const onSelect = (keys: (string | number)[], data: { node?: UiModule }) => {
  selectedKeys.value = keys as number[]
  emit('select', data.node || null)
}

const onDrop = async (info: {
  e: DragEvent
  dragNode: TreeNodeData
  dropNode: TreeNodeData
  dropPosition: number
}) => {
  const { dragNode, dropNode, dropPosition } = info
  if (!dragNode || !dropNode) return

  if (dragNode.id === dropNode.id) return

  // 检查移动后的深度是否超过5级限制
  let newLevel = dropNode.level as number
  if (dropPosition === 0) {
    newLevel = (dropNode.level as number) + 1
  }

  const getSubtreeDepth = (node: TreeNodeData): number => {
    if (!node.children || node.children.length === 0) return 1
    return 1 + Math.max(...(node.children as TreeNodeData[]).map(child => getSubtreeDepth(child)))
  }

  const subtreeDepth = getSubtreeDepth(dragNode)
  if (newLevel + subtreeDepth - 1 > 5) {
    Message.error('移动后模块层级将超过5级限制')
    return
  }

  loading.value = true
  try {
    await moduleApi.move(dragNode.id as number, {
      target_id: dropNode.id as number,
      drop_position: dropPosition
    })
    Message.success('模块排序/移动成功')
    await fetchModules()
  } catch (error) {
    console.error('移动模块出错:', error)
    Message.error('移动模块时发生错误')
    await fetchModules()
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  Object.assign(formData, { project: projectId.value || 0, name: '', parent: null })
  formRef.value?.clearValidate()
}

const showAddModal = (parent: UiModule | null) => {
  isEdit.value = false
  parentModule.value = parent
  resetForm()
  formData.parent = parent?.id || null
  modalVisible.value = true
}

const editModule = (node: UiModule) => {
  isEdit.value = true
  currentModule.value = node
  parentModule.value = null
  Object.assign(formData, { project: node.project, name: node.name, parent: node.parent })
  modalVisible.value = true
}

const handleSubmit = async (done: (closed: boolean) => void) => {
  try {
    await formRef.value?.validate()
  } catch {
    Message.warning('请填写必填项')
    done(false)
    return
  }
  submitting.value = true
  try {
    if (isEdit.value && currentModule.value) {
      await moduleApi.update(currentModule.value.id, formData)
      Message.success('更新成功')
    } else {
      await moduleApi.create(formData)
      Message.success('创建成功')
    }
    done(true)
    fetchModules()
  } catch (error: unknown) {
    const err = error as { errors?: Record<string, string[]>; error?: string }
    const errors = err?.errors
    if (errors && typeof errors === 'object' && !('error' in errors) && !('message' in errors)) {
      const messages = Object.entries(errors)
        .map(([field, msgs]) => `${field}: ${Array.isArray(msgs) ? msgs.join(', ') : msgs}`)
        .join('\n')
      Message.error({ content: messages, duration: 5000 })
    } else {
      Message.error(err?.error || (isEdit.value ? '更新失败' : '创建失败'))
    }
    done(false)
  } finally {
    submitting.value = false
  }
}

const handleCancel = () => {
  modalVisible.value = false
}

const deleteModule = (node: UiModule) => {
  Modal.confirm({
    title: '确认删除',
    content: `确定删除模块 "${node.name}" 吗？子模块也会被删除。`,
    okButtonProps: { status: 'danger' },
    onOk: async () => {
      try {
        await moduleApi.delete(node.id)
        Message.success('删除成功')
        fetchModules()
        if (selectedKeys.value.includes(node.id)) {
          selectedKeys.value = []
          emit('select', null)
        }
      } catch (error: unknown) {
        const err = error as { error?: string }
        Message.error(err?.error || '存在关联，无法删除。请先解除关联')
      }
    },
  })
}

watch(projectId, fetchModules, { immediate: true })

defineExpose({ refresh: fetchModules })
</script>

<style scoped>
.module-tree {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.tree-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border);
}
.tree-title {
  font-weight: 500;
  font-size: 14px;
}
.tree-content {
  flex: 1;
  overflow: auto;
  padding: 8px;
}
.tree-node {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}
.node-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.node-action {
  opacity: 0;
  transition: opacity 0.2s;
}
.tree-node:hover .node-action {
  opacity: 1;
}
.danger-option {
  color: rgb(var(--danger-6));
}
</style>
