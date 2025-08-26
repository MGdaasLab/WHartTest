<template>
  <a-card class="module-panel" :bordered="false" title="模块管理">
    <a-input-search
      v-model="moduleSearchKeyword"
      placeholder="请输入模块名称"
      allow-clear
      style="margin-bottom: 16px; flex-shrink: 0;"
      @search="onModuleSearch"
      @input="onModuleSearch"
    />
    <div class="module-actions">
      <a-dropdown @select="handleModuleAction" trigger="hover" position="bottom" :popup-max-width="false" class="module-dropdown">
        <a-button type="primary" size="small" class="module-action-button">
          操作
        </a-button>
        <template #content>
          <a-doption value="addRoot" class="centered-dropdown-item">添加根模块</a-doption>
          <a-doption value="addChild" :disabled="!selectedModuleKey" class="centered-dropdown-item">添加子模块</a-doption>
          <a-doption value="edit" :disabled="!selectedModuleKey" class="centered-dropdown-item">编辑模块</a-doption>
          <a-doption value="delete" :disabled="!selectedModuleKey" class="centered-dropdown-item">删除模块</a-doption>
        </template>
      </a-dropdown>
    </div>
    <div v-if="moduleLoading" class="module-loading-container">
      <a-spin />
    </div>
    <a-tree
      v-else-if="moduleTreeData.length > 0"
      :data="filteredModuleTreeData"
      :field-names="{ key: 'id', title: 'name' }"
      show-line
      block-node
      @select="onModuleSelect"
      v-model:selected-keys="selectedModuleKeys"
    >
      <template #title="nodeData">
        <span>{{ nodeData.name }}</span>
        <span class="module-count"> ({{ nodeData.testcase_count || nodeData.test_case_count || 0 }})</span>
      </template>
    </a-tree>
    <a-empty v-else description="暂无模块数据" />

    <!-- 模块管理模态框 -->
    <ModuleEditModal
      :visible="moduleModalVisible"
      :is-editing="isEditingModule"
      :initial-data="moduleForm"
      :module-tree="moduleTreeForSelect"
      :project-id="currentProjectId"
      @submit="handleModuleSubmit"
      @close="closeModuleModal"
    />
  </a-card>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed, watch, toRefs } from 'vue';
import { Message, Modal } from '@arco-design/web-vue';
import type { TreeNodeData, FormInstance } from '@arco-design/web-vue';
import {
  getTestCaseModules,
  createTestCaseModule,
  updateTestCaseModule,
  deleteTestCaseModule,
  type TestCaseModule,
  type CreateTestCaseModuleRequest,
  type UpdateTestCaseModuleRequest,
} from '@/services/testcaseModuleService';
import ModuleEditModal from './ModuleEditModal.vue'; // 引入模块编辑模态框

const props = defineProps<{
  currentProjectId: number | null;
}>();

const emit = defineEmits<{
  (e: 'moduleSelected', moduleId: number | null): void;
  (e: 'moduleUpdated'): void; // 当模块（增删改）更新后触发
}>();

const { currentProjectId } = toRefs(props);

// 加载状态
const moduleLoading = ref(false); // 模块列表加载状态

// 搜索关键词
const moduleSearchKeyword = ref(''); // 模块搜索关键词

// 模块管理相关
const testCaseModules = ref<TestCaseModule[]>([]);
const selectedModuleKey = ref<number | null>(null);
const selectedModuleKeys = ref<(number|string)[]>([]); // For a-tree v-model:selected-keys

// 模块编辑模态框相关
const moduleModalVisible = ref(false);
const moduleForm = reactive<CreateTestCaseModuleRequest & { id?: number }>({
  name: '',
  parent: undefined,
});
const isEditingModule = ref(false);


// 获取模块列表
const fetchTestCaseModules = async () => {
  if (!currentProjectId.value) return;
  moduleLoading.value = true;
  try {
    const response = await getTestCaseModules(currentProjectId.value, { search: moduleSearchKeyword.value }); // 假设API支持search参数
    if (response.success && response.data) {
      testCaseModules.value = response.data;
    } else {
      Message.error(response.error || '获取模块列表失败');
      testCaseModules.value = [];
    }
  } catch (error) {
    console.error('获取模块列表出错:', error);
    Message.error('获取模块列表时发生错误');
    testCaseModules.value = [];
  } finally {
    moduleLoading.value = false;
  }
};

