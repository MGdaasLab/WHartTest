<template>
  <div class="user-management">
    <div class="page-header">
      <div class="search-box">
        <a-input-search
          :placeholder="pageText.searchPlaceholder"
          allow-clear
          style="width: 300px"
          @search="onSearch"
        />
      </div>
      <div class="action-buttons">
        <a-button type="primary" @click="showAddUserModal">{{ pageText.addUser }}</a-button>
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
          {{ record.is_active ? pageText.enabled : pageText.disabled }}
        </a-tag>
      </template>
      <template #operations="{ record }">
        <a-space :size="4">
          <a-button type="primary" size="mini" @click="viewUserPermissions(record)">{{ pageText.permissions }}</a-button>
          <a-button type="primary" size="mini" @click="editUser(record)">{{ pageText.edit }}</a-button>
          <a-button type="primary" status="danger" size="mini" @click="deleteUser(record)">{{ pageText.delete }}</a-button>
        </a-space>
      </template>
    </a-table>

    <!-- 用户权限管理模态框 -->
    <a-modal
      v-model:visible="permissionsModalVisible"
      :title="pageText.userPermissionsTitle"
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
      :title="pageText.addUserTitle"
      @cancel="cancelAddUser"
      @before-ok="handleAddUser"
      :mask-closable="false"
      :width="600"
    >
      <a-form ref="addUserFormRef" :model="addUserForm" :rules="addUserRules" layout="vertical" :auto-label-width="false">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="username" :label="pageText.username" required>
              <a-input v-model="addUserForm.username" :placeholder="pageText.enterUsername" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="email" :label="pageText.email" required>
              <a-input v-model="addUserForm.email" :placeholder="pageText.enterEmail" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="password" :label="pageText.password" required>
              <a-input-password v-model="addUserForm.password" :placeholder="pageText.enterPassword" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="confirmPassword" :label="pageText.confirmPassword" required>
              <a-input-password v-model="addUserForm.confirmPassword" :placeholder="pageText.enterConfirmPassword" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="first_name" :label="pageText.firstName">
              <a-input v-model="addUserForm.first_name" :placeholder="pageText.enterFirstName" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="last_name" :label="pageText.lastName">
              <a-input v-model="addUserForm.last_name" :placeholder="pageText.enterLastName" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="is_staff" label=" ">
              <a-checkbox v-model="addUserForm.is_staff">{{ pageText.adminPrivileges }}</a-checkbox>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="is_active" label=" ">
              <a-checkbox v-model="addUserForm.is_active" default-checked>{{ pageText.enableAccount }}</a-checkbox>
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-modal>

    <!-- 编辑用户模态框 -->
    <a-modal
      v-model:visible="editUserModalVisible"
      :title="pageText.editUserTitle"
      @cancel="cancelEditUser"
      @before-ok="handleEditUser"
      :mask-closable="false"
      :width="1000"
    >
      <a-form ref="editUserFormRef" :model="editUserForm" :rules="editUserRules" layout="vertical" :auto-label-width="false">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="username" :label="pageText.username">
              <a-input v-model="editUserForm.username" :placeholder="pageText.enterUsername" disabled />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="email" :label="pageText.email">
              <a-input v-model="editUserForm.email" :placeholder="pageText.enterEmail" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="first_name" :label="pageText.firstName">
              <a-input v-model="editUserForm.first_name" :placeholder="pageText.enterFirstName" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="last_name" :label="pageText.lastName">
              <a-input v-model="editUserForm.last_name" :placeholder="pageText.enterLastName" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="is_staff" label=" ">
              <a-checkbox v-model="editUserForm.is_staff">{{ pageText.adminPrivileges }}</a-checkbox>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="is_active" label=" ">
              <a-checkbox v-model="editUserForm.is_active">{{ pageText.enableAccount }}</a-checkbox>
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider>{{ pageText.changePasswordOptional }}</a-divider>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item field="password" :label="pageText.newPassword">
              <a-input-password v-model="editUserForm.password" :placeholder="pageText.enterNewPassword" allow-clear />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item field="confirmPassword" :label="pageText.confirmNewPassword">
              <a-input-password v-model="editUserForm.confirmPassword" :placeholder="pageText.enterConfirmNewPassword" allow-clear />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch, nextTick, computed } from 'vue';
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
import { useAppI18n } from '@/composables/useAppI18n';
import { useProjectStore } from '@/store/projectStore';

const projectStore = useProjectStore();
const { isEnglish } = useAppI18n();

