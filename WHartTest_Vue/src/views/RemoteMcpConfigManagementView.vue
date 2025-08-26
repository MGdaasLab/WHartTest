<template>
  <div class="remote-mcp-management">
    <div class="page-header">
      <h2>MCP配置管理</h2>
      <a-button type="primary" @click="showAddForm">添加远程MCP</a-button>
    </div>

    <!-- 远程MCP配置列表 -->
    <a-card class="content-card">
      <a-table
        :data="mcpConfigs"
        :columns="columns"
        :loading="loading"
        :pagination="pagination"
        @page-change="onPageChange"
        @page-size-change="onPageSizeChange"
        row-key="id"
      >
        <template #is_active="{ record }">
          <a-tag :color="record.is_active ? 'green' : 'red'">
            {{ record.is_active ? '启用' : '禁用' }}
          </a-tag>
        </template>

        <template #created_at="{ record }">
          {{ formatDate(record.created_at) }}
        </template>

        <template #operations="{ record }">
          <a-space>
            <a-button type="text" size="small" @click="showEditForm(record)">
              <template #icon><icon-edit /></template>
              编辑
            </a-button>
            <a-button type="text" status="danger" size="small" @click="showDeleteConfirm(record)">
              <template #icon><icon-delete /></template>
              删除
            </a-button>
            <a-button
              type="text"
              :status="record.is_active ? 'warning' : 'success'"
              size="small"
              @click="toggleStatus(record)"
            >
              <template #icon>
                <icon-eye-invisible v-if="record.is_active" />
                <icon-eye v-else />
              </template>
              {{ record.is_active ? '禁用' : '启用' }}
            </a-button>
            <a-button
              type="text"
              status="success"
              size="small"
              @click="pingConfig(record)"
              :loading="record.pinging"
            >
              <template #icon><icon-link /></template>
              检查连通性
            </a-button>
          </a-space>
        </template>
      </a-table>

      <!-- 调试信息 -->
      <div v-if="mcpConfigs.length === 0 && !loading" class="empty-data">
        <p>暂无数据</p>
      </div>
      <div v-if="mcpConfigs.length > 0" class="debug-info" style="margin-top: 10px; font-size: 12px; color: #999;">
        <p>当前数据条数: {{ mcpConfigs.length }}</p>
      </div>
    </a-card>

    <!-- 添加/编辑远程MCP配置的弹窗 -->
    <a-modal
      v-model:visible="modalVisible"
      :title="isEditing ? '编辑远程MCP配置' : '添加远程MCP配置'"
      @cancel="closeModal"
      @before-ok="handleSubmit"
    >
      <a-form ref="formRef" :model="formData" :rules="formRules" label-align="left">
        <a-form-item field="name" label="名称" required>
          <a-input v-model="formData.name" placeholder="请输入配置名称" />
        </a-form-item>
        <a-form-item field="url" label="URL" required>
          <a-input v-model="formData.url" placeholder="请输入MCP服务器URL" />
        </a-form-item>
        <a-form-item field="transport" label="通信方式" required>
          <a-select v-model="formData.transport" placeholder="请选择通信方式">
            <a-option value="stdio">stdio</a-option>
            <a-option value="streamable_http">streamable_http</a-option>
            <a-option value="sse">sse</a-option>
          </a-select>
        </a-form-item>
        <a-form-item field="headers" label="请求头">
          <a-textarea
            v-model="formData.headersStr"
            placeholder='请输入请求头 (JSON格式, 例如: {"Authorization": "Bearer token"})'
            :auto-size="{ minRows: 3, maxRows: 5 }"
          />
        </a-form-item>
        <a-form-item field="is_active" label="状态">
          <a-switch v-model="formData.is_active" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 删除确认弹窗 -->
    <a-modal
      v-model:visible="deleteModalVisible"
      title="确认删除"
      @ok="handleDelete"
      @cancel="deleteModalVisible = false"
      simple
    >
      <p>确定要删除远程MCP配置 "{{ currentConfig?.name }}" 吗？此操作不可撤销。</p>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue';
