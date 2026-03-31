<template>
  <div class="permission-management">
    <div class="permission-content">
      <!-- 左侧实体选择面板 -->
      <div class="entity-panel">
        <div class="panel-header">
          <h3>选择实体</h3>
          <div class="entity-type-selector">
            <a-radio-group v-model="activeEntityType" @change="handleEntityTypeChange" type="button">
              <a-radio value="user">用户</a-radio>
              <a-radio value="group">组织</a-radio>
            </a-radio-group>
          </div>
        </div>
        
        <div class="search-section">
          <a-input-search
            v-model="entitySearchKeyword"
            :placeholder="activeEntityType === 'user' ? '搜索用户名/邮箱' : '搜索组织名称'"
            allow-clear
            @search="handleEntitySearch"
          />
        </div>

        <div class="entity-list">
          <a-spin :loading="entitiesLoading">
            <div 
              v-for="entity in filteredEntities" 
              :key="entity.id"
              :class="['entity-item', { active: selectedEntity?.id === entity.id }]"
              @click="selectEntity(entity)"
            >
              <div class="entity-info">
                <div class="entity-avatar">
                  {{ activeEntityType === 'user' ? (entity as User).username.charAt(0).toUpperCase() : (entity as Organization).name.charAt(0).toUpperCase() }}
                </div>
                <div class="entity-details">
                  <div class="entity-name">
                    {{ activeEntityType === 'user' ? (entity as User).username : (entity as Organization).name }}
                  </div>
                  <div class="entity-meta">
                    {{ activeEntityType === 'user' ? (entity as User).email : `ID: ${entity.id}` }}
                  </div>
                </div>
              </div>
            </div>
          </a-spin>
        </div>

        <!-- 分页 -->
        <div class="pagination-section" v-if="entityPagination.total > 0">
          <div class="pagination-total">{{ entityPagination.total }}</div>
          <div class="pagination-controls">
            <a-pagination
              v-model:current="entityPagination.current"
              :total="entityPagination.total"
              :page-size="entityPagination.pageSize"
              :show-total="false"
              :show-jumper="false"
              :show-page-size="false"
              size="small"
              class="compact-pagination"
              @change="handleEntityPageChange"
            />
          </div>
          <div class="pagination-size">
            <a-select
              v-model="entityPagination.pageSize"
              :options="[
                { label: '5条/页', value: 5 },
                { label: '10条/页', value: 10 },
                { label: '20条/页', value: 20 }
              ]"
              size="small"
              @change="handleEntityPageSizeChange"
            />
          </div>
        </div>
      </div>

      <!-- 右侧权限管理面板 -->
      <div class="permission-panel">
        <div v-if="!selectedEntity" class="no-selection">
          <div class="empty-state">
            <i class="arco-icon arco-icon-info-circle"></i>
            <p>请从左侧选择用户或组织来管理权限</p>
          </div>
        </div>
        
        <div v-else class="permission-details">
          <div class="details-header">
            <div class="entity-info">
              <i :class="activeEntityType === 'user' ? 'arco-icon arco-icon-user' : 'arco-icon arco-icon-user-group'"></i>
              <div class="entity-details">
                <h3>{{ activeEntityType === 'user' ? (selectedEntity as User).username : (selectedEntity as Organization).name }} 的权限</h3>
                <p>{{ activeEntityType === 'user' ? (selectedEntity as User).email : `组织 ID: ${selectedEntity.id}` }}</p>
              </div>
            </div>
          </div>
          
          <!-- 权限树形展示 -->
          <div class="permission-tree-container">
            <PermissionTreeSelector
              :type="activeEntityType"
              :id="selectedEntity.id"
              @refresh="handleRefresh"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue';
import { Message } from '@arco-design/web-vue';
import { getUserList, type User } from '@/services/userService';
import { getOrganizationList, type Organization } from '@/services/organizationService';
import PermissionTreeSelector from '@/components/permission/PermissionTreeSelector.vue';

// 实体类型
type EntityType = 'user' | 'group';
type Entity = User | Organization;

// 响应式数据
const activeEntityType = ref<EntityType>('user');
const selectedEntity = ref<Entity | null>(null);
const entitySearchKeyword = ref('');
const entitiesLoading = ref(false);

// 实体数据
const users = ref<User[]>([]);
const organizations = ref<Organization[]>([]);

