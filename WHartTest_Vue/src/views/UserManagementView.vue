<template>
  <div class="user-management">
    <div class="page-header">
      <div class="search-box">
        <a-input-search
          placeholder="搜索用户名/邮箱"
          allow-clear
          style="width: 300px"
          @search="onSearch"
        />
      </div>
      <div class="action-buttons">
        <a-button type="primary" @click="showAddUserModal">添加用户</a-button>
      </div>
    </div>

    <a-table
      :columns="columns"
      :data="userData"
      :pagination="pagination"
      :loading="loading"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
    >
      <template #status="{ record }">
        <a-tag :color="record.is_active ? 'green' : 'gray'">
          {{ record.is_active ? '启用' : '禁用' }}
        </a-tag>
      </template>
      <template #operations="{ record }">
        <a-space>
          <a-button type="primary" size="small" @click="viewUserPermissions(record)">权限</a-button>
          <a-button type="primary" size="small" @click="editUser(record)">编辑</a-button>
          <a-button type="primary" status="danger" size="small" @click="deleteUser(record)">删除</a-button>
        </a-space>
      </template>
    </a-table>

    <!-- 用户权限管理模态框 -->
    <a-modal
      v-model:visible="permissionsModalVisible"
      title="用户权限管理"
      :footer="false"
      :mask-closable="true"
      :width="1200"
    >
      <permission-tree-selector
        ref="permissionTreeSelectorRef"
        type="user"
        :id="selectedUserId"
        lazy
        @refresh="refreshUserList"
      />
    </a-modal>

    <!-- 添加用户模态框 -->
    <a-modal
      v-model:visible="addUserModalVisible"
      title="添加用户"
      @cancel="cancelAddUser"
      @before-ok="handleAddUser"
      :mask-closable="false"
      :width="600"
    >
      <a-form ref="addUserFormRef" :model="addUserForm" :rules="addUserRules" layout="vertical" :auto-label-width="false">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="username" label="用户名" required>
              <a-input v-model="addUserForm.username" placeholder="请输入用户名" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="email" label="邮箱" required>
              <a-input v-model="addUserForm.email" placeholder="请输入邮箱" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="password" label="密码" required>
              <a-input-password v-model="addUserForm.password" placeholder="请输入密码" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="confirmPassword" label="确认密码" required>
              <a-input-password v-model="addUserForm.confirmPassword" placeholder="请再次输入密码" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="first_name" label="名">
              <a-input v-model="addUserForm.first_name" placeholder="请输入名" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="last_name" label="姓">
              <a-input v-model="addUserForm.last_name" placeholder="请输入姓" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="is_staff" label=" ">
              <a-checkbox v-model="addUserForm.is_staff">管理员权限</a-checkbox>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="is_active" label=" ">
              <a-checkbox v-model="addUserForm.is_active" default-checked>启用账户</a-checkbox>
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-modal>

    <!-- 编辑用户模态框 -->
    <a-modal
      v-model:visible="editUserModalVisible"
      title="编辑用户"
      @cancel="cancelEditUser"
      @before-ok="handleEditUser"
      :mask-closable="false"
      :width="1000"
    >
      <a-tabs default-active-key="basic" @change="onEditUserTabChange">
        <a-tab-pane key="basic" title="基本信息">
          <a-form ref="editUserFormRef" :model="editUserForm" :rules="editUserRules" layout="vertical" :auto-label-width="false">
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item field="username" label="用户名">
                  <a-input v-model="editUserForm.username" placeholder="请输入用户名" disabled />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item field="email" label="邮箱">
                  <a-input v-model="editUserForm.email" placeholder="请输入邮箱" />
                </a-form-item>
              </a-col>
            </a-row>

            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item field="first_name" label="名">
                  <a-input v-model="editUserForm.first_name" placeholder="请输入名" />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item field="last_name" label="姓">
                  <a-input v-model="editUserForm.last_name" placeholder="请输入姓" />
                </a-form-item>
              </a-col>
            </a-row>

            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item field="is_staff" label=" ">
                  <a-checkbox v-model="editUserForm.is_staff">管理员权限</a-checkbox>
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item field="is_active" label=" ">
                  <a-checkbox v-model="editUserForm.is_active">启用账户</a-checkbox>
                </a-form-item>
              </a-col>
            </a-row>

            <a-divider>修改密码（可选）</a-divider>

            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item field="password" label="新密码">
                  <a-input-password v-model="editUserForm.password" placeholder="请输入新密码" allow-clear />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item field="confirmPassword" label="确认新密码">
                  <a-input-password v-model="editUserForm.confirmPassword" placeholder="请再次输入新密码" allow-clear />
                </a-form-item>
              </a-col>
            </a-row>
          </a-form>
        </a-tab-pane>
        
        <a-tab-pane key="permissions" title="权限管理">
          <permission-tree-selector
            v-if="editUserModalVisible && editUserForm.id"
            type="user"
            :id="editUserForm.id"
            lazy
            @refresh="refreshUserList"
          />
        </a-tab-pane>
      </a-tabs>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch, nextTick } from 'vue';
