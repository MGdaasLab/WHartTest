<template>
  <div class="remote-mcp-management">
    <div class="page-header">
      <h2>{{ pageText.pageTitle }}</h2>
      <a-button type="primary" @click="showAddForm">{{ pageText.addRemoteMcp }}</a-button>
    </div>

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
            {{ record.is_active ? pageText.enabled : pageText.disabled }}
          </a-tag>
        </template>

        <template #created_at="{ record }">
          {{ formatDate(record.created_at) }}
        </template>

        <template #operations="{ record }">
          <a-space>
            <a-button type="text" size="small" @click="showEditForm(record)">
              <template #icon><icon-edit /></template>
              {{ pageText.edit }}
            </a-button>
            <a-button type="text" status="danger" size="small" @click="showDeleteConfirm(record)">
              <template #icon><icon-delete /></template>
              {{ pageText.delete }}
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
              {{ record.is_active ? pageText.disable : pageText.enable }}
            </a-button>
            <a-button
              type="text"
              status="success"
              size="small"
              @click="pingConfig(record)"
              :loading="record.pinging"
            >
              <template #icon><icon-link /></template>
              {{ pageText.checkConnectivity }}
            </a-button>
          </a-space>
        </template>
      </a-table>

      <div v-if="mcpConfigs.length === 0 && !loading" class="empty-data">
        <p>{{ pageText.noData }}</p>
      </div>
      <div v-if="mcpConfigs.length > 0" class="debug-info">
        <p>{{ pageText.currentDataCount(mcpConfigs.length) }}</p>
      </div>
    </a-card>

    <a-modal
      v-model:visible="modalVisible"
      :title="isEditing ? pageText.editRemoteMcpTitle : pageText.addRemoteMcpTitle"
      :ok-text="pageText.confirm"
      :cancel-text="pageText.cancel"
      @cancel="closeModal"
      @before-ok="handleSubmit"
    >
      <a-form ref="formRef" :model="formData" :rules="formRules" label-align="left">
        <a-form-item field="name" :label="pageText.name" required>
          <a-input v-model="formData.name" :placeholder="pageText.namePlaceholder" />
        </a-form-item>
        <a-form-item field="url" :label="pageText.url" required>
          <a-input v-model="formData.url" :placeholder="pageText.urlPlaceholder" />
        </a-form-item>
        <a-form-item field="transport" :label="pageText.transport" required>
          <a-select v-model="formData.transport" :placeholder="pageText.transportPlaceholder">
            <a-option value="stdio">stdio</a-option>
            <a-option value="streamable_http">streamable_http</a-option>
            <a-option value="sse">sse</a-option>
          </a-select>
        </a-form-item>
        <a-form-item field="headers" :label="pageText.headers">
          <a-textarea
            v-model="formData.headersStr"
            :placeholder="pageText.headersPlaceholder"
            :auto-size="{ minRows: 3, maxRows: 5 }"
          />
        </a-form-item>
        <a-form-item field="is_active" :label="pageText.status">
          <a-switch v-model="formData.is_active" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:visible="deleteModalVisible"
      :title="pageText.deleteConfirmTitle"
      :ok-text="pageText.confirm"
      :cancel-text="pageText.cancel"
      @ok="handleDelete"
      @cancel="deleteModalVisible = false"
      simple
    >
      <p>{{ pageText.deleteConfirmContent(currentConfig?.name || '') }}</p>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue';
import { Message } from '@arco-design/web-vue';
import {
  IconEdit,
  IconDelete,
  IconEye,
  IconEyeInvisible,
  IconLink,
} from '@arco-design/web-vue/es/icon';
import {
  fetchRemoteMcpConfigs,
  createRemoteMcpConfig,
  updateRemoteMcpConfig,
  deleteRemoteMcpConfig,
  pingRemoteMcpConfig,
  type RemoteMcpConfig,
} from '@/services/remoteMcpConfigService';
import { useAppI18n } from '@/composables/useAppI18n';

