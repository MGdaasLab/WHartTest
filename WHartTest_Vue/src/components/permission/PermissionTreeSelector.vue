<template>
  <div class="permission-tree-selector">
    <!-- 搜索和操作区域 -->
    <div class="tree-header">
      <div class="search-box">
        <a-input-search
          v-model="searchKeyword"
          placeholder="搜索权限名称"
          allow-clear
          style="width: 300px"
          @search="handleSearch"
          @clear="handleSearch"
        />
      </div>
      <div class="action-buttons">
        <a-space>
          <a-button
            size="small"
            @click="toggleExpandAll"
          >
            {{ isAllExpanded ? '收起全部' : '展开全部' }}
          </a-button>
          <a-button
            type="primary"
            :loading="saveLoading"
            @click="handleSavePermissions"
          >
            <template #icon><icon-save /></template>
            保存权限
          </a-button>
        </a-space>
      </div>
    </div>

    <!-- 权限树 -->
    <div class="tree-container">
      <a-spin :loading="loading" style="width: 100%; height: 100%;">
        <div style="height: 100%; overflow: auto;">
          <a-tree
            v-if="permissionTreeData.length > 0"
            :data="filteredPermissionTreeData"
            :field-names="{ key: 'id', title: 'title' }"
            checkable
            show-line
            block-node
            :checked-keys="checkedKeys"
            :half-checked-keys="halfCheckedKeys"
            :expanded-keys="expandedKeys"
            @check="onPermissionCheck"
            @expand="onNodeExpand"
          >
            <template #title="nodeData">
              <div class="permission-node">
                <span class="permission-name">{{ nodeData.title }}</span>
                <span v-if="nodeData.isGroup && nodeData.children" class="permission-count">
                  ({{ nodeData.children.length }})
                </span>
                <a-tag
                  v-if="!nodeData.isGroup && nodeData.hasPermission"
                  color="green"
                  size="small"
                  class="permission-tag"
                >
                  已有
                </a-tag>
              </div>
            </template>
          </a-tree>
          <a-empty v-else description="暂无权限数据" />
        </div>
      </a-spin>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue';
import { Message, Modal } from '@arco-design/web-vue';
import { IconSave } from '@arco-design/web-vue/es/icon';
import {
  getPermissionList,
  getUserPermissions,
  getGroupPermissions,
  updateUserPermissions,
  updateGroupPermissions,
  type Permission,
  type PaginationParams
} from '@/services/permissionService';

// 权限树节点接口
interface PermissionTreeNode {
  id: string | number;
  title: string;
  isGroup: boolean;
  hasPermission?: boolean;
  children?: PermissionTreeNode[];
  app_label?: string;
  model?: string;
  permission?: Permission;
  modelCn?: string; // 模型中文名称
}

const props = defineProps<{
  type: 'user' | 'group';
  id: number;
  lazy?: boolean; // 是否懒加载，默认false
}>();

const emit = defineEmits<{
  (e: 'refresh'): void;
}>();

// 响应式数据
const loading = ref(false);
const saveLoading = ref(false);
const searchKeyword = ref('');

// 权限数据
const allPermissions = ref<Permission[]>([]);
const userPermissions = ref<Permission[]>([]);

// 树形数据
const permissionTreeData = ref<PermissionTreeNode[]>([]);
const checkedKeys = ref<(string | number)[]>([]);
const halfCheckedKeys = ref<(string | number)[]>([]);
const expandedKeys = ref<(string | number)[]>([]); // 默认全部收起

// 选中的权限ID
const selectedPermissionIds = computed(() => {
  return checkedKeys.value.filter(key => typeof key === 'number') as number[];
});

// 是否全部展开
const isAllExpanded = computed(() => {
  const allGroupKeys = getAllGroupKeys(permissionTreeData.value);
  return allGroupKeys.length > 0 && allGroupKeys.every(key => expandedKeys.value.includes(key));
});