import { Message, Modal, Row as ARow, Col as ACol, Divider as ADivider } from '@arco-design/web-vue';
import {
  getUserList,
  createUser,
  deleteUser as deleteUserService,
  updateUser,
  type User,
  type CreateUserRequest,
  type UpdateUserRequest
} from '@/services/userService';
import PermissionTreeSelector from '@/components/permission/PermissionTreeSelector.vue';
import { useProjectStore } from '@/store/projectStore';

const projectStore = useProjectStore();

// 加载状态
const loading = ref(false);
// 搜索关键词
const searchKeyword = ref('');

// 表格列定义
const columns = [
  {
    title: '用户ID',
    dataIndex: 'id',
    width: 80,
  },
  {
    title: '用户名',
    dataIndex: 'username',
  },
  {
    title: '邮箱',
    dataIndex: 'email',
  },
  {
    title: '姓名',
    dataIndex: 'name',
    render: ({ record }: { record: User }) => {
      const fullName = [record.first_name, record.last_name].filter(Boolean).join(' ');
      return fullName || '-';
    },
  },
  {
    title: '管理员',
    dataIndex: 'is_staff',
    render: ({ record }: { record: User }) => record.is_staff ? '是' : '否',
  },
  {
    title: '账户状态',
    dataIndex: 'is_active',
    slotName: 'status',
  },
  {
    title: '操作',
    slotName: 'operations',
    width: 150,
  },
];

// 用户数据
const userData = ref<User[]>([]);

// 用户权限管理相关
const permissionsModalVisible = ref(false);
const selectedUserId = ref<number>(0);
const permissionTreeSelectorRef = ref<{ loadPermissions: () => Promise<void> } | null>(null);

// 查看用户权限
const viewUserPermissions = async (user: User) => {
  selectedUserId.value = user.id;
  permissionsModalVisible.value = true;
  
  // 等待模态框打开后再加载权限
  await nextTick();
  if (permissionTreeSelectorRef.value) {
    await permissionTreeSelectorRef.value.loadPermissions();
  }
};

// 刷新用户列表
const refreshUserList = () => {
  fetchUserList();
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

// 获取用户列表数据
const fetchUserList = async () => {
  loading.value = true;
  try {
    const response = await getUserList({
      page: pagination.current,
      pageSize: pagination.pageSize,
      search: searchKeyword.value
    });

    if (response.success && response.data) {
      userData.value = response.data;
      pagination.total = response.total || response.data.length;
    } else {
      Message.error(response.error || '获取用户列表失败');
      userData.value = [];
      pagination.total = 0;
    }
  } catch (error) {
    console.error('获取用户列表出错:', error);
    Message.error('获取用户列表时发生错误');
    userData.value = [];
    pagination.total = 0;
  } finally {
    loading.value = false;
  }
};

// 搜索用户
const onSearch = (value: string) => {
  searchKeyword.value = value;
  pagination.current = 1; // 重置到第一页
  fetchUserList();
};

// 分页变化
const onPageChange = (page: number) => {
  pagination.current = page;
  fetchUserList();
};

// 每页显示数量变化
const onPageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize;
  pagination.current = 1; // 重置到第一页
  fetchUserList();
};

// 监听项目变化，重新加载数据
watch(() => projectStore.currentProjectId, (newProjectId, oldProjectId) => {
  if (newProjectId !== oldProjectId) {
    // 项目切换时重置状态
    pagination.current = 1;
    searchKeyword.value = '';

    // 重新获取用户列表
    fetchUserList();
  }
}, { immediate: false });

// 在组件挂载时加载用户数据
onMounted(() => {
  fetchUserList();
});

// 添加用户模态框相关
const addUserModalVisible = ref(false);
const addUserFormRef = ref();
const addUserForm = reactive<CreateUserRequest & { confirmPassword: string }>({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  first_name: '',
  last_name: '',
  is_staff: false,
  is_active: true
});