const { isEnglish } = useAppI18n();
const pageText = computed(() => (
  isEnglish.value
    ? {
        pageTitle: 'MCP Configuration Management',
        addRemoteMcp: 'Add Remote MCP',
        enabled: 'Enabled',
        disabled: 'Disabled',
        edit: 'Edit',
        delete: 'Delete',
        enable: 'Enable',
        disable: 'Disable',
        checkConnectivity: 'Check connectivity',
        noData: 'No data',
        currentDataCount: (count: number) => `Current records: ${count}`,
        editRemoteMcpTitle: 'Edit Remote MCP Config',
        addRemoteMcpTitle: 'Add Remote MCP Config',
        confirm: 'Confirm',
        cancel: 'Cancel',
        name: 'Name',
        namePlaceholder: 'Enter config name',
        url: 'URL',
        urlPlaceholder: 'Enter MCP server URL',
        transport: 'Transport',
        transportPlaceholder: 'Select transport',
        headers: 'Headers',
        headersPlaceholder: 'Enter headers in JSON format, e.g. {"Authorization": "Bearer token"}',
        status: 'Status',
        nameColumn: 'Name',
        statusColumn: 'Status',
        createdAtColumn: 'Created at',
        actionsColumn: 'Actions',
        nameRequired: 'Enter config name',
        urlRequired: 'Enter MCP server URL',
        urlInvalid: 'URL must start with http:// or https://',
        headersInvalid: 'Headers must be valid JSON',
        fetchListFailed: 'Failed to fetch remote MCP configs',
        headersFormatIncorrect: 'Invalid headers format',
        updateSuccess: 'Remote MCP config updated successfully',
        createSuccess: 'Remote MCP config added successfully',
        updateFailed: 'Failed to update remote MCP config',
        createFailed: 'Failed to add remote MCP config',
        deleteConfirmTitle: 'Confirm deletion',
        deleteConfirmContent: (name: string) => `Delete remote MCP config "${name}"? This action cannot be undone.`,
        deleteSuccess: 'Remote MCP config deleted successfully',
        deleteFailed: 'Failed to delete remote MCP config',
        disableSuccess: 'Remote MCP config disabled successfully',
        enableSuccess: 'Remote MCP config enabled successfully',
        disableFailed: 'Failed to disable remote MCP config',
        enableFailed: 'Failed to enable remote MCP config',
        responseTime: (time: number) => `Response time: ${time}ms`,
        connectionFailed: (message: string) => `Connection failed: ${message}`,
        connectivityCheckFailed: 'Connectivity check failed, please try again later',
      }
    : {
        pageTitle: 'MCP配置管理',
        addRemoteMcp: '添加远程MCP',
        enabled: '启用',
        disabled: '禁用',
        edit: '编辑',
        delete: '删除',
        enable: '启用',
        disable: '禁用',
        checkConnectivity: '检查连通性',
        noData: '暂无数据',
        currentDataCount: (count: number) => `当前数据条数: ${count}`,
        editRemoteMcpTitle: '编辑远程MCP配置',
        addRemoteMcpTitle: '添加远程MCP配置',
        confirm: '确认',
        cancel: '取消',
        name: '名称',
        namePlaceholder: '请输入配置名称',
        url: 'URL',
        urlPlaceholder: '请输入MCP服务器URL',
        transport: '通信方式',
        transportPlaceholder: '请选择通信方式',
        headers: '请求头',
        headersPlaceholder: '请输入请求头 (JSON格式, 例如: {"Authorization": "Bearer token"})',
        status: '状态',
        nameColumn: '名称',
        statusColumn: '状态',
        createdAtColumn: '创建时间',
        actionsColumn: '操作',
        nameRequired: '请输入配置名称',
        urlRequired: '请输入MCP服务器URL',
        urlInvalid: 'URL必须以http://或https://开头',
        headersInvalid: '请求头必须是有效的JSON格式',
        fetchListFailed: '获取远程MCP配置列表失败',
        headersFormatIncorrect: '请求头格式不正确',
        updateSuccess: '更新远程MCP配置成功',
        createSuccess: '添加远程MCP配置成功',
        updateFailed: '更新远程MCP配置失败',
        createFailed: '添加远程MCP配置失败',
        deleteConfirmTitle: '确认删除',
        deleteConfirmContent: (name: string) => `确定要删除远程MCP配置 "${name}" 吗？此操作不可撤销。`,
        deleteSuccess: '删除远程MCP配置成功',
        deleteFailed: '删除远程MCP配置失败',
        disableSuccess: '禁用远程MCP配置成功',
        enableSuccess: '启用远程MCP配置成功',
        disableFailed: '禁用远程MCP配置失败',
        enableFailed: '启用远程MCP配置失败',
        responseTime: (time: number) => `响应时间: ${time}ms`,
        connectionFailed: (message: string) => `连接失败: ${message}`,
        connectivityCheckFailed: '检查连通性失败，请稍后重试',
      }
));

const mcpConfigs = ref<RemoteMcpConfig[]>([]);
const loading = ref(false);
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
});

const columns = computed(() => [
  {
    title: pageText.value.nameColumn,
    dataIndex: 'name',
  },
  {
    title: 'URL',
    dataIndex: 'url',
  },
  {
    title: pageText.value.statusColumn,
    dataIndex: 'is_active',
    slotName: 'is_active',
  },
  {
    title: pageText.value.createdAtColumn,
    dataIndex: 'created_at',
    slotName: 'created_at',
  },
  {
    title: pageText.value.actionsColumn,
    slotName: 'operations',
    align: 'center',
  },
]);