// 过滤后的树形数据
const filteredPermissionTreeData = computed(() => {
  if (!searchKeyword.value) {
    return permissionTreeData.value;
  }

  return filterTreeData(permissionTreeData.value, searchKeyword.value.toLowerCase());
});

// 过滤树形数据
const filterTreeData = (treeData: PermissionTreeNode[], keyword: string): PermissionTreeNode[] => {
  return treeData.reduce((filtered: PermissionTreeNode[], node) => {
    const matchesKeyword = node.title.toLowerCase().includes(keyword);
    const filteredChildren = node.children ? filterTreeData(node.children, keyword) : [];

    if (matchesKeyword || filteredChildren.length > 0) {
      filtered.push({
        ...node,
        children: filteredChildren.length > 0 ? filteredChildren : node.children,
      });
    }

    return filtered;
  }, []);
};

// 构建权限树
const buildPermissionTree = (permissions: Permission[], userPerms: Permission[]): PermissionTreeNode[] => {
  const userPermIds = new Set(userPerms.map(p => p.id));

  // 按第一层分类和第二层子分类进行分组
  const groupedByCategory = permissions.reduce((categories, permission) => {
    const appLabelCn = permission.content_type.app_label_cn || permission.content_type.app_label;
    const appLabelSort = permission.content_type.app_label_sort || 999;
    const appLabelSubcategory = permission.content_type.app_label_subcategory;
    const appLabelSubcategorySort = permission.content_type.app_label_subcategory_sort || 999;
    const appLabel = permission.content_type.app_label;
    const model = permission.content_type.model;

    if (!categories[appLabelCn]) {
      categories[appLabelCn] = {
        sortOrder: appLabelSort,
        subcategories: {}
      };
    }
    
    const subcategoryKey = appLabelSubcategory || appLabel;
    if (!categories[appLabelCn].subcategories[subcategoryKey]) {
      categories[appLabelCn].subcategories[subcategoryKey] = {
        app_label: appLabel,
        app_label_subcategory: appLabelSubcategory,
        app_label_subcategory_sort: appLabelSubcategorySort,
        models: {}
      };
    }
    if (!categories[appLabelCn].subcategories[subcategoryKey].models[model]) {
      categories[appLabelCn].subcategories[subcategoryKey].models[model] = {
        model_cn: permission.content_type.model_cn || permission.content_type.model_verbose || model,
        permissions: []
      };
    }
    categories[appLabelCn].subcategories[subcategoryKey].models[model].permissions.push(permission);
    return categories;
  }, {} as Record<string, { sortOrder: number; subcategories: Record<string, { app_label: string; app_label_subcategory: string; app_label_subcategory_sort: number; models: Record<string, { model_cn: string; permissions: Permission[] }> }> }>);

  // 构建三层树形结构：第一层分类 -> 第二层子分类 -> 具体权限
  const sortedCategories = Object.entries(groupedByCategory).sort(([, categoryA], [, categoryB]) => {
    return categoryA.sortOrder - categoryB.sortOrder;
  });

  return sortedCategories.map(([categoryName, categoryData]) => {
    const subcategoryEntries = Object.entries(categoryData.subcategories);
    const sortedSubcategories = subcategoryEntries.sort(([, subcategoryA], [, subcategoryB]) => {
      return subcategoryA.app_label_subcategory_sort - subcategoryB.app_label_subcategory_sort;
    });

    const children: PermissionTreeNode[] = [];

    sortedSubcategories.forEach(([subcategoryKey, subcategoryData]) => {
      const modelEntries = Object.entries(subcategoryData.models);

      // 如果有 app_label_subcategory，创建子分类层
      if (subcategoryData.app_label_subcategory) {
        children.push({
          id: `subcategory_${subcategoryKey}`,
          title: subcategoryData.app_label_subcategory,
          isGroup: true,
          children: modelEntries.map(([model, modelData]) => ({
            id: `model_${subcategoryKey}_${model}`,
            title: modelData.model_cn || model,
            isGroup: true,
            children: modelData.permissions.map(permission => ({
              id: permission.id,
              title: permission.name_cn || permission.name,
              isGroup: false,
              hasPermission: userPermIds.has(permission.id),
              permission,
            })),
          })),
        });
      } else {
        // 没有 app_label_subcategory，model_cn 直接顶上去作为第二层
        modelEntries.forEach(([model, modelData]) => {
          children.push({
            id: `model_${subcategoryKey}_${model}`,
            title: modelData.model_cn || model,
            isGroup: true,
            children: modelData.permissions.map(permission => ({
              id: permission.id,
              title: permission.name_cn || permission.name,
              isGroup: false,
              hasPermission: userPermIds.has(permission.id),
              permission,
            })),
          });
        });
      }
    });

    return {
      id: `category_${categoryName}`,
      title: categoryName,
      isGroup: true,
      children,
    };
  });
};