import { Message } from '@arco-design/web-vue';
import {
  IconEdit,
  IconDelete,
  IconEye,
  IconEyeInvisible,
  IconLink
} from '@arco-design/web-vue/es/icon';
import {
  fetchRemoteMcpConfigs,
  createRemoteMcpConfig,
  updateRemoteMcpConfig,
  deleteRemoteMcpConfig,
  pingRemoteMcpConfig,
  type RemoteMcpConfig
} from '@/services/remoteMcpConfigService';
import { useProjectStore } from '@/store/projectStore';

const projectStore = useProjectStore();

// 表格数据和加载状态
const mcpConfigs = ref<RemoteMcpConfig[]>([]);
const loading = ref(false);
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
});

// 表格列定义
const columns = [
  {
    title: '名称',
    dataIndex: 'name',
  },
  {
    title: 'URL',
    dataIndex: 'url',
  },
  {
    title: '状态',
    dataIndex: 'is_active',
    slotName: 'is_active',
  },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    slotName: 'created_at',
  },
  {
    title: '操作',
    slotName: 'operations',
    align: 'center',
  },
];

// 表单数据和验证规则
const formRef = ref();
const formData = reactive({
  id: undefined as number | undefined,
  name: '',
  url: '',
  transport: 'streamable_http',
  headersStr: '',
  is_active: true,
});

const formRules = {
  name: [{ required: true, message: '请输入配置名称' }],
  url: [
    { required: true, message: '请输入MCP服务器URL' },
    {
      match: /^https?:\/\/.+/,
      message: 'URL必须以http://或https://开头'
    }
  ],
  headersStr: [
    {
      validator: (value: string) => {
        if (!value) return true;
        try {
          JSON.parse(value);
          return true;
        } catch (e) {
          return false;
        }
      },
      message: '请求头必须是有效的JSON格式'
    }
  ]
};

// 弹窗状态
const modalVisible = ref(false);
const deleteModalVisible = ref(false);
const isEditing = ref(false);
const currentConfig = ref<RemoteMcpConfig | null>(null);

// 加载远程MCP配置列表
const loadMcpConfigs = async () => {
  loading.value = true;
  try {
    console.log('开始加载MCP配置数据...');
    const data = await fetchRemoteMcpConfigs();
    console.log('API返回的原始数据:', data);
    mcpConfigs.value = Array.isArray(data) ? data : [];
    pagination.total = mcpConfigs.value.length;
    console.log('处理后的MCP配置数据:', mcpConfigs.value);
  } catch (error) {
    console.error('获取远程MCP配置列表失败:', error);
    Message.error('获取远程MCP配置列表失败');
    mcpConfigs.value = []; // 确保在出错时也设置为空数组
    pagination.total = 0;
  } finally {
    loading.value = false; // 确保无论如何都会结束加载状态
  }
};

// 分页相关方法
const onPageChange = (page: number) => {
  pagination.current = page;
};

const onPageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize;
};

// 格式化日期
const formatDate = (dateStr?: string) => {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
};

// 显示添加表单
const showAddForm = () => {
  isEditing.value = false;
  formData.id = undefined;
  formData.name = '';
  formData.url = '';
  formData.transport = 'streamable_http';
  formData.headersStr = '';
  formData.is_active = true;
  modalVisible.value = true;
};

// 显示编辑表单
const showEditForm = (record: RemoteMcpConfig) => {
  isEditing.value = true;
  formData.id = record.id;
  formData.name = record.name;
  formData.url = record.url;
  formData.transport = record.transport;
  formData.headersStr = record.headers ? JSON.stringify(record.headers) : '';
  formData.is_active = record.is_active;
  modalVisible.value = true;
};

