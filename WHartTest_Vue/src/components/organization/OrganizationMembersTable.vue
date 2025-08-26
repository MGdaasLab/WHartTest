<template>
  <div class="organization-members">
    <div class="table-header">
      <div class="search-box">
        <a-input-search
          placeholder="搜索用户名/邮箱"
          allow-clear
          style="width: 300px"
          @search="onSearch"
        />
      </div>
      <div class="action-buttons">
        <a-button type="primary" @click="showAddMembersModal">添加成员</a-button>
      </div>
    </div>

    <a-table
      :columns="columns"
      :data="membersData"
      :pagination="pagination"
      :loading="loading"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
    >
      <template #operations="{ record }">
        <a-space>
          <a-button type="primary" status="danger" size="small" @click="removeMember(record)">移除</a-button>
        </a-space>
      </template>
    </a-table>

    <!-- 添加成员模态框 -->
    <a-modal
      v-model:visible="addMembersModalVisible"
      title="添加成员"
      @cancel="cancelAddMembers"
      @before-ok="handleAddMembers"
      :mask-closable="false"
      :width="600"
    >
      <a-form ref="addMembersFormRef" :model="addMembersForm" layout="vertical" :auto-label-width="false">
        <a-form-item field="userIds" label="选择用户" required>
          <a-select
            v-model="addMembersForm.userIds"
            placeholder="请选择用户"
            multiple
            :options="availableUsers"
            :filter-option="true"
            :max-tag-count="5"
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
  getOrganizationUsers,
  addUsersToOrganization,
  removeUsersFromOrganization,
  type OrganizationUser
} from '@/services/organizationService';
import { getUserList, type User } from '@/services/userService';

const props = defineProps<{
  organizationId: number;
}>();

const emit = defineEmits<{
  (e: 'refresh'): void;
}>();

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
    render: ({ record }: { record: OrganizationUser }) => {
      const fullName = [record.first_name, record.last_name].filter(Boolean).join(' ');
      return fullName || '-';
    },
  },
  {
    title: '操作',
    slotName: 'operations',
    width: 100,
  },
];

// 成员数据
const membersData = ref<OrganizationUser[]>([]);

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

// 获取组织成员列表数据
const fetchMembersList = async () => {
  if (!props.organizationId) return;

  loading.value = true;
  try {
    const response = await getOrganizationUsers(props.organizationId, {
      page: pagination.current,
      pageSize: pagination.pageSize,
      search: searchKeyword.value
    });

    if (response.success && response.data) {
      membersData.value = response.data;
      pagination.total = response.total || response.data.length;
    } else {
      Message.error(response.error || '获取组织成员列表失败');
      membersData.value = [];
      pagination.total = 0;
    }
  } catch (error) {
    console.error('获取组织成员列表出错:', error);
    Message.error('获取组织成员列表时发生错误');
    membersData.value = [];
    pagination.total = 0;
  } finally {
    loading.value = false;
  }
};

// 搜索成员
const onSearch = (value: string) => {
  searchKeyword.value = value;
  pagination.current = 1; // 重置到第一页
  fetchMembersList();
};

// 分页变化
const onPageChange = (page: number) => {
  pagination.current = page;
  fetchMembersList();
};

// 每页显示数量变化
const onPageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize;
  pagination.current = 1; // 重置到第一页
  fetchMembersList();
};

// 在组件挂载时加载成员数据
onMounted(() => {
  if (props.organizationId) {
    fetchMembersList();
  }
});

// 监听组织ID变化
watch(() => props.organizationId, (newId) => {
  if (newId) {
    pagination.current = 1; // 重置到第一页
    fetchMembersList();
  }
});

// 可用用户列表
const availableUsers = ref<{ label: string; value: number }[]>([]);

// 获取所有用户列表
const fetchAllUsers = async () => {
  try {
    const response = await getUserList({
      page: 1,
      pageSize: 100, // 获取较多用户
    });

    if (response.success && response.data) {
      // 过滤掉已经是组织成员的用户
      const memberIds = membersData.value.map(member => member.id);
      const filteredUsers = response.data.filter(user => !memberIds.includes(user.id));

      // 转换为下拉选择框需要的格式
      availableUsers.value = filteredUsers.map(user => ({
        label: `${user.username} (${user.email})`,
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
  }
};

// 添加成员模态框相关
const addMembersModalVisible = ref(false);
const addMembersFormRef = ref();
const addMembersForm = reactive({
  userIds: [] as number[]
});

// 显示添加成员模态框
const showAddMembersModal = async () => {
  // 重置表单
  addMembersForm.userIds = [];

  // 获取可用用户列表
  await fetchAllUsers();

  // 显示模态框
  addMembersModalVisible.value = true;
};

// 取消添加成员
const cancelAddMembers = () => {
  addMembersModalVisible.value = false;
};

// 处理添加成员
const handleAddMembers = async (done: (closed: boolean) => void) => {
  if (!props.organizationId) {
    Message.error('组织ID无效');
    done(false);
    return;
  }

  if (addMembersForm.userIds.length === 0) {
    Message.warning('请选择至少一个用户');
    done(false);
    return;
  }

  try {
    const response = await addUsersToOrganization(props.organizationId, addMembersForm.userIds);

    if (response.success) {
      Message.success(response.message || '成员添加成功');
      // 刷新成员列表
      fetchMembersList();
      // 通知父组件刷新
      emit('refresh');
      done(true); // 关闭模态框
    } else {
      Message.error(response.error || '添加成员失败');
      done(false); // 不关闭模态框
    }
  } catch (error) {
    console.error('添加成员出错:', error);
    Message.error('添加成员时发生错误');
    done(false); // 不关闭模态框
  }
};

// 移除成员
const removeMember = (member: OrganizationUser) => {
  if (!props.organizationId) {
    Message.error('组织ID无效');
    return;
  }

  Modal.warning({
    title: '确认移除',
    content: `确定要将用户 "${member.username}" 从组织中移除吗？`,
    okText: '确定移除',
    cancelText: '取消',
    onOk: async () => {
      try {
        const response = await removeUsersFromOrganization(props.organizationId, [member.id]);

        if (response.success) {
          Message.success(response.message || '成员移除成功');
          // 刷新成员列表
          fetchMembersList();
          // 通知父组件刷新
          emit('refresh');
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
</script>

<style scoped>
.organization-members {
  margin-top: 20px;
}

.table-header {
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