// 获取应用子名称（在系统管理下的子分类）
const getAppSubName = (appLabel: string): string => {
  const subNames: Record<string, string> = {
    'admin': '日志管理',
    'auth': '认证授权',
    'contenttypes': '内容类型',
    'sessions': '会话管理',
    'api_keys': 'API密钥',
    'llm_config': 'LLM配置',
    'llms': 'LLM服务',
    'mcp_tools': 'MCP工具',
  };

  return subNames[appLabel] || appLabel;
};

// 注意：现在直接使用后端提供的中文名称，不需要前端映射

// 获取所有权限
const fetchAllPermissions = async () => {
  loading.value = true;
  try {
    const response = await getPermissionList({ page: 1, pageSize: 1000 });
    if (response.success && response.data) {
      allPermissions.value = response.data;
    } else {
      Message.error(response.error || '获取权限列表失败');
    }
  } catch (error) {
    console.error('获取权限列表出错:', error);
    Message.error('获取权限列表时发生错误');
  } finally {
    loading.value = false;
  }
};

// 获取用户/组织权限
const fetchUserPermissions = async () => {
  if (!props.id) return;

  try {
    let response;
    if (props.type === 'user') {
      response = await getUserPermissions(props.id);
    } else {
      response = await getGroupPermissions(props.id);
    }

    if (response.success && response.data) {
      userPermissions.value = response.data;
      updateCheckedKeys();
    } else {
      Message.error(response.error || `获取${props.type === 'user' ? '用户' : '组织'}权限失败`);
    }
  } catch (error) {
    console.error('获取权限出错:', error);
    Message.error('获取权限时发生错误');
  }
};

// 懒加载权限数据（供外部调用）
const loadPermissions = async () => {
  if (allPermissions.value.length === 0) {
    await fetchAllPermissions();
  }
  if (props.id) {
    await fetchUserPermissions();
  }
};

// 更新选中状态
const updateCheckedKeys = () => {
  const userPermIds = userPermissions.value.map(p => p.id);
  checkedKeys.value = userPermIds;

  // 构建权限树
  permissionTreeData.value = buildPermissionTree(allPermissions.value, userPermissions.value);
};

// 权限选择处理
const onPermissionCheck = (checkedKeysValue: (string | number)[], info: any) => {
  checkedKeys.value = checkedKeysValue;
  halfCheckedKeys.value = info.halfCheckedKeys || [];
};

// 节点展开处理
const onNodeExpand = (expandedKeysValue: (string | number)[], info: any) => {
  expandedKeys.value = expandedKeysValue;
};

// 获取所有分组节点的key
const getAllGroupKeys = (treeData: PermissionTreeNode[]): (string | number)[] => {
  const keys: (string | number)[] = [];

  const traverse = (nodes: PermissionTreeNode[]) => {
    nodes.forEach(node => {
      if (node.isGroup) {
        keys.push(node.id);
        if (node.children) {
          traverse(node.children);
        }
      }
    });
  };

  traverse(treeData);
  return keys;
};