const pageText = computed(() => (
  isEnglish.value
    ? {
        searchPlaceholder: 'Search username/email',
        addUser: 'Add user',
        enabled: 'Enabled',
        disabled: 'Disabled',
        permissions: 'Permissions',
        edit: 'Edit',
        delete: 'Delete',
        userPermissionsTitle: 'User permissions',
        addUserTitle: 'Add user',
        editUserTitle: 'Edit user',
        username: 'Username',
        email: 'Email',
        password: 'Password',
        confirmPassword: 'Confirm password',
        firstName: 'First name',
        lastName: 'Last name',
        adminPrivileges: 'Admin privileges',
        enableAccount: 'Enable account',
        changePasswordOptional: 'Change password (optional)',
        newPassword: 'New password',
        confirmNewPassword: 'Confirm new password',
        enterUsername: 'Enter username',
        enterEmail: 'Enter email',
        enterPassword: 'Enter password',
        enterConfirmPassword: 'Enter the password again',
        enterFirstName: 'Enter first name',
        enterLastName: 'Enter last name',
        enterNewPassword: 'Enter a new password',
        enterConfirmNewPassword: 'Enter the new password again',
        userId: 'User ID',
        fullName: 'Full name',
        admin: 'Admin',
        yes: 'Yes',
        no: 'No',
        accountStatus: 'Account status',
        actions: 'Actions',
        fetchUserListFailed: 'Failed to fetch user list',
        fetchUserListError: 'An error occurred while fetching the user list',
        usernameRequired: 'Enter username',
        usernameMinLength: 'Username must be at least 3 characters',
        usernameMaxLength: 'Username cannot exceed 150 characters',
        emailRequired: 'Enter email',
        emailInvalid: 'Enter a valid email address',
        passwordRequired: 'Enter password',
        passwordMinLength: 'Password must be at least 8 characters',
        confirmPasswordRequired: 'Confirm the password',
        passwordMismatch: 'The two passwords do not match',
        createUserSuccess: 'User created successfully',
        createUserFailed: 'Failed to create user',
        createUserError: 'An error occurred while creating the user',
        updateUserSuccess: 'User updated successfully',
        updateUserFailed: 'Failed to update user',
        updateUserError: 'An error occurred while updating the user',
        deleteConfirmTitle: 'Confirm deletion',
        deleteConfirmContent: (name: string) => `Delete user "${name}"? This action cannot be undone.`,
        deleteConfirmOk: 'Delete',
        deleteUserSuccess: 'User deleted successfully',
        deleteUserFailed: 'Failed to delete user',
        deleteUserError: 'An error occurred while deleting the user',
      }
    : {
        searchPlaceholder: '搜索用户名/邮箱',
        addUser: '添加用户',
        enabled: '启用',
        disabled: '禁用',
        permissions: '权限',
        edit: '编辑',
        delete: '删除',
        userPermissionsTitle: '用户权限管理',
        addUserTitle: '添加用户',
        editUserTitle: '编辑用户',
        username: '用户名',
        email: '邮箱',
        password: '密码',
        confirmPassword: '确认密码',
        firstName: '名',
        lastName: '姓',
        adminPrivileges: '管理员权限',
        enableAccount: '启用账户',
        changePasswordOptional: '修改密码（可选）',
        newPassword: '新密码',
        confirmNewPassword: '确认新密码',
        enterUsername: '请输入用户名',
        enterEmail: '请输入邮箱',
        enterPassword: '请输入密码',
        enterConfirmPassword: '请再次输入密码',
        enterFirstName: '请输入名',
        enterLastName: '请输入姓',
        enterNewPassword: '请输入新密码',
        enterConfirmNewPassword: '请再次输入新密码',
        userId: '用户ID',
        fullName: '姓名',
        admin: '管理员',
        yes: '是',
        no: '否',
        accountStatus: '账户状态',
        actions: '操作',
        fetchUserListFailed: '获取用户列表失败',
        fetchUserListError: '获取用户列表时发生错误',
        usernameRequired: '请输入用户名',
        usernameMinLength: '用户名长度不能小于3个字符',
        usernameMaxLength: '用户名长度不能超过150个字符',
        emailRequired: '请输入邮箱',
        emailInvalid: '请输入有效的邮箱地址',
        passwordRequired: '请输入密码',
        passwordMinLength: '密码长度不能小于8个字符',
        confirmPasswordRequired: '请确认密码',
        passwordMismatch: '两次输入的密码不一致',
        createUserSuccess: '用户创建成功',
        createUserFailed: '创建用户失败',
        createUserError: '创建用户时发生错误',
        updateUserSuccess: '用户更新成功',
        updateUserFailed: '更新用户失败',
        updateUserError: '更新用户时发生错误',
        deleteConfirmTitle: '确认删除',
        deleteConfirmContent: (name: string) => `确定要删除用户 "${name}" 吗？此操作不可恢复。`,
        deleteConfirmOk: '确定删除',
        deleteUserSuccess: '用户删除成功',
        deleteUserFailed: '删除用户失败',
        deleteUserError: '删除用户时发生错误',
      }
));