// 关闭表单弹窗
const closeModal = () => {
  formRef.value?.resetFields();
  modalVisible.value = false;
};

// 提交表单
const handleSubmit = async (done: (closed: boolean) => void) => {
  const result = await formRef.value?.validate();
  if (result) {
    done(false); // 表单验证失败，不关闭弹窗
    return;
  }

  try {
    // 解析headers字符串为对象
    let headers = {};
    if (formData.headersStr) {
      try {
        headers = JSON.parse(formData.headersStr);
      } catch (e) {
        Message.error('请求头格式不正确');
        done(false);
        return;
      }
    }

    const configData: RemoteMcpConfig = {
      name: formData.name,
      url: formData.url,
      transport: formData.transport,
      headers,
      is_active: formData.is_active
    };

    if (isEditing.value && formData.id) {
      // 更新配置
      await updateRemoteMcpConfig(formData.id, configData);
      Message.success('更新远程MCP配置成功');
    } else {
      // 创建新配置
      await createRemoteMcpConfig(configData);
      Message.success('添加远程MCP配置成功');
    }

    await loadMcpConfigs(); // 重新加载列表
    done(true); // 关闭弹窗
  } catch (error) {
    Message.error(isEditing.value ? '更新远程MCP配置失败' : '添加远程MCP配置失败');
    done(false); // 不关闭弹窗
  }
};

// 显示删除确认弹窗
const showDeleteConfirm = (record: RemoteMcpConfig) => {
  currentConfig.value = record;
  deleteModalVisible.value = true;
};

// 处理删除操作
const handleDelete = async () => {
  if (!currentConfig.value?.id) return;

  try {
    await deleteRemoteMcpConfig(currentConfig.value.id);
    Message.success('删除远程MCP配置成功');
    await loadMcpConfigs(); // 重新加载列表
  } catch (error) {
    Message.error('删除远程MCP配置失败');
  } finally {
    deleteModalVisible.value = false;
  }
};

// 切换配置状态
const toggleStatus = async (record: RemoteMcpConfig) => {
  if (!record.id) return;

  try {
    await updateRemoteMcpConfig(record.id, {
      is_active: !record.is_active
    });
    Message.success(`${record.is_active ? '禁用' : '启用'}远程MCP配置成功`);
    await loadMcpConfigs(); // 重新加载列表
  } catch (error) {
    Message.error(`${record.is_active ? '禁用' : '启用'}远程MCP配置失败`);
  }
};

// 添加ping功能
const pingConfig = async (record: RemoteMcpConfig) => {
  if (!record.id) return;

  // 设置当前记录的pinging状态为true
  mcpConfigs.value = mcpConfigs.value.map(config =>
    config.id === record.id ? { ...config, pinging: true } : config
  );

  try {
    const result = await pingRemoteMcpConfig(record.id);

    if (result.success) {
      let successMessage = result.message;
      if (result.response_time !== undefined) {
        successMessage += ` (响应时间: ${result.response_time}ms)`;
      }
      Message.success(successMessage);
    } else {
      Message.error(`连接失败: ${result.message}`);
    }
  } catch (error) {
    Message.error('检查连通性失败，请稍后重试');
  } finally {
    // 重置pinging状态
    mcpConfigs.value = mcpConfigs.value.map(config =>
      config.id === record.id ? { ...config, pinging: false } : config
    );
  }
};

// 监听项目变化，重新加载数据
watch(() => projectStore.currentProjectId, (newProjectId, oldProjectId) => {
  if (newProjectId !== oldProjectId) {
    // 项目切换时重置状态
    pagination.current = 1;

    // 重新获取远程MCP配置列表
    loadMcpConfigs();
  }
}, { immediate: false });

// 组件挂载时加载数据
onMounted(() => {
  loadMcpConfigs();
});
</script>

<style scoped>
.remote-mcp-management {
  padding: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.content-card {
  margin-bottom: 16px;
}
</style>