// 构建模块树 (扁平列表转树形)
const buildModuleTree = (modules: TestCaseModule[], parentId: number | null = null): TreeNodeData[] => {
  return modules
    .filter(module => module.parent === parentId || module.parent_id === parentId)
    .map(module => ({
      ...module,
      id: module.id, // 确保 id 作为 key
      key: module.id, // for a-tree
      title: module.name, // for a-tree
      children: buildModuleTree(modules, module.id),
      test_case_count: module.testcase_count || module.test_case_count || 0,
    }));
};

// 模块树数据
const moduleTreeData = computed(() => {
  return buildModuleTree(testCaseModules.value);
});

// 用于 TreeSelect 的模块树数据 (排除当前编辑的模块及其子模块，防止循环引用)
const moduleTreeForSelect = computed(() => {
  if (isEditingModule.value && moduleForm.id) {
    const filterOutIds = getAllChildModuleIds(testCaseModules.value, moduleForm.id);
    filterOutIds.add(moduleForm.id); // Also filter out the module itself
    const filteredModules = testCaseModules.value.filter(m => !filterOutIds.has(m.id));
    return buildModuleTree(filteredModules);
  }
  return moduleTreeData.value;
});

// 获取一个模块及其所有子模块的ID
const getAllChildModuleIds = (modules: TestCaseModule[], parentId: number): Set<number> => {
  const childrenIds = new Set<number>();
  const findChildren = (currentParentId: number) => {
    modules.forEach(module => {
      if (module.parent === currentParentId || module.parent_id === currentParentId) {
        childrenIds.add(module.id);
        findChildren(module.id);
      }
    });
  };
  findChildren(parentId);
  return childrenIds;
};


// 过滤后的模块树数据 (用于搜索)
const filteredModuleTreeData = computed(() => {
  if (!moduleSearchKeyword.value.trim()) {
    return moduleTreeData.value;
  }
  const keyword = moduleSearchKeyword.value.toLowerCase();

  function filterTree(nodes: TreeNodeData[]): TreeNodeData[] {
    return nodes.reduce((acc, node) => {
      const nodeName = (node.name || '').toLowerCase();
      const children = node.children ? filterTree(node.children as TreeNodeData[]) : [];

      if (nodeName.includes(keyword) || children.length > 0) {
        acc.push({ ...node, children: children.length > 0 ? children : undefined });
      }
      return acc;
    }, [] as TreeNodeData[]);
  }
  return filterTree(moduleTreeData.value);
});


// 模块搜索
const onModuleSearch = () => {
  // 前端过滤，如果需要API搜索，则调用 fetchTestCaseModules
};

// 模块树节点选择
const onModuleSelect = (
  newSelectedKeys: (string | number)[],
  data: { selected?: boolean; selectedNodes: TreeNodeData[]; node?: TreeNodeData; e?: Event }
) => {
  if (data.selected && data.node) {
    selectedModuleKey.value = data.node.key as number;
    emit('moduleSelected', selectedModuleKey.value);
  } else {
    selectedModuleKey.value = null;
    emit('moduleSelected', null);
  }
};

// 模块操作处理
const handleModuleAction = async (action: string | number | Record<string, any> | undefined) => {
  const actionValue = action as string;
  switch (actionValue) {
    case 'addRoot':
      isEditingModule.value = false;
      moduleForm.id = undefined;
      moduleForm.name = '';
      moduleForm.parent = undefined;
      moduleModalVisible.value = true;
      break;
    case 'addChild':
      if (selectedModuleKey.value) {
        isEditingModule.value = false;
        moduleForm.id = undefined;
        moduleForm.name = '';
        moduleForm.parent = selectedModuleKey.value;
        moduleModalVisible.value = true;
      } else {
        Message.warning('请先选择一个父模块');
      }
      break;
    case 'edit':
      if (selectedModuleKey.value) {
        const moduleToEdit = testCaseModules.value.find(m => m.id === selectedModuleKey.value);
        if (moduleToEdit) {
          isEditingModule.value = true;
          moduleForm.id = moduleToEdit.id;
          moduleForm.name = moduleToEdit.name;
          moduleForm.parent = moduleToEdit.parent || undefined;
          moduleModalVisible.value = true;
        }
      } else {
        Message.warning('请先选择要编辑的模块');
      }
      break;
    case 'delete':
      if (selectedModuleKey.value) {
        const moduleToDelete = testCaseModules.value.find(m => m.id === selectedModuleKey.value);
        if (moduleToDelete) {
          const children = testCaseModules.value.filter(m => m.parent === selectedModuleKey.value || m.parent_id === selectedModuleKey.value);
          if (children.length > 0) {
            Message.error('该模块下有子模块，请先删除子模块');
            return;
          }
          // 检查模块下是否有用例
          if (moduleToDelete.test_case_count && moduleToDelete.test_case_count > 0) {
            Message.error(`模块 "${moduleToDelete.name}" 下包含 ${moduleToDelete.test_case_count} 个测试用例，请先处理用例。`);
            return;
          }

          Modal.warning({
            title: '确认删除',
            content: `确定要删除模块 "${moduleToDelete.name}" 吗？此操作不可恢复。`,
            okText: '确认',
            cancelText: '取消',
            onOk: async () => {
              if (!currentProjectId.value || !selectedModuleKey.value) return;
              try {
                const response = await deleteTestCaseModule(currentProjectId.value, selectedModuleKey.value);
                if (response.success) {
                  Message.success('模块删除成功');
                  fetchTestCaseModules(); // 刷新模块列表
                  selectedModuleKey.value = null; // 清除选中
                  selectedModuleKeys.value = [];
                  emit('moduleUpdated');
                } else {
                  Message.error(response.error || '删除模块失败');
                }
              } catch (error) {
                Message.error('删除模块时发生错误');
              }
            },
          });
        }
      } else {
        Message.warning('请先选择要删除的模块');
      }
      break;
  }
};