// 分页配置
const entityPagination = reactive({
  total: 0,
  current: 1,
  pageSize: 10,
});

// 当前显示的实体列表
const filteredEntities = computed(() => {
  const entities = activeEntityType.value === 'user' ? users.value : organizations.value;
  if (!entitySearchKeyword.value) return entities;
  
  const keyword = entitySearchKeyword.value.toLowerCase();
  return entities.filter(entity => {
    if (activeEntityType.value === 'user') {
      const user = entity as User;
      return user.username.toLowerCase().includes(keyword) ||
             (user.email && user.email.toLowerCase().includes(keyword));
    } else {
      const org = entity as Organization;
      return org.name.toLowerCase().includes(keyword);
    }
  });
});

// 获取用户列表
const fetchUsers = async () => {
  entitiesLoading.value = true;
  try {
    const response = await getUserList({
      page: entityPagination.current,
      pageSize: entityPagination.pageSize,
      search: entitySearchKeyword.value
    });

    if (response.success && response.data) {
      users.value = response.data;
      entityPagination.total = response.total || response.data.length;
    } else {
      Message.error(response.error || '获取用户列表失败');
      users.value = [];
      entityPagination.total = 0;
    }
  } catch (error) {
    console.error('获取用户列表出错:', error);
    Message.error('获取用户列表时发生错误');
    users.value = [];
    entityPagination.total = 0;
  } finally {
    entitiesLoading.value = false;
  }
};

// 获取组织列表
const fetchOrganizations = async () => {
  entitiesLoading.value = true;
  try {
    const response = await getOrganizationList({
      page: entityPagination.current,
      pageSize: entityPagination.pageSize,
      search: entitySearchKeyword.value
    });

    if (response.success && response.data) {
      organizations.value = response.data;
      entityPagination.total = response.total || response.data.length;
    } else {
      Message.error(response.error || '获取组织列表失败');
      organizations.value = [];
      entityPagination.total = 0;
    }
  } catch (error) {
    console.error('获取组织列表出错:', error);
    Message.error('获取组织列表时发生错误');
    organizations.value = [];
    entityPagination.total = 0;
  } finally {
    entitiesLoading.value = false;
  }
};

// 获取当前类型的实体列表
const fetchEntities = async () => {
  if (activeEntityType.value === 'user') {
    await fetchUsers();
  } else {
    await fetchOrganizations();
  }
};

// 处理实体类型变化
const handleEntityTypeChange = () => {
  selectedEntity.value = null;
  entitySearchKeyword.value = '';
  entityPagination.current = 1;
  fetchEntities();
};

// 处理实体搜索
const handleEntitySearch = () => {
  entityPagination.current = 1;
  fetchEntities();
};

// 选择实体
const selectEntity = (entity: Entity) => {
  selectedEntity.value = entity;
};

// 处理分页变化
const handleEntityPageChange = (page: number) => {
  entityPagination.current = page;
  fetchEntities();
};

// 处理每页数量变化
const handleEntityPageSizeChange = (pageSize: number) => {
  entityPagination.pageSize = pageSize;
  entityPagination.current = 1;
  fetchEntities();
};

// 处理权限刷新
const handleRefresh = () => {
  Message.success('权限更新成功');
};

// 组件挂载时加载数据
onMounted(() => {
  fetchEntities();
});
</script>

<style scoped>
.permission-management {
  background: var(--theme-card-bg);
  color: var(--theme-page-text);
  border: 1px solid var(--theme-card-border);
  border-radius: 8px;
  padding: 20px;
  box-shadow: var(--theme-card-shadow);
  height: calc(100vh - 87px);
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}

.permission-content {
  flex: 1;
  display: flex;
  gap: 20px;
  min-height: 0;
}

/* 左侧实体面板 */
.entity-panel {
  width: 265px;
  background: var(--theme-shell-soft, var(--theme-surface-soft));
  border: 1px solid var(--theme-border);
  border-radius: 6px;
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.panel-header {
  margin-bottom: 16px;
}

.panel-header h3 {
  margin: 0 0 12px 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--theme-text);
}

.entity-type-selector {
  margin-top: 12px;
}

.entity-type-selector :deep(.arco-radio-group) {
  display: flex;
  gap: 8px;
}

.entity-type-selector :deep(.arco-radio-button) {
  flex: 1;
  text-align: center;
}

