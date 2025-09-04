<template>
  <div class="project-management">
    <!-- 无项目权限时显示提示 -->
    <div v-if="!hasProjectPermission" class="no-permission-panel">
      <div class="no-permission-content">
        <div class="icon-container">
          <svg class="permission-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" fill="#f5222d"/>
          </svg>
        </div>
        <h3>访问受限</h3>
        <p>您当前没有项目管理权限，请联系系统管理员申请相应权限。</p>
        <a-button type="primary" @click="contactAdmin">联系管理员</a-button>
      </div>
    </div>

    <!-- 有权限时显示正常内容 -->
    <div v-else>
      <div class="page-header">
        <div class="search-box">
          <a-input-search
            placeholder="搜索项目名称/描述"
            allow-clear
            style="width: 300px"
            @search="onSearch"
          />
        </div>
        <div class="action-buttons">
          <a-button type="primary" @click="showAddProjectModal">添加项目</a-button>
        </div>
      </div>

      <a-table
        :columns="columns"
        :data="projectData"
        :pagination="pagination"
        :loading="loading"
        :scroll="{ x: 900 }"
        @page-change="onPageChange"
        @page-size-change="onPageSizeChange"
        @row-click="handleRowClick"
      >
        <template #name="{ record }">
          <a-tooltip :content="record.name" position="top">
            <div class="ellipsis-text">{{ record.name }}</div>
          </a-tooltip>
        </template>
        <template #description="{ record }">
          <a-tooltip :content="record.description || '无描述'" position="top">
            <div class="ellipsis-text">{{ record.description || '无描述' }}</div>
          </a-tooltip>
        </template>
        <template #operations="{ record }">
          <a-space>
            <a-button type="primary" size="small" @click="viewProjectMembers(record, $event)">成员</a-button>
            <a-button type="primary" size="small" @click="editProject(record, $event)">编辑</a-button>
            <a-button type="primary" status="danger" size="small" @click="deleteProject(record, $event)">删除</a-button>
          </a-space>
        </template>
      </a-table>
    </div>

    <!-- 项目成员管理模态框 -->
    <a-modal
      v-model:visible="membersModalVisible"
      :title="`项目成员管理: ${selectedProject?.name || ''}`"
      :footer="false"
      :mask-closable="true"
      :width="900"
    >
      <div v-if="membersLoading" class="loading-container">
        <a-spin />
      </div>
      <div v-else>
        <div class="members-header">
          <a-button type="primary" @click="showAddMemberModal">添加成员</a-button>
        </div>
        <div v-if="projectMembers.length === 0" class="no-data">
          暂无成员数据
        </div>
        <a-table v-else :columns="memberColumns" :data="projectMembers" :pagination="false" row-key="id">
          <template #role="{ record }">
            <a-tag :color="record.role === 'owner' ? 'red' : record.role === 'admin' ? 'orange' : 'blue'">
              {{ record.role === 'owner' ? '拥有者' : record.role === 'admin' ? '管理员' : '成员' }}
            </a-tag>
          </template>
          <template #joined_at="{ record }">
            {{ record.joined_at ? new Date(record.joined_at).toLocaleString() : '-' }}
          </template>
          <template #operations="{ record }">
            <a-space>
              <a-button
                type="text"
                @click="showUpdateRoleModal(record)"
                :disabled="record.role === 'owner'"
              >
                修改角色
              </a-button>
              <a-button
                type="text"
                status="danger"
                @click="removeMember(record)"
                :disabled="record.role === 'owner'"
              >
                移除
              </a-button>
            </a-space>
          </template>
        </a-table>

      </div>
    </a-modal>

    <!-- 添加成员模态框 -->
    <a-modal
      v-model:visible="addMemberModalVisible"
      title="添加项目成员"
      @ok="handleAddMember"
      @cancel="() => addMemberModalVisible = false"
      :mask-closable="false"
    >
      <a-form :model="addMemberForm" layout="vertical">
        <a-form-item field="userId" label="选择用户" required>
          <a-select
            v-model="addMemberForm.userId"
            placeholder="请选择用户"
            :loading="usersLoading"
            :filter-option="true"
          >
            <a-option
              v-for="user in availableUsers"
              :key="user.value"
              :value="user.value"
              :label="user.label"
            />
          </a-select>
        </a-form-item>
        <a-form-item field="role" label="角色" required>
          <a-select v-model="addMemberForm.role" placeholder="请选择角色">
            <a-option value="member">成员</a-option>
            <a-option value="admin">管理员</a-option>
            <a-option value="owner">拥有者</a-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 更新角色模态框 -->
    <a-modal
      v-model:visible="updateRoleModalVisible"
      title="更新成员角色"
      @ok="handleUpdateRole"
      @cancel="() => updateRoleModalVisible = false"
      :mask-closable="false"
    >
      <a-form :model="updateRoleForm" layout="vertical">
        <a-form-item field="role" label="角色" required>
          <a-select v-model="updateRoleForm.role" placeholder="请选择角色">
            <a-option value="member">成员</a-option>
            <a-option value="admin">管理员</a-option>
            <a-option value="owner">拥有者</a-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 添加项目模态框 -->
    <a-modal
      v-model:visible="addProjectModalVisible"
      title="添加项目"
      @ok="handleAddProject"
      @cancel="cancelAddProject"
      :mask-closable="false"
    >
      <a-form
        ref="addProjectFormRef"
        :model="addProjectForm"
        :rules="addProjectRules"
        layout="vertical"
      >
        <a-form-item field="name" label="项目名称">
          <a-input v-model="addProjectForm.name" placeholder="请输入项目名称" />
        </a-form-item>
        <a-form-item field="description" label="项目描述">
          <a-textarea
            v-model="addProjectForm.description"
            placeholder="请输入项目描述"
            :auto-size="{ minRows: 3, maxRows: 5 }"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 编辑项目模态框 -->
    <a-modal
      v-model:visible="editProjectModalVisible"
      title="编辑项目"
      @ok="handleEditProject"
      @cancel="cancelEditProject"
      :mask-closable="false"
    >
      <a-form
        ref="editProjectFormRef"
        :model="editProjectForm"
        :rules="editProjectRules"
        layout="vertical"
      >
        <a-form-item field="name" label="项目名称">
          <a-input v-model="editProjectForm.name" placeholder="请输入项目名称" />
        </a-form-item>
        <a-form-item field="description" label="项目描述">
          <a-textarea
            v-model="editProjectForm.description"
            placeholder="请输入项目描述"
            :auto-size="{ minRows: 3, maxRows: 5 }"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue';