// 加载状态
const loading = ref(false);
// 搜索关键词
const searchKeyword = ref('');

// 表格列定义
const columns = computed(() => [
  {
    title: pageText.value.userId,
    dataIndex: 'id',
    width: 80,
    align: 'center',
  },
  {
    title: pageText.value.username,
    dataIndex: 'username',
    align: 'center',
  },
  {
    title: pageText.value.email,
    dataIndex: 'email',
    align: 'center',
  },
  {
    title: pageText.value.fullName,
    dataIndex: 'name',
    align: 'center',
    render: ({ record }: { record: User }) => {
      const fullName = [record.first_name, record.last_name].filter(Boolean).join(' ');
      return fullName || '-';
    },
  },
  {
    title: pageText.value.admin,
    dataIndex: 'is_staff',
    align: 'center',
    render: ({ record }: { record: User }) => record.is_staff ? pageText.value.yes : pageText.value.no,
  },
  {
    title: pageText.value.accountStatus,
    dataIndex: 'is_active',
    slotName: 'status',
    align: 'center',
  },
  {
    title: pageText.value.actions,
    slotName: 'operations',
    width: 180,
    fixed: 'right',
    align: 'center',
  },
]);

// 用户数据
const userData = ref<User[]>([]);

// 用户权限管理相关
const permissionsModalVisible = ref(false);
const selectedUserId = ref<number>(0);
const permissionTreeSelectorRef = ref<{ loadPermissions: (userId?: number) => Promise<void> } | null>(null);

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
      Message.error(response.error || pageText.value.fetchUserListFailed);
      userData.value = [];
      pagination.total = 0;
    }
  } catch (error) {
    console.error('获取用户列表出错:', error);
    Message.error(pageText.value.fetchUserListError);
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
const addUserRules = computed(() => ({
  username: [
    { required: true, message: pageText.value.usernameRequired },
    { minLength: 3, message: pageText.value.usernameMinLength },
    { maxLength: 150, message: pageText.value.usernameMaxLength }
  ],
  email: [
    { required: true, message: pageText.value.emailRequired },
    { type: 'email', message: pageText.value.emailInvalid }
  ],
  password: [
    { required: true, message: pageText.value.passwordRequired },
    { minLength: 8, message: pageText.value.passwordMinLength }
  ],
  confirmPassword: [
    { required: true, message: pageText.value.confirmPasswordRequired },
    {
      validator: (value: string, callback: (error?: string) => void) => {
        if (value !== addUserForm.password) {
          callback(pageText.value.passwordMismatch);
        } else {
          callback();
        }
      }
    }
  ]
}));

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
      Message.success(pageText.value.createUserSuccess);
      // 刷新用户列表
      fetchUserList();
      done(true); // 关闭模态框
    } else {
      Message.error(response.error || pageText.value.createUserFailed);
      done(false); // 不关闭模态框
    }
  } catch (error) {
    console.error('创建用户出错:', error);
    Message.error(pageText.value.createUserError);
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
const editUserRules = computed(() => ({
  email: [
    { type: 'email', message: pageText.value.emailInvalid }
  ],
  confirmPassword: [
    {
      validator: (value: string, callback: (error?: string) => void) => {
        if (value && value !== editUserForm.password) {
          callback(pageText.value.passwordMismatch);
        } else {
          callback();
        }
      }
    }
  ]
}));

// 显示编辑用户模态框
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

  // 显示模态框
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
      Message.success(pageText.value.updateUserSuccess);
      // 刷新用户列表
      fetchUserList();
      done(true); // 关闭模态框
    } else {
      Message.error(response.error || pageText.value.updateUserFailed);
      done(false); // 不关闭模态框
    }
  } catch (error) {
    console.error('更新用户出错:', error);
    Message.error(pageText.value.updateUserError);
    done(false); // 不关闭模态框
  }
};

// 删除用户
const deleteUser = (user: User) => {
  Modal.warning({
    title: pageText.value.deleteConfirmTitle,
    content: pageText.value.deleteConfirmContent(user.username),
    okText: pageText.value.deleteConfirmOk,
    onOk: async () => {
      try {
        const response = await deleteUserService(user.id);

        if (response.success) {
          Message.success(response.message || pageText.value.deleteUserSuccess);
          // 刷新用户列表
          fetchUserList();
        } else {
          Message.error(response.error || pageText.value.deleteUserFailed);
        }
      } catch (error) {
        console.error('删除用户出错:', error);
        Message.error(pageText.value.deleteUserError);
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
