<template>
  <div class="organization-management">
    <div class="page-header">
      <div class="search-box">
        <a-input-search
          placeholder="搜索组织名称/代码"
          allow-clear
          style="width: 300px"
          @search="onSearch"
        />
      </div>
      <div class="action-buttons">
        <a-button type="primary" @click="showAddOrganizationModal">添加组织</a-button>
      </div>
    </div>

    <a-table
      :columns="columns"
      :data="organizationData"
      :pagination="pagination"
      :loading="loading"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
      @row-click="handleRowClick"
    >
      <template #operations="{ record }">
        <a-space :size="4">
          <a-button type="primary" size="mini" @click="viewOrganizationMembers(record, $event)">成员</a-button>
          <a-button type="primary" size="mini" @click="viewOrganizationPermissions(record, $event)">权限</a-button>
          <a-button type="primary" size="mini" @click="editOrganization(record, $event)">编辑</a-button>
          <a-button type="primary" status="danger" size="mini" @click="deleteOrganization(record, $event)">删除</a-button>
        </a-space>
      </template>
    </a-table>

    <!-- 组织成员管理 -->
    <a-modal
      v-model:visible="membersModalVisible"
      title="组织成员管理"
      :footer="false"
      :mask-closable="true"
      :width="900"
    >
      <organization-members-table
        :organization-id="selectedOrganizationId"
        @refresh="refreshOrganizationList"
      />
    </a-modal>

    <!-- 组织权限管理 -->
    <a-modal
      v-model:visible="permissionsModalVisible"
      title="组织权限管理"
      :footer="false"
      :mask-closable="true"
      :width="1200"
    >
      <permission-tree-selector
        ref="permissionTreeSelectorRef"
        type="group"
        :id="selectedOrganizationId"
        :lazy="true"
        @refresh="refreshOrganizationList"
      />
    </a-modal>

    <!-- 添加组织模态框 -->
    <a-modal
      v-model:visible="addOrganizationModalVisible"
      title="添加组织"
      @cancel="cancelAddOrganization"
      @before-ok="handleAddOrganization"
      :mask-closable="false"
      :width="600"
    >
      <a-form ref="addOrganizationFormRef" :model="addOrganizationForm" :rules="addOrganizationRules" layout="vertical" :auto-label-width="false">
        <a-row :gutter="16">
          <a-col :span="24">
            <a-form-item field="name" label="组织名称" required>
              <a-input v-model="addOrganizationForm.name" placeholder="请输入组织名称" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-modal>

    <!-- 编辑组织模态框 -->
    <a-modal
      v-model:visible="editOrganizationModalVisible"
      title="编辑组织"
      @cancel="cancelEditOrganization"
      @before-ok="handleEditOrganization"
      :mask-closable="false"
      :width="600"
    >
      <a-form ref="editOrganizationFormRef" :model="editOrganizationForm" :rules="editOrganizationRules" layout="vertical" :auto-label-width="false">
        <a-row :gutter="16">
          <a-col :span="24">
            <a-form-item field="name" label="组织名称" required>
              <a-input v-model="editOrganizationForm.name" placeholder="请输入组织名称" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, nextTick } from 'vue';
import { Message, Modal, Row as ARow, Col as ACol } from '@arco-design/web-vue';
import {
  getOrganizationList,
  createOrganization,
  deleteOrganization as deleteOrganizationService,
  getOrganizationDetail,
  updateOrganization,
  type Organization,
  type CreateOrganizationRequest,
  type UpdateOrganizationRequest
} from '@/services/organizationService';
import OrganizationMembersTable from '@/components/organization/OrganizationMembersTable.vue';
import PermissionTreeSelector from '@/components/permission/PermissionTreeSelector.vue';

// 加载状态
const loading = ref(false);
// 搜索关键词
const searchKeyword = ref('');
// Permission tree selector ref
const permissionTreeSelectorRef = ref();

// 表格列定义
const columns = [
  {
    title: '组织ID',
    dataIndex: 'id',
    width: 80,
  },
  {
    title: '组织名称',
    dataIndex: 'name',
  },
  {
    title: '操作',
    slotName: 'operations',
    width: 240,
    fixed: 'right',
  },
];