import { Message, Modal } from '@arco-design/web-vue';
import {
  getProjectList,
  createProject,
  deleteProject as deleteProjectService,
  updateProject,
  getProjectDetail,
  getProjectMembers,
  addProjectMember,
  removeProjectMember,
  updateProjectMemberRole,
  type Project,
  type ProjectMember,
  type CreateProjectRequest,
  type UpdateProjectRequest
} from '@/services/projectService';
import { getUserList, type User } from '@/services/userService';
import { useAuthStore } from '@/store/authStore';

// 加载状态
const loading = ref(false);
// 搜索关键词
const searchKeyword = ref('');

// 权限检查
const authStore = useAuthStore();
const hasProjectPermission = ref(false); // 默认无权限，等待权限检查结果

// 简单的权限检查逻辑
const checkProjectPermission = () => {
  // 如果用户未登录，则无权限
  if (!authStore.isAuthenticated || !authStore.user) {
    hasProjectPermission.value = false;
    return;
  }
  
  // 如果是管理员，拥有所有权限
  if (authStore.user?.is_staff) {
    hasProjectPermission.value = true;
    return;
  }
  
  // 检查是否有项目相关权限
  const projectPermissions = [
    'projects.view_project',
    'projects.add_project',  
    'projects.change_project',
    'projects.delete_project'
  ];
  
  // 使用authStore的hasPermission方法检查权限
  hasProjectPermission.value = projectPermissions.some(permission =>
    authStore.hasPermission(permission)
  );
};

// 联系管理员
const contactAdmin = () => {
  Message.info('请联系系统管理员获取项目管理权限，邮箱：admin@example.com');
};

// 表格列定义
const columns = [
  {
    title: '项目ID',
    dataIndex: 'id',
    width: 80,
  },
  {
    title: '项目名称',
    dataIndex: 'name',
    slotName: 'name',
    width: 200,
  },
  {
    title: '项目描述',
    dataIndex: 'description',
    slotName: 'description',
    width: 300,
  },
  {
    title: '创建者',
    dataIndex: 'creator_detail',
    render: ({ record }) => {
      return record.creator_detail?.username || '-';
    }
  },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    render: ({ record }) => {
      const date = new Date(record.created_at);
      return date.toLocaleString();
    }
  },
  {
    title: '操作',
    slotName: 'operations',
    width: 150,
  },
];

// 项目数据
const projectData = ref<Project[]>([]);

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