// 切换展开全部/收起全部
const toggleExpandAll = () => {
  if (isAllExpanded.value) {
    // 收起全部
    expandedKeys.value = [];
  } else {
    // 展开全部
    expandedKeys.value = getAllGroupKeys(permissionTreeData.value);
  }
};

// 搜索处理
const handleSearch = () => {
  if (searchKeyword.value) {
    // 搜索时自动展开包含匹配项的节点
    const matchedGroupKeys = getMatchedGroupKeys(permissionTreeData.value, searchKeyword.value.toLowerCase());
    expandedKeys.value = matchedGroupKeys;
  } else {
    // 清空搜索时收起所有节点
    expandedKeys.value = [];
  }
};

// 获取包含匹配项的分组节点key
const getMatchedGroupKeys = (treeData: PermissionTreeNode[], keyword: string): (string | number)[] => {
  const keys: (string | number)[] = [];

  const traverse = (nodes: PermissionTreeNode[], parentKeys: (string | number)[] = []) => {
    nodes.forEach(node => {
      const currentPath = [...parentKeys, node.id];

      if (node.isGroup && node.children) {
        // 检查子节点是否有匹配项
        const hasMatchedChildren = hasMatchedDescendants(node.children, keyword);
        if (hasMatchedChildren) {
          keys.push(...parentKeys, node.id);
        }
        traverse(node.children, currentPath);
      }
    });
  };

  traverse(treeData);
  return [...new Set(keys)]; // 去重
};

// 检查节点及其后代是否有匹配项
const hasMatchedDescendants = (nodes: PermissionTreeNode[], keyword: string): boolean => {
  return nodes.some(node => {
    const matches = node.title.toLowerCase().includes(keyword);
    const childMatches = node.children ? hasMatchedDescendants(node.children, keyword) : false;
    return matches || childMatches;
  });
};

// 保存权限（完全替换）
const handleSavePermissions = () => {
  const entityType = props.type === 'user' ? '用户' : '组织';

  Modal.confirm({
    title: '确认保存权限',
    content: `确定要保存当前的权限设置吗？\n\n注意：此操作将完全替换${entityType}的权限列表，当前勾选的 ${selectedPermissionIds.value.length} 个权限将成为${entityType}的全部直接权限。`,
    onOk: async () => {
      saveLoading.value = true;
      try {
        let response;
        if (props.type === 'user') {
          response = await updateUserPermissions(props.id, selectedPermissionIds.value);
        } else {
          response = await updateGroupPermissions(props.id, selectedPermissionIds.value);
        }

        if (response.success) {
          Message.success(response.message || '权限保存成功');
          await fetchUserPermissions();
          emit('refresh');
        } else {
          Message.error(response.error || '权限保存失败');
        }
      } catch (error) {
        console.error('保存权限出错:', error);
        Message.error('保存权限时发生错误');
      } finally {
        saveLoading.value = false;
      }
    }
  });
};



// 监听props变化
watch(() => props.id, () => {
  if (props.id) {
    fetchUserPermissions();
  }
}, { immediate: true });

// 组件挂载
onMounted(async () => {
  if (!props.lazy) {
    await fetchAllPermissions();
    if (props.id) {
      await fetchUserPermissions();
    }
  }
});

// 暴露给父组件的方法
defineExpose({
  loadPermissions
});
</script>

<style scoped>
.permission-tree-selector {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.tree-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding: 16px;
  background: #f7f8fa;
  border-radius: 6px;
}

.tree-container {
  flex: 1;
  border: 1px solid #e5e6eb;
  border-radius: 6px;
  padding: 16px;
  min-height: 0;
  overflow: hidden;
}

.permission-node {
  display: flex;
  align-items: center;
  gap: 8px;
}

.permission-name {
  flex: 1;
}

.permission-count {
  color: #86909c;
  font-size: 12px;
}

.permission-tag {
  margin-left: auto;
}

:deep(.arco-tree-node-title) {
  flex: 1;
}
</style>