// 组织数据
const organizationData = ref<Organization[]>([]);

// 组织成员管理相关
const membersModalVisible = ref(false);
const permissionsModalVisible = ref(false);
const selectedOrganizationId = ref<number>(0);

// 查看组织成员
const viewOrganizationMembers = (organization: Organization, event: Event) => {
  // 阻止事件冒泡，避免触发行点击事件
  event.stopPropagation();

  selectedOrganizationId.value = organization.id;
  membersModalVisible.value = true;
};

// 查看组织权限
const viewOrganizationPermissions = async (organization: Organization, event: Event) => {
  // 阻止事件冒泡，避免触发行点击事件
  event.stopPropagation();

  selectedOrganizationId.value = organization.id;
  permissionsModalVisible.value = true;
  
  // 延迟加载权限数据
  await nextTick();
  permissionTreeSelectorRef.value?.loadPermissions(organization.id);
};

// 处理行点击事件
const handleRowClick = (record: Organization) => {
  selectedOrganizationId.value = record.id;
  membersModalVisible.value = true;
};

// 刷新组织列表
const refreshOrganizationList = () => {
  fetchOrganizationList();
};

// 分页配置
const pagination = reactive({
  total: 0,
  current: 1,
  pageSize: 10,
  showTotal: true,
  showJumper: true,
  showPageSize: true,
  pageSizeOptions: [10, 20, 50, 100],
});

// 获取组织列表数据
const fetchOrganizationList = async () => {
  loading.value = true;
  try {
    const response = await getOrganizationList({
      page: pagination.current,
      pageSize: pagination.pageSize,
      search: searchKeyword.value
    });

    if (response.success && response.data) {
      organizationData.value = response.data;
      pagination.total = response.total || response.data.length;
    } else {
      Message.error(response.error || '获取组织列表失败');
      organizationData.value = [];
      pagination.total = 0;
    }
  } catch (error) {
    console.error('获取组织列表出错:', error);
    Message.error('获取组织列表时发生错误');
    organizationData.value = [];
    pagination.total = 0;
  } finally {
    loading.value = false;
  }
};

// 搜索组织
const onSearch = (value: string) => {
  searchKeyword.value = value;
  pagination.current = 1; // 重置到第一页
  fetchOrganizationList();
};

// 分页变化
const onPageChange = (page: number) => {
  pagination.current = page;
  fetchOrganizationList();
};

// 每页显示数量变化
const onPageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize;
  pagination.current = 1; // 重置到第一页
  fetchOrganizationList();
};

// 在组件挂载时加载组织数据
onMounted(() => {
  fetchOrganizationList();
});

// 添加组织模态框相关
const addOrganizationModalVisible = ref(false);
const addOrganizationFormRef = ref();
const addOrganizationForm = reactive<CreateOrganizationRequest>({
  name: ''
});

// 表单验证规则
const addOrganizationRules = {
  name: [
    { required: true, message: '请输入组织名称' },
    { maxLength: 100, message: '组织名称长度不能超过100个字符' }
  ]
};

// 显示添加组织模态框
const showAddOrganizationModal = () => {
  // 重置表单
  Object.assign(addOrganizationForm, {
    name: ''
  });

  // 显示模态框
  addOrganizationModalVisible.value = true;
};

// 取消添加组织
const cancelAddOrganization = () => {
  addOrganizationModalVisible.value = false;
};

// 处理添加组织
const handleAddOrganization = async (done: (closed: boolean) => void) => {
  // 验证表单
  try {
    await addOrganizationFormRef.value.validate();
    // 验证通过，继续处理
  } catch (errors) {
    // 表单验证失败
    console.error('表单验证失败:', errors);
    done(false); // 不关闭模态框
    return;
  }

  // 创建组织数据对象
  const organizationData: CreateOrganizationRequest = {
    name: addOrganizationForm.name
  };

  try {
    // 调用创建组织API
    const response = await createOrganization(organizationData);

    if (response.success) {
      Message.success('组织创建成功');
      // 刷新组织列表
      fetchOrganizationList();
      done(true); // 关闭模态框
    } else {
      Message.error(response.error || '创建组织失败');
      done(false); // 不关闭模态框
    }
  } catch (error) {
    console.error('创建组织出错:', error);
    Message.error('创建组织时发生错误');
    done(false); // 不关闭模态框
  }
};