// 获取项目列表
const fetchProjectList = async () => {
  loading.value = true;
  try {
    const response = await getProjectList({
      page: pagination.current,
      pageSize: pagination.pageSize,
      search: searchKeyword.value,
    });

    if (response.success && response.data) {
      projectData.value = response.data;
      pagination.total = response.total || response.data.length;
    } else {
      Message.error(response.error || '获取项目列表失败');
      projectData.value = [];
      pagination.total = 0;
    }
  } catch (error) {
    console.error('获取项目列表出错:', error);
    Message.error('获取项目列表时发生错误');
    projectData.value = [];
    pagination.total = 0;
  } finally {
    loading.value = false;
  }
};

// 搜索项目
const onSearch = (value: string) => {
  searchKeyword.value = value;
  pagination.current = 1; // 重置到第一页
  fetchProjectList();
};

// 分页变化
const onPageChange = (page: number) => {
  pagination.current = page;
  fetchProjectList();
};

// 每页显示数量变化
const onPageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize;
  pagination.current = 1; // 重置到第一页
  fetchProjectList();
};

// 在组件挂载时检查权限并加载项目数据
onMounted(() => {
  checkProjectPermission();
  fetchProjectList();
});

// 监听认证状态变化
watch(() => authStore.isAuthenticated, () => {
  checkProjectPermission();
}, { immediate: true });

// 监听用户权限变化
watch(() => authStore.userPermissions, () => {
  checkProjectPermission();
}, { deep: true });

// 处理行点击事件
const handleRowClick = (record: Project) => {
  console.log('点击了项目:', record);
  // 查看项目详情
  viewProjectDetail(record);
};

// 项目成员管理相关
const membersModalVisible = ref(false);
const membersLoading = ref(false);
const selectedProject = ref<Project | null>(null);
const projectMembers = ref<ProjectMember[]>([]);

// 项目成员表格列定义
const memberColumns = [
  {
    title: '用户ID',
    dataIndex: 'user',
  },
  {
    title: '用户名',
    dataIndex: 'user_detail.username',
  },
  {
    title: '邮箱',
    dataIndex: 'user_detail.email',
  },
  {
    title: '角色',
    dataIndex: 'role',
    slotName: 'role',
  },
  {
    title: '加入时间',
    dataIndex: 'joined_at',
    slotName: 'joined_at',
  },
  {
    title: '操作',
    slotName: 'operations',
  }
];

// 监听项目成员数据变化
watch(projectMembers, (newValue) => {
  // 成员数据已更新
}, { deep: true });

// 查看项目详情
const viewProjectDetail = async (project: Project) => {
  try {
    const response = await getProjectDetail(project.id);
    if (response.success && response.data) {
      console.log('项目详情:', response.data);
      // 可以在这里添加更多处理逻辑
    } else {
      Message.error(response.error || '获取项目详情失败');
    }
  } catch (error) {
    console.error('获取项目详情出错:', error);
    Message.error('获取项目详情时发生错误');
  }
};

// 查看项目成员
const viewProjectMembers = async (project: Project, event?: Event) => {
  // 阻止事件冒泡，避免触发行点击事件
  if (event) {
    event.stopPropagation();
  }

  selectedProject.value = project;
  membersModalVisible.value = true;
  await fetchProjectMembers(project.id);
};

// 获取项目成员列表
const fetchProjectMembers = async (projectId: number) => {
  membersLoading.value = true;
  try {
    const response = await getProjectMembers(projectId);
    if (response.success && response.data) {

      projectMembers.value = response.data;
    } else {
      Message.error(response.error || '获取项目成员列表失败');
      projectMembers.value = [];
    }
  } catch (error) {
    console.error('获取项目成员列表出错:', error);
    Message.error('获取项目成员列表时发生错误');
    projectMembers.value = [];
  } finally {
    membersLoading.value = false;
  }
};

// 添加成员模态框相关
const addMemberModalVisible = ref(false);
const addMemberForm = reactive({
  userId: undefined as number | undefined,
  role: 'member' as string
});
const availableUsers = ref<{ label: string; value: number }[]>([]);
const usersLoading = ref(false);

// 显示添加成员模态框
const showAddMemberModal = () => {
  addMemberForm.userId = undefined;
  addMemberForm.role = 'member';
  addMemberModalVisible.value = true;
  fetchAvailableUsers();
};

