<template>
  <div class="module-panel-wrapper">
    <a-card class="module-panel" :bordered="false" title="模块管理">
      <div class="module-panel-content">
        <div class="module-panel-header">
          <a-input-search
            v-model="searchKeyword"
            placeholder="请输入模块名称"
            allow-clear
            @search="onSearch"
            @input="onSearch"
          />
          <div class="module-actions">
            <a-dropdown @select="handleAction" trigger="hover" position="bottom">
              <a-button type="primary" size="small" class="module-action-button">
                操作
              </a-button>
              <template #content>
                <a-doption value="addRoot">添加根模块</a-doption>
                <a-doption value="addChild" :disabled="!selectedModuleId">添加子模块</a-doption>
                <a-doption value="edit" :disabled="!selectedModuleId">编辑模块</a-doption>
                <a-doption value="delete" :disabled="!selectedModuleId">删除模块</a-doption>
              </template>
            </a-dropdown>
          </div>
        </div>
        <div class="tree-container">
          <div v-if="loading" class="module-loading-container">
            <a-spin />
          </div>
          <a-tree
            v-else-if="treeData.length > 0"
            :data="filteredTreeData"
            :field-names="{ key: 'id', title: 'name', children: 'children' }"
            show-line
            block-node
            @select="onSelect"
            v-model:selected-keys="selectedKeys"
            v-model:expanded-keys="expandedKeys"
          >
            <template #title="nodeData">
              <span>{{ nodeData.name }}</span>
            </template>
          </a-tree>
          <a-empty v-else description="暂无模块数据" />
        </div>
      </div>
    </a-card>

    <!-- 模块编辑弹窗 -->
    <a-modal
      v-model:visible="modalVisible"
      :title="isEditing ? '编辑模块' : '新增模块'"
      :ok-loading="submitLoading"
      @before-ok="handleSubmit"
      @cancel="handleCancel"
    >
      <a-form :model="formData" layout="vertical" ref="formRef">
        <a-form-item v-if="parentModule" label="父模块">
          <a-input :model-value="parentModule.name" disabled />
        </a-form-item>
        <a-form-item field="name" label="模块名称" :rules="[{ required: true, message: '请输入模块名称' }]">
          <a-input v-model="formData.name" placeholder="请输入模块名称" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { Message, Modal } from '@arco-design/web-vue';
import { moduleApi } from '../api';
import { extractResponseData, type UiModule, type UiModuleForm } from '../types';
import { useProjectStore } from '@/store/projectStore';

const emit = defineEmits<{
  (e: 'select', module: UiModule | null): void;
  (e: 'updated'): void;
}>();

const projectStore = useProjectStore();
const projectId = computed(() => projectStore.currentProject?.id);

// 数据状态
const loading = ref(false);
const searchKeyword = ref('');
const treeData = ref<UiModule[]>([]);
const selectedModuleId = ref<number | null>(null);
const selectedKeys = ref<(string | number)[]>([]);
const expandedKeys = ref<(string | number)[]>([]);

// 弹窗状态
const modalVisible = ref(false);
const isEditing = ref(false);
const submitLoading = ref(false);
const formRef = ref();
const parentModule = ref<UiModule | null>(null);
const currentModule = ref<UiModule | null>(null);
const formData = ref<UiModuleForm>({
  project: 0,
  name: '',
  parent: null
});

// 过滤后的树数据（搜索功能）
const filteredTreeData = computed(() => {
  if (!searchKeyword.value.trim()) return treeData.value;
  
  const keyword = searchKeyword.value.toLowerCase();
  const filterTree = (nodes: UiModule[]): UiModule[] => {
    return nodes.reduce((acc, node) => {
      const nodeName = (node.name || '').toLowerCase();
      const children = node.children ? filterTree(node.children) : [];
      if (nodeName.includes(keyword) || children.length > 0) {
        acc.push({ ...node, children: children.length > 0 ? children : [] });
      }
      return acc;
    }, [] as UiModule[]);
  };
  return filterTree(treeData.value);
});

// 加载模块树
const fetchModules = async () => {
  if (!projectId.value) {
    console.log('[ModulePanel] projectId is null, skipping fetch');
    return;
  }
  console.log('[ModulePanel] fetching modules for project:', projectId.value);
  loading.value = true;
  try {
    const res = await moduleApi.tree(projectId.value);
    console.log('[ModulePanel] API response:', res);
    const data = extractResponseData<UiModule[]>(res) || [];
    console.log('[ModulePanel] extracted data:', data);
    treeData.value = Array.isArray(data) ? data : [];
  } catch (error) {
    console.error('[ModulePanel] 获取模块失败:', error);
    Message.error('获取模块树失败');
    treeData.value = [];
  } finally {
    loading.value = false;
  }
};

// 搜索
const onSearch = () => {};

// 选择模块
const onSelect = (keys: (string | number)[], data: { node?: UiModule }) => {
  selectedModuleId.value = keys.length > 0 ? (keys[0] as number) : null;
  selectedKeys.value = keys;
  emit('select', data.node || null);
};

// 重置表单
const resetForm = () => {
  formData.value = { project: projectId.value || 0, name: '', parent: null };
  formRef.value?.clearValidate();
};