// 编辑组织模态框相关
const editOrganizationModalVisible = ref(false);
const editOrganizationFormRef = ref();
const editOrganizationForm = reactive<UpdateOrganizationRequest & { id: number }>({
  id: 0,
  name: ''
});

// 编辑组织表单验证规则
const editOrganizationRules = {
  name: [
    { required: true, message: '请输入组织名称' },
    { maxLength: 100, message: '组织名称长度不能超过100个字符' }
  ]
};

// 显示编辑组织模态框
const editOrganization = (organization: Organization, event?: Event) => {
  // 阻止事件冒泡，避免触发行点击事件
  if (event) {
    event.stopPropagation();
  }
  // 设置表单数据
  Object.assign(editOrganizationForm, {
    id: organization.id,
    name: organization.name
  });

  // 显示模态框
  editOrganizationModalVisible.value = true;
};

// 取消编辑组织
const cancelEditOrganization = () => {
  editOrganizationModalVisible.value = false;
};

// 处理编辑组织
const handleEditOrganization = async (done: (closed: boolean) => void) => {
  // 验证表单
  try {
    await editOrganizationFormRef.value.validate();
    // 验证通过，继续处理
  } catch (errors) {
    // 表单验证失败
    console.error('表单验证失败:', errors);
    done(false); // 不关闭模态框
    return;
  }

  // 创建更新数据对象
  const updateData: UpdateOrganizationRequest = {
    name: editOrganizationForm.name
  };

  try {
    // 调用更新组织API
    const response = await updateOrganization(editOrganizationForm.id, updateData);

    if (response.success) {
      Message.success('组织更新成功');
      // 刷新组织列表
      fetchOrganizationList();
      done(true); // 关闭模态框
    } else {
      Message.error(response.error || '更新组织失败');
      done(false); // 不关闭模态框
    }
  } catch (error) {
    console.error('更新组织出错:', error);
    Message.error('更新组织时发生错误');
    done(false); // 不关闭模态框
  }
};

// 删除组织
const deleteOrganization = (organization: Organization, event?: Event) => {
  // 阻止事件冒泡，避免触发行点击事件
  if (event) {
    event.stopPropagation();
  }
  Modal.warning({
    title: '确认删除',
    content: `确定要删除组织 "${organization.name}" 吗？此操作不可恢复。`,
    okText: '确定删除',
    cancelText: '取消',
    onOk: async () => {
      try {
        const response = await deleteOrganizationService(organization.id);

        if (response.success) {
          Message.success(response.message || '组织删除成功');
          // 刷新组织列表
          fetchOrganizationList();
        } else {
          Message.error(response.error || '删除组织失败');
        }
      } catch (error) {
        console.error('删除组织出错:', error);
        Message.error('删除组织时发生错误');
      }
    }
  });
};
</script>

<style scoped>
.organization-management {
  background-color: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.15);
  height: 100%;
  box-sizing: border-box;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.search-box {
  display: flex;
  align-items: center;
}

.action-buttons {
  display: flex;
  gap: 10px;
}

/* 操作按钮样式优化 */
:deep(.arco-table-th.operations-header) {
  white-space: nowrap;
}

:deep(.arco-table-td.operations-cell) {
  padding: 8px 4px;
}

:deep(.arco-btn-size-mini) {
  padding: 0 8px;
  font-size: 12px;
  height: 24px;
  line-height: 22px;
}

/* 确保操作列按钮不溢出 */
:deep(.arco-space-item) {
  margin-right: 2px !important;
}

:deep(.arco-space-item:last-child) {
  margin-right: 0 !important;
}
</style>