.search-section {
  margin-bottom: 16px;
}

.entity-list {
  flex: 1;
  overflow-y: auto;
  margin-bottom: 16px;
}

.entity-item {
  padding: 16px;
  border-radius: 6px;
  margin-bottom: 8px;
  background: var(--theme-surface);
  border: 1px solid var(--theme-border);
  cursor: pointer;
  transition: all 0.2s ease;
  box-sizing: border-box;
  display: block;
  width: 230px;
}

.entity-item:hover {
  border-color: var(--theme-accent);
  box-shadow: 0 12px 24px rgba(var(--theme-accent-rgb), 0.12);
}

.entity-item.active {
  border-color: var(--theme-accent);
  background: rgba(var(--theme-accent-rgb), 0.14);
}

.entity-info {
  display: flex !important;
  align-items: center;
  gap: 12px;
  width: 100% !important;
  min-width: 0;
}

.entity-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: #165dff;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  font-size: 16px;
  font-weight: 600;
}

.entity-item.active .entity-avatar {
  background: rgba(var(--theme-accent-rgb), 0.18);
  color: var(--theme-accent);
}

.entity-details {
  flex: 1;
  min-width: 0;
}

.entity-name {
  font-weight: 500;
  color: var(--theme-text);
  margin-bottom: 4px;
  font-size: 15px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.entity-meta {
  font-size: 13px;
  color: var(--theme-text-tertiary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pagination-section {
  margin-top: auto;
  padding-top: 16px;
  border-top: 1px solid var(--theme-border);
}

/* 右侧权限面板 */
.permission-panel {
  flex: 1;
  background: var(--theme-card-bg);
  border: 1px solid var(--theme-card-border);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.no-selection {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-state {
  text-align: center;
  color: var(--theme-text-tertiary);
}

.empty-state i {
  font-size: 48px;
  margin-bottom: 16px;
  display: block;
}

.empty-state p {
  margin: 0;
  font-size: 14px;
}

.permission-details {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: auto;
}

.details-header {
  padding: 20px;
  border-bottom: 1px solid var(--theme-border);
  background: var(--theme-surface);
}

.details-header .entity-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.details-header i {
  font-size: 24px;
  color: #165dff;
}

.details-header .entity-details h3 {
  margin: 0 0 4px 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--theme-text);
}

.details-header .entity-details p {
  margin: 0;
  font-size: 14px;
  color: var(--theme-text-tertiary);
}

.permission-tree-container {
  flex: 1;
  overflow: auto;
  min-height: 0;
  padding: 20px;
}

.compact-pagination :deep(.arco-pagination-size-changer) {
  min-width: 100px !important;
}

.compact-pagination :deep(.arco-select-view-single) {
  min-width: 80px !important;
  width: 80px !important;
}

.compact-pagination :deep(.arco-pagination-total) {
  font-size: 12px;
}

.compact-pagination :deep(.arco-pagination-list) {
  gap: 2px !important;
}

.compact-pagination :deep(.arco-pagination-item) {
  min-width: 24px !important;
  height: 24px !important;
  font-size: 12px !important;
}

.compact-pagination :deep(.arco-pagination-prev),
.compact-pagination :deep(.arco-pagination-next) {
  min-width: 24px !important;
  height: 24px !important;
}

.pagination-total {
  text-align: center;
  font-size: 12px;
  color: var(--theme-text-tertiary);
  margin-bottom: 4px;
}

.pagination-controls {
  display: flex;
  justify-content: center;
  margin-bottom: 4px;
}

.pagination-size {
  display: flex;
  justify-content: center;
}

.pagination-size :deep(.arco-select-view-single) {
  min-width: 100px !important;
  width: 100px !important;
}

:deep(.arco-radio-group-button .arco-radio-button) {
  background: var(--theme-surface);
  border-color: var(--theme-border);
  color: var(--theme-text-secondary);
}

:deep(.arco-radio-group-button .arco-radio-button.arco-radio-checked) {
  background: rgba(var(--theme-accent-rgb), 0.14);
  border-color: var(--theme-accent);
  color: var(--theme-accent);
}

:deep(.arco-radio-group-button .arco-radio-button:hover) {
  color: var(--theme-accent);
}

:deep(.arco-pagination-item),
:deep(.arco-pagination-prev),
:deep(.arco-pagination-next) {
  color: var(--theme-text-secondary);
}
</style>