// 获取可用用户列表
const fetchAvailableUsers = async () => {
  usersLoading.value = true;
  try {
    const response = await getUserList({
      page: 1,
      pageSize: 100, // 获取较多用户
    });

    if (response.success && response.data) {
      // 过滤掉已经是项目成员的用户
      const memberUserIds = projectMembers.value.map(member => member.user);
      const filteredUsers = response.data.filter(user => !memberUserIds.includes(user.id));

      // 转换为下拉选择框需要的格式
      availableUsers.value = filteredUsers.map(user => ({
        label: `${user.username} (${user.email || ''})`,
        value: user.id
      }));
    } else {
      Message.error(response.error || '获取用户列表失败');
      availableUsers.value = [];
    }
  } catch (error) {
    console.error('获取用户列表出错:', error);
    Message.error('获取用户列表时发生错误');
    availableUsers.value = [];
  } finally {
    usersLoading.value = false;
  }
};

// 处理添加成员
const handleAddMember = async () => {
  if (!selectedProject.value) {
    Message.error('未选择项目');
    return;
  }

  if (!addMemberForm.userId) {
    Message.error('请选择用户');
    return;
  }

  try {
    const response = await addProjectMember(
      selectedProject.value.id,
      addMemberForm.userId,
      addMemberForm.role
    );

    if (response.success) {
      Message.success('成员添加成功');
      addMemberModalVisible.value = false;
      // 刷新成员列表
      await fetchProjectMembers(selectedProject.value.id);
    } else {
      Message.error(response.error || '添加成员失败');
    }
  } catch (error) {
    console.error('添加成员出错:', error);
    Message.error('添加成员时发生错误');
  }
};

// 移除成员
const removeMember = (member: ProjectMember) => {
  if (!selectedProject.value) {
    Message.error('未选择项目');
    return;
  }



  Modal.warning({
    title: '确认移除',
    content: `确定要移除成员 "${member.user_detail?.username || ''}" 吗？`,
    okText: '确认',
    cancelText: '取消',
    onOk: async () => {
      try {
        const response = await removeProjectMember(selectedProject.value!.id, member.user);

        if (response.success) {
          Message.success('成员移除成功');
          // 刷新成员列表
          await fetchProjectMembers(selectedProject.value!.id);
        } else {
          Message.error(response.error || '移除成员失败');
        }
      } catch (error) {
        console.error('移除成员出错:', error);
        Message.error('移除成员时发生错误');
      }
    }
  });
};

// 更新成员角色模态框相关
const updateRoleModalVisible = ref(false);
const selectedMember = ref<ProjectMember | null>(null);
const updateRoleForm = reactive({
  role: ''
});

// 显示更新角色模态框
const showUpdateRoleModal = (member: ProjectMember) => {
  selectedMember.value = member;
  updateRoleForm.role = member.role;
  updateRoleModalVisible.value = true;
};

// 处理更新角色
const handleUpdateRole = async () => {
  if (!selectedProject.value || !selectedMember.value) {
    Message.error('未选择项目或成员');
    return;
  }

  try {
    const response = await updateProjectMemberRole(
      selectedProject.value.id,
      selectedMember.value.user,
      updateRoleForm.role
    );

    if (response.success) {
      Message.success('角色更新成功');
      updateRoleModalVisible.value = false;
      // 刷新成员列表
      await fetchProjectMembers(selectedProject.value.id);
    } else {
      Message.error(response.error || '更新角色失败');
    }
  } catch (error) {
    console.error('更新角色出错:', error);
    Message.error('更新角色时发生错误');
  }
};

// 添加项目模态框相关
const addProjectModalVisible = ref(false);
const addProjectFormRef = ref();
const addProjectForm = reactive<CreateProjectRequest>({
  name: '',
  description: ''
});

// 添加项目表单验证规则
const addProjectRules = {
  name: [
    { required: true, message: '请输入项目名称' },
    { maxLength: 100, message: '项目名称长度不能超过100个字符' }
  ],
  description: [
    { maxLength: 500, message: '项目描述长度不能超过500个字符' }
  ]
};

// 显示添加项目模态框
const showAddProjectModal = () => {
  // 重置表单
  addProjectForm.name = '';
  addProjectForm.description = '';
  // 显示模态框
  addProjectModalVisible.value = true;
};

// 取消添加项目
const cancelAddProject = () => {
  addProjectModalVisible.value = false;
};

// 处理添加项目
const handleAddProject = async () => {
  // 验证表单
  try {
    await addProjectFormRef.value.validate();
    // 验证通过，继续处理
  } catch (errors) {
    // 表单验证失败
    console.error('表单验证失败:', errors);
    return;
  }

  // 创建项目数据对象
  const projectData: CreateProjectRequest = {
    name: addProjectForm.name,
    description: addProjectForm.description
  };

  try {
    // 调用创建项目API
    const response = await createProject(projectData);

    if (response.success) {
      Message.success('项目创建成功');
      // 刷新项目列表
      fetchProjectList();
      // 关闭模态框
      addProjectModalVisible.value = false;
    } else {
      Message.error(response.error || '创建项目失败');
    }
  } catch (error) {
    console.error('创建项目出错:', error);
    Message.error('创建项目时发生错误');
  }
};