// 关闭模块模态框
const closeModuleModal = () => {
  moduleModalVisible.value = false;
};

// 提交模块表单 (添加/编辑)
const handleModuleSubmit = async (success: boolean) => {
  if (success) {
    fetchTestCaseModules(); // 刷新模块列表
    closeModuleModal();
    emit('moduleUpdated');
  }
};

onMounted(() => {
  if (currentProjectId.value) {
    fetchTestCaseModules();
  }
});

watch(currentProjectId, (newProjectId) => {
  if (newProjectId) {
    testCaseModules.value = [];
    selectedModuleKey.value = null;
    selectedModuleKeys.value = [];
    moduleSearchKeyword.value = '';
    fetchTestCaseModules();
  } else {
    testCaseModules.value = [];
    selectedModuleKey.value = null;
    selectedModuleKeys.value = [];
  }
});

// 暴露给父组件的方法
defineExpose({
  refreshModules: fetchTestCaseModules,
});

</script>

<style scoped>
.module-panel {
  width: 280px; /* 固定宽度，类似菜单栏 */
  min-width: 240px;
  height: 100%; /* 占满父容器高度 */
  display: flex;
  flex-direction: column;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: -4px 0 10px rgba(0, 0, 0, 0.2), 0 4px 10px rgba(0, 0, 0, 0.2), 0 0 10px rgba(0, 0, 0, 0.15);
  overflow: hidden; /* 防止内容溢出容器 */
}

:deep(.module-panel .arco-card-header) {
  border-bottom: 1px solid var(--color-border-2);
  padding: 12px 16px;
  flex-shrink: 0; /* 防止头部被压缩 */
}
:deep(.module-panel .arco-card-body) {
  padding: 16px;
  overflow-y: auto; /* 模块列表过长时可滚动 */
  flex-grow: 1; /* 占据剩余空间 */
  height: 0; /* 关键：强制flex-grow生效 */
  display: flex;
  flex-direction: column;
}

/* 确保树组件占据卡片内容区域的全部可用高度 */
:deep(.module-panel .arco-card-body .arco-tree) {
  flex-grow: 1;
  overflow-y: auto;
  height: 100%;
}

/* 确保空状态也能正确显示 */
:deep(.module-panel .arco-card-body .arco-empty) {
  margin: auto;
}

.module-loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  min-height: 100px;
}

.module-count {
  color: var(--color-text-3);
  font-size: 0.85em;
  margin-left: 4px;
}

.module-actions {
  display: flex;
  justify-content: center; /* 居中对齐 */
  margin-top: 8px;
  margin-bottom: 16px;
  flex-shrink: 0; /* 防止被压缩 */
}

/* 下拉菜单相关样式 */
.module-dropdown {
  width: 100%;
}

.module-action-button {
  width: 80px;
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

:deep(.arco-dropdown-list) {
  min-width: 120px;
  width: 100%;
}

:deep(.arco-dropdown) {
  width: 100%;
}

:deep(.arco-dropdown-menu) {
  width: 100%;
  padding: 4px 0;
}
</style>