// 找到节点（从树中查找）
const findNode = (nodes: UiModule[], id: number): UiModule | null => {
  for (const node of nodes) {
    if (node.id === id) return node;
    if (node.children) {
      const found = findNode(node.children, id);
      if (found) return found;
    }
  }
  return null;
};

// 操作处理
const handleAction = async (value: string) => {
  switch (value) {
    case 'addRoot':
      isEditing.value = false;
      parentModule.value = null;
      resetForm();
      modalVisible.value = true;
      break;
    case 'addChild':
      if (!selectedModuleId.value) {
        Message.warning('请先选择父模块');
        return;
      }
      isEditing.value = false;
      parentModule.value = findNode(treeData.value, selectedModuleId.value);
      resetForm();
      formData.value.parent = selectedModuleId.value;
      modalVisible.value = true;
      break;
    case 'edit':
      if (!selectedModuleId.value) {
        Message.warning('请先选择模块');
        return;
      }
      const moduleToEdit = findNode(treeData.value, selectedModuleId.value);
      if (moduleToEdit) {
        isEditing.value = true;
        currentModule.value = moduleToEdit;
        parentModule.value = null;
        formData.value = {
          project: moduleToEdit.project,
          name: moduleToEdit.name,
          parent: moduleToEdit.parent
        };
        modalVisible.value = true;
      }
      break;
    case 'delete':
      if (!selectedModuleId.value) {
        Message.warning('请先选择模块');
        return;
      }
      const moduleToDelete = findNode(treeData.value, selectedModuleId.value);
      if (moduleToDelete) {
        if (moduleToDelete.children && moduleToDelete.children.length > 0) {
          Message.error('该模块下有子模块，请先删除子模块');
          return;
        }
        Modal.warning({
          title: '确认删除',
          content: `确定要删除模块 "${moduleToDelete.name}" 吗？`,
          okText: '确认',
          cancelText: '取消',
          onOk: async () => {
            try {
              await moduleApi.delete(selectedModuleId.value!);
              Message.success('删除成功');
              selectedModuleId.value = null;
              selectedKeys.value = [];
              emit('updated');
              fetchModules();
            } catch (error: unknown) {
              const err = error as { error?: string };
              Message.error(err?.error || '存在关联，无法删除。请先解除关联');
            }
          }
        });
      }
      break;
  }
};

// 提交表单
const handleSubmit = async (done: (closed: boolean) => void) => {
  if (!formRef.value) {
    done(false);
    return;
  }
  try {
    await formRef.value.validate();
  } catch {
    Message.warning('请填写必填项');
    done(false);
    return;
  }
  
  submitLoading.value = true;
  try {
    if (isEditing.value && currentModule.value) {
      await moduleApi.update(currentModule.value.id, formData.value);
      Message.success('更新成功');
    } else {
      await moduleApi.create(formData.value);
      Message.success('创建成功');
    }
    
    done(true);
    emit('updated');
    fetchModules();
  } catch (error: unknown) {
    const err = error as { errors?: Record<string, string[]>; error?: string };
    const errors = err?.errors;
    if (errors && typeof errors === 'object' && !('error' in errors) && !('message' in errors)) {
      const messages = Object.entries(errors)
        .map(([field, msgs]) => `${field}: ${Array.isArray(msgs) ? msgs.join(', ') : msgs}`)
        .join('\n');
      Message.error({ content: messages, duration: 5000 });
    } else {
      Message.error(err?.error || (isEditing.value ? '更新失败' : '创建失败'));
    }
    done(false);
  } finally {
    submitLoading.value = false;
  }
};

const handleCancel = () => {
  modalVisible.value = false;
};

// 监听项目变化
watch(projectId, (newId) => {
  if (newId) {
    treeData.value = [];
    selectedModuleId.value = null;
    selectedKeys.value = [];
    searchKeyword.value = '';
    fetchModules();
  }
}, { immediate: true });

// 暴露刷新方法
defineExpose({
  refresh: fetchModules
});
</script>

<style scoped>
.module-panel-wrapper {
  width: 280px;
  min-width: 200px;
  max-width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

@media (max-width: 768px) {
  .module-panel-wrapper {
    width: 100%;
    height: 200px;
    min-height: 150px;
  }
}

.module-panel {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: -4px 0 10px rgba(0, 0, 0, 0.2), 0 4px 10px rgba(0, 0, 0, 0.2), 0 0 10px rgba(0, 0, 0, 0.15);
  overflow: hidden;
}

:deep(.module-panel .arco-card-header) {
  border-bottom: 1px solid var(--color-border-2);
  padding: 12px 16px;
  flex-shrink: 0;
}

:deep(.module-panel .arco-card-body) {
  padding: 0;
  flex-grow: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.module-panel-content {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.module-panel-header {
  flex-shrink: 0;
  padding: 16px;
  border-bottom: 1px solid var(--color-border-2);
}

.module-actions {
  display: flex;
  justify-content: center;
  margin-top: 8px;
}

.module-action-button {
  width: 80px;
}

.tree-container {
  flex-grow: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
  scrollbar-width: none;
}

.tree-container::-webkit-scrollbar {
  display: none;
}

.module-loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  min-height: 100px;
}

:deep(.arco-dropdown-option) {
  text-align: center !important;
  padding: 5px 12px !important;
}

:deep(.arco-dropdown-option-content) {
  display: block !important;
  text-align: center !important;
  width: 100% !important;
}
</style>