// 编辑项目模态框相关
const editProjectModalVisible = ref(false);
const editProjectFormRef = ref();
const editProjectForm = reactive<UpdateProjectRequest & { id: number }>({
  id: 0,
  name: '',
  description: ''
});

// 编辑项目表单验证规则
const editProjectRules = {
  name: [
    { required: true, message: '请输入项目名称' },
    { maxLength: 100, message: '项目名称长度不能超过100个字符' }
  ],
  description: [
    { maxLength: 500, message: '项目描述长度不能超过500个字符' }
  ]
};

// 显示编辑项目模态框
const editProject = (project: Project, event?: Event) => {
  // 阻止事件冒泡，避免触发行点击事件
  if (event) {
    event.stopPropagation();
  }
  // 设置表单数据
  Object.assign(editProjectForm, {
    id: project.id,
    name: project.name,
    description: project.description
  });

  // 显示模态框
  editProjectModalVisible.value = true;
};

// 取消编辑项目
const cancelEditProject = () => {
  editProjectModalVisible.value = false;
};

// 处理编辑项目
const handleEditProject = async () => {
  // 验证表单
  try {
    await editProjectFormRef.value.validate();
    // 验证通过，继续处理
  } catch (errors) {
    // 表单验证失败
    console.error('表单验证失败:', errors);
    return;
  }

  // 更新项目数据对象
  const projectData: UpdateProjectRequest = {
    name: editProjectForm.name,
    description: editProjectForm.description
  };

  try {
    // 调用更新项目API
    const response = await updateProject(editProjectForm.id, projectData);

    if (response.success) {
      Message.success('项目更新成功');
      // 刷新项目列表
      fetchProjectList();
      // 关闭模态框
      editProjectModalVisible.value = false;
    } else {
      Message.error(response.error || '更新项目失败');
    }
  } catch (error) {
    console.error('更新项目出错:', error);
    Message.error('更新项目时发生错误');
  }
};

// 删除项目
const deleteProject = (project: Project, event?: Event) => {
  // 阻止事件冒泡，避免触发行点击事件
  if (event) {
    event.stopPropagation();
  }

  Modal.warning({
    title: '确认删除',
    content: `确定要删除项目 "${project.name}" 吗？此操作不可恢复。`,
    okText: '确认',
    cancelText: '取消',
    onOk: async () => {
      try {
        const response = await deleteProjectService(project.id);
        if (response.success) {
          Message.success('项目删除成功');
          // 刷新项目列表
          fetchProjectList();
        } else {
          Message.error(response.error || '删除项目失败');
        }
      } catch (error) {
        console.error('删除项目出错:', error);
        Message.error('删除项目时发生错误');
      }
    }
  });
};
</script>

<style scoped>
.project-management {
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

.action-buttons {
  display: flex;
  gap: 10px;
}

.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
}

.members-header {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}

.no-data {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 40px 0;
}

.no-permission-panel {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
  padding: 40px 20px;
}

.no-permission-content {
  text-align: center;
  background: #f9f9f9;
  padding: 40px 32px;
  border-radius: 12px;
  border: 1px solid #e8e8e8;
  max-width: 400px;
  width: 100%;
}

.icon-container {
  margin-bottom: 20px;
}

.permission-icon {
  width: 48px;
  height: 48px;
  opacity: 0.8;
}

.no-permission-content h3 {
  font-size: 18px;
  font-weight: 600;
  color: #262626;
  margin-bottom: 12px;
  margin-top: 0;
}

.no-permission-content p {
  font-size: 14px;
  color: #595959;
  margin-bottom: 24px;
  line-height: 1.5;
}

/* 文本省略样式 */
.ellipsis-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  width: 100%;
  display: block;
  box-sizing: border-box;
}

/* 确保表格单元格也遵循省略规则 */
:deep(.arco-table-td) {
  overflow: hidden;
}

:deep(.arco-table-cell) {
  overflow: hidden;
}

/* 强制表格使用固定布局以确保列宽度生效 */
:deep(.arco-table-container .arco-table-element) {
  table-layout: fixed;
}

/* 确保tooltip内容换行显示 */
:deep(.arco-tooltip-content-inner) {
  max-width: 300px;
  white-space: normal;
  word-break: break-word;
}
</style>