const formRef = ref();
const formData = reactive({
  id: undefined as number | undefined,
  name: '',
  url: '',
  transport: 'streamable_http' as RemoteMcpConfig['transport'],
  headersStr: '',
  is_active: true,
});

const formRules = computed(() => ({
  name: [{ required: true, message: pageText.value.nameRequired }],
  url: [
    { required: true, message: pageText.value.urlRequired },
    {
      match: /^https?:\/\/.+/,
      message: pageText.value.urlInvalid,
    },
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
      message: pageText.value.headersInvalid,
    },
  ],
}));

const modalVisible = ref(false);
const deleteModalVisible = ref(false);
const isEditing = ref(false);
const currentConfig = ref<RemoteMcpConfig | null>(null);

const loadMcpConfigs = async () => {
  loading.value = true;
  try {
    const data = await fetchRemoteMcpConfigs();
    mcpConfigs.value = Array.isArray(data) ? data : [];
    pagination.total = mcpConfigs.value.length;
  } catch (error) {
    Message.error(pageText.value.fetchListFailed);
    mcpConfigs.value = [];
    pagination.total = 0;
  } finally {
    loading.value = false;
  }
};

const onPageChange = (page: number) => {
  pagination.current = page;
};

const onPageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize;
};

const formatDate = (dateStr?: string) => {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleString(isEnglish.value ? 'en-US' : 'zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

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

const closeModal = () => {
  formRef.value?.resetFields();
  modalVisible.value = false;
};

const handleSubmit = async (done: (closed: boolean) => void) => {
  const result = await formRef.value?.validate();
  if (result) {
    done(false);
    return;
  }

  try {
    let headers = {};
    if (formData.headersStr) {
      try {
        headers = JSON.parse(formData.headersStr);
      } catch (e) {
        Message.error(pageText.value.headersFormatIncorrect);
        done(false);
        return;
      }
    }

    const configData: RemoteMcpConfig = {
      name: formData.name,
      url: formData.url,
      transport: formData.transport,
      headers,
      is_active: formData.is_active,
    };

    if (isEditing.value && formData.id) {
      await updateRemoteMcpConfig(formData.id, configData);
      Message.success(pageText.value.updateSuccess);
    } else {
      await createRemoteMcpConfig(configData);
      Message.success(pageText.value.createSuccess);
    }

    await loadMcpConfigs();
    done(true);
  } catch (error) {
    Message.error(isEditing.value ? pageText.value.updateFailed : pageText.value.createFailed);
    done(false);
  }
};

const showDeleteConfirm = (record: RemoteMcpConfig) => {
  currentConfig.value = record;
  deleteModalVisible.value = true;
};

const handleDelete = async () => {
  if (!currentConfig.value?.id) return;

  try {
    await deleteRemoteMcpConfig(currentConfig.value.id);
    Message.success(pageText.value.deleteSuccess);
    await loadMcpConfigs();
  } catch (error) {
    Message.error(pageText.value.deleteFailed);
  } finally {
    deleteModalVisible.value = false;
  }
};

const toggleStatus = async (record: RemoteMcpConfig) => {
  if (!record.id) return;

  try {
    await updateRemoteMcpConfig(record.id, {
      is_active: !record.is_active,
    });
    Message.success(record.is_active ? pageText.value.disableSuccess : pageText.value.enableSuccess);
    await loadMcpConfigs();
  } catch (error) {
    Message.error(record.is_active ? pageText.value.disableFailed : pageText.value.enableFailed);
  }
};

const pingConfig = async (record: RemoteMcpConfig) => {
  if (!record.id) return;

  mcpConfigs.value = mcpConfigs.value.map(config =>
    config.id === record.id ? { ...config, pinging: true } : config
  );

  try {
    const result = await pingRemoteMcpConfig(record.id);

    if (result.success) {
      let successMessage = result.message;
      if (result.response_time !== undefined) {
        successMessage += ` (${pageText.value.responseTime(result.response_time)})`;
      }
      Message.success(successMessage);
    } else {
      Message.error(pageText.value.connectionFailed(result.message));
    }
  } catch (error) {
    Message.error(pageText.value.connectivityCheckFailed);
  } finally {
    mcpConfigs.value = mcpConfigs.value.map(config =>
      config.id === record.id ? { ...config, pinging: false } : config
    );
  }
};

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

.debug-info {
  margin-top: 10px;
  font-size: 12px;
  color: var(--theme-text-tertiary);
}
</style>