// 表单验证规则
const addUserRules = {
  username: [
    { required: true, message: '请输入用户名' },
    { minLength: 3, message: '用户名长度不能小于3个字符' },
    { maxLength: 150, message: '用户名长度不能超过150个字符' }
  ],
  email: [
    { required: true, message: '请输入邮箱' },
    { type: 'email', message: '请输入有效的邮箱地址' }
  ],
  password: [
    { required: true, message: '请输入密码' },
    { minLength: 8, message: '密码长度不能小于8个字符' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码' },
    {
      validator: (value: string, callback: (error?: string) => void) => {
        if (value !== addUserForm.password) {
          callback('两次输入的密码不一致');
        } else {
          callback();
        }
      }
    }
  ]
};

// 显示添加用户模态框
const showAddUserModal = () => {
  // 重置表单
  Object.assign(addUserForm, {
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    first_name: '',
    last_name: '',
    is_staff: false,
    is_active: true
  });

  // 显示模态框
  addUserModalVisible.value = true;
};

// 取消添加用户
const cancelAddUser = () => {
  addUserModalVisible.value = false;
};

// 处理添加用户
const handleAddUser = async (done: (closed: boolean) => void) => {
  // 验证表单
  try {
    await addUserFormRef.value.validate();
    // 验证通过，继续处理
  } catch (errors) {
    // 表单验证失败
    console.error('表单验证失败:', errors);
    done(false); // 不关闭模态框
    return;
  }

  // 创建用户数据对象
  const userData: CreateUserRequest = {
    username: addUserForm.username,
    email: addUserForm.email,
    password: addUserForm.password,
    first_name: addUserForm.first_name,
    last_name: addUserForm.last_name,
    is_staff: addUserForm.is_staff,
    is_active: addUserForm.is_active
  };

  try {
    // 调用创建用户API
    const response = await createUser(userData);

    if (response.success) {
      Message.success('用户创建成功');
      // 刷新用户列表
      fetchUserList();
      done(true); // 关闭模态框
    } else {
      Message.error(response.error || '创建用户失败');
      done(false); // 不关闭模态框
    }
  } catch (error) {
    console.error('创建用户出错:', error);
    Message.error('创建用户时发生错误');
    done(false); // 不关闭模态框
  }
};

// 编辑用户模态框相关
const editUserModalVisible = ref(false);
const editUserFormRef = ref();
const editUserForm = reactive<UpdateUserRequest & { confirmPassword: string, id: number }>({
  id: 0,
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  first_name: '',
  last_name: '',
  is_staff: false,
  is_active: true
});

// 编辑用户表单验证规则
const editUserRules = {
  email: [
    { type: 'email', message: '请输入有效的邮箱地址' }
  ],
  confirmPassword: [
    {
      validator: (value: string, callback: (error?: string) => void) => {
        if (value && value !== editUserForm.password) {
          callback('两次输入的密码不一致');
        } else {
          callback();
        }
      }
    }
  ]
};

// 显示编辑用户模态框
// Tab change handler for edit user modal
const onEditUserTabChange = async (key: string) => {
  if (key === 'permissions' && editUserForm.id) {
    await nextTick()
    permissionTreeSelectorRef.value?.loadPermissions(editUserForm.id)
  }
}

const editUser = async (user: User) => {
  // 设置表单数据
  Object.assign(editUserForm, {
    id: user.id,
    username: user.username,
    email: user.email,
    password: '',
    confirmPassword: '',
    first_name: user.first_name || '',
    last_name: user.last_name || '',
    is_staff: user.is_staff,
    is_active: user.is_active
  });

  // 显示模态框，不立即加载权限
  editUserModalVisible.value = true;
};

// 取消编辑用户
const cancelEditUser = () => {
  editUserModalVisible.value = false;
};

// 处理编辑用户
const handleEditUser = async (done: (closed: boolean) => void) => {
  // 验证表单
  try {
    await editUserFormRef.value.validate();
    // 验证通过，继续处理
  } catch (errors) {
    // 表单验证失败
    console.error('表单验证失败:', errors);
    done(false); // 不关闭模态框
    return;
  }

  // 创建更新数据对象
  const updateData: UpdateUserRequest = {};

  // 只包含已修改的字段
  if (editUserForm.email) updateData.email = editUserForm.email;
  if (editUserForm.first_name !== undefined) updateData.first_name = editUserForm.first_name;
  if (editUserForm.last_name !== undefined) updateData.last_name = editUserForm.last_name;
  if (editUserForm.is_staff !== undefined) updateData.is_staff = editUserForm.is_staff;
  if (editUserForm.is_active !== undefined) updateData.is_active = editUserForm.is_active;

  // 如果输入了密码，则包含密码字段
  if (editUserForm.password) {
    updateData.password = editUserForm.password;
  }

  try {
    // 调用更新用户API
    const response = await updateUser(editUserForm.id, updateData);

    if (response.success) {
      Message.success('用户更新成功');
      // 刷新用户列表
      fetchUserList();
      done(true); // 关闭模态框
    } else {
      Message.error(response.error || '更新用户失败');
      done(false); // 不关闭模态框
    }
  } catch (error) {
    console.error('更新用户出错:', error);
    Message.error('更新用户时发生错误');
    done(false); // 不关闭模态框
  }
};

// 删除用户
const deleteUser = (user: User) => {
  Modal.warning({
    title: '确认删除',
    content: `确定要删除用户 "${user.username}" 吗？此操作不可恢复。`,
    okText: '确定删除',
    cancelText: '取消',
    onOk: async () => {
      try {
        const response = await deleteUserService(user.id);

        if (response.success) {
          Message.success(response.message || '用户删除成功');
          // 刷新用户列表
          fetchUserList();
        } else {
          Message.error(response.error || '删除用户失败');
        }
      } catch (error) {
        console.error('删除用户出错:', error);
        Message.error('删除用户时发生错误');
      }
    }
  });
};
</script>

<style scoped>
.user-management {
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
</style>
